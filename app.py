"""
CertiK — Ferramenta de Scoping IN 701 (trilhas intermediária e custodiante) / BCB Res. 520.

UI Streamlit (este ficheiro): mesmo motor que a SPA em public/ + API FastAPI (main.py).
Trilha custodiante pode ser ocultada com CERTIK_ENABLE_CUSTODIANTE_TRACK=0 (alinhado à API).
"""

from __future__ import annotations

import hashlib
import os

import pandas as pd
import streamlit as st

from questionnaire_loader import get_blocks, get_questions
from rules_engine import compute_scope, questions_by_block

# Opcional: chave via variável de ambiente (não commitar segredos no código)
DEFAULT_GEMINI_ENV = "GEMINI_API_KEY"


def _custodiante_ui_enabled() -> bool:
    v = (os.environ.get("CERTIK_ENABLE_CUSTODIANTE_TRACK") or "").strip().lower()
    return v not in ("0", "false", "no", "off")


def _current_questions() -> list[dict]:
    tr = st.session_state.get("scope_track", "intermediaria")
    return get_questions(tr)


def _j2_pedido_widget_key(inciso_id: str, pedido_id: str) -> str:
    h = hashlib.sha256(f"{inciso_id}:{pedido_id}".encode()).hexdigest()[:22]
    return f"j2_ped_{h}"


def _default_answer_for_q(q: dict) -> bool | str | list | None:
    t = q.get("type")
    if t == "yes_no":
        return False
    if t == "single_choice":
        return None
    if t == "multi_choice":
        return []
    if t == "text_short":
        return ""
    return False


def _ensure_answer_shape() -> None:
    """Completa chaves novas do questionário (sessões antigas da fase B)."""
    qs = _current_questions()
    full = {q["id"]: _default_answer_for_q(q) for q in qs}
    for k, v in full.items():
        if k not in st.session_state.answers:
            st.session_state.answers[k] = v
    for dead in list(st.session_state.answers.keys()):
        if dead not in full:
            del st.session_state.answers[dead]


def _prime_question_widgets(qs: list[dict] | None = None) -> None:
    """Garante chaves de widget alinhadas a `answers` (evita conflito value/key no Streamlit)."""
    qs = qs or _current_questions()
    for q in qs:
        qid = q["id"]
        t = q.get("type")
        a = st.session_state.answers.get(qid)
        if t == "yes_no":
            k = f"q_{qid}"
            if k not in st.session_state:
                st.session_state[k] = "Sim" if a else "Não"
        elif t == "single_choice":
            k = f"q_{qid}_single"
            if k not in st.session_state:
                st.session_state[k] = a if isinstance(a, str) and a else ""
        elif t == "multi_choice":
            k = f"q_{qid}_multi"
            if k not in st.session_state:
                st.session_state[k] = list(a) if isinstance(a, list) else []
        elif t == "text_short":
            k = f"q_{qid}_text"
            if k not in st.session_state:
                st.session_state[k] = str(a or "")


def _init_session() -> None:
    if "scope_track" not in st.session_state:
        st.session_state.scope_track = "intermediaria"
    qs0 = get_questions(st.session_state.scope_track)
    if "answers" not in st.session_state:
        st.session_state.answers = {q["id"]: _default_answer_for_q(q) for q in qs0}
        _prime_question_widgets(qs0)
    if "scope_computed" not in st.session_state:
        st.session_state.scope_computed = False
    if "scope_df" not in st.session_state:
        st.session_state.scope_df = pd.DataFrame()
    if "scope_meta" not in st.session_state:
        st.session_state.scope_meta = {}
    if "gemini_cache" not in st.session_state:
        st.session_state.gemini_cache = ""
    if "gemini_last_key" not in st.session_state:
        st.session_state.gemini_last_key = ""
    if "vasp_name" not in st.session_state:
        st.session_state.vasp_name = ""


