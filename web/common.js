/* Shared helpers for the player screen and the harbor board. */
"use strict";

let COLORS = ["#b3261e", "#2d4a8a", "#2f7d5b", "#c58a1b", "#7a3b7d", "#1f7f8c", "#7a4a22", "#4f5d6b"];
let T = {};          // wording, from the server (Admin > Language & Text)
let TOK = {};        // names usable in any line: {lender}, {pirate}, {home}...
let CUR = "$";
let cfgSeen = null;  // settings version these screens last loaded

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, c =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

/* t("key", {name: value}) gives the wording for a key with {names} filled in. */
function t(key, vars) {
  const tpl = T[key] == null ? key : T[key];
  return tpl.replace(/\{(\w+)\}/g, (m, k) =>
    vars && vars[k] != null ? vars[k] : (TOK[k] != null ? TOK[k] : m));
}
const te = (key, vars) => esc(t(key, vars));
/* Like t(), but the wording is made safe for HTML and the values are inserted as HTML. */
function th(key, vars) {
  return esc(T[key] == null ? key : T[key]).replace(/\{(\w+)\}/g, (m, k) =>
    vars && vars[k] != null ? vars[k] : (TOK[k] != null ? esc(TOK[k]) : m));
}

function money(n) {
  const v = Math.round(Number(n) || 0);
  return (v < 0 ? "-" : "") + CUR + Math.abs(v).toLocaleString("en-US");
}

function store(key, value) {
  try {
    if (value === undefined) return localStorage.getItem(key);
    if (value === null) localStorage.removeItem(key); else localStorage.setItem(key, value);
  } catch (e) { /* private browsing: the token just lives for this page */ }
  return null;
}

/* Fetches the reference data and applies brand, colours, wording and theme. */
async function loadInfo() {
  const r = await fetch("/api/info");
  const info = await r.json();
  const d = info.data;
  // screens may carry their own fallback wording for keys an older server does not have yet
  T = Object.assign({}, typeof T_FALLBACK !== "undefined" ? T_FALLBACK : {}, d.text || {});
  TOK = d.tokens || {};
  CUR = d.brand.currency || "";
  COLORS = d.colors || COLORS;
  const theme = document.getElementById("theme");
  if (theme && cfgSeen !== null && cfgSeen !== info.cfg) theme.href = "/theme.css?v=" + info.cfg;
  const fontsLink = document.getElementById("fonts");
  if (fontsLink && cfgSeen !== null && cfgSeen !== info.cfg) fontsLink.href = "/fonts.css?v=" + info.cfg;
  cfgSeen = info.cfg;
  if (typeof Media !== "undefined") Media.setup(info.media);
  document.documentElement.lang = d.lang || "en";
  document.title = d.brand.title_a + d.brand.title_b + (document.body.classList.contains("board") ? " · " + t("board.houses") : "");
  const fav = document.getElementById("fav");
  if (fav) fav.href = d.graphics.favicon || "data:,";
  return info;
}

function brandHtml(D) {
  const b = D.brand;
  if (D.graphics.logo) return `<img class="logo" src="${esc(D.graphics.logo)}" alt="${esc(b.title_a + b.title_b)}">`;
  return `${esc(b.title_a)}<span>${esc(b.title_b)}</span>`;
}

function pic(url, cls) {
  return url ? `<img class="${cls}" src="${esc(url)}" alt="">` : "";
}

/* Opens the live stream and calls onState with each new game state.
   The browser reconnects on its own if the server restarts. */
function listen(token, onState, onStatus) {
  const es = new EventSource("/events" + (token ? "?token=" + encodeURIComponent(token) : ""));
  es.onmessage = e => { onStatus(true); onState(JSON.parse(e.data)); };
  es.onerror = () => onStatus(false);
  return es;
}

function weatherBadge(level, names) {
  return '<span class="wx wx' + level + '">' + esc(names[level]) + "</span>";
}
