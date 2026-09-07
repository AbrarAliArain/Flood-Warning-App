"""Feature extraction for the risk engine.

Normalizes raw district/reading data into the ``RiskFeatures`` dataclass
used by both the heuristic fallback and the XGBoost model.
"""
from __future__ import annotations

from ..data.gauges import BY_ID as GAUGE_BY_ID
from ..ingest.demo_simulator import DEMO_GAUGE_FLOWS
from ..scoring.base import DistrictProfile, LiveReading
from .spec import RiskFeatures
from .terrain import get_drainage, get_elevation

# mm/hr ceiling for normalization (same as legacy scoring)
RAIN_EXTREME_MM_HR = 45.0

# Report-density ceiling: 50 reports in a zone is treated as saturation.
REPORT_DENSITY_CEILING = 50.0


def _rainfall_norm(mm_hr: float, baseline_mm_yr: float) -> float:
    baseline_factor = min(1.3, max(0.8, 150.0 / max(baseline_mm_yr, 1.0)))
    return min(1.0, (mm_hr / RAIN_EXTREME_MM_HR) * baseline_factor)


def _river_norm(flow: float | None, gauge: str | None) -> float:
    if flow is None or gauge is None:
        return 0.2
    g = GAUGE_BY_ID[gauge]
    if flow < g["low"]:
        return 0.15
    if flow < g["medium"]:
        return 0.35
    if flow < g["high"]:
        return 0.55
    if flow < g["very_high"]:
        return 0.75
    if flow < g["exceptional"]:
        return 0.9
    return 1.0


def _report_density_norm(report_count: int) -> float:
    return min(1.0, report_count / REPORT_DENSITY_CEILING)


def build_features(
    district: DistrictProfile,
    reading: LiveReading,
    report_count: int = 0,
) -> RiskFeatures:
    return RiskFeatures(
        rainfall_intensity=_rainfall_norm(
            reading.rainfall_mm_hr, district.rainfall_baseline_mm_yr
        ),
        river_flow=_river_norm(reading.river_flow_lacs_cusecs, district.gauge),
        elevation=get_elevation(district.zone_id),
        drainage=get_drainage(district.zone_id),
        exposure=district.exposure_index,
        historical=district.historical_index,
        report_density=_report_density_norm(report_count),
    )
