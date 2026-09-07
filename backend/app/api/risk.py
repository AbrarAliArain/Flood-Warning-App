"""``/api/risk`` — new risk-engine endpoints.

These use the spec bands (Low/Medium/High/Critical, 0-24/25-49/50-74/75-100)
and expose per-feature contributions.  Legacy ``/api/zones`` etc. remain
untouched.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..auth.deps import require_role
from ..core import security
from ..data.districts import BY_ID as DISTRICTS
from ..risk import engine, store

router = APIRouter(prefix="/api/risk", tags=["risk"])


@router.get("/model")
def model_info():
    return engine.active_model()


@router.get("/zones")
def list_zones():
    stored = store.get_all_zones()
    if stored:
        return {"zones": stored, "source": "stored"}
    assessments = engine.score_all()
    for a in assessments:
        store.persist(a)
    return {
        "zones": [
            {
                "zone_id": a.zone_id,
                "name": a.name,
                "division": a.division,
                "score": a.score,
                "band": a.band,
                "model": a.model,
                "factors": a.features.as_dict(),
                "is_demo": a.is_demo,
            }
            for a in assessments
        ],
        "source": "computed",
    }


@router.get("/zones/{zone_id}")
def get_zone(zone_id: str):
    if zone_id not in DISTRICTS:
        raise HTTPException(404, f"Unknown zone: {zone_id}")
    assessment = engine.score_zone(DISTRICTS[zone_id])
    store.persist(assessment)
    return {
        "zone_id": assessment.zone_id,
        "name": assessment.name,
        "division": assessment.division,
        "score": assessment.score,
        "band": assessment.band,
        "model": assessment.model,
        "features": assessment.features.as_dict(),
        "contributions": assessment.contributions,
        "is_demo": assessment.is_demo,
    }


@router.get("/zones/{zone_id}/history")
def zone_history(zone_id: str, limit: int = 50):
    if zone_id not in DISTRICTS:
        raise HTTPException(404, f"Unknown zone: {zone_id}")
    return {"zone_id": zone_id, "history": store.get_zone_history(zone_id, limit)}


@router.post("/score")
def score_request(body: dict | None = None):
    body = body or {}
    zone_id = body.get("zone_id")
    if zone_id and zone_id in DISTRICTS:
        assessment = engine.score_zone(DISTRICTS[zone_id])
        store.persist(assessment)
        return {
            "zone_id": assessment.zone_id,
            "name": assessment.name,
            "score": assessment.score,
            "band": assessment.band,
            "features": assessment.features.as_dict(),
            "contributions": assessment.contributions,
            "model": assessment.model,
            "is_demo": assessment.is_demo,
        }
    assessments = engine.score_all()
    for a in assessments:
        store.persist(a)
    return {
        "scored": len(assessments),
        "results": [
            {
                "zone_id": a.zone_id,
                "name": a.name,
                "score": a.score,
                "band": a.band,
                "features": a.features.as_dict(),
                "contributions": a.contributions,
                "model": a.model,
                "is_demo": a.is_demo,
            }
            for a in assessments
        ],
    }


@router.post("/refresh")
def refresh_zones(user: dict = Depends(require_role(security.ADMIN, security.RESPONDER))):
    assessments = engine.score_all()
    for a in assessments:
        store.persist(a)
    return {"refreshed": len(assessments)}
