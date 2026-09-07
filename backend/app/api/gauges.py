from datetime import datetime, timezone

from fastapi import APIRouter

from ..data.gauges import CLASS_COLORS, GAUGES, gauge_class
from ..ingest.demo_simulator import DEMO_GAUGE_FLOWS

router = APIRouter(prefix="/api", tags=["gauges"])


@router.get("/gauges")
def get_gauges():
    stations = []
    for gauge in GAUGES:
        flow = DEMO_GAUGE_FLOWS[gauge["id"]]
        flood_class = gauge_class(flow, gauge["id"])
        stations.append(
            {
                **gauge,
                "flow_lacs_cusecs": flow,
                "flood_class": flood_class,
                "color": CLASS_COLORS[flood_class],
                "is_demo": True,
            }
        )
    return {
        "gauges": stations,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source_thresholds": "FFC flood levels, ffd.pmd.gov.pk (real)",
        "source_flows": "DEMO simulator",
    }
