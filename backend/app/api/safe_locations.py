"""``/api/safe-locations`` — nearby shelters, hospitals and emergency services.

Backs the frontend's "Nearby Safe Locations" card, which previously hardcoded
four Hyderabad entries. Three ways to resolve a place:

* ``zone_id`` — a curated Sindh district (offline, always works)
* ``q`` — free-text city or country; a curated district matches locally, anything
  else is geocoded live through OpenStreetMap
* ``lat`` + ``lng`` — a GPS fix, resolved to the district containing it
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..core import config
from ..data import safe_locations as districts
from ..safe_locations import service
from ..safe_locations import osm

router = APIRouter(prefix="/api/safe-locations", tags=["safe-locations"])


@router.get("")
def list_safe_locations(
    zone_id: str | None = Query(default=None, description="Sindh district id, e.g. hyderabad"),
    q: str | None = Query(default=None, min_length=1, description="City or country name"),
    lat: float | None = Query(default=None, ge=-90, le=90),
    lng: float | None = Query(default=None, ge=-180, le=180),
    category: str | None = Query(default=None, description="shelter|hospital|rescue|police|relief"),
    limit: int | None = Query(default=None, ge=1, le=50),
):
    if category and category not in districts.CATEGORIES:
        raise HTTPException(
            422, f"category must be one of {', '.join(districts.CATEGORIES)}"
        )
    if zone_id and zone_id not in districts.DISTRICTS:
        raise HTTPException(404, f"unknown district: {zone_id}")

    try:
        return service.lookup(
            zone_id=zone_id, query=q, lat=lat, lng=lng, category=category, limit=limit
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@router.get("/cities")
def list_cities(
    q: str = Query(default="", description="Filter districts by name or headquarters town"),
    limit: int = Query(default=50, ge=1, le=100),
):
    """Districts in the curated registry, for the city picker."""
    return {
        "cities": service.list_cities(query=q, limit=limit),
        "live_search_enabled": config.LIVE_GEO_ENABLED,
        "hint": "Any city worldwide can be sent to /api/safe-locations?q= — "
                "cities outside this list are resolved live via OpenStreetMap.",
    }


@router.get("/categories")
def list_categories():
    return {"categories": list(districts.CATEGORIES)}


@router.get("/reverse")
def reverse_lookup(
    lat: float = Query(ge=-90, le=90),
    lng: float = Query(ge=-180, le=180),
):
    """Resolve a GPS fix to the curated district that contains or is nearest it."""
    zone_id = service.zone_for_point(lat, lng)
    if zone_id is None:
        raise HTTPException(404, "no district found for that coordinate")
    name, hq = districts.DISTRICTS[zone_id]
    return {
        "zone_id": zone_id,
        "name": name,
        "headquarters": hq,
        "latitude": lat,
        "longitude": lng,
    }


@router.get("/stats")
def stats():
    """Coverage summary so the UI can state honestly what it does and does not have."""
    return {
        "districts": len(districts.DISTRICTS),
        "curated_locations": service.count(),
        "live_lookup_enabled": config.LIVE_GEO_ENABLED,
        "live_source": osm.SOURCE,
        "radius_km": config.SAFE_LOCATION_RADIUS_KM,
    }
