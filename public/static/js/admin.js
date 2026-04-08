/**
 * Admin panel — CertiK VASP Scoping
 * Auth: Google Sign-In restricted to @certik.com → HMAC session token.
 */

const $ = (s) => document.querySelector(s);
const API = "/api/v1";

let sessionToken = sessionStorage.getItem("admin_session") || "";
let sessionEmail = sessionStorage.getItem("admin_email") || "";
let questionsCache = {};

const PAGE_SIZE = 30;
let currentOffset = 0;
let currentTrack = "";
let currentSearch = "";
let currentSort = { col: "created_at", asc: false };

// ── Helpers ──────────────────────────────────────────────────────────────────

function esc(s) {
  const el = document.createElement("span");
  el.textContent = s;
  return el.innerHTML;
}

async function api(path, opts = {}) {
  const res = await fetch(`${API}${path}`, {
    ...opts,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${sessionToken}`,
      ...(opts.headers || {}),
    },
  });
  if (res.status === 401) {
    clearSession();
    showLogin("Sessão expirada — faça login novamente.");
    throw new Error("Unauthorized");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail?.message || body.detail || res.statusText);
  }
  return res.json();
}

function fmtDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric" })
    + " " + d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

function trackPill(track) {
  const cls = `track-pill track-pill--${track || "intermediaria"}`;
  return `<span class="${cls}">${esc(track || "intermediaria")}</span>`;
}

function clearSession() {
  sessionToken = "";
  sessionEmail = "";
  sessionStorage.removeItem("admin_session");
  sessionStorage.removeItem("admin_email");
  _loginInitDone = false;
}

// ── Views ────────────────────────────────────────────────────────────────────

function showLogin(error = "") {
  $("#view-login").classList.remove("hidden");
  $("#view-dashboard").classList.add("hidden");
  $("#view-detail").classList.add("hidden");
  $("#btn-logout").classList.add("hidden");
  $("#user-email").classList.add("hidden");
  $("#login-error").textContent = error;
  initLoginUI();
}

function showDashboard() {
  $("#view-login").classList.add("hidden");
  $("#view-dashboard").classList.remove("hidden");
  $("#view-detail").classList.add("hidden");
  $("#btn-logout").classList.remove("hidden");
  if (sessionEmail) {
    $("#user-email").textContent = sessionEmail;
    $("#user-email").classList.remove("hidden");
  }
  loadStats();
  loadSubmissions();
}

function showDetail(id) {
  $("#view-login").classList.add("hidden");
  $("#view-dashboard").classList.add("hidden");
  $("#view-detail").classList.remove("hidden");
  loadDetail(id);
}

// ── Login UI (Google OAuth or password fallback) ─────────────────────────────

let _googleClientId = "";
let _loginInitDone = false;
let _usePasswordLogin = false;

async function initLoginUI() {
  if (_loginInitDone) return;
  try {
    const cfg = await fetch(`${API}/admin/config`).then((r) => r.json());
    _googleClientId = cfg.google_client_id || "";
    _usePasswordLogin = !_googleClientId;
  } catch {
    $("#login-error").textContent = "Não foi possível obter configuração do servidor.";
    return;
  }

  if (_usePasswordLogin) {
    $("#login-sub").textContent = "Insira a senha de administrador.";
    $("#password-form").classList.remove("hidden");
    $("#google-signin-btn").classList.add("hidden");
    _loginInitDone = true;
    return;
  }

  $("#login-sub").innerHTML = 'Faça login com a sua conta Google <strong>@certik.com</strong>.';
  $("#password-form").classList.add("hidden");
  $("#google-signin-btn").classList.remove("hidden");
  initGoogleButton();
}

function initGoogleButton() {
  function loadGsiScript() {
    return new Promise((resolve, reject) => {
      if (window.google?.accounts?.id) return resolve();
      if (document.querySelector('script[src*="accounts.google.com/gsi/client"]')) {
        waitForGoogle(resolve, 40);
        return;
      }
      const s = document.createElement("script");
      s.src = "https://accounts.google.com/gsi/client";
      s.async = true;
      s.onload = () => waitForGoogle(resolve, 20);
      s.onerror = () => reject(new Error("Failed to load Google Sign-In"));
      document.head.appendChild(s);
    });
  }

  function waitForGoogle(cb, retries = 20) {
    if (window.google?.accounts?.id) return cb();
    if (retries <= 0) { $("#login-error").textContent = "Google Sign-In não carregou."; return; }
    setTimeout(() => waitForGoogle(cb, retries - 1), 250);
  }

  loadGsiScript()
    .then(() => {
      google.accounts.id.initialize({
        client_id: _googleClientId,
        callback: handleGoogleCredential,
      });
      google.accounts.id.renderButton($("#google-signin-btn"), {
        theme: "filled_black",
        size: "large",
        shape: "pill",
        text: "signin_with",
        locale: "pt-BR",
      });
      _loginInitDone = true;
    })
    .catch(() => {
      $("#login-error").textContent = "Google Sign-In não carregou.";
    });
}

async function handleGoogleCredential(response) {
  $("#login-error").textContent = "";
  try {
    const data = await doLogin({ credential: response.credential });
    applySession(data);
  } catch (e) {
    clearSession();
    $("#login-error").textContent = e.message || "Erro ao autenticar.";
  }
}

async function handlePasswordSubmit(e) {
  e.preventDefault();
  const pw = $("#password-input").value.trim();
  if (!pw) return;
  const btn = $("#password-form .login-btn");
  const originalText = btn.textContent;
  btn.disabled = true;
  btn.textContent = "A entrar…";
  $("#login-error").textContent = "";
  try {
    const data = await doLogin({ password: pw });
    applySession(data);
  } catch (err) {
    $("#login-error").textContent = err.message || "Erro ao autenticar.";
  } finally {
    btn.disabled = false;
    btn.textContent = originalText;
  }
}

async function doLogin(body) {
  const res = await fetch(`${API}/admin/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail?.message || err.detail || "Falha no login");
  }
  return res.json();
}

