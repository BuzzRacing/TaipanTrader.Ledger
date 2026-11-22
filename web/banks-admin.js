/* Crimson Ledger Admin: Language & Text > Dialogue Banks (slice 1, read-only, 22 Nov 2026).
   Every bank of dialogue the game, Dashboard, Table and Manual pull in, listed by persona or story, with each
   line shown as a spicy / clean pair and audited (no clean twin, {names} that do not match, duplicates, long
   spoken lines, thin banks). Server side: banks.py (GET /api/admin/banks). Nothing here changes the game;
   adding, editing and removing lines come in slice 2. */
(function () {
  "use strict";

  const st = {
    data: null, err: "", loading: false, off: false,
    owner: "", surface: "", q: "", issues: false, thin: false, thinN: 5, written: false, singles: false,
    open: new Set(),
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

  /* ------------------------------------------------------------ filter -- */
  function matches(b) {
    if (st.surface && b.surface !== st.surface) return false;
    if (!st.written && b.kind === "written") return false;
    if (st.issues && !b.issues) return false;
    if (st.thin && b.size >= st.thinN) return false;
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
      ${st.data.surfaces.map(x => stat(x.lines, x.name)).join("")}</div>`;
  }
  function voiceCard() {
    const now = st.data.voice_now;
    return `<details class="bk-voice"><summary>How each screen speaks today</summary>
      <p class="muted small">Voices are paid for only the first time a line is heard, then replayed free from the cache. A per-bank
      <b>Spoken</b> setting (Off, On request, Automatic) and a cap on new clips per bank come with editing; this is how it behaves now.</p>
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
      const bs = by.get(o.id), lines = bs.reduce((a, b) => a + b.size, 0), twins = bs.reduce((a, b) => a + b.twins, 0);
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
  function bankCard(b) {
    const open = st.open.has(b.id), thin = b.size < st.thinN;
    const body = open ? `<table class="bk-lines"><thead><tr><th>#</th><th>Spicy (house voice)</th><th>Clean (Family-friendly)</th></tr></thead><tbody>${
      b.lines.map(l => `<tr class="${l.flags.length ? "flagged" : ""}"><td class="mono">${b.numbered ? l.n : "·"}</td>
        <td>${field(l.spicy)}</td>
        <td>${l.twin ? (l.same ? '<span class="muted">same wording</span>' : field(l.clean)) : '<span class="bk-none">No clean twin</span>'}
          ${l.flags.length ? `<div>${flagChips(l.flags.filter(f => f !== "no_clean"))}</div>` : ""}</td></tr>`).join("")}</tbody></table>` : "";
    return `<section class="bk-bank${open ? " open" : ""}">
      <button type="button" class="bk-bhead" data-bk="bank" data-v="${e(b.id)}" aria-expanded="${open}">
        <span class="bk-id mono">${e(b.id)}</span>
        <span class="bk-badge">${e(SURF[b.surface] || b.surface)}</span>
        <span class="bk-badge ${b.kind}">${b.kind === "spoken" ? "spoken" : "written"}</span>
        ${b.numbered ? "" : '<span class="bk-badge">single line</span>'}
        <span class="bk-size">${b.size} line${b.size === 1 ? "" : "s"} · ${b.twins}/${b.size} clean</span>
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
      "Each line is shown as a spicy and a clean (Family-friendly) pair. This view is read-only for now.");
    if (st.off) return top + tabs + '<section class="card"><p>The game server needs a restart before this page can read the banks.</p></section>';
    if (st.err) return top + tabs + `<section class="card"><p class="bk-none">${e(st.err)}</p><button type="button" data-bk="retry">Try again</button></section>`;
    if (!st.data) return top + tabs + '<section class="card"><p class="muted">Reading the banks…</p></section>';
    return `<div id="bk">${top}${tabs}${summary()}${voiceCard()}${controls()}${inner()}</div>`;
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
    if (a === "expand") {
      const by = grouped(), all = (by.get(st.owner) || []).filter(b => st.singles || b.numbered || !(by.get(st.owner) || []).some(x => x.numbered));
      if (all.every(b => st.open.has(b.id))) all.forEach(b => st.open.delete(b.id)); else all.forEach(b => st.open.add(b.id));
      return redrawLists();
    }
  });
  main.addEventListener("change", ev => {
    if (!here()) return;
    const t = ev.target.closest("[data-bk]");
    if (t && ["issues", "thin", "singles", "written"].includes(t.dataset.bk)) { st[t.dataset.bk] = t.checked; redraw(); }
    if (ev.target.id === "bk-n") { st.thinN = Math.max(2, Math.min(50, Number(ev.target.value) || 5)); redraw(); }
  });
  main.addEventListener("input", ev => {
    if (!here() || ev.target.id !== "bk-q") return;
    st.q = ev.target.value;
    redrawLists();
  });

  window.SeaTraderBanks = { render, enter: () => load(!!st.data), leave: () => {} };
})();
