"""Same-origin PWA assets and shell safety."""

import json
import struct

import pytest

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "path, content_type",
    [
        ("/", "text/html"),
        ("/app.js", "application/javascript"),
        ("/service-worker.js", "application/javascript"),
        ("/manifest.json", "application/manifest+json"),
        ("/privacy.html", "text/html"),
        ("/icon-192.png", "image/png"),
        ("/icon-512.png", "image/png"),
        ("/apple-touch-icon.png", "image/png"),
    ],
)
def test_pwa_assets_same_origin(api_client, path, content_type):
    response = api_client.get(path)
    assert response.status_code == 200
    assert response["Content-Type"].startswith(content_type)
    response.close()


def test_manifest_install_scope(api_client):
    response = api_client.get("/manifest.json")
    data = json.loads(b"".join(response.streaming_content))
    assert data["name"] == "StarUP — demandas e soluções"
    assert data["short_name"] == "StarUP"
    assert data["scope"] == "/" and data["start_url"] == "/"
    assert data["display"] == "standalone"


def test_service_worker_scope_header(api_client):
    response = api_client.get("/service-worker.js")
    assert response["Service-Worker-Allowed"] == "/"
    assert response["Cache-Control"] == "no-cache"
    response.close()


@pytest.mark.parametrize(
    "path, size",
    [
        ("/icon-192.png", 192),
        ("/icon-512.png", 512),
        ("/apple-touch-icon.png", 180),
    ],
)
def test_install_icons_have_declared_dimensions(api_client, path, size):
    response = api_client.get(path)
    data = b"".join(response.streaming_content)
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert struct.unpack(">II", data[16:24]) == (size, size)
