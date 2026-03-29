/**
 * Árvore de decisão didática: perguntas × gatilhos × incisos (3 trilhas).
 * Dados: /static/data/decision_tree.json (gerado por scripts/export_decision_tree_data.py)
 */

import { t } from "./i18n.js?v=2";

const DT_JSON_VER = "3";

/** @type {Record<string, unknown> | null} */
let _dtCache = null;

function $(sel, root = document) {
  return root.querySelector(sel);
}

function escapeHtml(s) {
  if (s == null) return "";
  const d = document.createElement("div");
  d.textContent = String(s);
  return d.innerHTML;
}

async function loadDecisionTreeData() {
  if (_dtCache) return _dtCache;
  const res = await fetch(`/static/data/decision_tree.json?v=${DT_JSON_VER}`);
  if (!res.ok) throw new Error(t("dt_load_error"));
  _dtCache = await res.json();
  return _dtCache;
}

const TRACK_ORDER = ["intermediaria", "custodiante", "corretora"];

/**
 * @param {object} opts
 * @param {(view: string) => void} opts.setView
 * @param {() => string} opts.getTrack
 */
export function wireDecisionTreeUI({ setView, getTrack }) {
  const btnOpen = $("#btn-open-decision-tree");
  const btnBack = $("#btn-dt-back");
  const root = $("#decision-tree-view");

  if (!btnOpen || !btnBack || !root) return;

  btnOpen.addEventListener("click", async () => {
    try {
      await loadDecisionTreeData();
      setView("decisionTree");
      const tr = getTrack();
      renderDecisionTree(tr);
    } catch (e) {
      document.dispatchEvent(new CustomEvent("app:toast", { detail: String(e?.message || e) }));
      btnOpen.focus();
    }
  });

  btnBack.addEventListener("click", () => {
    setView("intro");
  });

  const pills = $("#dt-track-pills");
  if (pills) {
    pills.addEventListener("click", (ev) => {
      const btn = ev.target.closest("[data-dt-track]");
      if (!btn) return;
      const t = btn.getAttribute("data-dt-track");
      if (!t) return;
      pills.querySelectorAll("[data-dt-track]").forEach((b) => {
        b.classList.toggle("dt-pill--active", b === btn);
        b.setAttribute("aria-selected", b === btn ? "true" : "false");
      });
      renderDecisionTree(t);
    });
  }

  const filter = $("#dt-filter");
  if (filter) {
    filter.addEventListener("input", () => applyDtFilter(filter.value || ""));
  }

  const ex = $("#dt-expand-all");
  const col = $("#dt-collapse-all");
  const rootBlocks = $("#dt-blocks-root");
  if (ex && rootBlocks) {
    ex.addEventListener("click", () => {
      rootBlocks.querySelectorAll("details.dt-q").forEach((d) => {
        d.open = true;
      });
    });
  }
  if (col && rootBlocks) {
    col.addEventListener("click", () => {
      rootBlocks.querySelectorAll("details.dt-q").forEach((d) => {
        d.open = false;
      });
      rootBlocks.querySelectorAll(".dt-flow-rail--focus").forEach((r) => r.classList.remove("dt-flow-rail--focus"));
    });
  }
}

/**
 * @param {string} track
 */
