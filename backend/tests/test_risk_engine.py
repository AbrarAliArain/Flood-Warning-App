"""Tests for the new risk engine (app/risk)."""
import pytest

from app.risk.spec import (
    CRITICAL, HIGH, LOW, MEDIUM, RiskFeatures, classify,
)
from app.risk.terrain import get_drainage, get_elevation
from app.risk.features import build_features
from app.risk.heuristic import assess_heuristic, score_heuristic, WEIGHTS
from app.risk.engine import active_model, score_all, score_zone
from app.risk.store import get_all_zones, get_zone_history, persist
from app.scoring.base import DistrictProfile, LiveReading


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _district(**overrides) -> DistrictProfile:
    base = dict(
        zone_id="test-zone", name="Test Zone", division="Hyderabad",
        rainfall_baseline_mm_yr=150, baseline_source="test",
        houses_2022=None, houses_source="test",
        exposure_index=0.7, exposure_source="test",
        historical_index=0.7, historical_source="test",
        gauge="kotri",
    )
    base.update(overrides)
    return DistrictProfile(**base)


def _features(**overrides) -> RiskFeatures:
    base = dict(
        rainfall_intensity=0.5, river_flow=0.5, elevation=0.5,
        drainage=0.5, exposure=0.5, historical=0.5, report_density=0.3,
    )
    base.update(overrides)
    return RiskFeatures(**base)


# ---------------------------------------------------------------------------
# Band classification (spec bands)
# ---------------------------------------------------------------------------
class TestClassify:
    def test_low_band(self):
        assert classify(0) == LOW
        assert classify(24) == LOW

    def test_medium_band(self):
        assert classify(25) == MEDIUM
        assert classify(49) == MEDIUM

    def test_high_band(self):
        assert classify(50) == HIGH
        assert classify(74) == HIGH

    def test_critical_band(self):
        assert classify(75) == CRITICAL
        assert classify(100) == CRITICAL

    def test_boundary_monotonicity(self):
        for s in range(100):
            assert classify(s) in (LOW, MEDIUM, HIGH, CRITICAL)


# ---------------------------------------------------------------------------
# Terrain lookups
# ---------------------------------------------------------------------------
class TestTerrain:
    def test_known_zone(self):
        assert 0 <= get_elevation("badin") <= 1
        assert get_elevation("badin") > 0.5

    def test_unknown_zone_defaults(self):
        assert get_elevation("atlantis") == 0.5
        assert get_drainage("atlantis") == 0.5


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------
class TestFeatures:
    def test_build_features_from_district(self):
        d = _district()
        r = LiveReading(rainfall_mm_hr=20, river_flow_lacs_cusecs=4.0)
        f = build_features(d, r, report_count=5)
        assert 0 <= f.rainfall_intensity <= 1
        assert 0 <= f.river_flow <= 1
        assert f.exposure == 0.7

    def test_report_density_normalization(self):
        d = _district()
        r = LiveReading(rainfall_mm_hr=10, river_flow_lacs_cusecs=2.0)
        low = build_features(d, r, report_count=0)
        high = build_features(d, r, report_count=50)
        assert low.report_density < high.report_density
        assert high.report_density == 1.0

    def test_as_vector_length(self):
        f = _features()
        assert len(f.as_vector()) == 7

    def test_as_dict_keys(self):
        f = _features()
        expected = {"rainfall_intensity", "river_flow", "elevation",
                    "drainage", "exposure", "historical", "report_density"}
        assert set(f.as_dict().keys()) == expected


# ---------------------------------------------------------------------------
# Heuristic scorer
# ---------------------------------------------------------------------------
class TestHeuristic:
    def test_weights_sum_to_one(self):
        assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9

    def test_score_bounds(self):
        f = _features()
        score, contributions = score_heuristic(f)
        assert 0 <= score <= 100

    def test_all_zero_features(self):
        f = _features(
            rainfall_intensity=0, river_flow=0, elevation=0,
            drainage=0, exposure=0, historical=0, report_density=0,
        )
        score, _ = score_heuristic(f)
        assert score == 0

    def test_all_max_features(self):
        f = _features(
            rainfall_intensity=1, river_flow=1, elevation=1,
            drainage=1, exposure=1, historical=1, report_density=1,
        )
        score, _ = score_heuristic(f)
        assert score == 100

    def test_more_rain_means_higher_score(self):
        dry = _features(rainfall_intensity=0.1)
        wet = _features(rainfall_intensity=0.9)
        dry_score, _ = score_heuristic(dry)
        wet_score, _ = score_heuristic(wet)
        assert wet_score > dry_score

    def test_contributions_sum_approximately_to_score(self):
        f = _features(rainfall_intensity=0.8, river_flow=0.6)
        score, contributions = score_heuristic(f)
        contrib_sum = sum(contributions.values())
        assert abs(contrib_sum - score) < 2.0

    def test_assess_heuristic_model_label(self):
        f = _features()
        a = assess_heuristic("test", "Test", "Div", f)
        assert a.model == "heuristic"
        assert a.band == classify(a.score)


# ---------------------------------------------------------------------------
# Engine orchestrator
# ---------------------------------------------------------------------------
class TestEngine:
    def test_active_model_reports_info(self):
        info = active_model()
        assert "active" in info
        assert info["active"] in ("heuristic", "xgboost")

    def test_score_all_returns_24(self):
        results = score_all()
        assert len(results) == 24

    def test_score_zone_single(self):
        d = _district(zone_id="karachi", name="Karachi", division="Karachi",
                      rainfall_baseline_mm_yr=156, gauge=None)
        a = score_zone(d)
        assert 0 <= a.score <= 100
        assert a.band in (LOW, MEDIUM, HIGH, CRITICAL)
        assert a.zone_id == "karachi"


# ---------------------------------------------------------------------------
# Store (persistence)
# ---------------------------------------------------------------------------
class TestStore:
    def test_persist_and_retrieve(self):
        f = _features()
        a = assess_heuristic("store-test", "Store Test", "Div", f)
        persist(a)
        zones = get_all_zones()
        found = [z for z in zones if z["zone_id"] == "store-test"]
        assert len(found) == 1
        assert found[0]["score"] == a.score

    def test_history_appends(self):
        f = _features(rainfall_intensity=0.3)
        a1 = assess_heuristic("hist-test", "Hist Test", "Div", f)
        persist(a1)
        f2 = _features(rainfall_intensity=0.9)
        a2 = assess_heuristic("hist-test", "Hist Test", "Div", f2)
        persist(a2)
        history = get_zone_history("hist-test")
        assert len(history) >= 2
