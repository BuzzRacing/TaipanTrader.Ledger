"use strict";

/* Legends (legend.py, 20 Nov 2026; project doc "SeaTrader Legends Library"): big stories that break into the
   game and take no game time, told on the Sea Battle's story stage like the Jail story.

   - A LEGEND takes over the screen when it triggers (owner's decision: "it just happens"). One line at a time:
     a big picture behind, the line in large type, and whoever is speaking standing tall beside it. The
     STORYTELLER stands on the left; the Legend's own characters answer on the right, and whoever is not
     speaking steps back, as Powder and the enemy do in a fight.
   - Lines move on by themselves when they have been said (a tap moves them sooner). When the story asks its
     question the screen waits, with one big button for each road.
   - A chapter ends with THE RECKONING: what it brought, what it cost, and whether the Legend has more to say,
     on the Reckoning's own card. "Ring the bell" returns the Captain to the very month they left.
   The Captain's Log reading stays quiet while a Legend is on screen (player.js asks Legend.telling()).
   Reads S.me.legend and S.voice.legend; called from player.js render(). */
const Legend = (() => {
  let screen = null, busy = false;
  let story = null;                           // what is being told: {key, L, i, t0, timer, mode}
  let armTimer = null;

  const ARM_MS = 1200;                        // a beat before a held screen's buttons can be pressed
  const TAP_AFTER_MS = 800;                   // a tap cannot skip a line before it has had this long
  const MIN_BEAT_MS = 3200, PER_CHAR_MS = 55; // a line stays at least this long, plus reading time
  const VOICE_START_MS = 5000;                // a line that has not started by now is not coming
  const MAX_BEAT_MS = 26000, AFTER_VOICE_MS = 700;
  const TOLD_KEY = "seatrader_legend_told";
  let told = new Set();
  try { told = new Set(JSON.parse(sessionStorage.getItem(TOLD_KEY) || "[]")); } catch (e) { /* a fresh page */ }
  const remember = key => {
    told.add(key);
    try { sessionStorage.setItem(TOLD_KEY, JSON.stringify(Array.from(told).slice(-60))); } catch (e) { /* memory only */ }
  };

  const castOf = cid => (typeof VS !== "undefined" && VS && VS.cast && VS.cast[cid]) || {};
  const portName = k => (D.ports && D.ports[k] && D.ports[k].name) || k;
  const goodName = g => ((D.goods && D.goods[g] && D.goods[g].name) || g).toLowerCase();
  const tl = (key, fb, vars) => (T[key] == null ? esc(t(fb, vars)) : te(key, vars));

  /* ---- pictures ----------------------------------------------------------------------------------- */
  /* Her picture: a speaking one while she talks if she has one, else any portrait; a fresh draw per line. */
  function faceUrl(cid, seed) {
    const who = castOf(cid);
    const item = Media.choose("persona", cid, "speaking", { slot: "legend-" + cid + "-" + seed })
      || Media.choose("persona", cid, "portrait", { slot: "legend-" + cid });
    return (item && item.t === "image" && item.u) || who.portrait || "";
  }
  /* The picture behind: the chapter's own, else any Legend's, else the port by night or the open sea. */
  function sceneUrl(L) {
    const pic = i => (i && i.t === "image" && i.u) || "";
    const port = () => pic(Media.choose("port", L.port, "night", { slot: "legend-night" }))
      || pic(Media.choose("port", L.port, "banner", { slot: "legend-port" }));
    const sea = () => pic(Media.choose("scene", "voyage", "background", { slot: "legend-sea" }));
    return pic(Media.choose("scene", "legend_" + L.tale + "_" + L.chapter_id, "background", { slot: "legend-own" }))
      || pic(Media.choose("scene", "legend", "background", { slot: "legend-any" }))
      || (L.scene === "port" ? port() || sea() : sea() || port());
  }

  /* ---- the picture behind (two layers that crossfade, as the Sea Battle's) ---------------------------- */
  let pics = [], curPic = 0, picUrl = "";
  function setBg(url) {
    if (url === picUrl) return;
    picUrl = url;
    const next = pics[1 - curPic], prev = pics[curPic];
    if (!url) { prev.classList.remove("on"); return; }
    next.innerHTML = `<img src="${esc(url)}" alt="" decoding="async">`;
    const img = next.firstElementChild;
    let done = false;
    const go = () => { if (done) return; done = true; next.classList.add("on"); prev.classList.remove("on"); curPic = 1 - curPic; };
    if (img.complete && img.naturalWidth) go(); else img.addEventListener("load", go, { once: true });
    img.addEventListener("error", () => { done = true; }, { once: true });
    setTimeout(go, 1800);
  }

  /* ---- the two speakers: the storyteller on the left, the Legend's own on the right --------------------- */
  const seats = { left: "", right: "" };
  function seat(side, cid, seed) {
    const el = screen.querySelector(".lg-who." + side);
    if (!cid) { el.hidden = true; el.innerHTML = ""; seats[side] = ""; return; }
    if (seats[side] === cid) return;
    seats[side] = cid;
    const who = castOf(cid), url = faceUrl(cid, seed);
    el.style.setProperty("--who", who.color || "var(--deck-brass)");
    el.classList.toggle("nopic", !url);
    el.innerHTML = `${url ? `<div class="sf-frame"><img class="sf-face on" src="${esc(url)}" alt=""></div>` : ""}
      <div class="sf-plate"><b>${esc(who.name || "")}</b><span>${esc(who.title || "")}</span></div>`;
    el.hidden = false;
    el.classList.remove("in"); void el.offsetWidth; el.classList.add("in");
  }

  /* ---- the screen: built once, redrawn line by line ------------------------------------------------- */
  function build() {
    screen = document.createElement("div");
    screen.id = "legend-screen";
    screen.className = "lg-screen";
    screen.innerHTML = `
      <div class="sf-bg" aria-hidden="true"><div class="sf-pic"></div><div class="sf-pic"></div><div class="sf-shade"></div></div>
      <div class="lg-who left" hidden></div><div class="lg-who right" hidden></div>
      <header class="lg-top"><div class="lg-where"><small></small><b></b><em></em></div><div class="lg-ticks"></div></header>
      <div class="lg-mid"><p class="lg-name"></p><p class="lg-line" aria-live="polite"></p><div class="lg-roads" hidden></div></div>
      <footer class="lg-foot"><p class="lg-hint"></p><div class="lg-dots"></div></footer>
      <div class="sf-result lg-result" hidden></div>`;
    pics = Array.from(screen.querySelectorAll(".sf-pic"));
    curPic = 0; picUrl = ""; seats.left = seats.right = "";
    screen.addEventListener("click", e => {
      const b = e.target.closest(".lg-go");
      if (b) { if (!b.disabled) press(b); return; }
      if (e.target.closest(".sf-card")) return;
      tapOn();
    });
    document.body.appendChild(screen);
  }
  const $ = sel => screen.querySelector(sel);

  /* ---- telling ------------------------------------------------------------------------------------- */
  const keyOf = L => [S.game_id || "", L.id, L.step].join("|");
  const clipOf = i => { const v = S && S.voice && S.voice.legend; return (v && v[i]) || null; };

  function start(L) {
    if (story) { clearInterval(story.timer); if (typeof Voice !== "undefined") Voice.drop("legend"); }
    clearTimeout(armTimer);
    const key = keyOf(L);
    if (!story || story.L.id !== L.id) seat("right", "", "");      // a new chapter: its people have yet to arrive
    story = { key, L, i: 0, t0: 0, timer: null, started: false, lastEnd: 0, mode: "line", armedAt: 0 };
    drawTop(L);
    setBg(sceneUrl(L));
    // a step this page has already told (a reload) goes straight to where it waits
    if (told.has(key) || !L.beats.length) return hold();
    enter();
  }

  function drawTop(L) {
    $(".lg-where small").innerHTML = te("legend.eyebrow");
    $(".lg-where b").textContent = L.title;
    $(".lg-where em").textContent = L.chapter;
    $(".lg-ticks").innerHTML = Array.from({ length: L.of }, (_, i) =>
      `<span class="lg-tick${i < L.n - 1 ? " done" : ""}${i === L.n - 1 ? " now" : ""}"></span>`).join("");
  }

  function enter() {
    const me = story, L = me.L, b = L.beats[me.i];
    me.mode = "line";
    me.t0 = Date.now();
    me.started = false; me.lastEnd = 0;
    drawLine(b);
    const clip = clipOf(me.i);
    const voiced = !!(clip && typeof Voice !== "undefined" && Voice.enabled() && !Voice.muted());
    const tag = "legend:" + me.key + ":" + me.i;
    if (voiced) Voice.say([Object.assign({ tag, text: b.text }, clip)], { group: "legend", front: true });
    const quiet = Math.min(16000, Math.max(MIN_BEAT_MS, String(b.text || "").length * PER_CHAR_MS + 1400));
    const idx = me.i;
    me.timer = setInterval(() => {
      if (story !== me || me.i !== idx || me.mode !== "line") return clearInterval(me.timer);
      const now = Date.now() - me.t0, cur = typeof Voice !== "undefined" ? Voice.current() : null;
      const mine = !!(cur && cur.tag === tag);
      let over;
      if (!voiced) over = now >= quiet;
      else if (mine) { me.started = true; me.lastEnd = now; over = false; }
      else if (me.started) over = now - me.lastEnd >= AFTER_VOICE_MS && now >= MIN_BEAT_MS;
      else over = now >= VOICE_START_MS && now >= quiet;                 // muted, or the line never came
      if (over || now >= MAX_BEAT_MS + (voiced ? VOICE_START_MS : 0)) advance();
    }, 120);
  }

  function advance() {
    if (!story || story.mode !== "line") return;
    const me = story;
    clearInterval(me.timer);
    if (typeof Voice !== "undefined") Voice.drop("legend");
    if (me.i >= me.L.beats.length - 1) return hold();
    me.i += 1;
    enter();
  }
  function tapOn() {
    if (!story || story.mode !== "line" || Date.now() - story.t0 < TAP_AFTER_MS) return;
    advance();
  }
  document.addEventListener("keydown", e => {
    if (!story || story.mode !== "line" || !(e.key === " " || e.key === "Enter" || e.key === "ArrowRight")) return;
    if (e.target && /^(input|textarea|select|button)$/i.test(e.target.tagName)) return;
    e.preventDefault();
    tapOn();
  });

  /* One line: who is speaking steps forward, the other steps back. */
  function drawLine(b) {
    const L = story.L;
    screen.dataset.mode = "line";
    $(".lg-result").hidden = true;
    $(".lg-roads").hidden = true;
    seat("left", L.teller, story.key);
    if (b.side === "right") seat("right", b.who, story.key);
    screen.dataset.speaker = b.side;
    const who = castOf(b.who);
    const name = $(".lg-name");
    name.textContent = who.name || "";
    name.style.setProperty("--who", who.color || "var(--deck-brass)");
    const line = $(".lg-line");
    line.textContent = b.text;
    line.classList.remove("asked");
    line.classList.toggle("long", String(b.text).length > 150);
    line.classList.remove("in"); void line.offsetWidth; line.classList.add("in");
    $(".lg-hint").textContent = t("legend.hint");
    $(".lg-hint").hidden = false;
    $(".lg-dots").innerHTML = L.beats.map((_, i) => `<i class="${i < story.i ? "done" : i === story.i ? "now" : ""}"></i>`).join("");
  }

  /* The story waits: for an answer, or with the reckoning. */
  function hold() {
    const me = story, L = me.L;
    clearInterval(me.timer);
    remember(me.key);
    me.mode = L.done ? "reckon" : "roads";
    me.armedAt = Date.now();
    screen.dataset.mode = me.mode;
    $(".lg-hint").hidden = true;
    $(".lg-dots").innerHTML = "";
    seat("left", L.teller, me.key);
    screen.dataset.speaker = "left";
    if (L.done) {
      const result = $(".lg-result");
      result.innerHTML = reckonHtml(L);
      result.hidden = false;
    } else {
      $(".lg-result").hidden = true;
      $(".lg-name").textContent = castOf(L.teller).name || "";
      const last = L.beats[L.beats.length - 1];
      const line = $(".lg-line");
      line.textContent = last ? last.text : "";
      line.classList.add("asked");
      const roads = $(".lg-roads");
      roads.innerHTML = `<p class="lg-ask">${te("legend.choose")}</p>` + L.choices.map((c, i) =>
        `<button type="button" class="lg-go lg-road" data-choice="${esc(c.key)}" style="--entry:${i}" disabled>${esc(c.label)}</button>`).join("");
      roads.hidden = false;
    }
    clearTimeout(armTimer);
    armTimer = setTimeout(() => { if (story === me && screen) screen.querySelectorAll(".lg-go").forEach(b => { b.disabled = false; }); }, ARM_MS);
  }

  /* ---- the reckoning: the end of a chapter ------------------------------------------------------------ */
  const BELL = `<svg viewBox="0 0 48 52" aria-hidden="true"><path d="M24 6v4M12 38c2-4 3-9 3-15a9 9 0 0 1 18 0c0 6 1 11 3 15z"/><path d="M9 38h30M21 44a3 3 0 0 0 6 0"/></svg>`;
  function reckonHtml(L) {
    const gains = [], costs = [];
    let silver = 0, cargo = 0, standing = 0;
    (L.tally || []).forEach(x => {
      if (x.kind === "silver") {
        silver += x.amount;
        if (x.amount >= 0) gains.push(te("legend.fx.silver_up", { amount: money(x.amount) }));
        else {
          costs.push(te("legend.fx.silver_down", { amount: money(-x.amount) }));
          if (x.debt) costs.push(te("legend.fx.debt", { amount: money(x.debt) }));
        }
      } else if (x.kind === "cargo") {
        cargo += x.qty;
        gains.push(te("legend.fx.cargo_up", { qty: x.qty.toLocaleString("en-US"), good: goodName(x.good) }));
      } else if (x.kind === "lose_cargo") {
        const names = Object.keys(x.goods || {}).filter(g => x.goods[g] > 0);
        names.forEach(g => { cargo -= x.goods[g]; });
        costs.push(names.length
          ? te("legend.fx.cargo_down", { goods: names.map(g => x.goods[g].toLocaleString("en-US") + " " + goodName(g)).join(", ") })
          : te("legend.fx.cargo_none"));
      } else if (x.kind === "hull") {
        if (x.amount) costs.push(te("legend.fx.hull", { amount: x.amount.toLocaleString("en-US") }));
      } else if (x.kind === "standing") {
        standing += x.change;
        const n = Math.abs(Math.round(x.change));
        if (n) (x.change > 0 ? gains : costs).push(te(x.change > 0 ? "legend.fx.standing_up" : "legend.fx.standing_down", { port: portName(x.port), n }));
      }
    });
    const signed = (n, fmt) => (n > 0 ? "+" : n < 0 ? "−" : "") + fmt(Math.abs(n));
    const num = n => Math.round(n).toLocaleString("en-US");
    const cls = n => (n > 0 ? "up" : n < 0 ? "dn" : "");
    const tile = (label, value, c) => `<div class="${c || ""}"><small>${label}</small><b>${value}</b></div>`;
    const list = rows => (rows.length ? rows.map(r => `<li><span>${r}</span></li>`).join("") : `<li class="none">${te("legend.reck.none")}</li>`);
    const who = castOf(L.teller), url = faceUrl(L.teller, "reckon");
    const good = silver >= 0 && !costs.length, bad = !gains.length && costs.length;
    return `<figure class="sf-rwho lg-rwho${url ? "" : " nopic"}">${url ? `<img src="${esc(url)}" alt="">` : ""}
        <figcaption class="sf-rline"><header><span>${esc(who.name || "")}${who.title ? " · " + esc(who.title) : ""}</span></header>
          ${who.catchphrase ? `<p>“${esc(who.catchphrase)}”</p>` : ""}</figcaption></figure>
      <section class="sf-card lg-card ${good ? "o-good" : bad ? "o-bad" : ""}" role="dialog" aria-modal="true" aria-labelledby="lg-title">
        <header><p class="eyebrow">${te("legend.reck.eyebrow", { title: L.title })}</p>
          <div class="sf-rheading"><span class="sf-remblem" aria-hidden="true">${BELL}</span><h2 id="lg-title">${esc(L.chapter)}</h2></div>
          <p class="sf-rreason">${te("legend.reck.lead")} ${te(L.more ? "legend.reck.more" : "legend.reck.over")}</p></header>
        <div class="sf-rows">${tile(tl("legend.tile.chapter", "Chapter"), L.n + " / " + L.of, "gold")
          + tile(tl("legend.tile.silver", "Silver"), signed(silver, money), cls(silver))
          + tile(tl("legend.tile.cargo", "Cargo"), signed(cargo, num), cls(cargo))
          + tile(tl("legend.tile.standing", "Standing"), signed(standing, num), cls(standing))}</div>
        <div class="sf-cols">
          <div><h3>${te("legend.reck.gain")}</h3><ul class="sf-rcargo">${list(gains)}</ul></div>
          <div class="sf-rledger"><h3>${te("legend.reck.cost")}</h3><ul class="sf-rcargo">${list(costs)}</ul></div>
        </div>
        <footer>
          <p class="sf-net ${cls(silver)}"><span>${te("legend.reck.net")}</span><b>${signed(silver, money)}</b></p>
          <button type="button" class="primary lg-go" data-done="1" disabled>${te(L.more ? "legend.btn_done_more" : "legend.btn_done")} <span aria-hidden="true">&rarr;</span></button>
        </footer>
      </section>`;
  }

  async function press(btn) {
    if (busy) return;
    busy = true;
    screen.querySelectorAll(".lg-go").forEach(b => { b.disabled = true; });
    const ok = await act("legend", btn.dataset.done ? { done: true } : { choice: btn.dataset.choice });
    busy = false;
    if (!ok && screen) screen.querySelectorAll(".lg-go").forEach(b => { b.disabled = false; });
  }

  function teardown() {
    if (story) { clearInterval(story.timer); if (typeof Voice !== "undefined") Voice.drop("legend"); }
    clearTimeout(armTimer);
    story = null;
    if (screen) { screen.remove(); screen = null; }
    document.body.classList.remove("in-legend");
  }

  /* A Legend waits its turn: after the sea battle, the storm and the jail have had the screen. */
  function clear() {
    return !(typeof Battle !== "undefined" && Battle.busy()) && !(typeof Storm !== "undefined" && Storm.busy())
      && !(typeof Jail !== "undefined" && Jail.busy());
  }

  function sync() {
    if (typeof S === "undefined" || typeof D === "undefined" || !S || !D) return;
    const L = S.me && S.phase === "port" && S.me.legend;
    if (!L || (!screen && !clear())) { if (screen) teardown(); return; }
    if (!screen) build();
    document.body.classList.add("in-legend");
    if (!story || story.key !== keyOf(L)) start(L);
    else story.L = L;
  }

  function busyNow() { return !!screen; }
  /* True when a Legend is on the screen or about to be: it tells its own lines, so the log stays quiet. */
  function telling() { return !!screen || !!(typeof S !== "undefined" && S && S.me && S.phase === "port" && S.me.legend); }

  return { sync, busy: busyNow, telling };
})();
