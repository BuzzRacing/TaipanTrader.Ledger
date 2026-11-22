/* THE DASHBOARD (21 Nov 2026): an 1860s Formula 1 pit box for the big screen. See dashboard.css for the layout.
   Timing tower (left), a ledger book that turns its own pages (middle: The Race, Sea Lanes, Markets & Booms),
   brass dials and a chalkboard of month times (right), a telegraph tape (bottom).

   Data: the public stream (/events, the same one the harbor board uses) for the date, weather, fights and news;
   /api/dashboard (dashboard_feed.py) for history. The feed already leaves out whatever the game's visibility
   rule keeps private, so a block that is missing is shown stamped "Sealed" rather than guessed.
   Wording: every label is a key "dash.*" that Admin > Language & Text can override; DEF below is the fallback. */
"use strict";

const TURN_MS = 25000;       // how long a page stays open before the book turns
const FEED_MS = 5000;        // how often the history is fetched when nothing else asks for it
const TAPE_SHOW = 14;
const PAGES = [{ k: "race", n: "I" }, { k: "lanes", n: "II" }, { k: "markets", n: "III" }];

const DEF = {
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
  "mk.movers": "Movers this month", "mk.booms": "Booms and crashes", "mk.none": "The markets are quiet.", "mk.nobooms": "No booms or crashes yet.",
  "mk.boom": "Boom", "mk.crash": "Crash", "mk.months": "{n} months", "mk.month": "1 month", "mk.cheap": "cheap", "mk.dear": "dear",
  "sealed": "Sealed", "sealed.note": "Rivals are at the table. This page opens at the finale.",
  "tower": "Timing tower", "leader": "LEADER", "ghost.best": "Best game", "ghost.par": "Par pace",
  "status.port": "At {port}", "status.sea": "At sea", "status.fight": "In battle", "status.away": "Away",
  "tower.foot.solo": "Racing the ghost of your best game.", "tower.foot.par": "Racing a par pace until you have a game on the books.",
  "tower.foot.n": "{n} houses on the line",
  "chalk": "Month times", "chalk.month": "Month", "chalk.none": "No laps run yet.", "chalk.best": "Best month: {date}, {firm} {gain}",
  "dial.months": "Months left", "dial.of": "of {n}", "dial.baro": "Barometer", "dial.hull": "Fleet hull",
  "dial.ships": "{n} ships, {c} crippled", "dial.noships": "no ships afloat", "dial.fair": "fair everywhere",
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
let page = "race", pageAt = Date.now(), held = false, lastFeed = 0, feeding = false, feedTimer = 0;
let seenFights = null, seenBooms = null, tapeSeen = null, marketGood = null, marketTurn = -1;
let clicksOn = store("seatrader_dash_clicks") === "1", actx = null;
let spotsOn = store("seatrader_dash_spots") !== "0";
const app = document.getElementById("app"), loading = document.getElementById("db-loading");
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
    try { for (const i of Media.items("persona", cid, "wallpaper", false)) if ((i.g || []).some(t => /reclin|lying|laying/i.test(t))) pool.push(i); } catch (e) { /* no library yet */ }
  }
  if (!pool.length) { el.innerHTML = ""; return; }
  const fresh = pool.filter(i => i.id !== loungeId), item = (fresh.length ? fresh : pool)[Math.floor(Math.random() * (fresh.length || pool.length))];
  loungeId = item.id; loungeAt = Date.now();
  el.innerHTML = `<img src="${esc(item.u)}" alt="">`;
}

