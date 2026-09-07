"""Demo early-warning engine.

Alerts are derived from the DEMO-simulated live readings, so every alert the
system raises is labelled DEMO. Critical zones (score >= 78) get an automatic
active alert; authorities can also issue a manual demo alert.
"""
from datetime import datetime, timezone

from ..data.districts import BY_ID, DISTRICTS
from ..ingest.demo_simulator import current_reading
from ..scoring.heuristic import HeuristicScorer
from ..storage.db import get_conn

scorer = HeuristicScorer()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def evaluate() -> None:
    with get_conn() as conn:
        existing = {
            row["zone_id"]
            for row in conn.execute(
                "SELECT zone_id FROM alerts WHERE active = 1 AND severity = 'critical'"
            )
        }
        for district in DISTRICTS:
            result = scorer.score(district, current_reading(district.zone_id, district.gauge))
            if result.category == "critical" and district.zone_id not in existing:
                conn.execute(
                    "INSERT INTO alerts (zone_id, severity, message, is_demo, active, created_at)"
                    " VALUES (?, 'critical', ?, 1, 1, ?)",
                    (
                        district.zone_id,
                        f"{district.name} scored {result.score}/100 (critical) on DEMO inputs",
                        _now(),
                    ),
                )


def issue_demo_alert(zone_id: str | None, message: str | None) -> dict:
    if zone_id is not None and zone_id not in BY_ID:
        raise ValueError(f"unknown zone: {zone_id}")
    name = BY_ID[zone_id].name if zone_id else "Sindh"
    text = message or f"DEMO flood alert issued for {name}. Monitor vulnerable communities and drainage hotspots."
    created_at = _now()
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO alerts (zone_id, severity, message, is_demo, active, created_at)"
            " VALUES (?, 'warning', ?, 1, 1, ?)",
            (zone_id, text, created_at),
        )
        alert_id = cur.lastrowid
    return {"id": alert_id, "zone_id": zone_id, "severity": "warning", "message": text, "created_at": created_at}


def active_alerts() -> list[dict]:
    evaluate()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM alerts WHERE active = 1 ORDER BY created_at DESC, id DESC"
        ).fetchall()
    alerts = []
    for row in rows:
        item = dict(row)
        district = BY_ID.get(item["zone_id"]) if item["zone_id"] else None
        item["zone_name"] = district.name if district else None
        item["is_demo"] = bool(item["is_demo"])
        alerts.append(item)
    return alerts


def division_warnings() -> list[dict]:
    """Group critical/high-risk districts by division and emit one warning per affected division."""
    from collections import defaultdict

    evaluate()

    # score every district fresh
    division_map: dict[str, dict] = defaultdict(lambda: {
        "division": "",
        "severity": "moderate",
        "districts": [],
        "critical_count": 0,
        "high_count": 0,
    })

    for district in DISTRICTS:
        result = scorer.score(district, current_reading(district.zone_id, district.gauge))
        if result.category not in ("critical", "high"):
            continue
        div = district.division
        entry = division_map[div]
        entry["division"] = div
        entry["districts"].append({
            "zone_id": district.zone_id,
            "name": district.name,
            "score": result.score,
            "category": result.category,
        })
        if result.category == "critical":
            entry["critical_count"] += 1
        else:
            entry["high_count"] += 1

    warnings = []
    for div, entry in division_map.items():
        critical_c = entry["critical_count"]
        high_c = entry["high_count"]
        severity = "critical" if critical_c > 0 else "high"
        names = [d["name"] for d in sorted(entry["districts"], key=lambda x: -x["score"])]

        if critical_c and high_c:
            summary = (
                f"{critical_c} CRITICAL and {high_c} HIGH risk district(s) detected "
                f"in {div} Division (DEMO): {', '.join(names)}. "
                "Immediate action recommended — notify local authorities, "
                "prepare evacuation plans and monitor embankments."
            )
        elif critical_c:
            summary = (
                f"{critical_c} CRITICAL risk district(s) in {div} Division (DEMO): "
                f"{', '.join(names)}. Emergency flood protocols should be activated."
            )
        else:
            summary = (
                f"{high_c} HIGH risk district(s) in {div} Division (DEMO): "
                f"{', '.join(names)}. Authorities should heighten monitoring and "
                "pre-position response teams."
            )

        warnings.append({
            "division": div,
            "severity": severity,
            "message": summary,
            "districts": entry["districts"],
            "critical_count": critical_c,
            "high_count": high_c,
            "is_demo": True,
            "generated_at": _now(),
        })

    # sort: critical divisions first, then by name
    warnings.sort(key=lambda w: (0 if w["severity"] == "critical" else 1, w["division"]))
    return warnings
