/* SeaTrader player screen. The server owns the game; this file only draws the
   latest state and sends the player's choices back. All wording comes from
   the server through t("key"), so the Admin page can change any of it. */
"use strict";

let D = null;            // reference data (goods, ports, ships, brand, wording)
let S = null;            // latest game state from the server
/* This player's own home port (where they started): bank, lender, warehouse and protection. */
function myHome() { return (S && S.me && S.me.home) || D.home; }
/* Each house has its own home port, so {home} in any wording means this player's. */
function applyHome() { if (S && S.me && D && D.ports && D.ports[myHome()]) TOK.home = D.ports[myHome()].name; }
let token = store("seatrader_token");
let stream = null;
let online = true;
let reloading = false;
const ui = { tab: "port", vals: {}, dest: null, orders: null, seenTurn: null, busy: false, confirmNew: false,
             spokenTurn: null, newsSeen: null, feed: "log", paneTab: null, drag: false, meOpen: false,
             tally: false, tallyShown: false, tallyTurn: null,
             bookView: "signals", bookGood: null, bookPort: null, bookMode: "buy", bookRoute: null,
             portView: "arrival", portTurn: null, plRange: "voyage" };
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
  const requestedCfg = S.cfg;
  try { const info = await loadInfo(); D = info.data; VS = Voice.setup(info.voice); Stage.setCast(VS.cast); } catch (e) { /* try again on the next state */ }
  applyHome();
  reloading = false;
  if (S.cfg !== requestedCfg && S.cfg !== cfgSeen) return refreshInfo();
  if (ui.dest && !D.ports[ui.dest]) ui.dest = null;
  render();
  speak();
}

function connect() {
  if (stream) stream.close();
  stream = listen(token, state => {
    S = state;
    applyHome();
    if (state.unknown_token) { token = null; store("seatrader_token", null); connect(); return; }
    if (state.cfg !== cfgSeen) return refreshInfo();
    render();
    speak();
  }, ok => { if (ok !== online) { online = ok; render(); } });
}

/* Reads the month's log aloud while it is on screen, and any fresh news if this screen reads news. */
function speak() {
  if (!S || !S.voice) return;
  if (S.voice.log && document.querySelector(".captains-log") && ui.spokenTurn !== S.turn) {
    ui.spokenTurn = S.turn;
    Voice.say(S.voice.log.map((x, i) => x && Object.assign({ tag: "log:" + S.turn + ":" + i, text: S.me.log[i] }, x)), { group: "log", replace: "log" });
  }
  const news = S.news || [], plans = S.voice.news || [];
  if (ui.newsSeen === null) { ui.newsSeen = new Set(news); return; }
  const fresh = [];
  news.forEach((n, i) => { if (!ui.newsSeen.has(n)) { ui.newsSeen.add(n); if (plans[i]) fresh.unshift(Object.assign({ text: n }, plans[i])); } });
  if (fresh.length && VS.news_players) Voice.say(fresh, { group: "news" });
  Customs.speak();
}

function markSpeaking() {
  const item = Voice.current();
  Customs.markSpeaking(item);
  const log = document.querySelector(".captains-log");
  if (!log) return;
  const previous = log.querySelector(".cl-entry[aria-current]");
  const active = item && item.group === "log"
    ? Array.from(log.querySelectorAll(".cl-entry")).find(line => line.dataset.voiceTag === item.tag)
    : null;
  if (previous === active) return;
  if (previous) previous.removeAttribute("aria-current");
  if (active) {
    active.setAttribute("aria-current", "true");
    active.scrollIntoView({ block: "nearest" });
  }
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
  if (el && drawn[name] !== html) {
    // An overlay that is only changing its contents does not fade in again.
    const veil = name === "over" && el.querySelector(".veil");
    const kind = veil && ["cl-veil", "cx-veil"].find(c => veil.classList.contains(c));
    el.innerHTML = html; drawn[name] = html; Chart.fit(el);
    const next = kind && el.querySelector(".veil." + kind);
    if (next) next.classList.add("no-fade");
  }
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
    ["top", "nav", "pane", "side", "over"].forEach(k => {
      if (ui.drag && k === "pane") return;
      // The Port Authority's declaration desk is updated in place while it stays open.
      if (k === "over" && parts.over.includes("cx-desk declare") && Customs.keep()) { drawn.over = null; return; }
      region(k, parts[k]);
    });
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
  if (typeof Battle !== "undefined") Battle.sync();
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
  // At the Port Authority's desk the officer is already in the popup, so the stage shows the port.
  const cxOpen = Customs.isOpen() && !document.querySelector(".captains-log");
  // In the Mayor's Parlour the stage shows the port's Mayor.
  const woman = cxOpen ? null : mayorOpen() ? STAGE_WOMEN.chart : STAGE_WOMEN[ui.tab];
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
  // Ledger (the price book) has no stage: the side column is hidden so the table gets the room.
  chart: { role: "mayor", title: "chart.mayor" },
};
/* Stage titles until the server is restarted with the current strings.py. */
var T_FALLBACK = Object.assign(typeof T_FALLBACK !== "undefined" ? T_FALLBACK : {},
  { "bar.welcome": "Welcome to", "bar.came.sailed": "in from {from}", "bar.came.stayed": "a month at anchor", "bar.came.wrecked": "back after the wreck",
    "ledger.taxlady": "Tax collector of {port}, keeper of the ledger", "chart.mayor": "Mayor of {port}",
    "chart.current": "CURRENT PORT", "chart.destination": "DESTINATION", "chart.route_warning": "ROUTE WARNING", "chart.route_forecast": "Route forecast: {weather}",
    "deck.me": "Captain {name}: voices and options", "deck.speech": "Voices", "deck.speech_on": "Voices are on",
    "deck.speech_off": "Voices are off", "deck.speech_none": "Voices are turned off for this game",
    "deck.options": "Options", "deck.options_soon": "Options are not built yet.",
    "ledger.here": "you are here", "ledger.blank": "No prices yet. Visit to fill this page.",
    "ledger.key_lo": "cheapest seen", "ledger.key_hi": "dearest seen",
    "ledger.tip_lo": "Cheapest {cargo} you have seen", "ledger.tip_hi": "Dearest {cargo} you have seen",
    "dealer.title": "Dealer's margin", "dealer.margin": "{margin}%", "stat.standing": "Standing", "stat.standing_tip": "Your standing in {port}: {tier}", "stat.standing_hostile": "Hostile", "stat.standing_cool": "Cool", "stat.standing_neutral": "Neutral", "stat.standing_warm": "Warm", "stat.standing_favoured": "Favoured",
    "dealer.standing": "Standing", "dealer.standing_tip": "Your standing here: {rep} of 100",
    "clearance.title": "Outward clearance", "clearance.authority": "Port authority of {port}", "clearance.harbour": "A · Harbour account", "clearance.subtotal": "Harbour dues subtotal", "clearance.total": "Amount payable", "clearance.after": "Silver after filing: {amount}", "clearance.short": "Short by {amount}; the balance becomes debt.", "clearance.anchor": "Filed when the fleet sails · nothing is due while at anchor", "clearance.slip": "Night departure selected · caught: {caught}",
    "market.paid": "paid {paid} avg", "market.paid_tip": "You paid {paid} a unit on average for the {good} you hold, aboard and ashore. Selling one here now brings {price}.",
    "market.pl_up": "+{profit}", "market.pl_down": "−{profit}",
    "market.pl_tip_up": "Profit of {profit} on this sale, against the {paid} a unit you paid on average.",
    "market.pl_tip_down": "Loss of {profit} on this sale, against the {paid} a unit you paid on average.",
    "dealer.pay": "You pay", "dealer.get": "You get", "dealer.units": "{n} units", "dealer.cut": "Dealer's cut",
    "dealer.cut_sub": "{margin}% margin", "sail.risk_title": "Routes ranked by voyage risk",
    "sail.easiest": "Easiest",
    "sail.hardest": "Hardest", "sail.route": "Route", "sail.weather": "Weather", "sail.distance": "Distance",
    "sail.intel": "Intel", "sail.standing": "Standing",
    "dues.title": "Harbour dues", "dues.due": "Due when you sail", "dues.paid_on_leave": "Paid as you leave",
    "dues.after": "Silver {from} → {to} after dues", "dues.short": "You are {owed} short. It will go on your debt.",
    "dues.stay": "Nothing is due if you stay at anchor.", "dues.choice": "Leaving port", "dues.pay": "Pay the Mayor {total}",
    "dues.slip": "Slip out at night",
    "dues.slip_note": "{pct}% chance the harbour watch catches you. Get away and you pay nothing; get caught and you pay {caught} and lose {rep} standing in {port}.",
    "dues.slipping": "Slipping out at night: nothing to pay if you get away, {caught} if you are caught.", "dues.level": "{port} rates ×{level}",
    "dues.level_lo": "{port} rates ×{level}, cheaper than most", "dues.level_hi": "{port} rates ×{level}, dearer than most", "dues.restart": "The Mayor's bill shows once the Crimson Ledger server is restarted.",
    "dues.anchorage": "Anchorage", "dues.anchorage_sub": "{n} ship(s) × {rate}",
    "dues.tonnage": "Tonnage", "dues.tonnage_sub": "{n} hold × {rate} per 100",
    "dues.repair": "Shipyard levy", "dues.repair_sub": "{rate} of {n} repairs",
    "dues.yard": "Shipwright and chandler", "dues.yard_sub": "{rate} of {n} ships and guns",
    "dues.bank": "Counting-house fee", "dues.bank_sub": "{rate} of {n} banked",
    "dues.loan": "Moneylender's stamp", "dues.loan_sub": "{rate} of {n} borrowed or repaid",
    "dues.wh": "Wharfage", "dues.wh_sub": "{n} units × {rate} per 100",
    "dues.standing_off": "Mayor's courtesy", "dues.standing_off_sub": "standing {n}: {rate} off",
    "dues.standing_on": "Mayor's displeasure", "dues.standing_on_sub": "standing {n}: {rate} extra",
    "port.owe.grp_lender": "Moneylender", "port.owe.grp_collect": "Debt collectors", "port.owe.grp_port": "Leaving port", "port.owe.grp_bank": "Counting-house" });
const womanPick = {};
/* Cast members who are port women: while the Mayor or the Tax collector speaks, the stage shows the
   picture for the port the house is in (deck.js Stage asks for it), not one portrait for every port. */
const PORT_SPEAKERS = { mayor: "mayor", taxlady: "taxlady" };
/* While the Port Authority's desk is open the officer is already shown in the popup: when she speaks,
   the stage keeps the port pictures and only her words go on the plate (deck.js Stage.talk). */