function applySession(data) {
  sessionToken = data.session_token;
  sessionEmail = data.email || "";
  sessionStorage.setItem("admin_session", sessionToken);
  sessionStorage.setItem("admin_email", sessionEmail);
  showDashboard();
}

// ── Stats ────────────────────────────────────────────────────────────────────

async function loadStats() {
  try {
    const data = await api("/admin/stats");

    if (data.db === false) {
      $("#stats-row").innerHTML = `<div class="alert-banner">Base de dados não configurada — defina <code>DATABASE_URL</code> nas variáveis de ambiente para ativar a persistência.</div>`;
      return;
    }

    const byTrack = data.by_track || {};
    const cards = [
      { val: data.total, label: "Total submissões" },
      { val: byTrack.intermediaria || 0, label: "Intermediária" },
      { val: byTrack.custodiante || 0, label: "Custodiante" },
      { val: byTrack.corretora || 0, label: "Corretora" },
    ];
    $("#stats-row").innerHTML = cards
      .map((c) => `<div class="stat-card"><div class="stat-val">${c.val}</div><div class="stat-label">${c.label}</div></div>`)
      .join("");
  } catch {
    $("#stats-row").innerHTML = "";
  }
}

// ── List ─────────────────────────────────────────────────────────────────────

async function loadSubmissions() {
  const params = new URLSearchParams({
    limit: PAGE_SIZE,
    offset: currentOffset,
  });
  if (currentTrack) params.set("track", currentTrack);
  if (currentSearch) params.set("search", currentSearch);

  try {
    const data = await api(`/admin/submissions?${params}`);
    renderTable(data.items);
    renderPagination(data.total);
  } catch (e) {
    $("#table-wrap").innerHTML = `<div class="empty-state">Erro ao carregar: ${esc(e.message)}</div>`;
  }
}

