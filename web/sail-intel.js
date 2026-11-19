"use strict";

const SailIntel = (() => {
  const labels = { visits: "Visits", profit: "Trading P/L", shares: "Shares", standing: "Standing", risk: "Pirate risk" };
  const notes = {
    visits: "Ring fill compares completed arrivals with your most-visited port. Starting in a port is not an arrival.",
    profit: "Ring fill compares absolute realised trading P/L. Jade = profit; crimson = loss. Excludes tax, harbour dues and voyage costs.",
    shares: "Ring fill is your share of the port's total issue. The number is shares owned, not a percentage.",
    standing: "Ring fill shows local standing out of 100. Negative standing is crimson.",
    risk: "Ring fill shows the estimated pirate encounter chance on the route from your current port. Weather is shown separately."
  };
  let lens = "visits", key = "", rows = null, pending = "", error = false;
  const signed = n => (n > 0 ? "+" : "") + money(n);
  const compact = n => {
    const v = Math.abs(n), suffix = v >= 1e6 ? "m" : v >= 1e3 ? "k" : "";
    return (n < 0 ? "−" : n > 0 ? "+" : "") + CUR + (suffix ? (v / (suffix === "m" ? 1e6 : 1e3)).toFixed(1) : Math.round(v)) + suffix;
  };
  function signature() {
    return JSON.stringify([S.game_id, S.me.id, S.turn, S.me.books, S.me.cargo]);
  }
  function tips(k) {
    return (S.me.hot_tips || []).filter(tp => tp.port === k && D.goods[tp.good] && tp.ends >= S.turn && !hotGone(tp));
  }
  function metrics() {
    const me = S.me, historical = rows && key === signature();
    const maxVisits = Math.max(1, ...Object.values(historical ? rows : {}).map(r => r.visits));
    const maxProfit = Math.max(1, ...Object.values(historical ? rows : {}).map(r => Math.abs(r.profit)));
    const result = {};
    for (const k of Object.keys(D.ports)) {
      const r = historical ? rows[k] || { visits: 0, profit: 0, sales: 0 } : null;
      const shares = me.shares ? me.shares.mine[k] || 0 : null;
      const standing = me.rep[k] || 0, risk = k === me.port ? null : pirateRisk(me.port, k);
      let value, fill = 0, negative = false;
      if (lens === "visits") { value = r ? String(r.visits) : "—"; fill = r ? r.visits / maxVisits : 0; }
      if (lens === "profit") { value = r ? compact(r.profit) : "—"; fill = r ? Math.abs(r.profit) / maxProfit : 0; negative = !!r && r.profit < 0; }
      if (lens === "shares") { value = shares == null ? "Off" : String(shares); fill = shares / Math.max(1, (me.shares || {}).total || 1); }
      if (lens === "standing") { value = String(standing); fill = Math.abs(standing) / 100; negative = standing < 0; }
      if (lens === "risk") { value = risk == null ? "Here" : Math.round(risk * 100) + "%"; fill = risk || 0; negative = risk >= .22; }
      const hot = tips(k);
      const exact = lens === "profit" && r ? signed(r.profit) : value;
      result[k] = { value, fill: Math.max(0, Math.min(1, fill)), negative, positive: lens === "profit" && r && r.profit > 0, hot: hot.length > 0,
        title: `${D.ports[k].name}: ${labels[lens]} ${exact}${hot.length ? "; Hot tip: " + hot.map(tp => D.goods[tp.good].name).join(", ") : ""}` };
    }
    return result;
  }
  function detail(dest) {
    const k = dest || S.me.port, p = D.ports[k], me = S.me;
    const r = rows && key === signature() ? rows[k] || { visits: 0, profit: 0, sales: 0 } : null;
    const shares = me.shares, hot = tips(k), run = k === me.port ? null : tradeRun(k);
    const wx = Math.max(S.weather[p.region] || 0, S.weather[D.ports[me.port].region] || 0);
    const risk = k === me.port ? null : pirateRisk(me.port, k);
    const fact = (name, value, cls = "") => `<div><dt>${esc(name)}</dt><dd class="${cls}">${esc(value)}</dd></div>`;
    const tip = hot.map(tp => `<p class="si-tip"><b>HOT TIP · ${esc(D.goods[tp.good].name)}</b> ${S.turn < tp.lands ? `Boom expected in ${tp.lands - S.turn} month(s).` : "Boom window open."}${(S.bans[k] || []).includes(tp.good) ? " Cargo is currently banned here." : ""}</p>`).join("");
    const trade = !run ? "No known buy-here / sell-there opportunity." : `Best known trade: ${D.goods[run.g].name}, ${money(run.buy)} → approximately ${money(run.sell)} per unit (${Math.round(run.gain * 100)}%). Prices last seen ${run.age ? run.age + " month(s) ago" : "this month"}. Excludes voyage costs and tax.`;
    return `<section class="si-detail" aria-label="Selected port intelligence"><header><div><small>${k === me.port ? "CURRENT PORT" : "PLANNED DESTINATION"}</small><h3>${esc(p.name)}</h3></div><span>${esc(D.weather[wx])}${S.crackdown.includes(k) ? " · Customs crackdown" : ""}</span></header>
      <dl>${fact("Arrivals", r ? r.visits : "—")}${fact("Realised trading P/L", r ? signed(r.profit) : "—", r && r.profit < 0 ? "si-loss" : "si-profit")}${fact("Your shares", shares ? `${shares.mine[k] || 0} / ${shares.total}` : "Disabled")}${fact("Standing", me.rep[k] || 0)}${fact("Route pirate chance", risk == null ? "Already here" : Math.round(risk * 100) + "%")}</dl>
      ${tip}<p class="si-trade">${esc(k === me.port ? "Choose a destination on the chart or a port card to compare its route and trading opportunity." : trade)}</p></section>`;
  }
  function body(dest) {
    const waiting = !rows || key !== signature();
    return `<header class="si-head"><div><small>THE CAPTAIN'S CHART</small><h3>Port intelligence</h3></div><button type="button" data-intel-refresh ${pending ? "disabled" : ""}>Refresh record</button></header>
      <nav class="si-lenses" aria-label="Map data layer">${Object.entries(labels).map(([k, name]) => `<button type="button" data-intel-lens="${k}" aria-pressed="${lens === k}">${name}</button>`).join("")}</nav>
      <p class="si-key"><i class="si-key-ring"></i>${esc(notes[lens])} <b class="si-hot-key">✦ Hot tip</b></p>
      <p class="si-status" role="status">${error ? "Port history unavailable. Use Refresh record to retry; live shares, standing and route risk are still available." : waiting ? "Loading your port record…" : "Your record · this game · exact values below when you select a port."}</p>
      <div class="si-chart-scroll" tabindex="0" role="region" aria-label="Port chart; scroll sideways on small screens">${Chart.svg({ data: D, players: S.players, weather: S.weather, crackdown: S.crackdown, here: S.me.port, dest, clickable: !S.me.ready, mine: S.me.id, intel: metrics() })}</div>
      ${detail(dest)}`;
  }
  function paint() {
    const root = document.querySelector(".sail-intel");
    if (!root || !S || !S.me) return;
    const scroll = root.querySelector(".si-chart-scroll")?.scrollLeft || 0;
    const focusedLens = root.contains(document.activeElement) ? document.activeElement.dataset.intelLens : null;
    const dest = S.me.ready ? S.me.dest : ui.dest;
    root.innerHTML = body(dest);
    Chart.fit(root);
    root.querySelector(".si-chart-scroll").scrollLeft = scroll;
    if (focusedLens) root.querySelector(`[data-intel-lens="${focusedLens}"]`).focus({ preventScroll: true });
  }
  async function load(force = false) {
    const wanted = signature();
    if (pending === wanted || (!force && key === wanted)) return;
    pending = wanted; key = wanted; rows = null; error = false;
    try {
      const response = await fetch("/api/stats?scope=voyage&game=" + encodeURIComponent(S.game_id) + "&token=" + encodeURIComponent(token), { cache: "no-store" });
      if (!response.ok) throw new Error("HTTP " + response.status);
      const answer = await response.json();
      if (!answer.ok || !answer.voyage || !answer.voyage.me) throw new Error(answer.error || "Missing port record");
      if (key !== wanted) return;
      rows = Object.fromEntries(answer.voyage.me.ports.map(r => [r.port, r]));
    } catch (e) {
      console.error("Set Sail port history:", e);
      if (key === wanted) error = true;
    } finally {
      if (pending === wanted) pending = "";
      paint();
    }
  }
  document.addEventListener("click", e => {
    const button = e.target.closest("[data-intel-lens], [data-intel-refresh]");
    if (!button) return;
    if (button.dataset.intelLens) { lens = button.dataset.intelLens; paint(); }
    else { load(true); paint(); }
  });
  return { html(dest) { queueMicrotask(() => load()); return `<div class="sail-map sail-intel">${body(dest)}</div>`; } };
})();
