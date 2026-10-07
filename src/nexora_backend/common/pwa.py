"""Serve the small PWA shell on the same origin as the session API."""

import os
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404

PWA_FILES = {
    "index.html": "text/html",
    "app.js": "application/javascript",
    "app.css": "text/css",
    "service-worker.js": "application/javascript",
    "manifest.json": "application/manifest+json",
    "icon.svg": "image/svg+xml",
    "icon-192.png": "image/png",
    "icon-512.png": "image/png",
    "apple-touch-icon.png": "image/png",
    "privacy.html": "text/html",
}


def pwa_file(request, filename="index.html"):
    if filename not in PWA_FILES:
        raise Http404()
    root = Path(
        os.environ.get("PWA_ROOT", settings.BASE_DIR.parent / "starup-frontend")
    )
    path = root / filename
    if not path.is_file():
        raise Http404()
    response = FileResponse(path.open("rb"), content_type=PWA_FILES[filename])
    response["Cache-Control"] = "no-cache"
    if filename == "service-worker.js":
        response["Service-Worker-Allowed"] = "/"
    return response
