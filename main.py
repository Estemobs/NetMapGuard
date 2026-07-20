"""main.py – entry point: python main.py"""

from __future__ import annotations

import argparse
import logging
import os
import socket
import sys
import webbrowser

import uvicorn

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


def _port_in_use(host: str, port: int) -> bool:
    connect_host = "127.0.0.1" if host == "0.0.0.0" else host
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((connect_host, port)) == 0


def _open_browser(url: str) -> None:
    # PyInstaller's Linux bootloader points LD_LIBRARY_PATH at its bundled
    # libs so the frozen app can find them, and that setting leaks into
    # subprocesses webbrowser.open() spawns (e.g. xdg-open, itself a shell
    # script) — those then crash trying to load PyInstaller's bundled
    # libreadline/ncurses instead of the system's. Restore the original
    # value just for this launch.
    restore_key = None
    orig = os.environ.get("LD_LIBRARY_PATH_ORIG")
    if orig is not None:
        restore_key = os.environ.get("LD_LIBRARY_PATH")
        os.environ["LD_LIBRARY_PATH"] = orig

    try:
        opened = webbrowser.open(url)
    except Exception:
        opened = False
    finally:
        if orig is not None:
            if restore_key is not None:
                os.environ["LD_LIBRARY_PATH"] = restore_key
            else:
                os.environ.pop("LD_LIBRARY_PATH", None)

    if not opened:
        logger.warning("Could not open a browser automatically — open %s manually.", url)


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

    # 0.0.0.0 means "listen on every interface" — it isn't a valid address
    # to *open in a browser*, so point the browser at localhost instead.
    browser_host = "127.0.0.1" if args.host == "0.0.0.0" else args.host
    url = f"http://{args.host}:{args.port}"
    browser_url = f"http://{browser_host}:{args.port}"

    if _port_in_use(args.host, args.port):
        logger.info(
            "NetMapGuard already appears to be running at %s — opening it instead of starting a second instance.",
            browser_url,
        )
        if not args.no_browser:
            _open_browser(browser_url)
        return

    # Allow overriding the poll interval
    import server as _srv
    _srv._POLL_INTERVAL = args.poll_interval

    logger.info("Starting NetMapGuard at %s", url)

    if not args.no_browser:
        import threading
        threading.Timer(1.5, lambda: _open_browser(browser_url)).start()

    # Pass the app object directly (rather than the "server:app" import
    # string) so this works when frozen into a standalone executable, where
    # uvicorn's string-based module reload/import machinery isn't reliable.
    uvicorn.run(
        _srv.app,
        host=args.host,
        port=args.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
