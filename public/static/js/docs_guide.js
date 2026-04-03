/**
 * Guia de Documentos — IN 701 por inciso
 * Consome /static/data/docs_guide.json + docs_guide_en.json para i18n
 */

import { t, getCurrentLang } from "./i18n.js?v=3";

let _cjMapCache = null;
async function loadCjMap() {
  if (_cjMapCache) return _cjMapCache;
  try {
    const res = await fetch("/static/data/cross_jurisdiction_map.json?v=2");
    if (!res.ok) throw new Error(res.status);
    _cjMapCache = await res.json();
  } catch { _cjMapCache = { mappings: [] }; }
  return _cjMapCache;
}

function cjBadgesHtml(incisoId) {
  if (!_cjMapCache) return "";
  const m = (_cjMapCache.mappings || []).find(entry => entry.inciso_id === incisoId);
  if (!m) return "";
  const jurLabels = { eu_mica: "EU", vara_dubai: "VARA", adgm_abu_dhabi: "ADGM" };
  const badges = [];
  for (const [jid, jd] of Object.entries(m.jurisdictions || {})) {
    if (jd.overlap === "high" || jd.overlap === "medium") {
      const cls = jd.overlap === "high" ? "cj-overlap--high" : "cj-overlap--medium";
      badges.push(`<span class="cj-overlap ${cls}" title="${jd.ref}">${jurLabels[jid] || jid}</span>`);
    }
  }
  return badges.length ? `<span class="dg-cj-badges">${badges.join("")}</span>` : "";
}

const CAT_ICONS = {
  politica:     "📋",
  procedimento: "⚙️",
  relatorio:    "📊",
  contrato:     "📄",
  diagrama:     "🗺️",
  evidencia:    "🔍",
  certificacao: "🏆",
  treinamento:  "🎓",
};

function esc(s) {
  if (!s) return "";
  const d = document.createElement("div");
  d.textContent = String(s);
  return d.innerHTML;
}

/** Pick PT or EN field from an object (inline _en suffix or EN translations merged) */
function pick(obj, field) {
  if (!obj) return "";
  const lang = getCurrentLang();
  if (lang === "en") {
    if (obj[`${field}_en`] !== undefined) return obj[`${field}_en`] ?? "";
  }
  return obj[field] ?? "";
}

/** Merge English translations (docs_guide_en.json) into the inciso data objects */
function mergeEnTranslations(incisos, enData) {
  if (!enData || !enData.incisos) return incisos;
  return incisos.map((inc) => {
    const enInc = enData.incisos[inc.id];
    if (!enInc) return inc;
    // build merged document list
    const docsOut = (inc.documentos || []).map((doc) => {
      const enDoc = enInc.documentos?.[doc.id];
      if (!enDoc) return doc;
      return {
        ...doc,
        titulo_en:            enDoc.titulo            ?? doc.titulo,
        descricao_en:         enDoc.descricao         ?? doc.descricao,
        justificativa_legal_en: enDoc.justificativa_legal ?? doc.justificativa_legal,
        conteudo_minimo_en:   enDoc.conteudo_minimo   ?? doc.conteudo_minimo,
        retencao_en:          enDoc.retencao          ?? doc.retencao,
        certik_nota_en:       enDoc.certik_nota       ?? doc.certik_nota,
      };
    });
    const roOut = inc.resposta_otima
      ? {
          ...inc.resposta_otima,
          descricao_en:   enInc.resposta_otima?.descricao  ?? inc.resposta_otima?.descricao,
          indicadores_en: enInc.resposta_otima?.indicadores ?? inc.resposta_otima?.indicadores,
        }
      : inc.resposta_otima;
    return {
      ...inc,
      tema_en:    enInc.tema    ?? inc.tema,
      resumo_en:  enInc.resumo  ?? inc.resumo,
      gatilho_en: enInc.gatilho ?? inc.gatilho,
      documentos: docsOut,
      resposta_otima: roOut,
    };
  });
}

