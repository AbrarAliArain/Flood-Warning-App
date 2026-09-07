from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

VALID_CATEGORIES = {"low", "moderate", "high", "critical"}


def test_zones_returns_24_features():
    resp = client.get("/api/zones")
    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == 24


def test_every_zone_has_valid_risk():
    data = client.get("/api/zones").json()
    for feature in data["features"]:
        props = feature["properties"]
        assert 0 <= props["score"] <= 100
        assert props["category"] in VALID_CATEGORIES
        assert props["is_demo"] is True


def test_zone_detail_hyderabad():
    resp = client.get("/api/zones/hyderabad")
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["name"] == "Hyderabad"
    assert set(detail["factors"]) == {"rainfall", "river", "exposure", "historical"}
    assert detail["profile"]["houses_2022"] == 19556


def test_unknown_zone_404():
    assert client.get("/api/zones/atlantis").status_code == 404
