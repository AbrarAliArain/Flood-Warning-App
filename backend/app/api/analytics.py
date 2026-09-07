from fastapi import APIRouter

from ..data.districts import DISTRICTS
from ..ingest.demo_simulator import DEMO_RISK_TREND, current_reading
from ..scoring.base import CATEGORY_COLORS
from ..scoring.heuristic import HeuristicScorer
from ..storage.db import get_conn

router = APIRouter(prefix="/api", tags=["analytics"])

scorer = HeuristicScorer()


@router.get("/analytics")
def get_analytics():
    distribution = {cat: 0 for cat in CATEGORY_COLORS}
    for district in DISTRICTS:
        result = scorer.score(district, current_reading(district.zone_id, district.gauge))
        distribution[result.category] += 1

    with get_conn() as conn:
        reports_count = conn.execute("SELECT COUNT(*) AS n FROM reports").fetchone()["n"]
        alerts_count = conn.execute(
            "SELECT COUNT(*) AS n FROM alerts WHERE active = 1"
        ).fetchone()["n"]

    return {
        "distribution": distribution,
        "trend": DEMO_RISK_TREND,
        "trend_is_demo": True,
        "reports_count": reports_count,
        "active_alerts_count": alerts_count,
    }