/** Merge English category/priority/certik_servicos from enData into meta */
function mergeEnMeta(meta, enData) {
  if (!enData || !meta) return meta;
  const out = { ...meta };
  // categorias labels
  if (enData.categorias && meta.categorias) {
    const cats = {};
    for (const [k, v] of Object.entries(meta.categorias)) {
      cats[k] = { ...v, label_en: enData.categorias[k]?.label ?? v.label };
    }
    out.categorias = cats;
  }
  // prioridades
  if (enData.prioridades && meta.prioridades) {
    const prios = {};
    for (const [k, v] of Object.entries(meta.prioridades)) {
      prios[k] = { ...v, descricao_en: enData.prioridades[k] ?? (typeof v === "string" ? v : v.descricao) };
    }
    out.prioridades = prios;
  }
  // certik_servicos
  if (enData.certik_servicos && meta.certik_servicos) {
    const svcs = {};
    for (const [k, v] of Object.entries(meta.certik_servicos)) {
      svcs[k] = {
        ...v,
        nome_en:     enData.certik_servicos[k]?.nome     ?? v.nome,
        descricao_en: enData.certik_servicos[k]?.descricao ?? v.descricao,
      };
    }
    out.certik_servicos = svcs;
  }
  return out;
}

let _mergedGuideCache = null;

/**
 * Guia de documentos com traduções EN fundidas (cache por sessão do módulo).
 * @returns {Promise<{ incisos: any[]; meta: any }>}
 */
export async function fetchMergedDocsGuide() {
  if (_mergedGuideCache) return _mergedGuideCache;
  const res = await fetch("/static/data/docs_guide.json?v=1");
  if (!res.ok) throw new Error(`docs_guide: HTTP ${res.status}`);
  const guideData = await res.json();
  let enData = null;
  try {
    const enRes = await fetch("/static/data/docs_guide_en.json?v=1");
    if (enRes.ok) enData = await enRes.json();
  } catch {
    /* EN overlay opcional */
  }
  const meta = mergeEnMeta(guideData.meta || {}, enData);
  const incisos = mergeEnTranslations(guideData.incisos || [], enData);
  _mergedGuideCache = { incisos, meta };
  return _mergedGuideCache;
}

/** Renderiza o badge CertiK para um documento */
function renderCertikBadge(doc, certikServicos) {
  if (!doc.certik_servico) return "";
  const svc = certikServicos?.[doc.certik_servico] || {};
  const nome = getCurrentLang() === "en" ? (svc.nome_en || svc.nome || doc.certik_servico) : (svc.nome || doc.certik_servico);
  const url  = svc.url || "https://www.certik.com";
  const notaRaw = pick(doc, "certik_nota");
  const nota = notaRaw ? `<p class="dg-certik-nota">${esc(notaRaw)}</p>` : "";
  return `
<div class="dg-certik-block">
  <div class="dg-certik-badge">
    <span class="dg-certik-logo" aria-hidden="true">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
        <path d="M12 2L3 7v5c0 5.25 3.75 10.15 9 11.35C17.25 22.15 21 17.25 21 12V7L12 2z" fill="currentColor" opacity="0.9"/>
        <path d="M9 12l2 2 4-4" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
    </span>
    <span class="dg-certik-label">${t("dg_certik_label")}</span>
    <a href="${esc(url)}" target="_blank" rel="noopener noreferrer" class="dg-certik-service">${esc(nome)} ↗</a>
  </div>
  ${nota}
</div>`;
}

