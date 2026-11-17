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
  document.title = brandName(d.brand) + (document.body.classList.contains("board") ? " · " + t("board.houses") : "");
  const fav = document.getElementById("fav");
  if (fav) fav.href = d.graphics.favicon || "data:,";
  return info;
}

function brandName(b) {
  return [b.title_a, b.title_b].filter(Boolean).join(" ");
}

function brandHtml(D) {
  const b = D.brand;
  if (D.graphics.logo) return `<img class="logo" src="${esc(D.graphics.logo)}" alt="${esc(brandName(b))}">`;
  return `${esc(b.title_a)} <span>${esc(b.title_b)}</span>`;
}

/* Saved Captains' pictures for the seats at the table (Admin > Captains, Media Library): the Captain's
   portrait and the House's crest. The server sends them on each seat as portrait / crest; an older
   server that does not, gets them matched by the seat's name and House from /api/captains (seats taken
   with a Captain's PIN carry the Captain's name and the House's name). Faces.onChange is called when
   the pictures arrive or change, so a screen can draw itself again. */
const Faces = (() => {
  let list = null, at = 0, busy = false, sig = "";
  const api = { onChange: null };
  function refresh() {
    if (busy || (list && Date.now() - at < 30000)) return;
    busy = true;
    fetch("/api/captains").then(r => r.json()).then(r => {
      if (!r.ok) return;
      list = r.captains || [];
      const now = JSON.stringify(list.map(c => [c.name, c.portrait, (c.houses || []).map(h => [h.name, h.image])]));
      if (now !== sig) { sig = now; if (api.onChange) api.onChange(); }
    }).catch(() => { list = list || []; }).finally(() => { busy = false; at = Date.now(); });
  }
  const norm = (s, n) => String(s || "").split(/\s+/).filter(Boolean).join(" ").slice(0, n).toLowerCase();
  /* {portrait, crest} for a seat ({name, firm, portrait?, crest?}); "" where there is none. */
  api.of = p => {
    p = p || {};
    if (p.portrait !== undefined && p.crest !== undefined) return { portrait: p.portrait || "", crest: p.crest || "" };
    refresh();
    const c = list && list.find(x => norm(x.name, 20) === norm(p.name, 20));
    const h = c && (c.houses || []).find(x => norm(x.name, 28) === norm(p.firm, 28));
    return { portrait: (c && h && c.portrait) || "", crest: (h && h.image) || "" };
  };
  api.refresh = refresh;
  return api;
})();

/* The House's mark beside its name: its crest from the Media Library, else the old colour chip. */
function houseMark(p, cls) {
  const col = COLORS[((p && p.color) || 0) % COLORS.length];
  const u = Faces.of(p).crest;
  return u ? `<img class="crest${cls ? " " + cls : ""}" src="${esc(u)}" alt="" style="--house:${col}">`
    : `<i class="chip${cls ? " " + cls : ""}" style="background:${col}"></i>`;
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