function stageKeepsPort(cid) {
  return /^officer_|^taxlady$/.test(cid || "") && Customs.isOpen();
}
function stageFace(cid) {
  // The Port Authority officers (cast keys officer_<port>) are each port's tax lady too.
  const role = PORT_SPEAKERS[cid] || (/^officer_/.test(cid || "") ? "taxlady" : "");
  return role && S && S.me ? stageWomanHtml(S.me.port, role) : "";
}

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
    `<td><i class="chip" style="background:${COLORS[p.color % 8]}"></i><span class="hname">${esc(p.firm)}</span><br><span class="muted">${esc(p.name)}</span> <span class="rankname">${esc(p.rank)}</span></td>` +
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
  // The debt clock: months until the moneylender's collectors next call, if nothing changes.
  const due = (me.collectors || {}).calls_in;
  const stats = [["stat.silver", money(p.cash), "silver" + dir(p.cash, me.cash)], ["stat.bank", money(me.bank)],
                 ["stat.debt", money(me.debt), (me.debt > 0 ? "bad" : "") + (due ? " due" : "") + (due === 1 ? " due-now" : ""), due ? ten("stat.debt_due", due) : ""],
                 ["stat.worth", money(me.worth), "worth"], ["stat.hold", p.used + " / " + me.capacity, dir(p.used, me.used).trim()], ["stat.guns", guns()]]
    .map(s => `<div class="plq ${s[2] || ""}"><span>${te(s[0])}</span><b>${s[1]}</b>${s[3] ? `<small>${s[3]}</small>` : ""}</div>`).join("") +
    standingPlaque((me.rep || {})[me.port]);
  return `<div class="dk-house"><i class="chip" style="background:${COLORS[me.color % 8]}"></i>
      <div><b>${esc(me.firm)}</b><span class="rankname">${esc(me.rank)}</span>
      <small>${te("bar.where", { port: esc(portName(me.port)), date: esc(S.date), months: S.turns_left })}</small></div></div>
    ${portPlate()}
    <div class="dk-stats">${stats}</div>`;
}

/* The seventh plaque: the house's standing in this port as a heat icon, no number. Five fat rising
   bars running red (hostile) to green (favoured), lit up to the standing's tier. No shield. The tier's
   name is in the tooltip and for screen readers. */
const STANDING_HEAT = [4, 26, 44, 78, 122];
function standingPlaque(rep) {
  const r = Math.max(0, Math.min(100, Math.round(rep || 0)));
  const tier = Math.min(4, Math.floor(r / 20));
  const word = te("stat.standing_" + ["hostile", "cool", "neutral", "warm", "favoured"][tier]);
  const tip = te("stat.standing_tip", { port: esc(portName(S.me.port)), tier: word });
  const heat = i => `hsl(${STANDING_HEAT[i]} 72% ${i === 2 ? 50 : 46}%)`;
  const bars = STANDING_HEAT.map((_, i) => {
    const h = 6 + i * 3;
    return `<rect x="${(i * 10.4).toFixed(1)}" y="${18 - h}" width="8.6" height="${h}" rx="1.6" ` +
      (i <= tier ? `fill="${heat(i)}"` : `class="off"`) + `/>`;
  }).join("");
  const svg = `<svg class="plq-heat" viewBox="0 0 50 18" role="img" aria-label="${tip}" focusable="false">${bars}</svg>`;
  return `<div class="plq standing tier-${tier}" title="${tip}" style="--heat:${heat(tier)}"><span>${te("stat.standing")}</span><b>${svg}</b></div>`;
}

/* The port the fleet lies in, between the house name and the plaques: "Welcome to" over the port's
   name, with where the fleet came from beside it. Replaces the old banner card on Port > Arrival. */
function portPlate() {
  const me = S.me, last = (me.books || {}).last;
  const key = !last ? "" : last.wrecked ? "wrecked" : last.sailed ? "sailed" : "stayed";
  const came = key ? `<small>${te("bar.came." + key, { from: esc(portName(last.from)) })}</small>` : "";
  return `<div class="dk-port"><span>${te("bar.welcome")}</span><b>${esc(portName(me.port))}</b>${came}</div>`;
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
  // A fight at sea comes before everything: the log and the Port Authority wait until it is over (battle.js).
  const fighting = typeof Battle !== "undefined" && Battle.busy();
  const report = !fighting && ui.seenTurn !== S.turn && me.log.length ? logModal() : "";
  if (!fighting && ui.seenTurn !== S.turn && !me.log.length) ui.seenTurn = S.turn;

  const top = topHtml();
  const nav = ["port", "market", "ledger", "fleet", "chart"].map(k =>
    `<button type="button" class="${!ui.tally && ui.tab === k ? "on" : ""}${tabFaceUrl(k) ? " face" : ""}" data-act="tab" data-tab="${k}" aria-label="${te("tab." + k)}">` +
    `${tabFace(k)}<span>${te("tab." + k)}</span></button>`).join("") +
    `<button type="button" class="dk-tally${ui.tally ? " on" : ""}${tabFaceUrl("tally") ? " face" : ""}" data-act="tally" aria-pressed="${ui.tally}" aria-label="${te("st.open_hint")}" title="${te("st.open_hint")}">` +
    `${tabFace("tally")}<span>${te("st.open")}</span></button>` +
    `<i class="dk-gap"></i>` + meButton();
  const pane = { market: marketTab, port: portTab, fleet: fleetTab, chart: chartTab, ledger: ledgerTab }[ui.tab]();
  // The Mayor's side column is one outward-clearance document: harbour charges and the cargo declaration.
  // On the Port tab the race standings sit in the side column under the port art.
  const side = ui.tab === "market" ? dealerCard() : ui.tab === "chart" ? clearanceLedger()
    : ui.tab === "port" ? `<section class="card pt-race pt-race-side"><h2>${te("port.race.title")}</h2>${portRace()}</section>` : "";
  // The Port Authority's desk comes first in a new port (after the month's log is read).
  return { top, nav, pane, side, over: fighting ? "" : report || Customs.html() };
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
  const port = S.me.port;
  const art = Media.html("port", port, "arrival", "cl-art-media", "", { strict: true, video: true })
    || Media.html("port", port, "banner", "cl-art-media", ((D.graphics || {}).ports || {})[port], { strict: true });
  const plan = (S.voice && S.voice.log) || [];
  const entries = S.me.log.map((line, i) => {
    const reader = plan[i] && plan[i].c;
    const who = reader && (VS.cast || {})[reader];
    const face = who && Media.html("persona", reader, "portrait", "cl-face", who.portrait, { strict: true, slot: "captains-log" });
    return `<div class="cl-entry${face ? " has-face" : ""}" data-voice-tag="log:${S.turn}:${i}">
      ${face ? `<span class="cl-portrait">${face}</span>` : ""}
      <div><div class="cl-reader"><span><i aria-hidden="true">${DECK_ICONS.speech_on}</i>${te("log.reading")}</span>${who ? `<b>${esc(who.name)}</b>` : ""}</div>
      <p>${esc(line)}</p></div></div>`;
  }).join("");
  return `<div class="veil cl-veil"><section class="modal captains-log${art ? " has-art" : ""}" role="dialog" aria-labelledby="cl-title cl-date">
    ${art ? `<div class="cl-art" aria-hidden="true">${art}</div>` : ""}
    <div class="cl-scroll"><div class="cl-page">
      <header><p id="cl-title">${te("log.eyebrow")}</p><h2 id="cl-date">${esc(S.date)}</h2><p>${esc(portName(port))}</p></header>
      <div class="cl-entries">${entries}</div>
    </div></div>
    <footer>${btn(te("log.ashore") + ' <span aria-hidden="true">&rarr;</span>', "seen", "", "primary")}</footer>
  </section></div>`;
}

/* --------------------------------------------------------------- market -- */
/* One fat drag bar per cargo. The bar is how much of it the house will have aboard: it starts at what
   is aboard now (the brass tick), dragging right buys, dragging left sells. The single button beside
   it turns into "Buy n" or "Sell n" with the price. Dragging updates the row in place and the pane
   is not redrawn until the finger lifts, so the bar never jumps out from under it. */
function tradeOf(g) {
  const have = S.me.cargo[g] || 0, max = have + maxBuy(g);
  const raw = parseInt(val("t_" + g), 10);
  const sealed = Math.min(have, (S.me.bond || {})[g] || 0);      // sealed in bond at the Port Authority: not for sale here
  const at = isNaN(raw) ? have : Math.max(sealed, Math.min(max, raw));
  const d = at - have;
  return { have, max, at, d, sealed, qty: Math.abs(d), side: d > 0 ? "buy" : d < 0 ? "sell" : "" };
}

function barStyle(tr) {
  // Positions follow the thumb's centre, which travels from half a thumb in to half a thumb short.
  const at = v => `calc(var(--tw) / 2 + (100% - var(--tw)) * ${tr.max ? (v / tr.max).toFixed(4) : 0})`;
  const h = at(tr.have), lo = at(Math.min(tr.have, tr.at)), hi = at(Math.max(tr.have, tr.at));
  const tick = `linear-gradient(90deg,transparent calc(${h} - 2px),var(--bar-tick) calc(${h} - 2px) calc(${h} + 2px),transparent calc(${h} + 2px))`;
  // The sealed-in-bond share is hatched: it is aboard but cannot be sold in this port.
  const sl = tr.sealed ? at(tr.sealed) : null;
  const seal = sl ? `repeating-linear-gradient(135deg,rgba(0,0,0,.45) 0 4px,transparent 4px 8px) 0 0/${sl} 100% no-repeat,` : "";
  const fill = tr.side === "buy"
    ? `linear-gradient(90deg,var(--bar-held) 0 ${lo},var(--bar-buy) ${lo} ${hi},var(--bar-empty) ${hi} 100%)`
    : tr.side === "sell"
      ? `linear-gradient(90deg,var(--bar-held) 0 ${lo},var(--bar-sell) ${lo} ${hi},var(--bar-empty) ${hi} 100%)`
      : `linear-gradient(90deg,var(--bar-held) 0 ${h},var(--bar-empty) ${h} 100%)`;
  return `background:${seal}${tick},${fill}`;
}

function tradeButton(g, tr) {
  // The button and, to its right, its own profit/loss slot. The slot is always there (empty unless a
  // sale is lined up) so the drag bar keeps the same width and never jumps while dragging.
  if (!tr.side) return `<div class="mk-act"><button type="button" class="mk-go" data-act="trade" data-good="${g}" disabled>
    <b>${tr.max ? te("market.drag") : te("market.no_room")}</b></button><span class="mk-pl-slot"></span></div>`;
  const total = quote(g, tr.qty, tr.side), pl = tr.side === "sell" ? profitOf(g, tr.qty, total) : null;
  const tip = pl === null ? "" : ` title="${te(pl >= 0 ? "market.pl_tip_up" : "market.pl_tip_down", { profit: money(Math.abs(pl)), paid: money(paidFor(g)) })}"`;
  const plTag = pl === null ? "" : `<em class="mk-pl ${pl >= 0 ? "up" : "down"}"${tip}>${te(pl >= 0 ? "market.pl_up" : "market.pl_down", { profit: money(Math.abs(pl)) })}</em>`;
  return `<div class="mk-act${pl === null ? "" : " has-pl"}"><button type="button" class="mk-go ${tr.side}" data-act="trade" data-good="${g}"${tip}>
    <b>${te(tr.side === "buy" ? "btn.buy" : "btn.sell")} ${tr.qty.toLocaleString()}</b>
    <small>${money(total)}</small></button><span class="mk-pl-slot">${plTag}</span></div>`;
}

/* What the house paid for a cargo on average (engine p["basis"], hold and warehouse together), or
   null when the server has no record. Profit on a sale is the silver it brings less that average
   times the units, the same sum the Tax collector uses. Unknown cost shows nothing. */
