"""Nearby Safe Locations: curated Sindh registry plus live OpenStreetMap fallback.

The live tests stub out ``osm.geocode`` / ``osm.nearby`` so the suite never
touches the public OpenStreetMap service.
"""
import pytest

from app.core import config
from app.data import safe_locations as seed_data
from app.safe_locations import osm, service
from app.main import app
from app.storage.db import init_db
from fastapi.testclient import TestClient

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def _seeded():
    init_db()
    service.seed_defaults()
    yield


@pytest.fixture(autouse=True)
def _clean_osm_cache():
    osm.clear_cache()
    osm._cooldown_until = 0.0
    yield
    osm.clear_cache()
    osm._cooldown_until = 0.0


# ------------------------------------------------------------------ registry
def test_every_district_has_curated_facilities():
    """The original bug was a frontend hardcoded to a single city."""
    for zone_id in seed_data.DISTRICTS:
        rows = service.list_by_zone(zone_id)
        assert rows, f"{zone_id} has no safe locations"
        assert all(row["zone_id"] == zone_id for row in rows)


def test_registry_covers_multiple_categories_per_district():
    for zone_id in seed_data.DISTRICTS:
        categories = {row["category"] for row in service.list_by_zone(zone_id, limit=50)}
        assert {"hospital", "shelter", "police", "rescue"} <= categories, zone_id


def test_seed_is_idempotent():
    before = service.count()
    assert service.seed_defaults() == 0
    assert service.count() == before


def test_seeded_coordinates_are_real_district_centroids():
    rows = service.list_by_zone("karachi", limit=50)
    expected = seed_data.CENTERS["karachi"]
    for row in rows:
        assert row["latitude"] == pytest.approx(expected[0], abs=1e-4)
        assert row["longitude"] == pytest.approx(expected[1], abs=1e-4)
        assert row["coordinate_source"] == "district_center"


def test_capacity_is_never_invented():
    """A fabricated bed count would be worse than no number at all."""
    for zone_id in seed_data.DISTRICTS:
        for row in service.list_by_zone(zone_id, limit=50):
            assert row["capacity"] is None


# ------------------------------------------------------------------ distances
def test_distance_is_null_without_user_coordinates():
    """Centroid-to-centroid would report a meaningless 0.0 km for every row."""
    payload = client.get("/api/safe-locations?zone_id=hyderabad").json()
    assert payload["distance_basis"] == "unavailable"
    assert payload["locations"]
    assert all(row["distance_km"] is None for row in payload["locations"])


def test_distance_is_measured_from_user_coordinates():
    # A point well outside Hyderabad, so the distance is unambiguously non-zero.
    payload = client.get(
        "/api/safe-locations?zone_id=hyderabad&lat=24.8607&lng=67.0011"
    ).json()
    assert payload["distance_basis"] == "user_location"
    distances = [row["distance_km"] for row in payload["locations"]]
    assert all(d is not None and d > 50 for d in distances)


def test_nearest_first_when_coordinates_supplied():
    payload = client.get(
        "/api/safe-locations?zone_id=sukkur&lat=27.705&lng=68.857"
    ).json()
    distances = [row["distance_km"] for row in payload["locations"]]
    assert distances == sorted(distances)


# ------------------------------------------------------------------ maps links
def test_approximate_rows_link_by_name_not_by_centroid():
    """Sending a user to a district centroid pin drops them mid-district."""
    payload = client.get("/api/safe-locations?zone_id=larkana").json()
    for row in payload["locations"]:
        assert "google.com/maps/search/" in row["maps_url"]
        assert row["area"] or row["name"]
        assert f"{row['latitude']:.5f},{row['longitude']:.5f}" not in row["maps_url"]


def test_surveyed_rows_link_by_coordinate():
    row = service._shape(
        name="Real Place",
        category="hospital",
        area="Somewhere",
        lat=31.5,
        lon=74.3,
        coordinate_source="surveyed",
        phone=None,
        capacity=None,
        notes=None,
        origin=None,
        is_demo=False,
    )
    assert "query=31.50000,74.30000" in row["maps_url"]


# ------------------------------------------------------------------ API surface
def test_cities_endpoint_lists_all_districts():
    payload = client.get("/api/safe-locations/cities").json()
    assert len(payload["cities"]) == len(seed_data.DISTRICTS)
    assert payload["cities"][0]["facility_count"] > 0


def test_cities_filter_matches_headquarters_town():
    """Typing 'Nawabshah' must still find Shaheed Benazir Abad."""
    payload = client.get("/api/safe-locations/cities?q=nawabshah").json()
    assert [c["zone_id"] for c in payload["cities"]] == ["shaheed-benazir-abad"]


