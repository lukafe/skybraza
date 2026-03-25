"""Contrato HTTP da API (Onda A) — schema version e POST /api/scope."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from matrix_loader import INCISOS_MATRIX, MANDATORY_KEYS  # noqa: E402

# Import após sys.path
from main import API_SCHEMA_VERSION, app  # noqa: E402


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def test_health_includes_api_schema_version(client: TestClient) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["api_schema_version"] == API_SCHEMA_VERSION
    assert data.get("api_rest_version") == "v1"


def test_v1_routes_mirror_legacy(client: TestClient) -> None:
    h = client.get("/api/v1/health")
    assert h.status_code == 200
    assert h.json() == client.get("/api/health").json()
    q = client.get("/api/v1/questions")
    assert q.status_code == 200
    assert q.json()["api_schema_version"] == API_SCHEMA_VERSION
    leg = client.post("/api/v1/scope", json={"institution": "A", "answers": {}})
    assert leg.status_code == 200
    assert leg.json()["institution"] == "A"


def test_questions_includes_api_schema_version(client: TestClient) -> None:
    r = client.get("/api/questions")
    assert r.status_code == 200
    data = r.json()
    assert data["api_schema_version"] == API_SCHEMA_VERSION
    assert "blocks" in data
    assert len(data["blocks"]) >= 1


def test_post_scope_minimal_contract(client: TestClient) -> None:
    r = client.post("/api/scope", json={"institution": "Test Co", "answers": {}})
    assert r.status_code == 200
    data = r.json()
    assert data["api_schema_version"] == API_SCHEMA_VERSION
    assert data["institution"] == "Test Co"
    assert isinstance(data["incisos_sujeitos_auditoria"], list)
    assert isinstance(data["incisos_fora_escopo_auditoria"], list)
    assert len(data["incisos_sujeitos_auditoria"]) == len(MANDATORY_KEYS)
    assert "resumo" in data
    assert data["resumo"]["total_sujeitos_auditoria"] == len(MANDATORY_KEYS)
    assert "corpus_readiness" in data
    assert data["resumo"]["total_sujeitos_auditoria"] + data["resumo"]["total_fora_escopo_auditoria"] == len(
        INCISOS_MATRIX
    )
    j2 = data.get("journey_2")
    assert isinstance(j2, dict)
    assert j2.get("journey_2_schema_version") == "2"
    assert "checklist_por_inciso" in j2
    assert "documento_otimo" in (j2["checklist_por_inciso"][0]["pedidos"][0])


def test_post_scope_invalid_body_returns_422(client: TestClient) -> None:
    r = client.post("/api/scope", json={"answers": "not-a-dict"})
    assert r.status_code == 422


def test_post_scope_compute_error_hides_internal_detail(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    import rules_engine  # noqa: PLC0415

    def _boom(*_a, **_kw):
        raise RuntimeError("internal_secret_xyz")

    monkeypatch.setattr(rules_engine, "compute_scope", _boom)
    r = client.post("/api/scope", json={"institution": "X", "answers": {}})
    assert r.status_code == 400
    body = r.json()
    assert body["detail"]["code"] == "SCOPE_COMPUTE_ERROR"
    assert "internal_secret" not in str(body)


def test_optional_api_key_rejects_without_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CERTIK_API_KEY", "test-secret-key")
    # Lê CERTIK_API_KEY em cada pedido — não é necessário recarregar o módulo
    c = TestClient(app)
    r = c.post("/api/scope", json={"answers": {}})
    assert r.status_code == 401
    r2 = c.post("/api/scope", json={"answers": {}}, headers={"X-Certik-Api-Key": "test-secret-key"})
    assert r2.status_code == 200
    r3 = c.get("/api/health")
    assert r3.status_code == 200
    r4 = c.get("/api/v1/health")
    assert r4.status_code == 200
    r5 = c.post("/api/v1/scope", json={"answers": {}})
    assert r5.status_code == 401
    r6 = c.post(
        "/api/v1/scope",
        json={"answers": {}},
        headers={"X-Certik-Api-Key": "test-secret-key"},
    )
    assert r6.status_code == 200
    monkeypatch.delenv("CERTIK_API_KEY", raising=False)
