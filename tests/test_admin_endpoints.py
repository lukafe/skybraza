"""Tests for admin endpoints — auth, audit log, matrix versions, simulate, webhook."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from main import _admin_sign_session, app  # noqa: E402


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def _admin_header() -> dict[str, str]:
    """Build a valid admin session Authorization header."""
    token = _admin_sign_session("test@certik.com", "Tester")
    return {"Authorization": f"Bearer {token}"}


# ── Auth ──────────────────────────────────────────────────────────────────────


def test_admin_config_returns_google_client_id(client: TestClient) -> None:
    r = client.get("/api/v1/admin/config")
    assert r.status_code == 200
    data = r.json()
    assert "google_client_id" in data
    assert "domain" in data


def test_admin_endpoints_require_auth(client: TestClient) -> None:
    for path in ["/api/v1/admin/stats", "/api/v1/admin/submissions", "/api/v1/admin/audit"]:
        r = client.get(path)
        assert r.status_code == 401, f"{path} should require auth"


def test_admin_password_login(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADMIN_SECRET", "test-secret-123")
    r = client.post("/api/v1/admin/login", json={"password": "test-secret-123"})
    assert r.status_code == 200
    data = r.json()
    assert data["email"] == "admin@local"
    assert "session_token" in data


def test_admin_wrong_password_returns_401(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADMIN_SECRET", "correct-pw")
    r = client.post("/api/v1/admin/login", json={"password": "wrong"})
    assert r.status_code == 401


# ── Stats & Submissions ──────────────────────────────────────────────────────


def test_admin_stats_with_auth(client: TestClient) -> None:
    r = client.get("/api/v1/admin/stats", headers=_admin_header())
    assert r.status_code == 200
    data = r.json()
    assert "total" in data


def test_admin_submissions_with_auth(client: TestClient) -> None:
    r = client.get("/api/v1/admin/submissions", headers=_admin_header())
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert "total" in data


# ── Audit Log ─────────────────────────────────────────────────────────────────


def test_admin_audit_log_with_auth(client: TestClient) -> None:
    r = client.get("/api/v1/admin/audit", headers=_admin_header())
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert "total" in data


# ── Matrix Versions (Changelog) ──────────────────────────────────────────────


def test_admin_matrix_versions(client: TestClient) -> None:
    r = client.get("/api/v1/admin/matrix-versions", headers=_admin_header())
    assert r.status_code == 200
    data = r.json()
    assert "tracks" in data
    assert len(data["tracks"]) >= 1
    for t in data["tracks"]:
        assert "track" in t
        assert "matrix_version" in t


# ── Simulate ──────────────────────────────────────────────────────────────────


def test_admin_simulate_returns_result(client: TestClient) -> None:
    r = client.post(
        "/api/v1/admin/simulate",
        json={"answers": {}, "track": "intermediaria", "institution": "Test Sim", "lang": "pt"},
        headers=_admin_header(),
    )
    assert r.status_code == 200
    data = r.json()
    assert data["simulated"] is True
    assert data["track"] == "intermediaria"
    assert "resumo" in data
    assert "incisos_sujeitos_auditoria" in data


def test_admin_simulate_requires_auth(client: TestClient) -> None:
    r = client.post(
        "/api/v1/admin/simulate",
        json={"answers": {}, "track": "intermediaria", "institution": "X"},
    )
    assert r.status_code == 401


# ── Webhook ───────────────────────────────────────────────────────────────────


def test_webhook_fires_on_submission(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """When WEBHOOK_URL is set, a POST request is sent after a successful submission."""
    monkeypatch.setenv("WEBHOOK_URL", "https://httpbin.org/post")
    called = {}

    def mock_urlopen(req, timeout=5):
        called["url"] = req.full_url
        called["data"] = json.loads(req.data)

    with patch("urllib.request.urlopen", mock_urlopen):
        r = client.post("/api/v1/scope", json={"institution": "Webhook Test", "answers": {}, "track": "intermediaria"})
        assert r.status_code == 200

    if "url" in called:
        assert called["url"] == "https://httpbin.org/post"
        assert called["data"]["event"] == "new_submission"
        assert called["data"]["institution"] == "Webhook Test"
