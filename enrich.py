"""enrich.py – geolocate IPs via ip-api.com with in-memory TTL cache."""

from __future__ import annotations

import time
from typing import Dict, Optional, Tuple

import requests

_CACHE: Dict[str, Tuple[float, Optional[dict]]] = {}
_CACHE_TTL = 3600  # seconds – 1 hour

_GEO_URL = "http://ip-api.com/json/{ip}?fields=status,lat,lon,city,country,org,as,query"
_MY_GEO_URL = "http://ip-api.com/json/?fields=status,lat,lon,city,country,query"

_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": "NetMapGuard/2.0"})


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
    """Return geolocation dict for *ip*, using TTL cache.

    Returns a dict with keys: lat, lon, city, country, org, asn, ip
    or None if lookup failed.
    """
    now = time.monotonic()
    if ip in _CACHE:
        ts, cached = _CACHE[ip]
        if now - ts < _CACHE_TTL:
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

    _CACHE[ip] = (now, result)
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
    """Clear the geolocation cache (useful for testing)."""
    _CACHE.clear()
