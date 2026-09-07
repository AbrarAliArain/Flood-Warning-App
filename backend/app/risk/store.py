"""Persistence for the risk engine.

Upserts the latest state into ``risk_zones`` and appends every computation
into ``risk_scores``.  SQL uses ``ON CONFLICT`` syntax that works on both
SQLite 3.24+ and Postgres.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from ..storage.db import get_conn
from .spec import RiskAssessment


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def persist(assessment: RiskAssessment) -> None:
    now = _now_iso()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO risk_zones (zone_id, name, division, score, category,
                                    model, factors, is_demo, computed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(zone_id) DO UPDATE SET
                score       = excluded.score,
                category    = excluded.category,
                model       = excluded.model,
                factors     = excluded.factors,
                is_demo     = excluded.is_demo,
                computed_at = excluded.computed_at
            """,
            (
                assessment.zone_id,
                assessment.name,
                assessment.division,
                assessment.score,
                assessment.band,
                assessment.model,
                json.dumps(assessment.features.as_dict(), separators=(",", ":")),
                int(assessment.is_demo),
                now,
            ),
        )
        conn.execute(
            """
            INSERT INTO risk_scores (zone_id, score, category, model,
                                     features, contributions, is_demo, computed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                assessment.zone_id,
                assessment.score,
                assessment.band,
                assessment.model,
                json.dumps(assessment.features.as_dict(), separators=(",", ":")),
                json.dumps(assessment.contributions, separators=(",", ":")),
                int(assessment.is_demo),
                now,
            ),
        )


def get_zone_history(zone_id: str, limit: int = 50) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT score, category, model, features, contributions,
                   is_demo, computed_at
            FROM risk_scores
            WHERE zone_id = ?
            ORDER BY computed_at DESC
            LIMIT ?
            """,
            (zone_id, limit),
        ).fetchall()
    return [
        {
            "score": r["score"],
            "band": r["category"],
            "model": r["model"],
            "features": json.loads(r["features"]),
            "contributions": json.loads(r["contributions"]),
            "is_demo": bool(r["is_demo"]),
            "computed_at": r["computed_at"],
        }
        for r in rows
    ]


def get_all_zones() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT zone_id, name, division, score, category, model,
                   factors, is_demo, computed_at
            FROM risk_zones
            ORDER BY score DESC
            """
        ).fetchall()
    return [
        {
            "zone_id": r["zone_id"],
            "name": r["name"],
            "division": r["division"],
            "score": r["score"],
            "band": r["category"],
            "model": r["model"],
            "factors": json.loads(r["factors"]),
            "is_demo": bool(r["is_demo"]),
            "computed_at": r["computed_at"],
        }
        for r in rows
    ]
