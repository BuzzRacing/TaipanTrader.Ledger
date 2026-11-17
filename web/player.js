/* SeaTrader player screen. The server owns the game; this file only draws the
   latest state and sends the player's choices back. All wording comes from
   the server through t("key"), so the Admin page can change any of it. */
"use strict";

let D = null;            // reference data (goods, ports, ships, brand, wording)
let S = null;            // latest game state from the server
let token = store("seatrader_token");
let stream = null;
let online = true;
let reloading = false;
const ui = { tab: "market", vals: {}, dest: null, orders: null, seenTurn: null, busy: false, confirmNew: false,
             spokenTurn: null, newsSeen: null, feed: "log", paneTab: null, menu: false,
             tgt: {}, dragging: false };
let VS = {};             // voice settings: who is in the cast, what this screen reads aloud
const app = document.getElementById("app");

/* ---------------------------------------------------------------- net -- */
async function post(path, body) {
  try {
    const r = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" },
                                  body: JSON.stringify(body) });
    return await r.json();
  } catch (e) {
    return { ok: false, error: t("ui.no_server") };
  }
}

async function act(type, extra) {
  if (ui.busy) return;
  ui.busy = true;
  const res = await post("/api/act", Object.assign({ token, type }, extra || {}));
  ui.busy = false;
  toast(res.ok ? res.msg : res.error, !res.ok);
  if (res.voice) Voice.say([Object.assign({ text: res.ok ? res.msg : res.error }, res.voice)], { group: "msg", replace: "msg" });
  return res.ok;
}

/* Settings were changed in the Admin page: fetch them again, then redraw. */
async function refreshInfo() {
  if (reloading) return;
  reloading = true;
  try { const info = await loadInfo(); D = info.data; VS = Voice.setup(info.voice); Stage.setCast(VS.cast); } catch (e) { /* try again on the next state */ }
  reloading = false;
  if (ui.dest && !D.ports[ui.dest]) ui.dest = null;
  render();
  speak();
}

function connect() {
  if (stream) stream.close();
  stream = listen(token, state => {
    S = state;
    if (state.unknown_token) { token = null; store("seatrader_token", null); connect(); return; }
    if (state.cfg !== cfgSeen) return refreshInfo();
    render();
    speak();
  }, ok => { if (ok !== online) { online = ok; render(); } });
}

/* Reads the month's log aloud while it is on screen, and any fresh news if this screen reads news. */
function speak() {
  if (!S || !S.voice) return;
  if (S.voice.log && document.querySelector(".modal .log") && ui.spokenTurn !== S.turn) {
    ui.spokenTurn = S.turn;
    Voice.say(S.voice.log.map((x, i) => x && Object.assign({ tag: "log:" + i, text: S.me.log[i] }, x)), { group: "log", replace: "log" });
  }
  const news = S.news || [], plans = S.voice.news || [];
  if (ui.newsSeen === null) { ui.newsSeen = new Set(news); return; }
  const fresh = [];
  news.forEach((n, i) => { if (!ui.newsSeen.has(n)) { ui.newsSeen.add(n); if (plans[i]) fresh.unshift(Object.assign({ text: n }, plans[i])); } });
  if (fresh.length && VS.news_players) Voice.say(fresh, { group: "news" });
}

/* Underlines the log line being read. */
function markSpeaking() {
  const item = Voice.current();
  document.querySelectorAll(".modal .log li").forEach((li, i) =>
    li.classList.toggle("speaking", !!item && item.tag === "log:" + i));
}
Voice.onChange(item => { markSpeaking(); Stage.talk(item); });

let toastTimer = null;
function toast(msg, bad) {
  const el = document.getElementById("toast");
  el.textContent = msg || "";
  el.className = "show" + (bad ? " bad" : "");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.className = ""; }, bad ? 4200 : 2600);
}

/* ------------------------------------------------------------- helpers -- */
const val = k => ui.vals[k] == null ? "" : ui.vals[k];
const num = k => { const n = parseInt(val(k), 10); return n > 0 ? n : 0; };
const input = (k, ph, extra) =>
  `<input id="in_${k}" data-k="${k}" type="text" autocomplete="off" ` +
  `placeholder="${esc(ph || "0")}" value="${esc(val(k))}" ${extra || 'inputmode="numeric"'}>`;
const btn = (label, action, data, cls, disabled) =>
  `<button type="button" class="${cls || ""}" data-act="${action}" ${data || ""} ${disabled ? "disabled" : ""}>${label}</button>`;

function quote(good, qty, side) {
  const mid = S.me.prices[good], k = D.impact * qty / D.goods[good].depth;
  if (side === "buy") return Math.ceil(qty * (mid + mid * (1 + k)) / 2 * (1 + S.me.spread));
  return Math.floor(qty * (mid + mid / (1 + k)) / 2 * (1 - S.me.spread));
}

function maxBuy(good) {
  let lo = 0, hi = S.me.capacity - S.me.used;
  while (lo < hi) {
    const mid = Math.ceil((lo + hi) / 2);
    if (quote(good, mid, "buy") <= S.me.cash) lo = mid; else hi = mid - 1;
  }
  return lo;
}

const portName = k => D.ports[k] ? D.ports[k].name : k;
const guns = () => S.me.ships.reduce((n, s) => n + s.guns, 0);
const pct = (x, digits) => (x * 100).toFixed(digits == null ? 1 : digits).replace(/\.0+$/, "");

