"""``/api/weather`` — live conditions for the analytics weather tiles."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..core import config
from ..data import safe_locations as districts
from ..safe_locations import service as safe_service
from ..weather import service as weather_service

router = APIRouter(prefix="/api/weather", tags=["weather"])


@router.get("")
def get_weather(
    zone_id: str | None = Query(default=None, description="Sindh district id, e.g. hyderabad"),
    lat: float | None = Query(default=None, ge=-90, le=90),
    lng: float | None = Query(default=None, ge=-180, le=180),
):
    """Current weather for a district or an explicit GPS fix.

    ``available: false`` means the provider was unreachable or live lookups are
    disabled — the client must not substitute a made-up reading.
    """
    if zone_id:
        if zone_id not in districts.DISTRICTS:
            raise HTTPException(404, f"unknown district: {zone_id}")
        return weather_service.for_zone(zone_id)

    if lat is not None or lng is not None:
        if lat is None or lng is None:
            raise HTTPException(422, "lat and lng must both be provided")
        return weather_service.current(lat, lng)

    raise HTTPException(422, "provide zone_id, or both lat and lng")


@router.get("/zones")
def weather_zones():
    """Districts the weather endpoint accepts, so the UI can build its picker."""
    return {
        "zones": [
            {
                "zone_id": zone_id,
                "name": name,
                "headquarters": hq,
                "latitude": districts.CENTERS[zone_id][0],
                "longitude": districts.CENTERS[zone_id][1],
            }
            for zone_id, (name, hq) in sorted(districts.DISTRICTS.items())
        ],
        "live_enabled": config.LIVE_GEO_ENABLED,
        "source": weather_service.SOURCE,
    }


@router.get("/nearby")
def weather_nearby(
    lat: float = Query(ge=-90, le=90),
    lng: float = Query(ge=-180, le=180),
):
    """Weather for a GPS fix, labelled with the district it resolved to."""
    payload = weather_service.current(lat, lng, zone_id=safe_service.zone_for_point(lat, lng))
    return payload
