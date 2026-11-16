/* SeaTrader player screen. The server owns the game; this file only draws the
   latest state and sends the player's choices back. */
"use strict";

let D = null;            // static reference data (goods, ports, ships)
let S = null;            // latest game state from the server
let token = store("seatrader_token");
let stream = null;
let online = true;
const ui = { tab: "market", vals: {}, dest: null, orders: null, seenTurn: null, busy: false, confirmNew: false };
const app = document.getElementById("app");

/* ---------------------------------------------------------------- net -- */
async function post(path, body) {
  try {
    const r = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" },
                                  body: JSON.stringify(body) });
    return await r.json();
  } catch (e) {
    return { ok: false, error: "Cannot reach the game server." };
  }
}

async function act(type, extra) {
  if (ui.busy) return;
  ui.busy = true;
  const res = await post("/api/act", Object.assign({ token, type }, extra || {}));
  ui.busy = false;
  toast(res.ok ? res.msg : res.error, !res.ok);
  return res.ok;
}

function connect() {
  if (stream) stream.close();
  stream = listen(token, state => {
    S = state;
    if (state.unknown_token) {
      token = null; store("seatrader_token", null);
      ui.seenTurn = null; ui.tab = "market"; ui.dest = null; ui.confirmNew = false;
      connect(); return;
    }
    render();
  }, ok => { if (ok !== online) { online = ok; render(); } });
}

let toastTimer = null;
function toast(msg, bad) {
  const t = document.getElementById("toast");
  t.textContent = msg || "";
  t.className = "show" + (bad ? " bad" : "");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.className = ""; }, bad ? 4200 : 2600);
}

/* ------------------------------------------------------------- helpers -- */
const val = k => ui.vals[k] == null ? "" : ui.vals[k];
const num = k => { const n = parseInt(val(k), 10); return n > 0 ? n : 0; };
const input = (k, ph, extra) =>
  `<input id="in_${k}" data-k="${k}" type="text" autocomplete="off" ` +
  `placeholder="${ph || "0"}" value="${esc(val(k))}" ${extra || 'inputmode="numeric"'}>`;
const btn = (label, action, data, cls, disabled) =>
  `<button type="button" class="${cls || ""}" data-act="${action}" ${data || ""} ${disabled ? "disabled" : ""}>${label}</button>`;