function riskLabel(a, b) {
  const d = Chart.distance(D, a, b);
  return t(d < 260 ? "chart.short" : d < 480 ? "chart.long" : "chart.far");
}

function newGameControl() {
  if (!S.me.host) return "";
  return ui.confirmNew
    ? `<div class="row"><b>${te("host.new_confirm")}</b>${btn(te("host.new_yes"), "newgame", "", "primary")}${btn(te("host.new_no"), "newgame_no")}</div>`
    : `<div class="row">${btn(te("host.new_ask"), "newgame_ask", "", "ghost")}</div>`;
}

/* -------------------------------------------------------------- screens -- */
/* The game screen ("the deck") is a fixed frame that never scrolls: top bar, tab rail, the working
   pane, and the side column with the speaker stage, log and helm. Each region is only rewritten
   when its content changed, so scroll positions, focus and playing clips survive every update. */
const drawn = {};
function region(name, html) {
  const el = app.querySelector('[data-r="' + name + '"]');
  if (el && drawn[name] !== html) { el.innerHTML = html; drawn[name] = html; }
}
function forget() { Object.keys(drawn).forEach(k => delete drawn[k]); }

function deckFrame() {
  let deck = document.getElementById("deck");
  if (!deck) {
    forget();
    app.innerHTML = `<div class="deck" id="deck">
      <header class="dk-top" data-r="top"></header>
      <nav class="dk-nav" data-r="nav"></nav>
      <main class="dk-main"><div class="dk-pane" data-r="pane"></div></main>
      <aside class="dk-side"><div class="dk-stage" id="stageSlot"></div><div class="dk-dyn" data-r="side"></div></aside>
      <div class="dk-over" data-r="over"></div></div>`;
    deck = document.getElementById("deck");
  }
  return deck;
}

function render() {
  if (!D || !S) return;
  const active = document.activeElement;
  const focusId = active && active.id && active.id.startsWith("in_") ? active.id : null;
  const caret = focusId ? active.selectionStart : null;

  let off = document.getElementById("offline");
  if (!off) { off = document.createElement("div"); off.id = "offline"; off.className = "offline"; document.body.appendChild(off); }
  off.textContent = t("ui.offline");
  off.hidden = online;

  const inGame = S.me && S.phase !== "lobby" && S.phase !== "ended";
  document.body.classList.toggle("ingame", !!inGame);
  if (inGame) {
    const deck = deckFrame(), parts = gameScreen();
    deck.classList.toggle("locked", !!S.me.ready);
    deck.dataset.tab = ui.tab;
    ["top", "nav", "pane", "side", "over"].forEach(k => { if (!(k === "pane" && ui.dragging)) region(k, parts[k]); });
    if (ui.paneTab !== ui.tab) { ui.paneTab = ui.tab; app.querySelector(".dk-pane").scrollTop = 0; }
  } else {
    const html = !S.me ? joinScreen() : S.phase === "lobby" ? lobbyScreen() : endScreen();
    if (!app.querySelector(".solo")) { forget(); app.innerHTML = '<div class="solo" data-r="solo"></div>'; }
    region("solo", html);
  }

  if (focusId) {
    const el = document.getElementById(focusId);
    if (el && el !== document.activeElement) { el.focus(); try { el.setSelectionRange(caret, caret); } catch (e) { /* ignore */ } }
  }
  deckArt(inGame);
  markSpeaking();
}

/* The living background and the stage's picture between lines. */
function deckArt(inGame) {
  const g = D.graphics || {}, me = S.me;
  let list = inGame
    ? Media.items("scene", ["market", "voyage"], "background", true).concat(Media.items("port", me.port, "night", true))
    : Media.items("scene", ["title", "loading"], "background", true);
  if (!list.length) {
    list = [g.page_bg, g.masthead_bg].concat(inGame && g.ports ? [g.ports[me.port]] : []).filter(Boolean)
      .map(u => ({ id: u, u, t: "image", w: 1 }));
  }
  Ambient.set(list);
  if (!inGame) return;
  Stage.mount(document.getElementById("stageSlot"));
  const woman = stageWomanHtml(ui.tab);
  document.getElementById("deck").classList.toggle("woman", !!woman);
  if (woman) return Stage.idle(me.port + ":" + ui.tab, woman.html, woman.name, woman.note);
  Stage.idle(me.port, Media.html("port", me.port, "banner", "stg-img", (g.ports || {})[me.port],
                                 { video: true, slot: "stage", mode: "shuffle" }),
             portName(me.port), S.date);
}

/* The women who keep the stage while a tab is open: the market keeper on the Market tab and the
   ship master on the Fleet tab. Pictures come from Media Library > Ports > (port) in that role. A
   port without one borrows one from another port; with none anywhere the port picture shows. */
const STAGE_WOMEN = { market: { role: "keeper", key: "market.keeper" }, fleet: { role: "shipmaster", key: "fleet.master" } };
function stageWomanHtml(tab) {
  const w = STAGE_WOMEN[tab];
  if (!w) return null;
  const own = p => Media.items("port", p, w.role, true).some(i => i.r.includes(w.role));
  const here = S.me.port;
  const from = own(here) ? here : Object.keys(D.ports).find(own);
  if (!from) return null;
  const html = Media.html("port", from, w.role, "stg-img", "", { video: true, strict: true, slot: "stage-" + w.role, mode: "shuffle" });
  return html ? { html, name: t(w.key, { port: portName(here) }), note: S.date } : null;
}

