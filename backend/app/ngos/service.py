"""NGO registry: CRUD and lookup for rescue organisations."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from ..core.logging_conf import get_logger
from ..storage.db import get_conn

log = get_logger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _row_to_dict(row) -> dict:
    ngo = dict(row)
    ngo["coverage_zones"] = json.loads(ngo["coverage_zones"])
    ngo["capabilities"] = json.loads(ngo["capabilities"])
    ngo["available"] = bool(ngo["available"])
    ngo["active"] = bool(ngo["active"])
    ngo["is_demo"] = bool(ngo["is_demo"])
    return ngo


def list_all(active_only: bool = True) -> list[dict]:
    where = "WHERE active = 1" if active_only else ""
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT * FROM ngos {where} ORDER BY name"
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_by_id(ngo_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM ngos WHERE id = ?", (ngo_id,)).fetchone()
    return _row_to_dict(row) if row else None


def create(
    *,
    name: str,
    organisation_type: str = "ngo",
    contact_name: str | None = None,
    contact_phone: str | None = None,
    whatsapp_number: str | None = None,
    email: str | None = None,
    service_area: str | None = None,
    coverage_zones: list[str] | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    service_radius_km: float | None = None,
    capabilities: list[str] | None = None,
    max_concurrent_cases: int = 5,
    is_demo: bool = False,
) -> dict:
    now = _now_iso()
    with get_conn() as conn:
        cursor = conn.execute(
            """INSERT INTO ngos (name, organisation_type, contact_name, contact_phone,
               whatsapp_number, email, service_area, coverage_zones, latitude, longitude,
               service_radius_km, capabilities, max_concurrent_cases, is_demo,
               created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                name.strip(), organisation_type, contact_name, contact_phone,
                whatsapp_number, email, service_area,
                json.dumps(coverage_zones or [], separators=(",", ":")),
                latitude, longitude, service_radius_km,
                json.dumps(capabilities or [], separators=(",", ":")),
                max_concurrent_cases, int(is_demo),
                now, now,
            ),
        )
        ngo_id = cursor.lastrowid
        row = conn.execute("SELECT * FROM ngos WHERE id = ?", (ngo_id,)).fetchone()
    log.info("created NGO id=%s name=%s", ngo_id, name)
    return _row_to_dict(row)


def update(ngo_id: int, **fields) -> dict:
    sets: list[str] = []
    params: list = []
    json_fields = {"coverage_zones", "capabilities"}
    for key, value in fields.items():
        if value is None:
            continue
        if key in json_fields:
            sets.append(f"{key} = ?")
            params.append(json.dumps(value, separators=(",", ":")))
        elif key in ("available", "active"):
            sets.append(f"{key} = ?")
            params.append(int(value))
        else:
            sets.append(f"{key} = ?")
            params.append(value)
    if not sets:
        ngo = get_by_id(ngo_id)
        if ngo is None:
            raise ValueError(f"unknown NGO: {ngo_id}")
        return ngo
    sets.append("updated_at = ?")
    params.append(_now_iso())
    params.append(ngo_id)
    with get_conn() as conn:
        updated = conn.execute(
            f"UPDATE ngos SET {', '.join(sets)} WHERE id = ?", params
        ).rowcount
    if not updated:
        raise ValueError(f"unknown NGO: {ngo_id}")
    return get_by_id(ngo_id)


def get_active_case_count(ngo_id: int) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM emergency_cases "
            "WHERE ngo_id = ? AND status NOT IN ('resolved', 'closed')",
            (ngo_id,),
        ).fetchone()
    return row["n"] if row else 0