function renderTable(items) {
  if (!items.length) {
    const hasFilters = currentTrack || currentSearch;
    const msg = hasFilters
      ? "Nenhuma submissão corresponde aos filtros atuais."
      : "Ainda não há submissões. Os dados aparecerão quando clientes completarem o questionário.";
    $("#table-wrap").innerHTML = `<div class="empty-state"><div class="empty-state-icon">&#128203;</div><p>${msg}</p></div>`;
    return;
  }
  function sortIndicator(col) {
    if (currentSort.col !== col) return "";
    return currentSort.asc ? " ▲" : " ▼";
  }

  const sorted = [...items].sort((a, b) => {
    const col = currentSort.col;
    let va = a[col] ?? "", vb = b[col] ?? "";
    if (col === "created_at") { va = va || ""; vb = vb || ""; }
    if (typeof va === "number" && typeof vb === "number") return currentSort.asc ? va - vb : vb - va;
    return currentSort.asc ? String(va).localeCompare(String(vb)) : String(vb).localeCompare(String(va));
  });

  const cols = [
    { key: "created_at", label: "Data", align: "left" },
    { key: "institution", label: "Instituição", align: "left" },
    { key: "track", label: "Trilha", align: "left" },
    { key: "lang", label: "Lang", align: "center" },
    { key: "total_sujeitos", label: "Auditoria", align: "right" },
    { key: "total_fora", label: "Fora", align: "right" },
  ];

  let html = `<div class="sub-table-wrap"><table class="sub-table">
    <thead><tr>${cols.map((c) =>
      `<th class="sortable-th" data-sort="${c.key}" style="text-align:${c.align};cursor:pointer">${c.label}${sortIndicator(c.key)}</th>`
    ).join("")}</tr></thead><tbody>`;

  for (const r of sorted) {
    html += `<tr data-id="${esc(r.id)}">
      <td class="mono" style="white-space:nowrap">${fmtDate(r.created_at)}</td>
      <td>${esc(r.institution || "—")}</td>
      <td>${trackPill(r.track)}</td>
      <td style="text-align:center" class="mono">${esc(r.lang || "—")}</td>
      <td style="text-align:right" class="mono">${r.total_sujeitos ?? "—"}</td>
      <td style="text-align:right" class="mono">${r.total_fora ?? "—"}</td>
    </tr>`;
  }
  html += "</tbody></table></div>";
  $("#table-wrap").innerHTML = html;

  for (const th of document.querySelectorAll(".sortable-th")) {
    th.addEventListener("click", () => {
      const col = th.dataset.sort;
      if (currentSort.col === col) { currentSort.asc = !currentSort.asc; }
      else { currentSort = { col, asc: true }; }
      renderTable(items);
    });
  }

  for (const tr of document.querySelectorAll(".sub-table tbody tr")) {
    tr.addEventListener("click", () => showDetail(tr.dataset.id));
  }
}

function renderPagination(total) {
  const pg = $("#pagination");
  if (total <= PAGE_SIZE) { pg.classList.add("hidden"); return; }
  pg.classList.remove("hidden");
  const page = Math.floor(currentOffset / PAGE_SIZE) + 1;
  const pages = Math.ceil(total / PAGE_SIZE);
  pg.innerHTML = `
    <button id="pg-prev" ${currentOffset === 0 ? "disabled" : ""}>← Anterior</button>
    <span>Página ${page} de ${pages} · ${total} submissões</span>
    <button id="pg-next" ${currentOffset + PAGE_SIZE >= total ? "disabled" : ""}>Seguinte →</button>`;
  $("#pg-prev")?.addEventListener("click", () => { currentOffset = Math.max(0, currentOffset - PAGE_SIZE); loadSubmissions(); });
  $("#pg-next")?.addEventListener("click", () => { currentOffset += PAGE_SIZE; loadSubmissions(); });
}

// ── Detail ───────────────────────────────────────────────────────────────────

async function fetchQuestions(track) {
  if (questionsCache[track]) return questionsCache[track];
  try {
    const data = await fetch(`${API}/questions?track=${encodeURIComponent(track)}`).then((r) => r.json());
    const map = {};
    for (const block of data.blocks || []) {
      for (const q of block.questions || []) {
        map[q.id] = q.text || q.id;
      }
    }
    questionsCache[track] = map;
    return map;
  } catch {
    return {};
  }
}

