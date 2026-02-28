"""Standalone desktop entrypoint.

Starts the FastAPI server, also serves the pre-built React bundle at ``/``,
then opens the default browser at ``http://localhost:8000``. Bundled into a
single-file executable by ``scripts/build-desktop.py`` via PyInstaller.

Usage (dev)::

    python -m aperture_server.desktop

The exe built from this file requires neither Python nor Node on the user's
machine — everything is baked in.
"""
from __future__ import annotations

import os
import sys
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn
from fastapi.staticfiles import StaticFiles

from .main import app


def _bundle_root() -> Path:
    """Where PyInstaller unpacked our data files (sys._MEIPASS) in a frozen
    build, or the repo root in dev."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[3]


def _mount_static() -> None:
    """Mount the built React app at /. If /dist is missing (e.g. you forgot to
    `npm run build`), fall back to a tiny notice page."""
    dist = _bundle_root() / "apps" / "web" / "dist"
    if dist.is_dir():
        # The React router is history-mode, so SPA fallback: serve index.html
        # for unknown paths that aren't API routes.
        app.mount("/", StaticFiles(directory=str(dist), html=True), name="web")
    else:
        from fastapi.responses import HTMLResponse

        @app.get("/")
        async def _notice() -> HTMLResponse:
            return HTMLResponse(
                "<h1>Aperture</h1>"
                "<p>The web bundle was not found. Run <code>npm run build</code>"
                " in <code>apps/web/</code>, or use the pre-packaged installer "
                "from GitHub Releases.</p>"
            )


def _open_browser(url: str, delay: float = 1.5) -> None:
    def _go():
        time.sleep(delay)
        webbrowser.open(url)

    threading.Thread(target=_go, daemon=True).start()


def main() -> None:
    port = int(os.environ.get("APERTURE_PORT", "8000"))
    host = os.environ.get("APERTURE_HOST", "127.0.0.1")
    _mount_static()
    url = f"http://{host}:{port}"
    _open_browser(url)
    print(f"Aperture running at {url}")
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    main()
