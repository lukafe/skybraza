"""Fase E — integração, blocos do questionário e exportação JSON."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from matrix_loader import INCISOS_MATRIX, MANDATORY_KEYS  # noqa: E402
from questionnaire_loader import get_blocks, get_questions, normalize_answers  # noqa: E402
from readiness import build_export_package  # noqa: E402
from rules_engine import compute_scope  # noqa: E402
from scope_fixtures import maximize_scope_answers  # noqa: E402


def test_question_blocks_declared_in_yaml() -> None:
    block_ids = {str(b["id"]) for b in get_blocks()}
    for q in get_questions():
        bid = str(q.get("block", ""))
        assert bid in block_ids, f"Pergunta {q['id']}: bloco '{bid}' não está em questionnaire.blocks"


def test_max_scope_covers_all_matrix_incisos() -> None:
    """Com todas as opções “máximas”, o escopo deve incluir todos os ids da matriz."""
    df, meta = compute_scope(maximize_scope_answers())
    active = meta["active_keys"]
    assert active == set(INCISOS_MATRIX.keys())
    assert meta["total_count"] == len(INCISOS_MATRIX)
    assert len(df) == len(INCISOS_MATRIX)


def test_export_package_roundtrip_json() -> None:
    df, meta = compute_scope(maximize_scope_answers())
    records = df.to_dict(orient="records")
    pack = build_export_package(institution="Validação E", meta=meta, scope_items=records)
    raw = json.dumps(pack, ensure_ascii=True)
    assert len(raw) > 100
    loaded = json.loads(raw)
    assert loaded["coverage_matrix_meta"]["fase"] == "E"
    assert loaded["export_schema_version"] == "1"
    assert len(loaded["scope_table"]) == len(records)


def test_normalize_answers_preserves_unknown_keys() -> None:
    merged = normalize_answers({"P1": False, "client_request_id": "abc-123", "extra_flag": 1})
    assert merged["P1"] is False
    assert merged["client_request_id"] == "abc-123"
    assert merged["extra_flag"] == 1


def test_mandatory_subset_of_matrix() -> None:
    for k in MANDATORY_KEYS:
        assert k in INCISOS_MATRIX