function paidFor(g) {
  const b = S.me.basis && S.me.basis[g];
  return b > 0 ? b : null;
}
function profitOf(g, qty, total) {
  const paid = paidFor(g);
  return paid === null ? null : Math.round(total - paid * qty);
}

/* "paid 412 avg" under the price, jade when one unit sold here now beats it, oxblood when it does not. */
function paidHtml(g) {
  const paid = paidFor(g), have = (S.me.cargo[g] || 0) + ((S.me.wh || {})[g] || 0);
  if (paid === null || !have) return "";
  const one = quote(g, 1, "sell");
  return `<span class="mk-paid ${one >= paid ? "up" : "down"}" title="${te("market.paid_tip", { paid: money(paid), good: esc(D.goods[g].name), price: money(one) })}">${te("market.paid", { paid: money(paid) })}</span>`;
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
    <td class="n mk-num"><b class="mk-price">${money(me.prices[g])}</b><span class="mk-have">${haveHtml(tr)}</span>${tr.sealed ? `<small class="mk-sealed">${te("market.sealed", { n: tr.sealed.toLocaleString() })}</small>` : ""}${paidHtml(g)}</td>
    <td class="mk-bar"><input type="range" class="mk-range" id="in_t_${g}" data-k="t_${g}" data-good="${g}" min="0" max="${tr.max}" step="1"
      value="${tr.at}" style="${barStyle(tr)}" ${tr.max && !me.ready ? "" : "disabled"} aria-label="${esc(good.name)}"${tr.sealed ? ` title="${te("market.sealed_block", { n: tr.sealed.toLocaleString(), good: good.name, port: portName(me.port) })}"` : ""}></td>
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

/* One compact outward-clearance form under the Mayor: the harbour schedule and what leaving will cost. */
function clearanceLedger() {
  const me = S.me, bill = me && me.dues;
  if (!me) return "";
  if (!bill) return `<section class="cl-card"><header class="cl-head"><span>${te("clearance.authority", { port: esc(portName(me.port)) })}</span>
    <h3>${te("clearance.title")}</h3></header><p class="cl-note">${te("dues.restart")}</p></section>`;
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
    standing: ln => te(ln.amount < 0 ? "dues.standing_off_sub" : "dues.standing_on_sub", { n: ln.basis, rate: share(ln.rate) }),
  };
  const label = ln => ln.key === "standing" ? te(ln.amount < 0 ? "dues.standing_off" : "dues.standing_on") : te("dues." + ln.key);
  const amt = ln => ln.amount < 0 ? "−" + money(-ln.amount) : money(ln.amount);
  const cls = ln => ln.key === "standing" ? (ln.amount < 0 ? " credit" : " surcharge") : "";
  const rows = bill.lines.map(ln => `<div class="cl-row${cls(ln)}"><span><b>${label(ln)}</b><small>${subs[ln.key] ? subs[ln.key](ln) : ""}</small></span><strong>${amt(ln)}</strong></div>`).join("");
  const level = bill.level == null ? 1 : bill.level;
  const levelKey = level < 0.95 ? "dues.level_lo" : level > 1.05 ? "dues.level_hi" : "dues.level";
  const levelLine = `<span class="cl-rate ${level < 0.95 ? "credit" : level > 1.05 ? "surcharge" : ""}">${te(levelKey, { port: esc(portName(me.port)), level: +level.toFixed(2) })}</span>`;
  const total = bill.total, after = me.cash - total, owed = Math.max(0, -after);
  const slipping = me.ready ? !!me.slip : !!ui.slip;
  const caughtCost = money(Math.ceil(bill.total * ((D.dues_rules || {}).slip_mult || 2)));
  // Cargo is declared to the Port Authority on arrival (customs.js), not on leaving.
  const status = slipping && bill.total ? te("clearance.slip", { caught: caughtCost }) : "";
  return `<section class="cl-card${slipping && bill.total ? " slipping" : ""}">
    <header class="cl-head"><span>${te("clearance.authority", { port: esc(portName(me.port)) })}</span><h3>${te("clearance.title")}</h3>
      <div class="cl-pay"><small>${te("clearance.total")}</small><b data-cl="total">${money(total)}</b></div></header>
    <div class="cl-meta"><span>${te(me.ready && me.dest ? "dues.paid_on_leave" : "dues.due")}</span>${levelLine}</div>
    <div class="cl-section"><h4>${te("clearance.harbour")}</h4>${rows}
      <div class="cl-row subtotal"><span>${te("clearance.subtotal")}</span><strong>${money(bill.total)}</strong></div></div>
    <footer class="cl-foot"><p class="cl-status" data-cl="status">${status}</p>
      <p><b data-cl="after">${te("clearance.after", { amount: money(Math.max(0, after)) })}</b><em data-cl="short">${owed ? te("clearance.short", { amount: money(owed) }) : ""}</em></p>
      <small>${te("clearance.anchor")}</small></footer></section>`;
}

/* ----------------------------------------------------------------- port -- */
/* The Port tab opens with the house's news board: standings, port news and this month's log.
   They show in every port; the bank, loans, warehouse and agent below only at home. */
/* ----------------------------------------------------------------- port -- */
/* The Port screen: where a house lands in a new port. Sub-tabs (the headline figures live in the
   masthead, so the screen has no figure strip of its own): Arrival (what happened,
   what to do here, the port at a glance), Accounts (profit and loss, debts and dues), Log (the
   captain's log, this voyage and earlier ones), News (from the ports, bans, next month's weather)
   and, in Hong Kong only, Services (bank, moneylender, warehouse, protection).
   The figures come from the account book the server keeps (me.books, engine.py _book). */
const PL_GROUPS = [
  ["trade", ["sales", "pa_sold", "cost"]],
  ["port", ["dues", "gift", "repairs", "protection", "pa_tax", "pa_fine", "pa_bribe", "pa_premium"]],
  ["money", ["interest", "bank_interest"]],
  ["perils", ["booty", "parley", "plundered", "seized", "fines", "overboard", "ships_lost", "wreck", "wreck_cargo", "robbed"]],
];
const plTotal = lines => Object.values(lines || {}).reduce((a, b) => a + b, 0);
const signed = n => (n > 0 ? "+" : "") + money(n);
const tone = n => n > 0.5 ? "up" : n < -0.5 ? "down" : "";
/* "1 month" / "3 months": a key with "_1" after it is used for exactly one. */
const ten = (key, n, vars) => te(n === 1 && T[key + "_1"] != null ? key + "_1" : key, Object.assign({ n, months: n }, vars || {}));

function portViews() {
  return ["arrival", "accounts", "log", "news"].concat(S.me.port === myHome() ? ["services"] : []);
}

function portTab() {
  // A new month always opens on Arrival.
  if (ui.portTurn !== S.turn) { ui.portTurn = S.turn; ui.portView = "arrival"; ui.mayor = false; }
  const views = portViews();
  if (!views.includes(ui.portView)) ui.portView = "arrival";
  const seg = `<nav class="pt-tabs" role="tablist" aria-label="${te("port.views")}">${views.map(v =>
    `<button type="button" role="tab" class="pt-tab${ui.portView === v ? " on" : ""}" data-act="port_view" data-v="${v}" aria-selected="${ui.portView === v}"><span>${te("port.view." + v)}</span>${portBadge(v)}</button>`).join("")}</nav>`;
  const body = { arrival: portArrival, accounts: portAccounts, log: portLog, news: portNews, services: portServices }[ui.portView]();
  return `<div class="pt">${seg}<div class="pt-view pt-${ui.portView}">${body}</div></div>`;
}

/* A small count on a sub-tab: things needing attention on Arrival, lines in this voyage's log, news items. */
function portBadge(v) {
  const me = S.me;
  let n = 0, cls = "";
  if (v === "arrival") {
    n = (me.debt > 0 ? 1 : 0) + (me.protect <= D.renew_at ? 1 : 0) + ((me.ships || []).some(x => x.repair) ? 1 : 0)
      + (((S.bans || {})[me.port] || []).some(g => me.cargo[g]) ? 1 : 0);
    cls = "warn";
  } else if (v === "log") n = (me.log || []).length;
  else if (v === "news") n = (S.news || []).length;
  return n ? `<em class="pt-badge ${cls}" aria-hidden="true">${n}</em>` : "";
}

/* ---- Arrival */
function portArrival() {
  // The "Welcome to (port)" banner now lives in the header (portPlate); the month's result is under
  // Accounts and the full voyage log is under the Log sub-tab.
  const me = S.me;
  // Call on the Mayor swaps At a Glance for the Mayor's Parlour, and the stage shows her (deckArt).
  const right = mayorOpen() ? mayorParlour()
    : `<section class="card pt-glance"><h2>${te("port.glance.title", { port: esc(portName(me.port)) })}</h2>${portGlance()}</section>`;
  return `<section class="card pt-todo"><h2>${te("port.todo.title")}</h2>${portTodo()}</section>${right}`;
}

/* ---- The Mayor's Parlour: once per visit, a purse of silver for standing in this port.
   Standing gained = cap x (1 - e^(-gift / appetite)) x headroom (engine.py Game.gift_gain, mirrored
   here so the slider shows the result as it moves). me.gift carries the rule's numbers. */
