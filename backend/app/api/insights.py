from fastapi import APIRouter, HTTPException

from ..data.districts import BY_ID
from ..ingest.demo_simulator import current_reading
from ..insights.explainer import generate_insights
from ..scoring.heuristic import HeuristicScorer

router = APIRouter(prefix="/api", tags=["insights"])

scorer = HeuristicScorer()


@router.get("/insights/{zone_id}")
def get_insights(zone_id: str):
    district = BY_ID.get(zone_id)
    if district is None:
        raise HTTPException(status_code=404, detail=f"unknown zone: {zone_id}")
    result = scorer.score(district, current_reading(zone_id, district.gauge))
    return generate_insights(district, result)
