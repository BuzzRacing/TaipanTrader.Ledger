/* SeaTrader Admin. Draws itself from the settings description the server sends
   (config.py SECTIONS), so a new setting added there appears here on its own.
   Nothing is applied until "Save & apply"; then every open screen updates. */
"use strict";

const $ = (s, r) => (r || document).querySelector(s);
const main = $("#main");
let A = null;            // everything from /api/admin/all
let CFG = null;          // settings being edited
let SAVED = "";          // settings as last saved (JSON text)
let LANGS = {};          // language files being edited
let LANGS_SAVED = "";
let LIVE = null;         // latest live game state
let liveHold = 0;        // do not redraw the live page while someone is typing in it
let section = (location.hash || "#live").slice(1);
let errors = [];
let polling = false;
const FIELD = {}, COL = {};
const lv = { code: "en", q: "", group: "", changed: false, family: false };

const NAV = [
  ["Game", [["live", "Live Game"], ["captains", "Captains"], ["report", "Captain's Report"]]],
  ["Identity", [["brand", "Brand"], ["theme", "Look & Style"], ["graphics", "Graphics"], ["artbible", "Art Bible"], ["media", "Media Library"], ["clips", "Voices"], ["language", "Language & Text"]]],
  ["Rules", [["ratings", "Ratings & Difficulty"], ["game", "Game Setup"], ["economy", "Economy"], ["goods", "Cargo"],
             ["ports", "Ports"], ["ships", "Ships"], ["weather", "Weather & Seas"], ["danger", "Pirates & Customs"]]],
  ["System", [["backup", "Backup & Access"]]],
];
const NAV_MARKS = ["I", "II", "III", "IV"];
/* Voices is one nav entry with three tabs. Each tab is still its own section (clips, voices, cast). */
const VOICE_TABS = [["clips", "Clips"], ["voices", "Voice Library"], ["cast", "Cast & Voices"]];
const navOn = id => id === section || (id === "clips" && VOICE_TABS.some(([t]) => t === section));
function voiceTabs(active) {
  return `<nav class="vtabs" aria-label="Voices">${VOICE_TABS.map(([id, label]) =>
    `<button type="button" class="vtab${id === active ? " on" : ""}" data-vtab="${id}"${id === active ? ' aria-current="page"' : ""}>${label}${
      CFG && id === "cast" && sectionChanged(id) ? '<i aria-label="Unsaved changes"></i>' : ""}</button>`).join("")}</nav>`;
}
const openNavGroups = new Set(NAV.filter(([, items]) => items.some(([id]) => navOn(id))).map(([title]) => title));

/* ------------------------------------------------------------- basics -- */
function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, c =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
const clone = o => JSON.parse(JSON.stringify(o));
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
function get(o, path) { return path.split(".").reduce((d, k) => (d == null ? d : d[k]), o); }
function set(o, path, v) {
  const parts = path.split(".");
  const last = parts.pop();
  parts.reduce((d, k) => d[k], o)[last] = v;
}
const money = n => (n < 0 ? "-" : "") + CFG.brand.currency + Math.abs(Math.round(n)).toLocaleString("en-US");
const when = sec => new Date(sec * 1000).toLocaleString();
const fmtPct = v => String(Math.round(v * 1e6) / 1e4);

let toastTimer = null;
function toast(msg, bad) {
  const el = $("#toast");
  el.textContent = msg || "";
  el.className = "show" + (bad ? " bad" : "");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.className = ""; }, bad ? 5000 : 2600);
}

async function api(path, body, rawBody) {
  const opt = body === undefined && rawBody === undefined ? {} : {
    method: "POST", headers: { "X-SeaTrader": "admin" },
    body: rawBody !== undefined ? rawBody : JSON.stringify(body),
  };
  let res;
  try {
    const r = await fetch("/api/admin/" + path, opt);
    res = await r.json();
  } catch (e) {
    return { ok: false, error: "Cannot reach the game server." };
  }
  if (res.auth) showLogin(res.has_password);
  return res;
}

function showLogin(hasPassword) {
  $("#login").hidden = false;
  $("#loginmsg").textContent = hasPassword ? "Enter the admin password."
    : "No admin password has been set yet. Open this page on the computer running the game and set one under Backup & Access.";
}
$("#loginform").addEventListener("submit", async e => {
  e.preventDefault();
  const res = await api("login", { password: $("#loginpw").value });
  if (!res.ok) { $("#loginmsg").textContent = res.error; return; }
  $("#login").hidden = true;
  boot();
});

/* -------------------------------------------------------------- state -- */
const isDirty = () => JSON.stringify(CFG) !== SAVED || JSON.stringify(LANGS) !== LANGS_SAVED;
function refreshDirty() {
  const d = isDirty();
  const changed = d ? NAV.flatMap(([, items]) => items).filter(([id]) => sectionChanged(id)).map(([, label]) => label) : [];
  $("#top").classList.toggle("dirty", d);
  $("#saved").hidden = d;
  $("#dirty").hidden = !d;
  $("#dirty").textContent = changed.length === 1 ? "Unsaved: " + changed[0]
    : (changed.length || 1) + " pages unsaved";
  $("#dirty").title = changed.join(", ");
  $("#discard").hidden = !d;
  $("#save").hidden = !d;
  $("#save").disabled = !d;
  brandMark();
  drawNav();
}
/* Header emblem and browser tab icon follow Graphics > Browser icon (the Art Bible's brass mark). */
function brandMark() {
  const banner = CFG?.graphics?.admin_masthead_bg || "";
  $(".masthead").style.backgroundImage = banner ? `url(${JSON.stringify(banner)})` : "none";
  const url = (CFG && CFG.graphics && CFG.graphics.favicon) || "/assets/branding/crimson-ledger-icon-v01.png";
  if ($("#gmark").getAttribute("src") !== url) $("#gmark").src = url;
  if ($("#favicon").getAttribute("href") !== url) $("#favicon").href = url;
  const logo = CFG?.graphics?.logo || "";
  const name = [CFG.brand.title_a, CFG.brand.title_b].filter(Boolean).join(" ");
  $("#glogo").hidden = !logo;
  $("#gname").hidden = !!logo;
  $("#gmark").hidden = !!logo;
  $("#glogo").alt = name;
  if (logo && $("#glogo").getAttribute("src") !== logo) $("#glogo").src = logo;
}
window.addEventListener("keydown", e => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") { e.preventDefault(); if (!$("#save").disabled && !$("#save").hidden) $("#save").click(); }
});
window.addEventListener("beforeunload", e => { if (CFG && isDirty()) { e.preventDefault(); e.returnValue = ""; } });

