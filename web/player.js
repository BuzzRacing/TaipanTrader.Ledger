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
const cannons = () => S.me.ships.reduce((n, s) => n + (s.cannons || 0), 0);
const cannonSlots = () => D.cannon_slots || 2;
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
    best: '<path d="M3 17 9 11l4 4 8-8"/><path d="M15 7h6v6"/>',
    run: '<path d="M4 8h14l-3.5-3.5M20 16H6l3.5 3.5"/>',
    danger: '<path d="M12 3a7 7 0 0 0-7 7c0 2.4 1.2 4.2 3 5.3V18h8v-2.7c1.8-1.1 3-2.9 3-5.3a7 7 0 0 0-7-7Z"/><circle cx="9.3" cy="10.5" r="1.4"/><circle cx="14.7" cy="10.5" r="1.4"/><path d="M10 18v3M14 18v3"/>',
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

/* The Danger monitor: the chance of a pirate fight on this run, the same pirate and pirate-lord rolls the
   engine makes at sea (engine.py voyage stages 1 and 2), storms left out. Protection halves the pirate
   roll and keeps the lord's fleet off you entirely. */
function pirateRisk(a, b) {
  const r = D.voyage_risk || { risk_min: .6, risk_max: 1.8, risk_div: 350, pirate_chance: .18, lord_chance: .06, protect_save: .5 };
  const distance = Math.max(r.risk_min, Math.min(r.risk_max, Chart.distance(D, a, b) / r.risk_div));
  const pirate = Math.min(1, r.pirate_chance * distance) * (S.me.protect > 0 ? 1 - r.protect_save : 1);
  const lord = S.me.protect > 0 ? 0 : Math.min(1, r.lord_chance * distance);
  return 1 - (1 - pirate) * (1 - lord);
}

/* Best price: what each cargo should fetch in a port when you get there, worked out from the prices the
   house knows (the ledger's last visit, or a newer Registrar tip). A known price is only a snapshot: every
   month the market pulls it back toward normal (rules.market.reversion) and the voyage itself is one more
   month, so the gap above normal is shrunk once for each month since it was seen plus one for the trip
   (engine.py _move_markets runs before arrival). A foretold boom (a live hot tip that will still be running
   when you land) holds its level and wins outright. "worth" means the expected gap beats the dealer's
   margin at your standing there, so the trip should actually pay. Banned cargo is left out. Null when
   nothing is known. */
function bestPrice(k) {
  const me = S.me, known = me.known[k], tips = (me.tips || {})[k] || {}, bans = S.bans?.[k] || [];
  const mods = (D.ports[k] && D.ports[k].mods) || {};
  const mk = D.market || { reversion: .3, spread_base: .04, spread_swing: .03 };
  const rep = me.rep?.[k] ?? 50;
  const margin = Math.max(0, mk.spread_base - mk.spread_swing * (rep - 50) / 50);
  const arrive = S.turn + 1;
  const hot = (me.hot_tips || []).find(tp => tp.port === k && D.goods[tp.good] && !bans.includes(tp.good)
    && tp.over == null && tp.lands <= arrive && arrive <= tp.ends);
  if (hot) return { g: hot.good, hot: true, worth: true, age: Math.max(0, S.turn - hot.turn), margin };
  let best = null;
  Object.keys(D.goods).forEach(g => {
    if (bans.includes(g)) return;
    let price = known?.prices?.[g], turn = known ? known.turn : null;
    const tp = tips[g];
    if (tp && Number.isFinite(tp.price) && (turn == null || tp.turn >= turn)) { price = tp.price; turn = tp.turn; }
    if (!Number.isFinite(price)) return;
    const normal = (D.goods[g].base || 0) * (mods[g] == null ? 1 : mods[g]);
    if (!(normal > 0)) return;
    const age = Math.max(0, S.turn - turn);
    const seen = price / normal - 1;
    const over = seen * Math.pow(1 - mk.reversion, age + 1);
    if (!best || over > best.over) best = { g, price, normal, seen, over, age, margin, worth: over > margin };
  });
  return best;
}

/* Trade run: the best cargo to buy here and carry to port k. Cost is what one unit costs here now, the
   dealer's cut included (quote). The sale is the price known for k, drifted toward normal for its age plus
   the voyage month (as bestPrice), less the dealer's cut at your standing there. Cargo banned here or there
   is left out. Null when no price is known for k; gain may be negative when nothing from here pays. */
function tradeRun(k) {
  const me = S.me, known = me.known[k], tips = (me.tips || {})[k] || {};
  const bansThere = S.bans?.[k] || [], bansHere = S.bans?.[me.port] || [];
  const mods = (D.ports[k] && D.ports[k].mods) || {};
  const mk = D.market || { reversion: .3, spread_base: .04, spread_swing: .03 };
  const margin = Math.max(0, mk.spread_base - mk.spread_swing * ((me.rep?.[k] ?? 50) - 50) / 50);
  let best = null;
  Object.keys(D.goods).forEach(g => {
    if (bansHere.includes(g) || bansThere.includes(g) || !Number.isFinite(me.prices?.[g])) return;
    let price = known?.prices?.[g], turn = known ? known.turn : null;
    const tp = tips[g];
    if (tp && Number.isFinite(tp.price) && (turn == null || tp.turn >= turn)) { price = tp.price; turn = tp.turn; }
    if (!Number.isFinite(price)) return;
    const normal = (D.goods[g].base || 0) * (mods[g] == null ? 1 : mods[g]);
    if (!(normal > 0)) return;
    const age = Math.max(0, S.turn - turn);
    const there = normal + (price - normal) * Math.pow(1 - mk.reversion, age + 1);
    const sell = there * (1 - margin), buy = quote(g, 1, "buy");
    if (!(buy > 0)) return;
    const gain = sell / buy - 1;
    if (!best || gain > best.gain) best = { g, buy, sell, gain, age };
  });
  return best;
}

/* The house's standing as five rising heat bars, red to green, lit up to its tier: the masthead's
   standing plaque, shared by the plaque and the Sail cards. */
const STANDING_HEAT = [4, 26, 44, 78, 122];
const standingTier = rep => Math.min(4, Math.floor(Math.max(0, Math.min(100, Math.round(rep || 0))) / 20));
const standingHeat = i => `hsl(${STANDING_HEAT[i]} 72% ${i === 2 ? 50 : 46}%)`;
function standingHeatSvg(rep, label, cls) {
  const tier = standingTier(rep);
  const bars = STANDING_HEAT.map((_, i) => {
    const h = 6 + i * 3;
    return `<rect x="${(i * 10.4).toFixed(1)}" y="${18 - h}" width="8.6" height="${h}" rx="1.6" ` +
      (i <= tier ? `fill="${standingHeat(i)}"` : `class="off"`) + `/>`;
  }).join("");
  return `<svg class="${cls || "plq-heat"}" viewBox="0 0 50 18" role="img" aria-label="${label}" focusable="false" style="--heat:${standingHeat(tier)}">${bars}</svg>`;
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
      <header class="dk-top has-voy" data-r="top"></header>
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
  Ceremony.sync(S, D, app);
  const active = document.activeElement;
  const focusId = active && active.id && active.id.startsWith("in_") ? active.id : null;
  const caret = focusId ? active.selectionStart : null;

  let off = document.getElementById("offline");
  if (!off) { off = document.createElement("div"); off.id = "offline"; off.className = "offline"; document.body.appendChild(off); }
  off.textContent = t("ui.offline");
  off.hidden = online;

  const inGame = S.me && S.phase !== "lobby" && S.phase !== "ended";
  let portOverlay = false;
  document.body.classList.toggle("ingame", !!inGame);
  if (inGame) {
    const deck = deckFrame(), parts = gameScreen();
    portOverlay = !!parts.over;
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
  syncPromotion(inGame, S.phase === "ended" || (inGame && S.phase === "port" && !portOverlay));

  if (focusId) {
    const el = document.getElementById(focusId);
    if (el && el !== document.activeElement) { el.focus(); try { el.setSelectionRange(caret, caret); } catch (e) { /* ignore */ } }
  }
  deckArt(inGame);
  Pulse.sync(inGame && ui.tab === "market" && !ui.tally);
  markSpeaking();
  if (typeof Battle !== "undefined") Battle.sync();
  TownCrier.sync(S, D, inGame && !portOverlay && !S.me.promotion && !Battle.busy()
    && !document.querySelector(".ceremony") && !document.querySelector("dialog[open]"));
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
  // At the Port Authority's desk the stage shows the officer too, in a different picture from the
  // popup's (customs.js Customs.stage); with no second picture of her, it shows the port.
  const cxOpen = Customs.isOpen() && !document.querySelector(".captains-log");
  if (cxOpen) {
    const cx = Customs.stage();
    document.getElementById("deck").classList.toggle("woman", !!cx);
    if (cx) { Stage.idle(cx.key, cx.html, cx.name, cx.note); return; }
  }
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
  { "stat.weapons": "Weapons", "stat.weapons_tip": "{guns} guns / {cannons} cannons", "bar.welcome": "Welcome to", "bar.came.sailed": "in from {from}", "bar.came.stayed": "a month at anchor", "bar.came.wrecked": "back after the wreck",
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
    "market.all": "Trade all", "market.all_sell": "Sell {n}", "market.all_buy": "Buy {n}", "market.all_none": "Nothing to trade",
    "market.all_sell_tip": "Sell all {n} {good} aboard now for {total}.", "market.all_buy_tip": "Buy as much {good} as silver and hold allow: {n} for {total}.",
    "market.all_cargo": "Trade all cargo", "market.all_cargo_lined": "{n} trades lined up", "market.all_cargo_lined_1": "1 trade lined up",
    "market.all_cargo_sell": "Sell everything aboard", "market.all_cargo_tip_lined": "Make every trade lined up on the bars now: sales first, then purchases.",
    "market.all_cargo_tip_sell": "Sell every cargo aboard at this market (anything sealed in bond stays).", "market.all_cargo_done": "{n} trades done.",
    "market.pl_tip_up": "Profit of {profit} on this sale, against the {paid} a unit you paid on average.",
    "market.pl_tip_down": "Loss of {profit} on this sale, against the {paid} a unit you paid on average.",
    "dealer.pay": "You pay", "dealer.get": "You get", "dealer.units": "{n} units", "dealer.cut": "Dealer's cut",
    "dealer.cut_sub": "{margin}% margin", "sail.risk_title": "Routes ranked by voyage risk",
    "sail.easiest": "Easiest",
    "sail.hardest": "Hardest", "sail.route": "Route", "sail.weather": "Weather", "sail.distance": "Distance",
    "sail.intel": "Intel", "sail.standing": "Standing",
    "sail.best": "Best price", "sail.best_none": "prices unknown",
    "sail.best_tip": "{good} was {price} in {port} ({when}), {seen} against a usual {normal}. Markets drift back toward normal every month, so by the time you land expect about {expect}. The dealer there keeps about {margin}% at your standing.",
    "sail.best_hot": "{good} \u2014 foretold boom", "sail.best_hot_tip": "A tip says {good} is booming in {port} when you land. The boom holds its price until it runs out.",
    "sail.best_flat": "nothing above usual", "sail.best_seen": "seen {when}",
    "sail.run": "Buy here \u2192 sell there", "sail.run_none": "nothing from here pays",
    "sail.run_tip": "Buy {good} here for {buy} a unit (dealer's cut included). Sold in {port} it should fetch about {sell} a unit once the price has drifted and the dealer there takes his cut ({when}). Small buys only: big lots push the price against you.",
    "sail.danger": "Danger monitor", "sail.danger_tip": "{pct}% chance of a pirate fight on the way to {port}.",
    "sail.danger_0": "low", "sail.danger_1": "moderate", "sail.danger_2": "high", "sail.danger_3": "severe",
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
    "port.owe.grp_lender": "Moneylender", "port.owe.grp_collect": "Debt collectors", "port.owe.grp_port": "Leaving port", "port.owe.grp_bank": "Counting-house",
    "voy.left": "{n} months left", "voy.left_1": "Final month", "voy.closed": "The books are closed",
    "voy.close": "Books close {date}", "voy.seal": "終", "voy.aria": "Voyage: {date}. {left}. Books close {end}." });
const womanPick = {};
/* Cast members who are port women: while the Mayor or the Tax collector speaks, the stage shows the
   picture for the port the house is in (deck.js Stage asks for it), not one portrait for every port. */
const PORT_SPEAKERS = { mayor: "mayor", taxlady: "taxlady" };
/* While the Port Authority's desk is open the stage already shows the officer (a different picture
   from the popup's): when she speaks, the stage keeps that picture and only her words go on the plate
   (deck.js Stage.talk). */
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
    `<li>${houseMark(p)}<b>${esc(p.firm)}</b> ` +
    `<span class="muted">${esc(p.name)}${p.host ? " · " + te("w.host") : ""}${p.present ? "" : " · " + te("w.away")}</span></li>`).join("") + "</ul>";
}

