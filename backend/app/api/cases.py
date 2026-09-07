"""``/api/cases`` — emergency case lifecycle and dispatch."""
from __future__ import annotations

import urllib.parse

from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth.deps import current_user, require_role
from ..cases import service as case_service
from ..core import config, security
from ..ngos import match as ngo_match
from ..ngos import service as ngo_service
from ..storage.db import get_conn
from ..whatsapp import transport as wa

router = APIRouter(prefix="/api/cases", tags=["cases"])


def mask_phone(number: str | None) -> str | None:
    """Keep the country code and last two digits, mask the rest."""
    if not number:
        return None
    digits = number.strip()
    if len(digits) <= 6:
        return "*" * len(digits)
    return f"{digits[:3]}{'*' * (len(digits) - 5)}{digits[-2:]}"


def _redact_matches(matches: list[dict]) -> list[dict]:
    redacted = []
    for match in matches:
        entry = dict(match)
        number = entry.pop("whatsapp_number", None)
        phone = entry.pop("contact_phone", None)
        entry["contact_masked"] = mask_phone(number or phone)
        entry["contact_available"] = bool(number or phone)
        redacted.append(entry)
    return redacted


def _redact_case_for_citizen(case: dict) -> dict:
    """Strip responder contact details before returning a case to a citizen."""
    result = dict(case)
    if "matches" in result:
        result["matches"] = _redact_matches(result["matches"])
    dispatch = result.get("dispatch")
    if dispatch:
        block = dict(dispatch)
        recipient = block.pop("recipient", None)
        block["recipient_masked"] = mask_phone(recipient)
        block["recipient_available"] = bool(recipient)
        result["dispatch"] = block
    return result


@router.get("")
def list_cases(
    status: str | None = Query(None),
    zone_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    user: dict = Depends(current_user),
):
    if user["role"] == security.CITIZEN:
        return {"cases": case_service.list_cases(user_id=user["id"], limit=limit)}
    ngo_id = user.get("ngo_id") if user["role"] == security.RESPONDER else None
    return {
        "cases": case_service.list_cases(
            status=status, ngo_id=ngo_id, zone_id=zone_id, limit=limit,
        )
    }


@router.get("/{case_id}")
def get_case(case_id: int, user: dict = Depends(current_user)):
    case = case_service.get_by_id(case_id)
    if case is None:
        raise HTTPException(404, f"unknown case: {case_id}")
    if user["role"] == security.CITIZEN and case["user_id"] != user["id"]:
        raise HTTPException(403, "you can only view your own cases")
    return case


@router.get("/{case_id}/events")
def case_events(case_id: int, user: dict = Depends(current_user)):
    case = case_service.get_by_id(case_id)
    if case is None:
        raise HTTPException(404, f"unknown case: {case_id}")
    return {"case_id": case_id, "events": case_service.get_events(case_id)}


@router.get("/{case_id}/communications")
def case_comms(case_id: int, user: dict = Depends(require_role(security.ADMIN, security.RESPONDER))):
    case = case_service.get_by_id(case_id)
    if case is None:
        raise HTTPException(404, f"unknown case: {case_id}")
    return {"case_id": case_id, "logs": case_service.get_communication_logs(case_id)}