function masthead(sub) {
  return `<header class="masthead"><h1>${brandHtml(D)}</h1><p>${sub}</p></header>`;
}

function roster() {
  if (!S.players.length) return `<p class="muted">${te("join.none")}</p>`;
  return '<ul class="roster">' + S.players.map(p =>
    `<li><i class="chip" style="background:${COLORS[p.color % 8]}"></i><b>${esc(p.firm)}</b> ` +
    `<span class="muted">${esc(p.name)}${p.host ? " · " + te("w.host") : ""}${p.present ? "" : " · " + te("w.away")}</span></li>`).join("") + "</ul>";
}

const joinUrl = () => `<p class="muted center">${th("join.url", { url: "<b>" + esc(S.join_url) + "</b>" })}</p>`;

function joinScreen() {
  const late = S.phase === "port" ? `<p class="note">${te("join.late")}</p>` : "";
  const over = S.phase === "ended" ? `<p class="note">${te("join.over")}</p>` : "";
  return masthead(esc(D.brand.tagline)) + `<main class="narrow">
    <section class="card"><h2>${te("join.title")}</h2>${late}${over}
      <label>${te("join.name")} ${input("name", t("join.name_ph"), 'inputmode="text" maxlength="20"')}</label>
      <label>${te("join.firm")} ${input("firm", t("join.firm_ph"), 'inputmode="text" maxlength="28"')}</label>
      ${btn(te("join.button"), "join", "", "primary wide")}
    </section>
    <section class="card"><h2>${te("join.houses")}</h2>${roster()}</section>
    ${joinUrl()}</main>`;
}

function lobbyScreen() {
  const me = S.me;
  const years = D.lengths.map(y =>
    btn(te(y === 1 ? "lobby.year" : "lobby.years", { n: y }), "years", `data-y="${y}"`, S.years === y ? "on" : "")).join("");
  const level = D.difficulty ? `<p class="muted">${te("lobby.difficulty", { name: D.difficulty })}</p>` : "";
  const host = me.host
    ? `<h2>${te("lobby.host_title")}</h2><p>${te("lobby.length")}</p><div class="seg">${years}</div>
       <p class="muted">${te("lobby.turns", { years: S.years, turns: S.years * 12 })}</p>${level}
       ${btn(te("lobby.start"), "start", "", "primary wide")}`
    : `<h2>${te("lobby.wait_title")}</h2><p class="muted">${te("lobby.wait", { years: S.years })}</p>${level}`;
  return masthead(esc(D.brand.tagline)) + `<main class="narrow">
    <section class="card">${host}</section>
    <section class="card"><h2>${te("join.houses")}</h2>${roster()}${btn(te("st.open_hint"), "tally", "", "ghost wide")}</section>
    <p class="muted center">${th("join.url", { url: "<b>" + esc(S.join_url) + "</b>" })}<br>
    ${th("join.board_url", { url: "<b>" + esc(S.join_url) + "/board</b>" })}</p></main>`;
}

function standings() {
  const rows = S.players.slice().sort((a, b) => b.worth - a.worth).map((p, i) =>
    `<tr class="${p.id === S.me.id ? "me" : ""}"><td>${i + 1}</td>` +
    `<td><i class="chip" style="background:${COLORS[p.color % 8]}"></i>${esc(p.firm)}<br><span class="muted">${esc(p.name)}</span> <span class="rankname">${esc(p.rank)}</span></td>` +
    `<td>${esc(portName(p.port))}</td><td class="n">${p.ships}</td><td class="n">${money(p.worth)}</td></tr>`).join("");
  return `<table class="grid"><thead><tr><th></th><th>${te("col.house")}</th><th>${te("col.port")}</th><th class="n">${te("col.ships")}</th><th class="n">${te("col.worth")}</th></tr></thead><tbody>${rows}</tbody></table>`;
}

function endScreen() {
  const top = S.players.slice().sort((a, b) => b.worth - a.worth)[0];
  return masthead(te("end.sub", { date: S.date })) + `<main class="narrow">
    <section class="card"><h2>${te("end.title", { name: top.name, firm: top.firm })}</h2>${standings()}</section>
    <section class="card">${btn(te("st.open_end"), "tally", "", "primary wide")}</section>
    <section class="card">${newGameControl() || `<p class="muted">${te("end.host_can")}</p>`}
      <p class="muted">${te("end.kept")}</p></section></main>`;
}