function quote(good, qty, side) {
  const mid = S.me.prices[good], k = 0.25 * qty / D.goods[good].depth;
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

const portName = k => D.ports[k].name;
const guns = () => S.me.ships.reduce((n, s) => n + s.guns, 0);

function riskLabel(a, b) {
  const d = Chart.distance(D, a, b);
  return d < 260 ? "short run" : d < 480 ? "long passage" : "far voyage";
}

function newGameControl() {
  if (!S.me.host) return "";
  return ui.confirmNew
    ? `<div class="row"><b>End this game for everyone and open a new one?</b>${btn("Yes, new game", "newgame", "", "primary")}${btn("Keep playing", "newgame_no")}</div>`
    : `<div class="row">${btn("Host: start a new game", "newgame_ask", "", "ghost")}</div>`;
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
  app.innerHTML = (online ? "" : '<div class="offline">Connection lost. Reconnecting…</div>') + html;

  if (focusId) {
    const el = document.getElementById(focusId);
    if (el) { el.focus(); try { el.setSelectionRange(caret, caret); } catch (e) { /* ignore */ } }
  }
  window.scrollTo(0, scroll);
}

function masthead(sub) {
  return `<header class="masthead"><h1>Sea<span>Trader</span></h1><p>${sub}</p></header>`;
}

function roster() {
  if (!S.players.length) return '<p class="muted">No trading houses yet.</p>';
  return '<ul class="roster">' + S.players.map(p =>
    `<li><i class="chip" style="background:${COLORS[p.color % 8]}"></i><b>${esc(p.firm)}</b> ` +
    `<span class="muted">${esc(p.name)}${p.host ? " · host" : ""}${p.present ? "" : " · away"}</span></li>`).join("") + "</ul>";
}

function joinScreen() {
  const late = S.phase === "port" ? '<p class="note">A game is under way. You can still join it.</p>' : "";
  const over = S.phase === "ended" ? '<p class="note">The last game has ended. Ask the host to start a new one.</p>' : "";
  return masthead("Trading the China seas, 1860") + `<main class="narrow">
    <section class="card"><h2>Found your trading house</h2>${late}${over}
      <label>Your name ${input("name", "e.g. Anthony", 'inputmode="text" maxlength="20"')}</label>
      <label>Name of your firm ${input("firm", "e.g. Noble House", 'inputmode="text" maxlength="28"')}</label>
      ${btn("Join the game", "join", "", "primary wide")}
      <p class="muted">Already playing? Enter the same name to pick up your firm on this device.</p>
    </section>
    <section class="card"><h2>Houses in the harbour</h2>${roster()}</section>
    <p class="muted center">Other devices join at <b>${esc(S.join_url)}</b></p></main>`;
}

function lobbyScreen() {
  const me = S.me;
  const years = [1, 2, 3, 5, 10].map(y =>
    btn(y + (y === 1 ? " year" : " years"), "years", `data-y="${y}"`, S.years === y ? "on" : "")).join("");
  const host = me.host
    ? `<h2>You are the host</h2><p>Game length</p><div class="seg">${years}</div>
       <p class="muted">One turn is one month, so ${S.years} years is ${S.years * 12} turns.</p>
       ${btn("Start the game", "start", "", "primary wide")}`
    : `<h2>Waiting for the host</h2><p class="muted">The game runs for ${S.years} years. The host starts it when everyone is in.</p>`;
  return masthead("Trading the China seas, 1860") + `<main class="narrow">
    <section class="card">${host}</section>
    <section class="card"><h2>Houses in the harbour</h2>${roster()}</section>
    <p class="muted center">Other devices join at <b>${esc(S.join_url)}</b><br>
    Big-screen harbor board: <b>${esc(S.join_url)}/board</b></p></main>`;
}

function standings() {
  const rows = S.players.slice().sort((a, b) => b.worth - a.worth).map((p, i) =>
    `<tr class="${p.id === S.me.id ? "me" : ""}"><td>${i + 1}</td>` +
    `<td><i class="chip" style="background:${COLORS[p.color % 8]}"></i>${esc(p.firm)}<br><span class="muted">${esc(p.name)}</span></td>` +
    `<td>${esc(portName(p.port))}</td><td class="n">${p.ships}</td><td class="n">${money(p.worth)}</td></tr>`).join("");
  return `<table class="grid"><thead><tr><th></th><th>House</th><th>Port</th><th class="n">Ships</th><th class="n">Net worth</th></tr></thead><tbody>${rows}</tbody></table>`;
}

function endScreen() {
  const top = S.players.slice().sort((a, b) => b.worth - a.worth)[0];
  return masthead("The books are closed, " + esc(S.date)) + `<main class="narrow">
    <section class="card"><h2>${esc(top.name)} of ${esc(top.firm)} is Taipan</h2>${standings()}</section>
    <section class="card">${newGameControl() || '<p class="muted">The host can open a new game from their screen.</p>'}
      <p class="muted">The finished game is kept in the saves folder.</p></section></main>`;
}

function gameScreen() {
  const me = S.me;
  if (ui.seenTurn === null) ui.seenTurn = me.log.length && S.turn > 0 ? -1 : S.turn;
  const report = ui.seenTurn !== S.turn && me.log.length ? logModal() : "";
  if (ui.seenTurn !== S.turn && !me.log.length) ui.seenTurn = S.turn;

  const stats = [["Silver", money(me.cash)], ["Bank", money(me.bank)], ["Debt", money(me.debt), me.debt > 0 ? "bad" : ""],
                 ["Net worth", money(me.worth)], ["Hold", me.used + " / " + me.capacity], ["Guns", guns()]]
    .map(s => `<div class="stat ${s[2] || ""}"><span>${s[0]}</span><b>${s[1]}</b></div>`).join("");
  const tabs = [["market", "Market"], ["port", "Port"], ["fleet", "Fleet"], ["chart", "Set sail"], ["ledger", "Ledger"]]
    .map(t => btn(t[1], "tab", `data-tab="${t[0]}"`, ui.tab === t[0] ? "on" : "")).join("");
  const sailing = me.ready
    ? `<div class="banner"><div><b>${me.dest ? "Orders given: sail for " + esc(portName(me.dest)) : "Orders given: remain at anchor"}</b><br>
        <span>${S.waiting.length ? "Waiting for " + S.waiting.map(esc).join(", ") : "Weighing anchor…"}</span></div>
        ${btn("Cancel orders", "unsail", "", "ghost")}</div>` : "";
  const body = { market: marketTab, port: portTab, fleet: fleetTab, chart: chartTab, ledger: ledgerTab }[ui.tab]();
  return `<header class="bar">
      <div class="where"><i class="chip" style="background:${COLORS[me.color % 8]}"></i>
        <div><b>${esc(me.firm)}</b><span>${esc(portName(me.port))} · ${esc(S.date)} · ${S.turns_left} months left</span></div></div>
      <div class="stats">${stats}</div>
    </header>
    <nav class="tabs">${tabs}</nav>${sailing}
    <main class="${me.ready ? "locked" : ""}">${body}</main>${report}`;
}

function logModal() {
  return `<div class="veil"><div class="modal"><p class="eyebrow">Captain's log</p><h2>${esc(S.date)}</h2>
    <ul class="log">${S.me.log.map(l => "<li>" + esc(l) + "</li>").join("")}</ul>
    ${btn("Go ashore", "seen", "", "primary wide")}</div></div>`;
}

/* --------------------------------------------------------------- market -- */
function marketTab() {
  const me = S.me;
  const banned = S.crackdown.includes(me.port);
  const rows = Object.keys(D.goods).map(g => {
    const have = me.cargo[g] || 0, q = num("q_" + g);
    const est = q ? `<div class="est">Buy ${q}: ${money(quote(g, q, "buy"))} · Sell ${q}: ${money(quote(g, q, "sell"))}</div>` : "";
    return `<tr><td><b>${esc(D.goods[g].name)}</b>${D.goods[g].contraband ? ' <span class="tag">contraband</span>' : ""}${est}</td>
      <td class="n">${money(me.prices[g])}</td><td class="n">${have || "–"}</td>
      <td class="qty">${input("q_" + g, "qty")}
        <div class="mini">${btn("max", "fill", `data-k="q_${g}" data-v="${maxBuy(g)}"`, "link")}${have ? btn("all", "fill", `data-k="q_${g}" data-v="${have}"`, "link") : ""}</div></td>
      <td class="do">${btn("Buy", "buy", `data-good="${g}"`, "primary")}${btn("Sell", "sell", `data-good="${g}"`, "", !have)}</td></tr>`;
  }).join("");
  return `<section class="card">
    <h2>${esc(portName(me.port))} market</h2>
    <p class="muted">Your standing here is ${me.rep[me.port]} of 100, so dealers take a ${(me.spread * 100).toFixed(1)}% margin.
      Large orders move the price for everyone.</p>
    ${banned ? '<p class="note bad">Opium is banned here. Ships carrying it risk seizure, but buyers pay half as much again.</p>' : ""}
    <table class="grid market"><thead><tr><th>Cargo</th><th class="n">Price</th><th class="n">Aboard</th><th>Quantity</th><th></th></tr></thead>
    <tbody>${rows}</tbody></table>
    <p class="muted">Hold: ${me.used} of ${me.capacity} units used.</p></section>`;
}

/* ----------------------------------------------------------------- port -- */
function portTab() {
  const me = S.me;
  if (me.port !== D.home) {
    return `<section class="card"><h2>${esc(portName(me.port))}</h2>
      <p>The bank, Elder Brother Wu, your warehouse and Li Yuen's agent are all in Hong Kong.</p>
      <p class="muted">Here you can trade in the market${D.ports[me.port].shipyard ? ", visit the shipyard" : ""} and repair your ships.</p></section>`;
  }
  const goods = Object.keys(D.goods).filter(g => (me.cargo[g] || 0) + (me.wh[g] || 0) > 0);
  const whUsed = Object.values(me.wh).reduce((a, b) => a + b, 0);
  const whRows = goods.length ? goods.map(g => `<tr><td><b>${esc(D.goods[g].name)}</b></td>
      <td class="n">${me.cargo[g] || "–"}</td><td class="n">${me.wh[g] || "–"}</td>
      <td class="qty">${input("w_" + g, "qty")}</td>
      <td class="do">${btn("Store", "wh", `data-op="store" data-good="${g}"`, "", !me.cargo[g])}${btn("Load", "wh", `data-op="take" data-good="${g}"`, "", !me.wh[g])}</td></tr>`).join("")
    : '<tr><td colspan="5" class="muted">Nothing aboard or in store.</td></tr>';
  const liYuen = me.protect > 2
    ? `<p>Li Yuen is content. His fleets will leave you be for ${me.protect} more months.</p>`
    : `<p>${me.protect > 0 ? "Your arrangement runs out in " + me.protect + " months." : "You have no arrangement with Li Yuen. His war junks will hunt you."}</p>
       ${btn("Pay tribute of " + money(me.protect_cost), "protection", "", "primary")}`;
  return `<section class="card"><h2>Merchants' Bank of Hong Kong</h2>
      <p class="muted">Balance ${money(me.bank)} · pays ${(D.bank_rate * 100).toFixed(1)}% a month · safe from thieves.</p>
      <div class="row">${input("bank", "amount")}${btn("Deposit", "bank", 'data-op="deposit"', "primary")}${btn("Withdraw", "bank", 'data-op="withdraw"')}
        ${btn("all silver", "fill", `data-k="bank" data-v="${me.cash}"`, "link")}</div></section>
    <section class="card"><h2>Elder Brother Wu, moneylender</h2>
      <p class="muted">You owe ${money(me.debt)} · ${(D.loan_rate * 100).toFixed(0)}% a month, compounding · he will lend ${money(me.loan_room)} more.</p>
      <div class="row">${input("loan", "amount")}${btn("Repay", "loan", 'data-op="repay"', "primary")}${btn("Borrow", "loan", 'data-op="borrow"')}
        ${btn("whole debt", "fill", `data-k="loan" data-v="${Math.min(me.debt, me.cash)}"`, "link")}</div></section>
    <section class="card"><h2>Your warehouse</h2>
      <p class="muted">${whUsed.toLocaleString()} of ${me.wh_cap.toLocaleString()} units in store. Hold: ${me.used} of ${me.capacity}.</p>
      <table class="grid"><thead><tr><th>Cargo</th><th class="n">Aboard</th><th class="n">In store</th><th>Quantity</th><th></th></tr></thead><tbody>${whRows}</tbody></table></section>
    <section class="card"><h2>Li Yuen's agent</h2>${liYuen}</section>`;
}

/* ---------------------------------------------------------------- fleet -- */
function fleetTab() {
  const me = S.me, yard = D.ports[me.port].shipyard;
  const ships = me.ships.map((s, i) => {
    const spec = D.ships[s.type], pct = Math.round(100 * s.hull / spec.hull);
    return `<div class="ship"><div class="shiphead"><b>${esc(s.name)}</b><span class="muted">${esc(spec.name)} · hold ${spec.hold}</span></div>
      <div class="hull"><i style="width:${pct}%" class="${pct < 35 ? "low" : ""}"></i></div>
      <p class="muted">Hull ${s.hull} of ${spec.hull} · guns ${s.guns} of ${spec.slots}</p>
      <div class="row">${btn("Add gun " + money(D.gun_price), "gun", `data-i="${i}"`, "", s.guns >= spec.slots)}
        ${btn(s.repair ? "Repair " + money(s.repair) : "Sound", "repair", `data-i="${i}"`, "", !s.repair)}
        ${yard ? btn("Sell " + money(s.value), "sellship", `data-i="${i}"`, "ghost", me.ships.length < 2) : ""}</div></div>`;
  }).join("");
  const totalRepair = me.ships.reduce((n, s) => n + s.repair, 0);
  const forSale = Object.keys(D.ships).map(k => {
    const s = D.ships[k];
    return `<tr><td><b>${esc(s.name)}</b>${s.fast ? ' <span class="tag">fast</span>' : ""}</td><td class="n">${s.hold}</td><td class="n">${s.hull}</td>
      <td class="n">${s.slots}</td><td class="n">${money(s.price)}</td>
      <td class="do">${btn("Buy", "buyship", `data-ship="${k}"`, "primary", me.cash < s.price || me.ships.length >= D.max_fleet)}</td></tr>`;
  }).join("");
  return `<section class="card"><h2>Your fleet</h2>
      <p class="muted">Your ships sail together and share one hold. If a ship is lost, so is the cargo the rest cannot carry.</p>
      <div class="ships">${ships}</div>
      ${totalRepair ? btn("Repair all for " + money(totalRepair), "repair", 'data-i="all"', "primary") : ""}</section>
    <section class="card"><h2>Shipyard</h2>${yard
      ? `<table class="grid"><thead><tr><th>Ship</th><th class="n">Hold</th><th class="n">Hull</th><th class="n">Guns</th><th class="n">Price</th><th></th></tr></thead><tbody>${forSale}</tbody></table>
         <p class="muted">A fleet may have up to ${D.max_fleet} ships.</p>`
      : `<p class="muted">No shipyard in ${esc(portName(me.port))}. Ships are bought and sold in Hong Kong, Shanghai, Singapore and Calcutta. Repairs cost more here.</p>`}</section>`;
}

/* ---------------------------------------------------------------- chart -- */
function chartTab() {
  const me = S.me;
  const dest = me.ready ? me.dest : ui.dest;
  const orders = ui.orders || me.orders;
  const list = Object.keys(D.ports).filter(k => k !== me.port).map(k => {
    const p = D.ports[k];
    const wx = Math.max(S.weather[p.region], S.weather[D.ports[me.port].region]);
    const known = me.known[k];
    return `<button type="button" class="dest ${dest === k ? "on" : ""}" data-act="dest" data-port="${k}">
      <b>${esc(p.name)}</b>${S.crackdown.includes(k) ? '<span class="tag bad">opium ban</span>' : ""}
      <span class="muted">${riskLabel(me.port, k)} · ${weatherBadge(wx, D.weather)}</span>
      <span class="muted">${known ? "prices seen " + (S.turn - known.turn === 0 ? "this month" : (S.turn - known.turn) + " mo ago") : "prices unknown"} · standing ${me.rep[k]}</span></button>`;
  }).join("");
  return `<section class="card"><h2>Where next?</h2>
      ${Chart.svg({ data: D, players: S.players, weather: S.weather, crackdown: S.crackdown, here: me.port, dest, clickable: !me.ready, mine: me.id })}
      <p class="muted">The forecast is for this month's sailing and is right about four times in five. Longer passages meet more storms and pirates.</p>
      <div class="dests">${list}</div></section>
    <section class="card"><h2>Standing orders if attacked</h2>
      <div class="seg">${btn("Fight (" + guns() + " guns)", "orders", 'data-o="fight"', orders === "fight" ? "on" : "")}${btn("Run", "orders", 'data-o="run"', orders === "run" ? "on" : "")}</div>
      <p class="muted">${me.protect > 0 ? "Li Yuen's protection has " + me.protect + " months to run." : "You have no arrangement with Li Yuen."}</p>
      <div class="row">${btn(dest ? "Set sail for " + esc(portName(dest)) : "Choose a port above", "sail", "", "primary wide", !dest || me.ready)}</div>
      <div class="row">${btn("Stay in " + esc(portName(me.port)) + " this month", "stay", "", "wide", me.ready)}</div></section>`;
}

/* --------------------------------------------------------------- ledger -- */
function ledgerTab() {
  const me = S.me, goods = Object.keys(D.goods);
  const head = goods.map(g => `<th class="n">${esc(D.goods[g].name.split(" ")[0])}</th>`).join("");
  const rows = Object.keys(D.ports).map(k => {
    const kn = me.known[k];
    const age = kn ? (S.turn - kn.turn === 0 ? "now" : (S.turn - kn.turn) + " mo") : "";
    const cells = goods.map(g => `<td class="n">${kn ? kn.prices[g].toLocaleString() : "·"}</td>`).join("");
    return `<tr class="${k === me.port ? "me" : ""}"><td><b>${esc(portName(k))}</b><br><span class="muted">${kn ? "seen " + age : "not visited"} · standing ${me.rep[k]}</span></td>${cells}</tr>`;
  }).join("");
  return `<section class="card"><h2>Price book</h2>
      <p class="muted">Prices as you last saw them in each port. They will have moved since.</p>
      <div class="scroll"><table class="grid book"><thead><tr><th>Port</th>${head}</tr></thead><tbody>${rows}</tbody></table></div></section>
    <section class="card"><h2>Standings</h2>${standings()}</section>
    <section class="card"><h2>News from the ports</h2><ul class="log">${S.news.map(n => "<li>" + esc(n) + "</li>").join("") || "<li>No news.</li>"}</ul></section>
    <section class="card"><h2>Captain's log</h2><ul class="log">${me.log.map(n => "<li>" + esc(n) + "</li>").join("") || "<li>Nothing to report.</li>"}</ul></section>
    ${me.host ? '<section class="card"><h2>Host</h2>' + btn("End the month now", "force", "", "") + newGameControl() + "</section>" : ""}`;
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
    case "seen": ui.seenTurn = S.turn; return render();
    case "years": return act("settings", { years: +d.y });
    case "start": return act("start");
    case "force": return act("force");
    case "newgame_ask": ui.confirmNew = true; return render();
    case "newgame_no": ui.confirmNew = false; return render();
    case "newgame": ui.confirmNew = false; return act("new_game");
    case "fill": ui.vals[d.k] = d.v; return render();
    case "buy": case "sell": {
      const q = num("q_" + d.good);
      if (!q) return toast("Enter a quantity first.", true);
      if (await act(d.act, { good: d.good, qty: q })) { ui.vals["q_" + d.good] = ""; render(); }
      return;
    }
    case "bank": case "loan": {
      const a = num(d.act);
      if (!a) return toast("Enter an amount first.", true);
      if (await act(d.act, { op: d.op, amount: a })) { ui.vals[d.act] = ""; render(); }
      return;
    }
    case "wh": {
      const q = num("w_" + d.good);
      if (!q) return toast("Enter a quantity first.", true);
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
  }
});

loadInfo().then(info => { D = info.data; connect(); });
