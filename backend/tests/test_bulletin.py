import app.ingest.bulletin as bulletin_mod
from app.main import app
from fastapi.testclient import TestClient

SAMPLE = """
<html><body>
<h1>Flood Bulletins</h1>
<p>29 Aug 2026, 11:34</p>
<div>I.</div>
<div>METEOROLOGICAL FEATURES</div>
<p>Yesterday's trough of westerly wave over northwest Afghanistan today lies over north Afghanistan.</p>
<p>Seasonal low-pressure area lies over northeast Balochistan.</p>
<a>View Bulletins</a>
</body></html>
"""


def test_parse_bulletin_extracts_date_and_text():
    parsed = bulletin_mod.parse_bulletin(SAMPLE)
    assert parsed["date"] == "29 Aug 2026, 11:34"
    assert "trough of westerly wave" in parsed["text"]
    assert "View Bulletins" not in parsed["text"]


def test_bulletin_endpoint_with_stubbed_fetcher():
    bulletin_mod.fetcher = lambda: SAMPLE
    bulletin_mod._cache["data"] = None
    client = TestClient(app)
    resp = client.get("/api/bulletin")
    assert resp.status_code == 200
    body = resp.json()
    assert body["available"] is True
    assert "trough" in body["text"]
    bulletin_mod.fetcher = bulletin_mod._http_fetch
