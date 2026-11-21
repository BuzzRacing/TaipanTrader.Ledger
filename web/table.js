/* Harbor View: the game seen from straight above, laid out on a captain's table.
   Read-only, like the harbor board, and fed by the same public stream (so nothing private is shown).
   Phase 1 (21 Nov 2026): the table, the board with the title at its centre, the month track round the
   rim, a mat for every seat in play (and none for empty seats), ship pieces at their ports, sealed
   orders, weather and bans. Plan and later phases: project doc "SeaTrader Harbor View". */
"use strict";

// Wording this screen needs that an older server may not have yet (Admin > Language & Text wins).
const T_FALLBACK = {
  "table.title": "Harbor View",
  "table.gazette": "The Gazette",
  "table.fleet": "Fleet · {n}",
  "table.writing": "Writing orders…",
  "table.at": "At {port}",
  "table.jailed": "In jail at {port}",
};

let D = null, S = null, reloading = false, retryInfo, VS = {}, newsSeen = null, newsShown = new Set();
const app = document.getElementById("app");
const loading = document.getElementById("hv-loading");
const connection = document.getElementById("hv-connection");
const quitBtn = document.getElementById("hv-quit");
const previous = new Map();
const SVGNS = "http://www.w3.org/2000/svg";
const TITLE_AT = { x: 610, y: 262 };          // where the title sits on the 1000 x 600 chart

function update(id, html) {
  if (previous.get(id) === html) return null;
  const el = document.getElementById(id);
  el.innerHTML = html;
  previous.set(id, html);
  return el;
}
const portName = key => (D.ports[key] && D.ports[key].name) || key;
const colorOf = p => COLORS[(p.color || 0) % COLORS.length];

/* The table is a fixed 1920 x 1080 stage, scaled to whatever screen it is on. It never scrolls. */
function fitStage() {
  const s = Math.min(window.innerWidth / 1920, window.innerHeight / 1080);
  const x = (window.innerWidth - 1920 * s) / 2, y = (window.innerHeight - 1080 * s) / 2;
  app.style.transform = `translate(${x.toFixed(1)}px, ${y.toFixed(1)}px) scale(${s.toFixed(4)})`;
}
window.addEventListener("resize", fitStage);
fitStage();

/* ---------------------------------------------------------- month track -- */
/* A point f (0..1) of the way round the rim, clockwise from the top-left corner. */
function rimPoint(f) {
  const x0 = 15, y0 = 15, w = 1370, h = 834, P = 2 * (w + h);
  let d = ((f % 1) + 1) % 1 * P;
  if (d <= w) return { x: x0 + d, y: y0, nx: 0, ny: 1, side: 0 };
  d -= w;
  if (d <= h) return { x: x0 + w, y: y0 + d, nx: -1, ny: 0, side: 1 };
  d -= h;
  if (d <= w) return { x: x0 + w - d, y: y0 + h, nx: 0, ny: -1, side: 2 };
  d -= w;
  return { x: x0, y: y0 + h - d, nx: 1, ny: 0, side: 3 };
}

