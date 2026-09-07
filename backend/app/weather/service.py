"""Live weather via Open-Meteo (no API key required).

Replaces the fabricated constants the frontend used to show for temperature,
rain probability, wind and humidity. When the provider is unreachable the result
carries ``available: false`` so the UI can say "unavailable" instead of
inventing a number.
"""
from __future__ import annotations

import time

import httpx

from ..core import config
from ..core.logging_conf import get_logger
from ..data import safe_locations as districts

log = get_logger(__name__)

SOURCE = "Open-Meteo"

# WMO codes -> short human label. Only the ones that matter for flood response.
_CODES = {
    0: "Clear",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Rain",
    65: "Heavy rain",
    66: "Freezing rain",
    67: "Heavy freezing rain",
    80: "Slight rain showers",
    81: "Rain showers",
    82: "Violent rain showers",
    95: "Thunderstorm",
    96: "Thunderstorm with hail",
    99: "Thunderstorm with heavy hail",
}

_CURRENT_FIELDS = (
    "temperature_2m,relative_humidity_2m,precipitation,weather_code,"
    "wind_speed_10m,wind_direction_10m"
)

# lat,lon -> (timestamp, payload)
_cache: dict[str, tuple[float, object]] = {}


def clear_cache() -> None:
    _cache.clear()


def describe_code(code: int | None) -> str:
    if code is None:
        return "Unknown"
    return _CODES.get(int(code), "Unsettled")


def _cached(key: str) -> object | None:
    entry = _cache.get(key)
    if entry is None:
        return None
    at, payload = entry
    if time.time() - at >= config.WEATHER_CACHE_TTL_SECONDS:
        _cache.pop(key, None)
        return None
    return payload


def resolve_zone(zone_id: str) -> tuple[float, float] | None:
    """District centroid for a zone_id, or None if the district is unknown."""
    return districts.CENTERS.get(zone_id)


def current(
    lat: float,
    lng: float,
    zone_id: str | None = None,
) -> dict:
    """Current conditions plus today's peak rain probability for a point."""
    if not config.LIVE_GEO_ENABLED:
        return {
            "available": False,
            "reason": "live_lookups_disabled",
            "source": SOURCE,
            "zone_id": zone_id,
            "latitude": round(lat, 5),
            "longitude": round(lng, 5),
        }

    key = f"{lat:.3f},{lng:.3f}"
    hit = _cached(key)
    if hit is not None:
        payload = dict(hit)  # type: ignore[arg-type]
        payload["zone_id"] = zone_id
        return payload

    try:
        resp = httpx.get(
            config.OPEN_METEO_URL,
            timeout=config.LIVE_GEO_TIMEOUT_SECONDS,
            follow_redirects=True,
            headers={"User-Agent": config.OSM_USER_AGENT},
            params={
                "latitude": f"{lat:.5f}",
                "longitude": f"{lng:.5f}",
                "current": _CURRENT_FIELDS,
                "hourly": "precipitation_probability",
                "forecast_days": 1,
                "timezone": "auto",
            },
        )
        resp.raise_for_status()
        raw = resp.json()
    except Exception as exc:  # noqa: BLE001 - offline must not break the dashboard
        log.warning("open-meteo request failed at %.4f,%.4f: %s", lat, lng, exc)
        return {
            "available": False,
            "reason": "provider_unreachable",
            "source": SOURCE,
            "zone_id": zone_id,
            "latitude": round(lat, 5),
            "longitude": round(lng, 5),
        }

    current_block = raw.get("current") or {}
    hourly = raw.get("hourly") or {}
    rain_probability = None
    probabilities = hourly.get("precipitation_probability") or []
    if probabilities:
        scored = [p for p in probabilities if isinstance(p, (int, float))]
        rain_probability = max(scored) if scored else None

    payload = {
        "available": True,
        "source": SOURCE,
        "zone_id": zone_id,
        "latitude": round(lat, 5),
        "longitude": round(lng, 5),
        "temperature_c": current_block.get("temperature_2m"),
        "humidity_percent": current_block.get("relative_humidity_2m"),
        "wind_speed_kmh": current_block.get("wind_speed_10m"),
        "wind_direction_deg": current_block.get("wind_direction_10m"),
        "precipitation_mm": current_block.get("precipitation"),
        "weather_code": current_block.get("weather_code"),
        "conditions": describe_code(current_block.get("weather_code")),
        "rain_probability_percent": rain_probability,
        "observed_at": current_block.get("time"),
        "timezone": raw.get("timezone"),
        "units": {
            "temperature": (raw.get("current_units") or {}).get("temperature_2m", "°C"),
            "wind_speed": (raw.get("current_units") or {}).get("wind_speed_10m", "km/h"),
            "humidity": (raw.get("current_units") or {}).get("relative_humidity_2m", "%"),
        },
    }
    _cache[key] = (time.time(), payload)
    return payload


def for_zone(zone_id: str) -> dict:
    """Weather for a Sindh district, resolved through its centroid."""
    point = resolve_zone(zone_id)
    if point is None:
        raise KeyError(zone_id)
    return current(point[0], point[1], zone_id=zone_id)
