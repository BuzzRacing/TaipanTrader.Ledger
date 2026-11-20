/* SeaTrader Admin: Captains.
   Saved player profiles that last from game to game: PIN (the Captain's id number), portrait,
   Inworld voice id, story, Houses (the firms they sail as) and the record of every game.
   Portraits and House crests are Media Library pictures (kinds "captain" and "house"): generate
   several, star the one you like, regenerate any time. The starred picture is the one shown.
   Captains save straight away with their own Save button (they are not part of the settings). */
(function () {
  "use strict";

  const st = { data: null, loading: false, open: null, draft: null, dirty: false, voices: null, voicesErr: "",
               audio: null, poll: null, confirmDel: "", q: "", busy: "" };
  const e = s => esc(s);
  const SEC = "captains";

  /* --------------------------------------------------------- helpers -- */
  async function post(path, body) {
    try {
      const r = await fetch("/api/admin/" + path, { method: "POST", headers: { "X-SeaTrader": "admin" }, body: JSON.stringify(body) });
      if ((r.headers.get("Content-Type") || "").startsWith("audio/")) return { ok: true, audio: await r.blob() };
      return await r.json();
    } catch (err) { return { ok: false, error: "Cannot reach the game server." }; }
  }
  async function getJson(path) {
    try { return await (await fetch("/api/admin/" + path)).json(); }
    catch (err) { return { ok: false, error: "Cannot reach the game server." }; }
  }
  const D = () => st.data;
  const cap = cid => (D() && D().captains.find(c => c.cid === cid)) || null;
  const pics = subject => (D() && D().pictures[subject]) || [];
  const hhmm = secs => {
    secs = Math.round(secs || 0);
    const h = Math.floor(secs / 3600), m = Math.floor((secs % 3600) / 60);
    return h ? `${h}h ${String(m).padStart(2, "0")}m` : `${m}m`;
  };
  const cash = n => n == null ? "–" : money(n);
  const monogram = name => String(name || "?").split(/\s+/).filter(Boolean).slice(0, 2).map(w => w[0]).join("").toUpperCase();
  const rid = p => p + "_" + Array.from(crypto.getRandomValues(new Uint8Array(3))).map(b => b.toString(16).padStart(2, "0")).join("");
  const running = () => (D() && D().jobs || []).some(j => j.status === "waiting" || j.status === "running");
  function jobsFor(subject) { return (D() && D().jobs || []).filter(j => j.subject === subject && (j.status === "waiting" || j.status === "running")); }

  function redraw() {
    if (section !== SEC) return;
    const y = window.scrollY;
    document.getElementById("main").innerHTML = render();
    window.scrollTo(0, y);
  }

  async function load(quiet) {
    if (st.loading) return;
    st.loading = true;
    if (!quiet) redraw();
    const res = await getJson("captains");
    st.loading = false;
    if (!res.ok) { toast(res.error || "Could not load the Captains.", true); return redraw(); }
    st.data = res;
    if (st.open && !st.dirty) {
      const c = cap(st.open);
      st.draft = c ? clone(c) : st.draft;
    }
    keepPolling();
    redraw();
  }
  function keepPolling() {
    clearTimeout(st.poll);
    if (section === SEC && running()) st.poll = setTimeout(pollJobs, 3000);
  }
  async function pollJobs() {
    if (section !== SEC) return;
    const res = await getJson("media/jobs");
    if (!res.ok) return keepPolling();
    const was = running();
    D().jobs = res.jobs;
    if (was && !running()) { toast("New pictures are ready."); return load(true); }
    // pictures arrive one by one: refresh the galleries while the farm is painting
    const res2 = await getJson("captains");
    if (res2.ok) { const keep = st.data; st.data = res2; if (st.dirty) st.data.captains = keep.captains; }
    keepPolling();
    redraw();
  }

  /* ---------------------------------------------------- list (grid) -- */
  function cardPortrait(url, name, color, big) {
    return `<div class="cp-portrait${big ? " big" : ""}" style="--cp:${e(color || "#b8862b")}">${url
      ? `<img src="${e(url)}" alt="${e(name)}">` : `<span>${e(monogram(name))}</span><small>No portrait yet</small>`}</div>`;
  }
  function crest(h, size) {
    const url = (pics(h.hid)[0] && pics(h.hid).find(p => p.primary)) ? pics(h.hid).find(p => p.primary).url : h.image;
    return `<span class="cp-crest${size ? " " + size : ""}" style="--cp:${e(h.color)}" title="${e(h.name)}">${url
      ? `<img src="${e(url)}" alt="">` : e(monogram(h.name))}</span>`;
  }
  function record(c) {
    const s = (c.career && c.career.summary) || {};
    return `<div class="cp-wl"><b>${s.wins || 0}</b><small>won</small><b>${s.losses || 0}</b><small>lost</small>
      <b>${s.games || 0}</b><small>games</small><b>${hhmm(s.seconds || c.seconds)}</b><small>at sea</small></div>`;
  }
  function listView() {
    const q = st.q.trim().toLowerCase();
    const list = D().captains.filter(c => !q || (c.name + " " + c.title + " " + c.pin + " " + c.houses.map(h => h.name).join(" ")).toLowerCase().includes(q));
    const seated = D().seated || {};
    const cards = list.map(c => {
      const color = (c.houses[0] || {}).color;
      return `<article class="cp-card${c.retired ? " retired" : ""}" tabindex="0" data-cpopen="${e(c.cid)}" style="--cp:${e(color || "#b8862b")}">
        ${cardPortrait(c.portrait, c.name, color)}
        <div class="cp-plate"><b>${e(c.name)}</b><span>${e(c.title || (c.guest ? "Guest Captain" : "Captain"))}</span></div>
        <div class="cp-body">
          <div class="cp-tags">${c.guest ? `<em class="tag">Guest · no PIN</em>` : `<em class="tag pin">No. ${e(c.pin)}</em>`}
            ${c.retired ? `<em class="tag">Retired</em>` : ""}${seated[c.cid] ? `<em class="tag live">Sailing now</em>` : ""}</div>
          <div class="cp-houses">${c.houses.map(h => `${crest(h)}<span>${e(h.name)}</span>`).join("")}</div>
          ${record(c)}
          <p class="small muted">${c.last_played ? "Last sailed " + e(c.last_played) : "Not sailed yet"}</p>
        </div></article>`;
    }).join("");
    const pr = D().prompts;
    return `<section class="card"><div class="head"><h2>Captains</h2>
        <div class="row"><input type="search" data-cpq="1" placeholder="Search name, PIN or House…" value="${e(st.q)}">
        <button type="button" class="primary" data-cpnew="1">New Captain</button></div></div>
        <p class="help">Every player picks their Captain on the join screen and types the PIN. The PIN is the Captain's
        id number: their games, Houses and record all hang off it. The two guest Captains need no PIN.
        Pictures are kept in the Media Library under Captains and Houses; the starred one is shown.</p></section>
      <div class="cp-grid">${cards || `<p class="muted">No Captains match.</p>`}</div>
      <section class="card"><h2>Picture prompts</h2>
        <p class="help">Used when a Captain or House has no prompt of its own. Captain: <code>{name}</code> <code>{title}</code>.
        House: <code>{house}</code> <code>{motto_part}</code> <code>{color_word}</code>.</p>
        <div class="fields"><label class="f wide"><span>Captain portrait</span><textarea rows="4" data-cpprompt="portrait">${e(pr.portrait)}</textarea></label>
        <label class="f wide"><span>House crest</span><textarea rows="4" data-cpprompt="house">${e(pr.house)}</textarea></label></div>
        <div class="row"><button type="button" data-cpprompts="1">Save prompt templates</button></div></section>`;
  }

  /* ------------------------------------------------------ one Captain -- */
  function gallery(kind, subject, prompt, saved) {
    const list = pics(subject), jobs = jobsFor(subject);
    const waiting = jobs.reduce((n, j) => n + (j.count - j.done - j.failed), 0);
    const tiles = list.map(p => `<div class="cp-pic${p.primary ? " on" : ""}${p.enabled ? "" : " off"}">
        <button type="button" class="cp-pick" data-cppick="${e(p.id)}" title="${p.primary ? "Shown in the game" : "Show this one"}${p.nsfw ? " (NSFW)" : ""}${p.prompt ? "\n\n" + e(p.prompt) : ""}">
          <img src="${e(p.url)}" alt="" loading="lazy"></button>
        ${p.primary ? "<i>★</i>" : ""}${p.nsfw ? "<u>NSFW</u>" : ""}
        <span class="cp-tools">${p.prompt ? `<button type="button" data-cpreuse="${e(p.id)}" data-subject="${e(subject)}" title="Put this picture's prompt in the box to tweak it">✎</button>` : ""}
          <button type="button" class="cp-del" data-cpdelpic="${e(p.id)}" title="Delete this picture">✕</button></span></div>`).join("");
    const wait = Array.from({ length: waiting }, () => `<span class="cp-pic wait"><i></i></span>`).join("");
    const label = kind === "captain" ? "portrait" : "crest";
    return `<div class="cp-gallery ${kind}">${tiles}${wait}${!tiles && !wait ? `<p class="small muted">No ${label}s yet.</p>` : ""}</div>
      <label class="f wide"><span>Prompt <small class="muted">(edit and tweak; Generate uses exactly this)</small></span>
        <textarea rows="6" data-cpf="${kind === "captain" ? "prompt" : "house.prompt"}" ${kind === "house" ? `data-hid="${e(subject)}"` : ""}
          >${e((kind === "captain" ? st.draft.prompt : (st.draft.houses.find(h => h.hid === subject) || {}).prompt) || prompt)}</textarea></label>
      <div class="row"><button type="button" class="link" data-cpbase="${e(kind)}:${e(subject)}">Back to the base prompt</button></div>
      <div class="row">
        <select data-cpcount="${e(subject)}">${[1, 2, 4, 6, 8].map(n => `<option${n === 4 ? " selected" : ""}>${n}</option>`).join("")}</select>
        <button type="button" class="cp-generate" data-cpgen="${e(kind)}:${e(subject)}" ${saved ? "" : "disabled"}>${waiting ? "Painting " + waiting + "…" : "Generate " + label + "s"}</button>
        <label class="pick">Upload<input type="file" accept="image/*" data-cpup="${e(kind)}:${e(subject)}" ${saved ? "" : "disabled"}></label>
        <a href="#media" class="link" data-medialib="${e(kind)}:${e(subject)}">Open in Media Library</a>
        ${saved ? "" : `<span class="help">Save first, then add pictures.</span>`}</div>`;
  }

  function voicePicker(c) {
    const cur = c.voice_id || "";
    const row = (st.voices || []).find(v => v.id === cur);
    const opt = v => `<option value="${e(v.id)}"${v.id === cur ? " selected" : ""}>${e(v.name)}${v.lang ? " · " + e(v.lang) : ""}${v.gender ? " · " + e(v.gender) : ""}</option>`;
    const own = (st.voices || []).filter(v => v.source !== "SYSTEM"), sys = (st.voices || []).filter(v => v.source === "SYSTEM");
    const sel = st.voices ? `<select data-cpf="voice_id"><option value="">No voice yet</option>
        ${own.length ? `<optgroup label="Your voices">${own.map(opt).join("")}</optgroup>` : ""}<optgroup label="Inworld voices">${sys.map(opt).join("")}</optgroup></select>`
      : `<p class="small muted">${st.voicesErr ? e(st.voicesErr) : "Loading the Inworld voice list…"}</p>`;
    return `<label class="f"><span>Inworld voice</span>${sel}</label>
      <label class="f"><span>Voice ID</span><input type="text" data-cpf="voice_id" value="${e(cur)}" placeholder="any Inworld voice ID"></label>
      <div class="row"><input type="text" id="cptry" value="${e("I am " + (c.name || "your captain") + ", and the sea is mine.")}">
        <button type="button" data-cptry="1" ${cur ? "" : "disabled"}>${st.audio ? "Stop" : "Preview voice"}</button>
        <span class="help">${row ? e(row.description || "") : "Stored with the profile for now; not yet read aloud in play."}</span></div>`;
  }

  function houseEditor(h, saved, ports) {
    const portOpts = `<option value="">No preference</option>` + Object.entries(ports).map(([k, n]) =>
      `<option value="${e(k)}"${h.home_port === k ? " selected" : ""}>${e(n)}</option>`).join("");
    const orig = cap(st.draft.cid);
    const isSaved = saved && orig && orig.houses.some(x => x.hid === h.hid);
    const hs = ((st.draft.career || {}).houses || []).find(x => x.hid === h.hid) || {};
    return `<section class="card cp-house" style="--cp:${e(h.color)}"><div class="head">
        <h3>${crest(h, "big")} ${e(h.name || "New House")}</h3>
        <span class="small muted">${hs.games ? `${hs.wins} won · ${hs.losses} lost · ${hs.games} games · best ${cash(hs.best)}` : "No games yet"}</span></div>
      <div class="cp-house-cols"><div class="fields">
        <label class="f"><span>House name</span><input type="text" maxlength="28" data-cpf="house.name" data-hid="${e(h.hid)}" value="${e(h.name)}"></label>
        <label class="f"><span>Colour</span><input type="color" data-cpf="house.color" data-hid="${e(h.hid)}" value="${e(h.color)}"></label>
        <label class="f wide"><span>Motto</span><input type="text" maxlength="80" data-cpf="house.motto" data-hid="${e(h.hid)}" value="${e(h.motto)}"></label>
        <label class="f"><span>Favourite port</span><select data-cpf="house.home_port" data-hid="${e(h.hid)}">${portOpts}</select></label>
        <label class="cv-check"><input type="checkbox" data-cpf="house.retired" data-hid="${e(h.hid)}"${h.retired ? " checked" : ""}> Retired <small>Not offered on the join screen; its record stays.</small></label>
        <div class="row"><button type="button" class="link" data-cphdel="${e(h.hid)}">Remove this House</button></div>
      </div><div>${gallery("house", h.hid, h.prompt_shown || "", isSaved)}</div></div></section>`;
  }

  function careerView(c) {
    const k = c.career || {}, s = k.summary || {};
    const t = (n, l) => `<div class="cp-stat"><b>${n}</b><small>${l}</small></div>`;
    const tot = k.totals || {};
    const rate = s.wins + s.losses ? Math.round(100 * s.wins / (s.wins + s.losses)) + "%" : "–";
    const games = (k.games || []).map(g => `<tr class="${e(g.outcome)}"><td>${e(g.first || "")}–${e(g.last || "")}</td><td>${e(g.house || "")}</td>
        <td>${g.place ? g.place + " of " + g.players : "–"}</td><td class="num">${cash(g.worth)}</td><td>${Ranks.label(g)}</td>
        <td class="num">${g.months}</td><td class="num">${g.battles}</td><td class="num">${hhmm(g.seconds)}</td>
        <td><em class="tag ${e(g.outcome)}">${{ win: "Won", loss: "Lost", playing: "Sailing", unfinished: "Unfinished" }[g.outcome]}</em></td>
        <td class="small muted mono">${e(g.id)}</td></tr>`).join("");
    return `<section class="card"><h2>Record</h2>
      <div class="cp-stats">${t(s.games || 0, "games")}${t(s.wins || 0, "won")}${t(s.losses || 0, "lost")}${t(s.unfinished || 0, "unfinished")}
        ${t(rate, "win rate")}${t(cash(s.best), "best finish")}${t(s.months || 0, "months sailed")}${t(hhmm(s.seconds), "at the screen")}
        ${t(tot.battles || 0, "battles")}${t(tot.won || 0, "battles won")}${t(tot.wrecks || 0, "shipwrecks")}${t(tot.seizures || 0, "seizures")}</div>
      ${games ? `<div class="scroll"><table class="cp-games"><thead><tr><th>Dates</th><th>House</th><th>Place</th><th>Final worth</th><th>Rank</th>
        <th>Months</th><th>Battles</th><th>Time</th><th>Result</th><th>Game</th></tr></thead><tbody>${games}</tbody></table></div>`
        : `<p class="muted">No games recorded yet. Each game this Captain plays is added here from the Captain's Report.</p>`}
      </section>`;
  }

  function detailView() {
    const c = st.draft, orig = cap(c.cid), saved = !!orig;
    const seated = (D().seated || {})[c.cid];
    const del = st.confirmDel === c.cid;
    return `<section class="card"><div class="head">
        <button type="button" class="link" data-cpback="1">← All Captains</button>
        <div class="row">${st.dirty ? `<span class="muted">Unsaved changes</span>` : ""}
          <button type="button" data-cpdiscard="1" ${st.dirty ? "" : "disabled"}>Discard</button>
          <button type="button" class="primary" data-cpsave="1" ${st.dirty || !saved ? "" : "disabled"}>${st.busy === "save" ? "Saving…" : "Save Captain"}</button></div></div></section>
      <div class="cp-detail"><aside>${cardPortrait(saved ? orig.portrait : "", c.name, (c.houses[0] || {}).color, true)}
          <div class="cp-tags">${c.guest ? `<em class="tag">Guest · no PIN</em>` : ""}${seated ? `<em class="tag live">Sailing now</em>` : ""}</div></aside>
        <div><section class="card"><h2>${e(c.name || "New Captain")}</h2><div class="fields">
          <label class="f"><span>Name</span><input type="text" maxlength="20" data-cpf="name" value="${e(c.name)}"></label>
          <label class="f"><span>Title or nickname</span><input type="text" maxlength="40" data-cpf="title" value="${e(c.title)}" placeholder="e.g. the Iron Hand"></label>
          ${c.guest ? `<label class="f"><span>PIN</span><input type="text" value="Not needed (guest)" disabled></label>`
            : `<label class="f"><span>PIN (the Captain's id number)</span><input type="text" inputmode="numeric" maxlength="8" data-cpf="pin" value="${e(c.pin)}" autocomplete="off">
               <small class="help">4 to 8 digits, unique. Changing it keeps the whole history.</small></label>`}
          <label class="f wide"><span>Story</span><textarea rows="3" data-cpf="bio" maxlength="1200">${e(c.bio)}</textarea></label>
          ${voicePicker(c)}
          <label class="cv-check"><input type="checkbox" data-cpf="retired"${c.retired ? " checked" : ""}> Retired <small>Hidden from the join screen; the record stays.</small></label>
          <p class="small muted wide">Created ${e(c.created || "now")}${c.last_played ? " · last sailed " + e(c.last_played) : ""}</p>
        </div></section>
        <section class="card"><h2>Portrait</h2>${gallery("captain", c.cid, saved ? orig.prompt_shown : "", saved)}</section></div></div>
      <section class="card"><div class="head"><h2>Houses</h2><button type="button" data-cphadd="1">Add a House</button></div>
        <p class="help">The trading firms this Captain sails under. They choose one when they join. Generate a crest for each:
        every picture lands in the Media Library under Houses, and the starred one is shown.</p></section>
      ${c.houses.map(h => houseEditor(h, saved, D().ports)).join("")}
      ${saved ? careerView(orig) : ""}
      ${saved && !c.guest ? `<section class="card"><div class="row"><button type="button" class="${del ? "danger" : "link"}" data-cpdel="1">
        ${del ? "Click again to delete " + e(c.name) + " for good" : "Delete this Captain"}</button>
        <span class="help">Their games stay in the Captain's Report. Retiring keeps the record here too.</span></div></section>` : ""}`;
  }

  function render() {
    if (!st.data) { if (!st.loading) load(); return `<p class="muted">Loading the Captains…</p>`; }
    return `<div id="captains">${st.open ? detailView() : listView()}</div>`;
  }

  /* ------------------------------------------------------------ actions -- */
  function openCaptain(cid) {
    const c = cap(cid);
    st.open = cid; st.draft = clone(c); st.dirty = false; st.confirmDel = "";
    if (!st.voices && !st.voicesErr) loadVoices();
    redraw(); window.scrollTo(0, 0);
  }
  function newCaptain() {
    const cid = rid("c");
    st.open = cid; st.dirty = true; st.confirmDel = "";
    st.draft = { cid, pin: D().free_pin || "", name: "", title: "", bio: "", voice_id: "", prompt: "", guest: false,
                 retired: false, created: "", last_played: "", houses: [newHouse("")] };
    if (!st.voices && !st.voicesErr) loadVoices();
    redraw(); window.scrollTo(0, 0);
  }
  function newHouse(name) {
    const colors = ["#9f2f2f", "#2f6f9f", "#2f8f5f", "#b8862b", "#6f3f9f", "#1f1f1f"];
    return { hid: rid("h"), name, color: colors[Math.floor(Math.random() * colors.length)], motto: "", home_port: "", prompt: "", retired: false };
  }
  async function loadVoices() {
    const res = await getJson("voice/voices");
    if (res.ok) st.voices = res.voices; else st.voicesErr = res.error || "No Inworld voice list.";
    redraw();
  }
  async function saveCaptain() {
    st.busy = "save"; redraw();
    const res = await post("captains/save", { captain: st.draft });
    st.busy = "";
    if (!res.ok) { redraw(); toast(res.error, true); return false; }
    st.dirty = false; st.open = res.cid;
    toast(res.msg);
    await load(true);
    return true;
  }
  async function generate(kind, subject) {
    if (st.dirty && !(await saveCaptain())) return;
    const c = cap(st.open);
    if (!c) return toast("Save the Captain first.", true);
    const h = kind === "house" ? c.houses.find(x => x.hid === subject) : null;
    if (kind === "house" && !h) return toast("Save the House first.", true);
    const prompt = (kind === "captain" ? c.prompt_shown : h.prompt_shown) || "";
    if (prompt.trim().length < 20) return toast("Write a prompt first.", true);
    const sel = document.querySelector(`[data-cpcount="${subject}"]`);
    const count = sel ? +sel.value : 4;
    const res = await post("media/generate", { kind, subject, roles: [kind === "captain" ? "portrait" : "crest"], prompt,
                                                aspect: kind === "captain" ? "3:4" : "1:1", count, nsfw: "auto" });
    if (!res.ok) return toast(res.error, true);
    toast(res.msg);
    const j = await getJson("media/jobs");
    if (j.ok) D().jobs = j.jobs;
    keepPolling(); redraw();
  }
  async function upload(kind, subject, file) {
    let res;
    try {
      const r = await fetch(`/api/admin/captains/upload?kind=${kind}&subject=${subject}&name=${encodeURIComponent(file.name)}`,
        { method: "POST", headers: { "X-SeaTrader": "admin" }, body: file });
      res = await r.json();
    } catch (err) { res = { ok: false, error: "Cannot reach the game server." }; }
    if (!res.ok) return toast(res.error, true);
    toast(res.msg); load(true);
  }
  function stopAudio() { if (st.audio) { st.audio.pause(); URL.revokeObjectURL(st.audio.src); st.audio = null; } }

  function setField(el) {
    const d = el.dataset, f = d.cpf;
    let v = el.type === "checkbox" ? el.checked : el.value;
    if (f.startsWith("house.")) {
      const h = st.draft.houses.find(x => x.hid === d.hid);
      if (!h) return;
      h[f.slice(6)] = v;
    } else {
      if (f === "pin") v = String(v).replace(/\D/g, "").slice(0, 8);
      st.draft[f] = v;
    }
    st.dirty = true;
  }

  function onInput(ev) {
    if (section !== SEC) return;
    const el = ev.target, d = el.dataset;
    if (d.cpq !== undefined) { st.q = el.value; const p = el.selectionStart; redraw(); const n = document.querySelector("[data-cpq]"); if (n) { n.focus(); n.setSelectionRange(p, p); } return; }
    if (d.cpf) {
      setField(el);
      if (ev.type === "change" && (el.tagName === "SELECT" || el.type === "checkbox" || el.type === "color")) redraw();
      else { const b = document.querySelector("[data-cpsave]"); if (b) b.disabled = false; const x = document.querySelector("[data-cpdiscard]"); if (x) x.disabled = false; }
    }
    if (d.cpup && ev.type === "change" && el.files && el.files[0]) { const [k, s] = d.cpup.split(":"); upload(k, s, el.files[0]); }
  }

  async function onClick(ev) {
    if (section !== SEC) return;
    const card = ev.target.closest("[data-cpopen]");
    if (card) return openCaptain(card.dataset.cpopen);
    const el = ev.target.closest("button");
    if (!el) return;
    const d = el.dataset;
    if (d.cpnew) return newCaptain();
    if (d.cpback) {
      if (st.dirty && !confirmLeave()) return;
      st.open = null; st.draft = null; st.dirty = false; stopAudio(); redraw(); return window.scrollTo(0, 0);
    }
    if (d.cpdiscard) { st.dirty = false; const c = cap(st.open); if (!c) { st.open = null; st.draft = null; } else st.draft = clone(c); return redraw(); }
    if (d.cpsave) return saveCaptain();
    if (d.cphadd) { st.draft.houses.push(newHouse("")); st.dirty = true; return redraw(); }
    if (d.cphdel) {
      if (st.draft.houses.length < 2) return toast("A Captain needs at least one House. Retire it instead.", true);
      st.draft.houses = st.draft.houses.filter(h => h.hid !== d.cphdel); st.dirty = true; return redraw();
    }
    if (d.cpgen) { const [k, s] = d.cpgen.split(":"); return generate(k, s); }
    if (d.cpdelpic) {
      if (st.confirmPic !== d.cpdelpic) { st.confirmPic = d.cpdelpic; el.textContent = "Delete?"; el.classList.add("armed");
        setTimeout(() => { if (st.confirmPic === d.cpdelpic) { st.confirmPic = ""; redraw(); } }, 3500); return; }
      st.confirmPic = "";
      const res = await post("media/delete", { ids: [d.cpdelpic] });
      if (!res.ok) return toast(res.error, true);
      toast("Picture deleted (moved to web/media/_trash)."); return load(true);
    }
    if (d.cpreuse) {
      const pic = pics(d.subject).find(p => p.id === d.cpreuse);
      if (!pic) return;
      if (d.subject === st.draft.cid) st.draft.prompt = pic.prompt;
      else { const h = st.draft.houses.find(x => x.hid === d.subject); if (h) h.prompt = pic.prompt; }
      st.dirty = true; redraw();
      return toast("That picture's prompt is in the box. Tweak it, then Generate.");
    }
    if (d.cpbase) {
      // The template filled in for this Captain or House (as last saved); a new one starts from it anyway.
      const [k, s] = d.cpbase.split(":");
      const saved = cap(st.draft.cid), c = st.draft, h = k === "house" ? c.houses.find(x => x.hid === s) : null;
      const sh = saved && k === "house" ? saved.houses.find(x => x.hid === s) : null;
      const base = k === "captain" ? (saved && saved.prompt_base) : (sh && sh.prompt_base);
      if (k === "captain") c.prompt = base || ""; else if (h) h.prompt = base || "";
      st.dirty = true; redraw();
      return toast("Base prompt back in the box. Save or Generate to use it.");
    }
    if (d.cppick) {
      const res = await post("captains/pick", { id: d.cppick });
      if (!res.ok) return toast(res.error, true);
      toast(res.msg); return load(true);
    }
    if (d.cptry) {
      if (st.audio) { stopAudio(); return redraw(); }
      const text = (document.getElementById("cptry") || {}).value || "";
      const res = await post("voice/preview", { character: { voice_id: st.draft.voice_id }, text, model_id: CFG.voice.model_id, temperature: CFG.voice.temperature });
      if (!res.ok) return toast(res.error, true);
      st.audio = new Audio(URL.createObjectURL(res.audio));
      st.audio.onended = () => { stopAudio(); redraw(); };
      st.audio.play().catch(() => { stopAudio(); redraw(); });
      return redraw();
    }
    if (d.cpdel) {
      if (st.confirmDel !== st.open) { st.confirmDel = st.open; return redraw(); }
      const res = await post("captains/delete", { cid: st.open });
      if (!res.ok) return toast(res.error, true);
      toast(res.msg); st.open = null; st.draft = null; st.dirty = false; st.confirmDel = ""; return load(true);
    }
    if (d.cpprompts) {
      const p = {};
      document.querySelectorAll("[data-cpprompt]").forEach(t => { p[t.dataset.cpprompt] = t.value; });
      const res = await post("captains/prompts", { prompts: p });
      if (!res.ok) return toast(res.error, true);
      toast(res.msg); return load(true);
    }
  }
  let leaveWarned = false;
  function confirmLeave() {
    if (leaveWarned) { leaveWarned = false; return true; }
    leaveWarned = true; toast("Unsaved changes to this Captain. Click again to leave without saving.", true);
    setTimeout(() => { leaveWarned = false; }, 4000);
    return false;
  }

  document.addEventListener("DOMContentLoaded", () => {
    const m = document.getElementById("main");
    m.addEventListener("input", onInput);
    m.addEventListener("change", onInput);
    m.addEventListener("click", onClick);
    m.addEventListener("keydown", ev => {
      const card = ev.target.closest && ev.target.closest("[data-cpopen]");
      if (card && ev.target === card && (ev.key === "Enter" || ev.key === " ")) { ev.preventDefault(); card.click(); }
    });
  });

  window.SeaTraderCaptains = {
    render,
    enter() { load(!!st.data); },
    leave() { stopAudio(); clearTimeout(st.poll); },
    /* For the Media Library's "Generate" form: the prompt this Captain or House would use. */
    promptFor(kind, subject) {
      if (!st.data) { load(true); return ""; }
      for (const c of st.data.captains) {
        if (kind === "captain" && c.cid === subject) return c.prompt_shown || "";
        const h = c.houses.find(x => x.hid === subject);
        if (kind === "house" && h) return h.prompt_shown || "";
      }
      return "";
    },
  };
})();
