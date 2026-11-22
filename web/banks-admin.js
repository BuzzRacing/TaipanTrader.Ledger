/* Crimson Ledger Admin: Language & Text > Dialogue Banks (22 Nov 2026).
   Every bank of dialogue the game, Dashboard, Table and Manual pull in, listed by persona or story, with each
   line shown as a spicy / clean pair and audited (no clean twin, {names} that do not match, duplicates, long
   spoken lines, thin banks). Server side: banks.py (GET /api/admin/banks, POST /api/admin/banks/<op>).
   Slice 2: edit, add, remove (retire), restore and reset a line. A change is saved to config/banks/ and goes live
   in the game at once (decision 22 Nov 2026); it does not wait for Save & apply. Every line keeps its key for good. */
(function () {
  "use strict";

  const st = {
    data: null, err: "", loading: false, off: false,
    owner: "", surface: "", q: "", issues: false, thin: false, thinN: 5, written: false, singles: false,
    open: new Set(), edit: null, arm: "", voiceOpen: false,
    gen: { busy: "", msg: "", err: "", opts: {}, edits: {}, derr: {}, models: [], open: false, key: "" },
  };
  const e = s => esc(s);
  const here = () => section === "banks";
  const SURF = { game: "Game", dashboard: "Dashboard", table: "Table", manual: "Manual" };
  const FLAG = {
    no_clean: ["No clean twin", "Family-friendly screens show the spicy wording for this line."],
    fields: ["{names} differ", "The spicy and clean wording use different {names}."],
    dup: ["Duplicate", "The same wording appears earlier in this bank."],
    long: ["Long", "A long spoken line costs more to record."],
    empty: ["Empty", "This line has no wording."],
  };
  const field = s => e(s).replace(/\{(\w+)\}/g, '<code class="bk-f">{$1}</code>');
  const pct = (a, b) => b ? Math.round(100 * a / b) : 100;
  const plural = (n, w) => n + " " + w + (n === 1 ? "" : "s");

  async function load(quiet) {
    st.loading = !quiet;
    let res, status = 0;
    try { const r = await fetch("/api/admin/banks"); status = r.status; res = await r.json(); }
    catch (err) { res = { ok: false, error: "Cannot reach the game server." }; }
    st.loading = false;
    if (res.ok) { st.data = res; st.err = ""; }
    else if (status === 404) st.off = true;
    else st.err = res.error || "Could not read the dialogue banks.";
    redraw();
  }

  async function post(op, body) {
    try {
      const r = await fetch("/api/admin/banks/" + op, { method: "POST", headers: { "X-SeaTrader": "admin" }, body: JSON.stringify(body) });
      return await r.json();
    } catch (err) { return { ok: false, error: "Cannot reach the game server." }; }
  }
  async function change(op, body) {
    if (st.edit) { st.edit.busy = true; st.edit.err = ""; redrawLists(); }
    const res = await post(op, body);
    if (!res.ok) {
      if (st.edit) { st.edit.busy = false; st.edit.err = res.error || "That change could not be saved."; redrawLists(); }
      else { st.err = ""; note(res.error || "That change could not be saved."); }
      return;
    }
    st.edit = null; st.arm = "";
    await load(true);
    note("Saved. The game is using it now.");
  }
  function note(msg) {
    const t = document.getElementById("toast");
    if (t) { t.textContent = msg; t.classList.add("show"); setTimeout(() => t.classList.remove("show"), 3500); }
  }

  /* ------------------------------------------------------------ filter -- */
  function matches(b) {
    if (st.surface && b.surface !== st.surface) return false;
    if (!st.written && b.kind === "written") return false;
    if (st.issues && !b.issues) return false;
    if (st.thin && b.active >= st.thinN) return false;
    const q = st.q.trim().toLowerCase();
    if (q && !(b.id.toLowerCase().includes(q) || b.owner_name.toLowerCase().includes(q) ||
      b.lines.some(l => l.spicy.toLowerCase().includes(q) || l.clean.toLowerCase().includes(q)))) return false;
    return true;
  }
  function grouped() {
    const by = new Map();
    for (const b of st.data.banks) {
      if (!matches(b)) continue;
      if (!by.has(b.owner)) by.set(b.owner, []);
      by.get(b.owner).push(b);
    }
    return by;
  }

  /* -------------------------------------------------------------- draw -- */
  const stat = (n, label, warn) => `<div class="bk-stat${warn ? " warn" : ""}"><b>${e(n)}</b><span>${e(label)}</span></div>`;

  function summary() {
    const s = st.data.summary;
    return `<div class="bk-summary">${stat(s.banks, "banks")}${stat(s.lines, "lines")}
      ${stat(pct(s.twins, s.lines) + "%", "have a clean twin", s.twins < s.lines)}${stat(s.issues, "lines flagged", s.issues > 0)}
      ${s.edited || s.added || s.retired ? stat(s.edited, "edited") + stat(s.added, "added") + stat(s.retired, "removed") : ""}
      ${st.data.surfaces.map(x => stat(x.lines, x.name)).join("")}</div>`;
  }
  function voiceCard() {
    const now = st.data.voice_now;
    return `<details class="bk-voice" data-bkd="voice" ${st.voiceOpen ? "open" : ""}><summary>How each screen speaks today</summary>
      <p class="muted small">Voices are paid for only the first time a line is heard, then replayed free from the cache. Open a spoken bank
      to set its <b>Spoken</b> mode and a cap on new recordings per game; with nothing set a bank behaves as described here.</p>
      <table class="bk-t"><tbody>${st.data.surfaces.map(x => `<tr><th>${e(x.name)}</th><td>${e(now[x.id] || "")}</td></tr>`).join("")}</tbody></table></details>`;
  }
  function controls() {
    const chips = [["", "All"]].concat(st.data.surfaces.map(x => [x.id, x.name]));
    return `<div class="bk-bar">
      <div class="bk-chips" role="group" aria-label="Surface">${chips.map(([id, n]) =>
        `<button type="button" class="bk-chip${st.surface === id ? " on" : ""}" data-bk="surface" data-v="${id}">${e(n)}</button>`).join("")}</div>
      <input type="search" id="bk-q" placeholder="Search a persona, a bank or a line…" value="${e(st.q)}" aria-label="Search">
      <label class="bk-check"><input type="checkbox" data-bk="issues" ${st.issues ? "checked" : ""}> only with flags</label>
      <label class="bk-check"><input type="checkbox" data-bk="thin" ${st.thin ? "checked" : ""}> fewer than
        <input type="number" id="bk-n" min="2" max="50" value="${st.thinN}" class="bk-num"> lines</label>
      <label class="bk-check"><input type="checkbox" data-bk="singles" ${st.singles ? "checked" : ""}> single lines</label>
      <label class="bk-check"><input type="checkbox" data-bk="written" ${st.written ? "checked" : ""}> written-only banks</label></div>`;
  }
  function ownerList(by) {
    const rows = st.data.owners.filter(o => by.has(o.id)).map(o => {
      const bs = by.get(o.id), lines = bs.reduce((a, b) => a + b.active, 0), twins = bs.reduce((a, b) => a + b.twins, 0);
      const issues = bs.reduce((a, b) => a + b.issues, 0), full = twins >= lines;
      return `<button type="button" class="bk-owner${o.id === st.owner ? " sel" : ""}" data-bk="owner" data-v="${e(o.id)}">
        <span class="bk-oname">${e(o.name)}</span>
        <span class="bk-ometa">${plural(bs.length, "bank")} · ${plural(lines, "line")}${o.kind === "written" ? " · written" : ""}</span>
        <span class="bk-bar2" title="${twins} of ${lines} have a clean twin"><i class="${full ? "ok" : ""}" style="width:${pct(twins, lines)}%"></i></span>
        ${issues ? `<span class="bk-badge warn">${issues} flagged</span>` : ""}</button>`;
    }).join("");
    return rows || '<p class="muted">Nothing matches.</p>';
  }
  function flagChips(flags) {
    return flags.map(f => `<span class="bk-flag ${f}" title="${e((FLAG[f] || [])[1] || "")}">${e((FLAG[f] || [f])[0])}</span>`).join("");
  }
  function editForm(b, l) {
    const d = st.edit, adding = d.mode === "add";
    const names = b.fields.length ? b.fields.map(f => `<code class="bk-f">{${e(f)}}</code>`).join(" ") : "none";
    const said = b.kind === "spoken";
    return `<div class="bk-edit">
      <p class="muted small">${adding ? `New line, key <b class="mono">${e(b.id)}.${b.size}</b>. ` : `Key <b class="mono">${e(l.key)}</b> never changes. `}Names you may use: ${names}.
        Spicy and clean must use the same names.</p>
      <div class="bk-two">
        <label><span>Spicy (house voice)</span><textarea rows="3" data-bkf="spicy">${e(d.spicy)}</textarea></label>
        <label><span>Clean (Family-friendly)${!adding && !l.twin ? " — none yet" : ""}</span><textarea rows="3" data-bkf="clean">${e(d.clean)}</textarea></label></div>
      ${said ? `<div class="bk-two">
        <label><span>Spoken spicy, without figures <i class="muted">(needed when the line carries an amount)</i></span><textarea rows="2" data-bkf="say">${e(d.say)}</textarea></label>
        <label><span>Spoken clean, without figures</span><textarea rows="2" data-bkf="say_clean">${e(d.say_clean)}</textarea></label></div>
        <p class="muted small">Voices cost money only the first time a line is heard. A line with an amount in it is recorded once per spoken version, not once per amount.</p>` : ""}
      ${!adding && l && said && !d.err && ((d.say && d.say === l.say && d.spicy !== l.spicy) || (d.say_clean && d.say_clean === l.say_clean && d.clean !== (l.twin ? l.clean : "")))
        ? '<p class="bk-none">A spoken version is still the old line\'s. Rewrite it to match, or clear it to have the line read as written.</p>' : ""}
      ${d.err ? `<p class="bk-none">${e(d.err)}</p>` : ""}
      <div class="bk-actions"><button type="button" class="primary" data-bk="save" ${d.busy ? "disabled" : ""}>${d.busy ? "Saving…" : "Save to the game"}</button>
        <button type="button" data-bk="cancel" ${d.busy ? "disabled" : ""}>Cancel</button></div></div>`;
  }
  function lineActions(b, l) {
    if (l.retired) return `<button type="button" class="bk-mini" data-bk="restore" data-v="${e(l.key)}">Restore</button>`;
    const reset = l.edited ? `<button type="button" class="bk-mini${st.arm === "reset:" + l.key ? " danger" : ""}" data-bk="reset" data-v="${e(l.key)}">${st.arm === "reset:" + l.key ? "Put the shipped line back?" : "Reset"}</button>` : "";
    const remove = b.numbered ? `<button type="button" class="bk-mini" data-bk="retire" data-v="${e(l.key)}">Remove</button>` : "";
    return `<button type="button" class="bk-mini" data-bk="edit" data-v="${e(l.key)}">Edit</button>${reset}${remove}`;
  }
  /* ------------------------------------------------------------- generator -- */
  const G = () => st.data && st.data.generator;
  const gopt = id => (st.gen.opts[id] = st.gen.opts[id] || { count: "4", provider: "", notes: "" });
  function genBar(b) {
    const g = G();
    if (!g || !b.numbered || !b.addable || b.kind !== "spoken") return "";
    const o = gopt(b.id), prov = o.provider || g.settings.provider, busy = st.gen.busy === b.id;
    const waiting = g.queue.filter(x => x.bank === b.id).length;
    return `<div class="bk-gen"><b>Write new lines</b>
      <select data-bkg="count" data-b="${e(b.id)}">${[2, 4, 6, 8, 12].map(n => `<option${String(n) === o.count ? " selected" : ""}>${n}</option>`).join("")}</select>
      <select data-bkg="provider" data-b="${e(b.id)}"><option value="local"${prov === "local" ? " selected" : ""}>Local LLM</option><option value="api"${prov === "api" ? " selected" : ""}>Claude API</option></select>
      <input type="text" class="bk-notes" placeholder="Direction (optional), e.g. more about pirates" data-bkg="notes" data-b="${e(b.id)}" value="${e(o.notes)}">
      <button type="button" class="bk-mini" data-bk="grun" data-v="${e(b.id)}" ${st.gen.busy ? "disabled" : ""}>${busy ? "Writing…" : "Generate"}</button>
      ${waiting ? `<span class="bk-badge new">${waiting} waiting for review</span>` : ""}</div>`;
  }
  function draftRow(it) {
    const ed = st.gen.edits[it.id] || {}, val = f => (f in ed ? ed[f] : it[f] || "");
    const ta = (f, label) => `<label class="bk-dlab">${label}<textarea rows="2" data-bkg="d" data-f="${f}" data-id="${e(it.id)}">${e(val(f))}</textarea></label>`;
    return `<div class="bk-draft"><div class="bk-dmeta"><span class="bk-id mono">${e(it.bank)}</span>
        <span class="muted small">written by ${e(it.provider === "api" ? "Claude API" : "local LLM")} · ${e(it.model || "")}</span></div>
      <div class="bk-two">${ta("spicy", "Spicy")}${ta("clean", "Clean")}</div>
      ${it.say || it.say_clean || val("say") || val("say_clean") ? `<div class="bk-two">${ta("say", "Spoken spicy")}${ta("say_clean", "Spoken clean")}</div>` : ""}
      ${st.gen.derr[it.id] ? `<p class="bk-none">${e(st.gen.derr[it.id])}</p>` : ""}
      <div class="bk-actions"><button type="button" class="primary" data-bk="gapprove" data-v="${e(it.id)}">Approve: add to the game</button>
        <button type="button" data-bk="gdiscard" data-v="${e(it.id)}">Discard</button></div></div>`;
  }
  function genCard() {
    const g = G();
    if (!g) return "";
    const s = g.settings, n = g.queue.length;
    const models = st.gen.models.map(m => `<option value="${e(m)}"></option>`).join("");
    return `<details class="bk-genpanel" data-bkd="gen" ${st.gen.open ? "open" : ""}><summary>Generator${n ? ` · ${plural(n, "draft")} waiting for review` : ""}</summary>
      ${st.gen.msg ? `<p class="muted small">${e(st.gen.msg)}</p>` : ""}${st.gen.err ? `<p class="bk-none">${e(st.gen.err)}</p>` : ""}
      <div class="bk-gset"><h3>Settings</h3>
        <label>Default writer <select data-bkg="s-provider"><option value="local"${s.provider === "local" ? " selected" : ""}>Local LLM</option><option value="api"${s.provider === "api" ? " selected" : ""}>Claude API</option></select></label>
        <label>Local LLM address <input type="text" class="bk-wide" data-bkg="s-url" value="${e(s.local.base_url)}"></label>
        <label>Local model <input type="text" class="bk-wide" list="bk-models" data-bkg="s-model" value="${e(s.local.model)}" placeholder="Press Find models">
          <datalist id="bk-models">${models}</datalist></label>
        <button type="button" class="bk-mini" data-bk="gmodels">Find models</button>
        <label>Claude model <input type="text" data-bkg="s-api" value="${e(s.api.model)}"></label>
        <label>Anthropic API key <input type="password" autocomplete="off" data-bkg="s-key" placeholder="${g.key_set ? "A key is saved" + (g.key_from === "env" ? " (from the server's environment)" : "") + "; type to replace" : "Paste a key to use the API"}"></label>
        <div class="bk-actions"><button type="button" class="primary" data-bk="gsave">Save settings</button>
          ${g.key_set && g.key_from === "admin" ? '<button type="button" data-bk="gkeyclear">Remove saved key</button>' : ""}</div></div>
      <h3>Drafts waiting for review</h3>
      ${n ? g.queue.map(draftRow).join("") : '<p class="muted small">Nothing waiting. Open a spoken bank and press Generate. A draft only reaches the game when you approve it.</p>'}</details>`;
  }
  async function gcall(op, body) {
    const res = await post(op, body);
    if (!res.ok) { st.gen.err = res.error || "That did not work."; }
    return res;
  }
  async function genAction(a, v, t) {
    const gg = st.gen, val = sel => { const el = main.querySelector(sel); return el ? el.value : ""; };
    gg.err = ""; gg.msg = "";
    if (a === "grun") {
      const o = gopt(v);
      gg.busy = v; redraw();
      const res = await gcall("gen_run", { bank: v, count: o.count, provider: o.provider || G().settings.provider, notes: o.notes });
      gg.busy = "";
      if (res.ok) { gg.msg = `${plural(res.added, "draft")} ready to review${res.thrown ? `; ${res.thrown} failed the checks and were dropped` : ""}.`; gg.open = true; }
      await load(true); return;
    }
    if (a === "gsave" || a === "gmodels" || a === "gkeyclear") {
      const body = { provider: val('[data-bkg="s-provider"]'), base_url: val('[data-bkg="s-url"]'), model: val('[data-bkg="s-model"]'), api_model: val('[data-bkg="s-api"]') };
      const key = val('[data-bkg="s-key"]');
      if (a === "gkeyclear") body.key = ""; else if (key) body.key = key;
      gg.open = true;
      if (a === "gmodels") {
        gg.msg = "Asking the local LLM for its models…"; redraw();
        const saved = await gcall("gen_settings", { base_url: body.base_url, model: body.model });   // so the redraw keeps what you typed
        if (saved.ok) {
          const res = await gcall("gen_models", { base_url: body.base_url });
          if (res.ok) { gg.models = res.models; gg.msg = `${plural(res.models.length, "model")} found. Pick one in the Local model box.`; }
        }
        await load(true); return;
      }
      const res = await gcall("gen_settings", body);
      if (res.ok) gg.msg = "Generator settings saved.";
      await load(true); return;
    }
    if (a === "gapprove") {
      const ed = gg.edits[v] || {}; delete gg.derr[v];
      if (Object.keys(ed).length) { const r0 = await post("gen_edit", Object.assign({ id: v }, ed)); if (!r0.ok) { gg.derr[v] = r0.error || "Could not save your edits."; return redraw(); } }
      const res = await post("gen_approve", { id: v });
      if (!res.ok) { gg.derr[v] = res.error || "That line could not be added."; return redraw(); }
      delete gg.edits[v]; gg.open = true; gg.msg = "Added to the game. It is live now.";
      await load(true); return;
    }
    if (a === "gdiscard") { delete gg.edits[v]; await gcall("gen_discard", { id: v }); gg.open = true; await load(true); }
  }

  /* Spoken setting and the cap on new recordings per game (banks.py: SPOKEN_MODES, charge). */
  function voiceRow(b) {
    if (b.kind !== "spoken" || !b.spoken_options.length) return "";
    const opts = b.spoken_options.map((o, i) => `<option value="${e(o.id)}"${o.id === b.spoken ? " selected" : ""}>${e(o.name)}${i === 0 ? " (as now)" : ""}</option>`).join("");
    const used = b.cap ? `${b.used} of ${b.cap}` : `${b.used}`;
    return `<div class="bk-vox"><label>Spoken <select data-bkv="spoken" data-b="${e(b.id)}">${opts}</select></label>
      <label>New recordings per game, at most <input type="number" min="0" max="500" class="bk-num" data-bkv="cap" data-b="${e(b.id)}" value="${b.cap}"></label>
      <button type="button" class="bk-mini" data-bk="vsave" data-v="${e(b.id)}">Save</button>
      <span class="muted small">0 = no cap. ${e(used)} new this game. Lines already recorded always play free.</span></div>`;
  }
  function bankCard(b) {
    const open = st.open.has(b.id), thin = b.active < st.thinN;
    let body = "";
    if (open) {
      const rows = b.lines.map(l => {
        const editing = st.edit && st.edit.key === l.key && st.edit.mode === "edit";
        const tags = (l.added ? '<span class="bk-badge new">new</span>' : "") + (l.edited ? '<span class="bk-badge edited">edited</span>' : "") + (l.retired ? '<span class="bk-badge">removed</span>' : "");
        return `<tr class="${l.flags.length ? "flagged" : ""}${l.retired ? " retired" : ""}"><td class="mono">${b.numbered ? l.n : "·"}</td>
        <td>${tags}${l.retired && !l.spicy ? '<span class="muted">(removed)</span>' : field(l.spicy)}</td>
        <td>${l.retired ? '<span class="muted">—</span>' : l.twin ? (l.same ? '<span class="muted">same wording</span>' : field(l.clean)) : '<span class="bk-none">No clean twin</span>'}
          ${l.flags.length ? `<div>${flagChips(l.flags.filter(f => f !== "no_clean"))}</div>` : ""}</td>
        <td class="bk-act">${lineActions(b, l)}</td></tr>${editing ? `<tr class="bk-editrow"><td></td><td colspan="3">${editForm(b, l)}</td></tr>` : ""}`;
      }).join("");
      const adding = st.edit && st.edit.mode === "add" && st.edit.bank === b.id;
      const foot = adding ? `<tr class="bk-editrow"><td></td><td colspan="3">${editForm(b, null)}</td></tr>`
        : b.addable ? `<tr><td></td><td colspan="3"><button type="button" class="bk-mini" data-bk="add" data-v="${e(b.id)}">+ Add a line</button></td></tr>`
        : b.fixed_note ? `<tr><td></td><td colspan="3" class="muted small">${e(b.fixed_note)} You can still reword its lines.</td></tr>` : "";
      body = voiceRow(b) + genBar(b) + `<table class="bk-lines"><thead><tr><th>#</th><th>Spicy (house voice)</th><th>Clean (Family-friendly)</th><th></th></tr></thead><tbody>${rows}${foot}</tbody></table>`;
    }
    return `<section class="bk-bank${open ? " open" : ""}">
      <button type="button" class="bk-bhead" data-bk="bank" data-v="${e(b.id)}" aria-expanded="${open}">
        <span class="bk-id mono">${e(b.id)}</span>
        <span class="bk-badge">${e(SURF[b.surface] || b.surface)}</span>
        <span class="bk-badge ${b.kind}">${b.kind === "spoken" ? "spoken" : "written"}</span>
        ${b.numbered ? "" : '<span class="bk-badge">single line</span>'}
        <span class="bk-size">${b.active} line${b.active === 1 ? "" : "s"} · ${b.twins}/${b.active} clean</span>
        ${thin ? '<span class="bk-badge">thin</span>' : ""}${b.issues ? `<span class="bk-badge warn">${b.issues} flagged</span>` : ""}
      </button>${body}</section>`;
  }
  function bankPane(by) {
    const o = st.data.owners.find(x => x.id === st.owner);
    if (!o || !by.has(o.id)) return '<p class="muted">Pick a persona or story on the left.</p>';
    const all = by.get(o.id), numbered = all.filter(b => b.numbered), singles = all.filter(b => !b.numbered);
    const showSingles = st.singles || !numbered.length, list = showSingles ? all : numbered;
    const hidden = showSingles ? 0 : singles.length;
    return `<div class="bk-ohead"><h2>${e(o.name)}</h2>${o.note ? `<p class="muted">${e(o.note)}</p>` : ""}
      <p class="muted small">${o.kind === "spoken" ? `Voice if every line were heard once: about ${o.chars.toLocaleString()} characters (spicy wording only; the clean wording is recorded separately).` : "Written text; nobody reads it aloud."}</p></div>
      <p class="bk-count muted">${list.length} bank${list.length === 1 ? "" : "s"} shown${hidden ? ` · ${hidden} single line${hidden === 1 ? "" : "s"} hidden (tick “single lines”)` : ""}.
        <button type="button" class="bk-link" data-bk="expand">${list.every(b => st.open.has(b.id)) ? "Collapse all" : "Expand all"}</button></p>
      ${list.map(bankCard).join("")}`;
  }
  function inner() {
    const by = grouped();
    if (!by.has(st.owner)) st.owner = by.size ? by.keys().next().value : "";
    return `<div class="bk-wrap"><aside class="bk-list" id="bk-owners">${ownerList(by)}</aside><div class="bk-pane" id="bk-pane">${bankPane(by)}</div></div>`;
  }
  function redrawLists() {
    const by = grouped();
    if (!by.has(st.owner)) st.owner = by.size ? by.keys().next().value : "";
    const a = document.getElementById("bk-owners"), p = document.getElementById("bk-pane");
    if (a) a.innerHTML = ownerList(by);
    if (p) p.innerHTML = bankPane(by);
  }
  function render() {
    const tabs = typeof langTabs === "function" ? langTabs("banks") : "";
    const top = head("Language & Text", "Every bank of dialogue each persona or story pulls into the game, the Dashboard, the Table and the Manual. " +
      "Each line is a spicy and a clean (Family-friendly) pair. Changes are saved to the game as soon as you press Save on a line.");
    if (st.off) return top + tabs + '<section class="card"><p>The game server needs a restart before this page can read the banks.</p></section>';
    if (st.err) return top + tabs + `<section class="card"><p class="bk-none">${e(st.err)}</p><button type="button" data-bk="retry">Try again</button></section>`;
    if (!st.data) return top + tabs + '<section class="card"><p class="muted">Reading the banks…</p></section>';
    return `<div id="bk">${top}${tabs}${summary()}${voiceCard()}${genCard()}${controls()}${inner()}</div>`;
  }
  function findLine(key) {
    for (const b of st.data.banks) for (const l of b.lines) if (l.key === key) return l;
    return null;
  }
  function redraw() { if (here() && typeof draw === "function") draw(); }

  /* ------------------------------------------------------------ events -- */
  const main = document.getElementById("main");
  main.addEventListener("click", ev => {
    if (!here()) return;
    const t = ev.target.closest("[data-bk]");
    if (!t) return;
    const a = t.dataset.bk, v = t.dataset.v;
    if (a === "retry") { st.err = ""; load(); return; }
    if (a === "surface") { st.surface = v; return redraw(); }
    if (a === "owner") { st.owner = v; return redrawLists(); }
    if (a === "bank") { if (st.open.has(v)) st.open.delete(v); else st.open.add(v); return redrawLists(); }
    if (a === "edit") {
      const l = findLine(v);
      if (!l) return;
      st.edit = { mode: "edit", key: v, spicy: l.spicy, clean: l.twin ? l.clean : "", say: l.say || "", say_clean: l.say_clean || "", err: "", busy: false };
      st.arm = ""; return redrawLists();
    }
    if (a === "add") { st.edit = { mode: "add", bank: v, key: "", spicy: "", clean: "", say: "", say_clean: "", err: "", busy: false }; st.arm = ""; return redrawLists(); }
    if (a === "cancel") { st.edit = null; return redrawLists(); }
    if (a === "save") {
      const d = st.edit;
      if (!d || d.busy) return;
      const body = { spicy: d.spicy, clean: d.clean, say: d.say, say_clean: d.say_clean };
      return change(d.mode === "add" ? "add" : "edit", Object.assign(body, d.mode === "add" ? { bank: d.bank } : { key: d.key }));
    }
    if (["grun", "gsave", "gmodels", "gkeyclear", "gapprove", "gdiscard"].includes(a)) { genAction(a, v, t); return; }
    if (a === "vsave") {
      const pick = n => main.querySelector(`[data-bkv="${n}"][data-b="${v}"]`);
      const sel = pick("spoken"), cap = pick("cap");
      return post("spoken", { bank: v, spoken: sel ? sel.value : "", cap: cap ? cap.value : 0 }).then(async res => {
        if (!res.ok) return note(res.error || "That setting could not be saved.");
        await load(true); note("Saved. It applies from the next line the game plans.");
      });
    }
    if (a === "retire" || a === "restore") return change(a, { key: v });
    if (a === "reset") {
      if (st.arm !== "reset:" + v) { st.arm = "reset:" + v; return redrawLists(); }
      return change("reset", { key: v });
    }
    if (a === "expand") {
      const by = grouped(), all = (by.get(st.owner) || []).filter(b => st.singles || b.numbered || !(by.get(st.owner) || []).some(x => x.numbered));
      if (all.every(b => st.open.has(b.id))) all.forEach(b => st.open.delete(b.id)); else all.forEach(b => st.open.add(b.id));
      return redrawLists();
    }
  });
  main.addEventListener("toggle", ev => {          // toggle does not bubble, so listen in the capture phase
    const d = ev.target && ev.target.dataset && ev.target.dataset.bkd;
    if (!d || !here()) return;
    if (d === "voice") st.voiceOpen = ev.target.open; else st.gen.open = ev.target.open;
  }, true);
  main.addEventListener("change", ev => {
    if (!here()) return;
    const gb = ev.target.dataset && ev.target.dataset.bkg;
    if (gb === "count" || gb === "provider") { gopt(ev.target.dataset.b)[gb] = ev.target.value; return; }
    const t = ev.target.closest("[data-bk]");
    if (t && ["issues", "thin", "singles", "written"].includes(t.dataset.bk)) { st[t.dataset.bk] = t.checked; redraw(); }
    if (ev.target.id === "bk-n") { st.thinN = Math.max(2, Math.min(50, Number(ev.target.value) || 5)); redraw(); }
  });
  main.addEventListener("input", ev => {
    if (!here()) return;
    if (ev.target.dataset && ev.target.dataset.bkg === "notes") { gopt(ev.target.dataset.b).notes = ev.target.value; return; }
    if (ev.target.dataset && ev.target.dataset.bkg === "d") { (st.gen.edits[ev.target.dataset.id] = st.gen.edits[ev.target.dataset.id] || {})[ev.target.dataset.f] = ev.target.value; return; }
    if (ev.target.dataset && ev.target.dataset.bkf && st.edit) { st.edit[ev.target.dataset.bkf] = ev.target.value; return; }
    if (ev.target.id !== "bk-q") return;
    st.q = ev.target.value;
    redrawLists();
  });

  /* admin.js calls enter() on EVERY draw of this section, and load() redraws: so only the first call after arriving may
     fetch, or the page refetches the whole catalogue forever. */
  let fresh = false;
  window.SeaTraderBanks = { render, enter: () => { if (fresh) return; fresh = true; load(!!st.data); }, leave: () => { fresh = false; } };
})();