function drawTrack() {
  const years = Math.max(1, S.years || 1), total = years * 12;
  const turn = Math.max(0, S.turn || 0);
  const m = /(\d{4})/.exec(S.date || "");
  const firstYear = m ? Number(m[1]) - Math.floor(turn / 12) : 0;
  const every = Math.ceil(years / 12);
  const key = [years, firstYear, Math.min(turn, total)].join(":");
  const out = [];
  const months = total <= 240;
  for (let i = 0; i < total; i++) {
    const isYear = i % 12 === 0;
    if (!isYear && !months) continue;
    const p = rimPoint(i / total), len = isYear ? 13 : 6;
    const ax = p.x - p.nx * 13, ay = p.y - p.ny * 13;
    out.push(`<line class="tick${isYear ? " year" : ""}${i < turn ? " done" : ""}" x1="${ax}" y1="${ay}" x2="${ax + p.nx * len}" y2="${ay + p.ny * len}"/>`);
    if (isYear && (i / 12) % every === 0) {
      const label = firstYear ? firstYear + i / 12 : i / 12 + 1;
      const rot = p.side === 1 ? 90 : p.side === 3 ? -90 : 0;
      const tx = p.x + (p.side === 0 ? 5 : p.side === 2 ? -5 : p.nx * 5), ty = p.y + (p.side === 1 ? 5 : p.side === 3 ? -5 : p.ny * 5);
      out.push(`<text transform="translate(${tx.toFixed(1)} ${ty.toFixed(1)}) rotate(${rot})" text-anchor="${p.side === 2 ? "end" : "start"}" dy="${p.side === 0 ? 9 : p.side === 2 ? 0 : 4}">${label}</text>`);
    }
  }
  const at = rimPoint(Math.min(turn, total - .001) / total);
  const track = document.getElementById("hv-track");
  if (previous.get("hv-track-ticks") !== key) {
    previous.set("hv-track-ticks", key);
    const marker = track.querySelector(".marker");
    track.innerHTML = out.join("") + `<g class="marker"><circle r="12"/><path d="M0 -6 L5 0 L0 6 L-5 0Z"/></g>`;
    if (marker) track.querySelector(".marker").style.transform = marker.style.transform;   // step from where it was
  }
  requestAnimationFrame(() => {
    track.querySelector(".marker").style.transform = `translate(${at.x.toFixed(1)}px, ${at.y.toFixed(1)}px)`;
  });
}

/* --------------------------------------------------------------- the sky -- */
function drawSky() {
  const out = [];
  for (const key of Object.keys(D.regions)) {
    const reg = D.regions[key];
    let x = (reg.label_lon - 85) / 50 * 1000, y = (35 - reg.label_lat) / 45 * 600;
    if (Math.abs(x - TITLE_AT.x) < 190 && Math.abs(y - TITLE_AT.y) < 95) y = TITLE_AT.y + 118;   // keep clear of the title
    const lvl = S.weather[key] == null ? 0 : S.weather[key];
    let art = "";
    if (lvl >= 3) {
      art = `<ellipse class="cloud" cx="-30" cy="-34" rx="54" ry="26"/><ellipse class="cloud" cx="34" cy="-22" rx="48" ry="24"/>` +
        `<g transform="translate(0 -30)"><path class="spiral" d="M0 -30 A30 30 0 1 1 -30 0 M0 -18 A18 18 0 1 0 18 0 M0 -7 A7 7 0 1 1 -7 0"/>` +
        `<path class="spiral b" d="M0 -30 A30 30 0 1 1 -30 0 M0 -18 A18 18 0 1 0 18 0"/></g>`;
    } else if (lvl === 2) {
      art = `<ellipse class="cloud" cx="-24" cy="-40" rx="46" ry="20"/><ellipse class="cloud" cx="26" cy="-30" rx="42" ry="19"/>` +
        [-38, -22, -6, 10, 26, 42].map((dx, i) => `<line class="rain" style="animation-delay:${(i * .13).toFixed(2)}s" x1="${dx}" y1="-22" x2="${dx - 4}" y2="-10"/>`).join("");
    } else {
      art = [[-34, -30], [8, -42], [36, -24], [-8, -18]].map(([dx, dy], i) =>
        `<path class="glint" style="animation-delay:${(i * 1.2).toFixed(1)}s" transform="translate(${dx} ${dy})" d="M0 -5 L1.3 -1.3 L5 0 L1.3 1.3 L0 5 L-1.3 1.3 L-5 0 L-1.3 -1.3Z"/>`).join("");
    }
    out.push(`<g class="wx${lvl}" transform="translate(${x.toFixed(1)} ${y.toFixed(1)})">${art}` +
      `<text class="sea-wx" y="4">${esc(D.weather[lvl])}</text><text class="sea-name" y="21">${esc(reg.name)}</text></g>`);
  }
  update("hv-sky", out.join(""));
}

/* ------------------------------------------------------------ the pieces -- */
const HULL = "M0 -16 C7 -9 8 6 5 15 L-5 15 C-8 6 -7 -9 0 -16Z";
const SAILS = '<path class="deck" d="M0 -11 C4 -6 4.5 5 3 11 L-3 11 C-4.5 5 -4 -6 0 -11Z"/>' +
  '<rect class="sail" x="-10" y="-7" width="20" height="5.5" rx="1.5"/><rect class="sail" x="-9" y="3" width="18" height="5" rx="1.5"/>';