export async function renderDecisionTree(track) {
  const data = await loadDecisionTreeData();
  const tracks = data.tracks || {};
  const tdata = tracks[track];
  if (!tdata) return;

  const noteSuppress = $("#dt-note-suppress");
  if (noteSuppress) {
    const suppressText = data.notes?.suppress_custody_non_custodial;
    const showSuppress = Boolean(suppressText);
    noteSuppress.classList.toggle("hidden", !showSuppress);
    if (showSuppress) {
      noteSuppress.innerHTML = `<p class="dt-suppress-text"><strong>${t("dt_non_custodial_prefix")}</strong> ${escapeHtml(suppressText)}</p>`;
    }
  }

  const pills = $("#dt-track-pills");
  if (pills && !pills.dataset.built) {
    pills.innerHTML = TRACK_ORDER.map((tr) => {
      const td = tracks[tr];
      const lab = td?.label || tr;
      const active = tr === track;
      return `<button type="button" role="tab" class="dt-pill ${active ? "dt-pill--active" : ""}" data-dt-track="${escapeHtml(tr)}" aria-selected="${active}">${escapeHtml(lab.split("—")[0].trim())}</button>`;
    }).join("");
    pills.dataset.built = "1";
  } else if (pills) {
    pills.querySelectorAll("[data-dt-track]").forEach((b) => {
      const on = b.getAttribute("data-dt-track") === track;
      b.classList.toggle("dt-pill--active", on);
      b.setAttribute("aria-selected", on ? "true" : "false");
    });
  }

  const cat = tdata.incisos_catalog || {};
  const mand = tdata.mandatory_incisos || [];
  const mandHost = $("#dt-mandatory-chips");
  if (mandHost) {
    mandHost.innerHTML = mand
      .map((id) => {
        const meta = cat[id] || {};
        const title = `${meta.item || id} — ${meta.artigo || ""}`.trim();
        return `<button type="button" class="dt-inciso-chip dt-inciso-chip--mandatory" data-inciso="${escapeHtml(id)}" title="${escapeHtml(title)}">${escapeHtml(id)}</button>`;
      })
      .join("");
    mandHost.querySelectorAll(".dt-inciso-chip").forEach((chip) => {
      chip.addEventListener("click", (ev) => {
        ev.stopPropagation();
        showIncisoPopover(chip, cat);
      });
    });
  }

  const blocksRoot = $("#dt-blocks-root");
  if (!blocksRoot) return;

  const blocks = tdata.blocks || [];
  const blockMap = Object.fromEntries(blocks.map((b) => [b.id, b]));
  const questions = (tdata.questions || []).slice().sort((a, b) => {
    const ba = String(a.block || "");
    const bb = String(b.block || "");
    if (ba !== bb) return ba.localeCompare(bb);
    return (a.order || 0) - (b.order || 0);
  });

  /** @type {Record<string, typeof questions>} */
  const byBlock = {};
  for (const q of questions) {
    const bid = String(q.block || "Z");
    if (!byBlock[bid]) byBlock[bid] = [];
    byBlock[bid].push(q);
  }

  const blockOrder = blocks.map((b) => b.id);
  const html = [];
  for (const bid of blockOrder) {
    const qs = byBlock[bid];
    if (!qs?.length) continue;
    const bmeta = blockMap[bid] || { title: bid, lead: "" };
    html.push(`<section class="dt-block" data-dt-block="${escapeHtml(bid)}">`);
    html.push(`<h3 class="dt-block-title"><span class="dt-block-id">${escapeHtml(bid)}</span> ${escapeHtml(bmeta.title)}</h3>`);
    if (bmeta.lead) html.push(`<p class="dt-block-lead">${escapeHtml(bmeta.lead)}</p>`);
    html.push(`<div class="dt-questions">`);
    for (const q of qs) {
      html.push(renderQuestionCard(q, cat));
    }
    html.push(`</div></section>`);
  }

  blocksRoot.innerHTML = html.join("");

  blocksRoot.querySelectorAll(".dt-inciso-chip, .dt-flow-result-btn").forEach((chip) => {
    chip.addEventListener("click", (ev) => {
      ev.stopPropagation();
      showIncisoPopover(chip, cat);
    });
  });

  wireFlowRailUX(blocksRoot);

  const f = $("#dt-filter");
  if (f && f.value) applyDtFilter(f.value);
}

/**
 * Ramos clicáveis: realce fixo (toggle); teclado Enter/Espaço.
 * @param {HTMLElement} host
 */
function wireFlowRailUX(host) {
  host.querySelectorAll(".dt-flow-rail").forEach((rail) => {
    rail.setAttribute("tabindex", "0");
    if (!rail.getAttribute("aria-label")) {
      rail.setAttribute("aria-label", t("dt_branch_aria"));
    }
    rail.addEventListener("click", (ev) => {
      if (ev.target.closest("button")) return;
      const was = rail.classList.contains("dt-flow-rail--focus");
      host.querySelectorAll(".dt-flow-rail--focus").forEach((r) => r.classList.remove("dt-flow-rail--focus"));
      if (!was) rail.classList.add("dt-flow-rail--focus");
    });
    rail.addEventListener("keydown", (ev) => {
      if (ev.key !== "Enter" && ev.key !== " ") return;
      ev.preventDefault();
      rail.click();
    });
  });
}

