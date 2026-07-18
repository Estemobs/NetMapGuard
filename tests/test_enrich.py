"""Tests for enrich module."""

import pytest
from unittest.mock import patch, MagicMock

import enrich
from enrich import geolocate, get_my_location, clear_cache


# ── Helpers ───────────────────────────────────────────────────────────────

def _mock_response(data: dict) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = data
    resp.raise_for_status.return_value = None
    return resp


SUCCESS_PAYLOAD = {
    "status": "success",
    "lat": 37.4,
    "lon": -122.0,
    "city": "Mountain View",
    "country": "US",
    "org": "Google LLC",
    "as": "AS15169 Google LLC",
    "query": "8.8.8.8",
}


# ── geolocate ─────────────────────────────────────────────────────────────

class TestGeolocate:
    def setup_method(self):
        clear_cache()

    def test_success(self):
        with patch("enrich._SESSION") as mock_sess:
            mock_sess.get.return_value = _mock_response(SUCCESS_PAYLOAD)
            result = geolocate("8.8.8.8")
        assert result is not None
        assert result["lat"] == 37.4
        assert result["lon"] == -122.0
        assert result["city"] == "Mountain View"
        assert result["country"] == "US"
        assert result["org"] == "Google LLC"
        assert result["asn"] == "AS15169 Google LLC"
        assert result["ip"] == "8.8.8.8"

    def test_api_failure_returns_none(self):
        fail = {"status": "fail", "message": "reserved range"}
        with patch("enrich._SESSION") as mock_sess:
            mock_sess.get.return_value = _mock_response(fail)
            result = geolocate("192.168.1.1")
        assert result is None

    def test_network_error_returns_none(self):
        with patch("enrich._SESSION") as mock_sess:
            mock_sess.get.side_effect = ConnectionError("no network")
            result = geolocate("1.1.1.1")
        assert result is None

    def test_caching(self):
        """Second call for the same IP should NOT hit the network."""
        with patch("enrich._SESSION") as mock_sess:
            mock_sess.get.return_value = _mock_response(SUCCESS_PAYLOAD)
            first  = geolocate("8.8.8.8")
            second = geolocate("8.8.8.8")
        assert mock_sess.get.call_count == 1
        assert first == second

    def test_cache_stores_none(self):
        """A failed lookup is also cached so we don't hammer the API."""
        fail = {"status": "fail"}
        with patch("enrich._SESSION") as mock_sess:
            mock_sess.get.return_value = _mock_response(fail)
            geolocate("0.0.0.0")
            geolocate("0.0.0.0")
        assert mock_sess.get.call_count == 1

    def test_clear_cache_resets(self):
        with patch("enrich._SESSION") as mock_sess:
            mock_sess.get.return_value = _mock_response(SUCCESS_PAYLOAD)
            geolocate("8.8.8.8")
            clear_cache()
            geolocate("8.8.8.8")
        assert mock_sess.get.call_count == 2


# ── get_my_location ───────────────────────────────────────────────────────

class TestGetMyLocation:
    def setup_method(self):
        clear_cache()

    def test_success(self):
        payload = {
            "status": "success",
            "lat": 48.8,
            "lon": 2.3,
            "city": "Paris",
            "country": "France",
            "query": "203.0.113.1",
        }
        with patch("enrich._SESSION") as mock_sess:
            mock_sess.get.return_value = _mock_response(payload)
            result = get_my_location()
        assert result["lat"] == 48.8
        assert result["city"] == "Paris"
        assert result["ip"] == "203.0.113.1"

    def test_fallback_on_error(self):
        with patch("enrich._SESSION") as mock_sess:
            mock_sess.get.side_effect = TimeoutError()
            result = get_my_location()
        assert result["lat"] == 0.0
        assert result["lon"] == 0.0
        assert result["ip"] == "unknown"


# ── Persistent (SQLite) cache ────────────────────────────────────────────

class TestPersistentCache:
    def setup_method(self):
        clear_cache()

    def test_survives_in_memory_cache_eviction(self):
        """A lookup persisted to SQLite is served without hitting the network,
        even if the in-memory dict cache no longer has it (e.g. after restart)."""
        with patch("enrich._SESSION") as mock_sess:
            mock_sess.get.return_value = _mock_response(SUCCESS_PAYLOAD)
            geolocate("8.8.8.8")

        # Simulate a process restart: the in-memory cache is gone, but the
        # SQLite-backed cache is not.
        enrich._CACHE.clear()

        with patch("enrich._SESSION") as mock_sess:
            result = geolocate("8.8.8.8")
        assert mock_sess.get.call_count == 0
        assert result["city"] == "Mountain View"

    def test_clear_cache_wipes_sqlite_too(self):
        with patch("enrich._SESSION") as mock_sess:
            mock_sess.get.return_value = _mock_response(SUCCESS_PAYLOAD)
            geolocate("8.8.8.8")

        clear_cache()
        assert enrich._db_get("8.8.8.8") is None


# ── GeoLite2 local fallback ───────────────────────────────────────────────

class TestGeoipFallback:
    def setup_method(self):
        clear_cache()

    def test_falls_back_to_local_geoip_when_api_fails(self):
        fake_city = MagicMock()
        fake_city.location.latitude = 37.4
        fake_city.location.longitude = -122.0
        fake_city.city.name = "Mountain View"
        fake_city.country.name = "United States"

        fake_reader = MagicMock()
        fake_reader.city.return_value = fake_city

        with patch("enrich._SESSION") as mock_sess, \
             patch("enrich._get_geoip_reader", return_value=fake_reader):
            mock_sess.get.side_effect = ConnectionError("no network")
            result = geolocate("8.8.8.8")

        assert result is not None
        assert result["lat"] == 37.4
        assert result["city"] == "Mountain View"
        assert result["country"] == "United States"

    def test_no_fallback_available_returns_none(self):
        with patch("enrich._SESSION") as mock_sess, \
             patch("enrich._get_geoip_reader", return_value=None):
            mock_sess.get.side_effect = ConnectionError("no network")
            result = geolocate("8.8.8.8")
        assert result is None
