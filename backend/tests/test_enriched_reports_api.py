import pytest
from fastapi.testclient import TestClient

import app.storage.db as dbmod
from app.core import config
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(dbmod, "DB_PATH", tmp_path / "reports.db")
    monkeypatch.setattr(config, "UPLOAD_DIR", tmp_path / "uploads")
    dbmod.init_db()


def test_gps_report_resolves_zone_records_owner_and_returns_triage():
    registration = client.post(
        "/api/auth/register",
        json={
            "full_name": "GPS Reporter",
            "password": "safe-password-123",
            "email": "gps@example.test",
        },
    )
    token = registration.json()["access_token"]

    response = client.post(
        "/api/reports",
        headers={"Authorization": f"Bearer {token}"},
        data={
            "zone_id": "karachi",
            "latitude": "25.396",
            "longitude": "68.357",
            "emergency_type": "rescue",
            "severity": "critical",
            "description": "Two people are trapped and need urgent help.",
            "location_text": "Latifabad Unit 7",
        },
    )

    assert response.status_code == 201
    report = response.json()
    assert report["report_id"] == report["id"]
    assert report["zone_id"] == "hyderabad"
    assert report["user_id"] == registration.json()["user"]["id"]
    assert report["water_level"] == "severe"
    assert report["status"] == "submitted"
    assert report["timestamp"] == report["created_at"]
    assert report["ai_analysis"]["method"] == "rule_based_fallback"
    assert report["ai_analysis"]["human_review_required"] is True

    mine = client.get("/api/reports/mine", headers={"Authorization": f"Bearer {token}"})
    assert mine.status_code == 200
    assert [item["id"] for item in mine.json()["reports"]] == [report["id"]]
    assert client.get("/api/reports/mine").status_code == 401


def test_gps_requires_a_valid_sindh_location_or_legacy_zone():
    incomplete = client.post(
        "/api/reports",
        data={"latitude": "25.396", "description": "Flooding reported."},
    )
    assert incomplete.status_code == 422

    outside_sindh = client.post(
        "/api/reports",
        data={
            "latitude": "31.5204",
            "longitude": "74.3587",
            "description": "Flooding reported.",
        },
    )
    assert outside_sindh.status_code == 422

    missing_location = client.post(
        "/api/reports", data={"description": "Flooding reported."}
    )
    assert missing_location.status_code == 422


def test_valid_zone_falls_back_when_optional_gps_is_outside_sindh():
    response = client.post(
        "/api/reports",
        data={
            "zone_id": "hyderabad",
            "latitude": "31.5204",
            "longitude": "74.3587",
            "description": "Flooding reported.",
        },
    )

    assert response.status_code == 201
    assert response.json()["zone_id"] == "hyderabad"
    assert response.json()["latitude"] is None
    assert response.json()["longitude"] is None


def test_photo_upload_is_available_through_its_safe_url():
    response = client.post(
        "/api/reports",
        data={
            "zone_id": "hyderabad",
            "water_level": "high",
            "description": "Road access is blocked by floodwater.",
        },
        files={"photo": ("evidence.jpg", b"example-image-bytes", "image/jpeg")},
    )

    assert response.status_code == 201
    report = response.json()
    assert report["evidence_path"].endswith(".jpg")
    assert report["photo_url"] == report["evidence_url"]

    evidence = client.get(report["evidence_url"])
    assert evidence.status_code == 200
    assert evidence.content == b"example-image-bytes"