/**
 * Subtítulo curto para a aresta (estilo «Descrição» sob «Decisão A»).
 * @param {Record<string, unknown>} e
 * @param {string} whyPlain
 */
function edgeSubtitle(e, whyPlain) {
  const n = String(e.note || "").trim();
  if (n) return n.length > 100 ? `${n.slice(0, 97)}…` : n;
  if (whyPlain) return whyPlain.length > 90 ? `${whyPlain.slice(0, 87)}…` : whyPlain;
  return t("dt_branch_default");
}

/**
 * Diagrama horizontal: raiz cinza → ramos com rótulo → círculo azul → triângulos laranja (incisos).
 * @param {Record<string, unknown>} q
 * @param {Record<string, {item?: string, artigo?: string}>} cat
 */
function renderFlowDiagramHTML(q, cat) {
  const edges = Array.isArray(q.edges) ? q.edges : [];
  const id = escapeHtml(String(q.id));
  const whyPlain = String(q.justificativa || "").replace(/\s+/g, " ").trim();

  const rails = edges
    .map((e) => {
      const cond = escapeHtml(String(e.condition || "—"));
      const sub = escapeHtml(edgeSubtitle(e, whyPlain));
      const incs = Array.isArray(e.incisos) ? e.incisos : [];
      const noteHtml =
        incs.length > 0 && e.note
          ? `<p class="dt-flow-rail-footnote">${escapeHtml(String(e.note))}</p>`
          : "";

      let outcomesHtml;
      if (incs.length > 0) {
        outcomesHtml = incs
          .map((inc) => {
            const sid = String(inc);
            const meta = cat[sid] || {};
            const title = `${meta.item || sid} — ${meta.artigo || ""}`.trim();
            return `<div class="dt-flow-outcome">
              <span class="dt-flow-h-line" aria-hidden="true"></span>
              <span class="dt-flow-triangle" aria-hidden="true"></span>
              <button type="button" class="dt-inciso-chip dt-flow-result-btn" data-inciso="${escapeHtml(sid)}" title="${escapeHtml(title)}">${escapeHtml(sid)}</button>
            </div>`;
          })
          .join("");
      } else {
        const emptyLabel = e.note
          ? escapeHtml(String(e.note).slice(0, 120)) + (String(e.note).length > 120 ? "…" : "")
          : t("dt_no_clauses");
        outcomesHtml = `<div class="dt-flow-outcome dt-flow-outcome--empty">
            <span class="dt-flow-h-line" aria-hidden="true"></span>
            <span class="dt-flow-triangle dt-flow-triangle--muted" aria-hidden="true"></span>
            <span class="dt-flow-result-text">${emptyLabel}</span>
          </div>`;
      }

      return `<div class="dt-flow-rail">
        <div class="dt-flow-rail-head">
          <div class="dt-flow-edge-labels">
            <span class="dt-flow-lbl-main">${cond}</span>
            <span class="dt-flow-lbl-sub">${sub}</span>
          </div>
          <div class="dt-flow-rail-track">
            <div class="dt-flow-line-diag-wrap" aria-hidden="true">
              <div class="dt-flow-line-diag"></div>
            </div>
            <div class="dt-flow-node-circle" title="${t("dt_decision_point")}"></div>
          </div>
        </div>
        <div class="dt-flow-rail-tail">
          <div class="dt-flow-outcomes">${outcomesHtml}</div>
          ${noteHtml}
        </div>
      </div>`;
    })
    .join("");

  return `<div class="dt-flow-canvas" role="region" aria-label="${t("dt_diagram_aria")}">
    <ul class="dt-flow-micro-legend">
      <li><span class="dt-micro-ico dt-micro-ico--bar" aria-hidden="true"></span> ${t("dt_micro_bar")}</li>
      <li><span class="dt-micro-ico dt-micro-ico--dot" aria-hidden="true"></span> ${t("dt_micro_dot")}</li>
      <li><span class="dt-micro-ico dt-micro-ico--tri" aria-hidden="true"></span> ${t("dt_micro_tri")}</li>
    </ul>
    <div class="dt-flow-h-rail">
      <div class="dt-flow-root" title="${t("dt_decision_point")}">
        <span class="dt-flow-root-label">${id}</span>
      </div>
      <div class="dt-flow-rails">${rails}</div>
    </div>
  </div>`;
}

