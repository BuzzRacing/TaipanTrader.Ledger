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
  "table.fleet_label": "Ships in fleet",
  "table.writing": "Writing orders…",
  "table.at": "At {port}",
  "table.jailed": "In jail at {port}",
  "table.home": "Home",
  "table.mayor": "Mayor of {port}",
  "act.buy": "{firm} buys {qty} {good}.",
  "act.sell": "{firm} sells {qty} {good}.",
  "act.bank_out": "{firm} puts its silver in the bank.",
  "act.bank_in": "{firm} draws its silver from the bank.",
  "act.loan_in": "{firm} borrows against the House.",
  "act.loan_out": "{firm} pays down its debt.",
  "act.shares_out": "{firm} buys shares in our port.",
  "act.shares_in": "{firm} sells its shares in our port.",
  "act.estate_out": "{firm} builds a great house here.",
  "act.estate_in": "{firm} sells its great house.",
  "table.home_port": "Home port: {port}",
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
    out.push(`<g class="wx${lvl}" transform="translate(${x.toFixed(1)} ${y.toFixed(1)})"><g transform="scale(1.7)">${art}</g>` +
      `<rect class="plaque" x="-92" y="6" width="184" height="62" rx="9"/>` +
      `<text class="sea-wx" y="38">${esc(D.weather[lvl])}</text><text class="sea-name" y="59">${esc(reg.name)}</text></g>`);
  }
  update("hv-sky", out.join(""));
}

/* ------------------------------------------------------------ the pieces -- */
const HULL = "M0 -16 C7 -9 8 6 5 15 L-5 15 C-8 6 -7 -9 0 -16Z";
const SAILS = '<path class="deck" d="M0 -11 C4 -6 4.5 5 3 11 L-3 11 C-4.5 5 -4 -6 0 -11Z"/>' +
  '<rect class="sail" x="-10" y="-7" width="20" height="5.5" rx="1.5"/><rect class="sail" x="-9" y="3" width="18" height="5" rx="1.5"/>';
const pieces = new Map();      // player id -> { g, x, y, port, heading }

/* The spectator feed (/api/table, harbor_view.py): each house's Captain, home port and ship classes.
   Fetched again whenever the month, the phase or a fleet's size changes. */
let TV = null, tvKey = "", tvBusy = false, tvTimer = null;
function refreshTable() {
  if (!S || tvBusy) return;
  const key = [S.game_id, S.turn, S.phase, S.players.map(p => p.id + ":" + p.ships + ":" + p.port).join(","),
    TV && TV.level === "open" ? Math.floor(Date.now() / 2500) : ""].join("|");   // prices tick: ask again every few seconds
  if (key === tvKey) {      // nothing new yet: look again shortly, so a deal made just after a read is not missed
    if (TV && TV.level === "open" && !tvTimer) tvTimer = setTimeout(() => { tvTimer = null; refreshTable(); }, 2600);
    return;
  }
  tvBusy = true; tvKey = key;
  let failed = false;
  fetch("/api/table").then(r => r.json()).then(r => { if (r && r.ok) { TV = r; handleActivity(r.activity || []); render(); } })
    .catch(() => { failed = true; tvKey = ""; setTimeout(refreshTable, 5000); })
    .finally(() => { tvBusy = false; if (!failed) refreshTable(); });
}
const houseOf = p => (TV && TV.houses && TV.houses[p.id]) || null;

/* A painted ship piece (Media Library > Ships, role "topdown", on white so it lifts off the chart), or "". */
function shipArt(type) {
  const item = Media.choose("ship", [type], "topdown", { mode: "fixed", strict: true });
  return item && item.t === "image" ? cutout(item.u) : "";
}

/* The pictures are painted on plain white. Lift the ship off it in the browser: the white that touches the
   picture's edge becomes clear (inner white, such as sails, stays), and the result is kept. "" until ready. */