const mayorOpen = () => !!(ui.mayor && ui.tab === "port" && ui.portView === "arrival" && S.me.gift && S.me.gift.enabled);
function mayorGain(gv, rep, amount) {
  const soft = Math.min(99, Math.max(0, gv.soft_from));
  const head = rep <= soft ? 1 : Math.max(0, (100 - rep) / (100 - soft));
  return gv.cap * (1 - Math.exp(-Math.max(0, amount) / gv.appetite)) * head;
}
function mayorTier(gv, gain) {
  const [gracious, warm, delighted] = gv.tiers;
  return gain >= delighted ? "delighted" : gain >= warm ? "warm" : gain >= gracious ? "gracious" : "cool";
}
/* What a standing buys in this port, as the Parlour's table shows it. */
function mayorPerks(gv, rep) {
  const r = gv.rules, d = (50 - rep) / 50;
  const dues = rep < 50 ? "+" + Math.round(r.rep_discount * d * 100) + "%" : rep > 50 ? "−" + Math.round(-r.rep_discount * d * 100) + "%" : t("port.mayor.dues_full");
  const odds = k => "×" + Math.max(0.1, 1 + k * d).toFixed(2);
  return { dues, search: odds(r.rep_audit), buyout: odds(r.rep_buy), margin: pct(Math.max(0, r.spread_base - r.spread_swing * (rep - 50) / 50), 1) + "%" };
}
function mayorAmount(gv) {
  const raw = +(ui.vals.gift || 0) || Math.min(gv.max, Math.round(gv.appetite / gv.step) * gv.step);
  return Math.max(gv.min, Math.min(gv.max, raw));
}
function mayorNumbers(gv, amount) {
  const s0 = Math.round(gv.rep), gain = mayorGain(gv, gv.rep, amount);
  const s1 = Math.min(100, Math.round(gv.rep + gain)), add = s1 - s0;
  const more = Math.min(gv.max, amount + 500);
  const next = more > amount ? mayorGain(gv, gv.rep, more) - gain : 0;
  return { s0, s1, add, tier: mayorTier(gv, gain), next, after: S.me.cash - amount, now: mayorPerks(gv, gv.rep), then: mayorPerks(gv, gv.rep + gain) };
}
function mayorGauge(s0, s1, add, cls) {
  return `<div class="mp-gauge ${cls || ""}">
    <div class="mp-gauge-head"><span class="mp-lbl">${te("port.mayor.standing", { port: portName(S.me.port) })}</span>
      <b class="mp-fig" data-mp="s0">${s0}</b><span aria-hidden="true">→</span><b class="mp-fig up" data-mp="s1">${s1}</b>
      <em class="mp-plus" data-mp="add">+${add}</em></div>
    <div class="mp-bar" role="img" aria-label="${s0} → ${s1}" data-mp="bar" style="--from:${s0}%;--to:${s1}%">
      <i class="mp-then"></i><i class="mp-now"></i><i class="mp-tick"></i></div>
    <div class="mp-scale"><span>${te("port.mayor.scale_lo")}</span><span>${te("port.mayor.scale_mid")}</span><span>${te("port.mayor.scale_hi")}</span></div>
  </div>`;
}
function mayorParlour() {
  const me = S.me, gv = me.gift, port = portName(me.port);
  const head = (chip) => `<header class="pt-cardhead"><h2>${te("port.mayor.title")}</h2><span class="pt-chip">${chip}</span></header>`;
  if (gv.given) {
    const th_ = gv.thanks;
    let words = "";
    if (th_) {
      // Her own words: the confirmation without its receipt (everything after "+{gain}.").
      const tpl = (th_.key && T[th_.key]) || T["m.gift." + th_.tier] || "";
      const at = tpl.indexOf("{gain}.");
      const vars = { port: portName(me.port), amount: money(th_.amount), gain: Math.round(th_.gain) };
      words = esc((at >= 0 ? tpl.slice(at + 7).trim() : tpl).replace(/\{(\w+)\}/g, (m, k) => vars[k] != null ? vars[k] : (TOK[k] != null ? TOK[k] : m)));
    }
    const row = (label, value, cls) => `<tr><td>${label}</td><td class="n"><span class="pt-amt ${cls || ""}">${value}</span></td></tr>`;
    return `<section class="card pt-mayor">${head(te("port.mayor.called"))}
      ${th_ ? mayorGauge(th_.from, th_.to, th_.to - th_.from, "grown") : ""}
      ${th_ ? `<div class="mp-thanks"><span class="mp-lbl">${te("port.mayor.thanks")} · ${te("port.mayor.tier." + th_.tier)}</span><p>“${words}”</p></div>
      <table class="pt-table">${row(te("port.mayor.paid"), "−" + money(th_.amount), "down")}
        ${row(te("port.mayor.standing", { port }), th_.from + " → " + th_.to, "up")}
        ${row(te("port.mayor.dues"), esc(mayorPerks(gv, gv.rep).dues))}
        ${row(te("port.mayor.after"), money(me.cash))}</table>` : ""}
      <div class="pt-actions mp-actions"><span class="muted">${te("port.mayor.closed", { port })}</span>
        ${btn(te("port.mayor.back") + ' <span aria-hidden="true">&rsaquo;</span>', "mayor_close", "", "pt-go")}</div></section>`;
  }
  const greet = `<p class="mp-greet">“${te(gv.greet && T[gv.greet] ? gv.greet : "port.mayor.greet", { port })}”</p>`;
  const close = btn(te("port.mayor.no"), "mayor_close", "", "pt-go");
  if (gv.max < gv.min) {
    return `<section class="card pt-mayor">${head(te("port.mayor.once"))}${greet}
      <p class="mp-note">${te("port.mayor.poor", { amount: money(gv.min) })}</p><div class="pt-actions">${close}</div></section>`;
  }
  if (mayorGain(gv, gv.rep, gv.max) < 0.5) {
    return `<section class="card pt-mayor">${head(te("port.mayor.once"))}${greet}
      <p class="mp-note">${te("port.mayor.full")}</p><div class="pt-actions">${close}</div></section>`;
  }
  const amount = mayorAmount(gv), n = mayorNumbers(gv, amount), locked = me.ready;
  const perk = (label, k) => `<tr><td>${te(label)}</td><td class="n" data-mp="now_${k}">${esc(n.now[k])}</td><td class="n up" data-mp="then_${k}">${esc(n.then[k])}</td></tr>`;
  return `<section class="card pt-mayor">${head(te("port.mayor.once"))}${greet}
    ${mayorGauge(n.s0, n.s1, n.add)}
    <div class="mp-gift">
      <div class="mp-gift-head"><label for="mpGift">${te("port.mayor.gift")}</label><output for="mpGift" class="mp-amount" data-mp="amount">${money(amount)}</output></div>
      <input id="mpGift" type="range" class="mk-range pt-range mp-range" data-k="gift" min="${gv.min}" max="${gv.max}" step="${gv.step}" value="${amount}"
        aria-valuetext="${esc(money(amount))}" ${locked ? "disabled" : ""}>
      <div class="mp-ends"><span>${te("port.mayor.end_lo", { amount: money(gv.min) })}</span><span>${te("port.mayor.end_hi", { amount: money(gv.max) })}</span></div>
    </div>
    <div class="mp-boxes">
      <div class="mp-box"><span class="mp-lbl">${te("port.mayor.after")}</span><b class="mp-fig" data-mp="after">${money(n.after)}</b>
        <small data-mp="next">${n.next >= 0.05 ? te("port.mayor.next", { amount: money(500), gain: n.next.toFixed(1) }) : te("port.mayor.next_none")}</small></div>
      <div class="mp-box"><span class="mp-lbl">${te("port.mayor.take")}</span><b class="mp-tier" data-mp="tier">${te("port.mayor.tier." + n.tier)}</b>
        <small data-mp="hint">${te("port.mayor.hint." + n.tier)}</small></div>
    </div>
    <table class="pt-table mp-perks"><caption>${te("port.mayor.buys")}</caption>
      ${perk("port.mayor.dues", "dues")}${perk("port.mayor.search", "search")}${perk("port.mayor.buyout", "buyout")}${perk("port.mayor.margin", "margin")}</table>
    ${gv.home ? `<p class="mp-note">${te("port.mayor.home")}</p>` : ""}
    <div class="pt-actions mp-actions"><span class="muted">${te("port.mayor.fine")}</span>${close}
      ${btn(te("port.mayor.give", { amount: money(amount) }), "mayor_give", "", "primary mp-give", locked)}</div>
  </section>`;
}
/* While the purse slider moves: update the figures in place (the pane is redrawn once it is let go). */
function mayorLive(range) {
  const gv = S.me.gift, card = range.closest(".pt-mayor");
  if (!gv || !card) return;
  const amount = Math.max(gv.min, Math.min(gv.max, +range.value)), n = mayorNumbers(gv, amount);
  const set = (k, v) => { const el = card.querySelector(`[data-mp="${k}"]`); if (el) el.textContent = v; };
  set("amount", money(amount)); set("s1", n.s1); set("add", "+" + n.add); set("after", money(n.after));
  set("next", n.next >= 0.05 ? t("port.mayor.next", { amount: money(500), gain: n.next.toFixed(1) }) : t("port.mayor.next_none"));
  set("tier", t("port.mayor.tier." + n.tier)); set("hint", t("port.mayor.hint." + n.tier));
  ["dues", "search", "buyout", "margin"].forEach(k => set("then_" + k, n.then[k]));
  const bar = card.querySelector('[data-mp="bar"]');
  if (bar) { bar.style.setProperty("--to", n.s1 + "%"); bar.setAttribute("aria-label", n.s0 + " → " + n.s1); }
  range.setAttribute("aria-valuetext", money(amount));
  const give = card.querySelector(".mp-give");
  if (give) give.textContent = t("port.mayor.give", { amount: money(amount) });
}

/* What is worth doing in this port, most useful first. Each item can jump to the tab that does it. */
function portTodo() {
  const me = S.me, items = [];
  const arrow = ' <span aria-hidden="true">&rsaquo;</span>';
  const go = (tab, label) => btn(label + arrow, "tab", `data-tab="${tab}"`, "pt-go");
  const goView = (v) => btn(te("port.view." + v) + arrow, "port_view", `data-v="${v}"`, "pt-go");
  if (me.ready) items.push(["ok", te(me.dest ? "port.todo.sailing" : "port.todo.staying", { port: esc(portName(me.dest || me.port)) }), go("chart", te("tab.chart"))]);
  // Cargo that sells here for more than it cost.
  const sells = Object.keys(me.cargo || {}).map(g => {
    const q = me.cargo[g] - ((me.bond || {})[g] || 0), paid = paidFor(g);
    return paid === null || q <= 0 ? null : { g, q, gain: quote(g, q, "sell") - paid * q };
  }).filter(x => x && x.gain > 0).sort((a, b) => b.gain - a.gain).slice(0, 2);
  sells.forEach(x => items.push(["up", te("port.todo.sell", { qty: x.q.toLocaleString(), good: D.goods[x.g].name, gain: money(x.gain) }), go("market", te("tab.market"))]));
  const repair = (me.ships || []).reduce((n, s) => n + s.repair, 0);
  if (repair) {
    const low = Math.min(...me.ships.map(s => Math.round(100 * s.hull / D.ships[s.type].hull)));
    items.push(["warn", te(D.ports[me.port].shipyard ? "port.todo.repair_yard" : "port.todo.repair", { hull: low, cost: money(repair) }), go("fleet", te("tab.fleet"))]);
  }
  const storms = Object.keys(S.weather || {}).filter(r => S.weather[r] >= 3);
  if (storms.length) items.push(["warn", te("port.todo.typhoon", { seas: storms.map(r => (D.regions[r] || {}).name || r).join(", ") }), go("chart", te("tab.chart"))]);
  const banned = (S.bans || {})[me.port] || [];
  const aboard = banned.filter(g => me.cargo[g]);
  if (aboard.length) items.push(["warn", te("port.todo.banned", { goods: aboard.map(g => D.goods[g].name).join(", ") }), ""]);
  const home = me.port === myHome();
  if (me.protect <= D.renew_at) items.push(["warn", ten(me.protect > 0 ? "port.todo.protect_low" : "port.todo.protect_none", me.protect),
    home ? goView("services") : ""]);
  if (me.debt > 0) items.push(["down", te(home ? "port.todo.debt_home" : "port.todo.debt", { interest: money(me.debt * D.loan_rate) }),
    goView(home ? "services" : "accounts")]);
  const coll = me.collectors;
  if (coll && coll.calls_in) items.push([coll.calls_in === 1 ? "down" : "warn", ten("port.todo.collectors", coll.calls_in, { amount: money(coll.to_clear) }),
    goView("accounts")]);
  if (!me.used && !me.ready) items.push(["", te("port.todo.empty"), go("market", te("tab.market"))]);
  // The Mayor's Parlour: a brass "!" while she thinks little of the house (standing under 50).
  const gv = me.gift;
  if (gv && gv.enabled && !me.ready) {
    const port = portName(me.port), low = gv.rep < 50 && !gv.given;
    const call = mayorOpen() ? "" : btn(te(gv.given ? "port.todo.mayor_back" : "port.todo.mayor_go") + arrow, "mayor_open", "", "pt-go");
    items.push([gv.given ? "ok" : low ? "warn" : "",
      te(gv.given ? "port.todo.mayor_done" : low ? "port.todo.mayor_low" : "port.todo.mayor", { port, rep: Math.round(gv.rep) }), call]);
  }
  if (!items.length) return `<p class="muted">${te("port.todo.none")}</p>`;
  const icon = { up: "◆", warn: "!", down: "⚖", ok: "⚓", "": "·" };
  return `<ul class="pt-list">${items.map(([k, text, act]) =>
    `<li class="${k || "plain"}"><i aria-hidden="true">${icon[k]}</i><span>${text}</span>${act || "<b></b>"}</li>`).join("")}</ul>`;
}

