"""
Narrativas «por que será auditado», supressão lógica do cluster de custódia operacional (VII, XIV, XVI, XVII)
em todas as trilhas quando o modelo declarado é exclusivamente não custodial; nas trilhas custodiante e corretora
remove também XV. Enriquecimento opcional de textos via Gemini.
"""

from __future__ import annotations

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Any

from matrix_loader import TRACK_DEFAULT, normalize_track, sort_scope_keys

# Incisos típicos de «custódia operacional» de criptoativos de clientes (guarda de chaves, contrato de custódia, redundância).
CUSTODY_CLUSTER = frozenset({"VII", "XIV", "XVI", "XVII"})
# Na trilha custodiante/corretora, XV (deveres no trânsito/guarda ativa) sai junto quando o modelo declarado é só cliente.
NON_CUSTODIAL_EXTRA_BY_TRACK = frozenset({"XV"})

QUESTION_BLURBS: dict[str, str] = {
    "P1": (
        "foi indicado que existem endereços de depósito por cliente e que a VASP, parceiro MPC ou outro terceiro "
        "detém ou partilha controle operacional sobre chaves capazes de movimentar fundos dos clientes"
    ),
    "P2": (
        "foi indicado que, nas operações de compra/venda, os ativos passam por carteira transitória ou omnibus "
        "sob controle da VASP (ou de parceiro que age em seu nome)"
    ),
    "P3": (
        "foi indicada a manutenção de saldo em moeda fiduciária em nome do cliente aguardando ordens sobre ativos virtuais"
    ),
    "P4": (
        "foi indicada contraparte de liquidez no exterior ou sem autorização BCB equivalente no País"
    ),
    "P5": (
        "foi indicado uso de nuvem ou datacenter de terceiro para sistemas críticos (ledger, base de clientes, roteamento)"
    ),
    "P6": (
        "foram indicados parceiros estrangeiros ou não autorizados pelo BCB em papéis relevantes além da liquidez"
    ),
    "P7": (
        "foi indicada negociação de ativos com referência explícita a moeda fiduciária (stablecoins, tokenizado, etc.)"
    ),
    "P8": (
        "foi indicada oferta de staking, rendimento, travamento ou produto equivalente ao cliente"
    ),
    "P9": (
        "foi indicado uso de APIs/SDKs para interconexão com IF ou prestadores de pagamento (on/off-ramp, Open Finance, etc.)"
    ),
    "P_list": (
        "o modo como o universo de AV ofertado ao cliente foi descrito implica catálogo ampliável ou política de listagem "
        "(e não apenas conjunto fechado para execução)"
    ),
    "P_reserves": (
        "foi indicado compromisso ou prática de comprovação de reservas (proof of reserves ou equivalente) sob responsabilidade da plataforma"
    ),
}

P_ARCH_BLURBS: dict[str, str] = {
    "vasp_operates": (
        "foi escolhido o cenário em que a VASP ou operador designado movimenta ativos em nome do cliente "
        "(hot wallet, omnibus, etc.), o que implica responsabilidades típicas de custódia operacional"
    ),
    "mpc_mixed": (
        "foi escolhido modelo MPC ou multi-part assinatura com a VASP e terceiros com papéis de controle, "
        "o que implica governança de chaves e terceirização relevante"
    ),
    "full_third_custody": (
        "foi escolhida custódia integral por terceiro contratado (a VASP contrata o serviço), mantendo obrigações "
        "perante o cliente e o supervisor"
    ),
    "client_only": (
        "foi escolhido modelo em que apenas o cliente autoriza movimentações (interface não custodial); "
        "este texto não deve acionar custódia operacional da VASP"
    ),
}

