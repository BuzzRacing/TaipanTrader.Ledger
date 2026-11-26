/* THE DASHBOARD (21 Nov 2026): an 1860s Formula 1 pit box for the big screen. See dashboard.css for the layout.
   Timing tower (left), a ledger book that turns its own pages (middle: The Race, Sea Lanes, Markets & Booms),
   brass dials and a chalkboard of month times (right), a telegraph tape (bottom).

   Data: the public stream (/events, the same one the harbor board uses) for the date, weather, fights and news;
   /api/dashboard (dashboard_feed.py) for history. The feed already leaves out whatever the game's visibility
   rule keeps private, so a block that is missing is shown stamped "Sealed" rather than guessed.
   Wording: every label is a key "dash.*" that Admin > Language & Text can override; DEF below is the fallback. */
"use strict";

/* The Command Center (22 Nov 2026, dashboard-tabs.js): the book's three pages have become eight tabs, with a context
   bar and Watch Mode. Without that file (the older tests load this one alone) the book is the three pages it was. */
const TABS = typeof DashTabs !== "undefined" ? DashTabs : null;
const TURN_MS = TABS ? TABS.TURN_MS : 25000;       // how long a page stays open before the book turns
const IDLE_MS = TABS ? TABS.IDLE_MS : 0;           // after a touch, how long Watch Mode waits before turning again
const FEED_MS = 5000;        // how often the history is fetched when nothing else asks for it
const TAPE_SHOW = 14;
const PAGES = TABS ? TABS.PAGES : [{ k: "race", n: "I" }, { k: "lanes", n: "II" }, { k: "markets", n: "III" }];

const DEF = {
  "mk.intel": "Port intelligence", "mk.layer": "Map data layer", "mk.price": "Cargo prices", "mk.change": "Monthly change", "mk.weather": "Weather", "mk.active": "Active market effects", "mk.noactive": "No active booms or crashes.", "mk.history": "Recent market history", "mk.expired": "Recorded event", "mk.left": "{n} months remaining", "mk.leftone": "1 month remaining", "mk.all": "All ports", "mk.quote": "Posted quote", "mk.cargos": "Cargo at this port", "mk.status": "Trade status", "mk.banned": "Banned cargo", "mk.open": "No ban on this cargo", "mk.customs": "Customs crackdown", "mk.pricekey": "Ring fill compares current quotes. More ring fill = higher price. ✦ Active market effect.", "mk.changekey": "Ring fill compares the size of this month’s change. Jade = rising; crimson = falling. ✦ Active market effect.", "mk.weatherkey": "Ring fill shows weather severity at each port. Weather is current; it is not a voyage forecast.", "mk.inspect": "Select a port for its cargo, weather and market effects.", "mk.legal": "Comparison excludes banned ports. Posted quotes exclude dealer margins, tax and voyage costs.",

  "tab.race": "The Race", "tab.lanes": "Sea Lanes", "tab.markets": "Markets & Booms",
  "race.title": "The Race", "race.sub": "Net worth of every house, month by month",
  "race.lead": "Lead changes", "race.nolead": "No one has passed anyone yet.",
  "race.deals": "Biggest deals", "race.nodeals": "No sales to show yet.",
  "race.sealed": "Deals stay in the strongbox until the finale.",
  "lead.took": "{who} took the lead from {from}", "lead.passed": "{who} passed the {ghost}", "lead.fell": "{who} fell behind the {ghost}",
  "lanes.title": "Sea Lanes", "lanes.sub": "Every voyage sailed, thicker where sailed most",
  "lanes.busiest": "Busiest lanes", "lanes.now": "The fleets now", "lanes.none": "Nothing has sailed yet.",
  "lanes.sealed": "Profit by lane opens at the finale.", "lanes.times": "{n} trips", "lanes.time": "1 trip",
  "now.sea": "At sea, {origin} to {dest}", "now.port": "At anchor in {port}",
  "mk.title": "Markets & Booms", "mk.sub": "{good} across the ports: cheapest {low}, dearest {high}",
  "mk.basemovers": "Change this month", "mk.booms": "Booms and crashes", "mk.none": "The markets are quiet.", "mk.nobooms": "No booms or crashes yet.",
  "mk.boom": "Boom", "mk.crash": "Crash", "mk.months": "{n} months", "mk.month": "1 month", "mk.cheap": "cheap", "mk.dear": "dear",
  "sealed": "Sealed", "sealed.note": "Rivals are at the table. This page opens at the finale.",
  "tower": "Timing tower", "leader": "LEADER", "ghost.best": "Best game", "ghost.par": "Par pace",
  "status.port": "At {port}", "status.sea": "At sea", "status.fight": "In battle", "status.away": "Away",
  "tower.foot.par": "Racing a par pace until you have a game on the books.",
  "tower.foot.n": "{n} houses on the line",
  "chalk": "Month times", "chalk.month": "Month", "chalk.none": "No laps run yet.", "chalk.best": "Best month: {date}, {firm} {gain}",
  "dial.months": "Months left", "dial.of": "of {n}", "dial.baro": "Barometer", "dial.hull": "Fleet hull",
  "detail.close": "Close", "detail.hint": "Open details", "detail.weather": "Weather by sea", "detail.fleet": "Fleet condition", "detail.voyage": "The voyage", "detail.elapsed": "Months sailed", "detail.remaining": "Months remaining", "detail.sound": "Sound", "detail.crippled": "Crippled", "detail.scale": "Fair to dangerous · worst sea shown", "mk.cargo": "Choose cargo", "mk.buy": "Lowest quote", "mk.sell": "Highest quote", "mk.spread": "Price spread / unit", "mk.quotes": "Port quotes", "mk.select": "Select a port on the chart", "mk.gross": "Gross spread before voyage costs; quotes can change.", "mk.baseline": "Compared with the month’s opening quote; after a server restart, comparison begins with the first quote observed.", "mk.empty": "No quotes available yet.", "dial.ships": "{n} ships, {c} crippled", "dial.noships": "no ships afloat", "dial.fair": "fair everywhere",
  "date.lobby": "Waiting for captains", "sub.left": "{n} months left", "sub.ended": "Final standings", "sub.lobby": "Before departure",
  "tape.sailed": "{who} sailed {origin} for {dest}", "tape.arrived": "{who} dropped anchor at {port}", "tape.offcourse": "{who} was blown off course",
  "tape.storm": "Storm damage to {who}'s fleet", "tape.lost": "{who} lost a ship", "tape.crippled": "A ship of {who} is crippled",
  "tape.wreck": "{who} was shipwrecked", "tape.battle": "Sea fight: {who}", "tape.won": "{who} won the fight", "tape.retreat": "{who} fled the fight",
  "tape.broke": "{who} broke off the fight", "tape.paid": "{who} bought off the pirates", "tape.plundered": "{who} was plundered",
  "tape.promotion": "{who} was promoted", "tape.band": "{who} changed standing in port", "tape.patron": "{who} became Patron of {port}",
  "tape.boom": "BOOM: {good} at {port}", "tape.crash": "CRASH: {good} at {port}", "tape.ban": "Ban in {port}", "tape.banlift": "Ban lifted in {port}",
  "tape.buy": "{who} bought {qty} {good} at {port}, {value}", "tape.sell": "{who} sold {qty} {good} at {port}, {value}", "tape.deal": "{who} moved {value} at {port}",
  "tape.news": "A house", "btn.hold": "Hold page", "btn.held": "Page held", "btn.next": "Next page", "btn.clicks": "Clicks", "btn.quit": "Quit",
  "conn.stale": "Waiting for the harbour...",
  "btn.spots": "Spotlights", "host.on": "On the line",
  "sp.battle": "Sea fight", "sp.lost": "Ship lost", "sp.storm": "Storm", "sp.plundered": "Plundered", "sp.boom": "Boom", "sp.crash": "Crash",
  "sp.promotion": "Promotion", "sp.patron": "Patron", "sp.ban": "Ban", "sp.banlift": "Ban lifted", "sp.arrival": "In port",
  "sp.lead": "New leader", "sp.pass": "Passed the ghost", "sp.fell": "Behind the ghost", "sp.finale": "Final standings",
  "sp.took": "{who} takes the lead", "sp.finale.head": "{who} wins with {worth}", "sp.pass.head": "{who} passes the {ghost}", "sp.fell.head": "{who} falls behind the {ghost}"
};
function W(key, vars) {
  const k = "dash." + key;
  const tpl = T[k] != null ? T[k] : (DEF[key] != null ? DEF[key] : key);
  return tpl.replace(/\{(\w+)\}/g, (m, n) => (vars && vars[n] != null ? vars[n] : m));
}
const We = (key, vars) => esc(W(key, vars));

let D = null, S = null, F = null, reloading = false, retryInfo, online = true;
let page = TABS ? "now" : "race", pageAt = Date.now(), held = false, lastFeed = 0, feeding = false, feedTimer = 0;
/* Watch Mode: on unless this screen turned it off; lastTouch is when the Captain last touched the screen;
   watchSkip is the tabs unticked in the drawer (kept on this device only). */
let watchOn = store("seatrader_dash_watch") !== "0", lastTouch = 0, watchSkip = TABS ? TABS.readSkip() : new Set();
const tabTitle = k => TABS ? TABS.tabName(k) : W("tab." + k);
let marketPort = null, marketLens = "price", detailKind = null;
let seenFights = null, seenBooms = null, tapeSeen = null, marketGood = null;
let clicksOn = store("seatrader_dash_clicks") === "1", actx = null;
let spotsOn = store("seatrader_dash_spots") !== "0";
const app = document.getElementById("app"), loading = document.getElementById("db-loading");
if (typeof DashTabs !== "undefined") app.classList.add("cc");      // the Command Center's full-width stage (dashboard.css)
const previous = new Map();

/* ---------------------------------------------------------------- helpers -- */
function update(id, html) {
  if (previous.get(id) === html) return null;
  const el = document.getElementById(id);
  el.innerHTML = html;
  previous.set(id, html);
  return el;
}
const pn = k => esc((D.ports[k] || {}).name || k || "");
const gn = k => esc((D.goods[k] || {}).name || k || "");
const hcol = h => COLORS[((h && h.color) || 0) % COLORS.length];
const house = id => (F.houses || []).find(h => h.id === id);
const firmOf = id => esc((house(id) || {}).firm || W("tape.news"));
function kfmt(n) {
  const a = Math.abs(n), s = n < 0 ? "-" : "";
  if (a >= 1e6) return s + (a / 1e6).toFixed(a >= 1e7 ? 0 : 1).replace(/\.0$/, "") + "M";
  if (a >= 1e3) return s + Math.round(a / 1e3) + "k";
  return s + Math.round(a);
}
const signed = n => (n >= 0 ? "+" : "-") + money(Math.abs(n)).replace(/^-/, "");
function dateOfTurn(t) {
  for (const h of F.houses) { const m = h.months.find(x => x.turn === t); if (m) return m.date; }
  return "";
}
const ranked = () => [...F.houses].sort((a, b) => b.worth - a.worth);
const solo = () => F.houses.length === 1;
const monthsTotal = () => (S && S.years ? S.years * 12 : 0);

