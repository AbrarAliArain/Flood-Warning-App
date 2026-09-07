"""DEMO live-data simulator.

All values here are SIMULATED and clearly labelled DEMO DATA in the UI.
The interface mirrors what a real PMD/FFC feed adapter would return, so a
real source can replace this module without touching scoring or the API.
"""
from ..scoring.base import LiveReading

# Simulated current rainfall intensity (mm/hr), DEMO.
DEMO_RAINFALL_MM_HR = {
    "karachi": 46, "thatta": 45, "badin": 41, "sujawal": 43, "hyderabad": 38,
    "dadu": 32, "jamshoro": 30, "larkana": 29, "matiari": 24, "sukkur": 20,
    "naushahro-feroze": 20, "tando-muhammad-khan": 19, "tando-allahyar": 18,
    "shaheed-benazir-abad": 17, "mirpur-khas": 16, "kambar-shahdad-kot": 14,
    "sanghar": 11, "umer-kot": 10, "shikarpur": 9, "ghotki": 9,
    "jacobabad": 8, "kashmore": 8, "tharparkar": 8, "khairpur": 6,
}

# Simulated current gauge flows (lacs cusecs), DEMO. Real thresholds live in
# scoring.heuristic.GAUGE_THRESHOLDS (FFC).
DEMO_GAUGE_FLOWS = {"guddu": 5.6, "sukkur": 5.4, "kotri": 5.6}

# Simulated province-wide risk trend (DEMO), oldest to newest.
DEMO_RISK_TREND = [48, 54, 61, 65, 69, 72]


def current_reading(zone_id: str, gauge: str | None) -> LiveReading:
    return LiveReading(
        rainfall_mm_hr=DEMO_RAINFALL_MM_HR.get(zone_id, 10.0),
        river_flow_lacs_cusecs=DEMO_GAUGE_FLOWS.get(gauge) if gauge else None,
        is_demo=True,
    )
