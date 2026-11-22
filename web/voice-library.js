/* Crimson Ledger Admin: Voice Library.
   One page of every Inworld voice in the saved list (women by default). Under each voice sit
   the cards of the personas who speak with it, so it is plain who has which voice and which
   voices nobody has. Play a voice, mark it, note it, and assign a persona to it right there.
   The list is a saved snapshot (voicelib.py): it only changes when "Check Inworld for changes"
   is pressed, and the page then says what is new and what has gone. Assigning edits
   CFG.characters like the Cast & Voices page, so it is applied with "Save & apply". Marks,
   notes and the audition line are saved straight away. */
(function () {
  "use strict";

  const st = {
    lib: null, err: "", loading: false, checking: false, off: false,
    playing: "",            // "<voice id>|<character key or nothing>"
    audio: null, queue: false, order: [],
    f: { who: "female", lang: "", age: "", src: "", cast: "", mark: "", q: "", rejected: false },
  };
  const $m = () => document.getElementById("main");
  const e = s => esc(s);
  const C = () => CFG.characters;
  const here = () => section === "voices";
  const RATE = { star: "Shortlist", maybe: "Maybe", no: "No" };
  const RATE_ICON = { star: "★", maybe: "?", no: "✕" };

  function shown(cid) {
    const c = C()[cid] || {};
    return c.brand_link && CFG.brand[c.brand_link] ? CFG.brand[c.brand_link] : (c.name || cid);
  }
  const voices = () => (st.lib && st.lib.voices) || [];
  const row = id => voices().find(v => v.id === id);
  const markOf = id => (st.lib && st.lib.marks[id]) || { rating: "", note: "" };
  const vname = id => { const v = row(id); return v ? v.name : id; };
  const day = sec => sec ? new Date(sec * 1000).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }) : "";
  function langName(code) {
    try { return new Intl.DisplayNames(undefined, { type: "language" }).of(code) || code; } catch (err) { return code; }
  }
  const lang2 = v => String(v.lang || "").slice(0, 2).toLowerCase();

  /* Flags are drawn here as small SVGs (Windows does not show flag emoji, and the Pi may be offline).
     A language with no flag in this table simply shows its name. Arabic has no single country, so
     "ar" with no region shows Saudi Arabia unless Inworld gives a region (ar-EG and so on). */
  const FLAG_REGION = { en: "US", ko: "KR", ar: "SA" };
  const FLAGS = {
    KR: `<svg viewBox="0 0 36 24" aria-hidden="true"><rect width="36" height="24" fill="#fff"/>
      <circle cx="18" cy="12" r="6" fill="#cd2e3a"/><path d="M12 12a6 6 0 0 0 12 0a3 3 0 0 0-6 0a3 3 0 0 1-6 0z" fill="#0047a0"/>
      <g stroke="#000" stroke-width="1.1"><path d="M5.2 5.6l3-1.8M4.4 7l3-1.8M6 4.2l3-1.8" transform="translate(0 .4)"/>
      <path d="M30.8 5.6l-3-1.8M31.6 7l-3-1.8M30 4.2l-3-1.8" transform="translate(0 .4)"/>
      <path d="M5.2 18.4l3 1.8M4.4 17l3 1.8M6 19.8l3 1.8" transform="translate(0 -.4)"/>
      <path d="M30.8 18.4l-3 1.8M31.6 17l-3 1.8M30 19.8l-3 1.8" transform="translate(0 -.4)"/></g></svg>`,
    SA: `<svg viewBox="0 0 36 24" aria-hidden="true"><rect width="36" height="24" fill="#006c35"/>
      <g fill="#fff"><rect x="8" y="6.5" width="20" height="1.6" rx=".8"/><rect x="10" y="9.5" width="16" height="1.4" rx=".7"/>
      <rect x="6" y="16.6" width="24" height="1.1"/><path d="M6 18.4h19l2.4-1.2v-.1H6z"/><rect x="25" y="15.6" width="1.2" height="3"/></g></svg>`,
    US: `<svg viewBox="0 0 36 24" aria-hidden="true"><rect width="36" height="24" fill="#fff"/>
      <g fill="#b22234"><rect width="36" height="1.85"/><rect y="3.7" width="36" height="1.85"/><rect y="7.4" width="36" height="1.85"/>
      <rect y="11.1" width="36" height="1.85"/><rect y="14.8" width="36" height="1.85"/><rect y="18.5" width="36" height="1.85"/><rect y="22.2" width="36" height="1.85"/></g>
      <rect width="15" height="12.9" fill="#3c3b6e"/></svg>`,
  };
  const regionNames = () => { try { return new Intl.DisplayNames(undefined, { type: "region" }); } catch (err) { return null; } };
  function where(v) {          // { code, country, flag } for a voice, from "ko", "ko-KR", "ar-EG"…
    const parts = String(v.lang || "").replace("_", "-").split("-"), lg = parts[0].toLowerCase();
    const rg = (parts[1] || "").toUpperCase(), code = /^[A-Z]{2}$/.test(rg) ? rg : (FLAG_REGION[lg] || "");
    let country = "";
    try { country = code && regionNames() ? regionNames().of(code) : ""; } catch (err) { country = ""; }
    return { code, country, flag: FLAGS[code] || "" };
  }
  function users(id) { return Object.keys(C()).filter(cid => (C()[cid].voice_id || "").trim() === id); }
  function isNew(v) {
    const first = Math.min(...voices().map(x => x.first_seen || 0));
    return v.first_seen > first && Date.now() / 1000 - v.first_seen < 14 * 86400;
  }

  /* A persona whose voice needs attention, from the choices on screen (saved or not). Mirrors voicelib.check_cast;
     sharing a voice is fine and is simply shown by the cards under that voice. */
  function problem(cid) {
    const id = (C()[cid].voice_id || "").trim(), v = row(id);
    if (!id) return "No voice yet";
    if (!voices().length) return "";
    if (!v) return "Her voice “" + id + "” is not in the list";
    if (v.gone_at) return "Her voice " + v.name + " has gone from Inworld";
    if (v.gender === "male") return "Has a male voice (" + v.name + ")";
    return "";
  }

  /* ------------------------------------------------------------ filter -- */
  function pool() {            // voices allowed by the Women / unlabelled / everyone choice
    return voices().filter(v => st.f.who === "all" || v.gender === "female" || (st.f.who === "open" && v.gender !== "male"));
  }
  function filtered() {
    const f = st.f, q = f.q.trim().toLowerCase();
    const rank = { star: 1, maybe: 2, "": 3, no: 4 };
    const list = pool().filter(v => {
      const m = markOf(v.id).rating || "", n = users(v.id).length;
      if (f.lang && lang2(v) !== f.lang) return false;
      if (f.age && v.age !== f.age) return false;
      if (f.src === "own" && v.source === "SYSTEM") return false;
      if (f.src === "inworld" && v.source !== "SYSTEM") return false;
      if (f.cast === "free" ? n : f.cast === "taken" ? !n : f.cast === "shared" && n < 2) return false;
      if (f.mark === "none" ? m !== "" : f.mark && m !== f.mark) return false;
      if (m === "no" && !n && !f.rejected && f.mark !== "no") return false;
      if (q && !(v.name + " " + v.id + " " + (v.description || "") + " " + v.lang + " " + v.age + " " + (v.tags || []).join(" ") +
                 " " + markOf(v.id).note + " " + users(v.id).map(shown).join(" ")).toLowerCase().includes(q)) return false;
      return true;
    });
    // Voices with personas first, then shortlist, maybe, unmarked, no. Stable: the saved order holds inside each group.
    const key = v => users(v.id).length ? 0 : rank[markOf(v.id).rating || ""];
    list.sort((a, b) => key(a) - key(b));
    return list;
  }

  /* ------------------------------------------------------------ render -- */
  function statusCard() {
    const lib = st.lib, all = voices().filter(v => !v.gone_at), women = all.filter(v => v.gender === "female");
    const h = lib.history[0];
    const change = h ? `Last change ${e(day(h.at))}: ${h.added.length} new, ${h.removed.length} gone${h.back.length ? ", " + h.back.length + " back" : ""}.` : "";
    const hasKey = A.cast && A.cast.key && A.cast.key.has_key;
    const taken = women.filter(v => users(v.id).length).length;
    const top = lib.refreshed_at
      ? `<p><b>${women.length} women's voices</b> in the saved list (${women.filter(v => lang2(v) === "en").length} English), out of ${all.length} voices in all,
           ${all.filter(v => v.source !== "SYSTEM").length} of them your own. <b>${taken}</b> have a persona, <b>${women.length - taken}</b> have none.
           Last checked with Inworld on <b>${e(day(lib.refreshed_at))}</b>. ${change}</p>`
      : `<p><b>No list saved yet.</b> Fetch it once from Inworld; the game then keeps its own copy.</p>`;
    return `<section class="card vl-status">
      <div class="vl-status-top"><div><h2>The saved list</h2>${top}</div>
        <button type="button" class="${lib.refreshed_at ? "" : "primary"}" data-vlcheck="1" ${st.checking || !hasKey ? "disabled" : ""}>
          ${st.checking ? "Asking Inworld…" : lib.refreshed_at ? "Check Inworld for changes" : "Fetch the voice list"}</button></div>
      ${hasKey ? "" : `<p class="err">No Inworld key yet. Add it under Cast &amp; Voices first.</p>`}
      <p class="help">This list only changes when you press the button. A voice ID always sounds the same, so a persona keeps her voice
        for as long as Inworld offers it. Checking shows what is new and flags any persona whose voice has gone.</p>
      <div class="f vl-sample"><label><span>The line every voice reads</span></label>
        <textarea id="vlsample" rows="2" maxlength="300">${e(lib.sample_text)}</textarea>
        <div class="row"><button type="button" data-vlsample="save">Save line</button>
          ${lib.sample_text !== lib.default_sample ? `<button type="button" class="link" data-vlsample="stock">back to the stock line</button>` : ""}
          <span class="help">Each voice's first reading is paid for once (${lib.sample_text.length} characters), then replays for free.</span></div></div>
    </section>`;
  }

  /* A persona's card. Under a voice it can play her catchphrase in that voice. */
  function personaCard(cid, voiceId, note) {
    const c = C()[cid];
    return `<div class="vl-persona" style="--cv:${e(c.color)}" title="${e(c.title || "")}">
      <span class="vl-pic">${c.portrait ? `<img src="${e(c.portrait)}" alt="" loading="lazy">` : `<i>${e(shown(cid).slice(0, 1))}</i>`}</span>
      <b>${e(shown(cid))}</b>
      ${c.title ? `<small>${e(c.title)}</small>` : ""}
      ${note ? `<small class="vl-need">${e(note)}</small>` : ""}
      ${voiceId && c.catchphrase ? `<button type="button" class="vl-play vl-hear" data-vlplay="${e(voiceId)}" data-vlas="${e(cid)}"></button>` : ""}
    </div>`;
  }

  function needs() {           // personas with no usable voice: they have no voice row to sit under
    const list = Object.keys(C()).map(cid => [cid, problem(cid)]).filter(([, p]) => p);
    if (!list.length) return "";
    return `<section class="card vl-needs"><h2>Needing a voice <span class="muted">(${list.length})</span></h2>
      <p class="help">Find a voice below and choose her under “Assign a persona”.</p>
      <div class="vl-personas">${list.map(([cid, p]) => personaCard(cid, "", p)).join("")}</div></section>`;
  }

  function filters() {
    const f = st.f, p = pool();
    const count = (fn) => p.filter(fn).length;
    const langs = [...new Set(p.map(lang2).filter(Boolean))].sort((a, b) => (b === "en") - (a === "en") || langName(a).localeCompare(langName(b)));
    const ages = [...new Set(p.map(v => v.age).filter(Boolean))];
    const opt = (v, label, cur) => `<option value="${e(v)}" ${cur === v ? "selected" : ""}>${e(label)}</option>`;
    return `<section class="card vl-filters">
      <div class="vl-filter-row">
        <label><span>Show</span><select data-vlf="who">${opt("female", "Women", f.who)}${opt("open", "Women and unlabelled", f.who)}${opt("all", "Every voice", f.who)}</select></label>
        <label><span>Personas</span><select data-vlf="cast">${opt("", "Any", f.cast)}${opt("free", "No persona yet (" + count(v => !users(v.id).length) + ")", f.cast)}${opt("taken", "Has a persona (" + count(v => users(v.id).length) + ")", f.cast)}${opt("shared", "Shared by several (" + count(v => users(v.id).length > 1) + ")", f.cast)}</select></label>
        <label><span>Language</span><select data-vlf="lang">${opt("", "All languages", f.lang)}${langs.map(l => opt(l, langName(l) + " (" + count(v => lang2(v) === l) + ")", f.lang)).join("")}</select></label>
        <label><span>Age</span><select data-vlf="age">${opt("", "Any age", f.age)}${ages.map(a => opt(a, a.charAt(0).toUpperCase() + a.slice(1), f.age)).join("")}</select></label>
        <label><span>From</span><select data-vlf="src">${opt("", "Inworld and yours", f.src)}${opt("inworld", "Inworld's voices", f.src)}${opt("own", "Your own voices", f.src)}</select></label>
        <label><span>Marked</span><select data-vlf="mark">${opt("", "Any", f.mark)}${opt("star", "★ Shortlist", f.mark)}${opt("maybe", "? Maybe", f.mark)}${opt("none", "Not marked yet", f.mark)}${opt("no", "✕ No", f.mark)}</select></label>
        <label class="vl-search"><span>Search</span><input type="search" data-vlf="q" value="${e(f.q)}" placeholder="name, accent, tone, note, persona…"></label>
      </div>
      <div class="row"><button type="button" class="vl-play vl-all" data-vlall="1"></button>
        <span id="vlcount" class="muted"></span>
        <label class="vl-radio"><input type="checkbox" data-vlf="rejected" ${f.rejected ? "checked" : ""}> show the ones marked No</label></div>
    </section>`;
  }

  function assignBox(v, us) {
    if (v.gone_at) return "";
    const rest = Object.keys(C()).filter(cid => !us.includes(cid));
    const label = cid => { const id = (C()[cid].voice_id || "").trim(); return shown(cid) + (id ? "  (now " + vname(id) + ")" : "  (no voice)"); };
    return `<label class="vl-assign"><span>Assign a persona</span>
      <select data-vlassign="1"><option value="">Choose who speaks with ${e(v.name)}…</option>
        ${rest.map(cid => `<option value="${e(cid)}">${e(label(cid))}</option>`).join("")}</select></label>`;
  }

  function voiceRow(v) {
    const m = markOf(v.id), us = users(v.id);
    const meta = [v.gender, v.age, v.source === "SYSTEM" ? "Inworld" : "yours"].filter(Boolean).join(" · ");
    const w = where(v), lg = lang2(v);
    const place = lg ? `<span class="vl-where">${w.flag ? `<span class="vl-flagpic" title="${e(w.country)}">${w.flag}</span>` : ""}
      <b>${e(langName(lg))}</b>${w.country ? ` · ${e(w.country)}` : ""} <code>${e(v.lang)}</code></span>` : "";
    return `<article class="vl-row${m.rating ? " is-" + m.rating : ""}${v.gone_at ? " gone" : ""}${us.length ? " taken" : ""}" data-vlrow="${e(v.id)}">
      <div class="vl-voice">
        <button type="button" class="vl-play vl-big" data-vlplay="${e(v.id)}" aria-label="Play ${e(v.name)}">▶</button>
        <div class="vl-info">
          <h3>${e(v.name)}${v.id !== v.name ? ` <code>${e(v.id)}</code>` : ""}
            ${isNew(v) ? `<span class="vl-flag new">New</span>` : ""}${v.gone_at ? `<span class="vl-flag alert">Gone from Inworld ${e(day(v.gone_at))}</span>` : ""}</h3>
          ${place ? `<p class="vl-meta">${place}</p>` : ""}
          <p class="vl-meta">${e(meta)}</p>
          ${v.description ? `<p class="vl-desc">${e(v.description)}</p>` : ""}
          ${(v.tags || []).length ? `<p class="vl-tags">${v.tags.map(t => `<span>${e(t)}</span>`).join("")}</p>` : ""}
        </div>
        <div class="vl-side">
          <div class="vl-marks">${Object.keys(RATE).map(r => `<button type="button" class="vl-mark${m.rating === r ? " on" : ""}" data-vlmark="${r}"
              title="${RATE[r]}">${RATE_ICON[r]} ${RATE[r]}</button>`).join("")}</div>
          <input type="text" class="vl-note" data-vlnote="1" value="${e(m.note)}" maxlength="300" placeholder="Note: who she could be, what she sounds like…">
        </div>
      </div>
      <div class="vl-cast">
        <div class="vl-personas">${us.length ? us.map(cid => personaCard(cid, v.id)).join("") : `<p class="vl-nobody">No persona has this voice.</p>`}</div>
        ${assignBox(v, us)}
      </div></article>`;
  }

  function listHtml() {
    const list = filtered();
    st.order = list.map(v => v.id);
    if (!voices().length) return `<p class="muted">Fetch the voice list above to start.</p>`;
    return list.length ? list.map(voiceRow).join("") : `<p class="muted">No voices match. Loosen the filters.</p>`;
  }

  function render() { return (typeof voiceTabs === "function" ? voiceTabs("voices") : "") + renderPage(); }
  function renderPage() {
    if (!st.lib && !st.loading && !st.err && !st.off) load();
    const intro = "Every Inworld voice you can use, on one page, with the personas who speak with each one. Listen, mark the ones you like, " +
      "and assign a persona to a voice. Assignments are kept with Save & apply; marks and notes are saved as you go.";
    if (st.off) return head("Voice Library", intro) + `<section class="card"><h2>Restart the game server</h2>
      <p>The Voice Library needs the newer game server. Stop and start the game once on this machine, then come back to this page.</p></section>`;
    if (!st.lib) return head("Voice Library", intro) + `<section class="card"><p class="${st.err ? "err" : "muted"}">${e(st.err || "Opening the saved list…")}</p></section>`;
    return `<div id="vlib">${head("Voice Library", intro)}${statusCard()}${needs()}${filters()}
      <section id="vllist" class="vl-list">${listHtml()}</section></div>`;
  }
  function paint() {           // play buttons and counts, without redrawing (keeps typing and scroll)
    const m = $m();
    if (!here() || !m) return;
    m.querySelectorAll("[data-vlplay]").forEach(b => {
      const on = st.playing === b.dataset.vlplay + "|" + (b.dataset.vlas || "");
      b.classList.toggle("on", on);
      b.textContent = b.classList.contains("vl-big") ? (on ? "■" : "▶") : (on ? "■ Stop" : "▶ In her words");
    });
    const playingVoice = st.playing.split("|")[0];
    m.querySelectorAll("[data-vlrow]").forEach(r => r.classList.toggle("playing", !!st.playing && playingVoice === r.dataset.vlrow));
    const all = m.querySelector("[data-vlall]");
    if (all) { all.textContent = st.queue ? "■ Stop the playlist" : "▶ Play all " + st.order.length; all.classList.toggle("on", st.queue); all.disabled = !st.order.length; }
    const n = m.querySelector("#vlcount");
    if (n) n.textContent = st.order.length + (st.order.length === 1 ? " voice" : " voices") + " shown";
  }
  function redraw() {
    const m = $m();
    if (!here() || !m) return;
    const y = window.scrollY;
    m.innerHTML = render();
    window.scrollTo(0, y);
    paint();
  }
  function redrawList() {
    const box = document.getElementById("vllist");
    if (!box) return redraw();
    box.innerHTML = listHtml();
    paint();
  }
  function redrawRow(id) {
    const el = $m().querySelector(`[data-vlrow="${CSS.escape(id)}"]`), v = row(id);
    if (!el || !v) return;
    const tmp = document.createElement("div");
    tmp.innerHTML = voiceRow(v);
    el.replaceWith(tmp.firstElementChild);
    paint();
  }

  /* If Inworld sent no gender labels at all, "Women" would show nothing: widen the view. */
  function unlabelled() {
    if (st.f.who === "female" && voices().length && !voices().some(v => v.gender === "female")) st.f.who = "open";
  }

  /* -------------------------------------------------------------- server -- */
  async function load() {
    st.loading = true;
    let res, status = 0;
    try { const r = await fetch("/api/admin/voice/library"); status = r.status; res = await r.json(); }
    catch (err) { res = { ok: false, error: "Cannot reach the game server." }; }
    st.loading = false;
    if (res.ok) { st.lib = res; st.err = ""; unlabelled(); }
    else if (status === 404) st.off = true;          // an older server that has not been restarted yet
    else st.err = res.error || "Could not open the saved list.";
    redraw();
  }
  async function post(path, body) {
    try {
      const r = await fetch("/api/admin/" + path, { method: "POST", headers: { "X-SeaTrader": "admin" }, body: JSON.stringify(body) });
      if ((r.headers.get("Content-Type") || "").startsWith("audio/")) return { ok: true, audio: await r.blob() };
      return await r.json();
    } catch (err) { return { ok: false, error: "Cannot reach the game server." }; }
  }
  function stop() {
    if (st.audio) { st.audio.pause(); URL.revokeObjectURL(st.audio.src); st.audio = null; }
    st.playing = "";
  }
  function halt() { st.queue = false; stop(); paint(); }
  function audition(id, cid) { // what a voice reads: the shared line, or a persona's catchphrase at her speed
    const c = cid && C()[cid];
    const character = { voice_id: id, speaking_rate: c ? c.speaking_rate : 1, delivery: c ? c.delivery : "" };
    return { character, text: c ? c.catchphrase : st.lib.sample_text, model_id: CFG.voice.model_id, temperature: CFG.voice.temperature };
  }
  async function play(id, cid) {
    const key = id + "|" + (cid || "");
    stop();
    st.playing = key;
    paint();
    const res = await post("voice/preview", audition(id, cid));
    if (st.playing !== key) return;
    if (!res.ok) { halt(); return toast(vname(id) + ": " + res.error, true); }
    const a = new Audio(URL.createObjectURL(res.audio));
    st.audio = a;
    a.onended = () => { if (st.audio === a) { stop(); st.queue ? next(id) : paint(); } };
    a.play().catch(() => halt());
    const el = st.queue && $m().querySelector(`[data-vlrow="${CSS.escape(id)}"]`);
    if (el) el.scrollIntoView({ block: "center", behavior: "smooth" });
  }
  function next(after) {
    const i = st.order.indexOf(after);
    const id = st.order[i + 1];
    if (!here() || i < 0 || !id) return halt();
    setTimeout(() => { if (st.queue && !st.playing) play(id); }, 500);
  }

  /* -------------------------------------------------------------- events -- */
  async function onClick(ev) {
    if (!here()) return;
    const el = ev.target.closest("button");
    if (!el) return;
    const d = el.dataset, rowEl = el.closest("[data-vlrow]"), id = rowEl && rowEl.dataset.vlrow;
    if (d.vlplay) {
      const was = st.playing === d.vlplay + "|" + (d.vlas || "");
      st.queue = false;
      if (was) return halt();
      return play(d.vlplay, d.vlas);
    }
    if (d.vlall) {
      if (st.queue) return halt();
      if (!st.order.length) return;
      st.queue = true;
      return play(st.order[0]);
    }
    if (d.vlmark && id) {
      const res = await post("voice/library/mark", { id, rating: markOf(id).rating === d.vlmark ? "" : d.vlmark });
      if (!res.ok) return toast(res.error, true);
      setMark(id, res.mark);
      const hidden = res.mark.rating === "no" && !users(id).length && !st.f.rejected && st.f.mark !== "no";
      return hidden || st.f.mark ? redrawList() : redrawRow(id);
    }
    if (d.vlcheck) {
      st.checking = true;
      redraw();
      const res = await post("voice/library/refresh", {});
      st.checking = false;
      if (!res.ok) { redraw(); return toast(res.error, true); }
      st.lib = res;
      unlabelled();
      redraw();
      const df = res.diff;
      return toast(df.first ? "Saved " + res.voices.length + " voices from Inworld."
        : df.added.length || df.removed.length || df.back.length
          ? "Inworld changed: " + df.added.length + " new, " + df.removed.length + " gone" + (df.back.length ? ", " + df.back.length + " back" : "") + "."
          : "No changes at Inworld. Your list is up to date.");
    }
    if (d.vlsample) {
      const text = d.vlsample === "stock" ? "" : (document.getElementById("vlsample").value || "");
      const res = await post("voice/library/sample", { text });
      if (!res.ok) return toast(res.error, true);
      st.lib.sample_text = res.sample_text;
      redraw();
      return toast("Audition line saved.");
    }
  }
  function setMark(id, m) {
    if (m.rating || m.note) st.lib.marks[id] = m; else delete st.lib.marks[id];
  }
  async function onChange(ev) {
    if (!here()) return;
    const el = ev.target, d = el.dataset;
    if (d.vlnote) {
      const id = el.closest("[data-vlrow]").dataset.vlrow;
      const res = await post("voice/library/mark", { id, note: el.value });
      if (!res.ok) return toast(res.error, true);
      setMark(id, res.mark);
      return;
    }
    if (d.vlassign) {
      const id = el.closest("[data-vlrow]").dataset.vlrow, cid = el.value, c = C()[cid];
      if (!c) return;
      const old = (c.voice_id || "").trim();
      halt();
      c.voice_id = id;
      refreshDirty();
      redraw();                 // her card moves from one voice to the other, and the counts change
      return toast(shown(cid) + " now speaks with " + vname(id) + (old && old !== id ? " (was " + vname(old) + ")" : "") + ". Save & apply to keep it.");
    }
    if (d.vlf && d.vlf !== "q") {
      halt();
      st.f[d.vlf] = el.type === "checkbox" ? el.checked : el.value;
      if (d.vlf === "who") { st.f.lang = ""; st.f.age = ""; return redraw(); }   // the other lists depend on it
      return redrawList();
    }
  }
  function onInput(ev) {
    if (!here() || ev.target.dataset.vlf !== "q") return;
    halt();
    st.f.q = ev.target.value;
    redrawList();
  }

  document.addEventListener("DOMContentLoaded", () => {
    const m = $m();
    m.addEventListener("click", onClick);
    m.addEventListener("change", onChange);
    m.addEventListener("input", onInput);
  });

  window.SeaTraderVoices = { render, enter: paint, leave: halt };
})();
