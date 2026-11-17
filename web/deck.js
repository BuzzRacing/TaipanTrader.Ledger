/* SeaTrader player screen: the living background and the speaker stage.

   Ambient  Full-screen pictures (or muted clips) behind everything, fading slowly from one to the
            next with a gentle drift. They come from the Media Library: scenes in the "background"
            role, then the current port's "night" pictures, and the Graphics page backgrounds when the
            library has none. Admin > Look & Style sets how long each stays and how dark it is.

   Stage    The picture frame at the top of the side column. Between lines it shows the port the
            house is in; while a character reads a line it shows that character (their "while
            speaking" picture or clip, or their profile picture) with their name and the words.
            The stage is one element that is moved into place after each redraw, so a clip that is
            playing is never restarted by the screen redrawing. */
"use strict";

const Ambient = (() => {
  const root = document.createElement("div");
  root.id = "ambient";
  root.setAttribute("aria-hidden", "true");
  root.innerHTML = '<div class="amb"></div><div class="amb"></div><div class="amb-grain"></div>';
  document.body.prepend(root);
  const layers = Array.from(root.querySelectorAll(".amb"));
  const reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  let cur = 0, pool = [], key = "", shown = null, timer = null, drift = 0;

  const attr = s => String(s == null ? "" : s).replace(/[&<>"']/g, c =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  function seconds() {
    const v = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--amb-seconds"));
    return v >= 8 ? v : 40;
  }

  function pick() {
    const from = pool.length > 1 && shown ? pool.filter(i => i.id !== shown) : pool;
    const total = from.reduce((n, i) => n + (i.w || 1), 0);
    let r = Math.random() * total;
    for (const i of from) { r -= i.w || 1; if (r <= 0) return i; }
    return from[from.length - 1];
  }

  /* Loads the next picture into the hidden layer, then cross-fades to it. */
  function show(item) {
    if (!item) return;
    const next = layers[1 - cur], prev = layers[cur];
    const video = item.t === "video";
    next.innerHTML = video
      ? `<video src="${attr(item.u)}" muted autoplay loop playsinline preload="auto" disablepictureinpicture></video>`
      : `<img src="${attr(item.u)}" alt="" decoding="async">`;
    const media = next.firstElementChild;
    let done = false;
    const go = () => {
      if (done) return;
      done = true;
      drift = (drift + 1) % 4;
      next.className = "amb d" + drift;
      next.style.setProperty("--amb-dur", (seconds() + 8) + "s");
      void next.offsetWidth;
      next.classList.add("on");
      prev.classList.remove("on");
      cur = 1 - cur;
      shown = item.id;
      setTimeout(() => {
        if (!prev.classList.contains("on")) {
          const v = prev.querySelector("video");
          if (v) v.pause();
          prev.innerHTML = "";
        }
      }, 4500);
    };
    if (video) media.addEventListener("loadeddata", go, { once: true });
    else if (media.complete && media.naturalWidth) go();
    else media.addEventListener("load", go, { once: true });
    media.addEventListener("error", () => { done = true; pool = pool.filter(i => i.id !== item.id); }, { once: true });
    setTimeout(go, 6000);   // slow network: show it anyway
  }

  function schedule() {
    clearTimeout(timer);
    if (pool.length < 2 || reduced) return;
    timer = setTimeout(() => { show(pick()); schedule(); }, seconds() * 1000);
  }

  return {
    /* list: [{id, u, t, w}] — the pictures that suit what is on screen now. */
    set(list) {
      list = (list || []).filter(i => i && i.u);
      const k = list.map(i => i.id).join("|");
      if (k === key) return;
      key = k;
      pool = list;
      if (!pool.length) { layers.forEach(l => { l.classList.remove("on"); }); shown = null; return; }
      if (!pool.some(i => i.id === shown)) show(pick());
      schedule();
    },
    next() { if (pool.length) { show(pick()); schedule(); } },
  };
})();


const Stage = (() => {
  const el = document.createElement("div");
  el.id = "stage";
  el.innerHTML = `<div class="stg-layer stg-idle"></div><div class="stg-layer stg-talk"></div>
    <div class="stg-frame"></div>
    <div class="stg-plate"><b></b><span></span><p class="stg-sub"></p></div>
    <em class="stg-wave" aria-hidden="true"><s></s><s></s><s></s><s></s><s></s></em>`;
  const idleLayer = el.querySelector(".stg-idle"), talkLayer = el.querySelector(".stg-talk");
  const nameEl = el.querySelector(".stg-plate b"), roleEl = el.querySelector(".stg-plate span");
  const subEl = el.querySelector(".stg-sub");
  let idleKey = "", idleInfo = { name: "", note: "" }, talking = false, hideTimer = null, cast = {};

  function monogram(name) {
    return String(name || "?").replace(/[“”"']/g, "").split(/\s+/).filter(Boolean).slice(0, 2).map(w => w[0]).join("").toUpperCase();
  }

  function plate(name, role, sub) {
    nameEl.textContent = name || "";
    roleEl.textContent = role || "";
    subEl.textContent = sub || "";
    subEl.hidden = !sub;
  }

  function playAll(layer) {
    layer.querySelectorAll("video").forEach(v => { if (v.paused) v.play().catch(() => {}); });
  }

  return {
    el,
    /* Puts the stage into its frame on the screen (after a redraw built a new frame). */
    mount(slot) {
      if (!slot) return;
      if (el.parentNode !== slot) slot.appendChild(el);
      playAll(talking ? talkLayer : idleLayer);
    },
    setCast(c) { cast = c || {}; },
    /* What to show between lines: the port the house is in. */
    idle(port, html, name, note) {
      if (port !== idleKey) {
        idleKey = port;
        idleLayer.innerHTML = html || "";
      }
      idleInfo = { name, note };
      if (!talking) plate(name, note, "");
    },
    /* item: a voice line {c, text, m} as it starts, or null when it ends. */
    talk(item) {
      clearTimeout(hideTimer);
      if (!item) {
        // A short pause so back-to-back lines do not flash the port in between.
        hideTimer = setTimeout(() => {
          talking = false;
          el.classList.remove("talking");
          plate(idleInfo.name, idleInfo.note, "");
          playAll(idleLayer);
          setTimeout(() => { if (!talking) talkLayer.querySelectorAll("video").forEach(v => v.pause()); }, 900);
        }, 900);
        return;
      }
      const c = cast[item.c] || {};
      const lib = typeof Media !== "undefined" ? Media.speaker(item.c, "stg-img", item.m) : "";
      talkLayer.innerHTML = lib || (c.portrait ? `<img class="stg-img" src="${esc(c.portrait)}" alt="">`
                                               : `<i class="stg-mono">${esc(monogram(c.name))}</i>`);
      el.style.setProperty("--who", c.color || "var(--deck-brass)");
      plate(c.name, c.title, item.text || "");
      talking = true;
      el.classList.remove("talking");
      void el.offsetWidth;
      el.classList.add("talking");
      playAll(talkLayer);
    },
  };
})();


/* Line icons for the deck's tabs, drawn to sit on dark lacquer in brass. */
const DECK_ICONS = {
  market: '<svg viewBox="0 0 24 24"><path d="M12 3v17M7 20h10M4 7h16M6.5 7l-3 7a3.4 3.4 0 0 0 6 0zM17.5 7l-3 7a3.4 3.4 0 0 0 6 0z"/><circle cx="12" cy="4" r="1.2"/></svg>',
  port: '<svg viewBox="0 0 24 24"><circle cx="12" cy="5" r="2"/><path d="M12 7v13M8 10.5h8M4.5 13.5A7.5 7.5 0 0 0 12 20a7.5 7.5 0 0 0 7.5-6.5M4.5 13.5l-1.3 2M4.5 13.5l2 1.2M19.5 13.5l1.3 2M19.5 13.5l-2 1.2"/></svg>',
  fleet: '<svg viewBox="0 0 24 24"><path d="M11 3v13M11 4l7 9h-7M11 6l-5 7h5M3 17h18l-2.5 3.5h-13z"/></svg>',
  chart: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8.5"/><path d="M12 6.5l2 5.5-2 5.5-2-5.5zM12 2v2M12 20v2M2 12h2M20 12h2"/></svg>',
  ledger: '<svg viewBox="0 0 24 24"><path d="M5 4.5h11a3 3 0 0 1 3 3V20H8a3 3 0 0 1-3-3zM5 17a3 3 0 0 1 3-3h11M9 8h6M9 10.8h4"/></svg>',
  // a word in your ear: speech scroll with a star of counsel
  advice: '<svg viewBox="0 0 24 24"><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3h11A2.5 2.5 0 0 1 20 5.5v8a2.5 2.5 0 0 1-2.5 2.5H11l-4.5 4v-4h0A2.5 2.5 0 0 1 4 13.5z"/><path d="M12 6.2l1 2.1 2.3.3-1.7 1.6.4 2.3-2-1.1-2 1.1.4-2.3-1.7-1.6 2.3-.3z"/></svg>',
  speech_on: '<svg viewBox="0 0 24 24"><path d="M4 9.5h3.5L12 5.5v13l-4.5-4H4z"/><path d="M15.5 9a4 4 0 0 1 0 6M18 6.5a7.5 7.5 0 0 1 0 11"/></svg>',
  speech_off: '<svg viewBox="0 0 24 24"><path d="M4 9.5h3.5L12 5.5v13l-4.5-4H4z"/><path d="M16 9.5l5 5M21 9.5l-5 5"/></svg>',
  options: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M12 2.8v2.6M12 18.6v2.6M2.8 12h2.6M18.6 12h2.6M5.5 5.5l1.8 1.8M16.7 16.7l1.8 1.8M5.5 18.5l1.8-1.8M16.7 7.3l1.8-1.8"/><circle cx="12" cy="12" r="6.6"/></svg>',
  tally: '<svg viewBox="0 0 24 24"><path d="M4 20h16M6 17V11M10.5 17V6M15 17v-4M19.5 17V8"/><path d="M4 8.5l5-3.5 5 4 6-5" stroke-dasharray="1.6 2"/></svg>',
};
