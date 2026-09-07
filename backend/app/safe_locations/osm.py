"""Live place lookup via OpenStreetMap (Nominatim + Overpass).

Used as the fallback when the requested city is outside the curated Sindh
registry, so a user in any city or country still gets real shelters, hospitals
and police stations nearby.

Every call is best-effort. OSM is a shared public service with rate limits and
Overpass 504s on heavy queries, so:

* failures return an empty result rather than raising, and the caller tells the
  UI that live lookup was unavailable;
* a failed lookup is cached only for ``NEGATIVE_CACHE_TTL_SECONDS`` so one
  timeout does not blind the app to a city for the full success TTL;
* a timed-out Overpass query is retried once over a much smaller radius.
"""
from __future__ import annotations

import math
import time

import httpx

from ..core import config
from ..core.logging_conf import get_logger

log = get_logger(__name__)

SOURCE = "OpenStreetMap contributors"

# OSM amenity value -> our internal category. Overpass returns raw tags such as
# {"amenity": "police"}, so the lookup key is the tag *value*, not the tag name.
_AMENITY_CATEGORY = {
    "hospital": "hospital",
    "clinic": "hospital",
    "doctors": "hospital",
    "police": "police",
    "fire_station": "rescue",
    "shelter": "shelter",
}

# `nwr` matches nodes, ways and relations in one statement, which keeps the
# query small enough for Overpass to answer inside its timeout.
_OVERPASS_SELECTORS = (
    'nwr["amenity"="hospital"]({box});',
    'nwr["amenity"="clinic"]({box});',
    'nwr["amenity"="doctors"]({box});',
    'nwr["amenity"="police"]({box});',
    'nwr["amenity"="fire_station"]({box});',
    'nwr["amenity"="shelter"]({box});',
    'nwr["social_facility"="shelter"]({box});',
)

# key -> (stored_at, payload, ttl). Negative results carry a short TTL.
_cache: dict[str, tuple[float, object, float]] = {}


def clear_cache() -> None:
    _cache.clear()


def _cached(key: str) -> object | None:
    entry = _cache.get(key)
    if entry is None:
        return None
    at, payload, ttl = entry
    if time.time() - at >= ttl:
        _cache.pop(key, None)
        return None
    return payload


def _store(key: str, payload: object, ttl: float) -> None:
    _cache[key] = (time.time(), payload, ttl)


def _store_negative(key: str) -> None:
    _store(key, [], config.NEGATIVE_CACHE_TTL_SECONDS)


def _get(url: str, *, timeout: int, **kwargs) -> httpx.Response:
    # OpenStreetMap blocks clients that do not identify themselves.
    headers = {"User-Agent": config.OSM_USER_AGENT, "Accept-Language": "en"}
    headers.update(kwargs.pop("headers", None) or {})
    return httpx.get(url, timeout=timeout, follow_redirects=True, headers=headers, **kwargs)


