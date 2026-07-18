# NetMapGuard 🌐

**Real-time network traffic visualiser on a world map.**

![NetMapGuard screenshot](docs/screenshot.png)

When you run NetMapGuard, it opens a web interface showing:

- 📍 **Your machine** as a blue dot on the map.
- 🔴 **Remote endpoints** as coloured dots (green = standard web port, yellow = other well-known port, blue = ephemeral).
- ⚡ **Animated beams** (dashed lines) connecting your machine to every active remote connection — beams *appear* when a connection is established and *fade out* when it goes idle or closes.
- 📋 **Live connection list** in the sidebar with remote IP, geo-location, organisation, and process name.
- 🔍 **Filters** by text (IP, process, city, org) and protocol (TCP/UDP).
- ⏸ **Pause / resume** and 🗑 **clear** controls.

---

## Requirements

| Dependency | Purpose |
|---|---|
| Python ≥ 3.10 | Runtime |
| `psutil` | Cross-platform connection polling (no root required) |
| `fastapi` + `uvicorn` | Async web server + WebSocket |
| `requests` | IP geolocation via [ip-api.com](http://ip-api.com) (free, no key needed) |

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/Estemobs/NetMapGuard.git
cd NetMapGuard
```

### 2. Create and activate a virtual environment

**Linux / macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows:**
```bash
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

## Running

```bash
python main.py
```

This will:
1. Resolve the approximate location of your public IP.
2. Start the web server on **http://127.0.0.1:8888**.
3. Automatically open the map in your default browser.

### Options

```
python main.py --help

options:
  --host HOST           Bind host (default: 127.0.0.1)
  --port PORT           Bind port (default: 8888)
  --no-browser          Do not open browser automatically
  --poll-interval SEC   Connection poll interval in seconds (default: 2)
```

### Example – expose on the local network

```bash
python main.py --host 0.0.0.0 --port 8888
```

---

## Permissions

| Platform | Notes |
|---|---|
| **Linux** | `psutil.net_connections()` requires either `root` **or** running as the same user as the processes you want to see. Run with `sudo` for a complete view: `sudo python main.py` |
| **macOS** | Same as Linux. Full process names visible only for your own processes unless `sudo` is used. |
| **Windows** | No special permissions needed for standard TCP/UDP connections. Run as Administrator for complete process names. |

---

## Architecture

```
psutil.net_connections()          ← capture.py
        │
        ▼
  filter public IPs
        │
        ▼
ip-api.com geolocation (cached)   ← enrich.py
        │
        ▼
  FastAPI + WebSocket server       ← server.py
        │  (broadcasts every 2 s)
        ▼
  Leaflet.js map in browser        ← static/index.html
```

### Project Structure

```
NetMapGuard/
├── capture.py          Poll network connections via psutil
├── enrich.py           Geolocate IPs via ip-api.com (cached)
├── server.py           FastAPI app: serve UI + WebSocket broadcaster
├── main.py             CLI entry point
├── static/             Frontend assets
│   ├── index.html      Leaflet.js map interface
│   ├── leaflet.js/css  Map library
│   └── images/         Map icons
├── tests/              Unit tests (29 tests)
├── requirements.txt    Dependencies
└── README.md           This file
```

### Modules

| File | Responsibility |
|---|---|
| `capture.py` | Poll `psutil.net_connections()`, filter public IPs, resolve process names |
| `enrich.py` | Geolocate IPs via ip-api.com with TTL cache (1 h) |
| `server.py` | FastAPI app: serve UI + WebSocket broadcaster |
| `main.py` | CLI entry point |
| `static/index.html` | Leaflet.js frontend: map, animated beams, sidebar, filters |

---

## Running tests

```bash
pip install pytest
pytest tests/ -v
```

---

## Privacy note

Remote IP geolocation requests are sent to **ip-api.com** (free tier, no account needed, up to 45 req/min). Results are cached for 1 hour. No traffic payload or personal data is sent externally.

---

## Geolocation cache & offline fallback

- **Persistent cache** — Lookups are cached in a local SQLite database (`.cache/geo_cache.sqlite3`), not just in memory. Restarting NetMapGuard no longer re-burns your ip-api.com quota for IPs you've already resolved; entries expire after 1 hour like before.
- **Local GeoLite2 fallback** — If ip-api.com is unreachable or you hit its 45 req/min rate limit (common on a machine with many active connections), NetMapGuard can fall back to a local [MaxMind GeoLite2](https://dev.maxmind.com/geoip/geolite2-free-geolocation-data) City database so the map keeps working, even offline.

  To enable it:
  1. Create a free MaxMind account and download `GeoLite2-City.mmdb`.
  2. Place it at `./GeoLite2-City.mmdb` (project root) or `~/.netmapguard/GeoLite2-City.mmdb`, or point `NETMAPGUARD_GEOIP_DB` at its path.
  3. Install the optional dependency: `pip install geoip2` (already included in `requirements.txt`).

  Without a database file present, NetMapGuard runs exactly as before — the fallback is skipped silently.

---

## License

This project is licensed under the [Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License (CC BY-NC-SA 4.0)](http://creativecommons.org/licenses/by-nc-sa/4.0/).

- **Attribution** — You must give appropriate credit.
- **NonCommercial** — You may not use the material for commercial purposes.
- **ShareAlike** — If you remix, transform, or build upon the material, you must distribute your contributions under the same license.

See the [LICENSE](LICENSE) file for full details.
