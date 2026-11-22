/* Crimson Ledger Admin: Voices > Clips.
   Every saved voice clip, and every fixed line that has none yet, in one list you can filter, play,
   rank (1-5 stars + Redo), audit (is it still how she sounds today?), edit the wording of, re-record,
   and move to a Bin. The persona who speaks the selected line stands full height on the right,
   like the Sea Battle screen, with her voice, speed and delivery beside her and how much she speaks.
   Server side: voiceclips.py. Ranks, notes and the bin are saved straight away. A wording edit is the
   Admin's spoken version (CFG.voice.say) and a speed or delivery change is a Cast & Voices change:
   both are kept with Save & apply, and recording uses what has been saved. */
(function () {
  "use strict";

  const st = {
    data: null, err: "", loading: false, off: false,
    view: "all", sel: "", shown: 100, playing: "", audio: null, queue: false, order: [], busy: "", draft: {},
    f: { persona: "", voice: "", stars: "", redo: false, status: "", group: "", q: "", sort: "new" },
  };
  const $m = () => document.getElementById("main");
  const e = s => esc(s);
  const here = () => section === "clips";
  const C = () => CFG.characters;
  const rid = r => r.id || "m:" + r.key;
  const BADGE = { current: "Current", stale: "Out of date", early: "Early recording", recorded: "Recorded", missing: "Not recorded", binned: "In the bin" };

  function shown(cid) {
    const c = C()[cid] || {};
    return c.brand_link && CFG.brand[c.brand_link] ? CFG.brand[c.brand_link] : (c.name || cid || "");
  }
  const rows = () => st.data ? st.data.clips.concat(st.data.missing) : [];
  const byRid = id => rows().find(r => rid(r) === id);
  const day = s => String(s || "").slice(0, 10);
  const rateTxt = n => n == null ? "" : " ×" + Number(n).toFixed(2).replace(/0$/, "");
  const stats = cid => (st.data && st.data.personas[cid || ""]) || { clips: 0, chars: 0, share: 0, stale: 0, redo: 0, missing: 0, avg_stars: 0, rated: 0, low: 0 };

  /* --------------------------------------------------------------- data -- */
  async function post(path, body) {
    try {
      const r = await fetch("/api/admin/" + path, { method: "POST", headers: { "X-SeaTrader": "admin" }, body: JSON.stringify(body) });
      if ((r.headers.get("Content-Type") || "").startsWith("audio/")) return { ok: true, audio: await r.blob() };
      return await r.json();
    } catch (err) { return { ok: false, error: "Cannot reach the game server." }; }
  }
  async function load(quiet) {
    st.loading = !quiet;
    let res, status = 0;
    try { const r = await fetch("/api/admin/voice/clips"); status = r.status; res = await r.json(); }
    catch (err) { res = { ok: false, error: "Cannot reach the game server." }; }
    st.loading = false;
    if (res.ok) { st.data = res; st.err = ""; }
    else if (status === 404) st.off = true;
    else st.err = res.error || "Could not open the saved clips.";
    redraw();
  }

  /* ------------------------------------------------------------ filter -- */
  function inView(r) {
    if (st.view === "bin") return r.binned;
    if (r.binned) return false;
    if (st.view === "missing") return r.status === "missing";
    if (st.view === "attention") return r.redo || r.status === "stale" || r.status === "missing" || (r.stars && r.stars <= 2);
    return true;
  }
  function filtered() {
    const f = st.f, q = f.q.trim().toLowerCase();
    const list = rows().filter(r => {
      if (!inView(r)) return false;
      if (f.persona === "?" ? r.persona : f.persona && r.persona !== f.persona) return false;
      if (f.voice && r.voice !== f.voice) return false;
      if (f.stars === "0" ? r.stars : f.stars && !(r.stars && r.stars <= Number(f.stars))) return false;
      if (f.redo && !r.redo) return false;
      if (f.status && r.status !== f.status) return false;
      if (f.group && r.group !== f.group) return false;
      if (q && !(r.text + " " + r.key + " " + r.note + " " + shown(r.persona) + " " + r.voice).toLowerCase().includes(q)) return false;
      return true;
    });
    const by = {
      new: (a, b) => (b.at || "").localeCompare(a.at || ""),
      low: (a, b) => (a.stars || 9) - (b.stars || 9) || (b.at || "").localeCompare(a.at || ""),
      persona: (a, b) => shown(a.persona).localeCompare(shown(b.persona)) || a.text.localeCompare(b.text),
      long: (a, b) => b.chars - a.chars,
      text: (a, b) => a.text.localeCompare(b.text),
    }[f.sort] || (() => 0);
    return list.sort(by);
  }
  const counts = () => {
    const live = st.data.clips.filter(c => !c.binned);
    return { all: live.length + st.data.missing.length, attention: live.filter(r => r.redo || r.status === "stale" || (r.stars && r.stars <= 2)).length + st.data.missing.length,
      missing: st.data.missing.length, bin: st.data.clips.length - live.length };
  };

  /* ------------------------------------------------------------ render -- */
  function avatar(cid) {
    const c = C()[cid];
    if (!c) return `<span class="ck-av none">?</span>`;
    return c.portrait ? `<img class="ck-av" src="${e(c.portrait)}" alt="" style="--cv:${e(c.color)}">`
      : `<span class="ck-av" style="--cv:${e(c.color)}">${e(shown(cid).slice(0, 1))}</span>`;
  }
  function who(r) {
    if (r.persona) {
      const c = C()[r.persona];
      return `${avatar(r.persona)}<b>${e(shown(r.persona))}</b>` + (c ? ` <span class="ck-voice">${e(c.voice_id)}${e(rateTxt(c.speaking_rate))}</span>` : "");
    }
    if (r.shared && r.shared.length) return `<span class="ck-av none">?</span><b>Shared voice ${e(r.voice)}</b> <span class="ck-voice">${e(r.shared.map(shown).join(", "))}</span>`;
    return `<span class="ck-av none">?</span><b>Not placed</b> <span class="ck-voice">${e(r.voice)}</span>`;
  }
  function stars(r) {
    if (!r.id) return "";
    let h = `<span class="ck-stars" role="group" aria-label="Rank">`;
    for (let i = 1; i <= 5; i++) h += `<button type="button" class="ck-star${i <= r.stars ? " on" : ""}" data-ck-star="${e(r.id)}|${i}" title="${i} star${i > 1 ? "s" : ""}">★</button>`;
    return h + `</span>`;
  }
  function badge(r) {
    const why = r.status === "stale" ? ": " + r.diffs.map(d => st.data.diff_labels[d] || d).join(", ") : "";
    return `<span class="ck-badge ${e(r.status)}">${e(BADGE[r.status] || r.status)}${e(why)}</span>` + (r.redo ? `<span class="ck-badge redo">Redo</span>` : "")
      + (r.variant === "family" ? `<span class="ck-badge fam" title="The clean version, played on Family-friendly screens">Clean</span>` : "");
  }
  function rowHtml(r) {
    const id = rid(r), on = st.sel === id;
    return `<div class="ck-row ${e(r.status)}${on ? " sel" : ""}" data-ck-row="${e(id)}">
      <button type="button" class="ck-play" data-ck-play="${e(id)}" ${r.status === "missing" ? "disabled" : ""} title="${r.status === "missing" ? "Record it first" : "Play"}">${st.playing === id ? "■" : "▶"}</button>
      <div class="ck-body"><div class="ck-text">${e(r.text)}</div>
        <div class="ck-meta"><span class="ck-who">${who(r)}</span>${r.group ? `<span>${e(r.group)}</span>` : ""}${r.key ? `<code>${e(r.key)}</code>` : ""}${r.at ? `<span>${e(day(r.at))}</span>` : ""}<span>${r.chars} chars</span></div>
        ${r.note ? `<div class="ck-note">${e(r.note)}</div>` : ""}</div>
      <div class="ck-side">${stars(r)}<div class="ck-badges">${badge(r)}</div></div></div>`;
  }
  function listHtml() {
    const list = filtered();
    st.order = list.filter(r => r.id && !r.binned).map(rid);
    if (!list.length) return `<p class="muted ck-empty">${st.view === "bin" ? "The bin is empty." : "Nothing matches these filters."}</p>`;
    const more = list.length - st.shown;
    return `<p class="muted ck-count">${list.length} line${list.length === 1 ? "" : "s"}${list.length > st.shown ? ", showing the first " + st.shown : ""}</p>` +
      list.slice(0, st.shown).map(rowHtml).join("") +
      (more > 0 ? `<button type="button" class="ck-more" data-ck-more="1">Show ${Math.min(100, more)} more</button>` : "");
  }
  function options(list, cur, any) {
    return `<option value="">${e(any)}</option>` + list.map(([v, l]) => `<option value="${e(v)}"${String(cur) === String(v) ? " selected" : ""}>${e(l)}</option>`).join("");
  }
  function filters() {
    const d = st.data, f = st.f, n = counts();
    const ps = Object.keys(d.personas).filter(k => k).sort((a, b) => d.personas[b].chars - d.personas[a].chars)
      .map(cid => { const s = d.personas[cid], c = C()[cid] || {};
        return [cid, `${shown(cid)} · ${c.voice_id || "no voice"}${rateTxt(c.speaking_rate)} · ${s.clips} clips · ${s.share}%`]; });
    const voices = [...new Set(d.clips.map(c => c.voice).filter(Boolean))].sort().map(v => [v, v]);
    const groups = [...new Set(rows().map(r => r.group).filter(Boolean))].map(g => [g, g]);
    const tab = (id, l, c) => `<button type="button" class="ck-tab${st.view === id ? " on" : ""}" data-ck-view="${id}">${l} <i>${c}</i></button>`;
    return `<div class="ck-tabs">${tab("all", "All", n.all)}${tab("attention", "Needs attention", n.attention)}${tab("missing", "Missing", n.missing)}${tab("bin", "Bin", n.bin)}</div>
      <section class="card ck-filters">
        <label class="ck-wide"><span>Persona (voice · clips · share of everything spoken)</span><select data-ck-f="persona">${options(ps.concat([["?", "Not placed / shared voice"]]), f.persona, "Anyone")}</select></label>
        <label><span>Voice</span><select data-ck-f="voice">${options(voices, f.voice, "Any voice")}</select></label>
        <label><span>Rank</span><select data-ck-f="stars">${options([["0", "Unrated"], ["1", "1 star"], ["2", "2 stars or fewer"], ["3", "3 stars or fewer"], ["4", "4 stars or fewer"]], f.stars, "Any rank")}</select></label>
        <label><span>State</span><select data-ck-f="status">${options([["current", "Current"], ["stale", "Out of date"], ["early", "Early recording"], ["recorded", "Recorded (not checkable)"], ["missing", "Not recorded"]], f.status, "Any state")}</select></label>
        <label><span>Kind of line</span><select data-ck-f="group">${options(groups, f.group, "Any")}</select></label>
        <label><span>Sort</span><select data-ck-f="sort">${options([["new", "Newest first"], ["low", "Lowest rank first"], ["persona", "By persona"], ["long", "Longest first"], ["text", "A to Z"]], f.sort, "").replace('<option value=""></option>', "")}</select></label>
        <label class="ck-wide"><span>Search the words, line key, note or persona</span><input type="search" data-ck-f="q" value="${e(f.q)}" placeholder="e.g. hold, Yu-lan, customs"></label>
        <label class="ck-check"><input type="checkbox" data-ck-f="redo"${f.redo ? " checked" : ""}> Redo flagged only</label>
        <div class="ck-actions"><button type="button" data-ck-playall="1">${st.queue ? "■ Stop" : "▶ Play all shown"}</button>
          ${st.view === "bin" && n.bin ? `<button type="button" class="danger" data-ck-empty="1">Empty the bin…</button>` : ""}
          <button type="button" class="link" data-ck-clear="1">Clear filters</button></div>
      </section>`;
  }
  function summary() {
    const t = st.data.totals, price = st.data.price_per_1k, cost = t.chars / 1000 * price;
    const cell = (v, l, cls) => `<div class="ck-stat ${cls || ""}"><b>${v}</b><span>${l}</span></div>`;
    return `<section class="card ck-summary">${cell(t.clips, "saved clips")}${cell(t.chars.toLocaleString(), "characters spoken")}${cell((t.bytes / 1048576).toFixed(0) + " MB", "on disk")}
      ${cell(t.stale, "out of date", t.stale ? "warn" : "")}${cell(t.missing, "lines with no clip", t.missing ? "warn" : "")}${cell(t.redo, "flagged Redo", t.redo ? "warn" : "")}${cell(t.unrated, "unrated")}
      <label class="ck-price"><span>Inworld price per 1,000 characters</span><input type="number" min="0" step="0.01" data-ck-price="1" value="${price || ""}" placeholder="$ (optional)">
        <small>${price ? "About $" + cost.toFixed(2) + " spent on these clips" : "Add your price to see what each persona costs"}</small></label>
    </section>`;
  }

  /* -------------------------------------------------- the persona panel -- */
  function personaOf(r) { return (r && r.persona) || (st.f.persona && st.f.persona !== "?" ? st.f.persona : ""); }
  function leaderboard() {
    const d = st.data, price = d.price_per_1k;
    const top = Object.keys(d.personas).filter(k => k).sort((a, b) => d.personas[b].chars - d.personas[a].chars).slice(0, 14);
    const max = top.length ? d.personas[top[0]].chars || 1 : 1;
    return `<h3>Who speaks most</h3><p class="muted">Characters spoken so far. Click a persona to filter the list. A persona heard all the time is the one to get right.</p>
      ${top.map(cid => { const s = d.personas[cid], c = C()[cid] || {};
        return `<button type="button" class="ck-lb" data-ck-persona="${e(cid)}">${avatar(cid)}<span class="ck-lb-name"><b>${e(shown(cid))}</b><small>${e(c.voice_id || "no voice")}${e(rateTxt(c.speaking_rate))} · ${s.clips} clips</small></span>
          <span class="ck-lb-bar"><i style="width:${Math.max(3, 100 * s.chars / max)}%"></i></span><span class="ck-lb-pct">${s.share}%${price ? "<small>$" + (s.chars / 1000 * price).toFixed(2) + "</small>" : ""}</span></button>`; }).join("")}`;
  }
  function personaPanel(cid) {
    const c = C()[cid], s = stats(cid), price = st.data.price_per_1k;
    if (!c) return "";
    const unsaved = SAVED && SeaTraderCast.sectionChanged(JSON.parse(SAVED));
    return `<div class="ck-pp" style="--cv:${e(c.color)}">
      <div class="ck-portrait">${c.portrait ? `<img src="${e(c.portrait)}" alt="${e(shown(cid))}">` : `<span>${e(shown(cid).slice(0, 1))}</span>`}
        <div class="ck-portrait-name"><b>${e(shown(cid))}</b><small>${e(c.title || "")}</small></div></div>
      <div class="ck-vals">
        <div class="ck-val"><span>Voice</span><b>${e(c.voice_id || "none")}</b></div>
        <div class="ck-val"><span>Speed</span><b>${Number(c.speaking_rate || 1).toFixed(2)}</b></div>
        <div class="ck-val"><span>Clips</span><b>${s.clips}</b></div>
        <div class="ck-val"><span>Share</span><b>${s.share}%</b></div>
        <div class="ck-val"><span>Avg rank</span><b>${s.avg_stars ? s.avg_stars.toFixed(1) + " ★" : "–"}</b></div>
        <div class="ck-val"><span>Spend</span><b>${price ? "$" + (s.chars / 1000 * price).toFixed(2) : s.chars.toLocaleString() + " ch"}</b></div>
      </div>
      <p class="ck-need">${s.stale ? `<span class="ck-badge stale">${s.stale} out of date</span>` : ""}${s.redo ? `<span class="ck-badge redo">${s.redo} Redo</span>` : ""}${s.missing ? `<span class="ck-badge missing">${s.missing} not recorded</span>` : ""}${s.low ? `<span class="ck-badge stale">${s.low} rated 2 or fewer</span>` : ""}</p>
      <details class="ck-tune"><summary>Her speed and delivery</summary>
        <label><span>Speed (0.5 to 1.5)</span><input type="number" min="0.5" max="1.5" step="0.01" data-ck-rate="${e(cid)}" value="${Number(c.speaking_rate || 1).toFixed(2)}"></label>
        <label><span>Delivery note</span><textarea rows="3" data-ck-delivery="${e(cid)}">${e(c.delivery || "")}</textarea></label>
        <p class="help">${unsaved ? "Unsaved. " : ""}Kept with Save &amp; apply. Clips recorded at her old settings then show as out of date.</p></details>
      <div class="ck-links"><button type="button" data-nav-tab="voices">Voice Library</button><button type="button" data-nav-tab="cast">Cast &amp; Voices</button>
        ${st.f.persona === cid ? "" : `<button type="button" data-ck-persona="${e(cid)}">Only her clips</button>`}</div>
    </div>`;
  }
  function clipPanel(r) {
    const id = rid(r), canEdit = !!r.key && !r.names && r.variant !== "family" && r.status !== "binned";
    const draft = st.draft[id] != null ? st.draft[id] : (r.current || r.text);
    const dirtyWording = canEdit && ((CFG.voice.say || {})[r.key] !== (JSON.parse(SAVED).voice.say || {})[r.key]);
    const busy = st.busy === id;
    let acts = "";
    if (r.binned) acts = `<button type="button" data-ck-restore="${e(r.id)}">Restore from the bin</button>`;
    else if (r.status === "missing") acts = `<button type="button" class="primary" data-ck-record="${e(id)}" ${busy ? "disabled" : ""}>${busy ? "Recording…" : "Record this line"}</button>`;
    else acts = `<button type="button" class="primary" data-ck-record="${e(id)}" ${busy ? "disabled" : ""}>${busy ? "Recording…" : "Re-record"}</button>
      <button type="button" data-ck-bin="${e(r.id)}">Move to bin</button>`;
    return `<div class="ck-cp">
      <h3>This line</h3>
      <p class="ck-said">${e(r.text)}</p>
      ${r.screen && r.screen !== r.text ? `<p class="muted ck-screen">On screen: ${e(r.screen)}</p>` : ""}
      <p class="ck-facts">${r.key ? `<code>${e(r.key)}</code> ` : ""}${e(r.group)}${r.voice ? " · recorded with " + e(r.voice) + e(rateTxt(r.rate)) : ""}${r.at ? " · " + e(day(r.at)) : ""}</p>
      <p>${badge(r)}</p>
      ${r.id ? `<div class="ck-rank"><span>Rank</span>${stars(r)}<label class="ck-check"><input type="checkbox" data-ck-redo="${e(r.id)}"${r.redo ? " checked" : ""}> Redo</label></div>
        <label class="ck-notebox"><span>Note</span><input type="text" maxlength="300" data-ck-note="${e(r.id)}" value="${e(r.note)}" placeholder="e.g. too fast, says 'guilders' wrong"></label>` : ""}
      ${canEdit ? `<label class="ck-edit"><span>Wording the voice says (before recording)</span><textarea rows="4" data-ck-say="${e(id)}">${e(draft)}</textarea></label>
        <div class="ck-actions"><button type="button" data-ck-hear="${e(id)}">▶ Hear this wording</button><button type="button" data-ck-keep="${e(id)}">Keep this wording</button></div>
        <p class="help">${dirtyWording ? "Wording changed: use Save &amp; apply, then record." : "The screen text does not change; only what is spoken. Kept with Save &amp; apply."}</p>`
        : (r.names ? `<p class="help">This line has names or amounts filled in, so its spoken version is edited in Cast &amp; Voices.</p>` : r.variant === "family" ? `<p class="help">This is the clean (Family-friendly) version of a line. It is re-recorded as written.</p>` : "")}
      <div class="ck-actions">${acts}</div>
      ${r.status === "missing" || r.id ? `<p class="help">Recording sends ${r.chars} characters to Inworld${r.id && !r.binned ? "; the old take goes to the bin." : "."} It uses the saved settings.</p>` : ""}
    </div>`;
  }
  function panel() {
    const r = st.sel && byRid(st.sel), cid = personaOf(r);
    return (cid ? personaPanel(cid) : "") + (r ? clipPanel(r) : (cid ? "" : leaderboard()));
  }

  function render() {
    const intro = "Every saved voice clip, and every fixed line that has none yet. Rank them, hear them, change the wording, and re-record the ones that are not right. " +
      "Deleting moves a clip to the bin.";
    const tabs = typeof voiceTabs === "function" ? voiceTabs("clips") : "";
    if (!st.data && !st.loading && !st.err && !st.off) load();
    if (st.off) return tabs + head("Voice clips", intro) + `<section class="card"><h2>Restart the game server</h2><p>This page needs the newer game server. Stop and start the game once on this machine, then come back.</p></section>`;
    if (!st.data) return tabs + head("Voice clips", intro) + `<section class="card"><p class="${st.err ? "err" : "muted"}">${e(st.err || "Opening the saved clips…")}</p></section>`;
    return `<div id="ckp">${tabs}${head("Voice clips", intro)}${summary()}${filters()}
      <div class="ck-wrap"><section id="cklist" class="ck-list">${listHtml()}</section><aside id="ckpanel" class="ck-panel">${panel()}</aside></div></div>`;
  }
  function redraw() {
    const m = $m();
    if (!here() || !m) return;
    const y = window.scrollY;
    m.innerHTML = render();
    window.scrollTo(0, y);
  }
  function repaint() {          // list and panel only: keeps the filter boxes and their focus
    const l = document.getElementById("cklist"), p = document.getElementById("ckpanel");
    if (!l || !p) return redraw();
    l.innerHTML = listHtml();
    const top = st.sel !== st.lastSel ? 0 : p.scrollTop;      // a new line starts at her portrait
    st.lastSel = st.sel;
    p.innerHTML = panel();
    p.scrollTop = top;
    const pb = $m().querySelectorAll(".ck-tab i"), n = counts();
    [n.all, n.attention, n.missing, n.bin].forEach((v, i) => { if (pb[i]) pb[i].textContent = v; });
  }

  /* ----------------------------------------------------------- playing -- */
  function stop() {
    if (st.audio) { st.audio.pause(); if (st.audio.dataset && st.audio.dataset.blob) URL.revokeObjectURL(st.audio.src); st.audio = null; }
    st.playing = "";
  }
  function halt() { st.queue = false; stop(); if (here()) repaint(); }
  async function play(id) {
    const r = byRid(id);
    if (!r || !r.id) return;
    stop();
    st.playing = id;
    repaint();
    let src = "/voice/" + r.id + ".mp3", blob = false;
    if (r.binned) {
      try {
        const res = await fetch("/api/admin/voice/clips/bin_audio?id=" + encodeURIComponent(r.id));
        if (!res.ok) throw new Error("gone");
        src = URL.createObjectURL(await res.blob()); blob = true;
      } catch (err) { st.playing = ""; repaint(); return toast("That clip is no longer in the bin.", true); }
    }
    if (st.playing !== id) return;
    const a = new Audio(src);
    if (blob) a.dataset.blob = "1";
    st.audio = a;
    a.onended = () => { if (st.audio === a) { stop(); st.queue ? nextInQueue(id) : repaint(); } };
    a.onerror = () => { if (st.audio === a) { stop(); st.queue = false; repaint(); toast("That clip could not be played.", true); } };
    a.play().catch(() => halt());
  }
  function nextInQueue(after) {
    const i = st.order.indexOf(after), nx = st.order[i + 1];
    if (!here() || i < 0 || !nx) return halt();
    st.sel = nx;
    setTimeout(() => { if (st.queue && !st.playing) { play(nx); const el = $m().querySelector(`[data-ck-row="${CSS.escape(nx)}"]`); if (el) el.scrollIntoView({ block: "center", behavior: "smooth" }); } }, 400);
  }
  async function hear(id) {          // the edited wording, in her current settings (not saved anywhere)
    const r = byRid(id), c = r && C()[r.persona], ta = $m().querySelector(`[data-ck-say="${CSS.escape(id)}"]`);
    if (!r || !ta) return;
    if (!c || !c.voice_id) return toast("This line has no persona with a voice yet.", true);
    stop();
    toast("Sending " + ta.value.length + " characters to Inworld…");
    const res = await post("voice/preview", { character: { voice_id: c.voice_id, speaking_rate: c.speaking_rate, delivery: c.delivery },
      text: ta.value, model_id: CFG.voice.model_id, temperature: CFG.voice.temperature });
    if (!res.ok) return toast(res.error, true);
    const a = new Audio(URL.createObjectURL(res.audio));
    a.dataset.blob = "1";
    st.audio = a;
    a.onended = () => { if (st.audio === a) stop(); };
    a.play().catch(() => stop());
  }

  /* ----------------------------------------------------------- actions -- */
  const patch = (id, meta) => { const r = rows().find(x => x.id === id); if (r) Object.assign(r, meta); };
  async function setRank(id, body) {
    const res = await post("voice/clips/rate", Object.assign({ id }, body));
    if (!res.ok) return toast(res.error, true);
    patch(id, res.meta);
    repaint();
  }
  function needSaved(r) {
    if (SAVED && SeaTraderCast.sectionChanged(JSON.parse(SAVED))) {
      toast("Save & apply first: recording uses the saved voice, speed, delivery and wording.", true);
      return true;
    }
    return false;
  }
  async function record(id) {
    const r = byRid(id);
    if (!r || needSaved(r)) return;
    const msg = r.id ? "Re-record this line? " + r.chars + " characters go to Inworld, and the old take moves to the bin."
      : "Record this line? " + r.chars + " characters go to Inworld.";
    if (!window.confirm(msg)) return;
    st.busy = id; repaint();
    const res = await post("voice/clips/record", r.id ? { id: r.id, key: r.key } : { key: r.key });
    st.busy = "";
    if (!res.ok) { repaint(); return toast(res.error, true); }
    toast("Recorded.");
    st.sel = res.clip;
    await load(true);
    play(res.clip);
  }

  /* ------------------------------------------------------------ events -- */
  async function onClick(ev) {
    if (!here()) return;
    const el = ev.target.closest("button, .ck-row"), d = el ? el.dataset : {};
    if (!el) return;
    if (d.ckStar) {
      const [id, n] = d.ckStar.split("|"), r = byRid(id);
      return setRank(id, { stars: r && r.stars === Number(n) ? 0 : Number(n) });
    }
    if (d.ckPlay) { if (st.playing === d.ckPlay) return halt(); st.queue = false; st.sel = d.ckPlay; repaint(); return play(d.ckPlay); }
    if (d.ckView) { st.view = d.ckView; st.shown = 100; halt(); return redraw(); }
    if (d.ckMore) { st.shown += 100; return repaint(); }
    if (d.ckPersona) { st.f.persona = d.ckPersona; st.sel = ""; st.shown = 100; return redraw(); }
    if (d.ckClear) { st.f = { persona: "", voice: "", stars: "", redo: false, status: "", group: "", q: "", sort: "new" }; st.shown = 100; return redraw(); }
    if (d.ckPlayall) {
      if (st.queue) return halt();
      if (!st.order.length) return toast("Nothing to play in this list.", true);
      st.queue = true; st.sel = st.order[0]; redraw(); return play(st.order[0]);
    }
    if (d.ckHear) return hear(d.ckHear);
    if (d.ckKeep) {
      const r = byRid(d.ckKeep), ta = $m().querySelector(`[data-ck-say="${CSS.escape(d.ckKeep)}"]`);
      if (!r || !ta) return;
      if (!CFG.voice.say) CFG.voice.say = {};
      CFG.voice.say[r.key] = ta.value.trim();
      delete st.draft[d.ckKeep];
      refreshDirty();
      repaint();
      return toast("Wording kept. Use Save & apply, then record the line.");
    }
    if (d.ckRecord) return record(d.ckRecord);
    if (d.ckBin) {
      const res = await post("voice/clips/bin", { id: d.ckBin, why: "deleted on the Clips page" });
      if (!res.ok) return toast(res.error, true);
      stop(); toast("Moved to the bin. If the game needs that line again it will record a new take.");
      st.sel = ""; return load(true);
    }
    if (d.ckRestore) {
      const res = await post("voice/clips/restore", { id: d.ckRestore });
      if (!res.ok) return toast(res.error, true);
      toast("Restored."); return load(true);
    }
    if (d.ckEmpty) {
      if (!window.confirm("Delete everything in the bin for good? This removes the audio and cannot be undone.")) return;
      const res = await post("voice/clips/empty_bin", {});
      if (!res.ok) return toast(res.error, true);
      toast("Removed " + res.removed + " clip" + (res.removed === 1 ? "" : "s") + " for good."); return load(true);
    }
    if (d.navTab) return go(d.navTab);
    const row = ev.target.closest(".ck-row");
    if (row && !d.ckPlay) { st.sel = row.dataset.ckRow; repaint(); }
  }
  function onChange(ev) {
    if (!here()) return;
    const t = ev.target, d = t.dataset;
    if (d.ckF && d.ckF !== "q") {
      st.f[d.ckF] = t.type === "checkbox" ? t.checked : t.value;
      st.shown = 100; halt(); return redraw();
    }
    if (d.ckRedo) return setRank(d.ckRedo, { redo: t.checked });
    if (d.ckNote) return setRank(d.ckNote, { note: t.value });
    if (d.ckPrice) {
      post("voice/clips/price", { price: t.value || 0 }).then(res => {
        if (!res.ok) return toast(res.error, true);
        st.data.price_per_1k = res.price_per_1k; redraw();
      });
      return;
    }
    if (d.ckRate) {
      const c = C()[d.ckRate], v = Math.min(1.5, Math.max(0.5, Number(t.value) || 1));
      if (c) { c.speaking_rate = Math.round(v * 100) / 100; refreshDirty(); repaint(); }
      return;
    }
    if (d.ckDelivery) { const c = C()[d.ckDelivery]; if (c) { c.delivery = t.value; refreshDirty(); } return; }
  }
  function onInput(ev) {
    if (!here()) return;
    const d = ev.target.dataset;
    if (d.ckF === "q") { st.f.q = ev.target.value; st.shown = 100; const l = document.getElementById("cklist"); if (l) l.innerHTML = listHtml(); }
    if (d.ckSay) st.draft[d.ckSay] = ev.target.value;
  }

  document.addEventListener("DOMContentLoaded", () => {
    const m = $m();
    m.addEventListener("click", onClick);
    m.addEventListener("change", onChange);
    m.addEventListener("input", onInput);
  });

  window.SeaTraderClips = { render, enter: () => { if (st.data) load(true); }, leave: halt };
})();