def geocode(query: str, limit: int = 5) -> list[dict]:
    """Resolve a free-text city/country query to places with coordinates.

    Returns [] when live lookup is disabled or OSM is unreachable.
    """
    query = (query or "").strip()
    if not query or not config.LIVE_GEO_ENABLED:
        return []
    key = f"geocode:{query.lower()}:{limit}"
    hit = _cached(key)
    if hit is not None:
        return list(hit)  # type: ignore[arg-type]

    try:
        resp = _get(
            config.NOMINATIM_URL,
            timeout=config.LIVE_GEO_TIMEOUT_SECONDS,
            params={"q": query, "format": "jsonv2", "limit": limit, "addressdetails": 1},
        )
        resp.raise_for_status()
        raw = resp.json()
    except Exception as exc:  # noqa: BLE001 - any network/parse failure is non-fatal
        log.warning("nominatim geocode failed for %r: %s", query, exc)
        _store_negative(key)
        return []

    places: list[dict] = []
    for row in raw if isinstance(raw, list) else []:
        try:
            lat = float(row["lat"])
            lon = float(row["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        address = row.get("address") or {}
        city = (
            address.get("city")
            or address.get("town")
            or address.get("municipality")
            or address.get("county")
            or address.get("village")
        )
        places.append(
            {
                "name": city or row.get("name") or query,
                "display_name": row.get("display_name") or query,
                "country": address.get("country"),
                "country_code": (address.get("country_code") or "").upper() or None,
                "latitude": lat,
                "longitude": lon,
                "place_type": row.get("type"),
                "importance": row.get("importance"),
            }
        )
    if not places:
        _store_negative(key)
        return []
    _store(key, places, config.LIVE_GEO_CACHE_TTL_SECONDS)
    return places


def _bbox(lat: float, lng: float, radius_km: float) -> str:
    """Overpass bounding box in the south,west,north,east order it expects."""
    delta_lat = radius_km / 111.0
    # Clamp so a high-latitude city cannot divide by ~zero and span the globe.
    cos_lat = max(0.1, abs(math.cos(math.radians(lat))))
    delta_lng = radius_km / (111.0 * cos_lat)
    return f"{lat - delta_lat:.5f},{lng - delta_lng:.5f},{lat + delta_lat:.5f},{lng + delta_lng:.5f}"


def _category_for(tags: dict) -> str | None:
    amenity = tags.get("amenity")
    if amenity in _AMENITY_CATEGORY:
        return _AMENITY_CATEGORY[amenity]
    if tags.get("social_facility") == "shelter":
        return "shelter"
    return None


def _coordinates(element: dict) -> tuple[float, float] | None:
    """Ways and relations carry their position under `center`; nodes do not."""
    if element.get("lat") is not None and element.get("lon") is not None:
        return (float(element["lat"]), float(element["lon"]))
    center = element.get("center") or {}
    if center.get("lat") is not None and center.get("lon") is not None:
        return (float(center["lat"]), float(center["lon"]))
    return None


# Timestamp before which Overpass calls are skipped because a mirror returned 429.
_cooldown_until = 0.0


def _build_query(lat: float, lng: float, radius_km: float, timeout: int) -> str:
    box = _bbox(lat, lng, radius_km)
    # The in-query timeout must be shorter than the HTTP timeout so Overpass
    # answers with a partial result instead of the gateway timing out.
    query_timeout = max(5, timeout - 5)
    return (
        f"[out:json][timeout:{query_timeout}];("
        + "".join(selector.format(box=box) for selector in _OVERPASS_SELECTORS)
        + f");out center tags {config.SAFE_LOCATION_MAX_RESULTS * 4};"
    )


def rate_limited() -> bool:
    """True while backing off from a 429."""
    return time.time() < _cooldown_until


def _enter_cooldown() -> None:
    global _cooldown_until
    _cooldown_until = time.time() + config.OVERPASS_COOLDOWN_SECONDS
    log.warning(
        "overpass rate-limited (429) — pausing live lookups for %ss",
        config.OVERPASS_COOLDOWN_SECONDS,
    )


def _parse_elements(payload: object) -> list[dict]:
    results: list[dict] = []
    for element in payload.get("elements", []) if isinstance(payload, dict) else []:
        tags = element.get("tags") or {}
        category = _category_for(tags)
        if category is None:
            continue
        position = _coordinates(element)
        if position is None:
            continue
        name = tags.get("name") or tags.get("name:en") or tags.get("operator")
        if not name:
            continue
        results.append(
            {
                "name": name,
                "category": category,
                "area": tags.get("addr:city") or tags.get("addr:suburb")
                or tags.get("addr:street"),
                "latitude": position[0],
                "longitude": position[1],
                "phone": tags.get("phone") or tags.get("contact:phone"),
                "osm_type": element.get("type"),
                "osm_id": element.get("id"),
            }
        )
        if len(results) >= config.SAFE_LOCATION_MAX_RESULTS * 3:
            break
    return results


def _run_overpass(lat: float, lng: float, radius_km: float, timeout: int) -> list[dict] | None:
    """Query each Overpass mirror in turn. None means every endpoint failed."""
    if rate_limited():
        return None
    query = _build_query(lat, lng, radius_km, timeout)
    for url in config.OVERPASS_URLS:
        try:
            resp = _get(url, timeout=timeout, params={"data": query})
            if resp.status_code == 429:
                _enter_cooldown()
                return None
            if resp.status_code >= 500:
                log.warning("overpass %s returned %s", url, resp.status_code)
                continue
            resp.raise_for_status()
            return _parse_elements(resp.json())
        except Exception as exc:  # noqa: BLE001 - one bad mirror must not end the lookup
            log.warning("overpass %s failed at r=%.1fkm: %s", url, radius_km, exc)
            continue
    return None


def nearby(lat: float, lng: float, radius_km: float | None = None) -> list[dict]:
    """Find real shelters, hospitals and police near a point via Overpass.

    Returns [] when live lookup is disabled or OSM is unreachable — the caller
    must treat an empty list as "no live data", never as "no safe places exist".
    """
    if not config.LIVE_GEO_ENABLED:
        return []
    radius = radius_km or config.SAFE_LOCATION_RADIUS_KM
    key = f"nearby:{lat:.4f},{lng:.4f},{radius:.1f}"
    hit = _cached(key)
    if hit is not None:
        return list(hit)  # type: ignore[arg-type]

    if rate_limited():
        # Deliberately not cached: the block lifts on its own and the next
        # request should be allowed to try again immediately.
        return []

    # Dense cities time out on a wide box, so shrink the radius and retry.
    # The timeout shrinks with it: a small box answers fast, and giving every
    # attempt the full budget is what turns one slow city into a 90-second wait.
    divisor = max(1.5, config.OVERPASS_RETRY_RADIUS_DIVISOR)
    attempt_radius = radius
    attempt_timeout = config.OVERPASS_TIMEOUT_SECONDS
    results: list[dict] | None = None
    for _ in range(max(1, config.OVERPASS_MAX_ATTEMPTS)):
        results = _run_overpass(lat, lng, attempt_radius, attempt_timeout)
        if results is not None:
            break
        attempt_radius /= divisor
        attempt_timeout = max(config.OVERPASS_MIN_TIMEOUT_SECONDS, int(attempt_timeout * 0.6))

    if results is None:
        _store_negative(key)
        return []

    _store(key, results, config.LIVE_GEO_CACHE_TTL_SECONDS)
    return results
