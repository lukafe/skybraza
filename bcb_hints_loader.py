"""
Carrega orientações indicativas para o relatório ao BCB por inciso (laws/BCB_REPORT_HINTS.yaml).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from matrix_loader import INCISOS_MATRIX

PACKAGE_ROOT = Path(__file__).resolve().parent
HINTS_PATH = PACKAGE_ROOT / "laws" / "BCB_REPORT_HINTS.yaml"


@lru_cache(maxsize=1)
def _raw_hints() -> dict[str, Any]:
    if not HINTS_PATH.is_file():
        return {}
    with HINTS_PATH.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    inc = data.get("incisos")
    return inc if isinstance(inc, dict) else {}


def explicit_hint_keys() -> frozenset[str]:
    """Ids de inciso com texto explícito em BCB_REPORT_HINTS (não só fallback da matriz)."""
    keys: set[str] = set()
    for k, v in _raw_hints().items():
        if isinstance(v, str) and v.strip():
            keys.add(str(k))
    return frozenset(keys)


def missing_explicit_bcb_hints() -> list[str]:
    """Incisos da matriz sem entrada explícita no YAML de hints (ordenado)."""
    have = explicit_hint_keys()
    return sorted(k for k in INCISOS_MATRIX if k not in have)


def get_bcb_report_hint(inciso_id: str) -> str:
    raw = _raw_hints().get(inciso_id)
    if isinstance(raw, str) and raw.strip():
        return " ".join(raw.split())
    meta = INCISOS_MATRIX.get(inciso_id, {})
    desc = (meta.get("descricao") or "").strip()
    if desc:
        return (
            "O relatório deve demonstrar, com políticas, procedimentos e evidências verificáveis, o atendimento "
            "a este requisito, explicitamente ligado à redação da IN 701 e aos extratos da Res. 520 aplicáveis. "
            f"Foco: {desc[:500]}"
            + ("…" if len(desc) > 500 else "")
        )
    return (
        "Descreva de forma estruturada como a instituição implementa o requisito, com artefatos técnicos e "
        "referências normativas da Res. 520 correlatas."
    )


__all__ = [
    "HINTS_PATH",
    "explicit_hint_keys",
    "get_bcb_report_hint",
    "missing_explicit_bcb_hints",
]
