/* SeaTrader voices on the player screen and the harbor board.
   The server decides who reads each line and hands over a link to the audio
   (/voice/<clip>.mp3); this file plays the lines one after another and shows
   who is speaking. Each device can mute itself with the speaker button.

   Lines never overlap:
   - each screen plays through ONE audio channel, one line at a time, in the order the lines arrived;
   - before each line the screen asks the server for the turn (/api/voice/floor), so the player
     window, the harbor board and any other screen on the same computer wait for each other;
     a screen keeps the turn until its batch is read (the whole month's log, all fresh headlines);
   - a news headline another screen on this device has just read is skipped, not read twice;
   - a line that stalls or never reports its end is given up after a while, so the queue keeps moving. */
"use strict";

const Voice = (() => {
  const GAP_MS = 260;           // pause between lines
  const RENEW_MS = 2000;        // "still talking" to the server while a line plays
  const STALL_MS = 15000;       // no progress for this long: give the line up
  const SID = "s" + Math.random().toString(36).slice(2, 10) + Date.now().toString(36);

  let cast = {}, enabled = false, muted = store("seatrader_mute") === "1";
  let queue = [], cur = null, asking = false, blocked = false, onChange = () => {};
  let seq = 0, floorOk = true, retryTimer = null, holding = false;

  // One audio element for the whole page: two lines cannot play through it at once, and
  // tablets that need a tap before sound only need it once for this element.
  const player = new Audio();
  player.preload = "auto";

  const box = document.createElement("div");
  box.id = "voicebox";
  box.innerHTML = `<div id="speaking" hidden></div><button type="button" id="mute" title="Voices on or off"></button>`;
  document.body.appendChild(box);
  const speaking = box.querySelector("#speaking"), muteBtn = box.querySelector("#mute");

  function monogram(name) {
    return String(name || "?").replace(/[“”"']/g, "").split(/\s+/).filter(Boolean).slice(0, 2).map(w => w[0]).join("").toUpperCase();
  }
  function drawMute() {
    muteBtn.hidden = !enabled;
    muteBtn.textContent = muted ? "🔇" : "🔊";
    muteBtn.classList.toggle("off", muted);
    muteBtn.setAttribute("aria-label", muted ? "Voices off" : "Voices on");
  }
  function show(item) {
    const c = cast[item.c];
    if (!c) { speaking.hidden = true; return; }
    speaking.style.setProperty("--who", c.color || "#b08a2e");
    // A picture (or clip) from the Media Library, picked fresh for every line; else the profile picture.
    const lib = typeof Media !== "undefined" ? Media.speaker(item.c, "sp-art", item.m) : "";
    const art = lib || (c.portrait ? `<img class="sp-art" src="${esc(c.portrait)}" alt="">` : `<i>${esc(monogram(c.name))}</i>`);
    const card = typeof Media !== "undefined" && Media.options().speaker_card !== "badge" && (lib || c.portrait);
    speaking.classList.toggle("card", !!card);
    speaking.innerHTML = `${art}
      <div><b>${esc(c.name)}</b><span>${esc(c.title || "")}</span></div><em><s></s><s></s><s></s><s></s></em>`;
    speaking.hidden = false;
  }
  function hide() {
    speaking.hidden = true;
    const v = speaking.querySelector("video");
    if (v) v.pause();
  }

  /* ---- the turn, shared with the other screens through the server ---- */
  async function floor(op, item) {
    if (!floorOk) return { granted: true };
    const body = { id: SID, op };
    if (item) { body.clip = clipId(item.u); body.once = item.group === "news"; }
    try {
      const r = await fetch("/api/voice/floor", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      if (r.status === 404) { floorOk = false; return { granted: true }; }   // an older server: just this screen's queue
      const j = await r.json();
      return j && typeof j.granted === "boolean" ? j : { granted: true };
    } catch (e) {
      return { granted: true };          // server unreachable: never hold the lines back
    }
  }
  function freeFloor() { holding = false; if (floorOk) floor("free"); }
  function clipId(u) { const m = /\/voice\/([^/?#]+)\.mp3/.exec(String(u || "")); return m ? m[1] : String(u || ""); }
  window.addEventListener("pagehide", () => {
    if (!floorOk || !navigator.sendBeacon) return;
    try { navigator.sendBeacon("/api/voice/floor", JSON.stringify({ id: SID, op: "free" })); } catch (e) { /* closing anyway */ }
  });

  /* ---- playing ---- */
  function release(n) {
    if (!cur || cur.n !== n) return false;       // a late event from a line that is already over
    clearInterval(cur.renew);
    clearInterval(cur.watch);
    cur = null;
    return true;
  }
  function finish(n) {
    if (!release(n)) return;
    if (!queue.length) freeFloor();     // more lines waiting: keep the turn so this screen finishes its batch
    hide();
    onChange(null);
    setTimeout(pump, GAP_MS);
  }

  function pump() {
    clearTimeout(retryTimer);
    if (!cur && !asking && holding && (!queue.length || muted || !enabled)) freeFloor();
    if (cur || asking || muted || !enabled || !queue.length) return;
    const item = queue[0];
    asking = true;
    floor("take", item).then(r => {
      asking = false;
      if (r.granted) holding = true;
      if (queue[0] !== item || muted || !enabled) return pump();   // dropped or muted while we waited
      if (r.skip) { queue.shift(); return pump(); }  // another screen here just read this headline
      if (!r.granted) { retryTimer = setTimeout(pump, Math.max(150, (r.wait || 0.35) * 1000)); return; }
      start(queue.shift());
    });
  }

  function start(item) {
    const n = ++seq;
    cur = { n, item, renew: null, watch: null, pos: -1, moved: Date.now() };
    player.onended = () => finish(n);
    player.onerror = () => finish(n);
    player.src = item.u;
    show(item);
    onChange(item);
    if (queue[0]) fetch(queue[0].u).catch(() => {});     // have the next line ready
    cur.renew = setInterval(() => floor("renew"), RENEW_MS);
    cur.watch = setInterval(() => {
      if (!cur || cur.n !== n) return;
      const t = player.currentTime || 0;
      if (t !== cur.pos) { cur.pos = t; cur.moved = Date.now(); return; }
      if (!player.paused && Date.now() - cur.moved > STALL_MS) { player.pause(); finish(n); }
    }, 1000);
    const p = player.play();
    if (p && p.then) {
      p.then(() => { blocked = false; }).catch(() => {
        // The browser wants a tap first. Keep the line, give the turn back, and try again after a tap.
        if (cur && cur.n === n) {
          release(n);
          queue.unshift(item);
          freeFloor();
          hide();
          onChange(null);
          blocked = true;
        }
      });
    }
  }

  // A tiny silent sound, played on the first tap so tablets let this page play the voices later.
  let primed = false;
  const SILENT = (() => {
    const rate = 8000, len = 400, buf = new ArrayBuffer(44 + len), d = new DataView(buf);
    const w = (o, s) => { for (let i = 0; i < s.length; i++) d.setUint8(o + i, s.charCodeAt(i)); };
    w(0, "RIFF"); d.setUint32(4, 36 + len, true); w(8, "WAVE"); w(12, "fmt "); d.setUint32(16, 16, true);
    d.setUint16(20, 1, true); d.setUint16(22, 1, true); d.setUint32(24, rate, true); d.setUint32(28, rate, true);
    d.setUint16(32, 1, true); d.setUint16(34, 8, true); w(36, "data"); d.setUint32(40, len, true);
    for (let i = 0; i < len; i++) d.setUint8(44 + i, 128);
    try { return URL.createObjectURL(new Blob([buf], { type: "audio/wav" })); } catch (e) { return ""; }
  })();
  function unlock() {
    if (!primed && !cur && SILENT) {
      primed = true;
      player.src = SILENT;
      const p = player.play();
      if (p && p.catch) p.catch(() => { primed = false; });
    }
    if (blocked) { blocked = false; pump(); }
  }
  document.addEventListener("pointerdown", unlock, true);
  document.addEventListener("keydown", unlock, true);

  function setMuted(on) {
    muted = !!on;
    store("seatrader_mute", muted ? "1" : null);
    if (muted) stop(); else pump();
    drawMute();
  }
  muteBtn.addEventListener("click", () => setMuted(!muted));

  function stop() {
    queue = [];
    clearTimeout(retryTimer);
    if (cur) { player.pause(); finish(cur.n); return; }
    hide();
    onChange(null);
  }

  return {
    /* Settings from /api/info. */
    setup(v) {
      v = v || {};
      enabled = !!v.enabled;
      cast = v.cast || {};
      if (!enabled) stop();
      drawMute();
      return v;
    },
    /* items: [{c: character, u: audio link, tag}] in reading order. */
    say(items, opts) {
      if (!enabled || muted) return;
      items = (items || []).filter(x => x && x.u);
      if (!items.length) return;
      if (opts && opts.replace) queue = queue.filter(q => q.group !== opts.replace);
      if (opts && opts.group) items.forEach(x => { x.group = opts.group; });
      queue.push(...items);
      pump();
    },
    stop,
    /* Drop queued lines of one kind (for example the rest of a log the player has closed). */
    drop(group) {
      queue = queue.filter(q => q.group !== group);
      if (cur && cur.item.group === group) { player.pause(); finish(cur.n); }
    },
    current: () => (cur ? cur.item : null),
    /* The player screen's own Voices switch (in the captain's menu) uses these. */
    enabled: () => enabled,
    muted: () => muted,
    setMuted,
    onChange(fn) { onChange = fn; },
  };
})();