function gameScreen() {
  const me = S.me;
  if (ui.seenTurn === null) ui.seenTurn = me.log.length && S.turn > 0 ? -1 : S.turn;
  const report = ui.seenTurn !== S.turn && me.log.length ? logModal() : "";
  if (ui.seenTurn !== S.turn && !me.log.length) ui.seenTurn = S.turn;

  const stats = [["stat.silver", money(me.cash), "silver"], ["stat.bank", money(me.bank)], ["stat.debt", money(me.debt), me.debt > 0 ? "bad" : ""],
                 ["stat.worth", money(me.worth), "worth"], ["stat.hold", me.used + " / " + me.capacity], ["stat.guns", guns()]]
    .map(s => `<div class="plq ${s[2] || ""}"><span>${te(s[0])}</span><b>${s[1]}</b></div>`).join("");
  const top = `<div class="dk-house"><i class="chip" style="background:${COLORS[me.color % 8]}"></i>
      <div><b>${esc(me.firm)}</b><span class="rankname">${esc(me.rank)}</span>
      <small>${te("bar.where", { port: esc(portName(me.port)), date: esc(S.date), months: S.turns_left })}</small></div></div>
    <div class="dk-stats">${stats}</div>`;
  const tabBtn = k =>
    `<button type="button" class="${ui.tab === k ? "on" : ""}" data-act="tab" data-tab="${k}" aria-label="${te("tab." + k)}">` +
    `${DECK_ICONS[k] || ""}<span>${te("tab." + k)}</span></button>`;
  // tabs, the Tally Book, a gap, then Advice and the captain at the foot
  const nav = ["market", "port", "fleet", "chart", "ledger"].map(tabBtn).join("") +
    `<button type="button" class="dk-tally" data-act="tally" aria-label="${te("st.open_hint")}" title="${te("st.open_hint")}">` +
    `${DECK_ICONS.tally || ""}<span>${te("st.open")}</span></button>` +
    `<i class="dk-gap"></i>${tabBtn("advice")}${captainButton()}`;
  const pane = { market: marketTab, port: portTab, fleet: fleetTab, chart: chartTab, ledger: ledgerTab, advice: adviceTab }[ui.tab]();
  return { top, nav, pane, side: feed() + helm(), over: report };
}

/* The bottom of the rail: the player's own picture (or their initials in the house colour).
   It opens a small menu of the player's own things: voices on or off, options, and more later. */
function captainButton() {
  const me = S.me;
  const face = me.portrait
    ? `<img src="${esc(me.portrait)}" alt="">`
    : `<em>${esc(String(me.name || "?").split(/\s+/).filter(Boolean).slice(0, 2).map(w => w[0]).join("").toUpperCase())}</em>`;
  const voices = Voice.enabled();
  const muted = Voice.muted();
  const fly = !ui.menu ? "" : `<div class="dk-fly" role="menu">
      <button type="button" role="menuitem" data-act="speech" class="${voices && !muted ? "on" : ""}" ${voices ? "" : "disabled"}
        aria-label="${te(!voices ? "deck.speech_none" : muted ? "deck.speech_off" : "deck.speech_on")}" title="${te(!voices ? "deck.speech_none" : muted ? "deck.speech_off" : "deck.speech_on")}">
        ${DECK_ICONS[voices && !muted ? "speech_on" : "speech_off"]}<span>${te("deck.speech")}</span></button>
      <button type="button" role="menuitem" data-act="options" aria-label="${te("deck.options")}">${DECK_ICONS.options}<span>${te("deck.options")}</span></button>
    </div>`;
  return `<div class="dk-me${ui.menu ? " open" : ""}">${fly}
    <button type="button" class="dk-face" data-act="menu" aria-haspopup="menu" aria-expanded="${ui.menu}" aria-label="${te("deck.me", { name: me.name })}"
      style="--house:${COLORS[me.color % 8]}">${face}<span>${esc(me.name)}</span></button></div>`;
}

/* Advice from one of the cast, based on the player's numbers. Planned, not built yet. */
function adviceTab() {
  return `<section class="card"><p class="eyebrow">${te("advice.eyebrow")}</p><h2>${te("advice.title")}</h2>
    <p class="muted">${te("advice.soon")}</p></section>`;
}

/* The side column under the stage: this month's log or the port news, scrolling inside itself. */
function feed() {
  const f = ui.feed === "news" ? "news" : "log";
  const items = f === "log" ? S.me.log : S.news;
  const list = items.length ? items.map(n => "<li>" + esc(n) + "</li>").join("")
    : `<li class="muted">${te(f === "log" ? "ledger.no_log" : "ledger.no_news")}</li>`;
  return `<section class="dk-feed"><div class="dk-feedtabs">
      ${btn(te("deck.log"), "feed", 'data-f="log"', f === "log" ? "on" : "")}${btn(te("deck.news"), "feed", 'data-f="news"', f === "news" ? "on" : "")}</div>
    <ul class="dk-list">${list}</ul></section>`;
}

/* Sailing orders, always in reach. */
function helm() {
  const me = S.me;
  if (me.ready) {
    return `<section class="dk-helm ready"><p class="eyebrow">${te("deck.helm")}</p>
      <b>${me.dest ? te("sail.orders_to", { port: portName(me.dest) }) : te("sail.orders_stay")}</b>
      <span class="muted">${S.waiting.length ? te("sail.waiting", { names: S.waiting.join(", ") }) : te("sail.weighing")}</span>
      ${btn(te("sail.cancel"), "unsail", "", "ghost wide")}</section>`;
  }
  const dest = ui.dest && D.ports[ui.dest] ? ui.dest : null;
  return `<section class="dk-helm"><p class="eyebrow">${te("deck.helm")}</p>
      <b>${dest ? te("deck.course", { port: portName(dest) }) : te("deck.no_course")}</b>
      ${dest ? btn(te("sail.go", { port: portName(dest) }), "sail", "", "primary wide")
             : btn(te("deck.plot"), "tab", 'data-tab="chart"', "primary wide")}</section>`;
}