function sectionChanged(id) {
  const saved = JSON.parse(SAVED);
  if (id === "language") return JSON.stringify(LANGS) !== LANGS_SAVED || !same(CFG.language, saved.language);
  if (id === "graphics") return !same(CFG.graphics, saved.graphics);
  if (id === "cast") return SeaTraderCast.sectionChanged(saved);
  if (id === "clips" || id === "voices") return SeaTraderCast.sectionChanged(saved);
  const sec = A.sections.find(s => s.id === id);
  if (!sec) return false;
  return sectionPaths(sec).some(p => !same(get(CFG, p), get(saved, p)));
}
function sectionPaths(sec) {
  const out = [];
  (sec.groups || []).forEach(g => g.fields.forEach(f => out.push(f.path)));
  (sec.tables || []).forEach(t => out.push(t.path));
  if (sec.matrix && !out.includes(sec.matrix.path)) out.push(sec.matrix.path);
  return out;
}

function drawNav() {
  $("#nav").innerHTML = NAV.map(([title, items], index) => {
    const groupId = "nav-group-" + title.toLowerCase();
    const open = openNavGroups.has(title);
    const active = items.some(([id]) => navOn(id));
    return `<section class="nav-group${open ? " open" : ""}${active ? " active" : ""}">
      <button type="button" class="nav-section-toggle" data-nav-group="${title}" aria-expanded="${open}" aria-controls="${groupId}">
        <span class="nav-section-mark" aria-hidden="true">${NAV_MARKS[index]}</span>
        <span class="nav-section-copy"><span class="nav-section-kicker">Command deck</span><strong>${title}</strong></span>
        <span class="nav-section-chevron" aria-hidden="true"></span>
      </button>
      <div class="nav-options" id="${groupId}"${open ? "" : " hidden"}>${items.map(([id, label]) =>
        `<button type="button" data-nav="${id}" class="nav-option${navOn(id) ? " on" : ""}"${navOn(id) ? ' aria-current="page"' : ""}>
          <span>${label}</span>${CFG && sectionChanged(id) ? '<i aria-label="Unsaved changes"></i>' : ""}
        </button>`).join("")}</div>
    </section>`;
  }).join("");
}
main.addEventListener("click", e => {
  const t = e.target.closest("[data-vtab]");
  if (t && CFG) go(t.dataset.vtab);
});
$("#nav").addEventListener("click", e => {
  const toggle = e.target.closest("[data-nav-group]");
  if (toggle) {
    const title = toggle.dataset.navGroup;
    if (openNavGroups.has(title)) openNavGroups.delete(title); else openNavGroups.add(title);
    drawNav();
    return;
  }
  const a = e.target.closest("[data-nav]");
  if (a) go(a.dataset.nav);
});
function go(id) {
  if (section === "cast" && id !== "cast") SeaTraderCast.leave();
  if (section === "voices" && id !== "voices") SeaTraderVoices.leave();
  if (section === "clips" && id !== "clips") SeaTraderClips.leave();
  if (VOICE_TABS.some(([t]) => t === id)) openNavGroups.add("Identity");
  if (section === "captains" && id !== "captains") SeaTraderCaptains.leave();
  if (section === "report" && id !== "report") SeaTraderReport.leave();
  if (section === "media" && id !== "media") SeaTraderMedia.leave();
  if (section === "graphics" && id !== "graphics") SeaTraderGraphics.leave();
  if (id === "graphics") SeaTraderGraphics.enter();
  if (id === "live") openNavGroups.add("Game");
  section = id;
  history.replaceState(null, "", "#" + section);
  liveHold = 0;
  draw();
  window.scrollTo(0, 0);
}
$("#top").addEventListener("click", e => {
  const a = e.target.closest("[data-nav]");
  if (!a || !CFG) return;
  e.preventDefault();
  go(a.dataset.nav);
});

async function boot() {
  const res = await api("all");
  if (!res.ok) return;
  A = res;
  CFG = clone(A.config);
  try {
    const response = await fetch("/api/info");
    if (!response.ok) throw new Error("HTTP " + response.status);
    const info = await response.json();
    Ranks.configure(info.data);
    Media.setup(info.media);
  } catch (error) {
    console.error("Could not load captain rank colors", error);
    Ranks.configure({ ranks: CFG.ranks });
    toast("Could not load captain rank colors. Reload to try again.", true);
  }
  SAVED = JSON.stringify(CFG);
  LANGS = clone(A.lang);
  LANGS_SAVED = JSON.stringify(LANGS);
  if (!LANGS[lv.code]) lv.code = "en";
  A.sections.forEach(sec => {
    (sec.groups || []).forEach(g => g.fields.forEach(f => { FIELD[f.path] = f; }));
    (sec.tables || []).forEach(t => { COL[t.path] = {}; t.columns.forEach(c => { COL[t.path][c.key] = c; }); });
  });
  const gameName = [CFG.brand.title_a, CFG.brand.title_b].filter(Boolean).join(" ");
  $("#gname").textContent = gameName;
  document.title = gameName + " · Command Center";
  draw();
  refreshDirty();
  if (!polling) { polling = true; pollLive(); }
}

/* ------------------------------------------------------------ controls -- */
function optionsFor(spec) {
  if (spec.options) return spec.options;
  const src = get(CFG, spec.options_from) || {};
  return Object.keys(src).map(k => [k, src[k].name || k]);
}

