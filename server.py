"""server.py – FastAPI application: serves the UI and streams data via WebSocket."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import pathlib
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

STATIC_DIR = pathlib.Path(__file__).parent / "static"

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
            # Keep the connection alive by listening for pings / any client msg
            await asyncio.wait_for(websocket.receive_text(), timeout=30)
    except (WebSocketDisconnect, asyncio.TimeoutError, Exception):
        pass
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

    while True:
        try:
            connections_raw = await asyncio.to_thread(get_connections)

            # Enrich each connection with geo data (cached after first call)
            enriched = []
            for conn in connections_raw:
                geo = await asyncio.to_thread(geolocate, conn.remote_ip)
                if geo is None:
                    continue  # skip IPs we can't locate
                entry = conn.to_dict()
                entry["geo"] = geo
                enriched.append(entry)

            current_ids = {e["id"] for e in enriched}

            added = [e for e in enriched if e["id"] not in prev_ids]
            removed_ids = list(prev_ids - current_ids)

            if added or removed_ids:
                await _broadcast(
                    {
                        "type": "delta",
                        "added": added,
                        "removed": removed_ids,
                        "local": _cached_local,
                    }
                )

            prev_ids = current_ids

        except Exception:
            logger.exception("Error in poll_loop")

        await asyncio.sleep(_POLL_INTERVAL)


@app.on_event("startup")
async def startup_event() -> None:
    asyncio.create_task(poll_loop())
