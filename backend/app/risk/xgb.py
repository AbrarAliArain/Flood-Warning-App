"""XGBoost model loader and scorer.

The trained model is stored as an XGBoost JSON file at
``config.XGB_MODEL_PATH``.  If xgboost is not installed or the model file
is absent, ``is_available()`` returns False and the engine falls back to
the transparent heuristic.

Contributions are SHAP values from ``predict(..., pred_contribs=True)``,
re-scaled to sum to the final 0-100 score.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..core import config
from .spec import FEATURE_NAMES, RiskAssessment, RiskFeatures, classify

_model = None
_load_attempted = False


def is_available() -> bool:
    try:
        import xgboost  # noqa: F401
        return True
    except ImportError:
        return False


def model_exists() -> bool:
    return config.XGB_MODEL_PATH.exists()


def _load() -> object | None:
    global _model, _load_attempted
    if _load_attempted:
        return _model
    _load_attempted = True
    if not is_available() or not model_exists():
        return None
    try:
        import xgboost as xgb
        booster = xgb.Booster()
        booster.load_model(str(config.XGB_MODEL_PATH))
        _model = booster
        return _model
    except Exception:
        _model = None
        return None


def model_version() -> str:
    if _load() is not None:
        meta_path = config.XGB_MODEL_PATH.with_suffix(".meta.json")
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                return f"xgboost:{meta.get('version', 'unknown')}"
            except (json.JSONDecodeError, OSError):
                pass
        return "xgboost:unknown"
    return ""


def score_xgboost(features: RiskFeatures) -> tuple[int, dict[str, float]] | None:
    booster = _load()
    if booster is None:
        return None
    try:
        import numpy as np
        import xgboost as xgb

        row = np.array(features.as_vector(), dtype=np.float32).reshape(1, -1)
        dm = xgb.DMatrix(row, feature_names=FEATURE_NAMES)
        raw_score = float(booster.predict(dm)[0])
        raw_contribs = booster.predict(dm, pred_contribs=True)[0]

        score = int(round(min(1.0, max(0.0, raw_score)) * 100))

        contrib_values = raw_contribs[:-1]
        total = sum(abs(v) for v in contrib_values) or 1.0
        contributions: dict[str, float] = {}
        for name, val in zip(FEATURE_NAMES, contrib_values):
            contributions[name] = round((abs(val) / total) * score, 1)
        return score, contributions
    except Exception:
        return None


def assess_xgboost(
    zone_id: str,
    name: str,
    division: str,
    features: RiskFeatures,
    is_demo: bool = True,
) -> RiskAssessment | None:
    result = score_xgboost(features)
    if result is None:
        return None
    score, contributions = result
    return RiskAssessment(
        zone_id=zone_id,
        name=name,
        division=division,
        score=score,
        band=classify(score),
        features=features,
        contributions=contributions,
        model=model_version(),
        is_demo=is_demo,
    )
