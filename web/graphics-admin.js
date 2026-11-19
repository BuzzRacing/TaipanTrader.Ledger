/* SeaTrader Admin: Graphics.
   Every picture slot the game uses (main artwork, ports, ships, cargo), shown large, each one linked to
   the Media Library item it comes from. A slot knows which library item fills it, what it is tagged as,
   when it last changed and how (upload, regenerated, picked from the library, file replaced on disk),
   and which newer pictures of the same subject are waiting to be used.

   Picking, uploading or regenerating changes the editor only: Save & apply puts it on every screen,
   files it in the library under the slot, and writes the change into the slot's history. */
(function () {
  "use strict";

  const G = { lib: null, loading: false, poll: null, open: {}, hist: {}, size: "huge", filter: "", busy: {} };
  try { G.size = localStorage.getItem("st-gx-size") || "huge"; } catch (x) { /* storage off */ }

  const e = s => esc(s);
  const GROUPS = [
    ["brand", null, "Main artwork", "Logo, game icon, backgrounds and the chart. Shown across the join screen, lobby, player screens and harbor board.", "main"],
    ["port", "ports", "Port pictures", "Banner at the top of the market while a player is in that port.", "banner"],
    ["ship", "ships", "Ship pictures", "Fleet cards and the shipyard.", "card"],
    ["cargo", "goods", "Cargo pictures", "Beside each cargo in the market.", "icon"],
  ];
  const ASPECT = { brand: "16:9", port: "16:9", ship: "3:2", cargo: "1:1" };
  const BRAND_ASPECT = { logo: "3:1", favicon: "1:1", masthead_bg: "16:5", admin_masthead_bg: "3:1", page_bg: "16:9", board_bg: "16:9", chart_bg: "5:3" };
  const HOW = { first: "first filed", settings: "changed in settings", upload: "new upload", generated: "regenerated",
    library: "picked from the library", removed: "removed", file: "file replaced on disk" };
  const STYLE = "romanticized cinematic historical realism, China Seas 1860, humid salt haze, weathered maritime materials, lacquer black, oxblood silk, antique brass, imperial jade, dramatic but plausible lighting, no text";

  /* --------------------------------------------------------- helpers -- */
  const items = () => (G.lib ? G.lib.items : []);
  const byUrl = url => items().find(i => i.url === url);
  const byId = id => items().find(i => i.id === id);
  let savedMemo = ["", null];
  const savedCfg = () => { if (savedMemo[0] !== SAVED) savedMemo = [SAVED, JSON.parse(SAVED)]; return savedMemo[1]; };
  const fmtBytes = n => !n ? "" : n >= 1 << 20 ? (n / (1 << 20)).toFixed(1) + " MB" : Math.max(1, Math.round(n / 1024)) + " KB";

  function slots() {
    const out = [];
    GROUPS.forEach(([kind, table, , , role]) => {
      if (kind === "brand") {
        A.graphic_slots.forEach(([k, label, help]) => out.push({ key: "brand:" + k, kind, subject: k, role, label, help: k === "logo" ? "Transparent wide logo used on the join screen, lobby, opening, harbor board and admin header. Include the game name in the artwork." : help, path: "graphics." + k }));
      } else {
        const group = { port: "ports", ship: "ships", cargo: "goods" }[kind];
        Object.keys(CFG[table] || {}).forEach(k => out.push({ key: kind + ":" + k, kind, subject: k, role,
          label: (CFG[table][k] || {}).name || k, help: "", path: `graphics.${group}.${k}` }));
      }
    });
    return out;
  }
  function aspectOf(s) { return s.kind === "brand" ? (BRAND_ASPECT[s.subject] || "16:9") : ASPECT[s.kind]; }
  const cssRatio = a => a.replace(":", " / ");

  function defaultPrompt(s) {
    const n = s.label;
    if (s.kind === "brand" && s.subject === "logo") return 'Crimson Ledger primary logo, antique brass three-masted trading junk with oxblood battened sails over an open ivory merchant ledger and jade wave, emblem left of stacked engraved gold lettering CRIMSON LEDGER, transparent background, wide 3:1 composition, lacquer black, oxblood, antique brass and jade palette, no other text';
    if (s.kind === "brand" && s.subject === "favicon") return 'Crimson Ledger square game icon, antique brass three-masted trading junk with oxblood battened sails over an open ivory merchant ledger and jade wave, dark jade enamel, rounded oxblood lacquer tile, bold silhouette, no text';
    if (s.kind === "brand" && s.subject === "admin_masthead_bg") return `One cohesive panoramic 1860 Hong Kong trading-house chart room overlooking a misty jade harbor, oxblood-sailed trading junk and warm brass oil lamp on the right, teak desk with a merchant ledger and nautical charts, dark quiet left 40 percent for the existing title, important objects in the central horizontal third for a shallow banner crop, no people, no collage, ${STYLE}`;
    if (s.kind === "port") return `The port of ${n} in the 1860s seen from the water, busy trading harbour with junks, lorchas and clipper ships at anchor, waterfront godowns and hongs, wide banner composition, ${STYLE}`;
    if (s.kind === "ship") return `A ${n} under full sail on the South China Sea, 1860s, detailed rigging and weathered hull, ${STYLE}`;
    if (s.kind === "cargo") return `Still life of ${n} as 1860s trade cargo, crates, chests and bales on a teak deck, square composition, no person, ${STYLE}`;
    return `${n} for a 19th-century China Seas trading game, ${s.help || ""} ${STYLE}`;
  }

  /* Everything we know about one slot right now. */
  function info(s) {
    const url = get(CFG, s.path) || "";
    const savedUrl = get(savedCfg(), s.path) || "";
    const it = url ? byUrl(url) : null;
    const st = (G.lib && G.lib.slots && G.lib.slots[s.key]) || { history: [], since: "" };
    const mine = items().filter(i => i.kind === s.kind && i.subject === s.subject && !i.missing);
    const since = st.since || "";
    const isNew = i => i.url !== url && i.url !== savedUrl && since && String(i.added) > since;
    const cands = mine.filter(i => i.url !== url).sort((a, b) => isNew(b) - isNew(a) || String(b.added).localeCompare(String(a.added)));
    const linked = !url ? "empty" : !it ? "unfiled" : (it.kind !== s.kind || it.subject !== s.subject) ? "misfiled" : "linked";
    return { url, savedUrl, it, st, cands, newCount: cands.filter(isNew).length, isNew, linked,
      unsaved: url !== savedUrl, fileChanged: !!(st.file_changed && url === savedUrl) };
  }

  async function load(quiet) {
    if (G.loading) return;
    G.loading = true;
    const res = await api("media/library");
    G.loading = false;
    if (!res.ok) { if (!quiet) toast(res.error || "Could not read the media library.", true); return; }
    G.lib = res;
    redraw();
    watch();
  }

  function redraw() {
    if (section !== "graphics") return;
    const y = window.scrollY;
    const focus = document.activeElement && document.activeElement.id;
    document.getElementById("main").innerHTML = render();
    window.scrollTo(0, y);
    if (focus && document.getElementById(focus)) document.getElementById(focus).focus();
  }

  function running() { return ((G.lib && G.lib.jobs) || []).filter(j => ["waiting", "running", "cancelling"].includes(j.status)); }
  function watch() {
    if (G.poll || !running().length) return;
    G.poll = setInterval(async () => {
      if (section !== "graphics") { clearInterval(G.poll); G.poll = null; return; }
      const res = await api("media/jobs");
      if (!res.ok) return;
      const before = running().map(j => j.id + ":" + j.done).join(), after = res.jobs.filter(j => ["waiting", "running", "cancelling"].includes(j.status));
      const changed = before !== after.map(j => j.id + ":" + j.done).join();
      G.lib.jobs = res.jobs;
      if (!after.length) { clearInterval(G.poll); G.poll = null; }
      if (changed) { G.loading = false; load(true); }
    }, 4000);
  }

  /* ---------------------------------------------------------- render -- */
  function art(s, I) {
    const ratio = cssRatio(aspectOf(s));
    const img = I.url ? `<a href="${e(I.url)}" target="_blank" rel="noopener" title="Open full size"><img src="${e(I.url)}" alt="${e(s.label)}" loading="lazy"></a>`
      : `<div class="gx-empty"><b>No picture</b><span>Upload, regenerate or pick one below.</span></div>`;
    const badges = [
      I.unsaved ? '<b class="gx-b unsaved">unsaved</b>' : "",
      I.fileChanged ? '<b class="gx-b changed" title="The file on disk is different from when it was last saved here">file changed</b>' : "",
      I.newCount ? `<b class="gx-b new">${I.newCount} new</b>` : "",
      I.it && I.it.nsfw ? '<b class="gx-b nsfw">NSFW</b>' : "",
      I.it && I.it.type === "image" && I.it.width ? `<b class="gx-b dim">${I.it.width}×${I.it.height}</b>` : "",
    ].join("");
    return `<div class="gx-art" style="aspect-ratio:${ratio}">${img}<span class="gx-badges">${badges}</span></div>`;
  }

  function linkLine(s, I) {
    if (I.linked === "empty") return `<p class="gx-link none">Empty slot.</p>`;
    if (I.linked === "unfiled") return `<p class="gx-link warn">Not in the Media Library yet: it is filed under <b>${e(s.kind)} · ${e(s.subject)}</b> on Save &amp; apply.</p>`;
    if (I.linked === "misfiled") return `<p class="gx-link warn">Filed in the library as <b>${e(I.it.kind)} · ${e(I.it.subject || "unsorted")}</b>: re-tagged as <b>${e(s.kind)} · ${e(s.subject)}</b> on Save &amp; apply.</p>`;
    return `<p class="gx-link ok">Linked to library item <code>${e(I.it.id)}</code></p>`;
  }

  function chips(s, I) {
    const it = I.it;
    const list = [`<span class="gx-chip k">${e(s.kind)} · ${e(s.subject)}</span>`, `<span class="gx-chip r">${e(s.role)}</span>`];
    if (it) {
      it.tags.forEach(t => list.push(`<span class="gx-chip">${e(t)}</span>`));
      list.push(`<span class="gx-chip src">${e(it.source)}</span>`);
      if (it.primary) list.push('<span class="gx-chip star">★ primary</span>');
    }
    return `<div class="gx-chips">${list.join("")}</div>`;
  }

  function history(s, I) {
    const h = (I.st.history || []).slice().reverse();
    const last = h[0];
    const lastTxt = last ? `Last change <b>${e(last.at)}</b> · ${e(HOW[last.how] || last.how)}` : "No changes recorded yet.";
    const open = G.hist[s.key];
    const rows = h.map(x => {
      const it = x.item && byId(x.item);
      const thumbUrl = x.to && x.how !== "removed" ? x.to : x.from;
      return `<li><span class="gx-hthumb">${thumbUrl ? `<img src="${e(thumbUrl)}" alt="" loading="lazy">` : ""}</span>
        <span><b>${e(x.at)}</b> ${e(HOW[x.how] || x.how)}${it ? ` · <code>${e(it.id)}</code>` : ""}
        ${x.from && x.from !== x.to ? `<small>was ${e(x.from)}</small>` : ""}${x.to ? `<small>now ${e(x.to)}</small>` : ""}</span>
        ${x.from && x.from !== x.to && x.how !== "first" && x.from !== I.url ? `<button type="button" class="link" data-gxuse="${e(s.path)}" data-url="${e(x.from)}">put back</button>` : ""}</li>`;
    }).join("");
    return `<div class="gx-hist"><span>${lastTxt}${I.unsaved ? ' · <b class="warn">new pick not saved yet</b>' : ""}</span>
      ${h.length ? `<button type="button" class="link" data-gxhist="${e(s.key)}">${open ? "hide history" : `history (${h.length})`}</button>` : ""}
      ${open ? `<ol class="gx-hlist">${rows}</ol>` : ""}</div>`;
  }

  function candidates(s, I) {
    if (!I.cands.length) return `<p class="help gx-nocand">No other pictures of ${e(s.label)} in the library yet.</p>`;
    const list = I.cands.slice(0, 18).map(i => `<button type="button" class="gx-cand${I.isNew(i) ? " new" : ""}${i.nsfw ? " nsfw" : ""}${i.url === I.savedUrl ? " saved" : ""}"
        data-gxuse="${e(s.path)}" data-url="${e(i.url)}" title="Use this picture (${e(i.added)}${i.source ? ", " + e(i.source) : ""})">
        ${i.type === "video" ? `<video src="${e(i.url)}#t=0.5" muted preload="metadata"></video>` : `<img src="${e(i.url)}" alt="" loading="lazy">`}
        ${I.isNew(i) ? "<i>NEW</i>" : i.url === I.savedUrl ? "<i>saved</i>" : ""}</button>`).join("");
    return `<div class="gx-cands"><span class="gx-label">Other ${e(s.label)} pictures in the library · click to use</span><div class="gx-strip">${list}</div></div>`;
  }

  function regenPanel(s, I) {
    if (!G.open[s.key]) return "";
    const d = G.open[s.key];
    const job = running().find(j => j.kind === s.kind && j.subject === s.subject);
    return `<div class="gx-regen">
      <label class="gx-label" for="gxp-${e(s.key.replace(":", "-"))}">Prompt ${I.it && I.it.prompt ? "(from the current picture)" : "(starter prompt)"}</label>
      <textarea id="gxp-${e(s.key.replace(":", "-"))}" rows="5" class="code" data-gxprompt="${e(s.key)}">${e(d.prompt)}</textarea>
      <div class="row"><label>How many <select data-gxcount="${e(s.key)}">${[1, 2, 3, 4].map(n => `<option${n === d.count ? " selected" : ""}>${n}</option>`).join("")}</select></label>
        <span class="help">Shape ${e(aspectOf(s))}</span>
        <button type="button" class="primary" data-gxpaint="${e(s.key)}"${G.busy[s.key] ? " disabled" : ""}>Paint ${d.count} new</button>
        <button type="button" class="link" data-gxregen="${e(s.key)}">close</button>
        ${job ? `<span class="help">On the farm: ${job.done}/${job.count} painted · ${e(job.status)}</span>` : ""}</div>
      <p class="help">New pictures are filed in the Media Library under <b>${e(s.kind)} · ${e(s.subject)}</b>, tagged <b>regen</b> and linked to the picture they replace. They show up below marked NEW; click one to use it, then Save &amp; apply.</p></div>`;
  }

  function card(s) {
    const I = info(s);
    const cls = ["gx-card", I.unsaved ? "unsaved" : "", I.fileChanged ? "changed" : "", I.newCount ? "hasnew" : "", I.linked].filter(Boolean).join(" ");
    return `<article class="${cls}" id="gx-${e(s.key.replace(":", "-"))}">
      ${art(s, I)}
      <div class="gx-body">
        <div class="gx-title"><h3>${e(s.label)}</h3>${I.it ? `<span class="muted small">${e(fmtBytes(I.it.bytes))}${I.it.added ? " · added " + e(I.it.added) : ""}</span>` : ""}</div>
        ${s.help ? `<p class="help">${e(s.help)}</p>` : ""}
        ${linkLine(s, I)}
        ${chips(s, I)}
        ${history(s, I)}
        <div class="row gx-actions">
          <label class="pick">Upload new<input type="file" accept="image/*,.ico" data-gxup="${e(s.key)}" hidden></label>
          <button type="button" data-gxregen="${e(s.key)}">${G.open[s.key] ? "Hide regenerate" : "Regenerate"}</button>
          <button type="button" data-medialib="${e(s.kind)}:${e(s.subject)}">Open in Media Library</button>
          ${I.unsaved ? `<button type="button" class="link" data-gxuse="${e(s.path)}" data-url="${e(I.savedUrl)}">undo pick</button>` : ""}
          ${I.url ? `<button type="button" class="link" data-clear="${e(s.path)}">remove from slot</button>` : ""}
        </div>
        ${regenPanel(s, I)}
        ${candidates(s, I)}
      </div></article>`;
  }

  function textLogoCard() {
    const name = [CFG.brand.title_a, CFG.brand.title_b].filter(Boolean).join(" ");
    const markup = wordmarkHtml(name);
    return `<article class="gx-card gx-text-logo" id="gx-brand-text-logo">
      <div class="gx-art gx-text-preview" style="aspect-ratio:3 / 1">${markup}</div>
      <div class="gx-body">
        <div class="gx-title"><h3>HTML text logo</h3><span class="muted small">Live text · gilded lettering</span></div>
        <p class="help">The reusable text version, with gilded Ceremony Title lettering. It follows the game name in Brand and stays selectable and sharp at any size.</p>
        <p class="help">Include <code>/wordmark.css</code> wherever you paste this HTML. In game pages, <code>wordmarkHtml(name)</code> from <code>/wordmark.js</code> produces the same treatment. Set the surrounding font size to scale it.</p>
        <label class="gx-label" for="gx-wordmark-html">Reusable HTML</label>
        <textarea id="gx-wordmark-html" class="code" rows="4" readonly spellcheck="false">${e(markup)}</textarea>
        <div class="row gx-actions"><button type="button" data-gxcopytext="1">Copy HTML</button><button type="button" data-gxnav="brand">Change the game's name (Brand)</button></div>
      </div></article>`;
  }

  function render() {
    if (!G.lib) {
      if (!G.loading) setTimeout(() => load(), 0);
      return head("Graphics", "Loading the media library…");
    }
    const all = slots(), infos = all.map(s => [s, info(s)]);
    const n = f => infos.filter(([, I]) => f(I)).length;
    const counts = { unsaved: n(I => I.unsaved), changed: n(I => I.fileChanged), fresh: n(I => I.newCount), unlinked: n(I => I.linked === "unfiled" || I.linked === "misfiled"), empty: n(I => I.linked === "empty") };
    const show = ([s, I]) => !G.filter || (G.filter === "unsaved" && I.unsaved) || (G.filter === "changed" && I.fileChanged) ||
      (G.filter === "fresh" && I.newCount) || (G.filter === "unlinked" && (I.linked === "unfiled" || I.linked === "misfiled")) || (G.filter === "empty" && I.linked === "empty");
    const sizes = [["large", "Large"], ["huge", "Huge"], ["full", "Full width"]];
    const fbtn = (k, label, c) => `<button type="button" data-gxfilter="${k}" class="${G.filter === k ? "on" : ""}">${label}${c != null ? ` <i>${c}</i>` : ""}</button>`;
    const jobs = running();
    const sections = GROUPS.map(([kind, , title, note]) => {
      const list = infos.filter(([s]) => s.kind === kind).filter(show);
      if (!list.length) return "";
      return `<section class="card gx-group"><div class="head"><h2>${e(title)}</h2><button type="button" class="link" data-medialib="${kind}:">all ${e(title.toLowerCase())} in the library</button></div>
        <p class="help">${e(note)}</p><div class="gx-grid">${kind === "brand" && !G.filter ? textLogoCard() : ""}${list.map(([s]) => card(s)).join("")}</div></section>`;
    }).join("");
    return head("Graphics", "Every picture the game shows, linked to the Media Library. Uploads and regenerated pictures are filed under the slot they belong to, " +
        "so each slot knows its history and which newer pictures are waiting. Pick, then Save & apply.") +
      `<div class="gx-bar">
        <div class="gx-filters">${fbtn("", "All", all.length)}${fbtn("unsaved", "Unsaved", counts.unsaved)}${fbtn("fresh", "New pictures waiting", counts.fresh)}${fbtn("changed", "File changed", counts.changed)}${fbtn("unlinked", "Not linked", counts.unlinked)}${fbtn("empty", "Empty", counts.empty)}</div>
        <div class="gx-sizes"><span>Picture size</span>${sizes.map(([k, l]) => `<button type="button" data-gxsize="${k}" class="${G.size === k ? "on" : ""}">${l}</button>`).join("")}
          <button type="button" class="link" data-gxreload="1" title="Read the library again">refresh</button></div></div>
      ${jobs.length ? `<p class="gx-farm">The AI farm is painting: ${jobs.map(j => `${e(j.kind)} · ${e(j.subject)} ${j.done}/${j.count}`).join(", ")}</p>` : ""}
      <div class="gx-wrap size-${e(G.size)}">${sections || '<section class="card"><p class="muted">Nothing matches this filter.</p></section>'}</div>`;
  }

  /* --------------------------------------------------------- actions -- */
  const slotByKey = k => slots().find(s => s.key === k);
  function use(path, url) {
    set(CFG, path, url || "");
    const parts = path.split(".");
    if (!url && parts.length === 3) delete get(CFG, parts.slice(0, 2).join("."))[parts[2]];
    refreshDirty();
    redraw();
  }

  async function upload(s, file) {
    if (file.size > 40 * 1024 * 1024) return toast("That image is larger than 40 MB.", true);
    const I = info(s);
    let res;
    if (/\.ico$/i.test(file.name)) {
      res = await api("upload?name=" + encodeURIComponent(file.name), undefined, file);
      if (!res.ok) return toast(res.error, true);
      use(s.path, res.url);
      return toast("Icon uploaded. It is filed in the library on Save & apply.");
    }
    const q = new URLSearchParams({ name: file.name, kind: s.kind, subject: s.subject, roles: s.role, tags: "graphics, upload" });
    if (I.it) q.set("replaces", I.it.id);
    toast("Uploading…");
    res = await api("media/upload?" + q.toString(), undefined, file);
    if (!res.ok) return toast(res.error, true);
    G.lib.items.push(Object.assign({ missing: false }, res.item));
    use(s.path, res.item.url);
    toast("Uploaded and filed in the Media Library. Save & apply to use it.");
    load(true);
  }

  async function paint(s) {
    const d = G.open[s.key], I = info(s);
    if (!d || d.prompt.trim().length < 20) return toast("Write a prompt (at least 20 characters) first.", true);
    G.busy[s.key] = true;
    redraw();
    const res = await api("media/generate", { kind: s.kind, subject: s.subject, roles: [s.role], prompt: d.prompt,
      aspect: aspectOf(s), count: d.count, nsfw: "auto", tags: "graphics, regen", replaces: I.it ? I.it.id : "" });
    G.busy[s.key] = false;
    toast(res.ok ? res.msg : res.error, !res.ok);
    G.loading = false;
    load(true);
  }

  async function onClick(ev) {
    if (section !== "graphics") return;
    const el = ev.target.closest("button");
    if (!el || el.disabled) return;
    const d = el.dataset;
    if (d.gxcopytext) {
      const source = document.getElementById("gx-wordmark-html");
      try {
        await navigator.clipboard.writeText(source.value);
        toast("Text logo HTML copied.");
      } catch (error) {
        source.focus();
        source.select();
        toast("Clipboard unavailable. The HTML is selected; press Ctrl+C to copy.", true);
      }
      return;
    }
    if (d.gxnav) { ev.preventDefault(); return go(d.gxnav); }
    if (d.gxuse !== undefined) { ev.preventDefault(); return use(d.gxuse, d.url); }
    if (d.gxsize) { G.size = d.gxsize; try { localStorage.setItem("st-gx-size", G.size); } catch (x) { /* storage off */ } return redraw(); }
    if (d.gxfilter !== undefined) { G.filter = d.gxfilter; return redraw(); }
    if (d.gxreload) { G.loading = false; return load(); }
    if (d.gxhist) { G.hist[d.gxhist] = !G.hist[d.gxhist]; return redraw(); }
    if (d.gxregen) {
      const s = slotByKey(d.gxregen);
      if (G.open[s.key]) delete G.open[s.key];
      else { const I = info(s); G.open[s.key] = { prompt: (I.it && I.it.prompt) || defaultPrompt(s), count: 1 }; }
      return redraw();
    }
    if (d.gxpaint) return paint(slotByKey(d.gxpaint));
  }

  function onInput(ev) {
    if (section !== "graphics") return;
    const el = ev.target, d = el.dataset;
    if (d.gxprompt && G.open[d.gxprompt]) G.open[d.gxprompt].prompt = el.value;
    if (d.gxcount && G.open[d.gxcount]) { G.open[d.gxcount].count = +el.value || 1; if (ev.type === "change") redraw(); }
    if (d.gxup && ev.type === "change" && el.files && el.files[0]) upload(slotByKey(d.gxup), el.files[0]);
  }

  document.addEventListener("DOMContentLoaded", () => {
    const m = document.getElementById("main");
    m.addEventListener("click", onClick);
    m.addEventListener("input", onInput);
    m.addEventListener("change", onInput);
  });

  window.SeaTraderGraphics = {
    render,
    enter() { G.loading = false; load(true); },
    leave() { if (G.poll) { clearInterval(G.poll); G.poll = null; } },
  };
})();
