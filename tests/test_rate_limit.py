"""Rate limiting best-effort (ver rate_limit.py)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import rate_limit  # noqa: E402
from main import app  # noqa: E402


@pytest.fixture(autouse=True)
def _rate_limit_tight(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_WINDOW_SEC", "60")
    monkeypatch.setenv("RATE_LIMIT_MAX_REQUESTS", "3")
    monkeypatch.delenv("RATE_LIMIT_DISABLED", raising=False)
    rate_limit.reset_limiter_for_tests()
    yield
    rate_limit.reset_limiter_for_tests()
    monkeypatch.delenv("RATE_LIMIT_MAX_REQUESTS", raising=False)


def test_rate_limit_returns_429_after_max() -> None:
    c = TestClient(app)
    for _ in range(3):
        r = c.get("/api/v1/questions")
        assert r.status_code == 200
    r4 = c.get("/api/v1/questions")
    assert r4.status_code == 429
    body = r4.json()
    assert body["detail"]["code"] == "RATE_LIMIT_EXCEEDED"


def test_health_not_rate_limited() -> None:
    c = TestClient(app)
    for _ in range(10):
        assert c.get("/api/v1/health").status_code == 200