const pieces = new Map();      // player id -> { g, x, y, port, heading }

function seatAt(port, index, count) {
  const p = D.ports[port];
  if (!p) return { x: TITLE_AT.x, y: 560 };
  const side = p.label_left ? 1 : -1;
  return { x: p.x + side * 40, y: p.y + (index - (count - 1) / 2) * 34 };
}

function pieceMarkup(p) {
  const n = Math.max(1, Math.min(5, p.ships || 1)), col = colorOf(p);
  let behind = "";
  for (let i = n - 1; i >= 1; i--) behind += `<path class="hull behind" fill="${col}" transform="translate(${i * 5} ${i * 3.5})" d="${HULL}"/>`;
  return `<g class="turn"><g class="bob">${behind}<path class="hull" fill="${col}" d="${HULL}"/>${SAILS}</g></g>` +
    `<circle class="ready-ring" r="25"/>` +
    `<g class="bars"><rect x="-17" y="-19" width="34" height="38" rx="3"/><path d="M-9 -19 V19 M0 -19 V19 M9 -19 V19"/></g>` +
    ((p.ships || 0) > 1 ? `<text class="count" x="19" y="-13">×${p.ships}</text>` : "") +
    `<text class="tag" y="37">${esc(p.firm)}</text>`;
}

function drawPieces(fighting) {
  const layer = document.getElementById("hv-pieces");
  let fleet = layer.querySelector("#hv-fleet");
  if (!fleet) {
    layer.innerHTML = '<g id="hv-marks"></g><g id="hv-fleet"></g>';
    previous.delete("hv-marks");
    fleet = layer.querySelector("#hv-fleet");
  }
  const byPort = {};
  for (const p of S.players) (byPort[p.port] = byPort[p.port] || []).push(p);
  const seen = new Set();
  let overTitle = false;
  for (const port of Object.keys(byPort)) {
    byPort[port].forEach((p, i) => {
      seen.add(p.id);
      const at = seatAt(port, i, byPort[port].length);
      let rec = pieces.get(p.id);
      if (!rec) {
        const g = document.createElementNS(SVGNS, "g");
        g.setAttribute("class", "piece new");
        fleet.appendChild(g);
        rec = { g, x: at.x, y: at.y, port, heading: D.ports[port] && D.ports[port].label_left ? 90 : -90, mark: "" };
        pieces.set(p.id, rec);
      }
      const mark = pieceMarkup(p);
      if (rec.mark !== mark) { rec.g.innerHTML = mark; rec.mark = mark; }
      if (rec.port !== port && (Math.abs(at.x - rec.x) > 1 || Math.abs(at.y - rec.y) > 1)) {
        rec.heading = Math.atan2(at.x - rec.x, -(at.y - rec.y)) * 180 / Math.PI;       // bow toward the new port
      }
      rec.x = at.x; rec.y = at.y; rec.port = port;
      rec.g.style.transform = `translate(${at.x.toFixed(1)}px, ${at.y.toFixed(1)}px)`;
      rec.g.querySelector(".turn").style.transform = `rotate(${rec.heading.toFixed(1)}deg)`;
      rec.g.classList.toggle("ready", Boolean(p.ready && p.present && S.phase === "port"));
      rec.g.classList.toggle("away", !p.present && S.phase !== "lobby" && S.phase !== "ended");
      rec.g.classList.toggle("jailed", Boolean(p.jailed));
      if (rec.g.classList.contains("new")) requestAnimationFrame(() => rec.g.classList.remove("new"));
      if (Math.abs(at.x - TITLE_AT.x) < 150 && Math.abs(at.y - TITLE_AT.y) < 80) overTitle = true;
    });
  }
  for (const [id, rec] of pieces) if (!seen.has(id)) { rec.g.remove(); pieces.delete(id); }
  document.getElementById("hv-title").classList.toggle("dim", overTitle);

  // Ban seals, and the enemy closing in while a fight is on.
  const marks = [];
  for (const key of S.crackdown || []) {
    const p = D.ports[key];
    if (!p) continue;
    const cargo = ((S.bans && S.bans[key]) || []).map(g => (D.goods[g] && D.goods[g].name) || g).join(", ");
    marks.push(`<g class="ban" transform="translate(${p.x} ${p.y})"><circle r="13"/>` +
      `<path d="M-5 1 v-3 a5 5 0 0 1 10 0 v3 M-7 1 h14 v8 h-14z"/>` +
      (cargo ? `<text y="33">${esc(cargo)}</text>` : "") + `</g>`);
  }
  const byName = {};
  for (const k of Object.keys(D.ports)) byName[D.ports[k].name] = k;
  (fighting || []).forEach((fight, f) => {
    const rec = pieces.get(fight.id), port = D.ports[byName[fight.where]];
    const cx = port ? port.x + (port.label_left ? 86 : -86) : rec ? rec.x + 60 : 500, cy = port ? port.y + 6 + f * 20 : rec ? rec.y : 300;
    const total = Math.min(14, fight.n || 0), afloat = Math.min(total, Math.round(total * (fight.left || 0) / Math.max(1, fight.n || 1)));
    let foes = "";
    for (let i = 0; i < total; i++) {
      const fx = (i % 5) * 15 - 30, fy = Math.floor(i / 5) * 17 - 12;
      foes += `<g transform="translate(${fx} ${fy}) scale(.62)"><g class="foe${/lord|war|li/i.test(fight.kind || "") ? " lord" : ""}${i >= afloat ? " sunk" : ""}">` +
        `<path class="hull" d="${HULL}"/><rect class="sail" x="-9" y="-6" width="18" height="5" rx="1.5"/><rect class="sail" x="-8" y="3" width="16" height="4.5" rx="1.5"/></g></g>`;
    }
    marks.push(`<g transform="translate(${cx.toFixed(1)} ${cy.toFixed(1)})">` +
      `<circle class="flash" cx="-44" cy="-4" r="2"/><circle class="flash" style="animation-delay:.6s" cx="-36" cy="12" r="2"/>${foes}` +
      `<text class="fight-tag" y="${Math.floor((total - 1) / 5) * 17 + 20}">${esc(t("board.encounter_unknown", { left: fight.left, n: fight.n, enemy: fight.enemy }))}</text></g>`);
  });
  const html = marks.join("");
  if (previous.get("hv-marks") !== html) { previous.set("hv-marks", html); layer.querySelector("#hv-marks").innerHTML = html; }
}

