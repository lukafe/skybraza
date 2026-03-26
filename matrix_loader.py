"""
Fase B — carrega a matriz normativa por trilha (intermediária | custodiante | corretora)
e expõe INCISOS_MATRIX / MANDATORY_KEYS default (intermediária) para compatibilidade.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

PACKAGE_ROOT = Path(__file__).resolve().parent

TRACK_DEFAULT = "intermediaria"
TRACK_IDS: frozenset[str] = frozenset({"intermediaria", "custodiante", "corretora"})

MATRIX_PATH = PACKAGE_ROOT / "laws" / "COVERAGE_MATRIX.yaml"

_MATRIX_PATH_BY_TRACK: dict[str, Path] = {
    "intermediaria": PACKAGE_ROOT / "laws" / "COVERAGE_MATRIX.yaml",
    "custodiante": PACKAGE_ROOT / "laws" / "tracks" / "custodiante" / "COVERAGE_MATRIX.yaml",
    "corretora": PACKAGE_ROOT / "laws" / "tracks" / "corretora" / "COVERAGE_MATRIX.yaml",
}

_SCOPE_YAML_KEY_BY_TRACK: dict[str, str] = {
    "intermediaria": "escopo_intermediario",
    "custodiante": "escopo_custodiante",
    "corretora": "escopo_corretora",
}


class MatrixLoadError(RuntimeError):
    pass


def normalize_track(track: str | None) -> str:
    t = (track or TRACK_DEFAULT).strip().lower()
    if t not in TRACK_IDS:
        raise MatrixLoadError(f"Trilha inválida: {track!r}. Use: {', '.join(sorted(TRACK_IDS))}")
    return t


@lru_cache(maxsize=len(TRACK_IDS))
def _raw_matrix_for(track: str) -> dict[str, Any]:
    t = normalize_track(track)
    path = _MATRIX_PATH_BY_TRACK[t]
    if not path.is_file():
        raise MatrixLoadError(f"Matriz não encontrada para trilha {t!r}: {path}")
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict) or "incisos" not in data:
        raise MatrixLoadError(f"COVERAGE_MATRIX inválido (trilha {t}): falta chave 'incisos'.")
    return data


def _flatten_desc(text: Any) -> str:
    if text is None:
        return ""
    if not isinstance(text, str):
        return str(text)
    return " ".join(text.split())


def build_incisos_matrix(track: str | None = None) -> dict[str, dict[str, str]]:
    t = normalize_track(track)
    data = _raw_matrix_for(t)
    out: dict[str, dict[str, str]] = {}
    for row in data["incisos"]:
        iid = row["id"]
        refs = row.get("refs_explicitas_na_in701") or []
        ref_str = " | ".join(refs) if refs else "—"
        lf = row.get("law_files") or []
        st = row.get("stub_file")
        if lf:
            files_s = "; ".join(lf)
        elif st:
            files_s = st
        else:
            files_s = "—"
        out[iid] = {
            "item": str(row.get("rotulo_in701", iid)),
            "descricao": _flatten_desc(row.get("resumo_certificacao_pt", "")),
            "ref_resolucao": ref_str,
            "artigo_in701": str(row.get("artigo_in701", "")),
            "ficheiros_corpus": files_s,
            "corpus_status": str(row.get("status", "")),
        }
    return out


def build_mandatory_keys(track: str | None = None) -> frozenset[str]:
    t = normalize_track(track)
    data = _raw_matrix_for(t)
    sk = _SCOPE_YAML_KEY_BY_TRACK[t]
    esc = data.get(sk) or {}
    obs = esc.get("obrigatorios")
    if not isinstance(obs, list) or not obs:
        raise MatrixLoadError(f"{sk}.obrigatorios ausente ou vazio (trilha {t}).")
    return frozenset(str(x) for x in obs)


def build_order_index(track: str | None = None) -> dict[str, int]:
    t = normalize_track(track)
    data = _raw_matrix_for(t)
    order = data.get("ordem_exibicao")
    if not isinstance(order, list) or not order:
        raise MatrixLoadError(f"ordem_exibicao ausente ou vazio (trilha {t}).")
    return {str(k): i for i, k in enumerate(order)}


def sort_scope_keys(active_keys: set[str], track: str | None = None) -> list[str]:
    t = normalize_track(track)
    idx = build_order_index(t)

    def sort_key(k: str) -> tuple[int, str]:
        return (idx.get(k, 10_000), k)

    return sorted(active_keys, key=sort_key)


def get_coverage_meta(track: str | None = None) -> dict[str, Any]:
    t = normalize_track(track)
    m = _raw_matrix_for(t).get("meta")
    return dict(m) if isinstance(m, dict) else {}


def validate_matrix_consistency(track: str | None = None) -> list[str]:
    """Avisos de coerência para uma trilha."""
    t = normalize_track(track)
    matrix = build_incisos_matrix(t)
    mandatory = build_mandatory_keys(t)
    order_idx = build_order_index(t)
    warnings: list[str] = []

    for k in mandatory:
        if k not in matrix:
            warnings.append(f"[{t}] Obrigatório '{k}' não existe em incisos[].id")

    for k in matrix:
        if k not in order_idx:
            warnings.append(f"[{t}] Inciso '{k}' sem entrada em ordem_exibicao")

    for k in order_idx:
        if k not in matrix:
            warnings.append(f"[{t}] ordem_exibicao contém '{k}' sem entrada em incisos")

    return warnings


# Importação: validar todas as trilhas
for _tr in sorted(TRACK_IDS):
    _w = validate_matrix_consistency(_tr)
    if _w:
        raise MatrixLoadError("Matriz inconsistente:\n- " + "\n- ".join(_w))

INCISOS_MATRIX: dict[str, dict[str, str]] = build_incisos_matrix(TRACK_DEFAULT)
MANDATORY_KEYS: frozenset[str] = build_mandatory_keys(TRACK_DEFAULT)

__all__ = [
    "INCISOS_MATRIX",
    "MANDATORY_KEYS",
    "MATRIX_PATH",
    "MatrixLoadError",
    "TRACK_DEFAULT",
    "TRACK_IDS",
    "build_incisos_matrix",
    "build_mandatory_keys",
    "build_order_index",
    "get_coverage_meta",
    "normalize_track",
    "sort_scope_keys",
    "validate_matrix_consistency",
]
