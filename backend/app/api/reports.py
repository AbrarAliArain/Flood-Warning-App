import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from ..auth.deps import current_user, optional_user
from ..core import config
from ..data.districts import BY_ID
from ..report_analysis import analyze_report
from ..storage.db import get_conn
from ..storage.geo import within_sindh, zone_for_point

router = APIRouter(prefix="/api", tags=["reports"])

WATER_LEVELS = {"low", "rising", "high", "severe"}
SEVERITIES = {"low", "moderate", "high", "critical"}
EMERGENCY_TYPES = {
    "flood",
    "waterlogging",
    "river_overflow",
    "rescue",
    "medical",
    "evacuation",
    "infrastructure",
    "other",
}
WATER_LEVEL_FOR_SEVERITY = {
    "low": "low",
    "moderate": "rising",
    "high": "high",
    "critical": "severe",
}
SEVERITY_FOR_WATER_LEVEL = {
    "low": "low",
    "rising": "moderate",
    "high": "high",
    "severe": "critical",
}


def _value(value: str | None) -> str | None:
    return value.strip().lower() if value is not None and value.strip() else None


def _resolve_zone(
    zone_id: str | None, latitude: float | None, longitude: float | None
) -> str:
    normalized = _value(zone_id)
    if normalized is not None and normalized not in BY_ID:
        raise HTTPException(status_code=404, detail=f"unknown zone: {normalized}")

    if (latitude is None) != (longitude is None):
        raise HTTPException(
            status_code=422, detail="latitude and longitude must be provided together"
        )
    if latitude is not None and longitude is not None:
        if within_sindh(latitude, longitude):
            resolved = zone_for_point(latitude, longitude)
            if resolved is not None:
                return resolved
        if normalized is not None:
            return normalized
        raise HTTPException(status_code=422, detail="GPS location must be within Sindh")

    if normalized is None:
        raise HTTPException(status_code=422, detail="zone_id or GPS coordinates are required")
    return normalized


def _validate_fields(
    water_level: str | None, severity: str | None, emergency_type: str | None
) -> tuple[str, str, str]:
    normalized_water_level = _value(water_level)
    normalized_severity = _value(severity)
    normalized_type = _value(emergency_type) or "flood"

    if normalized_water_level is not None and normalized_water_level not in WATER_LEVELS:
        raise HTTPException(
            status_code=422, detail="water_level must be one of low/rising/high/severe"
        )
    if normalized_severity is not None and normalized_severity not in SEVERITIES:
        raise HTTPException(
            status_code=422, detail="severity must be one of low/moderate/high/critical"
        )
    if normalized_type not in EMERGENCY_TYPES:
        raise HTTPException(
            status_code=422,
            detail="emergency_type must be one of flood/waterlogging/river_overflow/"
            "rescue/medical/evacuation/infrastructure/other",
        )

    resolved_severity = normalized_severity or SEVERITY_FOR_WATER_LEVEL.get(
        normalized_water_level or "", "moderate"
    )
    resolved_water_level = normalized_water_level or WATER_LEVEL_FOR_SEVERITY[resolved_severity]
    return resolved_water_level, resolved_severity, normalized_type


async def _save_evidence(upload: UploadFile | None) -> str | None:
    if upload is None or not upload.filename:
        return None
    suffix = Path(upload.filename).suffix.lower()
    if suffix not in config.ALLOWED_EVIDENCE_EXTENSIONS:
        raise HTTPException(status_code=422, detail="evidence must be a png/jpg/webp/heic image")
    data = await upload.read(config.MAX_EVIDENCE_BYTES + 1)
    if len(data) > config.MAX_EVIDENCE_BYTES:
        raise HTTPException(status_code=422, detail="evidence too large (max 5MB)")

    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{suffix}"
    (config.UPLOAD_DIR / filename).write_bytes(data)
    return filename


def _serialize_report(row) -> dict:
    item = dict(row)
    district = BY_ID.get(item["zone_id"])
    item["zone_name"] = district.name if district else item["zone_id"]
    item["is_demo"] = bool(item["is_demo"])
    item["report_id"] = item["id"]
    item["timestamp"] = item["created_at"]
    evidence_path = item.get("evidence_path")
    item["evidence_url"] = f"/uploads/{evidence_path}" if evidence_path else None
    item["photo_url"] = item["evidence_url"]
    if item.get("ai_analysis"):
        try:
            item["ai_analysis"] = json.loads(item["ai_analysis"])
        except json.JSONDecodeError:
            item["ai_analysis"] = {"method": "unavailable"}
    return item


@router.post("/reports", status_code=201)
async def create_report(
    zone_id: str | None = Form(None),
    water_level: str | None = Form(None),
    description: str = Form(...),
    latitude: float | None = Form(None),
    longitude: float | None = Form(None),
    emergency_type: str | None = Form(None),
    severity: str | None = Form(None),
    location_text: str | None = Form(None),
    evidence: UploadFile | None = File(None),
    photo: UploadFile | None = File(None),
    user: dict | None = Depends(optional_user),
):
    description = description.strip()
    if not description:
        raise HTTPException(status_code=422, detail="description is required")
    if len(description) > 5000:
        raise HTTPException(status_code=422, detail="description must be at most 5000 characters")
    if location_text is not None and len(location_text.strip()) > 250:
        raise HTTPException(status_code=422, detail="location_text must be at most 250 characters")
    if evidence is not None and photo is not None:
        raise HTTPException(status_code=422, detail="submit either evidence or photo, not both")

    resolved_zone = _resolve_zone(zone_id, latitude, longitude)
    if latitude is not None and longitude is not None and zone_for_point(latitude, longitude) is None:
        latitude = longitude = None
    resolved_water_level, resolved_severity, resolved_type = _validate_fields(
        water_level, severity, emergency_type
    )
    evidence_path = await _save_evidence(evidence or photo)
    created_at = datetime.now(timezone.utc).isoformat()
    analysis = analyze_report(
        description=description,
        emergency_type=resolved_type,
        severity=resolved_severity,
        water_level=resolved_water_level,
    )
    is_demo = bool(user and user.get("is_demo"))

    with get_conn() as conn:
        cursor = conn.execute(
            "INSERT INTO reports (user_id, zone_id, latitude, longitude, emergency_type, "
            "water_level, severity, description, location_text, evidence_path, status, "
            "ai_analysis, is_demo, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'submitted', ?, ?, ?)",
            (
                user["id"] if user else None,
                resolved_zone,
                latitude,
                longitude,
                resolved_type,
                resolved_water_level,
                resolved_severity,
                description,
                location_text.strip() if location_text else None,
                evidence_path,
                json.dumps(analysis, separators=(",", ":")),
                1 if is_demo else 0,
                created_at,
            ),
        )
        row = conn.execute("SELECT * FROM reports WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return _serialize_report(row)


def _list_rows(where: str = "", params: tuple = (), limit: int = 20) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT * FROM reports {where} ORDER BY created_at DESC, id DESC LIMIT ?",
            (*params, limit),
        ).fetchall()
    return [_serialize_report(row) for row in rows]


@router.get("/reports")
def list_reports(limit: int = Query(20, ge=1, le=100)):
    return {"reports": _list_rows(limit=limit)}


@router.get("/reports/mine")
def list_my_reports(
    limit: int = Query(20, ge=1, le=100), user: dict = Depends(current_user)
):
    return {"reports": _list_rows("WHERE user_id = ?", (user["id"],), limit)}
