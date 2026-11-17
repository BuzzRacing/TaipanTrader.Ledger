/* SeaTrader — the Tally Book: a player's statistics, charts and heat maps.
   Opens in its own window from the player screen (/stats). The numbers come from /api/stats,
   which works them out from the game journal (stats.py). All wording comes from the server
   through t("key"), so Admin > Language & Text can change any of it.

   The window never scrolls: top bar, the headline figures and the section tabs stay put and
   only the panel area scrolls inside itself when a small screen needs it.

   Charts are drawn here as plain SVG and HTML (the game has no dependencies). Every chart has
   a hover read-out and a table view; identity is never colour alone (names sit on the lines). */
"use strict";

let D = null;                         // reference data from /api/info
let token = store("seatrader_token");
const app = document.getElementById("app");
const tip = document.getElementById("tip");
const ui = { scope: store("tally_scope") || "voyage", tab: store("tally_tab") || "fortune", game: null, name: null,
             good: null, tables: {}, raceAt: null, raceTimer: null, mapTimer: null, lastJson: {} };
let V = null;                         // voyage answer
let C = null;                         // career answer
const EMBED = new URLSearchParams(location.search).has("embed");   // inside the player screen
if (EMBED) document.body.classList.add("embed");
ui.visible = true;
const still = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/* Categorical slots for houses (validated for the dark deck: adjacent CVD and normal-vision
   separation pass, all >= 3:1 on the panel colour). A house keeps its slot by its seat colour. */
const SER = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#0ca30c", "#9085e9", "#e66767"];
const ser = i => SER[((i % 8) + 8) % 8];
const SINGLE = "#d6b25e";             // a lone series: brass
const POS = [57, 135, 229], NEG = [230, 103, 103], MID = [52, 47, 42];      // diverging poles and neutral
const SEQ0 = [44, 35, 26], SEQ1 = [236, 200, 110];                          // sequential: dark -> brass

/* ------------------------------------------------------------- helpers -- */
const portName = k => (D.ports[k] || {}).name || k;
const goodName = k => (D.goods[k] || {}).name || k;
const pct = v => v == null ? "–" : Math.round(v * 100) + "%";
const signed = v => (v > 0 ? "+" : "") + money(v);
function short(n) {
  const v = Math.abs(n), s = n < 0 ? "-" : "";
  if (v >= 1e6) return s + CUR + (v / 1e6).toFixed(v >= 1e7 ? 0 : 1) + "M";
  if (v >= 1e4) return s + CUR + Math.round(v / 1e3) + "k";
  if (v >= 1e3) return s + CUR + (v / 1e3).toFixed(1) + "k";
  return s + CUR + Math.round(v);
}
function mix(a, b, f) { return "rgb(" + a.map((x, i) => Math.round(x + (b[i] - x) * f)).join(",") + ")"; }
function divColor(v, max) {
  if (v == null || !max) return null;
  const f = v === 0 ? 0 : .22 + .78 * Math.min(1, Math.pow(Math.abs(v) / max, .6));
  return mix(MID, v >= 0 ? POS : NEG, f);
}
function seqColor(v, lo, hi) {
  if (v == null) return null;
  const f = hi > lo ? Math.max(0, Math.min(1, (v - lo) / (hi - lo))) : .5;
  return mix(SEQ0, SEQ1, f);
}
function inkOn(rgb) {           // ivory or night text on a filled cell
  const m = /(\d+),(\d+),(\d+)/.exec(rgb || "");
  if (!m) return "";
  const l = (.299 * m[1] + .587 * m[2] + .114 * m[3]);
  return l > 150 ? "#15100c" : "#f1e3c5";
}
function niceTicks(lo, hi, n) {
  if (lo === hi) { lo -= 1; hi += 1; }
  const span = hi - lo, step0 = span / Math.max(1, n);
  const mag = Math.pow(10, Math.floor(Math.log10(step0)));
  const step = [1, 2, 2.5, 5, 10].map(s => s * mag).find(s => s >= step0) || 10 * mag;
  const out = [];
  for (let v = Math.floor(lo / step) * step; v <= hi + step * .001; v += step) out.push(Math.round(v * 1e6) / 1e6);
  return out;
}
function btn(label, act, attrs, cls) {
  return `<button type="button" class="${cls || ""}" data-act="${act}" ${attrs || ""}>${label}</button>`;
}
const ICON = {
  fortune: '<path d="M4 19h16M6 16l4-5 4 3 5-7"/><circle cx="19" cy="7" r="1.6"/>',
  routes: '<circle cx="6" cy="17" r="2.2"/><circle cx="18" cy="7" r="2.2"/><path d="M8 16c5-1 3-7 8-8" stroke-dasharray="2 2.5"/>',
  markets: '<path d="M4 20V10M9 20V5M14 20v-8M19 20V8"/>',
  perils: '<path d="M12 3l9 16H3z"/><path d="M12 10v4M12 16.5v.5"/>',
  storm: '<path d="M7 15a4 4 0 1 1 1-7.9A5 5 0 0 1 18 9a3 3 0 0 1 0 6z"/><path d="M11 15l-2 4h3l-2 3"/>',
  battle: '<path d="M5 19L19 5M15 5h4v4M9 19H5v-4M5 5l14 14M5 9V5h4M19 15v4h-4"/>',
  wreck: '<path d="M3 15h18l-3 4H6z"/><path d="M12 15V5l5 6h-5"/><path d="M2 21c3-1 5 1 8 0s5 1 8 0 3 0 4 0"/>',
  seized: '<rect x="5" y="10" width="14" height="10" rx="1.5"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>',
  robbed: '<circle cx="12" cy="12" r="8"/><path d="M9 9l6 6M15 9l-6 6"/>',
  ship: '<path d="M4 16h16l-2 4H6z"/><path d="M12 16V4l6 9h-6M12 7l-5 7h5"/>',
  rank: '<path d="M12 3l2.6 5.6 6 .6-4.5 4 1.3 6-5.4-3.2L6.6 19l1.3-6-4.5-4 6-.6z"/>',
  lock: '<rect x="5" y="11" width="14" height="9" rx="1.5"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
  play: '<path d="M8 5l11 7-11 7z"/>', pause: '<path d="M8 5v14M16 5v14"/>',
  table: '<path d="M4 5h16v14H4zM4 10h16M4 15h16M10 5v14"/>', close: '<path d="M6 6l12 12M18 6L6 18"/>'
};
const icon = (k, cls) => `<svg class="ico ${cls || ""}" viewBox="0 0 24 24" aria-hidden="true">${ICON[k] || ""}</svg>`;

/* ----------------------------------------------------------------- net -- */
async function getJSON(url) {
  try {
    const r = await fetch(url, { cache: "no-store" });
    return await r.json();
  } catch (e) {
    return { ok: false, error: t("ui.no_server") };
  }
}
function q(scope, extra) {
  const p = new URLSearchParams({ scope });
  if (token) p.set("token", token);
  if (ui.name) p.set("name", ui.name);
  for (const k in extra || {}) if (extra[k] != null) p.set(k, extra[k]);
  return "/api/stats?" + p.toString();
}

async function load(quiet) {
  const vs = ui.scope === "voyage";
  const [a, b] = await Promise.all([getJSON(q("voyage", { game: ui.game })), getJSON(q("career"))]);
  if (!a.ok && !b.ok) {
    if (a.who || b.who) return pickWho(a.players || b.players || []);
    return message(esc(a.error || b.error));
  }
  const changed = JSON.stringify([a, b]) !== ui.lastJson.both;
  ui.lastJson.both = JSON.stringify([a, b]);
  V = a.ok ? a : null;
  C = b.ok ? b : null;
  if (!V && vs && C && C.career.games.length) {
    // No seat in the game in progress (or nothing recorded yet): show the latest past game.
    const past = C.career.games.find(g => !g.running);
    if (past && ui.game !== past.id) { ui.game = past.id; return load(quiet); }
  }
  if (quiet && !changed) return;
  render(!quiet);
}

/* -------------------------------------------------------------- frame -- */
function message(html) {
  app.innerHTML = `<div class="tl-solo"><section class="card"><h2>${te("st.title")}</h2><p>${html}</p>
    ${btn(te("st.back"), "back", "", "primary")}</section></div>`;
}

async function pickWho(players) {
  const list = players.length ? players.map(n => btn(esc(n), "who", `data-name="${esc(n)}"`, "")).join("")
    : `<p class="muted">${te("st.nobody")}</p>`;
  app.innerHTML = `<div class="tl-solo"><section class="card"><p class="eyebrow">${te("st.title")}</p>
    <h2>${te("st.who")}</h2><p class="muted">${te("st.who_info")}</p><div class="seg">${list}</div>
    ${btn(te("st.back"), "back", "", "ghost")}</section></div>`;
}

const TABS = ["fortune", "routes", "markets", "perils"];

