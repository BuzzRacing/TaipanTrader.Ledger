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
             spokenTurn: null, newsSeen: null, feed: "log", paneTab: null, drag: false, meOpen: false,
             tally: false, tallyShown: false, tallyTurn: null };
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

/* Silver and hold left for one cargo once every OTHER trade lined up on the market bars is counted:
   buys elsewhere take room and silver, sells elsewhere give them back. Reads the raw bar values (not
   tradeOf) so the bars never chase each other round in a loop. */
function roomFor(good) {
  const me = S.me;
  let cash = me.cash, used = me.used;
  if (!me.ready && D.goods) Object.keys(D.goods).forEach(g => {
    if (g === good || ui.vals["t_" + g] == null) return;
    const raw = parseInt(ui.vals["t_" + g], 10);
    if (isNaN(raw)) return;
    const have = me.cargo[g] || 0, d = Math.max(0, raw) - have;
    if (!d) return;
    const side = d > 0 ? "buy" : "sell", q = quote(g, Math.abs(d), side);
    cash += side === "buy" ? -q : q;
    used += d;
  });
  return { cash, free: Math.max(0, me.capacity - used) };
}

function maxBuy(good) {
  const r = roomFor(good);
  let lo = 0, hi = r.free;
  while (lo < hi) {
    const mid = Math.ceil((lo + hi) / 2);
    if (quote(good, mid, "buy") <= r.cash) lo = mid; else hi = mid - 1;
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

function sailIcon(kind) {
  const paths = {
    calm: '<path d="M3 13c2-2 4-2 6 0s4 2 6 0 4-2 6 0M5 17c2-1.7 4-1.7 6 0s4 1.7 6 0"/>',
    fair: '<circle cx="12" cy="12" r="3.5"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2.1 2.1M16.9 16.9 19 19M19 5l-2.1 2.1M7.1 16.9 5 19"/>',
    squalls: '<path d="M6 15a4 4 0 0 1 .7-7.9A5.5 5.5 0 0 1 17.4 9 3.2 3.2 0 0 1 18 15H6Z"/><path d="m8 18-1 2M13 18l-1 2M18 18l-1 2"/>',
    typhoon: '<path d="M20 7.5c-2.8-3.6-8.7-4.4-12.4-1.7C4.2 8.3 3.5 13 5.8 16.1c2 2.8 6 3.5 8.7 1.4 2.4-1.8 2.9-5.3 1.1-7.6-1.5-2-4.4-2.4-6.3-.9-1.6 1.2-1.9 3.6-.7 5.1"/>',
    distance: '<circle cx="12" cy="12" r="8.5"/><path d="m15.5 8.5-2.1 4.9-4.9 2.1 2.1-4.9 4.9-2.1Z"/>',
    intel: '<path d="M2.5 12s3.5-5.5 9.5-5.5 9.5 5.5 9.5 5.5-3.5 5.5-9.5 5.5S2.5 12 2.5 12Z"/><circle cx="12" cy="12" r="2.4"/>',
    standing: '<path d="M12 2.5 20 6v5.8c0 4.7-3.2 7.7-8 9.7-4.8-2-8-5-8-9.7V6l8-3.5Z"/><path d="m9 12 2 2 4-4"/>',
  };
  return `<svg class="dest-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">${paths[kind] || paths.distance}</svg>`;
}

function voyageRisk(a, b, level) {
  const r = D.voyage_risk || { risk_min: .6, risk_max: 1.8, risk_div: 350,
    storm_chance: [0, .04, .2, .6], pirate_chance: .18, lord_chance: .06, protect_save: .5 };
  const distance = Math.max(r.risk_min, Math.min(r.risk_max, Chart.distance(D, a, b) / r.risk_div));
  const storm = (r.storm_chance[level] || 0) * Math.min(distance, 1.4);
  const pirate = r.pirate_chance * distance * (S.me.protect > 0 ? 1 - r.protect_save : 1);
  const lord = S.me.protect > 0 ? 0 : r.lord_chance * distance;
  return Math.min(.99, 1 - (1 - storm) * (1 - pirate) * (1 - lord));
}

function newGameControl() {
  if (!S.me.host) return "";
  return ui.confirmNew
    ? `<div class="row"><b>${te("host.new_confirm")}</b>${btn(te("host.new_yes"), "newgame", "", "primary")}${btn(te("host.new_no"), "newgame_no")}</div>`
    : `<div class="row">${btn(te("host.new_ask"), "newgame_ask", "", "ghost")}</div>`;
}

/* -------------------------------------------------------------- screens -- */
/* The game screen ("the deck") is a fixed frame that never scrolls: top bar, tab rail, the working
   pane, and the side column with the square speaker stage. Each region is only rewritten
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
      <section class="dk-tallyhost" id="tallyHost"></section>
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
    deck.dataset.tab = ui.tally ? "tally" : ui.tab;
    ["top", "nav", "pane", "side", "over"].forEach(k => { if (!(ui.drag && k === "pane")) region(k, parts[k]); });
    if (ui.paneTab !== ui.tab) { ui.paneTab = ui.tab; app.querySelector(".dk-pane").scrollTop = 0; }
  } else {
    const html = !S.me ? joinScreen() : S.phase === "lobby" ? lobbyScreen() : endScreen();
    if (!app.querySelector(".solo")) { forget(); app.innerHTML = '<div class="solo" data-r="solo"></div>'; }
    region("solo", html);
  }
  syncTally(inGame);

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
  const woman = STAGE_WOMEN[ui.tab];
  const womanImg = woman ? stageWomanHtml(me.port, woman.role) : "";
  document.getElementById("deck").classList.toggle("woman", !!womanImg);
  if (womanImg) {
    Stage.idle(me.port + "#" + woman.role, womanImg, te(woman.title, { port: portName(me.port) }), S.date);
    return;
  }
  Stage.idle(me.port, Media.html("port", me.port, "banner", "stg-img", (g.ports || {})[me.port],
                                 { video: true, slot: "stage", mode: "shuffle" }),
             portName(me.port), S.date);
}

/* The women on the stage: while the Market tab is open, the keeper behind the stalls; while the
   Fleet tab is open, the ship master; while the Ledger tab is open, the tax lady, who keeps the
   books; while the Set sail tab is open, the town's lady mayor, who sees the ships off. Media Library > Ports > (port) pictures
   with the "Market keeper", "Ship master", "Mayor" or "Tax lady" role; a port without its own borrows one from another port. One pick per port
   visit, so she does not flicker on redraws. */
const STAGE_WOMEN = {
  market: { role: "keeper", title: "market.title" },
  fleet: { role: "shipmaster", title: "fleet.master" },
  ledger: { role: "taxlady", title: "ledger.taxlady" },
  chart: { role: "mayor", title: "chart.mayor" },
};
/* Stage titles until the server is restarted with the current strings.py. */
var T_FALLBACK = Object.assign(typeof T_FALLBACK !== "undefined" ? T_FALLBACK : {},
  { "ledger.taxlady": "Tax collector of {port}, keeper of the ledger", "chart.mayor": "Mayor of {port}",
    "deck.me": "Captain {name}: voices and options", "deck.speech": "Voices", "deck.speech_on": "Voices are on",
    "deck.speech_off": "Voices are off", "deck.speech_none": "Voices are turned off for this game",
    "deck.options": "Options", "deck.options_soon": "Options are not built yet.",
    "ledger.here": "you are here", "ledger.blank": "No prices yet. Visit to fill this page.",
    "ledger.key_lo": "cheapest seen", "ledger.key_hi": "dearest seen",
    "ledger.tip_lo": "Cheapest {cargo} you have seen", "ledger.tip_hi": "Dearest {cargo} you have seen",
    "dealer.title": "Dealer's margin", "dealer.margin": "{margin}%", "dealer.standing": "Standing", "dealer.standing_tip": "Your standing here: {rep} of 100",
    "dealer.pay": "You pay", "dealer.get": "You get", "dealer.units": "{n} units", "dealer.cut": "Dealer's cut",
    "dealer.cut_sub": "{margin}% margin", "sail.risk_title": "Routes ranked by voyage risk",
    "sail.risk_note": "Forecast conditions and distance, easiest to hardest", "sail.easiest": "Easiest",
    "sail.hardest": "Hardest", "sail.route": "Route", "sail.weather": "Weather", "sail.distance": "Distance",
    "sail.intel": "Intel", "sail.standing": "Standing", "sail.forecast_risk": "forecast risk",
    "dues.title": "Harbour dues", "dues.due": "Due when you sail", "dues.paid_on_leave": "Paid as you leave",
    "dues.after": "Silver {from} → {to} after dues", "dues.short": "You are {owed} short. It will go on your debt.",
    "dues.stay": "Nothing is due if you stay at anchor.", "dues.restart": "The Mayor's bill shows once the SeaTrader server is restarted.",
    "dues.anchorage": "Anchorage", "dues.anchorage_sub": "{n} ship(s) × {rate}",
    "dues.tonnage": "Tonnage", "dues.tonnage_sub": "{n} hold × {rate} per 100",
    "dues.repair": "Shipyard levy", "dues.repair_sub": "{rate} of {n} repairs",
    "dues.yard": "Shipwright and chandler", "dues.yard_sub": "{rate} of {n} ships and guns",
    "dues.bank": "Counting-house fee", "dues.bank_sub": "{rate} of {n} banked",
    "dues.loan": "Moneylender's stamp", "dues.loan_sub": "{rate} of {n} borrowed or repaid",
    "dues.wh": "Wharfage", "dues.wh_sub": "{n} units × {rate} per 100" });
const womanPick = {};

/* The tab rail shows a picture instead of an icon: the same woman the stage shows for that tab where
   there is one (Market: the market keeper, Fleet: the ship master, Ledger: the tax lady, Set sail: the
   mayor), the port the house is in for Port (and for Set sail without a mayor), and a cast member's
   profile picture for the rest (Ledger without a tax lady: the crier, Advice: the first mate, Tally Book:
   the bookmaker). Repaint any of them in the Media Library and the tab follows. The SVG
   icon is the fallback when there is no picture at all. */
const TAB_FACES = {
  market: { woman: "keeper", cast: "comprador" },
  fleet: { woman: "shipmaster", cast: "shipwright" },
  port: { port: true },
  ledger: { woman: "taxlady", cast: "crier" },
  advice: { cast: "narrator" },
  tally: { cast: "bookmaker" },
  chart: { woman: "mayor", port: true },
};
function tabFaceUrl(k) {
  const f = TAB_FACES[k], me = S.me;
  if (!f) return "";
  if (f.woman) {
    const tagged = subs => Media.items("port", subs, f.woman, false).filter(i => i.r.includes(f.woman));
    let list = tagged(me.port);
    if (!list.length) list = tagged(Object.keys(D.ports));
    if (list.length) {
      const key = f.woman + ":" + me.port;   // same pick as the stage, so tab and stage match
      let it = list.find(i => i.id === womanPick[key]);
      if (!it) { it = list[Math.floor(Math.random() * list.length)]; womanPick[key] = it.id; }
      return it.u;
    }
  }
  if (f.port) {   // Port, or Set sail without a mayor: the port the house is in
    const it = Media.choose("port", me.port, "banner", { slot: "tab", mode: "fixed" });
    return (it && it.u) || (D.graphics.ports || {})[me.port] || "";
  }
  const pic = Media.choose("persona", f.cast, "portrait", { slot: "tab", mode: "fixed" });
  return (pic && pic.u) || ((VS.cast || {})[f.cast] || {}).portrait || "";
}
function womanTabbed(k) {
  const f = TAB_FACES[k];
  return !!(f && f.woman && Media.items("port", Object.keys(D.ports), f.woman, false).some(i => i.r.includes(f.woman)));
}
function tabFace(k) {
  const u = tabFaceUrl(k);
  const isPort = TAB_FACES[k] && TAB_FACES[k].port && !womanTabbed(k);
  return u ? `<img class="dk-tabimg${isPort ? " port" : ""}" src="${esc(u)}" alt="">` : (DECK_ICONS[k] || "");
}
function stageWomanHtml(port, role) {
  const tagged = subs => Media.items("port", subs, role, true).filter(i => i.r.includes(role));
  let list = tagged(port);
  if (!list.length) list = tagged(Object.keys(D.ports));
  if (!list.length) return "";
  const key = role + ":" + port;
  let it = list.find(i => i.id === womanPick[key]);
  if (!it) { it = list[Math.floor(Math.random() * list.length)]; womanPick[key] = it.id; }
  const u = esc(it.u), cls = "stg-img stg-keeper stg-" + role;
  return it.t === "video"
    ? `<video class="${cls}" src="${u}" muted autoplay loop playsinline preload="auto" disablepictureinpicture></video>`
    : `<img class="${cls}" src="${u}" alt="">`;
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

/* The header plaques. While trades are lined up on the market bars, silver and hold show where they
   will land if every lined-up trade goes through, tinted by which way they move. */
function topHtml() {
  const me = S.me, p = pending();
  const dir = (to, from) => to > from ? " up" : to < from ? " dn" : "";
  const stats = [["stat.silver", money(p.cash), "silver" + dir(p.cash, me.cash)], ["stat.bank", money(me.bank)], ["stat.debt", money(me.debt), me.debt > 0 ? "bad" : ""],
                 ["stat.worth", money(me.worth), "worth"], ["stat.hold", p.used + " / " + me.capacity, dir(p.used, me.used).trim()], ["stat.guns", guns()]]
    .map(s => `<div class="plq ${s[2] || ""}"><span>${te(s[0])}</span><b>${s[1]}</b></div>`).join("");
  return `<div class="dk-house"><i class="chip" style="background:${COLORS[me.color % 8]}"></i>
      <div><b>${esc(me.firm)}</b><span class="rankname">${esc(me.rank)}</span>
      <small>${te("bar.where", { port: esc(portName(me.port)), date: esc(S.date), months: S.turns_left })}</small></div></div>
    <div class="dk-stats">${stats}</div>`;
}

/* Silver and hold after every trade lined up on the market bars (the live ones, before Buy/Sell). */
function pending() {
  const me = S.me;
  let cash = me.cash, used = me.used;
  if (me.ready || !D.goods) return { cash, used };
  Object.keys(D.goods).forEach(g => {
    if (ui.vals["t_" + g] == null) return;
    const tr = tradeOf(g);
    if (!tr.side) return;
    const q = quote(g, tr.qty, tr.side);
    cash += tr.side === "buy" ? -q : q;
    used += tr.d;
  });
  return { cash, used };
}

function gameScreen() {
  const me = S.me;
  if (ui.seenTurn === null) ui.seenTurn = me.log.length && S.turn > 0 ? -1 : S.turn;
  const report = ui.seenTurn !== S.turn && me.log.length ? logModal() : "";
  if (ui.seenTurn !== S.turn && !me.log.length) ui.seenTurn = S.turn;

  const top = topHtml();
  const nav = ["port", "market", "fleet", "chart", "ledger"].map(k =>
    `<button type="button" class="${!ui.tally && ui.tab === k ? "on" : ""}${tabFaceUrl(k) ? " face" : ""}" data-act="tab" data-tab="${k}" aria-label="${te("tab." + k)}">` +
    `${tabFace(k)}<span>${te("tab." + k)}</span></button>`).join("") +
    `<button type="button" class="dk-tally${ui.tally ? " on" : ""}${tabFaceUrl("tally") ? " face" : ""}" data-act="tally" aria-pressed="${ui.tally}" aria-label="${te("st.open_hint")}" title="${te("st.open_hint")}">` +
    `${tabFace("tally")}<span>${te("st.open")}</span></button>` +
    `<i class="dk-gap"></i>` + meButton();
  const pane = { market: marketTab, port: portTab, fleet: fleetTab, chart: chartTab, ledger: ledgerTab }[ui.tab]();
  const side = ui.tab === "market" ? dealerCard() : ui.tab === "chart" ? duesCard() : "";
  return { top, nav, pane, side, over: report };
}

/* The captain button at the foot of the rail: the player's picture (S.me.portrait if the server ever
   sends one), otherwise their initials on the house colour, with their name under it. Tapping it opens
   a small fly-out beside it (above it in portrait) with Voices on/off and Options. Tapping outside it
   or pressing Escape closes it. */
function meButton() {
  const me = S.me, open = !!ui.meOpen;
  const name = me.name || me.firm || "";
  const initials = name.split(/\s+/).filter(Boolean).slice(0, 2).map(w => w[0].toUpperCase()).join("") || "?";
  const face = me.portrait ? `<img src="${esc(me.portrait)}" alt="">` : `<em>${esc(initials)}</em>`;
  let fly = "";
  if (open) {
    const on = Voice.enabled(), muted = Voice.muted();
    const voice = !on
      ? `<button type="button" disabled title="${te("deck.speech_none")}">${DECK_ICONS.speech_off}<span>${te("deck.speech")}</span></button>`
      : `<button type="button" class="${muted ? "" : "on"}" data-act="speech" aria-pressed="${!muted}" title="${te(muted ? "deck.speech_off" : "deck.speech_on")}">` +
        `${DECK_ICONS[muted ? "speech_off" : "speech_on"]}<span>${te("deck.speech")}</span></button>`;
    fly = `<div class="dk-fly" role="menu">${voice}` +
      `<button type="button" data-act="options" title="${te("deck.options_soon")}">${DECK_ICONS.options}<span>${te("deck.options")}</span></button></div>`;
  }
  return `<div class="dk-me${open ? " open" : ""}" style="--house:${COLORS[me.color % 8]}">${fly}` +
    `<button type="button" class="dk-face" data-act="me" aria-haspopup="menu" aria-expanded="${open}" aria-label="${te("deck.me", { name })}" title="${te("deck.me", { name })}">` +
    `${face}<span>${esc(name)}</span></button></div>`;
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
/* One fat drag bar per cargo. The bar is how much of it the house will have aboard: it starts at what
   is aboard now (the brass tick), dragging right buys, dragging left sells. The single button beside
   it turns into "Buy n" or "Sell n" with the price. Dragging updates the row in place and the pane
   is not redrawn until the finger lifts, so the bar never jumps out from under it. */
function tradeOf(g) {
  const have = S.me.cargo[g] || 0, max = have + maxBuy(g);
  const raw = parseInt(val("t_" + g), 10);
  const at = isNaN(raw) ? have : Math.max(0, Math.min(max, raw));
  const d = at - have;
  return { have, max, at, d, qty: Math.abs(d), side: d > 0 ? "buy" : d < 0 ? "sell" : "" };
}

function barStyle(tr) {
  // Positions follow the thumb's centre, which travels from half a thumb in to half a thumb short.
  const at = v => `calc(var(--tw) / 2 + (100% - var(--tw)) * ${tr.max ? (v / tr.max).toFixed(4) : 0})`;
  const h = at(tr.have), lo = at(Math.min(tr.have, tr.at)), hi = at(Math.max(tr.have, tr.at));
  const tick = `linear-gradient(90deg,transparent calc(${h} - 2px),var(--bar-tick) calc(${h} - 2px) calc(${h} + 2px),transparent calc(${h} + 2px))`;
  const fill = tr.side === "buy"
    ? `linear-gradient(90deg,var(--bar-held) 0 ${lo},var(--bar-buy) ${lo} ${hi},var(--bar-empty) ${hi} 100%)`
    : tr.side === "sell"
      ? `linear-gradient(90deg,var(--bar-held) 0 ${lo},var(--bar-sell) ${lo} ${hi},var(--bar-empty) ${hi} 100%)`
      : `linear-gradient(90deg,var(--bar-held) 0 ${h},var(--bar-empty) ${h} 100%)`;
  return `background:${tick},${fill}`;
}

function tradeButton(g, tr) {
  if (!tr.side) return `<button type="button" class="mk-go" data-act="trade" data-good="${g}" disabled>
    <b>${tr.max ? te("market.drag") : te("market.no_room")}</b></button>`;
  return `<button type="button" class="mk-go ${tr.side}" data-act="trade" data-good="${g}">
    <b>${te(tr.side === "buy" ? "btn.buy" : "btn.sell")} ${tr.qty.toLocaleString()}</b>
    <small>${money(quote(g, tr.qty, tr.side))}</small></button>`;
}

/* "12 aboard", or "12 → 40 aboard" while a trade is lined up. */
function haveHtml(tr) {
  return (tr.side ? `<s>${tr.have.toLocaleString()}</s> → ` : "") + th("market.aboard", { n: `<b class="mk-at">${tr.at.toLocaleString()}</b>` });
}

function marketRow(g) {
  const me = S.me, good = D.goods[g], tr = tradeOf(g);
  const tag = good.contraband ? ` <span class="tag">${te("tag.contraband")}</span>` : "";
  return `<tr data-good="${g}" class="${tr.side}">
    <td class="mk-ico">${Media.html("cargo", g, "icon", "gicon", D.graphics.goods[g])}</td>
    <td class="mk-name"><b>${esc(good.name)}</b>${tag}</td>
    <td class="n mk-num"><b class="mk-price">${money(me.prices[g])}</b><span class="mk-have">${haveHtml(tr)}</span></td>
    <td class="mk-bar"><input type="range" class="mk-range" id="in_t_${g}" data-k="t_${g}" data-good="${g}" min="0" max="${tr.max}" step="1"
      value="${tr.at}" style="${barStyle(tr)}" ${tr.max && !me.ready ? "" : "disabled"} aria-label="${esc(good.name)}"></td>
    <td class="mk-do">${tradeButton(g, tr)}</td></tr>`;
}

function marketTab() {
  const me = S.me;
  const banned = S.crackdown.includes(me.port);
  const rows = Object.keys(D.goods).map(marketRow).join("");
  return `<section class="card mk" style="--n:${Object.keys(D.goods).length}">
    <header class="mk-head"><h2>${te("market.title", { port: portName(me.port) })}</h2>
      <span class="mk-hold">${te("market.hold_short", { used: pending().used, cap: me.capacity })}</span></header>
    ${banned ? `<p class="note bad">${te("market.banned")}</p>` : ""}
    <table class="mk-table"><thead><tr><th colspan="2">${te("col.cargo")}</th><th class="n">${te("col.price")} · ${te("col.aboard")}</th><th class="mk-scale"><span>${te("btn.sell")}</span><span>${te("btn.buy")}</span></th><th></th></tr></thead>
    <tbody>${rows}</tbody></table></section>`;
}

/* Live update of one market row while its bar is dragged (no redraw). */
function dragRow(g) {
  const row = app.querySelector('.mk-table tr[data-good="' + g + '"]');
  if (!row) return;
  const tr = tradeOf(g), range = row.querySelector(".mk-range");
  range.setAttribute("style", barStyle(tr));
  row.className = tr.side;
  row.querySelector(".mk-have").innerHTML = haveHtml(tr);
  row.querySelector(".mk-do").innerHTML = tradeButton(g, tr);
  // Keep the header plaques and the market's hold count in step with the bar.
  region("top", topHtml());
  const hold = app.querySelector(".mk-head .mk-hold");
  if (hold) hold.innerHTML = te("market.hold_short", { used: pending().used, cap: S.me.capacity });
  region("side", dealerCard());
}

/* The dealer's card under the market keeper on the stage: standing and margin in this port, and what
   the lined-up trades cost. "You pay" is the silver for every planned buy, "You get" the silver for
   every planned sale, and "Dealer's cut" is how much of that the margin takes (the difference from
   trading at the market price with no margin). Updates live while a bar is dragged. */
function dealerCut(g, qty, side) {
  const mid = S.me.prices[g], k = D.impact * qty / D.goods[g].depth;
  const end = side === "buy" ? mid * (1 + k) : mid / (1 + k);
  const total = quote(g, qty, side), base = qty * (mid + end) / 2;
  return { total, cut: Math.round(Math.abs(total - base)) };
}
function dealerCard() {
  const me = S.me;
  if (!me || !D.goods) return "";
  let pay = 0, get = 0, cut = 0, nBuy = 0, nSell = 0;
  if (!me.ready) Object.keys(D.goods).forEach(g => {
    if (ui.vals["t_" + g] == null) return;
    const tr = tradeOf(g);
    if (!tr.side) return;
    const q = dealerCut(g, tr.qty, tr.side);
    cut += q.cut;
    if (tr.side === "buy") { pay += q.total; nBuy += tr.qty; } else { get += q.total; nSell += tr.qty; }
  });
  const margin = pct(me.spread);
  const line = (label, v, cls, sub) => `<div class="dl-row ${cls}"><span>${label}${sub ? `<small>${sub}</small>` : ""}</span><b>${v}</b></div>`;
  const rows = (nBuy || nSell)
    ? (nBuy ? line(te("dealer.pay"), money(pay), "pay", te("dealer.units", { n: nBuy.toLocaleString() })) : "") +
      (nSell ? line(te("dealer.get"), money(get), "get", te("dealer.units", { n: nSell.toLocaleString() })) : "") +
      line(te("dealer.cut"), money(cut), "cut", te("dealer.cut_sub", { margin }))
    : "";
  return `<section class="dl-card" title="${te("market.standing", { rep: me.rep[me.port], margin })}">
    <header><span>${te("dealer.title")}</span><b>${te("dealer.margin", { margin })}</b></header>
    ${standingBar(me.rep[me.port])}${rows}</section>`;
}

/* Standing in this port as a heat bar: the track runs red (0) through amber to green (100) and is
   lit up to the house's standing, with the number at the end. */
function standingBar(rep) {
  const r = Math.max(0, Math.min(100, Math.round(rep || 0)));
  return `<div class="dl-standing" title="${te("dealer.standing_tip", { rep: r })}" style="--rep:${r}%;--rep-hue:${Math.round(r * 1.2)}">
    <span>${te("dealer.standing")}</span><div class="dl-heat" role="meter" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${r}" aria-label="${te("dealer.standing_tip", { rep: r })}"><i></i></div><b>${r}</b></div>`;
}

/* The mayor's bill, shown in the side column under her picture while the Set sail tab is open.
   The server works it out (engine Game.dues) from what the house did in this port this visit:
   anchorage, tonnage, and a share of repairs, ships and guns, bank and loan money, and warehouse
   use. Cargo trading is not on it. It is paid out of silver as the fleet sails; a shortfall goes
   on the debt. Staying at anchor costs nothing. */
function duesCard() {
  const me = S.me, bill = me && me.dues;
  if (!me) return "";
  if (!bill) return `<section class="dl-card du-card"><header><span>${te("dues.title")}</span><b>…</b></header>
    <p class="du-foot">${te("dues.restart")}</p></section>`;   // server still running the code from before the dues
  const share = r => pct(r) + "%";
  const per = r => money(r);
  const subs = {
    anchorage: ln => te("dues.anchorage_sub", { n: ln.basis, rate: per(ln.rate) }),
    tonnage: ln => te("dues.tonnage_sub", { n: ln.basis.toLocaleString(), rate: per(ln.rate) }),
    repair: ln => te("dues.repair_sub", { n: money(ln.basis), rate: share(ln.rate) }),
    yard: ln => te("dues.yard_sub", { n: money(ln.basis), rate: share(ln.rate) }),
    bank: ln => te("dues.bank_sub", { n: money(ln.basis), rate: share(ln.rate) }),
    loan: ln => te("dues.loan_sub", { n: money(ln.basis), rate: share(ln.rate) }),
    wh: ln => te("dues.wh_sub", { n: ln.basis.toLocaleString(), rate: per(ln.rate) }),
  };
  const rows = bill.lines.map(ln => `<div class="dl-row du-line"><span>${te("dues." + ln.key)}<small>${subs[ln.key] ? subs[ln.key](ln) : ""}</small></span><b>${money(ln.amount)}</b></div>`).join("");
  const after = me.cash - bill.total, owed = Math.max(0, -after);
  const foot = `<p class="du-foot">${te("dues.after", { from: money(me.cash), to: money(Math.max(0, after)) })}` +
    `${owed ? `<br><b class="du-short">${te("dues.short", { owed: money(owed) })}</b>` : ""}<br>${te("dues.stay")}</p>`;
  return `<section class="dl-card du-card">
    <header><span>${te("dues.title")}</span><b>${money(bill.total)}</b></header>
    <p class="du-sub">${te(me.ready && me.dest ? "dues.paid_on_leave" : "dues.due")}</p>${rows}${foot}</section>`;
}

/* ----------------------------------------------------------------- port -- */
/* The Port tab opens with the house's news board: standings, port news and this month's log.
   They show in every port; the bank, loans, warehouse and agent below only at home. */
function portBoard() {
  const me = S.me;
  const list = (items, empty) => items.map(n => "<li>" + esc(n) + "</li>").join("") || "<li>" + te(empty) + "</li>";
  return `<section class="card"><h2>${te("ledger.standings")}</h2>${standings()}
      ${btn(te("st.open_hint"), "tally", "", "wide")}</section>
    <section class="card"><h2>${te("ledger.news")}</h2><ul class="log">${list(S.news, "ledger.no_news")}</ul></section>
    <section class="card"><h2>${te("ledger.log")}</h2><ul class="log">${list(me.log, "ledger.no_log")}</ul></section>`;
}

function portTab() {
  const me = S.me;
  if (me.port !== D.home) {
    return `<section class="card">${Media.html("port", me.port, "banner", "portart", D.graphics.ports[me.port])}<h2>${esc(portName(me.port))}</h2>
      <p>${te("port.away")}</p>
      <p class="muted">${te(D.ports[me.port].shipyard ? "port.away_here_yard" : "port.away_here")}</p></section>
    ${portBoard()}`;
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
  return `${portBoard()}
    <section class="card"><h2>${te("bank.title")}</h2>
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
/* Compact ship cards (picture left, name, hull bar, gun pips, slim buttons) and a shipyard table
   built on the same row pattern as the market: picture cell, name, numbers, one button. */
function gunPips(guns, slots) {
  return Array.from({ length: slots }, (_, j) => `<i class="${j < guns ? "on" : ""}"></i>`).join("");
}

function shipCard(s, i, yard) {
  const me = S.me, spec = D.ships[s.type], p = Math.round(100 * s.hull / spec.hull);
  const fix = s.repair
    ? btn(te("fleet.repair", { cost: money(s.repair) }), "repair", `data-i="${i}"`, "fl-btn")
    : `<span class="fl-ok">${te("fleet.seaworthy")}</span>`;
  return `<article class="fl-ship">
    <div class="fl-art">${Media.html("ship", s.type, "card", "fl-img", D.graphics.ships[s.type], { slot: "fleet:" + s.name })}</div>
    <div class="fl-body">
      <header class="fl-name"><b>${esc(s.name)}</b>${spec.fast ? `<span class="tag">${te("tag.fast")}</span>` : ""}
        <span class="fl-type">${te("fleet.ship_line", { type: spec.name, hold: spec.hold })}</span></header>
      <div class="fl-stat"><span class="fl-lbl">${te("col.hull")}</span>
        <div class="hull"><i style="width:${p}%" class="${p < 35 ? "low" : ""}"></i></div><span class="fl-v">${s.hull}/${spec.hull}</span></div>
      <div class="fl-stat"><span class="fl-lbl">${te("col.guns")}</span>
        <span class="fl-pips">${gunPips(s.guns, spec.slots)}</span><span class="fl-v">${s.guns}/${spec.slots}</span></div>
      <div class="fl-acts">${btn(te("fleet.gun_short", { price: money(D.gun_price) }), "gun", `data-i="${i}"`, "fl-btn", s.guns >= spec.slots)}
        ${fix}
        ${yard ? btn(te("fleet.sell", { value: money(s.value) }), "sellship", `data-i="${i}"`, "fl-btn ghost", me.ships.length < 2) : ""}</div>
    </div></article>`;
}

function yardRow(k) {
  const me = S.me, s = D.ships[k];
  const cant = me.cash < s.price || me.ships.length >= D.max_fleet;
  return `<tr class="${cant ? "dim" : ""}">
    <td class="yd-ico">${Media.html("ship", k, "card", "yd-img", D.graphics.ships[k], { slot: "yard" })}</td>
    <td class="yd-name"><b>${esc(s.name)}</b>${s.fast ? `<span class="tag">${te("tag.fast")}</span>` : ""}</td>
    <td class="n">${s.hold}</td><td class="n">${s.hull}</td><td class="n">${s.slots}</td>
    <td class="n yd-price">${money(s.price)}</td>
    <td class="yd-do">${btn(te("btn.buy"), "buyship", `data-ship="${k}"`, "fl-btn primary", cant)}</td></tr>`;
}

function fleetTab() {
  const me = S.me, yard = D.ports[me.port].shipyard;
  const totalRepair = me.ships.reduce((n, s) => n + s.repair, 0);
  const ships = me.ships.map((s, i) => shipCard(s, i, yard)).join("");
  const yardBody = yard
    ? `<table class="yd-table"><thead><tr><th colspan="2">${te("col.ship")}</th><th class="n">${te("col.hold")}</th><th class="n">${te("col.hull")}</th>
        <th class="n">${te("col.guns")}</th><th class="n">${te("col.price")}</th><th></th></tr></thead>
        <tbody>${Object.keys(D.ships).map(yardRow).join("")}</tbody></table>`
    : `<p class="muted fl-none">${te("yard.none", { port: portName(me.port), yards: D.yards.join(", ") })}</p>`;
  return `<section class="card fl">
      <header class="mk-head"><h2>${te("fleet.title")}</h2>
        <span class="muted" title="${esc(t("fleet.info"))}">${te("fleet.info_short")}</span>
        <span class="mk-hold">${te("fleet.count", { n: me.ships.length, max: D.max_fleet })}</span>
        ${totalRepair ? btn(te("fleet.repair_all", { cost: money(totalRepair) }), "repair", 'data-i="all"', "fl-btn primary") : ""}</header>
      <div class="fl-ships">${ships}</div></section>
    <section class="card fl yd">
      <header class="mk-head"><h2>${te("yard.title")}</h2>${yard ? `<span class="muted">${te("yard.limit", { n: D.max_fleet })}</span>` : ""}</header>
      ${yardBody}</section>`;
}

/* ---------------------------------------------------------------- chart -- */
function chartTab() {
  const me = S.me;
  const dest = me.ready ? me.dest : ui.dest;
  const orders = ui.orders || me.orders;
  const routes = Object.keys(D.ports).filter(k => k !== me.port).map(k => {
    const p = D.ports[k];
    const wx = Math.max(S.weather[p.region] || 0, S.weather[D.ports[me.port].region] || 0);
    return { k, p, wx, score: voyageRisk(me.port, k, wx), distance: Chart.distance(D, me.port, k) };
  }).sort((a, b) => a.score - b.score || a.distance - b.distance || a.p.name.localeCompare(b.p.name));
  const minScore = routes.length ? routes[0].score : 0;
  const maxScore = routes.length ? routes[routes.length - 1].score : 1;
  const list = routes.map((route, i) => {
    const { k, p, wx, score } = route;
    const known = me.known[k];
    const seen = known ? (S.turn - known.turn === 0 ? te("chart.seen_now") : te("chart.seen_ago", { n: S.turn - known.turn })) : te("chart.unknown");
    const heat = maxScore > minScore ? (score - minScore) / (maxScore - minScore) : 0;
    const rankLabel = i === 0 ? te("sail.easiest") : i === routes.length - 1 ? te("sail.hardest") : `${te("sail.route")} ${i + 1}`;
    const weatherKind = ["calm", "fair", "squalls", "typhoon"][wx] || "calm";
    return `<button type="button" class="dest sail-card ${dest === k ? "on" : ""}" data-act="dest" data-port="${k}"
      style="--risk-hue:${Math.round(118 * (1 - heat))};--risk-level:${Math.round(score * 100)}%" aria-label="${esc(p.name)}, ${rankLabel}">
      <span class="dest-art">${Media.html("port", k, "banner", "dest-img", D.graphics.ports[k], { slot: "sail:" + k, mode: "fixed" })}
        <span class="dest-title"><b>${esc(p.name)}</b>${S.crackdown.includes(k) ? `<span class="tag bad">${te("tag.ban")}</span>` : ""}</span>
        <span class="dest-rank"><b>#${i + 1}</b><small>${rankLabel}</small></span></span>
      <span class="dest-data">
        <span class="dest-stat wx${wx}">${sailIcon(weatherKind)}<span><small>${te("sail.weather")}</small><strong>${esc(D.weather[wx])}</strong></span></span>
        <span class="dest-stat">${sailIcon("distance")}<span><small>${te("sail.distance")}</small><strong>${esc(riskLabel(me.port, k))}</strong></span></span>
        <span class="dest-stat">${sailIcon("intel")}<span><small>${te("sail.intel")}</small><strong>${seen}</strong></span></span>
        <span class="dest-stat">${sailIcon("standing")}<span><small>${te("sail.standing")}</small><strong>${Math.round(me.rep[k])}/100</strong></span></span>
      </span>
      <span class="dest-heat"><i></i><b>${Math.round(score * 100)}% <small>${te("sail.forecast_risk")}</small></b></span></button>`;
  }).join("");
  return `<section class="card">
      ${Chart.svg({ data: D, players: S.players, weather: S.weather, crackdown: S.crackdown, here: me.port, dest, clickable: !me.ready, mine: me.id })}
      <div class="sail-guide"><span><b>${te("sail.risk_title")}</b><small>${te("sail.risk_note")}</small></span>
        <span class="heat-key"><small>${te("sail.easiest")}</small><i></i><small>${te("sail.hardest")}</small></span></div>
      <div class="dests">${list}</div></section>
    <section class="card"><h2>${te("orders.title")}</h2>
      <div class="seg">${btn(te("orders.fight", { guns: guns() }), "orders", 'data-o="fight"', orders === "fight" ? "on" : "")}${btn(te("orders.run"), "orders", 'data-o="run"', orders === "run" ? "on" : "")}</div>
      <p class="muted">${me.protect > 0 ? te("orders.protected", { months: me.protect }) : te("orders.unprotected")}</p>
      <div class="row">${btn(dest ? te("sail.go", { port: portName(dest) }) : te("sail.choose"), "sail", "", "primary wide", !dest || me.ready)}</div>
      <div class="row">${btn(te("sail.stay", { port: portName(me.port) }), "stay", "", "wide", me.ready)}</div>
      ${me.ready ? `<p class="muted">${S.waiting.length ? te("sail.waiting", { names: S.waiting.join(", ") }) : te("sail.weighing")}</p>
      <div class="row">${btn(te("sail.cancel"), "unsail", "", "ghost wide")}</div>` : ""}</section>`;
}

/* --------------------------------------------------------------- ledger -- */
/* The price book: one row per port, one column per cargo. In each column the cheapest port the
   house has seen is marked jade (buy there) and the dearest oxblood (sell there). Old sightings
   fade with age; ports never visited are shown as blank pages. */
function ledgerTab() {
  const me = S.me, goods = Object.keys(D.goods), ports = Object.keys(D.ports);
  const priceAt = (k, g) => k === me.port ? me.prices[g] : (me.known[k] && me.known[k].prices[g]);
  // Cheapest and dearest port seen for each cargo (needs two ports to mean anything).
  const best = {};
  goods.forEach(g => {
    const seen = ports.filter(k => priceAt(k, g) != null);
    if (seen.length < 2) return;
    const by = seen.slice().sort((a, b) => priceAt(a, g) - priceAt(b, g));
    if (priceAt(by[0], g) !== priceAt(by[by.length - 1], g)) best[g] = { lo: by[0], hi: by[by.length - 1] };
  });
  const head = goods.map(g => {
    const n = me.cargo[g] || 0;
    return `<th class="pb-good" title="${esc(D.goods[g].name)}">
      <span class="pb-gico">${Media.html("cargo", g, "icon", "gicon", D.graphics.goods[g])}${n ? `<i class="pb-aboard">${n}</i>` : ""}
        <span class="pb-gname">${esc(D.goods[g].name.split(" ")[0])}</span></span></th>`;
  }).join("");
  const rows = ports.map(k => {
    const kn = me.known[k], here = k === me.port, age = here ? 0 : kn ? S.turn - kn.turn : null;
    const fresh = age === null ? "never" : age === 0 ? "now" : age <= 2 ? "recent" : "old";
    const when = here ? te("ledger.here") : age === null ? te("ledger.never") : age === 0 ? te("ledger.now") : te("ledger.ago", { n: age });
    const far = here ? "" : `<span class="pb-far">${esc(riskLabel(me.port, k))}</span>`;
    const ban = S.crackdown.includes(k) ? `<span class="tag bad">${te("tag.ban")}</span>` : "";
    const rep = Math.round(me.rep[k]);
    const cells = age === null
      ? `<td class="pb-blank" colspan="${goods.length}">${te("ledger.blank")}</td>`
      : goods.map(g => {
          const v = priceAt(k, g), b = best[g];
          const mark = b && b.lo === k ? "lo" : b && b.hi === k ? "hi" : "";
          const barred = D.goods[g].contraband && S.crackdown.includes(k) ? " barred" : "";
          const tip = mark ? ` title="${esc(te(mark === "lo" ? "ledger.tip_lo" : "ledger.tip_hi", { cargo: D.goods[g].name }))}"` : "";
          return `<td class="pb-p ${mark}${barred}"${tip}>${v != null ? `<b>${v.toLocaleString()}</b>` : "·"}</td>`;
        }).join("");
    return `<tr class="pb-row ${here ? "here" : ""} f-${fresh}">
      <th class="pb-port" scope="row">
        <span class="pb-pimg">${Media.html("port", k, "banner", "pb-img", D.graphics.ports[k])}</span>
        <span class="pb-ptext"><b class="pb-pname">${esc(portName(k))}</b>${ban}
          <span class="pb-meta"><i class="pb-dot"></i>${when}${far ? " · " + far : ""}</span>
          <span class="pb-rep" title="${esc(te("chart.standing", { rep }))}"><i style="width:${rep}%"></i></span></span></th>
      ${cells}</tr>`;
  }).join("");
  return `<section class="card pb">
      <header class="mk-head"><h2>${te("ledger.title")}</h2>
        <span class="pb-key"><i class="lo"></i>${te("ledger.key_lo")}<i class="hi"></i>${te("ledger.key_hi")}</span></header>
      <div class="pb-scroll"><table class="pb-table" style="--n:${goods.length}"><thead><tr><th class="pb-corner">${te("col.port")}</th>${head}</tr></thead>
        <tbody>${rows}</tbody></table></div></section>
    ${me.host ? `<section class="card"><h2>${te("host.title")}</h2>` + btn(te("host.end_month"), "force", "", "") + newGameControl() + "</section>" : ""}`;
}

/* --------------------------------------------------------------- events -- */
app.addEventListener("input", e => {
  const k = e.target.dataset.k;
  if (!k) return;
  ui.vals[k] = e.target.value;
  if (k.startsWith("t_")) { ui.drag = true; dragRow(e.target.dataset.good); }
});
/* The pane is held still while a bar is being dragged, then redrawn once it is let go. */
const endDrag = () => { if (ui.drag) { ui.drag = false; render(); } };
app.addEventListener("change", e => { if (e.target.classList.contains("mk-range")) endDrag(); });
window.addEventListener("pointerup", endDrag);
window.addEventListener("pointercancel", endDrag);

app.addEventListener("keydown", e => {
  if (e.key !== "Enter" || !e.target.dataset.k) return;
  const k = e.target.dataset.k;
  if (k === "name" || k === "firm") doJoin();
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
    case "tab": ui.tab = d.tab; ui.tally = false; return render();
    case "tally": ui.tally = !ui.tally; ui.meOpen = false; return render();
    case "me": ui.meOpen = !ui.meOpen; return render();
    case "speech": Voice.setMuted(!Voice.muted()); return render();
    case "options": ui.meOpen = false; render(); return toast(t("deck.options_soon"));
    case "seen": ui.seenTurn = S.turn; Voice.drop("log"); return render();
    case "years": return act("settings", { years: +d.y });
    case "start": return act("start");
    case "fill": ui.vals[d.k] = d.v; return render();
    case "trade": {
      const tr = tradeOf(d.good);
      if (!tr.side) return toast(t("e.qty_first"), true);
      if (await act(tr.side, { good: d.good, qty: tr.qty })) { delete ui.vals["t_" + d.good]; render(); }
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

/* ------------------------------------------------------------ the Tally Book -- */
/* The Tally Book (stats.js at /stats?embed=1) opens inside this same window, never a new one.
   In a game, Tally in the rail swaps the working pane and the side column for it (deck.css,
   .deck[data-tab="tally"]); in the lobby or at the end it covers the screen (.tally-solo).
   The frame is kept while it is hidden so it reopens at once and where it was left; the deck tells
   it when it is shown or hidden and when a month has passed. Its close button (or Escape) brings
   back the tab the player was on. */
const TALLY_SRC = "/stats?embed=1";
function tallyPost(f, msg) {
  if (f && f.contentWindow) f.contentWindow.postMessage({ tally: msg }, location.origin);
}
function syncTally(inGame) {
  const wantSolo = ui.tally && !inGame;
  let solo = document.getElementById("tallySolo");
  if (!wantSolo && solo) { solo.remove(); solo = null; }
  if (wantSolo && !solo) {
    solo = document.createElement("div");
    solo.id = "tallySolo";
    solo.className = "tally-solo";
    document.body.appendChild(solo);
  }
  const host = inGame ? document.getElementById("tallyHost") : solo;
  if (!host) return;
  let f = host.querySelector(".tally-frame");
  if (!f) {
    if (!ui.tally) return;
    f = document.createElement("iframe");
    f.className = "tally-frame";
    f.title = t("st.title");
    f.src = TALLY_SRC;
    host.appendChild(f);
    ui.tallyShown = true;
    ui.tallyTurn = S.turn;
    return;
  }
  if (ui.tally !== ui.tallyShown) {
    ui.tallyShown = ui.tally;
    if (ui.tally) ui.tallyTurn = S.turn;
    tallyPost(f, ui.tally ? "show" : "hide");
    return;
  }
  if (ui.tally && ui.tallyTurn !== S.turn) { ui.tallyTurn = S.turn; tallyPost(f, "refresh"); }
}
window.addEventListener("message", e => {
  if (e.origin !== location.origin || !e.data || e.data.tally !== "close") return;
  if (ui.tally) { ui.tally = false; render(); }
});
document.addEventListener("keydown", e => {
  if (e.key === "Escape" && ui.tally && !ui.meOpen) { ui.tally = false; render(); }
});

/* The captain's fly-out closes on a tap anywhere else, or on Escape. */
document.addEventListener("click", e => {
  if (ui.meOpen && !e.target.closest(".dk-me")) { ui.meOpen = false; render(); }
});
document.addEventListener("keydown", e => {
  if (e.key === "Escape" && ui.meOpen) { ui.meOpen = false; render(); }
});

loadInfo().then(info => { D = info.data; VS = Voice.setup(info.voice); Stage.setCast(VS.cast); connect(); });
