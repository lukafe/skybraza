"""
Jornada 2 — checklist de evidências por inciso ativo + diagnóstico SC audit / pentest.

Fonte: laws/AUDITOR_EVIDENCE_BY_INCISO.yaml
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from matrix_loader import build_incisos_matrix, normalize_track, sort_scope_keys

PACKAGE_ROOT = Path(__file__).resolve().parent
EVIDENCE_PATH = PACKAGE_ROOT / "laws" / "AUDITOR_EVIDENCE_BY_INCISO.yaml"

JOURNEY_2_SCHEMA_VERSION = "2"


def _journey_2_corretora_e_notas(answers: dict[str, Any], lang: str = "pt") -> list[str]:
    """Notas adicionais quando o questionário E (corretora) sinaliza intermediação ou produtos sensíveis."""
    en = lang == "en"
    out: list[str] = []
    if answers.get("corr_E_margin_product"):
        out.append(
            "Margin/leverage product indicated (corr_E_margin_product). Validate eligibility under Res. 520 art. 72 "
            "and compatibility with art. 12 restrictions — cross-check with legal/compliance before BCB reporting."
            if en else
            "Indicou produto de margem/alavancagem (corr_E_margin_product). Validar enquadramento na Res. 520 art. 72 "
            "(elegibilidade da instituição) e compatibilidade com vedações do art. 12 — cruzar com jurídico/compliance "
            "antes do relatório ao BCB."
        )
    if answers.get("corr_E_liquidity_provider_contract"):
        out.append(
            "Liquidity provider contract in place (corr_E_liquidity_provider_contract). Gather the minimum clauses of "
            "art. 38 Res. 520 (business model, settlement, safe custody transfer) for the evidence folder."
            if en else
            "Contrato com provedor de liquidez (corr_E_liquidity_provider_contract). Reunir cláusulas mínimas do "
            "art. 38 Res. 520 (modelo de negócio, liquidação, transferência segura de custódia) para pasta de evidências."
        )
    if answers.get("corr_E_market_maker_contract"):
        out.append(
            "Market maker contracted (corr_E_market_maker_contract). Document the contractual parameters of "
            "art. 39 Res. 520 and fairness among participants."
            if en else
            "Formador de mercado contratado (corr_E_market_maker_contract). Documentar parâmetros contratuais do "
            "art. 39 Res. 520 e equidade face a outros participantes."
        )
    if answers.get("corr_E_rfq_offering"):
        out.append(
            "RFQ / request for quote active (corr_E_rfq_offering). Confirm client disclosure per Res. 520 "
            "art. 67, §6 (quotes, deadlines, counterparty, risks)."
            if en else
            "RFQ / request for quote ativo (corr_E_rfq_offering). Confirmar disclosure ao cliente conforme Res. 520 "
            "art. 67, §6º (cotações, prazos, contraparte, riscos)."
        )
    if answers.get("corr_E_conflict_units"):
        out.append(
            "Desk vs. custody separation indicated (corr_E_conflict_units). Include organisational chart/policy "
            "referencing Res. 520 art. 85 and clause X (a) IN 701 in the evidence folder."
            if en else
            "Assinalou separação mesa vs custódia (corr_E_conflict_units). Incluir na evidência organograma/política "
            "referenciando Res. 520 art. 85 e inciso X (a) IN 701."
        )
    return out


def _journey_2_custodiante_e_notas(answers: dict[str, Any], lang: str = "pt") -> list[str]:
    """Notas quando o questionário E (custodiante) sinaliza programas de custódia ou supervisão reforçada."""
    en = lang == "en"
    out: list[str] = []
    if answers.get("cust_E_treasury_split"):
        out.append(
            "Documented segregation of own VA vs client VA indicated (cust_E_treasury_split). Attach the policy "
            "and org chart referencing Res. 520 arts. 29–31 and clauses I (a), XV IN 701."
            if en else
            "Assinalou segregação documentada AV próprios vs clientes (cust_E_treasury_split). Juntar política "
            "e organograma referenciando Res. 520 arts. 29–31 e incisos I (a), XV IN 701."
        )
    if answers.get("cust_E_subcustody_art74"):
        out.append(
            "Active sub-custody programme (cust_E_subcustody_art74). Ensure evidence of continuous monitoring "
            "and timely reporting of non-compliance to the BCB (Res. 520 art. 74, VI)."
            if en else
            "Programa de subcustódia ativo (cust_E_subcustody_art74). Garantir evidências de monitoramento "
            "contínuo e de comunicação tempestiva ao BCB em caso de descumprimento (Res. 520 art. 74, VI)."
        )
    if answers.get("cust_E_stress_art82"):
        out.append(
            "Stress tests conducted (cust_E_stress_art82). File the method and results for the legal retention "
            "period for supervision (Res. 520 art. 82, §2)."
            if en else
            "Testes de stress realizados (cust_E_stress_art82). Arquivar método e resultados pelo prazo legal "
            "para supervisão (Res. 520 art. 82, §2º)."
        )
    if answers.get("cust_E_staking_bcb_notice"):
        out.append(
            "Prior BCB notification for staking offering confirmed (cust_E_staking_bcb_notice). "
            "Verify the date and protocol against art. 82, §5 of Res. 520."
            if en else
            "Indicou cumprimento de comunicação prévia ao BCB sobre oferta de staking (cust_E_staking_bcb_notice). "
            "Confirmar data e protocolo face ao art. 82, §5º da Res. 520."
        )
    return out


def _journey_2_intermediaria_e_notas(answers: dict[str, Any], lang: str = "pt") -> list[str]:
    """Notas quando o bloco E (intermediária) sinaliza intermediação regulada ou produtos de mercado."""
    en = lang == "en"
    out: list[str] = []
    if answers.get("int_E_art69_controls"):
        out.append(
            "Art. 69 conflict-of-interest controls indicated (int_E_art69_controls). Attach the approved policy and "
            "evidence of independent monitoring to the dossier — clause X (a) IN 701."
            if en else
            "Assinalou controles de conflito art. 69 (int_E_art69_controls). Juntar política aprovada e evidências de "
            "monitoramento independente ao dossiê — inciso X (a) IN 701."
        )
    if answers.get("int_E_lp_art38"):
        out.append(
            "Liquidity provider contract in place (int_E_lp_art38). Gather the minimum clauses of art. 38 Res. 520 "
            "(business model, settlement, custody)."
            if en else
            "Contrato com provedor de liquidez (int_E_lp_art38). Reunir cláusulas mínimas do art. 38 Res. 520 "
            "(modelo de negócio, liquidação, custódia)."
        )
    if answers.get("int_E_mm_art39"):
        out.append(
            "Market maker contracted (int_E_mm_art39). Document the parameters of art. 39 Res. 520 and "
            "fairness among participants."
            if en else
            "Formador de mercado contratado (int_E_mm_art39). Documentar parâmetros do art. 39 Res. 520 e equidade "
            "entre participantes."
        )
    if answers.get("int_E_rfq_art67"):
        out.append(
            "RFQ active (int_E_rfq_art67). Confirm client disclosure per Res. 520 art. 67, §6."
            if en else
            "RFQ ativo (int_E_rfq_art67). Confirmar disclosure ao cliente conforme Res. 520 art. 67, §6º."
        )
    return out


# Texto base quando o YAML não define ``documento_otimo`` por item.
CRITERIOS_DOCUMENTO_OTIMO: dict[str, str] = {
    "politica": (
        "aprovador e data de vigência explícitos; dono do controle e periodicidade de revisão; "
        "objetivos e controles mensuráveis; ligação clara à operação e às exigências BCB / Res. 520 aplicáveis; "
        "histórico de versões ou referência à última aprovação formal."
    ),
    "procedimento": (
        "passos ordenados com responsáveis (RACI ou equivalente); SLAs e registos obrigatórios (templates de ticket, "
        "relatório ou checklist); tratamento de exceções e escalação; evidência de execução recente (amostra redigida)."
    ),
    "evidencia": (
        "artefatos datados e rastreáveis a um período recente; versão aprovada ou referência interna; "
        "dados sensíveis minimizados ou anonimizados; quando possível, ligação a um ticket ou referência de auditoria interna."
    ),
    "contrato": (
        "cláusulas relevantes identificadas (acesso, auditoria, SLA, confidencialidade, subcontratação, rescisão); "
        "versão assinada ou última em vigor; mapa de anexos e alterações; partes e datas claras."
    ),
    "diagrama": (
        "legenda e atores; fluxos de dados e de confiança; ambientes (produção, homologação); "
        "coerência com políticas e com a narrativa operacional apresentada ao auditor; data da última atualização."
    ),
    "organizacional": (
        "organograma ou mapa de mandatos atualizado; linhas de reporte ao conselho ou equivalente; "
        "periodicidade de informações e principais responsáveis nomeados."
    ),
    "_default": (
        "documento datado, com dono identificado, revisão periódica definida e amostra ou referência que demonstre "
        "implementação recente alinhada ao pedido."
    ),
}

CRITERIOS_DOCUMENTO_OTIMO_EN: dict[str, str] = {
    "politica": (
        "explicit approver and effective date; control owner and review frequency; "
        "measurable objectives and controls; clear link to operations and applicable BCB / Res. 520 requirements; "
        "version history or reference to the last formal approval."
    ),
    "procedimento": (
        "ordered steps with responsible parties (RACI or equivalent); mandatory SLAs and records (ticket templates, "
        "reports or checklists); exception handling and escalation paths; evidence of recent execution (redacted sample)."
    ),
    "evidencia": (
        "artefacts dated and traceable to a recent period; approved version or internal reference; "
        "sensitive data minimised or anonymised; where possible, linked to a ticket or internal audit reference."
    ),
    "contrato": (
        "relevant clauses identified (access, audit, SLA, confidentiality, subcontracting, termination); "
        "signed or current version; annexe and amendment map; parties and dates clearly stated."
    ),
    "diagrama": (
        "legend and actors; data and trust flows; environments (production, staging); "
        "consistency with policies and the operational narrative presented to the auditor; date of last update."
    ),
    "organizacional": (
        "up-to-date organisational chart or mandate map; reporting lines to the board or equivalent; "
        "information frequency and key named responsible parties."
    ),
    "_default": (
        "dated document with identified owner, defined periodic review and a sample or reference demonstrating "
        "recent implementation aligned with the request."
    ),
}


def _documento_otimo_text(pedido: dict[str, Any], lang: str = "pt") -> str:
    custom = str(pedido.get("documento_otimo") or "").strip()
    if custom:
        return " ".join(custom.split())
    cat = str(pedido.get("categoria") or "").strip().lower() or "_default"
    if lang == "en":
        base = CRITERIOS_DOCUMENTO_OTIMO_EN.get(cat) or CRITERIOS_DOCUMENTO_OTIMO_EN["_default"]
        tit = str(pedido.get("titulo_en") or pedido.get("titulo") or "").strip()
        if tit:
            return f'For «{tit}», an exemplary document typically includes: {base}'
        return f"An exemplary document typically includes: {base}"
    base = CRITERIOS_DOCUMENTO_OTIMO.get(cat) or CRITERIOS_DOCUMENTO_OTIMO["_default"]
    tit = str(pedido.get("titulo") or "").strip()
    if tit:
        return f'Para «{tit}», um documento exemplar costuma incluir: {base}'
    return f"Um documento exemplar costuma incluir: {base}"


def _enrich_pedidos(items: list[dict[str, Any]], lang: str = "pt") -> list[dict[str, Any]]:
    en = lang == "en"
    out: list[dict[str, Any]] = []
    for raw in items:
        p = dict(raw)
        if en:
            p["titulo"] = str(p.get("titulo_en") or p.get("titulo") or "").strip()
            p["detalhe"] = str(p.get("detalhe_en") or p.get("detalhe") or "").strip()
        p["documento_otimo"] = _documento_otimo_text(p, lang)
        out.append(p)
    return out


@lru_cache(maxsize=1)
def _raw_evidence_config() -> dict[str, Any]:
    if not EVIDENCE_PATH.is_file():
        return {}
    with EVIDENCE_PATH.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data if isinstance(data, dict) else {}


def evidence_inciso_keys_declared() -> frozenset[str]:
    data = _raw_evidence_config()
    inc = data.get("incisos")
    if not isinstance(inc, dict):
        return frozenset()
    return frozenset(str(k) for k in inc.keys())


def missing_evidence_yaml_incisos(track: str | None = None) -> list[str]:
    """
    Incisos da matriz (trilha dada ou todas as trilhas) sem bloco em AUDITOR_EVIDENCE_BY_INCISO.yaml.
    Sem ``track``, verifica a união das matrizes de todas as trilhas conhecidas.
    """
    from matrix_loader import TRACK_IDS, build_incisos_matrix, normalize_track

    declared = evidence_inciso_keys_declared()
    if track is not None:
        t = normalize_track(track)
        matrix_keys = set(build_incisos_matrix(t).keys())
        return sorted(k for k in matrix_keys if k not in declared)
    missing: set[str] = set()
    for tr in sorted(TRACK_IDS):
        for k in build_incisos_matrix(tr):
            if k not in declared:
                missing.add(k)
    return sorted(missing)


def build_journey_2_payload(
    answers: dict[str, Any],
    meta_scope: dict[str, Any],
    lang: str = "pt",
) -> dict[str, Any]:
    """
    ``answers`` deve estar normalizado (ex.: output de ``normalize_answers``).
    ``meta_scope`` deve conter pelo menos ``active_keys`` (set de ids de inciso).
    ``lang``: ``pt`` (default) | ``en``
    """
    en = lang == "en"
    data = _raw_evidence_config()
    meta_yaml = data.get("meta") if isinstance(data.get("meta"), dict) else {}
    gh_user = str(meta_yaml.get("smart_contract_github_user") or "Certik4audit").strip() or "Certik4audit"
    pentest_url = (os.environ.get("CERTIK_PENTEST_FORM_URL") or "").strip() or str(
        meta_yaml.get("pentest_form_url_default") or ""
    ).strip()

    track = normalize_track(str(meta_scope.get("track") or "intermediaria"))
    if track == "custodiante":
        p_sc = bool(answers.get("cust_diag_sc"))
        p_surf = bool(answers.get("cust_diag_surface"))
        p_staking = bool(answers.get("cust_C_staking"))
        q_staking, q_sc = "cust_C_staking", "cust_diag_sc"
    elif track == "corretora":
        p_sc = bool(answers.get("corr_diag_sc"))
        p_surf = bool(answers.get("corr_diag_surface"))
        p_staking = bool(answers.get("corr_C_staking"))
        q_staking, q_sc = "corr_C_staking", "corr_diag_sc"
    else:
        p_sc = bool(answers.get("P_diag_sc"))
        p_surf = bool(answers.get("P_diag_surface"))
        p_staking = bool(answers.get("P8"))
        q_staking, q_sc = "P8", "P_diag_sc"

    notas: list[str] = []
    if p_staking and not p_sc:
        if en:
            notas.append(
                f"The operation indicates staking/yield ({q_staking}). Confirm whether own or white-label "
                f"on-chain smart contracts exist that are not reflected in the corresponding question ({q_sc})."
            )
        else:
            notas.append(
                f"A operação indica staking/rendimento ({q_staking}). Confirme se existem smart contracts próprios ou "
                f"white-label on-chain não refletidos na pergunta correspondente ({q_sc})."
            )

    if track == "corretora":
        notas.extend(_journey_2_corretora_e_notas(answers, lang=lang))
    elif track == "custodiante":
        notas.extend(_journey_2_custodiante_e_notas(answers, lang=lang))
    elif track == "intermediaria":
        notas.extend(_journey_2_intermediaria_e_notas(answers, lang=lang))

    if en:
        sc_acao = (
            f"Share the Git repository URL (read access) for the smart contracts in scope **or** invite the GitHub user "
            f"**{gh_user}** to the private repository with the appropriate permission for audit."
        )
    else:
        sc_acao = (
            f"Enviar o URL do repositório Git (leitura) dos smart contracts em scope **ou** convidar o utilizador "
            f"GitHub **{gh_user}** ao repositório privado com permissão adequada para auditoria."
        )

    sc_block: dict[str, Any] = {
        "aplicavel": p_sc,
        "github_username_convite": gh_user,
        "acao_cliente": sc_acao,
    }

    if p_surf:
        if en:
            pentest_instr = (
                f"Fill in the penetration test scoping form: {pentest_url}"
                if pentest_url
                else "Fill in the pentest form that the CertiK team will send you (URL not configured on the server — set CERTIK_PENTEST_FORM_URL)."
            )
        else:
            pentest_instr = (
                f"Preencher o formulário de scoping de penetration test: {pentest_url}"
                if pentest_url
                else "Preencher o formulário de pentest que a equipa CertiK lhe enviar (URL não configurado no servidor — defina CERTIK_PENTEST_FORM_URL)."
            )
    else:
        if en:
            pentest_instr = (
                "You indicated that the institution does not operate its own internet-facing surfaces (website/app/API/panel). "
                "Confirm with the CertiK analyst before excluding pentest from the programme."
            )
        else:
            pentest_instr = (
                "Indicou que não opera superfícies expostas próprias (site/app/API/painel). "
                "Confirme com o analista CertiK antes de excluir pentest do programa."
            )

    pentest_block: dict[str, Any] = {
        "aplicavel": p_surf,
        "formulario_url": pentest_url if p_surf else "",
        "acao_cliente": pentest_instr,
    }

    incisos_data = data.get("incisos")
    if not isinstance(incisos_data, dict):
        incisos_data = {}

    active_keys: set[str] = set(meta_scope.get("active_keys") or [])
    inc_matrix = build_incisos_matrix(track)
    checklist: list[dict[str, Any]] = []
    total_pedidos = 0

    for key in sort_scope_keys(active_keys, track):
        raw_items = incisos_data.get(key)
        items: list[dict[str, Any]]
        if isinstance(raw_items, list) and raw_items:
            items = _enrich_pedidos([dict(x) for x in raw_items if isinstance(x, dict)], lang=lang)
        else:
            items = _enrich_pedidos(_fallback_pedidos_inciso(key, inc_matrix, lang=lang), lang=lang)
        checklist.append(
            {
                "inciso_id": key,
                "item_in701": inc_matrix.get(key, {}).get("item", key),
                "pedidos": items,
            }
        )
        total_pedidos += len(items)

    j2_label = "Journey 2 — evidence and technical services" if en else "Jornada 2 — evidências e serviços técnicos"

    return {
        "journey_2_schema_version": JOURNEY_2_SCHEMA_VERSION,
        "label": str(meta_yaml.get("journey_label") or j2_label),
        "smart_contract_audit": sc_block,
        "penetration_test": pentest_block,
        "notas_heuristica": notas,
        "checklist_por_inciso": checklist,
        "total_pedidos_documentacao": total_pedidos,
    }


def _fallback_pedidos_inciso(
    inciso_id: str, inc_matrix: dict[str, dict[str, str]], lang: str = "pt"
) -> list[dict[str, Any]]:
    rot = inc_matrix.get(inciso_id, {}).get("item", inciso_id)
    if lang == "en":
        return [
            {
                "id": f"ev_fallback_{inciso_id}_pol",
                "titulo": f"Applicable policies and procedures — {rot}",
                "detalhe": "Approved version, effective date, control owner and recent execution evidence (redacted sample).",
                "categoria": "politica",
            },
            {
                "id": f"ev_fallback_{inciso_id}_ev",
                "titulo": f"Supporting artefacts for clause — {rot}",
                "detalhe": "Technical documentation or internal reports demonstrating implementation (without unnecessary sensitive data).",
                "categoria": "evidencia",
            },
        ]
    return [
        {
            "id": f"ev_fallback_{inciso_id}_pol",
            "titulo": f"Política e procedimentos aplicáveis — {rot}",
            "detalhe": "Versão aprovada, vigência, dono do controle e evidência de execução recente (amostra redigida).",
            "categoria": "politica",
        },
        {
            "id": f"ev_fallback_{inciso_id}_ev",
            "titulo": f"Artefactos de suporte ao inciso — {rot}",
            "detalhe": "Documentação técnica ou relatórios internos que demonstrem implementação (sem dados sensíveis desnecessários).",
            "categoria": "evidencia",
        },
    ]


__all__ = [
    "CRITERIOS_DOCUMENTO_OTIMO",
    "EVIDENCE_PATH",
    "JOURNEY_2_SCHEMA_VERSION",
    "build_journey_2_payload",
    "evidence_inciso_keys_declared",
    "missing_evidence_yaml_incisos",
]