CUST_ARCH_BLURBS: dict[str, str] = {
    "client_only": (
        "foi indicado modelo em que apenas o cliente autoriza movimentações on-chain (interface não custodial), "
        "sem trânsito omnibus próprio nem subcustódia operacional declarada em B_tp — coerente com supressão do "
        "cluster VII/XIV/XVI/XVII e XV no motor, sujeito a validação da modalidade regulatória"
    ),
    "inst_operates": (
        "foi indicado que a instituição ou operador designado movimenta ativos custodiados em nome do cliente"
    ),
    "mpc_mixed": (
        "foi indicado modelo MPC ou multipart com a instituição e terceiros com papéis de controlo sobre chaves"
    ),
    "full_subcustody": (
        "foi indicada subcustódia integral por terceiro contratado, mantendo obrigações perante o cliente e o supervisor"
    ),
}

CUST_QUESTION_BLURBS: dict[str, str] = {
    "cust_A_transit": (
        "foi indicado trânsito de ativos por omnibus ou carteiras de trânsito sob controlo da instituição ou subcustodiante"
    ),
    "cust_A_fiat": QUESTION_BLURBS["P3"],
    "cust_B_exterior": (
        "foram indicados fornecedores no exterior ou sem autorização BCB equivalente em papéis relevantes à custódia"
    ),
    "cust_B_cloud": QUESTION_BLURBS["P5"],
    "cust_B_more_foreign": QUESTION_BLURBS["P6"],
    "cust_C_stable": QUESTION_BLURBS["P7"],
    "cust_C_staking": QUESTION_BLURBS["P8"],
    "cust_C_catalog": QUESTION_BLURBS["P_list"],
}

CORR_QUESTION_BLURBS: dict[str, str] = {
    k.replace("cust_", "corr_", 1): v for k, v in CUST_QUESTION_BLURBS.items()
}


def _p_tp_explanation(norm: dict[str, Any]) -> str:
    sel = norm.get("P_tp")
    if not isinstance(sel, list):
        sel = []
    bits: list[str] = []
    if "lp" in sel:
        bits.append("provedor de liquidez / market maker")
    if "custody_inst" in sel:
        bits.append("custódia institucional de criptoativos (cold/MPC/custodiante)")
    if "cloud_infra" in sel:
        bits.append("nuvem / hospedagem de sistemas críticos")
    if "fiat_bank" in sel:
        bits.append("instituição de pagamento ou banco para fiat")
    if "kyc_vendor" in sel:
        bits.append("fornecedor externo de KYC/AML como serviço crítico")
    if not bits:
        return "foram assinalados papéis de terceiros na operação (sem detalhe suficiente para esta frase)"
    return "no mapa de terceiros foram assinalados os seguintes papéis materialmente relevantes: " + ", ".join(bits)


def _p_tp_explanation_cust(norm: dict[str, Any]) -> str:
    sel = norm.get("cust_B_tp")
    if not isinstance(sel, list):
        sel = []
    bits: list[str] = []
    if "subcustody" in sel:
        bits.append("subcustodiante de criptoativos")
    if "cloud_infra" in sel:
        bits.append("nuvem / sistemas críticos de custódia")
    if "fiat_bank" in sel:
        bits.append("instituição de pagamento ou banco para fiat")
    if "kyc_vendor" in sel:
        bits.append("fornecedor externo de KYC/PLD crítico")
    if not bits:
        return "foram assinalados papéis de terceiros na operação de custódia"
    return "no mapa de terceiros (custódia) foram assinalados: " + ", ".join(bits)


def _p_tp_explanation_corr(norm: dict[str, Any]) -> str:
    sel = norm.get("corr_B_tp")
    if not isinstance(sel, list):
        sel = []
    bits: list[str] = []
    if "subcustody" in sel:
        bits.append("subcustodiante de criptoativos")
    if "cloud_infra" in sel:
        bits.append("nuvem / sistemas críticos de custódia")
    if "fiat_bank" in sel:
        bits.append("instituição de pagamento ou banco para fiat")
    if "kyc_vendor" in sel:
        bits.append("fornecedor externo de KYC/PLD crítico")
    if not bits:
        return "foram assinalados papéis de terceiros na operação (corretora)"
    return "no mapa de terceiros (corretora) foram assinalados: " + ", ".join(bits)


