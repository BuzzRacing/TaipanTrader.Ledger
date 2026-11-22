"use strict";
const T_FALLBACK = { "table.title": "Harbor View", "table.home": "Home" };
let D = null, S = null, TV = null, VS = {}, scene = null, infoAt = 0, hostSpoken = false;
const app = document.getElementById("app"), previous = new Map(), SVGNS = "http://www.w3.org/2000/svg";
const portName = key => D?.ports[key]?.name || key || "";
const colorOf = p => COLORS[(p.color || 0) % COLORS.length];
function update(id, html) {
  if (previous.get(id) === html) return null;
  const el = document.getElementById(id);
  if (!el) return null;
  el.innerHTML = html; previous.set(id, html); return el;
}
/* Liquid stage: the Table fills whatever window it is in. The design unit is the 1920x1080 "reference pixel";
   the stage keeps the reference AREA but takes the window's own shape, so a 16:9 screen looks exactly as
   designed while ultrawide, 16:10, 4:3 and upright screens get more width or more height instead of black
   bars. The CSS lays everything out from --w and --h (stage size in reference pixels). */
let resizeTimer = 0;
function fitStage() {
  const vw = Math.max(1, innerWidth), vh = Math.max(1, innerHeight);
  const k = Math.max(0.25, Math.sqrt(vw * vh / (1920 * 1080)));
  app.style.setProperty("--w", (vw / k).toFixed(2) + "px");
  app.style.setProperty("--h", (vh / k).toFixed(2) + "px");
  app.style.transform = `scale(${k})`;
}
function onResize() {
  app.classList.add("is-resizing");               /* no easing while the window is being dragged */
  fitStage();
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => app.classList.remove("is-resizing"), 250);
}
window.addEventListener("resize", onResize);
window.addEventListener("orientationchange", onResize);
fitStage();
/* --------------------------------------------------------------- the sky -- */
function drawSky(S) {
  const out = [];
  for (const key of Object.keys(D.regions)) {
    const reg = D.regions[key];
    let x = (reg.label_lon - 85) / 50 * 1000, y = (35 - reg.label_lat) / 45 * 600;
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

const houseOf = p => {
  const house = TV?.houses?.[p.id];
  return scene?.focus?.id === p.id && scene.focus.ships ? { ...house, ships: scene.focus.ships.map(sh => ({ ...sh, hull: sh.hull / Math.max(1, D.ships[sh.type]?.hull || 1) })) } : house;
};

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
  if (!p) return { x: 500, y: 560 };
  const side = p.label_left ? 1 : -1;
  return { x: p.x + side * 40, y: p.y + (index - (count - 1) / 2) * 34 };
}

function paintedMarkup(p, fleet) {
  const col = colorOf(p), size = 92;
  const shown = fleet.slice(0, 1).map(sh => ({ sh, u: shipArt(sh.type) }));
  if (!shown.some(x => x.u)) return "";
  let out = `<ellipse class="berth" rx="26" ry="38" fill="${col}"/>`;
  for (let i = shown.length - 1; i >= 0; i--) {
    const { sh, u } = shown[i];
    if (!u) continue;
    out += `<image class="painted${sh.crippled || sh.hull < .5 ? " hurt" : ""}" href="${u}" x="${-size / 2}" y="${-size / 2}" width="${size}" height="${size}"/>`;
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
  const n = 1, col = colorOf(p);
  let behind = "";
  for (let i = n - 1; i >= 1; i--) behind += `<path class="hull behind" fill="${col}" transform="translate(${i * 5} ${i * 3.5})" d="${HULL}"/>`;
  return `<g class="turn"><g class="bob">${behind}<path class="hull" fill="${col}" d="${HULL}"/>${SAILS}</g></g>` +
    `<circle class="ready-ring" r="25"/>` +
    `<g class="bars"><rect x="-17" y="-19" width="34" height="38" rx="3"/><path d="M-9 -19 V19 M0 -19 V19 M9 -19 V19"/></g>` +
    ((p.ships || 0) > 1 ? `<text class="count" x="19" y="-13">×${p.ships}</text>` : "") +
    `<text class="tag" y="37">${esc(p.firm)}</text>`;
}

function drawPieces(fighting, S) {
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
      rec.g.classList.toggle("sailing", scene?.kind === "voyage" && p.id === TV.focus?.id);
      if (rec.g.classList.contains("new")) requestAnimationFrame(() => rec.g.classList.remove("new"));
    });
  }
  for (const [id, rec] of pieces) if (!seen.has(id)) { rec.g.remove(); pieces.delete(id); }

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


