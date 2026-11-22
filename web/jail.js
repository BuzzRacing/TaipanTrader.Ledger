"use strict";

/* The jail (jail.py, 19 Nov 2026), told as a story (owner's decision, 20 Nov 2026: "the Jail Story should feel
   like the Sea Battle: large-screen story telling, and at the end the overlay of costs and data").

   - An arrest is three screens, each one big picture, one big caption and a speaker, like the Sea Battle:
       1. WHO CAUGHT YOU: the Mayor, Inspector Vane or Madam Wu fills the screen over the port, her line is
          heard and the caption says what happened. (Before this the warden's card covered the screen while the
          Mayor's voice was still talking, so the Mayor was never seen.)
       2. THE IRONS: the warden of that port, her line, the cell behind her.
       3. THE SENTENCE: months and the charge on one quiet screen, with "Into the cell".
     The first two move on by themselves when the line has been said (a tap moves them sooner); the third waits.
   - Each month inside is one screen: the cell, the warden, a line of story, the month ticks and "Serve the
     month" (pacing decision of 19 Nov 2026: a tap per month). No figures: they come at the end.
   - Release is the door opening, then the OVERLAY OF COSTS AND DATA (months served, silver drunk, cargo
     spoiled, the fine and what was paid, standing eased) over the last picture, with "Walk free".
   - A big fine may be swapped for time: the plea popup (unchanged in what it offers).
   While a story is on screen the Captain's Log reading stays quiet (player.js asks Jail.telling()) because
   this file plays the lines itself, in order, from S.voice.jail (server.py _jail_story).
   - THE PERSONAS CHANGE FACE (owner's request, 22 Nov 2026: "I need to see more persona image swapping in the jail
     story"). Every speaker (the Mayor, Inspector Vane, Madam Wu, the warden) has a deck of every picture and clip she
     has in the Media Library, dealt round-robin across her moods (angry, sly, happy, speaking, idle...), the first
     mood chosen by the screen (caught = angry, the irons = sly, the door = happy). A new pick comes on every
     screen, and again every SWAP_MS while a screen is held, crossfading, never the same twice in a row.
   Reads S.me.jail and S.voice.jail; called from player.js render(). */
