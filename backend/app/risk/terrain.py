"""Per-district elevation and drainage qualitative ratings (0-1).

Values are qualitative estimates derived from the research documents
(Lower Sindh Flood Rainfall Report, Sindh Flood Districts Research).
Higher values indicate greater flood risk contribution.

A real deployment would replace these with DEM-derived elevation percentiles
and NDMA drainage-capacity scores.  The interface is identical.
"""

# elevation: 1.0 = very low-lying / below design flood level
#            0.0 = elevated / fast-draining
ELEVATION: dict[str, float] = {
    "karachi": 0.35,
    "thatta": 0.85,
    "sujawal": 0.80,
    "badin": 0.90,
    "mirpur-khas": 0.55,
    "umer-kot": 0.40,
    "tharparkar": 0.25,
    "hyderabad": 0.50,
    "dadu": 0.85,
    "jamshoro": 0.45,
    "matiari": 0.70,
    "tando-allahyar": 0.55,
    "tando-muhammad-khan": 0.60,
    "shaheed-benazir-abad": 0.70,
    "naushahro-feroze": 0.70,
    "sanghar": 0.65,
    "khairpur": 0.65,
    "kambar-shahdad-kot": 0.60,
    "larkana": 0.65,
    "jacobabad": 0.60,
    "shikarpur": 0.55,
    "ghotki": 0.55,
    "sukkur": 0.50,
    "kashmore": 0.60,
}

# drainage: 1.0 = very poor drainage / known waterlogging
#           0.0 = excellent natural drainage
DRAINAGE: dict[str, float] = {
    "karachi": 0.80,
    "thatta": 0.65,
    "sujawal": 0.70,
    "badin": 0.90,
    "mirpur-khas": 0.70,
    "umer-kot": 0.50,
    "tharparkar": 0.20,
    "hyderabad": 0.85,
    "dadu": 0.90,
    "jamshoro": 0.55,
    "matiari": 0.65,
    "tando-allahyar": 0.60,
    "tando-muhammad-khan": 0.60,
    "shaheed-benazir-abad": 0.80,
    "naushahro-feroze": 0.85,
    "sanghar": 0.75,
    "khairpur": 0.60,
    "kambar-shahdad-kot": 0.65,
    "larkana": 0.80,
    "jacobabad": 0.60,
    "shikarpur": 0.65,
    "ghotki": 0.55,
    "sukkur": 0.60,
    "kashmore": 0.55,
}


def get_elevation(zone_id: str) -> float:
    return ELEVATION.get(zone_id, 0.5)


def get_drainage(zone_id: str) -> float:
    return DRAINAGE.get(zone_id, 0.5)
