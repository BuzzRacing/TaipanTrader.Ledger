/* SeaTrader harbor board: a read-only big-screen view of the shared world. */
"use strict";

let D = null, S = null, online = true, reloading = false, VS = {}, newsSeen = null;
const app = document.getElementById("app");

function render() {
  if (!D || !S) return;
  const ranked = S.players.slice().sort((a, b) => b.worth - a.worth);
  const lobby = S.phase === "lobby", ended = S.phase === "ended";

  const rows = ranked.map((p, i) => {
    const status = lobby ? (p.host ? t("w.host") : t("board.joined"))
      : ended ? "" : !p.present ? t("w.away") : p.ready ? t("board.ready") : t("board.in_port");
    return `<tr><td class="rank">${lobby ? "" : i + 1}</td>
      <td><i class="chip" style="background:${COLORS[p.color % 8]}"></i><b>${esc(p.firm)}</b><span>${esc(p.name)}${lobby ? "" : ` · <span class="rankname">${esc(p.rank)}</span>`}</span></td>
      <td>${esc(D.ports[p.port] ? D.ports[p.port].name : p.port)}<span class="st ${p.ready ? "ok" : ""}">${esc(status)}</span></td>
      <td class="n">${lobby ? "" : money(p.worth)}</td></tr>`;
  }).join("") || `<tr><td colspan="4" class="muted">${te("board.none")}</td></tr>`;

  const weather = Object.keys(D.regions).map(r =>
    `<li><span>${esc(D.regions[r].name)}</span>${weatherBadge(S.weather[r] || 0, D.weather)}</li>`).join("");
  const bans = S.crackdown.length
    ? `<p class="bans">${te("board.bans", { ports: S.crackdown.map(k => D.ports[k] ? D.ports[k].name : k).join(", ") })}</p>` : "";

  let headline;
  if (lobby) headline = te("board.join");
  else if (ended) headline = ranked.length ? te("board.winner", { name: ranked[0].name }) : te("board.over");
  else if (S.phase === "sea" && (S.sea || []).length) {
    // Houses fighting at sea: nobody lands until every fight is over.
    headline = S.sea.map(x => `<span style="display:block">${te("battle.board", { name: x.name, port: x.where, left: x.left, n: x.n, enemy: x.enemy })}</span>`).join("");
  }
  else headline = S.waiting.length ? te("sail.waiting", { names: S.waiting.join(", ") }) : te("board.at_sea");
  const sub = lobby ? te("board.length", { years: S.years }) : ended ? te("board.final") : te("board.months_left", { months: S.turns_left });

  // A rotating view of the ports the houses are in (Admin > Media Library > port pictures, "Harbor board" role).
  const here = [...new Set(S.players.map(p => p.port).filter(k => D.ports[k]))];
  const galleryPorts = here.length ? here : [D.home];
  const gallery = Media.options().board_gallery && galleryPorts.some(k => Media.has("port", k, "board", { video: true }))
    ? `<section class="panel bgallery">${Media.html("port", galleryPorts, "board", "bgart", "", { video: true, mode: "shuffle", slot: "board" })}</section>` : "";

  app.innerHTML = `
    <header class="bhead">
      <h1>${brandHtml(D)}</h1>
      <div class="bdate"><b>${esc(S.date)}</b><span>${sub}</span></div>
      <div class="bjoin"><span>${te("board.join_phone")}</span><b>${esc(S.join_url)}</b></div>
    </header>
    <div class="bgrid">
      <section class="bmap">
        ${Chart.svg({ data: D, players: S.players, weather: S.weather, crackdown: S.crackdown })}
        <p class="bstatus">${headline}${online ? "" : " · " + te("board.reconnecting")}</p>
      </section>
      <aside>${gallery}
        <section class="panel"><h2>${lobby ? te("board.houses") : te("ledger.standings")}</h2>
          <table class="btable"><tbody>${rows}</tbody></table></section>
        <section class="panel"><h2>${te("board.forecast")}</h2><ul class="bwx">${weather}</ul>${bans}</section>
        <section class="panel news"><h2>${te("ledger.news")}</h2>
          <ul>${S.news.slice(0, 8).map(n => "<li>" + esc(n) + "</li>").join("")}</ul></section>
      </aside>
    </div>`;
}

async function refreshInfo() {
  if (reloading) return;
  reloading = true;
  try { const info = await loadInfo(); D = info.data; VS = Voice.setup(info.voice); } catch (e) { /* try again on the next state */ }
  reloading = false;
  render();
}

/* The news crier (and whoever else the Admin page chose) reads fresh headlines aloud.
   Headlines already up when the board opens are not read. */
function speakNews() {
  const news = S.news || [], plans = (S.voice && S.voice.news) || [];
  if (newsSeen === null) { newsSeen = new Set(news); return; }
  const fresh = [];
  news.forEach((n, i) => { if (!newsSeen.has(n)) { newsSeen.add(n); if (plans[i]) fresh.unshift(plans[i]); } });
  if (fresh.length && VS.news_board) Voice.say(fresh, { group: "news" });
}

/* Esc or the small Quit button closes the board window (the game keeps running).
   If the browser refuses to close it, the button says how to close it instead. */
const quitBtn = document.getElementById("bquit");
function quitBoard() {
  window.close();
  setTimeout(() => {
    if (!window.closed) { quitBtn.textContent = t("board.quit_hint"); quitBtn.classList.add("hint"); }
  }, 300);
}
quitBtn.addEventListener("click", quitBoard);
document.addEventListener("keydown", e => { if (e.key === "Escape") { e.preventDefault(); quitBoard(); } });

loadInfo().then(info => {
  D = info.data;
  VS = Voice.setup(info.voice);
  quitBtn.textContent = t("board.quit");
  listen(null, state => { S = state; if (state.cfg !== cfgSeen) return refreshInfo(); render(); speakNews(); },
         ok => { if (ok !== online) { online = ok; render(); } });
});
