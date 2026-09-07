import httpx
import pytest
from fastapi.testclient import TestClient

from app.core import config
from app.data import safe_locations as districts
from app.main import app
from app.weather import service

client = TestClient(app)

HYDERABAD = districts.CENTERS["hyderabad"]

PAYLOAD = {
    "latitude": HYDERABAD[0],
    "longitude": HYDERABAD[1],
    "timezone": "Asia/Karachi",
    "current_units": {
        "temperature_2m": "°C",
        "relative_humidity_2m": "%",
        "wind_speed_10m": "km/h",
    },
    "current": {
        "time": "2026-09-05T12:00",
        "temperature_2m": 32.1,
        "relative_humidity_2m": 88,
        "precipitation": 0.4,
        "weather_code": 63,
        "wind_speed_10m": 14.2,
        "wind_direction_10m": 231,
    },
    "hourly_units": {"precipitation_probability": "%"},
    "hourly": {
        "time": [f"2026-09-05T{h:02d}:00" for h in range(6)],
        "precipitation_probability": [10, 40, 70, 55, 30, 20],
    },
}


class _Response:
    def __init__(self, payload=None, status=200):
        self._payload = payload if payload is not None else PAYLOAD
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("boom", request=None, response=None)

    def json(self):
        return self._payload


@pytest.fixture(autouse=True)
def _clean_cache():
    service.clear_cache()
    yield
    service.clear_cache()


def _stub_open_meteo(monkeypatch, payload=None, status=200, boom=None):
    """Record every outbound call so caching can be asserted on."""
    calls = []

    def fake_get(url, **kwargs):
        calls.append({"url": url, "params": kwargs.get("params") or {}})
        if boom:
            raise boom
        return _Response(payload, status)

    monkeypatch.setattr(httpx, "get", fake_get)
    return calls


# ----------------------------------------------------------------- happy path


def test_zone_weather_returns_live_reading(monkeypatch):
    calls = _stub_open_meteo(monkeypatch)
    resp = client.get("/api/weather?zone_id=hyderabad")
    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is True
    assert data["source"] == "Open-Meteo"
    assert data["zone_id"] == "hyderabad"
    assert data["temperature_c"] == 32.1
    assert data["humidity_percent"] == 88
    assert data["wind_speed_kmh"] == 14.2
    assert data["conditions"] == "Rain"
    assert len(calls) == 1


def test_request_targets_the_district_centroid(monkeypatch):
    calls = _stub_open_meteo(monkeypatch)
    client.get("/api/weather?zone_id=hyderabad")
    params = calls[0]["params"]
    assert calls[0]["url"] == config.OPEN_METEO_URL
    assert float(params["latitude"]) == pytest.approx(HYDERABAD[0], abs=1e-4)
    assert float(params["longitude"]) == pytest.approx(HYDERABAD[1], abs=1e-4)


def test_rain_probability_is_todays_peak_not_the_first_hour(monkeypatch):
    _stub_open_meteo(monkeypatch)
    data = client.get("/api/weather?zone_id=hyderabad").json()
    assert data["rain_probability_percent"] == 70


def test_units_come_from_the_provider_not_hardcoded(monkeypatch):
    _stub_open_meteo(monkeypatch)
    data = client.get("/api/weather?zone_id=hyderabad").json()
    assert data["units"]["temperature"] == "°C"
    assert data["units"]["wind_speed"] == "km/h"
    assert data["units"]["humidity"] == "%"


def test_explicit_gps_fix_is_accepted(monkeypatch):
    _stub_open_meteo(monkeypatch)
    resp = client.get("/api/weather?lat=24.8607&lng=67.0011")
    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is True
    assert data["latitude"] == 24.8607
    assert data["longitude"] == 67.0011


def test_nearby_labels_the_resolved_district(monkeypatch):
    _stub_open_meteo(monkeypatch)
    data = client.get("/api/weather/nearby?lat=25.396&lng=68.357").json()
    assert data["available"] is True
    assert data["zone_id"] == "hyderabad"


# ------------------------------------------------------------------ validation


def test_unknown_district_is_404():
    assert client.get("/api/weather?zone_id=atlantis").status_code == 404


def test_missing_selector_is_422():
    assert client.get("/api/weather").status_code == 422


def test_latitude_without_longitude_is_422():
    assert client.get("/api/weather?lat=25.4").status_code == 422


def test_out_of_range_latitude_is_422():
    assert client.get("/api/weather?lat=120&lng=0").status_code == 422


def test_unknown_district_never_reaches_the_network(monkeypatch):
    calls = _stub_open_meteo(monkeypatch)
    client.get("/api/weather?zone_id=atlantis")
    assert calls == []


# ----------------------------------------------------------------- zones index


def test_zones_lists_every_district_sorted():
    data = client.get("/api/weather/zones").json()
    ids = [z["zone_id"] for z in data["zones"]]
    assert ids == sorted(districts.DISTRICTS)
    assert len(ids) == 24
    assert data["live_enabled"] is True
    assert data["source"] == "Open-Meteo"


