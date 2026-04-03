/**
 * Gap analysis — cruza escopo calculado × guia de documentos × mapa transfronteiriço.
 */

import { t, getCurrentLang } from "./i18n.js?v=3";
import { fetchMergedDocsGuide } from "./docs_guide.js?v=10";

function esc(s) {
  if (!s) return "";
  const d = document.createElement("div");
  d.textContent = String(s);
  return d.innerHTML;
}

let _cjMapGap = null;
async function loadCjMap() {
  if (_cjMapGap) return _cjMapGap;
  try {
    const res = await fetch("/static/data/cross_jurisdiction_map.json?v=2");
    if (!res.ok) throw new Error(String(res.status));
    _cjMapGap = await res.json();
  } catch {
    _cjMapGap = { mappings: [] };
  }
  return _cjMapGap;
}

function overlapBadgeKey(level) {
  const map = { high: "cj_badge_high", medium: "cj_badge_medium", low: "cj_badge_low", none: "cj_badge_none" };
  return map[level] || "cj_badge_none";
}

function csvCell(val) {
  const s = val == null ? "" : String(val);
  if (s.includes('"') || s.includes(",") || s.includes("\n") || s.includes("\r")) {
    return '"' + s.replace(/"/g, '""') + '"';
  }
  return s;
}

function exportGapCsv(rows, scopeData) {
  const en = getCurrentLang() === "en";
  const today = new Date().toISOString().slice(0, 10);
  const inst = String(scopeData?.institution ?? "").trim();
  const track = String(scopeData?.track ?? "");

  const L = en
    ? {
        institution: "Institution",
        track: "Track",
        clause: "Clause",
        label: "Label",
        theme: "Theme",
        docs: "Guide documents",
        critical: "Critical-priority docs",
        eu: "EU overlap",
        vara: "VARA overlap",
        adgm: "ADGM overlap",
      }
    : {
        institution: "Instituição",
        track: "Trilha",
        clause: "Inciso",
        label: "Rótulo",
        theme: "Tema",
        docs: "Documentos (guia)",
        critical: "Docs prioridade crítica",
        eu: "Sobreposição UE",
        vara: "Sobreposição VARA",
        adgm: "Sobreposição ADGM",
      };

  const HEADERS = [
    L.institution,
    L.track,
    L.clause,
    L.label,
    L.theme,
    L.docs,
    L.critical,
    L.eu,
    L.vara,
    L.adgm,
  ];

  const info = en
    ? [
        ["CertiK — Gap report (scope × document guide × CJ)", "", "", "", "", "", "", "", ""],
        ["Exported on", today, "", "", "", "", "", "", ""],
        ["Language", "English", "", "", "", "", "", "", ""],
      ]
    : [
        ["CertiK — Relatório de lacunas (escopo × guia × CJ)", "", "", "", "", "", "", "", ""],
        ["Exportado em", today, "", "", "", "", "", "", ""],
        ["Idioma", "Português", "", "", "", "", "", "", ""],
      ];

  const dataRows = rows.map((r) => [
    inst,
    track,
    r.id,
    r.rotulo,
    r.tema,
    String(r.nDocs),
    String(r.nCrit),
    t(overlapBadgeKey(r.overlaps.eu_mica)),
    t(overlapBadgeKey(r.overlaps.vara_dubai)),
    t(overlapBadgeKey(r.overlaps.adgm_abu_dhabi)),
  ]);

  const BOM = "\uFEFF";
  const all = [
    ...info.map((r) => r.map(csvCell).join(",")),
    HEADERS.map(csvCell).join(","),
    ...dataRows.map((r) => r.map(csvCell).join(",")),
  ];
  const csv = BOM + all.join("\r\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `certik_gap_analysis_${today}_${getCurrentLang()}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

const JUR_IDS = ["eu_mica", "vara_dubai", "adgm_abu_dhabi"];

/**
 * @param {Record<string, unknown>} scopeData — payload de POST /scope
 * @param {HTMLElement | null} mountEl
 */
export async function renderGapAnalysisPanel(scopeData, mountEl) {
  if (!mountEl) return;

  const sujeitos = scopeData?.incisos_sujeitos_auditoria;
  if (!Array.isArray(sujeitos) || !sujeitos.length) {
    mountEl.innerHTML = "";
    mountEl.hidden = true;
    return;
  }

  mountEl.hidden = false;
  mountEl.innerHTML = `<p class="gap-loading">${esc(t("ga_loading"))}</p>`;

  let guide;
  let cj;
  try {
    [guide, cj] = await Promise.all([fetchMergedDocsGuide(), loadCjMap()]);
  } catch {
    mountEl.innerHTML = `<p class="gap-error">${esc(t("ga_load_error"))}</p>`;
    return;
  }

  const byId = new Map((guide.incisos || []).map((i) => [i.id, i]));
  const mappings = cj.mappings || [];
  const en = getCurrentLang() === "en";

  const rows = [];
  let totalDocs = 0;
  let totalCrit = 0;
  let cjHigh = 0;
  let cjMedLow = 0;

  for (const row of sujeitos) {
    if (!row || typeof row !== "object") continue;
    const id = String(row.inciso_id || "");
    if (!id) continue;

    const inc = byId.get(id);
    const docs = inc?.documentos || [];
    const nDocs = docs.length;
    const nCrit = docs.filter((d) => d.prioridade === "critica").length;
    totalDocs += nDocs;
    totalCrit += nCrit;

    const m = mappings.find((x) => x.inciso_id === id);
    const overlaps = { eu_mica: "none", vara_dubai: "none", adgm_abu_dhabi: "none" };
    for (const jid of JUR_IDS) {
      const ov = m?.jurisdictions?.[jid]?.overlap || "none";
      overlaps[jid] = ov;
      if (ov === "high") cjHigh += 1;
      else if (ov === "medium" || ov === "low") cjMedLow += 1;
    }

    const rotulo = inc?.rotulo || id;
    const tema = en ? (inc?.tema_en || inc?.tema || "") : (inc?.tema || "");

    rows.push({ id, rotulo, tema, nDocs, nCrit, overlaps });
  }

  if (!rows.length) {
    mountEl.innerHTML = "";
    mountEl.hidden = true;
    return;
  }

  const thE = t("ga_col_eu");
  const thV = t("ga_col_vara");
  const thA = t("ga_col_adgm");

  const tableRows = rows
    .map(
      (r) => `
<tr>
  <td class="tabular-nums"><code>${esc(r.id)}</code></td>
  <td>${esc(r.rotulo)}</td>
  <td class="tabular-nums">${r.nDocs}</td>
  <td class="tabular-nums">${r.nCrit}</td>
  <td><span class="cj-overlap cj-overlap--${r.overlaps.eu_mica === "high" ? "high" : r.overlaps.eu_mica === "medium" ? "medium" : r.overlaps.eu_mica === "low" ? "low" : "none"}">${esc(t(overlapBadgeKey(r.overlaps.eu_mica)))}</span></td>
  <td><span class="cj-overlap cj-overlap--${r.overlaps.vara_dubai === "high" ? "high" : r.overlaps.vara_dubai === "medium" ? "medium" : r.overlaps.vara_dubai === "low" ? "low" : "none"}">${esc(t(overlapBadgeKey(r.overlaps.vara_dubai)))}</span></td>
  <td><span class="cj-overlap cj-overlap--${r.overlaps.adgm_abu_dhabi === "high" ? "high" : r.overlaps.adgm_abu_dhabi === "medium" ? "medium" : r.overlaps.adgm_abu_dhabi === "low" ? "low" : "none"}">${esc(t(overlapBadgeKey(r.overlaps.adgm_abu_dhabi)))}</span></td>
</tr>`,
    )
    .join("");

  mountEl.innerHTML = `
<details class="gap-panel" open>
  <summary class="gap-summary">${esc(t("ga_panel_title"))} <span class="gap-count">(${rows.length} ${esc(t("ga_panel_count"))})</span></summary>
  <div class="gap-body">
    <div class="gap-kpi-row">
      <span class="gap-kpi"><strong class="tabular-nums">${totalDocs}</strong> ${esc(t("ga_kpi_docs"))}</span>
      <span class="gap-kpi-sep">·</span>
      <span class="gap-kpi gap-kpi--crit"><strong class="tabular-nums">${totalCrit}</strong> ${esc(t("ga_kpi_crit"))}</span>
      <span class="gap-kpi-sep">·</span>
      <span class="gap-kpi"><strong class="tabular-nums">${cjHigh}</strong> ${esc(t("ga_kpi_cj_high"))}</span>
      <span class="gap-kpi-sep">·</span>
      <span class="gap-kpi"><strong class="tabular-nums">${cjMedLow}</strong> ${esc(t("ga_kpi_cj_adapt"))}</span>
    </div>
    <div class="gap-actions">
      <button type="button" class="btn btn-ghost" id="btn-gap-csv" title="${esc(t("ga_export_title"))}">${esc(t("ga_export_csv"))}</button>
    </div>
    <div class="gap-table-wrap">
      <table class="gap-table">
        <thead>
          <tr>
            <th scope="col">${esc(t("ga_col_clause"))}</th>
            <th scope="col">${esc(t("ga_col_label"))}</th>
            <th scope="col">${esc(t("ga_col_docs"))}</th>
            <th scope="col">${esc(t("ga_col_crit"))}</th>
            <th scope="col">${esc(thE)}</th>
            <th scope="col">${esc(thV)}</th>
            <th scope="col">${esc(thA)}</th>
          </tr>
        </thead>
        <tbody>${tableRows}</tbody>
      </table>
    </div>
    <p class="gap-tip">${esc(t("ga_tip"))}</p>
  </div>
</details>`;

  mountEl.querySelector("#btn-gap-csv")?.addEventListener("click", () => {
    exportGapCsv(rows, scopeData);
    document.dispatchEvent(new CustomEvent("app:toast", { detail: { msg: t("ga_csv_done"), kind: "success" } }));
  });
}