/* One house's gain in each month it has a figure for: [{turn, date, gain}] */
function gainsOf(h) {
  const out = [];
  for (let i = 1; i < h.months.length; i++) {
    out.push({ turn: h.months[i].turn, date: h.months[i].date, gain: h.months[i].worth - h.months[i - 1].worth });
  }
  return out;
}

/* ---------------------------------------------------------------- the head -- */
function renderHead() {
  update("pw-brand", wordmarkHtml(brandName(D.brand)));
  const lobby = S.phase === "lobby", ended = S.phase === "ended";
  document.getElementById("pw-date").textContent = lobby ? W("date.lobby") : S.date || F.date || "";
  document.getElementById("pw-sub").textContent = lobby ? W("sub.lobby") : ended ? W("sub.ended") : W("sub.left", { n: S.turns_left });
  if (TABS) update("pw-context", TABS.contextHtml());
  renderLounge();
}

/* A woman lying back across the masthead. Any wallpaper (16:9) tagged "reclining" for Madame Anahit or Celeste the
   bookkeeper is used; a new one comes up about once a minute. With none in the library the masthead is just the banner.
   Make them with Queue_Masthead_Pictures.bat. */
let loungeId = "", loungeAt = 0;
function renderLounge() {
  const el = document.getElementById("pw-lounge");
  if (!el || (loungeId && Date.now() - loungeAt < 60000)) return;
  const pool = [];
  for (const cid of ["gamemaster", "bookkeeper"]) {
    try { for (const i of Media.items("persona", cid, "wallpaper", false, "masthead")) if ((i.g || []).some(t => /reclin|lying|laying|masthead-banner/i.test(t))) pool.push(i); } catch (e) { /* no library yet */ }
  }
  if (!pool.length) { el.innerHTML = ""; return; }
  /* Very wide banners (tag "masthead-banner", from Queue_Masthead_Banners.bat) take the whole masthead; if any exist
     they are preferred over the narrower reclining pictures, which keep their 640px spot. */
  const isBanner = i => (i.g || []).some(t => /masthead-banner/i.test(t)), banners = pool.filter(isBanner), use = banners.length ? banners : pool;
  const fresh = use.filter(i => i.id !== loungeId), item = (fresh.length ? fresh : use)[Math.floor(Math.random() * (fresh.length || use.length))];
  loungeId = item.id; loungeAt = Date.now();
  el.classList.toggle("wide", isBanner(item)); /* not "banner": style.css paints .banner jade green */
  el.innerHTML = `<img src="${esc(item.u)}" alt="">`;
}

function renderTabs() {
  if (TABS) {
    const el = update("pw-tabs", TABS.tabsHtml(page, F.locked));
    if (el) el.querySelector(".pw-tab.on")?.scrollIntoView?.({ block: "nearest", inline: "nearest" });
    return;
  }
  update("pw-tabs", PAGES.map(p => {
    const sealed = p.k === "markets" && F.locked;
    return `<button type="button" class="pw-tab${p.k === page ? " on" : ""}${sealed ? " sealed" : ""}" data-page="${p.k}"><i>${p.n}</i>${We("tab." + p.k)}<span class="pw-prog"></span></button>`;
  }).join(""));
}
document.getElementById("pw-tabs").addEventListener("click", e => {
  const b = e.target.closest("[data-page]");
  if (b) goto(b.dataset.page);
});

/* ---------------------------------------------------------------- tower -- */
function spark(values, color) {
  if (values.length < 2) return "";
  const w = 280, h = 26, lo = Math.min(...values), hi = Math.max(...values), span = hi - lo || 1;
  const pts = values.map((v, i) => `${(i / (values.length - 1) * w).toFixed(1)},${(h - 3 - (v - lo) / span * (h - 6)).toFixed(1)}`).join(" ");
  return `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-hidden="true"><polyline points="${pts}" fill="none" stroke="${color}" stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round"/></svg>`;
}

function ghostNow() {
  if (!F.ghost || !solo()) return null;
  const me = F.houses[0], i = Math.max(0, me.months.length - 1), c = F.ghost.curve;
  return c[Math.min(i, c.length - 1)];
}

function statusOf(h) {
  const fighting = (S.sea || []).some(f => f.firm === h.firm || f.pid === h.id);
  if (fighting) return { text: W("status.fight"), fight: true };
  const p = (S.players || []).find(x => x.id === h.id);
  if (p && p.present === false) return { text: W("status.away") };
  if (S.phase === "sea") return { text: W("status.sea") };
  return { text: W("status.port", { port: (D.ports[h.port] || {}).name || "" }) };
}

function towerHtml() {
  const hs = ranked(), lead = hs.length ? hs[0].worth : 0, rows = [];
  const g = ghostNow();
  const entries = hs.map(h => ({ h, worth: h.worth }));
  if (g != null) entries.push({ ghost: true, worth: g });
  entries.sort((a, b) => b.worth - a.worth);
  const top = entries.length ? entries[0].worth : 0;
  entries.forEach((e, i) => {
    if (e.ghost) {
      const label = F.ghost.kind === "best" ? W("ghost.best") : W("ghost.par");
      const behind = top - e.worth;
      rows.push(`<div class="tw-row ghost"><div class="tw-pos">&raquo;</div><div class="tw-bar"></div>
        <div class="tw-who"><b>${esc(label)}</b><span>${esc(F.ghost.date || "")}</span></div>
        <div class="tw-gap"><b class="${behind ? "" : "lead"}">${money(e.worth)}</b><span>${behind ? "-" + money(behind) : ""}</span></div></div>`);
      return;
    }
    const h = e.h, st = statusOf(h), gap = top - e.worth;
    const vals = h.months.slice(-24).map(m => m.worth);
    rows.push(`<div class="tw-row" style="--house:${hcol(h)}"><div class="tw-pos">${i + 1}</div><div class="tw-bar"></div>
      <div class="tw-who"><b>${esc(h.firm)}</b><span class="${st.fight ? "fight" : ""}">${esc(h.name || "")} &middot; ${esc(st.text)}</span></div>
      <div class="tw-gap"><b class="${gap ? "behind" : "lead"}">${gap ? "-" + money(gap) : We("leader")}</b><span>${money(e.worth)}</span></div>
      <div class="tw-spark">${spark(vals, hcol(h))}</div></div>`);
  });
  const foot = solo() ? (F.ghost && F.ghost.kind === "best" ? "" : W("tower.foot.par")) : W("tower.foot.n", { n: hs.length });
  return `<div class="tw-title"><span>${We("tower")}</span><b>${esc(S.date || "")}</b></div>
    <div class="tw-rows${hs.length > 5 ? " dense" : ""}">${rows.join("") || `<p class="pw-note" style="color:#a1b9af;padding:10px">${We("date.lobby")}</p>`}</div>
    ${foot ? `<div class="tw-foot">${esc(foot)}</div>` : ""}`;
}
/* The Command Center keeps the tower on the Career tab and the chalkboard on Now (the stage has the full width),
   so with it loaded the two side panels are not drawn. */
function renderTower() {
  document.getElementById("pw-tower").classList.toggle("solo", solo());
  if (!TABS) update("pw-tower", towerHtml());
}

/* ---------------------------------------------------------------- dials -- */
const DEG = a => a * Math.PI / 180;
function arc(r, a0, a1) {
  const p = a => [100 + r * Math.sin(DEG(a)), 104 - r * Math.cos(DEG(a))];
  const [x0, y0] = p(a0), [x1, y1] = p(a1);
  return `M${x0.toFixed(1)} ${y0.toFixed(1)} A${r} ${r} 0 ${a1 - a0 > 180 ? 1 : 0} 1 ${x1.toFixed(1)} ${y1.toFixed(1)}`;
}
function dialSvg(i, zones) {
  let s = `<svg viewBox="0 0 200 200" aria-hidden="true"><defs><radialGradient id="dface${i}" cx="50%" cy="40%"><stop offset="0" stop-color="#fbf0d4"/><stop offset="1" stop-color="#e2cfa4"/></radialGradient>
    <linearGradient id="dbrass${i}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f6d98c"/><stop offset=".5" stop-color="#b48a3a"/><stop offset="1" stop-color="#f0d48a"/></linearGradient></defs>
    <circle cx="100" cy="104" r="94" fill="url(#dbrass${i})"/><circle cx="100" cy="104" r="86" fill="url(#dface${i})" stroke="#385d64" stroke-width="2"/>`;
  zones.forEach((c, z) => { s += `<path d="${arc(74, -120 + z * 80, -120 + (z + 1) * 80 - 2)}" fill="none" stroke="${c}" stroke-width="9" stroke-linecap="butt" opacity=".85"/>`; });
  for (let t = 0; t <= 10; t++) {
    const a = DEG(-120 + t * 24), r0 = 60, r1 = t % 5 === 0 ? 50 : 54;
    s += `<line x1="${(100 + r0 * Math.sin(a)).toFixed(1)}" y1="${(104 - r0 * Math.cos(a)).toFixed(1)}" x2="${(100 + r1 * Math.sin(a)).toFixed(1)}" y2="${(104 - r1 * Math.cos(a)).toFixed(1)}" stroke="#1b2a33" stroke-width="${t % 5 === 0 ? 3 : 1.6}"/>`;
  }
  s += `<text id="dv${i}" x="100" y="150" text-anchor="middle" font-size="34" font-family="Georgia,serif" fill="#1b2a33"></text>
    <g class="needle" id="dn${i}" style="transform:rotate(-120deg)"><path d="M96 108 L100 28 L104 108 Z" fill="#1f5f7a"/></g>
    <circle cx="100" cy="104" r="9" fill="url(#dbrass${i})" stroke="#1b2a33" stroke-width="1.5"/></svg>`;
  return s;
}
const DIAL_ZONES = [
  ["#1f5c46", "#d6a84e", "#1f5f7a"],     // months left: the game runs out
  ["#1f5c46", "#d6a84e", "#1f5f7a"],     // barometer: fair to typhoon
  ["#1f5f7a", "#d6a84e", "#1f5c46"]      // hull: wrecked to sound
];
let dialsBuilt = false;
function buildDials() {
  if (dialsBuilt) return;
  document.getElementById("pw-dials").innerHTML = [0, 1, 2].map(i =>
    `<button type="button" class="dial" data-detail="${["voyage", "weather", "fleet"][i]}" aria-label="${We(["detail.voyage", "detail.weather", "detail.fleet"][i])}" title="${We("detail.hint")}">${dialSvg(i, DIAL_ZONES[i])}<b id="dt${i}"></b><span id="ds${i}"></span><small>${We("detail.hint")} &rarr;</small></button>`).join("");
  dialsBuilt = true;
}
function setDial(i, frac, value, title, sub) {
  const needle = document.getElementById("dn" + i);
  needle.style.transform = `rotate(${(-120 + Math.max(0, Math.min(1, frac)) * 240).toFixed(1)}deg)`;
  document.getElementById("dv" + i).textContent = value;
  document.getElementById("dt" + i).textContent = title;
  document.getElementById("ds" + i).textContent = sub;
}
function renderDials() {
  if (TABS) return;                 // retired: the context bar carries months left, the worst sea and the fleet's hull
  buildDials();
  // months left
  const total = monthsTotal(), left = S.turns_left == null ? 0 : S.turns_left, lobby = S.phase === "lobby";
  setDial(0, total ? (total - left) / total : 0, lobby ? "-" : String(left), W("dial.months"), total ? W("dial.of", { n: total }) : "");
  // barometer
  const lv = Object.entries(S.weather || {}), names = D.weather || [], top = Math.max(1, names.length - 1);
  let worst = 0, where = "";
  lv.forEach(([r, l]) => { if (l > worst) { worst = l; where = (D.regions[r] || {}).name || ""; } });
  setDial(1, worst / top, String(worst) + "/" + top, W("dial.baro"), worst ? `${names[worst] || ""}${where ? ", " + where : ""}` : W("dial.fair"));
  // fleet hull
  const ships = F.houses.flatMap(h => h.hull || []), crip = ships.filter(s => s.crippled).length;
  const avg = ships.length ? ships.reduce((a, s) => a + s.hull, 0) / ships.length : 0;
  setDial(2, avg, ships.length ? Math.round(avg * 100) + "%" : "-", W("dial.hull"), ships.length ? W("dial.ships", { n: ships.length, c: crip }) : W("dial.noships"));
}

