/**
 * SPA — questionário IN 701 (cliente). Consome /api/v1/questions e /api/v1/scope.
 * Legado /api/* mantido no servidor para integrações antigas.
 */

import { wireDecisionTreeUI } from "./decision_tree.js?v=3";
import { wireDocsGuideUI } from "./docs_guide.js?v=3";
import { initI18n, t, buildLangToggle } from "./i18n.js?v=1";

const $ = (sel, root = document) => root.querySelector(sel);

const TRACK_STORAGE_KEY = "certik701_scope_track";

const state = {
  blocks: [],
  step: 0,
  /** intermediaria | custodiante | corretora */
  track: "intermediaria",
  /** @type {{ custodiante_track: boolean; corretora_track: boolean }} */
  features: { custodiante_track: true, corretora_track: true },
  /** @type {Record<string, unknown>} */
  answers: {},
};

function loadTrackFromStorage() {
  try {
    const s = sessionStorage.getItem(TRACK_STORAGE_KEY);
    if (s === "custodiante" || s === "corretora" || s === "intermediaria") return s;
  } catch {
    /* ignore */
  }
  return "intermediaria";
}

function saveTrackToStorage() {
  try {
    sessionStorage.setItem(TRACK_STORAGE_KEY, state.track);
  } catch {
    /* ignore */
  }
}

function syncTrackButtonsUI() {
  document.querySelectorAll(".intro-track__btn").forEach((btn) => {
    const t = btn.getAttribute("data-track");
    const on = t === state.track;
    btn.classList.toggle("intro-track__btn--active", on);
    btn.setAttribute("aria-pressed", on ? "true" : "false");
    const disabledCust = t === "custodiante" && state.features.custodiante_track === false;
    const disabledCorr = t === "corretora" && state.features.corretora_track === false;
    if (disabledCust || disabledCorr) {
      btn.classList.add("hidden");
      btn.setAttribute("aria-hidden", "true");
    } else if (t === "custodiante" || t === "corretora") {
      btn.classList.remove("hidden");
      btn.removeAttribute("aria-hidden");
    }
  });
}

/** Prefixo REST versionado (recomendado). */
function apiBase() {
  return "/api/v1";
}

async function fetchJSON(path, options = {}) {
  const diag = `Diagnóstico: GET ${apiBase()}/health`;
  let res;
  try {
    res = await fetch(`${apiBase()}${path}`, {
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      ...options,
    });
  } catch (e) {
    const base =
      e instanceof TypeError
        ? "Não foi possível contactar a API (rede, CORS ou servidor parado)."
        : String(e?.message || e);
    throw new Error(`${base} ${diag}.`);
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const d = err.detail;
    let msg = res.statusText || "Erro na requisição";
    if (typeof d === "string") msg = d;
    else if (d && typeof d === "object" && typeof d.message === "string") msg = d.message;
    throw new Error(`${msg} — ${diag}.`);
  }
  return res.json();
}

function showToast(msg) {
  const el = $("#toast");
  el.textContent = msg;
  el.classList.remove("hidden");
  clearTimeout(showToast._t);
  showToast._t = setTimeout(() => el.classList.add("hidden"), 5000);
}

function setView(view) {
  const isIntroLike = view === "intro" || view === "decisionTree" || view === "docsGuide";
  document.body.classList.toggle("app-view-intro", isIntroLike);
  $("#intro").classList.toggle("hidden", view !== "intro");
  $("#wizard").classList.toggle("hidden", view !== "wizard");
  $("#results").classList.toggle("hidden", view !== "results");
  $("#decision-tree-view")?.classList.toggle("hidden", view !== "decisionTree");
  $("#docs-guide-view")?.classList.toggle("hidden", view !== "docsGuide");
}

function qType(q) {
  return q.type || "yes_no";
}

function initAnswersFromBlocks() {
  state.answers = {};
  for (const b of state.blocks) {
    for (const q of b.questions) {
      const t = qType(q);
      if (t === "yes_no") state.answers[q.id] = false;
      else if (t === "single_choice") state.answers[q.id] = null;
      else if (t === "multi_choice") state.answers[q.id] = [];
      else if (t === "text_short") state.answers[q.id] = "";
      else state.answers[q.id] = false;
    }
  }
}

/** single_choice obrigatório (exceto audit_only) antes de avançar ou submeter. */
function blockHasUnansweredSingleChoice(block) {
  for (const q of block.questions) {
    if (q.audit_only) continue;
    if (qType(q) !== "single_choice") continue;
    const v = state.answers[q.id];
    if (v == null || v === "") {
      showToast(`Selecione uma opção em ${q.id} antes de continuar.`);
      return true;
    }
  }
  return false;
}

function setNavLoading(loading) {
  const btn = $("#btn-next");
  const back = $("#btn-back");
  if (btn) {
    btn.disabled = loading;
    btn.classList.toggle("btn-loading", loading);
    btn.setAttribute("aria-busy", loading ? "true" : "false");
  }
  if (back) back.disabled = loading;
}

function normalizeBlockAnswers(block) {
  for (const q of block.questions) {
    const t = qType(q);
    const id = q.id;
    if (t === "yes_no") {
      if (typeof state.answers[id] !== "boolean") state.answers[id] = false;
    } else if (t === "single_choice") {
      if (state.answers[id] === undefined) state.answers[id] = null;
    } else if (t === "multi_choice") {
      if (!Array.isArray(state.answers[id])) state.answers[id] = [];
    } else if (t === "text_short") {
      if (typeof state.answers[id] !== "string") state.answers[id] = state.answers[id] == null ? "" : String(state.answers[id]);
    }
  }
}