function control(spec, v, attrs) {
  switch (spec.type) {
    case "text": return `<input type="text" ${attrs} value="${esc(v)}" maxlength="${spec.max || 200}">`;
    case "code": return `<textarea ${attrs} class="code" rows="9" spellcheck="false">${esc(v)}</textarea>`;
    case "int": case "num":
      return `<input type="number" ${attrs} value="${esc(v)}" step="${spec.type === "int" ? 1 : (spec.step || "any")}"` +
        `${spec.min != null ? ` min="${spec.min}"` : ""}${spec.max != null ? ` max="${spec.max}"` : ""}>`;
    case "pct": return `<span class="unit"><input type="number" ${attrs} value="${fmtPct(v)}" step="any"><i>%</i></span>`;
    case "bool": return `<input type="checkbox" ${attrs} ${v ? "checked" : ""}>`;
    case "select":
      return `<select ${attrs}>` + optionsFor(spec).map(o =>
        `<option value="${esc(o[0])}" ${o[0] === v ? "selected" : ""}>${esc(o[1])}</option>`).join("") + "</select>";
    case "color":
      return `<span class="color"><input type="color" ${attrs} value="${esc(v)}">` +
        `<input type="text" ${attrs} data-hex="1" value="${esc(v)}" maxlength="7" class="mono"></span>`;
    case "colorlist":
      return '<span class="colors">' + v.map((c, i) => `<input type="color" ${attrs} data-i="${i}" value="${esc(c)}">`).join("") + "</span>";
    case "numlist": return `<input type="text" ${attrs} value="${esc(v.join(", "))}">`;
    case "lines": return `<textarea ${attrs} rows="9">${esc(v.join("\n"))}</textarea>`;
    case "json": return `<textarea ${attrs} class="code" rows="2" spellcheck="false">${esc(JSON.stringify(v))}</textarea>`;
  }
  return "";
}

/* Reads a control back into a value. Returns undefined if what was typed is not usable. */
function readControl(el, spec, current) {
  const raw = el.value;
  switch (spec.type) {
    case "text": case "code": case "select": return raw;
    case "bool": return el.checked;
    case "int": case "num": case "pct": {
      if (raw.trim() === "" || isNaN(Number(raw))) return undefined;
      let n = Number(raw);
      if (spec.type === "pct") n = Math.round(n * 1e4) / 1e6;
      if (spec.type === "int") n = Math.round(n);
      if ((spec.min != null && n < spec.min) || (spec.max != null && n > spec.max)) return undefined;
      return n;
    }
    case "color": return /^#[0-9a-f]{6}$/i.test(raw) ? raw.toLowerCase() : undefined;
    case "colorlist": { const a = current.slice(); a[+el.dataset.i] = raw; return a; }
    case "numlist": {
      const a = raw.split(/[,\s]+/).filter(Boolean).map(Number);
      return a.length && a.every(n => !isNaN(n)) && (!spec.count || a.length === spec.count) ? a : undefined;
    }
    case "lines": return raw.split("\n").map(s => s.trim()).filter(Boolean);
    case "json": try { return JSON.parse(raw); } catch (e) { return undefined; }
  }
  return undefined;
}

const showDefault = (spec, v) => spec.type === "pct" ? fmtPct(v) + "%"
  : Array.isArray(v) ? (spec.type === "lines" ? v.length + " lines" : v.join(", "))
  : spec.type === "bool" ? (v ? "on" : "off") : String(v).slice(0, 60);

function fieldHtml(f) {
  const v = get(CFG, f.path), d = get(A.defaults, f.path);
  const wide = ["code", "lines", "colorlist"].includes(f.type);
  return `<div class="f${wide ? " wide" : ""}${same(v, d) ? "" : " mod"}" data-f="${f.path}">
    <label><span>${esc(f.label)}</span><button type="button" class="reset" data-reset="${f.path}" title="Back to the default: ${esc(showDefault(f, d))}">default</button></label>
    ${control(f, v, `data-path="${f.path}"`)}${f.help ? `<small>${esc(f.help)}</small>` : ""}</div>`;
}

function groupHtml(g) {
  return `<section class="card"><h2>${esc(g.title)}</h2><div class="fields${g.cols === 3 ? " c3" : ""}">${g.fields.map(fieldHtml).join("")}</div></section>`;
}

function blankRow(tb) {
  // Start from a copy of the last row, so the numbers are sensible ones to adjust.
  const rows = get(CFG, tb.path);
  const last = Array.isArray(rows) ? rows[rows.length - 1] : rows[Object.keys(rows).pop()];
  const row = clone(last || {});
  tb.columns.forEach(c => { if (row[c.key] === undefined) row[c.key] = c.type === "bool" ? false : c.type === "text" ? "" : 1; });
  if (tb.path === "ports") { row.mods = {}; row.no_ban = false; }
  if (tb.path === "goods") { row.family_name = ""; row.contraband = false; row.ban_odds = 0; }
  if (tb.path === "ranks") { row.worth = Math.max(0, row.worth) * 2 || 1000; row.title = "New rank"; }
  return row;
}

/* Cargo always lists dearest first (by usual price), wherever it is shown. Edits do not re-sort while typing;
   the list settles into order the next time it is drawn (add, remove, save, or opening the page). */
function goodsByPrice(keys) {
  const base = k => { const g = (CFG.goods || {})[k]; return g ? Number(g.base) || 0 : -1; };
  return keys.slice().sort((a, b) => base(b) - base(a));
}

function tableHtml(tb) {
  const rows = get(CFG, tb.path);
  const dict = tb.kind === "dict";
  const keys = dict ? (tb.path === "goods" ? goodsByPrice(Object.keys(rows)) : Object.keys(rows)) : rows.map((r, i) => i);
  const head = (dict ? `<th>${esc(tb.id_label || "Key")}</th>` : "") +
    tb.columns.map(c => `<th title="${esc(c.help || "")}">${esc(c.label)}${c.help ? " ⓘ" : ""}</th>`).join("") + "<th></th>";
  const body = keys.map(k => "<tr>" + (dict ? `<td class="mono">${esc(k)}</td>` : "") +
    tb.columns.map(c => `<td class="${c.type === "bool" ? "c" : ""}">${control(c, rows[k][c.key], `data-t="${tb.path}" data-r="${esc(k)}" data-c="${c.key}"`)}</td>`).join("") +
    `<td><button type="button" class="danger confirm" data-del="${tb.path}" data-r="${esc(k)}" ${keys.length < 2 ? "disabled" : ""}>Remove</button></td></tr>`).join("");
  const add = dict
    ? `<input type="text" id="new_${tb.path}" placeholder="new key, e.g. ${tb.path === "ports" ? "macao" : tb.path === "goods" ? "cotton" : "name"}" maxlength="24" class="mono">
       <button type="button" data-add="${tb.path}">Add</button><span class="muted small">Keys are lower-case, permanent and never shown to players.</span>`
    : `<button type="button" data-add="${tb.path}">Add a row</button>`;
  return `<section class="card"><div class="head"><h2>${esc(tb.title)}</h2>
      <button type="button" class="link" data-reset="${tb.path}" data-table="1">restore defaults</button></div>
    ${tb.help ? `<p class="help">${esc(tb.help)}</p>` : ""}
    <div class="scroll"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>
    <div class="row">${add}</div></section>`;
}

