import pytest
from fastapi.testclient import TestClient

import app.storage.db as dbmod
from app.auth import service
from app.core import config, security
from app.demo_seed import DEMO_PASSWORD
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setattr(dbmod, "DB_PATH", tmp_path / "auth.db")
    dbmod.init_db()


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def register_payload(**overrides) -> dict:
    payload = {
        "full_name": "Ayesha Citizen",
        "password": "safe-password-123",
        "phone": "+923001234567",
        "email": "ayesha@example.test",
    }
    payload.update(overrides)
    return payload


def create_admin_token() -> str:
    admin = service.create_user(
        full_name="Demo Administrator",
        password="admin-password-123",
        role=security.ADMIN,
        email="admin@example.test",
        is_demo=True,
    )
    return security.create_access_token(admin["id"], admin["role"])


def create_ngo() -> int:
    timestamp = service.now_iso()
    with dbmod.get_conn() as conn:
        cursor = conn.execute(
            "INSERT INTO ngos (name, created_at, updated_at) VALUES (?, ?, ?)",
            ("Sindh Rescue Network", timestamp, timestamp),
        )
    return cursor.lastrowid


def test_registers_only_citizens_and_returns_a_working_token():
    response = client.post(
        "/api/auth/register",
        json=register_payload(role="responder"),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["role"] == security.CITIZEN
    assert "password" not in body["user"]

    profile = client.get("/api/auth/me", headers=auth_headers(body["access_token"]))
    assert profile.status_code == 200
    assert profile.json()["email"] == "ayesha@example.test"

    duplicate = client.post("/api/auth/register", json=register_payload())
    assert duplicate.status_code == 409


def test_login_rejects_bad_credentials_and_invalid_tokens():
    client.post("/api/auth/register", json=register_payload())

    bad_login = client.post(
        "/api/auth/login",
        json={"identifier": "ayesha@example.test", "password": "wrong-password"},
    )
    assert bad_login.status_code == 401
    assert bad_login.json()["detail"] == "invalid identifier or password"

    login = client.post(
        "/api/auth/login",
        json={"identifier": "ayesha@example.test", "password": "safe-password-123"},
    )
    assert login.status_code == 200
    assert login.json()["user"]["role"] == security.CITIZEN

    invalid_token = client.get(
        "/api/auth/me", headers=auth_headers("not-a-valid-jwt")
    )
    assert invalid_token.status_code == 401


def test_admin_routes_require_administrator_and_validate_responder_ngo():
    citizen = client.post("/api/auth/register", json=register_payload()).json()
    denied = client.get(
        "/api/auth/users", headers=auth_headers(citizen["access_token"])
    )
    assert denied.status_code == 403
    assert client.get("/api/auth/users").status_code == 401

    admin_headers = auth_headers(create_admin_token())
    missing_ngo = client.post(
        "/api/auth/users",
        headers=admin_headers,
        json=register_payload(
            full_name="Responder Without NGO",
            email="responder@example.test",
            phone="+923001234568",
            role=security.RESPONDER,
        ),
    )
    assert missing_ngo.status_code == 422

    ngo_id = create_ngo()
    provisioned = client.post(
        "/api/auth/users",
        headers=admin_headers,
        json=register_payload(
            full_name="Rescue Responder",
            email="responder@example.test",
            phone="+923001234568",
            role=security.RESPONDER,
            ngo_id=ngo_id,
        ),
    )
    assert provisioned.status_code == 201
    assert provisioned.json()["user"]["role"] == security.RESPONDER
    assert provisioned.json()["user"]["ngo_id"] == ngo_id


def test_admin_cannot_promote_a_citizen_without_an_ngo():
    citizen = service.create_user(
        full_name="Citizen To Promote",
        password="citizen-password-123",
        email="promote@example.test",
    )
    admin_headers = auth_headers(create_admin_token())

    rejected = client.patch(
        f"/api/auth/users/{citizen['id']}",
        headers=admin_headers,
        json={"role": security.RESPONDER},
    )
    assert rejected.status_code == 422

    ngo_id = create_ngo()
    promoted = client.patch(
        f"/api/auth/users/{citizen['id']}",
        headers=admin_headers,
        json={"role": security.RESPONDER, "ngo_id": ngo_id},
    )
    assert promoted.status_code == 200
    assert promoted.json()["role"] == security.RESPONDER
    assert promoted.json()["ngo_id"] == ngo_id


def test_startup_seeds_a_clearly_labelled_demo_administrator(monkeypatch):
    monkeypatch.setattr(config, "SEED_DEMO_DATA", True)

    with TestClient(app) as seeded_client:
        login = seeded_client.post(
            "/api/auth/login",
            json={"identifier": "admin@demo.example", "password": DEMO_PASSWORD},
        )

    assert login.status_code == 200
    assert login.json()["user"]["role"] == security.ADMIN
    assert login.json()["user"]["is_demo"] is True
