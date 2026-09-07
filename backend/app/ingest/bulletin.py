"""Live flood bulletin ingestion from ffd.pmd.gov.pk (public government page).

The river-state data endpoint is bot-protected, but the bulletin page is
publicly served HTML, so we parse the latest bulletin text from it. Cached
for one hour; on any failure the last good bulletin (or None) is returned.
"""
import html
import re
import time
from typing import Callable

import httpx

URL = "https://ffd.pmd.gov.pk/bulletin"
SOURCE = "FFD / Pakistan Meteorological Department (live)"
TTL_SECONDS = 3600

_cache: dict = {"at": 0.0, "data": None}


def _http_fetch() -> str:
    resp = httpx.get(URL, timeout=15, headers={"User-Agent": "AquaShield-demo/0.1"})
    resp.raise_for_status()
    return resp.text


fetcher: Callable[[], str] = _http_fetch


def parse_bulletin(raw: str) -> dict:
    text = re.sub(r"<script[\s\S]*?</script>", "", raw)
    text = re.sub(r"<style[\s\S]*?</style>", "", text)
    text = re.sub(r"<[^>]+>", "\n", text)
    text = html.unescape(text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    date = None
    for line in lines[:120]:
        if re.search(r"\d{1,2} [A-Z][a-z]{2} \d{4}", line):
            date = line
            break

    start = None
    for i, line in enumerate(lines):
        if "METEOROLOGICAL FEATURES" in line.upper():
            start = i
            break
    if start is None:
        raise ValueError("bulletin structure not recognized")

    body: list[str] = []
    for line in lines[start:]:
        upper = line.upper()
        if any(m in upper for m in ("VIEW BULLETINS", "SUBSCRIBE", "STAY INFORMED")):
            break
        body.append(line)
        if len(body) >= 60:
            break
    return {"date": date, "text": "\n".join(body), "source": SOURCE}


def get_bulletin() -> dict | None:
    now = time.time()
    if _cache["data"] and now - _cache["at"] < TTL_SECONDS:
        return _cache["data"]
    try:
        data = parse_bulletin(fetcher())
        data["fetched_at"] = now
        _cache["at"] = now
        _cache["data"] = data
        return data
    except Exception:
        return _cache["data"]
