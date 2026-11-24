"use strict";

const SailIntel = (() => {
  let key = "", rows = null, pending = "", error = false, zoom = .82;
  const clamp = n => Math.max(0, Math.min(1, n || 0));
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
    const records = historical ? Object.values(rows) : [];
    const maxVisits = Math.max(1, ...records.map(r => r.visits));
    const maxProfit = Math.max(1, ...records.map(r => Math.abs(r.profit)));
    const shareTotal = Math.max(1, (me.shares || {}).total || 1), result = {};
    for (const k of Object.keys(D.ports)) {
      const r = historical ? rows[k] || { visits: 0, profit: 0, sales: 0 } : null;
      const shareCount = me.shares ? me.shares.mine[k] || 0 : 0;
      const standing = me.rep[k] || 0;
      const risk = k === me.port ? null : pirateRisk(me.port, k);
      const riskTier = risk == null ? 0 : risk >= .32 ? 3 : risk >= .22 ? 2 : risk >= .12 ? 1 : 0;
      const hot = tips(k), run = k === me.port ? null : tradeRun(k);
      const visits = r ? r.visits : null, profit = r ? r.profit : null;
      const exactProfit = r ? signed(profit) : "—";
      result[k] = {
        value: `${visits == null ? "—" : visits} arrivals · ${r ? compact(profit) : "—"}`,
        title: `${D.ports[k].name}: ${visits == null ? "record loading" : visits + " arrivals"}; trading P/L ${exactProfit}; shares ${me.shares ? shareCount + " of " + me.shares.total : "disabled"}; standing ${standing}; route risk ${risk == null ? "already here" : Math.round(risk * 100) + "%"}${hot.length ? "; Hot tip: " + hot.map(tp => D.goods[tp.good].name).join(", ") : ""}`,
        rings: {
          visits: { fill: visits == null ? 0 : clamp(visits / maxVisits), negative: false },
          profit: { fill: profit == null ? 0 : clamp(Math.abs(profit) / maxProfit), negative: profit < 0 },
          shares: { fill: me.shares ? clamp(shareCount / shareTotal) : 0, negative: false },
          standing: { fill: clamp(Math.abs(standing) / 100), negative: standing < 0 }
        },
        visits, profit, shareCount, shareTotal: me.shares ? me.shares.total : null, standing, risk, riskTier,
        weather: Math.max(S.weather[D.ports[k].region] || 0, S.weather[D.ports[me.port].region] || 0),
        opportunity: run ? clamp(run.gain) : 0, run, hot: hot.length > 0
      };
    }
    return result;
  }
  function summary(k, intel) {
    const p = D.ports[k], m = intel[k], here = k === S.me.port;
    const fact = (name, value, cls = "") => `<div><dt>${esc(name)}</dt><dd class="${cls}">${esc(value)}</dd></div>`;
    const shares = m.shareTotal == null ? "Disabled" : `${m.shareCount} / ${m.shareTotal}`;
    const risk = here ? "Already here" : Math.round(m.risk * 100) + "%";
    const weather = D.weather[m.weather] + (S.crackdown.includes(k) ? " · Customs crackdown" : "");
    let opportunity = here ? "Select a destination to compare its route." : "No known buy-here / sell-there opportunity.";
    if (m.run) opportunity = `${D.goods[m.run.g].name}: ${money(m.run.buy)} → ≈${money(m.run.sell)} per unit · +${Math.round(m.run.gain * 100)}%`;
    return `<aside class="si-summary" aria-label="Selected port intelligence"><header><div><small>${here ? "CURRENT PORT" : "PLANNED DESTINATION"}</small><h3>${esc(p.name)}</h3></div><span>${esc(weather)}</span></header>
      <dl>${fact("Arrivals", m.visits == null ? "—" : m.visits)}${fact("Trading P/L", m.profit == null ? "—" : signed(m.profit), m.profit < 0 ? "si-loss" : "si-profit")}${fact("Your shares", shares)}${fact("Standing", m.standing)}${fact("Route risk", risk)}</dl>
      <p>${esc(opportunity)}</p></aside>`;
  }
  function legend() {
    return `<div class="si-legend" aria-label="Chart legend"><b>PORT RINGS</b><span><i class="visits"></i>Visits</span><span><i class="profit"></i>P/L</span><span><i class="shares"></i>Shares</span><span><i class="standing"></i>Standing</span><span><i class="route"></i>Route / risk</span></div>`;
  }
  function body(dest) {
    const intel = metrics(), focus = dest || S.me.port, waiting = !rows || key !== signature();
    const status = error ? "Port history unavailable · live shares, standing and route risk are still shown." : waiting ? "Loading this game’s port record…" : "All signals live · select any port to refocus";
    return `<div class="si-stage">
      ${Chart.svg({ data: D, players: S.players, weather: S.weather, crackdown: S.crackdown, here: S.me.port, dest, clickable: !S.me.ready, mine: S.me.id, intel, intelRoutes: true, focusPort: focus, focusScale: zoom, hideRose: true })}
      <div class="si-map-head"><small>THE CAPTAIN'S CHART</small><h3>${esc(D.ports[focus].name)} orbit</h3><p>${esc(status)}</p></div>
      <div class="si-controls" aria-label="Chart controls"><button type="button" data-intel-zoom="out" aria-label="Zoom out" ${zoom >= 1 ? "disabled" : ""}>−</button><button type="button" data-intel-zoom="focus">Focus port</button><button type="button" data-intel-zoom="in" aria-label="Zoom in" ${zoom <= .65 ? "disabled" : ""}>+</button><button type="button" data-intel-refresh ${pending ? "disabled" : ""}>↻ Refresh</button></div>
      ${summary(focus, intel)}${legend()}</div>`;
  }
  function paint() {
    const root = document.querySelector(".sail-intel");
    if (!root || !S || !S.me) return;
    const dest = S.me.ready ? S.me.dest : ui.dest;
    root.innerHTML = body(dest);
    Chart.fit(root);
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
      console.error("Captain's Chart history:", e);
      if (key === wanted) error = true;
    } finally {
      if (pending === wanted) pending = "";
      paint();
    }
  }
  document.addEventListener("click", e => {
    const destination = e.target.closest('[data-act="dest"]');
    if (destination) { zoom = .82; return; }
    const button = e.target.closest("[data-intel-zoom], [data-intel-refresh]");
    if (!button) return;
    if (button.dataset.intelZoom === "in") zoom = Math.max(.65, +(zoom - .12).toFixed(2));
    else if (button.dataset.intelZoom === "out") zoom = Math.min(1, +(zoom + .12).toFixed(2));
    else if (button.dataset.intelZoom === "focus") zoom = .82;
    else { load(true); paint(); return; }
    paint();
  });
  return { html(dest) { queueMicrotask(() => load()); return `<div class="sail-map sail-intel">${body(dest)}</div>`; } };
})();
