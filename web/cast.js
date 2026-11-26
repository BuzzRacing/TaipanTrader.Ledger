/* SeaTrader Admin: Cast & Voices.
   The characters who read the game aloud: profile cards, Inworld voices,
   auditions, and who reads which line. Edits go into CFG like every other
   Admin page and are applied with "Save & apply". The Inworld key is saved
   straight away (it is never part of the settings file). */
(function () {
  "use strict";

  const st = { open: null, voices: null, voicesErr: "", loading: false, audio: null, playing: "", generating: "" };
  const $m = () => document.getElementById("main");
  const e = s => esc(s);
  const PLACE = {
    n: "4", qty: "20", port: "Manila", dest: "Manila", origin: "Hong Kong", good: "Silk", good_lower: "silk",
    cost: "$4,200", gain: "$5,100", amount: "$2,000", fine: "$3,600", lost: "$1,800", booty: "$1,200",
    price: "$600", value: "$4,500", debt: "$5,000", cash: "$3,500", worth: "$212,000", name: "Lucky Star",
    ship: "lorcha", weather: "through squalls", months: "6", rounds: "3", s: "s", enemy: "pirate junks",
    orders: "fight", rate: "6", free: "12", what: "The bank", firm: "Noble House", points: "34", years: "5",
    list: "1, 2, 3, 5", how: "foundered in the storm", contraband: "opium", Contraband: "Opium",
  };

  /* --------------------------------------------------------- helpers -- */
  const C = () => CFG.characters;
  const V = () => CFG.voice;
  const S = () => A.cast;
  function shown(cid) {
    const c = C()[cid] || {};
    // Her Brand name applies while the role is still hers; once Admin > Brand casts someone else as the
    // moneylender or pirate queen, the name there is the other woman's, so this card shows her own.
    const played = c.brand_link ? CFG.brand[c.brand_link + "_cast"] : "";
    return c.brand_link && CFG.brand[c.brand_link] && (!played || played === c.brand_link) ? CFG.brand[c.brand_link] : (c.name || cid);
  }
  function speaker(key) {
    const lines = V().lines, grp = key.split(".")[0];
    let who = key in lines ? lines[key] : defaultSpeaker(key);
    if (who && !C()[who]) who = C()[S().prefix_defaults[grp]] ? S().prefix_defaults[grp] : "";
    return who;
  }
  function defaultSpeaker(key) {
    const grp = key.split(".")[0];
    const d = S().line_defaults;      // a default of "" means silent, not "the group's usual reader"
    return key in d ? d[key] : (S().prefix_defaults[grp] || "");
  }
  function sample(tpl) {
    const home = (CFG.ports[CFG.rules.game.home] || {}).name || "Hong Kong";
    const tok = Object.assign({}, PLACE, { lender: CFG.brand.lender, pirate: CFG.brand.pirate, bank: CFG.brand.bank,
                                           winner: CFG.brand.winner, home });
    return String(tpl || "").replace(/\{(\w+)\}/g, (m, k) => tok[k] != null ? tok[k] : "");
  }
  /* What the voice says for a line: the spoken version set here, the stock one, or the line as shown. */
  const AMOUNTS = ["n", "qty", "cost", "cash", "gain", "amount", "rate", "value", "months", "price", "free", "debt",
                   "lost", "fine", "rounds", "booty", "points", "worth", "years", "list"];
  function sayMap() { if (!V().say) V().say = {}; return V().say; }
  function sayValue(key) { const m = sayMap(); return key in m ? m[key] : (S().say_defaults[key] || ""); }
  function spokenTpl(key, tpl) { return sayValue(key) || tpl; }
  function hasAmounts(tpl) { return AMOUNTS.some(a => String(tpl).includes("{" + a + "}")); }
  function linesFor(cid) { return S().lines.filter(([k]) => speaker(k) === cid); }
  function monogram(cid) {
    return shown(cid).replace(/[“”"']/g, "").split(/\s+/).filter(Boolean).slice(0, 2).map(w => w[0]).join("").toUpperCase();
  }
  function voiceRow(id) { return (st.voices || []).find(v => v.id === id); }
  function voiceLabel(id) {
    if (!id) return "No voice";
    const v = voiceRow(id);
    return v ? v.name : id;
  }
  function changed() { refreshDirty(); }

  /* ------------------------------------------------------------ render -- */
  function portrait(cid, big) {
    const c = C()[cid];
    return `<div class="cv-portrait${big ? " big" : ""}${st.generating === cid ? " generating" : ""}" style="--cv:${e(c.color)}">${c.portrait
      ? `<img src="${e(c.portrait)}" alt="${e(shown(cid))}">`
      : `<span>${e(monogram(cid))}</span><small>No portrait yet</small>`}
      ${st.generating === cid ? '<span class="cv-portrait-wait"><i></i>Painting on the AI farm…</span>' : ""}</div>`;
  }
  function bars(c) {
    return `<div class="cv-bars">${S().stat_keys.map(k => `<div><span>${e(S().stat_labels[k])}</span>
      <i><b style="width:${(c.stats[k] || 0) * 10}%"></b></i><em>${c.stats[k] || 0}</em></div>`).join("")}</div>`;
  }
  function playBtn(cid, text, label) {
    const id = cid + "|" + (text || "");
    const on = st.playing === id;
    return `<button type="button" class="cv-play${on ? " on" : ""}" data-cvplay="${e(cid)}" data-cvtext="${e(text || "")}">${on ? "■ Stop" : "▶ " + e(label || "Audition")}</button>`;
  }
  function voiceWarn(id) {
    if (!id) return `<span class="cv-warn">no voice set</span>`;
    if (st.voices && !voiceRow(id)) return `<span class="cv-warn" title="Not in this Inworld workspace's voice list">not found in Inworld</span>`;
    return "";
  }

  function keyCard() {
    const s = S(), k = s.key, v = V();
    const who = k.has_key ? (k.source === "admin" ? `Using the key saved on this page (ending <b>${e(k.tail)}</b>).`
      : `Using <code>INWORLD_API_KEY</code> from this computer (ending <b>${e(k.tail)}</b>), the same key as GrumpyRobot and Sector Says What.`)
      : `<b class="err">No Inworld key yet.</b> Paste the Base64 API key from the Inworld dashboard, or set <code>INWORLD_API_KEY</code> on the computer running the game.`;
    const chk = (k2, label, help) => `<label class="cv-check"><input type="checkbox" data-cvv="${k2}" ${v[k2] ? "checked" : ""}><span><b>${e(label)}</b>${help ? `<small>${e(help)}</small>` : ""}</span></label>`;
    const castOpts = (sel, none) => `<option value="">${e(none)}</option>` + Object.keys(C()).map(cid =>
      `<option value="${e(cid)}" ${sel === cid ? "selected" : ""}>${e(shown(cid))}</option>`).join("");
    const voicesLine = st.loading ? "Fetching the voice list from Inworld…"
      : st.voicesErr ? `<span class="err">${e(st.voicesErr)}</span>`
      : st.voices ? `${st.voices.length} Inworld voices available, ${st.voices.filter(x => x.source !== "SYSTEM").length} of them your own.` : "";
    const stx = s.stats;
    return `<section class="card cv-conn">
      <div class="cv-conn-top"><div><h2>Inworld connection</h2><p class="${k.has_key ? "ok" : ""}">${who}</p></div>
        <span class="cv-led ${k.has_key ? "on" : ""}">${k.has_key ? "Connected" : "Not set"}</span></div>
      <div class="row"><input type="password" id="cvkey" placeholder="Paste a new API key" autocomplete="off">
        <button type="button" data-cvkey="save">Save key</button>
        ${k.source === "admin" ? `<button type="button" class="link" data-cvkey="remove">remove saved key</button>` : ""}</div>
      <p class="help">The key is kept in <code>config/voice_key.json</code>, which is never uploaded to GitHub. It is used only by the game server; player screens never see it.</p>
      <div class="cv-cols">
        <div>${chk("enabled", "Voices on", "Switch every voice off without losing any settings.")}
          <div class="f"><label><span>Voice model</span></label><select data-cvv="model_id">${s.models.map(m =>
            `<option value="${e(m[0])}" ${v.model_id === m[0] ? "selected" : ""}>${e(m[1])}</option>`).join("")}</select>
            <small>TTS-2 Flash is quickest and cheapest. Full TTS-2 also follows each character's delivery note.</small></div>
          <div class="f"><label><span>Expressiveness (temperature)</span><b>${Number(v.temperature).toFixed(2)}</b></label>
            <input type="range" min="0.2" max="2" step="0.05" value="${v.temperature}" data-cvv="temperature"></div></div>
        <div><h3>Read aloud</h3>${chk("read_log", "Captain's log", "Each month's report, on the player's own screen.")}
          ${chk("read_confirmations", "Confirmations", "Trades, loans, repairs, sailing orders.")}
          ${chk("read_errors", "Rule messages", "When something is not allowed.")}
          ${chk("read_news_board", "News on the harbor board", "New headlines, as they arrive.")}
          ${chk("read_news_players", "News on player screens", "Best left off when a harbor board is running.")}
          <div class="f"><label><span>Reads news you post from Live Game</span></label><select data-cvv="custom_news">${castOpts(v.custom_news, "Nobody (silent)")}</select></div></div>
        <div><h3>Saved clips</h3><p>${s.cache.clips} lines saved (${s.cache.mb} MB). A line is paid for once, then replayed from here for free. Saved lines are kept for good.</p>
          <p class="muted small">Since the server started: ${stx.synth_calls} lines made, ${stx.synth_chars.toLocaleString()} characters sent, ${stx.cache_hits} replays.</p>
          ${stx.last_error ? `<p class="err small">Last problem: ${e(stx.last_error)}</p>` : ""}
          <div class="row"><button type="button" data-cvcache="1" title="Moves them to cache\\voice_cleared; nothing is deleted">Clear saved clips</button></div>
          <h3>Voices</h3><p class="small">${voicesLine}</p>
          <div class="row"><button type="button" data-cvvoices="1" ${k.has_key ? "" : "disabled"}>Refresh voice list</button></div></div>
      </div></section>`;
  }

  function grid() {
    const cards = Object.keys(C()).map(cid => {
      const c = C()[cid];
      return `<article class="cv-card" data-cvopen="${e(cid)}" style="--cv:${e(c.color)}" tabindex="0">
        ${portrait(cid)}
        <div class="cv-plate"><b>${e(shown(cid))}</b><span>${e(c.title)}</span></div>
        <div class="cv-body">
          <div class="cv-voice"><span>🎙 ${e(voiceLabel(c.voice_id))}</span>${voiceWarn(c.voice_id)}</div>
          <q>${e(c.catchphrase)}</q>
          ${bars(c)}
          <div class="cv-foot">${playBtn(cid, c.catchphrase, "Hear")}<small>${linesFor(cid).length === 1 ? "1 line" : linesFor(cid).length + " lines"}</small></div>
        </div></article>`;
    }).join("");
    return `<section class="cv-grid">${cards}
      <article class="cv-card cv-new"><div><h3>New character</h3><p class="help">A short key: lower-case letters, digits and _.</p>
        <input type="text" id="cvnewkey" placeholder="e.g. harbourmaster" maxlength="24"><button type="button" data-cvadd="1">Add to the cast</button></div></article>
    </section>`;
  }

  function whoReads() {
    const order = Object.keys(S().groups);
    const opts = (key) => {
      const cur = speaker(key), def = defaultSpeaker(key);
      return `<option value="" ${cur === "" ? "selected" : ""}>Silent</option>` + Object.keys(C()).map(cid =>
        `<option value="${e(cid)}" ${cur === cid ? "selected" : ""}>${e(shown(cid))}${cid === def ? " (default)" : ""}</option>`).join("");
    };
    return `<section class="card"><h2>Who reads what</h2>
      <p class="help">Every line the game can say, and the character who says it. Lines are shown with example names and amounts.
        Under each line is what the voice actually says. Lines with amounts are spoken without the numbers, so each is paid for once
        and then replayed for free; the screen still shows the full line. Clear a box to have that line read exactly as shown.</p>
      ${order.map(g => {
        const rows = S().lines.filter(([k]) => k.split(".")[0] === g);
        return `<details class="cv-lines" ${g === "l" ? "open" : ""}><summary>${e(S().groups[g])} <span class="muted">(${rows.length})</span></summary>
          <div class="scroll"><table><tbody>${rows.map(([k, t]) => {
            const who = speaker(k);
            const said = spokenTpl(k, t), costly = hasAmounts(said);
            return `<tr><td class="mono small">${e(k)}</td><td>${e(sample(t))}
                <input type="text" class="cv-say" data-cvsay="${e(k)}" value="${e(sayValue(k))}" maxlength="400"
                  placeholder="Spoken: read exactly as shown" title="What the voice says"
                  style="display:block;width:100%;margin-top:4px;font-style:italic">
                ${costly ? `<small class="muted">Says amounts aloud, so each different amount is a new paid line.</small>` : ""}</td>
              <td><span class="chip" style="background:${who ? e(C()[who].color) : "transparent"}"></span><select data-cvline="${e(k)}">${opts(k)}</select></td>
              <td>${who ? playBtn(who, sample(said), "") : ""}</td></tr>`;
          }).join("")}</tbody></table></div></details>`;
      }).join("")}</section>`;
  }

  function overview() {
    return head("Cast & Voices", "The characters who read the game aloud. Each has an Inworld voice and a profile card. " +
      "Pick a card to edit it; Save & apply when you are done. Auditions use your current, unsaved choices.") +
      keyCard() + grid() + whoReads();
  }

  /* The profile shows her voice; choosing one is done on the Voice Library page, where every voice can be heard. */
  function voicePicker(c) {
    const row = voiceRow(c.voice_id);
    return `<div class="f wide"><label><span>Inworld voice</span>${voiceWarn(c.voice_id)}</label>
        <p class="cv-hervoice"><b>🎙 ${e(voiceLabel(c.voice_id))}</b>${row && row.description ? ` <span class="muted">${e(row.description)}</span>` : ""}</p>
        <div class="row"><button type="button" data-cvlib="1">Change her voice in the Voice Library</button></div></div>`;
  }

  function detail(cid) {
    const c = C()[cid];
    const fld = (k, label, attrs, help) => `<div class="f"><label><span>${e(label)}</span></label><input type="text" data-cf="${k}" value="${e(c[k])}" ${attrs || ""}>${help ? `<small>${e(help)}</small>` : ""}</div>`;
    const area = (k, label, rows, help, cls) => `<div class="f wide"><label><span>${e(label)}</span></label><textarea data-cf="${k}" rows="${rows}" ${cls ? `class="${cls}"` : ""}>${e(c[k])}</textarea>${help ? `<small>${e(help)}</small>` : ""}</div>`;
    const ports = `<option value="">At sea / nowhere</option>` + Object.keys(CFG.ports).map(p =>
      `<option value="${e(p)}" ${c.home_port === p ? "selected" : ""}>${e(CFG.ports[p].name)}</option>`).join("");
    const links = [["", "Its own name"], ["lender", "Brand: moneylender (" + CFG.brand.lender + ")"],
                   ["pirate", "Brand: pirate queen (" + CFG.brand.pirate + ")"], ["bank", "Brand: bank (" + CFG.brand.bank + ")"]];
    const mine = linesFor(cid);
    const lineOpts = mine.map(([k, t]) => { const said = sample(spokenTpl(k, t));
      return `<option value="${e(said)}">${e(said.slice(0, 90))}</option>`; }).join("");
    const steer = !V().model_id.startsWith("inworld-tts-2") || V().model_id.includes("flash");
    return `<div class="head"><h1>${e(shown(cid))}</h1><button type="button" data-cvback="1">← All characters</button></div>
      <p class="intro">${e(c.title)}${c.origin ? " · from " + e(c.origin) : ""}. Changes apply with Save &amp; apply.</p>
      <div class="cv-detail" style="--cv:${e(c.color)}">
        <aside>${portrait(cid, true)}
          <div class="row"><label class="pick cv-pick">Choose portrait<input type="file" accept="image/*" data-up="characters.${e(cid)}.portrait"></label>
            ${c.portrait ? `<button type="button" class="link" data-cvnoimg="1">remove</button>` : ""}</div>
          <p class="help">3:4 works best (for example 1536 × 2048). Make one with the prompt below.</p>
          ${bars(c)}
          <div class="cv-stats-edit">${S().stat_keys.map(k => `<label><span>${e(S().stat_labels[k])}</span>
            <input type="range" min="0" max="10" step="1" value="${c.stats[k]}" data-cs="${k}"></label>`).join("")}</div>
        </aside>
        <div class="cv-main">
          <section class="card"><h2>Who they are</h2><div class="fields">
            ${fld("name", "Name", 'maxlength="60"', c.brand_link ? "Shown as the Brand name while linked." : "")}
            ${fld("title", "Title", 'maxlength="80"')}
            <div class="f"><label><span>Name comes from</span></label><select data-cf="brand_link">${links.map(([v, l]) => `<option value="${v}" ${c.brand_link === v ? "selected" : ""}>${e(l)}</option>`).join("")}</select></div>
            <div class="f"><label><span>Age</span></label><input type="number" min="18" max="150" data-cf="age" value="${e(c.age)}"></div>
            ${fld("origin", "Born in", 'maxlength="60"')}
            <div class="f"><label><span>Home port</span></label><select data-cf="home_port">${ports}</select></div>
            <div class="f"><label><span>Colour</span></label><div class="color"><input type="color" data-cf="color" value="${e(c.color)}"></div><small>Used for their speech badge.</small></div>
          </div></section>
          <section class="card"><h2>Voice</h2><div class="fields">
            ${voicePicker(c)}
            <div class="f"><label><span>Speaking speed</span><b>${Number(c.speaking_rate).toFixed(2)}×</b></label><input type="range" min="0.5" max="1.5" step="0.02" value="${c.speaking_rate}" data-cf="speaking_rate"></div>
            <div class="f"><label><span>Delivery note</span></label><input type="text" data-cf="delivery" value="${e(c.delivery)}" maxlength="200">
              <small>${steer ? "Only full TTS-2 follows this; the current model ignores it." : "Sent with every line, in square brackets, to steer the performance."}</small></div>
            <div class="f wide cv-audition"><label><span>Audition</span></label>
              <textarea id="cvtry" rows="2">${e(c.catchphrase)}</textarea>
              <div class="row"><button type="button" class="cv-play" data-cvtry="${e(cid)}">${st.playing === cid + "|try" ? "■ Stop" : "▶ Play this"}</button>
                ${mine.length ? `<select id="cvline">${lineOpts}</select><button type="button" data-cvtryline="${e(cid)}">▶ Play their line</button>` : ""}</div></div>
          </div></section>
          <section class="card"><h2>Profile</h2><div class="fields">
            ${area("catchphrase", "Catchphrase", 2, "Also the default audition line.")}
            ${area("bio", "Story", 5)}
            ${area("quirk", "Quirk", 2)}${area("vice", "Weakness", 2)}${area("secret", "Secret", 2, "Shown only here, on the Admin page.")}
          </div></section>
          <section class="card"><h2>Portrait prompt</h2>
            <p class="help">This is the one place this persona's look is edited. It is sent directly to the AI farm on .213, and the identity (everything before the costume: face, age, origin, setting) also carries into the portrait and wallpaper pictures. Taipan Trader makes fully dressed, family-friendly pictures only.</p>
            <textarea data-cf="portrait_prompt" rows="5" class="code">${e(c.portrait_prompt)}</textarea>
            <div class="row"><button type="button" class="cv-generate" data-cvgenerate="1" ${st.generating ? "disabled" : ""}>
              ${st.generating === cid ? "Painting portrait…" : "Generate new portrait"}</button>
              <span class="help">The finished image becomes this character's portrait. Save &amp; apply to keep it.</span></div></section>
          <section class="card"><h2>Lines ${e(shown(cid))} reads</h2>
            ${mine.length ? `<ul class="cv-mylines">${mine.map(([k, t]) => `<li><code>${e(k)}</code> ${e(sample(t))}</li>`).join("")}</ul>`
              : `<p class="muted">None yet. Give them lines under Who reads what.</p>`}
            <p class="help">Change who reads a line on the main Cast &amp; Voices page.</p></section>
          <div class="row"><button type="button" class="danger" data-cvdel="${e(cid)}">Remove from the cast</button></div>
        </div></div>`;
  }

  function render() {
    if (st.open && !C()[st.open]) st.open = null;
    if (!st.voices && !st.loading && !st.voicesErr && S().key.has_key) loadVoices(false);
    return (typeof voiceTabs === "function" ? voiceTabs("cast") : "") + `<div id="cast">${st.open ? detail(st.open) : overview()}</div>`;
  }
  function redraw() {
    const m = $m();
    if (section !== "cast" || !m) return;
    const y = window.scrollY;
    m.innerHTML = render();
    window.scrollTo(0, y);
  }

  /* -------------------------------------------------------------- server -- */
  async function loadVoices(force) {
    st.loading = true;
    let res;
    try { res = await (await fetch("/api/admin/voice/voices" + (force ? "?force=1" : ""))).json(); }
    catch (err) { res = { ok: false, error: "Cannot reach the game server." }; }
    st.loading = false;
    st.voices = res.ok ? res.voices : st.voices;
    st.voicesErr = res.ok ? "" : res.error;
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
  async function play(cid, text, id) {
    if (st.playing === id) { stop(); return redraw(); }
    stop();
    if (!text.trim()) return toast("Write something for them to say.", true);
    st.playing = id;
    redraw();
    const res = await post("voice/preview", { character: C()[cid], text, model_id: V().model_id, temperature: V().temperature });
    if (st.playing !== id) return;
    if (!res.ok) { st.playing = ""; redraw(); return toast(res.error, true); }
    const a = new Audio(URL.createObjectURL(res.audio));
    st.audio = a;
    a.onended = () => { if (st.audio === a) { stop(); redraw(); } };
    a.play().catch(() => { stop(); redraw(); });
  }
  async function refreshStatus(res) {
    if (res && res.key) Object.assign(A.cast, { key: res.key, cache: res.cache, stats: res.stats });
    redraw();
  }

  /* -------------------------------------------------------------- events -- */
  function onInput(ev) {
    if (section !== "cast") return;
    const el = ev.target, d = el.dataset;
    if (d.cf && st.open) {
      const c = C()[st.open];
      let v = el.value;
      if (d.cf === "age") { v = parseInt(v, 10); el.classList.toggle("bad", !(v >= 18 && v <= 150)); if (!(v >= 18 && v <= 150)) return; }
      if (d.cf === "speaking_rate") { v = Number(v); const b = el.parentNode.querySelector("label b"); if (b) b.textContent = v.toFixed(2) + "×"; }
      c[d.cf] = v;
      if (["name", "brand_link", "color"].includes(d.cf) && ev.type === "change") redraw();
      return changed();
    }
    if (d.cs && st.open) { C()[st.open].stats[d.cs] = parseInt(el.value, 10); if (ev.type === "change") redraw(); return changed(); }
    if (d.cvv) {
      const k = d.cvv;
      V()[k] = el.type === "checkbox" ? el.checked : k === "temperature" ? Number(el.value) : el.value;
      if (k === "temperature") { const b = el.parentNode.querySelector("label b"); if (b) b.textContent = Number(el.value).toFixed(2); }
      if (ev.type === "change" && k === "model_id") redraw();
      return changed();
    }
    if (d.cvsay) {
      const key = d.cvsay, v = el.value.replace(/\s+/g, " ").trim();
      if (v === (S().say_defaults[key] || "")) delete sayMap()[key]; else sayMap()[key] = v;
      if (ev.type === "change") redraw();
      return changed();
    }
    if (d.cvline) {
      const key = d.cvline, v = el.value;
      if (v === defaultSpeaker(key)) delete V().lines[key]; else V().lines[key] = v;
      if (ev.type === "change") redraw();
      return changed();
    }
  }

  async function onClick(ev) {
    if (section !== "cast") return;
    const el = ev.target.closest("[data-cvopen], button");
    if (!el) return;
    const d = el.dataset;
    if (d.cvplay !== undefined) {
      ev.stopPropagation();
      return play(d.cvplay, d.cvtext || C()[d.cvplay].catchphrase, d.cvplay + "|" + (d.cvtext || ""));
    }
    if (d.cvopen && !ev.target.closest("button, input")) { st.open = d.cvopen; stop(); redraw(); return window.scrollTo(0, 0); }
    if (d.cvlib) { stop(); return go("voices"); }
    if (d.cvback) { st.open = null; stop(); redraw(); return window.scrollTo(0, 0); }
    if (d.cvtry) return play(d.cvtry, document.getElementById("cvtry").value, d.cvtry + "|try");
    if (d.cvtryline) return play(d.cvtryline, document.getElementById("cvline").value, d.cvtryline + "|line");
    if (d.cvnoimg) { C()[st.open].portrait = ""; changed(); return redraw(); }
    if (d.cvgenerate) {
      const cid = st.open, prompt = (C()[cid].portrait_prompt || "").trim();
      if (!prompt) return toast("Write a portrait prompt first.", true);
      st.generating = cid;
      redraw();
      const res = await post("imagegen/portrait", { character: cid, prompt });
      st.generating = "";
      if (!res.ok) { redraw(); return toast(res.error, true); }
      if (C()[cid]) C()[cid].portrait = res.url;
      changed();
      redraw();
      toast(res.msg);
      return;
    }
    if (d.cvkey) {
      const key = d.cvkey === "remove" ? "" : (document.getElementById("cvkey").value || "").trim();
      if (d.cvkey === "save" && !key) return toast("Paste the key first.", true);
      const res = await post("voice/key", { key });
      toast(res.ok ? res.msg : res.error, !res.ok);
      if (res.ok) { st.voices = null; st.voicesErr = ""; refreshStatus(res); }
      return;
    }
    if (d.cvcache) {
      if (!d.cvarmed) { d.cvarmed = "1"; el.textContent = "Click again to clear"; setTimeout(() => { if (el.isConnected) { delete d.cvarmed; el.textContent = "Clear saved clips"; } }, 3500); return; }
      const res = await post("voice/clear_cache", {});
      toast(res.ok ? res.msg : res.error, !res.ok);
      return refreshStatus(res);
    }
    if (d.cvvoices) return loadVoices(true);
    if (d.cvadd) {
      const key = (document.getElementById("cvnewkey").value || "").trim().toLowerCase();
      if (!/^[a-z][a-z0-9_]{0,23}$/.test(key)) return toast("Keys start with a letter and use only a-z, 0-9 and _.", true);
      if (C()[key]) return toast("That key is already used.", true);
      C()[key] = { name: key.charAt(0).toUpperCase() + key.slice(1).replace(/_/g, " "), title: "", brand_link: "", age: 35,
        origin: "", home_port: "", color: "#" + Math.floor(0x404040 + Math.random() * 0x9f9f9f).toString(16).padStart(6, "0").slice(0, 6),
        portrait: "", voice_id: "", speaking_rate: 1.0, delivery: "", catchphrase: "", bio: "", quirk: "", vice: "", secret: "",
        stats: { cunning: 5, nerve: 5, charm: 5, greed: 5 }, portrait_prompt: "" };
      st.open = key;
      changed();
      redraw();
      return window.scrollTo(0, 0);
    }
    if (d.cvdel) {
      if (Object.keys(C()).length < 2) return toast("The cast needs at least one character.", true);
      if (!d.cvarmed) { d.cvarmed = "1"; el.textContent = "Click again to remove"; setTimeout(() => { if (el.isConnected) { delete d.cvarmed; el.textContent = "Remove from the cast"; } }, 3500); return; }
      const cid = d.cvdel;
      delete C()[cid];
      Object.keys(V().lines).forEach(k => { if (V().lines[k] === cid) delete V().lines[k]; });
      if (V().custom_news === cid) V().custom_news = "";
      st.open = null;
      changed();
      redraw();
      return toast("Removed. Their lines go back to the usual readers. Save & apply to keep it.");
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    const m = $m();
    m.addEventListener("input", onInput);
    m.addEventListener("change", onInput);
    m.addEventListener("click", onClick);
    m.addEventListener("keydown", ev => {
      const card = ev.target.closest && ev.target.closest("[data-cvopen]");
      if (card && ev.target === card && (ev.key === "Enter" || ev.key === " ")) { ev.preventDefault(); card.click(); }
    });
  });

  window.SeaTraderCast = {
    render, sectionChanged: saved => JSON.stringify(CFG.characters) !== JSON.stringify(saved.characters) ||
      JSON.stringify(CFG.voice) !== JSON.stringify(saved.voice),
    leave: () => { stop(); },
  };
})();
