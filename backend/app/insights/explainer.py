"""AI explanation + evidence-grounded recommendations.

TemplateExplainer always works offline. LLMExplainer is used when
OPENAI_API_KEY is configured (any OpenAI-compatible base URL); on any failure
it falls back to the template so the demo never breaks.
"""
import json

import httpx

from ..core import config
from ..data.districts import DistrictProfile
from ..scoring.base import CRITICAL, HIGH, RiskResult
from .retriever import get_retriever


def _river_class_label(river_norm: float) -> str:
    if river_norm >= 0.95:
        return "exceptional"
    if river_norm >= 0.85:
        return "very high"
    if river_norm >= 0.65:
        return "high"
    if river_norm >= 0.45:
        return "medium"
    if river_norm >= 0.25:
        return "low"
    return "below low"


def build_evidence(district: DistrictProfile, result: RiskResult) -> dict:
    return {
        "district": district.name,
        "score": result.score,
        "category": result.category,
        "rainfall_mm_hr": result.reading.rainfall_mm_hr,
        "rainfall_norm": result.rainfall_norm,
        "river_norm": result.river_norm,
        "gauge": district.gauge,
        "exposure": district.exposure_index,
        "historical": district.historical_index,
        "houses_2022": district.houses_2022,
        "flood_years": district.historical_events,
        "risk_factors": district.risk_factors,
    }


def template_explanation(district: DistrictProfile, result: RiskResult) -> str:
    parts = [
        f"{district.name} is at {result.category.upper()} flood risk "
        f"({result.score}/100) on current DEMO inputs."
    ]
    parts.append(
        f"Rainfall intensity of {result.reading.rainfall_mm_hr} mm/hr reaches "
        f"{result.rainfall_norm:.0%} of the extreme-cloudburst threshold."
    )
    if district.gauge and result.reading.river_flow_lacs_cusecs is not None:
        parts.append(
            f"River flow at the {district.gauge.upper()} gauge "
            f"({result.reading.river_flow_lacs_cusecs} lacs cusecs) is in the "
            f"{_river_class_label(result.river_norm)} flood class."
        )
    else:
        parts.append("Risk here is rainfall/urban-drainage driven rather than riverine.")
    parts.append(
        f"Exposure is high ({district.exposure_index:.0%}): "
        + "; ".join(district.risk_factors).lower()
        + "."
    )
    history = f"Historical severity is {district.historical_index:.0%}"
    if district.houses_2022:
        history += f", with {district.houses_2022:,} houses damaged in 2022"
    if district.historical_events:
        history += f" and flood years {', '.join(map(str, district.historical_events))}"
    parts.append(history + ".")
    return " ".join(parts)


def _chunk_for(keyword: str) -> dict:
    for chunk in get_retriever().chunks:
        if keyword in chunk.heading.lower():
            return {"doc": chunk.doc, "heading": chunk.heading}
    return {"doc": "preparedness_guidance", "heading": keyword}


def template_recommendations(
    district: DistrictProfile, result: RiskResult, retrieved: list[dict]
) -> list[dict]:
    actions: list[tuple[str, dict]] = []

    if result.rainfall_norm >= 0.5:
        actions.append(
            (
                "Pre-position de-watering pumps and clean storm drains at known waterlogging hotspots before peak rain.",
                _chunk_for("drainage preparation"),
            )
        )
    if district.gauge and result.river_norm >= 0.65:
        actions.append(
            (
                "Assign breach-watch volunteers along embankments while gauge flows remain in the high flood class.",
                _chunk_for("gauge watch"),
            )
        )
    if result.category in (CRITICAL, HIGH):
        actions.append(
            (
                "Disseminate community warnings via UC volunteers, SMS and mosque loudspeakers; confirm evacuation routes for low-lying settlements.",
                _chunk_for("early warning"),
            )
        )
    if any("LBOD" in factor for factor in district.risk_factors):
        actions.append(
            (
                "Clear regulator gates and remove drain encroachments in the LBOD-served area before the next heavy spell.",
                _chunk_for("congestion response"),
            )
        )
    if district.historical_index >= 0.7:
        actions.append(
            (
                "Plan rapid dewatering and damage assessment so standing water does not persist for months as in 2022.",
                _chunk_for("recovery"),
            )
        )
    if result.category in (CRITICAL, HIGH):
        actions.append(
            (
                "Monitor schools, hospitals, shelters and densely populated areas in the district.",
                {"doc": "aquashield", "heading": "MVP requirement: protect vulnerable facilities"},
            )
        )
    if retrieved:
        actions.append(
            (
                f"Cross-check {district.name}'s flood history and 2022 damage records in the research dossier before allocating resources.",
                {"doc": retrieved[0]["doc"], "heading": retrieved[0]["heading"]},
            )
        )

    unique: list[dict] = []
    seen: set[str] = set()
    for action, chunk in actions:
        if action in seen:
            continue
        seen.add(action)
        unique.append(
            {"action": action, "source": f"{chunk['doc']} — {chunk['heading']}"}
        )
    return unique[:5]


def llm_insights(evidence: dict, retrieved: list[dict]) -> dict | None:
    if not config.OPENAI_API_KEY:
        return None
    prompt = (
        "You are AquaShield, a flood-risk analyst for disaster-response authorities "
        "in Sindh, Pakistan. Using ONLY the evidence and retrieved guidance below, "
        "write (1) a 3-5 sentence explanation of why this district is at its current "
        "risk level and (2) 3-5 concrete preventive actions, each citing the guidance "
        "heading it comes from. Note that live inputs are DEMO simulations. "
        "Respond with JSON: {\"explanation\": str, \"recommendations\": "
        "[{\"action\": str, \"source\": str}]}.\n\n"
        f"EVIDENCE: {json.dumps(evidence)}\nRETRIEVED GUIDANCE: {json.dumps(retrieved)}"
    )
    try:
        resp = httpx.post(
            f"{config.OPENAI_BASE_URL.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}"},
            json={
                "model": config.LLM_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
            },
            timeout=20,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        if isinstance(parsed.get("explanation"), str) and isinstance(
            parsed.get("recommendations"), list
        ):
            return parsed
    except Exception:
        return None
    return None


def generate_insights(district: DistrictProfile, result: RiskResult) -> dict:
    retriever = get_retriever()
    query = f"{district.name} flood {' '.join(district.risk_factors[:3])} rainfall drainage"
    retrieved = retriever.retrieve(query, top_k=4)

    llm = llm_insights(build_evidence(district, result), retrieved)
    if llm:
        explanation = llm["explanation"]
        recommendations = llm["recommendations"]
        source = "llm"
    else:
        explanation = template_explanation(district, result)
        recommendations = template_recommendations(district, result, retrieved)
        source = "template"

    return {
        "zone_id": district.zone_id,
        "name": district.name,
        "score": result.score,
        "category": result.category,
        "explanation": explanation,
        "explanation_source": source,
        "recommendations": recommendations,
        "retrieved": retrieved,
        "inputs_are_demo": result.reading.is_demo,
    }