/* The port at a glance: what is cheap and dear, bans, the dealer's cut, dues, shipyard, the Port Authority, rivals. */
function portGlance() {
  const me = S.me, port = D.ports[me.port], mods = port.mods || {};
  const goods = Object.keys(D.goods).filter(g => mods[g] != null);
  const cheap = goods.filter(g => mods[g] < 1).sort((a, b) => mods[a] - mods[b]).slice(0, 3);
  const dear = goods.filter(g => mods[g] > 1).sort((a, b) => mods[b] - mods[a]).slice(0, 3);
  const chips = (list, cls) => list.length ? list.map(g => `<span class="pt-chip ${cls}">${esc(D.goods[g].name)}</span>`).join("") : `<span class="muted">—</span>`;
  const bans = (S.bans || {})[me.port] || [];
  const rivals = S.players.filter(p => p.port === me.port && p.id !== me.id);
  const rate = Number(port.tax_rate) || 0;
  const row = (label, value) => `<tr><td>${label}</td><td class="n">${value}</td></tr>`;
  return `<table class="pt-table">
    ${row(te("port.glance.cheap"), chips(cheap, "up"))}
    ${row(te("port.glance.dear"), chips(dear, "down"))}
    ${row(te("port.glance.bans"), bans.length ? chips(bans, "down") : te("port.glance.no_bans"))}
    ${row(te("port.glance.cut", { rep: (me.rep || {})[me.port] }), pct(me.spread, 1) + "%")}
    ${row(te("port.glance.dues"), "×" + (me.dues && me.dues.level != null ? me.dues.level : 1))}
    ${row(te("port.glance.authority"), me.home_free && me.port === myHome() ? te("port.glance.home_free") : rate > 0 ? te("port.glance.authority_rate", { rate: pct(rate, 1) }) : te("port.glance.free"))}
    ${row(te("port.glance.yard"), port.shipyard ? te("port.glance.yes") : te("port.glance.no_yard", { yards: esc(D.yards.join(", ")) }))}
    ${row(te("port.glance.rivals"), rivals.length ? rivals.map(p => `<span class="pt-chip"><i class="chip" style="background:${COLORS[p.color % 8]}"></i>${esc(p.firm)}</span>`).join("") : te("port.glance.alone"))}
  </table>`;
}

function portRace() {
  const me = S.me, ranked = S.players.slice().sort((a, b) => b.worth - a.worth);
  const place = ranked.findIndex(p => p.id === me.id) + 1;
  return `<p>${te("port.race.place", { place, of: ranked.length, rank: me.rank, months: S.turns_left })}</p>
    ${standings()}${btn(te("st.open_hint"), "tally", "", "wide ghost")}`;
}

/* ---- Accounts */
function portAccounts() {
  const me = S.me, bk = me.books || {};
  const range = ui.plRange || "voyage";
  const lines = range === "year" ? bk.year : range === "game" ? bk.game : (bk.last || {}).lines;
  const seg = `<div class="pt-seg" role="group" aria-label="${te("port.pl.range")}">${["voyage", "year", "game"].map(r =>
    `<button type="button" data-act="pl_range" data-v="${r}" aria-pressed="${range === r}">${te("port.pl.range_" + r)}</button>`).join("")}</div>`;
  let table;
  if (!lines || !Object.keys(lines).length) {
    table = `<p class="muted">${te(range === "voyage" && !bk.last ? "port.pl.none_yet" : "port.pl.empty")}</p>`;
  } else {
    const rows = PL_GROUPS.map(([grp, keys]) => {
      const here = keys.filter(k => Math.round(lines[k] || 0) !== 0);
      if (!here.length) return "";
      const sub = here.reduce((n, k) => n + lines[k], 0);
      return `<tr class="pt-grp"><td colspan="2">${te("port.pl.grp_" + grp)}</td></tr>` +
        here.map(k => `<tr><td>${te("port.pl." + k)}</td><td class="n ${tone(lines[k])}">${signed(lines[k])}</td></tr>`).join("") +
        `<tr class="pt-sub"><td>${te("port.pl.sub_" + grp)}</td><td class="n ${tone(sub)}">${signed(sub)}</td></tr>`;
    }).join("");
    const total = plTotal(lines);
    table = `<table class="pt-table pt-pl">${rows}<tr class="pt-total"><td>${te("port.pl.total_" + range)}</td><td class="n ${tone(total)}">${signed(total)}</td></tr></table>`;
  }
  const title = range === "voyage" && bk.last
    ? te(bk.last.sailed ? "port.pl.title_voyage" : "port.pl.title_month", { from: esc(portName(bk.last.from)), to: esc(portName(bk.last.to)), date: esc(bk.last.date) })
    : te("port.pl.title");
  return `<section class="card pt-plcard"><header class="pt-cardhead"><h2>${title}</h2>${seg}</header>${table}
      ${portUnrealised()}<p class="muted pt-fine">${te("port.pl.note")}</p></section>
    <section class="card pt-owe"><h2>${te("port.owe.title")}</h2>${portOwe()}</section>`;
}

/* Cargo aboard and in store: what it would fetch here now against what it cost. Not counted until sold. */
function portUnrealised() {
  const me = S.me;
  let worth = 0, paid = 0, n = 0;
  Object.keys(me.cargo || {}).forEach(g => {
    const p = paidFor(g);
    if (p === null) return;
    worth += quote(g, me.cargo[g], "sell");
    paid += p * me.cargo[g];
    n += me.cargo[g];
  });
  if (!n) return "";
  return `<p class="pt-unreal">${th("port.pl.aboard", { n: n.toLocaleString(), worth: `<b>${money(worth)}</b>`, paid: money(paid),
    gain: `<b class="${tone(worth - paid)}">${esc(signed(worth - paid))}</b>` })}</p>`;
}

function portOwe() {
  const me = S.me, r = D.loan_rate, home = me.port === myHome();
  const last = (me.books || {}).last, paid = last ? -(last.lines.interest || 0) : 0;
  const double = r > 0 ? Math.ceil(Math.log(2) / Math.log(1 + r)) : 0;
  const bill = (me.dues || {}).total || 0;
  /* Values: amounts in ledger figures; counts with the number in figures and the unit in general text;
     yes/no states as small coloured pills. */
  const amt = (n, cls) => `<span class="pt-amt ${cls || ""}">${money(n)}</span>`;
  const count = (text, cls) => `<span class="pt-count ${cls || ""}">${String(text).replace(/(\d[\d,.]*)/, "<b>$1</b>")}</span>`;
  const state = (text, cls) => `<span class="pt-chip ${cls || ""}">${text}</span>`;
  const row = (label, value, note, cls) => `<tr class="${cls || ""}"><td>${label}${note ? `<small>${note}</small>` : ""}</td><td class="pt-val">${value}</td></tr>`;
  const group = (title, rows) => rows ? `<tr class="pt-grp"><td colspan="2">${title}</td></tr>${rows}` : "";

  let hero;
  if (me.debt > 0) {
    const stats = [
      `<div class="pt-owe-stat"><span class="pt-owe-lbl">${te("port.owe.next")}</span>${amt(me.debt * r, "down")}</div>`,
      double ? `<div class="pt-owe-stat"><span class="pt-owe-lbl">${te("port.owe.double")}</span>${count(ten("port.owe.months", double), double <= 12 ? "down" : "")}</div>` : "",
      paid > 0.5 ? `<div class="pt-owe-stat"><span class="pt-owe-lbl">${te("port.owe.paid")}</span>${amt(paid, "down")}</div>` : "",
    ].join("");
    hero = `<div class="pt-owe-hero debt">
        <div class="pt-owe-main"><span class="pt-owe-lbl">${te("port.owe.lender")}</span><b>${money(me.debt)}</b><small>${te("port.owe.lender_note", { rate: pct(r, 2) })} · ${te(home ? "port.owe.repay_here" : "port.owe.repay_home")}</small></div>
        <div class="pt-owe-stats">${stats}</div></div>`;
  } else {
    hero = `<div class="pt-owe-hero clear">
        <div class="pt-owe-main"><span class="pt-owe-lbl">${te("port.owe.lender")}</span><b>${te("port.owe.clear")}</b></div>
        ${home ? `<div class="pt-owe-stats"><div class="pt-owe-stat"><span class="pt-owe-lbl">${te("port.owe.room")}</span>${amt(me.loan_room, "up")}</div></div>` : ""}</div>`;
  }

  let lender = "";
  if (me.debt > 0) {
    if (home) lender += row(te("port.owe.room"), amt(me.loan_room));
  }
  let collect = "";
  const c = me.debt > 0 && me.collectors;
  if (c) {
    collect += row(te("port.owe.line"), amt(c.line, c.over ? "down" : ""), ten("port.owe.line_note", c.every, { months: c.grace }));
    collect += c.calls_in
      ? row(`<b>${te("port.owe.call")}</b>`, count(ten("port.owe.call_in", c.calls_in), "down"), te("port.owe.call_note", { rep: c.penalty, amount: money(c.to_clear) }), "warn")
      : row(te("port.owe.call"), state(te("port.owe.call_none"), "up"), te("port.owe.call_none_note"));
  }
  let port = row(te("port.owe.dues", { port: esc(portName(me.port)) }), bill > 0 ? amt(bill) : state(te("port.owe.nothing"), "up"), te("port.owe.dues_note"));
  port += row(te("port.owe.protect"), me.protect > 0 ? count(ten("port.owe.months", me.protect), me.protect <= D.renew_at ? "down" : "up")
    : state(te("port.owe.no_protect"), "down"));
  const bank = me.bank > 0 ? row(te("port.owe.bank"), amt(me.bank, "up"), te("port.owe.bank_note", { rate: pct(D.bank_rate, 2), interest: money(me.bank * D.bank_rate) })) : "";

  return `${hero}<table class="pt-table pt-owetable">${group(te("port.owe.grp_lender"), lender)}${group(te("port.owe.grp_collect"), collect)}${group(te("port.owe.grp_port"), port)}${group(te("port.owe.grp_bank"), bank)}</table>
    ${home ? `<div class="pt-actions">${btn(te("port.owe.to_services") + ' <span aria-hidden="true">&rsaquo;</span>', "port_view", 'data-v="services"', "pt-go")}</div>` : ""}`;
}