function render(animate) {
  stopTimers();
  ui.tables = {};
  const vs = ui.scope === "voyage" && V;
  const scope = vs ? "voyage" : "career";
  if (scope !== ui.scope && !V) ui.scope = "career";
  const who = vs ? V.voyage.me : null;
  const name = (V && V.name) || (C && C.name) || ui.name || "";
  const head = vs
    ? `<b>${esc(who.firm)}</b><small>${th("st.head_voyage", { name: esc(name), first: esc(V.voyage.game.first), last: esc(V.voyage.game.last) })}${lockNote()}</small>`
    : `<b>${th("st.head_career", { name: esc(name) })}</b><small>${te("st.head_career_sub", { n: C ? C.career.totals.games : 0 })}</small>`;
  const games = gameOptions();
  app.innerHTML = `<div class="tl" data-scope="${scope}" data-tab="${ui.tab}">
    <header class="tl-top">
      <div class="tl-house">${vs ? `<i class="chip" style="background:${ser(who.color)}"></i>` : icon("rank", "big")}
        <div><p class="eyebrow">${te("st.title")}</p>${head}</div></div>
      <div class="tl-scope seg" role="tablist">
        ${btn(te("st.voyage"), "scope", `data-s="voyage" ${V ? "" : "disabled"}`, scope === "voyage" ? "on" : "")}
        ${btn(te("st.career"), "scope", 'data-s="career"', scope === "career" ? "on" : "")}</div>
      ${vs && games ? `<label class="tl-game"><span>${te("st.game")}</span><select data-act="game">${games}</select></label>` : ""}
      ${btn(icon("close"), "back", `aria-label="${te("st.back")}" title="${te("st.back")}"`, "ghost tl-x")}
    </header>
    <section class="tl-kpis">${vs ? voyageKpis() : careerKpis()}</section>
    <nav class="tl-tabs" role="tablist">${TABS.map(k =>
      btn(icon(k) + `<span>${te("st.tab." + k)}</span>`, "tab", `data-tab="${k}" role="tab" aria-selected="${ui.tab === k}"`,
          ui.tab === k ? "on" : "")).join("")}</nav>
    <main class="tl-main" id="main"></main>
  </div>`;
  const main = document.getElementById("main");
  main.innerHTML = (vs ? VOYAGE : CAREER)[ui.tab]();
  main.scrollTop = 0;
  drawAll(animate);
  countUp(animate);
}

function lockNote() {
  const g = V.voyage.game;
  if (g.reveal) return g.ended ? ` · <span class="ok">${te("st.unlocked")}</span>` : "";
  return ` · <span class="lock">${icon("lock")}${te("st.fair")}</span>`;
}

function gameOptions() {
  if (!C || !C.career.games.length) return "";
  const cur = V ? V.voyage.game.id : null;
  return C.career.games.map(g => `<option value="${esc(g.id)}" ${g.id === cur ? "selected" : ""}>` +
    esc(g.running ? t("st.game_now", { first: g.first }) : t("st.game_past", { first: g.first, last: g.last, place: g.place, players: g.players })) +
    "</option>").join("");
}

/* --------------------------------------------------- headline figures -- */
function kpi(label, value, opts) {
  const o = opts || {};
  const num = typeof value === "number";
  return `<div class="tk ${o.cls || ""}"><span>${label}</span>` +
    `<b ${num ? `data-count="${value}" data-fmt="${o.fmt || "money"}"` : ""}>${num ? fmtVal(value, o.fmt) : value}</b>` +
    (o.sub ? `<small>${o.sub}</small>` : "") + "</div>";
}
function fmtVal(v, f) {
  if (f === "int") return Math.round(v).toLocaleString("en-US");
  if ((f === "money" || f === "signed" || !f) && Math.abs(v) >= 1e6) {
    const m = (v < 0 ? "-" : f === "signed" ? "+" : "") + CUR + (Math.abs(v) / 1e6).toFixed(2) + "M";
    return m;
  }
  if (f === "pct") return Math.round(v) + "%";
  if (f === "signed") return signed(v);
  if (f === "place") return ordinal(Math.round(v));
  return money(v);
}
function ordinal(n) {
  const teen = n % 100 >= 11 && n % 100 <= 13, d = n % 10;
  return t(teen ? "st.ord" : d === 1 ? "st.ord1" : d === 2 ? "st.ord2" : d === 3 ? "st.ord3" : "st.ord", { n });
}

function voyageKpis() {
  const v = V.voyage, k = v.me.kpis, n = v.game.players;
  const change = k.worth - k.start_worth;
  return [
    kpi(te("st.k.worth"), k.worth, { cls: "hero", sub: esc(k.rank) }),
    kpi(te("st.k.change"), change, { fmt: "signed", cls: change >= 0 ? "up" : "down", sub: te("st.k.since", { worth: money(k.start_worth) }) }),
    kpi(te("st.k.place"), v.place, { fmt: "place", sub: te("st.k.of", { n }) }),
    kpi(te("st.k.realised"), k.realised, { fmt: "signed", cls: k.realised >= 0 ? "up" : "down", sub: te("st.k.trades", { n: k.trades }) }),
    kpi(te("st.k.score"), k.score == null ? "–" : k.score, { fmt: "int", sub: te("st.k.score_sub") }),
    kpi(te("st.k.voyages"), k.voyages, { fmt: "int", sub: te("st.k.ports", { n: k.ports_visited }) }),
    kpi(te("st.k.battles"), k.won + " / " + k.battles, { sub: te("st.k.won") }),
    kpi(te("st.k.losses"), k.losses, { cls: k.losses ? "down" : "", sub: te("st.k.wrecks", { n: k.wrecks }) })
  ].join("");
}
function careerKpis() {
  const tt = C.career.totals;
  if (!tt.games) return `<p class="muted">${te("st.no_games")}</p>`;
  return [
    kpi(te("st.k.games"), tt.games, { fmt: "int", cls: "hero", sub: te("st.k.finished", { n: tt.finished }) }),
    kpi(te("st.k.wins"), tt.wins, { fmt: "int", sub: tt.win_rate == null ? "" : te("st.k.win_rate", { pct: pct(tt.win_rate) }) }),
    kpi(te("st.k.best"), tt.best, { sub: te("st.k.average", { worth: money(tt.average) }) }),
    kpi(te("st.k.realised"), tt.realised, { fmt: "signed", cls: tt.realised >= 0 ? "up" : "down", sub: te("st.k.trades", { n: tt.trades }) }),
    kpi(te("st.k.score"), tt.score == null ? "–" : tt.score, { fmt: "int", sub: te("st.k.score_sub") }),
    kpi(te("st.k.months"), tt.months, { fmt: "int", sub: te("st.k.voyages_n", { n: tt.voyages }) }),
    kpi(te("st.k.battles"), tt.won + " / " + tt.battles, { sub: te("st.k.won") }),
    kpi(te("st.k.losses"), tt.losses, { cls: tt.losses ? "down" : "", sub: te("st.k.wrecks", { n: tt.wrecks }) })
  ].join("");
}

