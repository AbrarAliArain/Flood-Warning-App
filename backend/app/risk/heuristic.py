"""Transparent additive heuristic scorer.

Serves as the always-available fallback when XGBoost is absent or the
trained model file is missing.  Weights are hand-tuned to approximate the
legacy ``app/scoring`` behaviour while operating on the new feature set
and producing the spec 0-100 band.

Per-feature contributions are returned so the UI can show a breakdown.
"""
from __future__ import annotations

from .spec import FEATURE_NAMES, RiskAssessment, RiskFeatures, classify

# Weights sum to 1.0.  Tuned so that hazard features (rain + river) dominate,
# consistent with the PMD report methodology.
WEIGHTS: dict[str, float] = {
    "rainfall_intensity": 0.25,
    "river_flow": 0.15,
    "elevation": 0.12,
    "drainage": 0.10,
    "exposure": 0.15,
    "historical": 0.15,
    "report_density": 0.08,
}


def score_heuristic(features: RiskFeatures) -> tuple[int, dict[str, float]]:
    contributions: dict[str, float] = {}
    raw = 0.0
    for name in FEATURE_NAMES:
        value = getattr(features, name)
        weight = WEIGHTS[name]
        weighted = weight * value
        contributions[name] = round(weighted * 100, 1)
        raw += weighted
    score = int(round(min(1.0, max(0.0, raw)) * 100))
    return score, contributions


def assess_heuristic(
    zone_id: str,
    name: str,
    division: str,
    features: RiskFeatures,
    is_demo: bool = True,
) -> RiskAssessment:
    score, contributions = score_heuristic(features)
    return RiskAssessment(
        zone_id=zone_id,
        name=name,
        division=division,
        score=score,
        band=classify(score),
        features=features,
        contributions=contributions,
        model="heuristic",
        is_demo=is_demo,
    )