const detailDialog = document.getElementById("pw-detail");
function renderDetail() {
  if (!detailKind || !F || !S || !D) return;
  let body = "";
  const own = TABS ? TABS.detail(detailKind) : null;       // an explanation a Command Center page owns (a route's odds)
  if (own) {
    update("detail-body", `<h2 id="detail-title">${esc(own.title)}</h2>${own.body}`);
    document.getElementById("detail-close").textContent = W("detail.close");
    return;
  }
  if (TABS && String(detailKind).includes(":")) { detailDialog.close(); return; }    // what it explained is gone
  if (detailKind === "weather") {
    body = `<p class="pw-note">${We("detail.scale")}</p><ul class="instrument-list">${Object.entries(S.weather || {}).sort((a, b) => b[1] - a[1]).map(([r, level]) => `<li><b>${esc((D.regions[r] || {}).name || r)}</b><span>${esc((D.weather || [])[level] || level)}</span><meter min="0" optimum="0" low="${Math.max(1, (D.weather || []).length - 1) / 3}" high="${Math.max(1, (D.weather || []).length - 1) * 2 / 3}" max="${Math.max(1, (D.weather || []).length - 1)}" value="${level}">${level}</meter></li>`).join("")}</ul>`;
  } else if (detailKind === "fleet") {
    body = `<ul class="instrument-list">${ranked().map(h => `<li><b>${esc(h.firm)}</b><span>${(h.hull || []).length ? (h.hull || []).map((sh, i) => `<span class="ship-condition">#${i + 1} · ${Math.round(sh.hull * 100)}% · ${We(sh.crippled ? "detail.crippled" : "detail.sound")}</span>`).join("") : We("dial.noships")}</span></li>`).join("")}</ul>`;
  } else {
    const total = monthsTotal(), left = S.turns_left == null ? total : S.turns_left;
    body = `<div class="voyage-numbers"><div><b>${Math.max(0, total - left)}</b><span>${We("detail.elapsed")}</span></div><div><b>${left}</b><span>${We("detail.remaining")}</span></div></div><progress max="${total || 1}" value="${Math.max(0, total - left)}"></progress><p>${esc(S.date || W("date.lobby"))}</p>`;
  }
  update("detail-body", `<h2 id="detail-title">${We("detail." + detailKind)}</h2>${body}`);
  document.getElementById("detail-close").textContent = W("detail.close");
}
document.getElementById("pw-dials").addEventListener("click", e => {
  const b = e.target.closest("[data-detail]");
  if (!b) return;
  detailKind = b.dataset.detail; renderDetail(); detailDialog.showModal();
});
document.getElementById("detail-close").addEventListener("click", () => detailDialog.close());
detailDialog.addEventListener("close", () => { detailKind = null; pageAt = Date.now(); });
document.getElementById("pw-book").addEventListener("change", e => {
  if (e.target.id !== "market-cargo") return;
  marketGood = e.target.value; pageAt = Date.now(); renderPage(false);
  document.getElementById("market-cargo").focus({ preventScroll: true });
});
document.getElementById("pw-book").addEventListener("click", e => {
  if (page !== "markets" || F.locked) return;
  const b = e.target.closest("[data-market-port], [data-port], [data-market-good], [data-market-lens], [data-market-back]");
  if (!b) return;
  if (b.hasAttribute("data-market-back")) marketPort = null;
  if (b.dataset.marketPort || b.dataset.port) marketPort = b.dataset.marketPort || b.dataset.port;
  if (b.dataset.marketGood && D.goods[b.dataset.marketGood]) {
    marketGood = b.dataset.marketGood;
    if (b.dataset.marketPort) marketLens = "price";
  }
  if (["price","change","weather"].includes(b.dataset.marketLens)) marketLens = b.dataset.marketLens;
  const pane = document.getElementById("pw-right").querySelector(".pg");
  if (pane && !b.dataset.marketLens) pane.scrollTop = 0;
  pageAt = Date.now(); renderPage(false);
  const target = b.dataset.marketLens ? `[data-market-lens="${marketLens}"]` : b.hasAttribute("data-market-back") ? "[data-market-port]" : "[data-market-back]";
  document.querySelector(target)?.focus({ preventScroll: true });
});

/* ---------------------------------------------------------------- chalkboard -- */
function chalkHtml() {
  const hs = ranked(), turns = [...new Set(hs.flatMap(h => gainsOf(h).map(g => g.turn)))].sort((a, b) => a - b).slice(-2);
  if (!turns.length) return `<div class="chalk"><h4>${We("chalk")}</h4><p class="none">${We("chalk.none")}</p><footer></footer></div>`;
  let champ = null;
  hs.forEach(h => gainsOf(h).forEach(g => { if (!champ || g.gain > champ.gain) champ = { ...g, firm: h.firm }; }));
  const head = `<tr><th></th>${turns.map(t => `<th>${esc(dateOfTurn(t))}</th>`).join("")}</tr>`;
  const body = hs.map(h => `<tr><td>${esc(h.firm)}</td>${turns.map(t => {
    const g = gainsOf(h).find(g => g.turn === t);
    return `<td class="${g && g.gain > 0 ? "pos" : g && g.gain < 0 ? "worst" : ""}">${g ? signed(g.gain) : "—"}</td>`;
  }).join("")}</tr>`).join("");
  return `<div class="chalk"><h4>${We("chalk")}</h4><div class="chalk-scroll"><table>${head}${body}</table></div><footer>${champ ? We("chalk.best", { date: champ.date, firm: champ.firm, gain: signed(champ.gain) }) : ""}</footer></div>`;
}
function renderChalk() { if (!TABS) update("pw-chalk", chalkHtml()); }

/* ---------------------------------------------------------------- the telegraph -- */
function tapeText(e) {
  const who = firmOf(e.pid), port = pn(e.port), v = { who, port, origin: pn(e.origin), dest: pn(e.dest), good: gn(e.good) };
  switch (e.type) {
    case "sailed": return W("tape.sailed", v);
    case "arrived": return W("tape.arrived", v);
    case "offcourse": return W("tape.offcourse", v);
    case "storm_damage": return W("tape.storm", v);
    case "ship_lost": return W("tape.lost", v);
    case "ship_crippled": return W("tape.crippled", v);
    case "shipwreck": return W("tape.wreck", v);
    case "battle": return W("tape.battle", v);
    case "won": return W("tape.won", v);
    case "retreat": return W("tape.retreat", v);
    case "broke_off": return W("tape.broke", v);
    case "paid": return W("tape.paid", v);
    case "plundered": return W("tape.plundered", v);
    case "promotion": return W("tape.promotion", v);
    case "band": return W("tape.band", v);
    case "patron": return W("tape.patron", v);
    case "windfall": case "shock": return W(e.sort === "crash" ? "tape.crash" : "tape.boom", v);
    case "ban": return W("tape.ban", v);
    case "ban_lifted": return W("tape.banlift", v);
    case "deal":
      v.qty = e.qty || ""; v.value = money(e.value);
      return W(e.deal === "buy" ? "tape.buy" : e.deal === "sell" ? "tape.sell" : "tape.deal", v);
    default: return "";
  }
}
const HOT = new Set(["battle", "plundered", "storm_damage", "shipwreck", "ship_lost", "ship_crippled", "retreat", "offcourse"]);
function tapeClick() {
  if (!clicksOn) return;
  try {
    actx = actx || new (window.AudioContext || window.webkitAudioContext)();
    const t = actx.currentTime;
    [0, .07, .16, .22].forEach(d => {
      const o = actx.createOscillator(), g = actx.createGain();
      o.type = "square"; o.frequency.value = 1700 + Math.random() * 400;
      g.gain.setValueAtTime(.045, t + d); g.gain.exponentialRampToValueAtTime(.0001, t + d + .03);
      o.connect(g); g.connect(actx.destination); o.start(t + d); o.stop(t + d + .04);
    });
  } catch (e) { /* no audio on this screen */ }
}
function renderTape() {
  const items = (F.tape || []).filter(e => tapeText(e)).slice(-TAPE_SHOW);
  const fresh = tapeSeen === null ? new Set() : new Set(items.filter(e => !tapeSeen.has(e.n)).map(e => e.n));
  tapeSeen = new Set([...(tapeSeen || []), ...items.map(e => e.n)]);
  const html = items.map(e => {
    const h = house(e.pid), cls = ["tp"];
    if (fresh.has(e.n)) cls.push("new");
    if (HOT.has(e.type) || e.sort === "crash") cls.push("hot"); else if (e.type === "won" || e.type === "promotion" || e.sort === "boom") cls.push("good");
    return `<div class="${cls.join(" ")}" style="--house:${h ? hcol(h) : "#1f5f7a"}"><span>${tapeText(e)}</span>${e.turn != null && dateOfTurn(e.turn) ? `<small>${esc(dateOfTurn(e.turn))}</small>` : ""}</div>`;
  }).join("");
  const el = update("pw-tape-track", html);
  if (el && fresh.size) tapeClick();
}

