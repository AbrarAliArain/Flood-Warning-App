from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..alerts import engine as alerts_engine

router = APIRouter(prefix="/api", tags=["alerts"])


class DemoAlertRequest(BaseModel):
    zone_id: str | None = None
    message: str | None = None


@router.get("/alerts")
def get_alerts():
    return {"alerts": alerts_engine.active_alerts()}


@router.get("/alerts/auto")
def get_auto_warnings():
    """Auto-generated division-level flood warnings derived from live scoring."""
    return {"warnings": alerts_engine.division_warnings()}


@router.post("/alerts/demo", status_code=201)
def post_demo_alert(body: DemoAlertRequest):
    try:
        return alerts_engine.issue_demo_alert(body.zone_id, body.message)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