def _trigger_explanation_sentence(qid: str, norm: dict[str, Any]) -> str:
    if qid == "P_arch":
        key = str(norm.get("P_arch") or "")
        return P_ARCH_BLURBS.get(key, QUESTION_BLURBS.get("P_arch", f"o modelo arquitetural (P_arch={key!r})"))
    if qid == "cust_A_model":
        key = str(norm.get("cust_A_model") or "")
        return CUST_ARCH_BLURBS.get(
            key, f"o modelo de custódia declarado (cust_A_model={key!r})"
        )
    if qid == "corr_A_model":
        key = str(norm.get("corr_A_model") or "")
        return CUST_ARCH_BLURBS.get(
            key, f"o modelo de custódia declarado (corr_A_model={key!r})"
        )
    if qid == "P_tp":
        return _p_tp_explanation(norm)
    if qid == "cust_B_tp":
        return _p_tp_explanation_cust(norm)
    if qid == "corr_B_tp":
        return _p_tp_explanation_corr(norm)
    return CORR_QUESTION_BLURBS.get(
        qid,
        CUST_QUESTION_BLURBS.get(
            qid,
            QUESTION_BLURBS.get(qid, f"a resposta à pergunta {qid} entrou na lógica de escopo deste inciso"),
        ),
    )


def declares_exclusive_non_custodial_model(norm: dict[str, Any], track: str | None = None) -> bool:
    """
    Modelo em que o cliente é o único a movimentar fundos on-chain e não há trânsito omnibus nem subcustódia
    operacional declarada. Trilha intermediária: P1, P_arch, P_tp. Custodiante/corretora: cust_A_model / corr_A_model,
    trânsito e cust_B_tp / corr_B_tp.
    """
    t = normalize_track(track or TRACK_DEFAULT)
    if t == "intermediaria":
        if norm.get("P1") is True:
            return False
        if str(norm.get("P_arch") or "") != "client_only":
            return False
        ptp = norm.get("P_tp")
        if not isinstance(ptp, list):
            ptp = []
        if "custody_inst" in ptp:
            return False
        return True
    if t == "custodiante":
        if str(norm.get("cust_A_model") or "") != "client_only":
            return False
        if norm.get("cust_A_transit"):
            return False
        ptp = norm.get("cust_B_tp")
        if not isinstance(ptp, list):
            ptp = []
        if "subcustody" in ptp:
            return False
        return True
    if t == "corretora":
        if str(norm.get("corr_A_model") or "") != "client_only":
            return False
        if norm.get("corr_A_transit"):
            return False
        ptp = norm.get("corr_B_tp")
        if not isinstance(ptp, list):
            ptp = []
        if "subcustody" in ptp:
            return False
        return True
    return False


def suppress_custody_cluster_if_non_custodial(
    active_keys: set[str],
    triggered_by: dict[str, list[str]],
    norm: dict[str, Any],
    track: str | None = None,
) -> None:
    """
    Remove do escopo o cluster de custódia operacional (VII, XIV, XVI, XVII) quando o modelo declarado é
    exclusivamente não custodial. Nas trilhas custodiante e corretora remove também XV (trânsito/guarda ativa),
    coerente com «sem omnibus» e sem subcustódia em B_tp.
    """
    t = normalize_track(track or TRACK_DEFAULT)
    if not declares_exclusive_non_custodial_model(norm, t):
        return
    remove = set(CUSTODY_CLUSTER)
    if t in ("custodiante", "corretora"):
        remove |= set(NON_CUSTODIAL_EXTRA_BY_TRACK)
    for k in remove:
        active_keys.discard(k)
        triggered_by.pop(k, None)