function logModal() {
  return `<div class="veil"><div class="modal">${Media.html("port", S.me.port, "arrival", "portart logart", "", { strict: true, video: true })}<p class="eyebrow">${te("log.eyebrow")}</p><h2>${esc(S.date)}</h2>
    <ul class="log">${S.me.log.map((l, i) => {
      // Name the reader at the start of each run of lines they read.
      const plan = S.voice && S.voice.log, v = plan && plan[i], who = v && VS.cast && VS.cast[v.c];
      const same = i > 0 && plan && plan[i - 1] && v && plan[i - 1].c === v.c;
      const face = who && !same ? (Media.html("persona", v.c, "portrait", "whoface", who.portrait, { slot: "log" + i }) ) : "";
      return "<li>" + (who && !same ? `<span class="who" style="color:${esc(who.color)}">${face}${esc(who.name)}</span>` : "") + esc(l) + "</li>";
    }).join("")}</ul>
    ${btn(te("log.ashore"), "seen", "", "primary wide")}</div></div>`;
}

/* --------------------------------------------------------------- market -- */
/* One drag bar per cargo sets how much will be aboard. It starts at what is aboard now (the brass
   tick); drag right to buy (jade), left to sell (oxblood). The row's one button does the trade. */
function tradeOf(g) {
  const me = S.me, have = me.cargo[g] || 0, max = have + maxBuy(g);
  const tgt = Math.max(0, Math.min(max, ui.tgt[g] == null ? have : ui.tgt[g]));
  const n = tgt - have;
  const side = n > 0 ? "buy" : n < 0 ? "sell" : "";
  return { have, max, tgt, n: Math.abs(n), side, cost: side ? quote(g, Math.abs(n), side) : 0 };
}

function barStyle(tr) {
  const f = v => (tr.max ? v / tr.max : 0).toFixed(4);
  return `--h:${f(tr.have)};--a:${f(Math.min(tr.have, tr.tgt))};--b:${f(Math.max(tr.have, tr.tgt))}`;
}

function tradeLabel(tr) {
  if (!tr.max) return te("market.no_room");
  if (!tr.side) return te("market.drag");
  return te(tr.side === "buy" ? "market.buy_n" : "market.sell_n", { n: tr.n.toLocaleString(), cost: money(tr.cost) });
}

function marketTab() {
  const me = S.me;
  const banned = S.crackdown.includes(me.port);
  const rows = Object.keys(D.goods).map(g => {
    const tr = tradeOf(g), good = D.goods[g];
    return `<div class="mk-row ${tr.side}" data-good="${g}">
      <div class="mk-pic">${Media.html("cargo", g, "icon", "mk-img", D.graphics.goods[g])}</div>
      <div class="mk-name"><b>${esc(good.name)}</b>${good.contraband ? `<span class="tag">${te("tag.contraband")}</span>` : ""}</div>
      <div class="mk-price"><b>${money(me.prices[g])}</b><small>${te("market.aboard", { n: tr.have.toLocaleString() })}</small></div>
      <div class="mk-bar"><input type="range" class="mk-range" data-good="${g}" min="0" max="${tr.max}" step="1" value="${tr.tgt}"
        style="${barStyle(tr)}" aria-label="${te("market.bar", { good: good.name })}" ${tr.max ? "" : "disabled"}></div>
      <button type="button" class="mk-do ${tr.side}" data-act="trade" data-good="${g}" ${tr.side ? "" : "disabled"}>${tradeLabel(tr)}</button></div>`;
  }).join("");
  return `<section class="card mk">
    <div class="mk-head"><h2>${te("market.title", { port: portName(me.port) })}</h2>
      <span class="muted" title="${te("market.standing", { rep: me.rep[me.port], margin: pct(me.spread) })}">${te("market.standing_short", { rep: me.rep[me.port], margin: pct(me.spread) })}</span>
      <span class="mk-hold">${te("market.hold_short", { used: me.used, cap: me.capacity })}</span></div>
    ${banned ? `<p class="note bad">${te("market.banned")}</p>` : ""}
    <div class="mk-list">${rows}</div></section>`;
}

/* While a bar is dragged only its own row changes; the pane redraws when the finger lifts. */
function dragRow(input) {
  const g = input.dataset.good;
  ui.tgt[g] = parseInt(input.value, 10) || 0;
  const tr = tradeOf(g), row = input.closest(".mk-row"), b = row && row.querySelector(".mk-do");
  input.setAttribute("style", barStyle(tr));
  if (row) row.className = "mk-row " + tr.side;
  if (b) { b.className = "mk-do " + tr.side; b.disabled = !tr.side; b.innerHTML = tradeLabel(tr); }
}
function dragEnd() {
  if (!ui.dragging) return;
  ui.dragging = false;
  render();
}