def test_unknown_district_404():
    assert client.get("/api/safe-locations?zone_id=atlantis").status_code == 404


def test_invalid_category_rejected():
    resp = client.get("/api/safe-locations?zone_id=karachi&category=bogus")
    assert resp.status_code == 422


def test_missing_selector_rejected():
    assert client.get("/api/safe-locations").status_code == 422


def test_category_filter_narrows_results():
    payload = client.get("/api/safe-locations?zone_id=karachi&category=hospital").json()
    assert payload["locations"]
    assert all(row["category"] == "hospital" for row in payload["locations"])


def test_gps_lookup_resolves_to_containing_district():
    payload = client.get("/api/safe-locations?lat=25.396&lng=68.357").json()
    assert payload["source"] == "curated"
    assert payload["resolved"]["zone_id"] == "hyderabad"


def test_reverse_lookup_endpoint():
    payload = client.get("/api/safe-locations/reverse?lat=27.5453&lng=69.06539").json()
    assert payload["zone_id"] == "sukkur"


def test_stats_reports_real_coverage():
    payload = client.get("/api/safe-locations/stats").json()
    assert payload["districts"] == 24
    assert payload["curated_locations"] >= 24 * 5


# ------------------------------------------------------------------ OSM parsing
def test_category_reads_amenity_value_not_tag_name():
    """Regression: OSM tags are {"amenity": "police"}, so matching on the key
    silently dropped every element and live search always returned nothing."""
    assert osm._category_for({"amenity": "police", "name": "X"}) == "police"
    assert osm._category_for({"amenity": "hospital"}) == "hospital"
    assert osm._category_for({"amenity": "clinic"}) == "hospital"
    assert osm._category_for({"amenity": "fire_station"}) == "rescue"
    assert osm._category_for({"social_facility": "shelter"}) == "shelter"
    assert osm._category_for({"amenity": "cafe"}) is None


def test_coordinates_fall_back_to_way_centre():
    assert osm._coordinates({"lat": 1.0, "lon": 2.0}) == (1.0, 2.0)
    assert osm._coordinates({"center": {"lat": 3.0, "lon": 4.0}}) == (3.0, 4.0)
    assert osm._coordinates({"tags": {}}) is None


def test_bbox_stays_finite_at_high_latitude():
    box = osm._bbox(78.0, 15.0, 10.0)
    south, west, north, east = (float(v) for v in box.split(","))
    assert south < north and west < east
    assert north - south < 1.0


def test_balanced_round_robins_across_categories():
    rows = [
        {"category": "police", "distance_km": 0.5, "name": "P1"},
        {"category": "police", "distance_km": 0.6, "name": "P2"},
        {"category": "shelter", "distance_km": 2.0, "name": "S1"},
        {"category": "hospital", "distance_km": 1.0, "name": "H1"},
        {"category": "relief", "distance_km": None, "name": "R1"},
    ]
    assert [r["name"] for r in service._balanced(rows, 4)] == ["S1", "H1", "P1", "R1"]


# ------------------------------------------------------------------ live path
def test_curated_district_short_circuits_live_lookup(monkeypatch):
    """Sindh queries must not spend OSM quota on places we already cover."""
    def _boom(*args, **kwargs):
        raise AssertionError("live lookup should not run for a curated district")

    monkeypatch.setattr(osm, "geocode", _boom)
    payload = client.get("/api/safe-locations?q=hyderabad").json()
    assert payload["source"] == "curated"
    assert payload["live_status"] == "not_needed"
    assert payload["attribution"] is None


def test_live_search_returns_osm_facilities(monkeypatch):
    monkeypatch.setattr(
        osm,
        "geocode",
        lambda q, limit=5: [
            {
                "name": "Lahore",
                "country": "Pakistan",
                "latitude": 31.5657,
                "longitude": 74.3142,
            }
        ],
    )
    monkeypatch.setattr(
        osm,
        "nearby",
        lambda lat, lng, radius_km=None: [
            {"name": "Lahore General Hospital", "category": "hospital",
             "area": "Lahore", "latitude": 31.57, "longitude": 74.32,
             "phone": None, "osm_type": "node", "osm_id": 1},
            {"name": "City Police Station", "category": "police",
             "area": "Lahore", "latitude": 31.56, "longitude": 74.31,
             "phone": None, "osm_type": "node", "osm_id": 2},
        ],
    )
    payload = client.get("/api/safe-locations?q=Lahore").json()
    assert payload["source"] == "openstreetmap"
    assert payload["live_status"] == "ok"
    assert payload["attribution"] == osm.SOURCE
    assert payload["distance_basis"] == "resolved_city_center"
    names = [row["name"] for row in payload["locations"]]
    assert names == ["Lahore General Hospital", "City Police Station"]
    assert all(row["coordinate_source"] == "surveyed" for row in payload["locations"])
    assert all(row["distance_km"] is not None for row in payload["locations"])