function renderYesNo(card, q) {
  const qid = q.id;
  const val = state.answers[qid];

  const actions = document.createElement("div");
  actions.className = "q-actions";
  actions.setAttribute("role", "group");
  actions.setAttribute("aria-label", `${t("wizard_answer_group")} ${qid}`);

  const mkBtn = (label, v, pressed) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = `btn-yn ${v ? "yes" : "no"}`;
    btn.setAttribute("data-value", String(v));
    btn.setAttribute("aria-pressed", pressed ? "true" : "false");
    btn.textContent = label;
    btn.addEventListener("click", () => {
      state.answers[qid] = v;
      actions.querySelectorAll(".btn-yn").forEach((b) => {
        b.setAttribute("aria-pressed", b.getAttribute("data-value") === String(v) ? "true" : "false");
      });
    });
    return btn;
  };

  actions.appendChild(mkBtn(t("wizard_yn_no"), false, val === false));
  actions.appendChild(mkBtn(t("wizard_yn_yes"), true, val === true));
  card.appendChild(actions);
}

function renderSingleChoice(card, q) {
  const qid = q.id;
  const opts = q.options || [];
  /** Rádios em vez de &lt;select&gt;: listas nativas ignoram a largura do cartão com opções longas (ex.: P_list). */
  const wrap = document.createElement("fieldset");
  wrap.className = "q-multicheck q-radio-group";
  wrap.setAttribute("aria-label", `${t("wizard_single_label")} ${qid}`);

  const cur = state.answers[qid];
  const curId = cur && opts.some((o) => o.id === cur) ? cur : null;
  const groupName = `single_${qid}`;

  for (const o of opts) {
    const row = document.createElement("label");
    row.className = "q-check-row";
    const rb = document.createElement("input");
    rb.type = "radio";
    rb.name = groupName;
    rb.value = o.id;
    rb.checked = curId === o.id;
    rb.addEventListener("change", () => {
      if (rb.checked) state.answers[qid] = o.id;
    });
    const lab = document.createElement("span");
    lab.className = "q-check-text";
    lab.textContent = o.label;
    row.appendChild(rb);
    row.appendChild(lab);
    wrap.appendChild(row);
  }

  if (!curId) {
    const hint = document.createElement("p");
    hint.className = "q-radio-hint";
    hint.textContent = t("wizard_select_hint");
    wrap.appendChild(hint);
    wrap.addEventListener(
      "change",
      () => {
        hint.remove();
      },
      { once: true },
    );
  }

  card.appendChild(wrap);
}

function renderMultiChoice(card, q) {
  const qid = q.id;
  const opts = q.options || [];
  const wrap = document.createElement("fieldset");
  wrap.className = "q-multicheck";
  wrap.setAttribute("aria-label", `${t("wizard_multi_label")} ${qid}`);

  let chosen = new Set(Array.isArray(state.answers[qid]) ? state.answers[qid] : []);

  const sync = () => {
    state.answers[qid] = Array.from(chosen);
  };

  for (const o of opts) {
    const row = document.createElement("label");
    row.className = "q-check-row";
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.value = o.id;
    cb.checked = chosen.has(o.id);
    cb.addEventListener("change", () => {
      if (cb.checked) chosen.add(o.id);
      else chosen.delete(o.id);
      sync();
    });
    const lab = document.createElement("span");
    lab.className = "q-check-text";
    lab.textContent = o.label;
    row.appendChild(cb);
    row.appendChild(lab);
    wrap.appendChild(row);
  }

  card.appendChild(wrap);
}

function renderTextShort(card, q) {
  const qid = q.id;
  const wrap = document.createElement("div");
  wrap.className = "q-field";
  const ta = document.createElement("textarea");
  ta.className = "q-textarea";
  ta.rows = 4;
  ta.maxLength = q.max_length || 4000;
  ta.placeholder = q.placeholder || "";
  ta.value = typeof state.answers[qid] === "string" ? state.answers[qid] : "";
  ta.addEventListener("input", () => {
    state.answers[qid] = ta.value;
  });
  wrap.appendChild(ta);
  card.appendChild(wrap);
}

/** Renderiza os pontos de bloco (#4) */
function renderBlockDots(direction) {
  const dotsEl = $("#block-dots");
  if (!dotsEl) return;
  dotsEl.innerHTML = "";
  state.blocks.forEach((b, i) => {
    const dot = document.createElement("span");
    dot.className = "block-dot";
    if (i < state.step) dot.classList.add("block-dot--done");
    else if (i === state.step) dot.classList.add("block-dot--active");
    dot.title = b.title || t("wizard_block_of", { n: i + 1, total: state.blocks.length });
    dotsEl.appendChild(dot);
  });
  // Label do bloco actual
  const lbl = document.createElement("span");
  lbl.className = "block-dot-label";
  lbl.textContent = state.blocks[state.step]?.title || "";
  dotsEl.appendChild(lbl);
}

/** Retorna true se a pergunta tem impacto no escopo (não audit_only e tem incisos em when_true/tags) */
function hasScopeImpact(q) {
  if (q.audit_only) return false;
  if (Array.isArray(q.when_true) && q.when_true.length > 0) return true;
  if (Array.isArray(q.tags) && q.tags.length > 0) return true;
  if (Array.isArray(q.options)) {
    return q.options.some((o) => Array.isArray(o.add_incisos) && o.add_incisos.length > 0);
  }
  return false;
}