def _certik_css() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
        html, body, [class*="css"]  {
            font-family: 'Inter', 'Segoe UI', sans-serif;
        }
        .block-container { padding-top: 1.35rem; max-width: 1180px; }
        h1 { letter-spacing: -0.03em; color: #f4f4f5 !important; }
        .certik-badge {
            display: inline-block;
            padding: 0.28rem 0.7rem;
            border-radius: 999px;
            background: linear-gradient(135deg, rgba(255,59,71,0.14), rgba(255,59,71,0.06));
            border: 1px solid rgba(255,59,71,0.4);
            color: #ff6b6b;
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            margin-bottom: 0.55rem;
        }
        div[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0c0c0e 0%, #050506 100%);
            border-right: 1px solid #2a2a30;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _radio_to_bool(val: str) -> bool:
    return val == "Sim"


def _build_answers_from_ui() -> dict:
    out: dict = {}
    for q in _current_questions():
        qid = q["id"]
        t = q.get("type")
        if t == "yes_no":
            wid = f"q_{qid}"
            if wid in st.session_state:
                out[qid] = _radio_to_bool(st.session_state[wid])
            else:
                out[qid] = bool(st.session_state.answers.get(qid, False))
        elif t == "single_choice":
            k = f"q_{qid}_single"
            raw = st.session_state.get(k, st.session_state.answers.get(qid))
            if raw is None or raw == "":
                out[qid] = None
            else:
                out[qid] = str(raw)
        elif t == "multi_choice":
            k = f"q_{qid}_multi"
            out[qid] = list(st.session_state.get(k, st.session_state.answers.get(qid) or []))
        elif t == "text_short":
            k = f"q_{qid}_text"
            out[qid] = str(st.session_state.get(k, st.session_state.answers.get(qid) or ""))
        else:
            out[qid] = st.session_state.answers.get(qid)
    return out


def _question_answered_for_summary(qid: str, norm: dict, free_text: dict) -> bool:
    v = norm.get(qid)
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return bool(v.strip())
    if isinstance(v, list):
        return len(v) > 0
    if qid in free_text and (free_text.get(qid) or "").strip():
        return True
    return False


def _style_scope_df(df: pd.DataFrame) -> pd.io.formats.style.Styler:
    def color_origem(val: str) -> str:
        s = str(val)
        if "Obrigatório" in s:
            return "color: #2EE6B6; font-weight: 600;"
        if "Acionado" in s:
            return "color: #5C9DFF; font-weight: 600;"
        return ""

    if "Origem no escopo" in df.columns:
        styler = df.style.map(color_origem, subset=["Origem no escopo"])
    else:
        styler = df.style
    return styler.set_properties(**{"background-color": "#0c0e14", "color": "#EEF1F6"})


def _resumo_text(vasp_name: str, meta: dict, df: pd.DataFrame) -> str:
    lines: list[str] = []
    tr = str(meta.get("track") or "intermediaria")
    free_t = meta.get("free_text") or {}
    lines.append(f"**Instituição:** {vasp_name or '(não informado)'}")
    lines.append("")
    if tr == "custodiante":
        lines.append("### Núcleo obrigatório (trilha custodiante)")
        lines.append(
            "- Obrigatórios na matriz da trilha: segregação e guarda (I_a, I_b, VII–XVII), traves PLD/ciber/risco/práticas "
            "(VI, VIII, X–XIII, §1º I–III), terceirização e continuidade (II, IV) e governança (V). "
            "Condicionais: ver `laws/tracks/custodiante/COVERAGE_MATRIX.yaml` e respostas ao questionário."
        )
    else:
        lines.append("### Itens sempre no escopo (IN 701 — intermediária)")
        lines.append(
            "- Obrigatórios na matriz YAML: VI (a)(b), VIII, X (a) e X (b)(i), XI, XII, XIII, "
            "§ 1º (I), (II) e (III); demais incisos conforme respostas (ver COVERAGE_MATRIX.yaml)."
        )
    lines.append("")
    lines.append("### Respostas relevantes por bloco")
    norm = meta.get("answers", {})
    blocks = get_blocks(tr)
    qs_meta = get_questions(tr)
    by_block: dict[str, list[str]] = {b["id"]: [] for b in blocks}
    for q in qs_meta:
        bid = str(q.get("block", "A"))
        if bid not in by_block:
            by_block[bid] = []
        if _question_answered_for_summary(q["id"], norm, free_t):
            txt = q.get("text") or ""
            snippet = (txt[:120] + "…") if len(txt) > 120 else txt
            by_block[bid].append(f"**{q['id']}**: {snippet}")

    block_titles = {str(b["id"]): (b.get("title") or b["id"]) for b in blocks}
    for b in blocks:
        bid = str(b["id"])
        title = block_titles.get(bid, bid)
        lines.append(f"- **Bloco {bid} — {title}**")
        if by_block.get(bid):
            for item in by_block[bid]:
                lines.append(f"  - {item}")
        else:
            lines.append("  - Nenhuma resposta preenchida ou “Sim” neste bloco.")

    lines.append("")
    lines.append("### Incisos condicionais incluídos (por pergunta)")
    tb = meta.get("triggered_by", {})
    if tb:
        for key in sorted(tb.keys()):
            qids = ", ".join(tb[key])
            lines.append(f"- `{key}` ← gatilho(s): {qids}")
    else:
        lines.append("- Nenhum gatilho condicional acionado (apenas itens obrigatórios).")

    lines.append("")
    lines.append("### Áreas de risco (síntese)")
    risks: list[str] = []
    if tr == "custodiante":
        if norm.get("cust_A_transit"):
            risks.append("Trânsito/omnibus e movimentação sob controlo da instituição (I_a, I_b, XV).")
        if norm.get("cust_A_fiat"):
            risks.append("Contas em moeda fiduciária ligadas à custódia (Art. 85 / X (b) (ii)).")
        if norm.get("cust_B_cloud") or norm.get("cust_B_exterior") or norm.get("cust_B_more_foreign"):
            risks.append("Terceiros, nuvem ou prestadores no exterior — diligência e continuidade.")
        if norm.get("cust_C_stable") or norm.get("cust_C_staking"):
            risks.append("Stablecoins, staking ou produtos com exposição ao cliente — transparência e riscos.")
        if norm.get("cust_C_if_api"):
            risks.append("Interconectividade com IFs e superfície de integração.")
        if (free_t.get("cust_D_narr") or "").strip():
            risks.append("Narrativa operacional — validar com evidências e terceiros.")
    else:
        if norm.get("P1") or norm.get("P2"):
            risks.append("Custódia, segregação patrimonial e trânsito de ativos.")
        if norm.get("P3"):
            risks.append("Recursos em BRL e limites/controles financeiros (Art. 85).")
        if norm.get("P4") or norm.get("P5") or norm.get("P6"):
            risks.append("Terceirização, nuvem e contrapartes no exterior ou não autorizadas.")
        if norm.get("P7"):
            risks.append("Stablecoins e critérios de seleção de ativos.")
        if norm.get("P8"):
            risks.append("Staking/rendimento e transparência ao cliente.")
        if norm.get("P9"):
            risks.append("APIs e interconectividade com IFs.")
        if norm.get("P_reserves"):
            risks.append("Compromisso ou evidência de reservas (prova de reservas / I (b)).")
        if (free_t.get("P_narr") or "").strip():
            risks.append("Fluxo narrado pelo cliente — confrontar com evidências de processo e terceiros.")
    if not risks:
        risks.append("Escopo mínimo obrigatório; revisar se respostas refletem a operação real.")
    for r in risks:
        lines.append(f"- {r}")

    cr = meta.get("corpus_readiness") or {}
    if cr:
        lines.append("")
        lines.append("### Prontidão do corpus (laws/) — Fase D")
        idx = cr.get("readiness_index_0_100", 0)
        cnt = cr.get("counts") or {}
        stubs = len(cr.get("stub_references") or [])
        lines.append(
            f"- Índice documental (0–100): **{idx}** — completo: {cnt.get('completo', 0)}, "
            f"parcial: {cnt.get('parcial', 0)}, incompleto: {cnt.get('incompleto', 0)}; referências STUB: **{stubs}**."
        )

    lines.append("")
    lines.append("### Duas categorias (esta delimitação)")
    lines.append(
        f"- **Sujeitos a auditoria:** {meta.get('total_count', 0)} incisos (ver Dashboard para detalhe e orientação ao BCB)."
    )
    lines.append(
        f"- **Fora do escopo de auditoria nesta configuração:** {meta.get('total_fora_escopo_auditoria', 0)} incisos "
        "(não obrigatórios fixos e sem gatilho pelas respostas atuais)."
    )

    lines.append("")
    lines.append("### Tabela resumida (sujeitos a auditoria)")
    if df is not None and not df.empty:
        lines.append(df.to_markdown(index=False))
    return "\n".join(lines)


def _run_gemini_analysis(
    api_key: str,
    vasp_name: str,
    p1: bool,
    p2: bool,
    custody_items: list[str],
    track: str = "intermediaria",
) -> str:
    try:
        import google.generativeai as genai
    except ImportError:
        return "Pacote `google-generativeai` não instalado. Execute: `pip install -r requirements.txt`."

    genai.configure(api_key=api_key.strip())
    model_name = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")
    model = genai.GenerativeModel(model_name)

    if track == "custodiante":
        track_label = "trilha custodiante (núcleo de guarda)"
        q1_label = "Trânsito/omnibus (cust_A_transit)"
        q2_label = "Contas fiat ligadas à custódia (cust_A_fiat)"
    else:
        track_label = "fase intermediária"
        q1_label = "P1 (controle de chaves / endereços / MPC)"
        q2_label = "P2 (trânsito por carteira omnibus/transitória)"

    prompt = f"""Você é auditor técnico da CertiK (blockchain / VASP / BCB).

Contexto: escopo IN 701, {track_label}, alinhado à Resolução BCB nº 520.

Instituição: {vasp_name or "Não informado"}

Respostas do questionário de custódia e trânsito:
- {q1_label}: {"Sim" if p1 else "Não"}
- {q2_label}: {"Sim" if p2 else "Não"}

Itens de escopo relacionados a custódia atualmente incluídos pelo motor de regras:
{", ".join(custody_items) if custody_items else "(nenhum além dos obrigatórios gerais)"}

Escreva em português do Brasil, 3 a 4 parágrafos curtos:
1) Por que a inclusão ou exclusão de incisos de custódia faz sentido técnico frente ao BCB, dadas as duas respostas acima.
2) Riscos residuais se a operação real divergir das respostas.
3) Sugestão objetiva de evidências a coletar na fase de auditoria.

Tom: profissional, direto, sem repetir a legislação verbatim.
"""
    resp = model.generate_content(prompt)
    return (resp.text or "").strip()


def main() -> None:
    _init_session()
    if st.session_state.scope_track == "custodiante" and not _custodiante_ui_enabled():
        st.session_state.scope_track = "intermediaria"
        qs_fix = get_questions("intermediaria")
        st.session_state.answers = {q["id"]: _default_answer_for_q(q) for q in qs_fix}
        _prime_question_widgets(qs_fix)
        st.session_state.scope_computed = False
        st.session_state.scope_df = pd.DataFrame()
        st.session_state.scope_meta = {}
        st.session_state.gemini_cache = ""
        st.session_state.gemini_last_key = ""
    _ensure_answer_shape()
    _prime_question_widgets()
    _certik_css()

    st.sidebar.markdown("### CertiK")

    opts = ["intermediaria"] + (["custodiante"] if _custodiante_ui_enabled() else [])
    if st.session_state.scope_track not in opts:
        st.session_state.scope_track = "intermediaria"
    ix = opts.index(st.session_state.scope_track)
    sel = st.sidebar.selectbox(
        "Trilha IN 701",
        opts,
        index=ix,
        format_func=lambda x: "Intermediário (tipos mistos)" if x == "intermediaria" else "Custodiante",
    )
    if sel != st.session_state.scope_track:
        st.session_state.scope_track = sel
        qs = get_questions(sel)
        st.session_state.answers = {q["id"]: _default_answer_for_q(q) for q in qs}
        _prime_question_widgets(qs)
        st.session_state.scope_computed = False
        st.session_state.scope_df = pd.DataFrame()
        st.session_state.scope_meta = {}
        st.session_state.gemini_cache = ""
        st.session_state.gemini_last_key = ""
        st.rerun()

    trk = st.session_state.scope_track
    st.sidebar.caption(
        "Scoping IN 701 · trilha custodiante" if trk == "custodiante" else "Scoping IN 701 · VASP intermediária"
    )

    secrets_key = ""
    try:
        secrets_key = st.secrets.get("GEMINI_API_KEY", "")  # type: ignore[attr-defined]
    except Exception:
        secrets_key = ""

    env_key = os.environ.get(DEFAULT_GEMINI_ENV, "")
    default_key_hint = (secrets_key or env_key or "").strip()

    if "gemini_key_input" not in st.session_state:
        st.session_state.gemini_key_input = default_key_hint

    vasp_name = st.sidebar.text_input("Nome da VASP / projeto", key="vasp_name")

    gemini_key = st.sidebar.text_input(
        "Gemini API Key (opcional)",
        type="password",
        key="gemini_key_input",
        help="Preferência: variável de ambiente GEMINI_API_KEY ou .streamlit/secrets.toml",
    )

    st.markdown('<span class="certik-badge">INTERNAL · AUDIT SCOPING</span>', unsafe_allow_html=True)
    st.title("Escopo IN 701 — VASP custodiante" if trk == "custodiante" else "Escopo IN 701 — VASP intermediária")
    st.caption("Questionário interativo · Motor de regras · Dashboard · Resumo executivo · Análise Gemini (opcional)")

    tab_q, tab_dash, tab_resumo, tab_gemini = st.tabs(
        ["Questionário", "Dashboard de Escopo", "Resumo Executivo", "Análise Técnica (Gemini)"]
    )

    def _render_question_widget(q: dict) -> None:
        qid = q["id"]
        t = q.get("type", "yes_no")
        st.markdown(f"**{qid}** — {q['text']}")
        st.caption(q.get("justificativa", ""))
        if q.get("audit_only"):
            st.caption("ℹ️ Uso para relatório / maturidade; não altera incisos do escopo.")

        if t == "yes_no":
            current = "Sim" if st.session_state.answers.get(qid, False) else "Não"
            st.radio(
                f"Resposta {qid}",
                options=["Não", "Sim"],
                index=1 if current == "Sim" else 0,
                horizontal=True,
                key=f"q_{qid}",
                label_visibility="collapsed",
            )
        elif t == "single_choice":
            opts = q.get("options") or []
            ids = [""] + [str(o["id"]) for o in opts]

            def _fmt_sid(x: str) -> str:
                if x == "":
                    return "— Selecione —"
                for o in opts:
                    if o["id"] == x:
                        return str(o["label"])
                return x

            st.selectbox(
                f"Seleção {qid}",
                options=ids,
                format_func=_fmt_sid,
                key=f"q_{qid}_single",
                label_visibility="collapsed",
            )
        elif t == "multi_choice":
            opts = q.get("options") or []
            opt_ids = [str(o["id"]) for o in opts]

            def _fmt_mid(i: str) -> str:
                for o in opts:
                    if o["id"] == i:
                        return str(o["label"])
                return i

            st.multiselect(
                f"Seleção múltipla {qid}",
                options=opt_ids,
                format_func=_fmt_mid,
                key=f"q_{qid}_multi",
                label_visibility="collapsed",
            )
        elif t == "text_short":
            mx = int(q.get("max_length") or 4000)
            st.text_area(
                f"Texto {qid}",
                max_chars=mx,
                height=120,
                placeholder=q.get("placeholder") or "",
                key=f"q_{qid}_text",
                label_visibility="collapsed",
            )
        st.divider()

    with tab_q:
        if trk == "custodiante":
            st.subheader("Delimitação técnica (trilha custodiante)")
            st.write(
                "Núcleo **obrigatório** de custódia e correlatos permanece no escopo. Perguntas **Sim/Não**, escolha única, "
                "múltipla escolha e texto livre acionam incisos condicionais adicionais."
            )
        else:
            st.subheader("Delimitação técnica (Fase intermediária — tipos mistos)")
            st.write(
                "Itens **obrigatórios** permanecem sempre no escopo. Perguntas **Sim/Não**, escolha única, "
                "múltipla escolha e texto livre (onde indicado) definem incisos condicionais."
            )

        by_block = questions_by_block(trk)
        block_list = list(get_blocks(trk))
        for i, mb in enumerate(block_list):
            bid = str(mb["id"])
            title = mb.get("title", bid)
            lead = mb.get("lead", "")
            with st.expander(f"Bloco {bid} — {title}", expanded=(i == 0)):
                if lead:
                    st.caption(lead)
                for q in by_block.get(bid, []):
                    _render_question_widget(q)

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Gerar escopo", type="primary", use_container_width=True):
                answers = _build_answers_from_ui()
                st.session_state.answers = answers
                df, meta = compute_scope(answers, track=trk)
                st.session_state.scope_df = df
                st.session_state.scope_meta = meta
                st.session_state.scope_computed = True
                st.session_state.gemini_cache = ""
                st.session_state.gemini_last_key = ""
                st.success("Escopo calculado. Abra as abas **Dashboard** e **Resumo Executivo**.")
        with col2:
            if st.button("Redefinir respostas", use_container_width=True):
                qs_reset = _current_questions()
                st.session_state.answers = {q["id"]: _default_answer_for_q(q) for q in qs_reset}
                for q in qs_reset:
                    qid = q["id"]
                    t = q.get("type")
                    if t == "yes_no":
                        st.session_state[f"q_{qid}"] = "Não"
                    elif t == "single_choice":
                        st.session_state[f"q_{qid}_single"] = ""
                    elif t == "multi_choice":
                        st.session_state[f"q_{qid}_multi"] = []
                    elif t == "text_short":
                        st.session_state[f"q_{qid}_text"] = ""
                st.session_state.scope_computed = False
                st.session_state.scope_df = pd.DataFrame()
                st.session_state.scope_meta = {}
                st.session_state.gemini_cache = ""
                st.rerun()

    def _scope_snapshot() -> tuple[pd.DataFrame, dict]:
        if st.session_state.scope_computed:
            return st.session_state.scope_df, st.session_state.scope_meta
        live = _build_answers_from_ui()
        return compute_scope(live, track=st.session_state.scope_track)

    df_default, meta_default = _scope_snapshot()

    with tab_dash:
        st.subheader("Resultado — duas categorias de incisos")
        if not st.session_state.scope_computed:
            st.info(
                "Pré-visualização com respostas atuais. Clique em **Gerar escopo** no questionário para fixar o snapshot."
            )

        total = int(meta_default.get("total_count", 0))
        mand = int(meta_default.get("mandatory_count", 0))
        cond = int(meta_default.get("conditional_count", 0))
        n_fora = int(meta_default.get("total_fora_escopo_auditoria", 0))

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Sujeitos a auditoria", total)
        c2.metric("— obrigatórios (matriz)", mand)
        c3.metric("— por respostas", cond)
        c4.metric("Fora deste escopo", n_fora)

        j2 = meta_default.get("journey_2") or {}
        if j2:
            with st.expander("Jornada 2 — checklist de evidências e serviços técnicos", expanded=True):
                st.caption(j2.get("label", ""))
                sc = j2.get("smart_contract_audit") or {}
                pt = j2.get("penetration_test") or {}
                st.markdown("#### Smart contract audit")
                st.write("**Aplicável:** " + ("Sim" if sc.get("aplicavel") else "Não"))
                st.info(sc.get("acao_cliente", ""))
                st.markdown("#### Penetration test")
                st.write("**Aplicável:** " + ("Sim" if pt.get("aplicavel") else "Não"))
                fu = (pt.get("formulario_url") or "").strip()
                if fu:
                    st.markdown(
                        f"[CertiK Application Penetration Testing Questionnaire (Google Forms)]({fu})"
                    )
                st.info(pt.get("acao_cliente", ""))
                for n in j2.get("notas_heuristica") or []:
                    st.warning(str(n))
                st.metric("Total de pedidos na checklist (documentação)", int(j2.get("total_pedidos_documentacao") or 0))
                st.caption(
                    "Para cada pedido: **Pular por agora** ou **Preciso elaborar este documento** "
                    "se ainda não tiver o ficheiro (estado guardado na sessão Streamlit)."
                )
                for bloc in j2.get("checklist_por_inciso") or []:
                    iid = bloc.get("inciso_id", "")
                    tit = bloc.get("item_in701", "")
                    with st.expander(f"`{iid}` · {tit}", expanded=False):
                        for j, p in enumerate(bloc.get("pedidos") or []):
                            st.markdown(f"**{p.get('titulo', '')}** · `{p.get('categoria', '')}`")
                            st.caption(p.get("detalhe", ""))
                            do = (p.get("documento_otimo") or "").strip()
                            if do:
                                st.info(f"**Documento exemplar:** {do}")
                            pid = str(p.get("id") or f"_row{j}")
                            st.radio(
                                "Estado do pedido",
                                [
                                    "Não assinalado",
                                    "Pular por agora",
                                    "Preciso elaborar este documento",
                                ],
                                key=_j2_pedido_widget_key(str(iid), pid),
                                horizontal=True,
                                label_visibility="collapsed",
                            )

        cr = meta_default.get("corpus_readiness") or {}
        cnt = cr.get("counts") or {}
        with st.expander("Prontidão do corpus interno (laws/)", expanded=False):
            st.caption("Indicador documental no repositório; não substitui parecer jurídico.")
            d1, d2, d3, d4, d5 = st.columns(5)
            d1.metric("Índice 0–100", f"{cr.get('readiness_index_0_100', 0):.1f}")
            d2.metric("Completo", int(cnt.get("completo", 0)))
            d3.metric("Parcial", int(cnt.get("parcial", 0)))
            d4.metric("Incompleto", int(cnt.get("incompleto", 0)))
            d5.metric("Refs STUB", len(cr.get("stub_references") or []))
            gaps = cr.get("gaps_priority") or []
            if gaps:
                st.dataframe(
                    pd.DataFrame(gaps)[["inciso_id", "item", "corpus_status", "ficheiros_corpus"]],
                    use_container_width=True,
                    hide_index=True,
                )

        sujeitos = meta_default.get("incisos_sujeitos_auditoria") or []
        fora = meta_default.get("incisos_fora_escopo_auditoria") or []

        if sujeitos:
            st.markdown("### Sujeitos a auditoria (nesta delimitação)")
            st.caption("Cada inciso inclui o motivo e uma orientação indicativa para o relatório ao BCB (não é parecer jurídico).")
            for row in sujeitos:
                with st.expander(f"**{row['item']}** · `{row['inciso_id']}`", expanded=False):
                    st.markdown(f"**Artigo IN 701:** {row['artigo_in701']}")
                    st.markdown(f"**Por que será auditado:** {row['por_que_sera_auditado']}")
                    st.markdown(f"**Orientação para o relatório ao BCB:** {row['orientacao_relatorio_bcb']}")
                    st.caption(f"Corpus: {row.get('corpus_status', '')} · {row.get('ficheiros_corpus', '')[:120]}…")

            st.markdown("#### Vista tabular (resumo)")
            st.dataframe(
                _style_scope_df(df_default),
                use_container_width=True,
                hide_index=True,
                height=min(400, 36 + len(df_default) * 32),
            )
        else:
            st.warning("Nenhum inciso sujeito a auditoria.")

        if fora:
            st.markdown("### Fora do escopo de auditoria (nesta configuração)")
            st.caption("Estes incisos da matriz não entram nesta delimitação com as respostas atuais.")
            for row in fora:
                with st.expander(f"{row['item']} · `{row['inciso_id']}`", expanded=False):
                    st.markdown(row["por_que_nao_neste_escopo"])
                    st.caption(row.get("descricao", "")[:280] + ("…" if len(row.get("descricao", "")) > 280 else ""))

    with tab_resumo:
        st.subheader("Resumo executivo")
        text = _resumo_text(vasp_name, meta_default, df_default)
        st.markdown(text)

    with tab_gemini:
        st.subheader("Análise técnica do auditor (Gemini)")
        api = (gemini_key or "").strip()
        if not api:
            st.info(
                "Configure a API Key do Gemini na barra lateral, ou defina a variável de ambiente "
                "`GEMINI_API_KEY`, ou crie `.streamlit/secrets.toml` com `GEMINI_API_KEY`."
            )
        else:
            norm = meta_default.get("answers", {})
            tr_gem = str(meta_default.get("track") or st.session_state.scope_track)
            if tr_gem == "custodiante":
                p1, p2 = bool(norm.get("cust_A_transit")), bool(norm.get("cust_A_fiat"))
            else:
                p1, p2 = bool(norm.get("P1")), bool(norm.get("P2"))
            custody_labels: list[str] = []
            if df_default is not None and not df_default.empty:
                custody_items = {"VII", "XIV", "XVI", "XVII", "I (a)", "I (b)", "XV"}
                for _, row in df_default.iterrows():
                    item = str(row.get("Item IN 701", "")).strip()
                    if item in custody_items:
                        custody_labels.append(item)

            if st.button("Gerar análise de custódia (Gemini)", type="primary"):
                with st.spinner("Consultando Gemini…"):
                    try:
                        out = _run_gemini_analysis(
                            api, vasp_name, p1, p2, custody_labels, track=tr_gem
                        )
                        st.session_state.gemini_cache = out
                        st.session_state.gemini_last_key = api[:8] + "…"
                    except Exception as e:
                        st.error(f"Falha na chamada ao Gemini: {e}")

            if st.session_state.gemini_cache:
                st.markdown(st.session_state.gemini_cache)

    st.sidebar.markdown("---")
    st.sidebar.caption(
        "CertiK · Uso interno. IN 701 intermediária · Roteiro de implementação **E** "
        "(ver laws/ROTEIRO_FASES.txt)."
    )


if __name__ == "__main__":
    main()
