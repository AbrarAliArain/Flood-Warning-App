"""Geospatial helpers.

Pure Python so the MVP runs anywhere without compiled geo dependencies. Each
function mirrors a PostGIS operation (ST_Distance_Sphere, ST_Contains,
ST_DWithin), so moving to PostGIS is a query swap rather than a redesign — see
`storage/postgres/schema.sql`.
"""
import json
import math
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

from ..core import config

EARTH_RADIUS_KM = 6371.0088
GEO_PATH = Path(__file__).resolve().parent.parent.parent / "geo" / "sindh_zones.geojson"


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def within_sindh(lat: float, lng: float) -> bool:
    b = config.SINDH_BOUNDS
    return b["min_lat"] <= lat <= b["max_lat"] and b["min_lng"] <= lng <= b["max_lng"]


def point_in_ring(lat: float, lng: float, ring: list[list[float]]) -> bool:
    """Ray casting. Ring coordinates are GeoJSON ordered [lng, lat]."""
    inside = False
    previous = len(ring) - 1
    for index in range(len(ring)):
        xi, yi = ring[index][0], ring[index][1]
        xj, yj = ring[previous][0], ring[previous][1]
        if (yi > lat) != (yj > lat):
            x_intersect = (xj - xi) * (lat - yi) / (yj - yi) + xi
            if lng < x_intersect:
                inside = not inside
        previous = index
    return inside


def point_in_geometry(lat: float, lng: float, geometry: dict) -> bool:
    kind = geometry.get("type")
    coords = geometry.get("coordinates") or []
    if kind == "Polygon":
        if not coords or not point_in_ring(lat, lng, coords[0]):
            return False
        return not any(point_in_ring(lat, lng, hole) for hole in coords[1:])
    if kind == "MultiPolygon":
        return any(point_in_geometry(lat, lng, {"type": "Polygon", "coordinates": poly}) for poly in coords)
    return False


def _bbox(geometry: dict) -> tuple[float, float, float, float]:
    """(min_lng, min_lat, max_lng, max_lat) over every coordinate in the geometry."""
    lngs: list[float] = []
    lats: list[float] = []

    def walk(node):
        if isinstance(node, (list, tuple)):
            if len(node) == 2 and all(isinstance(v, (int, float)) for v in node):
                lngs.append(node[0])
                lats.append(node[1])
                return
            for child in node:
                walk(child)

    walk(geometry.get("coordinates") or [])
    if not lngs:
        return (0.0, 0.0, 0.0, 0.0)
    return (min(lngs), min(lats), max(lngs), max(lats))


@lru_cache
def load_zones_geojson() -> dict:
    return json.loads(GEO_PATH.read_text(encoding="utf-8"))


@lru_cache
def zone_index() -> tuple[dict, ...]:
    """Pre-computed bounding boxes so point lookups skip most polygons."""
    entries = []
    for feature in load_zones_geojson()["features"]:
        props = feature["properties"]
        entries.append(
            {
                "zone_id": props["zone_id"],
                "name": props["name"],
                "geometry": feature["geometry"],
                "bbox": _bbox(feature["geometry"]),
            }
        )
    return tuple(entries)


def zone_for_point(lat: float, lng: float) -> str | None:
    """Resolve a GPS fix to a Sindh district zone_id, or None if outside."""
    for entry in zone_index():
        min_lng, min_lat, max_lng, max_lat = entry["bbox"]
        if not (min_lat <= lat <= max_lat and min_lng <= lng <= max_lng):
            continue
        if point_in_geometry(lat, lng, entry["geometry"]):
            return entry["zone_id"]
    return None


def centroid(points: list[tuple[float, float]]) -> tuple[float, float]:
    if not points:
        return (0.0, 0.0)
    return (
        sum(lat for lat, _ in points) / len(points),
        sum(lng for _, lng in points) / len(points),
    )


def cluster(
    points: list[tuple[float, float]], radius_km: float
) -> list[list[int]]:
    """Single-linkage clustering: indices grouped so every pair within a
    connected component is reachable through hops of at most `radius_km`.

    O(n^2) by design — report volumes in an MVP are small, and the interface is
    what a DBSCAN/H3 implementation would later replace.
    """
    count = len(points)
    parent = list(range(count))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(count):
        lat_i, lng_i = points[i]
        for j in range(i + 1, count):
            lat_j, lng_j = points[j]
            if haversine_km(lat_i, lng_i, lat_j, lng_j) <= radius_km:
                root_i, root_j = find(i), find(j)
                if root_i != root_j:
                    parent[root_j] = root_i

    groups: dict[int, list[int]] = defaultdict(list)
    for i in range(count):
        groups[find(i)].append(i)
    return sorted(groups.values(), key=len, reverse=True)


def maps_url(lat: float, lng: float, zoom: int = 15) -> str:
    """Link a responder can open directly in the in-app map."""
    return f"{config.PUBLIC_APP_URL}/#/map?lat={lat:.5f}&lng={lng:.5f}&z={zoom}"


def google_maps_url(lat: float, lng: float) -> str:
    return f"https://www.google.com/maps/search/?api=1&query={lat:.5f},{lng:.5f}"
