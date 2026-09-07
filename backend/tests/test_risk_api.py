"""Tests for the /api/risk endpoints."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

VALID_BANDS = {"Low", "Medium", "High", "Critical"}


class TestModelEndpoint:
    def test_model_info(self):
        resp = client.get("/api/risk/model")
        assert resp.status_code == 200
        data = resp.json()
        assert "active" in data
        assert data["active"] in ("heuristic", "xgboost")
        assert "xgboost_available" in data


class TestZonesEndpoint:
    def test_list_zones(self):
        resp = client.get("/api/risk/zones")
        assert resp.status_code == 200
        data = resp.json()
        assert "zones" in data
        zones = data["zones"]
        assert len(zones) >= 24

    def test_zone_bands_valid(self):
        resp = client.get("/api/risk/zones")
        for z in resp.json()["zones"]:
            assert z["band"] in VALID_BANDS
            assert 0 <= z["score"] <= 100

    def test_get_single_zone(self):
        resp = client.get("/api/risk/zones/karachi")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Karachi"
        assert data["band"] in VALID_BANDS
        assert "features" in data
        assert "contributions" in data

    def test_unknown_zone_404(self):
        resp = client.get("/api/risk/zones/atlantis")
        assert resp.status_code == 404

    def test_zone_history(self):
        client.get("/api/risk/zones/karachi")
        resp = client.get("/api/risk/zones/karachi/history")
        assert resp.status_code == 200
        data = resp.json()
        assert data["zone_id"] == "karachi"
        assert isinstance(data["history"], list)


class TestScoreEndpoint:
    def test_score_all(self):
        resp = client.post("/api/risk/score", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert "scored" in data
        assert data["scored"] == 24

    def test_score_single_zone(self):
        resp = client.post("/api/risk/score", json={"zone_id": "badin"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["zone_id"] == "badin"
        assert "contributions" in data
        assert data["band"] in VALID_BANDS


class TestRefreshEndpoint:
    def test_refresh_requires_auth(self):
        resp = client.post("/api/risk/refresh")
        assert resp.status_code == 401
