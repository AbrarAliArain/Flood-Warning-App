"""Train an XGBoost risk model on clearly-labelled synthetic data.

This script generates synthetic flood-risk samples using the same feature
extraction as the live engine, then labels them with the transparent
heuristic scorer.  The resulting model is stored at
``config.XGB_MODEL_PATH`` (default: ``models/flood_risk_xgb.json``).

The synthetic data is NOT real historical observations — it is a teaching
signal so the XGBoost path can demonstrate SHAP contributions in the
MVP.  A production deployment would replace the generator with actual
flood-event records.

Usage:
    python scripts/train_risk_model.py
"""
import json
import random
import sys
from pathlib import Path

# Allow running from repo root or scripts/ directory.
BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from app.core import config
from app.risk.features import FEATURE_NAMES
from app.risk.heuristic import score_heuristic
from app.risk.spec import RiskFeatures

SEED = 42
N_SAMPLES = 2000


def generate_sample(rng: random.Random) -> RiskFeatures:
    return RiskFeatures(
        rainfall_intensity=rng.uniform(0.0, 1.0),
        river_flow=rng.uniform(0.0, 1.0),
        elevation=rng.uniform(0.0, 1.0),
        drainage=rng.uniform(0.0, 1.0),
        exposure=rng.uniform(0.0, 1.0),
        historical=rng.uniform(0.0, 1.0),
        report_density=rng.uniform(0.0, 1.0),
    )


def build_dataset(rng: random.Random) -> tuple[list[list[float]], list[float]]:
    X: list[list[float]] = []
    y: list[float] = []
    for _ in range(N_SAMPLES):
        features = generate_sample(rng)
        score, _ = score_heuristic(features)
        X.append(features.as_vector())
        y.append(score / 100.0)
    return X, y


def main() -> None:
    try:
        import xgboost as xgb
    except ImportError:
        print("xgboost is not installed.  Install it first:  pip install xgboost")
        sys.exit(1)

    rng = random.Random(SEED)
    X, y = build_dataset(rng)

    dm = xgb.DMatrix(X, label=y, feature_names=FEATURE_NAMES)
    params = {
        "max_depth": 4,
        "learning_rate": 0.1,
        "objective": "reg:squarederror",
        "n_estimators": 100,
        "seed": SEED,
    }
    booster = xgb.train(params, dm, num_boost_round=100)

    model_dir = config.XGB_MODEL_PATH.parent
    model_dir.mkdir(parents=True, exist_ok=True)
    booster.save_model(str(config.XGB_MODEL_PATH))

    meta = {"version": "synthetic-v1", "n_samples": N_SAMPLES, "seed": SEED}
    meta_path = config.XGB_MODEL_PATH.with_suffix(".meta.json")
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print(f"Model saved to {config.XGB_MODEL_PATH}")
    print(f"Metadata saved to {meta_path}")
    print(f"  samples: {N_SAMPLES}, seed: {SEED}")


if __name__ == "__main__":
    main()