function renderTabs() {
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

function renderTower() {
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
  const foot = solo() ? (F.ghost && F.ghost.kind === "best" ? W("tower.foot.solo") : W("tower.foot.par")) : W("tower.foot.n", { n: hs.length });
  update("pw-tower", `<div class="tw-title"><span>${We("tower")}</span><b>${esc(S.date || "")}</b></div>
    <div class="tw-rows${hs.length > 5 ? " dense" : ""}">${rows.join("") || `<p class="pw-note" style="color:#bfa77a;padding:10px">${We("date.lobby")}</p>`}</div>
    <div class="tw-foot">${esc(foot)}</div>`);
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
    <circle cx="100" cy="104" r="94" fill="url(#dbrass${i})"/><circle cx="100" cy="104" r="86" fill="url(#dface${i})" stroke="#6b452d" stroke-width="2"/>`;
  zones.forEach((c, z) => { s += `<path d="${arc(74, -120 + z * 80, -120 + (z + 1) * 80 - 2)}" fill="none" stroke="${c}" stroke-width="9" stroke-linecap="butt" opacity=".85"/>`; });
  for (let t = 0; t <= 10; t++) {
    const a = DEG(-120 + t * 24), r0 = 60, r1 = t % 5 === 0 ? 50 : 54;
    s += `<line x1="${(100 + r0 * Math.sin(a)).toFixed(1)}" y1="${(104 - r0 * Math.cos(a)).toFixed(1)}" x2="${(100 + r1 * Math.sin(a)).toFixed(1)}" y2="${(104 - r1 * Math.cos(a)).toFixed(1)}" stroke="#2a170e" stroke-width="${t % 5 === 0 ? 3 : 1.6}"/>`;
  }
  s += `<text id="dv${i}" x="100" y="150" text-anchor="middle" font-size="34" font-family="Georgia,serif" fill="#2a170e"></text>
    <g class="needle" id="dn${i}" style="transform:rotate(-120deg)"><path d="M96 108 L100 28 L104 108 Z" fill="#8a2219"/></g>
    <circle cx="100" cy="104" r="9" fill="url(#dbrass${i})" stroke="#2a170e" stroke-width="1.5"/></svg>`;
  return s;
}
const DIAL_ZONES = [
  ["#1f5c46", "#c9a34e", "#8a2219"],     // months left: the game runs out
  ["#1f5c46", "#c9a34e", "#8a2219"],     // barometer: fair to typhoon
  ["#8a2219", "#c9a34e", "#1f5c46"]      // hull: wrecked to sound
];
let dialsBuilt = false;
function buildDials() {
  if (dialsBuilt) return;
  document.getElementById("pw-dials").innerHTML = [0, 1, 2].map(i =>
    `<div class="dial">${dialSvg(i, DIAL_ZONES[i])}<b id="dt${i}"></b><span id="ds${i}"></span></div>`).join("");
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
  buildDials();
  // months left
  const total = monthsTotal(), left = S.turns_left == null ? 0 : S.turns_left, lobby = S.phase === "lobby";
  setDial(0, total ? (total - left) / total : 0, lobby ? "-" : String(left), W("dial.months"), total ? W("dial.of", { n: total }) : "");
  // barometer
  const lv = Object.entries(S.weather || {}), names = D.weather || [], top = Math.max(1, names.length - 1);
  let worst = 0, where = "", sum = 0;
  lv.forEach(([r, l]) => { sum += l; if (l > worst) { worst = l; where = (D.regions[r] || {}).name || ""; } });
  setDial(1, lv.length ? sum / lv.length / top : 0, "", W("dial.baro"), worst ? `${names[worst] || ""}${where ? ", " + where : ""}` : W("dial.fair"));
  // fleet hull
  const ships = F.houses.flatMap(h => h.hull || []), crip = ships.filter(s => s.crippled).length;
  const avg = ships.length ? ships.reduce((a, s) => a + s.hull, 0) / ships.length : 0;
  setDial(2, avg, ships.length ? Math.round(avg * 100) + "%" : "-", W("dial.hull"), ships.length ? W("dial.ships", { n: ships.length, c: crip }) : W("dial.noships"));
}

/* ---------------------------------------------------------------- chalkboard -- */
function chalkData() {
  const hs = ranked().slice(0, 4);
  const per = hs.map(h => ({ h, gains: gainsOf(h) }));
  const turns = [...new Set(per.flatMap(p => p.gains.map(g => g.turn)))].sort((a, b) => a - b);
  return { per, rows: turns.slice(-6) };
}
function lastGain() {
  const lead = ranked()[0];
  if (!lead) return 0;
  const g = gainsOf(lead);
  return g.length ? g[g.length - 1].gain : 0;
}
function renderChalk() {
  const { per, rows } = chalkData();
  if (!rows.length) { update("pw-chalk", `<div class="chalk"><h4>${We("chalk")}</h4><p class="none">${We("chalk.none")}</p><footer></footer></div>`); return; }
  const best = per.map(p => Math.max(...p.gains.map(g => g.gain))), worst = per.map(p => Math.min(...p.gains.map(g => g.gain)));
  let champ = null;
  per.forEach(p => p.gains.forEach(g => { if (!champ || g.gain > champ.gain) champ = { gain: g.gain, date: g.date, firm: p.h.firm }; }));
  const head = `<tr><th>${We("chalk.month")}</th>${per.map(p => `<th style="color:${hcol(p.h)}" title="${esc(p.h.firm)}">${esc(String(p.h.firm).slice(0, 9))}</th>`).join("")}</tr>`;
  const body = rows.map(t => `<tr><td>${esc(dateOfTurn(t))}</td>${per.map((p, i) => {
    const g = p.gains.find(x => x.turn === t);
    if (!g) return "<td>-</td>";
    const cls = g.gain === best[i] && g.gain > 0 ? "best" : g.gain === worst[i] && g.gain < 0 ? "worst" : g.gain > 0 ? "pos" : "";
    return `<td class="${cls}">${signed(g.gain)}${cls === "best" ? " &#9733;" : ""}</td>`;
  }).join("")}</tr>`).join("");
  update("pw-chalk", `<div class="chalk"><h4>${We("chalk")}</h4><table>${head}${body}</table>
    <footer>${champ ? W("chalk.best", { date: esc(champ.date), firm: esc(champ.firm), gain: signed(champ.gain) }) : ""}</footer></div>`);
}

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
    return `<div class="${cls.join(" ")}" style="--house:${h ? hcol(h) : "#8a2219"}"><span>${tapeText(e)}</span>${e.turn != null && dateOfTurn(e.turn) ? `<small>${esc(dateOfTurn(e.turn))}</small>` : ""}</div>`;
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
    s += `<line x1="${L}" x2="${w - R}" y1="${yy.toFixed(1)}" y2="${yy.toFixed(1)}" stroke="#6b452d" stroke-opacity=".25"/>
      <text x="${L - 6}" y="${(yy + 5).toFixed(1)}" text-anchor="end" font-size="14" fill="#6b452d">${kfmt(v)}</text>`;
  }
  for (let i = 0; i <= 3; i++) {
    const t = Math.round(t0 + (t1 - t0) * i / 3), label = dateOfTurn(t) || ("M" + (t - t0));
    s += `<text x="${x(t).toFixed(1)}" y="${h - 6}" text-anchor="${i === 0 ? "start" : i === 3 ? "end" : "middle"}" font-size="13" fill="#6b452d">${esc(label)}</text>`;
  }
  if (g) {
    s += `<polyline fill="none" stroke="#6b452d" stroke-opacity=".55" stroke-width="3" stroke-dasharray="3 7" stroke-linecap="round" points="${g.curve.map((v, i) => x(t0 + i).toFixed(1) + "," + y(v).toFixed(1)).join(" ")}"/>`;
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
    <div class="pg"><div>${raceChart(440, 520)}</div>
    <ul class="pw-list">${legend}${F.ghost ? `<li><span class="pw-dot" style="background:transparent;border:2px dotted #6b452d"></span><b>${esc(F.ghost.kind === "best" ? W("ghost.best") : W("ghost.par"))}</b><span class="num">${money(F.ghost.final)}</span></li>` : ""}</ul></div>`;
  const lc = leadChanges().slice(0, 6);
  const changes = lc.length ? `<ul class="pw-list">${lc.map(c => `<li style="grid-template-columns:1fr auto"><b class="${c.up ? "up" : "down"}">${c.text}</b><small>${esc(c.date)}</small></li>`).join("")}</ul>`
    : `<p class="pw-note">${We("race.nolead")}</p>`;
  let deals;
  if (F.locked) deals = `<div class="pw-block-locked">${stamp(W("sealed"), W("race.sealed"))}</div>`;
  else if (!(F.deals || []).length) deals = `<p class="pw-note">${We("race.nodeals")}</p>`;
  else deals = `<table><tbody>${F.deals.slice(0, 5).map(d => `<tr><td><span class="pw-dot" style="--house:${house(d.pid) ? hcol(house(d.pid)) : "#888"}"></span>${d.qty} ${gn(d.good)}<br><small class="pw-note">${pn(d.port)} &middot; ${esc(d.date)}</small></td><td class="num up">${signed(d.profit)}</td></tr>`).join("")}</tbody></table>`;
  const mood = lastGain() > 0 ? "happy" : lastGain() < 0 ? "angry" : "sly";
  const role = Media.has("persona", "bookkeeper", mood) ? mood : "portrait";
  const pic = Media.html("persona", "bookkeeper", role, "pz", "", { slot: "dash-keeper" });
  const keeper = `<figure class="pw-keeper mood-${mood}">${pic || '<span class="pw-quill" aria-hidden="true">&#9998;</span>'}</figure>`;
  const right = `<h2 style="padding-right:118px">${We("race.lead")}</h2><div class="pg" style="margin-right:118px">${changes}<h3 style="margin-top:8px">${We("race.deals")}</h3>${deals}</div>${keeper}`;
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
  const chart = withOverlay(cropChart(Chart.svg({ data: D, players: S.players, crackdown: S.crackdown || [], hideWeather: true, hideRose: true })), threads(lanes));
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
function lerpColor(a, b, t) {
  const pa = a.match(/\w\w/g).map(h => parseInt(h, 16)), pb = b.match(/\w\w/g).map(h => parseInt(h, 16));
  return "#" + pa.map((v, i) => Math.round(v + (pb[i] - v) * t).toString(16).padStart(2, "0")).join("");
}
function heat(ratio) {
  const t = Math.max(0, Math.min(1, (ratio - .65) / .7));
  return t < .5 ? lerpColor("1f5c46", "e8d4a0", t * 2) : lerpColor("e8d4a0", "8a2219", (t - .5) * 2);
}
function pageMarkets() {
  if (F.locked) {
    return { left: `<h2>${We("mk.title")}</h2><div class="pg">${stamp(W("sealed"), W("sealed.note"))}</div>`, right: `<h2>&nbsp;</h2><div class="pg">${stamp(W("sealed"), W("sealed.note"))}</div>` };
  }
  const rows = priceRows(), goods = Object.keys(D.goods);
  // a new cargo each time the page comes round, the biggest mover first
  if (marketTurn !== F.turn || marketGood === null) {
    marketTurn = F.turn;
    const big = rows.slice().sort((a, b) => Math.abs(b.pct) - Math.abs(a.pct))[0];
    marketGood = big ? big.good : goods[0];
  }
  const good = marketGood, ofGood = rows.filter(r => r.good === good);
  const avg = ofGood.length ? ofGood.reduce((a, r) => a + r.price, 0) / ofGood.length : 1;
  const low = ofGood.slice().sort((a, b) => a.price - b.price)[0], high = ofGood.slice().sort((a, b) => b.price - a.price)[0];
  let over = '<g style="pointer-events:none">';
  ofGood.forEach(r => {
    const p = D.ports[r.port];
    if (!p) return;
    over += `<circle cx="${p.x}" cy="${p.y}" r="30" fill="${heat(r.price / avg)}" fill-opacity=".86" stroke="#2a170e" stroke-opacity=".6" stroke-width="2"/>
      <text x="${p.x}" y="${p.y + 6}" text-anchor="middle" font-size="17" font-weight="700" fill="#fff" stroke="#2a170e" stroke-width="3.5" paint-order="stroke">${Math.round(r.price)}</text>`;
  });
  over += "</g>";
  const chart = withOverlay(cropChart(Chart.svg({ data: D, players: [], crackdown: [], hideWeather: true, hideRose: true })), over);
  const left = `<h2>${We("mk.title")}<small>${W("mk.sub", { good: gn(good), low: low ? pn(low.port) : "", high: high ? pn(high.port) : "" })}</small></h2>
    <div class="pg"><div class="chart-wrap" id="dash-chart">${chart}</div><div class="price-legend"><span>${We("mk.cheap")}</span><i></i><span>${We("mk.dear")}</span></div>
    <ul class="pw-list tight">${ofGood.slice().sort((a, b) => a.price - b.price).map(r => `<li style="grid-template-columns:1fr auto"><div><b>${pn(r.port)}</b>
      <div class="pw-bar"><i style="width:${Math.max(6, r.price / (high ? high.price : 1) * 100)}%;background:${heat(r.price / avg)}"></i></div></div><span class="num">${money(r.price)}</span></li>`).join("")}</ul></div>`;
  const movers = rows.filter(r => Math.abs(r.pct) >= .005).sort((a, b) => Math.abs(b.pct) - Math.abs(a.pct)).slice(0, 7);
  const moverHtml = movers.length ? `<table><tbody>${movers.map(r => `<tr><td><b class="${r.pct >= 0 ? "up" : "down"}">${r.pct >= 0 ? "&#9650;" : "&#9660;"}</b> ${gn(r.good)}<br><small class="pw-note">${pn(r.port)}</small></td>
    <td class="num">${money(r.price)}</td><td class="num ${r.pct >= 0 ? "up" : "down"}">${(r.pct >= 0 ? "+" : "") + Math.round(r.pct * 100)}%</td></tr>`).join("")}</tbody></table>` : `<p class="pw-note">${We("mk.none")}</p>`;
  const booms = (F.booms || []).slice().reverse().slice(0, 5);
  const boomHtml = booms.length ? `<ul class="pw-list">${booms.map(w => `<li style="grid-template-columns:auto 1fr auto"><b class="${w.sort === "crash" ? "down" : "up"}">${We(w.sort === "crash" ? "mk.crash" : "mk.boom")}</b>
    <span>${gn(w.good)} at ${pn(w.port)}<br><small>${esc(w.date)}</small></span><span class="num">&times;${w.mult} <small>${w.turns === 1 ? We("mk.month") : We("mk.months", { n: w.turns })}</small></span></li>`).join("")}</ul>` : `<p class="pw-note">${We("mk.nobooms")}</p>`;
  const right = `<h2>${We("mk.movers")}</h2><div class="pg">${moverHtml}<h3 style="margin-top:8px">${We("mk.booms")}</h3>${boomHtml}</div>`;
  return { left, right, fit: "dash-chart" };
}

const BUILDERS = { race: pageRace, lanes: pageLanes, markets: pageMarkets };
function renderPage(flip) {
  const b = BUILDERS[page]();
  const l = update("pw-left", b.left), r = update("pw-right", b.right);
  if (b.fit && typeof Chart.fit === "function") {
    const el = document.getElementById(b.fit);
    if (el && (l || r)) Chart.fit(el);
  }
  if (flip) ["pw-left", "pw-right"].forEach(id => { const el = document.getElementById(id); el.classList.remove("flip"); void el.offsetWidth; el.classList.add("flip"); });
}

/* ---------------------------------------------------------------- turning the book -- */
function available() { return PAGES.map(p => p.k).filter(k => !(k === "markets" && F && F.locked)); }
function goto(k, why) {
  if (!BUILDERS[k] || !F) return;
  if (k === "markets") marketGood = null;          // a fresh cargo each time the page comes round
  const changed = k !== page;
  if (changed) hostLine++;
  page = k; pageAt = Date.now();
  renderTabs(); renderHost();
  renderPage(changed);
}
function turnPage(step) {
  const list = available(), i = list.indexOf(page);
  goto(list[(i + (step || 1) + list.length) % list.length]);
}
setInterval(() => {
  if (!F) return;
  const bar = document.querySelector(".pw-tab.on .pw-prog");
  if (bar) bar.style.width = held ? "100%" : Math.min(100, (Date.now() - pageAt) / TURN_MS * 100) + "%";
  if (!held && Date.now() - pageAt >= TURN_MS) turnPage(1);
}, 500);

/* A fight, a boom or a crash that was not there a moment ago pulls the book to the page that shows it. */
function watchJumps() {
  const fights = new Set((S.sea || []).map(f => f.id)), booms = new Set((F.booms || []).map(w => [w.turn, w.port, w.good, w.sort].join("|")));
  if (seenFights === null) { seenFights = fights; seenBooms = booms; return; }
  const newFight = [...fights].some(id => !seenFights.has(id)), newBoom = [...booms].some(k => !seenBooms.has(k));
  seenFights = fights; seenBooms = booms;
  if (held) return;
  if (newFight) goto("lanes");                       // a battle first: the game itself holds for fights
  else if (newBoom && !F.locked) goto("markets");
}


/* ---------------------------------------------------------------- the women --
   Every moment of the race has a woman to go with it. One stands on the line all the time (the host card under the
   tower, who changes with the page) and when something big happens she steps forward: a spotlight takes the whole
   book for ten seconds, her picture (wallpaper first, then portrait, a clip if she has one) full height, F1 style
   lower third, her line. All from public facts, so it is safe with rivals at the table. Pictures follow the game's
   Family-friendly switch because they come from the same Media Library. Lines are written in the house voice, with
   a clean twin for Family-friendly screens. */
let CAST = {};
const FALLBACK_WHO = {
  gamemaster: ["Madame Anahit Sarkissian", "Mistress of the Table & Queen of the Hour", "#b48cf0"],
  narrator: ["Roxana Cama", "First Mate & Queen of the Black Log", "#c9a34e"],
  bookmaker: ["Isabel “Fan-Tan Bella” da Rocha", "Bookmaker of the Golden Fan", "#e0705a"],
  pirate: ["Admiral Li Yue", "Pirate Queen of the South China Sea", "#d0644f"],
  bosun: ["Peggy “Powder” O’Rourke", "Bosun, Master Gunner & Powder Queen", "#e0a050"],
  taxlady: ["Mrs. Evelyn Marlowe", "Registrar of the Merchant Houses", "#7fc4a2"],
  crier: ["Tilly Marsh", "Gazette Crier & Queen of Rumours", "#e8d4ae"],
  mayor: ["Her Worship the Mayor", "Mayor of the Port", "#c9a34e"]
};
function who(cid) {
  const c = CAST[cid] || {}, f = FALLBACK_WHO[cid] || [cid, "", "#c9a34e"];
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
    ["Mmm, the whole {port} floor is panting over {good}. Place your bets, sweetheart.", "The whole {port} floor is buzzing over {good}. Place your bets, sweetheart."]] },
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
/* The woman on the line for each page, with what she says there. */
const HOSTS = {
  race: ["gamemaster", [["Watch the leaderboard, darlings. Everything else is foreplay.", "Watch the leaderboard. Everything else is warm-up."], ["A lead is only a lead until someone hungrier arrives.", "A lead is only a lead until someone hungrier arrives."]]],
  lanes: ["narrator", [["Every lane is a promise, and the sea breaks most of them.", "Every lane is a promise, and the sea breaks most of them."], ["Sail where it's busy, and mind the weather. She has moods.", "Sail where it's busy, and mind the weather. She has moods."]]],
  markets: ["bookmaker", [["Cheap here, dear there. That, sweethearts, is the whole game.", "Cheap here, dear there. That, friends, is the whole game."], ["A boom is just a crowd with the same idea. Be early.", "A boom is just a crowd with the same idea. Be early."]]]
};
let hostLine = 0;
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
  const h = HOSTS[ended ? "race" : page] || HOSTS.race;
  const w = who(withArt([ended ? "gamemaster" : h[0]], HOST_FB[ended ? "race" : page] || HOST_FB.race)[0]);
  const text = ended ? lineOf(SAY.finale.lines[0]).replace(/\{who\}|\{worth\}/g, "") : lineOf(h[1][hostLine % h[1].length]);
  const pic = art(w.cid, ["portrait", "speaking"], "ho-pic", "dash-host");
  const body = ended ? W("sp.finale") : W("host.on");
  update("pw-host", `<div class="ho-art" style="--who:${w.color}">${pic || `<span class="ho-mono">${esc(monogram(w.name))}</span>`}</div>
    <div class="ho-shade"></div><div class="ho-on"><i></i>${esc(body)}</div>
    <div class="ho-plate"><p class="ho-line">${esc(ended ? "" : text)}</p><b>${esc(w.name)}</b><small>${esc(w.title)}</small></div>`);
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
  const pic = art(cid, ["wallpaper", "portrait"], "sp-pic", "dash-spot");
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
  if (!spotQ.length || now < spotFree || !F) return;
  const s = spotQ.shift();
  if (s.pri <= 2 && now - lastSpotAt < 40000) return;     // a plain arrival only gets the stage in a quiet moment
  showSpot(s);
}
setInterval(runSpots, 500);
document.getElementById("pw-spot").addEventListener("click", () => { if (spotNow) endSpot(); });

/* ---------------------------------------------------------------- data -- */
function renderAll() {
  if (!D || !S || !F) return;
  renderHead(); renderTower(); renderHost(); renderDials(); renderChalk(); renderTape(); renderTabs(); renderPage(false);
  app.hidden = false; loading.hidden = true; fit();
}
async function pullFeed() {
  if (feeding) return;
  feeding = true; lastFeed = Date.now();
  try {
    const r = await fetch("/api/dashboard", { cache: "no-store" });
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
    document.title = brandName(D.brand) + " · " + W("tab.race");
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
  pause.textContent = held ? W("btn.held") : W("btn.hold"); pause.setAttribute("aria-pressed", String(held));
  document.getElementById("pw-next").textContent = W("btn.next");
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
function quitDash() { window.close(); setTimeout(() => { if (!window.closed) document.getElementById("pw-quit").textContent = "Close this window"; }, 300); }
document.getElementById("pw-quit").addEventListener("click", quitDash);
document.addEventListener("keydown", e => {
  if (e.key === "Escape") { e.preventDefault(); quitDash(); }
  else if (e.key === "ArrowRight") turnPage(1);
  else if (e.key === "ArrowLeft") turnPage(-1);
  else if (e.key === " ") { e.preventDefault(); held = !held; pageAt = Date.now(); labelButtons(); }
});

/* The stage is 1920 x 1080 and is scaled to fit whatever 16:9 (or other) screen it is on. */
function fit() {
  const s = Math.min(window.innerWidth / 1920, window.innerHeight / 1080);
  app.style.transform = `scale(${s})`;
  app.style.left = ((window.innerWidth - 1920 * s) / 2) + "px";
  app.style.top = ((window.innerHeight - 1080 * s) / 2) + "px";
}
window.addEventListener("resize", fit);

Faces.onChange = () => renderAll();
listen(null, state => {
  S = state;
  if (!D || state.cfg !== cfgSeen) return refreshInfo();
  if (!F || Date.now() - lastFeed > 1500) pullFeed(); else renderAll();
}, showConnection);
feedTimer = setInterval(() => { if (D && S && Date.now() - lastFeed > FEED_MS) pullFeed(); }, 1000);
