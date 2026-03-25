"""
Motor de regras IN 701 / Resolução BCB nº 520 — escopo intermediário CertiK.

Incisos e obrigatórios: laws/COVERAGE_MATRIX.yaml (matrix_loader).
Gatilhos e questionário: laws/questionnaire.yaml (questionnaire_loader, Fase C).
Orientação relatório BCB: laws/BCB_REPORT_HINTS.yaml (bcb_hints_loader).
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from bcb_hints_loader import get_bcb_report_hint
from matrix_loader import INCISOS_MATRIX, MANDATORY_KEYS, sort_scope_keys
from questionnaire_loader import (
    QUESTIONS,
    normalize_answers,
    potential_triggers_per_inciso,
    questions_by_block,
    resolve_triggers,
)
from evidence_requests import build_journey_2_payload
from readiness import corpus_readiness_for_scope
from scope_narrative import (
    build_why_texts_for_scope,
    merge_llm_whys,
    suppress_custody_cluster_if_non_custodial,
    try_enrich_why_with_llm,
)

# Colunas do DataFrame (linhas = apenas incisos sujeitos a auditoria neste escopo)
SCOPE_COLUMNS: tuple[str, ...] = (
    "Item IN 701",
    "Artigo IN 701",
    "Descrição do Escopo",
    "Ref. Resolução 520",
    "Corpus (laws/)",
    "Status corpus",
    "Origem no escopo",
    "Por que será auditado",
    "Orientação relatório ao BCB",
)


def _why_out_of_scope(potential: list[str]) -> str:
    base = (
        "Não integra o escopo de auditoria desta delimitação: não é obrigatório fixo na fase intermediária "
        "para o modelo atual e nenhuma resposta dada acionou este inciso."
    )
    if potential:
        tail = "; ".join(potential[:8])
        if len(potential) > 8:
            tail += "…"
        return f"{base} Se a operação evoluir, condições indicativas na ferramenta incluem: {tail}"
    return f"{base} Não há gatilho mapeado no questionário atual para este inciso."


def compute_scope(answers: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Retorna (dataframe só com incisos sujeitos a auditoria, metadados).

    Metadados incluem ``incisos_fora_escopo_auditoria`` com incisos da matriz que,
    nesta configuração de respostas, não entram no escopo.
    """
    norm = normalize_answers(answers)
    triggered_by, free_text, audit_only = resolve_triggers(answers)
    pot_rev = potential_triggers_per_inciso()

    active_keys: set[str] = set(MANDATORY_KEYS)
    for inc in triggered_by:
        active_keys.add(inc)

    suppress_custody_cluster_if_non_custodial(active_keys, triggered_by, norm)

    why_by_key = build_why_texts_for_scope(active_keys, triggered_by, norm, MANDATORY_KEYS)
    llm_whys = try_enrich_why_with_llm(why_by_key, norm, triggered_by)
    why_by_key = merge_llm_whys(why_by_key, llm_whys)

    all_matrix_keys = set(INCISOS_MATRIX.keys())
    inactive_keys = all_matrix_keys - active_keys

    incisos_auditar: list[dict[str, Any]] = []
    rows: list[dict[str, str]] = []

    for key in sort_scope_keys(active_keys):
        meta = INCISOS_MATRIX[key]
        is_mandatory = key in MANDATORY_KEYS
        qids = triggered_by.get(key, [])
        origem = "Obrigatório (matriz)" if is_mandatory else "Acionado por respostas"
        why = why_by_key.get(key) or "Escopo alinhado à matriz IN 701 e às respostas ao questionário."
        hint = get_bcb_report_hint(key)

        row = {
            "Item IN 701": meta["item"],
            "Artigo IN 701": meta["artigo_in701"],
            "Descrição do Escopo": meta["descricao"],
            "Ref. Resolução 520": meta["ref_resolucao"],
            "Corpus (laws/)": meta["ficheiros_corpus"],
            "Status corpus": meta["corpus_status"],
            "Origem no escopo": origem,
            "Por que será auditado": why,
            "Orientação relatório ao BCB": hint,
            "_key": key,
        }
        rows.append(row)
        incisos_auditar.append(
            {
                "inciso_id": key,
                "item": meta["item"],
                "artigo_in701": meta["artigo_in701"],
                "descricao": meta["descricao"],
                "ref_resolucao": meta["ref_resolucao"],
                "ficheiros_corpus": meta["ficheiros_corpus"],
                "corpus_status": meta["corpus_status"],
                "origem_escopo": origem,
                "perguntas_gatilho": qids,
                "por_que_sera_auditado": why,
                "orientacao_relatorio_bcb": hint,
            }
        )

    incisos_fora: list[dict[str, Any]] = []
    for key in sort_scope_keys(inactive_keys):
        meta = INCISOS_MATRIX[key]
        pot = pot_rev.get(key, [])
        incisos_fora.append(
            {
                "inciso_id": key,
                "item": meta["item"],
                "artigo_in701": meta["artigo_in701"],
                "descricao": meta["descricao"],
                "por_que_nao_neste_escopo": _why_out_of_scope(pot),
            }
        )

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.drop(columns=["_key"], errors="ignore")

    mandatory_count = sum(1 for k in active_keys if k in MANDATORY_KEYS)
    conditional_count = len(active_keys) - mandatory_count
    corpus_readiness = corpus_readiness_for_scope(active_keys)

    meta_out = {
        "answers": norm,
        "active_keys": active_keys,
        "triggered_by": triggered_by,
        "free_text": free_text,
        "audit_only": audit_only,
        "mandatory_count": mandatory_count,
        "conditional_count": conditional_count,
        "total_count": len(active_keys),
        "total_fora_escopo_auditoria": len(incisos_fora),
        "corpus_readiness": corpus_readiness,
        "incisos_sujeitos_auditoria": incisos_auditar,
        "incisos_fora_escopo_auditoria": incisos_fora,
    }
    meta_out["journey_2"] = build_journey_2_payload(norm, meta_out)
    return df, meta_out


__all__ = [
    "QUESTIONS",
    "SCOPE_COLUMNS",
    "compute_scope",
    "questions_by_block",
]
