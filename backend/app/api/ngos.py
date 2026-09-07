"""``/api/ngos`` — NGO/rescue organisation registry."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..auth.deps import require_role
from ..core import security
from ..ngos import service as ngo_service

router = APIRouter(prefix="/api/ngos", tags=["ngos"])


@router.get("")
def list_ngos(active_only: bool = True):
    return {"ngos": ngo_service.list_all(active_only=active_only)}


@router.get("/{ngo_id}")
def get_ngo(ngo_id: int):
    ngo = ngo_service.get_by_id(ngo_id)
    if ngo is None:
        raise HTTPException(404, f"unknown NGO: {ngo_id}")
    return ngo


@router.post("", status_code=201)
def create_ngo(
    body: dict,
    user: dict = Depends(require_role(security.ADMIN)),
):
    return ngo_service.create(**body)


@router.put("/{ngo_id}")
def update_ngo(
    ngo_id: int,
    body: dict,
    user: dict = Depends(require_role(security.ADMIN)),
):
    try:
        return ngo_service.update(ngo_id, **body)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
