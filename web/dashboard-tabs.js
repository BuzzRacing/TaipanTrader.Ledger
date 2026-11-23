/* THE COMMAND CENTER'S TABS (22 Nov 2026). Plan: design/dashboard-captain-command-center-plan.md, Phase 1.

   The Dashboard is growing from a three-page book into eight tabs: Now, Atlas, Trade, Weather, Fleet, Treasury,
   Career, Wire. This file holds what is new in that step: the list of tabs, the five pages that did not exist
   before, the context bar, and the rule that says when Watch Mode may turn the page. dashboard.js still owns the
   stage, the three older pages (Sea Lanes is now the Atlas tab, Markets & Booms is Trade, The Race is Career) and
   everything that talks to the server.

   Read-only by design: nothing here sends anything to the game. Every figure comes from /api/dashboard or the
   public stream exactly as the server sent it; nothing is worked out here that the game's rules decide.
   With rivals at the table the server leaves private blocks out, and a page that needs one shows the "Sealed"
   stamp because the block is missing, never because something was hidden on the screen.

   Loaded before dashboard.js. The page builders below use dashboard.js's own helpers (W, We, D, S, F, money, pn,
   stamp, tapeText, ...), which exist by the time a page is first drawn. */
"use strict";

const DashTabs = (() => {
  /* k is the page key dashboard.js routes on (the three old pages keep their keys so nothing that points at them
     breaks); host is the woman who stands beside the page, fb who stands in when she has no pictures yet. */
  const PAGES = [
    { k: "now", n: "I", host: "gamemaster", fb: ["taxlady", "mayor", "bookkeeper"] },
    { k: "lanes", n: "II", host: "mayor", fb: ["narrator", "taxlady"] },
    { k: "markets", n: "III", host: "bookmaker", fb: ["comprador", "banker", "lender"] },
    { k: "weather", n: "IV", host: "bosun", fb: ["narrator", "pirate"] },
    { k: "fleet", n: "V", host: "bosun", fb: ["narrator", "pirate"] },
    { k: "treasury", n: "VI", host: "bookkeeper", fb: ["banker", "lender", "taxlady"] },
    { k: "race", n: "VII", host: "gamemaster", fb: ["taxlady", "mayor", "bookkeeper"] },
    { k: "wire", n: "VIII", host: "narrator", fb: ["crier", "bosun"] }
  ];
  const KEYS = PAGES.map(p => p.k);
  /* Pages that are mostly private: stamped "Sealed" on the tab itself while rivals are at the table. */
  const SEALED = new Set(["markets", "treasury"]);

  const TURN_MS = 12000;      // Watch Mode: how long a tab stays up
  const IDLE_MS = 60000;      // after a touch, Watch Mode waits this long before it turns a page again

  /* Wording: keys "dash.cc.*", which Admin > Language & Text can override like the rest of the Dashboard. */
  const DEF = {
    "cc.tab.now": "Now", "cc.tab.lanes": "Atlas", "cc.tab.markets": "Trade", "cc.tab.weather": "Weather",
    "cc.tab.fleet": "Fleet", "cc.tab.treasury": "Treasury", "cc.tab.race": "Career", "cc.tab.wire": "Wire",
    "cc.tabs": "Command Center tabs", "cc.sealed.tab": "sealed",
    "cc.watch": "Watch Mode", "cc.watch.wait": "resumes in {n}s", "cc.watch.off": "off", "cc.watch.on": "touring the tabs",
    "cc.watch.held": "waiting: tab pinned", "cc.watch.busy": "waiting", "cc.all": "All tabs", "cc.pin": "Pin tab", "cc.pinned": "Tab pinned", "cc.next": "Next tab",
    "cc.drawer": "All tabs", "cc.drawer.note": "Tap a tab to open it. Untick a tab to leave it out of Watch Mode on this screen.",
    "cc.drawer.in": "In Watch Mode", "cc.drawer.close": "Close",
    "cc.bar": "The voyage at a glance",
    "cc.bar.port": "In port", "cc.bar.sea": "At sea", "cc.bar.bound": "Bound for", "cc.bar.worth": "Net worth",
    "cc.bar.month": "this month", "cc.bar.fleet": "Fleet", "cc.bar.ships": "{n} ships", "cc.bar.ship": "1 ship",
    "cc.bar.crippled": "{n} crippled", "cc.bar.nofleet": "No ships", "cc.bar.weather": "Worst sea", "cc.bar.rank": "Rank",
    "cc.bar.houses": "Houses", "cc.bar.leader": "Leader",
    "cc.race.stand": "Standings",
    "cc.now.title": "Now", "cc.now.sub": "Where the voyage stands",
    "cc.now.months": "Months left", "cc.now.of": "of {n}", "cc.now.ended": "The voyage is over", "cc.now.lobby": "Waiting for captains",
    "cc.now.worth": "Net worth", "cc.now.first": "First month", "cc.now.position": "Position",
    "cc.now.sea": "Worst sea this month", "cc.now.forecast": "forecast",
    "cc.now.fleet": "Fleet condition", "cc.now.markets": "Markets", "cc.now.effects": "{n} booms or crashes running",
    "cc.now.effect": "1 boom or crash running", "cc.now.quiet": "No boom or crash running",
    "cc.now.bans": "Trade bans", "cc.now.noban": "No port has a ban", "cc.now.latest": "Latest on the wire",
    "cc.now.nothing": "Nothing on the wire yet.",
    "cc.wx.title": "Weather", "cc.wx.sub": "This month's forecast for each sea",
    "cc.wx.seas": "The four seas", "cc.wx.holds": "A forecast holds about {pct} of the time. The sea is settled when the month sails.",
    "cc.wx.route": "A voyage meets the worse of the two seas it sails between.",
    "cc.wx.odds": "Storm chance by forecast", "cc.wx.base": "Base chance. A short run scales it by {lo}, the longest by {hi}.",
    "cc.wx.level": "Forecast", "cc.wx.chance": "Storm chance",
    "cc.wx.here": "your fleet",
    "cc.lanes.sub.standing": "Standing", "cc.lanes.sub.tax": "Tax", "cc.lanes.sub.shares": "Shares", "cc.lanes.sub.stores": "Warehouses", "cc.lanes.sub.jobs": "Commissions", "cc.lanes.sub.bans": "Bans",
    "cc.band.0": "Hostile", "cc.band.1": "Cool", "cc.band.2": "Neutral", "cc.band.3": "Warm", "cc.band.4": "Favoured",
    "cc.at.title": "Atlas", "cc.at.sub.standing": "How each port thinks of your house", "cc.at.sub.tax": "The tax your house pays in each port",
    "cc.at.sub.shares": "Who holds each port's shares", "cc.at.sub.stores": "What you have ashore, and where", "cc.at.sub.jobs": "Where the Mayors' commissions end", "cc.at.sub.bans": "Ports with a trade ban",
    "cc.at.rank.standing": "Standing, best first", "cc.at.rank.tax": "Tax, lowest first", "cc.at.rank.shares": "Shares by port", "cc.at.rank.stores": "Warehouses", "cc.at.rank.jobs": "Commissions", "cc.at.rank.bans": "Bans in force",
    "cc.at.legend.standing": "The figure under each port is your standing there, out of 100.", "cc.at.legend.tax": "The figure under each port is the tax your house pays there.",
    "cc.at.legend.shares": "Shares held of each port's ten.", "cc.at.legend.stores": "Units stored over the warehouse's room.", "cc.at.legend.jobs": "Commissions in hand that end at each port. A question mark is one on offer.",
    "cc.at.legend.bans": "Cargoes a port will not land this month.",
    "cc.at.shares.foot": "{placed} of your {earned} shares are placed and {free} are free. A house can earn {cap} in all.",
    "cc.at.tap": "Tap a port, here or on the chart, for its dossier.", "cc.at.all": "All ports",
    "cc.at.sealed": "A house's standing, tax and stores stay private until the finale.", "cc.at.none": "No house has sailed yet.",
    "cc.at.empty.standing": "No standing to show.", "cc.at.empty.tax": "No tax to show.", "cc.at.empty.shares": "No shares to show.",
    "cc.at.empty.stores": "You have no warehouse yet.", "cc.at.empty.jobs": "No commission in hand or on offer.", "cc.at.empty.bans": "No port has a ban this month.",
    "cc.at.ban": "Ban", "cc.at.banned": "Banned here", "cc.at.patron": "Patron: {firm}", "cc.at.left": "{n} unsold", "cc.at.held": "{n} of {total} held",
    "cc.at.mine": "{n} of {total}", "cc.at.homefree": "No tax in your home port.", "cc.at.taxwas": "Down from {pct}.", "cc.at.taxfull": "The full rate.",
    "cc.at.sharecut": "Your shares take {pct} off.", "cc.at.holiday": "Tax holiday: {n} months left.",
    "cc.at.homestore": "Home warehouse, no rent", "cc.at.rent": "Rent {rent} a month", "cc.at.store": "{used} of {cap}",
    "cc.at.nostore": "A warehouse can be had here; you have none.", "cc.at.nowarehouse": "No warehouse in this port.",
    "cc.at.offer": "On offer", "cc.at.due": "due {date}", "cc.at.here": "Fleet here", "cc.at.home": "Home port",
    "cc.at.svc.bank": "Bank", "cc.at.svc.lender": "Moneylender", "cc.at.svc.warehouse": "Warehouse", "cc.at.svc.shipyard": "Shipyard",
    "cc.at.fx.tax": "tax cut {pct}", "cc.at.fx.audit": "desk checks ×{n}", "cc.at.fx.margin": "dealers take {pct} more", "cc.at.fx.yard": "the yard charges {pct} more",
    "cc.weather.sub.now": "Now", "cc.weather.sub.routes": "Routes", "cc.weather.sub.history": "History",
    "cc.rt.title": "Routes", "cc.rt.sub": "From {port}, on this month's forecast", "cc.rt.sub.sea": "Under sail for {port}", "cc.rt.sub.none": "From where the fleet lies",
    "cc.rt.sealed": "A house's routes stay private until the finale.", "cc.rt.none": "No fleet has sailed yet.",
    "cc.rt.what": "What this page shows", "cc.rt.about": "For a Captain sailing alone: the chance of a storm, of pirates and of the pirate queen on every route from where the fleet lies.",
    "cc.rt.legend": "Each line is coloured by the forecast it would sail under, heavier where a storm is likelier. The figure at each port is the storm chance.",
    "cc.rt.odds": "The odds by route", "cc.rt.to": "To", "cc.rt.storm": "Storm", "cc.rt.pirates": "Pirates", "cc.rt.queen": "Pirate queen", "cc.rt.queen.short": "Queen", "cc.rt.ban": "ban",
    "cc.rt.forecast": "Chances on the forecast, which holds about {pct} of the time.", "cc.rt.tap": "Tap a route to see how each figure is reached.",
    "cc.rt.hull": "Fleet hull", "cc.rt.cargo": "Cargo aboard, at cost", "cc.rt.protect": "Protection",
    "cc.rt.months": "{n} months left", "cc.rt.month": "1 month left", "cc.rt.unprotected": "None",
    "cc.rd.on": "Sailing under {level}, the worse of the two seas.", "cc.rd.distance": "Distance factor",
    "cc.rd.distance.how": "Distance {n}. Every route is held between ×{lo} and ×{hi}.",
    "cc.rd.storm.how": "{base} at {level} × {f}. For storms the distance factor stops at ×{cap}.",
    "cc.rd.pirates.how": "Rises with distance. Cargo and wealth aboard ×{allure}; the fleet's guns and name ×{flag}.",
    "cc.rd.queen.how": "Rises with distance. Her interest in this house ×{pull}.",
    "cc.rd.queen.safe": "She leaves a protected fleet alone. {n} months of protection left.", "cc.rd.queen.safe1": "She leaves a protected fleet alone. 1 month of protection left.",
    "cc.rd.cargo.how": "What a storm or a fight puts at stake.", "cc.rd.bans": "Banned there", "cc.rd.bans.how": "{port} will not land these.",
    "cc.rd.caveat": "These are chances on the forecast, which holds about {pct} of the time. If the sea comes different, the storm chance is the one for the sea that came. A fleet a storm has hit is found by pirates less often.",
    "cc.hx.title": "Storm history", "cc.hx.sub": "Every storm that landed, newest first", "cc.hx.none": "No storm has landed on a fleet this game.",
    "cc.hx.storm": "Storm", "cc.hx.typhoon": "Typhoon", "cc.hx.hit": "{n} ships hit, {d} hull points lost", "cc.hx.hit1": "1 ship hit, {d} hull points lost",
    "cc.hx.off": "blown to {port}", "cc.hx.cargo": "{n} units overboard", "cc.hx.guns": "{n} guns lost",
    "cc.hx.tally": "The tally", "cc.hx.voyages": "Voyages", "cc.hx.storms": "Storms landed", "cc.hx.typhoons": "{n} in a typhoon",
    "cc.hx.offcourse": "Blown off course", "cc.hx.wrecks": "Fleets wrecked",
    "cc.hx.held": "How often the forecast came true", "cc.hx.of": "{a} of {b} months", "cc.hx.held.note": "A month counts when the sea came exactly as forecast.",
    "cc.fleet.title": "Fleet", "cc.fleet.sub": "Hull condition, ship by ship",
    "cc.fleet.none": "No ships to show.", "cc.fleet.sound": "Sound", "cc.fleet.crippled": "Crippled", "cc.fleet.ship": "Ship {n}",
    "cc.fleet.log": "Storms and fights", "cc.fleet.quiet": "No storm or fight on the wire.",
    "cc.fleet.more": "Ship names, guns, holds, wages and repairs come with the Fleet milestone.",
    "cc.tr.title": "Treasury", "cc.tr.sub": "Net worth, month by month",
    "cc.tr.month": "Month", "cc.tr.worth": "Net worth", "cc.tr.change": "Change", "cc.tr.none": "No month has closed yet.",
    "cc.tr.books": "The books", "cc.tr.best": "Best month", "cc.tr.worst": "Worst month", "cc.tr.now": "Net worth now",
    "cc.tr.sealed": "Silver, bank and debt stay shut until the finale.",
    "cc.tr.more": "The balance sheet, bank interest, debt and monthly costs come with the Treasury milestone.",
    "cc.wire.title": "Wire", "cc.wire.sub": "Everything recorded, newest first",
    "cc.wire.month": "This month", "cc.wire.none": "Nothing recorded yet.", "cc.wire.quiet": "Nothing yet this month."
  };

  /* Text for a key, through dashboard.js's W() so an Admin override wins; DEF is the fallback. */
  function t(key, vars) {
    const k = "dash." + key, src = (typeof T !== "undefined" && T[k] != null) ? T[k] : (DEF[key] != null ? DEF[key] : key);
    return src.replace(/\{(\w+)\}/g, (m, n) => (vars && vars[n] != null ? vars[n] : m));
  }
  const te = (key, vars) => esc(t(key, vars));
  const tabName = k => t("cc.tab." + k);

  /* ------------------------------------------------------------ Watch Mode -- */
  /* When may Watch Mode turn the page? st: { on, held, busy, hidden, pageAt, lastTouch }. Returns the time the next
     turn is due, or null while something is holding the page. A touch pushes the turn out by the idle delay. */
  function dueAt(st) {
    if (!st.on || st.held || st.busy || st.hidden) return null;
    return Math.max(st.pageAt + TURN_MS, (st.lastTouch || 0) + IDLE_MS);
  }
  /* How much of the bar under the open tab is filled (0 to 1), and the note for the controls. */
  function progress(st, now) {
    const due = dueAt(st);
    if (due === null) return { frac: st.held ? 1 : 0, note: !st.on ? t("cc.watch.off") : st.held ? t("cc.watch.held") : t("cc.watch.busy") };
    const left = due - now, waiting = left > TURN_MS;
    return { frac: waiting ? 0 : Math.max(0, Math.min(1, 1 - left / TURN_MS)),
             note: waiting ? t("cc.watch.wait", { n: Math.ceil((left - TURN_MS) / 1000) }) : t("cc.watch.on") };
  }
  /* The tabs Watch Mode tours on this screen: every tab the Captain has not unticked (never none at all). */
  function tour(skip) {
    const list = KEYS.filter(k => !skip.has(k));
    return list.length ? list : KEYS.slice();
  }
  function readSkip() {
    try { return new Set(String(store("seatrader_dash_watch_skip") || "").split(",").filter(k => KEYS.includes(k))); }
    catch (e) { return new Set(); }
  }
  function writeSkip(skip) {
    try { store("seatrader_dash_watch_skip", skip.size ? [...skip].join(",") : null); } catch (e) { /* private window */ }
  }

  /* ------------------------------------------------------------ the tab bar and the drawer -- */
  function tabsHtml(page, locked) {
    return PAGES.map(p => {
      const sealed = locked && SEALED.has(p.k);
      return `<button type="button" role="tab" aria-selected="${p.k === page}" class="pw-tab${p.k === page ? " on" : ""}${sealed ? " sealed" : ""}" data-page="${p.k}"><i>${p.n}</i>${esc(tabName(p.k))}${sealed ? `<span class="visually-hidden"> (${te("cc.sealed.tab")})</span>` : ""}<span class="pw-prog"></span></button>`;
    }).join("");
  }
  function drawerHtml(page, skip) {
    return `<h2 id="drawer-title">${te("cc.drawer")}</h2><p class="pw-note">${te("cc.drawer.note")}</p>
      <ul class="drawer-list">${PAGES.map(p => `<li><button type="button" class="drawer-go${p.k === page ? " on" : ""}" data-page="${p.k}"><i>${p.n}</i><b>${esc(tabName(p.k))}</b></button>
        <label class="drawer-watch"><input type="checkbox" data-watch="${p.k}"${skip.has(p.k) ? "" : " checked"}><span>${te("cc.drawer.in")}</span></label></li>`).join("")}</ul>`;
  }

  /* ------------------------------------------------------------ the context bar -- */
  const levelName = lv => (D.weather || [])[lv] || String(lv);
  const seaName = r => (D.regions[r] || {}).name || r || "";
  const pct = x => Math.round(x * 100) + "%";
  function chip(page, label, value, extra, cls) {
    return `<button type="button" class="cx-chip${cls ? " " + cls : ""}" data-page="${page}"><small>${esc(label)}</small><b>${value}</b>${extra ? `<span>${extra}</span>` : ""}</button>`;
  }
  function fleetWords(f) {
    if (!f || !f.ships) return { main: te("cc.bar.nofleet"), sub: "" };
    const n = f.ships === 1 ? t("cc.bar.ship") : t("cc.bar.ships", { n: f.ships });
    return { main: f.hull == null ? esc(n) : pct(f.hull), sub: esc(n) + (f.crippled ? " &middot; " + te("cc.bar.crippled", { n: f.crippled }) : "") };
  }
  /* The Captain's own chips in an open solo game; table-wide chips with rivals at the table. */
  function contextHtml() {
    const c = F.context;
    if (!c) return "";
    const out = [], cap = c.captain;
    if (cap) {
      const sailing = cap.at_sea, where = sailing && cap.dest ? pn(cap.dest) : pn(cap.port);
      out.push(chip("lanes", sailing ? (cap.dest ? t("cc.bar.bound") : t("cc.bar.sea")) : t("cc.bar.port"), where || "&mdash;"));
      const ch = cap.worth_change;
      out.push(chip("treasury", t("cc.bar.worth"), money(cap.worth),
        ch == null ? "" : `<em class="${ch < 0 ? "down" : "up"}">${signed(ch)}</em> ${te("cc.bar.month")}`));
      const fw = fleetWords(cap.fleet);
      out.push(chip("fleet", t("cc.bar.fleet"), fw.main, fw.sub, cap.fleet && cap.fleet.crippled ? "warn" : ""));
    } else {
      const hs = ranked();
      out.push(chip("race", t("cc.bar.houses"), String(c.houses)));
      if (hs.length && c.phase !== "lobby") out.push(chip("race", t("cc.bar.leader"), esc(hs[0].firm), money(hs[0].worth)));
    }
    if (c.worst_sea && c.phase !== "lobby") {
      const lv = c.worst_sea.level;
      out.push(chip("weather", t("cc.bar.weather"), esc(levelName(lv)), lv ? esc(seaName(c.worst_sea.region)) : "", "wx" + lv));
    }
    if (cap && cap.rank) out.push(chip("race", t("cc.bar.rank"), esc(cap.rank)));
    return out.join("");
  }

  /* ------------------------------------------------------------ the five new pages -- */
  const leaf = (title, sub, body) => `<h2>${esc(title)}${sub ? `<small>${esc(sub)}</small>` : ""}</h2><div class="pg">${body}</div>`;
  const fact = (page, label, value, sub, cls) =>
    `<button type="button" class="cc-fact${cls ? " " + cls : ""}" data-page="${page}"><small>${esc(label)}</small><b>${value}</b>${sub ? `<span>${sub}</span>` : ""}</button>`;
  function wireRows(items, empty) {
    if (!items.length) return `<p class="pw-note">${esc(empty)}</p>`;
    return `<ul class="pw-list cc-wire">${items.map(e => {
      const h = house(e.pid), when = e.turn != null ? dateOfTurn(e.turn) : "";
      return `<li style="--house:${h ? hcol(h) : "#8a2219"}"><span class="pw-dot"></span><b>${tapeText(e)}</b><small>${esc(when)}</small></li>`;
    }).join("")}</ul>`;
  }
  const told = () => (F.tape || []).filter(e => tapeText(e));

  function pageNow() {
    const c = F.context || {}, cap = c.captain, facts = [];
    const lobby = S.phase === "lobby", ended = S.phase === "ended";
    const months = lobby ? fact("race", t("cc.now.months"), "&mdash;", te("cc.now.lobby"))
      : ended ? fact("race", t("cc.now.months"), "0", te("cc.now.ended"))
      : c.months_left != null ? fact("race", t("cc.now.months"), String(c.months_left), te("cc.now.of", { n: c.months_total })) : "";
    if (cap) {
      const ch = cap.worth_change, fw = fleetWords(cap.fleet);
      facts.push(fact("treasury", t("cc.now.worth"), money(cap.worth),
        ch == null ? te("cc.now.first") : `<em class="${ch < 0 ? "down" : "up"}">${signed(ch)}</em> ${te("cc.bar.month")}`, "wide"));
      if (months) facts.push(months);
      facts.push(fact("fleet", t("cc.now.fleet"), fw.main, fw.sub, cap.fleet && cap.fleet.crippled ? "warn" : ""));
    } else {
      const hs = ranked();
      if (hs.length && !lobby) facts.push(fact("race", t("cc.bar.leader"), esc(hs[0].firm), money(hs[0].worth), "wide"));
      if (months) facts.push(months);
    }
    if (c.worst_sea && !lobby) {
      const lv = c.worst_sea.level;
      facts.push(fact("weather", t("cc.now.sea"), esc(levelName(lv)), esc(seaName(c.worst_sea.region)) + " &middot; " + te("cc.now.forecast"), "wx" + lv));
    }
    if (!F.locked && F.market_effects) {
      const n = F.market_effects.length;
      facts.push(fact("markets", t("cc.now.markets"), String(n), te(n === 1 ? "cc.now.effect" : n ? "cc.now.effects" : "cc.now.quiet", { n })));
    }
    const banned = (S.crackdown || []).map(k => pn(k)).filter(Boolean);
    if (!lobby) facts.push(fact("lanes", t("cc.now.bans"), String(banned.length), banned.length ? banned.join(", ") : te("cc.now.noban"), banned.length ? "warn" : ""));
    const left = leaf(t("cc.now.title"), lobby ? t("cc.now.lobby") : (S.date || F.date || "") + " · " + t("cc.now.sub"), `<div class="cc-facts">${facts.join("")}</div>`);
    /* the chalkboard of month times, which used to hang beside the stage */
    const right = leaf(t("cc.now.latest"), "", wireRows(told().slice(-6).reverse(), t("cc.now.nothing")) + (lobby ? "" : `<div class="pw-chalk cc-chalk">${chalkHtml()}</div>`));
    return { left, right };
  }

  /* ---- THE MONSOON OBSERVATORY (Phase 3): the Weather tab's three pages. Now is this month's forecast; Routes is
     what the rules say about sailing from where the fleet lies to every other port; History is the storms that
     have landed. Everything shown is the server's (feed.weather, feed.routes). Nothing here says a route is safe
     or advises one: it gives the odds and what went into them. ---- */
  const SUBS = { weather: ["now", "routes", "history"], lanes: ["standing", "tax", "shares", "stores", "jobs", "bans"] };
  const sub = { weather: "now", lanes: "standing" };
  let atlasPort = "";          // the port whose dossier fills the Atlas's right leaf; "" shows the layer's ranked list
  const subOf = page => (SUBS[page] ? sub[page] : "");
  function setSub(page, v) { if (SUBS[page] && SUBS[page].includes(v)) sub[page] = v; }
  /* Watch Mode coming round to a tab again shows its next page, so a watched screen tours all three. */
  function lap(page) {
    const list = SUBS[page];
    if (list) sub[page] = list[(list.indexOf(sub[page]) + 1) % list.length];
    if (page === "lanes") {      // a watched Atlas tours its layers over the port the fleet lies in
      const cap = (F && F.context || {}).captain;
      atlasPort = cap && D.ports[cap.port] ? cap.port : "";
    }
  }
  function setPort(k) { atlasPort = k && D.ports[k] ? k : ""; }
  function subsHtml(page) {
    return `<nav class="cc-subs" aria-label="${te("cc.tab." + page)}">${SUBS[page].map(v =>
      `<button type="button" class="cc-sub${sub[page] === v ? " on" : ""}" aria-pressed="${sub[page] === v}" data-sub="${v}">${te("cc." + page + ".sub." + v)}</button>`).join("")}</nav>`;
  }
  const pc = (x, digits) => { const v = x * 100; return (digits == null ? (v && v < 10 ? v.toFixed(1) : v.toFixed(0)) : v.toFixed(digits)).replace(/\.0$/, "") + "%"; };
  const wxSeas = () => { const w = F.weather || {}, out = {}; Object.entries(w.seas || {}).forEach(([r, v]) => { out[r] = v.level; }); return Object.keys(out).length ? out : ((F.context || {}).seas || S.weather || {}); };
  const stormBase = () => (F.weather || {}).storm_chance || (D.voyage_risk || {}).storm_chance || [];
  const accuracy = () => { const a = (F.weather || {}).forecast_accuracy; return a != null ? a : (F.context || {}).forecast_accuracy; };

  function wxNow() {
    const seas = wxSeas(), rows = Object.entries(seas).sort((a, b) => b[1] - a[1]);
    const top = Math.max(1, (D.weather || []).length - 1), cap = (F.context || {}).captain, w = F.weather || {};
    const here = cap && D.ports[cap.port] ? D.ports[cap.port].region : null;
    const chart = cropChart(Chart.svg({ data: D, players: S.players || [], weather: seas, crackdown: [], hideRose: true }));
    const left = leaf(t("cc.wx.title"), t("cc.wx.sub"), subsHtml("weather") + `<div class="chart-wrap" id="dash-chart">${chart}</div>`);
    const list = `<ul class="instrument-list cc-seas">${rows.map(([r, lv]) => {
      const ports = (((w.seas || {})[r] || {}).harbours || []).map(k => pn(k)).filter(Boolean).join(", ");
      return `<li class="wx${lv}"><b>${esc(seaName(r))}${r === here ? ` <i class="cc-here">${te("cc.wx.here")}</i>` : ""}</b><span>${esc(levelName(lv))}</span><meter min="0" max="${top}" low="${top / 3}" high="${top * 2 / 3}" optimum="0" value="${lv}"></meter>${ports ? `<small>${ports}</small>` : ""}</li>`;
    }).join("")}</ul>`;
    const vr = D.voyage_risk || {}, chances = stormBase();
    const odds = chances.length ? `<h3>${te("cc.wx.odds")}</h3><table><thead><tr><th>${te("cc.wx.level")}</th><th class="num">${te("cc.wx.chance")}</th></tr></thead><tbody>${
      chances.map((ch, lv) => `<tr class="wx${lv}"><td>${esc(levelName(lv))}</td><td class="num">${pc(ch)}</td></tr>`).join("")}</tbody></table>
      <p class="pw-note">${te("cc.wx.base", { lo: "×" + vr.risk_min, hi: "×" + vr.risk_max })}</p>` : "";
    const acc = accuracy();
    const notes = `<p class="pw-note">${acc != null ? te("cc.wx.holds", { pct: pc(acc, 0) }) + " " : ""}${te("cc.wx.route")}</p>`;
    return { left, right: leaf(t("cc.wx.seas"), "", list + notes + odds), fit: "dash-chart" };
  }

  /* The routes on the chart: one line from the fleet to each port, coloured by the forecast it would sail under and
     heavier where a storm is likelier, with the storm chance written at the far end. */
  function routeLines(rt) {
    const a = D.ports[rt.from];
    if (!a) return "";
    let s = '<g class="cc-routes" style="pointer-events:none">';
    rt.routes.forEach(r => {
      const b = D.ports[r.dest];
      if (!b) return;
      const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2, dx = b.x - a.x, dy = b.y - a.y, len = Math.hypot(dx, dy) || 1;
      const cx = mx - dy / len * 18, cy = my + dx / len * 18;
      s += `<path class="wxl${r.level}${rt.dest === r.dest ? " bound" : ""}" d="M${a.x} ${a.y} Q${cx.toFixed(1)} ${cy.toFixed(1)} ${b.x} ${b.y}" fill="none" stroke-linecap="round" stroke-width="${(2.5 + Math.min(1, r.storm / .4) * 7).toFixed(1)}"/>`;
    });
    rt.routes.forEach(r => {
      const b = D.ports[r.dest];
      if (b) s += `<text class="cc-route-pct wxt${r.level}" x="${b.x}" y="${b.y - 20}" text-anchor="middle">${pc(r.storm)}</text>`;
    });
    return s + `<circle class="cc-route-from" cx="${a.x}" cy="${a.y}" r="13"/></g>`;
  }
  function wxRoutes() {
    const rt = F.routes, head = subsHtml("weather");
    if (!rt) {
      const why = F.locked ? `<div class="pw-block-locked">${stamp(W("sealed"), t("cc.rt.sealed"))}</div>` : `<p class="pw-note">${te("cc.rt.none")}</p>`;
      return { left: leaf(t("cc.rt.title"), t("cc.rt.sub.none"), head + why), right: leaf(t("cc.rt.what"), "", `<p class="pw-note">${te("cc.rt.about")}</p>`) };
    }
    const seas = wxSeas(), inp = rt.inputs || {};
    const chart = withOverlay(cropChart(Chart.svg({ data: D, players: [], weather: seas, crackdown: S.crackdown || [], here: rt.from, dest: rt.dest || undefined, hideRose: true, hideWeather: true })), routeLines(rt));
    const under = rt.at_sea && rt.dest ? t("cc.rt.sub.sea", { port: pn(rt.dest) }) : t("cc.rt.sub", { port: pn(rt.from) });
    const left = leaf(t("cc.rt.title"), under, head + `<div class="chart-wrap" id="dash-chart">${chart}</div>
      <p class="pw-note">${te("cc.rt.legend")}</p>`);
    const rows = rt.routes.slice().sort((a, b) => b.storm - a.storm || a.distance - b.distance).map(r =>
      `<li><button type="button" class="cc-route wx${r.level}${rt.dest === r.dest ? " bound" : ""}" data-route="${esc(r.dest)}">
        <span class="cc-route-name"><b>${pn(r.dest)}</b><small>${esc(levelName(r.level))} &middot; &times;${r.risk.toFixed(2)}${r.banned.length ? " &middot; " + te("cc.rt.ban") : ""}</small></span>
        <span class="num"><b>${pc(r.storm)}</b></span><span class="num">${pc(r.pirates)}</span><span class="num">${inp.protect > 0 ? "&mdash;" : pc(r.lord)}</span></button></li>`).join("");
    const table = `<div class="cc-route-head" aria-hidden="true"><span>${te("cc.rt.to")}</span><span class="num">${te("cc.rt.storm")}</span><span class="num">${te("cc.rt.pirates")}</span><span class="num">${te("cc.rt.queen.short")}</span></div>
      <ul class="cc-route-list">${rows}</ul>`;
    const acc = accuracy();
    const notes = `<p class="pw-note">${acc != null ? te("cc.rt.forecast", { pct: pc(acc, 0) }) + " " : ""}${te("cc.rt.tap")}</p>
      <ul class="instrument-list cc-stake"><li><b>${te("cc.rt.hull")}</b><span>${pc(inp.hull || 0, 0)}</span></li><li><b>${te("cc.rt.cargo")}</b><span>${money(inp.cargo_cost || 0)}</span></li>
      <li><b>${te("cc.rt.protect")}</b><span>${inp.protect > 0 ? te(inp.protect === 1 ? "cc.rt.month" : "cc.rt.months", { n: inp.protect }) : te("cc.rt.unprotected")}</span></li></ul>`;
    return { left, right: leaf(t("cc.rt.odds"), "", table + notes), fit: "dash-chart" };
  }
  /* Explain: how one route's odds were reached, in the server's own factors. Returned for the detail dialog. */
  function routeDetail(dest) {
    const rt = F.routes, r = rt && rt.routes.find(x => x.dest === dest);
    if (!r) return null;
    const inp = rt.inputs || {}, base = stormBase()[r.level], capped = Math.min(r.risk, inp.storm_risk_cap || r.risk);
    const here = D.ports[rt.from] || {}, there = D.ports[r.dest] || {}, seas = wxSeas();
    const seaLine = [here.region, there.region].filter((x, i, a) => x && a.indexOf(x) === i).map(x => `${esc(seaName(x))}: ${esc(levelName(seas[x] || 0))}`).join(" &middot; ");
    const line = (label, value, how) => `<li><b>${esc(label)}</b><span><strong>${value}</strong>${how ? `<small>${how}</small>` : ""}</span></li>`;
    const body = `<p class="pw-note">${te("cc.rd.on", { level: levelName(r.level) })} ${seaLine}</p>
      <ul class="instrument-list cc-explain">
        ${line(t("cc.rd.distance"), "&times;" + r.risk.toFixed(2), te("cc.rd.distance.how", { n: r.distance, lo: inp.risk_min, hi: inp.risk_max }))}
        ${line(t("cc.rt.storm"), pc(r.storm), base != null ? te("cc.rd.storm.how", { base: pc(base), level: levelName(r.level), f: capped.toFixed(2), cap: inp.storm_risk_cap }) : "")}
        ${line(t("cc.rt.pirates"), pc(r.pirates), te("cc.rd.pirates.how", { allure: (inp.allure || 1).toFixed(2), flag: (inp.flag_deter || 1).toFixed(2) }))}
        ${line(t("cc.rt.queen"), inp.protect > 0 ? "&mdash;" : pc(r.lord), inp.protect > 0 ? te(inp.protect === 1 ? "cc.rd.queen.safe1" : "cc.rd.queen.safe", { n: inp.protect }) : te("cc.rd.queen.how", { pull: (inp.lord_pull || 1).toFixed(2) }))}
        ${line(t("cc.rt.hull"), pc(inp.hull || 0, 0), "")}
        ${line(t("cc.rt.cargo"), money(inp.cargo_cost || 0), te("cc.rd.cargo.how"))}
        ${r.banned.length ? line(t("cc.rd.bans"), r.banned.map(g => esc(gn(g))).join(", "), te("cc.rd.bans.how", { port: pn(r.dest) })) : ""}
      </ul>
      <p class="pw-note">${te("cc.rd.caveat", { pct: pc(inp.forecast_accuracy != null ? inp.forecast_accuracy : accuracy() || 0, 0) })}</p>`;
    return { title: `${pn(rt.from)} → ${pn(r.dest)}`, body };
  }
  function detail(kind) {
    return typeof kind === "string" && kind.startsWith("route:") ? routeDetail(kind.slice(6)) : null;
  }

  function wxHistory() {
    const h = (F.weather || {}).history || { storms: [], totals: {}, seas: {} }, tot = h.totals || {}, many = (F.houses || []).length > 1;
    const rows = (h.storms || []).map(x => {
      const who = house(x.pid);
      const lost = [x.cargo ? te("cc.hx.cargo", { n: x.cargo }) : "", x.guns ? te("cc.hx.guns", { n: x.guns }) : ""].filter(Boolean).join(" &middot; ");
      return `<li class="${x.typhoon ? "wx3" : "wx2"}"><b>${esc(x.date)}${many && who ? " &middot; " + esc(who.firm) : ""}</b>
        <span>${te(x.typhoon ? "cc.hx.typhoon" : "cc.hx.storm")}${x.band ? " &middot; " + esc(x.band) : ""}</span>
        <small>${te(x.ships === 1 ? "cc.hx.hit1" : "cc.hx.hit", { n: x.ships, d: x.damage })}${x.offcourse ? " &middot; " + te("cc.hx.off", { port: pn(x.offcourse) }) : ""}${lost ? " &middot; " + lost : ""}</small></li>`;
    }).join("");
    const left = leaf(t("cc.hx.title"), t("cc.hx.sub"), subsHtml("weather") + (rows ? `<ul class="instrument-list cc-storms">${rows}</ul>` : `<p class="pw-note">${te("cc.hx.none")}</p>`));
    const facts = [fact("weather", t("cc.hx.voyages"), String(tot.voyages || 0), ""), fact("weather", t("cc.hx.storms"), String(tot.storms || 0), tot.typhoons ? te("cc.hx.typhoons", { n: tot.typhoons }) : ""),
      fact("weather", t("cc.hx.offcourse"), String(tot.offcourse || 0), ""), fact("weather", t("cc.hx.wrecks"), String(tot.wrecks || 0), "", tot.wrecks ? "warn" : "")];
    const seas = Object.entries(h.seas || {}).filter(([, v]) => v.months);
    const held = seas.length ? `<h3>${te("cc.hx.held")}</h3><table><tbody>${seas.map(([r, v]) =>
      `<tr><td>${esc(seaName(r))}</td><td class="num">${te("cc.hx.of", { a: v.held, b: v.months })}</td><td class="num">${pc(v.held / v.months, 0)}</td></tr>`).join("")}</tbody></table>
      <p class="pw-note">${te("cc.hx.held.note")}</p>` : "";
    return { left, right: leaf(t("cc.hx.tally"), "", `<div class="cc-facts">${facts.join("")}</div>${held}`) };
  }
  function pageWeather() {
    return sub.weather === "routes" ? wxRoutes() : sub.weather === "history" ? wxHistory() : wxNow();
  }

  /* ---- THE CAPTAIN'S ATLAS (Phase 4): one chart of the ten ports with a layer at a time, and a dossier for the port
     tapped. Every figure is feed.atlas (an open solo game). With rivals at the table that block is absent: the two
     layers that are public knowledge (who holds each port's shares, and the bans) still draw, the rest are sealed. ---- */
  const BANDS = ["hostile", "cool", "neutral", "warm", "favoured"];
  const bandName = b => (typeof T !== "undefined" && T["stat.standing_" + BANDS[b]]) || t("cc.band." + b);
  const PUBLIC_LAYERS = new Set(["shares", "bans"]);
  const offersOf = () => { const c = (F.career || {}).commissions || {}; return { active: c.active || [], offers: Object.values(c.offers || {}).filter(Boolean) }; };
  /* One port on one layer: { text, cls, sort, sub } or null when the layer has nothing to say about it. */
  function atlasCell(layer, k) {
    const a = F.atlas ? F.atlas.ports[k] : null;
    if (layer === "bans") {
      const goods = a ? a.banned : ((S.bans || {})[k] || []), on = a ? a.crackdown : (S.crackdown || []).includes(k);
      return on || goods.length ? { text: goods.length ? goods.map(g => gn(g)).join(", ") : t("cc.at.ban"), cls: "bad", sort: goods.length || 1, sub: t("cc.at.banned") } : null;
    }
    if (layer === "shares") {
      if (a) return { text: a.shares.mine + "/" + a.shares.total, cls: a.shares.patron_me ? "crown" : a.shares.mine ? "mine" : "", sort: a.shares.mine * 100 + (a.shares.total - a.shares.left),
                      sub: (a.shares.patron ? t("cc.at.patron", { firm: a.shares.patron }) + " · " : "") + t("cc.at.left", { n: a.shares.left }) };
      const pub = (F.ports || {})[k];
      if (!pub) return null;
      const held = Object.values(pub.shares || {}).reduce((x, n) => x + n, 0);
      return { text: held + "/" + pub.total, cls: held ? "mine" : "", sort: held, sub: t("cc.at.held", { n: held, total: pub.total }) };
    }
    if (!a) return null;
    if (layer === "standing") return { text: String(a.rep), cls: "b" + a.band, sort: a.rep, sub: bandName(a.band) };
    if (layer === "tax") {
      const cut = a.tax.mine < a.tax.base - 1e-9;
      return { text: pc(a.tax.mine), cls: cut ? "good" : "", sort: -a.tax.mine,
               sub: a.tax.home_free ? t("cc.at.homefree") : cut ? t("cc.at.taxwas", { pct: pc(a.tax.base) }) : t("cc.at.taxfull") };
    }
    if (layer === "stores") return a.warehouse ? { text: kfmt(a.warehouse.used) + "/" + kfmt(a.warehouse.cap), cls: a.warehouse.used ? "mine" : "", sort: a.warehouse.used,
      sub: a.warehouse.home ? t("cc.at.homestore") : t("cc.at.rent", { rent: money(a.warehouse.rent) }) } : null;
    if (layer === "jobs") {
      const o = offersOf(), act = o.active.filter(c => c.port === k), off = o.offers.filter(c => c.port === k);
      return act.length || off.length ? { text: act.length ? String(act.length) : "?", cls: act.length ? "mine" : "", sort: act.length * 10 + off.length,
        sub: [...act.map(c => c.text), ...off.map(c => t("cc.at.offer") + ": " + c.text)].join(" · ") } : null;
    }
    return null;
  }
  function atlasPins(layer) {
    let s = '<g class="cc-pins">';
    Object.keys(D.ports).forEach(k => {
      const p = D.ports[k], c = atlasCell(layer, k), on = k === atlasPort;
      const text = c ? c.text : "", w = Math.max(60, Math.min(300, text.length * 17 + 26));
      s += `<g class="cc-pin${c ? " " + c.cls : " none"}${on ? " on" : ""}" data-port="${esc(k)}" role="button" tabindex="0" aria-label="${esc(p.name)}${c ? ": " + esc(text) : ""}" aria-pressed="${on}">
        <circle class="hit" cx="${p.x}" cy="${p.y}" r="34"/>${on ? `<circle class="ring" cx="${p.x}" cy="${p.y}" r="17"/>` : ""}
        ${c ? `<rect x="${(p.x - w / 2).toFixed(1)}" y="${p.y + 16}" width="${w}" height="40" rx="6"/><text x="${p.x}" y="${p.y + 46}" text-anchor="middle">${esc(text)}</text>` : ""}</g>`;
    });
    return s + "</g>";
  }
  function atlasList(layer) {
    const sealed = !F.atlas && !PUBLIC_LAYERS.has(layer);
    if (sealed) return F.locked ? `<div class="pw-block-locked">${stamp(W("sealed"), t("cc.at.sealed"))}</div>` : `<p class="pw-note">${te("cc.at.none")}</p>`;
    const rows = Object.keys(D.ports).map(k => ({ k, c: atlasCell(layer, k) })).filter(r => r.c).sort((x, y) => y.c.sort - x.c.sort || pn(x.k).localeCompare(pn(y.k)));
    if (!rows.length) return `<p class="pw-note">${te("cc.at.empty." + layer)}</p>`;
    return `<ul class="cc-route-list">${rows.map(r => `<li><button type="button" class="cc-port ${r.c.cls}" data-port="${esc(r.k)}">
      <span class="cc-route-name"><b>${pn(r.k)}</b><small>${esc(r.c.sub || "")}</small></span><span class="num"><b>${esc(r.c.text)}</b></span></button></li>`).join("")}</ul>
      <p class="pw-note">${te("cc.at.tap")}</p>`;
  }
  function atlasDossier(k) {
    const a = F.atlas && F.atlas.ports[k], port = D.ports[k] || {};
    const back = `<button type="button" class="cc-sub cc-back" data-port="">${te("cc.at.all")}</button>`;
    if (!a) {
      const sh = atlasCell("shares", k), ban = atlasCell("bans", k);
      return back + `<ul class="instrument-list cc-dossier">${sh ? `<li><b>${te("cc.lanes.sub.shares")}</b><span>${esc(sh.sub)}</span></li>` : ""}${ban ? `<li class="bad"><b>${te("cc.at.banned")}</b><span>${esc(ban.text)}</span></li>` : ""}</ul>
        ${F.locked ? `<div class="pw-block-locked">${stamp(W("sealed"), t("cc.at.sealed"))}</div>` : ""}`;
    }
    const line = (label, value, how, cls) => `<li${cls ? ` class="${cls}"` : ""}><b>${esc(label)}</b><span><strong>${value}</strong>${how ? `<small>${how}</small>` : ""}</span></li>`;
    const tags = [a.here ? t("cc.at.here") : "", a.home ? t("cc.at.home") : "", ...["bank", "lender", "warehouse", "shipyard"].filter(x => a.services[x]).map(x => t("cc.at.svc." + x))].filter(Boolean);
    const fx = [], e = a.effects || {};
    if (e.tax_cut > 0) fx.push(te("cc.at.fx.tax", { pct: pc(e.tax_cut) }));
    if (e.audit && e.audit !== 1) fx.push(te("cc.at.fx.audit", { n: e.audit }));
    if (e.margin) fx.push(te("cc.at.fx.margin", { pct: pc(Math.abs(e.margin)) }));
    if (e.yard) fx.push(te("cc.at.fx.yard", { pct: pc(Math.abs(e.yard)) }));
    const tax = a.tax, cut = tax.mine < tax.base - 1e-9;
    const why = tax.home_free ? te("cc.at.homefree") : [cut ? te("cc.at.taxwas", { pct: pc(tax.base) }) : te("cc.at.taxfull"), tax.share_cut > 0 ? te("cc.at.sharecut", { pct: pc(tax.share_cut) }) : "",
      (F.atlas.tax_holiday || 0) > 0 ? te("cc.at.holiday", { n: F.atlas.tax_holiday }) : ""].filter(Boolean).join(" ");
    const sh = a.shares, wh = a.warehouse, o = offersOf();
    const jobs = [...o.active.filter(c => c.port === k).map(c => `${esc(c.text)} <small>${te("cc.at.due", { date: c.due_date || "" })}</small>`),
                  ...o.offers.filter(c => c.port === k).map(c => `${esc(c.text)} <small>${te("cc.at.offer")}</small>`)];
    const goods = wh ? Object.entries(wh.goods).filter(([, q]) => q > 0).sort((x, y) => y[1] - x[1]).map(([g, q]) => `${esc(gn(g))} ${q.toLocaleString()}`).join(", ") : "";
    return back + `<p class="cc-tags">${tags.map(x => `<span>${esc(x)}</span>`).join("")}</p><ul class="instrument-list cc-dossier">
      ${line(t("cc.lanes.sub.standing"), a.rep + " &middot; " + esc(bandName(a.band)), fx.join(" &middot; "), "b" + a.band)}
      ${line(t("cc.lanes.sub.tax"), pc(tax.mine), why, cut ? "good" : "")}
      ${line(t("cc.lanes.sub.shares"), te("cc.at.mine", { n: sh.mine, total: sh.total }), (sh.patron ? te("cc.at.patron", { firm: sh.patron }) + " &middot; " : "") + te("cc.at.left", { n: sh.left }), sh.patron_me ? "crown" : "")}
      ${wh ? line(t("cc.lanes.sub.stores"), te("cc.at.store", { used: wh.used.toLocaleString(), cap: wh.cap.toLocaleString() }), (wh.home ? te("cc.at.homestore") : te("cc.at.rent", { rent: money(wh.rent) })) + (goods ? " &middot; " + goods : ""))
           : line(t("cc.lanes.sub.stores"), "&mdash;", te(a.services.warehouse ? "cc.at.nostore" : "cc.at.nowarehouse"))}
      ${jobs.length ? line(t("cc.lanes.sub.jobs"), String(jobs.length), jobs.join("<br>")) : ""}
      ${a.crackdown || a.banned.length ? line(t("cc.at.banned"), a.banned.length ? a.banned.map(g => esc(gn(g))).join(", ") : te("cc.at.ban"), "", "bad") : ""}</ul>`;
  }
  function pageAtlas() {
    const layer = sub.lanes, k = D.ports[atlasPort] ? atlasPort : "", cap = (F.context || {}).captain;
    const chart = withOverlay(cropChart(Chart.svg({ data: D, players: F.atlas ? [] : S.players || [], crackdown: S.crackdown || [], here: cap ? cap.port : undefined, hideWeather: true, hideRose: true })), atlasPins(layer));
    const sh = F.atlas ? F.atlas.shares : null;
    const foot = layer === "shares" && sh ? `<p class="pw-note">${te("cc.at.shares.foot", { placed: sh.placed, earned: sh.earned, free: sh.free, cap: sh.cap })}</p>` : `<p class="pw-note">${te("cc.at.legend." + layer)}</p>`;
    const left = leaf(t("cc.at.title"), t("cc.at.sub." + layer), subsHtml("lanes") + `<div class="chart-wrap" id="dash-chart">${chart}</div>${foot}`);
    const right = k ? leaf(pn(k), seaName((D.ports[k] || {}).region), atlasDossier(k)) : leaf(t("cc.at.rank." + layer), "", atlasList(layer));
    return { left, right, fit: "dash-chart" };
  }

  const FLEET_NEWS = new Set(["storm_damage", "offcourse", "ship_lost", "ship_crippled", "shipwreck", "battle", "won", "retreat", "broke_off", "paid", "plundered"]);
  function pageFleet() {
    const hs = ranked();
    const rows = hs.map(h => {
      const ships = h.hull || [];
      const list = ships.length ? ships.map((sh, i) =>
        `<li class="${sh.crippled ? "bad" : ""}"><b>${te("cc.fleet.ship", { n: i + 1 })}</b><span>${pct(sh.hull)} &middot; ${te(sh.crippled ? "cc.fleet.crippled" : "cc.fleet.sound")}</span><meter min="0" max="1" low=".35" high=".7" optimum="1" value="${sh.hull}"></meter></li>`).join("")
        : `<li><span>${te("cc.fleet.none")}</span></li>`;
      return `${hs.length > 1 ? `<h3 style="--house:${hcol(h)}"><span class="pw-dot"></span>${esc(h.firm)}</h3>` : ""}<ul class="instrument-list cc-ships">${list}</ul>`;
    }).join("");
    const left = leaf(t("cc.fleet.title"), t("cc.fleet.sub"), rows || `<p class="pw-note">${te("cc.fleet.none")}</p>`);
    const news = told().filter(e => FLEET_NEWS.has(e.type)).slice(-8).reverse();
    const right = leaf(t("cc.fleet.log"), "", wireRows(news, t("cc.fleet.quiet")) + `<p class="pw-note cc-more">${te("cc.fleet.more")}</p>`);
    return { left, right };
  }

  function pageTreasury() {
    const hs = ranked(), one = hs.length === 1;
    let body;
    if (!hs.length) body = `<p class="pw-note">${te("cc.tr.none")}</p>`;
    else if (one) {
      const m = hs[0].months || [], rows = [];
      for (let i = m.length - 1; i >= Math.max(0, m.length - 12); i--) {
        const ch = i ? m[i].worth - m[i - 1].worth : null;
        rows.push(`<tr><td>${esc(m[i].date)}</td><td class="num">${money(m[i].worth)}</td><td class="num ${ch == null ? "" : ch < 0 ? "down" : "up"}">${ch == null ? "&mdash;" : signed(ch)}</td></tr>`);
      }
      body = rows.length ? `<table><thead><tr><th>${te("cc.tr.month")}</th><th class="num">${te("cc.tr.worth")}</th><th class="num">${te("cc.tr.change")}</th></tr></thead><tbody>${rows.join("")}</tbody></table>`
        : `<p class="pw-note">${te("cc.tr.none")}</p>`;
    } else {
      body = `<table><thead><tr><th></th><th class="num">${te("cc.tr.worth")}</th><th class="num">${te("cc.tr.change")}</th></tr></thead><tbody>${hs.map(h => {
        const g = gainsOf(h), last = g.length ? g[g.length - 1].gain : null;
        return `<tr><td><span class="pw-dot" style="--house:${hcol(h)}"></span>${esc(h.firm)}</td><td class="num">${money(h.worth)}</td><td class="num ${last == null ? "" : last < 0 ? "down" : "up"}">${last == null ? "&mdash;" : signed(last)}</td></tr>`;
      }).join("")}</tbody></table>`;
    }
    const left = leaf(t("cc.tr.title"), t("cc.tr.sub"), body);
    let best = null, worst = null;
    hs.forEach(h => gainsOf(h).forEach(g => {
      if (!best || g.gain > best.gain) best = { ...g, firm: h.firm };
      if (!worst || g.gain < worst.gain) worst = { ...g, firm: h.firm };
    }));
    const who = x => esc(x.date) + (one ? "" : " &middot; " + esc(x.firm));
    const facts = [];
    if (one) facts.push(fact("race", t("cc.tr.now"), money(hs[0].worth), ""));
    if (best) facts.push(fact("race", t("cc.tr.best"), `<em class="up">${signed(best.gain)}</em>`, who(best)));
    if (worst && worst !== best && worst.gain < 0) facts.push(fact("race", t("cc.tr.worst"), `<em class="down">${signed(worst.gain)}</em>`, who(worst)));
    const books = F.locked ? `<div class="pw-block-locked">${stamp(W("sealed"), t("cc.tr.sealed"))}</div>` : `<p class="pw-note cc-more">${te("cc.tr.more")}</p>`;
    return { left, right: leaf(t("cc.tr.books"), "", `<div class="cc-facts one">${facts.join("")}</div>${books}`) };
  }

  function pageWire() {
    const all = told().slice().reverse(), turn = F.turn;
    const left = leaf(t("cc.wire.title"), t("cc.wire.sub"), wireRows(all, t("cc.wire.none")));
    const right = leaf(t("cc.wire.month"), S.date || F.date || "", wireRows(all.filter(e => e.turn === turn), t("cc.wire.quiet")));
    return { left, right };
  }

  const BUILDERS = { now: pageNow, lanes: pageAtlas, weather: pageWeather, fleet: pageFleet, treasury: pageTreasury, wire: pageWire };

  return { PAGES, KEYS, SEALED, TURN_MS, IDLE_MS, DEF, t, tabName, dueAt, progress, tour, readSkip, writeSkip,
           tabsHtml, drawerHtml, contextHtml, BUILDERS, SUBS, subOf, setSub, lap, detail, setPort, port: () => atlasPort };
})();
