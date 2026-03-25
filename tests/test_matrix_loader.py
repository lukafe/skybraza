"""Testes do carregamento da matriz YAML (Fase B)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_matrix_path_exists() -> None:
    from matrix_loader import MATRIX_PATH, get_coverage_meta

    assert MATRIX_PATH.is_file()
    meta = get_coverage_meta()
    assert "fase" in meta
    assert meta["fase"] == "E"


def test_all_incisos_have_required_fields() -> None:
    from matrix_loader import INCISOS_MATRIX

    for iid, meta in INCISOS_MATRIX.items():
        assert iid
        for k in ("item", "descricao", "ref_resolucao", "artigo_in701", "ficheiros_corpus", "corpus_status"):
            assert k in meta


def test_par1_I_h_in_matrix() -> None:
    from matrix_loader import INCISOS_MATRIX

    assert "par1_I_h" in INCISOS_MATRIX
    assert "staking" in INCISOS_MATRIX["par1_I_h"]["descricao"].lower() or "art. 71" in INCISOS_MATRIX["par1_I_h"]["ref_resolucao"]
