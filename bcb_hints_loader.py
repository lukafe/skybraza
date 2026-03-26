"""
Carrega orientações indicativas para o relatório ao BCB por inciso (laws/BCB_REPORT_HINTS.yaml).
Suporta trilha intermediária e custodiante: overrides opcionais em ``tracks.<trilha>`` e fallback pela matriz da trilha.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from matrix_loader import build_incisos_matrix, normalize_track

PACKAGE_ROOT = Path(__file__).resolve().parent
HINTS_PATH = PACKAGE_ROOT / "laws" / "BCB_REPORT_HINTS.yaml"


@lru_cache(maxsize=1)
def _hints_document() -> dict[str, Any]:
    if not HINTS_PATH.is_file():
        return {}
    with HINTS_PATH.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data if isinstance(data, dict) else {}


def _incisos_hints() -> dict[str, Any]:
    inc = _hints_document().get("incisos")
    return inc if isinstance(inc, dict) else {}


def _track_hint_overrides(track: str) -> dict[str, Any]:
    t = normalize_track(track)
    if t == "intermediaria":
        return {}
    root = _hints_document().get("tracks")
    if not isinstance(root, dict):
        return {}
    ov = root.get(t)
    return ov if isinstance(ov, dict) else {}


def explicit_hint_keys(track: str | None = None) -> frozenset[str]:
    """Ids de inciso com texto explícito (YAML global ou override da trilha)."""
    t = normalize_track(track)
    keys: set[str] = set()
    for k, v in _incisos_hints().items():
        if isinstance(v, str) and v.strip():
            keys.add(str(k))
    for k, v in _track_hint_overrides(t).items():
        if isinstance(v, str) and v.strip():
            keys.add(str(k))
    return frozenset(keys)


def missing_explicit_bcb_hints(track: str | None = None) -> list[str]:
    """Incisos da matriz da trilha sem entrada explícita (global ou override de trilha)."""
    t = normalize_track(track)
    matrix_keys = set(build_incisos_matrix(t).keys())
    have = explicit_hint_keys(t)
    return sorted(k for k in matrix_keys if k not in have)


def get_bcb_report_hint(inciso_id: str, track: str | None = None) -> str:
    t = normalize_track(track)
    tovr = _track_hint_overrides(t).get(inciso_id)
    if isinstance(tovr, str) and tovr.strip():
        return " ".join(tovr.split())
    raw = _incisos_hints().get(inciso_id)
    if isinstance(raw, str) and raw.strip():
        return " ".join(raw.split())
    inc_matrix = build_incisos_matrix(t)
    meta = inc_matrix.get(inciso_id, {})
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
