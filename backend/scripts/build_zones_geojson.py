"""One-off script: derive backend/geo/sindh_zones.geojson from OCHA COD-PAK admin2.

Source: OCHA Pakistan COD (cod-ab-pak), pak_admin2.geojson (raw/pak_admin2.geojson).
Karachi's six administrative districts are merged into a single "Karachi" zone.
"""
import json
from pathlib import Path

GEO_DIR = Path(__file__).resolve().parent.parent / "geo"
RAW = GEO_DIR / "raw" / "pak_admin2.geojson"
OUT = GEO_DIR / "sindh_zones.geojson"

KARACHI_DISTRICTS = {
    "Central Karachi",
    "East Karachi",
    "Korangi Karachi",
    "Malir Karachi",
    "South Karachi",
    "West Karachi",
}


def slug(name: str) -> str:
    return name.lower().replace(" ", "-").replace(".", "")


def as_multipolygon(geometry: dict) -> dict:
    if geometry["type"] == "Polygon":
        return {"type": "MultiPolygon", "coordinates": [geometry["coordinates"]]}
    if geometry["type"] == "MultiPolygon":
        return geometry
    raise ValueError(f"unexpected geometry type {geometry['type']}")


def main() -> None:
    source = json.loads(RAW.read_text(encoding="utf-8"))
    sindh = [f for f in source["features"] if f["properties"].get("adm1_name") == "Sindh"]

    zones: dict[str, dict] = {}
    karachi_polys: list[list] = []

    for feature in sindh:
        props = feature["properties"]
        name = props["adm2_name"]
        if name in KARACHI_DISTRICTS:
            karachi_polys.extend(as_multipolygon(feature["geometry"])["coordinates"])
            continue
        zone_id = slug(name)
        zones[zone_id] = {
            "type": "Feature",
            "properties": {
                "zone_id": zone_id,
                "name": name,
                "area_sqkm": props.get("area_sqkm"),
                "center_lat": props.get("center_lat"),
                "center_lon": props.get("center_lon"),
                "source": "OCHA COD-PAK admin2 (2026-08)",
            },
            "geometry": feature["geometry"],
        }

    zones["karachi"] = {
        "type": "Feature",
        "properties": {
            "zone_id": "karachi",
            "name": "Karachi",
            "area_sqkm": None,
            "center_lat": 24.94,
            "center_lon": 67.11,
            "source": "OCHA COD-PAK admin2 (2026-08), 6 districts merged",
        },
        "geometry": {"type": "MultiPolygon", "coordinates": karachi_polys},
    }

    out = {"type": "FeatureCollection", "features": list(zones.values())}
    OUT.write_text(json.dumps(out), encoding="utf-8")
    print(f"wrote {OUT} with {len(out['features'])} zones, {OUT.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
