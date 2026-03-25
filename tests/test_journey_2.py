"""Jornada 2 — evidências por inciso, SC audit e pentest."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from evidence_requests import missing_evidence_yaml_incisos  # noqa: E402
from rules_engine import compute_scope  # noqa: E402
from scope_fixtures import maximize_scope_answers  # noqa: E402


def test_evidence_yaml_covers_all_matrix_incisos() -> None:
    assert missing_evidence_yaml_incisos() == []


def test_journey_2_presente_em_meta() -> None:
    _, meta = compute_scope({})
    j2 = meta.get("journey_2")
    assert isinstance(j2, dict)
    assert j2.get("journey_2_schema_version") == "2"
    assert "smart_contract_audit" in j2
    assert "penetration_test" in j2
    assert "checklist_por_inciso" in j2


def test_journey_2_diag_smart_contract_e_pentest() -> None:
    _, meta = compute_scope({"P_diag_sc": True, "P_diag_surface": True})
    j2 = meta["journey_2"]
    assert j2["smart_contract_audit"]["aplicavel"] is True
    assert "Certik4audit" in j2["smart_contract_audit"]["acao_cliente"]
    assert j2["penetration_test"]["aplicavel"] is True


def test_journey_2_checklist_so_incisos_ativos() -> None:
    _, meta = compute_scope({})
    j2 = meta["journey_2"]
    ids = {x["inciso_id"] for x in j2["checklist_por_inciso"]}
    assert ids == meta["active_keys"]


def test_pedidos_incluem_documento_otimo() -> None:
    _, meta = compute_scope({})
    first = (meta["journey_2"]["checklist_por_inciso"] or [])[0]
    p0 = first["pedidos"][0]
    assert "documento_otimo" in p0
    assert len(p0["documento_otimo"]) > 20


def test_journey_2_max_scope_total_pedidos() -> None:
    _, meta = compute_scope(maximize_scope_answers())
    j2 = meta["journey_2"]
    assert j2["total_pedidos_documentacao"] >= len(meta["active_keys"]) * 2
