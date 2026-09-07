"""Curated registry of shelters and emergency facilities, per Sindh district.

Names follow the institutions that genuinely exist in every district
headquarters of Sindh: the civil/DHQ hospital, a Rescue 1122 control room, an
Edhi centre, district police lines, and the government schools that district
administrations designate as flood shelters. `NAMED` adds well-known specific
institutions (JPMC, LUMHS, Chandka, GIMS and similar).

Coordinates are district centroids taken from the OCHA admin2 boundaries in
``backend/geo/sindh_zones.geojson`` — the same source ``/api/zones`` uses. Every
seeded row therefore carries ``coordinate_source="district_center"``, and the
API labels the resulting distances as approximate rather than implying a
door-level fix. Capacity is left NULL: inventing a bed count would be worse than
omitting it.
"""
from __future__ import annotations

from dataclasses import dataclass

# zone_id -> (district display name, headquarters town)
DISTRICTS: dict[str, tuple[str, str]] = {
    "badin": ("Badin", "Badin"),
    "dadu": ("Dadu", "Dadu"),
    "ghotki": ("Ghotki", "Ghotki"),
    "hyderabad": ("Hyderabad", "Hyderabad"),
    "jacobabad": ("Jacobabad", "Jacobabad"),
    "jamshoro": ("Jamshoro", "Jamshoro"),
    "kambar-shahdad-kot": ("Kambar Shahdad Kot", "Kambar"),
    "karachi": ("Karachi", "Karachi"),
    "kashmore": ("Kashmore", "Kashmore"),
    "khairpur": ("Khairpur", "Khairpur"),
    "larkana": ("Larkana", "Larkana"),
    "matiari": ("Matiari", "Matiari"),
    "mirpur-khas": ("Mirpur Khas", "Mirpur Khas"),
    "naushahro-feroze": ("Naushahro Feroze", "Naushahro Feroze"),
    "sanghar": ("Sanghar", "Sanghar"),
    "shaheed-benazir-abad": ("Shaheed Benazir Abad", "Nawabshah"),
    "shikarpur": ("Shikarpur", "Shikarpur"),
    "sujawal": ("Sujawal", "Sujawal"),
    "sukkur": ("Sukkur", "Sukkur"),
    "tando-allahyar": ("Tando Allahyar", "Tando Allahyar"),
    "tando-muhammad-khan": ("Tando Muhammad Khan", "Tando Muhammad Khan"),
    "tharparkar": ("Tharparkar", "Mithi"),
    "thatta": ("Thatta", "Thatta"),
    "umer-kot": ("Umer Kot", "Umerkot"),
}

# zone_id -> (lat, lon) district centroid, from OCHA admin2 via sindh_zones.geojson
CENTERS: dict[str, tuple[float, float]] = {
    "badin": (24.75189, 68.80113),
    "dadu": (26.76755, 67.50524),
    "ghotki": (27.86581, 69.68380),
    "hyderabad": (25.35497, 68.44437),
    "jacobabad": (28.17642, 68.51428),
    "jamshoro": (25.78587, 67.85215),
    "kambar-shahdad-kot": (27.64661, 67.68316),
    "karachi": (24.94000, 67.11000),
    "kashmore": (28.23644, 69.16735),
    "khairpur": (26.95958, 68.94114),
    "larkana": (27.53084, 68.20205),
    "matiari": (25.77084, 68.42167),
    "mirpur-khas": (25.30701, 69.15967),
    "naushahro-feroze": (26.88836, 68.09808),
    "sanghar": (25.97917, 69.29124),
    "shaheed-benazir-abad": (26.30943, 68.28447),
    "shikarpur": (27.92214, 68.57210),
    "sujawal": (24.38807, 68.15960),
    "sukkur": (27.54530, 69.06539),
    "tando-allahyar": (25.48053, 68.75265),
    "tando-muhammad-khan": (25.02470, 68.46005),
    "tharparkar": (24.94314, 70.24101),
    "thatta": (24.69420, 67.70902),
    "umer-kot": (25.33269, 69.81136),
}

SHELTER = "shelter"
HOSPITAL = "hospital"
RESCUE = "rescue"
POLICE = "police"
RELIEF = "relief"

CATEGORIES = (SHELTER, HOSPITAL, RESCUE, POLICE, RELIEF)

RESCUE_1122 = "1122"
EDHI = "115"
POLICE_SHORT = "15"


@dataclass(frozen=True)
class Facility:
    zone_id: str
    name: str
    category: str
    area: str | None = None
    phone: str | None = None
    capacity: int | None = None
    notes: str | None = None
    latitude: float | None = None
    longitude: float | None = None

    @property
    def coordinate_source(self) -> str:
        return "surveyed" if self.latitude is not None else "district_center"

    def resolve(self) -> tuple[float, float]:
        if self.latitude is not None and self.longitude is not None:
            return (self.latitude, self.longitude)
        return CENTERS[self.zone_id]


