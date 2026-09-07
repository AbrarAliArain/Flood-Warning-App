"""Emergency case lifecycle.

A case is created when a citizen report is escalated (high/critical severity
or rescue/medical/evacuation type). The lifecycle:

  pending → assigned → in_progress → resolved
                  ↘ closed (by admin)

Every status transition is logged in ``case_events`` with actor info.
Priority is computed from report severity + local risk score.
"""
from __future__ import annotations

import json
import secrets
import string
from datetime import datetime, timezone

from ..core.logging_conf import get_logger
from ..data.safe_locations import CENTERS
from ..ngos import match as ngo_match
from ..ngos import service as ngo_service
from ..storage.db import get_conn
from ..whatsapp import transport as wa

log = get_logger(__name__)

VALID_TRANSITIONS = {
    "pending": {"assigned", "closed"},
    "assigned": {"in_progress", "closed"},
    "in_progress": {"resolved", "closed"},
    "resolved": set(),
    "closed": set(),
}

SEVERITY_PRIORITY = {"low": 1, "moderate": 2, "high": 4, "critical": 5}
PRIORITY_LABELS = {1: "LOW", 2: "MEDIUM", 3: "MEDIUM", 4: "HIGH", 5: "CRITICAL"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _generate_code() -> str:
    suffix = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
    return f"EC-{suffix}"


def _compute_priority(severity: str, risk_score: int | None = None) -> tuple[int, str]:
    base = SEVERITY_PRIORITY.get(severity, 2)
    if risk_score is not None:
        if risk_score >= 75:
            base = max(base, 5)
        elif risk_score >= 50:
            base = max(base, 4)
        elif risk_score >= 25:
            base = max(base, 3)
    return base, PRIORITY_LABELS.get(base, "MEDIUM")


def _get_risk_for_zone(zone_id: str) -> int | None:
    try:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT score FROM risk_zones WHERE zone_id = ?", (zone_id,)
            ).fetchone()
        return row["score"] if row else None
    except Exception:
        return None


def _row_to_dict(row) -> dict:
    case = dict(row)
    case["is_demo"] = bool(case["is_demo"])
    evidence = case.get("evidence_path")
    case["evidence_url"] = f"/uploads/{evidence}" if evidence else None
    return case