const cutouts = new Map();       // url -> data URL, or "" while loading / if it cannot be made
function cutout(url) {
  if (!url) return "";
  if (cutouts.has(url)) return cutouts.get(url);
  cutouts.set(url, "");
  const img = new Image();
  img.onload = () => {
    try {
      const W = 360, c = document.createElement("canvas");
      c.width = c.height = W;
      const x = c.getContext("2d", { willReadFrequently: true });
      x.drawImage(img, 0, 0, W, W);
      const d = x.getImageData(0, 0, W, W), px = d.data, gone = new Uint8Array(W * W), stack = [];
      const white = i => px[i * 4] > 226 && px[i * 4 + 1] > 226 && px[i * 4 + 2] > 226;
      const seed = i => { if (!gone[i] && white(i)) { gone[i] = 1; stack.push(i); } };
      for (let k = 0; k < W; k++) { seed(k); seed((W - 1) * W + k); seed(k * W); seed(k * W + W - 1); }
      while (stack.length) {
        const i = stack.pop(), cx = i % W, cy = (i - cx) / W;
        if (cx > 0) seed(i - 1);
        if (cx < W - 1) seed(i + 1);
        if (cy > 0) seed(i - W);
        if (cy < W - 1) seed(i + W);
      }
      for (let i = 0; i < W * W; i++) {
        if (gone[i]) px[i * 4 + 3] = 0;
        else if ((i % W && gone[i - 1]) || (i % W < W - 1 && gone[i + 1]) || (i >= W && gone[i - W]) || (i < W * (W - 1) && gone[i + W])) {
          px[i * 4 + 3] = Math.min(px[i * 4 + 3], 150);          // soften the rim
        }
      }
      x.putImageData(d, 0, 0);
      cutouts.set(url, c.toDataURL("image/png"));
      for (const rec of pieces.values()) rec.mark = "";        // draw the pieces again with the lifted pictures
      render();
    } catch (e) { console.warn("Could not lift ship picture", e); }
  };
  img.crossOrigin = "anonymous";
  img.src = url;
  return "";
}

function seatAt(port, index, count) {
  const p = D.ports[port];
  if (!p) return { x: TITLE_AT.x, y: 560 };
  const side = p.label_left ? 1 : -1;
  return { x: p.x + side * 40, y: p.y + (index - (count - 1) / 2) * 34 };
}

function paintedMarkup(p, fleet) {
  const col = colorOf(p), size = 92;
  const shown = fleet.slice(0, 4).map(sh => ({ sh, u: shipArt(sh.type) }));
  if (!shown.some(x => x.u)) return "";
  let out = `<ellipse class="berth" rx="26" ry="38" fill="${col}"/>`;
  for (let i = shown.length - 1; i >= 0; i--) {
    const { sh, u } = shown[i];
    if (!u) continue;
    out += `<image class="painted${sh.crippled || sh.hull < .5 ? " hurt" : ""}" href="${u}" x="${-size / 2 + i * 9}" y="${-size / 2 + i * 6}" width="${size}" height="${size}"/>`;
  }
  return `<g class="turn"><g class="bob">${out}<circle class="pennant" cx="0" cy="-38" r="5" fill="${col}"/></g></g>` +
    `<circle class="ready-ring" r="30"/>` +
    ((p.ships || 0) > 1 ? `<text class="count" x="24" y="-20">×${p.ships}</text>` : "") +
    `<text class="tag" y="46">${esc(p.firm)}</text>`;
}

