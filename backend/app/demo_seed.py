"""Idempotent development/demo account provisioning."""

from .auth import service
from .core import security
from .storage.db import get_conn

DEMO_PASSWORD = "AquaShieldDemo2026!"
DEMO_NGO_NAME = "Sindh Rescue Network (DEMO)"
DEMO_ACCOUNTS = (
    ("Demo Citizen", "citizen@demo.example", "+923000000101", security.CITIZEN),
    ("Demo Responder", "responder@demo.example", "+923000000102", security.RESPONDER),
    ("Demo Administrator", "admin@demo.example", "+923000000103", security.ADMIN),
)


def seed_demo_accounts() -> list[str]:
    """Create clearly labelled demo identities without changing existing users."""
    timestamp = service.now_iso()
    with get_conn() as conn:
        ngo = conn.execute(
            "SELECT id FROM ngos WHERE name = ? ORDER BY id LIMIT 1",
            (DEMO_NGO_NAME,),
        ).fetchone()
        if ngo is None:
            ngo_id = conn.execute(
                "INSERT INTO ngos (name, organisation_type, contact_name, contact_phone, "
                "whatsapp_number, email, service_area, coverage_zones, latitude, longitude, "
                "service_radius_km, capabilities, max_concurrent_cases, is_demo, "
                "created_at, updated_at) "
                "VALUES (?, 'ngo', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)",
                (
                    DEMO_NGO_NAME,
                    "Demo Dispatch Lead",
                    "+923000000102",
                    "+923000000102",
                    "demo@sindhrescue.example",
                    "Lower Sindh",
                    '["hyderabad", "badin", "thatta", "sujawal", "mirpur-khas", "tando-allahyar", '
                    '"tando-muhammad-khan", "matiari"]',
                    25.396, 68.358,
                    80.0,
                    '["rescue", "boat", "medical", "evacuation"]',
                    10,
                    timestamp,
                    timestamp,
                ),
            ).lastrowid
        else:
            ngo_id = ngo["id"]

        _seed_extra_ngos(conn, timestamp)

    created: list[str] = []
    for full_name, email, phone, role in DEMO_ACCOUNTS:
        if service.find_by_identifier(email):
            continue
        service.create_user(
            full_name=full_name,
            password=DEMO_PASSWORD,
            role=role,
            phone=phone,
            email=email,
            ngo_id=ngo_id if role == security.RESPONDER else None,
            is_demo=True,
        )
        created.append(email)
    return created


def _seed_extra_ngos(conn, timestamp: str) -> None:
    extra = [
        {
            "name": "Upper Sindh Relief (DEMO)",
            "service_area": "Upper Sindh",
            "coverage_zones": '["sukkur", "ghotki", "khairpur", "kashmore", "jacobabad", "shikarpur"]',
            "capabilities": '["rescue", "boat", "medical"]',
            "latitude": 27.705,
            "longitude": 68.857,
            "whatsapp_number": "+923000000201",
        },
        {
            "name": "Central Sindh Aid Network (DEMO)",
            "service_area": "Central Sindh",
            "coverage_zones": '["larkana", "dadu", "jamshoro", "naushahro-feroze", '
                              '"shaheed-benazir-abad", "sanghar", "kambar-shahdad-kot"]',
            "capabilities": '["rescue", "medical", "evacuation", "pump"]',
            "latitude": 27.556,
            "longitude": 68.216,
            "whatsapp_number": "+923000000301",
        },
    ]
    for ngo in extra:
        existing = conn.execute(
            "SELECT id FROM ngos WHERE name = ?", (ngo["name"],)
        ).fetchone()
        if existing:
            continue
        conn.execute(
            """INSERT INTO ngos (name, organisation_type, contact_name, contact_phone,
               whatsapp_number, service_area, coverage_zones, latitude, longitude,
               service_radius_km, capabilities, max_concurrent_cases, is_demo,
               created_at, updated_at)
               VALUES (?, 'ngo', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
            (
                ngo["name"], f"Demo {ngo['service_area']} Lead",
                ngo["whatsapp_number"], ngo["whatsapp_number"],
                ngo["service_area"], ngo["coverage_zones"],
                ngo["latitude"], ngo["longitude"], 100.0,
                ngo["capabilities"], 8, timestamp, timestamp,
            ),
        )
