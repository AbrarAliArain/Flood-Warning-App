from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_subscribe_ok():
    resp = client.post(
        "/api/subscribe",
        json={"name": "Test Officer", "email": "officer@pdma.gov.pk", "organization": "PDMA"},
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "subscribed"


def test_subscribe_rejects_bad_email():
    resp = client.post("/api/subscribe", json={"name": "X", "email": "not-an-email"})
    assert resp.status_code == 422