/* ----------------------------------------------------------------- port -- */
function portTab() {
  const me = S.me;
  if (me.port !== D.home) {
    return `<section class="card">${Media.html("port", me.port, "banner", "portart", D.graphics.ports[me.port])}<h2>${esc(portName(me.port))}</h2>
      <p>${te("port.away")}</p>
      <p class="muted">${te(D.ports[me.port].shipyard ? "port.away_here_yard" : "port.away_here")}</p></section>`;
  }
  const goods = Object.keys(D.goods).filter(g => (me.cargo[g] || 0) + (me.wh[g] || 0) > 0);
  const whUsed = Object.values(me.wh).reduce((a, b) => a + b, 0);
  const whRows = goods.length ? goods.map(g => `<tr><td><b>${esc(D.goods[g].name)}</b></td>
      <td class="n">${me.cargo[g] || "–"}</td><td class="n">${me.wh[g] || "–"}</td>
      <td class="qty">${input("w_" + g, t("ph.qty"))}</td>
      <td class="do">${btn(te("btn.store"), "wh", `data-op="store" data-good="${g}"`, "", !me.cargo[g])}${btn(te("btn.load"), "wh", `data-op="take" data-good="${g}"`, "", !me.wh[g])}</td></tr>`).join("")
    : `<tr><td colspan="5" class="muted">${te("wh.empty")}</td></tr>`;
  const agent = me.protect > D.renew_at
    ? `<p>${te("agent.content", { months: me.protect })}</p>`
    : `<p>${me.protect > 0 ? te("agent.running_out", { months: me.protect }) : te("agent.none")}</p>
       ${btn(te("agent.pay", { cost: money(me.protect_cost) }), "protection", "", "primary")}`;
  return `<section class="card"><h2>${te("bank.title")}</h2>
      <p class="muted">${te("bank.info", { balance: money(me.bank), rate: pct(D.bank_rate, 2) })}</p>
      <div class="row">${input("bank", t("ph.amount"))}${btn(te("btn.deposit"), "bank", 'data-op="deposit"', "primary")}${btn(te("btn.withdraw"), "bank", 'data-op="withdraw"')}
        ${btn(te("btn.all_silver"), "fill", `data-k="bank" data-v="${me.cash}"`, "link")}</div></section>
    <section class="card"><h2>${te("loan.title")}</h2>
      <p class="muted">${te("loan.info", { debt: money(me.debt), rate: pct(D.loan_rate, 2), room: money(me.loan_room) })}</p>
      <div class="row">${input("loan", t("ph.amount"))}${btn(te("btn.repay"), "loan", 'data-op="repay"', "primary")}${btn(te("btn.borrow"), "loan", 'data-op="borrow"')}
        ${btn(te("btn.whole_debt"), "fill", `data-k="loan" data-v="${Math.min(me.debt, me.cash)}"`, "link")}</div></section>
    <section class="card"><h2>${te("wh.title")}</h2>
      <p class="muted">${te("wh.info", { used: whUsed.toLocaleString(), cap: me.wh_cap.toLocaleString(), hold_used: me.used, hold: me.capacity })}</p>
      <table class="grid"><thead><tr><th>${te("col.cargo")}</th><th class="n">${te("col.aboard")}</th><th class="n">${te("col.in_store")}</th><th>${te("col.quantity")}</th><th></th></tr></thead><tbody>${whRows}</tbody></table></section>
    <section class="card"><h2>${te("agent.title")}</h2>${agent}</section>`;
}

/* ---------------------------------------------------------------- fleet -- */
function shipCard(s, i, yard) {
  const me = S.me, spec = D.ships[s.type], p = Math.round(100 * s.hull / spec.hull);
  const pips = Array.from({ length: spec.slots }, (_, k) => `<i class="${k < s.guns ? "on" : ""}"></i>`).join("");
  const repair = s.repair
    ? btn(te("fleet.repair", { cost: money(s.repair) }), "repair", `data-i="${i}"`, "slim")
    : `<span class="fl-ok">${te("fleet.seaworthy")}</span>`;
  return `<div class="fl-row">
    <div class="fl-pic">${Media.html("ship", s.type, "card", "fl-img", D.graphics.ships[s.type], { slot: "fleet:" + s.name })}</div>
    <div class="fl-name"><b>${esc(s.name)}</b><span class="muted">${te("fleet.ship_line", { type: spec.name, hold: spec.hold })}</span></div>
    <div class="fl-stats">
      <div class="fl-hull"><div class="hull"><i style="width:${p}%" class="${p < 35 ? "low" : ""}"></i></div><small>${te("fleet.hull_short", { hull: s.hull, max: spec.hull })}</small></div>
      <div class="fl-guns"><span class="fl-pips">${pips}</span><small>${te("fleet.guns_short", { guns: s.guns, slots: spec.slots })}</small></div></div>
    <div class="fl-do">${btn(te("fleet.gun_short"), "gun", `data-i="${i}" title="${te("fleet.gun_tip", { price: money(D.gun_price) })}"`, "slim", s.guns >= spec.slots)}
      ${repair}
      ${yard ? btn(te("fleet.sell", { value: money(s.value) }), "sellship", `data-i="${i}"`, "slim ghost", me.ships.length < 2) : ""}</div></div>`;
}

function yardRow(k) {
  const me = S.me, s = D.ships[k];
  const no = me.cash < s.price || me.ships.length >= D.max_fleet;
  return `<div class="yd-row${no ? " dim" : ""}">
    <div class="yd-pic">${Media.html("ship", k, "card", "yd-img", D.graphics.ships[k], { slot: "yard" })}</div>
    <div class="yd-name"><b>${esc(s.name)}</b>${s.fast ? `<span class="tag">${te("tag.fast")}</span>` : ""}</div>
    <div class="yd-n">${s.hold}</div><div class="yd-n yd-hull">${s.hull}</div><div class="yd-n">${s.slots}</div>
    <div class="yd-n yd-price">${money(s.price)}</div>
    <div class="yd-do">${btn(te("btn.buy"), "buyship", `data-ship="${k}"`, "slim primary", no)}</div></div>`;
}