function pieceMarkup(p) {
  const house = houseOf(p);
  if (house && house.ships && house.ships.length) {
    const painted = paintedMarkup(p, house.ships);
    if (painted) return painted;
  }
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
    layer.innerHTML = '<g id="hv-ports"></g><g id="hv-marks"></g><g id="hv-fleet"></g>';
    previous.delete("hv-marks"); previous.delete("hv-ports");
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
  // Each house's home port wears its flag: a ring in the house colour with its crest (or an anchor).
  const homes = {};
  for (const p of S.players) { const h = houseOf(p); if (h && D.ports[h.home]) (homes[h.home] = homes[h.home] || []).push(p); }
  for (const key of Object.keys(homes)) {
    const port = D.ports[key], list = homes[key];
    list.forEach((p, i) => {
      const col = colorOf(p), crest = Faces.of(p).crest, id = "hv-home-" + String(p.id).replace(/\W/g, "");
      const dx = (i - (list.length - 1) / 2) * 44, side = port.label_left ? 1 : -1;
      marks.push(`<g class="home" transform="translate(${(port.x + side * 4 + dx).toFixed(1)} ${(port.y + (port.y < 90 ? 48 : -40)).toFixed(1)})">` +
        `<path class="pole" d="M0 22 V-8"/><path class="flag" fill="${col}" d="M0 -8 H26 L20 0 L26 8 H0Z"/>` +
        `<circle class="disc" r="17" fill="${col}"/>` +
        (crest ? `<clipPath id="${id}"><circle r="14"/></clipPath><image href="${esc(crest)}" x="-14" y="-14" width="28" height="28" clip-path="url(#${id})"/>`
          : `<path class="anchor" d="M0 -9 V9 M-7 3 Q0 12 7 3 M-5 -4 H5"/>`) +
        `<text class="home-tag" y="36">${te("table.home")}</text></g>`);
    });
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

/* ---------------------------------------------- the camera and the Mayor -- */
// Big deals (harbor_view.activity: at least half the cash held before) pull the camera to the port for a few seconds
// with the Mayor's popup; deals queue and play one after another, and a burst of the same kind is joined into one.
const ZOOM = 3, HOLD_MS = 8000, EASE_MS = 1800;
let seenN = null, zooming = false;
const queue = [];
function handleActivity(list) {
  const top = list.reduce((m, e) => Math.max(m, e.n || 0), 0);
  if (seenN === null) { seenN = top; return; }            // what happened before the view opened is not replayed
  for (const e of list) {
    if (!(e.n > seenN)) continue;
    const last = queue[queue.length - 1];
    if (last && last.pid === e.pid && last.port === e.port && last.type === e.type && last.good === e.good && last.cash_out === e.cash_out) {
      last.value += e.value; last.qty += e.qty;
    } else queue.push(Object.assign({}, e));
  }
  seenN = Math.max(seenN, top);
  playQueue();
}
function portPx(key) {
  const world = document.getElementById("hv-world"), idx = Object.keys(D.ports).indexOf(key);
  const g = document.getElementById("hv-chart-base").querySelectorAll(".port")[idx], dot = g && g.querySelector(".dot");
  if (!dot) return null;
  const was = [world.style.transform, world.style.transition];
  world.style.transition = "none"; world.style.transform = "none";
  const wr = world.getBoundingClientRect(), k = wr.width / world.offsetWidth, r = dot.getBoundingClientRect();
  world.style.transform = was[0]; world.style.transition = was[1];
  return { x: (r.left + r.width / 2 - wr.left) / k, y: (r.top + r.height / 2 - wr.top) / k, w: world.offsetWidth, h: world.offsetHeight };
}
function playQueue() {
  if (zooming || !queue.length || !D || !S) return;
  const e = queue.shift(), p = S.players.find(q => q.id === e.pid), pt = portPx(e.port);
  if (!p || !pt) return playQueue();
  zooming = true;
  const world = document.getElementById("hv-world"), pop = document.getElementById("hv-popup");
  const tx = Math.min(0, Math.max(pt.w - pt.w * ZOOM, pt.w / 2 - pt.x * ZOOM)), ty = Math.min(0, Math.max(pt.h - pt.h * ZOOM, pt.h / 2 - pt.y * ZOOM));
  const sx = pt.x * ZOOM + tx, sy = pt.y * ZOOM + ty, PW = 470, PH = 190;
  const left = sx + 70 + PW > pt.w - 10 ? sx - 70 - PW : sx + 70, top = Math.min(pt.h - PH - 10, Math.max(10, sy - PH / 2));
  const key = e.type === "buy" || e.type === "sell" ? "act." + e.type : "act." + e.type + (e.cash_out ? "_out" : "_in");
  const mayor = Media.choose("port", [e.port], "mayor", { mode: "fixed" });
  const good = (D.goods[e.good] && D.goods[e.good].name) || e.good;
  pop.style.left = left.toFixed(0) + "px"; pop.style.top = top.toFixed(0) + "px";
  pop.innerHTML = `<div class="mayor">${mayor && mayor.t === "image" ? `<img src="${esc(mayor.u)}" alt="">` : "<b>M</b>"}</div>` +
    `<div class="say"><span class="who">${te("table.mayor", { port: portName(e.port) })}</span>` +
    `<p class="line">${te(key, { firm: p.firm, qty: e.qty, good })}</p>` +
    `<span class="amt ${e.cash_out ? "out" : "in"}">${e.cash_out ? "−" : "+"}${esc(money(e.value))}</span></div>`;
  world.style.transform = `translate(${tx.toFixed(1)}px, ${ty.toFixed(1)}px) scale(${ZOOM})`;
  pop.classList.add("show");
  setTimeout(() => {
    pop.classList.remove("show");
    world.style.transform = "none";
    setTimeout(() => { zooming = false; playQueue(); }, EASE_MS);
  }, HOLD_MS);
}

/* ------------------------------------------------ port rings and cards -- */
// One segment per share round the port, in the holder's house colour (sweeping in when bought); a small stock-board
// card at ports in play (a ship, a home port, or a house holding shares) with the three goods that moved most.
const SHARE_R = 15, lastRing = {}, lastPrice = {};
function ringPath(i, n, r) {
  const gap = 0.10, a0 = -Math.PI / 2 + (i / n) * 2 * Math.PI + gap, a1 = -Math.PI / 2 + ((i + 1) / n) * 2 * Math.PI - gap;
  return `M${(r * Math.cos(a0)).toFixed(2)} ${(r * Math.sin(a0)).toFixed(2)} A${r} ${r} 0 0 1 ${(r * Math.cos(a1)).toFixed(2)} ${(r * Math.sin(a1)).toFixed(2)}`;
}
function drawPorts() {
  if (!TV || !TV.ports) return;
  const byId = new Map(S.players.map(p => [p.id, p]));
  const active = new Set(S.players.map(p => p.port));
  for (const h of Object.values(TV.houses || {})) if (h.home) active.add(h.home);
  const out = [];
  for (const key of Object.keys(D.ports)) {
    const port = D.ports[key], info = TV.ports[key];
    if (!info) continue;
    const holders = Object.entries(info.shares || {}).filter(([id]) => byId.has(id)).sort((a, b) => b[1] - a[1]);
    const colours = [];
    for (const [id, n] of holders) for (let i = 0; i < n && colours.length < info.total; i++) colours.push(colorOf(byId.get(id)));
    const before = lastRing[key] || [];
    let ring = "";
    for (let i = 0; i < info.total; i++) {
      const c = colours[i];
      ring += `<path class="seg${c ? "" : " empty"}${c && before[i] !== c ? " fresh" : ""}"${c ? ` stroke="${c}"` : ""} d="${ringPath(i, info.total, SHARE_R)}"/>`;
    }
    lastRing[key] = colours;
    let card = "";
    if (info.prices && (active.has(key) || holders.length)) {
      const goods = Object.keys(info.prices);
      const move = g => { const b = (info.base || {})[g] || info.prices[g]; return b ? (info.prices[g] - b) / b : 0; };
      const rows = goods.sort((a, b) => Math.abs(move(b)) - Math.abs(move(a)) || info.prices[b] - info.prices[a]).slice(0, 3).map((g, i) => {
        const m = move(g), prev = (lastPrice[key] || {})[g], tick = prev != null && prev !== info.prices[g] ? (info.prices[g] > prev ? " tick-up" : " tick-down") : "";
        return `<g class="row${tick}" transform="translate(0 ${i * 17})"><text class="g" x="6" y="13">${esc(((D.goods[g] && D.goods[g].name) || g).slice(0, 9))}</text>` +
          `<text class="v" x="92" y="13">${esc(money(info.prices[g]))}</text>` +
          `<path class="arr ${m > .005 ? "up" : m < -.005 ? "down" : "flat"}" d="${m > .005 ? "M106 12 l4 -8 l4 8z" : m < -.005 ? "M106 5 l4 8 l4 -8z" : "M105 9 h10"}"/></g>`;
      }).join("");
      lastPrice[key] = Object.assign({}, info.prices);
      card = `<g class="pcard" transform="translate(${(-60).toFixed(0)} ${port.y < 90 ? 20 : 20})"><rect width="120" height="55" rx="6"/>${rows}</g>`;
    }
    if (colours.length || card || active.has(key)) {
      out.push(`<g class="share-ring" transform="translate(${port.x} ${port.y})">${ring}</g>` +
        (card ? `<g transform="translate(${port.x} ${port.y})">${card}</g>` : ""));
    }
  }
  update("hv-ports", out.join(""));
}

/* -------------------------------------------------------------- the mats -- */


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
    const cloth = Media.choose("scene", ["table_cloth"], "background", { mode: "fixed" });
    return `<article class="${cls.join(" ")}" style="--house:${colorOf(p)}${cloth ? `;--cloth:url('${esc(cloth.u)}')` : ""}">
      ${!lobby && n > 1 ? `<span class="place">${place.get(p.id) || ""}</span>` : ""}
      <div class="face">${faces.portrait ? `<img src="${esc(faces.portrait)}" alt="">` : `<b>${initial}</b>`}</div>
      ${faces.crest ? `<div class="crestbox"><img src="${esc(faces.crest)}" alt=""></div>` : ""}
      <div class="who"><h3>${esc(p.firm)}</h3><span class="cap">${esc(p.name)}${lobby && status ? " · " + esc(status) : ""}</span>${lobby ? "" : Ranks.label(p)}</div>
      ${lobby || ended ? "" : `<div class="orders"><div class="letter">${te("table.writing")}</div><span class="seal">${initial}</span>
        <small class="${battle ? "bad" : p.ready && p.present ? "ok" : ""}">${esc(status)}</small></div>`}
      <div class="fleet"><span class="label">${te("table.fleet_label")}</span><span class="ships">${esc(String(p.ships || 0))}</span>
        <span class="where">${te(p.jailed ? "table.jailed" : "table.at", { port: portName(p.port) })}</span>
        ${houseOf(p) ? `<span class="homeline">${te("table.home_port", { port: portName(houseOf(p).home) })}</span>` : ""}</div>
      ${lobby ? "" : `<div class="silver"><span class="label">${te("stat.worth")}</span><span class="worth">${esc(money(p.worth))}</span></div>`}
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
  update("hv-date", `<span class="kicker">${te(label)}</span><h2>${esc(S.date)}</h2><span class="sub">${esc(sub)}</span>${lobby ? "" : `<div class="prog" title="${esc(sub)}"><i style="width:${Math.min(100, Math.round(100 * (S.turn || 0) / Math.max(1, (S.years || 1) * 12)))}%"></i></div>`}
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
    `<path class="needle" d="M0 -150 L6 0 L-6 0Z"/></svg><h1>${wordmarkHtml(brandName(D.brand))}</h1>` +
    (D.brand.tagline ? `<p>${esc(D.brand.tagline)}</p>` : ""));
  drawSky();
  drawPieces(encounters);
  drawPorts();
  drawMats(ranked, fighting);
  drawDate(ranked, encounters);
  drawNews();

  app.hidden = false;
  loading.hidden = true;
  const base = document.getElementById("hv-chart-base");
  const here = new Set(S.players.map(p => p.port));
  [...base.querySelectorAll(".port")].forEach((g, i) => g.classList.toggle("occupied", here.has(Object.keys(D.ports)[i])));
  if (chart) { Chart.fit(chart); refitSoon(); }
  if (typeof Soundscape !== "undefined") Soundscape.sync(S, { battle: encounters.length > 0 });
}

/* Port label boxes are sized to their text, so measure again once the web fonts are really in. */
let refitTimer = null;
function refitSoon() {
  clearTimeout(refitTimer);
  refitTimer = setTimeout(() => Chart.fit(document.getElementById("hv-chart-base")), 900);
}
if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => refitSoon());

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
  refreshTable();
  if (!D || state.cfg !== cfgSeen) return refreshInfo();
  render();
  speakNews();
}, showConnection);
