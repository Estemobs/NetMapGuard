"""server.py – FastAPI application: serves the UI and streams data via WebSocket."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import pathlib
import sys
from typing import Dict, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from capture import get_connections
from enrich import geolocate, get_my_location

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

_clients: Set[WebSocket] = set()
_POLL_INTERVAL = 2.0  # seconds between connection polls

# When packaged with PyInstaller, bundled data (static/) is extracted to
# sys._MEIPASS rather than sitting next to this file.
_BASE_DIR = pathlib.Path(getattr(sys, "_MEIPASS", pathlib.Path(__file__).parent))
STATIC_DIR = _BASE_DIR / "static"

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(title="NetMapGuard", version="2.0.0")

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=FileResponse)
async def index() -> FileResponse:
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/healthz")
async def health() -> dict:
    return {"status": "ok"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    _clients.add(websocket)
    logger.info("Client connected: %s (total %d)", websocket.client, len(_clients))
    try:
        # Send the current local location immediately on connect
        local = _cached_local or {"ip": "unknown", "lat": 0.0, "lon": 0.0, "city": "", "country": ""}
        await websocket.send_text(json.dumps({"type": "local", "local": local}))
        # Then wait for disconnect (all state updates come via the broadcaster)
        while True:
            try:
                # Listen for client msg with 10s timeout 
                await asyncio.wait_for(websocket.receive_text(), timeout=10)
            except asyncio.TimeoutError:
                # Send heartbeat to keep connection alive
                await websocket.send_text(json.dumps({"type": "ping"}))
    except (WebSocketDisconnect, Exception) as e:
        logger.debug("WebSocket error: %s", type(e).__name__)
    finally:
        _clients.discard(websocket)
        logger.info("Client disconnected (total %d)", len(_clients))


# ---------------------------------------------------------------------------
# Background broadcaster
# ---------------------------------------------------------------------------

_cached_local: dict | None = None


async def _broadcast(message: dict) -> None:
    """Send *message* to all connected WebSocket clients."""
    if not _clients:
        return
    text = json.dumps(message)
    dead: Set[WebSocket] = set()
    for ws in list(_clients):
        try:
            await ws.send_text(text)
        except Exception:
            dead.add(ws)
    _clients.difference_update(dead)


async def poll_loop() -> None:
    """Background task: poll connections and broadcast updates every POLL_INTERVAL seconds."""
    global _cached_local

    # Resolve local location once (may block briefly)
    logger.info("Resolving local machine location …")
    _cached_local = await asyncio.to_thread(get_my_location)
    logger.info("Local location: %s", _cached_local)

    prev_ids: Set[str] = set()
    geo_failures = 0

    while True:
        try:
            connections_raw = await asyncio.to_thread(get_connections)
            logger.debug("Polled %d raw connections", len(connections_raw))

            # Enrich each connection with geo data (cached after first call)
            enriched = []
            for conn in connections_raw:
                try:
                    geo = await asyncio.wait_for(
                        asyncio.to_thread(geolocate, conn.remote_ip),
                        timeout=1.5  # Max 1.5s per IP
                    )
                    if geo is None:
                        continue  # skip IPs we can't locate
                    entry = conn.to_dict()
                    entry["geo"] = geo
                    enriched.append(entry)
                except asyncio.TimeoutError:
                    logger.debug("Timeout geolocating IP: %s", conn.remote_ip)
                    geo_failures += 1
                    continue
                except Exception as e:
                    logger.debug("Error geolocating %s: %s", conn.remote_ip, e)
                    geo_failures += 1
                    continue

            current_ids = {e["id"] for e in enriched}

            added = [e for e in enriched if e["id"] not in prev_ids]
            removed_ids = list(prev_ids - current_ids)

            if added or removed_ids:
                logger.info("Broadcasting: +%d, -%d connections", len(added), len(removed_ids))
                await _broadcast(
                    {
                        "type": "delta",
                        "added": added,
                        "removed": removed_ids,
                        "local": _cached_local,
                    }
                )

            if geo_failures > 0:
                logger.warning("Had %d geolocation failures this cycle", geo_failures)
                geo_failures = 0

            prev_ids = current_ids

        except Exception as e:
            logger.exception("Error in poll_loop: %s", e)

        await asyncio.sleep(_POLL_INTERVAL)


@app.on_event("startup")
async def startup_event() -> None:
    asyncio.create_task(poll_loop())
