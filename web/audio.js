/* SeaTrader sound: one mixer for every screen (player screens and the harbor board).

   Four player controls: System Sounds, Music, Atmosphere, Spoken Dialogue, plus a master.
   Everything audible goes through the Web Audio API, because iPads ignore audio.volume:

     effects ------------------------------> system  --\
     music tracks -> musicBus -> musicDuck -> music  ---+--> master -> compressor -> speakers
     atmosphere ---> ambBus ----> ambDuck --> atmos. ---|
     voices (voice.js's audio element) -> dialogue -----/

   Game code never names a file. It asks for an event ("trade.buy.success") or a scene ("battle")
   and web/audio/catalog.json decides what plays. Missing files, a blocked browser or a failed
   catalog never reach the player: the game carries on silently and the counters in
   SeaAudio.diag() say what happened.

   Rules the rest of the game relies on:
   - one-shot cues are only ever fired from the reply to the player's own action (never from polled
     state), and playOnce(key, ...) makes a repeated key do nothing, so a redraw cannot replay a cue;
   - ducking and scene fades multiply the player's chosen level, they never overwrite it;
   - music and atmosphere crossfade between scenes and loop with an overlapping crossfade (compressed
     files leave a gap at a plain loop point);
   - settings are per screen, stored with seatrader_audio_* keys. */
"use strict";