function renderQuestions(direction = "forward") {
  const block = state.blocks[state.step];
  if (!block) return;

  $("#block-title").textContent = block.title;
  if (block.lead) {
    $("#block-lead").textContent = block.lead;
    $("#block-lead").classList.remove("hidden");
  } else {
    $("#block-lead").textContent = "";
    $("#block-lead").classList.add("hidden");
  }

  $("#step-label").textContent = t("wizard_block_of", { n: state.step + 1, total: state.blocks.length });

  const pct = ((state.step + 1) / state.blocks.length) * 100;
  $("#progress-bar").style.width = `${pct}%`;

  renderBlockDots(direction);

  const container = $("#questions-container");
  container.innerHTML = "";

  // #5: slide animation
  container.classList.remove("questions--slide-in", "questions--slide-back");
  void container.offsetWidth; // force reflow
  container.classList.add(direction === "back" ? "questions--slide-back" : "questions--slide-in");

  for (const q of block.questions) {
    const card = document.createElement("article");
    const isAuditOnly = !!q.audit_only;
    card.className = isAuditOnly ? "q-card q-card--audit-only" : "q-card";
    card.setAttribute("data-qid", q.id);

    // #6: audit-only tag
    if (isAuditOnly) {
      const tag = document.createElement("div");
      tag.className = "q-audit-tag";
      tag.innerHTML = `<span aria-hidden="true">◉</span> ${t("wizard_audit_tag")}`;
      card.appendChild(tag);
    } else {
      // #7: impact badge for scope questions
      const wt = q.when_true || [];
      const optsIncisos = (q.options || []).flatMap((o) => o.add_incisos || []);
      const allIncisos = [...new Set([...wt, ...optsIncisos])];
      if (allIncisos.length > 0) {
        const badge = document.createElement("div");
        badge.className = "q-impact-badge";
        badge.innerHTML = `<span class="q-impact-badge__dot" aria-hidden="true"></span>${t("wizard_impact_badge")}`;
        card.appendChild(badge);
      }
    }

    const head = document.createElement("div");
    head.className = "q-id";
    head.textContent = q.id;
    card.appendChild(head);

    const pText = document.createElement("p");
    pText.className = "q-text";
    pText.textContent = q.text;
    card.appendChild(pText);

    const pWhy = document.createElement("p");
    pWhy.className = "q-why";
    pWhy.textContent = q.justificativa || "";
    card.appendChild(pWhy);

    if (isAuditOnly) {
      const note = document.createElement("p");
      note.className = "q-audit-note";
      note.textContent =
        t("wizard_audit_note");
      card.appendChild(note);
    }

    const t = qType(q);
    if (t === "yes_no") renderYesNo(card, q);
    else if (t === "single_choice") renderSingleChoice(card, q);
    else if (t === "multi_choice") renderMultiChoice(card, q);
    else if (t === "text_short") renderTextShort(card, q);
    else renderYesNo(card, q);

    container.appendChild(card);
  }

  $("#btn-back").classList.toggle("hidden", state.step === 0);

  const last = state.step === state.blocks.length - 1;
  $("#btn-next").textContent = last ? t("wizard_btn_finish") : t("wizard_btn_next");

  // #9: save progress
  saveProgressToStorage();
}

function escapeHtml(s) {
  if (s == null) return "";
  const d = document.createElement("div");
  d.textContent = String(s);
  return d.innerHTML;
}

/** Classe CSS do emblema de origem (matriz vs gatilhos). */
function origemPillClass(origem) {
  const o = String(origem || "");
  if (o.includes("Obrigatório")) return "dash-inciso-pill dash-inciso-pill--mandatory";
  if (o.includes("Acionado")) return "dash-inciso-pill dash-inciso-pill--triggered";
  return "dash-inciso-pill dash-inciso-pill--neutral";
}

/**
 * Rosca de cobertura: obrigatórios + acionados + fora = universo da matriz na trilha.
 * @param {number} mand
 * @param {number} cond
 * @param {number} nf
 */
function renderComplianceDonut(mand, cond, nf) {
  const ring = $("#compliance-donut");
  const pctEl = $("#donut-pct");
  const legM = $("#leg-mand");
  const legC = $("#leg-cond");
  const legF = $("#leg-fora");
  const total = mand + cond + nf;
  const na = mand + cond;

  if (legM) legM.textContent = String(mand);
  if (legC) legC.textContent = String(cond);
  if (legF) legF.textContent = String(nf);

  if (pctEl) {
    if (total > 0) {
      const p = Math.round((na / total) * 1000) / 10;
      pctEl.textContent = `${Number.isInteger(p) ? p : p.toFixed(1)}%`;
    } else {
      pctEl.textContent = "0%";
    }
  }

  if (!ring) return;
  if (total <= 0) {
    ring.style.background = "conic-gradient(#4b5563 0% 100%)";
    return;
  }
  const pM = (mand / total) * 100;
  const pC = (cond / total) * 100;
  const a1 = pM;
  const a2 = pM + pC;
  ring.style.background = `conic-gradient(
    #22c55e 0% ${a1}%,
    #ca8a04 ${a1}% ${a2}%,
    #4b5563 ${a2}% 100%
  )`;
}

const J2_PEDIDO_STORAGE_KEY = "certik_vasp_j2_pedido_status";

/* ---- #9: Persistência de respostas em localStorage ---- */
const PROGRESS_STORAGE_KEY = "certik701_progress_v1";

function saveProgressToStorage() {
  try {
    const snapshot = {
      track: state.track,
      step: state.step,
      answers: state.answers,
      institution: (document.getElementById("institution")?.value || "").trim(),
      savedAt: Date.now(),
    };
    localStorage.setItem(PROGRESS_STORAGE_KEY, JSON.stringify(snapshot));
  } catch {
    /* quota exceeded or private mode */
  }
}

