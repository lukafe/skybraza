"""Cobertura explícita de BCB_REPORT_HINTS para todos os incisos da matriz (Onda A)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bcb_hints_loader import missing_explicit_bcb_hints  # noqa: E402
from matrix_loader import TRACK_IDS  # noqa: E402


def test_bcb_hints_yaml_covers_all_matrix_incisos() -> None:
    for t in sorted(TRACK_IDS):
        missing = missing_explicit_bcb_hints(t)
        assert missing == [], f"[{t}] Incisos sem texto explícito em BCB_REPORT_HINTS.yaml: {missing}"


def test_custodiante_track_override_changes_hint_vii() -> None:
    from bcb_hints_loader import get_bcb_report_hint  # noqa: PLC0415

    a = get_bcb_report_hint("VII", track="intermediaria")
    b = get_bcb_report_hint("VII", track="custodiante")
    assert a != b
    assert "custodiante" in b.lower() or "MPC" in b or "HSM" in b