def test_unreachable_osm_reports_unavailable_not_empty(monkeypatch):
    """An empty list must never read as 'this city has no shelters'."""
    monkeypatch.setattr(osm, "geocode", lambda q, limit=5: [])
    payload = client.get("/api/safe-locations?q=Nowhere").json()
    assert payload["locations"] == []
    assert payload["live_status"] == "unavailable"


def test_rate_limited_status_is_surfaced(monkeypatch):
    monkeypatch.setattr(osm, "geocode", lambda q, limit=5: [])
    monkeypatch.setattr(osm, "rate_limited", lambda: True)
    payload = client.get("/api/safe-locations?q=Istanbul").json()
    assert payload["live_status"] == "rate_limited"


def test_disabled_live_lookup_still_serves_curated(monkeypatch):
    monkeypatch.setattr(config, "LIVE_GEO_ENABLED", False)
    curated = client.get("/api/safe-locations?zone_id=badin").json()
    assert curated["locations"]
    assert curated["live_lookup_available"] is False

    monkeypatch.setattr(osm, "geocode", lambda q, limit=5: [{"name": "X", "latitude": 1.0, "longitude": 2.0}])
    live = client.get("/api/safe-locations?q=Xanadu").json()
    assert live["locations"] == []
    assert live["live_status"] == "disabled"


def test_negative_cache_expires_quickly(monkeypatch):
    """One timeout must not blind the app to a city for the full success TTL."""
    calls = {"n": 0}

    def _fail(*args, **kwargs):
        calls["n"] += 1
        return None

    monkeypatch.setattr(osm, "_run_overpass", _fail)
    assert osm.nearby(10.0, 10.0) == []
    assert calls["n"] == config.OVERPASS_MAX_ATTEMPTS

    # Cached failure: no further calls.
    assert osm.nearby(10.0, 10.0) == []
    assert calls["n"] == config.OVERPASS_MAX_ATTEMPTS

    stored_at, payload, ttl = osm._cache[next(iter(osm._cache))]
    assert payload == []
    assert ttl == config.NEGATIVE_CACHE_TTL_SECONDS
    assert ttl < config.LIVE_GEO_CACHE_TTL_SECONDS


def test_rate_limit_cooldown_skips_without_caching(monkeypatch):
    monkeypatch.setattr(osm, "_cooldown_until", 9e18)
    calls = {"n": 0}

    def _count(*args, **kwargs):
        calls["n"] += 1
        return []

    monkeypatch.setattr(osm, "_run_overpass", _count)
    assert osm.nearby(20.0, 20.0) == []
    assert calls["n"] == 0
    # Not cached, so the lookup is retried once the cooldown lifts.
    assert osm._cache == {}


def test_mirror_failover_tries_next_endpoint(monkeypatch):
    monkeypatch.setattr(config, "OVERPASS_URLS", ["https://a.invalid/api", "https://b.invalid/api"])
    seen: list[str] = []

    class _Resp:
        status_code = 504
        text = "gateway timeout"

        def raise_for_status(self):
            raise RuntimeError("504")

        def json(self):
            return {}

    def _fake_get(url, **kwargs):
        seen.append(url)
        return _Resp()

    monkeypatch.setattr(osm, "_get", _fake_get)
    assert osm._run_overpass(1.0, 1.0, 10.0, 10) is None
    assert seen == ["https://a.invalid/api", "https://b.invalid/api"]


def test_429_triggers_global_cooldown(monkeypatch):
    monkeypatch.setattr(config, "OVERPASS_URLS", ["https://a.invalid/api"])
    monkeypatch.setattr(config, "OVERPASS_COOLDOWN_SECONDS", 120)

    class _Resp:
        status_code = 429
        text = "too many requests"

        def raise_for_status(self):
            raise RuntimeError("429")

        def json(self):
            return {}

    monkeypatch.setattr(osm, "_get", lambda url, **kwargs: _Resp())
    assert osm._run_overpass(1.0, 1.0, 10.0, 10) is None
    assert osm.rate_limited() is True


def test_zone_for_point_falls_back_to_nearest_centroid():
    """A GPS fix outside every polygon still resolves to the closest district."""
    assert service.zone_for_point(25.396, 68.357) == "hyderabad"
    far = service.zone_for_point(0.0, 0.0)
    assert far in seed_data.DISTRICTS
