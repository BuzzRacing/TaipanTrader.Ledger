/* SeaTrader media on the player screen and the harbor board.
   The server sends the media library (Admin > Media Library) with /api/info, already filtered:
   while the game is family-friendly, nothing tagged NSFW is in it. This file picks which picture or
   clip to show for a persona, port, ship, cargo or scene, and keeps rotating it by the library's rules:

     random   a new pick each time it comes on screen (or each spoken line, for a persona: from all
              of that persona's pictures and clips, not just the ones tagged "speaking")
     shuffle  a new random pick every N seconds, never the same twice in a row
     rotate   the next one in order every N seconds
     fixed    always the starred (primary) item

   Screens redraw often, so the current pick for each place is remembered here and survives redraws. */
"use strict";

// Rank badges made on the AI farm are square pictures of a round medallion: show them cut to a circle
// everywhere (fleet card, promotion certificate, Captain's ledger, Tally Book), so the corners never show.
// The hand-drawn badges in /assets/rank-badges/ have ribbon tails and are left as they are.
try {
  const s = document.createElement("style");
  s.textContent = 'img[src*="/media/rank/"]{border-radius:50%}';
  (document.head || document.documentElement).appendChild(s);
} catch (e) { /* no DOM */ }

const Media = (() => {
  let L = { items: {}, rules: { defaults: {}, subjects: {} }, options: {}, fallback: {}, family: false };
  const st = {};            // slot key -> {id, at, seen}
  const GONE_MS = 2500;     // off screen this long = "appears again" for random mode
  // "Images only" (Options > This screen, 20 Nov 2026): this screen never plays a clip, anywhere. Every pick below
  // (and every list handed to a screen) leaves the clips out, so stills show wherever a clip would have played.
  const KEY_IMG = "seatrader_images_only";
  let imagesOnly = false;
  try { imagesOnly = localStorage.getItem(KEY_IMG) === "1"; } catch (e) { /* private mode */ }

  const a = s => String(s == null ? "" : s).replace(/[&<>"']/g, c =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  /* Scene pictures are made for ONE slot and nowhere else. They are wide scenes, not figures, so they never turn up
     as a portrait, a speaker picture, a fallback or an "any picture" pick. Two kinds, told apart by role and tag:
       "masthead"   tagged masthead*, reclining       -> the Dashboard masthead only (opts.scene = "masthead")
       "wallpaper"  role wallpaper or tagged
                    wallpaper / master-shot           -> the Ledger's faded page backdrop only (opts.scene = "wallpaper")
       "certificate" tagged certificate (21 Nov 2026) -> the Voyage Certificate only (opts.scene = "certificate"):
                    its port backdrops and the women composed at one side of a wide, dark frame. Checked
                    first, because those pictures also carry the wallpaper tags (an older media.js keeps
                    them off every other screen by those).
       "weather"    role weather or tagged
                    weather / weather-<kind>          -> behind the Newspaper's forecast only (opts.scene = "weather";
                                                         weather-glass.js picks the kind by its tag)
     A slot that wants one asks for it by name with opts.scene; every other request leaves all of them out,
     whatever role it asks for and however far it falls back. */
  function sceneOf(i) {
    const marks = [...(i.g || []), ...(i.r || [])].map(x => String(x).toLowerCase());
    if (marks.includes("certificate")) return "certificate";
    if (marks.some(x => x === "reclining" || x.startsWith("masthead"))) return "masthead";
    if (marks.some(x => x === "wallpaper" || x === "master-shot")) return "wallpaper";
    if (marks.some(x => x === "weather" || x.startsWith("weather-"))) return "weather";
    return "";
  }
  const sceneOk = (i, scene) => { const k = sceneOf(i); return scene ? k === scene : !k; };

  function rule(kind, subject) {
    const d = (L.rules.defaults || {})[kind] || { mode: "random", seconds: 10, video_chance: 0 };
    const s = (L.rules.subjects || {})[kind + ":" + subject] || {};
    return Object.assign({}, d, s);
  }

  /* Items for one subject (or several) in one role. An item with no roles fits any role.
     Without a match the kind's usual role is tried, then a persona's profile pictures. */
  function pool(kind, subjects, role, opts) {
    const all = [].concat(...[].concat(subjects).map(s => ((L.items[kind] || {})[s] || []))).filter(i => sceneOk(i, opts.scene));
    const fits = r => all.filter(i => !r || !i.r.length || i.r.includes(r) || (opts.scene && sceneOf(i) === opts.scene));
    let list = fits(role);
    if (!list.length && !opts.strict && !opts.scene) {
      if (role !== L.fallback[kind]) list = fits(L.fallback[kind]);
      if (!list.length && kind === "persona") list = fits("portrait");
      if (!list.length) list = all;
    }
    if (!opts.video || imagesOnly) list = list.filter(i => i.t === "image");
    return list;
  }

  function weighted(list, avoid) {
    const pickFrom = list.length > 1 && avoid ? list.filter(i => i.id !== avoid) : list;
    const total = pickFrom.reduce((n, i) => n + (i.w || 1), 0);
    let r = Math.random() * total;
    for (const i of pickFrom) { r -= i.w || 1; if (r <= 0) return i; }
    return pickFrom[pickFrom.length - 1];
  }

  /* Videos are only chosen as often as the rule's "video chance" allows. */
  function split(list, chance) {
    const vids = list.filter(i => i.t === "video"), imgs = list.filter(i => i.t !== "video");
    if (!vids.length) return imgs;
    if (!imgs.length) return vids;
    return Math.random() * 100 < chance ? vids : imgs;
  }

  function keyOf(kind, subjects, role, opts) {
    return [kind, [].concat(subjects).join("+"), role || "", opts.slot || "", opts.video ? "v" : "", opts.scene || ""].join("|");
  }

  /* The item to show now for a place on screen. opts: {video, fresh, strict, slot, mode}. */
  function choose(kind, subjects, role, opts) {
    opts = opts || {};
    const list = pool(kind, subjects, role, opts);
    if (!list.length) return null;
    const subj = [].concat(subjects)[0];
    const r = rule(kind, subj), mode = opts.mode || r.mode;
    const key = keyOf(kind, subjects, role, opts), now = Date.now();
    let s = st[key];
    const curr = s && list.find(i => i.id === s.id);
    let next = null;
    if (mode === "fixed") {
      next = list.find(i => i.p) || list.find(i => i.t === "image") || list[0];
    } else if (mode === "rotate") {
      if (!curr) next = list[0];
      else if (opts.fresh || now - s.at >= r.seconds * 1000) next = list[(list.indexOf(curr) + 1) % list.length];
    } else if (mode === "shuffle") {
      if (!curr || opts.fresh || now - s.at >= r.seconds * 1000) next = weighted(split(list, r.video_chance), curr && curr.id);
    } else {   // random
      if (!curr || opts.fresh || now - s.seen > GONE_MS) next = weighted(split(list, r.video_chance), curr && curr.id);
    }
    if (next) { s = st[key] = { id: next.id, at: now, seen: now }; return next; }
    s.seen = now;
    return curr;
  }

  function attrs(kind, subjects, role, opts) {
    return `data-mk="${a(kind)}" data-ms="${a([].concat(subjects).join("+"))}" data-mr="${a(role || "")}"` +
      (opts.video ? ' data-mv="1"' : "") + (opts.slot ? ` data-mslot="${a(opts.slot)}"` : "") +
      (opts.mode ? ` data-mmode="${a(opts.mode)}"` : "") + (opts.strict ? ' data-mstrict="1"' : "") +
      (opts.scene ? ` data-mscene="${a(opts.scene)}"` : "");
  }

  function element(item, cls, extra) {
    if (item.t === "video") {
      // A clip made from a picture shows that picture while it loads (poster, 20 Nov 2026).
      return `<video class="${a(cls)} mslot" ${extra} data-mid="${a(item.id)}" src="${a(item.u)}"${item.po ? ` poster="${a(item.po)}"` : ""} muted autoplay loop playsinline preload="auto" disablepictureinpicture></video>`;
    }
    return `<img class="${a(cls)} mslot" ${extra} data-mid="${a(item.id)}" src="${a(item.u)}" alt="">`;
  }

  /* HTML for a picture (or clip) of kind/subject in a role. Falls back to a plain picture (the
     Graphics page's), or nothing, when the library has none. */
  function html(kind, subjects, role, cls, fallbackUrl, opts) {
    opts = opts || {};
    const item = choose(kind, subjects, role, opts);
    if (!item) return fallbackUrl ? `<img class="${a(cls)}" src="${a(fallbackUrl)}" alt="">` : "";
    return element(item, cls, attrs(kind, subjects, role, opts));
  }

  function has(kind, subject, role, opts) {
    return pool(kind, subject, role, opts || {}).length > 0;
  }

  /* Swap one element on screen for another item, fading the new one in. */
  function swap(el, item) {
    if (!item || el.dataset.mid === item.id) return;
    if (item.t === "image" && el.tagName === "IMG") {
      const pre = new Image();
      pre.onload = () => {
        if (!el.isConnected) return;
        el.src = item.u;
        el.dataset.mid = item.id;
        el.classList.remove("mfade"); void el.offsetWidth; el.classList.add("mfade");
      };
      pre.src = item.u;
      return;
    }
    const keep = Array.from(el.attributes).filter(x => /^data-m(?!id)/.test(x.name)).map(x => `${x.name}="${a(x.value)}"`).join(" ");
    const cls = Array.from(el.classList).filter(c => c !== "mslot" && c !== "mfade").join(" ");
    const tmp = document.createElement("div");
    tmp.innerHTML = element(item, cls + " mfade", keep);
    el.replaceWith(tmp.firstElementChild);
  }

  function optsOf(el) {
    const d = el.dataset;
    return { video: d.mv === "1", slot: d.mslot || "", mode: d.mmode || "", strict: d.mstrict === "1", scene: d.mscene || "" };
  }

  /* Every second: mark what is on screen as seen, and move timed rotations along. */
  function tick() {
    document.querySelectorAll(".mslot[data-mk]").forEach(el => {
      const d = el.dataset, item = choose(d.mk, d.ms.split("+"), d.mr, optsOf(el));
      if (item && item.id !== d.mid) swap(el, item);
    });
  }
  setInterval(tick, 1000);
  // The same switch changed on another window of this device (the harbor board, say).
  window.addEventListener("storage", e => {
    if (e.key !== KEY_IMG) return;
    imagesOnly = e.newValue === "1";
    tick();
  });

  function find(id) {
    for (const k of Object.keys(L.items)) for (const s of Object.keys(L.items[k])) {
      const it = L.items[k][s].find(i => i.id === id);
      if (it) return it;
    }
    return null;
  }

  return {
    /* The library from /api/info. Anything on screen that is no longer allowed is swapped at once. */
    setup(m) {
      if (!m || !m.items) return;
      L = m;
      document.querySelectorAll(".mslot").forEach(el => {
        if (find(el.dataset.mid)) return;
        const d = el.dataset;
        const item = d.mk ? choose(d.mk, d.ms.split("+"), d.mr, optsOf(el)) : null;
        if (item) swap(el, item); else el.remove();
      });
    },
    html, has, choose,
    /* Every item of a kind for these subjects that fits a role (an item with no roles fits any role).
       Used for full-screen backgrounds, which rotate on their own clock. */
    items(kind, subjects, role, video, scene) {
      const out = [];
      [].concat(subjects).forEach(s => ((L.items[kind] || {})[s] || []).forEach(i => {
        if (sceneOk(i, scene || "") && (!role || !i.r.length || i.r.includes(role) || (scene && sceneOf(i) === scene)) && ((video && !imagesOnly) || i.t === "image")) out.push(i);
      }));
      return out;
    },
    /* The picture or clip for a persona reading a line: a fresh pick for every line, from every
       picture and clip that persona has in the library, whatever its roles (portrait, speaking,
       angry, idle...). Weights and the video chance still apply, and the same item is never picked
       twice in a row. A line read in a mood the library has pictures for keeps to those. */
    speaker(cid, cls, mood) {
      if (mood && has("persona", cid, mood, { video: true, strict: true })) {
        return html("persona", cid, mood, cls || "", "", { video: true, fresh: true, strict: true, slot: "speak" });
      }
      return html("persona", cid, "", cls || "", "", { video: true, fresh: true, slot: "speak" });
    },
    /* A face for a Story screen (22 Nov 2026), the same video-first rule the Captain screen uses: from a list of
       items, a clip is chosen as often as the persona's "video chance" allows (80% by default), else a still.
       cid names whose rule to follow (the Mayor of a port follows the persona rule too, though her port pictures
       are filed under "port"). opts.primary: when a still is chosen, take the starred one (else the first) instead
       of a random one, as before. "Images only" drops the clips, as everywhere. Returns an item or null. */
    pickFace(list, cid, opts) {
      opts = opts || {};
      list = (list || []).filter(i => i && (!imagesOnly || i.t === "image"));
      if (!list.length) return null;
      const side = split(list, rule("persona", cid || "").video_chance);
      if (opts.primary && side.length && side[0].t !== "video") return side.find(i => i.p) || side[0];
      return weighted(side, opts.avoid);
    },
    /* A picture or a clip as markup for a Story screen's own layout (no timed swapping): a clip plays muted and
       looping, its still shown as the poster while it loads. */
    faceMarkup(item, cls, extra) {
      if (!item) return "";
      const c = a(cls || ""), x = extra ? " " + extra : "";
      if (item.t === "video") {
        return `<video class="${c}"${x} src="${a(item.u)}"${item.po ? ` poster="${a(item.po)}"` : ""} muted autoplay loop playsinline preload="auto" disablepictureinpicture></video>`;
      }
      return `<img class="${c}"${x} src="${a(item.u)}" alt="">`;
    },
    options: () => L.options || {},
    family: () => !!L.family,
    imagesOnly: () => imagesOnly,
    /* Images only on or off for this screen. Anything on screen changes at once (the next tick); a clip
       played by a screen's own markup changes when that screen next redraws. */
    setImagesOnly(on) {
      imagesOnly = !!on;
      try { if (imagesOnly) localStorage.setItem(KEY_IMG, "1"); else localStorage.removeItem(KEY_IMG); } catch (e) { /* private mode */ }
      tick();
    },
  };
})();
