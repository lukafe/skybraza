/**
 * Guia de Documentos — IN 701 por inciso
 * Consome /static/data/docs_guide.json
 */

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

const PRIO_CONFIG = {
  critica: { label: "Crítica",  cls: "dg-prio--critica" },
  alta:    { label: "Alta",     cls: "dg-prio--alta"    },
  media:   { label: "Média",    cls: "dg-prio--media"   },
};

function esc(s) {
  if (!s) return "";
  const d = document.createElement("div");
  d.textContent = String(s);
  return d.innerHTML;
}

/** Renderiza um documento individual dentro do accordion do inciso */
function renderDocCard(doc, meta) {
  const catMeta = meta.categorias?.[doc.categoria] || {};
  const icon = CAT_ICONS[doc.categoria] || "📁";
  const prio = PRIO_CONFIG[doc.prioridade] || PRIO_CONFIG.media;
  const conteudo = Array.isArray(doc.conteudo_minimo)
    ? doc.conteudo_minimo.map((c) => `<li>${esc(c)}</li>`).join("")
    : "";

  return `
<div class="dg-doc-card dg-doc-card--${esc(doc.prioridade)}">
  <div class="dg-doc-header">
    <span class="dg-doc-icon" aria-hidden="true">${icon}</span>
    <span class="dg-doc-titulo">${esc(doc.titulo)}</span>
    <span class="dg-prio-badge ${prio.cls}" title="${esc(prio.label)} — ${esc(meta.prioridades?.[doc.prioridade] || "")}">${esc(prio.label)}</span>
    ${doc.categoria ? `<span class="dg-cat-badge" style="background: ${esc(catMeta.cor || "#555")}22; border-color: ${esc(catMeta.cor || "#555")}55; color: ${esc(catMeta.cor || "#999")}">${esc(catMeta.label || doc.categoria)}</span>` : ""}
  </div>
  <p class="dg-doc-descricao">${esc(doc.descricao)}</p>
  <details class="dg-doc-detail">
    <summary class="dg-doc-detail-summary">
      <span class="dg-doc-detail-toggle">⚖️ Justificativa legal</span>
    </summary>
    <p class="dg-doc-justificativa">${esc(doc.justificativa_legal)}</p>
  </details>
  ${conteudo ? `
  <details class="dg-doc-detail">
    <summary class="dg-doc-detail-summary">
      <span class="dg-doc-detail-toggle">📋 Conteúdo mínimo exigido</span>
    </summary>
    <ul class="dg-conteudo-list">${conteudo}</ul>
  </details>` : ""}
  ${doc.retencao ? `<p class="dg-retencao">⏱ Retenção: <strong>${esc(doc.retencao)}</strong></p>` : ""}
</div>`;
}

/** Renderiza o bloco de resposta ótima */
function renderRespostaOtima(ro) {
  if (!ro) return "";
  const items = Array.isArray(ro.indicadores)
    ? ro.indicadores.map((i) => `<li>${esc(i)}</li>`).join("")
    : "";
  return `
<div class="dg-otima">
  <div class="dg-otima-header">
    <span class="dg-otima-icon" aria-hidden="true">⭐</span>
    <span class="dg-otima-label">Resposta Ótima</span>
  </div>
  <p class="dg-otima-desc">${esc(ro.descricao)}</p>
  ${items ? `
  <div class="dg-otima-indicadores-label">Indicadores de excelência:</div>
  <ul class="dg-otima-indicadores">${items}</ul>` : ""}
</div>`;
}

/** Renderiza um card de inciso completo */
function renderIncisoCard(inciso, meta, idx) {
  const docsHtml = (inciso.documentos || [])
    .map((d) => renderDocCard(d, meta))
    .join("");
  const baseLegal = Array.isArray(inciso.base_legal)
    ? inciso.base_legal.map((b) => `<span class="dg-base-pill">${esc(b)}</span>`).join("")
    : "";
  const totalDocs = inciso.documentos?.length || 0;
  const criticos = inciso.documentos?.filter((d) => d.prioridade === "critica").length || 0;

  return `
<details class="dg-inciso" id="dg-inc-${esc(inciso.id)}" data-inciso-id="${esc(inciso.id)}"
  data-tema="${esc(inciso.tema)}" data-resumo="${esc(inciso.resumo)}" data-rotulo="${esc(inciso.rotulo)}">
  <summary class="dg-inciso-summary">
    <span class="dg-inc-chevron" aria-hidden="true">▸</span>
    <span class="dg-inc-rotulo">${esc(inciso.rotulo)}</span>
    <div class="dg-inc-info">
      <span class="dg-inc-tema">${esc(inciso.tema)}</span>
      <span class="dg-inc-art">${esc(inciso.artigo_in701)}</span>
    </div>
    <div class="dg-inc-badges">
      <span class="dg-inc-badge dg-inc-badge--docs" title="${totalDocs} documentos">${totalDocs} doc${totalDocs !== 1 ? "s" : ""}</span>
      ${criticos > 0 ? `<span class="dg-inc-badge dg-inc-badge--critico" title="${criticos} crítico(s)">${criticos} crítico${criticos !== 1 ? "s" : ""}</span>` : ""}
    </div>
  </summary>
  <div class="dg-inciso-body">
    <div class="dg-inciso-meta">
      <p class="dg-resumo">${esc(inciso.resumo)}</p>
      ${inciso.gatilho ? `<p class="dg-gatilho"><strong>Gatilho:</strong> ${esc(inciso.gatilho)}</p>` : ""}
      <div class="dg-base-legal">${baseLegal}</div>
    </div>
    <h4 class="dg-docs-section-title">Documentos necessários</h4>
    <div class="dg-docs-list">${docsHtml}</div>
    ${renderRespostaOtima(inciso.resposta_otima)}
  </div>
</details>`;
}

/** Filtra os incisos visíveis com base no texto de pesquisa e categoria */
function applyGuideFilter(root, searchVal, catVal) {
  const q = searchVal.trim().toLowerCase();
  root.querySelectorAll(".dg-inciso").forEach((el) => {
    const id = el.dataset.incisoId || "";
    const tema = el.dataset.tema || "";
    const resumo = el.dataset.resumo || "";
    const rotulo = el.dataset.rotulo || "";
    const matchSearch = !q ||
      id.toLowerCase().includes(q) ||
      tema.toLowerCase().includes(q) ||
      resumo.toLowerCase().includes(q) ||
      rotulo.toLowerCase().includes(q);

    let matchCat = true;
    if (catVal && catVal !== "all") {
      const docs = el.querySelectorAll(".dg-doc-card");
      matchCat = Array.from(docs).some((dc) =>
        dc.classList.contains(`dg-doc-card--${catVal}`) ||
        dc.querySelector(`.dg-cat-badge`)?.textContent?.toLowerCase().includes(catVal)
      );
    }

    el.classList.toggle("dg-hidden", !(matchSearch && matchCat));
  });
}

/** Ponto de entrada — chamar após montar o HTML do guia */
export function wireDocsGuideUI({ btnOpen, viewEl, btnBack, getTrack, setView }) {
  if (!btnOpen || !viewEl) return;

  let guideData = null;

  async function loadAndRender() {
    if (!guideData) {
      try {
        const res = await fetch("/static/data/docs_guide.json?v=1");
        guideData = await res.json();
      } catch (e) {
        viewEl.querySelector("#dg-body").innerHTML =
          `<p class="dg-error">Erro ao carregar o guia: ${esc(String(e.message || e))}</p>`;
        return;
      }
    }

    const body = viewEl.querySelector("#dg-body");
    if (!body) return;

    const meta = guideData.meta || {};
    const incisos = guideData.incisos || [];

    // Render stats
    const totalDocs = incisos.reduce((sum, i) => sum + (i.documentos?.length || 0), 0);
    const totalCriticos = incisos.reduce(
      (sum, i) => sum + (i.documentos?.filter((d) => d.prioridade === "critica").length || 0), 0
    );
    const statsEl = viewEl.querySelector("#dg-stats");
    if (statsEl) {
      statsEl.innerHTML = `
        <span class="dg-stat"><strong>${incisos.length}</strong> incisos</span>
        <span class="dg-stat-sep">·</span>
        <span class="dg-stat"><strong>${totalDocs}</strong> documentos mapeados</span>
        <span class="dg-stat-sep">·</span>
        <span class="dg-stat dg-stat--crit"><strong>${totalCriticos}</strong> documentos críticos</span>`;
    }

    body.innerHTML = incisos
      .map((inc, i) => renderIncisoCard(inc, meta, i))
      .join("");

    // Wire filter
    const searchEl = viewEl.querySelector("#dg-search");
    const prioEl = viewEl.querySelector("#dg-prio-filter");

    function doFilter() {
      applyGuideFilter(body, searchEl?.value || "", prioEl?.value || "all");
      const visible = body.querySelectorAll(".dg-inciso:not(.dg-hidden)").length;
      const countEl = viewEl.querySelector("#dg-filter-count");
      if (countEl) countEl.textContent = `${visible} de ${incisos.length}`;
    }

    searchEl?.addEventListener("input", doFilter);
    prioEl?.addEventListener("change", doFilter);

    // Expand all / Collapse all
    viewEl.querySelector("#dg-expand-all")?.addEventListener("click", () => {
      body.querySelectorAll(".dg-inciso:not(.dg-hidden)").forEach((el) => { el.open = true; });
    });
    viewEl.querySelector("#dg-collapse-all")?.addEventListener("click", () => {
      body.querySelectorAll(".dg-inciso").forEach((el) => { el.open = false; });
    });

    // Export guide
    viewEl.querySelector("#dg-export")?.addEventListener("click", () => {
      const blob = new Blob([JSON.stringify(guideData, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `certik_vasp_docs_guide_${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
    });
  }

  btnOpen.addEventListener("click", () => {
    setView("docsGuide");
    loadAndRender();
  });

  if (btnBack) {
    btnBack.addEventListener("click", () => setView("intro"));
  }
}
