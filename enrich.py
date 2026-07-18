"""enrich.py – geolocate IPs via ip-api.com, with a persistent SQLite cache
and an optional local GeoLite2 fallback for when the API is rate-limited
or unreachable."""

from __future__ import annotations

import json
import logging
import os
import pathlib
import sqlite3
import threading
import time
from typing import Dict, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

_CACHE: Dict[str, Tuple[float, Optional[dict]]] = {}
_CACHE_TTL = 3600  # seconds – 1 hour

_GEO_URL = "http://ip-api.com/json/{ip}?fields=status,lat,lon,city,country,org,as,query"
_MY_GEO_URL = "http://ip-api.com/json/?fields=status,lat,lon,city,country,query"

_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": "NetMapGuard/2.0"})

# ---------------------------------------------------------------------------
# Persistent cache (SQLite) – survives restarts so we don't re-burn the
# ip-api.com free-tier quota (45 req/min) every time NetMapGuard is launched.
# ---------------------------------------------------------------------------

_DB_PATH = pathlib.Path(__file__).parent / ".cache" / "geo_cache.sqlite3"
_DB_LOCK = threading.Lock()


def _db_connect() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS geo_cache (ip TEXT PRIMARY KEY, data TEXT, ts REAL)"
    )
    conn.commit()
    return conn


_DB = _db_connect()


def _db_get(ip: str) -> Optional[Tuple[float, Optional[dict]]]:
    with _DB_LOCK:
        row = _DB.execute("SELECT data, ts FROM geo_cache WHERE ip = ?", (ip,)).fetchone()
    if row is None:
        return None
    data_json, ts = row
    return ts, json.loads(data_json)


def _db_set(ip: str, result: Optional[dict], ts: float) -> None:
    with _DB_LOCK:
        _DB.execute(
            "INSERT OR REPLACE INTO geo_cache (ip, data, ts) VALUES (?, ?, ?)",
            (ip, json.dumps(result), ts),
        )
        _DB.commit()


def _db_clear() -> None:
    with _DB_LOCK:
        _DB.execute("DELETE FROM geo_cache")
        _DB.commit()


# ---------------------------------------------------------------------------
# Local GeoLite2 fallback (optional) – kicks in when ip-api.com fails or is
# rate-limited, keeping the map populated even offline / over quota.
# Requires the `geoip2` package and a GeoLite2-City.mmdb file (MaxMind
# license required, not bundled) at NETMAPGUARD_GEOIP_DB or one of the
# default locations below.
# ---------------------------------------------------------------------------

try:
    import geoip2.database
    import geoip2.errors

    _GEOIP_AVAILABLE = True
except ImportError:
    _GEOIP_AVAILABLE = False

_GEOIP_DB_ENV_VAR = "NETMAPGUARD_GEOIP_DB"
_DEFAULT_GEOIP_PATHS = [
    pathlib.Path(__file__).parent / "GeoLite2-City.mmdb",
    pathlib.Path.home() / ".netmapguard" / "GeoLite2-City.mmdb",
]

_geoip_reader = None
_geoip_checked = False


def _get_geoip_reader():
    """Lazily open the local GeoLite2 database, if available. Cached after first call."""
    global _geoip_reader, _geoip_checked
    if _geoip_checked:
        return _geoip_reader
    _geoip_checked = True

    if not _GEOIP_AVAILABLE:
        return None

    env_path = os.environ.get(_GEOIP_DB_ENV_VAR)
    candidates = [pathlib.Path(env_path)] if env_path else _DEFAULT_GEOIP_PATHS

    for candidate in candidates:
        if candidate.is_file():
            try:
                _geoip_reader = geoip2.database.Reader(str(candidate))
                logger.info("Local GeoLite2 fallback enabled (%s)", candidate)
            except Exception:
                logger.warning("Failed to open GeoLite2 database at %s", candidate)
            break

    return _geoip_reader


def _geolocate_local(ip: str) -> Optional[dict]:
    reader = _get_geoip_reader()
    if reader is None:
        return None
    try:
        resp = reader.city(ip)
    except (geoip2.errors.AddressNotFoundError, ValueError):
        return None
    except Exception:
        return None

    if resp.location.latitude is None or resp.location.longitude is None:
        return None

    return {
        "ip": ip,
        "lat": resp.location.latitude,
        "lon": resp.location.longitude,
        "city": resp.city.name or "",
        "country": resp.country.name or "",
        "org": "",
        "asn": "",
    }


def _fetch_geo(url: str) -> Optional[dict]:
    try:
        resp = _SESSION.get(url, timeout=2)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") == "success":
            return data
    except requests.ConnectTimeout:
        # Network timeout - likely due to firewall/DNS block
        pass
    except requests.ReadTimeout:
        # Server timeout
        pass
    except requests.RequestException:
        # Any other request error
        pass
    except Exception:
        # JSON parsing or other errors
        pass
    return None


def geolocate(ip: str) -> Optional[dict]:
    """Return geolocation dict for *ip*, using a TTL cache backed by SQLite.

    Falls back to a local GeoLite2 database (if configured) when ip-api.com
    is unreachable or rate-limited.

    Returns a dict with keys: lat, lon, city, country, org, asn, ip
    or None if lookup failed.
    """
    now = time.time()

    if ip in _CACHE:
        ts, cached = _CACHE[ip]
        if now - ts < _CACHE_TTL:
            return cached
    else:
        persisted = _db_get(ip)
        if persisted is not None:
            ts, cached = persisted
            if now - ts < _CACHE_TTL:
                _CACHE[ip] = (ts, cached)
                return cached

    data = _fetch_geo(_GEO_URL.format(ip=ip))
    result: Optional[dict] = None
    if data:
        result = {
            "ip": data.get("query", ip),
            "lat": data["lat"],
            "lon": data["lon"],
            "city": data.get("city", ""),
            "country": data.get("country", ""),
            "org": data.get("org", ""),
            "asn": data.get("as", ""),
        }
    else:
        result = _geolocate_local(ip)

    _CACHE[ip] = (now, result)
    _db_set(ip, result, now)
    return result


def get_my_location() -> dict:
    """Return approximate geolocation of this machine's public IP."""
    data = _fetch_geo(_MY_GEO_URL)
    if data:
        return {
            "ip": data.get("query", "unknown"),
            "lat": data["lat"],
            "lon": data["lon"],
            "city": data.get("city", ""),
            "country": data.get("country", ""),
        }
    return {"ip": "unknown", "lat": 0.0, "lon": 0.0, "city": "", "country": ""}


def clear_cache() -> None:
    """Clear the geolocation cache (in-memory and persistent), useful for testing."""
    _CACHE.clear()
    _db_clear()