const joinUrl = () => `<p class="muted center">${th("join.url", { url: "<b>" + esc(S.join_url) + "</b>" })}</p>`;

/* Saved Captains (Admin > Captains): pick yours, type the PIN, choose the House. */
let CAPS = null, capsAt = 0, capsLoading = false;
async function loadCaptains() {
  capsLoading = true;
  try { const r = await (await fetch("/api/captains")).json(); if (r.ok) CAPS = r; }
  catch (err) { if (!CAPS) CAPS = { captains: [], typed: true }; }
  capsLoading = false; capsAt = Date.now();
  if (S && !S.me) render();
}
const capInitials = n => String(n || "?").split(/\s+/).filter(Boolean).slice(0, 2).map(w => w[0]).join("").toUpperCase();
function capFace(c, big) {
  return `<span class="cap-face${big ? " big" : ""}">${c.portrait ? `<img src="${esc(c.portrait)}" alt="">` : `<b>${esc(capInitials(c.name))}</b>`}</span>`;
}
function capCrest(h) {
  return `<span class="cap-crest" style="--hc:${esc(h.color)}">${h.image ? `<img src="${esc(h.image)}" alt="">` : esc(capInitials(h.name))}</span>`;
}
function captainPicker() {
  if (!CAPS) return `<p class="muted">…</p>`;
  const list = CAPS.captains || [];
  if (!list.length) return `<p class="muted">${te("join.captain_none")}</p>`;
  const c = list.find(x => x.cid === ui.capSel);
  if (!c) {
    return `<p class="muted">${te("join.captain_help")}</p><div class="cap-grid">${list.map(x =>
      `<button type="button" class="cap-tile${x.guest ? " guest" : ""}" data-act="cap_pick" data-cid="${esc(x.cid)}">${capFace(x)}
        <b>${esc(x.name)}</b><small>${esc(x.guest ? t("join.guest") : x.title || "")}</small></button>`).join("")}</div>`;
  }
  const houses = c.houses || [];
  if (!houses.some(h => h.hid === ui.capHouse)) ui.capHouse = houses[0] ? houses[0].hid : "";
  const pin = c.guest ? `<p class="muted">${te("join.guest")}</p>`
    : `<label>${te("join.pin")} <input id="in_pin" data-k="pin" type="password" inputmode="numeric" autocomplete="off"
        maxlength="8" placeholder="${esc(t("join.pin_ph"))}" value="${esc(val("pin"))}"></label>`;
  return `<div class="cap-chosen">${capFace(c, true)}<div><h3>${esc(c.name)}</h3><p class="muted">${esc(c.title || "")}
      ${c.games ? " · " + te("join.games", { n: c.games }) : ""}</p>${pin}</div></div>
    ${houses.length ? `<p class="cap-label">${te("join.house")}</p><div class="cap-houses">${houses.map(h =>
      `<button type="button" class="cap-house${h.hid === ui.capHouse ? " on" : ""}" data-act="cap_house" data-hid="${esc(h.hid)}"
        style="--hc:${esc(h.color)}">${capCrest(h)}<span><b>${esc(h.name)}</b>${h.motto ? `<small>${esc(h.motto)}</small>` : ""}</span></button>`).join("")}</div>` : ""}
    ${btn(te("join.captain_button"), "cap_join", "", "primary wide")}
    ${btn(te("join.change"), "cap_back", "", "link wide")}`;
}

function joinScreen() {
  const late = S.phase === "port" ? `<p class="note">${te("join.late")}</p>` : "";
  const over = S.phase === "ended" ? `<p class="note">${te("join.over")}</p>` : "";
  if (!capsLoading && (!CAPS || Date.now() - capsAt > 20000)) loadCaptains();
  const typed = !CAPS || CAPS.typed ? `<details class="card cap-typed"${CAPS && !(CAPS.captains || []).length ? " open" : ""}>
      <summary>${te("join.typed")}</summary>
      <label>${te("join.name")} ${input("name", t("join.name_ph"), 'inputmode="text" maxlength="20"')}</label>
      <label>${te("join.firm")} ${input("firm", t("join.firm_ph"), 'inputmode="text" maxlength="28"')}</label>
      ${btn(te("join.button"), "join", "", "primary wide")}</details>` : "";
  return masthead(esc(D.brand.tagline)) + `<main class="narrow cap-join">
    <section class="card"><h2>${te("join.captain_title")}</h2>${late}${over}${captainPicker()}</section>
    ${typed}
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
       ${btn(te("ceremony.cue"), "start", "", "primary wide", !!S.start_at)}`
    : `<h2>${te("lobby.wait_title")}</h2><p class="muted">${te("lobby.wait", { years: S.years })}</p>${level}`;
  return masthead(esc(D.brand.tagline)) + `<main class="narrow">
    <section class="card">${host}</section>
    <section class="card"><h2>${te("join.houses")}</h2>${roster()}${btn(te("st.open_hint"), "tally", "", "ghost wide")}</section>
    <p class="muted center">${th("join.url", { url: "<b>" + esc(S.join_url) + "</b>" })}<br>
    ${th("join.board_url", { url: "<b>" + esc(S.join_url) + "/board</b>" })}</p></main>`;
}

/* The race: one ledger line per House, richest first. The top three wear gold, silver and bronze
   medals; everyone below gets a plain engraved ring. Equal fortunes share a place. Each line shows the
   crest, the House and its captain, where it lies and how many ships, then net worth with the gap to
   the leader underneath. */
const ORD = typeof Intl !== "undefined" && Intl.PluralRules ? new Intl.PluralRules("en", { type: "ordinal" }) : null;
function ordinal(n) {
  const k = ORD ? ORD.select(n) : "other";
  return te("race.ord_" + k, { n });
}
function standings() {
  const list = Ceremony.ranked(S);
  const lead = list.length ? list[0].worth : 0;
  let place = 0;
  const rows = list.map((p, i) => {
    if (i === 0 || p.worth !== list[i - 1].worth) place = i + 1;
    const medal = ["", "gold", "silver", "bronze"][place] || "";
    const me = p.id === S.me.id;
    const gap = lead - p.worth;
    const sub = place === 1
      ? (list.length > 1 && list[1].worth < p.worth ? te("race.lead_by", { gap: money(p.worth - list[1].worth) }) : te("race.leader"))
      : te("race.behind", { gap: money(gap) });
    return `<li class="race-row${medal ? " " + medal : ""}${me ? " me" : ""}">
      <span class="medal${medal ? " " + medal : ""}" title="${esc(ordinal(place))}" aria-label="${esc(ordinal(place))}"><b>${place}</b></span>
      <span class="race-crest">${houseMark(p)}</span>
      <span class="race-who"><b class="hname">${esc(p.firm)}</b>${me ? `<em class="race-you">${te("race.you")}</em>` : ""}
        <span class="race-capt">${esc(p.name)} <span class="rankname">${esc(p.rank)}</span></span>
        <small class="race-where">${esc(portName(p.port))} · ${esc(ten("race.ships", p.ships))}</small></span>
      <span class="race-worth"><small>${te("col.worth")}</small><b class="${p.worth < 0 ? "down" : ""}">${money(p.worth)}</b><small>${sub}</small></span>
    </li>`;
  }).join("");
  return `<ol class="race">${rows}</ol>`;
}