/* -------------------------------------------------------------- the mats -- */
function coins(worth) {
  const n = worth > 0 ? Math.max(1, Math.min(45, Math.round((Math.log10(worth) - 2) * 7))) : 0;
  let html = "";
  for (let s = 0; s * 9 < n; s++) {
    let stack = "";
    for (let k = 0; k < Math.min(9, n - s * 9); k++) {
      const gold = s * 9 + k >= 28;
      stack += `<i class="coin${gold ? " gold" : ""}" style="top:${-k * 3}px;left:${-k}px;animation-delay:${((s * 9 + k) * .025).toFixed(2)}s"></i>`;
    }
    html += `<div class="stack">${stack}</div>`;
  }
  return html;
}

function hullIcons(n) {
  const one = '<svg viewBox="-23 -11 46 22"><g transform="rotate(90)"><path class="hull" d="' + HULL + '"/>' +
    '<rect class="sail" x="-9" y="-6" width="18" height="5" rx="1.5"/><rect class="sail" x="-8" y="3" width="16" height="4.5" rx="1.5"/></g></svg>';
  return one.repeat(Math.max(0, Math.min(14, n)));
}

function drawMats(ranked, fighting) {
  const lobby = S.phase === "lobby", ended = S.phase === "ended";
  const players = S.players, n = players.length;
  const mats = document.getElementById("hv-mats");
  mats.className = "hv-mats n" + n + (n >= 5 ? " many" : "");
  const place = new Map(ranked.map((p, i) => [p.id, i + 1]));
  update("hv-mats", players.map(p => {
    const faces = Faces.of(p), battle = fighting.has(p.id);
    const status = lobby ? t(p.host ? "w.host" : "board.joined")
      : ended ? "" : t(battle ? "board.in_battle" : !p.present ? "w.away" : p.ready ? "board.ready" : "board.in_port");
    const cls = ["hv-mat"];
    if (!lobby && !ended && !p.present) cls.push("away");
    if (!lobby && !ended && p.ready && p.present && !battle) cls.push("ready");
    if (battle) cls.push("fighting");
    const initial = esc(String(p.firm || p.name || "?").trim().charAt(0).toUpperCase());
    return `<article class="${cls.join(" ")}" style="--house:${colorOf(p)}">
      ${!lobby && n > 1 ? `<span class="place">${place.get(p.id) || ""}</span>` : ""}
      <div class="face">${faces.portrait ? `<img src="${esc(faces.portrait)}" alt="">` : `<b>${initial}</b>`}</div>
      ${faces.crest ? `<div class="crestbox"><img src="${esc(faces.crest)}" alt=""></div>` : ""}
      <div class="who"><h3>${esc(p.firm)}</h3><span class="cap">${esc(p.name)}${lobby && status ? " · " + esc(status) : ""}</span>${lobby ? "" : Ranks.label(p)}</div>
      ${lobby || ended ? "" : `<div class="orders"><div class="letter">${te("table.writing")}</div><span class="seal">${initial}</span>
        <small class="${battle ? "bad" : p.ready && p.present ? "ok" : ""}">${esc(status)}</small></div>`}
      <div class="fleet"><span class="label">${te("table.fleet", { n: p.ships || 0 })}</span><div class="hulls">${hullIcons(p.ships || 0)}</div>
        <span class="where">${te(p.jailed ? "table.jailed" : "table.at", { port: portName(p.port) })}</span></div>
      ${lobby ? "" : `<div class="silver"><span class="worth">${esc(money(p.worth))}</span><div class="stacks">${coins(p.worth)}</div></div>`}
    </article>`;
  }).join(""));
}