/* ---------------------------------------------------------------- the pages -- */
const stamp = (title, note) => `<div class="pw-stamp">${esc(title)}<small>${esc(note)}</small></div>`;

function raceChart(w, h) {
  const hs = F.houses.filter(x => x.months.length), g = F.ghost;
  if (!hs.length) return "";
  let t0 = Infinity, t1 = -Infinity, lo = 0, hi = 1;
  hs.forEach(x => x.months.forEach(m => { t0 = Math.min(t0, m.turn); t1 = Math.max(t1, m.turn); lo = Math.min(lo, m.worth); hi = Math.max(hi, m.worth); }));
  if (g) { t1 = Math.max(t1, t0 + g.curve.length - 1); g.curve.forEach(v => { lo = Math.min(lo, v); hi = Math.max(hi, v); }); }
  hi *= 1.06;
  const L = 56, R = 12, TOP = 12, B = 28;
  const x = t => L + (t - t0) / ((t1 - t0) || 1) * (w - L - R), y = v => TOP + (1 - (v - lo) / ((hi - lo) || 1)) * (h - TOP - B);
  let s = `<svg viewBox="0 0 ${w} ${h}" width="100%" role="img" aria-label="${esc(W("race.title"))}" style="display:block;overflow:visible">`;
  for (let i = 0; i <= 4; i++) {
    const v = lo + (hi - lo) * i / 4, yy = y(v);
    s += `<line x1="${L}" x2="${w - R}" y1="${yy.toFixed(1)}" y2="${yy.toFixed(1)}" stroke="#d6a84e" stroke-opacity=".25"/>
      <text x="${L - 6}" y="${(yy + 5).toFixed(1)}" text-anchor="end" font-size="14" fill="#c4b18d">${kfmt(v)}</text>`;
  }
  for (let i = 0; i <= 3; i++) {
    const t = Math.round(t0 + (t1 - t0) * i / 3), label = dateOfTurn(t) || ("M" + (t - t0));
    s += `<text x="${x(t).toFixed(1)}" y="${h - 6}" text-anchor="${i === 0 ? "start" : i === 3 ? "end" : "middle"}" font-size="13" fill="#c4b18d">${esc(label)}</text>`;
  }
  if (g) {
    s += `<polyline fill="none" stroke="#385d64" stroke-opacity=".55" stroke-width="3" stroke-dasharray="3 7" stroke-linecap="round" points="${g.curve.map((v, i) => x(t0 + i).toFixed(1) + "," + y(v).toFixed(1)).join(" ")}"/>`;
  }
  hs.forEach(hh => {
    const pts = hh.months.map(m => x(m.turn).toFixed(1) + "," + y(m.worth).toFixed(1)).join(" "), last = hh.months[hh.months.length - 1];
    s += `<polyline fill="none" stroke="${hcol(hh)}" stroke-width="4" stroke-linejoin="round" stroke-linecap="round" points="${pts}"/>
      <circle cx="${x(last.turn).toFixed(1)}" cy="${y(last.worth).toFixed(1)}" r="6" fill="${hcol(hh)}" stroke="#fff6dc" stroke-width="2"/>`;
  });
  return s + "</svg>";
}

function leadChanges() {
  const out = [];
  const hs = F.houses.filter(x => x.months.length);
  if (solo() && F.ghost && hs.length) {
    const me = hs[0], c = F.ghost.curve, name = F.ghost.kind === "best" ? W("ghost.best").toLowerCase() : W("ghost.par").toLowerCase();
    let prev = null;
    me.months.forEach((m, i) => {
      const ahead = m.worth > c[Math.min(i, c.length - 1)];
      if (prev !== null && ahead !== prev) out.push({ date: m.date, text: W(ahead ? "lead.passed" : "lead.fell", { who: esc(me.firm), ghost: esc(name) }), up: ahead });
      prev = ahead;
    });
    return out.reverse();
  }
  const turns = [...new Set(hs.flatMap(x => x.months.map(m => m.turn)))].sort((a, b) => a - b);
  let prev = null;
  turns.forEach(t => {
    const row = hs.map(x => ({ x, m: x.months.find(m => m.turn === t) })).filter(r => r.m).sort((a, b) => b.m.worth - a.m.worth);
    if (row.length < 2) return;
    const lead = row[0].x;
    if (prev && prev.id !== lead.id) out.push({ date: row[0].m.date, text: W("lead.took", { who: esc(lead.firm), from: esc(prev.firm) }), up: true, color: hcol(lead) });
    prev = lead;
  });
  return out.reverse();
}

function pageRace() {
  const hs = ranked();
  if (!hs.length) return { left: `<h2>${We("race.title")}<small>${We("date.lobby")}</small></h2><div class="pg"></div>`, right: `<h2>&nbsp;</h2><div class="pg"></div>` };
  const legend = hs.map(h => `<li style="--house:${hcol(h)}"><span class="pw-dot"></span><b>${esc(h.firm)}</b><span class="num">${money(h.worth)}</span></li>`).join("");
  const left = `<h2>${We("race.title")}<small>${We("race.sub")}</small></h2>
    <div class="pg"><div>${raceChart(520, 410)}</div>
    <ul class="pw-list">${legend}${F.ghost ? `<li><span class="pw-dot" style="background:transparent;border:2px dotted #385d64"></span><b>${esc(F.ghost.kind === "best" ? W("ghost.best") : W("ghost.par"))}</b><span class="num">${money(F.ghost.final)}</span></li>` : ""}</ul></div>`;
  const tower = TABS ? `<div class="pw-tower cc-tower${solo() ? " solo" : ""}">${towerHtml()}</div>` : "";
  const lc = leadChanges().slice(0, 6);
  const changes = lc.length ? `<ul class="pw-list">${lc.map(c => `<li style="grid-template-columns:1fr auto"><b class="${c.up ? "up" : "down"}">${c.text}</b><small>${esc(c.date)}</small></li>`).join("")}</ul>`
    : `<p class="pw-note">${We("race.nolead")}</p>`;
  let deals;
  if (F.locked) deals = `<div class="pw-block-locked">${stamp(W("sealed"), W("race.sealed"))}</div>`;
  else if (!(F.deals || []).length) deals = `<p class="pw-note">${We("race.nodeals")}</p>`;
  else deals = `<table><tbody>${F.deals.slice(0, 5).map(d => `<tr><td><span class="pw-dot" style="--house:${house(d.pid) ? hcol(house(d.pid)) : "#888"}"></span>${d.qty} ${gn(d.good)}<br><small class="pw-note">${pn(d.port)} &middot; ${esc(d.date)}</small></td><td class="num up">${signed(d.profit)}</td></tr>`).join("")}</tbody></table>`;
  const right = `<h2>${TABS ? esc(TABS.t("cc.race.stand")) : We("race.lead")}</h2><div class="pg">${tower}${tower ? `<h3 style="margin-top:8px">${We("race.lead")}</h3>` : ""}${changes}<h3 style="margin-top:8px">${We("race.deals")}</h3>${deals}</div>`;
  return { left, right };
}