function matrixHtml(m) {
  const rows = get(CFG, m.path), cols = get(CFG, m.cols_from);
  const colKeys = m.cols_from === "goods" ? goodsByPrice(Object.keys(cols)) : Object.keys(cols);
  const head = "<th>Port</th>" + colKeys.map(g => `<th class="n">${esc(cols[g].name)}<br><span class="muted">${money(cols[g].base)}</span></th>`).join("");
  const body = Object.keys(rows).map(p => `<tr><td><b>${esc(rows[p].name)}</b></td>` + colKeys.map(g => {
    const v = (rows[p][m.sub] || {})[g];
    const price = cols[g].base * (v == null ? 1 : v);
    return `<td class="${v == null ? "" : v < 1 ? "lo" : "hi"}"><input type="number" step="0.05" min="${m.min}" max="${m.max}" placeholder="1" ` +
      `value="${v == null ? "" : v}" data-m="${m.path}" data-r="${esc(p)}" data-c="${esc(g)}" title="Usual price here: ${money(price)}"></td>`;
  }).join("") + "</tr>").join("");
  return `<section class="card"><h2>${esc(m.title)}</h2><p class="help">${esc(m.help)} Green is cheap there, red is dear. Hover over a cell for the resulting price.</p>
    <div class="scroll"><table class="matrix"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div></section>`;
}

function schemaSection(sec) {
  const groups = (sec.groups || []).map(groupHtml).join("");
  const tables = (sec.tables || []).map(tableHtml).join("") + (sec.matrix ? matrixHtml(sec.matrix) : "");
  const extra = sec.id === "theme" ? `<section class="card"><div class="head"><h2>Preview</h2>
      <span><a href="/" target="_blank">Open player screen</a> · <a href="/board" target="_blank">Open harbor board</a></span></div>
      <p class="help">Colours, fonts and corners show here as you change them. Nothing reaches the players until you save.</p>
      <iframe class="preview" id="preview" src="/" title="Player screen preview"></iframe></section>` : "";
  return head(sec.title, sec.intro, `<button type="button" class="link confirm" data-resetsec="${sec.id}">reset this page to defaults</button>`) +
    (["ratings", "brand", "theme", "game", "economy", "danger"].includes(sec.id) ? groups + tables : tables + groups) + extra;
}

function head(title, intro, right) {
  return `<div class="head"><h1>${esc(title)}</h1>${right || ""}</div><p class="intro">${esc(intro || "")}</p>` +
    (errors.length ? `<section class="card errors"><h2>Not saved: these need fixing</h2><ul>${errors.map(e => "<li>" + esc(e) + "</li>").join("")}</ul></section>` : "");
}

/* ---------------------------------------------------------------- draw -- */
function draw() {
  drawNav();
  if (!CFG) return;
  const sec = A.sections.find(s => s.id === section);
  if (sec) main.innerHTML = schemaSection(sec);
  else if (section === "graphics") main.innerHTML = SeaTraderGraphics.render();
  else if (section === "artbible") {
    main.innerHTML = SeaTraderArtBible.render(CFG);
    SeaTraderArtBible.hydrate();
  }
  else if (section === "cast") main.innerHTML = SeaTraderCast.render();
  else if (section === "clips") { main.innerHTML = SeaTraderClips.render(); SeaTraderClips.enter(); }
  else if (section === "voices") { main.innerHTML = SeaTraderVoices.render(); SeaTraderVoices.enter(); }
  else if (section === "captains") { main.innerHTML = SeaTraderCaptains.render(); SeaTraderCaptains.enter(); }
  else if (section === "media") { main.innerHTML = SeaTraderMedia.render(); SeaTraderMedia.enter(); }
  else if (section === "report") { main.innerHTML = SeaTraderReport.render(); SeaTraderReport.enter(); }
  else if (section === "language") main.innerHTML = languageSection();
  else if (section === "backup") main.innerHTML = backupSection();
  else { section = "live"; main.innerHTML = liveSection(); }
  if (section === "theme") { const f = $("#preview"); if (f) f.addEventListener("load", previewTheme); }
}

function previewTheme() {
  const f = $("#preview");
  if (!f || !f.contentDocument) return;
  const st = f.contentDocument.documentElement.style, th = CFG.theme;
  Object.keys(th.colors).forEach(k => st.setProperty("--" + k, th.colors[k]));
  st.setProperty("--serif", th.font_serif);
  st.setProperty("--sans", th.font_sans);
  st.setProperty("--base-size", th.font_size + "px");
  st.setProperty("--radius", th.radius + "px");
}

/* ------------------------------------------------------------ graphics -- */
/* Admin > Graphics lives in graphics-admin.js (SeaTraderGraphics): large pictures, each linked to the
   Media Library item it comes from, with its history and the newer pictures waiting for that slot. */

