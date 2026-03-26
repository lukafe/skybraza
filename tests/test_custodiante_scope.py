"""Trilhas custodiante e corretora — evidências, Jornada 2 e gatilhos críticos."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from evidence_requests import missing_evidence_yaml_incisos  # noqa: E402
from matrix_loader import TRACK_IDS, build_incisos_matrix, build_mandatory_keys  # noqa: E402
from rules_engine import compute_scope  # noqa: E402
from scope_fixtures import maximize_scope_answers  # noqa: E402


def test_missing_evidence_yaml_covers_all_tracks() -> None:
    assert missing_evidence_yaml_incisos() == []
    for tr in sorted(TRACK_IDS):
        assert missing_evidence_yaml_incisos(tr) == []


def test_maximize_scope_custodiante_covers_matrix() -> None:
    keys = set(build_incisos_matrix("custodiante").keys())
    _, meta = compute_scope(maximize_scope_answers("custodiante"), track="custodiante")
    assert meta["active_keys"] == keys


def test_maximize_scope_corretora_covers_matrix() -> None:
    keys = set(build_incisos_matrix("corretora").keys())
    _, meta = compute_scope(maximize_scope_answers("corretora"), track="corretora")
    assert meta["active_keys"] == keys


def test_journey_2_custodiante_staking_note_mentions_question_ids() -> None:
    answers = {
        "cust_diag_sc": False,
        "cust_diag_surface": False,
        "cust_C_staking": True,
    }
    _, meta = compute_scope(answers, track="custodiante")
    notas = meta["journey_2"].get("notas_heuristica") or []
    assert notas, "esperada nota heurística staking + ausência de SC"
    joined = " ".join(notas)
    assert "cust_C_staking" in joined
    assert "cust_diag_sc" in joined
    assert "P8" not in joined


def test_journey_2_corretora_staking_note_mentions_question_ids() -> None:
    answers = {
        "corr_diag_sc": False,
        "corr_diag_surface": False,
        "corr_C_staking": True,
    }
    _, meta = compute_scope(answers, track="corretora")
    notas = meta["journey_2"].get("notas_heuristica") or []
    assert notas, "esperada nota heurística staking + ausência de SC"
    joined = " ".join(notas)
    assert "corr_C_staking" in joined
    assert "corr_diag_sc" in joined
    assert "P8" not in joined


def test_mpc_mixed_adds_inciso_iii() -> None:
    """Modelo MPC deve acionar III (diligência terceiros), não só II obrigatório."""
    base = {
        "cust_diag_sc": False,
        "cust_diag_surface": False,
        "cust_A_transit": False,
        "cust_A_fiat": False,
        "cust_B_exterior": False,
        "cust_B_cloud": False,
        "cust_B_more_foreign": False,
        "cust_B_tp": [],
        "cust_C_stable": False,
        "cust_C_staking": False,
        "cust_C_if_api": False,
        "cust_C_catalog": "closed_set",
        "cust_D_narr": "",
        "cust_D_attestation": False,
        "cust_D_surveillance": False,
    }
    base["cust_A_model"] = "mpc_mixed"
    _, meta = compute_scope(base, track="custodiante")
    assert "III" in meta["active_keys"]
    mand = build_mandatory_keys("custodiante")
    extra = meta["active_keys"] - mand
    assert "III" in extra


def test_corretora_mpc_mixed_adds_inciso_iii() -> None:
    base = {
        "corr_diag_sc": False,
        "corr_diag_surface": False,
        "corr_A_transit": False,
        "corr_A_fiat": False,
        "corr_B_exterior": False,
        "corr_B_cloud": False,
        "corr_B_more_foreign": False,
        "corr_B_tp": [],
        "corr_C_stable": False,
        "corr_C_staking": False,
        "corr_C_if_api": False,
        "corr_C_catalog": "closed_set",
        "corr_D_narr": "",
        "corr_D_attestation": False,
        "corr_D_surveillance": False,
    }
    base["corr_A_model"] = "mpc_mixed"
    _, meta = compute_scope(base, track="corretora")
    assert "III" in meta["active_keys"]
    mand = build_mandatory_keys("corretora")
    extra = meta["active_keys"] - mand
    assert "III" in extra


def test_maximize_scope_default_track_is_intermediaria() -> None:
    from matrix_loader import INCISOS_MATRIX  # noqa: PLC0415

    _, meta = compute_scope(maximize_scope_answers())
    assert meta["active_keys"] == set(INCISOS_MATRIX.keys())
