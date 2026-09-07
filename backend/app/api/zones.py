import json
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..data.districts import BY_ID
from ..ingest.demo_simulator import current_reading
from ..scoring.base import CATEGORY_COLORS
from ..scoring.heuristic import HeuristicScorer

router = APIRouter(prefix="/api", tags=["zones"])

GEO_PATH = Path(__file__).resolve().parent.parent.parent / "geo" / "sindh_zones.geojson"

scorer = HeuristicScorer()


@lru_cache
def _zones_geojson() -> dict:
    return json.loads(GEO_PATH.read_text(encoding="utf-8"))


def _risk_for(zone_id: str):
    district = BY_ID[zone_id]
    reading = current_reading(zone_id, district.gauge)
    return scorer.score(district, reading)


@router.get("/zones")
def get_zones():
    geo = _zones_geojson()
    features = []
    for feature in geo["features"]:
        zone_id = feature["properties"]["zone_id"]
        result = _risk_for(zone_id)
        props = dict(feature["properties"])
        props.update(
            score=result.score,
            category=result.category,
            color=CATEGORY_COLORS[result.category],
            rainfall_mm_hr=result.reading.rainfall_mm_hr,
            is_demo=result.reading.is_demo,
        )
        features.append({**feature, "properties": props})
    features.sort(key=lambda f: f["properties"]["score"], reverse=True)
    return {"type": "FeatureCollection", "features": features}


@router.get("/zones/{zone_id}")
def get_zone(zone_id: str):
    if zone_id not in BY_ID:
        raise HTTPException(status_code=404, detail=f"unknown zone: {zone_id}")
    district = BY_ID[zone_id]
    result = _risk_for(zone_id)
    return {
        "zone_id": zone_id,
        "name": district.name,
        "division": district.division,
        "score": result.score,
        "category": result.category,
        "color": CATEGORY_COLORS[result.category],
        "factors": {
            "rainfall": {"value": result.rainfall_norm, "weight": 0.35},
            "river": {"value": result.river_norm, "weight": 0.15},
            "exposure": {"value": result.exposure, "weight": 0.3},
            "historical": {"value": result.historical, "weight": 0.2},
        },
        "live": {
            "rainfall_mm_hr": result.reading.rainfall_mm_hr,
            "river_flow_lacs_cusecs": result.reading.river_flow_lacs_cusecs,
            "gauge": district.gauge,
            "is_demo": result.reading.is_demo,
        },
        "profile": {
            "rainfall_baseline_mm_yr": district.rainfall_baseline_mm_yr,
            "baseline_source": district.baseline_source,
            "houses_2022": district.houses_2022,
            "houses_source": district.houses_source,
            "exposure_source": district.exposure_source,
            "historical_source": district.historical_source,
            "historical_events": district.historical_events,
            "risk_factors": district.risk_factors,
        },
    }
