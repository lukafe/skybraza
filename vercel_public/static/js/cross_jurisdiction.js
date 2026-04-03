/**
 * Cross-Jurisdiction Regulatory Comparison — IN 701 × MiCA / VARA / ADGM
 * Designed for Binance compliance workflow
 */

import { t, getCurrentLang } from "./i18n.js?v=3";

function esc(s) {
  if (!s) return "";
  const d = document.createElement("div");
  d.textContent = String(s);
  return d.innerHTML;
}

function pickBi(biObj) {
  if (!biObj) return "";
  return getCurrentLang() === "en" ? (biObj.en ?? biObj.pt ?? "") : (biObj.pt ?? biObj.en ?? "");
}

function overlapBadgeText(level) {
  const map = { high: "cj_badge_high", medium: "cj_badge_medium", low: "cj_badge_low", none: "cj_badge_none" };
  return t(map[level] || "cj_badge_none");
}

// ── CSV helpers ────────────────────────────────────────────────────────────────
function csvCell(val) {
  const s = val == null ? "" : String(val);
  if (s.includes('"') || s.includes(',') || s.includes('\n') || s.includes('\r')) {
    return '"' + s.replace(/"/g, '""') + '"';
  }
  return s;
}

function exportDeltaCsv(mappings, domains, jurisdictions, overlapFilter) {
  const lang = getCurrentLang();
  const en = lang === "en";
  const today = new Date().toISOString().slice(0, 10);
  const jurMap = {};
  for (const j of jurisdictions) if (j.id !== "bcb_in701") jurMap[j.id] = j;

  const L = en ? {
    type: "Type", clause: "Clause", label: "Label", domain: "Domain",
    bcb_ref: "BCB Reference", jurisdiction: "Jurisdiction", overlap: "Overlap",
    foreign_ref: "Foreign Reference", artefact: "Binance Artefact",
    delta: "Delta / Gap", action: "Action Required?", notes: "Auditor Notes"
  } : {
    type: "Tipo", clause: "Inciso", label: "Rótulo", domain: "Domínio",
    bcb_ref: "Referência BCB", jurisdiction: "Jurisdição", overlap: "Sobreposição",
    foreign_ref: "Referência Estrangeira", artefact: "Artefato Binance",
    delta: "Delta / Lacuna", action: "Ação Necessária?", notes: "Observações do Auditor"
  };

  const HEADERS = Object.values(L);
  const N = HEADERS.length;
  const blank = () => new Array(N).fill("").map(csvCell);

  const mkInfo = (label, value = "") => {
    const r = new Array(N).fill("");
    r[0] = "ℹ INFO"; r[1] = label; r[2] = value;
    return r.map(csvCell);
  };

  const totalMappings = mappings.length;
  let highCount = 0, medCount = 0, lowCount = 0;
  for (const m of mappings) {
    for (const jd of Object.values(m.jurisdictions || {})) {
      if (jd.overlap === "high") highCount++;
      else if (jd.overlap === "medium") medCount++;
      else lowCount++;
    }
  }

  const infoRows = [
    mkInfo(en ? "CertiK — Cross-Jurisdiction Delta Report" : "CertiK — Relatório Delta Transfronteiriço"),
    mkInfo(en ? "Exported on" : "Exportado em", today),
    mkInfo(en ? "Language" : "Idioma", en ? "English" : "Português"),
    mkInfo(en ? "Coverage" : "Cobertura",
      en ? `${totalMappings} clauses · ${highCount} high · ${medCount} medium · ${lowCount} low/none`
         : `${totalMappings} incisos · ${highCount} alta · ${medCount} média · ${lowCount} baixa/nenhuma`),
    mkInfo(en ? "Filter" : "Filtro",
      overlapFilter === "all" ? (en ? "All overlap levels" : "Todos os níveis") : overlapFilter),
    mkInfo(en ? "Row types" : "Tipos de linha",
      en ? "CLAUSE = IN 701 header | JURISDICTION = foreign mapping (fill last 2 cols)"
         : "INCISO = cabeçalho IN 701 | JURISDIÇÃO = mapeamento estrangeiro (preencha as 2 últimas colunas)"),
    blank(),
  ];

  const T_CLAUSE = en ? "CLAUSE" : "INCISO";
  const T_JUR = en ? "JURISDICTION" : "JURISDIÇÃO";

  const dataRows = [];
  for (const m of mappings) {
    const domainLabel = pickBi(domains[m.domain] || {});
    const rClause = new Array(N).fill("");
    rClause[0] = T_CLAUSE;
    rClause[1] = m.inciso_id;
    rClause[3] = domainLabel;
    rClause[4] = m.bcb_ref;
    dataRows.push(rClause.map(csvCell));

    const jurIds = ["eu_mica", "vara_dubai", "adgm_abu_dhabi"];
    for (const jid of jurIds) {
      const jd = (m.jurisdictions || {})[jid];
      if (!jd) continue;
      if (overlapFilter !== "all" && jd.overlap !== overlapFilter) continue;
      const jMeta = jurMap[jid];
      const delta = pickBi(jd.delta_notes);
      const r = new Array(N).fill("");
      r[0] = T_JUR;
      r[1] = m.inciso_id;
      r[5] = jMeta ? pickBi(jMeta.name) : jid;
      r[6] = jd.overlap.toUpperCase();
      r[7] = jd.ref;
      r[8] = jd.binance_artefact;
      r[9] = delta;
      dataRows.push(r.map(csvCell));
    }
    dataRows.push(blank());
  }

  const allRows = [...infoRows, HEADERS.map(csvCell), ...dataRows];
  const BOM = "\uFEFF";
  const csv = BOM + allRows.map(r => r.join(",")).join("\r\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `certik_cross_jurisdiction_delta_${today}_${lang}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

// ── Rendering ──────────────────────────────────────────────────────────────────
function renderIncisoRow(m, domains, jurisdictions, visibleJurs) {
  const domainLabel = pickBi(domains[m.domain] || {});
  const jurIds = ["eu_mica", "vara_dubai", "adgm_abu_dhabi"].filter(j => visibleJurs.has(j));
  const jurMap = {};
  for (const j of jurisdictions) jurMap[j.id] = j;

  const overlapBadges = jurIds.map(jid => {
    const jd = (m.jurisdictions || {})[jid];
    if (!jd) return "";
    const jMeta = jurMap[jid] || {};
    return `<span class="cj-overlap cj-overlap--${jd.overlap}" title="${esc(pickBi(jMeta.name))}">${jMeta.flag || ""} ${overlapBadgeText(jd.overlap)}</span>`;
  }).join("");

  const cards = jurIds.map(jid => {
    const jd = (m.jurisdictions || {})[jid];
    if (!jd) return "";
    const jMeta = jurMap[jid] || {};
    const delta = pickBi(jd.delta_notes);
    const deltaHtml = delta
      ? `<div class="cj-card-delta"><div class="cj-card-delta-label">${t("cj_delta_label")}</div>${esc(delta)}</div>`
      : "";
    return `
<div class="cj-card cj-card--${jd.overlap}" data-jur="${esc(jid)}" data-overlap="${jd.overlap}">
  <div class="cj-card-header">
    <span class="cj-card-flag">${jMeta.flag || ""}</span>
    <span class="cj-card-jur">${esc(pickBi(jMeta.name))}</span>
    <span class="cj-overlap cj-overlap--${jd.overlap}">${overlapBadgeText(jd.overlap)}</span>
  </div>
  <div class="cj-card-ref">${esc(jd.ref)}</div>
  <div class="cj-card-artefact">
    <div class="cj-card-artefact-label">${t("cj_artefact_label")}</div>
    ${esc(jd.binance_artefact)}
  </div>
  ${deltaHtml}
</div>`;
  }).join("");

  const searchParts = [m.inciso_id, domainLabel, m.bcb_ref];
  for (const jd of Object.values(m.jurisdictions || {})) {
    searchParts.push(jd.ref || "", jd.binance_artefact || "", jd.overlap || "");
    if (jd.delta_notes) searchParts.push(jd.delta_notes.pt || "", jd.delta_notes.en || "");
  }

  return `
<details class="cj-inciso" data-id="${esc(m.inciso_id)}" data-domain="${esc(m.domain)}"
  data-search="${esc(searchParts.join(' ').toLowerCase())}">
  <summary class="cj-inciso-summary">
    <span class="cj-chevron" aria-hidden="true">▸</span>
    <span class="cj-inc-id">${esc(m.inciso_id)}</span>
    <span class="cj-inc-domain">${esc(domainLabel)}</span>
    <span class="cj-inc-theme">${esc(m.bcb_ref)}</span>
    <span class="cj-inc-overlaps">${overlapBadges}</span>
  </summary>
  <div class="cj-inciso-body">
    <p class="cj-bcb-ref"><strong>${esc(t("cj_bcb_prefix"))}</strong> ${esc(m.bcb_ref)}</p>
    <div class="cj-grid">${cards}</div>
  </div>
</details>`;
}

// ── Main wiring ────────────────────────────────────────────────────────────────
export function wireCrossJurisdictionUI({ btnOpen, viewEl, btnBack, setView }) {
  if (!btnOpen || !viewEl) return;

  let mapData = null;
  let jurData = null;
  let rendered = false;

  async function loadData() {
    if (!mapData) {
      const res = await fetch("/static/data/cross_jurisdiction_map.json?v=2");
      if (!res.ok) throw new Error(`cross_jurisdiction_map: HTTP ${res.status}`);
      mapData = await res.json();
    }
    if (!jurData) {
      const res = await fetch("/static/data/jurisdictions.json?v=1");
      if (!res.ok) throw new Error(`jurisdictions: HTTP ${res.status}`);
      jurData = await res.json();
    }
  }

  async function renderView() {
    try {
      await loadData();
    } catch (e) {
      const body = viewEl.querySelector("#cj-body");
      if (body) body.innerHTML = `<p class="cj-loading">${esc(String(e.message || e))}</p>`;
      return;
    }

    const body = viewEl.querySelector("#cj-body");
    if (!body) return;

    const mappings = mapData.mappings || [];
    const domains = mapData.domains || {};
    const jurisdictions = jurData.jurisdictions || [];
    const foreignJurs = jurisdictions.filter(j => j.id !== "bcb_in701");

    // Jurisdiction toggles
    const togglesEl = viewEl.querySelector("#cj-jur-toggles");
    if (togglesEl && !rendered) {
      togglesEl.innerHTML = foreignJurs.map(j => `
        <label class="cj-jur-toggle">
          <input type="checkbox" value="${esc(j.id)}" checked />
          <span>${j.flag || ""} ${esc(pickBi(j.name).split("—")[0].trim())}</span>
        </label>
      `).join("");
    }

    const visibleJurs = new Set();
    togglesEl?.querySelectorAll("input:checked").forEach(cb => visibleJurs.add(cb.value));
    if (visibleJurs.size === 0) foreignJurs.forEach(j => visibleJurs.add(j.id));

    // Domain filter options — rebuild on every render so language switches are reflected
    const domainSelect = viewEl.querySelector("#cj-domain-filter");
    if (domainSelect) {
      const prevVal = domainSelect.value;
      while (domainSelect.options.length > 1) domainSelect.remove(1);
      domainSelect.options[0].textContent = t("cj_domain_all");
      for (const [key, val] of Object.entries(domains)) {
        const opt = document.createElement("option");
        opt.value = key;
        opt.textContent = pickBi(val);
        domainSelect.appendChild(opt);
      }
      domainSelect.value = prevVal;
    }

    // Refresh overlap filter labels on lang change
    const overlapSel = viewEl.querySelector("#cj-overlap-filter");
    if (overlapSel) {
      overlapSel.querySelectorAll("option[data-i18n]").forEach(opt => {
        opt.textContent = t(opt.getAttribute("data-i18n"));
      });
    }

    // Refresh jurisdiction toggle labels
    if (togglesEl) {
      togglesEl.querySelectorAll(".cj-jur-toggle span").forEach((span, i) => {
        const j = foreignJurs[i];
        if (j) span.textContent = `${j.flag || ""} ${pickBi(j.name).split("—")[0].trim()}`;
      });
    }

    // Stats
    let highTotal = 0, medTotal = 0, lowTotal = 0;
    for (const m of mappings) {
      for (const [jid, jd] of Object.entries(m.jurisdictions || {})) {
        if (!visibleJurs.has(jid)) continue;
        if (jd.overlap === "high") highTotal++;
        else if (jd.overlap === "medium") medTotal++;
        else lowTotal++;
      }
    }
    const statsEl = viewEl.querySelector("#cj-stats");
    if (statsEl) {
      statsEl.innerHTML = `
        <span class="cj-stat"><strong>${mappings.length}</strong> ${t("cj_stat_clauses")}</span>
        <span class="cj-stat-sep">·</span>
        <span class="cj-stat"><span class="cj-overlap cj-overlap--high">${highTotal}</span> ${t("cj_stat_high")}</span>
        <span class="cj-stat-sep">·</span>
        <span class="cj-stat"><span class="cj-overlap cj-overlap--medium">${medTotal}</span> ${t("cj_stat_medium")}</span>
        <span class="cj-stat-sep">·</span>
        <span class="cj-stat"><span class="cj-overlap cj-overlap--low">${lowTotal}</span> ${t("cj_stat_low")}</span>`;
    }

    // Render rows
    body.innerHTML = mappings.map(m => renderIncisoRow(m, domains, jurisdictions, visibleJurs)).join("");

    // Filters
    const searchEl = viewEl.querySelector("#cj-search");
    const overlapEl = viewEl.querySelector("#cj-overlap-filter");

    function doFilter() {
      const q = (searchEl?.value || "").trim().toLowerCase();
      const domainVal = domainSelect?.value || "all";
      const overlapVal = overlapEl?.value || "all";

      body.querySelectorAll(".cj-inciso").forEach(el => {
        const matchSearch = !q || (el.dataset.search || "").includes(q);
        const matchDomain = domainVal === "all" || el.dataset.domain === domainVal;

        let matchOverlap = true;
        if (overlapVal !== "all") {
          const cards = el.querySelectorAll(".cj-card");
          matchOverlap = Array.from(cards).some(c => c.dataset.overlap === overlapVal);
        }

        el.classList.toggle("cj-hidden", !(matchSearch && matchDomain && matchOverlap));
      });

      const visible = body.querySelectorAll(".cj-inciso:not(.cj-hidden)").length;
      const countEl = viewEl.querySelector("#cj-filter-count");
      if (countEl) countEl.textContent = `${visible} ${t("cj_of")} ${mappings.length}`;
    }

    if (!rendered) {
      searchEl?.addEventListener("input", doFilter);
      domainSelect?.addEventListener("change", doFilter);
      overlapEl?.addEventListener("change", doFilter);
      togglesEl?.addEventListener("change", () => { rendered = false; renderView(); });

      viewEl.querySelector("#cj-expand-all")?.addEventListener("click", () => {
        body.querySelectorAll(".cj-inciso:not(.cj-hidden)").forEach(el => { el.open = true; });
      });
      viewEl.querySelector("#cj-collapse-all")?.addEventListener("click", () => {
        body.querySelectorAll(".cj-inciso").forEach(el => { el.open = false; });
      });

      viewEl.querySelector("#cj-export-csv")?.addEventListener("click", () => {
        const overlapVal = overlapEl?.value || "all";
        exportDeltaCsv(mappings, domains, jurisdictions.filter(j => j.id !== "bcb_in701"), overlapVal);
        document.dispatchEvent(new CustomEvent("app:toast", {
          detail: { msg: t("cj_csv_done"), kind: "success" }
        }));
      });
    }

    rendered = true;
    doFilter();
  }

  btnOpen.addEventListener("click", () => {
    setView("crossJurisdiction");
    renderView();
  });

  if (btnBack) {
    btnBack.addEventListener("click", () => setView("intro"));
  }

  document.addEventListener("langchange", () => {
    if (!viewEl.classList.contains("hidden")) {
      rendered = false;
      renderView();
    } else {
      rendered = false;
    }
  });
}