const SeaAudio = (() => {
  const SELF = document.currentScript && document.currentScript.src || "";
  const CATS = ["system", "music", "atmosphere", "dialogue"];
  const DEFAULTS = {
    master: { on: true, vol: 1 },
    system: { on: true, vol: 0.8 },
    music: { on: true, vol: 0.45 },
    atmosphere: { on: true, vol: 0.3 },
    dialogue: { on: true, vol: 1 },
  };
  // Extra switches on the Sound tab: ease the music and atmosphere down while someone speaks, and Night mode
  // (a tighter limiter so cannons and thunder cannot startle anyone).
  const OPT_DEFAULTS = { duck: true, night: false };
  const KEY = "seatrader_audio_";
  const AUDIO_BASE = "/media/audio/";           // clip paths in the catalog are relative to this
  const CATALOG_URL = "/audio/catalog.json";
  const XFADE = 4;                              // seconds: overlap between two tracks of one playlist
  const SCENE_FADE = 2.5;                       // seconds: crossfade between scenes
  const DUCK_GAIN = 0.35;                       // music and atmosphere while someone speaks (about -9 dB)
  const DUCK_ATTACK = 0.25;                     // seconds
  const DUCK_RELEASE_MS = 1000;                 // hold the duck this long after the last voice, so a batch does not pump
  const MAX_VOICES = 14;                        // overlapping effects before low-priority ones are dropped
  const STALE_MS = 800;                         // an effect that took longer than this to load is no longer wanted

  const clamp = (v, lo = 0, hi = 1) => Math.min(hi, Math.max(lo, v));
  const dbToGain = db => Math.pow(10, (Number(db) || 0) / 20);
  const lsGet = k => { try { return localStorage.getItem(k); } catch (e) { return null; } };
  const lsSet = (k, v) => { try { if (v === null) localStorage.removeItem(k); else localStorage.setItem(k, v); } catch (e) { /* private browsing: not saved */ } };

  const diag = { played: 0, dropped: 0, unknown: 0, missing: 0, errors: 0, blocked: 0 };
  const warned = new Set();
  function warn(what, id) {
    const k = what + ":" + id;
    if (warned.has(k)) return;
    warned.add(k);
    try { console.warn("[audio] " + what + ": " + id); } catch (e) { /* no console */ }
  }

  /* ---------------- settings ---------------- */
  const st = {}, opts = {};
  let listeners = [];
  function loadSettings() {
    // Anyone who muted the voices before now has Dialogue off, so they do not suddenly hear music and
    // sound they never asked for. Done once per screen.
    if (lsGet(KEY + "migrated") === null) {
      if (lsGet("seatrader_mute") === "1" && lsGet(KEY + "dialogue_on") === null) lsSet(KEY + "dialogue_on", "0");
      lsSet(KEY + "migrated", "1");
    }
    for (const k of ["master", ...CATS]) {
      const d = DEFAULTS[k], on = lsGet(KEY + k + "_on"), vol = parseFloat(lsGet(KEY + k + "_vol"));
      st[k] = { on: on === null ? d.on : on === "1", vol: Number.isFinite(vol) ? clamp(vol) : d.vol };
    }
    for (const k in OPT_DEFAULTS) { const v = lsGet(KEY + "opt_" + k); opts[k] = v === null ? OPT_DEFAULTS[k] : v === "1"; }
  }
  function settings() {
    const o = {};
    for (const k in st) o[k] = { on: st[k].on, vol: st[k].vol };
    return o;
  }
  function set(cat, patch) {
    if (!st[cat] || !patch) return;
    if (typeof patch.on === "boolean") { st[cat].on = patch.on; lsSet(KEY + cat + "_on", patch.on ? "1" : "0"); }
    if (Number.isFinite(patch.vol)) { st[cat].vol = clamp(patch.vol); lsSet(KEY + cat + "_vol", String(st[cat].vol)); }
    applyLevels();
    listeners.forEach(fn => { try { fn(settings()); } catch (e) { /* a listener's problem */ } });
  }
  function setOption(k, on) {
    if (!(k in OPT_DEFAULTS)) return;
    opts[k] = !!on; lsSet(KEY + "opt_" + k, on ? "1" : "0");
    applyLevels(); applyDuck();
    listeners.forEach(fn => { try { fn(settings()); } catch (e) { /* a listener's problem */ } });
  }
  let tableChannels = new Set();
  const audible = cat => !tableChannels.has(cat) && st.master.on && st.master.vol > 0 && st[cat].on && st[cat].vol > 0;

  /* ---------------- the Web Audio graph ---------------- */
  let ctx = null, nodes = null, failed = false, catalog = null, catalogLoading = null;

  function ensure() {
    if (ctx || failed) return ctx;
    try {
      const AC = window.AudioContext || window.webkitAudioContext;
      if (!AC) { failed = true; return null; }
      ctx = new AC({ latencyHint: "interactive" });
      // Lets Web Audio play with the iPhone's silent switch on. Ignored where unsupported.
      try { if (navigator.audioSession) navigator.audioSession.type = "playback"; } catch (e) { /* ignore */ }
      build();
      ctx.onstatechange = onState;
      applyLevels();
      onState();
    } catch (e) {
      failed = true; ctx = null; diag.errors++;
      warn("no audio context", String(e && e.message || e));
    }
    return ctx;
  }
  function build() {
    const mk = () => ctx.createGain();
    nodes = { master: mk(), comp: ctx.createDynamicsCompressor() };
    // A gentle limiter so a cannon or a thunderclap cannot jump out of the mix.
    nodes.comp.threshold.value = -10; nodes.comp.knee.value = 12; nodes.comp.ratio.value = 3;
    nodes.comp.attack.value = 0.005; nodes.comp.release.value = 0.25;
    nodes.master.connect(nodes.comp); nodes.comp.connect(ctx.destination);
    for (const c of CATS) { nodes[c] = mk(); nodes[c].connect(nodes.master); }
    nodes.musicBus = mk(); nodes.musicDuck = mk(); nodes.musicBus.connect(nodes.musicDuck); nodes.musicDuck.connect(nodes.music);
    nodes.ambBus = mk(); nodes.ambDuck = mk(); nodes.ambBus.connect(nodes.ambDuck); nodes.ambDuck.connect(nodes.atmosphere);
  }
  const bus = cat => (cat === "music" ? nodes.musicBus : cat === "atmosphere" ? nodes.ambBus : nodes[cat]);
  function ramp(param, value, tc) {
    try { param.cancelScheduledValues(ctx.currentTime); param.setTargetAtTime(value, ctx.currentTime, tc || 0.05); } catch (e) { /* ignore */ }
  }
  function applyLevels() {
    if (!nodes) return;
    ramp(nodes.master.gain, st.master.on ? st.master.vol : 0);
    for (const c of CATS) ramp(nodes[c].gain, st[c].on && !tableChannels.has(c) ? st[c].vol : 0);
    // Night mode: the limiter bites much earlier, so loud moments are pulled down toward the quiet ones.
    nodes.comp.threshold.value = opts.night ? -30 : -10; nodes.comp.ratio.value = opts.night ? 10 : 3; nodes.comp.knee.value = opts.night ? 20 : 12;
    refresh();
  }

  /* ---------------- starting sound (browsers want a tap first) ---------------- */
  let pill = null, runningFns = [], wasRunning = false;
  function running() { return !!ctx && ctx.state === "running"; }
  function onState() {
    if (!pill && document.body) {
      pill = document.createElement("button");
      pill.type = "button"; pill.id = "audio-enable"; pill.hidden = true;
      pill.textContent = "🔈 Tap to enable sound";
      pill.addEventListener("click", unlock);
      document.body.appendChild(pill);
    }
    if (pill) pill.hidden = running() || !audible("music") && !audible("system") && !audible("dialogue");
    const now = running();
    if (now) resumeStreams();
    if (now && !wasRunning) runningFns.forEach(fn => { try { fn(); } catch (e) { /* a listener's problem */ } });
    wasRunning = now;
  }
  function unlock() {
    if (!ensure()) return;
    if (ctx.state !== "running") {
      const p = ctx.resume();
      if (p && p.then) p.then(onState, () => { diag.blocked++; });
    }
    onState();
  }
  for (const ev of ["pointerdown", "touchend", "click", "keydown"]) document.addEventListener(ev, () => { if (!running()) unlock(); }, true);
  document.addEventListener("visibilitychange", () => {
    // A screen nobody is looking at stops playing; coming back picks the scene up again.
    if (!ctx) return;
    if (document.hidden) { try { ctx.suspend(); } catch (e) { /* ignore */ } } else { try { ctx.resume(); } catch (e) { /* ignore */ } }
  });

  /* ---------------- the catalog ---------------- */
  function loadCatalog() {
    if (catalogLoading) return catalogLoading;
    catalogLoading = fetch(CATALOG_URL, { cache: "no-cache" })
      .then(r => (r.ok ? r.json() : Promise.reject(new Error("catalog " + r.status))))
      .then(j => { catalog = j && typeof j === "object" ? j : null; refresh(); return catalog; })
      .catch(e => { diag.errors++; warn("catalog not loaded", String(e && e.message || e)); return null; });
    return catalogLoading;
  }
  const url = f => AUDIO_BASE + String(f).replace(/^\/+/, "");

  /* ---------------- one-shot effects ---------------- */
  const buffers = new Map();       // url -> Promise<AudioBuffer|null>
  const lastAt = new Map();        // event id -> time of last play
  const lastFile = new Map();      // event id -> file last used (to avoid an immediate repeat)
  const active = new Set();        // {id, src, g, group}
  const counts = new Map();        // event id -> overlapping instances
  const fired = new Set();         // keys already played by playOnce

  function loadBuffer(u) {
    if (!buffers.has(u)) {
      buffers.set(u, fetch(u)
        .then(r => (r.ok ? r.arrayBuffer() : Promise.reject(new Error(String(r.status)))))
        .then(ab => new Promise((res, rej) => ctx.decodeAudioData(ab, res, rej)))
        .catch(e => { diag.missing++; warn("clip not available", u); return null; }));
    }
    return buffers.get(u);
  }
  function pick(id, files) {
    if (files.length === 1) return files[0];
    const last = lastFile.get(id), pool = files.filter(f => f !== last);
    return pool[Math.floor(Math.random() * pool.length)];
  }

  /* Play a catalog event. Returns true when it was started (or is loading and still wanted). */
  function play(id, opts) {
    opts = opts || {};
    const ev = catalog && catalog.events && catalog.events[id];
    if (!ev) { diag.unknown++; warn("unknown event", id); return false; }
    const cat = ev.category;
    if (!audible(cat) || !ensure() || !running()) { diag.dropped++; return false; }
    const now = Date.now();
    if (now - (lastAt.get(id) || 0) < (ev.cooldown_ms || 0)) { diag.dropped++; return false; }
    if ((counts.get(id) || 0) >= (ev.max || 3)) { diag.dropped++; return false; }
    if (active.size >= MAX_VOICES && (ev.priority || 1) < 2) { diag.dropped++; return false; }
    lastAt.set(id, now);
    const gain = dbToGain(ev.gain_db) * (opts.gain === undefined ? 1 : opts.gain);
    const files = ev.files || [];
    if (!files.length) {
      if (!ev.synth) { warn("event has no sound", id); return false; }
      synth(ev.synth, bus(cat), gain);
      counts.set(id, (counts.get(id) || 0) + 1);
      setTimeout(() => counts.set(id, Math.max(0, (counts.get(id) || 1) - 1)), 500);
      diag.played++;
      return true;
    }
    const file = pick(id, files);
    lastFile.set(id, file);
    counts.set(id, (counts.get(id) || 0) + 1);
    const done = () => counts.set(id, Math.max(0, (counts.get(id) || 1) - 1));
    loadBuffer(url(file)).then(buf => {
      if (!buf || Date.now() - now > STALE_MS || !running()) { done(); return; }
      const src = ctx.createBufferSource(), g = ctx.createGain();
      src.buffer = buf; g.gain.value = gain;
      src.connect(g); g.connect(bus(cat));
      const rec = { id, src, g, group: opts.group || ev.group || "" };
      active.add(rec);
      src.onended = () => { active.delete(rec); done(); try { g.disconnect(); } catch (e) { /* gone */ } };
      src.start();
      diag.played++;
    });
    return true;
  }
  /* A key that plays once: playOnce("sf:3:2", "battle.broadside") fires on the first call only, so a
     redraw or a repeated state update never replays it. forget(prefix) clears keys for a new battle. */
  function playOnce(key, id, opts) {
    if (fired.has(key)) return false;
    fired.add(key);
    if (fired.size > 300) fired.delete(fired.values().next().value);
    return play(id, opts);
  }
  function forget(prefix) { for (const k of Array.from(fired)) if (k.indexOf(prefix) === 0) fired.delete(k); }
  /* Cut effects of one group short (a battle beat the player skipped past). */
  function stopGroup(group, ms) {
    if (!ctx) return;
    const t = ctx.currentTime, d = (ms === undefined ? 80 : ms) / 1000;
    for (const rec of Array.from(active)) {
      if (rec.group !== group) continue;
      try { rec.g.gain.cancelScheduledValues(t); rec.g.gain.setValueAtTime(rec.g.gain.value, t); rec.g.gain.linearRampToValueAtTime(0, t + d); rec.src.stop(t + d + 0.02); } catch (e) { /* already over */ }
    }
  }

  /* Plain built-in sounds, used while an event has no recorded clip yet (and for the Sound tab's test
     buttons). They are deliberately small and dry; real clips replace them by naming files in the catalog. */
  let noiseBuf = null;
  function noise() {
    if (!noiseBuf) {
      noiseBuf = ctx.createBuffer(1, ctx.sampleRate, ctx.sampleRate);
      const d = noiseBuf.getChannelData(0);
      for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
    }
    return noiseBuf;
  }
  function synth(kind, out, gain) {
    const t = ctx.currentTime;
    const env = (g, a, d, peak) => {
      g.gain.setValueAtTime(0.0001, t);
      g.gain.exponentialRampToValueAtTime(Math.max(0.0002, peak * gain), t + a);
      g.gain.exponentialRampToValueAtTime(0.0001, t + a + d);
    };
    const tone = (freq, type, a, d, peak) => {
      const o = ctx.createOscillator(), g = ctx.createGain();
      o.type = type; o.frequency.value = freq; env(g, a, d, peak);
      o.connect(g); g.connect(out); o.start(t); o.stop(t + a + d + 0.05);
    };
    const hiss = (dur, freq, q, peak, a) => {
      const s = ctx.createBufferSource(), f = ctx.createBiquadFilter(), g = ctx.createGain();
      s.buffer = noise(); s.loop = true; f.type = "bandpass"; f.frequency.value = freq; f.Q.value = q;
      env(g, a || 0.002, dur, peak);
      s.connect(f); f.connect(g); g.connect(out); s.start(t); s.stop(t + (a || 0.002) + dur + 0.05);
    };
    switch (kind) {
      case "click": hiss(0.03, 2200, 1.2, 0.5); tone(1400, "sine", 0.002, 0.03, 0.15); break;      // a wooden tick
      case "chime": tone(880, "sine", 0.005, 0.35, 0.35); tone(1318.5, "sine", 0.005, 0.25, 0.2); break; // silver
      case "knock": tone(110, "triangle", 0.004, 0.14, 0.6); hiss(0.04, 400, 0.8, 0.25); break;    // refused
      case "bell": [523.25, 1046.5, 1568].forEach((f, i) => tone(f, "sine", 0.005, 1.4 / (i + 1), 0.3 / (i + 1))); break;
      case "wash": hiss(1.4, 900, 0.4, 0.25, 0.4); break;                                           // sea test
      default: warn("unknown built-in sound", kind);
    }
  }

  /* ---------------- music and atmosphere ---------------- */
  const CURVE_IN = Float32Array.from({ length: 64 }, (_, i) => Math.sin(i / 63 * Math.PI / 2));
  const CURVE_OUT = Float32Array.from({ length: 64 }, (_, i) => Math.cos(i / 63 * Math.PI / 2));
  function fadeIn(g, dur) {
    const p = g.gain, t = ctx.currentTime;
    try { p.cancelScheduledValues(t); p.setValueAtTime(0, t); p.setValueCurveAtTime(CURVE_IN, t, Math.max(0.05, dur)); } catch (e) { p.value = 1; }
  }
  function fadeOut(g, dur) {
    const p = g.gain, t = ctx.currentTime, cur = clamp(p.value);
    try { p.cancelScheduledValues(t); p.setValueAtTime(cur, t); p.setValueCurveAtTime(CURVE_OUT.map(v => v * cur), t, Math.max(0.05, dur)); } catch (e) { p.value = 0; }
  }
  let tokenCounter = 0;

  function makeStream(cat) {
    const s = { cat, slots: [null, null], cur: -1, list: [], key: "", last: "", gap: 0, tailing: false, gapTimer: null, timer: null };
    function slot(i) {
      if (!s.slots[i]) {
        const el = new Audio();
        el.preload = "auto"; el.loop = false;
        const src = ctx.createMediaElementSource(el), g = ctx.createGain();   // so levels are gain nodes, which iPads obey
        g.gain.value = 0; src.connect(g); g.connect(bus(cat));
        const sl = { el, g, tok: 0 };
        el.addEventListener("ended", () => { if (s.slots[s.cur] === sl && !s.tailing && s.list.length) startTrack(choose(), 0.5); });
        s.slots[i] = sl;
      }
      return s.slots[i];
    }
    function choose() {
      if (s.list.length === 1) return s.list[0];
      const pool = s.list.filter(f => f !== s.last);
      return pool[Math.floor(Math.random() * pool.length)];
    }
    function startTrack(file, fade) {
      const ni = s.cur < 0 ? 0 : 1 - s.cur, sl = slot(ni), old = s.cur >= 0 ? s.slots[s.cur] : null;
      sl.tok = ++tokenCounter;
      sl.file = file;
      sl.el.src = url(file);
      try { sl.el.currentTime = 0; } catch (e) { /* not loaded yet */ }
      fadeIn(sl.g, fade);
      const p = sl.el.play();
      if (p && p.catch) p.catch(() => { diag.blocked++; onState(); });
      if (old) {
        fadeOut(old.g, fade);
        const tok = old.tok = ++tokenCounter;
        setTimeout(() => { if (old.tok === tok) old.el.pause(); }, fade * 1000 + 150);
      }
      s.cur = ni; s.last = file; s.tailing = false;
      clearTimeout(s.gapTimer);
      if (!s.timer) s.timer = setInterval(tick, 250);
    }
    function tick() {
      if (s.cur < 0) return;
      const sl = s.slots[s.cur], d = sl.el.duration;
      if (!isFinite(d) || d <= 0 || sl.el.paused) return;
      const left = d - sl.el.currentTime;
      if (s.gap > 0) {
        // Peaceful scenes may rest between tracks: fade out at the end, wait, then start another.
        if (left <= 3.2 && !s.tailing) {
          s.tailing = true;
          fadeOut(sl.g, Math.max(0.2, Math.min(3, left)));
          s.gapTimer = setTimeout(() => { s.tailing = false; if (s.list.length) startTrack(choose(), 0.8); }, (left + s.gap) * 1000);
        }
      } else if (left <= XFADE + 0.15) {
        startTrack(choose(), Math.max(0.3, Math.min(XFADE, left)));   // overlap the tail with the next track
      }
    }
    s.to = (list, opts) => {
      list = list || [];
      s.gap = (opts && opts.gap) || 0;
      if (!list.length) { s.stop(SCENE_FADE); return; }
      const key = list.join("|");
      if (key === s.key && s.cur >= 0) return;                         // already playing this: never restart
      s.key = key; s.list = list;
      const playing = s.cur >= 0 ? s.slots[s.cur].file : "";
      if (playing && list.indexOf(playing) >= 0) return;               // the track on now belongs to the new list too
      startTrack(choose(), SCENE_FADE);
    };
    s.stop = fade => {
      s.key = ""; s.list = []; s.tailing = false;
      clearTimeout(s.gapTimer);
      if (s.cur < 0) return;
      const old = s.slots[s.cur];
      fadeOut(old.g, fade || 0.4);
      const tok = old.tok = ++tokenCounter;
      setTimeout(() => { if (old.tok === tok) old.el.pause(); }, (fade || 0.4) * 1000 + 150);
      s.cur = -1;
    };
    s.resume = () => {
      if (s.cur < 0) return;
      const sl = s.slots[s.cur];
      if (sl.el.paused) { const p = sl.el.play(); if (p && p.catch) p.catch(() => { diag.blocked++; }); }
    };
    return s;
  }
  let streamM = null, streamA = null;
  function streams() {
    if (!ensure()) return false;
    if (!streamM) { streamM = makeStream("music"); streamA = makeStream("atmosphere"); }
    return true;
  }
  function resumeStreams() { if (streamM) { streamM.resume(); streamA.resume(); } }

  /* Scenes. There is one base scene (where the game is: lobby, port, voyage) and a stack of overlays
     (battle, jail, a ceremony) that take over deliberately and hand back to what lies underneath. A scene
     part left out, or "inherit", shows what is underneath; null or [] is silence. */
  let base = "", overlays = [];
  function resolve(kind) {
    const all = catalog && catalog.scenes || {};
    for (const name of [...overlays].reverse().concat(base)) {
      const sc = all[name];
      if (!sc || sc[kind] === undefined || sc[kind] === "inherit") continue;
      return { list: (sc[kind] || []).map(String), gap: (kind === "music" ? sc.gap_s : sc.atmosphere_gap_s) || 0 };
    }
    return { list: [], gap: 0 };
  }
  function refresh() {
    if (!catalog || !ctx || failed) return;
    if (!streams()) return;
    for (const [kind, stream] of [["music", streamM], ["atmosphere", streamA]]) {
      if (!audible(kind)) { stream.stop(0.4); continue; }
      const r = resolve(kind);
      stream.to(r.list, { gap: r.gap });
    }
  }
  function scene(name) { base = name || ""; refresh(); }
  function push(name) { overlays = overlays.filter(n => n !== name); overlays.push(name); refresh(); }
  function pop(name) { overlays = overlays.filter(n => n !== name); refresh(); }

  /* ---------------- ducking ---------------- */
  const duckers = new Set();
  let duckTimer = null;
  function applyDuck() {
    if (!nodes) return;
    const target = duckers.size && opts.duck ? DUCK_GAIN : 1;
    ramp(nodes.musicDuck.gain, target, duckers.size ? DUCK_ATTACK / 3 : 0.4);
    ramp(nodes.ambDuck.gain, target, duckers.size ? DUCK_ATTACK / 3 : 0.4);
  }
  /* duck("voice", true) while someone speaks; duck("voice", false) when they are done. The release is held
     for a second so the music does not pump between two lines of one batch. */
  function duck(reason, on) {
    clearTimeout(duckTimer);
    if (on) { duckers.add(reason); applyDuck(); return; }
    duckers.delete(reason);
    if (duckers.size) return;
    duckTimer = setTimeout(applyDuck, DUCK_RELEASE_MS);
  }

  /* ---------------- voices ---------------- */
  const attached = new WeakSet();
  /* voice.js hands over its single audio element once, so voices run through the Dialogue level and the
     master like everything else. Returns false when audio is unavailable (the voice then plays normally). */
  function attachVoice(el) {
    if (!el || attached.has(el) || !ensure()) return attached.has(el);
    try {
      ctx.createMediaElementSource(el).connect(nodes.dialogue);
      attached.add(el);
      return true;
    } catch (e) { diag.errors++; warn("voice not attached", String(e && e.message || e)); return false; }
  }

  /* The Sound tab's Test buttons. Dialogue plays an already cached clip through Voice, never a new paid line. */
  function test(cat) {
    unlock();
    if (!ensure() || !running() || !audible(cat)) return;
    // Dialogue repeats the last line this screen heard (already cached, never a new paid line); with none yet, a chime.
    if (cat === "dialogue" && typeof Voice !== "undefined" && Voice.test && Voice.test()) return;
    const kinds = { system: "chime", music: "bell", atmosphere: "wash", dialogue: "chime" };
    if (kinds[cat]) synth(kinds[cat], bus(cat), 1);
  }

  function init() {
    loadSettings();
    // The stylesheet for the "Tap to enable sound" pill and the Sound tab rides along with this script, so a
    // page needs only one new script tag. It keeps the script's own ?v= stamp.
    if (SELF && document.head) {
      const link = document.createElement("link");
      link.rel = "stylesheet"; link.href = SELF.replace(/audio\.js/, "audio.css");
      document.head.appendChild(link);
      const sc = document.createElement("script");           // the Sound tab for the Captain's Options
      sc.src = SELF.replace(/audio\.js/, "audio-panel.js"); sc.defer = true;
      document.head.appendChild(sc);
    }
    ensure();
    loadCatalog();
  }
  init();
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", onState); else onState();

  return {
    followTable(channels) {
      const next = new Set(channels || []);
      if (next.size === tableChannels.size && [...next].every(c => tableChannels.has(c))) return;
      tableChannels = next; applyLevels();
      listeners.forEach(fn => fn(settings()));
    },
    settings, set,
    option: k => opts[k], setOption,
    onChange(fn) { if (typeof fn === "function") listeners.push(fn); },
    audible, running, unlock,
    onRunning(fn) { if (typeof fn === "function") runningFns.push(fn); },
    play, playOnce, forget, stopGroup,
    scene, push, pop,
    duck, attachVoice, test,
    dialogueOn: () => audible("dialogue"),
    catalog: () => catalog,
    ready: () => loadCatalog(),
    diag: () => Object.assign({}, diag, { state: ctx ? ctx.state : failed ? "unavailable" : "none", scene: overlays.length ? overlays[overlays.length - 1] : base }),
  };
})();
