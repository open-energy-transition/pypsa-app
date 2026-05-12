"""Tests for SPAStaticFiles: API paths must 404 instead of falling back to index.html."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pypsa_app.backend.settings import API_V1_PREFIX
from pypsa_app.backend.spa_static_files import SPAStaticFiles


@pytest.fixture
def spa_app(tmp_path: Path) -> FastAPI:
    """FastAPI app with SPAStaticFiles mounted at '/' — mirrors production setup."""
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<!doctype html><html><body>SPA</body></html>")

    app = FastAPI()

    @app.get(f"{API_V1_PREFIX}/known")
    def known() -> dict:
        return {"ok": True}

    app.mount("/", SPAStaticFiles(directory=static_dir, html=True), name="app")
    return app


class TestSpaApiFallthroughGuard:
    def test_unknown_api_path_returns_404(self, spa_app: FastAPI) -> None:
        """Unregistered /api/v1/* path must 404, not fall back to index.html."""
        client = TestClient(spa_app)
        resp = client.get(f"{API_V1_PREFIX}/does-not-exist")
        assert resp.status_code == 404, (
            f"expected 404 for unknown API path, got {resp.status_code} "
            f"with body starting: {resp.text[:80]!r}"
        )

    def test_unknown_api_path_returns_json_not_html(self, spa_app: FastAPI) -> None:
        """The 404 response must be JSON so SPA fetch().then(r=>r.json()) does not crash."""
        client = TestClient(spa_app)
        resp = client.get(f"{API_V1_PREFIX}/does-not-exist")
        ctype = resp.headers.get("content-type", "")
        assert "application/json" in ctype, (
            f"expected JSON content-type for unknown API path, got {ctype!r}; "
            f"body: {resp.text[:80]!r}"
        )

    def test_known_api_path_still_works(self, spa_app: FastAPI) -> None:
        """Registered API routes must continue to work — guard only fires on miss."""
        client = TestClient(spa_app)
        resp = client.get(f"{API_V1_PREFIX}/known")
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

    def test_spa_route_still_falls_back_to_index_html(self, spa_app: FastAPI) -> None:
        """Non-API paths must still get index.html (SvelteKit client-side routing)."""
        client = TestClient(spa_app)
        resp = client.get("/some/spa/route")
        assert resp.status_code == 200
        assert "<!doctype html>" in resp.text.lower()
