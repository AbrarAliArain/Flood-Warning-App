"""Seed the reports table with clearly-labelled DEMO community reports.

Idempotent: only inserts when the table is empty.
"""
from datetime import datetime, timedelta, timezone

from app.storage.db import get_conn, init_db

DEMO_REPORTS = [
    ("hyderabad", "high", "Water accumulation reported in residential area near Latifabad."),
    ("badin", "rising", "Local residents reported drainage overflow after continuous rain."),
    ("thatta", "high", "Floodwater reported near a vulnerable road embankment."),
    ("karachi", "severe", "Urban waterlogging reported after heavy rainfall; underpasses closed."),
    ("sujawal", "rising", "Seepage observed along embankment; villagers monitoring."),
    ("dadu", "high", "Rainwater standing in low-lying fields near Manchar catchment."),
    ("mirpur-khas", "rising", "Drainage congestion reported in city center."),
    ("tando-muhammad-khan", "low", "Ponding on roads after 3 hours of rain; drains slow."),
]


def main() -> None:
    init_db()
    with get_conn() as conn:
        count = conn.execute("SELECT COUNT(*) AS n FROM reports").fetchone()["n"]
        if count:
            print(f"reports table already has {count} rows; skipping seed")
            return
        now = datetime.now(timezone.utc)
        for i, (zone_id, level, text) in enumerate(DEMO_REPORTS):
            created = (now - timedelta(hours=3 * (i + 1))).isoformat()
            conn.execute(
                "INSERT INTO reports (zone_id, water_level, description, evidence_path, is_demo, created_at)"
                " VALUES (?, ?, ?, NULL, 1, ?)",
                (zone_id, level, text, created),
            )
    print(f"seeded {len(DEMO_REPORTS)} DEMO reports")


if __name__ == "__main__":
    main()