/* ------------------------------------------------- the cards beside the board -- */
function drawDate(ranked, encounters) {
  const lobby = S.phase === "lobby", ended = S.phase === "ended", sea = S.phase === "sea";
  const active = S.players.filter(p => p.present);
  const label = lobby ? "board.before_departure" : ended ? "board.voyage_complete"
    : encounters.length ? "board.battle" : sea ? "battle.title" : "board.orders";
  let headline, detail = "";
  if (lobby) headline = t("board.join");
  else if (ended) headline = ranked.length ? t("board.winner", { name: ranked[0].firm }) : t("board.over");
  else if (sea) headline = t("board.at_sea");
  else {
    headline = active.length ? t("board.readiness", { n: active.filter(p => p.ready).length, total: active.length }) : t("board.no_active");
    if (S.waiting.length) detail = t("sail.waiting", { names: S.waiting.join(", ") });
  }
  const sub = lobby ? t("board.length", { years: S.years }) : ended ? t("board.final") : t("board.months_left", { months: S.turns_left });
  document.getElementById("hv-date").classList.toggle("battle", encounters.length > 0);
  update("hv-date", `<span class="kicker">${te(label)}</span><h2>${esc(S.date)}</h2><span class="sub">${esc(sub)}</span>
    <div class="state">${esc(headline)}${detail ? `<small>${esc(detail)}</small>` : ""}</div>
    ${encounters.length ? `<ul>${encounters.map(f => `<li><b>${esc(f.firm)}</b> · ${te(f.where ? "board.encounter" : "board.encounter_unknown",
      { port: f.where, left: f.left, n: f.n, enemy: f.enemy })}</li>`).join("")}</ul>` : ""}
    ${lobby ? `<div class="join">${te("board.join_phone")}<b>${esc(S.join_url)}</b></div>` : ""}`);
}