/** Renderiza um documento individual dentro do accordion do inciso */
function renderDocCard(doc, meta) {
  const lang = getCurrentLang();
  const catMeta = meta.categorias?.[doc.categoria] || {};
  const catLabel = lang === "en" ? (catMeta.label_en || catMeta.label || doc.categoria) : (catMeta.label || doc.categoria);
  const icon = CAT_ICONS[doc.categoria] || "📁";

  const prioLabel = t(`prio_${doc.prioridade}`);
  const prioCls = doc.prioridade === "critica" ? "dg-prio--critica" : doc.prioridade === "alta" ? "dg-prio--alta" : "dg-prio--media";

  const prioTitle = (() => {
    const v = meta.prioridades?.[doc.prioridade];
    if (!v) return "";
    if (lang === "en") return typeof v === "object" ? (v.descricao_en || v.descricao || "") : String(v);
    return typeof v === "object" ? (v.descricao || "") : String(v);
  })();

  const conteudoItems = pick(doc, "conteudo_minimo");
  const conteudo = Array.isArray(conteudoItems)
    ? conteudoItems.map((c) => `<li>${esc(c)}</li>`).join("")
    : "";
  const hasCertik = !!doc.certik_servico;
  const titulo   = pick(doc, "titulo");
  const descricao = pick(doc, "descricao");
  const justif   = pick(doc, "justificativa_legal");
  const retencao = pick(doc, "retencao");

  return `
<div class="dg-doc-card dg-doc-card--${esc(doc.prioridade)}${hasCertik ? " dg-doc-card--certik" : ""}">
  <div class="dg-doc-header">
    <span class="dg-doc-icon" aria-hidden="true">${icon}</span>
    <span class="dg-doc-titulo">${esc(titulo)}</span>
    <span class="dg-prio-badge ${prioCls}" title="${esc(prioLabel)} — ${esc(prioTitle)}">${esc(prioLabel)}</span>
    ${doc.categoria ? `<span class="dg-cat-badge" style="background: ${esc(catMeta.cor || "#555")}22; border-color: ${esc(catMeta.cor || "#555")}55; color: ${esc(catMeta.cor || "#999")}">${esc(catLabel)}</span>` : ""}
  </div>
  ${renderCertikBadge(doc, meta.certik_servicos)}
  <p class="dg-doc-descricao">${esc(descricao)}</p>
  <details class="dg-doc-detail">
    <summary class="dg-doc-detail-summary">
      <span class="dg-doc-detail-toggle">${t("dg_justify_toggle")}</span>
    </summary>
    <p class="dg-doc-justificativa">${esc(justif)}</p>
  </details>
  ${conteudo ? `
  <details class="dg-doc-detail">
    <summary class="dg-doc-detail-summary">
      <span class="dg-doc-detail-toggle">${t("dg_content_toggle")}</span>
    </summary>
    <ul class="dg-conteudo-list">${conteudo}</ul>
  </details>` : ""}
  ${retencao ? `<p class="dg-retencao">${t("dg_retention")} <strong>${esc(retencao)}</strong></p>` : ""}
</div>`;
}

/** Renderiza o bloco de resposta ótima */
function renderRespostaOtima(ro) {
  if (!ro) return "";
  const descricao = pick(ro, "descricao");
  const indicadoresRaw = pick(ro, "indicadores");
  const items = Array.isArray(indicadoresRaw)
    ? indicadoresRaw.map((i) => `<li>${esc(i)}</li>`).join("")
    : "";
  return `
<div class="dg-otima">
  <div class="dg-otima-header">
    <span class="dg-otima-icon" aria-hidden="true">⭐</span>
    <span class="dg-otima-label">${t("dg_optimal_label")}</span>
  </div>
  <p class="dg-otima-desc">${esc(descricao)}</p>
  ${items ? `
  <div class="dg-otima-indicadores-label">${t("dg_optimal_indicators")}</div>
  <ul class="dg-otima-indicadores">${items}</ul>` : ""}
</div>`;
}

/** Renderiza um card de inciso completo */
function renderIncisoCard(inciso, meta) {
  const docsHtml = (inciso.documentos || [])
    .map((d) => renderDocCard(d, meta))
    .join("");
  const baseLegal = Array.isArray(inciso.base_legal)
    ? inciso.base_legal.map((b) => `<span class="dg-base-pill">${esc(b)}</span>`).join("")
    : "";
  const totalDocs = inciso.documentos?.length || 0;
  const criticos  = inciso.documentos?.filter((d) => d.prioridade === "critica").length || 0;

  const docsLabel = totalDocs === 1 ? t("dg_docs_label", { n: totalDocs }) : t("dg_docs_label_plural", { n: totalDocs });
  const critLabel = criticos === 1  ? t("dg_critico_label", { n: criticos }) : t("dg_critico_label_plural", { n: criticos });

  const tema    = pick(inciso, "tema");
  const resumo  = pick(inciso, "resumo");
  const gatilho = pick(inciso, "gatilho");

  return `
<details class="dg-inciso" id="dg-inc-${esc(inciso.id)}" data-inciso-id="${esc(inciso.id)}"
  data-tema="${esc(tema)}" data-resumo="${esc(resumo)}" data-rotulo="${esc(inciso.rotulo)}">
  <summary class="dg-inciso-summary">
    <span class="dg-inc-chevron" aria-hidden="true">▸</span>
    <span class="dg-inc-rotulo">${esc(inciso.rotulo)}</span>
    <div class="dg-inc-info">
      <span class="dg-inc-tema">${esc(tema)}</span>
      <span class="dg-inc-art">${esc(inciso.artigo_in701)}</span>
    </div>
    <div class="dg-inc-badges">
      <span class="dg-inc-badge dg-inc-badge--docs" title="${esc(docsLabel)}">${esc(docsLabel)}</span>
      ${criticos > 0 ? `<span class="dg-inc-badge dg-inc-badge--critico" title="${esc(critLabel)}">${esc(critLabel)}</span>` : ""}
      ${cjBadgesHtml(inciso.id)}
    </div>
  </summary>
  <div class="dg-inciso-body">
    <div class="dg-inciso-meta">
      <p class="dg-resumo">${esc(resumo)}</p>
      ${gatilho ? `<p class="dg-gatilho"><strong>${t("dg_gatilho")}</strong> ${esc(gatilho)}</p>` : ""}
      <div class="dg-base-legal">${baseLegal}</div>
    </div>
    <h4 class="dg-docs-section-title">${t("dg_docs_section_title")}</h4>
    <div class="dg-docs-list">${docsHtml}</div>
    ${renderRespostaOtima(inciso.resposta_otima)}
  </div>
</details>`;
}

/** Filtra os incisos visíveis com base no texto de pesquisa, prioridade e flag certik */
function applyGuideFilter(root, searchVal, prioVal, certikOnly) {
  const q = searchVal.trim().toLowerCase();
  root.querySelectorAll(".dg-inciso").forEach((el) => {
    const id     = el.dataset.incisoId || "";
    const tema   = el.dataset.tema   || "";
    const resumo = el.dataset.resumo || "";
    const rotulo = el.dataset.rotulo || "";
    const matchSearch = !q ||
      id.toLowerCase().includes(q) ||
      tema.toLowerCase().includes(q) ||
      resumo.toLowerCase().includes(q) ||
      rotulo.toLowerCase().includes(q);

    let matchPrio = true;
    if (prioVal && prioVal !== "all") {
      const docs = el.querySelectorAll(".dg-doc-card");
      matchPrio = Array.from(docs).some((dc) => dc.classList.contains(`dg-doc-card--${prioVal}`));
    }

    let matchCertik = true;
    if (certikOnly) {
      matchCertik = el.querySelector(".dg-doc-card--certik") !== null;
    }

    el.classList.toggle("dg-hidden", !(matchSearch && matchPrio && matchCertik));
  });
}

/** RFC 4180 CSV cell escaping */
function csvCell(val) {
  const s = val == null ? "" : String(val);
  if (s.includes('"') || s.includes(',') || s.includes('\n') || s.includes('\r')) {
    return '"' + s.replace(/"/g, '""') + '"';
  }
  return s;
}

/**
 * Build and download a well-structured CSV from the merged guide data.
 *
 * Structure:
 *   ─ Metadata block (INFO rows)  ← explanatory header before the table
 *   ─ Blank separator row
 *   ─ Column headers row
 *   ─ For each inciso:
 *       • INCISO row  — clause-level data + optimal response summary
 *       • DOCUMENTO rows (one per required document) + empty checklist cols
 *       • RESPOSTA ÓTIMA row — full optimal response + excellence indicators
 *       • Blank separator row
 */
function exportDocsGuideCsv(incisos, meta) {
  const lang = getCurrentLang();
  const en   = lang === "en";
  const today = new Date().toISOString().slice(0, 10);

  // ── Column labels ────────────────────────────────────────────────────────────
  const L = en ? {
    type:        "Type",
    clause:      "Clause",
    label:       "Label",
    article:     "IN 701 Art.",
    theme:       "Theme",
    summary:     "Summary",
    legal_basis: "Legal Basis",
    trigger:     "Trigger",
    seq:         "No.",
    doc_id:      "Document ID",
    doc_title:   "Document Title",
    priority:    "Priority",
    category:    "Category",
    certik:      "CertiK Service",
    description: "Description",
    content:     "Minimum Content  (items separated by  |)",
    justif:      "Legal Justification",
    retention:   "Retention",
    opt_desc:    "Optimal Response — Description",
    opt_ind:     "Optimal Response — Excellence Indicators  (items separated by  |)",
    gathered:    "✓ Gathered?",
    notes:       "Auditor Notes",
  } : {
    type:        "Tipo",
    clause:      "Inciso",
    label:       "Rótulo",
    article:     "Art. IN 701",
    theme:       "Tema",
    summary:     "Resumo",
    legal_basis: "Base Legal",
    trigger:     "Gatilho",
    seq:         "Nº",
    doc_id:      "ID Documento",
    doc_title:   "Título do Documento",
    priority:    "Prioridade",
    category:    "Categoria",
    certik:      "Serviço CertiK",
    description: "Descrição",
    content:     "Conteúdo Mínimo  (itens separados por  |)",
    justif:      "Justificativa Legal",
    retention:   "Retenção",
    opt_desc:    "Resposta Ótima — Descrição",
    opt_ind:     "Resposta Ótima — Indicadores de Excelência  (itens separados por  |)",
    gathered:    "✓ Recolhido?",
    notes:       "Observações do Auditor",
  };

  const HEADERS = Object.values(L);
  const N = HEADERS.length; // 22 columns

  // ── Row builders ─────────────────────────────────────────────────────────────
  const blank = () => new Array(N).fill("").map(csvCell);

  const mkInfo = (label, value = "") => {
    const r = new Array(N).fill("");
    r[0] = en ? "ℹ INFO" : "ℹ INFO";
    r[1] = label;
    r[2] = value;
    return r.map(csvCell);
  };

  // ── Lookup helpers ────────────────────────────────────────────────────────────
  const catLabel = (catKey) => {
    const m = meta.categorias?.[catKey] || {};
    return en ? (m.label_en || m.label || catKey) : (m.label || catKey);
  };
  const prioLabel = (prioKey) => t(`prio_${prioKey}`) || prioKey;
  const certikName = (svcKey) => {
    if (!svcKey) return "";
    const svc = meta.certik_servicos?.[svcKey] || {};
    return en ? (svc.nome_en || svc.nome || svcKey) : (svc.nome || svcKey);
  };

  // ── Stats for INFO block ──────────────────────────────────────────────────────
  const totalDocs     = incisos.reduce((s, i) => s + (i.documentos?.length || 0), 0);
  const totalCriticos = incisos.reduce((s, i) =>
    s + (i.documentos?.filter(d => d.prioridade === "critica").length || 0), 0);
  const totalCertik   = incisos.reduce((s, i) =>
    s + (i.documentos?.filter(d => d.certik_servico).length || 0), 0);

  // ── INFO block (before headers) ───────────────────────────────────────────────
  const infoRows = [
    mkInfo(en ? "CertiK — Document Guide  IN 701" : "CertiK — Guia de Documentos  IN 701"),
    mkInfo(en ? "Exported on" : "Exportado em", today),
    mkInfo(en ? "Language" : "Idioma", en ? "English" : "Português"),
    mkInfo(
      en ? "Coverage" : "Cobertura",
      en
        ? `${incisos.length} clauses · ${totalDocs} documents · ${totalCriticos} critical · ${totalCertik} CertiK`
        : `${incisos.length} incisos · ${totalDocs} documentos · ${totalCriticos} críticos · ${totalCertik} CertiK`
    ),
    mkInfo(
      en ? "Row types" : "Tipos de linha",
      en
        ? "CLAUSE = clause header | DOCUMENT = required document (fill last 2 cols) | OPTIMAL RESPONSE = best-practice target"
        : "INCISO = cabeçalho do inciso | DOCUMENTO = doc exigido (preencha as 2 últimas colunas) | RESPOSTA ÓTIMA = alvo de excelência"
    ),
    mkInfo(
      en ? "How to use" : "Como usar",
      en
        ? "Sort or filter by Priority to work on critical items first. Mark ✓ Gathered? and add Auditor Notes as you collect documents."
        : "Ordene ou filtre por Prioridade para trabalhar primeiro nos itens críticos. Marque ✓ Recolhido? e adicione Observações à medida que recolhe os documentos."
    ),
    blank(),
  ];

  // ── Row type labels ───────────────────────────────────────────────────────────
  const T_CLAUSE  = en ? "CLAUSE"           : "INCISO";
  const T_DOC     = en ? "DOCUMENT"         : "DOCUMENTO";
  const T_OPTIMAL = en ? "OPTIMAL RESPONSE" : "RESPOSTA ÓTIMA";

  // ── Data rows ─────────────────────────────────────────────────────────────────
  const dataRows = [];

  for (const inc of incisos) {
    const id      = inc.id || "";
    const rotulo  = inc.rotulo || "";
    const artigo  = inc.artigo_in701 || "";
    const tema    = pick(inc, "tema");
    const resumo  = pick(inc, "resumo");
    const base    = Array.isArray(inc.base_legal) ? inc.base_legal.join("; ") : (inc.base_legal || "");
    const gatilho = pick(inc, "gatilho");
    const docs    = Array.isArray(inc.documentos) ? inc.documentos : [];
    const ro      = inc.resposta_otima || null;
    const roDesc  = ro ? pick(ro, "descricao") : "";
    const roInds  = ro ? pick(ro, "indicadores") : [];
    const roStr   = Array.isArray(roInds) ? roInds.join(" | ") : (roInds || "");

    // Count docs by priority for the INCISO summary
    const nCrit = docs.filter(d => d.prioridade === "critica").length;
    const nHigh = docs.filter(d => d.prioridade === "alta").length;
    const nMed  = docs.filter(d => d.prioridade === "media").length;
    const docSummary = en
      ? `${docs.length} doc(s) — ${nCrit} critical · ${nHigh} high · ${nMed} medium`
      : `${docs.length} doc(s) — ${nCrit} crítico(s) · ${nHigh} alto(s) · ${nMed} médio(s)`;

    // INCISO header row
    const rInc = new Array(N).fill("");
    rInc[0]  = T_CLAUSE;
    rInc[1]  = id;
    rInc[2]  = rotulo;
    rInc[3]  = artigo;
    rInc[4]  = tema;
    rInc[5]  = resumo;
    rInc[6]  = base;
    rInc[7]  = gatilho;
    rInc[9]  = docSummary;   // doc_id col repurposed for summary on clause row
    rInc[18] = roDesc;        // opt_desc (brief preview on clause row)
    dataRows.push(rInc.map(csvCell));

    // DOCUMENTO rows
    docs.forEach((doc, idx) => {
      const contItems = pick(doc, "conteudo_minimo");
      const r = new Array(N).fill("");
      r[0]  = T_DOC;
      r[1]  = id;
      r[2]  = rotulo;
      r[3]  = artigo;
      r[8]  = String(idx + 1);                                          // seq
      r[9]  = doc.id || "";                                             // doc_id
      r[10] = pick(doc, "titulo");                                      // title
      r[11] = prioLabel(doc.prioridade || "");                          // priority
      r[12] = catLabel(doc.categoria || "");                            // category
      r[13] = certikName(doc.certik_servico || "");                     // certik
      r[14] = pick(doc, "descricao");                                   // description
      r[15] = Array.isArray(contItems) ? contItems.join(" | ") : (contItems || ""); // content
      r[16] = pick(doc, "justificativa_legal");                         // justif
      r[17] = pick(doc, "retencao");                                    // retention
      // r[20] = "" — ✓ Gathered?  (user fills)
      // r[21] = "" — Notes        (user fills)
      dataRows.push(r.map(csvCell));
    });

    // RESPOSTA ÓTIMA row (only if data exists)
    if (roDesc || roStr) {
      const rOpt = new Array(N).fill("");
      rOpt[0]  = T_OPTIMAL;
      rOpt[1]  = id;
      rOpt[2]  = rotulo;
      rOpt[3]  = artigo;
      rOpt[18] = roDesc;
      rOpt[19] = roStr;
      dataRows.push(rOpt.map(csvCell));
    }

    // Blank separator between incisos
    dataRows.push(blank());
  }

  // ── Assemble & download ───────────────────────────────────────────────────────
  const allRows = [
    ...infoRows,
    HEADERS.map(csvCell),   // column headers row
    ...dataRows,
  ];

  const BOM = "\uFEFF"; // UTF-8 BOM for correct Excel encoding
  const csv = BOM + allRows.map(r => r.join(",")).join("\r\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement("a");
  a.href = url;
  a.download = `certik_vasp_docs_guide_${today}_${lang}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

/** Ponto de entrada — chamar após montar o HTML do guia */
export function wireDocsGuideUI({ btnOpen, viewEl, btnBack, getTrack, setView }) {
  if (!btnOpen || !viewEl) return;

  let guideData = null;
  let enData    = null;
  let rendered  = false;

  async function loadData() {
    if (!guideData) {
      const res = await fetch("/static/data/docs_guide.json?v=1");
      if (!res.ok) throw new Error(`docs_guide: HTTP ${res.status}`);
      guideData = await res.json();
    }
    if (!enData) {
      try {
        const res = await fetch("/static/data/docs_guide_en.json?v=1");
        if (res.ok) enData = await res.json();
      } catch { /* optional */ }
    }
    await loadCjMap();
  }

  async function renderGuide() {
    try {
      await loadData();
    } catch (e) {
      const body = viewEl.querySelector("#dg-body");
      if (body) body.innerHTML = `<p class="dg-error">${t("dg_error")} ${esc(String(e.message || e))}</p>`;
      return;
    }

    const body = viewEl.querySelector("#dg-body");
    if (!body) return;

    const meta   = mergeEnMeta(guideData.meta || {}, enData);
    const incisos = mergeEnTranslations(guideData.incisos || [], enData);

    // Stats
    const totalDocs     = incisos.reduce((s, i) => s + (i.documentos?.length || 0), 0);
    const totalCriticos = incisos.reduce((s, i) => s + (i.documentos?.filter((d) => d.prioridade === "critica").length || 0), 0);
    const totalCertik   = incisos.reduce((s, i) => s + (i.documentos?.filter((d) => d.certik_servico).length || 0), 0);
    const statsEl = viewEl.querySelector("#dg-stats");
    if (statsEl) {
      statsEl.innerHTML = `
        <span class="dg-stat"><strong>${incisos.length}</strong> ${t("dg_stat_incisos_label")}</span>
        <span class="dg-stat-sep">·</span>
        <span class="dg-stat"><strong>${totalDocs}</strong> ${t("dg_stat_docs_label")}</span>
        <span class="dg-stat-sep">·</span>
        <span class="dg-stat dg-stat--crit"><strong>${totalCriticos}</strong> ${t("dg_stat_criticos_label")}</span>
        <span class="dg-stat-sep">·</span>
        <span class="dg-stat dg-stat--certik"><strong>${totalCertik}</strong> ${t("dg_stat_certik_label")}</span>`;
    }

    // Update select option texts (data-i18n inside select don't auto-apply on option tags in all browsers)
    const prioEl = viewEl.querySelector("#dg-prio-filter");
    if (prioEl) {
      prioEl.querySelectorAll("option[data-i18n]").forEach((opt) => {
        opt.textContent = t(opt.getAttribute("data-i18n"));
      });
    }

    body.innerHTML = incisos.map((inc) => renderIncisoCard(inc, meta)).join("");

    // Wire filter (idempotent: remove old listeners by replacing element)
    const searchEl = viewEl.querySelector("#dg-search");
    const certikEl = viewEl.querySelector("#dg-certik-only");

    function doFilter() {
      const certikOnly = certikEl?.checked || false;
      applyGuideFilter(body, searchEl?.value || "", prioEl?.value || "all", certikOnly);
      const visible  = body.querySelectorAll(".dg-inciso:not(.dg-hidden)").length;
      const countEl  = viewEl.querySelector("#dg-filter-count");
      if (countEl) countEl.textContent = `${visible} ${t("dg_of")} ${incisos.length}`;
    }

    if (!rendered) {
      searchEl?.addEventListener("input", doFilter);
      prioEl?.addEventListener("change", doFilter);
      certikEl?.addEventListener("change", doFilter);

      viewEl.querySelector("#dg-expand-all")?.addEventListener("click", () => {
        body.querySelectorAll(".dg-inciso:not(.dg-hidden)").forEach((el) => { el.open = true; });
      });
      viewEl.querySelector("#dg-collapse-all")?.addEventListener("click", () => {
        body.querySelectorAll(".dg-inciso").forEach((el) => { el.open = false; });
      });
      viewEl.querySelector("#dg-export")?.addEventListener("click", () => {
        const blob = new Blob([JSON.stringify(guideData, null, 2)], { type: "application/json" });
        const url  = URL.createObjectURL(blob);
        const a    = document.createElement("a");
        a.href = url;
        a.download = `certik_vasp_docs_guide_${new Date().toISOString().slice(0, 10)}.json`;
        a.click();
        URL.revokeObjectURL(url);
      });

      viewEl.querySelector("#dg-export-csv")?.addEventListener("click", () => {
        const mergedMeta   = mergeEnMeta(guideData.meta || {}, enData);
        const mergedIncisos = mergeEnTranslations(guideData.incisos || [], enData);
        exportDocsGuideCsv(mergedIncisos, mergedMeta);
        // Show a brief toast if available
        document.dispatchEvent(new CustomEvent("app:toast", {
          detail: { msg: t("dg_csv_done"), kind: "success" }
        }));
      });
    }
    rendered = true;
    doFilter();
  }

  btnOpen.addEventListener("click", () => {
    setView("docsGuide");
    renderGuide();
  });

  if (btnBack) {
    btnBack.addEventListener("click", () => setView("intro"));
  }

  // Re-render on language change
  document.addEventListener("langchange", () => {
    if (!viewEl.classList.contains("hidden")) {
      rendered = false;
      renderGuide();
    } else {
      rendered = false; // will re-render next time opened
    }
  });
}
