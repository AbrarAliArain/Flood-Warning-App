"""NGO matching: find the best rescue organisation for an emergency.

Matching considers:
1. Zone coverage — NGO must list the zone in coverage_zones
2. Capability match — NGO capabilities vs required capabilities for the type
3. Proximity — haversine distance if both have coordinates
4. Capacity — current active cases vs max_concurrent_cases
5. Availability — NGO must be marked available and active

Returns ranked candidates with reasons.
"""
from __future__ import annotations

from ..storage.geo import haversine_km
from . import service as ngo_service

# Map emergency types to desired capabilities
CAPABILITY_MAP = {
    "rescue": {"rescue", "boat"},
    "medical": {"medical", "rescue"},
    "evacuation": {"rescue", "boat", "evacuation"},
    "flood": {"rescue", "boat"},
    "waterlogging": {"rescue", "pump", "drainage"},
    "river_overflow": {"rescue", "boat"},
    "infrastructure": {"rescue", "engineering"},
    "other": set(),
}


def match_ngos(
    *,
    zone_id: str,
    emergency_type: str = "flood",
    latitude: float | None = None,
    longitude: float | None = None,
    limit: int = 5,
) -> list[dict]:
    ngos = ngo_service.list_all(active_only=True)
    candidates: list[dict] = []

    for ngo in ngos:
        score = 0.0
        reasons: list[str] = []

        if zone_id not in ngo["coverage_zones"]:
            continue

        score += 40
        reasons.append(f"covers zone {zone_id}")

        required = CAPABILITY_MAP.get(emergency_type, set())
        ngo_caps = set(ngo["capabilities"])
        matched_caps = required & ngo_caps
        if matched_caps:
            cap_score = 20 * len(matched_caps) / max(len(required), 1)
            score += cap_score
            reasons.append(f"capabilities: {', '.join(sorted(matched_caps))}")
        elif not required:
            score += 10
            reasons.append("general purpose")

        active_cases = ngo_service.get_active_case_count(ngo["id"])
        if active_cases < ngo["max_concurrent_cases"]:
            capacity_score = 15 * (1.0 - active_cases / max(ngo["max_concurrent_cases"], 1))
            score += capacity_score
            reasons.append(f"capacity: {active_cases}/{ngo['max_concurrent_cases']}")
        else:
            reasons.append(f"at capacity: {active_cases}/{ngo['max_concurrent_cases']}")

        if ngo["available"]:
            score += 10
            reasons.append("available")

        if latitude and longitude and ngo.get("latitude") and ngo.get("longitude"):
            dist = haversine_km(latitude, longitude, ngo["latitude"], ngo["longitude"])
            if dist < 50:
                prox_score = 15 * max(0, 1.0 - dist / 50.0)
                score += prox_score
                reasons.append(f"distance: {dist:.1f}km")

        candidates.append({
            "ngo_id": ngo["id"],
            "ngo_name": ngo["name"],
            "score": round(score, 1),
            "reasons": reasons,
            "whatsapp_number": ngo.get("whatsapp_number"),
            "contact_phone": ngo.get("contact_phone"),
            "distance_km": (
                haversine_km(latitude, longitude, ngo["latitude"], ngo["longitude"])
                if latitude and longitude and ngo.get("latitude") and ngo.get("longitude")
                else None
            ),
        })

    candidates.sort(key=lambda c: c["score"], reverse=True)
    return candidates[:limit]