/* The lanes: every voyage as an inked thread on the sea chart, thicker where sailed most. */
function laneTotals() {
  const map = {};
  F.houses.forEach(h => (h.lanes || []).forEach(l => {
    const k = l.origin + ">" + l.dest, r = map[k] || (map[k] = { origin: l.origin, dest: l.dest, count: 0, wrecks: 0, by: {} });
    r.count += l.count; r.wrecks += l.wrecks; r.by[h.id] = (r.by[h.id] || 0) + l.count;
  }));
  return Object.values(map).sort((a, b) => b.count - a.count);
}
function threads(lanes) {
  const hs = F.houses;
  let s = '<g class="pw-threads" style="pointer-events:none">';
  lanes.forEach(l => {
    const a = D.ports[l.origin], b = D.ports[l.dest];
    if (!a || !b || l.origin === l.dest) return;
    const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2, dx = b.x - a.x, dy = b.y - a.y, len = Math.hypot(dx, dy) || 1;
    hs.forEach((h, i) => {
      const n = l.by[h.id];
      if (!n) return;
      const bulge = 16 + (i - (hs.length - 1) / 2) * 12, cx = mx - dy / len * bulge, cy = my + dx / len * bulge;
      s += `<path d="M${a.x} ${a.y} Q${cx.toFixed(1)} ${cy.toFixed(1)} ${b.x} ${b.y}" fill="none" stroke="${hcol(h)}" stroke-opacity=".82" stroke-linecap="round" stroke-width="${(2.5 + Math.min(n, 9) * 1.4).toFixed(1)}"/>`;
    });
  });
  hs.forEach((h, i) => {
    const last = (h.legs || [])[(h.legs || []).length - 1], atSea = S.phase === "sea" && last && !last.arrived;
    let px, py;
    if (atSea && D.ports[last.origin] && D.ports[last.dest]) { px = (D.ports[last.origin].x + D.ports[last.dest].x) / 2; py = (D.ports[last.origin].y + D.ports[last.dest].y) / 2; }
    else if (D.ports[h.port]) { px = D.ports[h.port].x + (i - (hs.length - 1) / 2) * 22; py = D.ports[h.port].y - 26; }
    else return;
    s += `<g transform="translate(${px.toFixed(1)} ${py.toFixed(1)})"><circle r="13" fill="${hcol(h)}" stroke="#fff6dc" stroke-width="3"/><text y="5" text-anchor="middle" font-size="14" font-weight="700" fill="#fff">${esc(String(h.firm).charAt(0))}</text></g>`;
  });
  return s + "</g>";
}
/* Frames the chart on the ports (the trading waters are only a part of the whole chart), at 4:3. */
function cropChart(svg) {
  const ps = Object.values(D.ports || {});
  if (!ps.length) return svg;
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  ps.forEach(p => { x0 = Math.min(x0, p.x); x1 = Math.max(x1, p.x); y0 = Math.min(y0, p.y); y1 = Math.max(y1, p.y); });
  const pad = 70; x0 -= pad; x1 += pad; y0 -= pad; y1 += pad;
  let w = x1 - x0, h = y1 - y0;
  if (w / h < 4 / 3) { const nw = h * 4 / 3; x0 -= (nw - w) / 2; w = nw; } else { const nh = w * 3 / 4; y0 -= (nh - h) / 2; h = nh; }
  w = Math.min(w, 1000); h = Math.min(h, 600);
  x0 = Math.max(0, Math.min(1000 - w, x0)); y0 = Math.max(0, Math.min(600 - h, y0));
  return svg.replace('viewBox="0 0 1000 600"', `viewBox="${x0.toFixed(0)} ${y0.toFixed(0)} ${w.toFixed(0)} ${h.toFixed(0)}"`);
}
function withOverlay(svg, overlay) {
  return /<\/svg>\s*$/.test(svg) ? svg.replace(/<\/svg>\s*$/, overlay + "</svg>") : svg + overlay;
}
function pageLanes() {
  const lanes = laneTotals();
  const chart = withOverlay(cropChart(Chart.svg({ data: D, players: S.players, crackdown: S.crackdown || [], weather: S.weather, hideWeather: false, hideRose: true })), threads(lanes));
  const left = `<h2>${We("lanes.title")}<small>${We("lanes.sub")}</small></h2><div class="pg"><div class="chart-wrap" id="dash-chart">${chart}</div>
    ${lanes.length ? `<ul class="pw-list">${ranked().map(h => {
      const n = (h.lanes || []).reduce((a, l) => a + l.count, 0), w = (h.lanes || []).reduce((a, l) => a + l.wrecks, 0);
      return `<li style="--house:${hcol(h)};grid-template-columns:auto 1fr auto"><span class="pw-dot"></span><b>${esc(h.firm)}</b><span class="num">${We(n === 1 ? "lanes.time" : "lanes.times", { n })}${w ? ` &middot; &#9875; ${w}` : ""}</span></li>`;
    }).join("")}</ul>` : `<p class="pw-note">${We("lanes.none")}</p>`}</div>`;
  const max = lanes.length ? lanes[0].count : 1;
  const busiest = lanes.slice(0, 6).map(l => {
    const profit = F.locked ? "" : (F.lane_profit || {})[l.origin + ">" + l.dest];
    return `<li style="grid-template-columns:1fr auto"><div><b>${pn(l.origin)} &rarr; ${pn(l.dest)}</b>${l.wrecks ? ` <small>&#9875; ${l.wrecks}</small>` : ""}
      <div class="pw-bar"><i style="width:${Math.max(6, l.count / max * 100)}%"></i></div></div>
      <span class="num"><b>${l.count === 1 ? We("lanes.time") : We("lanes.times", { n: l.count })}</b>${profit != null && profit !== "" ? `<br><small class="${profit >= 0 ? "up" : "down"}">${signed(profit)}</small>` : ""}</span></li>`;
  }).join("");
  const now = ranked().map(h => {
    const last = (h.legs || [])[(h.legs || []).length - 1], atSea = S.phase === "sea" && last && !last.arrived;
    const text = atSea ? W("now.sea", { origin: pn(last.origin), dest: pn(last.dest) }) : W("now.port", { port: pn(h.port) });
    return `<li style="grid-template-columns:auto 1fr"><span class="pw-dot" style="--house:${hcol(h)}"></span><span><b>${esc(h.firm)}</b><br><small>${text}</small></span></li>`;
  }).join("");
  const right = `<h2>${We("lanes.busiest")}</h2><div class="pg">${lanes.length ? `<ul class="pw-list">${busiest}</ul>` : `<p class="pw-note">${We("lanes.none")}</p>`}
    ${F.locked ? `<p class="pw-note">${We("lanes.sealed")}</p>` : ""}<h3 style="margin-top:8px">${We("lanes.now")}</h3><ul class="pw-list">${now}</ul></div>`;
  return { left, right, fit: "dash-chart" };
}

/* Markets: open level only. A heat-map of one cargo, a movers board, the booms and crashes. */
function priceRows() {
  const out = [];
  Object.entries(F.ports || {}).forEach(([k, p]) => Object.entries(p.prices || {}).forEach(([g, price]) => {
    const base = (p.base || {})[g] || price;
    out.push({ port: k, good: g, price, base, pct: base ? (price - base) / base : 0 });
  }));
  return out;
}
const marketEffects = () => F.locked ? [] : F.market_effects || [];
const marketBanned = (port, good) => ((S.bans || {})[port] || []).includes(good);
const marketPct = r => (r.pct >= 0 ? "+" : "") + Math.round(r.pct * 100) + "%";
function marketMetrics(rows, good, lens) {
  const selected = rows.filter(r => r.good === good), maxPrice = Math.max(1, ...selected.map(r => r.price));
  const maxChange = Math.max(.01, ...selected.map(r => Math.abs(r.pct))), maxWeather = Math.max(1, (D.weather || []).length - 1);
  const intel = {};
  Object.entries(D.ports).forEach(([port, p]) => {
    const row = selected.find(r => r.port === port), wx = (S.weather || {})[p.region] || 0;
    const events = marketEffects().filter(w => w.port === port && w.good === good);
    const banned = marketBanned(port, good);
    const value = lens === "weather" ? (D.weather || [])[wx] || "—" : !row ? "—" : lens === "change" ? marketPct(row) : money(row.price);
    intel[port] = { value: value + (banned ? " · ×" : events.length ? " · ✦" : ""),
      fill: lens === "weather" ? wx / maxWeather : !row ? 0 : lens === "change" ? Math.abs(row.pct) / maxChange : row.price / maxPrice,
      negative: banned || (lens === "weather" ? wx >= 2 : lens === "change" && row && row.pct < 0),
      positive: !banned && lens === "change" && row && row.pct > 0,
      title: `${p.name}: ${value}${banned ? "; " + W("mk.banned") : ""}${events.map(w => "; " + W(w.sort === "crash" ? "mk.crash" : "mk.boom") + " ×" + w.mult + ", " + W(w.turns === 1 ? "mk.leftone" : "mk.left", { n: w.turns })).join("")}` };
  });
  return intel;
}
function effectButtons(effects) {
  if (!effects.length) return `<p class="pw-note">${We("mk.noactive")}</p>`;
  return `<div class="market-effects">${effects.map(w => `<button type="button" data-market-good="${esc(w.good)}" data-market-port="${esc(w.port)}"><span class="${w.sort === "crash" ? "down" : "up"}">${We(w.sort === "crash" ? "mk.crash" : "mk.boom")} · ${gn(w.good)}</span><b>${pn(w.port)} <em>×${w.mult}</em></b><small>${We(w.turns === 1 ? "mk.leftone" : "mk.left", { n: w.turns })}</small></button>`).join("")}</div>`;
}
function marketPortDetail(rows, port, good) {
  const p = D.ports[port], chosen = rows.find(r => r.port === port && r.good === good);
  const wx = (S.weather || {})[p.region] || 0, banned = marketBanned(port, good);
  const facts = [[W("mk.quote"), chosen ? money(chosen.price) : "—"], [W("mk.basemovers"), chosen ? marketPct(chosen) : "—"], [W("mk.weather"), (D.weather || [])[wx] || "—"], [W("mk.status"), W(banned ? "mk.banned" : "mk.open")]];
  return `<section class="market-port-detail" aria-label="${We("mk.intel")}"><div class="market-detail-head"><span>${gn(good)}</span><button type="button" data-market-back>${We("mk.all")}</button></div><dl>${facts.map(([k,v]) => `<div><dt>${esc(k)}</dt><dd${k === W("mk.status") && banned ? ' class="market-ban"' : ""}>${esc(v)}</dd></div>`).join("")}</dl>${(S.crackdown || []).includes(port) ? `<p class="market-warning">${We("mk.customs")}</p>` : ""}<h3>${We("mk.active")}</h3>${effectButtons(marketEffects().filter(w => w.port === port))}<h3>${We("mk.cargos")}</h3><div class="port-quotes">${rows.filter(r => r.port === port).map(r => `<button type="button" data-market-good="${esc(r.good)}" aria-pressed="${r.good === good}"><span>${gn(r.good)}${marketBanned(port,r.good) ? " ×" : ""}</span><b>${money(r.price)}<small class="${r.pct < 0 ? "down" : "up"}">${marketPct(r)}</small></b></button>`).join("")}</div></section>`;
}
function pageMarkets() {
  if (F.locked) return { left: `<h2>${We("mk.title")}</h2><div class="pg">${stamp(W("sealed"), W("sealed.note"))}</div>`, right: `<h2>&nbsp;</h2><div class="pg">${stamp(W("sealed"), W("sealed.note"))}</div>` };
  const rows = priceRows(), goods = Object.keys(D.goods);
  if (marketGood === null || !D.goods[marketGood]) {
    const big = rows.slice().sort((a, b) => Math.abs(b.pct) - Math.abs(a.pct))[0];
    marketGood = big ? big.good : goods[0];
  }
  const good = marketGood, ofGood = rows.filter(r => r.good === good);
  const legal = ofGood.filter(r => !marketBanned(r.port, good)).sort((a, b) => a.price - b.price);
  const low = legal[0], high = legal[legal.length - 1];
  let chart = cropChart(Chart.svg({ data: D, players: [], crackdown: S.crackdown || [], hideWeather: true, hideRose: true, clickable: true, intel: marketMetrics(rows,good,marketLens) }));
  chart = chart.replace(/class="port-name"/g, 'class="port-name" dy="-4"').replace(/class="intel-value port-status"/g, 'class="intel-value port-status" dy="4"').replace(/height="64"/g, 'height="76"');
  chart = chart.replace(/(<g\b[^>]*data-port="([^"]+)"[^>]*aria-pressed=")false/g, (all, start, port) => port === marketPort ? start + "true" : all);
  const selector = `<label class="cargo-picker">${We("mk.cargo")}<select id="market-cargo">${goods.map(g => `<option value="${esc(g)}"${g === good ? " selected" : ""}>${gn(g)}</option>`).join("")}</select></label>`;
  const layers = `<nav class="market-lenses" aria-label="${We("mk.layer")}">${["price","change","weather"].map(lens => `<button type="button" data-market-lens="${lens}" aria-pressed="${marketLens === lens}">${We("mk."+lens)}</button>`).join("")}</nav>`;
  const summary = low && high ? `<div class="market-summary"><div><small>${We("mk.buy")}</small><b>${money(low.price)}</b><span>${pn(low.port)}</span></div><div><small>${We("mk.sell")}</small><b>${money(high.price)}</b><span>${pn(high.port)}</span></div><div><small>${We("mk.spread")}</small><b>${money(high.price-low.price)}</b><span>${gn(good)}</span></div></div>` : `<p class="pw-note">${We("mk.empty")}</p>`;
  const left = `<h2>${We("mk.intel")}<small>${We("mk.inspect")}</small></h2><div class="pg market-map">${selector}${layers}<div class="chart-wrap" id="dash-chart">${chart}</div><p class="pw-note market-key">${We("mk."+marketLens+"key")}</p>${summary}<p class="pw-note">${We("mk.legal")}</p></div>`;
  const quotes = `<div class="port-quotes">${ofGood.slice().sort((a,b) => a.price-b.price).map(r => `<button type="button" data-market-port="${esc(r.port)}"><span>${pn(r.port)}${marketBanned(r.port,good) ? " ×" : ""}</span><b>${money(r.price)}</b></button>`).join("")}</div>`;
  const movers = rows.slice().sort((a,b) => Math.abs(b.pct)-Math.abs(a.pct)).slice(0,3);
  const moverHtml = `<div class="market-effects">${movers.map(r => `<button type="button" data-market-good="${esc(r.good)}" data-market-port="${esc(r.port)}"><b>${gn(r.good)} <em class="${r.pct < 0 ? "down" : "up"}">${marketPct(r)}</em></b><small>${pn(r.port)}</small></button>`).join("")}</div>`;
  const history = (F.booms || []).slice().reverse().slice(0,4);
  const historyHtml = history.length ? `<details class="market-history"><summary>${We("mk.history")}</summary>${history.map(w => `<p><b>${gn(w.good)} · ${pn(w.port)}</b><br><small>${esc(w.date)} · ${We("mk.expired")} · ×${w.mult}</small></p>`).join("")}</details>` : "";
  const selected = marketPort && D.ports[marketPort];
  const right = selected ? `<h2>${pn(marketPort)}</h2><div class="pg">${marketPortDetail(rows,marketPort,good)}</div>` : `<h2>${We("mk.active")}</h2><div class="pg">${effectButtons(marketEffects())}<h3>${We("mk.quotes")}</h3>${quotes}<h3>${We("mk.basemovers")}</h3>${moverHtml}<p class="pw-note">${We("mk.baseline")}</p>${historyHtml}</div>`;
  return { left, right, fit: "dash-chart" };
}

const BUILDERS = Object.assign({ race: pageRace, lanes: pageLanes, markets: pageMarkets }, TABS ? TABS.BUILDERS : {});
function renderPage(flip) {
  const scrolls = ["pw-left", "pw-right"].map(id => document.getElementById(id).querySelector(".pg")?.scrollTop || 0);
  document.getElementById("pw-book").dataset.page = page;
  document.getElementById("pw-book").dataset.sub = TABS ? TABS.subOf(page) : "";
  const b = BUILDERS[page]();
  const l = update("pw-left", b.left), r = update("pw-right", b.right);
  if (!flip) ["pw-left", "pw-right"].forEach((id,i) => { const pg = document.getElementById(id).querySelector(".pg"); if (pg) pg.scrollTop = scrolls[i]; });
  if (b.fit && typeof Chart.fit === "function") {
    const el = document.getElementById(b.fit);
    if (el && (l || r)) Chart.fit(el);
  }
  if (flip) ["pw-left", "pw-right"].forEach(id => { const el = document.getElementById(id); el.classList.remove("flip"); void el.offsetWidth; el.classList.add("flip"); });
}

/* ---------------------------------------------------------------- turning the book -- */
/* Every tab stays in the bar with rivals at the table; a page that needs private figures shows the Sealed stamp. */
function available() { return PAGES.map(p => p.k).filter(k => TABS || !(k === "markets" && F && F.locked)); }
const dashBusy = () => !!detailKind || (typeof DashWhisper !== "undefined" && DashWhisper.isOpen()) || !!document.getElementById("pw-drawer")?.open;
const watchState = () => ({ on: watchOn, held, busy: dashBusy(), hidden: !!document.hidden, pageAt, lastTouch });
const touching = () => !!TABS && Date.now() - lastTouch < IDLE_MS;
function goto(k, why) {
  if (!BUILDERS[k] || !F) return;
  if (k === "markets") marketGood = null;          // a fresh cargo each time the page comes round
  const changed = k !== page;
  page = k; pageAt = Date.now();
  document.title = brandName(D.brand) + " · " + tabTitle(page);
  renderTabs(); renderHost();
  renderPage(changed);
}
/* auto: Watch Mode's own turn, which tours only the tabs left ticked in the drawer. A turn by hand visits them all. */
function turnPage(step, auto) {
  const list = auto && TABS ? TABS.tour(watchSkip) : available(), i = list.indexOf(page);
  const next = list[((i < 0 ? -1 : i) + (step || 1) + list.length) % list.length];
  if (auto && TABS) TABS.lap(next);          // a tab with pages of its own shows the next of them on each lap
  goto(next);
}
setInterval(() => {
  if (!F) return;
  const bar = document.querySelector(".pw-tab.on .pw-prog"), now = Date.now();
  if (!TABS) {
    if (bar) bar.style.width = held ? "100%" : Math.min(100, (now - pageAt) / TURN_MS * 100) + "%";
    if (!held && !dashBusy() && now - pageAt >= TURN_MS) turnPage(1);
    return;
  }
  /* Watch Mode: a touch holds the page for IDLE_MS; a dialog, a pinned tab or a hidden window holds it for as long
     as it lasts. Nothing is redrawn or turned while the window is hidden. */
  const st = watchState(), due = TABS.dueAt(st), pr = TABS.progress(st, now);
  if (bar) bar.style.width = (pr.frac * 100).toFixed(1) + "%";
  const note = document.getElementById("pw-watch-note");
  if (note && note.textContent !== pr.note) note.textContent = pr.note;
  if (due !== null && now >= due) turnPage(1, true);
}, 500);

/* A fight, a boom or a crash that was not there a moment ago pulls the book to the page that shows it. */
function watchJumps() {
  const fights = new Set((S.sea || []).map(f => f.id)), booms = new Set((F.booms || []).map(w => [w.turn, w.port, w.good, w.sort].join("|")));
  if (seenFights === null) { seenFights = fights; seenBooms = booms; return; }
  const newFight = [...fights].some(id => !seenFights.has(id)), newBoom = [...booms].some(k => !seenBooms.has(k));
  seenFights = fights; seenBooms = booms;
  if (held || dashBusy() || touching()) return;     // never pulls the page from under a Captain who is reading it
  if (newFight) goto(TABS ? "fleet" : "lanes");                       // a battle first: the game itself holds for fights
  else if (newBoom && !F.locked) goto("markets");
}


/* ---------------------------------------------------------------- the cast --
   Every moment of the race has a woman to go with it. One stands on the line all the time (the host card under the
   tower, who changes with the page) and when something big happens she steps forward: a spotlight takes the whole
   book for ten seconds, her picture (portrait, a clip if she has one; never a wallpaper or masthead scene) full height, F1 style
   lower third, her line. All from public facts, so it is safe with rivals at the table. Pictures follow the game's
   Family-friendly switch because they come from the same Media Library. Lines are written in the house voice, with
   a clean twin for Family-friendly screens. */
let CAST = {};
const FALLBACK_WHO = {
  gamemaster: ["Madame Anahit Sarkissian", "Mistress of the Table & Queen of the Hour", "#b48cf0"],
  narrator: ["Roxana Cama", "First Mate & Queen of the Black Log", "#d6a84e"],
  bookmaker: ["Isabel “Fan-Tan Bella” da Rocha", "Bookmaker of the Golden Fan", "#e0705a"],
  pirate: ["Admiral Li Yue", "Pirate Queen of the South China Sea", "#d0644f"],
  bosun: ["Patrick “Powder” O’Rourke", "Bosun & Master Gunner", "#e0a050"],
  taxlady: ["Mrs. Evelyn Marlowe", "Registrar of the Merchant Houses", "#7fc4a2"],
  crier: ["Tommy Marsh", "Gazette Crier & Keeper of Rumours", "#d8e7dc"],
  mayor: ["The Mayor", "Mayor of the Port", "#d6a84e"]
};
function who(cid) {
  const c = CAST[cid] || {}, f = FALLBACK_WHO[cid] || [cid, "", "#d6a84e"];
  return { cid, name: c.name || f[0], title: c.title || f[1], color: /^#[0-9a-f]{3,8}$/i.test(c.color || "") ? c.color : f[2] };
}
const cleanScreen = () => { try { return screenFamily() || Media.family(); } catch (e) { return false; } };
const fill = (tpl, v) => tpl.replace(/\{(\w+)\}/g, (m, n) => (v && v[n] != null ? v[n] : m));

/* kind: [who, tag key, priority, ms, [spicy, clean] lines]. Higher priority goes first; low ones are dropped if stale. */
const SAY = {
  battle: { who: ["pirate", "bosun"], pri: 9, ms: 10000, lines: [
    ["{who} has wandered into my waters. I do so enjoy company that struggles.", "{who} has wandered into my waters. I do enjoy company that puts up a fight."],
    ["Load her up, lads. {who} wants it rough, and Powder never disappoints.", "Load her up, lads. {who} wants a fight, and Powder never disappoints."]] },
  lost: { who: ["narrator"], fb: ["bosun", "pirate"], pri: 8, ms: 9500, lines: [
    ["Down she goes, {who}'s pride and joy. I'll write her slowly into the Black Log.", "Down she goes, {who}'s pride and joy. I'll write her gently into the Black Log."]] },
  plundered: { who: ["pirate"], fb: ["bosun"], pri: 7, ms: 9000, lines: [
    ["Plundered, {who}. Don't pout, darling; it's only cargo.", "Plundered, {who}. Don't sulk; it's only cargo."]] },
  lead: { who: ["gamemaster"], fb: ["taxlady", "mayor"], pri: 7, ms: 10000, lines: [
    ["Darlings, the lead changes hands, and not gently. {who} takes the throne.", "Ladies and gentlemen, the lead changes hands. {who} takes the throne."]] },
  pass: { who: ["gamemaster"], fb: ["taxlady", "mayor"], pri: 6, ms: 9000, lines: [
    ["{who} has passed the old champion in front of everyone. How brazen.", "{who} has passed the old champion in front of everyone."]] },
  fell: { who: ["gamemaster"], fb: ["taxlady", "mayor"], pri: 5, ms: 8500, lines: [
    ["{who} slips behind the ghost. Chin up, darling; the night is young.", "{who} slips behind the ghost. Chin up; the night is young."]] },
  boom: { who: ["bookmaker"], fb: ["comprador", "banker"], pri: 6, ms: 9000, lines: [
    ["Mmm, the whole {port} floor is panting over {good}. Place your bets, sweetheart.", "The whole {port} floor is buzzing over {good}. Place your bets, Captains."]] },
  crash: { who: ["bookmaker"], fb: ["comprador", "banker"], pri: 6, ms: 9000, lines: [
    ["{good} at {port} has dropped everything. Poor lambs. Bella will hold what's left.", "{good} at {port} has dropped like a stone. Poor lambs. Bella will mind what's left."]] },
  promotion: { who: ["taxlady"], fb: ["mayor"], pri: 6, ms: 9000, lines: [
    ["Congratulations, {who}. Do come by; I so enjoy a firm stamp on clean paper.", "Congratulations, {who}. Do come by and I'll stamp your papers."]] },
  patron: { who: ["mayor"], fb: ["taxlady"], pri: 4, ms: 8500, lines: [
    ["{who} is now Patron of {port}. The harbour is yours, and so is my attention.", "{who} is now Patron of {port}. The harbour is yours."]] },
  storm: { who: ["narrator"], fb: ["bosun", "pirate"], pri: 5, ms: 9000, lines: [
    ["The sea has taken a rough bite out of {who}. She never was gentle.", "The sea has taken a rough bite out of {who}. She is never gentle."]] },
  ban: { who: ["crier"], fb: ["mayor", "taxlady"], pri: 3, ms: 8000, lines: [
    ["Hear it, hear it! {port} has slammed its doors, and not everyone is invited in.", "Hear ye! {port} has closed its doors to the trade."]] },
  banlift: { who: ["crier"], fb: ["mayor", "taxlady"], pri: 3, ms: 8000, lines: [
    ["{port} has thrown its doors open again. Come in, come in, everyone.", "{port} has opened its doors again. Come in, everyone."]] },
  arrival: { who: ["@officer"], pri: 2, ms: 7500, lines: [
    ["Welcome to {port}, {who}. Declare everything. I will know if you don't.", "Welcome to {port}, {who}. Declare everything; I will know."]] },
  finale: { who: ["gamemaster"], fb: ["taxlady", "mayor"], pri: 10, ms: 16000, lines: [
    ["The ledger closes. {who} takes the night with {worth}. Take a bow, darling.", "The ledger closes. {who} takes the night with {worth}. Take a bow."]] }
};
const HOSTS = { race: "gamemaster", lanes: "narrator", markets: "bookmaker" };
const HOST_FB = { race: ["taxlady", "mayor", "bookkeeper"], lanes: ["bosun", "pirate"], markets: ["comprador", "banker", "lender"] };
/* A woman with no pictures yet is stood in for by the next one who has some, so the stage is never an empty frame. */
const hasArt = cid => { try { return Media.has("persona", cid, "", {}); } catch (e) { return false; } };
const withArt = (list, fb) => { const a = list.filter(hasArt); if (a.length) return a; const b = (fb || []).filter(hasArt); return b.length ? b : list; };
const pick = a => a[Math.floor(Math.random() * a.length)];
const lineOf = pair => pair[cleanScreen() ? 1 : 0];
const monogram = name => (name.replace(/[^\p{L} ]/gu, "").split(" ").filter(Boolean).slice(0, 2).map(w => w[0]).join("") || "?").toUpperCase();

function art(cid, roles, cls, slot) {
  let pic = "";
  for (const r of roles) { if (Media.has("persona", cid, r, { strict: true, video: true })) { pic = Media.html("persona", cid, r, cls, "", { video: true, strict: true, slot }); break; } }
  if (!pic) pic = Media.html("persona", cid, "portrait", cls, "", { video: true, slot });
  return pic;
}

function renderHost() {
  const ended = S.phase === "ended";
  const tab = TABS && !ended ? PAGES.find(p => p.k === page) : null;
  const host = tab ? tab.host : HOSTS[ended ? "race" : page] || HOSTS.race;
  const w = who(withArt([ended ? "gamemaster" : host], tab ? tab.fb : HOST_FB[ended ? "race" : page] || HOST_FB.race)[0]);
  const pic = art(w.cid, [F.brief?.mood || "portrait", "portrait", "speaking"], "ho-pic", "dash-host");
  document.getElementById("pw-host").setAttribute("aria-label", w.name);
  update("pw-host", `<div class="ho-art" style="--who:${w.color}">${pic || `<span class="ho-mono">${esc(monogram(w.name))}</span>`}</div><div class="ho-shade"></div>`);
  if (typeof DashWhisper !== "undefined") DashWhisper.sync(F.brief, w.cid, { blocked: !online || !!spotNow || detailDialog.open });
}

/* ---- the spotlight ---- */
let spotQ = [], spotNow = null, spotEnd = 0, spotFree = 0, lastSpotAt = 0, stageSeen = null, lastLeader = null, lastAhead = null, finaleFor = null, officerTurn = {};
function raw(id) { const h = house(id); return h ? h.firm : W("tape.news"); }
function enqueue(s) {
  if (!spotsOn || !s || !SAY[s.kind]) return;
  s.at = Date.now(); s.pri = SAY[s.kind].pri;
  if (spotQ.some(q => q.key === s.key) || (spotNow && spotNow.key === s.key)) return;
  spotQ.push(s);
  spotQ.sort((a, b) => b.pri - a.pri || a.at - b.at);
  spotQ = spotQ.slice(0, 4);
}
function fromTape(e) {
  const v = { who: raw(e.pid), port: (D.ports[e.port] || {}).name || e.port || "", good: (D.goods[e.good] || {}).name || e.good || "", head: tapeText(e) };
  let kind = "";
  switch (e.type) {
    case "battle": kind = "battle"; break;
    case "shipwreck": case "ship_lost": kind = "lost"; break;
    case "plundered": kind = "plundered"; break;
    case "storm_damage": case "offcourse": kind = "storm"; break;
    case "windfall": case "shock": kind = e.sort === "crash" ? "crash" : "boom"; break;
    case "promotion": kind = "promotion"; break;
    case "patron": kind = "patron"; break;
    case "ban": kind = "ban"; break;
    case "ban_lifted": kind = "banlift"; break;
    case "arrived": kind = "arrival"; v.officer = "officer_" + e.port; break;
    default: return null;
  }
  return { kind, key: "t" + e.n, vars: v, pid: e.pid };
}
function watchStage() {
  if (!D || !F) return;
  const items = F.tape || [], hs = ranked(), top = hs[0];
  if (stageSeen === null) {
    stageSeen = new Set(items.map(e => e.n)); lastLeader = top ? top.id : null;
    const g = ghostNow(); lastAhead = solo() && g != null && top ? top.worth > g : null;
    return;
  }
  items.forEach(e => { if (stageSeen.has(e.n)) return; stageSeen.add(e.n); const s = fromTape(e); if (s) enqueue(s); });
  if (hs.length > 1 && top && lastLeader && top.id !== lastLeader && S.phase !== "ended") {
    const prev = house(lastLeader);
    enqueue({ kind: "lead", key: "lead" + top.id + "@" + S.turns_left, vars: { who: top.firm, from: prev ? prev.firm : "", head: W("sp.took", { who: top.firm }) }, pid: top.id });
  }
  if (top) lastLeader = top.id;
  const g = ghostNow();
  if (solo() && g != null && top) {
    const ahead = top.worth > g;
    if (lastAhead !== null && ahead !== lastAhead) {
      const gh = F.ghost.kind === "best" ? W("ghost.best").toLowerCase() : W("ghost.par").toLowerCase();
      enqueue({ kind: ahead ? "pass" : "fell", key: (ahead ? "pass" : "fell") + "@" + S.turns_left, vars: { who: top.firm, ghost: gh, head: W(ahead ? "sp.pass.head" : "sp.fell.head", { who: top.firm, ghost: gh }) }, pid: top.id });
    }
    lastAhead = ahead;
  }
  if (S.phase === "ended" && top && finaleFor !== F.game_id) {
    finaleFor = F.game_id;
    enqueue({ kind: "finale", key: "finale" + F.game_id, vars: { who: top.firm, worth: money(top.worth), head: W("sp.finale.head", { who: top.firm, worth: money(top.worth) }) }, pid: top.id });
  }
}
function showSpot(s) {
  const def = SAY[s.kind];
  let cid = pick(def.who.includes("@officer") ? def.who : withArt(def.who, def.fb));
  if (cid === "@officer") cid = CAST[s.vars.officer] ? s.vars.officer : "mayor";
  const w = who(cid), line = fill(lineOf(pick(def.lines)), s.vars);
  const h = house(s.pid), stripe = h ? hcol(h) : w.color;
  const pic = art(cid, ["portrait", "speaking"], "sp-pic", "dash-spot");
  const el = document.getElementById("pw-spot");
  el.style.setProperty("--who", w.color); el.style.setProperty("--house", stripe);
  el.className = "pw-spot k-" + s.kind;
  el.innerHTML = `<div class="sp-art">${pic || `<span class="sp-mono">${esc(monogram(w.name))}</span>`}</div><div class="sp-shade"></div>
    <div class="sp-tag"><i></i><b>${We("sp." + s.kind)}</b></div>
    <h3 class="sp-head">${esc(s.vars.head || "")}</h3>
    <blockquote class="sp-line">${esc(line)}</blockquote>
    <div class="sp-plate"><small>${esc(w.title)}</small><b>${esc(w.name)}</b></div>
    <div class="sp-clock"><i style="animation-duration:${def.ms}ms"></i></div>`;
  el.hidden = false; void el.offsetWidth; el.classList.add("on");
  spotNow = s; spotEnd = Date.now() + def.ms;
  tapeClick();
}
function endSpot() {
  const el = document.getElementById("pw-spot");
  el.classList.remove("on"); el.classList.add("off");
  setTimeout(() => { if (!spotNow) { el.hidden = true; el.className = "pw-spot"; el.innerHTML = ""; } }, 700);
  spotNow = null; lastSpotAt = Date.now(); spotFree = lastSpotAt + 4000;
}
function runSpots() {
  const now = Date.now();
  if (spotNow) { if (now >= spotEnd || !spotsOn) endSpot(); return; }
  spotQ = spotQ.filter(s => now - s.at < (s.pri >= 6 ? 60000 : 25000));
  if (!spotsOn) { spotQ = []; return; }
  if (!spotQ.length || now < spotFree || !F || detailKind || typeof DashWhisper !== "undefined" && DashWhisper.isOpen()) return;
  const s = spotQ.shift();
  if (s.pri <= 2 && now - lastSpotAt < 40000) return;     // a plain arrival only gets the stage in a quiet moment
  showSpot(s);
}
setInterval(runSpots, 500);
document.getElementById("pw-spot").addEventListener("click", () => { if (spotNow) endSpot(); });

/* ---------------------------------------------------------------- data -- */
function renderAll() {
  if (!D || !S || !F) return;
  renderHead(); renderTower(); renderHost(); renderDials(); renderDetail(); renderChalk(); renderTape(); renderTabs(); renderPage(false);
  app.hidden = false; loading.hidden = true; fit();
}
async function pullFeed() {
  if (feeding) return;
  feeding = true; lastFeed = Date.now();
  try {
    const r = await fetch("/api/dashboard" + (screenFamily() ? "?family=1" : ""), { cache: "no-store" });
    const f = await r.json();
    if (f && f.ok) { F = f; watchJumps(); watchStage(); renderAll(); }
  } catch (e) { /* the next poll tries again */ }
  feeding = false;
}
function showConnection(ok) {
  online = ok;
  document.getElementById("pw-connection").textContent = ok ? "" : W("conn.stale");
}
async function refreshInfo() {
  if (reloading) return;
  clearTimeout(retryInfo);
  reloading = true;
  try {
    const info = await loadInfo();
    D = info.data; CAST = (info.voice && info.voice.cast) || {};
    if (typeof DashWhisper !== "undefined") {
      Voice.setup(info.voice);
      DashWhisper.setup({ closed: () => { pageAt = Date.now(); }, navigate: target => {
        if (target.page === "fleet" && !TABS) document.querySelector('[data-detail="fleet"]').click();
        else if (TABS && (target.page === "weather" || target.page === "fleet")) goto(target.page);
        else {
          goto(target.page);
          if (target.page === "markets" && !F.locked) { marketPort = target.port; marketGood = target.good; marketLens = "price"; renderPage(false); }
        }
      } });
    }
    document.title = brandName(D.brand) + " · " + tabTitle(page);
    labelButtons();
  } catch (e) {
    console.warn("The Dashboard could not load settings", e);
    retryInfo = setTimeout(refreshInfo, 3000);
  } finally { reloading = false; }
  if (D && S && S.cfg === cfgSeen) pullFeed();
}

/* ---------------------------------------------------------------- the small controls -- */
function labelButtons() {
  const pause = document.getElementById("pw-pause");
  pause.textContent = TABS ? TABS.t(held ? "cc.pinned" : "cc.pin") : held ? W("btn.held") : W("btn.hold"); pause.setAttribute("aria-pressed", String(held));
  document.getElementById("pw-next").textContent = TABS ? TABS.t("cc.next") : W("btn.next");
  if (TABS) {
    document.getElementById("pw-watch-label").textContent = TABS.t("cc.watch"); document.getElementById("pw-watch").setAttribute("aria-pressed", String(watchOn));
    document.getElementById("pw-all").textContent = TABS.t("cc.all");
    document.getElementById("pw-tabs").setAttribute("aria-label", TABS.t("cc.tabs"));
    document.getElementById("pw-context").setAttribute("aria-label", TABS.t("cc.bar"));
    document.getElementById("drawer-close").textContent = TABS.t("cc.drawer.close");
  }
  const sp = document.getElementById("pw-spots"); sp.textContent = W("btn.spots"); sp.setAttribute("aria-pressed", String(spotsOn));
  const snd = document.getElementById("pw-sound"); snd.textContent = W("btn.clicks"); snd.setAttribute("aria-pressed", String(clicksOn));
  document.getElementById("pw-quit").textContent = W("btn.quit");
}
document.getElementById("pw-pause").addEventListener("click", () => { held = !held; pageAt = Date.now(); labelButtons(); });
document.getElementById("pw-next").addEventListener("click", () => turnPage(1));
document.getElementById("pw-spots").addEventListener("click", () => {
  spotsOn = !spotsOn; store("seatrader_dash_spots", spotsOn ? null : "0"); labelButtons(); if (!spotsOn && spotNow) endSpot();
});
document.getElementById("pw-sound").addEventListener("click", () => {
  clicksOn = !clicksOn; store("seatrader_dash_clicks", clicksOn ? "1" : null); labelButtons(); if (clicksOn) tapeClick();
});
/* ---- the Command Center's own controls: Watch Mode, the drawer of all tabs, a swipe, and what counts as a touch ---- */
if (TABS) {
  const drawer = document.getElementById("pw-drawer");
  const renderDrawer = () => { previous.delete("drawer-body"); update("drawer-body", TABS.drawerHtml(page, watchSkip)); };
  document.getElementById("pw-watch").addEventListener("click", () => {
    watchOn = !watchOn; store("seatrader_dash_watch", watchOn ? null : "0");
    if (watchOn) { lastTouch = 0; pageAt = Date.now(); }      // switched on by hand: start touring now, not in a minute
    labelButtons();
  });
  document.getElementById("pw-all").addEventListener("click", () => { renderDrawer(); drawer.showModal(); });
  document.getElementById("drawer-close").addEventListener("click", () => drawer.close());
  drawer.addEventListener("close", () => { pageAt = Date.now(); });
  drawer.addEventListener("click", e => {
    if (e.target === drawer) return drawer.close();             // a tap on the dimmed backdrop
    const go = e.target.closest(".drawer-go");
    if (go) { drawer.close(); goto(go.dataset.page); }
  });
  drawer.addEventListener("change", e => {
    const k = e.target.dataset.watch;
    if (!k) return;
    if (e.target.checked) watchSkip.delete(k); else watchSkip.add(k);
    TABS.writeSkip(watchSkip);
  });
  /* A fact card or a context chip opens the tab that explains it. */
  const jump = e => { const b = e.target.closest("button[data-page]"); if (b && BUILDERS[b.dataset.page]) goto(b.dataset.page); };
  document.getElementById("pw-context").addEventListener("click", jump);
  /* The date in the masthead opens Now (the months-left dial it replaces used to open a pop-up). */
  const clock = document.querySelector(".pw-clock");
  if (clock) {
    clock.setAttribute("role", "button"); clock.tabIndex = 0;
    clock.addEventListener("click", () => goto("now"));
    clock.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); goto("now"); } });
  }
  document.getElementById("pw-book").addEventListener("click", e => {
    const sb = e.target.closest("button[data-sub]"), rt = e.target.closest("button[data-route]"), pt = e.target.closest("[data-port]");
    if (sb) { TABS.setSub(page, sb.dataset.sub); renderPage(true); }
    else if (pt && page === "lanes") { TABS.setPort(pt.dataset.port); renderPage(false); }      // the Atlas: a port's dossier, or back to the list
    else if (rt) { detailKind = "route:" + rt.dataset.route; renderDetail(); detailDialog.showModal(); }
    else if (e.target.closest(".cc-fact")) jump(e);
  });
  /* A port on the Atlas's chart is a button drawn in the chart: Enter or Space presses it. */
  document.getElementById("pw-book").addEventListener("keydown", e => {
    const pin = (e.key === "Enter" || e.key === " ") && e.target instanceof Element ? e.target.closest("g[data-port]") : null;
    if (pin && page === "lanes") { e.preventDefault(); TABS.setPort(pin.dataset.port); renderPage(false); }
  });
  /* Any touch, key or scroll is the Captain reading: Watch Mode stands back. Switching Watch Mode on is not one. */
  const touched = e => { if (!(e.target instanceof Element && e.target.closest("#pw-watch"))) lastTouch = Date.now(); };
  ["pointerdown", "keydown", "wheel", "touchstart"].forEach(ev => document.addEventListener(ev, touched, { capture: true, passive: true }));
  /* A sideways swipe across the book turns to the next or the previous tab. */
  let swipe = null;
  const book = document.getElementById("pw-book");
  book.addEventListener("pointerdown", e => { swipe = e.isPrimary ? { x: e.clientX, y: e.clientY, at: Date.now() } : null; });
  book.addEventListener("pointerup", e => {
    if (!swipe) return;
    const dx = e.clientX - swipe.x, dy = e.clientY - swipe.y, quick = Date.now() - swipe.at < 700;
    swipe = null;
    if (quick && Math.abs(dx) > 70 && Math.abs(dx) > Math.abs(dy) * 2 && !spotNow) turnPage(dx < 0 ? 1 : -1);
  });
  book.addEventListener("pointercancel", () => { swipe = null; });
  /* Back from a hidden window: the open tab gets its full time again instead of turning at once. */
  document.addEventListener("visibilitychange", () => { if (!document.hidden) { pageAt = Date.now(); if (D && S) pullFeed(); } });
}
function quitDash() { window.close(); setTimeout(() => { if (!window.closed) document.getElementById("pw-quit").textContent = "Close this window"; }, 300); }
document.getElementById("pw-quit").addEventListener("click", quitDash);
document.addEventListener("keydown", e => {
  if (e.defaultPrevented || detailDialog.open || typeof DashWhisper !== "undefined" && DashWhisper.isOpen() || e.key !== "Escape" && e.target.closest("button, select, input, textarea, [role=button]")) return;
  if (e.key === "Escape") { e.preventDefault(); quitDash(); }
  else if (e.key === "ArrowRight") turnPage(1);
  else if (e.key === "ArrowLeft") turnPage(-1);
  else if (e.key === " ") { e.preventDefault(); held = !held; pageAt = Date.now(); labelButtons(); }
});

/* The page is liquid. It is designed on a 1920 x 1080 stage; fit() scales that stage to the window, then widens or heightens
   it by the same factor so it fills the whole browser at any shape (no bars). The grid's flexible middle column and rows take up the slack. */
let refitTimer = 0;
function fit() {
  const w = window.innerWidth, h = window.innerHeight;
  /* A tall screen (a tablet held upright) gets a narrower stage in one column; --touch is 44 real pixels measured on
     the stage, so buttons stay finger-sized however far the stage is scaled down, and --boost lifts the Command
     Center's own type on small screens. */
  const tall = !!TABS && h > w * 1.05, s = tall ? w / 1080 : Math.min(w / 1920, h / 1080);
  app.classList.toggle("portrait", tall);
  app.style.setProperty("--touch", (44 / s).toFixed(1) + "px");
  app.style.setProperty("--boost", Math.max(1, Math.min(1.5, 0.92 / s)).toFixed(3));
  app.style.width = (w / s) + "px"; app.style.height = (h / s) + "px";
  app.style.transform = `scale(${s})`; app.style.left = "0px"; app.style.top = "0px";
}
window.addEventListener("resize", () => {
  fit();
  clearTimeout(refitTimer); refitTimer = setTimeout(() => { if (D && S && F && !app.hidden) renderPage(false); }, 250);
});

Faces.onChange = () => renderAll();
listen(null, state => {
  S = state;
  if (!D || state.cfg !== cfgSeen) return refreshInfo();
  if (!F || Date.now() - lastFeed > 1500) pullFeed(); else renderAll();
}, showConnection);
feedTimer = setInterval(() => { if (D && S && !document.hidden && Date.now() - lastFeed > FEED_MS) pullFeed(); }, 1000);