function fleetTab() {
  const me = S.me, yard = D.ports[me.port].shipyard;
  const totalRepair = me.ships.reduce((n, s) => n + s.repair, 0);
  const head = `<div class="yd-row yd-th"><div></div><div>${te("col.ship")}</div><div class="yd-n">${te("col.hold")}</div>
    <div class="yd-n yd-hull">${te("col.hull")}</div><div class="yd-n">${te("col.guns")}</div><div class="yd-n">${te("col.price")}</div><div></div></div>`;
  return `<section class="card fl">
      <div class="mk-head"><h2>${te("fleet.title")}</h2>
        <span class="muted" title="${te("fleet.info")}">${te("fleet.info_short")}</span>
        <span class="mk-hold">${te("fleet.count", { n: me.ships.length, max: D.max_fleet })}</span>
        ${totalRepair ? btn(te("fleet.repair_all", { cost: money(totalRepair) }), "repair", 'data-i="all"', "slim primary") : ""}</div>
      <div class="fl-list">${me.ships.map((s, i) => shipCard(s, i, yard)).join("")}</div></section>
    <section class="card yd"><h2>${te("yard.title")}</h2>${yard
      ? `<div class="yd-list">${head}${Object.keys(D.ships).map(yardRow).join("")}</div>
         <p class="muted">${te("yard.limit", { n: D.max_fleet })}</p>`
      : `<p class="muted">${te("yard.none", { port: portName(me.port), yards: D.yards.join(", ") })}</p>`}</section>`;
}

/* ---------------------------------------------------------------- chart -- */
function chartTab() {
  const me = S.me;
  const dest = me.ready ? me.dest : ui.dest;
  const orders = ui.orders || me.orders;
  const list = Object.keys(D.ports).filter(k => k !== me.port).map(k => {
    const p = D.ports[k];
    const wx = Math.max(S.weather[p.region] || 0, S.weather[D.ports[me.port].region] || 0);
    const known = me.known[k];
    const seen = known ? (S.turn - known.turn === 0 ? te("chart.seen_now") : te("chart.seen_ago", { n: S.turn - known.turn })) : te("chart.unknown");
    return `<button type="button" class="dest ${dest === k ? "on" : ""}" data-act="dest" data-port="${k}">
      <b>${esc(p.name)}</b>${S.crackdown.includes(k) ? `<span class="tag bad">${te("tag.ban")}</span>` : ""}
      <span class="muted">${esc(riskLabel(me.port, k))} · ${weatherBadge(wx, D.weather)}</span>
      <span class="muted">${seen} · ${te("chart.standing", { rep: me.rep[k] })}</span></button>`;
  }).join("");
  return `<section class="card"><h2>${te("chart.title")}</h2>
      ${Chart.svg({ data: D, players: S.players, weather: S.weather, crackdown: S.crackdown, here: me.port, dest, clickable: !me.ready, mine: me.id })}
      <p class="muted">${te("chart.forecast", { pct: Math.round(D.forecast_accuracy * 100) })}</p>
      <div class="dests">${list}</div></section>
    <section class="card"><h2>${te("orders.title")}</h2>
      <div class="seg">${btn(te("orders.fight", { guns: guns() }), "orders", 'data-o="fight"', orders === "fight" ? "on" : "")}${btn(te("orders.run"), "orders", 'data-o="run"', orders === "run" ? "on" : "")}</div>
      <p class="muted">${me.protect > 0 ? te("orders.protected", { months: me.protect }) : te("orders.unprotected")}</p>
      <div class="row">${btn(dest ? te("sail.go", { port: portName(dest) }) : te("sail.choose"), "sail", "", "primary wide", !dest || me.ready)}</div>
      <div class="row">${btn(te("sail.stay", { port: portName(me.port) }), "stay", "", "wide", me.ready)}</div></section>`;
}

/* --------------------------------------------------------------- ledger -- */
function ledgerTab() {
  const me = S.me, goods = Object.keys(D.goods);
  const head = goods.map(g => `<th class="n">${esc(D.goods[g].name.split(" ")[0])}</th>`).join("");
  const rows = Object.keys(D.ports).map(k => {
    const kn = me.known[k];
    const age = kn ? (S.turn - kn.turn === 0 ? te("ledger.now") : te("ledger.ago", { n: S.turn - kn.turn })) : te("ledger.never");
    const cells = goods.map(g => `<td class="n">${kn && kn.prices[g] != null ? kn.prices[g].toLocaleString() : "·"}</td>`).join("");
    return `<tr class="${k === me.port ? "me" : ""}"><td><b>${esc(portName(k))}</b><br><span class="muted">${age} · ${te("chart.standing", { rep: me.rep[k] })}</span></td>${cells}</tr>`;
  }).join("");
  const list = (items, empty) => items.map(n => "<li>" + esc(n) + "</li>").join("") || "<li>" + te(empty) + "</li>";
  return `<section class="card"><h2>${te("ledger.title")}</h2>
      <p class="muted">${te("ledger.info")}</p>
      <div class="scroll"><table class="grid book"><thead><tr><th>${te("col.port")}</th>${head}</tr></thead><tbody>${rows}</tbody></table></div></section>
    <section class="card"><h2>${te("ledger.standings")}</h2>${standings()}
      ${btn(te("st.open_hint"), "tally", "", "wide")}</section>
    <section class="card"><h2>${te("ledger.news")}</h2><ul class="log">${list(S.news, "ledger.no_news")}</ul></section>
    <section class="card"><h2>${te("ledger.log")}</h2><ul class="log">${list(me.log, "ledger.no_log")}</ul></section>
    ${me.host ? `<section class="card"><h2>${te("host.title")}</h2>` + btn(te("host.end_month"), "force", "", "") + newGameControl() + "</section>" : ""}`;
}

