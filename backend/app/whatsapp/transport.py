"""WhatsApp message transport.

Two modes:
- **demo**: logs the message locally and records it in communication_logs
  but does not call any external API.  Used when WhatsApp credentials are
  absent or ``WHATSAPP_FORCE_DEMO`` is set.
- **cloud_api**: posts to the Meta WhatsApp Cloud API.

The transport is selected at call time by ``config.whatsapp_mode()`` so
changing credentials at runtime takes effect without a restart.
"""
from __future__ import annotations

import json
import urllib.request
import urllib.error
from datetime import datetime, timezone

from ..core import config
from ..core.logging_conf import get_logger
from ..storage.db import get_conn
from ..storage.geo import google_maps_url

log = get_logger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _write_log(
    *,
    case_id: int,
    channel: str = "whatsapp",
    transport: str,
    recipient: str,
    payload: dict,
    status: str,
    provider_message_id: str | None = None,
    deeplink: str | None = None,
    is_demo: bool = True,
    error: str | None = None,
) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO communication_logs
               (case_id, channel, transport, direction, recipient, payload,
                status, provider_message_id, deeplink, is_demo, error, created_at)
               VALUES (?, ?, ?, 'outbound', ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                case_id, channel, transport, recipient,
                json.dumps(payload, separators=(",", ":")),
                status, provider_message_id, deeplink,
                int(is_demo), error, _now_iso(),
            ),
        )


def _send_cloud_api(recipient: str, text: str) -> tuple[str | None, str | None]:
    url = (
        f"{config.WHATSAPP_GRAPH_URL}/{config.WHATSAPP_API_VERSION}"
        f"/{config.WHATSAPP_PHONE_NUMBER_ID}/messages"
    )
    body = json.dumps({
        "messaging_product": "whatsapp",
        "to": recipient.lstrip("+"),
        "type": "text",
        "text": {"body": text},
    }).encode()
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={
            "Authorization": f"Bearer {config.WHATSAPP_TOKEN}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            msg_id = data.get("messages", [{}])[0].get("id")
            return msg_id, None
    except urllib.error.HTTPError as exc:
        try:
            err_body = exc.read().decode()
        except Exception:
            err_body = str(exc)
        return None, f"HTTP {exc.code}: {err_body}"
    except Exception as exc:
        return None, str(exc)


def build_case_message(case: dict) -> str:
    lat = case.get("latitude")
    lng = case.get("longitude")
    maps = google_maps_url(lat, lng) if lat and lng else ""

    lines = [
        f"🚨 AquaShield Emergency — {case['code']}",
        f"Type: {case['emergency_type']}",
        f"Severity: {case['severity']} | Priority: {case['priority_label']}",
    ]
    if case.get("description"):
        lines.append(f"Details: {case['description'][:200]}")
    if case.get("location_text"):
        lines.append(f"Location: {case['location_text']}")
    if maps:
        lines.append(f"Google Maps: {maps}")
    if case.get("contact_phone"):
        lines.append(f"Citizen phone: {case['contact_phone']}")
    lines.append(f"Case URL: {config.PUBLIC_APP_URL}/#/cases/{case['id']}")
    return "\n".join(lines)


def dispatch(case: dict) -> dict:
    mode = config.whatsapp_mode()
    recipient = case.get("ngo_whatsapp") or case.get("ngo_phone")
    message = build_case_message(case)

    result = {
        "case_id": case["id"],
        "case_code": case["code"],
        "mode": mode,
        "recipient": recipient,
        "message": message,
    }

    if not recipient:
        result["status"] = "skipped"
        result["reason"] = "no WhatsApp/phone number on matched NGO"
        _write_log(
            case_id=case["id"], transport=mode, recipient="",
            payload={"message": message}, status="skipped",
            is_demo=mode == "demo",
            error="no recipient phone number",
        )
        return result

    if mode == "cloud_api":
        msg_id, error = _send_cloud_api(recipient, message)
        if error:
            result["status"] = "failed"
            result["error"] = error
            _write_log(
                case_id=case["id"], transport="cloud_api",
                recipient=recipient, payload={"message": message},
                status="failed", error=error, is_demo=False,
            )
        else:
            result["status"] = "sent"
            result["provider_message_id"] = msg_id
            _write_log(
                case_id=case["id"], transport="cloud_api",
                recipient=recipient, payload={"message": message},
                status="sent", provider_message_id=msg_id,
                deeplink=google_maps_url(case["latitude"], case["longitude"])
                    if case.get("latitude") else None,
                is_demo=False,
            )
    else:
        result["status"] = "demo"
        result["demo_note"] = (
            "DEMO: No real message sent. In production with WhatsApp "
            "credentials configured, this would dispatch to the NGO."
        )
        deeplink = (
            google_maps_url(case["latitude"], case["longitude"])
            if case.get("latitude") else None
        )
        _write_log(
            case_id=case["id"], transport="demo", recipient=recipient,
            payload={"message": message}, status="demo",
            deeplink=deeplink, is_demo=True,
        )
        log.info("DEMO dispatch case=%s to=%s", case["code"], recipient)

    with get_conn() as conn:
        conn.execute(
            "UPDATE emergency_cases SET communication_status = ?, updated_at = ? WHERE id = ?",
            (result["status"], _now_iso(), case["id"]),
        )

    return result
