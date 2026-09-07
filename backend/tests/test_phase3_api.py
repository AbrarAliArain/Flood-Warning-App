import os
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

# isolate the database per test run
_tmp = tempfile.mkdtemp(prefix="aquashield_test_")

import app.storage.db as dbmod

dbmod.DB_PATH = Path(_tmp) / "test.db"
dbmod.init_db()

from app.main import app

client = TestClient(app)


def test_submit_and_list_report():
    resp = client.post(
        "/api/reports",
        data={"zone_id": "hyderabad", "water_level": "high", "description": "test flooding"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["zone_name"] == "Hyderabad"
    assert body["is_demo"] is False

    listing = client.get("/api/reports").json()["reports"]
    assert listing[0]["description"] == "test flooding"


def test_report_rejects_unknown_zone():
    resp = client.post(
        "/api/reports",
        data={"zone_id": "atlantis", "water_level": "high", "description": "x"},
    )
    assert resp.status_code == 404


def test_report_rejects_bad_water_level():
    resp = client.post(
        "/api/reports",
        data={"zone_id": "hyderabad", "water_level": "wet", "description": "x"},
    )
    assert resp.status_code == 422


def test_alerts_include_critical_zones():
    alerts = client.get("/api/alerts").json()["alerts"]
    zone_ids = {a["zone_id"] for a in alerts if a["severity"] == "critical"}
    assert "karachi" in zone_ids
    assert "hyderabad" in zone_ids


def test_issue_demo_alert():
    resp = client.post("/api/alerts/demo", json={"zone_id": "sukkur"})
    assert resp.status_code == 201
    assert resp.json()["severity"] == "warning"

    alerts = client.get("/api/alerts").json()["alerts"]
    assert any(a["zone_id"] == "sukkur" and a["severity"] == "warning" for a in alerts)


def test_analytics_shape():
    data = client.get("/api/analytics").json()
    assert set(data["distribution"]) == {"low", "moderate", "high", "critical"}
    assert sum(data["distribution"].values()) == 24
    assert data["trend_is_demo"] is True
    assert data["reports_count"] >= 1