@router.get("/{case_id}/whatsapp-preview")
def case_whatsapp_preview(case_id: int, user: dict = Depends(current_user)):
    """The exact alert text, shown in-app before anything leaves the device.

    ``wa_link`` carries the responder's number because wa.me cannot work
    without it, but the number is never returned as a readable field.
    """
    case = case_service.get_by_id(case_id)
    if case is None:
        raise HTTPException(404, f"unknown case: {case_id}")
    is_citizen = user["role"] == security.CITIZEN
    if is_citizen and case["user_id"] != user["id"]:
        raise HTTPException(403, "you can only view your own cases")

    if case.get("report_id"):
        with get_conn() as conn:
            row = conn.execute(
                "SELECT location_text FROM reports WHERE id = ?", (case["report_id"],)
            ).fetchone()
        if row and row["location_text"]:
            case["location_text"] = row["location_text"]

    responder = None
    recipient = None
    if case.get("ngo_id"):
        ngo = ngo_service.get_by_id(case["ngo_id"])
        if ngo is not None:
            recipient = ngo.get("whatsapp_number") or ngo.get("contact_phone")
            active = ngo_service.get_active_case_count(ngo["id"])
            responder = {
                "ngo_id": ngo["id"],
                "name": ngo["name"],
                "organisation_type": ngo["organisation_type"],
                "service_area": ngo.get("service_area"),
                "capabilities": ngo["capabilities"],
                "available": ngo["available"],
                "active_cases": active,
                "max_concurrent_cases": ngo["max_concurrent_cases"],
                "is_demo": ngo["is_demo"],
                "contact_masked": mask_phone(recipient),
                "contact_available": bool(recipient),
            }

    case["ngo_whatsapp"] = recipient
    message = wa.build_case_message(case)
    wa_link = None
    if recipient:
        digits = "".join(ch for ch in recipient if ch.isdigit())
        wa_link = f"https://wa.me/{digits}?text={urllib.parse.quote(message)}"

    mode = config.whatsapp_mode()
    return {
        "case_id": case["id"],
        "case_code": case["code"],
        "mode": mode,
        "is_live": mode != "demo",
        "message": message,
        "responder": responder,
        "wa_link": wa_link,
        "communication_status": case["communication_status"],
        "priority_label": case["priority_label"],
        "status": case["status"],
        "assigned_at": case.get("assigned_at"),
        "created_at": case["created_at"],
        "is_demo": case["is_demo"],
    }


@router.post("/from-report", status_code=201)
def create_from_report(
    body: dict,
    user: dict = Depends(current_user),
):
    report_id = body.get("report_id")
    if not report_id:
        raise HTTPException(422, "report_id is required")

    with get_conn() as conn:
        report = conn.execute(
            "SELECT * FROM reports WHERE id = ?", (report_id,)
        ).fetchone()
    if report is None:
        raise HTTPException(404, f"unknown report: {report_id}")
    if user["role"] == security.CITIZEN and report["user_id"] != user["id"]:
        raise HTTPException(403, "you can only escalate your own reports")

    case = case_service.create_from_report(
        user_id=user["id"],
        report_id=report_id,
        zone_id=report["zone_id"],
        latitude=report["latitude"],
        longitude=report["longitude"],
        emergency_type=report["emergency_type"] or "flood",
        severity=report["severity"] or "moderate",
        description=report["description"],
        evidence_path=report["evidence_path"],
        contact_phone=user.get("phone"),
        location_text=body.get("location_text") or report["location_text"],
        is_demo=bool(user.get("is_demo")),
        auto_dispatch=body.get("auto_dispatch", True),
    )
    if user["role"] == security.CITIZEN:
        return _redact_case_for_citizen(case)
    return case


@router.post("/{case_id}/transition")
def transition_case(
    case_id: int,
    body: dict,
    user: dict = Depends(current_user),
):
    new_status = body.get("status")
    if not new_status:
        raise HTTPException(422, "status is required")
    try:
        case = case_service.transition(
            case_id, new_status,
            actor_id=user["id"],
            actor_role=user["role"],
            note=body.get("note"),
        )
        return case
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.post("/match")
def match_ngos_for_case(
    body: dict,
    user: dict = Depends(current_user),
):
    zone_id = body.get("zone_id")
    if not zone_id:
        raise HTTPException(422, "zone_id is required")
    matches = ngo_match.match_ngos(
        zone_id=zone_id,
        emergency_type=body.get("emergency_type", "flood"),
        latitude=body.get("latitude"),
        longitude=body.get("longitude"),
    )
    if user["role"] == security.CITIZEN:
        matches = _redact_matches(matches)
    return {"zone_id": zone_id, "matches": matches}
