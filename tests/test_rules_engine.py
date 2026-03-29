"""Testes do motor de escopo IN 701."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rules_engine import SCOPE_COLUMNS, compute_scope, questions_by_block  # noqa: E402
from matrix_loader import INCISOS_MATRIX, MANDATORY_KEYS  # noqa: E402
from questionnaire_loader import TRIGGER_MAP  # noqa: E402


def test_mandatory_only_when_all_no() -> None:
    df, meta = compute_scope({})
    assert meta["total_count"] == len(MANDATORY_KEYS)
    assert meta["mandatory_count"] == len(MANDATORY_KEYS)
    assert meta["conditional_count"] == 0
    assert set(meta["active_keys"]) == set(MANDATORY_KEYS)
    assert meta["triggered_by"] == {}
    assert len(meta["incisos_sujeitos_auditoria"]) == len(MANDATORY_KEYS)
    assert meta["total_fora_escopo_auditoria"] == len(meta["incisos_fora_escopo_auditoria"])
    assert meta["total_count"] + meta["total_fora_escopo_auditoria"] == len(INCISOS_MATRIX)


def test_dataframe_columns() -> None:
    df, _ = compute_scope({})
    assert tuple(df.columns) == SCOPE_COLUMNS


def test_p1_triggers_custody_cluster() -> None:
    df, meta = compute_scope({"P1": True})
    items = set(df["Item IN 701"].tolist())
    assert {"VII", "XIV", "XVI", "XVII"}.issubset(items)
    assert meta["total_count"] == len(MANDATORY_KEYS) + 4


def test_p2_triggers_transit() -> None:
    df, _ = compute_scope({"P2": True})
    items = set(df["Item IN 701"].tolist())
    assert {"I (a)", "I (b)", "XV"}.issubset(items)


def test_p3_adds_x_b_ii_conditional() -> None:
    df, meta = compute_scope({"P3": True})
    row = df[df["Item IN 701"] == "X (b) (ii)"]
    assert len(row) == 1
    assert row.iloc[0]["Origem no escopo"] == "Acionado por respostas"
    assert "X_b_ii" in meta["triggered_by"]


def test_p4_p5_dedupes_ii_and_iv() -> None:
    df, meta = compute_scope({"P4": True, "P5": True})
    assert df[df["Item IN 701"] == "II"].shape[0] == 1
    assert df[df["Item IN 701"] == "IV"].shape[0] == 1
    assert meta["triggered_by"]["II"] == ["P4", "P5"]


def test_string_sim_normalized() -> None:
    df, _ = compute_scope({"P9": "Sim"})
    assert "V" in set(df["Item IN 701"].tolist())


def test_p8_par1_I_h() -> None:
    df, meta = compute_scope({"P8": True})
    assert "§ 1º (I) (h)" in set(df["Item IN 701"].tolist())
    assert "par1_I_h" in meta["triggered_by"]


def test_questions_by_block_counts() -> None:
    blocks = questions_by_block()
    assert len(blocks["diag"]) == 2
    assert len(blocks["A"]) == 4
    assert len(blocks["B"]) == 4
    assert len(blocks["C"]) == 4
    assert len(blocks["D"]) == 3


def test_all_triggers_max_scope() -> None:
    answers = {f"P{i}": True for i in range(1, 10)}
    df, meta = compute_scope(answers)
    assert meta["total_count"] == len(df)
    expected_extra = set().union(*TRIGGER_MAP.values())
    assert expected_extra <= meta["active_keys"]


def test_mandatory_includes_x_b_i_not_x_b_ii() -> None:
    df, _ = compute_scope({})
    items = set(df["Item IN 701"].tolist())
    assert "X (b) (i)" in items
    assert "X (b) (ii)" not in items


def test_rows_sorted_like_yaml_order() -> None:
    df, _ = compute_scope({})
    # Primeiro item obrigatório na ordem do art. 4º é IV (continuidade — elevado a obrigatório fixo)
    assert df.iloc[0]["Item IN 701"] == "IV"


def test_modelo_nao_custodial_remove_cluster_vii_xiv() -> None:
    """P1 Não + P_arch client_only + sem custody_inst em P_tp não deve acionar VII/XIV/XVI/XVII."""
    _, meta = compute_scope({"P1": False, "P_arch": "client_only", "P_tp": []})
    ids = {x["inciso_id"] for x in meta["incisos_sujeitos_auditoria"]}
    assert "VII" not in ids
    assert "XIV" not in ids
    assert "XVI" not in ids
    assert "XVII" not in ids


def test_custody_inst_em_p_tp_mantem_xiv_mesmo_client_only() -> None:
    """Custodiante institucional declarado reintroduz custódia mesmo com P_arch client_only."""
    _, meta = compute_scope({"P1": False, "P_arch": "client_only", "P_tp": ["custody_inst"]})
    ids = {x["inciso_id"] for x in meta["incisos_sujeitos_auditoria"]}
    assert "XIV" in ids
    assert "VII" in ids


def test_por_que_nao_e_apenas_lista_de_perguntas() -> None:
    _, meta = compute_scope({"P3": True})
    row = next(x for x in meta["incisos_sujeitos_auditoria"] if x["inciso_id"] == "X_b_ii")
    why = row["por_que_sera_auditado"]
    assert "P3" not in why or "pergunta" in why.lower()
    assert "«" in why or "X" in why
    assert len(why) > 80
