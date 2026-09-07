"""Tests for the NGO registry, matching, emergency case lifecycle and WhatsApp dispatch."""
import os
import pytest
from fastapi.testclient import TestClient

os.environ["WHATSAPP_FORCE_DEMO"] = "1"

import app.storage.db as dbmod
from app.auth import service as auth_service
from app.core import security
from app.demo_seed import seed_demo_accounts
from app.main import app
from app.ngos import match as ngo_match
from app.ngos import service as ngo_service
from app.cases import service as cases_service
from app.whatsapp import transport as wa

client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setattr(dbmod, "DB_PATH", tmp_path / "cases.db")
    dbmod.init_db()


def make_citizen(*, phone="+923001234567", name="Ayesha Citizen"):
    return auth_service.create_user(
        full_name=name, password="password-123", phone=phone, role="citizen"
    )


def make_report(citizen: dict, *, zone="hyderabad", severity="critical",
                emergency_type="rescue", latitude=25.3960, longitude=68.3578):
    from datetime import datetime, timezone
    with dbmod.get_conn() as conn:
        cursor = conn.execute(
            """INSERT INTO reports
               (user_id, zone_id, latitude, longitude, emergency_type,
                water_level, severity, description, status, is_demo, created_at)
               VALUES (?, ?, ?, ?, ?, 'severe', ?, ?, 'submitted', 1, ?)""",
            (citizen["id"], zone, latitude, longitude, emergency_type,
             severity, "People trapped, water rising fast",
             datetime.now(timezone.utc).isoformat()),
        )
        return cursor.lastrowid


# -------- NGO service --------

class TestNGOService:
    def test_list_all_empty(self):
        assert ngo_service.list_all() == []

    def test_create_and_get(self):
        ngo = ngo_service.create(
            name="Test Rescue",
            coverage_zones=["hyderabad", "karachi"],
            capabilities=["rescue", "boat"],
            whatsapp_number="+923000000000",
        )
        assert ngo["id"] is not None
        assert ngo["coverage_zones"] == ["hyderabad", "karachi"]
        assert ngo["capabilities"] == ["rescue", "boat"]
        fetched = ngo_service.get_by_id(ngo["id"])
        assert fetched["name"] == "Test Rescue"

    def test_update(self):
        ngo = ngo_service.create(name="Old Name", coverage_zones=["sukkur"])
        updated = ngo_service.update(ngo["id"], name="New Name", available=False)
        assert updated["name"] == "New Name"
        assert updated["available"] is False

    def test_active_case_count_zero(self):
        ngo = ngo_service.create(name="X")
        assert ngo_service.get_active_case_count(ngo["id"]) == 0


# -------- NGO matching --------

class TestNGOMatching:
    def test_no_ngos_returns_empty(self):
        assert ngo_match.match_ngos(zone_id="hyderabad") == []

    def test_zone_coverage_required(self):
        ngo_service.create(
            name="Only Karachi",
            coverage_zones=["karachi"],
            capabilities=["rescue"],
            whatsapp_number="+923000000001",
        )
        # Hyderabad not covered
        assert ngo_match.match_ngos(zone_id="hyderabad") == []

    def test_matches_covered_zone(self):
        ngo_service.create(
            name="Hyderabad Rescuers",
            coverage_zones=["hyderabad"],
            capabilities=["rescue", "boat"],
            whatsapp_number="+923000000002",
            latitude=25.396, longitude=68.3578,
        )
        matches = ngo_match.match_ngos(
            zone_id="hyderabad", emergency_type="rescue",
            latitude=25.396, longitude=68.3578,
        )
        assert len(matches) == 1
        assert matches[0]["ngo_name"] == "Hyderabad Rescuers"
        assert matches[0]["score"] > 0
        assert any("covers zone" in r for r in matches[0]["reasons"])

    def test_capability_bonus(self):
        ngo_service.create(
            name="Capable", coverage_zones=["hyderabad"],
            capabilities=["rescue", "boat", "medical"],
        )
        ngo_service.create(
            name="Limited", coverage_zones=["hyderabad"],
            capabilities=["rescue"],
        )
        matches = ngo_match.match_ngos(zone_id="hyderabad", emergency_type="rescue")
        by_name = {m["ngo_name"]: m for m in matches}
        assert by_name["Capable"]["score"] > by_name["Limited"]["score"]

    def test_demo_seed_match_for_hyderabad(self):
        seed_demo_accounts()
        matches = ngo_match.match_ngos(
            zone_id="hyderabad", emergency_type="rescue",
            latitude=25.396, longitude=68.3578,
        )
        assert matches, "demo NGOs should cover hyderabad"
        top = matches[0]
        assert "Sindh Rescue" in top["ngo_name"]
        assert top["score"] > 0
        assert top["whatsapp_number"]


