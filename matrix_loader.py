"""
Fase B — carrega a matriz normativa a partir de laws/COVERAGE_MATRIX.yaml
e expõe INCISOS_MATRIX, MANDATORY_KEYS e ordenação para o motor de escopo.
(Gatilhos por pergunta: laws/questionnaire.yaml via questionnaire_loader.)
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

PACKAGE_ROOT = Path(__file__).resolve().parent
MATRIX_PATH = PACKAGE_ROOT / "laws" / "COVERAGE_MATRIX.yaml"


class MatrixLoadError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _raw_matrix() -> dict[str, Any]:
    if not MATRIX_PATH.is_file():
        raise MatrixLoadError(f"Matriz não encontrada: {MATRIX_PATH}")
    with MATRIX_PATH.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict) or "incisos" not in data:
        raise MatrixLoadError("COVERAGE_MATRIX.yaml inválido: falta chave 'incisos'.")
    return data


def _flatten_desc(text: Any) -> str:
    if text is None:
        return ""
    if not isinstance(text, str):
        return str(text)
    return " ".join(text.split())


def build_incisos_matrix() -> dict[str, dict[str, str]]:
    data = _raw_matrix()
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


def build_mandatory_keys() -> frozenset[str]:
    data = _raw_matrix()
    esc = data.get("escopo_intermediario") or {}
    obs = esc.get("obrigatorios")
    if not isinstance(obs, list) or not obs:
        raise MatrixLoadError("escopo_intermediario.obrigatorios ausente ou vazio.")
    return frozenset(str(x) for x in obs)


def build_order_index() -> dict[str, int]:
    data = _raw_matrix()
    order = data.get("ordem_exibicao")
    if not isinstance(order, list) or not order:
        raise MatrixLoadError("ordem_exibicao ausente ou vazio.")
    return {str(k): i for i, k in enumerate(order)}


def sort_scope_keys(active_keys: set[str]) -> list[str]:
    idx = build_order_index()

    def sort_key(k: str) -> tuple[int, str]:
        return (idx.get(k, 10_000), k)

    return sorted(active_keys, key=sort_key)


def get_coverage_meta() -> dict[str, Any]:
    """Cabeçalho descritivo de COVERAGE_MATRIX.yaml (chave meta)."""
    m = _raw_matrix().get("meta")
    return dict(m) if isinstance(m, dict) else {}


def validate_matrix_consistency() -> list[str]:
    """Retorna lista de avisos (vazia se coerente)."""
    warnings: list[str] = []
    matrix = build_incisos_matrix()
    mandatory = build_mandatory_keys()
    order_idx = build_order_index()

    for k in mandatory:
        if k not in matrix:
            warnings.append(f"Obrigatório '{k}' não existe em incisos[].id")

    for k in matrix:
        if k not in order_idx:
            warnings.append(f"Inciso '{k}' sem entrada em ordem_exibicao")

    for k in order_idx:
        if k not in matrix:
            warnings.append(f"ordem_exibicao contém '{k}' sem entrada em incisos")

    return warnings


# Carrega uma vez na importação
INCISOS_MATRIX: dict[str, dict[str, str]] = build_incisos_matrix()
MANDATORY_KEYS: frozenset[str] = build_mandatory_keys()
_MATRIX_WARNINGS = validate_matrix_consistency()
if _MATRIX_WARNINGS:
    raise MatrixLoadError("COVERAGE_MATRIX inconsistente:\n- " + "\n- ".join(_MATRIX_WARNINGS))

__all__ = [
    "INCISOS_MATRIX",
    "MANDATORY_KEYS",
    "MATRIX_PATH",
    "MatrixLoadError",
    "build_incisos_matrix",
    "build_mandatory_keys",
    "build_order_index",
    "get_coverage_meta",
    "sort_scope_keys",
    "validate_matrix_consistency",
]
