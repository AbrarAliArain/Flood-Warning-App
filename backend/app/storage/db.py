"""SQLite storage layer.

Schema is written to map 1:1 onto the PostGIS DDL in
`app/storage/postgres/schema.sql`: coordinates live in REAL latitude/longitude
columns here and in `geography(Point,4326)` there, and JSON columns become
`jsonb`. Swapping databases is a connection change, not a rewrite.
"""
import sqlite3
from pathlib import Path

from ..core import config

DB_PATH = Path(__file__).resolve().parent.parent.parent / "aquashield.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS ngos (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    name                 TEXT NOT NULL,
    organisation_type    TEXT NOT NULL DEFAULT 'ngo',
    contact_name         TEXT,
    contact_phone        TEXT,
    whatsapp_number      TEXT,
    email                TEXT,
    service_area         TEXT,
    coverage_zones       TEXT NOT NULL DEFAULT '[]',
    latitude             REAL,
    longitude            REAL,
    service_radius_km    REAL,
    capabilities         TEXT NOT NULL DEFAULT '[]',
    available            INTEGER NOT NULL DEFAULT 1,
    active               INTEGER NOT NULL DEFAULT 1,
    max_concurrent_cases INTEGER NOT NULL DEFAULT 5,
    is_demo              INTEGER NOT NULL DEFAULT 0,
    created_at           TEXT NOT NULL,
    updated_at           TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name     TEXT NOT NULL,
    phone         TEXT UNIQUE,
    email         TEXT UNIQUE,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'citizen',
    ngo_id        INTEGER REFERENCES ngos(id),
    is_active     INTEGER NOT NULL DEFAULT 1,
    is_demo       INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reports (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id        INTEGER REFERENCES users(id),
    zone_id        TEXT NOT NULL,
    latitude       REAL,
    longitude      REAL,
    emergency_type TEXT NOT NULL DEFAULT 'flood',
    water_level    TEXT NOT NULL,
    severity       TEXT NOT NULL DEFAULT 'moderate',
    description    TEXT NOT NULL,
    location_text  TEXT,
    evidence_path  TEXT,
    status         TEXT NOT NULL DEFAULT 'submitted',
    ai_analysis    TEXT,
    is_demo        INTEGER NOT NULL DEFAULT 0,
    created_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS alerts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    zone_id    TEXT,
    severity   TEXT NOT NULL,
    message    TEXT NOT NULL,
    is_demo    INTEGER NOT NULL DEFAULT 1,
    active     INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    email        TEXT NOT NULL,
    organization TEXT,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS risk_zones (
    zone_id     TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    division    TEXT NOT NULL,
    score       INTEGER NOT NULL,
    category    TEXT NOT NULL,
    model       TEXT NOT NULL,
    factors     TEXT NOT NULL DEFAULT '{}',
    is_demo     INTEGER NOT NULL DEFAULT 1,
    computed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS risk_scores (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    zone_id       TEXT NOT NULL,
    score         INTEGER NOT NULL,
    category      TEXT NOT NULL,
    model         TEXT NOT NULL,
    features      TEXT NOT NULL DEFAULT '{}',
    contributions TEXT NOT NULL DEFAULT '{}',
    is_demo       INTEGER NOT NULL DEFAULT 1,
    computed_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS flood_hotspots (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    zone_id             TEXT,
    latitude            REAL NOT NULL,
    longitude           REAL NOT NULL,
    radius_km           REAL NOT NULL,
    report_count        INTEGER NOT NULL DEFAULT 0,
    recent_count        INTEGER NOT NULL DEFAULT 0,
    density_per_100km2  REAL NOT NULL DEFAULT 0,
    level               TEXT NOT NULL,
    trend               TEXT NOT NULL DEFAULT 'stable',
    max_severity        TEXT,
    dominant_type       TEXT,
    is_demo             INTEGER NOT NULL DEFAULT 0,
    first_seen          TEXT,
    updated_at          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS emergency_cases (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    code                 TEXT UNIQUE NOT NULL,
    user_id              INTEGER NOT NULL REFERENCES users(id),
    report_id            INTEGER REFERENCES reports(id),
    zone_id              TEXT,
    latitude             REAL NOT NULL,
    longitude            REAL NOT NULL,
    emergency_type       TEXT NOT NULL,
    severity             TEXT NOT NULL,
    description          TEXT,
    evidence_path        TEXT,
    contact_phone        TEXT,
    risk_score           INTEGER,
    risk_category        TEXT,
    priority             INTEGER NOT NULL DEFAULT 3,
    priority_label       TEXT NOT NULL DEFAULT 'MEDIUM',
    status               TEXT NOT NULL DEFAULT 'pending',
    ngo_id               INTEGER REFERENCES ngos(id),
    assigned_user_id     INTEGER REFERENCES users(id),
    match_reason         TEXT,
    communication_status TEXT NOT NULL DEFAULT 'not_sent',
    is_demo              INTEGER NOT NULL DEFAULT 0,
    created_at           TEXT NOT NULL,
    assigned_at          TEXT,
    responded_at         TEXT,
    resolved_at          TEXT,
    updated_at           TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS case_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id     INTEGER NOT NULL REFERENCES emergency_cases(id),
    event_type  TEXT NOT NULL,
    from_status TEXT,
    to_status   TEXT,
    actor_id    INTEGER,
    actor_role  TEXT,
    note        TEXT,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS communication_logs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id             INTEGER REFERENCES emergency_cases(id),
    channel             TEXT NOT NULL DEFAULT 'whatsapp',
    transport           TEXT NOT NULL,
    direction           TEXT NOT NULL DEFAULT 'outbound',
    recipient           TEXT NOT NULL,
    payload             TEXT NOT NULL DEFAULT '{}',
    status              TEXT NOT NULL,
    provider_message_id TEXT,
    deeplink            TEXT,
    is_demo             INTEGER NOT NULL DEFAULT 1,
    error               TEXT,
    created_at          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS knowledge_documents (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    doc         TEXT NOT NULL,
    heading     TEXT NOT NULL,
    text        TEXT NOT NULL,
    source      TEXT,
    is_official INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);

-- coordinate_source distinguishes a surveyed fix from a district centroid, so
-- the API can label approximate rows instead of implying door-level accuracy.
CREATE TABLE IF NOT EXISTS safe_locations (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    name              TEXT NOT NULL,
    category          TEXT NOT NULL DEFAULT 'shelter',
    zone_id           TEXT NOT NULL,
    area              TEXT,
    latitude          REAL NOT NULL,
    longitude         REAL NOT NULL,
    coordinate_source TEXT NOT NULL DEFAULT 'district_center',
    phone             TEXT,
    capacity          INTEGER,
    notes             TEXT,
    is_demo           INTEGER NOT NULL DEFAULT 1,
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL,
    UNIQUE (name, zone_id)
);
"""

# Applied after _migrate(): some indexed columns only reach older databases
# through the ALTER TABLE pass.
INDEXES = """
CREATE INDEX IF NOT EXISTS idx_reports_zone        ON reports(zone_id);
CREATE INDEX IF NOT EXISTS idx_reports_user        ON reports(user_id);
CREATE INDEX IF NOT EXISTS idx_reports_created     ON reports(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_reports_coords      ON reports(latitude, longitude);
CREATE INDEX IF NOT EXISTS idx_risk_scores_zone    ON risk_scores(zone_id, computed_at DESC);
CREATE INDEX IF NOT EXISTS idx_cases_status        ON emergency_cases(status);
CREATE INDEX IF NOT EXISTS idx_cases_ngo           ON emergency_cases(ngo_id);
CREATE INDEX IF NOT EXISTS idx_cases_user          ON emergency_cases(user_id);
CREATE INDEX IF NOT EXISTS idx_cases_priority      ON emergency_cases(priority, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_case_events_case    ON case_events(case_id);
CREATE INDEX IF NOT EXISTS idx_comm_logs_case      ON communication_logs(case_id);
CREATE INDEX IF NOT EXISTS idx_hotspots_level      ON flood_hotspots(level);
CREATE INDEX IF NOT EXISTS idx_ngos_active         ON ngos(active, available);
CREATE INDEX IF NOT EXISTS idx_safe_locations_zone ON safe_locations(zone_id);
CREATE INDEX IF NOT EXISTS idx_safe_locations_cat  ON safe_locations(category);
"""

# Columns added to databases created by an earlier version of the app.
_REPORT_MIGRATIONS = {
    "user_id": "INTEGER REFERENCES users(id)",
    "latitude": "REAL",
    "longitude": "REAL",
    "emergency_type": "TEXT NOT NULL DEFAULT 'flood'",
    "severity": "TEXT NOT NULL DEFAULT 'moderate'",
    "location_text": "TEXT",
    "status": "TEXT NOT NULL DEFAULT 'submitted'",
    "ai_analysis": "TEXT",
}


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _existing_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def _migrate(conn: sqlite3.Connection) -> None:
    present = _existing_columns(conn, "reports")
    for column, ddl in _REPORT_MIGRATIONS.items():
        if column not in present:
            conn.execute(f"ALTER TABLE reports ADD COLUMN {column} {ddl}")


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        _migrate(conn)
        conn.executescript(INDEXES)


def database_info() -> dict:
    """Reported by /api/health so the active backend is never ambiguous."""
    return {
        "backend": config.DB_BACKEND,
        "url": str(DB_PATH) if config.DB_BACKEND == "sqlite" else config.DATABASE_URL,
        "postgis": config.DB_BACKEND == "postgres",
    }