function loadProgressFromStorage() {
  try {
    const raw = localStorage.getItem(PROGRESS_STORAGE_KEY);
    if (!raw) return null;
    const p = JSON.parse(raw);
    // expire after 48 h
    if (!p || typeof p !== "object") return null;
    if (Date.now() - (p.savedAt || 0) > 48 * 60 * 60 * 1000) {
      localStorage.removeItem(PROGRESS_STORAGE_KEY);
      return null;
    }
    return p;
  } catch {
    return null;
  }
}

function clearProgressStorage() {
  try { localStorage.removeItem(PROGRESS_STORAGE_KEY); } catch { /* ignore */ }
}

function showResumeBanner(saved) {
  const banner = document.getElementById("resume-banner");
  if (!banner || !saved) return;
  const trackNames = {
    intermediaria: t("track_intermediaria_label"),
    custodiante:   t("track_custodiante_label"),
    corretora:     t("track_corretora_label"),
  };
  const trk = trackNames[saved.track] || saved.track;
  const inst = saved.institution ? ` · ${saved.institution}` : "";
  const mins = Math.round((Date.now() - (saved.savedAt || 0)) / 60000);
  const timeStr = mins < 60 ? `${mins} min` : `${Math.round(mins / 60)} h`;
  banner.querySelector(".resume-banner__text").textContent =
    `${t("resume_text")} ${trk}${inst} (${timeStr}).`;
  banner.classList.remove("hidden");
}

