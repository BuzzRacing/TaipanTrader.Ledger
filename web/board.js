/* SeaTrader harbor board: a read-only big-screen view of the shared world. */
"use strict";

let D = null, S = null, reloading = false, retryInfo, VS = {}, newsSeen = null;
const app = document.getElementById("app");
const loading = document.getElementById("board-loading");
const connection = document.getElementById("board-connection");
const quitBtn = document.getElementById("bquit");
const previous = new Map();

function update(id, html) {
  if (previous.get(id) === html) return;
  const el = document.getElementById(id);
  el.innerHTML = html;
  previous.set(id, html);
  return el;
}

function portName(key) {
  return D.ports[key]?.name || key;
}

function render() {
  if (!D || !S) return;
  const lobby = S.phase === "lobby", ended = S.phase === "ended", sea = S.phase === "sea";
  const ranked = lobby ? S.players : S.players.slice().sort((a, b) => b.worth - a.worth);
  const encounters = sea ? S.sea || [] : [];
  const fighting = new Set(encounters.map(fight => fight.id));
  const active = S.players.filter(p => p.present);
  const label = lobby ? "board.before_departure" : ended ? "board.voyage_complete"
    : encounters.length ? "board.battle" : sea ? "battle.title" : "board.orders";
  let headline, detail = "";
  if (lobby) headline = te("board.join");
  else if (ended) headline = ranked.length ? te("board.winner", { name: ranked[0].firm }) : te("board.over");
  else if (sea) headline = te("board.at_sea");
  else {
    headline = active.length ? te("board.readiness", { n: active.filter(p => p.ready).length, total: active.length })
      : te("board.no_active");
    if (S.waiting.length) detail = te("sail.waiting", { names: S.waiting.join(", ") });
  }

  const sub = lobby ? te("board.length", { years: S.years })
    : ended ? te("board.final") : te("board.months_left", { months: S.turns_left });
  update("board-head", `
    <div class="br-brand"><h1>${brandHtml(D)}</h1><span>${te("board.title")}</span></div>
    <div class="br-date"><b>${esc(S.date)}</b><span>${sub}</span></div>
    <div class="br-join"><span>${te("board.join_phone")}</span><b>${esc(S.join_url)}</b></div>`);

  document.getElementById("board-turn").classList.toggle("br-battle", encounters.length > 0);
  update("board-turn", `
    <div><span class="br-label">${te(label)}</span><h2>${headline}</h2>${detail ? `<p>${detail}</p>` : ""}</div>
    ${encounters.length ? `<ul class="br-encounters" tabindex="0">${encounters.map(fight => `
      <li><b>${esc(fight.firm)}</b><span>${te(fight.where ? "board.encounter" : "board.encounter_unknown",
        { port: fight.where, left: fight.left, n: fight.n, enemy: fight.enemy })}</span></li>`).join("")}</ul>` : ""}`);

  update("board-ledger-head", `<h2>${te(lobby ? "board.houses" : ended ? "board.final" : "ledger.standings")}</h2>
    ${lobby ? "" : `<span>${te("stat.worth")}</span>`}`);
  update("board-houses", ranked.length ? `<ol>${ranked.map((p, index) => {
    const battle = fighting.has(p.id);
    const status = lobby ? te(p.host ? "w.host" : "board.joined")
      : ended ? esc(p.rank) : te(battle ? "board.in_battle" : !p.present ? "w.away" : p.ready ? "board.ready" : "board.in_port");
    const tone = battle ? "br-danger" : !lobby && !ended && p.present && p.ready ? "br-ready" : "";
    return `<li>
      <span class="br-place" aria-hidden="true">${lobby ? "" : index + 1}</span>
      <div class="br-house" style="--house:${COLORS[p.color % COLORS.length]}">
        <b>${esc(p.firm)}</b><span>${esc(p.name)} · ${esc(portName(p.port))}</span></div>
      <div class="br-result">${lobby ? "" : `<b>${esc(money(p.worth))}</b>`}<span class="${tone}">${status}</span></div>
    </li>`;
  }).join("")}</ol>` : `<p class="br-empty">${te("board.none")}</p>`);

  update("board-chart-head", `<h2>${te("board.chart")}</h2><span>${te("board.flags")}</span>`);
  const chart = update("board-chart", Chart.svg({ data: D, players: S.players, crackdown: S.crackdown,
    hideWeather: true, hideRose: Boolean(D.graphics.chart_bg) }));

  const bans = S.crackdown.map(key => {
    const cargo = (S.bans?.[key] || []).map(g => D.goods[g]?.name || g);
    return `<li><b>${esc(portName(key))}</b>${cargo.length ? `<span>${te("board.restricted_cargo", { cargo: cargo.join(", ") })}</span>` : ""}</li>`;
  }).join("");
  update("board-advisories", lobby ? "" : `
    <section class="br-panel br-forecast">
      <header class="br-section-head"><h2>${te("board.forecast")}</h2></header>
      <ul class="br-scroll">${Object.keys(D.regions).map(key =>
        `<li><span>${esc(D.regions[key].name)}</span>${weatherBadge(S.weather[key] ?? 0, D.weather)}</li>`).join("")}</ul>
    </section>
    ${bans ? `<section class="br-panel br-bans"><header class="br-section-head"><h2>${te("board.customs")}</h2></header>
      <ul class="br-scroll">${bans}</ul></section>` : ""}`);

  update("board-news-head", `<h2>${te("ledger.news")}</h2>`);
  const news = update("board-news", S.news.length ? `<ul>${S.news.map(line => `<li>${esc(line)}</li>`).join("")}</ul>`
    : `<p class="br-empty">${te("ledger.no_news")}</p>`);
  if (news) document.getElementById("board-bulletins").scrollTop = 0;

  const ports = [...new Set(S.players.map(p => p.port).filter(key => D.ports[key]))];
  const galleryPorts = ports.length ? ports : [D.home];
  update("board-gallery", Media.options().board_gallery
    ? Media.html("port", galleryPorts, "board", "br-gallery", "", { video: true, mode: "shuffle", slot: "board" }) : "");

  app.hidden = false;
  loading.hidden = true;
  if (chart) Chart.fit(chart);
}

function showConnection(online) {
  connection.textContent = online ? "" : t("board.stale");
}

async function refreshInfo() {
  if (reloading) return;
  clearTimeout(retryInfo);
  reloading = true;
  try {
    const info = await loadInfo();
    D = info.data;
    VS = Voice.setup(info.voice);
    document.title = brandName(D.brand) + " · " + t("board.title");
    quitBtn.textContent = t("board.quit");
    quitBtn.title = t("board.quit");
  } catch (error) {
    console.warn("Harbor Board could not load settings", error);
    retryInfo = setTimeout(refreshInfo, 3000);
  } finally {
    reloading = false;
  }
  if (D && S.cfg === cfgSeen) { render(); speakNews(); }
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
function quitBoard() {
  window.close();
  setTimeout(() => {
    if (!window.closed) { quitBtn.textContent = t("board.quit_hint"); }
  }, 300);
}
quitBtn.addEventListener("click", quitBoard);
document.addEventListener("keydown", e => { if (e.key === "Escape") { e.preventDefault(); quitBoard(); } });

document.getElementById("board-controls").prepend(document.getElementById("voicebox"));
listen(null, state => {
  S = state;
  if (!D || state.cfg !== cfgSeen) return refreshInfo();
  render();
  speakNews();
}, showConnection);