# -------- WhatsApp transport --------

class TestWhatsAppTransport:
    def test_build_case_message_includes_fields(self):
        case = {
            "id": 1, "code": "EC-TEST1", "emergency_type": "rescue",
            "severity": "critical", "priority_label": "CRITICAL",
            "description": "water rising", "location_text": "Qasimabad",
            "contact_phone": "+923001234567",
            "latitude": 25.396, "longitude": 68.3578,
        }
        msg = wa.build_case_message(case)
        assert "EC-TEST1" in msg
        assert "rescue" in msg
        assert "CRITICAL" in msg
        assert "Qasimabad" in msg
        assert "google.com/maps" in msg
        assert "+923001234567" in msg

    def test_dispatch_demo_writes_comm_log(self):
        seed_demo_accounts()
        citizen = make_citizen()
        report_id = make_report(citizen)
        case = cases_service.create_from_report(
            user_id=citizen["id"], report_id=report_id,
            zone_id="hyderabad", latitude=25.396, longitude=68.3578,
            emergency_type="rescue", severity="critical",
            description="People trapped", contact_phone=citizen["phone"],
            is_demo=True,
        )
        logs = cases_service.get_communication_logs(case["id"])
        assert len(logs) >= 1
        assert logs[0]["status"] == "demo"
        assert logs[0]["transport"] == "demo"
        assert logs[0]["recipient"].startswith("+92")

    def test_dispatch_skips_without_recipient(self, monkeypatch):
        # Force the case to have no NGO phone
        case = {
            "id": 9999, "code": "EC-NOONE", "emergency_type": "flood",
            "severity": "high", "priority_label": "HIGH",
            "description": "test", "latitude": 25.0, "longitude": 68.0,
        }
        with dbmod.get_conn() as conn:
            # insert a stub case row so _write_log FK passes
            citizen = make_citizen(phone="+923009999999")
            report_id = make_report(citizen)
            cursor = conn.execute(
                """INSERT INTO emergency_cases
                   (code, user_id, report_id, zone_id, latitude, longitude,
                    emergency_type, severity, priority, priority_label,
                    status, communication_status, is_demo, created_at, updated_at)
                   VALUES ('EC-NOONE', ?, ?, 'hyderabad', 25.0, 68.0,
                    'flood', 'high', 4, 'HIGH', 'pending', 'not_sent', 1, ?, ?)""",
                (citizen["id"], report_id, wa._now_iso(), wa._now_iso()),
            )
            case["id"] = cursor.lastrowid
        result = wa.dispatch(case)
        assert result["status"] == "skipped"


# -------- Case lifecycle --------