async function loadDetail(id) {
  const view = $("#view-detail");
  view.innerHTML = '<div class="empty-state">A carregar…</div>';
  try {
    const data = await api(`/admin/submissions/${id}`);
    const qMap = await fetchQuestions(data.track);
    const snap = data.scope_snapshot || {};
    const resumo = snap.resumo || {};
    const audit = snap.incisos_sujeitos_auditoria || [];
    const fora = snap.incisos_fora_escopo_auditoria || [];
    const answers = data.answers || {};

    let html = `
      <button class="detail-back" id="btn-back-list">← Voltar à lista</button>
      <div class="detail-hero">
        <h2>${esc(data.institution || "Sem nome")}</h2>
        <div class="detail-meta">
          <span>${trackPill(data.track)}</span>
          <span>${fmtDate(data.created_at)}</span>
          <span class="mono text-muted">${esc(data.id)}</span>
        </div>
      </div>

      <div class="stats-row" style="margin-bottom:1.25rem">
        <div class="stat-card"><div class="stat-val">${resumo.total_sujeitos_auditoria ?? "—"}</div><div class="stat-label">No escopo</div></div>
        <div class="stat-card"><div class="stat-val">${resumo.obrigatorios_matriz ?? "—"}</div><div class="stat-label">Obrigatórios</div></div>
        <div class="stat-card"><div class="stat-val">${resumo.acionados_por_respostas ?? "—"}</div><div class="stat-label">Por respostas</div></div>
        <div class="stat-card"><div class="stat-val">${resumo.total_fora_escopo_auditoria ?? "—"}</div><div class="stat-label">Fora do escopo</div></div>
      </div>

      <div class="detail-section">
        <h3 class="detail-section-title">Incisos sujeitos a auditoria (${audit.length})</h3>
        <div class="detail-section-body">
          ${audit.length
            ? `<div class="incisos-chips">${audit.map((i) => `<span class="inciso-chip inciso-chip--audit">${esc(typeof i === "string" ? i : i.id || JSON.stringify(i))}</span>`).join("")}</div>`
            : '<span class="text-muted">Nenhum</span>'}
        </div>
      </div>

      <div class="detail-section">
        <h3 class="detail-section-title">Incisos fora do escopo (${fora.length})</h3>
        <div class="detail-section-body">
          ${fora.length
            ? `<div class="incisos-chips">${fora.map((i) => `<span class="inciso-chip inciso-chip--out">${esc(typeof i === "string" ? i : i.id || JSON.stringify(i))}</span>`).join("")}</div>`
            : '<span class="text-muted">Nenhum</span>'}
        </div>
      </div>

      <div class="detail-section">
        <h3 class="detail-section-title">Respostas do questionário (${Object.keys(answers).length})</h3>
        <div class="detail-section-body">
          <div class="answers-grid">
            ${Object.entries(answers)
              .map(([k, v]) => {
                const qText = qMap[k] || "";
                let display = v;
                let cls = "";
                if (v === true) { display = "Sim"; cls = "answer-val--true"; }
                else if (v === false) { display = "Não"; cls = "answer-val--false"; }
                else if (Array.isArray(v)) { display = v.join(", ") || "—"; }
                else if (v === null || v === "") { display = "—"; cls = "answer-val--false"; }
                return `<div class="answer-item">
                  <div class="answer-id">${esc(k)}</div>
                  ${qText ? `<div class="answer-q">${esc(qText)}</div>` : ""}
                  <div class="answer-val ${cls}">${esc(String(display))}</div>
                </div>`;
              })
              .join("")}
          </div>
        </div>
      </div>

      <div style="display:flex; gap:0.75rem; margin-top:1rem; margin-bottom:2rem">
        <button class="btn-danger" id="btn-delete-sub">Apagar submissão</button>
      </div>`;

    view.innerHTML = html;
    $("#btn-back-list").addEventListener("click", showDashboard);
    $("#btn-delete-sub").addEventListener("click", async () => {
      if (!confirm("Tem certeza que deseja apagar esta submissão?")) return;
      try {
        await api(`/admin/submissions/${id}`, { method: "DELETE" });
        showDashboard();
      } catch (e) {
        alert("Erro: " + e.message);
      }
    });
  } catch (e) {
    view.innerHTML = `<div class="empty-state">Erro: ${esc(e.message)}</div>`;
  }
}

// ── Events ───────────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  $("#btn-logout").addEventListener("click", (e) => {
    e.preventDefault();
    clearSession();
    showLogin();
  });

  $("#btn-export-csv")?.addEventListener("click", async () => {
    const params = new URLSearchParams();
    if (currentTrack) params.set("track", currentTrack);
    if (currentSearch) params.set("search", currentSearch);
    try {
      const res = await fetch(`${API}/admin/submissions/export?${params}`, {
        headers: { Authorization: `Bearer ${sessionToken}` },
      });
      if (!res.ok) throw new Error("Export failed");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "certik_submissions.csv";
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      alert("Erro ao exportar: " + e.message);
    }
  });

  let searchTimer;
  $("#search-input").addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      currentSearch = ($("#search-input").value || "").trim();
      currentOffset = 0;
      loadSubmissions();
    }, 350);
  });

  $("#filter-track").addEventListener("change", () => {
    currentTrack = $("#filter-track").value;
    currentOffset = 0;
    loadSubmissions();
  });

  $("#password-form")?.addEventListener("submit", handlePasswordSubmit);

  if (sessionToken) {
    api("/admin/stats")
      .then(() => showDashboard())
      .catch(() => { clearSession(); showLogin(); });
  } else {
    showLogin();
  }
});
