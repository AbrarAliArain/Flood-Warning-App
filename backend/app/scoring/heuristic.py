"""Composite heuristic risk scorer.

Methodology (from Lower_Sindh_Flood_Rainfall_Report.pdf, section 5):
    score = 0.5 * hazard + 0.3 * exposure + 0.2 * historical, rescaled 0-100
where hazard blends rainfall intensity (0.7) and river gauge level (0.3).
Weights are the report's hackathon defaults, not a calibrated scientific result.
"""
from ..data.gauges import BY_ID as GAUGE_BY_ID
from .base import DistrictProfile, LiveReading, RiskResult, categorize

WEIGHTS = {"hazard": 0.5, "exposure": 0.3, "historical": 0.2}
HAZARD_SPLIT = {"rainfall": 0.7, "river": 0.3}

# mm/hr treated as extreme cloudburst (PMD/NDMA urban-flooding trigger is 50-100mm
# in a short spell; 45 mm/hr used as the normalization ceiling).
RAIN_EXTREME_MM_HR = 45.0

# FFC flood-class thresholds in lacs cusecs per gauge (real data, ffd.pmd.gov.pk).
GAUGE_THRESHOLDS = {
    gid: {k: g[k] for k in ("low", "medium", "high", "very_high", "exceptional")}
    for gid, g in GAUGE_BY_ID.items()
}


def rainfall_norm(mm_hr: float, baseline_mm_yr: float) -> float:
    # Arid districts with low baselines flood at lower intensities (report sec. 6).
    baseline_factor = min(1.3, max(0.8, 150.0 / baseline_mm_yr))
    return min(1.0, (mm_hr / RAIN_EXTREME_MM_HR) * baseline_factor)


def river_norm(flow: float | None, gauge: str | None) -> float:
    if flow is None or gauge is None:
        return 0.2  # urban rainfall-driven zone, no riverine anchor
    t = GAUGE_THRESHOLDS[gauge]
    if flow < t["low"]:
        return 0.15
    if flow < t["medium"]:
        return 0.35
    if flow < t["high"]:
        return 0.55
    if flow < t["very_high"]:
        return 0.75
    if flow < t["exceptional"]:
        return 0.9
    return 1.0


class HeuristicScorer:
    def score(self, district: DistrictProfile, reading: LiveReading) -> RiskResult:
        r_norm = rainfall_norm(reading.rainfall_mm_hr, district.rainfall_baseline_mm_yr)
        v_norm = river_norm(reading.river_flow_lacs_cusecs, district.gauge)
        hazard = HAZARD_SPLIT["rainfall"] * r_norm + HAZARD_SPLIT["river"] * v_norm
        raw = (
            WEIGHTS["hazard"] * hazard
            + WEIGHTS["exposure"] * district.exposure_index
            + WEIGHTS["historical"] * district.historical_index
        )
        score = int(round(min(1.0, max(0.0, raw)) * 100))
        return RiskResult(
            zone_id=district.zone_id,
            name=district.name,
            score=score,
            category=categorize(score),
            rainfall_norm=round(r_norm, 3),
            river_norm=round(v_norm, 3),
            exposure=district.exposure_index,
            historical=district.historical_index,
            reading=reading,
        )
