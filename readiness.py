"""
Prontidão do corpus (laws/) no escopo ativo e pacote de exportação JSON (Fase D; integrado no roteiro E).

Agrega status por inciso (completo / parcial / incompleto), referências STUB e índice simples
para priorizar trabalho de evidências antes da auditoria. Valida também a existência real dos
ficheiros referenciados em ``laws/`` e devolve avisos quando há divergência entre o status YAML
e a presença física do arquivo.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from matrix_loader import (
    TRACK_DEFAULT,
    PACKAGE_ROOT,
    build_incisos_matrix,
    get_coverage_meta,
    normalize_track,
    sort_scope_keys,
)

LAWS_DIR = PACKAGE_ROOT / "laws"


def _check_corpus_files(ficheiros_str: str) -> tuple[list[str], list[str]]:
    """
    Dada a string de ficheiros do campo ``ficheiros_corpus``, devolve (existentes, ausentes).
    Ficheiros separados por ``;``.
    """
    if not ficheiros_str or ficheiros_str == "—":
        return [], []
    names = [f.strip() for f in ficheiros_str.split(";") if f.strip()]
    present = [n for n in names if (LAWS_DIR / n).is_file()]
    missing = [n for n in names if not (LAWS_DIR / n).is_file()]
    return present, missing


def validate_corpus_files(track: str | None = None) -> list[dict[str, Any]]:
    """
    Verifica se os ficheiros referenciados na matriz (trilha dada ou intermediária por defeito)
    existem em ``laws/``. Devolve lista de avisos para os que estão em falta.
    """
    t = normalize_track(track or TRACK_DEFAULT)
    inc_matrix = build_incisos_matrix(t)
    warnings: list[dict[str, Any]] = []
    for key, meta in inc_matrix.items():
        files_str = str(meta.get("ficheiros_corpus") or "")
        _, missing = _check_corpus_files(files_str)
        if missing:
            warnings.append(
                {
                    "inciso_id": key,
                    "item": meta.get("item", key),
                    "corpus_status_yaml": meta.get("corpus_status", ""),
                    "ficheiros_ausentes": missing,
                }
            )
    return warnings

EXPORT_SCHEMA_VERSION = "1"


def _norm_status(raw: str) -> str:
    s = (raw or "").strip().lower()
    if s in ("completo", "parcial", "incompleto"):
        return s
    return "outro"


def corpus_readiness_for_scope(active_keys: set[str], track: str | None = None) -> dict[str, Any]:
    """
    Resume cobertura do corpus na matriz para os incisos atualmente no escopo.
    Inclui verificação de existência física dos ficheiros referenciados em ``laws/``.
    """
    t = normalize_track(track or TRACK_DEFAULT)
    inc_matrix = build_incisos_matrix(t)
    counts: dict[str, int] = {"completo": 0, "parcial": 0, "incompleto": 0, "outro": 0}
    items: list[dict[str, Any]] = []
    stub_refs: list[dict[str, Any]] = []
    files_ausentes: list[dict[str, Any]] = []

    for k in sort_scope_keys(active_keys, t):
        m = inc_matrix[k]
        files = str(m.get("ficheiros_corpus") or "")
        st = _norm_status(str(m.get("corpus_status") or ""))
        counts[st] = counts.get(st, 0) + 1
        uses_stub = "STUB" in files.upper()
        _, missing = _check_corpus_files(files)
        row = {
            "inciso_id": k,
            "item": m.get("item", k),
            "corpus_status": m.get("corpus_status", ""),
            "ficheiros_corpus": files,
            "uses_stub_reference": uses_stub,
            "ficheiros_ausentes_em_disco": missing,
        }
        items.append(row)
        if uses_stub:
            stub_refs.append({"inciso_id": k, "item": row["item"], "ficheiros_corpus": files})
        if missing:
            files_ausentes.append(
                {
                    "inciso_id": k,
                    "item": row["item"],
                    "corpus_status_yaml": m.get("corpus_status", ""),
                    "ficheiros_ausentes": missing,
                }
            )

    total = len(active_keys)
    if total:
        weighted = (counts["completo"] + 0.5 * counts["parcial"]) / total
        idx = round(100 * weighted, 1)
    else:
        idx = 100.0

    gaps_priority = [r for r in items if _norm_status(r["corpus_status"]) == "incompleto"]
    gaps_priority.extend([r for r in items if _norm_status(r["corpus_status"]) == "parcial"])

    return {
        "counts": counts,
        "total_in_scope": total,
        "readiness_index_0_100": idx,
        "items": items,
        "stub_references": stub_refs,
        "gaps_priority": gaps_priority,
        "ficheiros_ausentes_em_disco": files_ausentes,
    }


def json_safe_meta(meta: dict[str, Any]) -> dict[str, Any]:
    """Converte sets e estruturas aninhadas para JSON (cópia superficial profunda limitada)."""

    def walk(x: Any) -> Any:
        if isinstance(x, set):
            return sorted(x)
        if isinstance(x, dict):
            return {str(k): walk(v) for k, v in x.items()}
        if isinstance(x, list):
            return [walk(v) for v in x]
        return x

    return walk(meta)


def build_export_package(
    *,
    institution: str,
    meta: dict[str, Any],
    scope_items: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Pacote único para arquivo / integração (respostas, escopo, prontidão do corpus).
    """
    meta_public = {k: v for k, v in meta.items() if k != "active_keys"}
    meta_public = json_safe_meta(meta_public)
    ak = meta.get("active_keys")
    if isinstance(ak, set):
        meta_public["active_keys"] = sorted(ak)
    elif ak is not None:
        meta_public["active_keys"] = list(ak)

    tr = meta.get("track")
    cov = get_coverage_meta(tr if isinstance(tr, str) else None)
    return {
        "export_schema_version": EXPORT_SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "institution": institution.strip(),
        "coverage_matrix_meta": {
            "fase": cov.get("fase", ""),
            "instrucao_normativa": cov.get("instrucao_normativa", ""),
            "resolucao_principal": cov.get("resolucao_principal", ""),
        },
        "scope_table": scope_items,
        "engine_meta": meta_public,
    }


__all__ = [
    "EXPORT_SCHEMA_VERSION",
    "LAWS_DIR",
    "build_export_package",
    "corpus_readiness_for_scope",
    "json_safe_meta",
    "validate_corpus_files",
]