def _log_event(
    conn,
    case_id: int,
    event_type: str,
    from_status: str | None = None,
    to_status: str | None = None,
    actor_id: int | None = None,
    actor_role: str | None = None,
    note: str | None = None,
) -> None:
    conn.execute(
        """INSERT INTO case_events
           (case_id, event_type, from_status, to_status, actor_id, actor_role, note, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (case_id, event_type, from_status, to_status, actor_id, actor_role, note, _now_iso()),
    )


def get_by_id(case_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM emergency_cases WHERE id = ?", (case_id,)
        ).fetchone()
    return _row_to_dict(row) if row else None


def get_by_code(code: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM emergency_cases WHERE code = ?", (code,)
        ).fetchone()
    return _row_to_dict(row) if row else None


def list_cases(
    *,
    status: str | None = None,
    ngo_id: int | None = None,
    user_id: int | None = None,
    zone_id: str | None = None,
    limit: int = 50,
) -> list[dict]:
    conditions: list[str] = []
    params: list = []
    if status:
        conditions.append("status = ?")
        params.append(status)
    if ngo_id is not None:
        conditions.append("ngo_id = ?")
        params.append(ngo_id)
    if user_id is not None:
        conditions.append("user_id = ?")
        params.append(user_id)
    if zone_id:
        conditions.append("zone_id = ?")
        params.append(zone_id)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.append(limit)
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT * FROM emergency_cases {where} ORDER BY priority DESC, created_at DESC LIMIT ?",
            params,
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def create_from_report(
    *,
    user_id: int,
    report_id: int,
    zone_id: str,
    latitude: float | None = None,
    longitude: float | None = None,
    emergency_type: str = "flood",
    severity: str = "moderate",
    description: str | None = None,
    evidence_path: str | None = None,
    contact_phone: str | None = None,
    location_text: str | None = None,
    is_demo: bool = False,
    auto_dispatch: bool = True,
) -> dict:
    if latitude is None or longitude is None:
        latitude, longitude = CENTERS.get(zone_id, (None, None))
    if latitude is None or longitude is None:
        raise ValueError(f"no fallback coordinates available for zone: {zone_id}")

    risk_score = _get_risk_for_zone(zone_id)
    priority, priority_label = _compute_priority(severity, risk_score)
    code = _generate_code()
    now = _now_iso()

    # Phase 1 — persist the case + NGO assignment in one committed transaction.
    # The block below MUST exit before WhatsApp dispatch runs, because dispatch
    # opens its own connections (communication_logs + a status update) and
    # SQLite only allows one writer at a time.
    with get_conn() as conn:
        cursor = conn.execute(
            """INSERT INTO emergency_cases
               (code, user_id, report_id, zone_id, latitude, longitude,
                emergency_type, severity, description, evidence_path,
                contact_phone, risk_score, risk_category, priority,
                priority_label, status, communication_status,
                is_demo, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', 'not_sent', ?, ?, ?)""",
            (
                code, user_id, report_id, zone_id, latitude, longitude,
                emergency_type, severity, description, evidence_path,
                contact_phone, risk_score,
                _risk_category(risk_score),
                priority, priority_label,
                int(is_demo), now, now,
            ),
        )
        case_id = cursor.lastrowid
        _log_event(conn, case_id, "created", to_status="pending",
                   actor_id=user_id, actor_role="citizen",
                   note=f"Created from report #{report_id}")

        matches = ngo_match.match_ngos(
            zone_id=zone_id, emergency_type=emergency_type,
            latitude=latitude, longitude=longitude,
        )

        assigned_ngo = None
        if matches and auto_dispatch:
            best = matches[0]
            assigned_ngo = ngo_service.get_by_id(best["ngo_id"])
            conn.execute(
                """UPDATE emergency_cases SET ngo_id = ?, match_reason = ?,
                   status = 'assigned', assigned_at = ?, updated_at = ?
                   WHERE id = ?""",
                (best["ngo_id"], json.dumps(best["reasons"], separators=(",", ":")),
                 now, now, case_id),
            )
            _log_event(conn, case_id, "matched", from_status="pending",
                       to_status="assigned", actor_role="system",
                       note=f"Matched to {best['ngo_name']} (score: {best['score']})")
    # Phase 1 commits here — the write lock is released before any dispatch IO.

    dispatch_result = None
    if assigned_ngo is not None:
        case_dict = get_by_id(case_id)
        case_dict["ngo_whatsapp"] = assigned_ngo.get("whatsapp_number") or assigned_ngo.get("contact_phone")
        case_dict["ngo_phone"] = assigned_ngo.get("contact_phone")
        if location_text:
            case_dict["location_text"] = location_text

        # Phase 2 — dispatch owns its DB work (communication_logs insert +
        # emergency_cases.communication_status update), so run it with no
        # outer connection held.
        dispatch_result = wa.dispatch(case_dict)

        comm_status = dispatch_result.get("status", "not_sent")
        with get_conn() as conn:
            _log_event(conn, case_id, "dispatched", actor_role="system",
                       note=f"WhatsApp {comm_status}: {dispatch_result.get('mode', '?')}")

    row_dict = get_by_id(case_id)
    result = dict(row_dict)
    result["matches"] = matches
    if dispatch_result:
        result["dispatch"] = dispatch_result
    return result


def transition(
    case_id: int,
    new_status: str,
    *,
    actor_id: int | None = None,
    actor_role: str | None = None,
    note: str | None = None,
) -> dict:
    case = get_by_id(case_id)
    if case is None:
        raise ValueError(f"unknown case: {case_id}")

    allowed = VALID_TRANSITIONS.get(case["status"], set())
    if new_status not in allowed:
        raise ValueError(
            f"cannot transition from {case['status']} to {new_status}; "
            f"allowed: {sorted(allowed)}"
        )

    now = _now_iso()
    with get_conn() as conn:
        updates = ["status = ?", "updated_at = ?"]
        params: list = [new_status, now]
        if new_status == "in_progress":
            updates.append("responded_at = ?")
            params.append(now)
        elif new_status == "resolved":
            updates.append("resolved_at = ?")
            params.append(now)
        params.append(case_id)
        conn.execute(
            f"UPDATE emergency_cases SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        _log_event(conn, case_id, "status_change",
                   from_status=case["status"], to_status=new_status,
                   actor_id=actor_id, actor_role=actor_role, note=note)

    return get_by_id(case_id)


def get_events(case_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM case_events WHERE case_id = ? ORDER BY created_at",
            (case_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_communication_logs(case_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM communication_logs WHERE case_id = ? ORDER BY created_at DESC",
            (case_id,),
        ).fetchall()
    results = []
    for r in rows:
        entry = dict(r)
        entry["is_demo"] = bool(entry["is_demo"])
        try:
            entry["payload"] = json.loads(entry["payload"])
        except (json.JSONDecodeError, TypeError):
            pass
        results.append(entry)
    return results


def _risk_category(score: int | None) -> str | None:
    if score is None:
        return None
    if score >= 75:
        return "Critical"
    if score >= 50:
        return "High"
    if score >= 25:
        return "Medium"
    return "Low"
