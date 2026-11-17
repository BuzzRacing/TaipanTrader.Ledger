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
             spokenTurn: null, newsSeen: null };
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
  if (res.voice) Voice.say([res.voice], { group: "msg", replace: "msg" });
  return res.ok;
}

/* Settings were changed in the Admin page: fetch them again, then redraw. */
async function refreshInfo() {
  if (reloading) return;
  reloading = true;
  try { const info = await loadInfo(); D = info.data; VS = Voice.setup(info.voice); } catch (e) { /* try again on the next state */ }
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
    Voice.say(S.voice.log.map((x, i) => x && Object.assign({ tag: "log:" + i }, x)), { group: "log", replace: "log" });
  }
  const news = S.news || [], plans = S.voice.news || [];
  if (ui.newsSeen === null) { ui.newsSeen = new Set(news); return; }
  const fresh = [];
  news.forEach((n, i) => { if (!ui.newsSeen.has(n)) { ui.newsSeen.add(n); if (plans[i]) fresh.unshift(plans[i]); } });
  if (fresh.length && VS.news_players) Voice.say(fresh, { group: "news" });
}

/* Underlines the log line being read. */
function markSpeaking() {
  const item = Voice.current();
  document.querySelectorAll(".modal .log li").forEach((li, i) =>
    li.classList.toggle("speaking", !!item && item.tag === "log:" + i));
}
Voice.onChange(markSpeaking);

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
function render() {
  if (!D || !S) return;
  const active = document.activeElement;
  const focusId = active && active.id && active.id.startsWith("in_") ? active.id : null;
  const caret = focusId ? active.selectionStart : null;
  const scroll = window.scrollY;

  let html;
  if (!S.me) html = joinScreen();
  else if (S.phase === "lobby") html = lobbyScreen();
  else if (S.phase === "ended") html = endScreen();
  else html = gameScreen();
  app.innerHTML = (online ? "" : `<div class="offline">${te("ui.offline")}</div>`) + html;

  if (focusId) {
    const el = document.getElementById(focusId);
    if (el) { el.focus(); try { el.setSelectionRange(caret, caret); } catch (e) { /* ignore */ } }
  }
  window.scrollTo(0, scroll);
  markSpeaking();
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
    <section class="card"><h2>${te("join.houses")}</h2>${roster()}</section>
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
    <section class="card">${newGameControl() || `<p class="muted">${te("end.host_can")}</p>`}
      <p class="muted">${te("end.kept")}</p></section></main>`;
}

function gameScreen() {
  const me = S.me;
  if (ui.seenTurn === null) ui.seenTurn = me.log.length && S.turn > 0 ? -1 : S.turn;
  const report = ui.seenTurn !== S.turn && me.log.length ? logModal() : "";
  if (ui.seenTurn !== S.turn && !me.log.length) ui.seenTurn = S.turn;

  const stats = [["stat.silver", money(me.cash)], ["stat.bank", money(me.bank)], ["stat.debt", money(me.debt), me.debt > 0 ? "bad" : ""],
                 ["stat.worth", money(me.worth)], ["stat.hold", me.used + " / " + me.capacity], ["stat.guns", guns()]]
    .map(s => `<div class="stat ${s[2] || ""}"><span>${te(s[0])}</span><b>${s[1]}</b></div>`).join("");
  const tabs = ["market", "port", "fleet", "chart", "ledger"]
    .map(k => btn(te("tab." + k), "tab", `data-tab="${k}"`, ui.tab === k ? "on" : "")).join("");
  const sailing = me.ready
    ? `<div class="banner"><div><b>${me.dest ? te("sail.orders_to", { port: portName(me.dest) }) : te("sail.orders_stay")}</b><br>
        <span>${S.waiting.length ? te("sail.waiting", { names: S.waiting.join(", ") }) : te("sail.weighing")}</span></div>
        ${btn(te("sail.cancel"), "unsail", "", "ghost")}</div>` : "";
  const body = { market: marketTab, port: portTab, fleet: fleetTab, chart: chartTab, ledger: ledgerTab }[ui.tab]();
  return `<header class="bar">
      <div class="where"><i class="chip" style="background:${COLORS[me.color % 8]}"></i>
        <div><b>${esc(me.firm)}<span class="rankname">${esc(me.rank)}</span></b><span>${te("bar.where", { port: portName(me.port), date: S.date, months: S.turns_left })}</span></div></div>
      <div class="stats">${stats}</div>
    </header>
    <nav class="tabs">${tabs}</nav>${sailing}
    <main class="${me.ready ? "locked" : ""}">${body}</main>${report}`;
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
function marketTab() {
  const me = S.me;
  const banned = S.crackdown.includes(me.port);
  const rows = Object.keys(D.goods).map(g => {
    const have = me.cargo[g] || 0, q = num("q_" + g);
    const est = q ? `<div class="est">${te("market.est", { qty: q, buy: money(quote(g, q, "buy")), sell: money(quote(g, q, "sell")) })}</div>` : "";
    return `<tr><td>${Media.html("cargo", g, "icon", "gicon", D.graphics.goods[g])}<b>${esc(D.goods[g].name)}</b>${D.goods[g].contraband ? ` <span class="tag">${te("tag.contraband")}</span>` : ""}${est}</td>
      <td class="n">${money(me.prices[g])}</td><td class="n">${have || "–"}</td>
      <td class="qty">${input("q_" + g, t("ph.qty"))}
        <div class="mini">${btn(te("btn.max"), "fill", `data-k="q_${g}" data-v="${maxBuy(g)}"`, "link")}${have ? btn(te("btn.all"), "fill", `data-k="q_${g}" data-v="${have}"`, "link") : ""}</div></td>
      <td class="do">${btn(te("btn.buy"), "buy", `data-good="${g}"`, "primary")}${btn(te("btn.sell"), "sell", `data-good="${g}"`, "", !have)}</td></tr>`;
  }).join("");
  return `<section class="card">${Media.html("port", me.port, "banner", "portart", D.graphics.ports[me.port])}
    <h2>${te("market.title", { port: portName(me.port) })}</h2>
    <p class="muted">${te("market.standing", { rep: me.rep[me.port], margin: pct(me.spread) })}</p>
    ${banned ? `<p class="note bad">${te("market.banned")}</p>` : ""}
    <table class="grid market"><thead><tr><th>${te("col.cargo")}</th><th class="n">${te("col.price")}</th><th class="n">${te("col.aboard")}</th><th>${te("col.quantity")}</th><th></th></tr></thead>
    <tbody>${rows}</tbody></table>
    <p class="muted">${te("market.hold", { used: me.used, cap: me.capacity })}</p></section>`;
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
function fleetTab() {
  const me = S.me, yard = D.ports[me.port].shipyard;
  const ships = me.ships.map((s, i) => {
    const spec = D.ships[s.type], p = Math.round(100 * s.hull / spec.hull);
    return `<div class="ship">${Media.html("ship", s.type, "card", "shipart", D.graphics.ships[s.type], { slot: "fleet:" + s.name })}<div class="shiphead"><b>${esc(s.name)}</b><span class="muted">${te("fleet.ship_line", { type: spec.name, hold: spec.hold })}</span></div>
      <div class="hull"><i style="width:${p}%" class="${p < 35 ? "low" : ""}"></i></div>
      <p class="muted">${te("fleet.hull_line", { hull: s.hull, max: spec.hull, guns: s.guns, slots: spec.slots })}</p>
      <div class="row">${btn(te("fleet.add_gun", { price: money(D.gun_price) }), "gun", `data-i="${i}"`, "", s.guns >= spec.slots)}
        ${btn(s.repair ? te("fleet.repair", { cost: money(s.repair) }) : te("fleet.sound"), "repair", `data-i="${i}"`, "", !s.repair)}
        ${yard ? btn(te("fleet.sell", { value: money(s.value) }), "sellship", `data-i="${i}"`, "ghost", me.ships.length < 2) : ""}</div></div>`;
  }).join("");
  const totalRepair = me.ships.reduce((n, s) => n + s.repair, 0);
  const forSale = Object.keys(D.ships).map(k => {
    const s = D.ships[k];
    return `<tr><td>${Media.html("ship", k, "card", "yardart", D.graphics.ships[k], { slot: "yard" })}<b>${esc(s.name)}</b>${s.fast ? ` <span class="tag">${te("tag.fast")}</span>` : ""}</td><td class="n">${s.hold}</td><td class="n">${s.hull}</td>
      <td class="n">${s.slots}</td><td class="n">${money(s.price)}</td>
      <td class="do">${btn(te("btn.buy"), "buyship", `data-ship="${k}"`, "primary", me.cash < s.price || me.ships.length >= D.max_fleet)}</td></tr>`;
  }).join("");
  return `<section class="card"><h2>${te("fleet.title")}</h2>
      <p class="muted">${te("fleet.info")}</p>
      <div class="ships">${ships}</div>
      ${totalRepair ? btn(te("fleet.repair_all", { cost: money(totalRepair) }), "repair", 'data-i="all"', "primary") : ""}</section>
    <section class="card"><h2>${te("yard.title")}</h2>${yard
      ? `<table class="grid"><thead><tr><th>${te("col.ship")}</th><th class="n">${te("col.hold")}</th><th class="n">${te("col.hull")}</th><th class="n">${te("col.guns")}</th><th class="n">${te("col.price")}</th><th></th></tr></thead><tbody>${forSale}</tbody></table>
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
    <section class="card"><h2>${te("ledger.standings")}</h2>${standings()}</section>
    <section class="card"><h2>${te("ledger.news")}</h2><ul class="log">${list(S.news, "ledger.no_news")}</ul></section>
    <section class="card"><h2>${te("ledger.log")}</h2><ul class="log">${list(me.log, "ledger.no_log")}</ul></section>
    ${me.host ? `<section class="card"><h2>${te("host.title")}</h2>` + btn(te("host.end_month"), "force", "", "") + newGameControl() + "</section>" : ""}`;
}

/* --------------------------------------------------------------- events -- */
app.addEventListener("input", e => {
  const k = e.target.dataset.k;
  if (!k) return;
  ui.vals[k] = e.target.value;
  if (k.startsWith("q_")) render();
});

app.addEventListener("keydown", e => {
  if (e.key !== "Enter" || !e.target.dataset.k) return;
  const k = e.target.dataset.k;
  if (k === "name" || k === "firm") doJoin();
});

async function doJoin() {
  const res = await post("/api/join", { name: val("name"), firm: val("firm") });
  if (res.voice) Voice.say([res.voice], { group: "msg", replace: "msg" });
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
    case "tab": ui.tab = d.tab; window.scrollTo(0, 0); return render();
    case "seen": ui.seenTurn = S.turn; Voice.drop("log"); return render();
    case "years": return act("settings", { years: +d.y });
    case "start": return act("start");
    case "fill": ui.vals[d.k] = d.v; return render();
    case "buy": case "sell": {
      const q = num("q_" + d.good);
      if (!q) return toast(t("e.qty_first"), true);
      if (await act(d.act, { good: d.good, qty: q })) { ui.vals["q_" + d.good] = ""; render(); }
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

loadInfo().then(info => { D = info.data; VS = Voice.setup(info.voice); connect(); });
