from dataclasses import dataclass, field


LOW = "low"
MODERATE = "moderate"
HIGH = "high"
CRITICAL = "critical"

CATEGORY_COLORS = {
    LOW: "#1b8a3f",
    MODERATE: "#f2c200",
    HIGH: "#ef7d00",
    CRITICAL: "#d21f1f",
}


def categorize(score: float) -> str:
    if score >= 78:
        return CRITICAL
    if score >= 60:
        return HIGH
    if score >= 40:
        return MODERATE
    return LOW


@dataclass
class DistrictProfile:
    zone_id: str
    name: str
    division: str
    rainfall_baseline_mm_yr: float
    baseline_source: str  # "report" | "demo-estimate"
    houses_2022: int | None
    houses_source: str
    exposure_index: float  # 0-1, qualitative per research docs
    exposure_source: str
    historical_index: float  # 0-1
    historical_source: str
    gauge: str | None  # kotri | sukkur | guddu | None (urban rainfall-driven)
    historical_events: list[int] = field(default_factory=list)
    risk_factors: list[str] = field(default_factory=list)


@dataclass
class LiveReading:
    rainfall_mm_hr: float
    river_flow_lacs_cusecs: float | None
    is_demo: bool = True


@dataclass
class RiskResult:
    zone_id: str
    name: str
    score: int
    category: str
    rainfall_norm: float
    river_norm: float
    exposure: float
    historical: float
    reading: LiveReading
