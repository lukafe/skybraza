"""
Prontidão do corpus (laws/) no escopo ativo e pacote de exportação JSON (Fase D; integrado no roteiro E).

Agrega status por inciso (completo / parcial / incompleto), referências STUB e índice simples
para priorizar trabalho de evidências antes da auditoria.

Limitações: o índice reflete apenas os campos ``corpus_status`` e ``ficheiros_corpus`` da matriz YAML,
não valida conteúdo real dos ficheiros em ``laws/``. STUBs contam como evidência pendente.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from matrix_loader import (
    TRACK_DEFAULT,
    build_incisos_matrix,
    get_coverage_meta,
    normalize_track,
    sort_scope_keys,
)

EXPORT_SCHEMA_VERSION = "1"


def _norm_status(raw: str) -> str:
    s = (raw or "").strip().lower()
    if s in ("completo", "parcial", "incompleto"):
        return s
    return "outro"


def corpus_readiness_for_scope(active_keys: set[str], track: str | None = None) -> dict[str, Any]:
    """
    Resume cobertura do corpus na matriz para os incisos atualmente no escopo.
    """
    t = normalize_track(track or TRACK_DEFAULT)
    inc_matrix = build_incisos_matrix(t)
    counts: dict[str, int] = {"completo": 0, "parcial": 0, "incompleto": 0, "outro": 0}
    items: list[dict[str, Any]] = []
    stub_refs: list[dict[str, Any]] = []

    for k in sort_scope_keys(active_keys, t):
        m = inc_matrix[k]
        files = str(m.get("ficheiros_corpus") or "")
        st = _norm_status(str(m.get("corpus_status") or ""))
        counts[st] = counts.get(st, 0) + 1
        uses_stub = "STUB" in files.upper()
        row = {
            "inciso_id": k,
            "item": m.get("item", k),
            "corpus_status": m.get("corpus_status", ""),
            "ficheiros_corpus": files,
            "uses_stub_reference": uses_stub,
        }
        items.append(row)
        if uses_stub:
            stub_refs.append({"inciso_id": k, "item": row["item"], "ficheiros_corpus": files})

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
    "build_export_package",
    "corpus_readiness_for_scope",
    "json_safe_meta",
]