/**
 * @param {Record<string, unknown>} q
 * @param {Record<string, {item?: string, artigo?: string}>} cat
 */
function renderQuestionCard(q, cat) {
  const id = escapeHtml(q.id);
  const typ = escapeHtml(q.type || "");
  const audit = q.audit_only ? `<span class="dt-badge dt-badge--audit">${t("dt_badge_audit")}</span>` : `<span class="dt-badge dt-badge--scope">${t("dt_badge_scope")}</span>`;
  const text = escapeHtml(q.text || "");
  const why = escapeHtml(q.justificativa || "");

  const flowHtml = renderFlowDiagramHTML(q, cat);

  const searchPlain = `${q.id} ${String(q.text || "").replace(/\s+/g, " ")}`.trim().toLowerCase();
  return `
    <details class="dt-q" data-dt-qid="${id}" data-search-enc="${encodeURIComponent(searchPlain)}">
      <summary class="dt-q-summary">
        <span class="dt-q-chevron" aria-hidden="true"></span>
        <span class="dt-q-id">${id}</span>
        <span class="dt-q-type">${typ}</span>
        ${audit}
        <span class="dt-q-preview">${text.slice(0, 120)}${text.length > 120 ? "…" : ""}</span>
      </summary>
      <div class="dt-q-body">
        <p class="dt-q-text">${text}</p>
        <p class="dt-q-why"><strong>${t("dt_scope_link")}</strong> ${why || "—"}</p>
        <div class="dt-flow-wrap" role="group" aria-label="${t("dt_trigger_map_aria")}">
          ${flowHtml}
        </div>
      </div>
    </details>`;
}

function applyDtFilter(raw) {
  const q = raw.trim().toLowerCase();
  document.querySelectorAll(".dt-q").forEach((el) => {
    let hay = "";
    try {
      hay = decodeURIComponent(el.getAttribute("data-search-enc") || "").toLowerCase();
    } catch {
      hay = "";
    }
    el.classList.toggle("hidden", q.length > 0 && !hay.includes(q));
  });
  document.querySelectorAll(".dt-block").forEach((block) => {
    const any = block.querySelector(".dt-q:not(.hidden)");
    block.classList.toggle("hidden", q.length > 0 && !any);
  });
}

/**
 * @param {HTMLElement} chip
 * @param {Record<string, {item?: string, artigo?: string}>} cat
 */
function showIncisoPopover(chip, cat) {
  const id = chip.getAttribute("data-inciso");
  if (!id) return;
  const meta = cat[id] || {};
  const old = document.querySelector(".dt-popover");
  if (old) old.remove();

  const pop = document.createElement("div");
  pop.className = "dt-popover";
  pop.setAttribute("role", "tooltip");
  pop.innerHTML = `
    <button type="button" class="dt-popover-close" aria-label="${t("dt_popover_close")}">×</button>
    <p class="dt-popover-id">${escapeHtml(id)}</p>
    <p class="dt-popover-item">${escapeHtml(meta.item || "")}</p>
    <p class="dt-popover-art">${escapeHtml(meta.artigo || "")}</p>
  `;
  document.body.appendChild(pop);
  pop.addEventListener("click", (ev) => ev.stopPropagation());

  const r = chip.getBoundingClientRect();
  pop.style.left = `${Math.min(Math.max(8, r.left), window.innerWidth - 300)}px`;
  pop.style.top = `${r.bottom + 8 + window.scrollY}px`;

  const close = () => pop.remove();
  pop.querySelector(".dt-popover-close")?.addEventListener("click", close);
  setTimeout(() => document.addEventListener("click", close, { once: true }), 50);
}
