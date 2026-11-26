/* SeaTrader Admin: Certificate Studio (21 Nov 2026; project doc "SeaTrader Voyage Certificate").

   Makes a Voyage Certificate at will from any finished game. Pick a game and a Captain and every figure is
   filled in from the books; then go through the sections, change what you like (sliders, fields, picture
   strips), and tick Approved on each. Save as wallpaper wakes up once every section is approved, and
   downloads the 1920 x 1080 PNG. It is painted by the same code as the end-of-game certificate
   (certificate.js), so what shows here is exactly what is saved. Nothing here is part of "Save & apply". */
(function () {
  "use strict";

  const SECTIONS = [
    ["captain", "Captain and voyage", "Who it is for, the House, the home port and the length of the voyage."],
    ["backdrop", "Backdrop", "The scene behind everything: pictures of the home port."],
    ["left", "Left side: the Mayor", "She fades in from the left. Pictures of the home port's Mayor."],
    ["right", "Right side: the story woman", "She fades in from the right. The woman the voyage earned, or any other."],
    ["headline", "Headline", "The big line: the finishing place or rank, and the career line under it."],
    ["figures", "Figures", "Final net worth, best sale and battles."],
  ];
  const YEARS = [5, 10, 20, 50];

  const st = {
    games: null, game: "", houses: [], pid: "", f: null, who: "", lib: null, fam: true,
    pics: { bg: [], mayor: [], persona: [] }, sel: { bg: null, mayor: null, persona: null },
    ok: new Set(), busy: "", msg: "", timer: 0, listen: null,
  };
  const $s = sel => document.querySelector("#main " + sel);
  const e = s => esc(s);
  const here = () => section === "certificate";

  async function getj(path) {
    try { return await (await fetch("/api/admin/certificate/" + path)).json(); }
    catch (err) { return { ok: false, error: "Cannot reach the game server." }; }
  }
  const cash = n => (n < 0 ? "-" : "") + CFG.brand.currency + Math.abs(Math.round(n)).toLocaleString("en-US");
  const ports = () => CFG.ports || {};
  const goods = () => CFG.goods || {};
  const world = () => ({ ports: CFG.ports, goods: CFG.goods, graphics: CFG.graphics || {}, brand: CFG.brand });
  const stamp = t => (t ? new Date(t * 1000).toLocaleString([], { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "");

  /* -------------------------------------------------------- the page -- */
  function render() {
    return `<div class="cs">
      <section class="card cs-intro"><h2>Certificate Studio</h2>
        <p class="help">Make a Voyage Certificate wallpaper from any finished game. Choose the game and Captain, change anything you like,
        then tick <b>Approved</b> on each section. Save as wallpaper unlocks once every section is approved.</p>
        <div class="row" id="cs-pick"><span class="muted">Opening the books…</span></div></section>
      <div class="cs-grid">
        <div class="cs-view"><div class="cs-stage"><canvas id="cs-canvas" width="1920" height="1080"></canvas><p class="cs-status" id="cs-status"></p></div>
          <p class="cs-line" id="cs-line" hidden></p>
          <div class="cs-bar"><span id="cs-count" class="muted"></span>
            <button type="button" id="cs-all" class="link">Approve all</button>
            <button type="button" id="cs-save" class="primary" disabled>Save as wallpaper</button></div>
          <p class="help" id="cs-hint" hidden></p></div>
        <div class="cs-sections" id="cs-sections"></div></div></div>`;
  }

  function enter() {
    CertStudioInit();
  }
  function leave() {
    clearTimeout(st.timer);
    if (st.listen) { document.removeEventListener("input", st.listen); document.removeEventListener("change", st.listen); document.removeEventListener("click", st.listen); st.listen = null; }
  }

  async function CertStudioInit() {
    if (typeof Certificate === "undefined" || !Certificate.studio) { $s("#cs-pick").innerHTML = '<span class="err">certificate.js is missing.</span>'; return; }
    if (typeof window.CUR !== "string") window.CUR = CFG.brand.currency;
    Certificate.studio.world(world());
    if (!st.listen) {
      st.listen = onEvent;
      document.addEventListener("input", onEvent); document.addEventListener("change", onEvent); document.addEventListener("click", onEvent);
    }
    drawSections();
    if (!st.games) {
      const r = await getj("games");
      if (!here()) return;
      st.games = r.ok ? r.games : [];
    }
    const want = window.CertStudioGame;
    window.CertStudioGame = "";
    if (want && st.games.some(g => g.id === want)) { st.game = want; st.houses = []; st.pid = ""; st.f = null; }
    drawPick();
    if (!st.lib) await loadLibrary();
    if (st.game && !st.houses.length) await loadGame(st.game);
    else if (st.f) { repaint(); drawSections(); }
    else if (!st.game) {                       // nothing chosen yet: the newest game whose books have closed
      for (const g of st.games.slice(0, 6)) { if (!here()) return; if (await loadGame(g.id)) return; }
      st.game = ""; drawPick();
      status("No finished game yet. A game's certificate can be made once its books have closed.");
    }
  }

  /* ---------------------------------------------------- loading data -- */
  async function loadLibrary() {
    st.busy = "pictures";
    const r = await getj("library?family=" + (st.fam ? 1 : 0));
    if (!here()) return;
    st.busy = "";
    if (r.ok) { st.lib = r.media; Media.setup(r.media); }
    if (st.f) { pictures(true); drawSections(); repaint(); }
  }
  async function loadGame(gid) {
    st.game = gid; st.houses = []; st.pid = ""; st.f = null; st.ok.clear();
    drawPick(); drawSections(); status("Opening the books…");
    const r = await getj("game?game=" + encodeURIComponent(gid));
    if (!here() || st.game !== gid) return;
    if (!r.ok) { status(r.error || "That game has no closing standings."); drawPick(); return false; }
    st.houses = r.houses;
    await loadCaptain(r.houses[0] && r.houses[0].id);
    return true;
  }
  async function loadCaptain(pid) {
    if (!pid) return;
    st.pid = pid; st.f = null; st.ok.clear();
    drawPick(); status("Reading the Captain's voyage…");
    const r = await getj("facts?game=" + encodeURIComponent(st.game) + "&pid=" + encodeURIComponent(pid) + "&family=" + (st.fam ? 1 : 0));
    if (!here() || st.pid !== pid) return;
    if (!r.ok) { status(r.error || "That Captain could not be read."); return; }
    st.f = r;
    st.who = (r.women[0] || (r.others || [])[0] || {}).who || "gamemaster";
    st.sel = { bg: null, mayor: null, persona: null };
    pictures(false);
    drawPick(); drawSections(); repaint();
  }

  /* Every picture that can fill each place; keeps the current choice while it is still on offer. */
  function pictures(keep) {
    if (!st.f || !st.lib) return;
    st.pics = Certificate.studio.pictures(st.f, st.who);
    [["bg", "bg"], ["mayor", "mayor"], ["persona", "persona"]].forEach(([k]) => {
      const list = st.pics[k];
      const cur = st.sel[k];
      st.sel[k] = (keep && cur && list.find(i => (i.id || i.u) === (cur.id || cur.u))) || list[0] || null;
    });
  }

  /* ----------------------------------------------------------- drawing -- */
  function status(text) {
    const s = $s("#cs-status");
    if (s) { s.textContent = text || ""; s.hidden = !text; }
  }
  function drawPick() {
    const box = $s("#cs-pick");
    if (!box) return;
    if (!st.games) { box.innerHTML = '<span class="muted">Opening the books…</span>'; return; }
    if (!st.games.length) { box.innerHTML = '<span class="muted">No games have been recorded yet.</span>'; return; }
    box.innerHTML = `<label class="cs-f"><span>Game</span><select id="cs-game">${st.game ? "" : '<option value="">Choose a game…</option>'}${st.games.map(g =>
        `<option value="${e(g.id)}"${g.id === st.game ? " selected" : ""}>${e(stamp(g.updated || g.started) || g.id)}${g.current ? " · latest" : ""} · ${e(g.id)}</option>`).join("")}</select></label>
      <label class="cs-f"><span>Captain</span><select id="cs-captain"${st.houses.length ? "" : " disabled"}>${st.houses.map(h =>
        `<option value="${e(h.id)}"${h.id === st.pid ? " selected" : ""}>${e(h.place ? h.place + ". " : "")}${e(h.name)} · ${e(h.firm)} · ${e(cash(h.worth))}</option>`).join("")}</select></label>
      <label class="cs-check"><input type="checkbox" id="cs-fam"${st.fam ? " checked" : ""}> Family-friendly pictures</label>`;
  }

  const tiles = (key, list) => !list.length ? '<p class="muted small">No pictures for this yet. Queue some with Queue_Certificate_Pictures.bat.</p>'
    : `<div class="cs-tiles">${list.map((i, n) => `<button type="button" class="cs-tile${st.sel[key] && (st.sel[key].id || st.sel[key].u) === (i.id || i.u) ? " on" : ""}" data-pic="${key}" data-n="${n}" title="${e(i.id || "")}"><img src="${e(i.u)}" alt="" loading="lazy"></button>`).join("")}</div>
      <div class="row"><button type="button" data-shuffle="${key}">Another picture</button></div>`;
  const num = (path, label, min, max, val, step) => `<label class="cs-f"><span>${label}</span><span class="cs-pair">
      <input type="range" data-f="${path}" min="${min}" max="${max}" step="${step || 1}" value="${val}"><input type="number" data-f="${path}" min="${min}" max="${max}" step="${step || 1}" value="${val}"></span></label>`;
  const money = (path, label, val) => `<label class="cs-f"><span>${label}</span><span class="cs-pair">
      <input type="range" data-f="${path}" data-log="1" min="0" max="900" value="${Math.round(Math.log10(Math.max(1, val)) * 100)}"><input type="number" data-f="${path}" min="0" step="1000" value="${Math.round(val)}"></span></label>`;
  const text = (path, label, val) => `<label class="cs-f"><span>${label}</span><input type="text" data-f="${path}" value="${e(val == null ? "" : val)}"></label>`;
  const pick = (path, label, opts, val) => `<label class="cs-f"><span>${label}</span><select data-f="${path}">${opts.map(([v, n]) => `<option value="${e(v)}"${String(v) === String(val) ? " selected" : ""}>${e(n)}</option>`).join("")}</select></label>`;

  function body(id) {
    const f = st.f;
    const portOpts = Object.keys(ports()).map(k => [k, ports()[k].name || k]);
    switch (id) {
      case "captain": return text("name", "Captain", f.name) + text("firm", "House", f.firm) + pick("home", "Home port", portOpts, f.home) +
        pick("years", "Voyage length (years)", YEARS.map(y => [y, y]), f.years) + text("first", "Voyage began", f.first) + text("last", "Voyage ended", f.last);
      case "backdrop": return tiles("bg", st.pics.bg);
      case "left": return tiles("mayor", st.pics.mayor);
      case "right": {
        const all = (f.women || []).map(w => [w.who, w.name || w.who]).concat((f.others || []).map(w => [w.who, (w.name || w.who) + " (not earned)"]));
        return pick("who", "Woman", all, st.who) + tiles("persona", st.pics.persona);
      }
      case "headline": {
        const c = f.career;
        return text("rank", "Rank", f.rank) + num("houses", "Houses in the game", 1, 8, f.houses) + num("place", "Finishing place", 1, Math.max(1, f.houses), Math.min(f.place, f.houses)) +
          `<label class="cs-check"><input type="checkbox" data-f="bad"${f.bad ? " checked" : ""}> Bad finish wording ("Survived the China Seas")</label>` +
          `<label class="cs-check"><input type="checkbox" data-f="careerOn"${c ? " checked" : ""}> Show the career line</label>` +
          (c ? num("career.place", "Career place", 1, Math.max(1, c.of), Math.min(c.place, c.of)) + num("career.of", "Voyages of this length", 1, 99, c.of) : "");
      }
      case "figures": {
        const s = f.best_sale;
        return money("worth", "Final net worth", f.worth) +
          `<label class="cs-check"><input type="checkbox" data-f="saleOn"${s ? " checked" : ""}> A profitable best sale</label>` +
          (s ? money("best_sale.profit", "Best sale profit", s.profit) + num("best_sale.qty", "Quantity", 1, 5000, s.qty) +
            pick("best_sale.good", "Cargo", Object.keys(goods()).map(k => [k, goods()[k].name || k]), s.good) + pick("best_sale.port", "Sold in", portOpts, s.port) : "") +
          num("battles", "Battles fought", 0, 60, f.battles) + num("won", "Battles won", 0, Math.max(f.battles, 1), Math.min(f.won, Math.max(f.battles, 1))) + num("sunk", "Enemy ships sunk", 0, 60, f.sunk);
      }
    }
    return "";
  }
  function drawSections() {
    const box = $s("#cs-sections");
    if (!box) return;
    if (!st.f) { box.innerHTML = ""; count(); return; }
    box.innerHTML = SECTIONS.map(([id, title, help]) => `<section class="card cs-sec${st.ok.has(id) ? " done" : ""}" data-sec="${id}">
      <div class="cs-head"><h2>${e(title)}</h2><label class="cs-ok"><input type="checkbox" data-ok="${id}"${st.ok.has(id) ? " checked" : ""}> Approved</label></div>
      <p class="help">${e(help)}</p>${body(id)}</section>`).join("");
    count();
  }
  function count() {
    const c = $s("#cs-count"), b = $s("#cs-save");
    if (!c) return;
    const n = st.ok.size, total = SECTIONS.length;
    c.textContent = st.f ? `${n} of ${total} sections approved` : "";
    if (b) b.disabled = !(st.f && n === total);
    document.querySelectorAll("#main .cs-sec").forEach(s => {
      s.classList.toggle("done", st.ok.has(s.dataset.sec));
      const box = s.querySelector("[data-ok]");
      if (box) box.checked = st.ok.has(s.dataset.sec);
    });
  }
  function caption() {
    const p = $s("#cs-line");
    if (!p || !st.f) return;
    const w = (st.f.women || []).find(x => x.who === st.who);
    if (!w || !w.text) { p.hidden = true; return; }
    p.innerHTML = `<b>${e(w.name || w.who)}</b><span>${e(st.fam ? w.family || w.text : w.text)}</span>`;
    p.hidden = false;
  }
  function repaint() {
    clearTimeout(st.timer);
    st.timer = setTimeout(async () => {
      const canvas = $s("#cs-canvas");
      if (!canvas || !st.f) return;
      status("");
      const done = await Certificate.studio.paint(canvas, st.f, { bg: st.sel.bg, mayor: st.sel.mayor, persona: st.sel.persona });
      if (done && here()) { status(""); caption(); }
    }, 120);
  }

  /* ----------------------------------------------------------- editing -- */
  const LOG = 10;
  function setPath(path, v) {
    const parts = path.split("."), last = parts.pop();
    let o = st.f;
    for (const k of parts) { if (!o[k]) o[k] = {}; o = o[k]; }
    o[last] = v;
  }
  function touch(section) {
    if (section) st.ok.delete(section);
    count();
    repaint();
  }
  function onEvent(ev) {
    if (!here()) return;
    const t = ev.target;
    if (!t || !t.closest || !t.closest("#main")) return;
    if (ev.type === "click") {
      const tile = t.closest("[data-pic]");
      if (tile) { const k = tile.dataset.pic; st.sel[k] = st.pics[k][+tile.dataset.n]; st.ok.delete(secOf(k)); drawSections(); repaint(); return; }
      const sh = t.closest("[data-shuffle]");
      if (sh) {
        const k = sh.dataset.shuffle, list = st.pics[k];
        if (list.length > 1) { const cur = st.sel[k]; let n; do { n = list[Math.floor(Math.random() * list.length)]; } while (cur && (n.id || n.u) === (cur.id || cur.u)); st.sel[k] = n; }
        st.ok.delete(secOf(k)); drawSections(); repaint(); return;
      }
      if (t.closest("#cs-all") && st.f) { SECTIONS.forEach(([id]) => st.ok.add(id)); count(); return; }
      if (t.closest("#cs-save")) { save(); return; }
      return;
    }
    if (t.id === "cs-game" && ev.type === "change") { if (t.value) loadGame(t.value); return; }
    if (t.id === "cs-captain" && ev.type === "change") { loadCaptain(t.value); return; }
    if (t.id === "cs-fam" && ev.type === "change") { st.fam = t.checked; st.lib = null; if (st.pid) { loadCaptain(st.pid); } loadLibrary(); return; }
    if (t.dataset && t.dataset.ok) {
      if (t.checked) st.ok.add(t.dataset.ok); else st.ok.delete(t.dataset.ok);
      count(); return;
    }
    const path = t.dataset && t.dataset.f;
    if (!path || !st.f) return;
    const sec = t.closest("[data-sec]");
    const secId = sec && sec.dataset.sec;
    if (t.type === "checkbox") {
      if (path === "bad") st.f.bad = t.checked;
      else if (path === "careerOn") st.f.career = t.checked ? { place: 1, of: Math.max(1, st.f.career && st.f.career.of || 1), years: st.f.years } : null;
      else if (path === "saleOn") st.f.best_sale = t.checked ? { good: Object.keys(goods())[0], port: st.f.home || Object.keys(ports())[0], qty: 100, profit: 50000 } : null;
      st.ok.delete(secId); drawSections(); repaint(); return;
    }
    let v = t.value;
    if (t.type === "range" && t.dataset.log) {
      v = Math.round(Math.pow(10, +v / 100));
      if (+t.value === 0) v = 0;
    } else if (t.type === "range" || t.type === "number") v = +v || 0;
    if (path === "who") {
      st.who = v; st.sel.persona = null; pictures(true); st.sel.persona = st.pics.persona[0] || null;
      st.ok.delete(secId); drawSections(); repaint(); return;
    }
    if (path === "years") v = +v;
    setPath(path, v);
    if (path === "home") {
      st.f.home_name = (ports()[v] || {}).name || v;
      st.sel.bg = st.sel.mayor = null; pictures(true); st.ok.delete("backdrop"); st.ok.delete("left");
    }
    if (path === "houses" && st.f.place > v) st.f.place = v;
    if (path === "battles" && st.f.won > v) st.f.won = v;
    if (path === "career.of" && st.f.career && st.f.career.place > v) st.f.career.place = v;
    if (path === "years" && st.f.career) st.f.career.years = v;
    // keep a slider and its number box in step, and the slider limits that depend on another value
    const same = document.querySelectorAll(`#main [data-f="${path}"]`);
    same.forEach(x => {
      if (x === t || x.type === "checkbox") return;
      if (x.type === "range" && x.dataset.log) x.value = Math.round(Math.log10(Math.max(1, v)) * 100);
      else if (x.type === "range" || x.type === "number") x.value = v;
    });
    if (["houses", "battles", "career.of", "home", "years"].includes(path)) { st.ok.delete(secId); drawSections(); repaint(); return; }
    touch(secId);
  }
  const secOf = key => ({ bg: "backdrop", mayor: "left", persona: "right" }[key]);

  /* ------------------------------------------------------------- saving -- */
  function save() {
    const canvas = $s("#cs-canvas");
    if (!canvas || !st.f || st.ok.size !== SECTIONS.length) return;
    canvas.toBlob(blob => {
      if (!blob) { hint("The picture could not be made. Try again."); return; }
      const brand = (document.querySelector("#gname") || {}).textContent || "Taipan Trader";
      const name = `${brand} - Captain ${st.f.name} - ${st.f.last || ""}`.replace(/[\\/:*?"<>|]+/g, " ").replace(/\s+/g, " ").trim();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = name + ".png"; a.rel = "noopener";
      document.body.append(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 4000);
      hint("Saved " + name + ".png to your downloads. Set it as your wallpaper from there.");
    }, "image/png");
  }
  function hint(text) {
    const h = $s("#cs-hint");
    if (h) { h.textContent = text; h.hidden = !text; }
  }

  window.SeaTraderCertStudio = { render, enter, leave };
})();