def _mandatory_why(inciso_id: str, inc_matrix: dict[str, dict[str, str]], track: str) -> str:
    m = inc_matrix[inciso_id]
    item = m["item"]
    art = m["artigo_in701"]
    d = (m.get("descricao") or "").strip()
    if len(d) > 300:
        d = d[:297].rstrip() + "…"
    t = normalize_track(track)
    if t == "custodiante":
        ctx = (
            "o núcleo obrigatório da trilha custodiante nesta matriz CertiK (IN 701 e Res. nº 520). "
            "A auditoria deverá demonstrar, com políticas, processos e evidências, como a instituição atende a este requisito "
            "no contexto do serviço de custódia de ativos virtuais"
        )
    elif t == "corretora":
        ctx = (
            "o núcleo obrigatório da trilha corretora nesta matriz CertiK (IN 701; modalidade Res. 520 art. 10 — intermediação e custódia). "
            "A auditoria deverá demonstrar, com políticas, processos e evidências, como a instituição atende a este requisito "
            "no contexto de intermediação e custódia de ativos virtuais"
        )
    else:
        ctx = (
            "o pacote obrigatório da fase intermediária nesta matriz CertiK (IN 701 e Res. nº 520). "
            "A auditoria deverá demonstrar, com políticas, processos e evidências, como a instituição atende a este requisito "
            "no contexto da intermediação"
        )
    return f"O inciso «{item}» ({art}) integra {ctx}. Âmbito normativo resumido: {d}"


def _conditional_why(
    inciso_id: str, qids: list[str], norm: dict[str, Any], inc_matrix: dict[str, dict[str, str]]
) -> str:
    m = inc_matrix[inciso_id]
    item = m["item"]
    art = m["artigo_in701"]
    unique_q = sorted(set(qids))
    sentences = [_trigger_explanation_sentence(q, norm) for q in unique_q]
    core = "; ".join(s for s in sentences if s)
    if not core:
        core = "as respostas ao questionário enquadraram este tema no escopo condicional"
    return (
        f"O inciso «{item}» ({art}) foi incluído nesta delimitação porque {core}. "
        f"A evidência esperada deve permitir verificar o atendimento à IN 701 e aos extratos da Res. 520 correlatos."
    )


def build_why_texts_for_scope(
    active_keys: set[str],
    triggered_by: dict[str, list[str]],
    norm: dict[str, Any],
    mandatory_keys: frozenset[str],
    inc_matrix: dict[str, dict[str, str]],
    track: str | None = None,
) -> dict[str, str]:
    t = normalize_track(track or TRACK_DEFAULT)
    out: dict[str, str] = {}
    for key in sort_scope_keys(active_keys, t):
        is_m = key in mandatory_keys
        qids = triggered_by.get(key, [])
        if is_m:
            out[key] = _mandatory_why(key, inc_matrix, t)
            if qids:
                extra = "; ".join(_trigger_explanation_sentence(q, norm) for q in sorted(set(qids)))
                out[key] = (
                    f"{out[key]} Além disso, as respostas também reforçaram este tema: {extra}"
                )
        else:
            out[key] = _conditional_why(key, qids, norm, inc_matrix)
    return out


