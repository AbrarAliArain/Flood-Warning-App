from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..data.districts import BY_ID
from ..ingest.demo_simulator import current_reading
from ..scoring.heuristic import HeuristicScorer

router = APIRouter(prefix="/api", tags=["predict"])

scorer = HeuristicScorer()


class PredictRequest(BaseModel):
    zone_id: str
    rainfall_mm_hr: float | None = Field(None, ge=0, le=1000)
    river_flow_lacs_cusecs: float | None = Field(None, ge=0, le=50)


@router.post("/predict")
def predict(body: PredictRequest):
    district = BY_ID.get(body.zone_id)
    if district is None:
        raise HTTPException(status_code=404, detail=f"unknown zone: {body.zone_id}")

    reading = current_reading(body.zone_id, district.gauge)
    if body.rainfall_mm_hr is not None:
        reading.rainfall_mm_hr = body.rainfall_mm_hr
    if body.river_flow_lacs_cusecs is not None:
        reading.river_flow_lacs_cusecs = body.river_flow_lacs_cusecs

    result = scorer.score(district, reading)
    return {
        "zone_id": district.zone_id,
        "name": district.name,
        "flood_probability": round(result.score / 100, 2),
        "risk_score": result.score,
        "risk_level": result.category.upper(),
        "factors": {
            "rainfall": result.rainfall_norm,
            "river": result.river_norm,
            "exposure": result.exposure,
            "historical": result.historical,
        },
        "inputs_are_demo": reading.is_demo,
    }
