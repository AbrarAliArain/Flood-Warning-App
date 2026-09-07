"""Safe-location registry: curated Sindh shelters plus live worldwide fallback.

Two sources, one response shape:

* ``zone_id`` lookups read the curated ``safe_locations`` table, which is seeded
  from :mod:`app.data.safe_locations` and covers all 24 Sindh districts offline.
* free-text city/country lookups go to OpenStreetMap, so a user outside Sindh
  still gets real facilities near them.

Distances are haversine from the caller's coordinates when supplied, otherwise
from the district centroid — and ``distance_basis`` always says which, so an
approximate figure is never presented as a precise one.
"""
from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import quote

from ..core import config
from ..core.logging_conf import get_logger
from ..data import safe_locations as seed
from ..storage.db import get_conn
from ..storage.geo import haversine_km
from ..storage.geo import zone_for_point as _zone_in_polygon
from . import osm

log = get_logger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ------------------------------------------------------------------ seeding
def seed_defaults() -> int:
    """Insert the curated registry. Idempotent on (name, zone_id)."""
    now = _now_iso()
    inserted = 0
    with get_conn() as conn:
        for facility in seed.all_facilities():
            lat, lon = facility.resolve()
            district = seed.DISTRICTS[facility.zone_id][0]
            existing = conn.execute(
                "SELECT id FROM safe_locations WHERE name = ? AND zone_id = ?",
                (facility.name, facility.zone_id),
            ).fetchone()
            if existing:
                continue
            conn.execute(
                """INSERT INTO safe_locations (name, category, zone_id, area, latitude,
                       longitude, coordinate_source, phone, capacity, notes, is_demo,
                       created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
                (
                    facility.name,
                    facility.category,
                    facility.zone_id,
                    facility.area or district,
                    lat,
                    lon,
                    facility.coordinate_source,
                    facility.phone,
                    facility.capacity,
                    facility.notes,
                    now,
                    now,
                ),
            )
            inserted += 1
    if inserted:
        log.info("seeded %s safe location(s)", inserted)
    return inserted


def count() -> int:
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) AS n FROM safe_locations").fetchone()["n"]


# ------------------------------------------------------------------ cities
def list_cities(query: str = "", limit: int = 50) -> list[dict]:
    """Districts available in the curated registry, filtered by free text.

    Matched against both the district name and its headquarters town so typing
    "Nawabshah" still finds Shaheed Benazir Abad.
    """
    needle = (query or "").strip().lower()
    rows: list[dict] = []
    for zone_id, (district, hq) in seed.DISTRICTS.items():
        lat, lon = seed.CENTERS[zone_id]
        entry = {
            "zone_id": zone_id,
            "name": district,
            "headquarters": hq,
            "latitude": lat,
            "longitude": lon,
            "source": "curated",
            "facility_count": 0,
        }
        if needle and needle not in district.lower() and needle not in hq.lower():
            continue
        rows.append(entry)

    with get_conn() as conn:
        counts = {
            r["zone_id"]: r["n"]
            for r in conn.execute(
                "SELECT zone_id, COUNT(*) AS n FROM safe_locations GROUP BY zone_id"
            ).fetchall()
        }
    for row in rows:
        row["facility_count"] = counts.get(row["zone_id"], 0)
    rows.sort(key=lambda r: r["name"])
    return rows[:limit]


# ------------------------------------------------------------------ helpers
def _maps_url(name: str, area: str | None, lat: float, lon: float, source: str) -> str:
    """Precise fixes link straight to the pin; approximate ones search by name.

    A district centroid is not the facility's address, so sending a user to that
    pin would drop them in the middle of the district.
    """
    if source == "surveyed":
        return f"https://www.google.com/maps/search/?api=1&query={lat:.5f},{lon:.5f}"
    query = f"{name}, {area}" if area else name
    return f"https://www.google.com/maps/search/{quote(query)}"


def _shape(
    *,
    name: str,
    category: str,
    area: str | None,
    lat: float,
    lon: float,
    coordinate_source: str,
    phone: str | None,
    capacity: int | None,
    notes: str | None,
    origin: tuple[float, float] | None,
    is_demo: bool,
    extra: dict | None = None,
) -> dict:
    row: dict = {
        "name": name,
        "category": category,
        "area": area,
        "latitude": round(lat, 5),
        "longitude": round(lon, 5),
        "coordinate_source": coordinate_source,
        "phone": phone,
        "capacity": capacity,
        "notes": notes,
        "is_demo": is_demo,
        "maps_url": _maps_url(name, area, lat, lon, coordinate_source),
        "distance_km": round(haversine_km(origin[0], origin[1], lat, lon), 1)
        if origin
        else None,
    }
    if extra:
        row.update(extra)
    return row


# ------------------------------------------------------------------ queries
# Categories most relevant when fleeing a flood are dealt first.
_CATEGORY_PRIORITY = ("shelter", "hospital", "rescue", "police", "relief")


def _distance_key(row: dict) -> float:
    distance = row.get("distance_km")
    return float("inf") if distance is None else distance


def _balanced(rows: list[dict], limit: int) -> list[dict]:
    """Round-robin across categories: nearest of each, then second-nearest, and so on.

    Sorting purely by distance tends to return a dozen of whichever facility
    type is densest in that city, which is useless to someone who specifically
    needs a shelter.
    """
    buckets: dict[str, list[dict]] = {}
    for row in rows:
        buckets.setdefault(row["category"], []).append(row)
    for bucket in buckets.values():
        bucket.sort(key=_distance_key)

    order = [c for c in _CATEGORY_PRIORITY if c in buckets]
    order += [c for c in buckets if c not in _CATEGORY_PRIORITY]

    out: list[dict] = []
    depth = 0
    while len(out) < limit:
        added = False
        for category in order:
            bucket = buckets[category]
            if depth < len(bucket):
                out.append(bucket[depth])
                added = True
                if len(out) >= limit:
                    break
        if not added:
            break
        depth += 1
    return out


def list_by_zone(
    zone_id: str,
    lat: float | None = None,
    lng: float | None = None,
    category: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    """Curated facilities for a Sindh district, nearest first.

    Distances are only computed when the caller supplied real coordinates. The
    curated rows store the district centroid rather than a surveyed fix, so
    measuring centroid-to-centroid would report a meaningless 0.0 km for every
    facility — distance_km is left null instead.
    """
    if zone_id not in seed.DISTRICTS:
        raise KeyError(zone_id)

    sql = "SELECT * FROM safe_locations WHERE zone_id = ?"
    params: list = [zone_id]
    if category:
        sql += " AND category = ?"
        params.append(category)
    sql += " ORDER BY category, name"
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()

    origin = (lat, lng) if (lat is not None and lng is not None) else None
    results = [
        _shape(
            name=r["name"],
            category=r["category"],
            area=r["area"],
            lat=r["latitude"],
            lon=r["longitude"],
            coordinate_source=r["coordinate_source"],
            phone=r["phone"],
            capacity=r["capacity"],
            notes=r["notes"],
            origin=origin,
            is_demo=bool(r["is_demo"]),
            extra={"id": r["id"], "zone_id": r["zone_id"]},
        )
        for r in rows
    ]
    if origin:
        results.sort(key=lambda item: (item["distance_km"] is None, item["distance_km"] or 0.0))
    limit = limit or config.SAFE_LOCATION_MAX_RESULTS
    return results[:limit]


def zone_for_point(lat: float, lng: float) -> str | None:
    """Nearest curated district to a GPS fix — polygon first, then centroid."""
    inside = _zone_in_polygon(lat, lng)
    if inside:
        return inside
    best = min(
        seed.CENTERS.items(),
        key=lambda item: haversine_km(lat, lng, item[1][0], item[1][1]),
        default=None,
    )
    return best[0] if best else None


def search(query: str, limit: int | None = None) -> list[dict]:
    """Live worldwide lookup: geocode the city, then find facilities near it.

    Returns [] if OSM is unreachable; the caller reports that honestly rather
    than implying the place has no shelters.
    """
    query = (query or "").strip()
    if not query:
        return []

    # A curated district wins over a live round-trip: it is offline, vetted, and
    # avoids spending OSM quota on a place we already cover.
    needle = query.lower()
    for zone_id, (district, hq) in seed.DISTRICTS.items():
        if needle in (district.lower(), hq.lower(), zone_id):
            return list_by_zone(zone_id, limit=limit)

    places = osm.geocode(query)
    if not places:
        return []
    place = places[0]
    results = osm.nearby(place["latitude"], place["longitude"])
    origin = (place["latitude"], place["longitude"])
    shaped = [
        _shape(
            name=r["name"],
            category=r["category"],
            area=r.get("area") or place.get("name"),
            lat=r["latitude"],
            lon=r["longitude"],
            coordinate_source="surveyed",
            phone=r.get("phone"),
            capacity=None,
            notes=None,
            origin=origin,
            is_demo=False,
            extra={
                "osm_type": r.get("osm_type"),
                "osm_id": r.get("osm_id"),
                "resolved_city": place.get("name"),
                "resolved_country": place.get("country"),
            },
        )
        for r in results
    ]
    return _balanced(shaped, limit or config.SAFE_LOCATION_MAX_RESULTS)


def _live_status(locations: list[dict], curated: bool) -> str:
    """Why the result set looks the way it does.

    An empty list from the live path has several very different causes, and
    "this city has no shelters" is the one thing it must never be read as.
    """
    if curated:
        return "not_needed"
    if locations:
        return "ok"
    if not config.LIVE_GEO_ENABLED:
        return "disabled"
    if osm.rate_limited():
        return "rate_limited"
    return "unavailable"


def lookup(
    zone_id: str | None = None,
    query: str | None = None,
    lat: float | None = None,
    lng: float | None = None,
    category: str | None = None,
    limit: int | None = None,
) -> dict:
    """Single entry point for the API: resolve a district, a search, or a GPS fix."""
    if zone_id:
        locations = list_by_zone(zone_id, lat=lat, lng=lng, category=category, limit=limit)
        district, hq = seed.DISTRICTS[zone_id]
        return {
            "source": "curated",
            "live_lookup_available": config.LIVE_GEO_ENABLED,
            "live_status": _live_status(locations, curated=True),
            "resolved": {
                "zone_id": zone_id,
                "name": district,
                "headquarters": hq,
                "latitude": seed.CENTERS[zone_id][0],
                "longitude": seed.CENTERS[zone_id][1],
            },
            "distance_basis": "user_location" if (lat is not None and lng is not None)
            else "unavailable",
            "attribution": None,
            "locations": locations,
        }

    if query:
        locations = search(query, limit=limit)
        curated = any(loc.get("zone_id") for loc in locations)
        return {
            "source": "curated" if curated else "openstreetmap",
            "live_lookup_available": config.LIVE_GEO_ENABLED,
            "live_status": _live_status(locations, curated=curated),
            "resolved": {"query": query, "name": query},
            "distance_basis": "unavailable" if curated else "resolved_city_center",
            "attribution": None if curated else osm.SOURCE,
            "locations": locations,
        }

    if lat is not None and lng is not None:
        resolved = zone_for_point(lat, lng)
        if resolved:
            return lookup(zone_id=resolved, lat=lat, lng=lng, category=category, limit=limit)

    raise ValueError("provide zone_id, query, or lat+lng")