const Jail = (() => {
  let screen = null, dialog = null, dialogId = null, busy = false;
  let story = null;                           // the card being told: {key, beats, i, t0, timer, ...}
  let armTimer = null;

  const ARM_MS = 1500;                        // a beat before a held card's button can be pressed
  const TAP_AFTER_MS = 900;                   // a tap cannot skip a screen before it has had this long
  const MIN_BEAT_MS = 3400, PER_CHAR_MS = 40; // a caption stays at least this long, plus reading time
  const VOICE_START_MS = 5000;                // a line that has not started by now is not coming (new lines take a moment)
  const MAX_BEAT_MS = 16000, AFTER_VOICE_MS = 900;
  const TOLD_KEY = "seatrader_jail_told";
  let told = new Set();
  try { told = new Set(JSON.parse(sessionStorage.getItem(TOLD_KEY) || "[]")); } catch (e) { /* a fresh page */ }
  const remember = key => {
    told.add(key);
    try { sessionStorage.setItem(TOLD_KEY, JSON.stringify(Array.from(told).slice(-40))); } catch (e) { /* memory only */ }
  };

  const castOf = cid => (typeof VS !== "undefined" && VS && VS.cast && VS.cast[cid]) || {};
  const portName = k => (D.ports && D.ports[k] && D.ports[k].name) || k;
  const tl = (key, fb, vars) => (T[key] == null ? esc(t(fb, vars)) : te(key, vars));
  function goodsText(goods) {
    return Object.keys(goods || {}).filter(g => goods[g] > 0)
      .map(g => goods[g].toLocaleString("en-US") + " " + ((D.goods && D.goods[g] && D.goods[g].name) || g).toLowerCase())
      .join(", ");
  }
  function goodsCount(goods) {
    return Object.keys(goods || {}).reduce((n, g) => n + (goods[g] > 0 ? goods[g] : 0), 0);
  }
  const hash = s => { let h = 7; for (const c of String(s)) h = (h * 31 + c.charCodeAt(0)) >>> 0; return h; };
  /* one line of a bank (jail.month.0, .1, ...), chosen from a seed so a redraw never changes it */
  function bankLine(prefix, seed, vars) {
    const keys = Object.keys(T).filter(k => k.startsWith(prefix + ".") && T[k] != null && String(T[k]).trim()).sort();
    if (!keys.length) return "";
    return te(keys[hash(seed) % keys.length], vars);
  }
  const hasBank = prefix => Object.keys(T).some(k => k.startsWith(prefix + ".") && T[k] != null && String(T[k]).trim());

  /* ---- pictures ----------------------------------------------------------------------------------- */
  const clean = i => (i.g || []).includes("clean");
  /* Her faces (22 Nov 2026): not one photo or clip but a DECK of everything she has in the library, so the screen
     can swap between them. Pictures are grouped by mood (a picture's roles: angry, sly, happy, speaking, idle,
     portrait) and dealt round-robin across the moods the screen asks for, so two faces in a row are never the same
     mood or the same picture. The first mood is the screen's (the Mayor catches you angry, the warden shuts the
     irons sly, the door opens happy); `shift` turns the order so each month starts on a different mood.
     The Mayor of a port also deals that port's own Mayor pictures (Ports > Mayor), as on the Parlour. Clips and
     stills are dealt together; "Images only" (Options) leaves the clips out (Media.items does that). */
  const SWAP_MS = 3500;                       // a held screen changes its speaker's face this often
  const MOODS = {
    caught: ["angry", "sly", "speaking", "idle", "happy"],
    irons:  ["sly", "happy", "angry", "speaking", "idle"],
    hold:   ["speaking", "sly", "angry", "idle", "happy"],
    month:  ["idle", "sly", "happy", "angry", "speaking"],
    door:   ["happy", "sly", "speaking", "idle", "angry"],
    costs:  ["happy", "sly", "idle", "speaking", "angry"],
    plea:   ["sly", "speaking", "angry", "idle", "happy"]
  };
  const shuffle = a => { const r = a.slice(); for (let i = r.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [r[i], r[j]] = [r[j], r[i]]; } return r; };
  const hasRole = (i, r) => (i.r || []).includes(r);
  function faceDeck(cid, port, kind, shift, avoidId) {
    const roles = MOODS[kind] || MOODS.month, n = roles.length;
    const order = roles.map((_, k) => roles[(k + (shift || 0)) % n]);
    const all = Media.items("persona", cid, "", true);
    const lists = order.map(m => shuffle(all.filter(i => hasRole(i, m))));
    if (cid === "mayor" && port) lists.unshift(shuffle(Media.items("port", port, "mayor", true).filter(i => hasRole(i, "mayor"))));
    const seen = new Set(), deck = [];
    const add = i => { if (i && !seen.has(i.id)) { seen.add(i.id); deck.push(i); } };
    for (let k = 0, more = true; more; k++) {
      more = false;
      lists.forEach(l => { if (k < l.length) { more = true; add(l[k]); } });
    }
    shuffle(all.filter(i => hasRole(i, "portrait") || !(i.r || []).length)).forEach(add);
    // the clean copy of a nude photo is for family-friendly screens; leave it out only when plenty of others remain
    const bare = deck.filter(i => !clean(i));
    const out = bare.length >= 3 ? bare : deck;
    if (out.length > 1 && avoidId && out[0].id === avoidId) out.push(out.shift());
    return out;
  }
  /* One face as markup: a clip (muted, looping, its still as the poster) or a picture. */
  function faceMarkup(item, cls) {
    if (!item) return "";
    if (item.t === "video") {
      return `<video class="${cls} jl-clip" data-jlclip="${esc(item.id)}" src="${esc(item.u)}"${item.po ? ` poster="${esc(item.po)}"` : ""} muted autoplay loop playsinline preload="auto" disablepictureinpicture></video>`;
    }
    return `<img class="${cls}" src="${esc(item.u)}" alt="">`;
  }
  /* A speaker whose face is swapped on screen: {sel: where her face lives, cls, deck, i}. */
  const faceOf = (el) => el && Array.from(el.children).find(c => c.matches(".sf-face, .jl-face"));
  function showFace(f, i) {
    if (!f || !f.deck.length) return;
    f.i = ((i % f.deck.length) + f.deck.length) % f.deck.length;
    const host = document.querySelector(f.sel);
    if (!host) return;
    const old = faceOf(host);
    const html = faceMarkup(f.deck[f.i], f.cls);
    if (old) old.insertAdjacentHTML("afterend", html); else host.insertAdjacentHTML("afterbegin", html);
    const fresh = old ? old.nextElementSibling : host.firstElementChild;
    if (fresh) fresh.classList.add("jl-in");
    if (old) setTimeout(() => old.remove(), 900);
  }
  const stepFace = f => { if (f && f.deck.length > 1) showFace(f, f.i + 1); };
  let whoFace = null;                          // the speaker on the left of a story screen
  const wardFaces = {};                        // the warden on the costs overlay and the plea: "costs", "plea"
  let swapTimer = null;
  function tickFaces() {
    if (document.hidden) return;
    if (screen && screen.dataset.kind !== "costs") stepFace(whoFace);
    Object.keys(wardFaces).forEach(k => stepFace(wardFaces[k]));
  }
  function startSwap() { if (!swapTimer) swapTimer = setInterval(tickFaces, SWAP_MS); }
  function stopSwap() { if (swapTimer && !screen && !dialog) { clearInterval(swapTimer); swapTimer = null; } }
  function cellUrl(port) {
    const item = Media.choose("port", port, "jail_cell", { mode: "fixed", slot: "jail-cell", strict: true })
      || Media.choose("port", port, "night", { slot: "jail-cell-night" });
    return item ? item.u : "";
  }
  function sceneUrl(port) {
    const item = Media.choose("port", port, "night", { slot: "jail-scene-night" })
      || Media.choose("port", port, "banner", { slot: "jail-scene" });
    return (item && item.t === "image" && item.u) || cellUrl(port);
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

  /* ---- the speaker: a tall portrait on the left with her name plate, as the Sea Battle's -------------- */
  function figureHtml(cid, port, kind, shift) {
    const who = castOf(cid);
    const deck = faceDeck(cid, port, kind, shift, whoFace && whoFace.cid === cid ? (whoFace.deck[whoFace.i] || {}).id : "");
    whoFace = { cid, port, deck, i: 0, sel: ".jl-who .sf-frame", cls: "sf-face on" };
    const item = deck[0] || null;
    const face = item ? faceMarkup(item, "sf-face on jl-in")
      : who.portrait ? `<img class="sf-face on" src="${esc(who.portrait)}" alt="">` : "";
    return `<div class="sf-who jl-who${face ? "" : " nopic"}" style="--who:${esc(who.color || "var(--deck-brass)")}">${face ? `<div class="sf-frame">${face}</div>` : ""}
      <div class="sf-plate"><b>${esc(who.name || "")}</b><span>${esc(who.title || "")}</span></div></div>`;
  }

  /* Each screen shows its speaker in a new face; when the speaker is the same as the screen before (the warden
     through the irons, the sentence and the months) the picture swaps in place, so she is never the same twice. */
  function setWho(mid, cid, port, kind, shift) {
    const old = mid.querySelector(".jl-who");
    if (old && whoFace && whoFace.cid === cid && whoFace.port === port && whoFace.deck.length) {
      const cur = (whoFace.deck[whoFace.i] || {}).id;
      whoFace.deck = faceDeck(cid, port, kind, shift, cur);
      showFace(whoFace, 0);
      return;
    }
    if (old) old.remove();
    mid.insertAdjacentHTML("afterbegin", figureHtml(cid, port, kind, shift));
  }

  /* ---- the Reckoning look, for the costs overlay and the plea ----------------------------------------- */
  const KEY_ICON = `<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="8" cy="8" r="4.5"/><path d="M11.2 11.2 20 20M16.5 16.5l2-2M14 14l2-2"/></svg>`;
  const BARS = `<svg viewBox="0 0 48 52" aria-hidden="true"><path d="M8 6h32M8 46h32M6 6v40M42 6v40"/><path d="M15 6v40M24 6v40M33 6v40"/><path d="M6 24h36" opacity=".55"/><circle cx="28.5" cy="27" r="2.2"/></svg>`;
  const OPEN = `<svg viewBox="0 0 48 52" aria-hidden="true"><path d="M8 6h20M8 46h20M6 6v40M15 6v40M24 6v40"/><path d="M28 6l14 5v34l-14 1z"/><path d="M33 8v37M38 10v34" opacity=".7"/></svg>`;
  const SCALES = `<svg viewBox="0 0 48 52" aria-hidden="true"><path d="M24 6v38M14 46h20M10 12h28"/><path d="M10 12 4 28h12zM38 12l-6 16h12z"/><path d="M4 28a6 6 0 0 0 12 0M32 28a6 6 0 0 0 12 0"/></svg>`;

  function bgHtml(port) {
    const cell = cellUrl(port);
    return `<div class="jl-bg"${cell ? ` style="background-image:url('${esc(cell)}')"` : ""}></div><div class="jl-shade"></div>`;
  }
  function wardenFigure(cid, kind, reg) {
    const who = castOf(cid);
    const deck = faceDeck(cid, "", kind || "costs", 0, "");
    wardFaces[reg || "costs"] = { cid, deck, i: 0, cls: "jl-face", sel: reg === "plea" ? ".jl-dialog .jl-warden" : ".jl-screen .jl-warden" };
    const item = deck[0] || null;
    const face = item ? faceMarkup(item, "jl-face jl-in")
      : who.portrait ? `<img class="jl-face" src="${esc(who.portrait)}" alt="">` : "";
    const line = who.catchphrase ? `<figcaption class="sf-rline jl-line"><header><span class="sf-rsay">${KEY_ICON}</span>
        <span>${esc(who.name || "")}${who.title ? " · " + esc(who.title) : ""}</span></header>
        <p>“${esc(who.catchphrase)}”</p></figcaption>`
      : who.name ? `<figcaption class="sf-rline jl-line"><header><span class="sf-rsay">${KEY_ICON}</span>
        <span>${esc(who.name)}${who.title ? " · " + esc(who.title) : ""}</span></header></figcaption>` : "";
    return `<figure class="sf-rwho jl-warden${face ? "" : " nopic"}">${face}${line}</figure>`;
  }
  const tile = (label, value, cls) => `<div class="${cls || ""}"><small>${label}</small><b>${value}</b></div>`;
  const months = m => tl("jail.tile.months", m === 1 ? "{n} month" : "{n} months", { n: m });

  /* ---- the costs overlay: the end of the story -------------------------------------------------------- */
  function costsHtml(f) {
    const port = portName(f.port), s = f.months === 1 ? "" : "s";
    const lines = [];
    if (f.fine) lines.push(te("freed.fine", { fine: money(f.fine), paid: money(f.paid || 0) }));
    if (f.drunk) lines.push(te("freed.drunk", { lost: money(f.drunk) }));
    if (f.spoiled && Object.keys(f.spoiled).length) lines.push(te("freed.spoiled", { goods: esc(goodsText(f.spoiled)) }));
    if (!lines.length) lines.push(te("freed.clean"));
    const spoiled = goodsCount(f.spoiled);
    const rows = tile(tl("jail.tile.served", "Served"), months(f.months), "gold")
      + tile(tl("jail.tile.drunk", "Silver lost aboard"), f.drunk ? "−" + money(f.drunk) : money(0), f.drunk ? "dn" : "up")
      + tile(tl("jail.tile.spoiled", "Cargo spoiled"), spoiled ? spoiled.toLocaleString("en-US") : "0", spoiled ? "dn" : "up")
      + (f.fine ? tile(tl("jail.tile.paid", "Paid instead"), "−" + money(f.paid || 0), "dn")
        : tile(tl("jail.tile.standing", "Standing"), tl("jail.tile.eased", "Eased"), "up"));
    return `${wardenFigure(f.warden, "costs", "costs")}
        <section class="sf-card jl-card o-freed" role="dialog" aria-modal="true" aria-labelledby="jl-title">
          <header><p class="eyebrow">${te("freed.eyebrow", { port })}</p>
            <div class="sf-rheading"><span class="sf-remblem" aria-hidden="true">${OPEN}</span><h2 id="jl-title">${te("freed.title")}</h2></div>
            <p class="sf-rreason">${te("freed.lead", { months: f.months, s })}</p></header>
          <div class="sf-rows">${rows}</div>
          <div class="sf-cols">
            <div><h3>${tl("jail.cost.title", "What it cost you")}</h3><ul class="sf-rcargo">${lines.map(l => `<li><span>${l}</span></li>`).join("")}</ul></div>
            <div class="sf-rledger"><h3>${tl("jail.cost.stand", "Where you stand")}</h3><ul class="sf-rcargo">
              <li><span>${te("freed.standing", { port })}</span></li><li><span>${te("freed.fleet", { port })}</span></li></ul></div>
          </div>
          <footer>
            <p class="sf-net up"><span>${tl("jail.tile.served", "Served")}</span><b>${months(f.months)}</b></p>
            <button type="button" class="primary jl-go free" data-go="jail_free" disabled>${te("freed.btn")} <span aria-hidden="true">&rarr;</span></button>
          </footer>
        </section>`;
  }

  /* ---- the screen: built once, redrawn beat by beat --------------------------------------------------- */
  function build() {
    screen = document.createElement("div");
    screen.id = "jail-screen";
    screen.className = "jl-screen";
    screen.innerHTML = `
      <div class="sf-bg" aria-hidden="true"><div class="sf-pic"></div><div class="sf-pic"></div><div class="sf-shade"></div></div>
      <header class="jl-top"><div class="jl-where"><small></small><b></b></div><div class="jl-ticks"></div><span></span></header>
      <div class="sf-mid jl-mid"><p class="sf-cap" aria-live="polite"></p><p class="jl-say"></p><p class="jl-sub"></p></div>
      <footer class="jl-foot"><p class="jl-hint"></p><div class="jl-act"></div></footer>
      <div class="sf-result jl-result" hidden></div>`;
    pics = Array.from(screen.querySelectorAll(".sf-pic"));
    curPic = 0; picUrl = ""; whoFace = null; delete wardFaces.costs;
    screen.addEventListener("click", e => {
      const b = e.target.closest(".jl-go");
      if (b) { if (!b.disabled) press(b); return; }
      if (e.target.closest(".sf-rline")) return;
      tapOn();
    });
    document.body.appendChild(screen);
    startSwap();
  }
  const $ = sel => screen.querySelector(sel);

  /* ---- the beats of a card ---------------------------------------------------------------------------- */
  function sayOf(name) {
    const v = (typeof S !== "undefined" && S && S.voice && S.voice.jail) || null;
    return (v && v[name]) || null;
  }
  const monthsText = (n, port) => te("jail.hold.lead", { months: n, s: n === 1 ? "" : "s", port });

  function cardKey(j) {
    return j.fresh ? ["A", S.turn, j.port, j.since].join("|") : ["M", j.port, j.since, j.served || 0, j.months].join("|");
  }

  function beatsForJail(j, key) {
    const port = j.port, name = portName(port), s = j.months === 1 ? "" : "s";
    const sentence = { months: j.months, served: j.served || 0 };
    const base = { port, warden: j.warden, ticks: sentence };
    const beats = [];
    const introKey = "I|" + j.port + "|" + j.since;
    if (j.fresh) {
      // 1. who caught you
      if (hasBank("jail.caught." + j.charge)) {
        const said = sayOf("caught");
        const by = (said && said.clip && said.clip.c) || j.by || "mayor";
        beats.push(Object.assign({}, base, {
          kind: "caught", who: by, bg: sceneUrl(port), eyebrow: te("jail.caught.eyebrow", { port: name }), title: "",
          cap: bankLine("jail.caught." + j.charge, key, { port: name }), say: said, ticks: null }));
      }
      // 2. the irons
      beats.push(Object.assign({}, base, {
        kind: "irons", who: j.warden, bg: cellUrl(port), eyebrow: te("jail.eyebrow", { port: name }), title: te("jail.arrested"),
        cap: bankLine("jail.irons", key, { port: name, months: j.months, s }), say: sayOf("warden") }));
      // 3. the sentence
      beats.push(Object.assign({}, base, {
        kind: "hold", who: j.warden, bg: cellUrl(port), eyebrow: te("jail.eyebrow", { port: name }), title: te("jail.arrested"),
        cap: monthsText(j.months, name), sub: (j.charges || [j.charge]).map(c => te("jail.charge." + c)).join(" · "),
        button: "jail_serve", label: te("jail.btn_into"), last: true }));
      remember(introKey);
      return beats;
    }
    const n = Math.min(j.months, (j.served || 0) + 1);
    if ((j.served || 0) === 0 && !told.has(introKey)) {
      // a sentence taken in place of a fine: no arrest, but the door still shuts first
      beats.push(Object.assign({}, base, {
        kind: "irons", who: j.warden, bg: cellUrl(port), eyebrow: te("jail.eyebrow", { port: name }), title: te("jail.arrested"),
        cap: bankLine("jail.irons", key, { port: name, months: j.months, s }), say: sayOf("warden") }));
      remember(introKey);
    }
    const lastMonth = j.left <= 1;
    beats.push(Object.assign({}, base, {
      kind: "month", who: j.warden, bg: cellUrl(port), eyebrow: te("jail.eyebrow", { port: name }),
      title: te("jail.month_of", { n, months: j.months }),
      cap: bankLine(lastMonth ? "jail.month_last" : "jail.month", key, { port: name }),
      button: "jail_serve", label: lastMonth ? te("jail.btn_last") : te("jail.btn_serve"), last: true }));
    return beats;
  }

  function beatsForFreed(f, key) {
    const name = portName(f.port);
    return [
      { kind: "door", who: f.warden, port: f.port, bg: cellUrl(f.port), eyebrow: te("freed.eyebrow", { port: name }),
        title: te("freed.title"), cap: bankLine("jail.free", key, { port: name }), say: sayOf("free"), ticks: null },
      { kind: "costs", who: f.warden, port: f.port, bg: cellUrl(f.port), freed: f, button: "jail_free", last: true }
    ];
  }

  /* ---- playing a card --------------------------------------------------------------------------------- */
  function startCard(key, j, f) {
    if (story) { clearInterval(story.timer); Voice.drop("jail"); }
    clearTimeout(armTimer);
    const beats = j ? beatsForJail(j, key) : beatsForFreed(f, key);
    story = { key, beats, i: 0, t0: 0, timer: null, started: false, lastEnd: 0, armedAt: 0 };
    // a card this page has already told (a reload) goes straight to its last screen
    if (told.has("C|" + key)) story.i = beats.length - 1;
    enter();
  }

  /* Sounds (web/audio.js plays them): the door and the irons when the sentence begins, the lock and the door
     when she walks out. Keyed by card and beat so a redraw never replays one; a late cue is dropped if the
     story has moved on. */
  function sfx(me, b) {
    const A = typeof SeaAudio !== "undefined" ? SeaAudio : null;
    if (!A) return;
    const i = me.i, key = "jl:" + me.key + ":" + i;
    const now = id => A.playOnce(key + ":" + id, id);
    const later = (ms, id) => setTimeout(() => { if (story === me && me.i === i) A.playOnce(key + ":" + id + ms, id); }, ms);
    if (b.kind === "irons") { now("jail.door"); later(650, "jail.irons"); }
    else if (b.kind === "door") { now("jail.unlock"); later(700, "jail.door"); }
  }

  function enter() {
    const me = story, b = me.beats[me.i];
    me.t0 = Date.now();
    me.started = false; me.lastEnd = 0;
    me.armedAt = b.last ? Date.now() : 0;
    drawBeat(b);
    sfx(me, b);
    if (b.last) {
      told.add("C|" + me.key);
      try { sessionStorage.setItem(TOLD_KEY, JSON.stringify(Array.from(told).slice(-40))); } catch (e) { /* memory only */ }
      clearTimeout(armTimer);
      armTimer = setTimeout(() => { if (story === me) refreshFoot(); }, ARM_MS + 50);
      return;
    }
    // the line this screen waits for, the way the Sea Battle's pictures do: until it has been said
    const voiced = !!(b.say && b.say.clip && typeof Voice !== "undefined" && Voice.enabled() && !Voice.muted());
    const tag = "jail:" + me.key + ":" + me.i;
    if (voiced) Voice.say([Object.assign({ tag, text: b.say.text }, b.say.clip)], { group: "jail", front: true });
    const quiet = Math.min(9000, Math.max(MIN_BEAT_MS, String(b.cap || "").length * PER_CHAR_MS + 1600));
    const idx = me.i;
    me.timer = setInterval(() => {
      if (story !== me || me.i !== idx) return clearInterval(me.timer);
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
    if (!story) return;
    const me = story;
    if (me.i >= me.beats.length - 1) return;
    clearInterval(me.timer);
    if (typeof Voice !== "undefined") Voice.drop("jail");
    me.i += 1;
    enter();
  }
  function tapOn() {
    if (!story) return;
    const b = story.beats[story.i];
    if (!b || b.last || Date.now() - story.t0 < TAP_AFTER_MS) return;
    advance();
  }
  document.addEventListener("keydown", e => {
    if (!story || dialog || !(e.key === " " || e.key === "Enter" || e.key === "ArrowRight")) return;
    if (e.target && /^(input|textarea|select|button)$/i.test(e.target.tagName)) return;
    const b = story.beats[story.i];
    if (b && !b.last) { e.preventDefault(); tapOn(); }
  });

  /* ---- drawing one beat ------------------------------------------------------------------------------- */
  function drawBeat(b) {
    const costs = b.kind === "costs";
    screen.dataset.kind = b.kind;
    screen.classList.toggle("costs", costs);
    const result = $(".jl-result");
    if (costs) {
      setBg(b.bg);
      result.innerHTML = costsHtml(b.freed);
      result.hidden = false;
      refreshFoot();
      return;
    }
    result.hidden = true;
    result.innerHTML = "";
    setBg(b.bg);
    $(".jl-where small").innerHTML = b.eyebrow || "";
    $(".jl-where b").innerHTML = b.title || "";
    $(".jl-ticks").innerHTML = b.ticks
      ? Array.from({ length: b.ticks.months }, (_, i) =>
        `<span class="jl-tick${i < b.ticks.served ? " done" : ""}${b.kind === "month" && i === b.ticks.served ? " now" : ""}"></span>`).join("")
      : "";
    const mid = $(".jl-mid");
    setWho(mid, b.who, b.port, b.kind, b.kind === "month" && b.ticks ? b.ticks.served : 0);
    const cap = $(".sf-cap");
    cap.innerHTML = b.cap || "";
    cap.classList.remove("in"); void cap.offsetWidth; cap.classList.add("in");
    const say = $(".jl-say");
    const who = castOf(b.who);
    say.innerHTML = b.say && b.say.text ? `<b>${esc(who.name || "")}</b> “${esc(b.say.text)}”` : "";
    say.hidden = !say.innerHTML;
    const sub = $(".jl-sub");
    sub.innerHTML = b.sub || "";
    sub.hidden = !b.sub;
    refreshFoot();
  }

  /* The footer: a hint while the story moves on by itself, the button when it waits for the Captain. */
  function refreshFoot() {
    if (!screen || !story) return;
    const b = story.beats[story.i];
    const jv = S && S.me && S.me.jail;
    const j = jv && jv.jail;
    const hint = $(".jl-hint"), act = $(".jl-act");
    if (!b.last) {
      hint.textContent = t("jail.story.next");
      hint.hidden = false;
      act.innerHTML = "";
      return;
    }
    hint.hidden = true;
    const armed = Date.now() - story.armedAt >= ARM_MS;
    if (j && j.ready) {
      const names = (S.waiting || []).filter(n => n !== S.me.name);
      act.innerHTML = `<p class="jl-waiting">${names.length ? te("jail.waiting", { names: esc(names.join(", ")) }) : te("jail.served")}</p>`;
      return;
    }
    if (b.kind === "costs") {
      const btn = screen.querySelector(".jl-go.free");
      if (btn) btn.disabled = !armed;
      return;
    }
    const cur = act.querySelector(".jl-go");
    if (cur && cur.dataset.go === b.button && cur.dataset.label === b.label) { cur.disabled = !armed; return; }
    act.innerHTML = `<button type="button" class="primary jl-go${b.button === "jail_free" ? " free" : ""}" data-go="${b.button}" data-label="${esc(b.label)}"${armed ? "" : " disabled"}>${b.label} <span aria-hidden="true">&rarr;</span></button>`;
  }

  async function press(btn) {
    if (busy) return;
    busy = true;
    btn.disabled = true;
    const ok = await act(btn.dataset.go, {});
    busy = false;
    if (!ok && btn.isConnected) btn.disabled = false;
  }

  function teardown() {
    if (story) { clearInterval(story.timer); if (typeof Voice !== "undefined") Voice.drop("jail"); }
    clearTimeout(armTimer);
    story = null;
    if (screen) { screen.remove(); screen = null; }
    whoFace = null; delete wardFaces.costs;
    stopSwap();
  }

  function syncScreen() {
    const jv = S && S.me && S.phase !== "lobby" && S.me.jail;
    const j = jv && jv.jail;
    const f = !j && jv && S.phase === "port" && jv.freed;       // the release story, until "Walk free"
    document.body.classList.toggle("in-jail", !!(j || f));
    if (!j && !f) { if (screen) teardown(); return; }
    if (!screen) build();
    const key = j ? cardKey(j) : ["F", f.turn, f.port].join("|");
    if (!story || story.key !== key) startCard(key, j, f);
    else refreshFoot();
  }

  /* ---- the plea deal (what it offers is unchanged) ---------------------------------------------------- */
  function closePlea() {
    if (dialog) { try { dialog.close(); } catch (e) { /* closed */ } dialog.remove(); }
    dialog = dialogId = null;
    delete wardFaces.plea;
    stopSwap();
  }

  function drawPlea(pl) {
    const port = portName(pl.port);
    const opt = o => {
      if (!o.months) {
        return `<button type="button" class="jl-opt pay" data-m="0"><small>${te("plea.share", { pct: 100 })}</small>
          <b>${te("plea.pay_all")}</b><span class="jl-amt">${money(o.pay)}</span></button>`;
      }
      return `<button type="button" class="jl-opt cell" data-m="${o.months}"><small>${te("plea.share", { pct: Math.round(o.share * 100) })}</small>
        <b>${te("plea.months", { months: o.months, s: o.months === 1 ? "" : "s" })}</b>
        <span class="jl-amt">${te("plea.pay", { pay: money(o.pay) })}</span></button>`;
    };
    return `${bgHtml(pl.port)}
      <div class="sf-result jl-result">
        ${wardenFigure(pl.warden, "plea", "plea")}
        <section class="sf-card jl-card o-plea" aria-labelledby="jl-plea-title">
          <header><p class="eyebrow">${te("plea.eyebrow", { port })}</p>
            <div class="sf-rheading"><span class="sf-remblem" aria-hidden="true">${SCALES}</span><h2 id="jl-plea-title">${te("plea.title", { fine: money(pl.amount) })}</h2></div>
            <p class="sf-rreason">${te("plea.why." + pl.charge)}</p>
            <p class="jl-lead">“${te("plea.lead")}”</p></header>
          <div class="jl-opts">${pl.opts.map(opt).join("")}</div>
          <p class="sf-note">${te("plea.note")}</p>
          <footer><p class="sf-net dn"><span>${tl("jail.tile.fine", "The fine")}</span><b>${money(pl.amount)}</b></p>
            <p class="jl-auto">${te("plea.auto")}</p></footer>
        </section>
      </div>`;
  }

  function syncPlea() {
    const pl = S && S.me && S.phase === "port" && S.me.jail && S.me.jail.plea;
    if (!pl) { closePlea(); return; }
    if (dialog && dialogId === pl.id) return;
    closePlea();
    dialogId = pl.id;
    dialog = document.createElement("dialog");
    dialog.className = "jl-dialog";
    dialog.innerHTML = drawPlea(pl);
    dialog.addEventListener("cancel", e => e.preventDefault());     // it must be answered
    dialog.querySelectorAll(".jl-opt").forEach(b => b.addEventListener("click", async () => {
      if (busy) return;
      busy = true;
      dialog.querySelectorAll(".jl-opt").forEach(x => { x.disabled = true; });
      const ok = await act("plea", { months: Number(b.dataset.m) });
      busy = false;
      if (!ok && dialog) dialog.querySelectorAll(".jl-opt").forEach(x => { x.disabled = false; });
    }));
    document.body.appendChild(dialog);
    startSwap();
    try { dialog.showModal(); } catch (e) { dialog.setAttribute("open", ""); }
  }

  function sync() {
    if (typeof S === "undefined" || typeof D === "undefined" || !S || !D) return;
    syncScreen();
    syncPlea();
  }

  function busyNow() { return !!(screen || dialog); }
  /* True while a jail story is on screen: it reads its own lines, so the Captain's Log stays quiet. */
  function telling() { return !!screen; }

  return { sync, busy: busyNow, telling };
})();
