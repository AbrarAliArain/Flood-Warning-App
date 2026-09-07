"""Risk-engine bands, feature definitions, and shared dataclasses.

Bands follow the project spec (0-24 Low, 25-49 Medium, 50-74 High,
75-100 Critical).  The legacy ``app/scoring`` module keeps its own
40/60/78 bands so existing dashboards are unaffected.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Bands
# ---------------------------------------------------------------------------
LOW = "Low"
MEDIUM = "Medium"
HIGH = "High"
CRITICAL = "Critical"

BAND_COLORS = {
    LOW: "#1b8a3f",
    MEDIUM: "#f2c200",
    HIGH: "#ef7d00",
    CRITICAL: "#d21f1f",
}


def classify(score: int) -> str:
    if score >= 75:
        return CRITICAL
    if score >= 50:
        return HIGH
    if score >= 25:
        return MEDIUM
    return LOW


# ---------------------------------------------------------------------------
# Features
# ---------------------------------------------------------------------------
FEATURE_NAMES = [
    "rainfall_intensity",
    "river_flow",
    "elevation",
    "drainage",
    "exposure",
    "historical",
    "report_density",
]

FEATURE_LABELS = {
    "rainfall_intensity": "Rainfall intensity",
    "river_flow": "River flow level",
    "elevation": "Low elevation risk",
    "drainage": "Poor drainage",
    "exposure": "Population exposure",
    "historical": "Historical flood frequency",
    "report_density": "Community report density",
}


@dataclass
class RiskFeatures:
    rainfall_intensity: float
    river_flow: float
    elevation: float
    drainage: float
    exposure: float
    historical: float
    report_density: float

    def as_vector(self) -> list[float]:
        return [getattr(self, n) for n in FEATURE_NAMES]

    def as_dict(self) -> dict[str, float]:
        return {n: round(getattr(self, n), 3) for n in FEATURE_NAMES}


@dataclass
class RiskAssessment:
    zone_id: str
    name: str
    division: str
    score: int
    band: str
    features: RiskFeatures
    contributions: dict[str, float] = field(default_factory=dict)
    model: str = "heuristic"
    is_demo: bool = True
