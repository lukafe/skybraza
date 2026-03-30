"""
Motor de regras IN 701 / Resolução BCB nº 520 — escopo por trilha (intermediária | custodiante | corretora).

Incisos: laws/COVERAGE_MATRIX.yaml ou laws/tracks/{custodiante,corretora}/COVERAGE_MATRIX.yaml
Gatilhos: questionnaire por trilha (questionnaire_loader).
Pós-gatilhos: scope_narrative.suppress_custody_cluster_if_non_custodial — retira VII, XIV, XVI, XVII em qualquer trilha
quando o declarado for exclusivamente não custodial; em custodiante/corretora retira também XV (ver declares_exclusive_non_custodial_model).
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from bcb_hints_loader import get_bcb_report_hint
from matrix_loader import (
    TRACK_DEFAULT,
    build_incisos_matrix,
    build_mandatory_keys,
    normalize_track,
    sort_scope_keys,
)
from questionnaire_loader import (
    QUESTIONS,
    normalize_answers,
    potential_triggers_per_inciso,
    questions_by_block as _questionnaire_questions_by_block,
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


def _why_out_of_scope(potential: list[str], *, mandatory_in_yaml: bool, lang: str = "pt") -> str:
    """Texto para incisos fora do ``active_keys`` (inclui supressão de ids ainda obrigatórios na YAML)."""
    en = lang == "en"
    tail = ""
    if potential:
        tr = "; ".join(potential[:8])
        if len(potential) > 8:
            tr += "…"
        if en:
            tail = f" If the operation evolves, indicative conditions in the tool include: {tr}"
        else:
            tail = f" Se a operação evoluir, condições indicativas na ferramenta incluem: {tr}"

    if mandatory_in_yaml:
        if en:
            base = (
                "Not in the active scope calculated for this submission: the clause is a fixed mandatory in the YAML "
                "matrix for this track, but was excluded by a declarative rule (e.g. exclusively non-custodial model) "
                "or does not apply given the answers."
            )
            if not potential:
                return (
                    base
                    + " There are no conditional questions listing this id; the exclusion generally follows "
                    "non-custodial suppression — verify with compliance or legal."
                )
        else:
            base = (
                "Não consta no escopo ativo calculado nesta submissão: o inciso é obrigatório fixo na matriz YAML desta "
                "trilha, mas foi excluído por regra declarativa (por exemplo, modelo exclusivamente não custodial) ou não "
                "se mantém na delimitação face às respostas."
            )
            if not potential:
                return (
                    base
                    + " Não há perguntas condicionais que listem este id; em geral a exclusão segue a supressão não custodial "
                    "— validar enquadramento com compliance ou jurídico."
                )
        return base + tail

    if en:
        base = (
            "Not part of the audit scope for this delimitation: it is not a fixed mandatory in this track's matrix "
            "for the current model and no answer given triggered this clause."
        )
        if potential:
            return base + tail
        return f"{base} There is no trigger mapped in the current questionnaire for this clause."
    else:
        base = (
            "Não integra o escopo de auditoria desta delimitação: não é obrigatório fixo na matriz desta trilha "
            "para o modelo atual e nenhuma resposta dada acionou este inciso."
        )
        if potential:
            return base + tail
        return f"{base} Não há gatilho mapeado no questionário atual para este inciso."


def compute_scope(
    answers: dict[str, Any],
    track: str | None = None,
    lang: str = "pt",
    build_df: bool = True,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Retorna (dataframe só com incisos sujeitos a auditoria, metadados).

    ``track``: ``intermediaria`` (default), ``custodiante`` ou ``corretora``.
    ``lang``: ``pt`` (default) | ``en``
    ``build_df``: se ``False``, devolve um DataFrame vazio (útil em endpoints onde só
    os metadados são necessários, evitando a alocação desnecessária do pandas).
    """
    t = normalize_track(track or TRACK_DEFAULT)
    inc_matrix = build_incisos_matrix(t)
    mandatory = build_mandatory_keys(t)

    norm = normalize_answers(answers, t)
    triggered_by, free_text, audit_only = resolve_triggers(answers, t)
    pot_rev = potential_triggers_per_inciso(t)

    active_keys: set[str] = set(mandatory)
    for inc in triggered_by:
        active_keys.add(inc)

    # Ajuste declarativo: modelo exclusivamente não custodial (condições por trilha em scope_narrative).
    suppress_custody_cluster_if_non_custodial(active_keys, triggered_by, norm, t)

    why_by_key = build_why_texts_for_scope(active_keys, triggered_by, norm, mandatory, inc_matrix, t, lang=lang)
    llm_whys = try_enrich_why_with_llm(why_by_key, norm, triggered_by, inc_matrix, t)
    why_by_key = merge_llm_whys(why_by_key, llm_whys)

    all_matrix_keys = set(inc_matrix.keys())
    inactive_keys = all_matrix_keys - active_keys

    incisos_auditar: list[dict[str, Any]] = []
    rows: list[dict[str, str]] = []

    for key in sort_scope_keys(active_keys, t):
        meta = inc_matrix[key]
        is_mandatory = key in mandatory
        qids = triggered_by.get(key, [])
        if lang == "en":
            origem = "Mandatory (matrix)" if is_mandatory else "Triggered by answers"
            why_fallback = "Scope aligned with the IN 701 matrix and questionnaire answers."
        else:
            origem = "Obrigatório (matriz)" if is_mandatory else "Acionado por respostas"
            why_fallback = "Escopo alinhado à matriz IN 701 e às respostas ao questionário."
        why = why_by_key.get(key) or why_fallback
        hint = get_bcb_report_hint(key, track=t, lang=lang)

        if build_df:
            rows.append({
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
            })
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
    for key in sort_scope_keys(inactive_keys, t):
        meta = inc_matrix[key]
        pot = pot_rev.get(key, [])
        incisos_fora.append(
            {
                "inciso_id": key,
                "item": meta["item"],
                "artigo_in701": meta["artigo_in701"],
                "descricao": meta["descricao"],
                "por_que_nao_neste_escopo": _why_out_of_scope(pot, mandatory_in_yaml=key in mandatory, lang=lang),
            }
        )

    if build_df:
        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.drop(columns=["_key"], errors="ignore")
    else:
        df = pd.DataFrame()

    mandatory_count = sum(1 for k in active_keys if k in mandatory)
    conditional_count = len(active_keys) - mandatory_count
    corpus_readiness = corpus_readiness_for_scope(active_keys, t)

    meta_out: dict[str, Any] = {
        "track": t,
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
    meta_out["journey_2"] = build_journey_2_payload(norm, meta_out, lang=lang)
    return df, meta_out


def questions_by_block(track: str | None = None) -> dict[str, list[dict[str, Any]]]:
    return _questionnaire_questions_by_block(track)


__all__ = [
    "QUESTIONS",
    "SCOPE_COLUMNS",
    "compute_scope",
    "questions_by_block",
]