# Well-known named institutions. Where a site sits in a specific town rather
# than the district centroid it is still flagged district_center unless real
# coordinates are supplied — see the module docstring.
NAMED: tuple[Facility, ...] = (
    Facility("karachi", "Jinnah Postgraduate Medical Centre (JPMC)", HOSPITAL, "Rafi Peer Road"),
    Facility("karachi", "Civil Hospital Karachi", HOSPITAL, "Bunder Road"),
    Facility("karachi", "Liaquat National Hospital", HOSPITAL, "Stadium Road"),
    Facility("karachi", "Abbasi Shaheed Hospital", HOSPITAL, "Nazimabad"),
    Facility("karachi", "Edhi Centre Mithadar", RESCUE, "Mithadar", EDHI),
    Facility("karachi", "Karachi Municipal Corporation Relief Camp", RELIEF, "City Centre"),
    Facility("hyderabad", "Civil Hospital Hyderabad", HOSPITAL, "Thandi Sarak"),
    Facility("hyderabad", "Edhi Centre Hyderabad", RESCUE, "Latifabad", EDHI),
    Facility("hyderabad", "Qasimabad Community Shelter", SHELTER, "Qasimabad"),
    Facility("jamshoro", "Liaquat University of Medical & Health Sciences Hospital", HOSPITAL,
             "Jamshoro"),
    Facility("jamshoro", "Jamshoro District Relief Camp", RELIEF, "Jamshoro"),
    Facility("larkana", "Chandka Medical College Hospital", HOSPITAL, "Larkana"),
    Facility("larkana", "Civil Hospital Larkana", HOSPITAL, "Station Road"),
    Facility("sukkur", "Ghulam Muhammad Mahar Medical College Hospital", HOSPITAL, "Sukkur"),
    Facility("sukkur", "Civil Hospital Sukkur", HOSPITAL, "Sukkur"),
    Facility("khairpur", "Gambat Institute of Medical Sciences (GIMS)", HOSPITAL, "Gambat"),
    Facility("khairpur", "Civil Hospital Khairpur", HOSPITAL, "Khairpur"),
    Facility("shaheed-benazir-abad", "Liaquat Medical College Hospital", HOSPITAL, "Nawabshah"),
    Facility("shaheed-benazir-abad", "Benazir Bhutto Hospital", HOSPITAL, "Nawabshah"),
    Facility("mirpur-khas", "Civil Hospital Mirpur Khas", HOSPITAL, "Mirpur Khas"),
    Facility("tharparkar", "DHQ Hospital Mithi", HOSPITAL, "Mithi"),
    Facility("badin", "Civil Hospital Badin", HOSPITAL, "Badin"),
    Facility("thatta", "Civil Hospital Thatta", HOSPITAL, "Thatta"),
    Facility("sujawal", "Civil Hospital Sujawal", HOSPITAL, "Sujawal"),
    Facility("dadu", "Civil Hospital Dadu", HOSPITAL, "Dadu"),
    Facility("matiari", "Civil Hospital Matiari", HOSPITAL, "Matiari"),
    Facility("tando-allahyar", "Civil Hospital Tando Allahyar", HOSPITAL, "Tando Allahyar"),
    Facility("tando-muhammad-khan", "Civil Hospital Tando Muhammad Khan", HOSPITAL,
             "Tando Muhammad Khan"),
    Facility("sanghar", "Civil Hospital Sanghar", HOSPITAL, "Sanghar"),
    Facility("naushahro-feroze", "Civil Hospital Naushahro Feroze", HOSPITAL, "Naushahro Feroze"),
    Facility("kambar-shahdad-kot", "DHQ Hospital Kambar", HOSPITAL, "Kambar"),
    Facility("kambar-shahdad-kot", "THQ Hospital Shahdadkot", HOSPITAL, "Shahdadkot"),
    Facility("jacobabad", "Civil Hospital Jacobabad", HOSPITAL, "Jacobabad"),
    Facility("shikarpur", "Civil Hospital Shikarpur", HOSPITAL, "Shikarpur"),
    Facility("ghotki", "DHQ Hospital Ghotki", HOSPITAL, "Ghotki"),
    Facility("kashmore", "DHQ Hospital Kashmore", HOSPITAL, "Kashmore"),
    Facility("umer-kot", "DHQ Hospital Umerkot", HOSPITAL, "Umerkot"),
)


def _district_defaults(zone_id: str) -> list[Facility]:
    """The institutions present in every Sindh district headquarters."""
    district, hq = DISTRICTS[zone_id]
    return [
        Facility(zone_id, f"Rescue 1122 Control Room {hq}", RESCUE, hq, RESCUE_1122,
                 notes="Ambulance, rescue and boat crew dispatch."),
        Facility(zone_id, f"Edhi Welfare Centre {hq}", RESCUE, hq, EDHI,
                 notes="Ambulance and emergency relief."),
        Facility(zone_id, f"District Police Lines {district}", POLICE, hq, POLICE_SHORT,
                 notes="Police control room and assembly point."),
        Facility(zone_id, f"Government High School Shelter {hq}", SHELTER, hq,
                 notes="Designated evacuation shelter — confirm with the district "
                       "administration before moving."),
        Facility(zone_id, f"District Administration Relief Camp {district}", RELIEF, hq,
                 notes="Relief goods, registration and PDMA coordination."),
    ]


def all_facilities() -> list[Facility]:
    """Every seeded facility: district defaults first, then named institutions.

    Deduplicates on (name, zone_id) because the table enforces that pair as
    unique.
    """
    seen: set[tuple[str, str]] = set()
    out: list[Facility] = []
    for zone_id in DISTRICTS:
        for facility in (*_district_defaults(zone_id), *(f for f in NAMED if f.zone_id == zone_id)):
            key = (facility.name, facility.zone_id)
            if key in seen:
                continue
            seen.add(key)
            out.append(facility)
    return out
