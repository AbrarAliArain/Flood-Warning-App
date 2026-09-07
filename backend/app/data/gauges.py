"""FFC river gauge stations and flood-classification levels.

Thresholds (lacs cusecs) are real FFC flood levels as published on
ffd.pmd.gov.pk (captured 2026-08-29). Current flows are DEMO-simulated
in ingest.demo_simulator and labelled DEMO DATA in the UI.
"""

GAUGES = [
    {"id": "guddu", "name": "Guddu", "river": "Indus", "design_capacity": 12.0,
     "low": 2.0, "medium": 3.5, "high": 5.0, "very_high": 7.0, "exceptional": 9.0},
    {"id": "sukkur", "name": "Sukkur", "river": "Indus", "design_capacity": 9.0,
     "low": 2.0, "medium": 3.5, "high": 5.0, "very_high": 7.0, "exceptional": 9.0},
    {"id": "kotri", "name": "Kotri", "river": "Indus", "design_capacity": 8.75,
     "low": 2.0, "medium": 3.0, "high": 4.5, "very_high": 6.5, "exceptional": 8.0},
]

BY_ID = {g["id"]: g for g in GAUGES}

CLASS_COLORS = {
    "below low": "#22a559",
    "low": "#2f80ed",
    "medium": "#f2c200",
    "high": "#ef7d00",
    "very high": "#d21f1f",
    "exceptional": "#8e1414",
}


def gauge_class(flow: float, gauge_id: str) -> str:
    g = BY_ID[gauge_id]
    if flow < g["low"]:
        return "below low"
    if flow < g["medium"]:
        return "low"
    if flow < g["high"]:
        return "medium"
    if flow < g["very_high"]:
        return "high"
    if flow < g["exceptional"]:
        return "very high"
    return "exceptional"
