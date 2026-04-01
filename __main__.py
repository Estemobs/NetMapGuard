"""__main__.py – entry point: python -m netmapguard"""

from __future__ import annotations

import argparse
import logging
import sys
import webbrowser

import uvicorn

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="netmapguard",
        description="Real-time network traffic visualiser on a world map.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8888, help="Bind port (default: 8888)")
    parser.add_argument("--no-browser", action="store_true", help="Do not open browser automatically")
    parser.add_argument("--poll-interval", type=float, default=2.0,
                        help="Connection poll interval in seconds (default: 2)")
    args = parser.parse_args()

    # Allow overriding the poll interval
    import server as _srv
    _srv._POLL_INTERVAL = args.poll_interval

    url = f"http://{args.host}:{args.port}"
    logger.info("Starting NetMapGuard at %s", url)

    if not args.no_browser:
        import threading
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()

    uvicorn.run(
        "server:app",
        host=args.host,
        port=args.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
