"""Deterministic report triage until the richer NLP pipeline is enabled."""

HIGH_RISK_TERMS = {
    "trapped",
    "stranded",
    "injured",
    "collapse",
    "breach",
    "urgent",
    "help",
    "rescue",
    "medical",
}


def analyze_report(
    *, description: str, emergency_type: str, severity: str, water_level: str
) -> dict:
    text = description.lower()
    signals = sorted(term for term in HIGH_RISK_TERMS if term in text)
    review_required = severity in {"high", "critical"} or emergency_type in {
        "rescue",
        "medical",
        "evacuation",
    }
    if signals:
        review_required = True

    if review_required:
        action = "Route to a human responder for verification and prioritisation."
    elif emergency_type in {"waterlogging", "flood", "river_overflow"}:
        action = "Monitor conditions and include the report in local situation awareness."
    else:
        action = "Review the report in the next operational triage cycle."

    return {
        "method": "rule_based_fallback",
        "human_review_required": review_required,
        "signals": signals,
        "recommended_action": action,
        "summary": f"{severity.title()} {emergency_type.replace('_', ' ')} report with {water_level} water level.",
    }
