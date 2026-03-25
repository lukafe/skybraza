"""Fase D — prontidão do corpus e pacote de exportação."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from readiness import build_export_package, corpus_readiness_for_scope  # noqa: E402
from matrix_loader import MANDATORY_KEYS  # noqa: E402
from rules_engine import compute_scope  # noqa: E402


def test_corpus_readiness_counts_sum_to_scope() -> None:
    _, meta = compute_scope({})
    cr = meta["corpus_readiness"]
    assert cr["total_in_scope"] == meta["total_count"]
    assert sum(cr["counts"].values()) == cr["total_in_scope"]
    assert 0 <= cr["readiness_index_0_100"] <= 100


def test_corpus_readiness_mandatory_keys_only() -> None:
    cr = corpus_readiness_for_scope(set(MANDATORY_KEYS))
    assert cr["total_in_scope"] == len(MANDATORY_KEYS)


def test_export_bundle_json_serializable() -> None:
    _, meta = compute_scope({"P1": True})
    records = [{"Item IN 701": "VII", "Status": "x"}]
    pack = build_export_package(institution="Test Co", meta=meta, scope_items=records)
    json.dumps(pack, ensure_ascii=True)
    assert pack["export_schema_version"] == "1"
    assert "generated_at_utc" in pack
    assert pack["engine_meta"]["total_count"] == meta["total_count"]
    assert isinstance(pack["engine_meta"]["active_keys"], list)
