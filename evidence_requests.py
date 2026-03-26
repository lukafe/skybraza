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


def _journey_2_corretora_e_notas(answers: dict[str, Any]) -> list[str]:
    """Notas adicionais quando o questionário E (corretora) sinaliza intermediação ou produtos sensíveis."""
    out: list[str] = []
    if answers.get("corr_E_margin_product"):
        out.append(
            "Indicou produto de margem/alavancagem (corr_E_margin_product). Validar enquadramento na Res. 520 art. 72 "
            "(elegibilidade da instituição) e compatibilidade com vedações do art. 12 — cruzar com jurídico/compliance "
            "antes do relatório ao BCB."
        )
    if answers.get("corr_E_liquidity_provider_contract"):
        out.append(
            "Contrato com provedor de liquidez (corr_E_liquidity_provider_contract). Reunir cláusulas mínimas do "
            "art. 38 Res. 520 (modelo de negócio, liquidação, transferência segura de custódia) para pasta de evidências."
        )
    if answers.get("corr_E_market_maker_contract"):
        out.append(
            "Formador de mercado contratado (corr_E_market_maker_contract). Documentar parâmetros contratuais do "
            "art. 39 Res. 520 e equidade face a outros participantes."
        )
    if answers.get("corr_E_rfq_offering"):
        out.append(
            "RFQ / request for quote ativo (corr_E_rfq_offering). Confirmar disclosure ao cliente conforme Res. 520 "
            "art. 67, §6º (cotações, prazos, contraparte, riscos)."
        )
    if answers.get("corr_E_conflict_units"):
        out.append(
            "Assinalou separação mesa vs custódia (corr_E_conflict_units). Incluir na evidência organograma/política "
            "referenciando Res. 520 art. 85 e inciso X (a) IN 701."
        )
    return out


def _journey_2_custodiante_e_notas(answers: dict[str, Any]) -> list[str]:
    """Notas quando o questionário E (custodiante) sinaliza programas de custódia ou supervisão reforçada."""
    out: list[str] = []
    if answers.get("cust_E_treasury_split"):
        out.append(
            "Assinalou segregação documentada AV próprios vs clientes (cust_E_treasury_split). Juntar política "
            "e organograma referenciando Res. 520 arts. 29–31 e incisos I (a), XV IN 701."
        )
    if answers.get("cust_E_subcustody_art74"):
        out.append(
            "Programa de subcustódia ativo (cust_E_subcustody_art74). Garantir evidências de monitoramento "
            "contínuo e de comunicação tempestiva ao BCB em caso de descumprimento (Res. 520 art. 74, VI)."
        )
    if answers.get("cust_E_stress_art82"):
        out.append(
            "Testes de stress realizados (cust_E_stress_art82). Arquivar método e resultados pelo prazo legal "
            "para supervisão (Res. 520 art. 82, §2º)."
        )
    if answers.get("cust_E_staking_bcb_notice"):
        out.append(
            "Indicou cumprimento de comunicação prévia ao BCB sobre oferta de staking (cust_E_staking_bcb_notice). "
            "Confirmar data e protocolo face ao art. 82, §5º da Res. 520."
        )
    return out


def _journey_2_intermediaria_e_notas(answers: dict[str, Any]) -> list[str]:
    """Notas quando o bloco E (intermediária) sinaliza intermediação regulada ou produtos de mercado."""
    out: list[str] = []
    if answers.get("int_E_art69_controls"):
        out.append(
            "Assinalou controles de conflito art. 69 (int_E_art69_controls). Juntar política aprovada e evidências de "
            "monitoramento independente ao dossiê — inciso X (a) IN 701."
        )
    if answers.get("int_E_lp_art38"):
        out.append(
            "Contrato com provedor de liquidez (int_E_lp_art38). Reunir cláusulas mínimas do art. 38 Res. 520 "
            "(modelo de negócio, liquidação, custódia)."
        )
    if answers.get("int_E_mm_art39"):
        out.append(
            "Formador de mercado contratado (int_E_mm_art39). Documentar parâmetros do art. 39 Res. 520 e equidade "
            "entre participantes."
        )
    if answers.get("int_E_rfq_art67"):
        out.append(
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


def _documento_otimo_text(pedido: dict[str, Any]) -> str:
    custom = str(pedido.get("documento_otimo") or "").strip()
    if custom:
        return " ".join(custom.split())
    cat = str(pedido.get("categoria") or "").strip().lower() or "_default"
    base = CRITERIOS_DOCUMENTO_OTIMO.get(cat) or CRITERIOS_DOCUMENTO_OTIMO["_default"]
    tit = str(pedido.get("titulo") or "").strip()
    if tit:
        return f'Para «{tit}», um documento exemplar costuma incluir: {base}'
    return f"Um documento exemplar costuma incluir: {base}"


def _enrich_pedidos(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw in items:
        p = dict(raw)
        p["documento_otimo"] = _documento_otimo_text(p)
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


def build_journey_2_payload(answers: dict[str, Any], meta_scope: dict[str, Any]) -> dict[str, Any]:
    """
    ``answers`` deve estar normalizado (ex.: output de ``normalize_answers``).
    ``meta_scope`` deve conter pelo menos ``active_keys`` (set de ids de inciso).
    """
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
        notas.append(
            f"A operação indica staking/rendimento ({q_staking}). Confirme se existem smart contracts próprios ou "
            f"white-label on-chain não refletidos na pergunta correspondente ({q_sc})."
        )

    if track == "corretora":
        notas.extend(_journey_2_corretora_e_notas(answers))
    elif track == "custodiante":
        notas.extend(_journey_2_custodiante_e_notas(answers))
    elif track == "intermediaria":
        notas.extend(_journey_2_intermediaria_e_notas(answers))

    sc_block: dict[str, Any] = {
        "aplicavel": p_sc,
        "github_username_convite": gh_user,
        "acao_cliente": (
            f"Enviar o URL do repositório Git (leitura) dos smart contracts em scope **ou** convidar o utilizador "
            f"GitHub **{gh_user}** ao repositório privado com permissão adequada para auditoria."
        ),
    }

    if p_surf:
        pentest_instr = (
            f"Preencher o formulário de scoping de penetration test: {pentest_url}"
            if pentest_url
            else "Preencher o formulário de pentest que a equipa CertiK lhe enviar (URL não configurado no servidor — defina CERTIK_PENTEST_FORM_URL)."
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
            items = _enrich_pedidos([dict(x) for x in raw_items if isinstance(x, dict)])
        else:
            items = _enrich_pedidos(_fallback_pedidos_inciso(key, inc_matrix))
        checklist.append(
            {
                "inciso_id": key,
                "item_in701": inc_matrix.get(key, {}).get("item", key),
                "pedidos": items,
            }
        )
        total_pedidos += len(items)

    return {
        "journey_2_schema_version": JOURNEY_2_SCHEMA_VERSION,
        "label": str(meta_yaml.get("journey_label") or "Jornada 2 — evidências e serviços técnicos"),
        "smart_contract_audit": sc_block,
        "penetration_test": pentest_block,
        "notas_heuristica": notas,
        "checklist_por_inciso": checklist,
        "total_pedidos_documentacao": total_pedidos,
    }


def _fallback_pedidos_inciso(inciso_id: str, inc_matrix: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    rot = inc_matrix.get(inciso_id, {}).get("item", inciso_id)
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
