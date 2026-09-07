from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_predict_returns_score_and_level():
    resp = client.post(
        "/api/predict",
        json={"zone_id": "hyderabad", "rainfall_mm_hr": 120, "river_flow_lacs_cusecs": 7.8},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["risk_score"] >= 78
    assert body["risk_level"] == "CRITICAL"
    assert 0 <= body["flood_probability"] <= 1


def test_predict_low_inputs_stay_low_risk_zone():
    resp = client.post(
        "/api/predict",
        json={"zone_id": "tharparkar", "rainfall_mm_hr": 2, "river_flow_lacs_cusecs": 1},
    )
    assert resp.json()["risk_level"] == "LOW"


def test_predict_validates_input():
    assert (
        client.post("/api/predict", json={"zone_id": "hyderabad", "rainfall_mm_hr": -5}).status_code
        == 422
    )
    assert client.post("/api/predict", json={"zone_id": "atlantis"}).status_code == 404
