from app.scoring.base import categorize, CRITICAL, HIGH, LOW, MODERATE, DistrictProfile, LiveReading
from app.scoring.heuristic import HeuristicScorer, rainfall_norm, river_norm


def _district(**overrides) -> DistrictProfile:
    base = dict(
        zone_id="test", name="Test", division="Hyderabad",
        rainfall_baseline_mm_yr=150, baseline_source="test",
        houses_2022=None, houses_source="test",
        exposure_index=0.7, exposure_source="test",
        historical_index=0.7, historical_source="test",
        gauge="kotri",
    )
    base.update(overrides)
    return DistrictProfile(**base)


def test_categorize_thresholds():
    assert categorize(0) == LOW
    assert categorize(39) == LOW
    assert categorize(40) == MODERATE
    assert categorize(59) == MODERATE
    assert categorize(60) == HIGH
    assert categorize(77) == HIGH
    assert categorize(78) == CRITICAL
    assert categorize(100) == CRITICAL


def test_score_within_bounds():
    scorer = HeuristicScorer()
    for rain in (0, 10, 45, 200):
        result = scorer.score(_district(), LiveReading(rainfall_mm_hr=rain, river_flow_lacs_cusecs=12))
        assert 0 <= result.score <= 100


def test_more_rain_means_more_risk():
    scorer = HeuristicScorer()
    dry = scorer.score(_district(), LiveReading(rainfall_mm_hr=5, river_flow_lacs_cusecs=2))
    wet = scorer.score(_district(), LiveReading(rainfall_mm_hr=45, river_flow_lacs_cusecs=2))
    assert wet.score > dry.score


def test_river_above_exceptional_maxes_river_norm():
    assert river_norm(9.5, "sukkur") == 1.0
    assert river_norm(None, None) == 0.2


def test_rainfall_norm_caps_at_one():
    assert rainfall_norm(500, 150) == 1.0
    assert rainfall_norm(0, 150) == 0.0


def test_extreme_inputs_yield_critical():
    scorer = HeuristicScorer()
    result = scorer.score(
        _district(exposure_index=1.0, historical_index=1.0),
        LiveReading(rainfall_mm_hr=100, river_flow_lacs_cusecs=20),
    )
    assert result.category == CRITICAL