function countUp(animate) {
  app.querySelectorAll("[data-count]").forEach(el => {
    const to = +el.dataset.count, f = el.dataset.fmt;
    if (!animate || still || !isFinite(to)) { el.textContent = fmtVal(to, f); return; }
    const t0 = performance.now(), dur = 900;
    const step = now => {
      const p = Math.min(1, (now - t0) / dur), e = 1 - Math.pow(1 - p, 3);
      el.textContent = fmtVal(to * e, f);
      if (p < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  });
}

/* --------------------------------------------------------------- panels -- */
const drawers = [];
function panel(id, title, sub, body, opts) {
  const o = opts || {};
  return `<section class="pn ${o.cls || ""}" style="--ga:${id};${o.style || ""}">
    <header><div><h3>${title}</h3>${sub ? `<small>${sub}</small>` : ""}</div>
      <div class="pn-tools">${o.tools || ""}${o.table === false ? "" : btn(icon("table"), "table", `data-id="${id}" aria-label="${te("st.table")}" title="${te("st.table")}"`, "ghost mini")}</div></header>
    <div class="cv" id="c_${id}">${body || ""}</div></section>`;
}
function drawAll(animate) {
  const list = drawers.splice(0);
  ui.redraw = list;
  list.forEach(f => f(animate));
}
function later(fn) { drawers.push(fn); }
function el(id) { return document.getElementById("c_" + id); }
function size(node) { const r = node.getBoundingClientRect(); return [Math.max(220, r.width), Math.max(130, r.height)]; }

function tableHtml(head, rows) {
  return `<div class="tl-table"><table class="grid"><thead><tr>${head.map((h, i) => `<th class="${i ? "n" : ""}">${h}</th>`).join("")}</tr></thead>
    <tbody>${rows.map(r => "<tr>" + r.map((c, i) => `<td class="${i ? "n" : ""}">${c}</td>`).join("") + "</tr>").join("")}</tbody></table></div>`;
}

/* The hover read-out, shared by every chart. */
function showTip(html, x, y) {
  tip.innerHTML = html;
  tip.hidden = false;
  const r = tip.getBoundingClientRect(), W = window.innerWidth, H = window.innerHeight;
  let lx = x + 16, ly = y + 14;
  if (lx + r.width > W - 8) lx = x - r.width - 16;
  if (ly + r.height > H - 8) ly = y - r.height - 14;
  tip.style.left = Math.max(8, lx) + "px";
  tip.style.top = Math.max(8, ly) + "px";
}
function hideTip() { tip.hidden = true; }
function hoverable(node, fn) {
  node.addEventListener("pointermove", e => { const h = fn(e); if (h) showTip(h, e.clientX, e.clientY); else hideTip(); });
  node.addEventListener("pointerleave", hideTip);
}

/* ---------------------------------------------------- the line chart -- */
/* o: { id, xs: [labels], series: [{name, color, vals: [n|null], width}], fmt, area, marks: [{i, label, kind}],
        zero: bool, labels: bool (names at the line ends), tipExtra(i) } */
function lineChart(o, animate) {
  const node = el(o.id);
  if (!node) return;
  const [W, H] = size(node);
  const named = o.labels !== false && o.series.length > 1;
  const pad = { l: 58, r: named ? Math.min(118, 30 + 6.6 * Math.max(...o.series.map(s => String(s.name).length))) : 16, t: (o.marks || []).length ? 26 : 14, b: 26 };
  const n = o.xs.length;
  const all = [];
  o.series.forEach(s => s.vals.forEach(v => { if (v != null) all.push(v); }));
  if (!all.length || n < 1) { node.innerHTML = `<p class="muted empty">${te("st.empty")}</p>`; return; }
  let lo = Math.min(...all), hi = Math.max(...all);
  if (o.zero !== false) { lo = Math.min(lo, 0); hi = Math.max(hi, 0); }
  const ticks = niceTicks(lo, hi, Math.max(3, Math.round(H / 70)));
  lo = Math.min(lo, ticks[0]); hi = Math.max(hi, ticks[ticks.length - 1]);
  const X = i => pad.l + (n === 1 ? (W - pad.l - pad.r) / 2 : i * (W - pad.l - pad.r) / (n - 1));
  const Y = v => pad.t + (hi - v) / (hi - lo || 1) * (H - pad.t - pad.b);
  const fmt = o.fmt || short;
  const out = [`<svg class="lc" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}">`];
  ticks.forEach(tk => out.push(`<line class="gl${tk === 0 ? " zero" : ""}" x1="${pad.l}" x2="${W - pad.r}" y1="${Y(tk)}" y2="${Y(tk)}"/>` +
    `<text class="ax" x="${pad.l - 8}" y="${Y(tk) + 4}" text-anchor="end">${esc(fmt(tk))}</text>`));
  const every = Math.max(1, Math.ceil(n / Math.max(2, Math.floor((W - pad.l - pad.r) / 74))));
  // Month labels: evenly spaced, never touching (about 6px a letter).
  let right = -1e9;
  const labelAt = i => {
    const w = String(o.xs[i]).length * 6.2, anchor = n > 1 && i === n - 1 ? "end" : n > 1 && i === 0 ? "start" : "middle";
    const left = anchor === "start" ? X(i) : anchor === "end" ? X(i) - w : X(i) - w / 2;
    return { left, w, anchor };
  };
  const lastL = labelAt(n - 1);
  o.xs.forEach((x, i) => {
    if (i % every !== 0 && i !== n - 1) return;
    const L = labelAt(i);
    if (L.left < right + 10) return;
    if (i !== n - 1 && n > 1 && L.left + L.w + 10 > lastL.left) return;
    right = L.left + L.w;
    out.push(`<text class="ax" x="${X(i)}" y="${H - 7}" text-anchor="${L.anchor}">${esc(x)}</text>`);
  });
  const ends = [];
  o.series.forEach((s, si) => {
    let d = "", started = false, lastI = -1;
    s.vals.forEach((v, i) => {
      if (v == null) { started = false; return; }
      d += (started ? "L" : "M") + X(i).toFixed(1) + " " + Y(v).toFixed(1);
      started = true; lastI = i;
    });
    if (!d) return;
    if (o.area && o.series.length === 1) {
      const first = s.vals.findIndex(v => v != null);
      out.push(`<path class="ar${animate && !still ? " fade" : ""}" d="${d}L${X(lastI)} ${Y(Math.max(lo, 0))}L${X(first)} ${Y(Math.max(lo, 0))}Z" fill="${s.color}"/>`);
    }
    out.push(`<path class="ln${animate && !still ? " draw" : ""}" pathLength="1" d="${d}" stroke="${s.color}" style="stroke-width:${s.width || 2}px;animation-delay:${si * 120}ms"/>`);
    if (n <= 1 || s.vals.filter(v => v != null).length === 1) out.push(`<circle class="pt" cx="${X(lastI)}" cy="${Y(s.vals[lastI])}" r="5" fill="${s.color}"/>`);
    if (named && lastI >= 0) ends.push({ y: Y(s.vals[lastI]), y0: Y(s.vals[lastI]), x: X(lastI), s });
  });
  // Names at the line ends, nudged apart so they never sit on each other.
  ends.sort((a, b) => a.y - b.y);
  for (let i = 1; i < ends.length; i++) if (ends[i].y - ends[i - 1].y < 15) ends[i].y = ends[i - 1].y + 15;
  ends.forEach(e => out.push(`<circle class="pt" cx="${e.x}" cy="${e.y0}" r="3.5" fill="${e.s.color}"/>` +
    `<text class="endl" x="${W - pad.r + 8}" y="${e.y + 4}"><tspan fill="${e.s.color}">■</tspan> ${esc(e.s.name)}</text>`));
  (o.marks || []).forEach(m => {
    const s = o.series[0], v = s.vals[m.i];
    if (v == null) return;
    const glyph = m.kind === "bad" ? '<path d="M-3 -3L3 3M3 -3L-3 3"/>' : m.kind === "down" ? '<path d="M-3 -1.5L0 2.5L3 -1.5"/>' : "";
    out.push(`<g class="mk mk-${m.kind || "rank"}" transform="translate(${X(m.i)},${Y(v)})"><circle r="6.5"/>${glyph}` +
      (m.short ? `<text y="-12" text-anchor="middle">${esc(m.short)}</text>` : "") + "</g>");
  });
  out.push(`<line class="xh" x1="0" x2="0" y1="${pad.t}" y2="${H - pad.b}" visibility="hidden"/>`);
  out.push(`<rect class="hit" x="${pad.l}" y="0" width="${Math.max(1, W - pad.l - pad.r)}" height="${H}"/></svg>`);
  node.innerHTML = out.join("");
  const svg = node.querySelector("svg"), xh = svg.querySelector(".xh");
  hoverable(svg, e => {
    const r = svg.getBoundingClientRect();
    const px = (e.clientX - r.left) * W / r.width;
    const i = n === 1 ? 0 : Math.max(0, Math.min(n - 1, Math.round((px - pad.l) / ((W - pad.l - pad.r) / (n - 1)))));
    xh.setAttribute("x1", X(i)); xh.setAttribute("x2", X(i)); xh.setAttribute("visibility", "visible");
    const rows = o.series.filter(s => s.vals[i] != null).sort((a, b) => b.vals[i] - a.vals[i])
      .map(s => `<div><i style="background:${s.color}"></i>${esc(s.name)}<b>${esc((o.tipFmt || money)(s.vals[i]))}</b></div>`).join("");
    const mark = (o.marks || []).filter(m => m.i === i).map(m => `<div class="tip-note">${esc(m.label)}</div>`).join("");
    return `<p>${esc(o.xs[i])}</p>${rows}${mark}${o.tipExtra ? o.tipExtra(i) : ""}`;
  });
  svg.addEventListener("pointerleave", () => xh.setAttribute("visibility", "hidden"));
  ui.tables[o.id] = () => tableHtml([te("st.col.month")].concat(o.series.map(s => esc(s.name))),
    o.xs.map((x, i) => [esc(x)].concat(o.series.map(s => s.vals[i] == null ? "·" : esc((o.tipFmt || money)(s.vals[i]))))));
}

/* ------------------------------------------------- horizontal bars -- */
/* Diverging around zero when any value is negative. items: [{label, value, sub, tip}] */
function bars(id, items, opts, animate) {
  const node = el(id);
  if (!node) return;
  const o = opts || {};
  if (!items.length) { node.innerHTML = `<p class="muted empty">${te(o.empty || "st.empty")}</p>`; return; }
  const max = Math.max(1, ...items.map(i => Math.abs(i.value)));
  const neg = items.some(i => i.value < 0), pos = items.some(i => i.value > 0);
  const split = neg && pos ? Math.max(.2, Math.min(.8, Math.max(...items.map(i => i.value < 0 ? -i.value : 0)) /
    (Math.max(...items.map(i => Math.max(0, i.value))) + Math.max(...items.map(i => i.value < 0 ? -i.value : 0))))) : neg ? 1 : 0;
  const rows = items.map((it, k) => {
    const w = Math.abs(it.value) / max * (it.value < 0 ? split : 1 - split) * 100;
    const left = it.value < 0 ? split * 100 - w : split * 100;
    const color = o.color ? o.color(it) : it.value >= 0 ? `rgb(${POS})` : `rgb(${NEG})`;
    return `<div class="br" data-k="${k}"><span class="bl">${it.label}</span>
      <span class="bt"><i class="${animate && !still ? "grow" : ""}" style="left:${left}%;width:${Math.max(.6, w)}%;background:${color};animation-delay:${k * 45}ms"></i>
      ${neg && pos ? `<em style="left:${split * 100}%"></em>` : ""}</span>
      <b class="${it.value < 0 ? "down" : ""}">${(o.fmt || signed)(it.value)}</b></div>`;
  }).join("");
  node.innerHTML = `<div class="bars">${rows}</div>`;
  hoverable(node, e => {
    const r = e.target.closest(".br");
    if (!r) return null;
    const it = items[+r.dataset.k];
    return it.tip || `<p>${it.label}</p><div><b>${(o.fmt || signed)(it.value)}</b></div>${it.sub ? `<div class="tip-note">${it.sub}</div>` : ""}`;
  });
  ui.tables[id] = () => tableHtml([te("st.col.item"), te("st.col.value")], items.map(i => [i.label, (o.fmt || signed)(i.value)]));
}

/* --------------------------------------------------------- heat maps -- */
/* o: { rows: [{k, label}], cols: [{k, label}], val(r, c), text(r, c, v), tip(r, c, v), kind: "div" | "seq",
        lo, hi, legend: [left, right] } */
function heat(id, o, animate) {
  const node = el(id);
  if (!node) return;
  const vals = [];
  o.rows.forEach(r => o.cols.forEach(c => { const v = o.val(r.k, c.k); if (v != null) vals.push(v); }));
  if (!vals.length) { node.innerHTML = `<p class="muted empty">${te(o.empty || "st.empty")}</p>`; return; }
  const max = Math.max(1, ...vals.map(Math.abs));
  const lo = o.lo != null ? o.lo : Math.min(...vals), hi = o.hi != null ? o.hi : Math.max(...vals);
  const cells = [];
  cells.push(`<div class="hc hh"></div>` + o.cols.map(c => `<div class="hc hh" title="${esc(c.title || "")}">${esc(c.label)}</div>`).join(""));
  let k = 0;
  o.rows.forEach(r => {
    cells.push(`<div class="hc hr">${esc(r.label)}</div>`);
    o.cols.forEach(c => {
      const v = o.val(r.k, c.k);
      const bg = v == null ? null : o.kind === "seq" ? seqColor(v, lo, hi) : divColor(v, o.max || max);
      const text = v == null ? "" : o.text ? o.text(r.k, c.k, v) : "";
      cells.push(`<div class="hc cell${v == null ? " none" : ""}${animate && !still ? " pop" : ""}" data-r="${esc(r.k)}" data-c="${esc(c.k)}"` +
        ` style="${bg ? `background:${bg};color:${inkOn(bg)};` : ""}animation-delay:${Math.min(900, k * 9)}ms">${text}</div>`);
      k++;
    });
  });
  const legend = o.legend ? `<div class="hlg"><span>${o.legend[0]}</span><i class="${o.kind === "seq" ? "seq" : "div"}"></i><span>${o.legend[1]}</span>` +
    (o.legend[2] ? `<span class="none-key"><i></i>${o.legend[2]}</span>` : "") + "</div>" : "";
  node.innerHTML = `<div class="heat" style="grid-template-columns: minmax(5.6rem, auto) repeat(${o.cols.length}, minmax(${o.min || "2.4rem"}, 1fr))">${cells.join("")}</div>${legend}`;
  hoverable(node, e => {
    const c = e.target.closest(".cell");
    if (!c) return null;
    const v = o.val(c.dataset.r, c.dataset.c);
    return o.tip ? o.tip(c.dataset.r, c.dataset.c, v) : `<p>${esc(c.dataset.r)} · ${esc(c.dataset.c)}</p><div><b>${v == null ? "–" : signed(v)}</b></div>`;
  });
  ui.tables[id] = () => tableHtml([""].concat(o.cols.map(c => esc(c.label))),
    o.rows.map(r => [esc(r.label)].concat(o.cols.map(c => { const v = o.val(r.k, c.k); return v == null ? "·" : (o.tableFmt || money)(v); }))));
}

function spark(vals, color, w, h) {
  const v = vals.filter(x => x != null);
  if (v.length < 2) return "";
  const lo = Math.min(...v, 0), hi = Math.max(...v, 0), W = w || 120, H = h || 30;
  const pts = vals.map((x, i) => x == null ? null : [i * W / (vals.length - 1), H - 2 - (x - lo) / (hi - lo || 1) * (H - 4)]).filter(Boolean);
  const zero = H - 2 - (0 - lo) / (hi - lo || 1) * (H - 4);
  return `<svg class="spark" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none"><line x1="0" x2="${W}" y1="${zero}" y2="${zero}" class="z"/>` +
    `<polyline points="${pts.map(p => p.map(n => n.toFixed(1)).join(",")).join(" ")}" stroke="${color}"/></svg>`;
}

/* =================================================== THIS VOYAGE ===== */
const VOYAGE = {
  fortune() {
    const me = V.voyage.me, m = me.months;
    const xs = m.map(r => r.date);
    later(a => lineChart({ id: "worth", xs, area: true, series: [{ name: t("st.worth"), color: SINGLE, vals: m.map(r => r.worth), width: 2.5 }],
      marks: me.rankups.map(r => ({ i: m.findIndex(x => x.turn === r.turn), label: t(r.up ? "st.rankup" : "st.rankdown", { rank: r.rank }),
                                    short: r.up ? "★" : "", kind: r.up ? "rank" : "down" }))
        .concat(me.moments.filter(x => x.kind === "wreck").map(x => ({ i: m.findIndex(r => r.turn === x.turn + 1), label: t("st.m.wreck"), short: "", kind: "bad" })))
        .filter(x => x.i >= 0),
      tipExtra: i => `<div class="tip-note">${esc(portName(m[i].port))} · ${te("st.ships_n", { n: m[i].ships })} · ${te("st.guns_n", { n: m[i].guns })}</div>` }, a));
    later(a => lineChart({ id: "purse", xs, series: [
      { name: t("st.cash"), color: ser(0), vals: m.map(r => r.cash) },
      { name: t("st.bank"), color: ser(2), vals: m.map(r => r.bank) },
      { name: t("st.debt"), color: ser(1), vals: m.map(r => -r.debt) }] }, a));
    later(a => bars("cargo", me.cargo.filter(c => c.trades).map(c => ({
      label: esc(goodName(c.good)), value: c.profit,
      tip: `<p>${esc(goodName(c.good))}</p><div>${te("st.bought")}<b>${c.bought_qty} · ${money(c.bought_cost)}</b></div>` +
        `<div>${te("st.sold")}<b>${c.sold_qty} · ${money(c.sold_rev)}</b></div>` +
        `<div>${te("st.avg")}<b>${c.avg_buy == null ? "–" : money(c.avg_buy)} → ${c.avg_sell == null ? "–" : money(c.avg_sell)}</b></div>` +
        (c.lost_qty ? `<div>${te("st.lost")}<b>${c.lost_qty} · ${money(c.lost_value)}</b></div>` : "") +
        `<div>${te("st.margin_paid")}<b>${money(c.margin_paid)}</b></div><div>${te("st.impact")}<b>${money(c.impact)}</b></div><div class="tip-note">${te("st.profit")} ${signed(c.profit)}</div>`
    })), { empty: "st.no_trades" }, a));
    const lines = Object.entries(me.lines).filter(([k, v]) => v).sort((a, b) => b[1] - a[1])
      .map(([k, v]) => ({ label: te("st.line." + k), value: v }));
    later(a => bars("lines", lines, {}, a));
    return `<div class="pg pg-fortune">
      ${panel("worth", te("st.p.worth"), te("st.p.worth_sub"), "", { cls: "wide tall" })}
      ${panel("purse", te("st.p.purse"), te("st.p.purse_sub"))}
      ${panel("cargo", te("st.p.cargo"), te("st.p.cargo_sub"))}
      ${panel("lines", te("st.p.lines"), te("st.p.lines_sub"))}
      ${panel("trades", te("st.p.trades"), te("st.p.trades_sub"), tradeList(me), { table: false })}
    </div>`;
  },

  routes() {
    const me = V.voyage.me;
    const turns = me.months.map(r => r.turn), dates = me.months.map(r => r.date);
    const portsAll = Object.keys(D.ports);
    const mode = ui.heat === "standing" ? "standing" : "profit";
    later(a => seaMap("map", me, a));
    if (mode === "profit") {
      later(a => heat("pheat", {
        rows: portsAll.map(k => ({ k, label: portName(k) })),
        cols: turns.map((tn, i) => ({ k: String(tn), label: monthShort(dates[i]), title: dates[i] })),
        val: (p, tn) => { const v = (me.heat_port_month[p] || {})[tn]; return v == null ? null : v; },
        tip: (p, tn, v) => `<p>${esc(portName(p))} · ${esc(dates[turns.indexOf(+tn)])}</p><div>${te("st.profit")}<b>${signed(v)}</b></div>`,
        legend: [te("st.loss"), te("st.gain"), te("st.no_sales")], min: "1.5rem", empty: "st.no_trades"
      }, a));
    } else {
      const reps = [].concat(...portsAll.map(p => (me.rep[p] || []).filter(v => v != null)));
      const lo = Math.min(...reps), hi = Math.max(...reps);
      later(a => heat("pheat", {
        rows: portsAll.map(k => ({ k, label: portName(k) })),
        cols: turns.map((tn, i) => ({ k: String(i), label: monthShort(dates[i]), title: dates[i] })),
        val: (p, i) => (me.rep[p] || [])[+i], kind: "seq", lo, hi,
        text: (p, i, v) => +i === turns.length - 1 || +i === 0 ? v : "",
        tip: (p, i, v) => `<p>${esc(portName(p))} · ${esc(dates[+i])}</p><div>${te("st.standing")}<b>${v}</b></div>`,
        legend: [String(lo), String(hi)], min: "1.5rem", tableFmt: v => v
      }, a));
    }
    const pr = me.ports.filter(p => p.visits || p.sales || p.buys);
    later(a => bars("ports", pr.map(p => ({ label: esc(portName(p.port)), value: p.profit,
      sub: te("st.port_sub", { visits: p.visits, buys: p.buys, sales: p.sales }) })), {}, a));
    const sw = btn(te("st.heat_profit"), "heat", 'data-h="profit"', "mini " + (mode === "profit" ? "on" : "")) +
      btn(te("st.heat_standing"), "heat", 'data-h="standing"', "mini " + (mode === "standing" ? "on" : ""));
    return `<div class="pg pg-routes">
      ${panel("map", te("st.p.map"), te("st.p.map_sub"), "", { tools: btn(icon("play") + `<span>${te("st.replay")}</span>`, "replay", "", "mini on") })}
      ${panel("ports", te("st.p.ports"), te("st.p.ports_sub"))}
      ${panel("pheat", te(mode === "profit" ? "st.p.pmonth" : "st.p.rep"), te(mode === "profit" ? "st.p.pmonth_sub" : "st.p.rep_sub"), "", { cls: "wide", tools: sw })}
    </div>`;
  },

  markets() {
    const me = V.voyage.me, mk = me.markets, goods = Object.keys(D.goods);
    if (!ui.good || !D.goods[ui.good]) ui.good = (me.cargo[0] && me.cargo[0].good) || goods[0];
    const avg = {};
    goods.forEach(g => {
      const vals = Object.values(mk.latest).map(r => r[g] && r[g].price).filter(v => v != null);
      avg[g] = vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null;
    });
    const now = V.voyage.game.turn;
    later(a => heat("prices", {
      rows: Object.keys(D.ports).map(k => ({ k, label: portName(k) })),
      cols: goods.map(g => ({ k: g, label: goodName(g).split(" ")[0] })),
      val: (p, g) => { const c = (mk.latest[p] || {})[g]; return c && avg[g] ? (c.price - avg[g]) / avg[g] : null; },
      max: .6,
      text: (p, g) => { const c = mk.latest[p][g]; return `<b>${short(c.price).replace(CUR, "")}</b>${mk.full ? "" : `<small>${ago(now - c.turn)}</small>`}`; },
      tip: (p, g, v) => { const c = (mk.latest[p] || {})[g];
        return `<p>${esc(goodName(g))} · ${esc(portName(p))}</p><div>${te("st.price")}<b>${money(c.price)}</b></div>` +
          `<div>${te("st.vs_avg")}<b>${(v >= 0 ? "+" : "") + Math.round(v * 100)}%</b></div><div class="tip-note">${te("st.seen", { when: ago(now - c.turn) })}</div>`; },
      legend: [te("st.cheap"), te("st.dear"), mk.full ? "" : te("st.never_seen")], min: "3.4rem",
      tableFmt: v => (v >= 0 ? "+" : "") + Math.round(v * 100) + "%"
    }, a));
    later(a => priceSmall("history", me, ui.good, a));
    later(a => scoreHist("scores", me, a));
    const chips = goods.map(g => btn(esc(goodName(g)), "good", `data-g="${g}"`, "mini " + (g === ui.good ? "on" : ""))).join("");
    return `<div class="pg pg-markets">
      ${panel("prices", te("st.p.prices"), mk.full ? te("st.p.prices_full") : te("st.p.prices_fair"), "", { cls: "wide" })}
      ${panel("history", th("st.p.history", { good: esc(goodName(ui.good)) }), te("st.p.history_sub"), "", { cls: "tall", tools: `<div class="chips">${chips}</div>` })}
      ${panel("scores", te("st.p.scores"), te("st.p.scores_sub"))}
    </div>`;
  },

  perils() {
    const v = V.voyage, me = v.me, p = me.perils;
    const everyone = [me].concat(v.rivals);
    const xs = me.months.map(r => r.date);
    later(a => lineChart({ id: "race", xs, series: everyone.map(h => ({
      name: h.firm, color: ser(h.color), width: h.id === me.id ? 3 : 2,
      vals: xs.map((_d, i) => { const row = (h.months || []).find(r => r.turn === me.months[i].turn); return row ? row.worth : null; })
    })) }, a));
    later(a => raceBars("racebars", everyone, me, a));
    const tiles = [
      ["storm", t("st.t.storms"), p.storms, t("st.t.storm_sub", { dmg: p.storm_damage, n: p.typhoons })],
      ["battle", t("st.t.battles"), p.battles, t("st.t.battle_sub", { won: p.won, ran: p.escaped, off: p.broke_off, lost: p.plundered })],
      ["ship", t("st.t.gunnery"), me.kpis.accuracy == null ? "–" : pct(me.kpis.accuracy), t("st.t.gunnery_sub", { sunk: me.battles.reduce((s, b) => s + b.sunk, 0) })],
      ["rank", t("st.t.booty"), money(p.booty), t("st.t.booty_sub", { n: p.won })],
      ["seized", t("st.t.seized"), p.seizures, t("st.t.seized_sub", { v: money(p.seized_value + p.fines) })],
      ["robbed", t("st.t.robbed"), p.robbed, t("st.t.robbed_sub", { v: money(p.robbed_value) })],
      ["wreck", t("st.t.wrecks"), p.wrecks, t("st.t.wrecks_sub", { n: p.ships_lost })],
      ["perils", t("st.t.driven"), p.driven_off, t("st.t.driven_sub")]
    ];
    const losses = [["plunder_value", p.plunder_value], ["seized_value", p.seized_value], ["fines", p.fines],
      ["robbed_value", p.robbed_value], ["wreck_cash", p.wreck_cash], ["wreck_cargo_value", p.wreck_cargo_value],
      ["cargo_lost_value", p.cargo_lost_value]].filter(x => x[1]).map(([k, val]) => ({ label: te("st.loss." + k), value: -val }));
    later(a => bars("losses", losses, { empty: "st.no_losses" }, a));
    return `<div class="pg pg-perils">
      ${panel("race", te("st.p.race"), v.game.reveal ? te("st.p.race_sub") : te("st.p.race_fair"), "", { cls: "wide" })}
      ${panel("racebars", te("st.p.racebars"), te("st.p.racebars_sub"), "", { tools: btn(icon("play") + `<span>${te("st.play")}</span>`, "race", "", "mini on"), table: false })}
      ${panel("tiles", te("st.p.tiles"), te("st.p.tiles_sub"), `<div class="tiles">${tiles.map(x =>
        `<div class="tile">${icon(x[0])}<span>${esc(x[1])}</span><b>${esc(String(x[2]))}</b><small>${esc(x[3])}</small></div>`).join("")}</div>`, { table: false })}
      ${panel("losses", te("st.p.losses"), te("st.p.losses_sub"))}
      ${panel("battles", te("st.p.battles"), te("st.p.battles_sub"), battleList(me), { table: false })}
      ${panel("h2h", te("st.p.h2h"), v.game.reveal ? te("st.p.h2h_sub") : te("st.p.h2h_fair"), headToHead(v), { cls: "wide", table: false })}
    </div>`;
  }
};

function monthShort(date) { return String(date || "").split(" ")[0].slice(0, 1); }
function ago(n) { return n <= 0 ? t("st.now") : t("st.ago", { n }); }

function tradeList(me) {
  const row = (tr, cls) => `<li class="${cls}"><span class="sc" title="${te("st.k.score")}">${tr.score == null ? "–" : tr.score}</span>
      <div><b>${esc(goodName(tr.good))}</b><small>${te("st.trade_line", { qty: tr.qty, port: portName(tr.port), date: tr.date })}</small>
      <small>${te("st.trade_sub", { buy: money(tr.basis / Math.max(1, tr.qty)), sell: money(tr.unit), pct: tr.pct == null ? "–" : Math.round(tr.pct * 100) + "%" })}</small></div>
      <em class="${tr.profit < 0 ? "down" : "up"}">${signed(tr.profit)}</em></li>`;
  if (!me.best.length && !me.worst.length) return `<p class="muted empty">${te("st.no_trades")}</p>`;
  const best = me.best.filter(x => x.profit > 0).map(x => row(x, "good")).join("");
  const worst = me.worst.map(x => row(x, "bad")).join("");
  return `<div class="trades"><p class="eyebrow">${te("st.best")}</p>${best ? `<ul>${best}</ul>` : `<p class="muted">–</p>`}
    <p class="eyebrow">${te("st.worst")}</p>${worst ? `<ul>${worst}</ul>` : `<p class="muted">${te("st.no_worst")}</p>`}</div>`;
}

function battleList(me) {
  if (!me.battles.length) return `<p class="muted empty">${te("st.no_battles")}</p>`;
  return `<ul class="blist">${me.battles.slice().reverse().map(b => `<li class="r-${b.result}">${icon(b.result === "won" ? "rank" : b.result === "plundered" ? "robbed" : "battle")}
    <div><b>${th("st.b.title", { n: b.count, enemy: esc(b.enemy || "") })}</b><small>${esc(b.date)}${b.route ? " · " + esc(portName(b.route[0])) + " → " + esc(portName(b.route[1])) : ""} · ${th("st.b.orders", { o: esc(b.orders || "") })}</small></div>
    <span>${te("st.b." + b.result)}<small>${b.booty ? "+" + money(b.booty) : b.plundered ? "-" + money(b.plundered) : b.paid ? "-" + money(b.paid) : b.overboard ? "-" + money(b.overboard) : te("st.b.rounds", { n: b.rounds, sunk: b.sunk })}</small></span></li>`).join("")}</ul>`;
}

function headToHead(v) {
  const all = [v.voyage ? v.voyage.me : v.me].concat(v.rivals).sort((a, b) => b.kpis.worth - a.kpis.worth);
  const full = v.game.reveal;
  const head = [te("col.house"), te("st.k.worth"), te("st.peak")].concat(full ? [te("st.k.realised"), te("st.k.score"), te("st.k.trades_h"), te("st.k.battles"), te("st.t.wrecks"), te("st.best_cargo")] : []);
  const rows = all.map((h, i) => {
    const k = h.kpis;
    const base = [`${i + 1}. <i class="chip" style="background:${ser(h.color)}"></i><b>${esc(h.firm)}</b> <span class="muted">${esc(h.name)}</span> <span class="rankname">${esc(k.rank)}</span>`,
      money(k.worth), money(k.peak)];
    return full ? base.concat([signed(k.realised), k.score == null ? "–" : k.score, k.trades, k.won + "/" + k.battles, k.wrecks,
      k.best_cargo ? esc(goodName(k.best_cargo)) : "–"]) : base;
  });
  return tableHtml(head, rows) + (full ? "" : `<p class="muted lockline">${icon("lock")}${te("st.h2h_locked")}</p>`);
}

/* The sea chart with every voyage traced on it, and a replay of the whole run. */
function seaMap(id, me, animate) {
  const node = el(id);
  if (!node) return;
  const legs = me.legs || [];
  const P = k => D.ports[k];
  const curve = (a, b, bend) => {
    const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2, dx = b.x - a.x, dy = b.y - a.y;
    return `M${a.x} ${a.y} Q${mx - dy * bend} ${my + dx * bend} ${b.x} ${b.y}`;
  };
  const maxCount = Math.max(1, ...me.routes.map(r => r.count));
  const routes = me.routes.filter(r => P(r.origin) && P(r.dest) && r.origin !== r.dest).map((r, i) =>
    `<path class="rt" data-i="${i}" d="${curve(P(r.origin), P(r.dest), .18)}" style="stroke-width:${2 + 7 * r.count / maxCount}px"/>`).join("");
  const marks = legs.map(l => {
    const a = P(l.origin), b = P(l.arrived || l.dest);
    if (!a || !b) return "";
    const x = (a.x + b.x) / 2 - (b.y - a.y) * .09, y = (a.y + b.y) / 2 + (b.x - a.x) * .09;
    const kind = l.outcome === "wrecked" ? "wreck" : l.perils.includes("battle") ? "battle" : l.perils.some(p => p === "storm" || p === "typhoon") ? "storm" : l.perils.includes("seized") ? "seized" : null;
    return kind ? `<g class="pm pm-${kind}" transform="translate(${x - 9},${y - 9}) scale(.75)"><circle cx="12" cy="12" r="13"/>${ICON[kind]}</g>` : "";
  }).join("");
  const visits = {};
  me.ports.forEach(p => { visits[p.port] = p.visits; });
  const halo = Object.keys(visits).filter(k => P(k) && visits[k]).map(k =>
    `<circle class="vh" cx="${P(k).x}" cy="${P(k).y}" r="${8 + Math.sqrt(visits[k]) * 5}"/>`).join("");
  const base = Chart.svg({ data: D, weather: {}, crackdown: [] });
  const overlay = `<g class="trails">${halo}${routes}</g><g class="perilmarks">${marks}</g>
    <path class="sail" id="sailpath" d=""/><g class="ship" id="mapship" visibility="hidden"><circle r="9"/><path d="M-5 3h10l-2 3h-6z M0 3v-9l5 6h-5"/></g>
    <text class="mapdate" id="mapdate" x="26" y="580"></text>`;
  node.innerHTML = `<div class="map">${base.replace("</svg>", overlay + "</svg>")}</div>`;
  if (animate && !still) node.querySelectorAll(".rt").forEach((p, i) => { p.style.animationDelay = (i * 70) + "ms"; p.classList.add("draw"); });
  hoverable(node, e => {
    const r = e.target.closest(".rt");
    if (!r) return null;
    const x = me.routes.filter(rr => P(rr.origin) && P(rr.dest) && rr.origin !== rr.dest)[+r.dataset.i];
    return `<p>${esc(portName(x.origin))} → ${esc(portName(x.dest))}</p><div>${te("st.sailed")}<b>${x.count}</b></div>` +
      `<div>${te("st.perils_met")}<b>${x.perils}</b></div><div>${te("st.route_profit")}<b>${signed(x.profit)}</b></div>`;
  });
  ui.tables[id] = () => tableHtml([te("st.col.route"), te("st.sailed"), te("st.perils_met"), te("st.route_profit")],
    me.routes.map(r => [esc(portName(r.origin)) + " → " + esc(portName(r.dest)), r.count, r.perils, signed(r.profit)]));
}

function replayMap() {
  const me = V && V.voyage.me;
  if (!me || !me.legs.length) return;
  stopTimers();
  const ship = document.getElementById("mapship"), path = document.getElementById("sailpath"), label = document.getElementById("mapdate");
  if (!ship) return;
  let i = 0, t0 = null;
  const LEG = still ? 1 : 900;
  ship.setAttribute("visibility", "visible");
  const step = now => {
    if (!document.getElementById("mapship")) return;
    const l = me.legs[i];
    const a = D.ports[l.origin], b = D.ports[l.arrived || l.dest];
    if (!a || !b) { i++; t0 = null; if (i < me.legs.length) ui.mapTimer = requestAnimationFrame(step); return; }
    if (t0 === null) {
      t0 = now;
      const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2, dx = b.x - a.x, dy = b.y - a.y;
      path.setAttribute("d", `M${a.x} ${a.y} Q${mx - dy * .18} ${my + dx * .18} ${b.x} ${b.y}`);
      label.textContent = l.date + " · " + portName(l.origin) + " → " + portName(l.arrived || l.dest);
      ship.setAttribute("class", "ship" + (l.outcome === "wrecked" ? " wrecked" : l.perils.length ? " rough" : ""));
    }
    const p = Math.min(1, (now - t0) / LEG);
    const len = path.getTotalLength(), pt = path.getPointAtLength(len * p);
    ship.setAttribute("transform", `translate(${pt.x},${pt.y})`);
    if (p < 1) { ui.mapTimer = requestAnimationFrame(step); return; }
    i++; t0 = null;
    if (i < me.legs.length) ui.mapTimer = requestAnimationFrame(step);
  };
  ui.mapTimer = requestAnimationFrame(step);
}

/* A bar race of every house's net worth, month by month. */
function raceBars(id, houses, me, animate) {
  const node = el(id);
  if (!node) return;
  const months = me.months;
  if (!months.length) { node.innerHTML = `<p class="muted empty">${te("st.empty")}</p>`; return; }
  const at = ui.raceAt == null ? months.length - 1 : ui.raceAt;
  const values = houses.map(h => {
    const row = (h.months || []).find(r => r.turn === months[at].turn);
    return { h, v: row ? row.worth : 0 };
  });
  const max = Math.max(1, ...values.map(x => Math.abs(x.v)));
  const order = values.slice().sort((a, b) => b.v - a.v);
  node.innerHTML = `<div class="race" style="height:${houses.length * 2.6}rem">${values.map(x => {
    const rank = order.indexOf(x);
    return `<div class="rb${x.h.id === me.id ? " me" : ""}" style="transform:translateY(${rank * 2.6}rem)">
      <span class="rn"><i class="chip" style="background:${ser(x.h.color)}"></i>${esc(x.h.firm)}</span>
      <span class="rt2"><i style="width:${Math.max(1, Math.abs(x.v) / max * 100)}%;background:${ser(x.h.color)};${x.v < 0 ? "opacity:.45" : ""}"></i></span>
      <b>${short(x.v)}</b></div>`;
  }).join("")}</div>
  <div class="racectl"><input type="range" min="0" max="${months.length - 1}" value="${at}" data-act="raceat" aria-label="${te("st.col.month")}"><span>${esc(months[at].date)}</span></div>`;
  node.querySelector("input").addEventListener("input", e => { ui.raceAt = +e.target.value; stopTimers(); raceBars(id, houses, me, false); });
  ui.raceData = { id, houses, me };
}
function playRace() {
  const r = ui.raceData;
  if (!r) return;
  stopTimers();
  ui.raceAt = 0;
  raceBars(r.id, r.houses, r.me, false);
  ui.raceTimer = setInterval(() => {
    if (ui.raceAt >= r.me.months.length - 1) { clearInterval(ui.raceTimer); ui.raceTimer = null; return; }
    ui.raceAt++;
    raceBars(r.id, r.houses, r.me, false);
  }, still ? 60 : 420);
}

/* Small multiples: one cargo's price in every port, with this house's trades on it. */
function priceSmall(id, me, good, animate) {
  const node = el(id);
  if (!node) return;
  const hist = me.markets.history[good] || {};
  const ports = Object.keys(D.ports).filter(p => (hist[p] || []).length);
  if (!ports.length) { node.innerHTML = `<p class="muted empty">${te("st.never_seen_good")}</p>`; return; }
  const all = [].concat(...ports.map(p => hist[p].map(x => x[1])));
  const lo = Math.min(...all), hi = Math.max(...all);
  const t0 = Math.min(...[].concat(...ports.map(p => hist[p].map(x => x[0])))), t1 = Math.max(V.voyage.game.turn, t0 + 1);
  const W = 260, H = 70;
  const X = tn => 6 + (tn - t0) / (t1 - t0) * (W - 12), Y = v => 6 + (hi - v) / (hi - lo || 1) * (H - 14);
  const trades = me.trades.filter(tr => tr.good === good);
  node.innerHTML = `<div class="smalls">${ports.map(p => {
    const pts = hist[p];
    const d = pts.map((x, i) => (i ? "L" : "M") + X(x[0]).toFixed(1) + " " + Y(x[1]).toFixed(1)).join("");
    const dots = pts.length < 3 ? pts.map(x => `<circle cx="${X(x[0])}" cy="${Y(x[1])}" r="2.5" fill="${SINGLE}"/>`).join("") : "";
    const tr = trades.filter(x => x.port === p).map(x => x.side === "buy"
      ? `<path class="tb" d="M${X(x.turn)} ${Y(x.unit) - 7}l5 8h-10z"/>` : `<path class="ts" d="M${X(x.turn)} ${Y(x.unit) + 7}l5 -8h-10z"/>`).join("");
    const last = pts[pts.length - 1][1];
    return `<figure data-p="${p}"><figcaption>${esc(portName(p))}<b>${money(last)}</b></figcaption>
      <svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none"><path class="ln${animate && !still ? " draw" : ""}" pathLength="1" d="${d}" stroke="${SINGLE}"/>${dots}${tr}</svg></figure>`;
  }).join("")}</div><div class="hlg"><span><svg class="key" viewBox="0 0 12 10"><path class="tb" d="M6 1l5 8H1z"/></svg>${te("st.you_bought")}</span><span><svg class="key" viewBox="0 0 12 10"><path class="ts" d="M6 9l5-8H1z"/></svg>${te("st.you_sold")}</span></div>`;
  hoverable(node, e => {
    const f = e.target.closest("figure");
    if (!f) return null;
    const p = f.dataset.p, pts = hist[p];
    const svg = f.querySelector("svg").getBoundingClientRect();
    const tn = t0 + (e.clientX - svg.left) / svg.width * (t1 - t0);
    const near = pts.reduce((a, b) => Math.abs(b[0] - tn) < Math.abs(a[0] - tn) ? b : a);
    const mine = trades.filter(x => x.port === p && x.turn === near[0]).map(x =>
      `<div>${te(x.side === "buy" ? "st.you_bought" : "st.you_sold")}<b>${x.qty} @ ${money(x.unit)}</b></div>`).join("");
    return `<p>${esc(portName(p))} · ${esc(engineDate(near[0]))}</p><div>${te("st.price")}<b>${money(near[1])}</b></div>${mine}`;
  });
  ui.tables[id] = () => tableHtml([te("col.port"), te("st.col.month"), te("st.price")],
    [].concat(...ports.map(p => hist[p].map(x => [esc(portName(p)), esc(engineDate(x[0])), money(x[1])]))));
}
function engineDate(turn) {
  return t("mon." + (turn % 12)) + " " + (D.start_year + Math.floor(turn / 12));
}

/* How every trade scored: a histogram from "paid over the odds" to "a steal". */
function scoreHist(id, me, animate) {
  const node = el(id);
  if (!node) return;
  const sc = me.trades.filter(x => x.score != null);
  if (!sc.length) { node.innerHTML = `<p class="muted empty">${te("st.no_trades")}</p>`; return; }
  const bins = Array.from({ length: 10 }, () => ({ buy: 0, sell: 0 }));
  sc.forEach(x => { bins[Math.min(9, Math.floor(x.score / 10))][x.side]++; });
  const max = Math.max(1, ...bins.map(b => b.buy + b.sell));
  const avg = me.kpis.score;
  node.innerHTML = `<div class="dial"><svg viewBox="0 0 120 70"><path class="dial-bg" d="M10 62a50 50 0 0 1 100 0"/>
      <path class="dial-fg${animate && !still ? " draw" : ""}" pathLength="1" style="--to:${1 - avg / 100}" d="M10 62a50 50 0 0 1 100 0"/>
      <text x="60" y="58" text-anchor="middle">${avg}</text></svg><small>${te("st.score_means")}</small></div>
    <div class="costs"><span>${te("st.margin_paid")}<b>${money(me.kpis.margin_paid)}</b></span><span>${te("st.impact")}<b>${money(me.kpis.impact)}</b></span></div>
    <div class="hist">${bins.map((b, i) => `<div class="hb" data-i="${i}" title="">
      <i class="${animate && !still ? "rise" : ""}" style="height:${(b.buy + b.sell) / max * 100}%;animation-delay:${i * 50}ms">
        <i class="sb" style="height:${b.buy + b.sell ? b.sell / (b.buy + b.sell) * 100 : 0}%"></i></i><span>${i * 10}</span></div>`).join("")}</div>
    <div class="hlg"><span><i class="sw" style="background:${ser(0)}"></i>${te("st.buys")}</span><span><i class="sw" style="background:${ser(3)}"></i>${te("st.sells")}</span><span>${te("st.score_axis")}</span></div>`;
  hoverable(node, e => {
    const b = e.target.closest(".hb");
    if (!b) return null;
    const i = +b.dataset.i, x = bins[i];
    return `<p>${te("st.score_range", { a: i * 10, b: i * 10 + 9 })}</p><div>${te("st.buys")}<b>${x.buy}</b></div><div>${te("st.sells")}<b>${x.sell}</b></div>`;
  });
  ui.tables[id] = () => tableHtml([te("st.k.score"), te("st.buys"), te("st.sells")], bins.map((b, i) => [i * 10 + "–" + (i * 10 + 9), b.buy, b.sell]));
}

/* ========================================================= CAREER ===== */
const CAREER = {
  fortune() {
    const c = C.career;
    if (!c.games.length) return `<p class="muted empty big">${te("st.no_games")}</p>`;
    const games = c.games.slice().reverse();
    const gl = games.map((g, i) => t("st.game_n", { n: i + 1 }));
    later(a => lineChart({ id: "finals", xs: gl, area: true,
      series: [{ name: t("st.final_worth"), color: SINGLE, vals: games.map(g => g.worth), width: 2.5 }],
      tipExtra: i => `<div class="tip-note">${esc(games[i].first)} – ${esc(games[i].last)} · ${te("st.place_of", { place: ordinal(games[i].place), n: games[i].players })}${games[i].running ? " · " + te("st.in_progress") : ""}</div>` }, a));
    later(a => bars("ccargo", c.cargo.filter(x => x.trades).map(x => ({ label: esc(goodName(x.good)), value: x.profit,
      sub: te("st.ccargo_sub", { b: x.bought_qty, s: x.sold_qty }) })), { empty: "st.no_trades" }, a));
    return `<div class="pg pg-cfortune">
      ${panel("games", te("st.p.games"), te("st.p.games_sub"), gameCards(c), { cls: "tall", table: false })}
      ${panel("finals", te("st.p.finals"), te("st.p.finals_sub"), "", { cls: "wide" })}
      ${panel("ccargo", te("st.p.ccargo"), te("st.p.ccargo_sub"))}
      ${panel("records", te("st.p.records"), te("st.p.records_sub"), recordsHtml(c), { table: false })}
    </div>`;
  },
  routes() {
    const c = C.career;
    later(a => bars("cports", c.ports.filter(p => p.visits || p.sales).map(p => ({ label: esc(portName(p.port)), value: p.profit,
      sub: te("st.port_sub", { visits: p.visits, buys: p.buys, sales: p.sales }) })), {}, a));
    later(a => heat("cheat", {
      rows: Object.keys(D.ports).map(k => ({ k, label: portName(k) })),
      cols: Object.keys(D.goods).map(g => ({ k: g, label: goodName(g).split(" ")[0] })),
      val: (p, g) => { const v = (c.heat[p] || {})[g]; return v == null ? null : v; },
      text: (p, g, v) => short(v),
      tip: (p, g, v) => `<p>${esc(goodName(g))} ${te("st.sold_in")} ${esc(portName(p))}</p><div>${te("st.profit")}<b>${signed(v)}</b></div>`,
      legend: [te("st.loss"), te("st.gain"), te("st.no_sales")], min: "3.2rem", empty: "st.no_trades"
    }, a));
    later(a => bars("cvisits", c.ports.filter(p => p.visits).sort((x, y) => y.visits - x.visits)
      .map(p => ({ label: esc(portName(p.port)), value: p.visits })), { fmt: v => v, color: () => SINGLE }, a));
    return `<div class="pg pg-croutes">
      ${panel("cheat", te("st.p.cheat"), te("st.p.cheat_sub"), "", { cls: "wide" })}
      ${panel("cports", te("st.p.cports"), te("st.p.cports_sub"))}
      ${panel("cvisits", te("st.p.cvisits"), te("st.p.cvisits_sub"))}
    </div>`;
  },
  markets() {
    const c = C.career, games = c.games.slice().reverse().filter(g => g.score != null);
    const all = c.games.slice().reverse();
    later(a => lineChart({ id: "cscore", xs: games.map(g => t("st.game_n", { n: all.indexOf(g) + 1 })), zero: false,
      fmt: v => Math.round(v), tipFmt: v => Math.round(v), series: [{ name: t("st.k.score"), color: SINGLE, vals: games.map(g => g.score) }] }, a));
    const rows = c.cargo.map(x => [esc(goodName(x.good)), x.bought_qty, x.sold_qty, x.trades, money(x.lost_value), signed(x.profit)]);
    return `<div class="pg pg-cmarkets">
      ${panel("cscore", te("st.p.cscore"), te("st.p.cscore_sub"), "", { cls: "wide" })}
      ${panel("cbook", te("st.p.cbook"), te("st.p.cbook_sub"), rows.length ? tableHtml([te("st.cargo"), te("st.bought"), te("st.sold"), te("st.k.trades_h"), te("st.lost"), te("st.profit")], rows)
        : `<p class="muted empty">${te("st.no_trades")}</p>`, { cls: "wide", table: false })}
    </div>`;
  },
  perils() {
    const c = C.career, tt = c.totals, games = c.games.slice().reverse();
    later(a => lineChart({ id: "places", xs: games.map((g, i) => t("st.game_n", { n: i + 1 })), zero: false, fmt: v => v < 0 && v === Math.round(v) ? ordinal(-v) : "",
      tipFmt: v => ordinal(-v), series: [{ name: t("st.k.place"), color: SINGLE, vals: games.map(g => -g.place) }],
      tipExtra: i => `<div class="tip-note">${te("st.place_of", { place: ordinal(games[i].place), n: games[i].players })}</div>` }, a));
    const tiles = [["rank", t("st.k.wins"), tt.wins, t("st.t.podiums", { n: tt.podiums })],
      ["battle", t("st.t.battles"), tt.battles, t("st.t.won_n", { n: tt.won })], ["rank", t("st.t.booty"), money(tt.booty), ""],
      ["storm", t("st.t.storms"), tt.storms, ""], ["seized", t("st.t.seized"), tt.seizures, ""],
      ["wreck", t("st.t.wrecks"), tt.wrecks, t("st.t.wrecks_sub", { n: tt.ships_lost })], ["robbed", t("st.k.losses"), money(tt.losses), ""],
      ["markets", t("st.margin_paid"), money(tt.margin_paid), t("st.t.margin_sub")],
      ["markets", t("st.impact"), money(tt.impact), t("st.t.impact_sub")]];
    return `<div class="pg pg-cperils">
      ${panel("ctiles", te("st.p.ctiles"), te("st.p.ctiles_sub"), `<div class="tiles">${tiles.map(x =>
        `<div class="tile">${icon(x[0])}<span>${esc(x[1])}</span><b>${esc(String(x[2]))}</b><small>${esc(x[3])}</small></div>`).join("")}</div>`, { cls: "wide", table: false })}
      ${panel("places", te("st.p.places"), te("st.p.places_sub"), "", { cls: "wide" })}
    </div>`;
  }
};

function gameCards(c) {
  return `<ul class="gcards">${c.games.map(g => `<li><button type="button" data-act="open" data-g="${esc(g.id)}">
      <span class="gp p${Math.min(g.place, 4)}">${g.running ? "⋯" : ordinal(g.place)}</span><i class="gn">${te("st.game_n", { n: c.games.length - c.games.indexOf(g) })}</i>
      <div class="gt"><b>${esc(g.firm || "")}</b><small>${g.running ? th("st.game_now", { first: esc(g.first) }) : th("st.game_span", { first: esc(g.first), last: esc(g.last), n: g.players })}</small></div>
      <span class="gs">${spark(g.curve, g.worth >= 0 ? SINGLE : `rgb(${NEG})`, 110, 30)}</span>
      <em class="${g.worth < 0 ? "down" : ""}">${short(g.worth)}<small>${esc(g.rank)}</small></em></button></li>`).join("")}</ul>`;
}

function recordsHtml(c) {
  const r = c.records, out = [];
  const add = (key, val, sub) => { if (r[key]) out.push(`<li><span>${te("st.r." + key)}</span><b>${val}</b><small>${sub}</small></li>`); };
  add("best_finish", r.best_finish && money(r.best_finish.value), r.best_finish && esc(r.best_finish.firm + " · " + r.best_finish.date));
  add("peak_worth", r.peak_worth && money(r.peak_worth.value), r.peak_worth && esc(r.peak_worth.date));
  add("best_sale", r.best_sale && signed(r.best_sale.value), r.best_sale && te("st.r.sale_sub", { qty: r.best_sale.qty, good: goodName(r.best_sale.good), port: portName(r.best_sale.port), date: r.best_sale.date }));
  add("worst_sale", r.worst_sale && signed(r.worst_sale.value), r.worst_sale && te("st.r.sale_sub", { qty: r.worst_sale.qty, good: goodName(r.worst_sale.good), port: portName(r.worst_sale.port), date: r.worst_sale.date }));
  add("biggest_booty", r.biggest_booty && money(r.biggest_booty.value), r.biggest_booty && te("st.r.booty_sub", { n: r.biggest_booty.count, date: r.biggest_booty.date }));
  add("biggest_fight", r.biggest_fight && r.biggest_fight.value, r.biggest_fight && te("st.r.fight_sub", { result: t("st.b." + r.biggest_fight.result), date: r.biggest_fight.date }));
  add("best_score", r.best_score && r.best_score.value, r.best_score && esc(r.best_score.firm));
  Object.keys(r).filter(k => k.startsWith("rank_")).sort((a, b) => r[a].value - r[b].value).forEach(k =>
    out.push(`<li><span>${th("st.r.rank", { rank: esc(r[k].rank) })}</span><b>${te("st.r.months", { n: r[k].value })}</b><small>${esc(r[k].firm + " · " + r[k].date)}</small></li>`));
  return out.length ? `<ul class="records">${out.join("")}</ul>` : `<p class="muted empty">${te("st.empty")}</p>`;
}

/* -------------------------------------------------------------- events -- */
function stopTimers() {
  if (ui.raceTimer) { clearInterval(ui.raceTimer); ui.raceTimer = null; }
  if (ui.mapTimer) { cancelAnimationFrame(ui.mapTimer); ui.mapTimer = null; }
}

app.addEventListener("click", e => {
  const b = e.target.closest("[data-act]");
  if (!b || b.tagName === "SELECT" || b.tagName === "INPUT") return;
  const d = b.dataset;
  switch (d.act) {
    case "scope": ui.scope = d.s; store("tally_scope", d.s); return render(true);
    case "tab": ui.tab = d.tab; store("tally_tab", d.tab); ui.raceAt = null; return render(true);
    case "good": ui.good = d.g; return redraw();
    case "heat": ui.heat = d.h; return redraw();
    case "open": ui.game = d.g; ui.scope = "voyage"; store("tally_scope", "voyage"); ui.lastJson = {}; return load(false);
    case "who": ui.name = d.name; return load(false);
    case "replay": return replayMap();
    case "race": return playRace();
    case "table": {
      const node = el(d.id);
      if (!node || !ui.tables[d.id]) return;
      if (node.dataset.tbl) { delete node.dataset.tbl; b.classList.remove("on"); return redraw(); }
      node.dataset.tbl = "1";
      b.classList.add("on");
      node.innerHTML = ui.tables[d.id]();
      return;
    }
    case "back":
      if (EMBED) { parent.postMessage({ tally: "close" }, location.origin); return; }
      if (window.opener && !window.opener.closed) { window.close(); return; }
      location.href = "/";
      return;
  }
});
app.addEventListener("change", e => {
  if (e.target.dataset.act === "game") { ui.game = e.target.value; ui.lastJson = {}; load(false); }
});
function redraw() {
  // Charts are sized to their panels, so draw again after a resize (no animation the second time).
  const main = document.getElementById("main");
  if (!main) return;
  const vs = ui.scope === "voyage" && V;
  const keep = main.scrollTop;
  ui.tables = {};
  main.innerHTML = (vs ? VOYAGE : CAREER)[ui.tab]();
  drawAll(false);
  main.scrollTop = keep;
}
let resizeT = null;
window.addEventListener("resize", () => { if (!ui.visible) return; clearTimeout(resizeT); resizeT = setTimeout(redraw, 160); });
document.addEventListener("keydown", e => {
  if (e.key === "Escape") { const x = app.querySelector(".tl-x"); if (x) x.click(); }
});
// While a game is in progress the numbers move every month: look again now and then.
setInterval(() => { if (ui.visible && !document.hidden && V && V.voyage.game.running && !ui.raceTimer && !ui.mapTimer) load(true); }, 20000);
// Inside the player screen: the deck says when the Tally Book is shown or hidden, and when a month passes.
window.addEventListener("message", e => {
  if (e.origin !== location.origin || !e.data || !e.data.tally) return;
  const m = e.data.tally;
  if (m === "hide") { ui.visible = false; stopTimers(); hideTip(); return; }
  if (m === "show") { ui.visible = true; requestAnimationFrame(() => { if (V || C) render(true); load(true); }); return; }
  if (m === "refresh" && ui.visible) load(true);
});
document.addEventListener("visibilitychange", () => { if (ui.visible && !document.hidden && V) load(true); });

(async function start() {
  try {
    const info = await loadInfo();
    D = info.data;
    document.title = t("st.title") + " · " + [D.brand.title_a, D.brand.title_b].filter(Boolean).join(" ");
  } catch (e) {
    return message(te("ui.no_server"));
  }
  const want = new URLSearchParams(location.search);
  if (want.get("scope")) ui.scope = want.get("scope");
  if (want.get("game")) ui.game = want.get("game");
  if (!TABS.includes(ui.tab)) ui.tab = "fortune";
  load(false);
})();
