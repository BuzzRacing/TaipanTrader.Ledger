(function () {
  "use strict";

  const KEY_ART = "/assets/ceremony-harbor.png";
  const PALETTE = "porcelain blue, deep harbor indigo, jade, celadon paper, sail ochre and ivory canvas";
  const MASTER_STYLE = [
    "cinematic historical realism for a family-friendly merchant adventure in the China Seas circa 1860",
    "fully dressed adult characters at work, natural expressions and believable anatomy",
    PALETTE,
    "humid salt haze, weathered maritime materials, painterly depth and one clear light source",
  ].join(", ");
  const NEGATIVE = [
    "age ambiguity, modern clothes, modern ships, electric lighting, fantasy armor, steampunk, cosplay",
    "racial caricature, generic Orientalism, invented Chinese lettering, random dragon motifs",
    "plastic skin, distorted anatomy, malformed hands, duplicate limbs",
    "nudity, sexualized posing, fetishwear, graphic injury",
    "text, logo, caption, border, signature, watermark",
  ].join(", ");

  const e = value => String(value == null ? "" : value).replace(/[&<>"']/g, char =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));

  const option = (value, label) => `<option value="${e(value)}">${e(label)}</option>`;
  const copyButton = (target, label) =>
    `<button type="button" class="ab-copy" data-ab-copy="${e(target)}">${e(label || "Copy")}</button>`;

  function swatch(hex, name, use) {
    return `<div class="ab-swatch"><i style="background:${hex}"></i><div><b>${e(name)}</b><code>${hex}</code><small>${e(use)}</small></div></div>`;
  }

  function spec(label, size, ratio, notes) {
    return `<tr><td><b>${e(label)}</b></td><td class="mono">${e(size)}</td><td>${e(ratio)}</td><td>${e(notes)}</td></tr>`;
  }


  /* ------------------------------------------------------------ examples --
     Every listed item gets an image beside the exact prompt that makes it.
     Images come from the game's current art (cfg.graphics / cast portraits)
     or from the AI farm via /api/admin/imagegen/example, which keeps a
     history per slot in config/artbible_examples.json. */
  const EX = { book: {}, loaded: false, loading: null, view: {}, pick: {}, queue: [], running: null, started: 0, errors: {}, timer: 0 };
  let SLOTS = {};
  let CUR = null;

  const SIZE = { "16:5": "1600 × 500", "1:1": "1024 × 1024", "3:1": "2400 × 800", "16:9": "2560 × 1440",
    "5:3": "2000 × 1200", "18:7": "1800 × 700", "3:2": "1536 × 1024", "3:4": "1536 × 2048" };
  const AR = a => a.replace(":", " / ");

  async function adminFetch(path, body) {
    const opt = body === undefined ? {} : { method: "POST", headers: { "X-SeaTrader": "admin" }, body: JSON.stringify(body) };
    try {
      const res = await (await fetch("/api/admin/" + path, opt)).json();
      if (res.auth && typeof showLogin === "function") showLogin(res.has_password);
      return res;
    } catch (_err) {
      return { ok: false, error: "Cannot reach the game server." };
    }
  }

  function loadBook() {
    if (EX.loaded) return Promise.resolve();
    if (!EX.loading) {
      EX.loading = adminFetch("artbible/examples").then(res => {
        EX.loading = null;
        if (res.ok) { EX.book = res.examples || {}; EX.loaded = true; }
        refreshAll();
      });
    }
    return EX.loading;
  }

  function define(slot, def) {
    SLOTS[slot] = Object.assign({ slot, negative: null, current: "", size: SIZE[def.aspect] || "" }, def);
    return slot;
  }

  function shots(slot) {
    const def = SLOTS[slot] || {};
    const list = (EX.book[slot] || []).map((x, i) => ({ kind: "gen", i, url: x.url, prompt: x.prompt, seed: x.seed, date: x.date }));
    if (def.current) list.push({ kind: "game", url: def.current, prompt: def.prompt });
    return list;
  }

  function shown(slot) {
    const list = shots(slot);
    const want = EX.view[slot];
    return list.find(x => (want === "game" ? x.kind === "game" : x.kind === "gen" && x.i === want)) || list[0] || null;
  }

  function missing() {
    return Object.keys(SLOTS).filter(slot => slot !== "studio" && !SLOTS[slot].noAuto && !shots(slot).length);
  }

  function busyFor(slot) {
    return EX.running && EX.running.slot === slot;
  }

  function figure(slot, compact) {
    const def = SLOTS[slot];
    const cur = shown(slot);
    const queued = EX.queue.some(job => job.slot === slot);
    const busy = busyFor(slot);
    const badge = "";
    const art = cur
      ? `<div class="ab-ex-blur" style="background-image:url('${e(cur.url)}')"></div><img src="${e(cur.url)}" alt="${e(def.title)} example" loading="lazy" data-ab-zoom="${e(slot)}">${badge}`
      : `<div class="ab-ex-empty"><svg viewBox="0 0 64 64" aria-hidden="true"><circle cx="32" cy="32" r="22" fill="none" stroke="currentColor" stroke-width="1.2"/><path d="M32 6v52M6 32h52" stroke="currentColor" stroke-width=".8"/><path d="M32 14l5 18-5 18-5-18z" fill="currentColor" opacity=".55"/></svg><b>${queued ? "Queued for the farm" : "No example yet"}</b><span>${def.aspect} · ${e(def.size)}</span></div>`;
    const status = busy
      ? `<div class="ab-ex-busy"><i></i><b>Rendering on the farm</b><span data-ab-clock>${clock()}</span></div>`
      : (queued && cur ? `<div class="ab-ex-queued">Queued</div>` : "");
    const err = EX.errors[slot] ? `<div class="ab-ex-err">${e(EX.errors[slot])}</div>` : "";
    return `<figure class="ab-ex-art${compact ? " compact" : ""}" style="--ar:${AR(def.aspect)}">${art}${status}${err}</figure>`;
  }

  function strip(slot) {
    const list = shots(slot);
    if (list.length < 2) return "";
    const cur = shown(slot);
    return `<div class="ab-ex-strip" aria-label="Versions">${list.map(x => {
      const on = cur && x.kind === cur.kind && x.i === cur.i;
      const label = x.kind === "game" ? "Current game art" : "Version from " + (x.date || "");
      return `<button type="button" class="${on ? "on" : ""}${x.kind === "game" ? " game" : ""}" title="${e(label)}" data-ab-view="${e(slot)}" data-ab-i="${x.kind === "game" ? "game" : x.i}"><img src="${e(x.url)}" alt=""></button>`;
    }).join("")}</div>`;
  }

  function actions(slot) {
    const def = SLOTS[slot];
    const cur = shown(slot);
    const busy = busyFor(slot) || EX.queue.some(job => job.slot === slot);
    const gen = shots(slot).some(x => x.kind === "gen");
    const canUse = def.apply && cur && cur.kind === "gen" && cur.url !== def.current;
    return `<div class="ab-ex-actions">
      <button type="button" class="ab-copy" data-ab-copy="ab-p-${e(slot)}">Copy prompt</button>
      ${def.locked ? `<span class="ab-ex-lock">${e(def.locked)}</span>` : `<button type="button" class="ab-gen" data-ab-gen="${e(slot)}" ${busy ? "disabled" : ""}>${busy ? "In the queue…" : gen || def.current ? "Generate another" : "Generate example"}</button>`}
      ${canUse ? `<button type="button" class="ab-use" data-ab-use="${e(slot)}">Use in game</button>` : ""}
    </div>`;
  }

  function promptBlock(slot) {
    const def = SLOTS[slot];
    const cur = shown(slot);
    const exact = cur && cur.kind === "gen";
    const text = exact ? cur.prompt : def.prompt;
    const label = exact ? "Exact prompt for this image" : cur && cur.kind === "game" ? "Recipe for this slot" : "Prompt that will be sent";
    return `<div class="ab-ex-prompt"><span>${label}</span><p id="ab-p-${e(slot)}">${e(text)}</p></div>`;
  }

  function cardInner(slot, compact) {
    const def = SLOTS[slot];
    if (!def) return "";
    const meta = `<div class="ab-ex-meta"><b>${e(def.aspect)}</b><span>${e(def.size)}</span>${def.kicker ? `<span>${e(def.kicker)}</span>` : ""}</div>`;
    if (compact) {
      return `${figure(slot, true)}<div class="ab-ex-body"><header><h4>${e(def.title)}</h4>${meta}</header>${def.notes ? `<p class="ab-ex-note">${e(def.notes)}</p>` : ""}${strip(slot)}${promptBlock(slot)}${actions(slot)}</div>`;
    }
    return `${figure(slot, false)}<div class="ab-ex-body"><header><h3>${e(def.title)}</h3>${meta}</header>${def.notes ? `<p class="ab-ex-note">${e(def.notes)}</p>` : ""}${strip(slot)}${promptBlock(slot)}${actions(slot)}</div>`;
  }

  function card(slot, compact) {
    return `<article class="ab-ex${compact ? " compact" : ""}" data-ex="${e(slot)}" data-compact="${compact ? 1 : 0}">${cardInner(slot, compact)}</article>`;
  }

  function collection(id, title, lede, items) {
    if (!items.length) return "";
    const pick = items.some(x => x.slot === EX.pick[id]) ? EX.pick[id] : items[0].slot;
    EX.pick[id] = pick;
    return `<div class="ab-coll" data-coll="${e(id)}">
      <div class="ab-coll-head"><div><h3>${e(title)}</h3><p>${e(lede)}</p></div><span>${items.length} items</span></div>
      <div class="ab-coll-tabs" role="tablist">${items.map(x => tab(id, x, pick)).join("")}</div>
      ${card(pick, false)}
    </div>`;
  }

  function tab(id, x, pick) {
    const cur = shown(x.slot);
    return `<button type="button" role="tab" class="${x.slot === pick ? "on" : ""}" data-ab-pick="${e(id)}" data-slot="${e(x.slot)}">${cur ? `<img src="${e(cur.url)}" alt="">` : "<i>＋</i>"}<span>${e(x.label)}</span></button>`;
  }

  function refreshSlot(slot) {
    document.querySelectorAll(`#art-bible [data-ex="${slot}"]`).forEach(node => {
      node.innerHTML = cardInner(slot, node.dataset.compact === "1");
    });
    document.querySelectorAll(`#art-bible [data-ab-pick][data-slot="${slot}"]`).forEach(btn => {
      const cur = shown(slot);
      const img = btn.querySelector("img, i");
      if (img) img.outerHTML = cur ? `<img src="${e(cur.url)}" alt="">` : "<i>＋</i>";
    });
  }

  function refreshAll() {
    Object.keys(SLOTS).forEach(refreshSlot);
    refreshCoverage();
    refreshQueue();
  }

  function refreshCoverage() {
    const node = document.getElementById("ab-coverage");
    if (!node) return;
    const total = Object.keys(SLOTS).filter(s => s !== "studio").length;
    const miss = missing();
    const queued = EX.queue.length + (EX.running ? 1 : 0);
    node.innerHTML = `<div class="ab-cov-bar"><i style="width:${total ? Math.round((total - miss.length) / total * 100) : 0}%"></i></div>
      <p><b>${total - miss.length} of ${total}</b> listed items have a visual example${EX.loaded ? "" : " (loading farm history…)"}.</p>
      ${miss.length ? `<button type="button" class="ab-gen" data-ab-genall="1" ${queued ? "disabled" : ""}>Generate the ${miss.length} missing on the farm</button><small>About ${Math.max(1, Math.round(miss.length * 0.75))}–${miss.length * 2} min · runs one at a time</small>` : `<span class="ab-cov-done">Every item has an example</span>`}`;
  }

  function clock() {
    if (!EX.running) return "";
    const s = Math.floor((Date.now() - EX.started) / 1000);
    return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0");
  }

  function refreshQueue() {
    let pill = document.getElementById("ab-queue");
    const n = EX.queue.length + (EX.running ? 1 : 0);
    if (!n || !document.getElementById("art-bible")) { if (pill) pill.remove(); return; }
    if (!pill) {
      pill = document.createElement("div");
      pill.id = "ab-queue";
      document.body.appendChild(pill);
    }
    const now = EX.running ? SLOTS[EX.running.slot] : null;
    pill.innerHTML = `<i></i><div><b>${now ? e(now.title) : "Starting…"}</b><span>${EX.queue.length ? EX.queue.length + " more queued · " : ""}<em data-ab-clock>${clock()}</em></span></div>${EX.queue.length ? `<button type="button" data-ab-cancel="1">Cancel rest</button>` : ""}`;
  }

  function enqueue(slot) {
    const def = SLOTS[slot];
    if (!def || def.locked || busyFor(slot) || EX.queue.some(job => job.slot === slot)) return;
    delete EX.errors[slot];
    EX.queue.push({ slot, prompt: def.prompt, aspect: def.aspect, negative: def.negative });
    refreshSlot(slot);
    pump();
  }

  async function pump() {
    refreshQueue();
    refreshCoverage();
    if (EX.running || !EX.queue.length) return;
    EX.running = EX.queue.shift();
    EX.started = Date.now();
    clearInterval(EX.timer);
    EX.timer = setInterval(() => document.querySelectorAll("[data-ab-clock]").forEach(n => { n.textContent = clock(); }), 1000);
    refreshSlot(EX.running.slot);
    refreshQueue();
    const job = EX.running;
    const res = await adminFetch("imagegen/example", job);
    EX.running = null;
    clearInterval(EX.timer);
    if (res.ok) {
      EX.book[job.slot] = res.history;
      EX.view[job.slot] = 0;
    } else {
      EX.errors[job.slot] = res.error || "The farm could not render this one.";
      if (/cannot be reached|not configured|workflow file/i.test(EX.errors[job.slot]) && EX.queue.length) {
        EX.queue.forEach(other => { EX.errors[other.slot] = "Skipped: " + EX.errors[job.slot]; });
        const skipped = EX.queue.map(x => x.slot);
        EX.queue = [];
        skipped.forEach(refreshSlot);
      }
    }
    refreshSlot(job.slot);
    if (job.slot === "studio") refreshStudio();
    pump();
  }

  function useInGame(slot) {
    const def = SLOTS[slot];
    const cur = shown(slot);
    if (!def || !def.apply || !cur || cur.kind !== "gen" || !CUR) return;
    def.apply(CUR, cur.url);
    def.current = cur.url;
    if (typeof refreshDirty === "function") refreshDirty();
    if (typeof toast === "function") toast(def.title + " now uses this image. Save & apply to keep it.");
    EX.view[slot] = "game";
    refreshSlot(slot);
  }

  function zoom(slot) {
    const cur = shown(slot);
    if (!cur) return;
    const box = document.createElement("div");
    box.className = "ab-lightbox";
    box.innerHTML = `<figure><img src="${e(cur.url)}" alt=""><figcaption><b>${e(SLOTS[slot].title)}</b><p>${e(cur.prompt || SLOTS[slot].prompt)}</p><a href="${e(cur.url)}" target="_blank" rel="noopener">Open full size</a></figcaption></figure><button type="button" aria-label="Close">×</button>`;
    box.addEventListener("click", ev => { if (ev.target === box || ev.target.closest("button")) box.remove(); });
    document.addEventListener("keydown", function esc(ev) { if (ev.key === "Escape") { box.remove(); document.removeEventListener("keydown", esc); } });
    document.body.appendChild(box);
  }

  function refreshStudio() {
    const node = document.querySelector('#art-bible [data-ex="studio"]');
    if (node) node.innerHTML = cardInner("studio", true);
  }

  const SUBJECTS = [
    ["merchant-captain", "Woman merchant-captain", "An unmistakably adult woman (age 28+), a merchant-captain,", "surveying the harbor from the quarterdeck before a dangerous high-value trade", "an unmistakably adult woman merchant-captain"],
    ["pirate-captain", "Woman pirate captain", "An unmistakably adult woman (age 28+), a pirate captain,", "commanding the quarterdeck as a rival ship closes through cannon smoke", "an unmistakably adult woman pirate captain"],
    ["trading-house", "Woman trading-house proprietor", "An unmistakably adult woman (age 28+), a trading-house proprietor,", "weighing silver sycee on brass scales in a lantern-lit counting room", "an unmistakably adult woman who owns a trading house"],
    ["harbor-official", "Man harbor official", "An adult man, a harbor official,", "checking a cargo manifest before waving a crew through customs", "an adult man working as a harbor official"],
    ["shipwright", "Man shipwright", "An adult man, a shipwright,", "checking the fit of a new plank beside a grounded junk", "an adult man working as a shipwright"],
    ["harbor-agent", "Woman harbor agent", "An unmistakably adult woman (age 28+), a harbor agent,", "sliding a sealed bill of lading across a teahouse table on the Praya", "an unmistakably adult woman harbor agent"],
    ["rival-merchants", "Two rival merchants", "Two unmistakably adult merchants (age 28+), a man and a woman,", "bargaining hard over an open tea chest on a crowded wharf", "two unmistakably adult rival merchants, a man and a woman"],
  ];
  const LIGHTS = [
    ["golden hour through humid salt haze", "Golden hour", "Warm rim light, long shadows, haze glowing behind the masts."],
    ["lantern light against cool night sea", "Lantern night", "Sail-ochre pools of light against a deep indigo harbor."],
    ["monsoon overcast with wet highlights", "Monsoon", "Soft grey ceiling, rain-slick decks, specular highlights on wet timber."],
    ["hard tropical noon with deep awning shade", "Tropical noon", "High sun, bleached stone, deep black shade under awnings."],
    ["storm break with a shaft of sun", "Storm break", "Bruised clouds splitting open over one lit subject; maximum drama."],
  ];
  const MATERIALS = [
    ["teak", "Salt-stained teak & tarred rope", "Macro still life of salt-stained teak ship's decking and tarred hemp rope coiled around a belaying pin, crusted salt bloom, wet specular highlights, one warm lantern from the left, square composition, no person, no text. "],
    ["brass", "Hammered & patinated brass", "Macro still life of a patinated brass compass bowl, merchant scale weights and worn trade coins on deep indigo cloth, verdigris in the crevices, one warm lantern from the left, square composition, no person, no text. "],
    ["leather", "Worn black-brown leather", "Macro still life of worn black-brown leather: a captain's ledger cover, a sword belt and a sea-chest strap with tarnished brass buckles, creased grain and scuffed edges, one warm lantern from the left, square composition, no person, no text. "],
    ["silk", "Silk, linen & porcelain", "Macro still life of jade silk and ivory linen folded beside blue-and-white export porcelain on a weathered timber counter, rich fabric texture and glaze reflections, one warm lantern from the left, square composition, no person, no text. "],
  ];
  const UI_TEXTURE = "Low-contrast indigo wash over celadon ledger-paper fibers with faint salt bloom. Keep the center even and quiet under UI. No lettering, people or distinct objects. ";

  function cargoPrompt(name) {
    return "A single historically plausible " + String(name).toLowerCase() +
      " cargo arrangement on deep indigo, three-quarter view with tactile materials and soft lantern light, " +
      "square composition, clear silhouette at 30 pixels, no person, label, coin or seal. " + MASTER_STYLE;
  }
  const STUDIO_ASPECT = [["16:9", "16:9"], ["18:7", "18:7"], ["square", "1:1"], ["3:4", "3:4"], ["3:2", "3:2"]];

  function defineSlots(o) {
    const { G, goods, ports, ships, recipeStyle, subjectList } = o;
    const neg = NEGATIVE;
    const setG = key => (c, url) => { c.graphics = c.graphics || {}; c.graphics[key] = url; };
    const setGroup = (group, key) => (c, url) => { c.graphics = c.graphics || {}; c.graphics[group] = c.graphics[group] || {}; c.graphics[group][key] = url; };

    define("surf_logo", { title: "Logo / wordmark", aspect: "16:5", size: "1600 × 500 PNG", kicker: "16:5 transparent", current: G.logo, apply: setG("logo"), negative: neg.replace("text, logo, caption, border, signature, watermark", "caption, signature, watermark"),
      notes: "Transparent background. Set the approved Taipan Trader wordmark in IM Fell English SC beside the seal and test at 320 px wide.",
      prompt: "Wide Taipan Trader wordmark on a transparent background. Merchant-house seal on the left: a Chinese trading junk with sail-ochre battened sails over jade waves and an open ivory ledger, porcelain-blue rim. TAIPAN TRADER in restrained old-style small caps. Clear at 320 pixels wide." });
    define("surf_favicon", { title: "Browser icon", aspect: "1:1", size: "512 × 512 PNG", kicker: "1:1", current: G.favicon, apply: setG("favicon"), negative: neg,
      notes: "Approved merchant-house seal on a porcelain-blue tile. Test at 32 px.",
      prompt: "Merchant-house seal: a Chinese trading junk with sail-ochre battened sails over jade waves, a rounded porcelain-blue tile, bold silhouette, no lettering, readable at 32 pixels." });
    define("surf_masthead", { title: "Title masthead", aspect: "3:1", size: "2400 × 800 WebP", kicker: "3:1", current: G.masthead_bg, apply: setG("masthead_bg"), negative: neg,
      notes: "Dark left/center title-safe zone; subject may occupy outer third.",
      prompt: "Wide title banner of Victoria Harbour, Hong Kong, 1860 at golden hour: junks and a clipper at anchor, green hills in humid haze, a lantern-lit veranda rail in the outer right third, the left and center two-thirds dark and quiet for title lettering, no foreground face, no text. " + recipeStyle });
    define("surf_page", { title: "Player background", aspect: "16:9", size: "2560 × 1440 WebP", kicker: "16:9", current: G.page_bg, apply: setG("page_bg"), negative: neg,
      notes: "Low contrast under cards, detail at edges, no face behind text.",
      prompt: UI_TEXTURE + recipeStyle });
    define("surf_board", { title: "Harbor board background", aspect: "16:9", size: "3840 × 2160 WebP", kicker: "16:9", current: G.board_bg, apply: setG("board_bg"), negative: neg,
      notes: "Readable from across a room; center kept quiet for game state.",
      prompt: "Grand harbor-board backdrop: the lantern-lit interior of a Hong Kong trading-house office at night, tall windows onto a moonlit harbor full of anchored shipping, ledgers, brass scales and silk drapes pushed to the edges, the center deliberately dark and empty for game information, no person, no text. " + recipeStyle });
    define("surf_chart", { title: "Chart artwork", aspect: "5:3", size: "2000 × 1200 PNG/WebP", kicker: "5:3 exact", current: G.chart_bg, apply: setG("chart_bg"), negative: neg,
      notes: "Geographic base only. Must align to 85–135°E and 10°S–35°N. A generated chart is a mood reference; the in-game chart is built from real coastlines.",
      prompt: "Antique hand-painted nautical chart of the China Seas in 1860 seen straight from above, covering 85°E to 135°E and 10°S to 35°N: Bay of Bengal, Malay Peninsula, Sumatra, Java, Borneo, the Philippines, Indochina, the China coast and southern Japan, aged ivory paper, sea washed in storm blue, faint rhumb lines, no lettering, no border. " + recipeStyle });

    goods.forEach(([key, v]) => define("cargo_" + key, { title: "Cargo · " + (v.name || key), aspect: "1:1", size: "1024 × 1024 WebP", kicker: "Cargo icon",
      current: (G.goods || {})[key], apply: setGroup("goods", key), negative: neg,
      notes: "Single object cluster, three-quarter view, plain dark ground, readable at 30 px.",
      prompt: cargoPrompt(v.name || key) }));
    ports.forEach(([key, v]) => define("port_" + key, { title: "Port · " + (v.name || key), aspect: "18:7", size: "1800 × 700 WebP", kicker: "Port banner",
      current: (G.ports || {})[key], apply: setGroup("ports", key), negative: neg,
      notes: "Landmark/environment; horizon upper third; survives a 190 px center crop.",
      prompt: "A wide environmental portrait of " + (v.name || key) + " in the China Seas, 1860: recognizable geography and port activity, layered junks and merchant shipping, humid atmosphere, workers and traders as tiny supporting figures, strong depth, horizon in the upper third, center crop safe, no close-up face, no text. " + recipeStyle }));
    ships.forEach(([key, v]) => define("ship_" + key, { title: "Ship · " + (v.name || key), aspect: "3:2", size: "1536 × 1024 WebP", kicker: "Ship portrait",
      current: (G.ships || {})[key], apply: setGroup("ships", key), negative: neg,
      notes: "Full vessel silhouette, bow three-quarter view, weather conveys role.",
      prompt: "Full portrait of a historically plausible " + (v.name || key) + " underway in the China Seas, 1860, bow three-quarter view, entire hull and rig visible, purposeful weather and sea state expressing its role, no modern fittings, no crew close-up, no text. " + recipeStyle }));
    /* Personas are NOT defined here any more (25 Nov 2026). Cast & Voices is the only place a persona is edited, so the
       Art Bible only shows a read-only sample of the live cast (castGallery below): no saved copies, no generate button. */

    LIGHTS.forEach(([light, label, note], i) => define("light_" + (i + 1), { title: label, aspect: "16:9", size: "Mood reference", kicker: "Lighting", negative: neg, notes: note,
      prompt: "Victoria Harbour, Hong Kong, 1860: a three-masted clipper at anchor among junks and lorchas beside a teak wharf stacked with tea chests and silk bales, hills behind, environment only, no foreground character. Lighting: " + light + ". Composition: wide 16:9 with strong depth. No text. " + recipeStyle }));
    MATERIALS.forEach(([key, label, text]) => define("material_" + key, { title: label, aspect: "1:1", size: "Material study", kicker: "Material", negative: neg, prompt: text + recipeStyle }));
    subjectList.forEach(([key, label, who, action]) => define("arch_" + key.replace(/-/g, "_"), { title: label, aspect: "3:4", size: "1536 × 2048 WebP", kicker: "Archetype · dressed", negative: neg,
      notes: "Wardrobe, silhouette and status signal for this role, fully dressed so the costume reads.",
      prompt: who + " in Victoria Harbour, Hong Kong, caught while " + action + ", fully dressed in clothing grounded in 1860 maritime trade, confident posture, hands visible, original face, pose and garment design, no text. " + recipeStyle }));
    define("studio", { title: "Prompt studio preview", aspect: "16:9", size: "From composition", kicker: "Live brief", negative: neg, noAuto: true, prompt: "" });
  }

  /* The cast, read-only: up to 10 random personas, straight from Cast & Voices (name, title, portrait and the live
     portrait prompt). Nothing here is saved, generated or edited; change a persona under Cast & Voices. */
  const GALLERY_SIZE = 10;
  function castGallery(cfg) {
    const all = Object.entries((cfg && cfg.characters) || {}).filter(([, v]) => v && (v.portrait || (v.portrait_prompt || "").trim()));
    const pool = all.filter(([, v]) => v.portrait);
    const list = (pool.length >= GALLERY_SIZE ? pool : all).slice();
    for (let i = list.length - 1; i > 0; i--) {   // Fisher-Yates shuffle
      const j = Math.floor(Math.random() * (i + 1));
      [list[i], list[j]] = [list[j], list[i]];
    }
    const tiles = list.slice(0, GALLERY_SIZE).map(([key, v]) => {
      const name = v.name || key;
      const art = v.portrait
        ? `<img src="${e(v.portrait)}" alt="${e(name)}" loading="lazy" style="width:100%;aspect-ratio:3/4;object-fit:cover;border-radius:8px;display:block">`
        : `<div style="width:100%;aspect-ratio:3/4;border-radius:8px;display:grid;place-items:center;background:rgba(255,255,255,.06)"><small>No portrait yet</small></div>`;
      return `<article class="ab-rule" style="padding:8px">${art}<h4 style="margin:8px 0 0">${e(name)}</h4>
        <small>${e(v.title || "")}${v.origin ? " · " + e(v.origin) : ""}${v.age ? " · " + e(v.age) : ""}</small>
        <details><summary><small>Portrait prompt (live)</small></summary><p style="font-size:.8em">${e((v.portrait_prompt || "").trim() || "(No portrait prompt yet.)")}</p></details></article>`;
    }).join("");
    return `<div class="ab-coll"><div class="ab-coll-head"><div><h3>The cast</h3>
      <p>${list.length ? Math.min(GALLERY_SIZE, list.length) + " of " + all.length + " personas. Edit portraits and prompts in Cast &amp; Voices." : "No personas yet. Add them under Cast &amp; Voices."}</p></div>
      ${all.length > GALLERY_SIZE ? `<button type="button" class="ab-copy" data-ab-shuffle="1">Show others</button>` : ""}</div>
      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px">${tiles}</div></div>`;
  }

  function render(cfg) {
    const goods = Object.entries(cfg.goods || {}).map(([key, good]) =>
      [key, { ...good, name: good.family_name || good.name || key }]);
    const ports = Object.entries(cfg.ports || {});
    const ships = Object.entries(cfg.ships || {});
    const subjectOptions = SUBJECTS.map(x => option(x[4], x[1]))
      .concat([option("none", "No character / environment only")]).join("");
    const portOptions = ports.map(([key, value]) => option(value.name || key, value.name || key)).join("");
    const cargoOptions = goods.map(([key, value]) => option(value.name || key, value.name || key)).join("");
    const shipOptions = ships.map(([key, value]) => option(value.name || key, value.name || key)).join("");
    const recipeStyle = MASTER_STYLE;
    const characterRecipe = "A fully dressed adult [ROLE] in [PORT], caught while [ACTION], wearing period-appropriate work or formal clothes. Show purposeful posture, clear hands and a recognizable silhouette. No text. " + recipeStyle;
    const G = cfg.graphics || {};
    CUR = cfg;
    SLOTS = {};
    defineSlots({ G, goods, ports, ships, recipeStyle, subjectList: SUBJECTS });

    return `<div id="art-bible">
      <section class="ab-hero" style="--ab-mobile-image:url('${KEY_ART}');background-image:linear-gradient(90deg,rgba(11,22,29,.96) 0%,rgba(11,22,29,.76) 38%,rgba(11,22,29,.06) 76%),url('${KEY_ART}')">
        <div class="ab-hero-copy"><span class="ab-kicker">Taipan Trader · 1860 China Seas</span>
          <h1>Art Bible</h1>
          <p>A treaty-port ledger brought to life in porcelain blue, jade and sail ochre. Make the harbor feel busy, the weather consequential and every cargo worth a second look.</p>
        </div>
      </section>

      <nav class="ab-jump" aria-label="Art Bible sections">
        <a href="#ab-north-star">North star</a><a href="#ab-dna">Visual DNA</a><a href="#ab-people">People &amp; wardrobe</a>
        <a href="#ab-surfaces">Asset specs</a><a href="#ab-library">Cargo, ports &amp; ships</a><a href="#ab-prompts">Prompt studio</a><a href="#ab-qa">QA gate</a>
      </nav>
      <div class="ab-coverage" id="ab-coverage"></div>


      <section class="card ab-section" id="ab-north-star">
        <div class="ab-title"><div><h2>Brand north star</h2><p>Every image should make wealth look tactile, danger feel close and the player feel one excellent decision away from owning the harbor.</p></div></div>
        <div class="ab-grid three">
          <article class="ab-rule"><b>World</b><h3>Romanticized history</h3><p>Anchor the world in 1856–1865: Qing-era treaty ports, junks, clippers, early coastal steamers, crowded warehouses and monsoon weather. Heighten atmosphere with weather, depth and warm working lights.</p></article>
          <article class="ab-rule"><b>Player fantasy</b><h3>Build a trading house</h3><p>Show the work behind a fortune: a captain reading the tide, merchants checking a shipment, or a crew making sail before the monsoon closes in.</p></article>
          <article class="ab-rule"><b>Stakes</b><h3>Opportunity and risk</h3><p>Put something at stake in the frame. A stamped manifest, a waterlogged tea chest or a rival sail on the horizon can tell the story at a glance.</p></article>
        </div>
        <div class="ab-quote"><span>One-sentence art direction</span><p id="ab-master-line">${e(MASTER_STYLE)}.</p>${copyButton("ab-master-line", "Copy master style")}</div>
        <div class="ab-split">
          <div><h3>Historical anchors</h3><p>Keep ships, harbor geography, architecture, cargo and tools credible for the place and period. Use clothing and grooming to signal role and status. Heighten weather and lighting while keeping both physically plausible.</p></div>
          <div><h3>Working references</h3><p>Use the recipes below for new art. Review current game images and earlier renders against this palette before using them as references. For named characters, take identity and wardrobe from Cast &amp; Voices.</p></div>
        </div>
      </section>

      <section class="card ab-section" id="ab-dna">
        <div class="ab-title"><div><h2>Visual DNA</h2><p>A stable palette and material vocabulary keeps art from looking as if six unrelated games wandered into the same harbor.</p></div></div>
        <div class="ab-swatches">
          ${swatch("#0B161D", "Harbor night", "Deep backgrounds")}
          ${swatch("#12283A", "Porcelain indigo", "Deck panels and shadow")}
          ${swatch("#1F5F7A", "Porcelain blue", "Headers and primary actions")}
          ${swatch("#3F9A7F", "Jade", "Trade, success and cool accents")}
          ${swatch("#D6A84E", "Sail ochre", "Lanterns, brass and highlights")}
          ${swatch("#ECF0E4", "Celadon paper", "Ledgers and light surfaces")}
          ${swatch("#EEF1E2", "Ivory canvas", "Type, linen and sails")}
          ${swatch("#B5462A", "Cinnabar", "Warnings and losses")}
        </div>
        <div class="ab-grid three">
          <article><h3>Light</h3><ul class="ab-list"><li>Golden-hour rim light through humid haze</li><li>Lantern pools against cool sea shadow</li><li>Monsoon overcast with wet specular highlights</li><li>One dominant light direction; no flat studio wash</li></ul></article>
          <article><h3>Material</h3><ul class="ab-list"><li>Salt-stained teak and tarred rope</li><li>Hammered or patinated brass</li><li>Worn black-brown leather</li><li>Heavy silk, linen, lace and porcelain</li></ul></article>
          <article><h3>Finish</h3><ul class="ab-list"><li>Photoreal cinematic concept art</li><li>Natural pores, believable fabric tension</li><li>Restrained film grain and atmospheric depth</li><li>No plastic skin or glossy cosplay surfaces</li></ul></article>
        </div>
        <div class="ab-subhead"><h3>Lighting moods</h3><p>The same harbor under each light option in the prompt studio, so you can pick a mood by eye.</p></div>
        <div class="ab-exgrid five">${LIGHTS.map((_x, i) => card("light_" + (i + 1), true)).join("")}</div>
        <div class="ab-subhead"><h3>Material vocabulary</h3><p>Close-up studies of the four materials every image should be built from.</p></div>
        <div class="ab-exgrid four">${MATERIALS.map(x => card("material_" + x[0], true)).join("")}</div>
        <div class="ab-type"><div><span>Titles &amp; display</span><strong style="font-family:var(--title)">IM Fell English SC</strong><p>Game titles, headings in Admin, short labels and ceremonial text.</p></div><div><span>Reading text</span><strong style="font-family:var(--sans)">Libre Caslon Text</strong><p>Admin instructions and copy, with regular, bold and italic faces. Both display and reading fonts use local WOFF2 files.</p></div><div><span>Figures &amp; prompts</span><strong style="font-family:var(--mono)">Monospace</strong><p>Prices, coordinates, seeds and prompt metadata.</p></div></div>
      </section>

      <section class="card ab-section" id="ab-people">
        <div class="ab-title"><div><h2>People &amp; wardrobe</h2><p>Taipan Trader is family-friendly throughout. Show adult characters in fully dressed, period-appropriate wardrobe.</p></div></div>
        <div class="ab-callout"><b>Copyable character direction</b><p id="ab-adult-line">Foreground characters are clearly adult, fully dressed and engaged in a purposeful action. Show the role through wardrobe, tools, expression and posture.</p>${copyButton("ab-adult-line")}</div>
        <div class="ab-split">
          <div><h3>Cast direction</h3><ul class="ab-list"><li>Use adult women and men of varied East Asian, South Asian, Southeast Asian, European and mixed heritage appropriate to cosmopolitan trade ports.</li><li>Give each recurring figure a distinct silhouette, face, palette and status signal.</li><li>Favor merchants, captains, financiers, smugglers, performers and officials with agency.</li><li>Pose from intention: negotiating, surveying, concealing, commanding or celebrating—not merely standing near a ship.</li></ul></div>
          <div><h3>Cultural detail</h3><ul class="ab-list"><li>Choose garments and grooming specific to the character’s community, place and date.</li><li>Show people from different communities as owners, workers, officials and crew.</li><li>Use a verified inscription when a scene needs legible lettering. Leave lettering out of generated art.</li></ul></div>
        </div>
        ${collection("arch", "Style examples (not cast members)", "Generic wardrobe and silhouette studies for the prompt studio. They are not personas; the real characters are in Cast & Voices.", SUBJECTS.map(x => ({ slot: "arch_" + x[0].replace(/-/g, "_"), label: x[1] })))}
        <div id="ab-cast-gallery">${castGallery(cfg)}</div>
        <div class="ab-dont"><div><b>Use</b><p>Distinct silhouettes, practical clothing, natural expressions and props that establish the character’s work.</p></div><div><b>Avoid</b><p>Sexualized framing, cultural caricature, copied faces and modern costume details.</p></div></div>
      </section>

      <section class="card ab-section" id="ab-surfaces">
        <div class="ab-title"><div><h2>Asset system &amp; delivery specs</h2><p>Generate larger than display size, keep the focal subject inside the crop-safe area, then export web-ready derivatives.</p></div></div>
        <div class="ab-exlist">${["surf_logo", "surf_favicon", "surf_masthead", "surf_page", "surf_board", "surf_chart"].map(slot => card(slot, false)).join("")}</div>
        <details class="ab-details"><summary>All specs as a table</summary><div class="scroll"><table class="ab-spec"><thead><tr><th>Asset</th><th>Master size</th><th>Shape</th><th>Composition and delivery</th></tr></thead><tbody>
          ${spec("Logo / wordmark", "1600 × 500 PNG", "16:5 transparent", "No baked background. Test at 320 px wide and on dark teak.")}
          ${spec("Browser icon", "512 × 512 PNG", "1:1", "Approved merchant-house seal on a porcelain-blue tile. Test at 32 px.")}
          ${spec("Title masthead", "2400 × 800 WebP", "3:1", "Dark left/center title-safe zone; subject may occupy outer third.")}
          ${spec("Player background", "2560 × 1440 WebP", "16:9", "Low contrast under cards, detail at edges, no face behind text.")}
          ${spec("Harbor board background", "3840 × 2160 WebP", "16:9", "Readable from across a room; center kept quiet for game state.")}
          ${spec("Chart artwork", "2000 × 1200 PNG/WebP", "5:3 exact", "Geographic base only. Must align to 85–135°E and 10°S–35°N.")}
          ${spec("Cargo icon", "1024 × 1024 WebP", "1:1", "Single object cluster, three-quarter view, plain dark ground, readable at 30 px.")}
          ${spec("Port banner", "1800 × 700 WebP", "18:7", "Landmark/environment; horizon upper third; survives a 190 px center crop.")}
          ${spec("Ship portrait", "1536 × 1024 WebP", "3:2", "Full vessel silhouette, bow three-quarter view, weather conveys role.")}
          ${spec("Character / event art", "1536 × 2048 WebP", "3:4", "Knees-up or full figure; hands visible; keep alternate 16:9 crop in mind.")}
        </tbody></table></div></details>
        <div id="ab-library" class="ab-library">
          ${collection("cargo", "Cargo icons", "Each trade good beside its filled-in cargo recipe.", goods.map(([k, v]) => ({ slot: "cargo_" + k, label: v.name || k })))}
          ${collection("ports", "Port banners", "Each port of call beside its filled-in port recipe.", ports.map(([k, v]) => ({ slot: "port_" + k, label: v.name || k })))}
          ${collection("ships", "Ship portraits", "Each hull type beside its filled-in ship recipe.", ships.map(([k, v]) => ({ slot: "ship_" + k, label: v.name || k })))}
        </div>
        <div class="ab-grid three">
          <article><h3>Master</h3><p>Keep the highest-quality PNG or lossless source outside <code>web/</code>, with prompt, seed, model/workflow and date beside it.</p></article>
          <article><h3>Web delivery</h3><p>Use WebP for art, PNG for transparency, SVG only for hand-built marks. Aim under 500 KB per UI image and under 1.5 MB for large backgrounds.</p></article>
          <article><h3>Filename</h3><p><code>historical_surface_subject_mood_v01.webp</code><br>Example: <code>historical_port_hongkong_lanterns_v03.webp</code>.</p></article>
        </div>
        <div class="ab-safe"${G.masthead_bg ? ` style="background-image:linear-gradient(rgba(13,9,7,.35),rgba(13,9,7,.35)),url('${e(G.masthead_bg)}')"` : ""}><div><b>Desktop safe area</b><i></i></div><div><b>Phone crop</b><i></i></div><p>Keep faces, hands, cargo labels and ship silhouettes inside the center 60%. Put atmospheric detail and expendable scenery in the outer 20% on each side.</p></div>
      </section>

      <section class="card ab-section" id="ab-prompts">
        <div class="ab-title"><div><h2>AI Farm prompt studio</h2><p>Build a production brief, copy it into the current local workflow, and preserve the returned workflow metadata with the asset.</p></div></div>
        <div class="ab-builder">
          <div class="ab-controls">
            <label>Asset type<select data-ab-field="asset"><option value="cinematic key art">Cinematic key art</option><option value="port banner">Port banner</option><option value="ship portrait">Ship portrait</option><option value="cargo icon">Cargo icon</option><option value="character or event portrait">Character / event portrait</option><option value="subtle UI background texture">UI background</option></select></label>
            <label>Subject<select data-ab-field="subject">${subjectOptions}</select></label>
            <label>Port / setting<select data-ab-field="place"><option value="Victoria Harbour, Hong Kong">Victoria Harbour, Hong Kong</option>${portOptions}</select></label>
            <label>Cargo focus<select data-ab-field="cargo"><option value="none">None</option>${cargoOptions}</select></label>
            <label>Ship focus<select data-ab-field="ship"><option value="period trading vessel">Period trading vessel</option>${shipOptions}</select></label>
            <label>Light<select data-ab-field="light"><option>golden hour through humid salt haze</option><option>lantern light against cool night sea</option><option>monsoon overcast with wet highlights</option><option>hard tropical noon with deep awning shade</option><option>storm break with a shaft of sun</option></select></label>
            <label>Scene mood<select data-ab-field="mood"><option>purposeful maritime adventure</option><option>busy market and friendly rivalry</option><option>quiet concentration before departure</option><option>tense weather and a crew working together</option></select></label>
            <label>Composition<select data-ab-field="composition"><option>wide 16:9, subject in the right third, dark negative space on the left for UI</option><option>wide 18:7 environmental banner, no close foreground face, center crop safe</option><option>square centered object, clear silhouette, readable at icon size</option><option>vertical 3:4 full figure, hands visible, uncropped limbs</option><option>landscape 3:2, full vessel in bow three-quarter view</option></select></label>
            <label class="wide">Specific moment or object<input data-ab-field="moment" value="checking the harbor traffic and wind before bringing a cargo of tea alongside" maxlength="220"></label>
          </div>
          <div class="ab-prompt-output">
            <div class="ab-code-head"><b>Positive prompt</b>${copyButton("ab-positive")}</div><textarea id="ab-positive" class="code" rows="16" readonly></textarea>
            <div class="ab-code-head"><b>Negative prompt</b>${copyButton("ab-negative")}</div><textarea id="ab-negative" class="code" rows="9" readonly>${e(NEGATIVE)}</textarea>
          </div>
          <div class="ab-studio-preview"><div class="ab-code-head"><b>What this brief generates</b><small>Sent to the farm exactly as shown, at the composition's aspect ratio</small></div>${card("studio", true)}</div>
        </div>
        <details class="ab-details"><summary>Production settings &amp; metadata card</summary><div class="ab-split"><div><h3>Farm starting point</h3><ul class="ab-list"><li>Use the farm’s best photoreal checkpoint/workflow; do not hard-code a model name into the brand.</li><li>Start at the master aspect ratio above, not square-and-crop for banners.</li><li>Keep CFG/steps at the workflow’s proven defaults; style consistency beats random knob theater.</li><li>Generate four drafts, select composition first, then iterate one change at a time.</li></ul></div><div><h3>Save beside every master</h3><p><code>asset_id · surface · mode=historical · prompt · negative · model · workflow · seed · width · height · sampler · steps · cfg · date · approval</code></p><p class="help">This is the minimum recipe needed to reproduce or repair an image six months later.</p></div></div></details>
        <details class="ab-details"><summary>Copy-ready specialist recipes</summary><div class="ab-recipes">
          ${recipe("Cargo icon", cargoPrompt("[CARGO]"))}
          ${recipe("Port banner", "A wide environmental portrait of [PORT] in the China Seas, 1860: recognizable geography and port activity, layered junks and merchant shipping, humid atmosphere, workers and traders as tiny supporting figures, strong depth, horizon in the upper third, center crop safe, no close-up face, no text. " + recipeStyle)}
          ${recipe("Ship portrait", "Full portrait of a historically plausible [SHIP] underway in the China Seas, 1860, bow three-quarter view, entire hull and rig visible, purposeful weather and sea state expressing its role, no modern fittings, no crew close-up, no text. " + recipeStyle)}
          ${recipe("Character portrait", characterRecipe)}
          ${recipe("UI texture", UI_TEXTURE + recipeStyle)}
        </div></details>
      </section>

      <section class="card ab-section" id="ab-qa">
        <div class="ab-title"><div><h2>Approval gate</h2><p>An image is not finished because the generator stopped. It ships only when every applicable check passes at actual UI size.</p></div></div>
        <div class="ab-checks">
          ${checkGroup("Canon", ["Reads as 1860 China Seas before it reads as generic pirate fantasy", "Matches the approved palette, materials and cinematic finish", "Adds trade, danger or ambition—not decoration alone"])}
          ${checkGroup("People", ["Foreground characters read as fully dressed adults", "Faces, hands and wardrobe hold up at display size", "Pose and props show what each character is doing", "Named characters match their Cast & Voices reference"])}
          ${checkGroup("History", ["Ship type, cargo, tools and architecture are plausible", "No modern closure, heel, light, vessel or prop slipped through", "Any non-English lettering is verified or omitted", "Cultural specificity replaces stereotype"])}
          ${checkGroup("UI", ["Correct aspect ratio and master dimensions", "Subject survives desktop and phone crops", "Text zone is genuinely quiet", "Thumbnail remains readable; WebP size is reasonable"])}
          ${checkGroup("Record", ["Prompt and negative prompt saved", "Model, workflow, seed and settings saved", "Master and web derivative use canonical filenames", "Approved version is identifiable without opening five mystery files"])}
        </div>
        <div class="ab-final"><b>Fast rejection rule</b><p>If it looks like cosplay, a travel poster, a pin-up pasted onto a harbor, or a fantasy pirate from the wrong century, reject it before polishing. Expensive wrong is still wrong.</p></div>
      </section>
    </div>`;
  }

  function recipe(title, text) {
    const id = "ab-recipe-" + title.toLowerCase().replace(/[^a-z]+/g, "-");
    return `<article><div class="ab-code-head"><b>${e(title)}</b>${copyButton(id)}</div><p id="${id}">${e(text)}</p></article>`;
  }

  function checkGroup(title, items) {
    return `<fieldset><legend>${e(title)}</legend>${items.map(item => `<label><input type="checkbox"> <span>${e(item)}</span></label>`).join("")}</fieldset>`;
  }

  function buildPrompt() {
    const root = document.getElementById("art-bible");
    if (!root) return;

    const value = name => {
      const control = root.querySelector(`[data-ab-field="${name}"]`);
      return control ? control.value.trim() : "";
    };
    const subject = value("subject") === "none" ? "environment only, no foreground character" : value("subject");
    const cargo = value("cargo") === "none" ? "" : ` Cargo focus: ${value("cargo")}, shown accurately and secondary to the scene.`;
    const ship = value("ship") ? ` Vessel: ${value("ship")}, historically plausible for 1860.` : "";
    const constraints = "fully dressed adult foreground characters, purposeful action, original faces and garments, believable anatomy and period details, no text, logo, border, signature or watermark";
    const prompt = `Use case: historical-scene\nAsset type: Taipan Trader ${value("asset")}\nPrimary request: ${subject} in ${value("place")}, ${value("moment")}.\nWorld and style: ${MASTER_STYLE}.\nLighting: ${value("light")}.\nMood: ${value("mood")}.\nComposition: ${value("composition")}.${cargo}${ship}\nConstraints: ${constraints}.`;
    const out = root.querySelector("#ab-positive");
    if (out) out.value = prompt;
    if (SLOTS.studio) {
      const comp = value("composition");
      const hit = STUDIO_ASPECT.find(x => comp.indexOf(x[0]) >= 0);
      SLOTS.studio.prompt = prompt;
      SLOTS.studio.aspect = hit ? hit[1] : "16:9";
      SLOTS.studio.size = SIZE[SLOTS.studio.aspect] || "";
      SLOTS.studio.negative = NEGATIVE;
      refreshStudio();
    }
    const negative = root.querySelector("#ab-negative");
    if (negative) negative.value = NEGATIVE;
  }

  async function copyText(text) {
    try {
      await navigator.clipboard.writeText(text);
    } catch (_err) {
      const area = document.createElement("textarea");
      area.value = text;
      area.style.position = "fixed";
      area.style.opacity = "0";
      document.body.appendChild(area);
      area.select();
      document.execCommand("copy");
      area.remove();
    }
  }

  document.addEventListener("click", async event => {
    const button = event.target.closest("[data-ab-copy]");
    if (!button) return;
    const target = document.getElementById(button.dataset.abCopy);
    if (!target) return;
    const text = "value" in target ? target.value : target.textContent.trim();
    await copyText(text);
    const old = button.textContent;
    button.textContent = "Copied";
    setTimeout(() => { if (button.isConnected) button.textContent = old; }, 1300);
  });
  document.addEventListener("input", event => {
    if (event.target.closest("#art-bible [data-ab-field]")) buildPrompt();
  });
  document.addEventListener("change", event => {
    if (event.target.closest("#art-bible [data-ab-field]")) buildPrompt();
  });

  function hydrate() {
    buildPrompt();
    refreshCoverage();
    refreshQueue();
    if (!EX.running && !EX.loading) EX.loaded = false;   // re-read history so deleted images drop out
    loadBook();
  }

  document.addEventListener("click", event => {
    const t = event.target;
    if (!t.closest || !t.closest("#art-bible, #ab-queue")) return;
    if (t.closest("[data-ab-shuffle]")) {
      const box = document.getElementById("ab-cast-gallery");
      if (box && CUR) box.innerHTML = castGallery(CUR);
      return;
    }
    const gen = t.closest("[data-ab-gen]");
    if (gen) return enqueue(gen.dataset.abGen);
    const all = t.closest("[data-ab-genall]");
    if (all) { missing().forEach(enqueue); return; }
    const use = t.closest("[data-ab-use]");
    if (use) return useInGame(use.dataset.abUse);
    const view = t.closest("[data-ab-view]");
    if (view) {
      EX.view[view.dataset.abView] = view.dataset.abI === "game" ? "game" : Number(view.dataset.abI);
      return refreshSlot(view.dataset.abView);
    }
    const pick = t.closest("[data-ab-pick]");
    if (pick) {
      const coll = pick.closest("[data-coll]");
      EX.pick[pick.dataset.abPick] = pick.dataset.slot;
      coll.querySelectorAll("[data-ab-pick]").forEach(b => b.classList.toggle("on", b === pick));
      const holder = coll.querySelector("[data-ex]");
      holder.dataset.ex = pick.dataset.slot;
      holder.innerHTML = cardInner(pick.dataset.slot, false);
      return;
    }
    const z = t.closest("[data-ab-zoom]");
    if (z) return zoom(z.dataset.abZoom);
    if (t.closest("[data-ab-cancel]")) {
      const dropped = EX.queue.map(x => x.slot);
      EX.queue = [];
      dropped.forEach(refreshSlot);
      refreshQueue();
      refreshCoverage();
    }
  });

  window.SeaTraderArtBible = { render, hydrate, generate: slots => [].concat(slots).forEach(enqueue), masterStyle: MASTER_STYLE, negative: NEGATIVE };
}());