function loadJ2PedidoStatuses() {
  try {
    const raw = sessionStorage.getItem(J2_PEDIDO_STORAGE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function saveJ2PedidoStatuses(map) {
  sessionStorage.setItem(J2_PEDIDO_STORAGE_KEY, JSON.stringify(map));
}

function setJ2PedidoStatus(pedidoKey, status) {
  const o = loadJ2PedidoStatuses();
  if (!status) delete o[pedidoKey];
  else o[pedidoKey] = status;
  saveJ2PedidoStatuses(o);
}

/**
 * @param {HTMLElement} el — contentor dos botões (`.dash-pedido-shell` ou `.j2-pedido`)
 * @param {string} status  '' | 'skip' | 'elaborate'
 */
function applyJ2PedidoVisual(el, status) {
  el.classList.remove("j2-pedido--skip", "j2-pedido--elaborate");
  const badge = el.querySelector(":scope > .j2-pedido-badge");
  if (badge) badge.remove();
  const skipBtn = el.querySelector(".btn-j2-skip");
  const elabBtn = el.querySelector(".btn-j2-elaborate");
  if (skipBtn) skipBtn.setAttribute("aria-pressed", status === "skip" ? "true" : "false");
  if (elabBtn) elabBtn.setAttribute("aria-pressed", status === "elaborate" ? "true" : "false");

  if (status === "skip") {
    el.classList.add("j2-pedido--skip");
    const b = document.createElement("span");
    b.className = "j2-pedido-badge j2-pedido-badge--skip";
    b.textContent = "Adiado por agora";
    el.insertBefore(b, el.firstChild);
  } else if (status === "elaborate") {
    el.classList.add("j2-pedido--elaborate");
    const b = document.createElement("span");
    b.className = "j2-pedido-badge j2-pedido-badge--elab";
    b.textContent = "Preciso elaborar este documento";
    el.insertBefore(b, el.firstChild);
  }
}

function buildChecklistMap(j2) {
  const m = new Map();
  const cl = j2 && Array.isArray(j2.checklist_por_inciso) ? j2.checklist_por_inciso : [];
  for (const b of cl) {
    if (b && b.inciso_id != null) m.set(String(b.inciso_id), b);
  }
  return m;
}

function createDashDocumentRow(p, iid, getNextPedidoIndex) {
  const idx = getNextPedidoIndex();
  const pid = (p.id != null && String(p.id).trim()) || `p${idx}`;
  const pedidoKey = `${iid}:${pid}`;

  const details = document.createElement("details");
  details.className = "dash-doc";

  const sum = document.createElement("summary");
  sum.className = "dash-doc-summary";
  sum.innerHTML = `<span class="dash-doc-title">${escapeHtml(p.titulo || "")}</span><span class="dash-doc-cat">${escapeHtml(p.categoria || "")}</span>`;

  const panel = document.createElement("div");
  panel.className = "dash-doc-panel";

  const lg = document.createElement("p");
  lg.className = "dash-doc-label";
  lg.textContent = "O que reunir";

  const detp = document.createElement("p");
  detp.className = "dash-doc-det";
  detp.textContent = String(p.detalhe || "");

  const ot = document.createElement("aside");
  ot.className = "dash-doc-otimo";
  ot.innerHTML = `<p class="dash-doc-otimo-label">Entregável exemplar</p><p class="dash-doc-otimo-text">${escapeHtml(String(p.documento_otimo || ""))}</p>`;

  const shell = document.createElement("div");
  shell.className = "dash-pedido-shell j2-pedido";

  const actions = document.createElement("div");
  actions.className = "j2-pedido-actions";
  actions.setAttribute("role", "group");
  actions.setAttribute("aria-label", "Estado do pedido de documentação");

  const mkBtn = (cls, label, statusVal) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = `btn-j2 ${cls}`;
    btn.textContent = label;
    btn.setAttribute("aria-pressed", "false");
    btn.addEventListener("click", () => {
      const cur = loadJ2PedidoStatuses()[pedidoKey];
      const next = cur === statusVal ? "" : statusVal;
      setJ2PedidoStatus(pedidoKey, next);
      applyJ2PedidoVisual(shell, next);
    });
    return btn;
  };

  actions.appendChild(mkBtn("btn-j2-skip", "Pular por agora", "skip"));
  actions.appendChild(mkBtn("btn-j2-elaborate", "Preciso elaborar este documento", "elaborate"));

  const btnReset = document.createElement("button");
  btnReset.type = "button";
  btnReset.className = "btn-j2 btn-j2-reset";
  btnReset.textContent = "Repor";
  btnReset.addEventListener("click", () => {
    setJ2PedidoStatus(pedidoKey, "");
    applyJ2PedidoVisual(shell, "");
  });
  actions.appendChild(btnReset);

  shell.appendChild(actions);

  panel.appendChild(lg);
  panel.appendChild(detp);
  panel.appendChild(ot);
  panel.appendChild(shell);

  details.appendChild(sum);
  details.appendChild(panel);
  applyJ2PedidoVisual(shell, loadJ2PedidoStatuses()[pedidoKey] || "");
  return details;
}

function renderDashAuditInciso(row, checklistBloc, index, getNextPedidoIndex) {
  const det = document.createElement("details");
  det.className = "dash-inciso";
  if (index === 0) det.open = true;

  const pedidos = checklistBloc && Array.isArray(checklistBloc.pedidos) ? checklistBloc.pedidos : [];
  const nDocs = pedidos.length;

  const sum = document.createElement("summary");
  sum.className = "dash-inciso-summary";
  const pillCls = origemPillClass(row.origem_escopo);
  sum.innerHTML = `<span class="${pillCls}">${escapeHtml(row.origem_escopo || "")}</span><span class="dash-inciso-heading"><span class="dash-inciso-item">${escapeHtml(row.item || "")}</span><span class="dash-inciso-meta"><code>${escapeHtml(row.inciso_id || "")}</code> · ${escapeHtml(row.artigo_in701 || "")}</span></span><span class="dash-inciso-docs-n" aria-hidden="true">${nDocs} doc.</span>`;

  const body = document.createElement("div");
  body.className = "dash-inciso-body";

  const ctx = document.createElement("details");
  ctx.className = "dash-context";
  const ctxSum = document.createElement("summary");
  ctxSum.className = "dash-context-summary";
  ctxSum.textContent = "Contexto de escopo";
  const ctxBody = document.createElement("div");
  ctxBody.className = "dash-context-body";
  const pq = Array.isArray(row.perguntas_gatilho) ? row.perguntas_gatilho : [];
  const gat = pq.length
    ? `<p class="dash-gatilho"><strong>Gatilho no questionário:</strong> ${escapeHtml(pq.join(", "))}</p>`
    : "";
  ctxBody.innerHTML = `<p class="dash-label">Por que entra no escopo</p><p class="dash-text">${escapeHtml(row.por_que_sera_auditado || "")}</p><p class="dash-label dash-label--bcb">Relatório ao BCB (indicativo)</p><p class="dash-text dash-text--bcb">${escapeHtml(row.orientacao_relatorio_bcb || "")}</p>${gat}`;
  ctx.appendChild(ctxSum);
  ctx.appendChild(ctxBody);

  const docsSection = document.createElement("div");
  docsSection.className = "dash-docs-section";
  const docsTitle = document.createElement("h4");
  docsTitle.className = "dash-docs-title";
  docsTitle.textContent = "Checklist de evidências";
  const docsLead = document.createElement("p");
  docsLead.className = "dash-docs-lead";
  docsLead.textContent =
    "Apenas incisos no escopo atual. Abra cada linha para o pedido e o perfil de um entregável exemplar.";
  docsSection.appendChild(docsTitle);
  docsSection.appendChild(docsLead);

  const iid = String(row.inciso_id || "");
  if (nDocs) {
    for (const p of pedidos) {
      if (p && typeof p === "object") {
        docsSection.appendChild(createDashDocumentRow(p, iid, getNextPedidoIndex));
      }
    }
  } else {
    const emp = document.createElement("p");
    emp.className = "dash-docs-empty";
    emp.textContent = "Sem pedidos mapeados para este inciso.";
    docsSection.appendChild(emp);
  }

  body.appendChild(ctx);
  body.appendChild(docsSection);
  det.appendChild(sum);
  det.appendChild(body);
  return det;
}

function renderDashSkipContainer(fora) {
  const host = document.createElement("div");
  host.className = "dash-skip-host";
  if (!fora.length) {
    host.innerHTML = '<p class="empty-col">Todos os incisos da matriz entram no escopo nesta configuração.</p>';
    return host;
  }
  const outer = document.createElement("details");
  outer.className = "dash-skip-outer";
  const s = document.createElement("summary");
  s.className = "dash-skip-outer-summary";
  s.innerHTML = `<span class="dash-skip-outer-title">Incisos fora deste escopo</span><span class="dash-skip-outer-count">${fora.length}</span>`;
  outer.appendChild(s);
  const inner = document.createElement("div");
  inner.className = "dash-skip-outer-body";
  for (const row of fora) {
    if (!row || typeof row !== "object") continue;
    const d = document.createElement("details");
    d.className = "dash-skip-item";
    const sm = document.createElement("summary");
    sm.className = "dash-skip-item-summary";
    sm.innerHTML = `<span>${escapeHtml(row.item || "")}</span><code>${escapeHtml(row.inciso_id || "")}</code>`;
    d.appendChild(sm);
    const db = document.createElement("div");
    db.className = "dash-skip-item-body";
    db.innerHTML = `<p class="dash-skip-art">${escapeHtml(row.artigo_in701 || "")}</p><p class="dash-skip-why">${escapeHtml(row.por_que_nao_neste_escopo || "")}</p>`;
    d.appendChild(db);
    inner.appendChild(d);
  }
  outer.appendChild(inner);
  host.appendChild(outer);
  return host;
}

/**
 * Jornada 2 — SC audit e pentest (documentação por inciso está no painel abaixo).
 * @param {Record<string, unknown>|undefined} j2
 */
function renderJourney2(j2) {
  const panel = $("#journey-2-panel");
  const lead = $("#j2-lead");
  const streams = $("#j2-streams");
  const notes = $("#j2-notes");
  if (!panel || !lead || !streams || !notes) return;

  if (!j2 || typeof j2 !== "object") {
    panel.classList.add("hidden");
    return;
  }

  panel.classList.remove("hidden");
  lead.textContent =
    typeof j2.label === "string" && j2.label.trim()
      ? j2.label
      : "Smart contract audit e pentest quando aplicáveis. A checklist por inciso está na secção «No escopo de auditoria» abaixo.";

  const sc = j2.smart_contract_audit && typeof j2.smart_contract_audit === "object" ? j2.smart_contract_audit : {};
  const pt = j2.penetration_test && typeof j2.penetration_test === "object" ? j2.penetration_test : {};
  const scOn = !!sc.aplicavel;
  const ptOn = !!pt.aplicavel;
  const formUrl = typeof pt.formulario_url === "string" ? pt.formulario_url.trim() : "";

  streams.innerHTML = `
    <article class="j2-product ${scOn ? "j2-product--active" : "j2-product--inactive"}">
      <div class="j2-product-head">
        <span class="j2-product-name">Smart contract audit</span>
        <span class="j2-product-status">${scOn ? "Ativo" : "Inativo"}</span>
      </div>
      <p class="j2-product-tagline">${scOn ? "Aplicável nesta configuração" : "Não indicado no diagnóstico"}</p>
      <p class="j2-product-body">${escapeHtml(sc.acao_cliente || "")}</p>
    </article>
    <article class="j2-product ${ptOn ? "j2-product--active" : "j2-product--inactive"}">
      <div class="j2-product-head">
        <span class="j2-product-name">Penetration test</span>
        <span class="j2-product-status">${ptOn ? "Ativo" : "Inativo"}</span>
      </div>
      <p class="j2-product-tagline">${
        ptOn ? "Superfície exposta indicada — confirmar âmbito com a CertiK" : "Não aplicável por defeito — confirmar com a CertiK se tiver dúvida"
      }</p>
      <p class="j2-product-body">${escapeHtml(pt.acao_cliente || "")}</p>
      ${
        ptOn && formUrl
          ? `<p class="j2-product-form"><a href="${escapeHtml(formUrl)}" target="_blank" rel="noopener noreferrer" title="CertiK Application Penetration Testing Questionnaire">Abrir formulário de pentest</a></p>`
          : ""
      }
    </article>
  `;

  const nh = Array.isArray(j2.notas_heuristica) ? j2.notas_heuristica : [];
  if (nh.length) {
    notes.classList.remove("hidden");
    notes.innerHTML = nh.map((n) => `<p class="j2-note">${escapeHtml(String(n))}</p>`).join("");
  } else {
    notes.classList.add("hidden");
    notes.innerHTML = "";
  }
}

/**
 * Garante arrays vindos da API (ou respostas antigas / cache).
 */
function normalizeScopePayload(data) {
  let sujeitos = data?.incisos_sujeitos_auditoria;
  let fora = data?.incisos_fora_escopo_auditoria;
  if (!Array.isArray(sujeitos)) sujeitos = [];
  if (!Array.isArray(fora)) fora = [];
  return { sujeitos, fora, raw: data };
}

async function submitScope() {
  const institution = ($("#institution").value || "").trim();
  const payload = {
    institution,
    track: state.track,
    answers: { ...state.answers },
  };

  let data;
  try {
    setNavLoading(true);
    data = await fetchJSON("/scope", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  } catch (e) {
    showToast(String(e.message || e));
    throw e;
  } finally {
    setNavLoading(false);
  }

  const { sujeitos, fora } = normalizeScopePayload(data);
  const resumo = data.resumo && typeof data.resumo === "object" ? data.resumo : {};
  const na = Number(resumo.total_sujeitos_auditoria ?? sujeitos.length) || 0;
  const nf = Number(resumo.total_fora_escopo_auditoria ?? fora.length) || 0;
  const mand = Number(resumo.obrigatorios_matriz ?? 0) || 0;
  const cond = Number(resumo.acionados_por_respostas ?? 0) || 0;

  const elSummary = $("#results-summary");
  const elMetrics = $("#metrics");
  const elCountA = $("#count-audit");
  const elCountS = $("#count-skip");
  const elLeadA = $("#col-audit-lead");
  const elLeadS = $("#col-skip-lead");
  const listA = $("#cards-audit");
  const listS = $("#cards-skip");

  if (!elSummary || !elMetrics || !listA || !listS || !elCountA || !elCountS || !elLeadA || !elLeadS) {
    showToast("Erro: estrutura da página de resultados incompleta. Atualize com Ctrl+F5.");
    return;
  }

  const elEntity = $("#results-entity-name");
  const elTrackPill = $("#results-track-badge");
  if (elEntity) {
    elEntity.textContent = institution || "—";
  }
  const trkLabel =
    data.track === "custodiante"
      ? "Trilha custodiante"
      : data.track === "corretora"
        ? "Trilha corretora"
        : "Fase intermediária";
  if (elTrackPill) {
    elTrackPill.textContent = `${trkLabel} · IN 701`;
  }

  const nome = institution ? `<strong>${escapeHtml(institution)}</strong> — ` : "";
  const trk =
    data.track === "custodiante"
      ? "trilha custodiante"
      : data.track === "corretora"
        ? "trilha corretora (intermediação e custódia)"
        : "fase intermediária";
  elSummary.innerHTML = `${nome}<strong>${na}</strong> inciso(s) no <strong>escopo de auditoria</strong> e <strong>${nf}</strong> <strong>fora deste escopo</strong> (matriz IN 701 · ${trk}).`;

  elMetrics.innerHTML = `
    <div class="metric kpi-card"><div class="metric-value">${na}</div><div class="metric-label">No escopo</div></div>
    <div class="metric kpi-card"><div class="metric-value">${mand}</div><div class="metric-label">Obrigatórios</div></div>
    <div class="metric kpi-card"><div class="metric-value">${cond}</div><div class="metric-label">Por respostas</div></div>
    <div class="metric metric--muted kpi-card"><div class="metric-value">${nf}</div><div class="metric-label">Fora do escopo</div></div>
  `;

  renderComplianceDonut(mand, cond, nf);

  elCountA.textContent = String(sujeitos.length);
  elCountS.textContent = String(fora.length);

  elLeadA.textContent =
    "Abra cada inciso: contexto, relatório BCB (indicativo) e checklist de evidências com perfil de entregável.";
  elLeadS.textContent =
    "Incisos excluídos nesta configuração — expanda para o motivo.";

  sessionStorage.removeItem(J2_PEDIDO_STORAGE_KEY);
  renderJourney2(data.journey_2);

  const cmap = buildChecklistMap(data.journey_2);
  let pedidoSeq = 0;
  const nextPedido = () => {
    pedidoSeq += 1;
    return pedidoSeq;
  };

  listA.innerHTML = "";
  listS.innerHTML = "";
  listA.classList.add("dash-audit-list");
  listS.classList.add("dash-skip-list");

  if (!sujeitos.length) {
    listA.innerHTML =
      '<p class="empty-col">Nenhum inciso no escopo. Se esperava linhas, confirme a versão da API (GET /api/v1/health).</p>';
  } else {
    sujeitos.forEach((row, i) => {
      if (!row || typeof row !== "object") return;
      const bloc = cmap.get(String(row.inciso_id || ""));
      listA.appendChild(renderDashAuditInciso(row, bloc, i, nextPedido));
    });
  }

  listS.appendChild(renderDashSkipContainer(fora));

  // #2: wrap skip cards in collapsible (closed by default)
  wireSkipToggle(nf);

  // store scope data for export (#10)
  state._lastScopeData = data;
  state._lastInstitution = ($("#institution").value || "").trim();

  setView("results");
  clearProgressStorage();
  requestAnimationFrame(() => {
    const body = $("#results-body");
    if (body) body.scrollIntoView({ behavior: "smooth", block: "start" });
  });
}

/** #2: wrap skip list in a collapsible panel */
function wireSkipToggle(nf) {
  const skipSection = document.querySelector(".results-section--skip");
  if (!skipSection) return;

  // idempotent — remove previous wrapper if re-running
  const existing = skipSection.querySelector(".skip-cards-wrap");
  if (existing) {
    const list = existing.querySelector(".inciso-card-list");
    if (list) skipSection.appendChild(list);
    existing.remove();
  }
  const oldToggle = skipSection.querySelector(".skip-section-toggle");
  if (oldToggle) oldToggle.remove();

  const cardList = skipSection.querySelector(".inciso-card-list");
  if (!cardList) return;

  // create wrapper
  const wrap = document.createElement("div");
  wrap.className = "skip-cards-wrap";
  cardList.parentNode.insertBefore(wrap, cardList);
  wrap.appendChild(cardList);

  // create toggle button
  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "skip-section-toggle";
  toggle.setAttribute("aria-expanded", "false");
  toggle.innerHTML = `<span class="skip-section-toggle__chevron">▸</span> Ver ${nf} inciso(s) excluído(s)`;

  const head = skipSection.querySelector(".results-section-head");
  if (head) head.appendChild(toggle);

  toggle.addEventListener("click", () => {
    const open = wrap.classList.toggle("is-open");
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
    toggle.innerHTML = open
      ? `<span class="skip-section-toggle__chevron">▸</span> Ocultar incisos excluídos`
      : `<span class="skip-section-toggle__chevron">▸</span> Ver ${nf} inciso(s) excluído(s)`;
  });
}

/** #10: export JSON download */
async function exportScopeJSON() {
  const btn = $("#btn-export-json");
  if (!btn) return;
  const data = state._lastScopeData;
  if (!data) {
    showToast("Execute o questionário antes de exportar.");
    return;
  }
  try {
    btn.classList.add("btn-export-loading");
    btn.textContent = "A exportar…";
    const payload = {
      institution: state._lastInstitution,
      track: state.track,
      answers: { ...state.answers },
    };
    let exportData;
    try {
      exportData = await fetchJSON("/scope/export", { method: "POST", body: JSON.stringify(payload) });
    } catch {
      // fallback: use the last scope response directly
      exportData = data;
    }
    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    const inst = (state._lastInstitution || "vasp").replace(/[^a-z0-9]/gi, "_").toLowerCase();
    a.download = `certik_vasp_scope_${inst}_${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
    showToast("Exportação JSON concluída.");
  } catch (e) {
    showToast("Erro ao exportar: " + String(e.message || e));
  } finally {
    if (btn) {
      btn.classList.remove("btn-export-loading");
      btn.textContent = "Exportar JSON";
    }
  }
}

async function loadFeaturesFromHealth() {
  try {
    const h = await fetch(`${apiBase()}/health`, { headers: { Accept: "application/json" } });
    if (!h.ok) return;
    const j = await h.json();
    const f = j.features || {};
    if (typeof f.custodiante_track === "boolean") {
      state.features.custodiante_track = f.custodiante_track;
    }
    if (typeof f.corretora_track === "boolean") {
      state.features.corretora_track = f.corretora_track;
    }
  } catch {
    /* offline / CORS — manter default */
  }
}

async function boot() {
  // Init i18n first (loads strings + restores saved language)
  await initI18n();

  // Mount language toggle in header
  const langMount = document.getElementById("lang-toggle-mount");
  if (langMount) langMount.appendChild(buildLangToggle());

  await loadFeaturesFromHealth();
  state.track = loadTrackFromStorage();
  if (state.features.custodiante_track === false && state.track === "custodiante") {
    state.track = "intermediaria";
    try {
      sessionStorage.setItem(TRACK_STORAGE_KEY, "intermediaria");
    } catch {
      /* ignore */
    }
  }
  if (state.features.corretora_track === false && state.track === "corretora") {
    state.track = "intermediaria";
    try {
      sessionStorage.setItem(TRACK_STORAGE_KEY, "intermediaria");
    } catch {
      /* ignore */
    }
  }
  syncTrackButtonsUI();

  wireDecisionTreeUI({
    setView,
    getTrack: () => state.track,
  });

  wireDocsGuideUI({
    btnOpen: $("#btn-open-docs-guide"),
    viewEl:  $("#docs-guide-view"),
    btnBack: $("#btn-dg-back"),
    getTrack: () => state.track,
    setView,
  });

  document.querySelectorAll(".intro-track__btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const trk = btn.getAttribute("data-track");
      if (trk !== "intermediaria" && trk !== "custodiante" && trk !== "corretora") return;
      state.track = trk;
      saveTrackToStorage();
      syncTrackButtonsUI();
    });
  });

  $("#btn-start").addEventListener("click", async () => {
    const inst = $("#institution");
    const name = (inst.value || "").trim();
    if (!name) {
      showToast("Indique o nome da sua empresa para continuar.");
      inst.focus();
      return;
    }
    let data;
    try {
      data = await fetchJSON(`/questions?track=${encodeURIComponent(state.track)}`);
    } catch (e) {
      showToast(
        String(e.message || e) +
          " — Confirme a API em /api/v1/questions?track=… (serve_web.py ou Vercel).",
      );
      return;
    }
    state.blocks = data.blocks || [];
    if (!state.blocks.length) {
      showToast("Nenhum bloco de perguntas retornado para esta trilha.");
      return;
    }
    if (data.track && data.track !== state.track) state.track = data.track;
    initAnswersFromBlocks();
    state.step = 0;
    setView("wizard");
    renderQuestions();
  });

  $("#btn-back").addEventListener("click", () => {
    if (state.step > 0) {
      state.step -= 1;
      renderQuestions("back"); // #5: slide back
    }
  });

  $("#btn-next").addEventListener("click", async () => {
    const block = state.blocks[state.step];
    normalizeBlockAnswers(block);
    if (blockHasUnansweredSingleChoice(block)) return;

    const last = state.step === state.blocks.length - 1;
    if (last) {
      try {
        await submitScope();
      } catch (e) {
        showToast(String(e.message || e));
      }
      return;
    }
    state.step += 1;
    renderQuestions("forward"); // #5
  });

  $("#btn-restart").addEventListener("click", () => {
    $("#institution").value = "";
    state.blocks = [];
    state.step = 0;
    state.track = "intermediaria";
    state._lastScopeData = null;
    try {
      sessionStorage.removeItem(TRACK_STORAGE_KEY);
    } catch {
      /* ignore */
    }
    clearProgressStorage();
    syncTrackButtonsUI();
    initAnswersFromBlocks();
    $("#journey-2-panel")?.classList.add("hidden");
    sessionStorage.removeItem(J2_PEDIDO_STORAGE_KEY);
    // check for saved session to show resume banner
    const saved = loadProgressFromStorage();
    if (saved && saved.answers && Object.keys(saved.answers).length > 0) showResumeBanner(saved);
    setView("intro");
  });

  // #10: export button
  const exportBtn = $("#btn-export-json");
  if (exportBtn) {
    exportBtn.addEventListener("click", () => exportScopeJSON());
  }

  // #9: resume banner logic
  const saved = loadProgressFromStorage();
  if (saved && saved.answers && Object.keys(saved.answers).length > 0) {
    showResumeBanner(saved);
  }

  document.getElementById("btn-resume")?.addEventListener("click", async () => {
    const prog = loadProgressFromStorage();
    if (!prog) return;
    const instEl = $("#institution");
    if (instEl && prog.institution) instEl.value = prog.institution;
    if (prog.track) {
      state.track = prog.track;
      saveTrackToStorage();
      syncTrackButtonsUI();
    }
    // fetch questions for track then restore answers
    let data;
    try {
      data = await fetchJSON(`/questions?track=${encodeURIComponent(state.track)}`);
    } catch (e) {
      showToast("Não foi possível retomar: " + String(e.message || e));
      return;
    }
    state.blocks = data.blocks || [];
    if (!state.blocks.length) { showToast("Sem blocos para retomar."); return; }
    initAnswersFromBlocks();
    // restore saved answers
    if (prog.answers) {
      for (const [k, v] of Object.entries(prog.answers)) {
        if (k in state.answers) state.answers[k] = v;
      }
    }
    state.step = Math.min(prog.step || 0, state.blocks.length - 1);
    document.getElementById("resume-banner")?.classList.add("hidden");
    setView("wizard");
    renderQuestions();
  });

  document.getElementById("btn-resume-dismiss")?.addEventListener("click", () => {
    clearProgressStorage();
    document.getElementById("resume-banner")?.classList.add("hidden");
  });
}

document.addEventListener("DOMContentLoaded", boot);