function endScreen() {
  const top = Ceremony.ranked(S)[0];
  return masthead(te("end.sub", { date: S.date })) + `<main class="narrow">
    <section class="card"><h2>${te("end.title", { name: top.name, firm: top.firm })}</h2>${standings()}</section>
    ${S.voyage_story ? `<section class="card">${Ceremony.story(S, D.ports)}</section>` : ""}
    <section class="card">${btn(te("end.ledger"), "ledger", "", "wide")}</section>
    <section class="card">${btn(te("end.free_play"), "free_play", "", "primary wide")}
      <p class="muted">${te("end.free_play_note")}</p></section>
    <section class="card">${btn(te("st.open_end"), "tally", "", "ghost wide")}</section>
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
  // Money plaques show a short figure ($112K, $1.25M) with the exact sum in the tooltip (s[4]).
  const ms = n => [moneyShort(n), money(n)];
  const cash = ms(p.cash), bank = ms(me.bank), debt = ms(me.debt), worth = ms(me.worth);
  // Weapons: guns / cannons on one line (the full wording in the tooltip).
  const cn = cannons();
  const stats = [["stat.silver", cash[0], "silver" + dir(p.cash, me.cash), "", cash[1]], ["stat.bank", bank[0], "", "", bank[1]],
                 ["stat.debt", debt[0], (me.debt > 0 ? "bad" : "") + (due ? " due" : "") + (due === 1 ? " due-now" : ""), due ? ten("stat.debt_due", due) : "", debt[1]],
                 ["stat.worth", worth[0], "worth", "", worth[1]], ["stat.hold", p.used + " / " + me.capacity, dir(p.used, me.used).trim()],
                 ["stat.weapons", guns() + " / " + cn, "guns", "", t("stat.weapons_tip", { guns: guns(), cannons: cn })]]
    .map(s => `<div class="plq ${s[2] || ""}"${s[4] && s[4] !== s[1] ? ` title="${esc(s[4])}"` : ""}><span>${te(s[0])}</span><b>${s[1]}</b>${s[3] ? `<small>${s[3]}</small>` : ""}</div>`).join("") +
    standingPlaque((me.rep || {})[me.port]);
  return `<div class="dk-house${Faces.of(me).crest ? " has-crest" : ""}">${houseMark(me, "dk-crest")}
      <div><b>${esc(me.firm)}</b><span class="rankname">${esc(me.rank)}</span></div></div>
    ${portPlate()}
    <div class="dk-stats">${stats}</div>
    ${voyageRibbon()}`;
}

/* The voyage ribbon along the foot of the top bar, the full width of the screen, for the whole game:
   a lacquer silk ribbon with brass hairlines, lit from the start date to this month by a fixed
   jade > brass > oxblood gradient (so the colour at the leading edge says how late it is; the rest of
   the gradient shows faintly ahead). Ticks mark the years (quarters in a 1-year game), a ship rides the
   leading edge, and the oxblood seal at the right end is the day the books close. In the last
   VOY_NEAR months each month gets a notch and the count turns brass; in the last VOY_END the count
   turns oxblood and the seal pulses. Numbers come from the view: turn, years, turns_left. */
const VOY_NEAR = 10, VOY_END = 3;
const VOY_SHIP = `<svg viewBox="0 0 26 22" aria-hidden="true" focusable="false"><path fill="currentColor" d="M1.5 15.2h23l-3.4 4.6H5.2z"/>` +
  `<path fill="currentColor" d="M12.4 1.6h1.1v13.2h-1.1z"/><path fill="currentColor" opacity=".92" d="M14 2.6c4.6 1.4 7.6 5.3 8.4 11.4H14z"/>` +
  `<path fill="currentColor" opacity=".8" d="M11.9 4.8c-3.4 1.2-5.7 4.2-6.4 9.2h6.4z"/>` +
  `<path fill="none" stroke="#15100c" stroke-opacity=".45" stroke-width=".7" d="M14 5.6h4.4M14 8.6h6.4M14 11.4h7.6M11.9 7.6H8.4M11.9 10.8H6.6"/></svg>`;
function voyageRibbon() {
  const total = Math.max(1, Math.round((Number(S.years) || 1) * 12));
  const turn = Math.min(total, Math.max(0, Number(S.turn) || 0));
  const left = Math.max(0, S.turns_left != null ? Number(S.turns_left) : total - turn);
  const pct = n => (n / total * 100).toFixed(3) + "%";
  const step = total <= 12 ? 3 : total <= 240 ? 12 : 60;
  let marks = "";
  for (let m = step; m < total; m += step) marks += `<i class="voy-tick" style="left:${pct(m)}"></i>`;
  if (left <= VOY_NEAR) for (let m = Math.max(1, total - VOY_NEAR); m < total; m++)
    if (m % step) marks += `<i class="voy-notch" style="left:${pct(m)}"></i>`;
  const label = n => `${te("mon." + (n % 12))} ${(Number(D.start_year) || 1860) + Math.floor(n / 12)}`;
  const from = label(0), end = label(total - 1);
  const free = !!S.free_play;
  const count = free ? te("voy.free") : left === 0 ? te("voy.closed") : left === 1 ? te("voy.left_1") : te("voy.left", { n: left });
  const close = free ? te("voy.free_sub", { date: end }) : te("voy.close", { date: end });
  const stage = free ? " free" : left <= VOY_END ? " end" : left <= VOY_NEAR ? " near" : "";
  const aria = te("voy.aria", { date: esc(S.date || ""), left: count, end });
  return `<div class="dk-voy${stage}" role="img" aria-label="${aria}" title="${aria}">
      <span class="voy-from">${from}</span>
      <div class="voy-track" style="--p:${pct(turn)}"><div class="voy-silk"><i class="voy-ghost"></i><i class="voy-fill"></i>${marks}</div>
        <i class="voy-ship">${VOY_SHIP}</i></div>
      <span class="voy-seal" aria-hidden="true">${te("voy.seal")}</span>
      <span class="voy-left"><b>${count}</b><small>${close}</small></span></div>`;
}

/* The seventh plaque: the house's standing in this port as a heat icon, no number. Five fat rising
   bars running red (hostile) to green (favoured), lit up to the standing's tier. No shield. The tier's
   name is in the tooltip and for screen readers. */
function standingPlaque(rep) {
  const tier = standingTier(rep);
  const word = te("stat.standing_" + ["hostile", "cool", "neutral", "warm", "favoured"][tier]);
  const tip = te("stat.standing_tip", { port: esc(portName(S.me.port)), tier: word });
  return `<div class="plq standing tier-${tier}" title="${tip}" style="--heat:${standingHeat(tier)}"><span>${te("stat.standing")}</span><b>${standingHeatSvg(rep, tip)}</b></div>`;
}

/* The port the fleet lies in, between the house name and the plaques: "Welcome to" over the port's
   name. (The "in from {port}" line under it was dropped 19 Nov 2026.) */
function portPlate() {
  return `<div class="dk-port"><span>${te("bar.welcome")}</span><b>${esc(portName(S.me.port))}</b></div>`;
}

/* Short money for the masthead plaques: exact below $10,000, then $12.5K / $112K, $1.25M / $12.5M / $125M,
   and B past a billion. Three significant figures at most, so a plaque never grows past "$999K". */
function moneyShort(n) {
  const v = Math.round(Number(n) || 0), a = Math.abs(v), sign = v < 0 ? "-" : "";
  if (a < 10000) return money(v);
  const [div, unit] = a >= 1e9 ? [1e9, "B"] : a >= 1e6 ? [1e6, "M"] : [1e3, "K"];
  const x = a / div, dp = x >= 100 ? 0 : x >= 10 ? 1 : 2;
  let s = (Math.floor(x * 10 ** dp + 1e-6) / 10 ** dp).toFixed(dp);
  if (dp) s = s.replace(/\.?0+$/, "");
  return sign + CUR + s + unit;
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
  const side = ui.tab === "market" ? dealerCard() + Pulse.card() : ui.tab === "chart" ? clearanceLedger()
    : ui.tab === "fleet" ? captainCommission(me)
    : ui.tab === "port" ? `<section class="card pt-race pt-race-side"><h2>${te("port.race.title")}</h2>${portRace()}</section>` : "";
  // The Port Authority's desk comes first in a new port (after the month's log is read).
  return { top, nav, pane, side, over: fighting ? "" : report || Customs.html() };
}

function rankSeal(rankId) {
  const art = Media.choose("rank", rankId, "badge", { mode: "fixed", strict: true });
  return art ? `<img class="fleet-rank-seal" src="${esc(art.u)}" alt="">` : "";
}

function captainCommission(me) {
  const portrait = Faces.of(me).portrait;
  const { next_rank: next, qualified_rank: qualified } = me;
  const status = qualified ? te("fleet.rank_earned", { rank: qualified })
    : next ? te("fleet.rank_next", { rank: next.title }) : te("fleet.rank_max");
  const note = qualified ? me.port === me.home ? te("fleet.rank_customs")
    : te("fleet.rank_return", { port: portName(me.home) })
    : next ? te("fleet.rank_goal", { worth: money(me.worth), goal: money(next.worth) }) : "";
  return `<section class="fleet-commission" aria-label="${te("fleet.commission")}">
    ${portrait ? `<img class="fleet-captain-portrait" src="${esc(portrait)}" alt="">` : ""}
    <div class="fleet-commission-label">${te("fleet.commission")}</div>
    <div class="fleet-rank-identity">${rankSeal(me.rank_id)}<div>
      <h2>${te("fleet.captain", { name: me.name })}</h2><strong>${esc(me.rank)}</strong>
    </div></div>
    <dl><div><dt>${te("fleet.captain_worth")}</dt><dd>${esc(money(me.worth))}</dd></div>
      <div><dt>${te("fleet.captain_ships")}</dt><dd>${me.ships.length}</dd></div>
      <div><dt>${te("fleet.captain_home")}</dt><dd>${esc(portName(me.home))}</dd></div></dl>
    <div class="fleet-rank-progress"><b>${status}</b>${note ? `<small>${note}</small>` : ""}</div>
  </section>`;
}

const tfb = (key, fb, vars) => T[key] == null ? esc(t(fb, vars)) : te(key, vars);
function promotionArt(port, rank) {
  const pick = (role, opts) => Media.choose("port", port, role, Object.assign({ strict: true, slot: "promo" }, opts || {}));
  const dedicated = Media.items("port", port, "mayor_" + rank, false).filter(i => i.r.includes("mayor_" + rank));
  const mayor = dedicated.find(i => i.p) || dedicated[0] || pick("mayor", { mode: "fixed" });
  const scene = pick("banner") || pick("arrival") || null;
  return { mayor: mayor && mayor.t === "image" ? mayor.u : "", scene: scene && scene.t === "image" ? scene.u
    : (((D.graphics || {}).ports || {})[port] || "") };
}
function syncPromotion(inGame, canShow) {
  const promotion = canShow && S.me && S.me.promotion;
  let dialog = app.querySelector(".fleet-promotion");
  if (!promotion) {
    if (dialog) dialog.remove();
    return;
  }
  const key = S.game_id + ":" + promotion.id;
  if (dialog && dialog.dataset.promotion === key) return;
  if (dialog) dialog.remove();
  const me = S.me, port = portName(promotion.port);
  const record = promotion.record || {};
  const ranks = record.ranks || D.ranks || [];
  const rankIndex = ranks.findIndex(r => r.id === promotion.rank_id);
  const numeral = n => {
    let out = "";
    for (const [value, mark] of [[1000, "M"], [900, "CM"], [500, "D"], [400, "CD"], [100, "C"], [90, "XC"],
      [50, "L"], [40, "XL"], [10, "X"], [9, "IX"], [5, "V"], [4, "IV"], [1, "I"]]) {
      while (n >= value) { out += mark; n -= value; }
    }
    return out;
  };
  const art = promotionArt(promotion.port, promotion.rank_id);
  const badge = Media.choose("rank", promotion.rank_id, "badge", { mode: "fixed", strict: true });
  const next = Object.hasOwn(record, "next") ? record.next : me.next_rank;
  const achievements = promotion.achievements;
  const mayorLabel = te("fleet.promotion_mayor", { port });
  const said = promotion.text || t("fleet.promotion_quote", { name: me.name, rank: promotion.title });
  const clip = ((S.voice || {}).promotion || [])[0] || null;
  const captain = Object.assign({}, me, { name: record.name || me.name, firm: record.firm || me.firm });
  const crest = houseMark(captain, "pr-crest");
  const style = (D.promotion_styles || {})[promotion.rank_id];
  const facts = [
    [t("fleet.captain_worth"), money(record.worth ?? me.worth), "pr-worth"],
    [t("fleet.promotion_ships"), record.ships ?? me.ships.length, ""]
  ];
  if (achievements) {
    facts.push([t("fleet.promotion_voyages"), achievements.voyages, ""]);
  }
  const best = achievements && achievements.best;
  const bestLine = best ? t("fleet.promotion_best_line", { qty: best.qty,
    good: (D.goods[best.good] || {}).name || best.good, port: portName(best.port), profit: money(best.profit) }) : "";
  dialog = document.createElement("dialog");
  dialog.className = "fleet-promotion pr";
  dialog.dataset.rank = promotion.rank_id;
  if (style) for (const k of ["tone", "deep", "metal", "paper", "ink"]) dialog.style.setProperty("--pr-" + k, style[k]);
  dialog.dataset.promotion = key;
  dialog.setAttribute("aria-labelledby", "fleet-promotion-title");
  dialog.innerHTML = `
    ${art.scene ? `<img class="pr-scene" src="${esc(art.scene)}" alt="">` : ""}<div class="pr-shade" aria-hidden="true"></div>
    <div class="pr-ceremony">
    <header class="pr-mast"><span class="pr-brand">${esc(typeof brandName === "function" && D.brand ? brandName(D.brand) : "")}</span>
      <span>${esc(port)} · ${te("fleet.promotion_letter")}</span></header>
    <div class="pr-house">${crest}<div><p class="pr-house-label">${te("fleet.promotion_house_of")}</p>
      <h2>${esc(captain.firm || captain.name)}</h2><p class="pr-to">${tfb("fleet.promotion_to", "Captain {name}", { name: captain.name })}</p></div>
      ${rankIndex >= 0 ? `<div class="pr-tier" aria-hidden="true"><strong>${numeral(rankIndex + 1)}</strong><span>${te("fleet.promotion_rank_label")}</span></div>` : ""}</div>
    <div class="pr-document${art.mayor ? "" : " pr-no-portrait"}">
    <section class="pr-card">
      <p class="pr-eyebrow">${tfb("fleet.promotion_order", "By order of the {mayor}", { mayor: t("fleet.promotion_mayor", { port }) })}</p>
      <p class="pr-hereby">${te("fleet.promotion_you_commissioned")}</p>
      <div class="pr-seal"><span class="pr-rays" aria-hidden="true"></span>
        ${badge ? `<img src="${esc(badge.u)}" alt="">` : `<span class="pr-noseal" aria-hidden="true">${numeral(rankIndex + 1)}</span>`}</div>
      <h2 class="pr-rank" id="fleet-promotion-title">${esc(promotion.title)}</h2>
      <p class="pr-elevation">${record.previous ? `${esc(record.previous.title)} <span aria-hidden="true">→</span> ` : ""}${esc(promotion.title)}</p>
      ${ranks.length ? `<ol class="pr-path" aria-label="${te("fleet.promotion_progress")}">${ranks.map((r, i) =>
        `<li class="${i <= rankIndex ? "earned" : ""}${i === rankIndex ? " current" : ""}"${i === rankIndex ? ' aria-current="step"' : ""}>
          <span aria-hidden="true">${numeral(i + 1)}</span><span class="pr-accessible">${esc(r.title)}</span></li>`).join("")}</ol>` : ""}
      <p class="pr-citation">${te(next ? "fleet.promotion_citation" : "fleet.promotion_citation_top", { firm: captain.firm || captain.name })}</p>
      <p class="pr-record-label">${te("fleet.promotion_record")}</p>
      <dl class="pr-figs">${facts.map(([label, value, cls]) => `<div class="${cls}"><dt>${esc(label)}</dt><dd>${esc(value)}</dd></div>`).join("")}</dl>
      ${achievements && (achievements.ports || achievements.won) ? `<p class="pr-deeds">${[
        achievements.ports ? te("fleet.promotion_ports_count", { n: achievements.ports }) : "",
        achievements.won ? te("fleet.promotion_wins_count", { n: achievements.won }) : ""
      ].filter(Boolean).join(" · ")}</p>` : ""}
      ${best ? `<p class="pr-exploit"><span>${te("fleet.promotion_best")}</span><em>${esc(bestLine)}</em></p>` : ""}
      <p class="pr-sign"><span>${mayorLabel}</span><small>${esc(port)} · ${esc(record.date || S.date || "")}</small></p>
    </section>
    <figure class="pr-who${art.mayor ? "" : " nopic"}">
      ${art.mayor ? `<img src="${esc(art.mayor)}" alt="${mayorLabel}">` : ""}
      <figcaption class="pr-line"><header>${clip && typeof Voice !== "undefined"
          ? `<button type="button" class="pr-say" data-pr="say" aria-label="${tfb("fleet.promotion_say", "Hear her again")}"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M11 5 6 9H2v6h4l5 4V5z"/><path d="M15.5 8.5a5 5 0 0 1 0 7"/><path d="M19 5a10 10 0 0 1 0 14"/></svg></button>` : ""}
        <span>${mayorLabel}</span></header>
        <p>“${esc(said)}”</p><small>${te("fleet.promotion_audience", { rank: promotion.title })}</small></figcaption>
    </figure>
    </div>
    <footer class="pr-actions">
      <button type="button" data-pr="go">${te("fleet.promotion_accept")} <span aria-hidden="true">&rarr;</span></button>
      <p class="pr-next">${next ? `${te("fleet.promotion_next")}: ${esc(next.title)} · ${esc(money(next.worth))}` : te("fleet.promotion_top")}</p>
    </footer>
      <div class="fleet-promotion-error" role="alert"></div>
    </div>`;
  // The Mayor says her congratulations as the ceremony opens, and again from the speaker button.
  const sayIt = () => {
    if (!clip || typeof Voice === "undefined") return;
    Voice.drop("promotion");
    Voice.say([Object.assign({ tag: "promo:" + key, text: said }, clip)], { group: "promotion" });
  };
  const again = dialog.querySelector("[data-pr=say]");
  if (again) again.addEventListener("click", sayIt);
  dialog.addEventListener("cancel", e => e.preventDefault());
  const button = dialog.querySelector("[data-pr=go]");
  button.addEventListener("click", async () => {
    if (typeof Voice !== "undefined") Voice.drop("promotion");
    const error = dialog.querySelector(".fleet-promotion-error");
    error.textContent = "";
    button.disabled = true;
    const result = await post("/api/act", { token, type: "promotion_ack", id: promotion.id });
    if (!result.ok) {
      button.disabled = false;
      error.textContent = result.error;
      return;
    }
    if (S.me && S.game_id + ":" + (S.me.promotion || {}).id === key) S.me.promotion = null;
    if (inGame && S.phase === "port") {
      ui.tab = "fleet";
      ui.tally = false;
    }
    render();
  });
  app.appendChild(dialog);
  dialog.showModal();
  button.focus({ preventScroll: true });
  dialog.scrollTop = 0;
  setTimeout(() => { if (dialog.isConnected && dialog.open) sayIt(); }, 900);
}

/* The captain button at the foot of the rail: the Captain's portrait from the Media Library, square and
   as big as the tab pictures above it, with the name in white across its foot (the same "face" look as the
   tabs). Without a portrait: their initials on the house colour, with their name under it. Tapping it opens
   a small fly-out beside it (above it in portrait) with Voices on/off and Options. Tapping outside it
   or pressing Escape closes it. */
function meButton() {
  const me = S.me, open = !!ui.meOpen;
  const name = me.name || me.firm || "";
  const initials = name.split(/\s+/).filter(Boolean).slice(0, 2).map(w => w[0].toUpperCase()).join("") || "?";
  const portrait = Faces.of(me).portrait;
  const face = portrait ? `<img class="dk-tabimg" src="${esc(portrait)}" alt="">` : `<em>${esc(initials)}</em>`;
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
    `<button type="button" class="dk-face${portrait ? " face" : ""}" data-act="me" aria-haspopup="menu" aria-expanded="${open}" aria-label="${te("deck.me", { name })}" title="${te("deck.me", { name })}">` +
    `${face}<span>${esc(name)}</span></button></div>`;
}

/* Her hot tip's log line (l.registrar_hot_logged) carries a brass "Hot tip" badge, here and in Port > Log.
   Log lines are plain text, so it is found by the wording's fixed opening. */
const HOT_FLAME = `<svg viewBox="0 0 16 16" width="1em" height="1em" aria-hidden="true"><path fill="currentColor" d="M8.6 1c.3 2.2-1 3.4-2.1 4.6C5.4 6.8 4.5 8 4.5 9.8A3.6 3.6 0 0 0 8 13.5a3.6 3.6 0 0 0 3.5-3.7c0-1.3-.6-2.3-1.2-3 .1 1-.3 1.8-1 2.1.3-2.6-.4-5.6-1.7-7.9zM8 15a5 5 0 0 1-5-5c0-2.4 1.3-3.9 2.4-5.1C6.6 3.6 7.6 2.6 7 0c3.3 1.6 5.5 5.3 5.5 9.8A4.9 4.9 0 0 1 8 15z"/></svg>`;
function isHotLog(line) {
  // The Registrar's (at home) and a port officer's (anywhere else) hot-tip log lines.
  return ["l.registrar_hot_logged", "l.officer_hot_logged"].some(k => {
    const head = ((typeof T !== "undefined" && T[k]) || "").split("{")[0];
    return !!head && String(line).startsWith(head);
  });
}
const hotBadge = line => isHotLog(line) ? `<span class="hot-badge">${HOT_FLAME}${te("hot.badge")}</span> ` : "";

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
      <p${isHotLog(line) ? ' class="hot-line"' : ""}>${hotBadge(line)}${esc(line)}</p></div></div>`;
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

/* TRADE ALL (18 Nov 2026). The row's "Trade all" button does the whole thing in one click, ignoring the
   bar: with this cargo aboard it sells all of it (bonded units stay); with none aboard it buys as much
   as silver and free hold allow right now. Other rows' lined-up trades are not counted: they have not
   happened yet. */
function maxBuyNow(g) {
  const me = S.me, free = Math.max(0, me.capacity - me.used);
  let lo = 0, hi = free;
  while (lo < hi) {
    const mid = Math.ceil((lo + hi) / 2);
    if (quote(g, mid, "buy") <= me.cash) lo = mid; else hi = mid - 1;
  }
  return lo;
}
function allOf(g) {
  const have = S.me.cargo[g] || 0, sealed = Math.min(have, (S.me.bond || {})[g] || 0), sellable = have - sealed;
  if (sellable > 0) return { side: "sell", qty: sellable };
  const n = maxBuyNow(g);
  return n > 0 ? { side: "buy", qty: n } : { side: "", qty: 0 };
}
function tradeAllButton(g) {
  const a = allOf(g);
  if (!a.side || S.me.ready) return `<button type="button" class="mk-all" disabled><b>${te("market.all")}</b><small>${te("market.all_none")}</small></button>`;
  const total = quote(g, a.qty, a.side), n = a.qty.toLocaleString();
  const tip = te(a.side === "sell" ? "market.all_sell_tip" : "market.all_buy_tip", { n, good: esc(D.goods[g].name), total: money(total) });
  return `<button type="button" class="mk-all ${a.side}" data-act="trade_all" data-good="${g}" title="${tip}">
    <b>${te("market.all")}</b><small>${te(a.side === "sell" ? "market.all_sell" : "market.all_buy", { n })}</small></button>`;
}

/* The header's "Trade all cargo": with trades lined up on the bars it makes all of them at once; with
   none lined up it sells everything aboard. */
function linedUp() {
  const me = S.me, out = [];
  if (me.ready || !D.goods) return out;
  Object.keys(D.goods).forEach(g => {
    if (ui.vals["t_" + g] == null) return;
    const tr = tradeOf(g);
    if (tr.side) out.push({ g, side: tr.side, qty: tr.qty });
  });
  return out;
}
function sellAllList() {
  const me = S.me, out = [];
  Object.keys(D.goods).forEach(g => {
    const have = me.cargo[g] || 0, sealed = Math.min(have, (me.bond || {})[g] || 0);
    if (have - sealed > 0) out.push({ g, side: "sell", qty: have - sealed });
  });
  return out;
}
function tradeAllCargoButton() {
  const lined = linedUp(), list = lined.length ? lined : sellAllList();
  const sub = lined.length ? ten("market.all_cargo_lined", lined.length) : te("market.all_cargo_sell");
  const tip = te(lined.length ? "market.all_cargo_tip_lined" : "market.all_cargo_tip_sell");
  return `<button type="button" class="mk-allcargo${lined.length ? " lined" : list.length && !S.me.ready ? " sell" : ""}" data-act="trade_all_cargo" title="${tip}"${list.length && !S.me.ready ? "" : " disabled"}>
    <b>${te("market.all_cargo")}</b><small>${sub}</small></button>`;
}
async function runTrades(list) {
  if (ui.busy || !list.length) return;
  ui.busy = true;
  // Sales first so their silver and hold are there for the purchases.
  list = list.filter(x => x.side === "sell").concat(list.filter(x => x.side === "buy"));
  let done = 0, last = null;
  for (const x of list) {
    const res = await post("/api/act", { token, type: x.side, good: x.g, qty: x.qty });
    last = res;
    if (!res.ok) break;
    delete ui.vals["t_" + x.g];
    done++;
  }
  ui.busy = false;
  if (last && !last.ok) toast(last.error, true);
  else if (done === 1) toast(last.msg);
  else toast(t("market.all_cargo_done", { n: done }));
  if (last && last.voice) Voice.say([Object.assign({ text: last.ok ? last.msg : last.error }, last.voice)], { group: "msg", replace: "msg" });
  render();
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
  const paid = paidFor(g), have = (S.me.cargo[g] || 0) + ((S.me.stored || S.me.wh || {})[g] || 0);
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
  const held = Pulse.pinned && Pulse.good === g ? " mp-held" : "";
  const tip = te("pulse.row_tip", { good: good.name });
  // The cargo of a live hot tip carries the brass flame (hotPin), where to buy it or where it booms.
  const hp = hotLive(), hot = hp && !hotGone(hp) && hp.good === g && (me.port === hp.home || me.port === hp.port);
  const hotTag = hot ? ` <span class="hot-badge mk-hot">${HOT_FLAME}${te("hot.badge")}</span>` : "";
  return `<tr data-good="${g}" class="${tr.side}${held}"${hot ? ' data-hot="1"' : ""}>
    <td class="mk-ico" data-act="pulse_pin" data-good="${g}" title="${tip}">${Media.html("cargo", g, "icon", "gicon", D.graphics.goods[g])}</td>
    <td class="mk-name" data-act="pulse_pin" data-good="${g}" title="${tip}"><b>${esc(good.name)}</b>${tag}${hotTag}</td>
    <td class="n mk-num"><b class="mk-price">${money(me.prices[g])}</b><span class="mk-have">${haveHtml(tr)}</span>${tr.sealed ? `<small class="mk-sealed">${te("market.sealed", { n: tr.sealed.toLocaleString() })}</small>` : ""}${paidHtml(g)}</td>
    <td class="mk-bar"><input type="range" class="mk-range" id="in_t_${g}" data-k="t_${g}" data-good="${g}" min="0" max="${tr.max}" step="1"
      value="${tr.at}" style="${barStyle(tr)}" ${tr.max && !me.ready ? "" : "disabled"} aria-label="${esc(good.name)}"${tr.sealed ? ` title="${te("market.sealed_block", { n: tr.sealed.toLocaleString(), good: good.name, port: portName(me.port) })}"` : ""}></td>
    <td class="mk-do">${tradeButton(g, tr)}</td>
    <td class="mk-alltd">${tradeAllButton(g)}</td></tr>`;
}

function marketTab() {
  const me = S.me;
  const banned = S.crackdown.includes(me.port);
  const rows = Object.keys(D.goods).map(marketRow).join("");
  return `<section class="card mk" style="--n:${Object.keys(D.goods).length}">
    <header class="mk-head"><h2>${te("market.title", { port: portName(me.port) })}</h2>
      <span class="mk-hold">${te("market.hold_short", { used: pending().used, cap: me.capacity })}</span>
      <span class="mk-allslot">${tradeAllCargoButton()}</span></header>
    ${banned ? `<p class="note bad">${te("market.banned")}</p>` : ""}
    <table class="mk-table"><thead><tr><th colspan="2">${te("col.cargo")}</th><th class="n">${te("col.price")} · ${te("col.aboard")}</th><th class="mk-scale"><span>${te("btn.sell")}</span><span>${te("btn.buy")}</span></th><th></th><th></th></tr></thead>
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
  const allSlot = app.querySelector(".mk-head .mk-allslot");
  if (allSlot) allSlot.innerHTML = tradeAllCargoButton();
  // Only the dealer's card changes while dragging; the market pulse under it keeps running.
  const card = app.querySelector(".dk-dyn .dl-card");
  if (card) card.outerHTML = dealerCard();
}

/* ------------------------------------------------------------ market pulse -- */
/* Under the dealer's card: the market keeper's own price book for this port (engine market_view,
   12 months of month-start prices, every month, not only the ones the house was here) with the live
   price as the last point. Idle, it roams the cargoes moving most this month plus any boom or crash
   running here, one every few seconds, the line morphing from one to the next. Tapping a cargo's
   picture or name in the trade list holds that cargo on the chart; tapping the chart lets it roam
   again. Two small tiles: this month's biggest riser and faller here, and the house's most
   profitable single sale in this port. The card's markup is fixed; Pulse.paint() fills it in place
   so the side column is not redrawn every few seconds. */
const Pulse = {
  good: null, pinned: false, timer: null, ys: null, anim: 0, sig: "",
  SECONDS: 4.5,
  book() { return (S.me && S.me.market) || { hist: [], windfalls: {}, best: null }; },
  /* Month-start prices before this month, oldest first, then the price now. */
  series(g) {
    const rows = this.book().hist.filter(r => r.turn < S.turn && r.prices[g] != null);
    return rows.map(r => ({ v: r.prices[g], d: r.date })).concat([{ v: S.me.prices[g], d: S.date }]);
  },
  /* This month's change: the price now against last month's opening price here. */
  change(g) {
    const rows = this.book().hist.filter(r => r.turn < S.turn && r.prices[g] != null);
    const was = rows.length ? rows[rows.length - 1].prices[g] : null;
    return was ? S.me.prices[g] / was - 1 : null;
  },
  goods() { return Object.keys(D.goods).filter(g => S.me.prices[g] != null); },
  /* What it roams when nobody is holding a cargo: booms and crashes first, then the three biggest moves. */
  roster() {
    const wf = this.book().windfalls || {}, all = this.goods();
    const moved = all.filter(g => this.change(g) != null).sort((a, b) => Math.abs(this.change(b)) - Math.abs(this.change(a)));
    const pick = all.filter(g => wf[g]).concat(moved.length ? moved : all.slice().sort((a, b) => S.me.prices[b] - S.me.prices[a]));
    return pick.filter((g, i) => pick.indexOf(g) === i).slice(0, Math.max(3, all.filter(g => wf[g]).length + 2));
  },
  movers() {
    const ch = this.goods().map(g => [g, this.change(g)]).filter(x => x[1] != null && Math.abs(x[1]) >= 0.005);
    if (!ch.length) return null;
    ch.sort((a, b) => b[1] - a[1]);
    const up = ch[0][1] > 0 ? ch[0] : null, down = ch[ch.length - 1][1] < 0 ? ch[ch.length - 1] : null;
    return { up, down };
  },
  /* The card's fixed frame plus the two tiles (they change only with the month or a sale). */
  card() {
    const me = S.me;
    if (!me || !D.goods) return "";
    const mv = this.movers(), best = this.book().best;
    const mover = (x, cls) => x ? `<div class="mp-mv ${cls}"><span>${esc(D.goods[x[0]].name)}</span><b>${x[1] > 0 ? "▲ +" : "▼ −"}${pct(Math.abs(x[1]), 0)}%</b></div>` : "";
    const movers = mv ? mover(mv.up, "up") + mover(mv.down, "down") : `<p class="mp-none">${te("pulse.no_movers")}</p>`;
    const bestHtml = best && D.goods[best.good]
      ? `<b class="mp-best-v">+${money(best.profit)}</b><small>${te("pulse.best_line", { qty: best.qty.toLocaleString(), good: D.goods[best.good].name, date: best.date })}</small>`
      : `<p class="mp-none">${te("pulse.best_none")}</p>`;
    return `<section class="mp-card" id="mpCard">
      <header class="mp-head"><span>${te("pulse.title")}</span><b class="mp-name" data-mp="name"></b></header>
      <div class="mp-now"><b class="mp-price" data-mp="price"></b><span class="mp-delta" data-mp="delta"></span><em class="mp-tag" data-mp="tag" hidden></em></div>
      <div class="mp-plot" data-act="pulse_free" role="img" data-mp="plot">
        <svg viewBox="0 0 300 100" preserveAspectRatio="none" aria-hidden="true">
          <defs><linearGradient id="mpFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="currentColor" stop-opacity=".32"/><stop offset="1" stop-color="currentColor" stop-opacity="0"/></linearGradient></defs>
          <line class="mp-base" x1="0" x2="300" y1="50" y2="50" vector-effect="non-scaling-stroke" data-mp="base"/>
          <path class="mp-area" fill="url(#mpFill)" data-mp="area"/>
          <path class="mp-line" vector-effect="non-scaling-stroke" data-mp="line"/>
        </svg><i class="mp-dot" data-mp="dot"></i></div>
      <div class="mp-axis"><span data-mp="from"></span><em data-mp="hint"></em><span data-mp="to"></span></div>
      <div class="mp-tiles"><div class="mp-tile"><small>${te("pulse.movers")}</small>${movers}</div>
        <div class="mp-tile best"><small>${te("pulse.best")}</small>${bestHtml}</div></div></section>`;
  },
  /* Called after every render: start or stop roaming, and fill a freshly drawn card. */
  sync(on) {
    if (!on) { clearInterval(this.timer); this.timer = null; return; }
    const el = document.getElementById("mpCard");
    if (!el) return;
    const goods = this.goods();
    if (!this.good || !goods.includes(this.good)) { this.good = this.roster()[0] || goods[0]; this.pinned = false; }
    const sig = S.turn + "|" + S.me.port + "|" + (S.me.prices[this.good] || 0);
    if (!el.dataset.painted || sig !== this.sig) this.paint(el.dataset.painted && sig !== this.sig);
    if (!this.timer) this.timer = setInterval(() => this.roam(), this.SECONDS * 1000);
  },
  roam() {
    if (this.pinned || ui.drag || ui.tab !== "market" || document.hidden || !document.getElementById("mpCard")) return;
    const list = this.roster();
    if (!list.length) return;
    this.good = list[(list.indexOf(this.good) + 1) % list.length];
    this.paint(true);
  },
  pin(g) {
    if (!D.goods[g]) return;
    const moved = this.good !== g;
    this.good = g; this.pinned = true;
    if (moved) requestAnimationFrame(() => this.paint(true));
  },
  free() {
    this.pinned = false;
    requestAnimationFrame(() => this.roam());
  },
  /* Fill the card for this.good; glide the line from where it was when animate is true. */
  paint(animate) {
    const el = document.getElementById("mpCard");
    if (!el || !this.good) return;
    const g = this.good, good = D.goods[g], pts = this.series(g);
    const q = k => el.querySelector('[data-mp="' + k + '"]');
    this.sig = S.turn + "|" + S.me.port + "|" + (S.me.prices[g] || 0);
    el.dataset.painted = "1";
    const now = pts[pts.length - 1].v, ch = this.change(g), wf = (this.book().windfalls || {})[g];
    const name = q("name");
    if (name.textContent !== good.name) { name.textContent = good.name; name.style.animation = "none"; void name.offsetWidth; name.style.animation = ""; }
    q("price").textContent = money(now);
    const delta = q("delta");
    delta.textContent = ch == null ? te("pulse.first") : (ch >= 0 ? "▲ +" : "▼ −") + pct(Math.abs(ch), 0) + "%";
    delta.className = "mp-delta " + (ch == null ? "" : ch >= 0 ? "up" : "down");
    const tag = q("tag");
    tag.hidden = !wf; tag.className = "mp-tag " + (wf || ""); tag.textContent = wf ? te("pulse." + wf) : "";
    q("from").textContent = pts[0].d || "";
    q("to").textContent = pts.length > 1 ? (S.date || "") : "";
    q("hint").textContent = te(this.pinned ? "pulse.pinned" : "pulse.roam");
    q("plot").setAttribute("aria-label", te("pulse.aria", { good: good.name, port: portName(S.me.port), price: money(now), n: pts.length }));
    el.classList.toggle("down", ch != null && ch < 0);
    el.classList.toggle("boom", wf === "boom");
    el.classList.toggle("crash", wf === "crash");
    // Scale: the cargo's own low-to-high, padded, so a quiet cargo still shows its ripples.
    const vs = pts.map(p => p.v), lo = Math.min(...vs), hi = Math.max(...vs), span = (hi - lo) || hi * 0.04 || 1;
    const target = vs.map(v => 90 - (v - lo) / span * 80);
    const first = vs[0], baseY = 90 - (first - lo) / span * 80;
    const from = this.ys && animate && !matchMedia("(prefers-reduced-motion: reduce)").matches
      ? target.map((_, i) => this.ys[Math.round(i * (this.ys.length - 1) / Math.max(1, target.length - 1))]) : target;
    const draw = ys => {
      const n = ys.length, x = i => n > 1 ? i * 300 / (n - 1) : 300;
      const d = ys.map((y, i) => (i ? "L" : "M") + x(i).toFixed(1) + " " + y.toFixed(1)).join(" ");
      q("line").setAttribute("d", n > 1 ? d : "M0 " + ys[0].toFixed(1) + " L300 " + ys[0].toFixed(1));
      q("area").setAttribute("d", (n > 1 ? d : "M0 " + ys[0].toFixed(1) + " L300 " + ys[0].toFixed(1)) + " L300 100 L0 100 Z");
      const dot = q("dot");
      dot.style.left = "100%"; dot.style.top = ys[n - 1] + "%";
      this.ys = ys;
    };
    q("base").setAttribute("y1", baseY.toFixed(1)); q("base").setAttribute("y2", baseY.toFixed(1));
    cancelAnimationFrame(this.anim);
    if (from === target) { draw(target); return; }
    const t0 = performance.now(), ms = 750;
    const step = now2 => {
      const k = Math.min(1, (now2 - t0) / ms), e = k < .5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2;
      draw(target.map((y, i) => from[i] + (y - from[i]) * e));
      if (k < 1) this.anim = requestAnimationFrame(step);
    };
    this.anim = requestAnimationFrame(step);
  },
};

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
  ["port", ["dues", "gift", "depot", "repairs", "protection", "pa_tax", "pa_fine", "pa_bribe", "pa_premium"]],
  ["money", ["interest", "bank_interest"]],
  ["perils", ["booty", "parley", "plundered", "seized", "fines", "overboard", "ships_lost", "wreck", "wreck_cargo", "robbed", "wh_robbed"]],
];
const plTotal = lines => Object.values(lines || {}).reduce((a, b) => a + b, 0);
const signed = n => (n > 0 ? "+" : "") + money(n);
const tone = n => n > 0.5 ? "up" : n < -0.5 ? "down" : "";
/* "1 month" / "3 months": a key with "_1" after it is used for exactly one. */
const ten = (key, n, vars) => te(n === 1 && T[key + "_1"] != null ? key + "_1" : key, Object.assign({ n, months: n }, vars || {}));

/* Services: the full set at home; elsewhere only where the port has a bank counter or warehouses to let. */
function portViews() {
  const me = S.me, here = me.port === myHome() || me.bank_here || (me.wh_here && me.wh_here !== "none");
  return ["arrival", "accounts", "log", "news"].concat(here ? ["services"] : []);
}
const portViewLabel = v => v === "services" && S.me.port !== myHome()
  ? te("port.view.services_here", { port: esc(portName(S.me.port)) }) : te("port.view." + v);

function portTab() {
  // A new month always opens on Arrival.
  if (ui.portTurn !== S.turn) { ui.portTurn = S.turn; ui.portView = "arrival"; ui.mayor = false; }
  const views = portViews();
  if (!views.includes(ui.portView)) ui.portView = "arrival";
  const seg = `<nav class="pt-tabs" role="tablist" aria-label="${te("port.views")}">${views.map(v =>
    `<button type="button" role="tab" class="pt-tab${ui.portView === v ? " on" : ""}" data-act="port_view" data-v="${v}" aria-selected="${ui.portView === v}"><span>${portViewLabel(v)}</span>${portBadge(v)}</button>`).join("")}</nav>`;
  const body = { arrival: portArrival, accounts: portAccounts, log: portLog, news: portNews, services: portServices }[ui.portView]();
  return `<div class="pt">${hotPin()}${seg}<div class="pt-view pt-${ui.portView}">${body}</div></div>`;
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

/* The Registrar's hot tips still to come or still running: kept on screen so the captain can act on
   them without having to remember what she said (customs.js hotTipHtml). */
function hotTipsCard() {
  const list = (S.me.hot_tips || []).filter(tp => tp.ends >= S.turn);
  if (!list.length) return "";
  return `<section class="card hot-tips">${list.map(tp => hotTipHtml(tp, false)).join("")}</section>`;
}

/* The live hot tip, pinned in brass across the top of the Port and Market screens from the month it
   is given until its boom is over, so it can't be lost among the ordinary price moves. One line:
   the cargo, where it booms, when (or how long is left), and what to do in the port the fleet is in. */
/* A tip is shown from the month it is given until the latest its boom could run, and for one month after
   it really ends (tp.over, set by the server; how long it runs is never sent ahead). */
const hotGone = tp => tp.over != null && S.turn >= tp.over;
const hotLive = () => ((S.me && S.me.hot_tips) || []).filter(x => (x.ends >= S.turn || (x.over != null && S.turn === x.over))
  && D.goods[x.good] && D.ports[x.port]).slice(-1)[0];
function hotPin() {
  const me = S.me, tp = hotLive();
  if (!tp) return "";
  const goods = D.goods[tp.good].name, where = portName(tp.port), home = portName(tp.home || me.home);
  const on = S.turn >= tp.lands, gone = hotGone(tp);
  const when = gone ? te("hot.over", { where, goods })
    : on ? `${te("hot.on", { where })} · ${te("hot.any_month")}`
    : `${te("hot.soon", { where, when: hotWhen(tp.lands - S.turn) })} · ${te("hot.how_long")}`;
  const held = (me.cargo || {})[tp.good] || 0;
  const act = gone ? te("hot.pin_missed")
    : on && me.port === tp.port ? te("hot.pin_sell", { goods, where })
    : !on && me.port === tp.home ? te("hot.pin_buy", { goods, port: home })
    : !on ? te("hot.pin_go", { goods, where }) : te("hot.pin_race", { where });
  return `<section class="hot-pin${gone ? " gone" : on ? " on" : ""}" role="status" aria-label="${te("hot.badge")}">
    <span class="hot-pin-art" aria-hidden="true">${Media.html("cargo", tp.good, "icon", "hot-pin-img", (D.graphics.goods || {})[tp.good], { mode: "fixed" })}</span>
    <div class="hot-pin-text">
      <p class="hot-pin-head"><span class="hot-badge">${HOT_FLAME}${te("hot.badge")}</span>
        <b>${te("hot.pin_route", { goods, where })}</b></p>
      <p class="hot-pin-when">${when}</p>
    </div>
    <div class="hot-pin-act"><b>${act}</b>${held ? `<small>${te("hot.pin_held", { n: held, goods })}</small>` : ""}</div>
  </section>`;
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
  // Out of silver with one ship: the shipyard will swap her for a junk and the difference in silver.
  const td = me.trade_down;
  if (td && !me.ready && me.cash + me.bank < 1000) {
    const yardHere = D.ports[me.port].shipyard;
    items.push(["warn", te(yardHere ? "port.todo.broke_yard" : "port.todo.broke",
      { name: esc(td.name), junk: esc(td.junk), value: money(td.value), yards: esc(D.yards.join(", ")) }),
      yardHere ? go("fleet", te("tab.fleet")) : go("chart", te("tab.chart"))]);
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
    ${row(te("port.glance.rivals"), rivals.length ? rivals.map(p => `<span class="pt-chip">${houseMark(p)}${esc(p.firm)}</span>`).join("") : te("port.glance.alone"))}
  </table>`;
}

function portRace() {
  return `${standings()}${btn(te("st.open_hint"), "tally", "", "wide ghost")}`;
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
  const lines = list => `<ol class="pt-entries">${list.map(l => `<li${isHotLog(l) ? ' class="hot-line"' : ""}><span>${hotBadge(l)}${esc(l)}</span></li>`).join("")}</ol>`;
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
  /* Heat: the server sends 0..1 per headline (its importance, cooled by its age in months); hot items
     glow amber-to-crimson behind the text and fade back to plain as the weeks pass. */
  const heat = S.news_heat || [];
  const news = (S.news || []).map((n, i) => {
    const at = n.indexOf(": "), h = Math.max(0, Math.min(1, +heat[i] || 0));
    const hot = h > 0.04 ? ` class="pt-hot${h >= 0.8 ? " pt-blaze" : ""}" style="--heat:${h.toFixed(3)}"` : "";
    return at > 0 && at < 14 ? `<li${hot}><span class="pt-when">${esc(n.slice(0, at))}</span><span>${esc(n.slice(at + 2))}</span></li>` : `<li${hot}><span class="pt-when"></span><span>${esc(n)}</span></li>`;
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
      Math.min((me.cargo[g] || 0) - ((me.bond || {})[g] || 0), me.wh_cap - whUsed)];
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
  const me = S.me, home = me.port === myHome(), port = esc(portName(me.port));
  const locked = me.ready, dr = me.depot_rules || {};
  let out = "";
  if (home || me.bank_here) {
    out += serviceCard("bank", te("bank.title"), te("bank.info", { balance: money(me.bank), rate: pct(D.bank_rate, 2) })
      + (home ? "" : " " + te("bank.one_account")), serviceSlider("bank", te("bank.title")));
  }
  if (home) {
    out += serviceCard("lender", te("loan.title"), te("loan.info", { debt: money(me.debt), rate: pct(D.loan_rate, 2), room: money(me.loan_room) }),
      serviceSlider("loan", te("loan.title")));
  }
  if (me.wh_here === "closed") {
    out += serviceCard("warehouse", te("wh.offer_title"), te("wh.offer", { port, cost: money(dr.open), cap: (dr.cap || 0).toLocaleString() }),
      `<div class="pt-actions">${btn(te("wh.open", { cost: money(dr.open) }), "depot", 'data-op="open"', "primary", locked || dr.open > me.cash)}</div>`);
  } else if (me.wh_here === "home" || me.wh_here === "open") {
    const whUsed = Object.values(me.wh).reduce((a, b) => a + b, 0);
    const goods = Object.keys(D.goods).filter(g => (me.cargo[g] || 0) + (me.wh[g] || 0) > 0);
    const warehouse = goods.map(g => {
      const name = esc(D.goods[g].name);
      const sellable = (me.wh[g] || 0) + Math.max(0, (me.cargo[g] || 0) - ((me.bond || {})[g] || 0));
      const sellAll = (me.wh[g] || 0) > 0 && sellable > 0 && Number.isFinite(me.prices[g])
        ? btn(te("wh.sell_all", { qty: sellable.toLocaleString(), gain: money(quote(g, sellable, "sell")) }), "sell_all",
          `data-good="${g}" title="${te("wh.sell_all_tip")}"`, "pt-sellall", locked) : "";
      return `<div class="pt-service-good"><div class="pt-service-stock"><b>${name}</b>
        <span>${te("col.aboard")} <b>${(me.cargo[g] || 0).toLocaleString()}</b> ·
          ${te("col.in_store")} <b>${(me.wh[g] || 0).toLocaleString()}</b></span>${sellAll}</div>
        ${serviceSlider("wh", name, g)}</div>`;
    }).join("") || `<p class="muted">${te("wh.empty")}</p>`;
    // What sits in the house's other warehouses, so nothing is forgotten in a far port.
    const others = Object.entries(Object.assign(home ? {} : { [myHome()]: { goods: me.wh_home || {} } }, me.wh_away || {}))
      .filter(([k, d]) => k !== me.port && Object.keys(d.goods || {}).length)
      .map(([k, d]) => esc(portName(k)) + " (" + Object.entries(d.goods).map(([g, q]) => q.toLocaleString() + " " + esc(D.goods[g] ? D.goods[g].name : g)).join(", ") + ")");
    const expand = me.wh_here === "open"
      ? `<div class="pt-actions">${btn(te("wh.expand", { qty: (dr.add || 0).toLocaleString(), cost: money(dr.expand) }), "depot", 'data-op="expand"', "pt-go", locked || dr.expand > me.cash)}</div>` : "";
    out += serviceCard("warehouse", home ? te("wh.title") : te("wh.title_away", { port }),
      te("wh.info", { used: whUsed.toLocaleString(), cap: me.wh_cap.toLocaleString(), hold_used: me.used, hold: me.capacity })
      + (others.length ? " " + te("wh.elsewhere", { list: others.join("; ") }) : ""), warehouse + expand);
  }
  if (home) {
    const agent = me.protect > D.renew_at ? te("agent.content", { months: me.protect })
      : me.protect > 0 ? te("agent.running_out", { months: me.protect }) : te("agent.none");
    const tribute = me.protect > D.renew_at ? "" : btn(te("agent.pay", { cost: money(me.protect_cost) }),
      "protection", "", "primary", me.ready || me.protect_cost > me.cash);
    out += serviceCard("agent", te("agent.title"), agent, tribute);
  }
  return out;
}

/* ---------------------------------------------------------------- fleet -- */
/* Compact ship cards (picture left, name, hull bar, gun pips, slim buttons) and a shipyard table
   built on the same row pattern as the market: picture cell, name, numbers, one button. */
/* Cannons come first, each one pip twice as wide (it fills cannon_slots mounts), then the guns, then empty mounts. */
function gunPips(guns, slots, cannons) {
  const cs = cannonSlots(), c = cannons || 0;
  const empty = Math.max(0, slots - guns - cs * c);
  return `<i class="on cn"></i>`.repeat(c) + `<i class="on"></i>`.repeat(guns) + `<i></i>`.repeat(empty);
}

function mountsLine(s, spec) {
  if (!s.cannons) return `${s.guns}/${spec.slots}`;
  return `${s.cannons} ${esc(t("tag.cannons"))} + ${s.guns} · ${te("fleet.mounts", { used: s.guns + cannonSlots() * s.cannons, slots: spec.slots })}`;
}

/* Three classes of ship (18 Nov 2026): merchantmen (cargo and guns, the line), escorts (guns only, the van)
   and cargo ships (hold only, the rear). The Fleet tab and the shipyard keep them apart, each with its own count
   and limit; escorts and cargo ships open once the line of merchantmen is full. */
const CLASS_ORDER = ["trader", "escort", "cargo"];
const roleOf = k => ((D.ships[k] || {}).role) || "trader";
function classInfo(role) {
  const c = (S.me.classes || {})[role];
  if (c) return c;
  const r = (D.fleet_rules || {})[role] || { max: D.max_fleet, unlock: 0 };
  const n = S.me.ships.filter(s => roleOf(s.type) === role).length;
  const traders = S.me.ships.filter(s => roleOf(s.type) === "trader").length;
  return { n, max: r.max, unlock: r.unlock, open: traders >= r.unlock };
}

function shipCard(s, i, yard) {
  const me = S.me, spec = D.ships[s.type], p = Math.round(100 * s.hull / spec.hull), role = roleOf(s.type);
  const free = s.free != null ? s.free : spec.slots - s.guns - cannonSlots() * (s.cannons || 0);
  const fix = s.repair
    ? btn(te("fleet.repair", { cost: money(s.repair) }), "repair", `data-i="${i}"`, "fl-btn")
    : `<span class="fl-ok">${te("fleet.seaworthy")}</span>`;
  const traders = me.ships.filter(x => roleOf(x.type) === "trader").length;
  const lastTrader = D.keep_trader !== false && role === "trader" && traders <= 1;
  const line = role === "escort" ? `${esc(spec.name)} · ${te("fleet.no_hold")}`
    : role === "cargo" ? `${esc(spec.name)} · ${te("col.hold").toLowerCase()} ${spec.hold} · ${te("fleet.no_guns")}`
    : te("fleet.ship_line", { type: spec.name, hold: spec.hold });
  const guns = spec.slots > 0 ? `<div class="fl-stat"><span class="fl-lbl">${te("col.guns")}</span>
        <span class="fl-pips">${gunPips(s.guns, spec.slots, s.cannons)}</span><span class="fl-v">${mountsLine(s, spec)}</span></div>` : "";
  const gunBtns = spec.slots > 0 ? `${btn(te("fleet.gun_short"), "gun", `data-i="${i}" title="${esc(t("fleet.gun_tip", { price: money(D.gun_price) }))}"`, "fl-btn", free < 1 || me.cash < D.gun_price)}
        ${spec.cannons ? btn(te("fleet.cannon_short"), "cannon", `data-i="${i}" title="${esc(t("fleet.cannon_tip", { price: money(D.cannon_price), power: D.cannon_power, slots: cannonSlots() }))}"`, "fl-btn", free < cannonSlots() || me.cash < D.cannon_price) : ""}
        ${s.guns ? btn(te("fleet.sell_gun"), "sellgun", `data-i="${i}" title="${esc(t("fleet.sell_gun_tip", { value: money(Math.floor(D.gun_price * D.gun_resale)) }))}"`, "fl-btn ghost") : ""}
        ${s.cannons ? btn(te("fleet.sell_cannon"), "sellcannon", `data-i="${i}" title="${esc(t("fleet.sell_cannon_tip", { value: money(Math.floor(D.cannon_price * D.gun_resale)) }))}"`, "fl-btn ghost") : ""}` : "";
  return `<article class="fl-ship fl-${role}">
    <div class="fl-art">${Media.html("ship", s.type, "card", "fl-img", D.graphics.ships[s.type], { slot: "fleet:" + s.name })}</div>
    <div class="fl-body">
      <header class="fl-name"><b>${esc(s.name)}</b>${spec.fast ? `<span class="tag">${te("tag.fast")}</span>` : ""}
        <span class="fl-type">${line}</span></header>
      <div class="fl-stat"><span class="fl-lbl">${te("col.hull")}</span>
        <div class="hull"><i style="width:${p}%" class="${p < 35 ? "low" : ""}"></i></div><span class="fl-v">${s.hull}/${spec.hull}</span></div>
      ${guns}
      <div class="fl-acts">${gunBtns}
        ${fix}
        ${yard && me.ships.length < 2 && me.trade_down
          ? btn(te("fleet.trade_down", { value: money(me.trade_down.value) }), "tradedown", `title="${esc(t("fleet.trade_down_tip", { junk: me.trade_down.junk, hold: me.trade_down.hold, guns: me.trade_down.guns, value: money(me.trade_down.value) }))}"`, "fl-btn ghost")
          : yard ? btn(te("fleet.sell", { value: money(s.value) }), "sellship", `data-i="${i}"`, "fl-btn ghost", me.ships.length < 2 || lastTrader) : ""}</div>
    </div></article>`;
}

function yardRow(k) {
  const me = S.me, s = D.ships[k], c = classInfo(roleOf(k));
  const cant = me.cash < s.price || c.n >= c.max || !c.open;
  return `<tr class="${cant ? "dim" : ""}">
    <td class="yd-ico">${Media.html("ship", k, "card", "yd-img", D.graphics.ships[k], { slot: "yard" })}</td>
    <td class="yd-name"><b>${esc(s.name)}</b>${s.fast ? `<span class="tag">${te("tag.fast")}</span>` : ""}${s.cannons ? `<span class="tag" title="${esc(t("fleet.cannon_tip", { price: money(D.cannon_price), power: D.cannon_power, slots: cannonSlots() }))}">${te("tag.cannons")}</span>` : ""}</td>
    <td class="n">${s.hold || "—"}</td><td class="n">${s.hull}</td><td class="n">${s.slots || "—"}</td>
    <td class="n yd-price">${money(s.price)}</td>
    <td class="yd-do">${btn(te("btn.buy"), "buyship", `data-ship="${k}"`, "fl-btn primary", cant)}</td></tr>`;
}

/* One class's heading: name, what it is for, count of limit, and (for escorts and cargo ships) when it opens. */
function classHead(role, tag) {
  const c = classInfo(role);
  const state = !c.open ? `<span class="fl-lock">${te("class.locked", { n: c.unlock })}</span>`
    : c.n >= c.max ? `<span class="fl-full">${te("class.full")}</span>` : "";
  return `<${tag} class="fl-class-head fl-${role}"><b>${te("class." + role)}</b><span class="fl-class-sub">${te("class." + role + "_sub")}</span>
    <span class="fl-class-n">${te("class.count", { n: c.n, max: c.max })}</span>${state}</${tag}>`;
}

function fleetTab() {
  const me = S.me, yard = D.ports[me.port].shipyard;
  const totalRepair = me.ships.reduce((n, s) => n + s.repair, 0);
  const groups = CLASS_ORDER.map(role => {
    const mine = me.ships.map((s, i) => [s, i]).filter(([s]) => roleOf(s.type) === role);
    const c = classInfo(role);
    if (!mine.length && role !== "trader" && !c.open) return "";      // nothing to show until the line is full
    return `<div class="fl-class">${classHead(role, "header")}
      ${mine.length ? `<div class="fl-ships">${mine.map(([s, i]) => shipCard(s, i, yard)).join("")}</div>`
        : `<p class="muted fl-none">${te("class.none")}</p>`}</div>`;
  }).join("");
  const esc_ = classInfo("escort").n, rear = classInfo("cargo").n;
  const screen = rear ? `<span class="fl-screen${esc_ < rear ? " thin" : ""}">${te(esc_ < rear ? "class.screen_thin" : "class.screen", { n: esc_, max: rear })}</span>` : "";
  const maxAll = CLASS_ORDER.reduce((n, r) => n + classInfo(r).max, 0);
  const types = Object.keys(D.ships);
  const yardBody = yard
    ? `<table class="yd-table"><thead><tr><th colspan="2">${te("col.ship")}</th><th class="n">${te("col.hold")}</th><th class="n">${te("col.hull")}</th>
        <th class="n">${te("col.guns")}</th><th class="n">${te("col.price")}</th><th></th></tr></thead>
        ${CLASS_ORDER.map(role => {
          const rows = types.filter(k => roleOf(k) === role);
          return rows.length ? `<tbody class="yd-class"><tr class="yd-head"><th colspan="7">${classHead(role, "div")}</th></tr>${rows.map(yardRow).join("")}</tbody>` : "";
        }).join("")}</table>`
    : `<p class="muted fl-none">${te("yard.none", { port: portName(me.port), yards: D.yards.join(", ") })}</p>`;
  const r = D.fleet_rules || {};
  return `<section class="card fl">
      <header class="mk-head"><h2>${te("fleet.title")}</h2>
        <span class="muted" title="${esc(t("fleet.info"))}">${te("fleet.info_short")}</span>
        <span class="mk-hold">${te("fleet.count", { n: me.ships.length, max: maxAll })}</span>${screen}
        ${totalRepair ? btn(te("fleet.repair_all", { cost: money(totalRepair) }), "repair", 'data-i="all"', "fl-btn primary") : ""}</header>
      ${groups}</section>
    <section class="card fl yd">
      <header class="mk-head"><h2>${te("yard.title")}</h2>${yard ? `<span class="muted">${te("yard.classes", { n: D.max_fleet, max: (r.escort || {}).max || 0, cap: (r.cargo || {}).max || 0 })}</span>` : ""}</header>
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
    const best = bestPrice(k);
    const signed = x => { const n = Math.round(x * 100); return `${n >= 0 ? "+" : "\u2212"}${Math.abs(n)}%`; };
    const bestText = !best ? te("sail.best_none")
      : best.hot ? te("sail.best_hot", { good: D.goods[best.g].name })
      : Math.round(best.over * 100) <= 0 ? te("sail.best_flat")
      : `${esc(D.goods[best.g].name)} \u2248 ${signed(best.over)}`;
    const bestAge = best && !best.hot ? te("sail.best_seen", { when: bookSeen(best.age) }) : "";
    const bestTip = !best ? "" : best.hot ? esc(t("sail.best_hot_tip", { good: D.goods[best.g].name, port: p.name }))
      : esc(t("sail.best_tip", { good: D.goods[best.g].name, price: money(best.price), normal: money(best.normal),
        port: p.name, when: bookSeen(best.age), seen: signed(best.seen), expect: signed(best.over),
        margin: (best.margin * 100).toFixed(1) }));
    const bestCls = !best ? "" : best.worth ? " best-up" : " best-flat";
    const run = tradeRun(k);
    const runPct = run ? Math.round(run.gain * 100) : 0;
    const runHtml = !run ? "" : runPct <= 0
      ? `<span class="dest-stat dest-run best-flat">${sailIcon("run")}<span><small>${te("sail.run")}</small><strong>${te("sail.run_none")}</strong></span></span>`
      : `<span class="dest-stat dest-run best-up" title="${esc(t("sail.run_tip", { good: D.goods[run.g].name, buy: money(run.buy),
          sell: money(Math.round(run.sell)), port: p.name, when: bookSeen(run.age) }))}">${sailIcon("run")}<span><small>${te("sail.run")}</small>
          <strong>${esc(D.goods[run.g].name)}: ${money(run.buy)} \u2192 \u2248${money(Math.round(run.sell))} <b class="dest-gain">+${runPct}%</b></strong></span></span>`;
    const danger = pirateRisk(me.port, k), dangerPct = Math.round(danger * 100);
    const dangerTier = danger < .12 ? 0 : danger < .22 ? 1 : danger < .32 ? 2 : 3;
    const rep = Math.round(me.rep[k] || 0);
    const repTip = te("dealer.standing_tip", { rep });
    const heat = maxScore > minScore ? (score - minScore) / (maxScore - minScore) : 0;
    const rankLabel = i === 0 ? te("sail.easiest") : i === routes.length - 1 ? te("sail.hardest") : `${te("sail.route")} ${i + 1}`;
    const weatherKind = ["calm", "fair", "squalls", "typhoon"][wx] || "calm";
    const isHome = k === myHome();
    const facilities = [
      p.shipyard && te("sail.facility.shipyard"),
      (p.bank || isHome) && te("sail.facility.bank"),
      (p.warehouse || isHome) && te("sail.facility.warehouse"),
    ].filter(Boolean);
    const label = [esc(p.name), ...(isHome ? [te("sail.home_port")] : []), rankLabel, ...facilities].join(", ");
    return `<button type="button" class="dest sail-card ${dest === k ? "on" : ""}${isHome ? " home" : ""}" data-act="dest" data-port="${k}"
      style="--risk-hue:${Math.round(118 * (1 - heat))};--risk-level:${Math.round(score * 100)}%" aria-label="${label}">
      <span class="dest-art">${Media.html("port", k, "banner", "dest-img", D.graphics.ports[k], { slot: "sail:" + k, mode: "fixed" })}
        ${S.crackdown.includes(k) ? `<span class="dest-ban tag bad">${te("tag.ban")}</span>` : ""}
        ${isHome ? `<span class="dest-home">\u2693 ${te("sail.home_port")}</span>` : ""}
        <span class="dest-title"><b>${esc(p.name)}</b><span class="dest-pct">${Math.round(score * 100)}%</span></span></span>
      <span class="dest-data">
        <span class="dest-stat wx${wx}">${sailIcon(weatherKind)}<span><small>${te("sail.weather")}</small><strong>${esc(D.weather[wx])}</strong></span></span>
        <span class="dest-stat dz${dangerTier}" title="${te("sail.danger_tip", { pct: dangerPct, port: esc(p.name) })}">${sailIcon("danger")}<span><small>${te("sail.danger")}</small><strong>${dangerPct}% · ${te("sail.danger_" + dangerTier)}</strong></span></span>
        <span class="dest-stat" title="${repTip}">${sailIcon("standing")}<span><small>${te("sail.standing")}</small><strong class="dest-rep" style="--heat:${standingHeat(standingTier(rep))}">${standingHeatSvg(rep, repTip, "dest-heat")}<em>${rep}</em></strong></span></span>
        <span class="dest-stat dest-best${bestCls}"${best ? ` title="${bestTip}"` : ""}>${sailIcon("best")}<span><small>${te("sail.best")}</small><strong>${bestText}</strong>${bestAge ? `<em class="dest-age">${bestAge}</em>` : ""}</span></span>
        ${runHtml}
      </span>
      ${facilities.length ? `<span class="dest-facilities">${facilities.map(name => `<span>${name}</span>`).join("")}</span>` : ""}
      </button>`;
  }).join("");
  return `<section class="card">
      <div class="sail-guide sail-guide-top"><span><b>${te("sail.risk_title")}</b></span>
        <span class="heat-key"><small>${te("sail.easiest")}</small><i></i><small>${te("sail.hardest")}</small></span></div>
      <div class="dests">${list}</div>
      <div class="sail-map">${Chart.svg({ data: D, players: S.players, weather: S.weather, crackdown: S.crackdown, here: me.port, dest, clickable: !me.ready, mine: me.id, focusRoute: true })}</div></section>
    <section class="card"><h2>${te("orders.title")}</h2>
      <div class="seg">${btn(cannons() ? te("orders.fight_cannons", { guns: guns(), cannons: cannons() }) : te("orders.fight", { guns: guns() }), "orders", 'data-o="fight"', orders === "fight" ? "on" : "")}${btn(te("orders.run"), "orders", 'data-o="run"', orders === "run" ? "on" : "")}</div>
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
    const when = p.here ? t("ledger.here") : !known ? t("ledger.unknown")
      : p.tip && p.tip[g] != null ? t("ledger.tip") + " · " + bookSeen(p.tip[g]) : bookSeen(p.age);
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
          ${selected.here ? "" : `<small>${esc(riskLabel(me.port, selected.key))} · ${esc(!Number.isFinite(selected.price) ? t("ledger.unknown")
            : selected.tip && selected.tip[g] != null ? t("ledger.tip") + " · " + bookSeen(selected.tip[g]) : bookSeen(selected.age))}</small>`}</div>
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
      .map(g => ({ g, price: p.prices[g], gap: p.prices[g] - local[g], tipped: p.tip && p.tip[g] != null,
                   age: p.tip && p.tip[g] != null ? p.tip[g] : p.age }))
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
    <small>${esc((p.tipped ? t("ledger.tip") + " · " : "") + bookSeen(p.age))}</small><span class="book-gain">+${esc(bookPrice(p.gap))} / unit</span>`,
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
      const tipped = !p.here && p.tip && p.tip[g] != null;
      const tip = [tipped ? t("ledger.tip") + " · " + bookSeen(p.tip[g]) : "", label ? t("ledger." + label) : "", pct].filter(Boolean).join(" · ");
      const style = heat ? ` style="--heat:${(.22 + heat * .78).toFixed(2)}"` : "";
      const mark = tone === "blocked" ? '<i class="book-ban" aria-hidden="true">⊘</i>' : "";
      return `<td class="${tone}${tipped ? " tipped" : ""}"${style}${tip ? ` title="${esc(tip)}" aria-label="${esc((Number.isFinite(price) ? bookPrice(price) + " · " : "") + tip)}"` : ""}>${mark}${
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
    // The Registrar's tips (Hong Kong): a price she gave for one cargo, newer than the last visit,
    // fills that cargo's square; tip[g] is its age in months.
    const prices = here ? me.prices : Object.assign({}, known?.prices || {}), tip = {};
    if (!here) Object.entries((me.tips || {})[key] || {}).forEach(([g, tp]) => {
      if (tp && Number.isFinite(tp.price) && (!known || tp.turn >= known.turn)) {
        prices[g] = tp.price; tip[g] = Math.max(0, S.turn - tp.turn);
      }
    });
    const tipAges = Object.values(tip);
    return { key, here, bans, prices, tip,
      age: here ? 0 : known ? Math.max(0, S.turn - known.turn) : tipAges.length ? Math.min(...tipAges) : null };
  });
  // No banner: the view switch is a slim segmented bar so the page's height goes to the prices.
  const banner = `<div class="book-seg" role="group" aria-label="${te("ledger.view")}">
      ${bookButton(te("ledger.signals"), "view", "signals", ui.bookView === "signals", "book-toggle")}
      ${bookButton(te("ledger.voyage"), "view", "voyage", ui.bookView === "voyage", "book-toggle")}
      ${bookButton(te("ledger.all"), "view", "all", ui.bookView === "all", "book-toggle")}</div>`;
  const view = { signals: bookSignals, voyage: bookVoyages, all: bookTable }[ui.bookView];
  return `${hotTipsCard()}<section class="card book">${view(goods, ports, banner)}</section>
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
  if (k === "pin") doJoinCaptain();
});

async function doJoinCaptain() {
  const res = await post("/api/join", { captain: ui.capSel, pin: val("pin"), house: ui.capHouse });
  if (res.voice) Voice.say([Object.assign({ text: res.ok ? "" : res.error }, res.voice)], { group: "msg", replace: "msg" });
  if (!res.ok) return toast(res.error, true);
  ui.vals.pin = "";
  token = res.token;
  store("seatrader_token", token);
  connect();
}

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
    case "cap_pick": ui.capSel = d.cid; ui.capHouse = ""; ui.vals.pin = ""; render();
      { const f = document.getElementById("in_pin"); if (f) f.focus(); } return;
    case "cap_house": ui.capHouse = d.hid; return render();
    case "cap_back": ui.capSel = ""; ui.vals.pin = ""; return render();
    case "cap_join": return doJoinCaptain();
    case "tab": ui.tab = d.tab; ui.tally = false; return render();
    case "pulse_pin": Pulse.pin(d.good); return render();
    case "pulse_free": Pulse.free(); return render();
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
    case "trade_all": {
      const a = allOf(d.good);
      if (!a.side) return;
      return runTrades([{ g: d.good, side: a.side, qty: a.qty }]);
    }
    case "trade_all_cargo": {
      const lined = linedUp();
      return runTrades(lined.length ? lined : sellAllList());
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
    case "depot": return act("depot", { op: d.op });
    case "sell_all": return act("sell", { good: d.good, src: "all" });
    case "gun": return act("buy_gun", { index: +d.i });
    case "cannon": return act("buy_cannon", { index: +d.i });
    case "sellgun": return act("sell_gun", { index: +d.i });
    case "sellcannon": return act("sell_cannon", { index: +d.i });
    case "repair": return act("repair", { index: d.i === "all" ? "all" : +d.i });
    case "sellship": return act("sell_ship", { index: +d.i });
    case "tradedown": return act("trade_down", {});
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
    case "free_play": return act("free_play");
    case "ledger": return Ceremony.openLedger(S, D, app);
    default: if (d.act.startsWith("cx_")) return Customs.click(d);
  }
});

// The finale's "Continue free play" button (ceremony.js) carries the whole world on past the last month.
window.addEventListener("ceremony:free-play", () => { if (S && S.me) act("free_play"); });

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

Faces.onChange = () => render();   // Captain portraits and House crests arrived or changed
loadInfo().then(info => { D = info.data; VS = Voice.setup(info.voice); Stage.setCast(VS.cast); connect(); });
