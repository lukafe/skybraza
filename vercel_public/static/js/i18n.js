/**
 * i18n — PT / EN switcher
 * Usage: import { t, getLangField, setLang, initI18n, initLangSync, getCurrentLang } from "./i18n.js"
 */

const STORAGE_KEY = "certik_lang";
let _lang = "pt";
const _strings = {};
let _i18nLoaded = false;

export function getCurrentLang() { return _lang; }

/**
 * Synchronously restore the saved language from localStorage.
 * Call this BEFORE any async work so buildLangToggle() uses the correct lang
 * without waiting for the i18n.json fetch to complete.
 */
export function initLangSync() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "en" || saved === "pt") _lang = saved;
  } catch { /* ignore */ }
  document.documentElement.lang = _lang === "en" ? "en" : "pt-BR";
}

/** Load the i18n.json bundle and apply to DOM. Safe to call multiple times. */
export async function initI18n() {
  if (!_i18nLoaded) {
    try {
      const res = await fetch("/static/data/i18n.json?v=6");
      const data = await res.json();
      Object.assign(_strings, data);
      _i18nLoaded = true;
    } catch (e) {
      console.warn("[i18n] Could not load i18n.json", e);
    }
    // Restore saved lang (in case initLangSync was not called first)
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved === "en" || saved === "pt") _lang = saved;
    } catch { /* ignore */ }
  }
  _applyHTML();
}

/** Translate a key with optional {var} interpolation */
export function t(key, vars = {}) {
  const entry = _strings[key];
  if (!entry) return key;
  const raw = entry[_lang] ?? entry["pt"] ?? key;
  return raw.replace(/\{(\w+)\}/g, (_, k) => (vars[k] !== undefined ? String(vars[k]) : `{${k}}`));
}

/**
 * Pick the language-appropriate field from an object.
 * e.g. getLangField(doc, "titulo") → doc.titulo_en (if EN) or doc.titulo (if PT)
 * The English translations are stored in docs_guide_en.json and merged externally.
 */
export function getLangField(obj, field) {
  if (!obj) return "";
  if (_lang === "en") {
    const enKey = `${field}_en`;
    if (obj[enKey] !== undefined && obj[enKey] !== null) return obj[enKey];
  }
  return obj[field] ?? "";
}

/** Switch language, persist and re-render static DOM */
export function setLang(lang) {
  if (lang !== "pt" && lang !== "en") return;
  _lang = lang;
  try { localStorage.setItem(STORAGE_KEY, lang); } catch { /* ignore */ }
  document.documentElement.lang = lang === "en" ? "en" : "pt-BR";
  _updateToggleButtons(lang);
  _applyHTML();
  document.dispatchEvent(new CustomEvent("langchange", { detail: { lang } }));
}

/** Apply translations to all [data-i18n] elements in the DOM */
function _applyHTML() {
  // text content
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const key = el.getAttribute("data-i18n");
    el.textContent = t(key);
  });
  // inner HTML (for strings with bold/em)
  document.querySelectorAll("[data-i18n-html]").forEach((el) => {
    const key = el.getAttribute("data-i18n-html");
    el.innerHTML = t(key);
  });
  // placeholder
  document.querySelectorAll("[data-i18n-ph]").forEach((el) => {
    el.placeholder = t(el.getAttribute("data-i18n-ph"));
  });
  // title attribute
  document.querySelectorAll("[data-i18n-title]").forEach((el) => {
    el.title = t(el.getAttribute("data-i18n-title"));
  });
  // aria-label
  document.querySelectorAll("[data-i18n-aria]").forEach((el) => {
    el.setAttribute("aria-label", t(el.getAttribute("data-i18n-aria")));
  });
}

function _updateToggleButtons(lang) {
  document.querySelectorAll(".lang-toggle-btn").forEach((btn) => {
    const isActive = btn.dataset.lang === lang;
    btn.classList.toggle("lang-toggle-btn--active", isActive);
    btn.setAttribute("aria-pressed", isActive ? "true" : "false");
  });
}

/** Build and return the language toggle HTML snippet */
export function buildLangToggle() {
  const wrap = document.createElement("div");
  wrap.className = "lang-toggle";
  wrap.setAttribute("role", "group");
  wrap.setAttribute("aria-label", "Language / Idioma");

  const mkBtn = (lang, label) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "lang-toggle-btn";
    btn.dataset.lang = lang;
    btn.textContent = label;
    btn.setAttribute("aria-pressed", lang === _lang ? "true" : "false");
    if (lang === _lang) btn.classList.add("lang-toggle-btn--active");
    btn.addEventListener("click", () => setLang(lang));
    return btn;
  };

  wrap.appendChild(mkBtn("pt", "PT"));
  wrap.appendChild(mkBtn("en", "EN"));
  return wrap;
}