/* ------------------------------------------------------------ language -- */
function languageSection() {
  const L = LANGS[lv.code];
  const part = lv.family ? "family" : "strings";
  const order = {};
  A.string_groups.forEach((g, i) => { order[g[0]] = i; });
  const keys = Object.keys(A.strings).sort((a, b) => order[a.split(".")[0]] - order[b.split(".")[0]]).filter(k => {
    if (lv.group && k.split(".")[0] !== lv.group) return false;
    if (lv.changed && !L[part][k]) return false;
    if (lv.family && lv.code === "en" && !lv.changed && !lv.q && !lv.group && A.family[k] == null && !L.family[k]) return false;
    if (lv.q) {
      const q = lv.q.toLowerCase();
      return k.includes(q) || A.strings[k].toLowerCase().includes(q) || (L[part][k] || "").toLowerCase().includes(q);
    }
    return true;
  });
  const rows = keys.map(k => {
    const base = lv.family ? (lv.code === "en" && A.family[k] != null ? A.family[k] : (L.strings[k] || A.strings[k])) : A.strings[k];
    return `<tr class="${L[part][k] ? "mod" : ""}"><td class="k mono">${esc(k)}</td><td class="d">${esc(base)}</td>
      <td><textarea rows="1" data-lang="${esc(k)}" placeholder="${esc(base)}">${esc(L[part][k] || "")}</textarea></td></tr>`;
  }).join("") || '<tr><td colspan="3" class="muted">Nothing matches.</td></tr>';
  const langOpts = sel => Object.keys(LANGS).map(c => `<option value="${c}" ${c === sel ? "selected" : ""}>${esc(LANGS[c].name)} (${c})</option>`).join("");
  return head("Language & Text", "Every line the game shows. Reword English to taste, or add a whole new language. " +
      "Leave a box empty to keep the wording shown beside it. The game runs in one language for everyone.") +
    `<section class="card"><h2>Languages</h2><div class="fields">
        <div class="f"><label><span>Language the game uses</span></label><select data-langactive="1">${langOpts(CFG.language.active)}</select></div>
        <div class="f"><label><span>Language you are editing</span></label><select data-langedit="1">${langOpts(lv.code)}</select></div>
        <div class="f"><label><span>Its name</span></label><input type="text" data-langname="1" value="${esc(L.name)}" maxlength="40"></div>
      </div>
      <div class="row"><input type="text" id="newlangcode" placeholder="code, e.g. es" maxlength="8" class="mono" style="flex-basis:8rem">
        <input type="text" id="newlangname" placeholder="name, e.g. Español" maxlength="40">
        <button type="button" data-langadd="1">Add language</button>
        ${lv.code !== "en" ? '<button type="button" class="danger confirm" data-langdel="1">Delete this language</button>' : ""}</div>
      <p class="help">Words in {braces} are filled in by the game; keep them as they are. These work in every line:
        <code>{lender}</code> <code>{pirate}</code> <code>{bank}</code> <code>{winner}</code> <code>{home}</code> <code>{title}</code> <code>{contraband}</code> <code>{Contraband}</code>.</p></section>
    <section class="card"><div class="row" style="margin:0 0 .7rem">
        <input type="search" data-langq="1" placeholder="Search wording or key…" value="${esc(lv.q)}" style="flex:1 1 16rem">
        <select data-langgroup="1"><option value="">All parts of the game</option>${A.string_groups.map(g => `<option value="${g[0]}" ${g[0] === lv.group ? "selected" : ""}>${esc(g[1])}</option>`).join("")}</select>
        <label><input type="checkbox" data-langchanged="1" ${lv.changed ? "checked" : ""}> only lines I changed</label>
        <label><input type="checkbox" data-langfamily="1" ${lv.family ? "checked" : ""}> family-friendly wording</label></div>
      ${lv.family ? '<p class="help">These lines replace the usual ones while the content rating is family-friendly (Ratings & Difficulty).</p>' : ""}
      <div class="scroll"><table class="lang"><thead><tr><th>Key</th><th>${lv.family ? "Wording used" : "English"}</th><th>Your wording${lv.code === "en" ? "" : " in " + esc(L.name)}</th></tr></thead>
      <tbody id="langrows">${rows}</tbody></table></div><p class="muted small">${keys.length} of ${Object.keys(A.strings).length} lines shown.</p></section>`;
}