/* ---- Log */
function portLog() {
  const me = S.me, bk = me.books || {};
  const lines = list => `<ol class="pt-entries">${list.map(l => `<li>${esc(l)}</li>`).join("")}</ol>`;
  const read = `<button type="button" class="primary pt-read" data-act="relog">${DECK_ICONS.speech_on}<span>${te("port.log.read")}</span></button>`;
  const now = (me.log || []).length ? `<section class="card pt-logcard">
      <header class="pt-cardhead"><h2>${te("port.log.now", { date: esc(bk.last ? bk.last.date : S.date) })}</h2>${read}</header>
      ${lines(me.log)}</section>` : "";
  const older = (bk.logbook || []).map(e => `<section class="card pt-logcard old">
      <header class="pt-loghead"><b>${esc(e.date)}</b><span>${te(e.from === e.to ? "port.log.at" : "port.log.route", { from: esc(portName(e.from)), to: esc(portName(e.to)) })}</span></header>
      ${lines(e.lines || [])}</section>`).join("");
  return now + older || `<section class="card"><p class="muted">${te("ledger.no_log")}</p></section>`;
}

/* ---- News */
function portNews() {
  const news = (S.news || []).map(n => {
    const at = n.indexOf(": ");
    return at > 0 && at < 14 ? `<li><span class="pt-when">${esc(n.slice(0, at))}</span><span>${esc(n.slice(at + 2))}</span></li>` : `<li><span class="pt-when"></span><span>${esc(n)}</span></li>`;
  }).join("");
  const bans = Object.keys(S.bans || {}).map(k => `<tr><td>${esc(portName(k))}</td><td class="n">${(S.bans[k] || []).map(g => `<span class="pt-chip down">${esc(D.goods[g] ? D.goods[g].name : g)}</span>`).join("")}</td></tr>`).join("");
  const here = (D.ports[S.me.port] || {}).region;
  const wx = Object.keys(D.regions || {}).map(r => {
    const lv = Math.max(0, Math.min(3, (S.weather || {})[r] || 0));
    const kind = ["calm", "fair", "squalls", "typhoon"][lv];
    const ports = Object.keys(D.ports).filter(k => D.ports[k].region === r).map(k => esc(D.ports[k].name)).join(" \u00b7 ");
    return `<li class="pt-wxsea wx${lv}${r === here ? " here" : ""}">
      <span class="pt-wxicon">${sailIcon(kind)}</span>
      <div class="pt-wxbody">
        <div class="pt-wxhead"><b>${esc(D.regions[r].name || r)}</b>${r === here ? `<span class="pt-wxhere">\u2693 ${te("port.news.wx_here")}</span>` : ""}</div>
        <strong class="pt-wxcond">${esc(D.weather[lv])}</strong>
        <dl class="pt-wxfacts"><dt>${te("port.news.wx_wind")}</dt><dd>${te("port.news.wx_wind." + lv)}</dd>
          <dt>${te("port.news.wx_sea")}</dt><dd>${te("port.news.wx_sea." + lv)}</dd></dl>
        <p class="pt-wxadvice">${te("port.news.wx_advice." + lv)}</p>
        ${ports ? `<small class="pt-wxports">${ports}</small>` : ""}
      </div></li>`;
  }).join("");
  const worst = Math.max(0, ...Object.keys(D.regions || {}).map(r => (S.weather || {})[r] || 0));
  return `<section class="card pt-newscard"><h2>${te("port.news.title")}</h2><ul class="pt-news-list">${news || `<li class="muted">${te("ledger.no_news")}</li>`}</ul></section>
    <section class="card"><h2>${te("port.news.bans")}</h2>${bans ? `<table class="pt-table">${bans}</table>` : `<p class="muted">${te("port.news.no_bans")}</p>`}</section>
    <section class="card pt-wxcard${worst >= 3 ? " alert" : ""}">
      <header class="pt-wxbanner"><span class="pt-wxeyebrow">${te("port.news.wx_bureau")}</span>
        <h2>${te("port.news.weather")}</h2><span class="pt-wxissued">${te("port.news.wx_issued", { date: esc(S.date) })}</span></header>
      ${worst >= 3 ? `<p class="pt-wxwarning">${sailIcon("typhoon")}<span>${te("port.news.wx_warning")}</span></p>` : ""}
      <ul class="pt-wxlist">${wx}</ul>
      <p class="muted pt-fine">${te("port.news.weather_note", { right: pct(D.forecast_accuracy, 0) })}</p></section>`;
}

/* ---- Home port services */
function serviceTransfer(k, g) {
  const me = S.me;
  let left, right, out, into;
  if (k === "bank") {
    [left, right, out, into] = ["withdraw", "deposit", me.bank, me.cash];
  } else if (k === "loan") {
    [left, right, out, into] = ["repay", "borrow", Math.min(Math.ceil(me.debt), me.cash), me.loan_room];
  } else {
    const whUsed = Object.values(me.wh).reduce((a, b) => a + b, 0);
    [left, right, out, into] = ["load", "store", Math.min(me.wh[g] || 0, me.capacity - me.used),
      Math.min(me.cargo[g] || 0, me.wh_cap - whUsed)];
  }
  const key = g ? "w_" + g : k;
  const have = Math.max(0, Math.floor(out)), max = have + Math.max(0, Math.floor(into));
  const at = Math.max(0, Math.min(max, have + (parseInt(val(key), 10) || 0)));
  const delta = at - have, qty = Math.abs(delta);
  const label = g ? qty.toLocaleString() : money(qty);
  return { key, have, max, at, qty, left, right, label,
    op: delta < 0 ? left : right, side: delta < 0 ? "sell" : delta > 0 ? "buy" : "" };
}

function serviceSlider(k, title, g) {
  const tr = serviceTransfer(k, g), locked = S.me.ready;
  return `<div class="pt-transfer">
    <div class="pt-transfer-scale"><span>${te("btn." + tr.left)}</span><span>${te("btn." + tr.right)}</span></div>
    <input type="range" class="mk-range pt-range" data-k="${tr.key}" data-service="${k}" data-good="${g || ""}"
      min="${-tr.have}" max="${tr.max - tr.have}" step="1" value="${tr.at - tr.have}" style="${barStyle(tr)}"
      aria-label="${title} · ${te("btn." + tr.left)} / ${te("btn." + tr.right)}"
      aria-valuetext="${tr.qty ? te("btn." + tr.op) + " " : ""}${esc(tr.label)}" ${locked || !tr.max ? "disabled" : ""}>
    <div class="pt-transfer-action" data-side="${tr.side}"><output>${esc(tr.label)}</output>
      ${btn(tr.qty ? te("btn." + tr.op) : te("btn." + tr.left) + " / " + te("btn." + tr.right),
        "service_transfer", `data-service="${k}" data-good="${g || ""}"`, "", locked || !tr.qty)}</div>
  </div>`;
}

function serviceDrag(range) {
  const tr = serviceTransfer(range.dataset.service, range.dataset.good);
  const action = range.nextElementSibling;
  const button = action.querySelector("button");
  const label = tr.qty ? t("btn." + tr.op) : t("btn." + tr.left) + " / " + t("btn." + tr.right);
  range.style.cssText = barStyle(tr);
  range.setAttribute("aria-valuetext", tr.qty ? label + " " + tr.label : tr.label);
  action.dataset.side = tr.side;
  action.querySelector("output").textContent = tr.label;
  button.textContent = label;
  button.disabled = S.me.ready || !tr.qty;
}

function serviceCard(art, title, info, body) {
  return `<section class="card pt-service">
    <header class="pt-service-art">
      ${Media.html("service", art, "background", "pt-service-image", "", { strict: true })}
      <h2>${title}</h2>
    </header>
    <div class="pt-service-body"><p>${info}</p>${body}</div>
  </section>`;
}

function portServices() {
  const me = S.me;
  const whUsed = Object.values(me.wh).reduce((a, b) => a + b, 0);
  const goods = Object.keys(D.goods).filter(g => (me.cargo[g] || 0) + (me.wh[g] || 0) > 0);
  const warehouse = goods.map(g => {
    const name = esc(D.goods[g].name);
    return `<div class="pt-service-good"><div class="pt-service-stock"><b>${name}</b>
      <span>${te("col.aboard")} <b>${(me.cargo[g] || 0).toLocaleString()}</b> ·
        ${te("col.in_store")} <b>${(me.wh[g] || 0).toLocaleString()}</b></span></div>
      ${serviceSlider("wh", name, g)}</div>`;
  }).join("") || `<p class="muted">${te("wh.empty")}</p>`;
  const agent = me.protect > D.renew_at ? te("agent.content", { months: me.protect })
    : me.protect > 0 ? te("agent.running_out", { months: me.protect }) : te("agent.none");
  const tribute = me.protect > D.renew_at ? "" : btn(te("agent.pay", { cost: money(me.protect_cost) }),
    "protection", "", "primary", me.ready || me.protect_cost > me.cash);
  return serviceCard("bank", te("bank.title"), te("bank.info", { balance: money(me.bank), rate: pct(D.bank_rate, 2) }),
    serviceSlider("bank", te("bank.title")))
    + serviceCard("lender", te("loan.title"), te("loan.info", { debt: money(me.debt), rate: pct(D.loan_rate, 2), room: money(me.loan_room) }),
      serviceSlider("loan", te("loan.title")))
    + serviceCard("warehouse", te("wh.title"), te("wh.info", { used: whUsed.toLocaleString(), cap: me.wh_cap.toLocaleString(),
      hold_used: me.used, hold: me.capacity }), warehouse)
    + serviceCard("agent", te("agent.title"), agent, tribute);
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
    const isHome = k === myHome();
    return `<button type="button" class="dest sail-card ${dest === k ? "on" : ""}${isHome ? " home" : ""}" data-act="dest" data-port="${k}"
      style="--risk-hue:${Math.round(118 * (1 - heat))};--risk-level:${Math.round(score * 100)}%" aria-label="${esc(p.name)}${isHome ? ", " + te("sail.home_port") : ""}, ${rankLabel}">
      <span class="dest-art">${Media.html("port", k, "banner", "dest-img", D.graphics.ports[k], { slot: "sail:" + k, mode: "fixed" })}
        ${S.crackdown.includes(k) ? `<span class="dest-ban tag bad">${te("tag.ban")}</span>` : ""}
        ${isHome ? `<span class="dest-home">\u2693 ${te("sail.home_port")}</span>` : ""}
        <span class="dest-title"><b>${esc(p.name)}</b><span class="dest-pct">${Math.round(score * 100)}%</span></span></span>
      <span class="dest-data">
        <span class="dest-stat wx${wx}">${sailIcon(weatherKind)}<span><small>${te("sail.weather")}</small><strong>${esc(D.weather[wx])}</strong></span></span>
        <span class="dest-stat">${sailIcon("distance")}<span><small>${te("sail.distance")}</small><strong>${esc(riskLabel(me.port, k))}</strong></span></span>
        <span class="dest-stat">${sailIcon("intel")}<span><small>${te("sail.intel")}</small><strong>${seen}</strong></span></span>
        <span class="dest-stat">${sailIcon("standing")}<span><small>${te("sail.standing")}</small><strong>${Math.round(me.rep[k])}/100</strong></span></span>
      </span></button>`;
  }).join("");
  return `<section class="card">
      <div class="sail-guide sail-guide-top"><span><b>${te("sail.risk_title")}</b></span>
        <span class="heat-key"><small>${te("sail.easiest")}</small><i></i><small>${te("sail.hardest")}</small></span></div>
      <div class="dests">${list}</div>
      <div class="sail-map">${Chart.svg({ data: D, players: S.players, weather: S.weather, crackdown: S.crackdown, here: me.port, dest, clickable: !me.ready, mine: me.id, focusRoute: true })}</div></section>
    <section class="card"><h2>${te("orders.title")}</h2>
      <div class="seg">${btn(te("orders.fight", { guns: guns() }), "orders", 'data-o="fight"', orders === "fight" ? "on" : "")}${btn(te("orders.run"), "orders", 'data-o="run"', orders === "run" ? "on" : "")}</div>
      ${protectionNote()}
      ${slipChoice()}
      <div class="row">${btn(dest ? te("sail.go", { port: portName(dest) }) : te("sail.choose"), "sail", "", "primary wide", !dest || me.ready)}</div>
      <div class="row">${btn(te("sail.stay", { port: portName(me.port) }), "stay", "", "wide", me.ready)}</div>
      ${me.ready ? `<p class="muted">${S.waiting.length ? te("sail.waiting", { names: S.waiting.join(", ") }) : te("sail.weighing")}</p>
      <div class="row">${btn(te("sail.cancel"), "unsail", "", "ghost wide")}</div>` : ""}</section>`;
}