def test_zone_rows_carry_real_centroids():
    data = client.get("/api/weather/zones").json()
    for row in data["zones"]:
        district, hq = districts.DISTRICTS[row["zone_id"]]
        assert row["name"] == district
        assert row["headquarters"] == hq
        assert (row["latitude"], row["longitude"]) == districts.CENTERS[row["zone_id"]]


def test_zones_needs_no_network(monkeypatch):
    calls = _stub_open_meteo(monkeypatch)
    client.get("/api/weather/zones")
    assert calls == []


# --------------------------------------------------------------- degradation


def test_unreachable_provider_is_reported_not_invented(monkeypatch):
    _stub_open_meteo(monkeypatch, boom=httpx.ConnectError("offline"))
    resp = client.get("/api/weather?zone_id=hyderabad")
    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is False
    assert data["reason"] == "provider_unreachable"
    assert "temperature_c" not in data


def test_http_error_status_is_reported_as_unreachable(monkeypatch):
    _stub_open_meteo(monkeypatch, status=500)
    data = client.get("/api/weather?zone_id=hyderabad").json()
    assert data["available"] is False
    assert data["reason"] == "provider_unreachable"


def test_failures_are_not_cached(monkeypatch):
    _stub_open_meteo(monkeypatch, boom=httpx.ConnectError("offline"))
    client.get("/api/weather?zone_id=hyderabad")
    client.get("/api/weather?zone_id=hyderabad")
    assert service._cache == {}


def test_disabled_live_lookups_skip_the_network(monkeypatch):
    calls = _stub_open_meteo(monkeypatch)
    monkeypatch.setattr(config, "LIVE_GEO_ENABLED", False)
    data = client.get("/api/weather?zone_id=hyderabad").json()
    assert data["available"] is False
    assert data["reason"] == "live_lookups_disabled"
    assert calls == []


def test_missing_hourly_block_leaves_probability_null(monkeypatch):
    _stub_open_meteo(monkeypatch, payload={**PAYLOAD, "hourly": {}})
    data = client.get("/api/weather?zone_id=hyderabad").json()
    assert data["available"] is True
    assert data["rain_probability_percent"] is None


def test_null_probabilities_are_ignored(monkeypatch):
    payload = {
        **PAYLOAD,
        "hourly": {"precipitation_probability": [None, 25, None, 60]},
    }
    _stub_open_meteo(monkeypatch, payload=payload)
    data = client.get("/api/weather?zone_id=hyderabad").json()
    assert data["rain_probability_percent"] == 60


def test_empty_current_block_still_reports_available_with_nulls(monkeypatch):
    _stub_open_meteo(monkeypatch, payload={"timezone": "UTC"})
    data = client.get("/api/weather?zone_id=hyderabad").json()
    assert data["available"] is True
    assert data["temperature_c"] is None
    assert data["conditions"] == "Unknown"


# ---------------------------------------------------------------------- cache


def test_second_request_is_served_from_cache(monkeypatch):
    calls = _stub_open_meteo(monkeypatch)
    client.get("/api/weather?zone_id=hyderabad")
    client.get("/api/weather?zone_id=hyderabad")
    assert len(calls) == 1


def test_different_districts_get_separate_cache_entries(monkeypatch):
    calls = _stub_open_meteo(monkeypatch)
    client.get("/api/weather?zone_id=hyderabad")
    client.get("/api/weather?zone_id=sukkur")
    assert len(calls) == 2
    assert len(service._cache) == 2


def test_cached_payload_relabels_the_zone(monkeypatch):
    _stub_open_meteo(monkeypatch)
    service.current(HYDERABAD[0], HYDERABAD[1], zone_id="hyderabad")
    again = service.current(HYDERABAD[0], HYDERABAD[1], zone_id="sukkur")
    assert again["zone_id"] == "sukkur"


def test_cache_entry_expires(monkeypatch):
    calls = _stub_open_meteo(monkeypatch)
    service.current(HYDERABAD[0], HYDERABAD[1])
    stored_at, payload = service._cache[next(iter(service._cache))]
    service._cache[next(iter(service._cache))] = (
        stored_at - config.WEATHER_CACHE_TTL_SECONDS - 1,
        payload,
    )
    service.current(HYDERABAD[0], HYDERABAD[1])
    assert len(calls) == 2


def test_nearby_points_round_to_a_shared_cache_key(monkeypatch):
    calls = _stub_open_meteo(monkeypatch)
    service.current(25.3960, 68.3570)
    service.current(25.39604, 68.35701)
    assert len(calls) == 1


# ----------------------------------------------------------------- code labels


@pytest.mark.parametrize(
    "code,expected",
    [(0, "Clear"), (65, "Heavy rain"), (95, "Thunderstorm"), (42, "Unsettled"), (None, "Unknown")],
)
def test_describe_code(code, expected):
    assert service.describe_code(code) == expected


def test_resolve_zone_unknown_returns_none():
    assert service.resolve_zone("atlantis") is None
    assert service.resolve_zone("hyderabad") == districts.CENTERS["hyderabad"]


def test_for_zone_raises_for_unknown_district():
    with pytest.raises(KeyError):
        service.for_zone("atlantis")