/* --------------------------------------------------------------- events -- */
app.addEventListener("input", e => {
  const k = e.target.dataset.k;
  if (!k) return;
  ui.vals[k] = e.target.value;
});

/* The market's drag bars. */
app.addEventListener("input", e => {
  if (!e.target.classList || !e.target.classList.contains("mk-range")) return;
  ui.dragging = true;
  dragRow(e.target);
});
app.addEventListener("change", e => { if (e.target.classList && e.target.classList.contains("mk-range")) dragEnd(); });
["pointerup", "pointercancel", "touchend"].forEach(ev => document.addEventListener(ev, () => setTimeout(dragEnd, 0)));

app.addEventListener("keydown", e => {
  if (e.key !== "Enter" || !e.target.dataset.k) return;
  const k = e.target.dataset.k;
  if (k === "name" || k === "firm") doJoin();
});

/* Tapping anywhere outside the captain's menu closes it. */
document.addEventListener("click", e => {
  if (ui.menu && !(e.target.closest && e.target.closest(".dk-me"))) { ui.menu = false; render(); }
});
document.addEventListener("keydown", e => {
  if (e.key === "Escape" && ui.menu) { ui.menu = false; render(); }
});

async function doJoin() {
  const res = await post("/api/join", { name: val("name"), firm: val("firm") });
  if (res.voice) Voice.say([Object.assign({ text: res.ok ? "" : res.error }, res.voice)], { group: "msg", replace: "msg" });
  if (!res.ok) return toast(res.error, true);
  token = res.token;
  store("seatrader_token", token);
  connect();
}

app.addEventListener("click", async e => {
  const el = e.target.closest("[data-act]");
  if (!el || el.disabled) return;
  const d = el.dataset;
  switch (d.act) {
    case "join": return doJoin();
    case "tab": ui.tab = d.tab; ui.menu = false; return render();
    case "menu": ui.menu = !ui.menu; return render();
    case "speech": Voice.setMuted(!Voice.muted()); return render();
    case "options": ui.menu = false; render(); return toast(t("deck.options_soon"));
    case "tally": {
      // The Tally Book opens in its own window so the deck never scrolls or loses its place.
      const w = window.open("/stats", "seatrader_tally");
      if (!w) location.href = "/stats";
      return;
    }
    case "feed": ui.feed = d.f; return render();
    case "seen": ui.seenTurn = S.turn; Voice.drop("log"); return render();
    case "years": return act("settings", { years: +d.y });
    case "start": return act("start");
    case "fill": ui.vals[d.k] = d.v; return render();
    case "trade": {
      const tr = tradeOf(d.good);
      if (!tr.side) return toast(t("e.qty_first"), true);
      if (await act(tr.side, { good: d.good, qty: tr.n })) { delete ui.tgt[d.good]; render(); }
      return;
    }
    case "bank": case "loan": {
      const a = num(d.act);
      if (!a) return toast(t("e.amount_first"), true);
      if (await act(d.act, { op: d.op, amount: a })) { ui.vals[d.act] = ""; render(); }
      return;
    }
    case "wh": {
      const q = num("w_" + d.good);
      if (!q) return toast(t("e.qty_first"), true);
      if (await act("warehouse", { op: d.op, good: d.good, qty: q })) { ui.vals["w_" + d.good] = ""; render(); }
      return;
    }
    case "protection": return act("protection");
    case "gun": return act("buy_gun", { index: +d.i });
    case "repair": return act("repair", { index: d.i === "all" ? "all" : +d.i });
    case "sellship": return act("sell_ship", { index: +d.i });
    case "buyship": return act("buy_ship", { ship: d.ship });
    case "dest": if (!S.me.ready) { ui.dest = d.port; render(); } return;
    case "orders": ui.orders = d.o; return render();
    case "sail":
      if (await act("sail", { dest: ui.dest, orders: ui.orders || S.me.orders })) ui.dest = null;
      return;
    case "stay": return act("sail", { dest: null, orders: ui.orders || S.me.orders });
    case "unsail": return act("unsail");
    case "force": return act("force");
    case "newgame_ask": ui.confirmNew = true; return render();
    case "newgame_no": ui.confirmNew = false; return render();
    case "newgame": ui.confirmNew = false; return act("new_game");
  }
});

loadInfo().then(info => { D = info.data; VS = Voice.setup(info.voice); Stage.setCast(VS.cast); connect(); });
