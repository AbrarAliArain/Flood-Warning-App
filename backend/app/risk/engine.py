"""Risk engine orchestrator.

Selects the best available model (XGBoost when imports succeed and a
trained model file exists, otherwise the transparent heuristic), scores
a single zone or all zones, and attaches provenance metadata.
"""
from __future__ import annotations

from ..core import config
from ..core.logging_conf import get_logger
from ..data.districts import BY_ID as DISTRICTS
from ..ingest.demo_simulator import current_reading
from ..scoring.base import DistrictProfile
from .features import build_features
from .heuristic import assess_heuristic
from .spec import RiskAssessment
from .xgb import assess_xgboost, is_available, model_exists, model_version

log = get_logger(__name__)

_fallback_reason: str | None = None


def _resolve_model() -> str:
    """Return 'xgboost' or 'heuristic' based on config.RISK_MODEL and availability."""
    global _fallback_reason
    pref = config.RISK_MODEL
    if pref == "heuristic":
        _fallback_reason = "configured to use heuristic"
        return "heuristic"
    if pref == "xgboost":
        if is_available() and model_exists():
            return "xgboost"
        _fallback_reason = "XGBoost forced but unavailable"
        return "heuristic"
    if is_available() and model_exists():
        return "xgboost"
    reasons = []
    if not is_available():
        reasons.append("xgboost not installed")
    if not model_exists():
        reasons.append(f"model file missing ({config.XGB_MODEL_PATH.name})")
    _fallback_reason = "; ".join(reasons) if reasons else None
    return "heuristic"


def _count_reports(zone_id: str) -> int:
    try:
        from ..storage.db import get_conn
        with get_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM reports WHERE zone_id = ?", (zone_id,)
            ).fetchone()
            return row["n"] if row else 0
    except Exception:
        return 0


def active_model() -> dict:
    model = _resolve_model()
    info: dict = {
        "active": model,
        "xgboost_available": is_available(),
        "model_file_exists": model_exists(),
    }
    if model == "xgboost":
        info["version"] = model_version()
    if _fallback_reason:
        info["fallback_reason"] = _fallback_reason
    return info


def score_zone(
    district: DistrictProfile,
    report_count: int | None = None,
) -> RiskAssessment:
    reading = current_reading(district.zone_id, district.gauge)
    features = build_features(
        district, reading,
        report_count=report_count if report_count is not None else _count_reports(district.zone_id),
    )
    model = _resolve_model()
    assessment: RiskAssessment | None = None

    if model == "xgboost":
        assessment = assess_xgboost(
            district.zone_id, district.name, district.division,
            features, is_demo=reading.is_demo,
        )

    if assessment is None:
        assessment = assess_heuristic(
            district.zone_id, district.name, district.division,
            features, is_demo=reading.is_demo,
        )

    return assessment


def score_all() -> list[RiskAssessment]:
    results = []
    for district in DISTRICTS.values():
        try:
            results.append(score_zone(district))
        except Exception:
            log.exception("failed to score zone %s", district.zone_id)
    return results
