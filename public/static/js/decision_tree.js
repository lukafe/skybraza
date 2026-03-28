/**
 * Árvore de decisão didática: perguntas × gatilhos × incisos (3 trilhas).
 * Dados: /static/data/decision_tree.json (gerado por scripts/export_decision_tree_data.py)
 */

const DT_JSON_VER = "1";

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
  if (!res.ok) throw new Error(`Ficheiro decision_tree.json indisponível (${res.status}). Execute python scripts/export_decision_tree_data.py`);
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
      alert(String(e?.message || e));
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
    const isInt = track === "intermediaria";
    noteSuppress.classList.toggle("hidden", !isInt);
    if (isInt && data.notes?.suppress_custody_intermediaria) {
      noteSuppress.innerHTML = `<p class="dt-suppress-text"><strong>Regra especial (intermediária):</strong> ${escapeHtml(data.notes.suppress_custody_intermediaria)}</p>`;
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

  blocksRoot.querySelectorAll(".dt-inciso-chip").forEach((chip) => {
    chip.addEventListener("click", (ev) => {
      ev.stopPropagation();
      showIncisoPopover(chip, cat);
    });
  });

  const f = $("#dt-filter");
  if (f && f.value) applyDtFilter(f.value);
}

/**
 * @param {Record<string, unknown>} q
 * @param {Record<string, {item?: string, artigo?: string}>} cat
 */
function renderQuestionCard(q, cat) {
  const id = escapeHtml(q.id);
  const typ = escapeHtml(q.type || "");
  const audit = q.audit_only ? `<span class="dt-badge dt-badge--audit">Só relatório / J2</span>` : `<span class="dt-badge dt-badge--scope">Pode alterar escopo</span>`;
  const text = escapeHtml(q.text || "");
  const why = escapeHtml(q.justificativa || "");

  const branches = (q.edges || [])
    .map((e) => {
      const cond = escapeHtml(e.condition || "");
      const incs = e.incisos || [];
      const note = e.note ? `<p class="dt-branch-note">${escapeHtml(e.note)}</p>` : "";
      const chips =
        incs.length > 0
          ? incs
              .map((inc) => {
                const meta = cat[inc] || {};
                const title = `${meta.item || inc} — ${meta.artigo || ""}`.trim();
                return `<button type="button" class="dt-inciso-chip" data-inciso="${escapeHtml(String(inc))}" title="${escapeHtml(title)}">${escapeHtml(String(inc))}</button>`;
              })
              .join("")
          : `<span class="dt-no-incisos">Nenhum inciso por esta ramificação</span>`;
      return `
        <div class="dt-branch">
          <div class="dt-branch-condition">${cond}</div>
          <div class="dt-branch-arrow" aria-hidden="true">→</div>
          <div class="dt-branch-target">${chips}</div>
          ${note}
        </div>`;
    })
    .join("");

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
        <p class="dt-q-why"><strong>Objetivo / ligação ao escopo:</strong> ${why || "—"}</p>
        <div class="dt-branches" role="group" aria-label="Gatilhos para incisos">
          ${branches}
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
    <button type="button" class="dt-popover-close" aria-label="Fechar">×</button>
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