const SHARE_R = 15, lastRing = {}, lastPrice = {};
function ringPath(i, n, r) {
  const gap = 0.10, a0 = -Math.PI / 2 + (i / n) * 2 * Math.PI + gap, a1 = -Math.PI / 2 + ((i + 1) / n) * 2 * Math.PI - gap;
  return `M${(r * Math.cos(a0)).toFixed(2)} ${(r * Math.sin(a0)).toFixed(2)} A${r} ${r} 0 0 1 ${(r * Math.cos(a1)).toFixed(2)} ${(r * Math.sin(a1)).toFixed(2)}`;
}
function drawPorts(S) {
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
    if (info.prices && scene?.kind === 'trade' && scene.port === key) {
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


const whoOf = key => VS.cast?.[key] || {};
const fact = (label, value) => `<span><small>${esc(label)}</small><b>${esc(value)}</b></span>`;
const reduced = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
const director = new TableDirector(next => {
  Voice.drop('table');
  scene = next;
  document.getElementById('hv-linger').setAttribute('aria-pressed', String(director.linger));
  render();
  speakScene();
  if (next) sceneSound(next);
});
director.canAdvance = s => {
  const now = Date.now(), age = now - s.startedAt;
  const reading = Math.max(s.kind === 'voyage' ? 6500 : 3400, Math.min(16000, 1600 + (s.presentationText || '').length * 40), s.duration);
  if (age >= 28000) return true;
  if (!s.voiceExpected || Voice.muted()) return age >= reading;
  if (s.voiceEndedAt) return age >= 3400 && now >= s.voiceEndedAt + 900;
  if (s.voiceStarted) return false;
  return age >= Math.max(5000, reading);
};

function sceneSound(s) {
  const moment = s.frame?.moment || s.frame?.kind;
  const cue = s.kind === 'battle' ? ({ sighting: 'battle.alert', broadside: 'battle.broadside', enemy_hit: 'battle.enemy_hit',
    we_are_hit: 'battle.we_are_hit', ship_lost: 'battle.ship_lost', boarding: 'battle.boarding.clash',
    victory: 'stinger.victory', defeat: 'stinger.defeat', got_away: 'battle.got_away', retreat: 'battle.retreat' })[moment]
    : s.kind === 'storm' ? 'ship.groan' : s.kind === 'promotion' ? 'stinger.promotion'
    : s.kind === 'jail' ? 'jail.door' : s.kind === 'news' ? 'crier.headline'
    : s.kind === 'host' ? 'turn.new' : ({ buy: 'trade.buy.success', sell: 'trade.sell.success', repair: 'ship.repair',
      ship: 'ship.purchased', protect: 'deal.heavy', loan: 'desk.coin', bank: 'desk.coin', ship_lost: 'stinger.ship_lost' })[s.type];
  if (cue) SeaAudio.playOnce('table:' + TV.game_id + ':' + s.key, cue);
}

function chooseArt(who, mood, key, port, story) {
  if (port && who === 'mayor') {
    const portraits = Media.items('port', port);
    const role = story?.kind === 'promotion' ? 'mayor_congrats' : 'mayor';
    const image = portraits.find(i => (i.r || []).includes(role));
    if (image) return image;
  }
  // The persona spot is a figure standing in the scene. Wallpaper master shots (Accounting Ledger backdrops) and the
  // Dashboard's masthead pictures and banners are wide scenes used elsewhere, so they never appear here.
  const list = Media.items('persona', who).filter(i => !notFigure(i));
  const dedicated = list.filter(i => (i.g || []).includes('table-' + mood));
  const pick = dedicated.length ? dedicated : list.filter(i => (i.r || []).includes(mood));
  if (pick.length) {
    let hash = 0;
    for (const c of String(key)) hash = ((hash << 5) - hash + c.charCodeAt(0)) | 0;
    return pick[Math.abs(hash) % pick.length];
  }
  // No picture for this mood: her starred portrait, else any portrait, else any other figure picture. Never null-routed
  // through the wallpaper role (the old fallback); with nothing left, figure() shows her profile portrait.
  const portraits = list.filter(i => !(i.r || []).length || i.r.includes('portrait'));
  return portraits.find(i => i.p) || portraits[0] || list.find(i => i.p) || list[0] || null;
}

/* A persona picture that is a wide scene for another screen: tagged or filed as wallpaper / master shot, or masthead. */
function notFigure(item) {
  const marks = [...(item.g || []), ...(item.r || [])].map(x => String(x).toLowerCase());
  return marks.some(x => x === 'wallpaper' || x === 'master-shot' || x === 'reclining' || x.startsWith('masthead'));
}

function characterOf(s) {
  if (!s) return 'gamemaster';
  if (s.who) return s.who;
  return ({ buy: 'comprador', sell: 'comprador', bank: 'banker', loan: 'lender', protect: 'agent', repair: 'shipwright',
    ship: 'shipwright', guns: 'bosun', seized: 'officer_' + s.port, customs: 'officer_' + s.port,
    declare: 'officer_' + s.port, tax: 'officer_' + s.port, jail: 'warden_' + s.port,
    shipwreck: 'narrator', ship_lost: 'narrator', won: 'bosun', retreat: 'bosun', plundered: 'bosun',
    arrived: 'mayor', shares: 'mayor', estate: 'mayor', gift: 'mayor', band: 'mayor', patron: 'mayor' })[s.type] || 'gamemaster';
}

function lineText(key, report = {}) {
  if (!key || !T[key]) return '';
  return t(key, { goods: (report.cargo || []).map(c => D.goods[c.good]?.name || c.good).join(', '),
    port: portName(report.landing?.port || report.port), yard: portName(report.landing?.yard_port) });
}
const words = (key, fallback) => T[key] == null ? fallback : t(key);

function stageData() {
  const s = scene, p = s?.focus || TV.focus, who = characterOf(s), r = s?.report || {};
  let title = '', text = s?.text || '', facts = '', location = portName(s?.port || p?.port), mood = s?.mood || 'speaking';
  let clips = (s?.clips || []).filter(Boolean), backdrop = null, full = false;
  const voice = s?.voice || {};
  if (!s || ['host','departure','landfall','return'].includes(s.kind)) {
    const key = s?.hostKey || (S.phase === 'lobby' ? 'gm.welcome' : S.phase === 'ended' ? 'gm.finale' : p?.storm ? 'gm.storm' : p?.battle ? 'gm.ask_battle' : 'gm.ask_sail');
    const host = s?.hostLine || s?.host?.[key] || TV.host?.[key];
    title = whoOf('gamemaster').name || 'Madame Anahit Sarkissian';
    text = host?.text || whoOf('gamemaster').catchphrase || '';
    clips = host?.clip ? [host.clip] : [];
    mood = s?.mood || (S.phase === 'ended' || S.phase === 'lobby' ? 'happy' : p?.ready ? 'sly' : 'host');
  } else if (s.kind === 'voyage') {
    title = `${portName(s.from)} → ${portName(s.port)}`; location = title;
    backdrop = Media.choose('scene', ['voyage'], 'background', { mode: 'fixed' });
  } else if (s.kind === 'arrival') {
    full = true; title = portName(s.port);
    backdrop = Media.choose('port', [s.port], 'arrival', { mode: 'fixed' });
  } else if (s.kind === 'storm' || (s.kind === 'reckoning' && s.source === 'storm')) {
    full = true;
    title = words('storm.title.' + r.band, 'Storm at sea');
    text = lineText(s.textKey, r);
    backdrop = Media.choose('scene', [r.typhoon ? 'typhoon' : 'storm'], 'background', { mode: 'fixed' });
    if (s.kind === 'reckoning') {
      facts = fact(words('storm.t.hull','Hull lost'), (r.hull_full ? Math.round(100 * r.hull_lost / r.hull_full) : 0) + '%')
        + fact(words('storm.t.cargo','Cargo lost'), money(r.cargo_cost || 0))
        + fact(words('storm.t.guns','Guns lost'), (r.guns_lost || 0) + (r.cannons_lost || 0))
        + fact('Making port', portName(r.landing?.port));
    }
  } else if (s.kind === 'battle' || (s.kind === 'reckoning' && s.source === 'battle')) {
    full = true;
    title = s.kind === 'reckoning' ? words('battle.res.' + r.outcome, 'The Reckoning') : s.frame?.cap || r.enemy || 'At close quarters';
    backdrop = Media.choose('scene', [r.kind === 'lord' ? 'seafight_lord' : 'seafight_pirates', 'battle'], s.frame?.moment || 'event', { mode: 'fixed' });
    if (s.kind === 'reckoning') {
      text = words('battle.res.reason_' + r.outcome, '');
      facts = fact(words('battle.res.sunk','Enemy sunk'), `${r.sunk} / ${r.n}`)
        + fact('Ships home', `${(r.ships || []).filter(x => !x.lost).length} / ${(r.ships || []).length}`)
        + fact('Prize silver', money(r.booty || 0)) + fact(words('battle.res.net','Net result'), (r.net > 0 ? '+' : '') + money(r.net || 0));
    }
  } else if (s.kind === 'legend') {
    full = true; title = r.chapter || r.title;
    backdrop = Media.choose('scene', ['legend_' + r.tale + '_' + r.chapter_id, 'legend'], 'background', { mode: 'fixed' });
  } else if (s.kind === 'customs' || (s.kind === 'reckoning' && s.source === 'customs')) {
    full = true; title = s.phase === 'verdict' || s.kind === 'reckoning' ? words('customs.verdict','Her verdict') : 'The Port Authority';
    backdrop = Media.choose('port', [s.port], 'banner', { mode: 'fixed' });
    if (s.kind === 'reckoning') {
      const result = r.result || {};
      facts = fact(words('customs.paid_her','Paid to the officer'), money((result.tax || 0) + (result.fine || 0)))
        + (result.paid ? fact(words('customs.she_paid','Paid to the House'), money(result.paid)) : '')
        + fact('Standing', (result.rep > 0 ? '+' : '') + (result.rep || 0))
        + (result.owed ? fact('Added to debt', money(result.owed)) : '');
    }
  } else if (s.kind === 'jail' || (s.kind === 'reckoning' && s.source === 'jail')) {
    full = true; title = words('jail.arrested','An audience behind bars');
    text = s.text || '';
    if (s.kind === 'reckoning') { const j = r.jail || r.plea || {}; facts = fact('Months remaining', j.left ?? j.months ?? 0); }
    backdrop = Media.choose('port', [s.port], 'jail_cell', { mode: 'fixed' });
    clips = s.clips || [];
  } else if (s.kind === 'promotion') {
    full = true; title = r.title || 'A House ascends'; text = r.text || '';
    clips = (voice.promotion || []).filter(Boolean);
    backdrop = Media.choose('port', [s.port], 'banner', { mode: 'fixed' });
  } else if (s.kind === 'news') { title = 'Word from the waterfront'; }
  else {
    title = ({ buy:'A bargain struck', sell:'The silver changes hands', bank:'Under lock and key', loan:'The price of ambition',
      protect:'A price for safe passage', shares:'A stake in the harbour', estate:'A House takes root', repair:'Fit for the next voyage',
      seized:'The hold is opened', ship_lost:'A ship lost', shipwreck:'The cost of the sea' })[s.type] || 'At the table';
    backdrop = Media.choose('port', [s.port], 'banner', { mode: 'fixed' });
  }
  const art = chooseArt(who, mood, s?.key || 'host:' + S.turn, s?.port, s);
  const peerArt = s?.peer ? chooseArt(s.peer, 'speaking', s.sequence + ':peer', s.port, s) : null;
  return { who, title, text, facts, location, mood, clips, backdrop, full, art, peerArt, focus:p, state:s?.state || S };
}

function camera(port, from) {
  const world = document.getElementById('hv-world'), p = D.ports[port], a = D.ports[from];
  let zoom = 1, cx = 500, cy = 300;
  if (p && a) {
    const w = Math.max(260, Math.abs(p.x - a.x) + 200), h = Math.max(180, Math.abs(p.y - a.y) + 130);
    zoom = Math.min(2, 1000 / w, 600 / h); cx = (p.x + a.x) / 2; cy = (p.y + a.y) / 2;
  } else if (p && scene && !['host','return','storm','battle','reckoning','legend','jail','promotion','customs'].includes(scene.kind)) {
    zoom = 1.75; cx = p.x; cy = p.y;
  }
  const x = Math.min(0, Math.max(1000 - 1000 * zoom, 500 - cx * zoom));
  const y = Math.min(0, Math.max(600 - 600 * zoom, 300 - cy * zoom));
  world.style.transform = `translate(${x / 10}%,${y / 6}%) scale(${zoom})`;
}

function route() {
  if (scene?.kind !== 'voyage') return update('hv-route', '');
  const a = D.ports[scene.from], b = D.ports[scene.port];
  if (!a || !b) return;
  const id = 'hv-course', path = `M${a.x} ${a.y} Q${(a.x+b.x)/2+28} ${(a.y+b.y)/2-28} ${b.x} ${b.y}`;
  const art = shipArt(scene.focus?.ships?.[0]?.type);
  const ship = art ? `<image href="${art}" x="-36" y="-36" width="72" height="72"/>` : '<path d="M0 -14L7 9L0 5L-7 9Z"/>';
  update('hv-route', `<path id="${id}" class="course" d="${path}"/><g class="traveller"${reduced() ? ` transform="translate(${b.x} ${b.y})"` : ''}><g transform="rotate(90)">${ship}</g>${reduced() ? '' : `<animateMotion dur="5s" fill="freeze" rotate="auto"><mpath href="#${id}"/></animateMotion>`}</g>`);
}

let backdropUrl = '', backdropToken = 0, backdropSide = 0;
function setBackdrop(url) {
  if (!url || url === backdropUrl) return;
  backdropUrl = url;
  const token = ++backdropToken, image = new Image();
  image.onload = () => {
    if (token !== backdropToken) return;
    backdropSide = 1 - backdropSide;
    const panes = [document.getElementById('hv-backdrop'), document.getElementById('hv-backdrop-next')];
    panes[backdropSide].style.backgroundImage = `url("${url}")`;
    panes[backdropSide].classList.add('on'); panes[1-backdropSide].classList.remove('on');
  };
  image.onerror = () => { console.warn('Table backdrop could not load', url); backdropUrl = ''; };
  image.src = url;
}

function render() {
  if (!D || !S || director.paused) return;
  const view = stageData(), shown = { ...view.state };
  const focus = view.focus;
  shown.players = (shown.players || []).map(p => p.id === focus?.id ? { ...p, port: focus.port, ships: focus.ships?.length ?? p.ships, worth: focus.worth } : p);
  app.classList.toggle('is-duet', Boolean(scene?.peer && view.peerArt));
  app.classList.toggle('speaker-right', scene?.side === 'right');
  app.dataset.scene = scene?.kind || 'host'; app.classList.toggle('is-story', view.full);
  update('hv-date', esc(shown.date)); update('hv-location', esc(view.location));
  update('hv-phase', esc(scene?.kind === 'voyage' ? 'Under sail' : shown.phase === 'ended' ? 'Voyage complete' : shown.phase === 'sea' ? 'At sea' : shown.phase === 'lobby' ? 'The table is gathering' : 'In port'));
  const changed = update('hv-chart-base', Chart.svg({ data: D, players: [], crackdown: shown.crackdown, hideWeather: true, hideRose: false }));
  drawSky(shown); drawPieces(shown.sea || [], shown); drawPorts(shown); route(); camera(scene?.port, scene?.from);
  if (changed) { requestAnimationFrame(() => Chart.fit(changed)); setTimeout(() => Chart.fit(changed), 900); }
  const figure = (art, who) => {
    const picture = art?.u || whoOf(who).portrait;
    return picture ? `<img class="figure" src="${esc(picture)}" alt="${esc(whoOf(who).name || who)}">`
      : `<div class="missing"><b>${esc(whoOf(who).name || who)}</b><p>Her portrait is being prepared.</p></div>`;
  };
  const right = scene?.side === 'right';
  update('hv-persona', figure(right && view.peerArt ? view.peerArt : view.art, right && view.peerArt ? scene.peer : view.who));
  update('hv-counterpart', scene?.peer && view.peerArt ? figure(right ? view.art : view.peerArt, right ? view.who : scene.peer) : '');
  const background = view.backdrop?.u || Media.items('scene', 'loading').find(x => (x.g || []).includes('table-cabin'))?.u;
  setBackdrop(background);
  update('hv-story', `<p class="eyebrow">${esc(scene?.kind === 'reckoning' ? 'The Reckoning · ' + view.location : view.full ? view.location : whoOf(view.who).title || '')}</p><h1>${esc(view.title)}</h1>`
    + (view.text ? `<blockquote>${esc(view.text)}</blockquote>` : '')
    + (view.full || scene?.kind === 'trade' ? `<p class="byline">${esc(whoOf(view.who).name || '')}</p>` : '')
    + (view.facts ? `<div class="facts">${view.facts}</div>` : '') + (scene?.beatCount > 1 ? `<p class="hv-beats" aria-label="Story beat ${scene.beatIndex+1} of ${scene.beatCount}">${Array.from({length:scene.beatCount}, (_,i) => `<i class="${i===scene.beatIndex?'active':''}"></i>`).join('')}</p>` : ''));
  const p = focus || shown.players[0], crest = p && Faces.of(p).crest;
  const shipCount = Array.isArray(p?.ships) ? p.ships.length : p?.ships || 0;
  update('hv-ledger', p ? `${crest ? `<img class="crest" src="${esc(crest)}" alt="">` : ''}<span class="house">${esc(p.firm)}</span><span>${esc(portName(p.port))}</span><span>${shipCount} ${shipCount === 1 ? 'ship' : 'ships'}</span><span class="worth">Net worth ${esc(money(p.worth))}</span>` : '<span>The table awaits its Captain.</span>');
  update('hv-map-note', esc(scene?.kind === 'voyage' ? `${portName(scene.from)} → ${portName(scene.port)}` : TV.focus ? `${portName(TV.focus.port)} · ${TV.focus.ready ? 'Orders sealed' : 'The Captain is doing business'}` : 'The trading waters'));
  update('hv-bulletin', esc((S.news || [])[0] || ''));
  document.getElementById('hv-loading').hidden = true; app.hidden = false;
  Soundscape.sync(shown, { battle: scene?.kind === 'battle', storm: scene?.kind === 'storm' });
}

function speakScene() {
  if (!TV || director.paused) return;
  const view = stageData();
  if (!scene && hostSpoken) return;
  if (!scene) hostSpoken = true;
  if (scene) { scene.presentationText = view.text; scene.voiceExpected = view.clips.length > 0 && Voice.enabled() && !Voice.muted(); }
  if (view.clips.length) Voice.say(view.clips.map(c => ({ ...c, tag: 'table:' + (scene?.key || TV.game_id), m: view.mood })), { group: 'table', front: true });
}

let polling = false, retry = 1500, closed = false;
async function poll() {
  if (polling || closed) return;
  polling = true;
  try {
    const response = await fetch('/api/table', { cache: 'no-store' });
    if (!response.ok) throw new Error('Table feed HTTP ' + response.status);
    const feed = await response.json();
    if (!feed.ok || !feed.state) throw new Error('Table feed is missing its game snapshot');
    if (!D || Date.now() - infoAt > 30000 || feed.state.cfg !== cfgSeen) {
      const info = await loadInfo(); D = info.data; VS = Voice.setup(info.voice); infoAt = Date.now();
      document.title = brandName(D.brand) + ' · Harbor View'; previous.clear();
    }
    if (feed.state.cfg !== undefined && feed.state.cfg !== cfgSeen) return;
    if (TV && TV.game_id !== feed.game_id) {
      pieces.clear(); previous.clear(); hostSpoken = false; scene = null; Voice.drop('table');
      for (const key of Object.keys(lastRing)) delete lastRing[key];
      for (const key of Object.keys(lastPrice)) delete lastPrice[key];
      document.getElementById('hv-pieces').innerHTML = '';
    }
    TV = feed; S = feed.state;
    director.ingest(feed);
    const pause = document.getElementById('hv-pause');
    pause.setAttribute('aria-pressed', String(director.paused)); pause.textContent = director.paused ? 'Resume' : 'Pause';
    document.getElementById('hv-paused').hidden = !director.paused;
    render();
    if (!hostSpoken && !scene) speakScene();
    document.getElementById('hv-connection').textContent = '';
    retry = 1500;
  } catch (error) {
    console.warn('Harbor View could not refresh', error);
    document.getElementById('hv-connection').textContent = 'Reconnecting…'; retry = 4000;
    if (!D) document.getElementById('hv-loading').textContent = 'The table is reconnecting to the game…';
  } finally { polling = false; if (!closed) setTimeout(poll, retry); }
}

const soundDialog = document.getElementById('hv-sound-dialog');
const muteButton = document.getElementById('mute');
if (muteButton) document.getElementById('hv-controls').prepend(muteButton);
function drawSound() { if (typeof SeaAudioPanel !== 'undefined') update('hv-sound-panel', SeaAudioPanel.html((key, fb) => T[key] || fb)); }
function quitView() { window.close(); setTimeout(() => { document.getElementById('hv-quit').textContent = 'Close this browser window'; }, 300); }

document.getElementById('hv-controls').addEventListener('click', e => {
  const id = e.target.closest('button')?.id;
  if (id === 'hv-pause') {
    const paused = director.pause(); e.target.setAttribute('aria-pressed', String(paused)); e.target.textContent = paused ? 'Resume' : 'Pause';
    document.getElementById('hv-paused').hidden = !paused; Voice.lead(!paused); if (paused) Voice.drop('table'); else render();
  } else if (id === 'hv-skip') director.skip();
  else if (id === 'hv-board') director.board();
  else if (id === 'hv-linger') { director.linger = !director.linger; e.target.setAttribute('aria-pressed', String(director.linger)); }
  else if (id === 'hv-sound') { drawSound(); soundDialog.showModal(); }
  else if (id === 'hv-quit') quitView();
});
document.getElementById('hv-sound-close').addEventListener('click', () => soundDialog.close());
soundDialog.addEventListener('input', e => { if (typeof SeaAudioPanel !== 'undefined') SeaAudioPanel.input(e); });
soundDialog.addEventListener('click', e => { if (typeof SeaAudioPanel !== 'undefined') SeaAudioPanel.click(e); });
SeaAudio.onChange(() => { if (soundDialog.open) { previous.delete('hv-sound-panel'); drawSound(); } });
Voice.onChange(item => {
  if (!scene || director.paused) return;
  if (item?.tag === 'table:' + scene.key) scene.voiceStarted = true;
  else if (scene.voiceStarted && !scene.voiceEndedAt) scene.voiceEndedAt = Date.now();
});
document.addEventListener('keydown', e => {
  if (soundDialog.open || e.target.matches('input,button,select,textarea')) return;
  if (e.key === 'Escape') { e.preventDefault(); director.board(); }
  if (e.key === ' ') { e.preventDefault(); document.getElementById('hv-pause').click(); }
  if (e.key === 'ArrowRight') director.skip();
});
Faces.onChange = () => render();
window.addEventListener('pagehide', () => { closed = true; Voice.stop(); });
setInterval(() => { if (D && S) director.tick(); }, 200);
if (document.fonts?.ready) document.fonts.ready.then(() => Chart.fit(document.getElementById('hv-chart-base')));
poll();