/* Protection under the standing orders. Comfortable cover is one quiet line; none (or nearly out) is a
   warning panel with one button straight to where tribute is paid: the home port services when here,
   otherwise it sets course for home. */
function protectionNote() {
  const me = S.me, home = myHome();
  if (me.protect > D.renew_at) return `<p class="muted">${te("orders.protected", { months: me.protect })}</p>`;
  const low = me.protect > 0;
  const action = me.port === home
    ? btn(te("orders.go_pay", { cost: money(me.protect_cost) }), "to_services", "", "primary or-pay", me.ready)
    : btn(te("orders.sail_home"), "dest", `data-port="${home}"`, "primary or-pay" + (ui.dest === home ? " on" : ""), me.ready);
  return `<div class="or-protect${low ? " low" : ""}" role="alert">
      <span class="or-protect-icon" aria-hidden="true">${low ? "\u23F3" : "\u2620"}</span>
      <div class="or-protect-text"><b>${te(low ? "orders.protect_low_title" : "orders.unprotected_title")}</b>
        <span>${low ? ten("orders.protect_low_body", me.protect) : te("orders.unprotected_body")}
          ${me.port === home ? "" : te("orders.pay_where")}</span></div>
      ${action}</div>`;
}

/* Leaving port: pay the Mayor's bill, or try to slip out at night (engine Game._depart). Only offered
   when there is a bill to dodge. While orders stand, the choice shows as given and cannot change. */
function slipChoice() {
  const me = S.me, bill = me.dues, r = (D.dues_rules || {});
  if (!bill || !bill.total) return "";
  const slip = me.ready ? !!me.slip : !!ui.slip;
  const caught = money(Math.ceil(bill.total * (r.slip_mult || 2)));
  return `<h2 class="du-choice-h">${te("dues.choice")}</h2>
    <div class="seg">${btn(te("dues.pay", { total: money(bill.total) }), "slip", 'data-s="0"', slip ? "" : "on", me.ready)}${btn(te("dues.slip"), "slip", 'data-s="1"', slip ? "on bad" : "", me.ready)}</div>
    ${slip ? `<p class="muted du-slipnote">${te("dues.slip_note", { pct: Math.round((r.slip_caught == null ? .35 : r.slip_caught) * 100), caught, rep: r.slip_rep == null ? 10 : r.slip_rep, port: esc(portName(me.port)) })}</p>` : ""}`;
}

/* --------------------------------------------------------------- ledger -- */
function bookPrice(price) {
  return CUR + price.toLocaleString("en-US", { maximumFractionDigits: 2 });
}

function bookSeen(age) {
  if (age === null) return t("ledger.unknown");
  if (age === 0) return t("ledger.fresh");
  const when = age === 1 ? t("ledger.month") : t("ledger.months", { n: age });
  return age >= 4 ? t("ledger.old", { age: when }) : when;
}

function bookButton(label, action, value, selected, cls = "") {
  return `<button type="button" class="${cls}" data-act="book_${action}" data-value="${esc(value)}" aria-pressed="${selected}">${label}</button>`;
}

function bookCargoTile(g) {
  const art = Media.html("cargo", g, "icon", "book-cargo-art", (D.graphics.goods || {})[g], { mode: "fixed" });
  const aboard = S.me.cargo[g] || 0;
  return `<span class="book-cargo-tile">${art}<span class="book-cargo-name">${esc(D.goods[g].name)}</span>
    <span class="book-cargo-count" aria-hidden="true">${aboard.toLocaleString()}</span><span class="book-cargo-quantity">${te("ledger.aboard", { n: aboard })}</span></span>`;
}

function bookSignals(goods, ports, banner) {
  const me = S.me, g = goods.includes(ui.bookGood) ? ui.bookGood : goods[0];
  const local = me.prices[g], name = D.goods[g].name, home = portName(me.port);
  const rows = ports.map(p => ({ ...p, price: p.prices[g] }));
  const selected = rows.find(p => p.key === ui.bookPort) || rows.find(p => !p.here && Number.isFinite(p.price)) || rows[0];
  const scale = Math.max(1, ...rows.filter(p => Number.isFinite(p.price) && Number.isFinite(local)).map(p => Math.abs(p.price - local)));
  const cargo = goods.map(key => bookButton(bookCargoTile(key), "good", key, key === g, "book-cargo")).join("");
  const chart = rows.map(p => {
    const known = Number.isFinite(p.price), gap = known && Number.isFinite(local) ? p.price - local : 0;
    const width = Math.abs(gap) / scale * 50;
    const bars = `<span class="book-axis${known ? "" : " unknown"}" aria-hidden="true">${known ? `<span class="book-bar ${gap < 0 ? "lower" : "higher"}"
      data-book-port="${esc(p.key)}" style="left:${gap < 0 ? 50 - width : 50}%;width:${width}%;--strength:${(width / 50).toFixed(2)}"></span>` : ""}</span>`;
    const when = p.here ? t("ledger.here") : known ? bookSeen(p.age) : t("ledger.unknown");
    const ban = p.bans.includes(g) ? ` · ${te("ledger.banned")}` : "";
    return bookButton(`<span><b>${esc(portName(p.key))}</b><small class="${p.age >= 4 ? "book-old" : ""}">${esc(when)}${ban}</small></span>${bars}
      <strong>${known ? esc(bookPrice(p.price)) : "—"}</strong>`, "port", p.key, p === selected, `book-port${p.here ? " here" : ""}`);
  }).join("");
  const gap = selected.price - local;
  let detail;
  if (selected.bans.includes(g)) detail = t("ledger.banned");
  else if (!Number.isFinite(selected.price)) detail = t("ledger.unknown");
  else if (selected.here) detail = t("ledger.live") + " · " + t("ledger.unit", { price: bookPrice(local) });
  else if (!Number.isFinite(local)) detail = t("ledger.no_baseline");
  else if (Math.abs(gap) < .005) detail = t("ledger.equal", { port: home });
  else detail = t(gap < 0 ? "ledger.lower" : "ledger.higher", { gap: bookPrice(Math.abs(gap)) });
  return `${banner}
    <div class="book-cargo-grid" role="group" aria-label="${te("ledger.cargo")}">${cargo}</div>
    <div class="book-comparison">
      <div class="book-key">
        <span>${esc(home)} <b>${Number.isFinite(local) ? esc(bookPrice(local)) : "—"}</b></span>
        <span class="book-key-axis"><span>${te("ledger.cheaper")}</span><span>${te("ledger.dearer")}</span></span>
      </div>
      <div class="book-ports" role="group" aria-label="${te("ledger.port")}">${chart}</div>
      <div class="book-detail" aria-live="polite">
        <div><strong>${esc(name)} · ${esc(portName(selected.key))}</strong>
          ${selected.here ? "" : `<small>${esc(riskLabel(me.port, selected.key))} · ${esc(Number.isFinite(selected.price) ? bookSeen(selected.age) : t("ledger.unknown"))}</small>`}</div>
        <p>${esc(detail)}</p>
      </div>
    </div>`;
}

function bookVoyages(goods, ports, banner) {
  const me = S.me, buying = ui.bookMode === "buy";
  const local = Object.fromEntries(goods.filter(g => Number.isFinite(me.prices[g]) && !ports[0].bans.includes(g) &&
    (buying ? me.capacity > me.used && quote(g, 1, "buy") <= me.cash : me.cargo[g] > 0))
    .map(g => [g, quote(g, 1, buying ? "buy" : "sell")]));
  const options = ports.filter(p => !p.here && p.age !== null).flatMap(p => {
    const trades = Object.keys(local).filter(g => !p.bans.includes(g) && Number.isFinite(p.prices[g]) && p.prices[g] - local[g] >= .005)
      .map(g => ({ g, price: p.prices[g], gap: p.prices[g] - local[g] }))
      .sort((a, b) => b.gap - a.gap);
    return trades.length ? [{ ...p, ...trades[0] }] : [];
  }).sort((a, b) => (a.age >= 4) - (b.age >= 4) || b.gap - a.gap || a.age - b.age);
  const route = options.find(p => p.key === ui.bookRoute) || options[0];
  const mode = `<div class="book-controls" role="group" aria-label="${te("ledger.intent")}">
    ${bookButton(te("ledger.buy"), "mode", "buy", buying, "book-toggle")}
    ${bookButton(te("ledger.sell"), "mode", "sell", !buying, "book-toggle")}</div>`;
  if (!route) return `${banner}${mode}<p class="book-detail">${te("ledger.none")}</p>`;
  const summary = p => t("ledger.route_age", { port: portName(p.key), age: bookSeen(p.age), distance: riskLabel(me.port, p.key) });
  const gap = p => t(buying ? "ledger.buy_gap" : "ledger.sell_gap", { gap: bookPrice(p.gap) });
  const list = options.map(p => bookButton(`<strong>${esc(portName(p.key))} · ${esc(D.goods[p.g].name)}</strong>
    <small>${esc(bookSeen(p.age))}</small><span class="book-gain">+${esc(bookPrice(p.gap))} / unit</span>`,
    "route", p.key, p === route, "book-route")).join("");
  return `${banner}${mode}<div class="book-voyage">
    <div class="book-routes" role="group" aria-label="${te("ledger.routes")}">${list}</div>
    <section class="book-detail book-plan">
      <div aria-live="polite"><div class="book-plan-head">${bookCargoTile(route.g)}<div><h3>${te(buying ? "ledger.buy_route" : "ledger.sell_route", { cargo: D.goods[route.g].name, port: portName(route.key) })}</h3>
      <small>${esc(summary(route))}</small></div></div>
      <div class="book-quotes"><div><small>${te(buying ? "ledger.buy_here" : "ledger.sell_here")}</small><b>${esc(bookPrice(local[route.g]))}</b></div>
      <div><small>${te("ledger.seen_bid")}</small><b>${esc(bookPrice(route.price))}</b></div></div>
      <p class="book-gain">+${esc(gap(route))}</p></div>
      ${btn(te("ledger.open_chart"), "book_chart", `data-value="${esc(route.key)}"`, "book-toggle", me.ready)}
    </section></div>`;
}