function drawNews() {
  update("hv-gazette-head", te("table.gazette"));
  const news = S.news || [], heat = S.news_heat || [];
  const first = newsShown.size === 0;
  const html = news.length ? news.map((line, i) => {
    const h = heat[i] || 0, fresh = !first && !newsShown.has(line);
    return `<article class="${h >= .66 ? "hot" : h >= .33 ? "warm" : ""}${fresh ? " fresh" : ""}" style="animation-delay:${(i * .12).toFixed(2)}s">${esc(line)}</article>`;
  }).join("") : `<p class="empty">${te("ledger.no_news")}</p>`;
  if (update("hv-news", html)) news.forEach(line => newsShown.add(line));
}

function drawPostcard(ranked) {
  const lead = ranked[0] || S.players[0];
  const port = lead && D.ports[lead.port] ? lead.port : D.home;
  const art = Media.html("port", [port], "board", "hv-postcard-img", "", { video: true, mode: "shuffle", slot: "table" });
  update("hv-postcard", art ? `${art}<span class="cap">${esc(portName(port))}</span>` : "");
}

/* ------------------------------------------------------------------ draw -- */
function render() {
  if (!D || !S) return;
  Ceremony.sync(S, D, app);
  const lobby = S.phase === "lobby", sea = S.phase === "sea";
  const ranked = lobby ? S.players : Ceremony.ranked(S);
  const encounters = sea ? S.sea || [] : [];
  const fighting = new Set(encounters.map(f => f.id));

  const chart = update("hv-chart-base", Chart.svg({ data: D, players: [], crackdown: S.crackdown, hideWeather: true, hideRose: true }));
  update("hv-title", `<svg class="rose" viewBox="-170 -170 340 340"><circle r="160"/><circle r="120"/>` +
    `<path class="pt" d="M0 -160 L10 0 L0 160 L-10 0Z M-160 0 L0 -10 L160 0 L0 10Z"/>` +
    `<path class="needle" d="M0 -150 L6 0 L-6 0Z"/></svg><h1>${brandHtml(D)}</h1>` +
    (D.brand.tagline ? `<p>${esc(D.brand.tagline)}</p>` : ""));
  drawTrack();
  drawSky();
  drawPieces(encounters);
  drawMats(ranked, fighting);
  drawDate(ranked, encounters);
  drawNews();
  drawPostcard(ranked);

  app.hidden = false;
  loading.hidden = true;
  if (chart) Chart.fit(chart);
  if (typeof Soundscape !== "undefined") Soundscape.sync(S, { battle: encounters.length > 0 });
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
    document.title = brandName(D.brand) + " · " + t("table.title");
    quitBtn.textContent = t("board.quit");
    quitBtn.title = t("board.quit");
    previous.clear();
    const layer = document.getElementById("hv-pieces");
    layer.innerHTML = "";
    pieces.clear();
  } catch (error) {
    console.warn("Harbor View could not load settings", error);
    retryInfo = setTimeout(refreshInfo, 3000);
  } finally {
    reloading = false;
  }
  if (D && S && S.cfg === cfgSeen) { render(); speakNews(); }
}

/* The news crier reads fresh headlines aloud, exactly as on the harbor board (same Admin switch).
   Headlines already up when the view opens are not read. */
function speakNews() {
  const news = S.news || [], plans = (S.voice && S.voice.news) || [];
  if (newsSeen === null) { newsSeen = new Set(news); return; }
  const fresh = [];
  news.forEach((n, i) => { if (!newsSeen.has(n)) { newsSeen.add(n); if (plans[i]) fresh.unshift(plans[i]); } });
  if (fresh.length && VS.news_board) Voice.say(fresh, { group: "news" });
}

/* Esc or the small Quit button closes the window (the game keeps running). */
function quitView() {
  window.close();
  setTimeout(() => { if (!window.closed) quitBtn.textContent = t("board.quit_hint"); }, 300);
}
quitBtn.addEventListener("click", quitView);
document.addEventListener("keydown", e => { if (e.key === "Escape") { e.preventDefault(); quitView(); } });

// The mute button joins the corner controls; the speaking card stays on the page so it keeps its place.
const muteButton = document.getElementById("mute");
if (muteButton) document.getElementById("hv-controls").prepend(muteButton);
Faces.onChange = () => render();
listen(null, state => {
  S = state;
  if (!D || state.cfg !== cfgSeen) return refreshInfo();
  render();
  speakNews();
}, showConnection);