/* -------------------------------------------------------------- backup -- */
function backupSection() {
  const list = (items, kind) => items.length ? "<table><tbody>" + items.map(p => `<tr><td><b>${esc(p.name)}</b></td><td class="muted">${when(p.time)}</td>
      <td class="n"><button type="button" data-load="${kind}" data-name="${esc(p.name)}">Load into editor</button>
      ${kind === "preset" ? `<button type="button" class="danger confirm" data-presetdel="${esc(p.name)}">Delete</button>` : ""}</td></tr>`).join("") + "</tbody></table>"
    : '<p class="muted">None yet.</p>';
  const host = A.join_url.replace(/^https?:\/\//, "");
  return head("Backup & Access", "Keep named sets of settings, undo a bad change, move settings between machines and control who can open this page.") +
    `<section class="card"><h2>Presets</h2><p class="help">A preset is a named copy of every setting (not languages or images). Loading one fills the editor; nothing changes until you save.</p>
      <div class="row"><input type="text" id="presetname" placeholder="Preset name, e.g. Family night" maxlength="40"><button type="button" data-presetsave="1">Save current settings as a preset</button></div>
      <div style="margin-top:.7rem">${list(A.presets, "preset")}</div></section>
    <section class="card"><h2>Automatic backups</h2><p class="help">Each save keeps the settings it replaced. The newest 30 are kept in config/backups.</p>${list(A.backups.slice(0, 12), "backup")}</section>
    <section class="card"><h2>Export, import and reset</h2>
      <div class="row"><a href="/api/admin/export" download="seatrader-settings.json"><button type="button">Download settings file</button></a>
        <label class="pick" style="border:1px solid var(--line);border-radius:6px;padding:.42rem .8rem;cursor:pointer;font-weight:600">Load a settings file<input type="file" accept=".json,application/json" data-import="1" hidden></label>
        <button type="button" class="danger confirm" data-resetall="1">Reset every setting to the defaults</button></div>
      <p class="help">To move the game to another computer, copy the whole game folder: settings are in <code>config</code>, images in <code>web/uploads</code>, games in <code>saves</code>.</p></section>
    <section class="card"><h2>Who can open this page</h2>
      <p>${A.local ? "You are on the computer running the game, which never needs a password." : "You are signed in from another device."}
        ${A.has_password ? '<b class="ok">A password is set</b>, so other devices can sign in at' : '<b class="warn">No password is set</b>, so other devices cannot open this page. Once set, they sign in at'}
        <code>http://${esc(host)}/admin</code>.</p>
      <div class="row">${A.local ? "" : '<input type="password" id="pwcur" placeholder="Current password" autocomplete="current-password">'}
        <input type="password" id="pwnew" placeholder="New password (blank removes it)" autocomplete="new-password">
        <button type="button" data-password="1">Set password</button></div></section>
    <section class="card"><h2>Server</h2><table><tbody>
      <tr><td class="muted">Game folder</td><td class="mono">${esc(A.server.folder)}</td></tr>
      <tr><td class="muted">Players join at</td><td class="mono">${esc(A.join_url)}</td></tr>
      <tr><td class="muted">Harbor board</td><td class="mono">${esc(A.join_url)}/board</td></tr>
      <tr><td class="muted">Running on</td><td>${esc(A.server.system)}, Python ${esc(A.server.python)}, since ${when(A.server.started)}</td></tr></tbody></table></section>`;
}

/* ---------------------------------------------------------------- live -- */
function liveSection() {
  if (!LIVE) return head("Live Game", "The game in progress, with nothing hidden.") + '<p class="muted">Loading…</p>';
  const L = LIVE, ports = CFG.ports, goods = CFG.goods;
  const pname = k => ports[k] ? ports[k].name : k;
  const gname = k => goods[k] ? goods[k].name : k;
  const phase = L.start_at ? "Opening in progress"
    : { lobby: "Lobby, waiting to start", port: "In progress", ended: "Finished" }[L.phase] || L.phase;
  const stats = [["Status", phase], ["Date", L.date], ["Months left", L.turns_left], ["Length", L.years + " years"],
                 ["Players", L.players.filter(p => p.present).length + " of " + L.players.length + " connected"]]
    .map(s => `<div class="stat"><span>${s[0]}</span><b>${esc(s[1])}</b></div>`).join("");
  const controls = `<section class="card"><h2>Controls</h2><div class="row" style="margin-top:0">
      ${L.phase === "lobby" && !L.start_at ? '<button type="button" class="primary" data-g="start">Cue opening</button>' : ""}
      ${L.phase === "port" ? '<button type="button" class="primary" data-g="force">End the turn now</button><button type="button" class="confirm" data-g="finish">Finish the game now</button>' : ""}
      <span class="unit"><input type="number" id="gyears" min="1" max="100" value="${L.years}" style="width:5rem"><i>years</i></span>
      <button type="button" data-g="years">Set length</button>
      <button type="button" class="danger confirm" data-g="new">Start a new game</button>
      <span class="muted small">Players join at <b>${esc(L.join_url)}</b></span></div>
      <div class="row"><input type="text" id="gnews" placeholder="Post a line of news to every screen…" maxlength="240" style="flex:1 1 20rem"><button type="button" data-g="news">Post news</button></div></section>`;
  const players = L.players.length ? L.players.map(p => {
    const cargo = Object.keys(p.cargo).map(g => p.cargo[g] + " " + gname(g)).join(", ") || "empty";
    const wh = Object.keys(p.wh).map(g => p.wh[g] + " " + gname(g)).join(", ");
    const ships = p.ships.map(s => `${esc(s.name)} (${esc((CFG.ships[s.type] || {}).name || s.type)}, hull ${s.hull}, ${s.guns} guns)`).join("<br>");
    const state = !p.present ? '<span class="err">away</span>' : p.ready ? `<span class="ok">orders: ${p.dest ? esc(pname(p.dest)) : "stay"}, ${p.orders}</span>` : '<span class="warn">in port</span>';
    return `<tr data-pid="${p.id}"><td><i class="chip" style="background:${CFG.theme.player_colors[p.color % 8]}"></i><b>${esc(p.firm)}</b><br><span class="muted">${esc(p.name)}</span><br>${Ranks.label(p)}<br>${state}</td>
      <td><select data-a="port">${Object.keys(ports).map(k => `<option value="${k}" ${k === p.port ? "selected" : ""}>${esc(ports[k].name)}</option>`).join("")}</select></td>
      <td><input type="number" data-a="cash" value="${p.cash}" min="0"></td><td><input type="number" data-a="bank" value="${p.bank}" min="0"></td>
      <td><input type="number" data-a="debt" value="${p.debt}" min="0"></td>
      <td><input type="number" data-a="protect" value="${p.protect}" min="0" style="width:4.5rem"></td>
      <td class="n"><b>${money(p.worth)}</b></td>
      <td class="small">${ships}<br><span class="muted">Hold ${p.used}/${p.hold}: ${esc(cargo)}${wh ? "<br>Warehouse: " + esc(wh) : ""}${p.wrecks ? "<br>Wrecks: " + p.wrecks : ""}</span></td>
      <td><button type="button" data-g="adjust">Apply</button> <button type="button" class="danger confirm" data-g="kick">Remove</button></td></tr>`;
  }).join("") : '<tr><td colspan="9" class="muted">Nobody has joined yet.</td></tr>';
  const shock = (port, g) => L.shocks.find(s => s.port === port && s.good === g);
  const prices = Object.keys(L.prices).map(port => `<tr><td><b>${esc(pname(port))}</b></td>` + goodsByPrice(Object.keys(L.prices[port])).map(g => {
    const s = shock(port, g);
    return `<td class="${s ? (s.mult > 1 ? "hi" : "lo") : ""}"><input type="number" min="0.01" step="any" value="${L.prices[port][g]}" data-price="${esc(port)}" data-good="${esc(g)}" ${s ? `title="${s.mult > 1 ? "Shortage" : "Glut"} x${s.mult}, ${s.turns} more months"` : ""}></td>`;
  }).join("") + `<td><input type="number" min="0" max="120" value="${L.crackdown[port] || 0}" data-ban="${esc(port)}" style="min-width:4rem;width:4rem"></td></tr>`).join("");
  const wxNames = [0, 1, 2, 3].map(i => (LANGS[CFG.language.active] && LANGS[CFG.language.active].strings["wx." + i]) || A.strings["wx." + i]);
  const weather = Object.keys(L.weather).map(r => `<div class="f"><label><span>${esc((CFG.regions[r] || {}).name || r)}</span></label>
      <select data-wx="${esc(r)}">${wxNames.map((n, i) => `<option value="${i}" ${i === L.weather[r] ? "selected" : ""}>${esc(n)}</option>`).join("")}</select></div>`).join("");
  const saves = L.saves.length ? "<table><tbody>" + L.saves.slice(0, 10).map(s => `<tr><td class="mono">${esc(s.name)}</td><td class="muted">${when(s.time)}</td>
      <td class="n"><button type="button" class="confirm" data-g="load_save" data-name="${esc(s.name)}">Restore this game</button></td></tr>`).join("") + "</tbody></table>"
    : '<p class="muted">No earlier games yet.</p>';
  return head("Live Game", "The game in progress, with nothing hidden. Changes here act on the game at once; they are not part of Save & apply.",
      '<span><a href="/" target="_blank">Player screen</a> · <a href="/board" target="_blank">Harbor board</a></span>') +
    `<div class="live"><div class="stats">${stats}</div>${controls}
    <section class="card"><h2>Trading houses</h2><div class="scroll"><table><thead><tr><th>House</th><th>Port</th><th>Silver</th><th>Bank</th><th>Debt</th><th>Protection (mo)</th><th class="n">Net worth</th><th>Fleet and cargo</th><th></th></tr></thead><tbody>${players}</tbody></table></div></section>
    <section class="card"><h2>Markets</h2><p class="help">Every price in every port. Type a new price and press Enter to set it. Green cells are in a glut, red in a shortage. The last column is months of contraband ban left (0 for none).</p>
      <div class="scroll"><table class="matrix"><thead><tr><th>Port</th>${goodsByPrice(Object.keys(goods)).map(g => `<th class="n">${esc(goods[g].name)}</th>`).join("")}<th>Ban</th></tr></thead><tbody>${prices}</tbody></table></div></section>
    <section class="card"><h2>Forecast for this month</h2><div class="fields c3">${weather}</div></section>
    <section class="card"><h2>News</h2><ul class="news">${L.news.map(n => "<li>" + esc(n) + "</li>").join("")}</ul></section>
    <section class="card"><h2>Earlier games</h2><p class="help">Restoring one sets the current game aside in the saves folder first.</p>${saves}</section></div>`;
}

async function pollLive() {
  const res = await api("state");
  if (res.ok) {
    LIVE = res;
    const on = res.players.filter(p => p.present).length;
    const phase = res.start_at ? "Opening"
      : { lobby: "Lobby", port: "In progress", ended: "Finished" }[res.phase] || res.phase;
    $("#status").dataset.phase = res.phase;
    $("#status").innerHTML = `<span class="st-phase">${esc(phase)}</span>` +
      (res.phase === "lobby" ? "" : `<span class="st-item"><b>${esc(res.date)}</b></span><span class="st-item"><b>${esc(res.turns_left)}</b> months left</span>`) +
      `<span class="st-item${on < res.players.length ? " warn" : ""}"><b>${on}</b>/${res.players.length} players connected</span>`;
    const typing = document.activeElement && main.contains(document.activeElement) && /INPUT|SELECT|TEXTAREA/.test(document.activeElement.tagName);
    if (section === "live" && Date.now() > liveHold && !typing && !$("[data-armed]", main)) main.innerHTML = liveSection();
  } else {
    $("#status").dataset.phase = "offline";
    $("#status").innerHTML = '<span class="st-phase">Server offline</span><span class="st-item">retrying…</span>';
  }
  setTimeout(pollLive, 2500);
}

async function game(op, extra) {
  const res = await api("game", Object.assign({ op }, extra || {}));
  toast(res.ok ? res.msg : res.error, !res.ok);
  liveHold = 0;
  if (document.activeElement) document.activeElement.blur();
  const st = await api("state");
  if (st.ok) { LIVE = st; if (section === "live") main.innerHTML = liveSection(); }
}

/* -------------------------------------------------------------- events -- */
function edited(e) {
  const el = e.target, d = el.dataset;
  if (section === "live") { liveHold = Date.now() + 20000; return; }
  if (section === "report") return;
  if (d.path) {
    const spec = FIELD[d.path];
    const v = readControl(el, spec, get(CFG, d.path));
    el.classList.toggle("bad", v === undefined);
    if (v === undefined) return;
    set(CFG, d.path, v);
    if (spec.type === "color") el.parentNode.querySelectorAll("input").forEach(o => { if (o !== el) o.value = v; });
    const box = el.closest(".f");
    if (box) box.classList.toggle("mod", !same(v, get(A.defaults, d.path)));
    if (d.path.startsWith("theme.")) previewTheme();
    if (d.path.startsWith("brand.title")) $("#gname").textContent = [CFG.brand.title_a, CFG.brand.title_b].filter(Boolean).join(" ");
  } else if (d.t) {
    const rows = get(CFG, d.t), row = rows[d.r];
    const v = readControl(el, COL[d.t][d.c], row[d.c]);
    el.classList.toggle("bad", v === undefined);
    if (v === undefined) return;
    row[d.c] = v;
  } else if (d.m) {
    const row = get(CFG, d.m)[d.r];
    row.mods = row.mods || {};
    const raw = el.value.trim(), n = Number(raw);
    const ok = raw === "" || (!isNaN(n) && n >= 0.05 && n <= 20);
    el.classList.toggle("bad", !ok);
    if (!ok) return;
    if (raw === "" || n === 1) delete row.mods[d.c]; else row.mods[d.c] = n;
    el.parentNode.className = raw === "" || n === 1 ? "" : n < 1 ? "lo" : "hi";
  } else if (d.lang) {
    const L = LANGS[lv.code], part = lv.family ? "family" : "strings";
    if (el.value.trim()) L[part][d.lang] = el.value; else delete L[part][d.lang];
    el.closest("tr").classList.toggle("mod", !!el.value.trim());
  } else if (d.langname) {
    LANGS[lv.code].name = el.value;
  } else if (d.langq) {
    lv.q = el.value;
    const pos = el.selectionStart;
    main.innerHTML = languageSection();
    const q = $("[data-langq]"); q.focus(); q.setSelectionRange(pos, pos);
    return;
  } else return;
  refreshDirty();
}
main.addEventListener("input", edited);

main.addEventListener("change", async e => {
  const el = e.target, d = el.dataset;
  if (d.langactive) { CFG.language.active = el.value; refreshDirty(); return; }
  if (d.langedit) { lv.code = el.value; return draw(); }
  if (d.langgroup) { lv.group = el.value; return draw(); }
  if (d.langchanged) { lv.changed = el.checked; return draw(); }
  if (d.langfamily) { lv.family = el.checked; return draw(); }
  if (d.up && el.files[0]) {
    const file = el.files[0];
    if (file.size > 8 * 1024 * 1024) return toast("That image is larger than 8 MB.", true);
    const res = await api("upload?name=" + encodeURIComponent(file.name), undefined, file);
    if (!res.ok) return toast(res.error, true);
    set(CFG, d.up, res.url);
    refreshDirty();
    return draw();
  }
  if (d.import && el.files[0]) {
    try {
      const data = JSON.parse(await el.files[0].text());
      if (!data || typeof data !== "object" || !data.rules) throw new Error();
      CFG = Object.assign(clone(A.defaults), data);
      toast("Settings file loaded into the editor. Save & apply to use it.");
      refreshDirty();
    } catch (err) { toast("That is not a SeaTrader settings file.", true); }
    return;
  }
  if (d.price) return game("price", { port: d.price, good: d.good, value: el.value });
  if (d.ban) return game("ban", { port: d.ban, turns: el.value });
  if (d.wx) return game("weather", { region: d.wx, level: el.value });
  if (el.tagName === "SELECT" || el.type === "checkbox" || el.type === "color") edited(e);
});

main.addEventListener("click", async e => {
  const el = e.target.closest("button, [data-clear]");
  if (!el || el.disabled) return;
  const d = el.dataset;
  if (el.classList.contains("confirm") && !d.armed) {
    d.armed = "1"; d.label = el.textContent; el.textContent = "Click again to confirm";
    setTimeout(() => { if (el.isConnected && d.armed) { delete d.armed; el.textContent = d.label; } }, 3500);
    return;
  }
  if (d.reset) {
    set(CFG, d.reset, clone(get(A.defaults, d.reset)));
    refreshDirty();
    return draw();
  }
  if (d.resetsec) {
    const sec = A.sections.find(s => s.id === d.resetsec);
    sectionPaths(sec).forEach(p => set(CFG, p, clone(get(A.defaults, p))));
    refreshDirty();
    return draw();
  }
  if (d.add) {
    const tb = A.sections.flatMap(s => s.tables || []).find(t => t.path === d.add);
    const rows = get(CFG, d.add);
    if (tb.kind === "dict") {
      const key = ($("#new_" + CSS.escape(d.add)).value || "").trim().toLowerCase();
      if (!/^[a-z][a-z0-9_]{0,23}$/.test(key)) return toast("Keys start with a letter and use only a-z, 0-9 and _.", true);
      if (rows[key]) return toast("That key is already used.", true);
      rows[key] = blankRow(tb);
      rows[key].name = key.charAt(0).toUpperCase() + key.slice(1);
    } else rows.push(blankRow(tb));
    refreshDirty();
    return draw();
  }
  if (d.del) {
    const rows = get(CFG, d.del);
    if (Array.isArray(rows)) rows.splice(+d.r, 1); else delete rows[d.r];
    if (["goods", "ports", "ships"].includes(d.del)) delete CFG.graphics[d.del][d.r];
    if (d.del === "goods") Object.values(CFG.ports).forEach(p => { if (p.mods) delete p.mods[d.r]; });
    refreshDirty();
    return draw();
  }
  if (d.clear) { set(CFG, d.clear, ""); if (d.clear.split(".").length === 3) delete get(CFG, d.clear.split(".").slice(0, 2).join("."))[d.clear.split(".")[2]]; refreshDirty(); return draw(); }
  if (d.langadd) {
    const code = $("#newlangcode").value.trim().toLowerCase(), name = $("#newlangname").value.trim();
    if (!/^[a-z]{2,3}(-[a-z0-9]{2,8})?$/.test(code)) return toast("Use a short code such as es, de or pt-br.", true);
    if (LANGS[code]) return toast("That language already exists.", true);
    LANGS[code] = { name: name || code, strings: {}, family: {} };
    lv.code = code;
    refreshDirty();
    return draw();
  }
  if (d.langdel) {
    const code = lv.code;
    if (A.lang[code]) { const res = await api("lang_delete", { code }); if (!res.ok) return toast(res.error, true); delete A.lang[code]; }
    delete LANGS[code];
    const saved = JSON.parse(LANGS_SAVED); delete saved[code]; LANGS_SAVED = JSON.stringify(saved);
    if (CFG.language.active === code) CFG.language.active = "en";
    lv.code = "en";
    refreshDirty();
    return draw();
  }
  if (d.presetsave) {
    const res = await api("preset", { op: "save", name: $("#presetname").value, config: CFG });
    toast(res.ok ? res.msg : (res.errors || [res.error])[0], !res.ok);
    if (res.ok) { A.presets = res.presets; draw(); }
    return;
  }
  if (d.presetdel) {
    const res = await api("preset", { op: "delete", name: d.presetdel });
    if (res.ok) { A.presets = res.presets; draw(); }
    return toast(res.ok ? res.msg : res.error, !res.ok);
  }
  if (d.load) {
    const res = d.load === "preset" ? await api("preset", { op: "load", name: d.name }) : await api("backup", { name: d.name });
    if (!res.ok) return toast(res.error, true);
    CFG = res.config;
    refreshDirty();
    return toast("Loaded into the editor. Look it over, then Save & apply.");
  }
  if (d.resetall) { CFG = clone(A.defaults); refreshDirty(); return toast("Everything is back to the defaults in the editor. Save & apply to use them."); }
  if (d.password) {
    const res = await api("password", { password: $("#pwnew").value, current: ($("#pwcur") || {}).value });
    toast(res.ok ? res.msg : res.error, !res.ok);
    if (res.ok) { A.has_password = !!$("#pwnew").value; draw(); }
    return;
  }
  if (d.g) {
    const row = el.closest("[data-pid]");
    const extra = {};
    if (row) {
      extra.pid = row.dataset.pid;
      if (d.g === "adjust") row.querySelectorAll("[data-a]").forEach(i => { extra[i.dataset.a] = i.value; });
    }
    if (d.g === "years") extra.years = $("#gyears").value;
    if (d.g === "news") extra.text = $("#gnews").value;
    if (d.name) extra.name = d.name;
    return game(d.g, extra);
  }
});

main.addEventListener("keydown", e => {
  if (e.key !== "Enter") return;
  if (e.target.id === "gnews") game("news", { text: e.target.value });
  else if (e.target.dataset.price || e.target.dataset.ban) e.target.blur();
});

$("#save").addEventListener("click", async () => {
  if ($(".bad", main)) return toast("Fix the fields outlined in red first.", true);
  const langs = {}, was = JSON.parse(LANGS_SAVED);
  Object.keys(LANGS).forEach(c => { if (!same(LANGS[c], was[c])) langs[c] = LANGS[c]; });
  $("#save").disabled = true;
  const res = await api("save", { config: CFG, langs });
  if (!res.ok) {
    errors = res.errors || [res.error];
    toast(res.error, true);
    refreshDirty();
    draw();
    return window.scrollTo(0, 0);
  }
  errors = [];
  toast(res.msg);
  const keep = section;
  await boot();
  section = keep;
  if (section === "graphics") SeaTraderGraphics.enter();
});

$("#discard").addEventListener("click", () => {
  CFG = JSON.parse(SAVED);
  LANGS = JSON.parse(LANGS_SAVED);
  if (!LANGS[lv.code]) lv.code = "en";
  errors = [];
  refreshDirty();
  draw();
  toast("Changes discarded.");
});

boot();
