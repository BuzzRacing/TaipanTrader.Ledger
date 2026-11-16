/* SeaTrader harbor board: a read-only big-screen view of the shared world. */
"use strict";

let D = null, S = null, online = true;
const app = document.getElementById("app");

function render() {
  if (!D || !S) return;
  const ranked = S.players.slice().sort((a, b) => b.worth - a.worth);
  const lobby = S.phase === "lobby", ended = S.phase === "ended";

  const rows = ranked.map((p, i) => {
    const status = lobby ? (p.host ? "host" : "joined")
      : ended ? "" : !p.present ? "away" : p.ready ? "orders given" : "in port";
    return `<tr><td class="rank">${lobby ? "" : i + 1}</td>
      <td><i class="chip" style="background:${COLORS[p.color % 8]}"></i><b>${esc(p.firm)}</b><span>${esc(p.name)}</span></td>
      <td>${esc(D.ports[p.port].name)}<span class="st ${p.ready ? "ok" : ""}">${status}</span></td>
      <td class="n">${lobby ? "" : money(p.worth)}</td></tr>`;
  }).join("") || '<tr><td colspan="4" class="muted">No trading houses have joined yet.</td></tr>';

  const weather = Object.keys(D.regions).map(r =>
    `<li><span>${esc(D.regions[r])}</span>${weatherBadge(S.weather[r], D.weather)}</li>`).join("");
  const bans = S.crackdown.length
    ? `<p class="bans">Opium banned in ${S.crackdown.map(k => esc(D.ports[k].name)).join(", ")}</p>` : "";

  let headline;
  if (lobby) headline = "Join the game";
  else if (ended) headline = ranked.length ? esc(ranked[0].name) + " is Taipan" : "The game is over";
  else headline = S.waiting.length ? "Waiting for " + S.waiting.map(esc).join(", ") : "The fleets are at sea…";

  app.innerHTML = `
    <header class="bhead">
      <h1>Sea<span>Trader</span></h1>
      <div class="bdate"><b>${esc(S.date)}</b><span>${lobby ? "Game length " + S.years + " years" : ended ? "Final standings" : S.turns_left + " months left"}</span></div>
      <div class="bjoin"><span>Join on your phone</span><b>${esc(S.join_url)}</b></div>
    </header>
    <div class="bgrid">
      <section class="bmap">
        ${Chart.svg({ data: D, players: S.players, weather: S.weather, crackdown: S.crackdown })}
        <p class="bstatus">${headline}${online ? "" : " · reconnecting…"}</p>
      </section>
      <aside>
        <section class="panel"><h2>${lobby ? "Trading houses" : "Standings"}</h2>
          <table class="btable"><tbody>${rows}</tbody></table></section>
        <section class="panel"><h2>Forecast for this month</h2><ul class="bwx">${weather}</ul>${bans}</section>
        <section class="panel news"><h2>News from the ports</h2>
          <ul>${S.news.slice(0, 8).map(n => "<li>" + esc(n) + "</li>").join("")}</ul></section>
      </aside>
    </div>`;
}

loadInfo().then(info => {
  D = info.data;
  listen(null, state => { S = state; render(); }, ok => { if (ok !== online) { online = ok; render(); } });
});