function bookTable(goods, ports, banner) {
  /* Heat map: each cell is shaded by how far the destination's last posted price sits above (green)
     or below (red) the cost to buy one unit here. Strength grows with the gap, saturating at ±50%,
     so a glance separates really bad, bad, good and really good. The exact gap is in the tooltip. */
  const me = S.me;
  const buyCosts = Object.fromEntries(goods.filter(g => Number.isFinite(me.prices[g]))
    .map(g => [g, quote(g, 1, "buy")]));
  const headings = goods.map(g => `<th scope="col">${bookCargoTile(g)}</th>`).join("");
  const rows = ports.map(p => {
    const seen = p.here ? t("ledger.here") : bookSeen(p.age);
    const cells = goods.map(g => {
      const cost = buyCosts[g], price = p.here ? cost : p.prices[g];
      let label = "", tone = "", heat = 0, pct = "";
      if (p.bans.includes(g)) { label = "banned"; tone = "blocked"; }
      else if (ports[0].bans.includes(g)) { label = "banned_here"; tone = "blocked"; }
      else if (Number.isFinite(price)) {
        if (p.here) { label = "buy_cost"; tone = "base"; }
        else if (!Number.isFinite(cost) || cost <= 0) label = "no_baseline";
        else {
          const r = (price - cost) / cost;
          heat = Math.min(1, Math.abs(r) / .5);
          pct = (r >= 0 ? "+" : "−") + Math.round(Math.abs(r) * 100) + "%";
          label = r > 0 ? "good_buy" : "dont_buy";
          tone = r > 0 ? (r >= .25 ? "good hot" : "good") : (r <= -.25 ? "poor hot" : "poor");
        }
      }
      const tip = [label ? t("ledger." + label) : "", pct].filter(Boolean).join(" · ");
      const style = heat ? ` style="--heat:${(.22 + heat * .78).toFixed(2)}"` : "";
      const mark = tone === "blocked" ? '<i class="book-ban" aria-hidden="true">⊘</i>' : "";
      return `<td class="${tone}"${style}${tip ? ` title="${esc(tip)}" aria-label="${esc((Number.isFinite(price) ? bookPrice(price) + " · " : "") + tip)}"` : ""}>${mark}${
        Number.isFinite(price) ? esc(bookPrice(price)) : `<span aria-label="${te("ledger.unknown")}">—</span>`}</td>`;
    }).join("");
    return `<tr class="${p.here ? "here" : ""}"><th scope="row" title="${esc(seen)}"><b>${p.here ? "⚓ " : ""}${esc(portName(p.key))}</b>
      <small class="${p.age >= 4 ? "book-old" : ""}">${esc(p.here ? t("ledger.now") : p.age === null ? "—" : t("ledger.ago", { n: p.age }))}</small></th>${cells}</tr>`;
  }).join("");
  const legend = `<div class="book-heat-key" id="book-table-note" title="${te("ledger.all_note")}">
      <span class="k poor hot"></span><span>${te("ledger.heat_worst")}</span>
      <span class="k poor"></span><span>${te("ledger.heat_bad")}</span>
      <span class="k good"></span><span>${te("ledger.heat_good")}</span>
      <span class="k good hot"></span><span>${te("ledger.heat_best")}</span>
      <span class="book-heat-info" aria-hidden="true">ⓘ</span></div>`;
  return `${banner}${legend}
    <div class="book-table-scroll" role="region" aria-label="${te("ledger.all")}" aria-describedby="book-table-note" tabindex="0">
      <table class="book-table" aria-label="${te("ledger.all")}">
        <thead><tr><th scope="col">${te("col.port")}</th>${headings}</tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}

function ledgerTab() {
  const me = S.me, goods = Object.keys(D.goods);
  const ports = [me.port, ...Object.keys(D.ports).filter(k => k !== me.port)].map(key => {
    const here = key === me.port, known = me.known[key];
    const bans = S.bans?.[key] || [];
    return { key, here, bans, prices: here ? me.prices : (known?.prices || {}),
      age: here ? 0 : known ? Math.max(0, S.turn - known.turn) : null };
  });
  // No banner: the view switch is a slim segmented bar so the page's height goes to the prices.
  const banner = `<div class="book-seg" role="group" aria-label="${te("ledger.view")}">
      ${bookButton(te("ledger.signals"), "view", "signals", ui.bookView === "signals", "book-toggle")}
      ${bookButton(te("ledger.voyage"), "view", "voyage", ui.bookView === "voyage", "book-toggle")}
      ${bookButton(te("ledger.all"), "view", "all", ui.bookView === "all", "book-toggle")}</div>`;
  const view = { signals: bookSignals, voyage: bookVoyages, all: bookTable }[ui.bookView];
  return `<section class="card book">${view(goods, ports, banner)}</section>
    ${me.host ? `<section class="card host-bar"><h2>${te("host.title")}</h2><div class="host-actions">` +
      btn(te("host.end_month"), "force", "", "slim") + newGameControl() + "</div></section>" : ""}`;
}

function bookSelect(action, value) {
  const motion = !matchMedia("(prefers-reduced-motion: reduce)").matches;
  const prior = new Map();
  if (action === "good" && motion) {
    app.querySelectorAll(".book-bar").forEach(bar => {
      const style = getComputedStyle(bar);
      prior.set(bar.dataset.bookPort, { left: style.left, width: style.width });
    });
  }
  switch (action) {
    case "view": ui.bookView = value; break;
    case "good": ui.bookGood = value; break;
    case "port": ui.bookPort = value; break;
    case "mode": ui.bookMode = value; ui.bookRoute = null; break;
    case "route": ui.bookRoute = value; break;
  }
  render();
  app.querySelectorAll(`[data-act="book_${action}"]`).forEach(button => {
    if (button.dataset.value === value && document.activeElement !== button) button.focus({ preventScroll: true });
  });
  if (prior.size) app.querySelectorAll(".book-bar").forEach(bar => {
    const from = prior.get(bar.dataset.bookPort);
    if (from) bar.animate([from, { left: bar.style.left, width: bar.style.width }], { duration: 440, easing: "ease-out" });
  });
}

/* --------------------------------------------------------------- events -- */
app.addEventListener("input", e => {
  const k = e.target.dataset.k;
  if (!k) return;
  ui.vals[k] = e.target.value;
  if (k.startsWith("t_")) {
    // Cargo sealed in bond can't be sold here: hold the thumb at the seal instead of letting it slide
    // past and snap back, and say why once per drag.
    const g = e.target.dataset.good, sealed = tradeOf(g).sealed;
    if (sealed && +e.target.value < sealed) {
      e.target.value = sealed;
      ui.vals[k] = String(sealed);
      if (ui.sealWarned !== g) {
        ui.sealWarned = g;
        toast(t("market.sealed_block", { n: sealed.toLocaleString(), good: D.goods[g].name, port: portName(S.me.port) }), true);
      }
    }
    ui.drag = true; dragRow(g);
  }
  if (k.startsWith("cx_")) { ui.drag = true; Customs.live(e.target); }
  if (k === "gift") { ui.drag = true; mayorLive(e.target); }
  if (e.target.dataset.service) serviceDrag(e.target);
});
app.addEventListener("pointerdown", e => {
  if (e.target.matches(".pt-range:enabled")) ui.drag = true;
});
/* The pane is held still while a bar is being dragged, then redrawn once it is let go. */
const endDrag = () => { ui.sealWarned = null; if (ui.drag) { ui.drag = false; render(); } };
app.addEventListener("change", e => { if (e.target.classList.contains("mk-range") || e.target.classList.contains("cx-range")) endDrag(); });
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
    case "book_view": case "book_good": case "book_port": case "book_mode": case "book_route":
      return bookSelect(d.act.slice(5), d.value);
    case "book_chart":
      if (!S.me.ready && d.value !== S.me.port && D.ports[d.value]) {
        ui.dest = d.value;
        ui.tab = "chart";
        return render();
      }
      return;
    case "tally": ui.tally = !ui.tally; ui.meOpen = false; return render();
    case "me": ui.meOpen = !ui.meOpen; return render();
    case "speech": Voice.setMuted(!Voice.muted()); return render();
    case "options": ui.meOpen = false; render(); return toast(t("deck.options_soon"));
    // Closing the log opens the Port Authority desk: her greeting starts with it, not at the next update.
    case "seen": ui.seenTurn = S.turn; Voice.drop("log"); render(); return Customs.speak();
    case "relog": ui.seenTurn = null; ui.spokenTurn = null; return render();
    case "port_view": ui.portView = d.v; return render();
    case "to_services": ui.tab = "port"; ui.tally = false; ui.portTurn = S.turn; ui.portView = "services"; return render();
    case "pl_range": ui.plRange = d.v; return render();
    case "mayor_open": ui.mayor = true; ui.vals.gift = ""; return render();
    case "mayor_close": ui.mayor = false; return render();
    case "mayor_give": {
      const gv = S.me.gift;
      if (!gv) return;
      return act("gift", { amount: mayorAmount(gv) });
    }
    case "years": return act("settings", { years: +d.y });
    case "start": return act("start");
    case "trade": {
      const tr = tradeOf(d.good);
      if (!tr.side) return toast(t("e.qty_first"), true);
      if (await act(tr.side, { good: d.good, qty: tr.qty })) { delete ui.vals["t_" + d.good]; render(); }
      return;
    }
    case "service_transfer": {
      const tr = serviceTransfer(d.service, d.good);
      if (!tr.qty || S.me.ready) return;
      const ok = d.service === "wh"
        ? await act("warehouse", { op: tr.op === "load" ? "take" : tr.op, good: d.good, qty: tr.qty })
        : await act(d.service, { op: tr.op, amount: tr.qty });
      if (ok) { delete ui.vals[tr.key]; render(); }
      return;
    }
    case "protection": return act("protection");
    case "gun": return act("buy_gun", { index: +d.i });
    case "repair": return act("repair", { index: d.i === "all" ? "all" : +d.i });
    case "sellship": return act("sell_ship", { index: +d.i });
    case "buyship": return act("buy_ship", { ship: d.ship });
    case "dest": if (!S.me.ready) { ui.dest = d.port; render(); } return;
    case "orders": ui.orders = d.o; return render();
    case "slip": if (!S.me.ready) { ui.slip = d.s === "1"; render(); } return;
    case "sail":
      if (await act("sail", { dest: ui.dest, orders: ui.orders || S.me.orders, slip: !!ui.slip })) { ui.dest = null; ui.slip = false; }
      return;
    case "stay": return act("sail", { dest: null, orders: ui.orders || S.me.orders });
    case "unsail": return act("unsail");
    case "force": return act("force");
    case "newgame_ask": ui.confirmNew = true; return render();
    case "newgame_no": ui.confirmNew = false; return render();
    case "newgame": ui.confirmNew = false; return act("new_game");
    default: if (d.act.startsWith("cx_")) return Customs.click(d);
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
