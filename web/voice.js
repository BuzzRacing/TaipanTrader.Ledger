/* SeaTrader voices on the player screen and the harbor board.
   The server decides who reads each line and hands over a link to the audio
   (/voice/<clip>.mp3); this file plays the lines one after another and shows
   who is speaking. Each device can mute itself with the speaker button. */
"use strict";

const Voice = (() => {
  let cast = {}, enabled = false, muted = store("seatrader_mute") === "1";
  let queue = [], cur = null, blocked = false, onChange = () => {};
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

  function finish() {
    cur = null;
    hide();
    onChange(null);
    setTimeout(pump, 260);
  }
  function pump() {
    if (cur || muted || !enabled || !queue.length) return;
    const item = queue.shift();
    const a = new Audio(item.u);
    cur = { a, item };
    a.onended = finish;
    a.onerror = finish;
    show(item);
    onChange(item);
    if (queue[0]) fetch(queue[0].u).catch(() => {});     // have the next line ready
    a.play().then(() => { blocked = false; }).catch(() => {
      // The browser wants a tap first. Keep the line and try again on the next one.
      if (cur && cur.a === a) { cur = null; queue.unshift(item); hide(); onChange(null); blocked = true; }
    });
  }
  function unlock() { if (blocked) { blocked = false; pump(); } }
  document.addEventListener("pointerdown", unlock, true);
  document.addEventListener("keydown", unlock, true);

  muteBtn.addEventListener("click", () => {
    muted = !muted;
    store("seatrader_mute", muted ? "1" : null);
    if (muted) stop(); else pump();
    drawMute();
  });

  function stop() {
    queue = [];
    if (cur) { cur.a.pause(); cur = null; }
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
      if (cur && cur.item.group === group) { cur.a.pause(); finish(); }
    },
    current: () => (cur ? cur.item : null),
    onChange(fn) { onChange = fn; },
  };
})();
