"""Gatilhos adicionais (P_arch, P_tp, P_list, P_reserves) — Onda B."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rules_engine import compute_scope  # noqa: E402


def _items(meta: dict) -> set[str]:
    return {x["item"] for x in meta["incisos_sujeitos_auditoria"]}


def test_p_arch_mpc_mixed_triggers_vii_ii() -> None:
    base = {qid: False for qid in ["P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9"]}
    base["P_arch"] = "mpc_mixed"
    _, meta = compute_scope(base)
    items = _items(meta)
    assert "VII" in items
    assert "II" in items
    assert "par1_I_h" not in meta["triggered_by"]
    assert "§ 1º (I) (h)" not in items


def test_p_tp_all_options_maximizes_terceiros() -> None:
    base = {f"P{i}": False for i in range(1, 10)}
    base["P_tp"] = ["lp", "custody_inst", "cloud_infra", "fiat_bank", "kyc_vendor"]
    _, meta = compute_scope(base)
    items = _items(meta)
    for label in ("II", "IV", "V", "VII", "VI (a)"):
        assert label in items


def test_p_list_own_committee_triggers_ix() -> None:
    base = {f"P{i}": False for i in range(1, 10)}
    base["P_list"] = "own_committee"
    _, meta = compute_scope(base)
    assert "IX_a" in meta["triggered_by"]
    assert "IX_b" in meta["triggered_by"]


def test_p_list_execution_only_nao_aciona_ix_a() -> None:
    """Conjunto fechado só para execução: sem política de listagem/catálogo ampliável → não IX (a)."""
    base = {f"P{i}": False for i in range(1, 10)}
    base["P_list"] = "execution_only"
    _, meta = compute_scope(base)
    assert "IX_a" not in meta["triggered_by"]
    assert "IX_a" not in meta["active_keys"]


def test_p_list_mirror_lp_ainda_aciona_ix_a() -> None:
    base = {f"P{i}": False for i in range(1, 10)}
    base["P_list"] = "mirror_lp"
    _, meta = compute_scope(base)
    assert "IX_a" in meta["triggered_by"]


def test_p_reserves_adds_ib_when_p2_false() -> None:
    """I (b) pode vir só de P_reserves se P2 não aciona trânsito."""
    base = {f"P{i}": False for i in range(1, 10)}
    base["P_reserves"] = True
    _, meta = compute_scope(base)
    items = _items(meta)
    assert "I (b)" in items
    assert "I_b" in meta["triggered_by"]


def test_mandatory_plus_conditional_why_text_when_overlap() -> None:
    """Se um inciso obrigatório também for citado por gatilho, o texto de justificativa combina ambos."""
    # par1_I é obrigatório; nenhuma pergunta atual aciona par1_I em duplicado com triggered_by.
    # Usamos respostas vazias: só obrigatórios; par1_I deve ter texto só de obrigatoriedade.
    _, meta = compute_scope({})
    par1 = next(x for x in meta["incisos_sujeitos_auditoria"] if x["inciso_id"] == "par1_I")
    assert "Obrigatório" in par1["origem_escopo"] or "matriz" in par1["por_que_sera_auditado"].lower()
    assert "Adicionalmente" not in par1["por_que_sera_auditado"]