class TestCaseLifecycle:
    def test_end_to_end_dispatch(self):
        seed_demo_accounts()
        citizen = make_citizen()
        report_id = make_report(citizen)
        case = cases_service.create_from_report(
            user_id=citizen["id"], report_id=report_id,
            zone_id="hyderabad", latitude=25.396, longitude=68.3578,
            emergency_type="rescue", severity="critical",
            description="People trapped, water rising fast",
            contact_phone=citizen["phone"],
            location_text="Qasimabad, Hyderabad",
            is_demo=True,
        )
        # Case fields
        assert case["status"] == "assigned"
        assert case["ngo_id"] is not None
        assert case["communication_status"] == "demo"
        assert case["priority"] >= 4
        assert case["code"].startswith("EC-")
        # NGO matched
        assert case["matches"]
        assert case["matches"][0]["ngo_name"].startswith("Sindh Rescue")
        # Dispatch block
        assert case["dispatch"]["status"] == "demo"
        assert case["dispatch"]["mode"] == "demo"
        # Audit events
        events = cases_service.get_events(case["id"])
        types = [e["event_type"] for e in events]
        assert types == ["created", "matched", "dispatched"]

    def test_transition_pending_to_assigned_to_in_progress_to_resolved(self):
        seed_demo_accounts()
        citizen = make_citizen()
        report_id = make_report(citizen)
        case = cases_service.create_from_report(
            user_id=citizen["id"], report_id=report_id,
            zone_id="hyderabad", latitude=25.396, longitude=68.3578,
            emergency_type="rescue", severity="critical",
            description="x", contact_phone=citizen["phone"],
            auto_dispatch=False,  # keep it in 'pending'
        )
        assert case["status"] == "pending"

        case = cases_service.transition(case["id"], "assigned", actor_role="admin")
        assert case["status"] == "assigned"

        case = cases_service.transition(case["id"], "in_progress", actor_role="responder")
        assert case["status"] == "in_progress"
        assert case["responded_at"] is not None

        case = cases_service.transition(case["id"], "resolved", actor_role="responder")
        assert case["status"] == "resolved"
        assert case["resolved_at"] is not None

    def test_transition_rejects_invalid(self):
        seed_demo_accounts()
        citizen = make_citizen()
        report_id = make_report(citizen)
        case = cases_service.create_from_report(
            user_id=citizen["id"], report_id=report_id,
            zone_id="hyderabad", latitude=25.396, longitude=68.3578,
            emergency_type="rescue", severity="critical",
            description="x", contact_phone=citizen["phone"],
            auto_dispatch=False,
        )
        with pytest.raises(ValueError, match="cannot transition"):
            cases_service.transition(case["id"], "resolved")

    def test_priority_boosted_by_risk_score(self):
        seed_demo_accounts()
        # Seed a high risk_score for hyderabad
        from datetime import datetime, timezone
        with dbmod.get_conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO risk_zones
                   (zone_id, name, division, score, category, model, factors,
                    is_demo, computed_at)
                   VALUES ('hyderabad', 'Hyderabad', 'Lower Sindh', 82,
                    'Critical', 'heuristic', '{}', 1, ?)""",
                (datetime.now(timezone.utc).isoformat(),),
            )
        citizen = make_citizen()
        report_id = make_report(citizen, severity="moderate")
        case = cases_service.create_from_report(
            user_id=citizen["id"], report_id=report_id,
            zone_id="hyderabad", latitude=25.396, longitude=68.3578,
            emergency_type="flood", severity="moderate",
            description="x", contact_phone=citizen["phone"],
            auto_dispatch=False,
        )
        # risk_score >= 75 should boost priority to CRITICAL (5)
        assert case["priority"] == 5
        assert case["priority_label"] == "CRITICAL"


# -------- API endpoints --------

class TestNGOAPI:
    def test_list_ngos_anonymous(self):
        seed_demo_accounts()
        resp = client.get("/api/ngos")
        assert resp.status_code == 200
        data = resp.json()
        assert "ngos" in data
        assert len(data["ngos"]) >= 3

    def test_get_single_ngo(self):
        seed_demo_accounts()
        resp = client.get("/api/ngos/1")
        assert resp.status_code == 200
        ngo = resp.json()
        assert ngo["id"] == 1
        assert "Sindh Rescue" in ngo["name"]

    def test_create_requires_admin(self):
        citizen = make_citizen()
        token = security.create_access_token(citizen["id"], citizen["role"])
        resp = client.post(
            "/api/ngos",
            json={"name": "Citizen NGO"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code in (401, 403)

    def test_admin_can_create(self):
        seed_demo_accounts()
        admin_token = self._admin_token()
        resp = client.post(
            "/api/ngos",
            json={
                "name": "Test NGO",
                "coverage_zones": ["badin"],
                "capabilities": ["rescue"],
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 201, resp.text

    def _admin_token(self):
        admin = auth_service.find_by_identifier("+923000000003")
        if admin is None:
            admin = auth_service.create_user(
                full_name="Admin", password="admin-password",
                role=security.ADMIN, phone="+923000000003", is_demo=True,
            )
        return security.create_access_token(admin["id"], admin["role"])


class TestCasesAPI:
    def test_from_report_end_to_end(self):
        seed_demo_accounts()
        citizen = make_citizen()
        token = security.create_access_token(citizen["id"], citizen["role"])
        report_id = make_report(citizen)

        resp = client.post(
            "/api/cases/from-report",
            json={"report_id": report_id},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["code"].startswith("EC-")
        assert data["status"] == "assigned"
        assert data["communication_status"] == "demo"

    def test_from_report_uses_zone_center_without_gps(self):
        seed_demo_accounts()
        citizen = make_citizen()
        token = security.create_access_token(citizen["id"], citizen["role"])
        report = client.post(
            "/api/reports",
            data={"zone_id": "hyderabad", "description": "No GPS rescue request"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert report.status_code == 201

        response = client.post(
            "/api/cases/from-report",
            json={"report_id": report.json()["id"]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201, response.text
        assert response.json()["latitude"] is not None
        assert response.json()["longitude"] is not None

    def test_list_own_cases(self):
        seed_demo_accounts()
        citizen = make_citizen()
        token = security.create_access_token(citizen["id"], citizen["role"])
        report_id = make_report(citizen)
        client.post(
            "/api/cases/from-report",
            json={"report_id": report_id},
            headers={"Authorization": f"Bearer {token}"},
        )
        resp = client.get(
            "/api/cases",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert len(resp.json()["cases"]) >= 1

    def test_match_preview_requires_auth(self):
        resp = client.post(
            "/api/cases/match",
            json={"zone_id": "hyderabad", "emergency_type": "rescue"},
        )
        assert resp.status_code in (401, 403)