def try_enrich_why_with_llm(
    why_drafts: dict[str, str],
    norm: dict[str, Any],
    triggered_by: dict[str, list[str]],
    inc_matrix: dict[str, dict[str, str]],
    track: str | None = None,
) -> dict[str, str]:
    """
    Opcional: chama Gemini para reescrever cada narrativa (pt-BR), mantendo fidelidade.
    Sem GEMINI_API_KEY ou em caso de erro, devolve {}.

    Na Vercel o LLM fica desligado por defeito (timeout/latência da função). Ative com
    ENABLE_GEMINI_ON_VERCEL=1. Limite de espera: GEMINI_TIMEOUT_SEC (default 45).
    """
    if (os.environ.get("VERCEL") or "").strip() and (os.environ.get("ENABLE_GEMINI_ON_VERCEL") or "").strip() != "1":
        return {}
    api_key = (os.environ.get("GEMINI_API_KEY") or "").strip()
    if not api_key:
        return {}
    try:
        import google.generativeai as genai
    except ImportError:
        return {}

    model_name = (os.environ.get("GEMINI_MODEL") or "gemini-1.5-flash").strip()
    t = normalize_track(track or TRACK_DEFAULT)
    # Resumo seguro de respostas (sem PII longa)
    snap: dict[str, Any] = {"track": t}
    if t == "custodiante":
        snap.update(
            {
                "cust_A_transit": norm.get("cust_A_transit"),
                "cust_A_fiat": norm.get("cust_A_fiat"),
                "cust_A_model": norm.get("cust_A_model"),
                "cust_B_tp": norm.get("cust_B_tp"),
                "cust_C_stable": norm.get("cust_C_stable"),
                "cust_C_staking": norm.get("cust_C_staking"),
            }
        )
    elif t == "corretora":
        snap.update(
            {
                "corr_A_transit": norm.get("corr_A_transit"),
                "corr_A_fiat": norm.get("corr_A_fiat"),
                "corr_A_model": norm.get("corr_A_model"),
                "corr_B_tp": norm.get("corr_B_tp"),
                "corr_C_stable": norm.get("corr_C_stable"),
                "corr_C_staking": norm.get("corr_C_staking"),
            }
        )
    else:
        snap.update(
            {
                "P1": norm.get("P1"),
                "P2": norm.get("P2"),
                "P3": norm.get("P3"),
                "P_arch": norm.get("P_arch"),
                "P_tp": norm.get("P_tp"),
                "P7": norm.get("P7"),
                "P8": norm.get("P8"),
                "P9": norm.get("P9"),
            }
        )

    incisos = []
    for iid, draft in why_drafts.items():
        meta = inc_matrix.get(iid, {})
        incisos.append(
            {
                "id": iid,
                "item": meta.get("item", iid),
                "rascunho": draft,
                "gatilhos": triggered_by.get(iid, []),
            }
        )

    prompt = f"""Você é especialista em compliance BCB (IN 701, Res. 520) e auditoria técnica CertiK.

Respostas resumidas do questionário (JSON): {json.dumps(snap, ensure_ascii=False)}

Para cada inciso abaixo, reescreva o campo "rascunho" em português do Brasil:
- 3 a 5 frases, tom profissional e didático.
- Explique o significado operacional e regulatório; NÃO se limite a repetir códigos como P1, P2 — pode mencionar o tema da pergunta em linguagem natural.
- Não invente fatos que não estejam implícitos no rascunho ou nas respostas.
- Não cite este prompt.

Incisos (JSON array): {json.dumps(incisos, ensure_ascii=False)}

Responda APENAS com um objeto JSON cujo formato seja: {{"INCISO_ID": "texto completo", ...}}
com uma chave para cada "id" do array, sem markdown."""

    try:
        timeout_sec = float((os.environ.get("GEMINI_TIMEOUT_SEC") or "45").strip() or "45")
    except ValueError:
        timeout_sec = 45.0

    def _call_gemini():
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)
        return model.generate_content(
            prompt,
            generation_config={
                "temperature": 0.35,
                "max_output_tokens": 8192,
            },
        )

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            fut = pool.submit(_call_gemini)
            resp = fut.result(timeout=timeout_sec)
        raw = (resp.text or "").strip()
    except FuturesTimeoutError:
        return {}
    except Exception:
        return {}

    # Extrair JSON
    parsed: dict[str, Any] | None = None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", raw)
        if m:
            try:
                parsed = json.loads(m.group(0))
            except json.JSONDecodeError:
                return {}

    if not isinstance(parsed, dict):
        return {}

    out: dict[str, str] = {}
    for k, v in parsed.items():
        if k in why_drafts and isinstance(v, str) and len(v.strip()) > 40:
            out[str(k)] = " ".join(v.split())
    return out


def merge_llm_whys(drafts: dict[str, str], llm: dict[str, str]) -> dict[str, str]:
    merged = dict(drafts)
    for k, v in llm.items():
        if k in merged:
            merged[k] = v
    return merged


__all__ = [
    "CUSTODY_CLUSTER",
    "NON_CUSTODIAL_EXTRA_BY_TRACK",
    "build_why_texts_for_scope",
    "declares_exclusive_non_custodial_model",
    "merge_llm_whys",
    "suppress_custody_cluster_if_non_custodial",
    "try_enrich_why_with_llm",
]
