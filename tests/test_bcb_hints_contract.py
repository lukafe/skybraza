"""Cobertura explícita de BCB_REPORT_HINTS para todos os incisos da matriz (Onda A)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bcb_hints_loader import missing_explicit_bcb_hints  # noqa: E402


def test_bcb_hints_yaml_covers_all_matrix_incisos() -> None:
    missing = missing_explicit_bcb_hints()
    assert missing == [], f"Incisos sem texto explícito em BCB_REPORT_HINTS.yaml: {missing}"
