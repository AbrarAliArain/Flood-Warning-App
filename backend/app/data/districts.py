"""Static district profiles.

Real values are cited from the project research documents:
- baselines: Lower_Sindh_Flood_Rainfall_Report.pdf (PMD climatology)
- houses_2022: Sindh_Flood_Districts_Research.pdf + 2022 reconstruction survey tables
- exposure/historical indices: qualitative ratings derived from those documents
  (labelled "qualitative"); values marked demo-estimate are clearly flagged.
"""
from ..scoring.base import DistrictProfile

REPORT = "Lower Sindh rainfall report (PMD climatology)"
SURVEY = "2022 flood reconstruction survey"
QUAL = "qualitative rating from research docs (DEMO)"

DISTRICTS: list[DistrictProfile] = [
    # ---- Lower Sindh ----
    DistrictProfile("karachi", "Karachi", "Karachi", 156, REPORT, 52,
                    f"{SURVEY} (Malir figure only)", 0.9, QUAL, 0.7, QUAL,
                    None, [2020, 2022],
                    ["Urban flash flooding", "Storm-drain overload", "Coastal storm surge"]),
    DistrictProfile("thatta", "Thatta", "Hyderabad", 230, REPORT, None,
                    "not separately reported (delta-wide damage)", 0.85, QUAL, 0.7, QUAL,
                    "kotri", [2010, 2022],
                    ["Indus delta low-lying", "Tidal influence", "Embankment dependent"]),
    DistrictProfile("sujawal", "Sujawal", "Hyderabad", 230, REPORT, 52097, SURVEY,
                    0.85, QUAL, 0.75, QUAL, "kotri", [2010, 2022],
                    ["Indus delta", "Embankment breaches (2022)", "Cyclone exposed"]),
    DistrictProfile("badin", "Badin", "Hyderabad", 230, REPORT, 110786, SURVEY,
                    0.9, QUAL, 0.85, "23.4% inundated 2022 (Sentinel-1 study)", "kotri",
                    [2010, 2011, 2022],
                    ["LBOD tail-end waterlogging", "Coastal/deltaic", "Standing water months"]),
    DistrictProfile("mirpur-khas", "Mirpur Khas", "Mirpur Khas", 215, REPORT, 85673, SURVEY,
                    0.7, QUAL, 0.7, QUAL, "kotri", [2011, 2022],
                    ["Flat canal-irrigated plain", "Poor drainage", "Standing water into 2023"]),
    DistrictProfile("umer-kot", "Umerkot", "Mirpur Khas", 237, REPORT, None,
                    "not separately reported", 0.55, QUAL, 0.5, QUAL, "kotri", [2011, 2022],
                    ["Desert-edge flash waterlogging", "Flat topography"]),
    DistrictProfile("tharparkar", "Tharparkar", "Mirpur Khas", 237, REPORT, 8515, SURVEY,
                    0.45, QUAL, 0.4, QUAL, None, [2022],
                    ["Hyper-arid", "Episodic cloudburst flooding", "Fast-draining dunes"]),
    # ---- Central Sindh ----
    DistrictProfile("hyderabad", "Hyderabad", "Hyderabad", 170, "demo-estimate (PMD zone)",
                    19556, SURVEY, 0.85, QUAL, 0.75, QUAL, "kotri",
                    [2001, 2003, 2008, 2016, 2017, 2022],
                    ["Urban drainage failure", "Paved-surface runoff", "Floods most monsoons"]),
    DistrictProfile("dadu", "Dadu", "Hyderabad", 150, "demo-estimate (PMD zone)", 156210,
                    SURVEY, 0.85, QUAL, 0.95, QUAL, "kotri", [2010, 2022],
                    ["Manchar Lake overflow", "MNVD drain breach 2022", "Worst-hit 2022"]),
    DistrictProfile("jamshoro", "Jamshoro", "Hyderabad", 150, "demo-estimate (PMD zone)",
                    55401, SURVEY, 0.75, QUAL, 0.75, QUAL, "kotri", [2022],
                    ["Mountain runoff from Balochistan", "Manchar Lake shared", "Flat land"]),
    DistrictProfile("matiari", "Matiari", "Hyderabad", 150, "demo-estimate (PMD zone)",
                    45879, SURVEY, 0.8, QUAL, 0.7, QUAL, "kotri", [2022],
                    ["Indus floodplain", "River overflow 2022"]),
    DistrictProfile("tando-allahyar", "Tando Allahyar", "Hyderabad", 160,
                    "demo-estimate (PMD zone)", 29971, SURVEY, 0.7, QUAL, 0.6, QUAL,
                    "kotri", [2022], ["Flat low-lying", "Urban flooding flagged 2025"]),
    DistrictProfile("tando-muhammad-khan", "Tando Muhammad Khan", "Hyderabad", 160,
                    "demo-estimate (PMD zone)", 28456, SURVEY, 0.7, QUAL, 0.6, QUAL,
                    "kotri", [2022], ["Low-lying", "20h continuous rainfall 2025"]),
    DistrictProfile("shaheed-benazir-abad", "Shaheed Benazirabad", "Hyderabad", 160,
                    "demo-estimate (PMD zone)", 113590, SURVEY, 0.8, QUAL, 0.8, QUAL,
                    "kotri", [2022], ["Very flat terrain", "LBOD faulty"]),
    DistrictProfile("naushahro-feroze", "Naushahro Feroze", "Hyderabad", 150,
                    "demo-estimate (PMD zone)", 134960, SURVEY, 0.8, QUAL, 0.9, QUAL,
                    "kotri", [2022], ["Stagnant water months after 2022"]),
    DistrictProfile("sanghar", "Sanghar", "Hyderabad", 160, "demo-estimate (PMD zone)",
                    104830, SURVEY, 0.75, QUAL, 0.8, QUAL, "kotri", [2022],
                    ["LBOD outdated", "Low-lying"]),
    # ---- Upper Sindh ----
    DistrictProfile("khairpur", "Khairpur", "Sukkur", 130, "demo-estimate (PMD zone)",
                    243870, SURVEY, 0.75, QUAL, 0.95, QUAL, "sukkur", [2022],
                    ["Indus riverine", "Highest houses damaged 2022"]),
    DistrictProfile("kambar-shahdad-kot", "Kambar Shahdadkot", "Larkana", 140,
                    "demo-estimate (PMD zone)", 137126, SURVEY, 0.75, QUAL, 0.9, QUAL,
                    "sukkur", [2022], ["Kirthar hill torrents", "2022 inundation"]),
    DistrictProfile("larkana", "Larkana", "Larkana", 140, "demo-estimate (PMD zone)",
                    131806, SURVEY, 0.75, QUAL, 0.85, QUAL, "sukkur", [2022],
                    ["Low-lying", "Drainage congestion"]),
    DistrictProfile("jacobabad", "Jacobabad", "Larkana", 130, "demo-estimate (PMD zone)",
                    109700, SURVEY, 0.75, QUAL, 0.85, QUAL, "guddu", [2010, 2022],
                    ["Indus riverine", "Repeated super-floods"]),
    DistrictProfile("shikarpur", "Shikarpur", "Larkana", 130, "demo-estimate (PMD zone)",
                    89791, SURVEY, 0.7, QUAL, 0.75, QUAL, "guddu", [2022],
                    ["Low-lying", "Drainage congestion"]),
    DistrictProfile("ghotki", "Ghotki", "Sukkur", 120, "demo-estimate (PMD zone)", 82746,
                    SURVEY, 0.7, QUAL, 0.75, QUAL, "guddu", [2022],
                    ["Indus riverine", "Embankment breaches"]),
    DistrictProfile("sukkur", "Sukkur", "Sukkur", 120, "demo-estimate (PMD zone)", 81035,
                    SURVEY, 0.7, QUAL, 0.75, QUAL, "sukkur", [2022],
                    ["Indus proximity", "Urban drainage"]),
    DistrictProfile("kashmore", "Kashmore", "Sukkur", 120, "demo-estimate (PMD zone)",
                    73957, SURVEY, 0.7, QUAL, 0.7, "2022: >=25% area inundated (Sentinel-1 study)",
                    "guddu", [2022], ["Indus riverine", "Verified 2022 inundation"]),
]

BY_ID = {d.zone_id: d for d in DISTRICTS}
