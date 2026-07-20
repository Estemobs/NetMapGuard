"""main.py – entry point: python main.py"""

from __future__ import annotations

import argparse
import logging
import os
import platform
import shutil
import socket
import subprocess
import sys
import webbrowser

import uvicorn

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)

# Any Chromium-based browser can be launched "as an app": a plain window
# with no address bar or tabs, so NetMapGuard opens looking like a real
# desktop app instead of a browser tab pointed at a raw localhost URL.
_CHROMIUM_LINUX_NAMES = [
    "google-chrome-stable", "google-chrome", "chromium-browser", "chromium",
    "brave-browser", "microsoft-edge-stable", "microsoft-edge",
]
_CHROMIUM_MACOS_PATHS = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
]
# Edge ships with Windows 10/11 by default, so this is almost always found.
_CHROMIUM_WINDOWS_PATH_TEMPLATES = [
    r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe",
    r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe",
    r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
    r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
    r"%LocalAppData%\Google\Chrome\Application\chrome.exe",
    r"%ProgramFiles%\BraveSoftware\Brave-Browser\Application\brave.exe",
    r"%LocalAppData%\BraveSoftware\Brave-Browser\Application\brave.exe",
]


def _port_in_use(host: str, port: int) -> bool:
    connect_host = "127.0.0.1" if host == "0.0.0.0" else host
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((connect_host, port)) == 0


def _find_chromium_browser() -> str | None:
    system = platform.system()
    if system == "Linux":
        for name in _CHROMIUM_LINUX_NAMES:
            path = shutil.which(name)
            if path:
                return path
    elif system == "Darwin":
        for path in _CHROMIUM_MACOS_PATHS:
            if os.path.isfile(path):
                return path
    elif system == "Windows":
        for template in _CHROMIUM_WINDOWS_PATH_TEMPLATES:
            path = os.path.expandvars(template)
            if os.path.isfile(path):
                return path
    return None


def _open_browser(url: str) -> None:
    # PyInstaller's Linux bootloader points LD_LIBRARY_PATH at its bundled
    # libs so the frozen app can find them, and that setting leaks into any
    # subprocess we spawn here — those then risk crashing trying to load
    # PyInstaller's bundled libs instead of the system's. Restore the
    # original value just for this launch.
    restore_key = None
    orig = os.environ.get("LD_LIBRARY_PATH_ORIG")
    if orig is not None:
        restore_key = os.environ.get("LD_LIBRARY_PATH")
        os.environ["LD_LIBRARY_PATH"] = orig

    opened = False
    try:
        browser_path = _find_chromium_browser()
        if browser_path:
            subprocess.Popen(
                [browser_path, f"--app={url}", "--window-size=1280,860"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=(platform.system() != "Windows"),
            )
            opened = True
        else:
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
