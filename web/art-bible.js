(function () {
  "use strict";

  const KEY_ART = "/assets/sea-trader-historical-key-art.png";
  const MASTER_STYLE = [
    "romanticized cinematic historical realism set in the China Seas in 1860",
    "private-release adult power fantasy with erotic after-hours glamour",
    "humid salt haze, natural skin, believable anatomy, weathered maritime materials",
    "lacquer black, oxblood silk, antique brass, imperial jade, ivory and storm blue",
    "premium tabletop-game key art, richly textured, dramatic but plausible lighting",
  ].join(", ");
  const FAMILY_STYLE = [
    "romanticized cinematic historical realism set in the China Seas in 1860",
    "family-friendly maritime adventure with confident fully dressed adult characters",
    "humid salt haze, natural skin, believable anatomy, weathered maritime materials",
    "lacquer black, oxblood silk, antique brass, imperial jade, ivory and storm blue",
    "premium tabletop-game key art, richly textured, dramatic but plausible lighting",
  ].join(", ");
  const NEGATIVE_PARTS = [
    "minor, teen, child, youthful face, school uniform, age ambiguity",
    "modern clothing, zipper, latex, stiletto heel, modern ship, electric light",
    "generic fantasy armor, steampunk machinery, cosplay plastic, Halloween costume",
    "racial caricature, generic Orientalism, faux Asian lettering, random dragon motif",
    "plastic skin, airbrushed anatomy, doll face, extra fingers, malformed hands, duplicate limbs",
    "explicit sexual act, sexual violence, coercion, non-consensual scenario",
    "text, logo, caption, border, signature, watermark",
  ];
  const NEGATIVE = NEGATIVE_PARTS.join(", ");
  const FAMILY_NEGATIVE = NEGATIVE_PARTS.concat([
    "nudity, exposed breasts, exposed genitals, erotic pose, fetishwear, bondage, kink imagery",
  ]).join(", ");

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
    ["harbor-agent", "Woman harbor agent", "An unmistakably adult woman (age 28+), a harbor agent,", "sliding a sealed bill of lading across a teahouse table on the Praya", "an unmistakably adult woman harbor agent"],
    ["rival-merchants", "Two rival merchant women", "Two unmistakably adult women (age 28+), rival merchants,", "bargaining hard over an open tea chest on a crowded wharf", "two unmistakably adult women, rival merchants"],
  ];
  const LIGHTS = [
    ["golden hour through humid salt haze", "Golden hour", "Warm rim light, long shadows, haze glowing behind the masts."],
    ["lantern light against cool night sea", "Lantern night", "Warm lantern pools against a cold blue harbor; the after-hours look."],
    ["monsoon overcast with wet highlights", "Monsoon", "Soft grey ceiling, rain-slick decks, specular highlights on wet timber."],
    ["hard tropical noon with deep awning shade", "Tropical noon", "High sun, bleached stone, deep black shade under awnings."],
    ["storm break with a shaft of sun", "Storm break", "Bruised clouds splitting open over one lit subject; maximum drama."],
  ];
  const MATERIALS = [
    ["teak", "Salt-stained teak & tarred rope", "Macro still life of salt-stained teak ship's decking and tarred hemp rope coiled around a belaying pin, crusted salt bloom, wet specular highlights, one warm lantern from the left, square composition, no person, no text. "],
    ["brass", "Hammered & patinated brass", "Macro still life of hammered and patinated antique brass: a ship's compass bowl, merchant scale weights and worn trade coins on a lacquer-black surface, verdigris in the crevices, one warm lantern from the left, square composition, no person, no text. "],
    ["leather", "Worn black-brown leather", "Macro still life of worn black-brown leather: a captain's ledger cover, a sword belt and a sea-chest strap with tarnished brass buckles, creased grain and scuffed edges, one warm lantern from the left, square composition, no person, no text. "],
    ["silk", "Silk, linen, lace & porcelain", "Macro still life of heavy oxblood silk, ivory linen and lace folded beside blue-and-white export porcelain on a lacquer tray, rich fabric tension and glaze reflections, one warm lantern from the left, square composition, no person, no text. "],
  ];
  const TIERS = [
    ["I · Smolder", "Atmosphere", "Close eye contact, rolled sleeves, open collar, damp hair, fitted waist, lantern light. Use for markets, rules and general UI art."],
    ["II · Sultry", "Dressed heat", "Corsetry, deep neckline, exposed thigh or shoulder, sheer layers and a commanding pose. Provocative and credible inside the scene."],
    ["III · Nude glamour", "Exposed", "Bare breasts or buttocks, optional full-frontal adult nudity and a deliberately erotic pose. Story-led, natural and visibly adult."],
    ["IV · Private after hours", "Historical default", "Exposed breasts, buttocks or genitals; bold erotic posing; and consensual kink cues built from silk, rope, leather and power exchange. Adult agency stays unmistakable."],
  ];
  const STUDIO_ASPECT = [["16:9", "16:9"], ["18:7", "18:7"], ["square", "1:1"], ["3:4", "3:4"], ["3:2", "3:2"]];

  function defineSlots(o) {
    const { cfg, G, goods, ports, ships, familyMode, recipeStyle, heatList } = o;
    const neg = familyMode ? FAMILY_NEGATIVE : NEGATIVE;
    const setG = key => (c, url) => { c.graphics = c.graphics || {}; c.graphics[key] = url; };
    const setGroup = (group, key) => (c, url) => { c.graphics = c.graphics || {}; c.graphics[group] = c.graphics[group] || {}; c.graphics[group][key] = url; };

    define("surf_logo", { title: "Logo / wordmark", aspect: "16:5", size: "1600 × 500 PNG", kicker: "16:5 transparent", current: G.logo, apply: setG("logo"), negative: neg,
      notes: "No baked background. Test at 320 px wide and on dark teak. The game name itself is set in Uncial Antiqua, so the art is the emblem only.",
      prompt: "Sea Trader emblem artwork for a wide wordmark: an engraved antique-brass maritime crest combining a compass rose, a furled square sail and a merchant's balance in a horizontal cartouche, on a plain pure-black ground for easy cut-out, crisp silhouette, no lettering, readable at 320 pixels wide. " + recipeStyle });
    define("surf_favicon", { title: "Browser icon", aspect: "1:1", size: "512 × 512 PNG", kicker: "1:1", current: G.favicon, apply: setG("favicon"), negative: neg,
      notes: "One brass mark: coin, sail or ST monogram. Must read at 32 px.",
      prompt: "A single antique-brass trade coin stamped with a full-bellied square sail, centered on plain black, bold simple silhouette, high contrast, no lettering, designed to read at 32 pixels. " + recipeStyle });
    define("surf_masthead", { title: "Title masthead", aspect: "3:1", size: "2400 × 800 WebP", kicker: "3:1", current: G.masthead_bg, apply: setG("masthead_bg"), negative: neg,
      notes: "Dark left/center title-safe zone; subject may occupy outer third.",
      prompt: "Wide title banner of Victoria Harbour, Hong Kong, 1860 at golden hour: junks and a clipper at anchor, green hills in humid haze, a lantern-lit veranda rail in the outer right third, the left and center two-thirds dark and quiet for title lettering, no foreground face, no text. " + recipeStyle });
    define("surf_page", { title: "Player background", aspect: "16:9", size: "2560 × 1440 WebP", kicker: "16:9", current: G.page_bg, apply: setG("page_bg"), negative: neg,
      notes: "Low contrast under cards, detail at edges, no face behind text.",
      prompt: "Seamless-feeling low-contrast field of dark lacquered teak, ledger paper fibers, faint salt bloom and restrained antique-brass corner ornament, no central object, no readable writing, no face, designed to sit behind light UI cards without competing. " + recipeStyle });
    define("surf_board", { title: "Harbor board background", aspect: "16:9", size: "3840 × 2160 WebP", kicker: "16:9", current: G.board_bg, apply: setG("board_bg"), negative: neg,
      notes: "Readable from across a room; center kept quiet for game state.",
      prompt: "Grand harbor-board backdrop: the lantern-lit interior of a Hong Kong trading-house office at night, tall windows onto a moonlit harbor full of anchored shipping, ledgers, brass scales and silk drapes pushed to the edges, the center deliberately dark and empty for game information, no person, no text. " + recipeStyle });
    define("surf_chart", { title: "Chart artwork", aspect: "5:3", size: "2000 × 1200 PNG/WebP", kicker: "5:3 exact", current: G.chart_bg, apply: setG("chart_bg"), negative: neg,
      notes: "Geographic base only. Must align to 85–135°E and 10°S–35°N. A generated chart is a mood reference; the in-game chart is built from real coastlines.",
      prompt: "Antique hand-painted nautical chart of the China Seas in 1860 seen straight from above, covering 85°E to 135°E and 10°S to 35°N: Bay of Bengal, Malay Peninsula, Sumatra, Java, Borneo, the Philippines, Indochina, the China coast and southern Japan, aged ivory paper, sea washed in storm blue, faint rhumb lines, no lettering, no border. " + recipeStyle });

    goods.forEach(([key, v]) => define("cargo_" + key, { title: "Cargo · " + (v.name || key), aspect: "1:1", size: "1024 × 1024 WebP", kicker: "Cargo icon",
      current: (G.goods || {})[key], apply: setGroup("goods", key), negative: neg,
      notes: "Single object cluster, three-quarter view, plain dark ground, readable at 30 px.",
      prompt: "A single historically plausible " + String(v.name || key).toLowerCase() + " trade-goods arrangement on a lacquer-black surface: tactile material, antique brass merchant token for scale, three-quarter product view, soft directional lantern light, square composition, clean silhouette, no person, no label, readable at 30 pixels. " + recipeStyle }));
    ports.forEach(([key, v]) => define("port_" + key, { title: "Port · " + (v.name || key), aspect: "18:7", size: "1800 × 700 WebP", kicker: "Port banner",
      current: (G.ports || {})[key], apply: setGroup("ports", key), negative: neg,
      notes: "Landmark/environment; horizon upper third; survives a 190 px center crop.",
      prompt: "A wide environmental portrait of " + (v.name || key) + " in the China Seas, 1860: recognizable geography and port activity, layered junks and merchant shipping, humid atmosphere, workers and traders as tiny supporting figures, strong depth, horizon in the upper third, center crop safe, no close-up face, no text. " + recipeStyle }));
    ships.forEach(([key, v]) => define("ship_" + key, { title: "Ship · " + (v.name || key), aspect: "3:2", size: "1536 × 1024 WebP", kicker: "Ship portrait",
      current: (G.ships || {})[key], apply: setGroup("ships", key), negative: neg,
      notes: "Full vessel silhouette, bow three-quarter view, weather conveys role.",
      prompt: "Full portrait of a historically plausible " + (v.name || key) + " underway in the China Seas, 1860, bow three-quarter view, entire hull and rig visible, purposeful weather and sea state expressing its role, no modern fittings, no crew close-up, no text. " + recipeStyle }));
    Object.entries(cfg.characters || {}).forEach(([key, v]) => {
      if (!v || !(v.portrait_prompt || v.portrait)) return;
      define("cast_" + key, { title: (v.name || key), aspect: "3:4", size: "1536 × 2048 WebP", kicker: v.title || "Cast portrait",
        current: v.portrait || "", apply: (c, url) => { if (c.characters && c.characters[key]) c.characters[key].portrait = url; },
        locked: (v.portrait_prompt || "").trim().length < 20 ? "Write this character's portrait prompt under Cast & Voices" : "",
        notes: "Uses the portrait prompt from Cast & Voices, so the image here is exactly what that character's prompt produces.",
        prompt: (v.portrait_prompt || "").trim() || "(No portrait prompt yet.)" });
    });

    LIGHTS.forEach(([light, label, note], i) => define("light_" + (i + 1), { title: label, aspect: "16:9", size: "Mood reference", kicker: "Lighting", negative: neg, notes: note,
      prompt: "Victoria Harbour, Hong Kong, 1860: a three-masted clipper at anchor among junks and lorchas beside a teak wharf stacked with tea chests and silk bales, hills behind, environment only, no foreground character. Lighting: " + light + ". Composition: wide 16:9 with strong depth. No text. " + recipeStyle }));
    MATERIALS.forEach(([key, label, text]) => define("material_" + key, { title: label, aspect: "1:1", size: "Material study", kicker: "Material", negative: neg, prompt: text + recipeStyle }));
    o.subjectList.forEach(([key, label, who, action]) => define("arch_" + key.replace(/-/g, "_"), { title: label, aspect: "3:4", size: "1536 × 2048 WebP", kicker: "Archetype · dressed", negative: neg,
      notes: "Wardrobe, silhouette and status signal for this role, fully dressed so the costume reads.",
      prompt: who + " in Victoria Harbour, Hong Kong, caught while " + action + ", fully dressed in clothing grounded in 1860 maritime trade, confident posture and clear agency, hands visible, original faces, poses and garment design, no text. " + (familyMode ? FAMILY_STYLE : recipeStyle + ". Tone: smolder: restrained sensuality through gaze, tailoring and posture") }));
    heatList.forEach((heat, i) => define("heat_" + (i + 1), { title: TIERS[i] ? TIERS[i][0] : "Tier " + (i + 1), aspect: "3:4", size: "1536 × 2048 WebP", kicker: "Sensuality tier", negative: NEGATIVE,
      prompt: "An unmistakably adult woman (age 28+), a merchant-captain, in Victoria Harbour, Hong Kong, caught while surveying the harbor before a dangerous high-value trade; clear agency, hands visible, original face, pose and garment design, no explicit sex act, no text. Tone: " + heat + ". " + MASTER_STYLE }));
    define("studio", { title: "Prompt studio preview", aspect: "16:9", size: "From composition", kicker: "Live brief", negative: neg, noAuto: true, prompt: "" });
  }

  function render(cfg) {
    const familyMode = Boolean(cfg.content && cfg.content.rating === "family");
    const goods = Object.entries(cfg.goods || {});
    const ports = Object.entries(cfg.ports || {});
    const ships = Object.entries(cfg.ships || {});
    const subjectOptions = [option("an unmistakably adult woman pirate queen, a commanding beauty who rules her own fleet", "★ Pirate queen (default)")]
      .concat(SUBJECTS.map(x => option(x[4], x[1])))
      .concat([`<optgroup label="Men (if a scene needs one)">`,
        option("an unmistakably adult man merchant-captain", "Man merchant-captain"),
        option("an unmistakably adult man pirate captain", "Man pirate captain"),
        option("an unmistakably adult man harbor official", "Man harbor official"),
        option("an unmistakably adult pirate queen and an adult man rival captain", "Pirate queen with a man rival"),
        "</optgroup>"])
      .concat([option("none", "No character / environment only")]).join("");
    const portOptions = ports.map(([key, value]) => option(value.name || key, value.name || key)).join("");
    const cargoOptions = goods.map(([key, value]) => option(value.name || key, value.name || key)).join("");
    const shipOptions = ships.map(([key, value]) => option(value.name || key, value.name || key)).join("");
    const heatOptions = familyMode
      ? '<option selected value="family-safe: fully dressed adults, confident posture, no erotic framing, nudity or kink imagery">Family · Dressed adventure</option>'
      : '<option value="smolder: restrained sensuality through gaze, tailoring and posture">I · Smolder</option>' +
        '<option value="sultry: deep neckline, exposed thigh, corsetry and commanding adult glamour">II · Sultry</option>' +
        '<option value="nude glamour: exposed breasts or buttocks, optional full-frontal adult nudity and a deliberately erotic pose">III · Nude glamour</option>' +
        '<option selected value="private after hours: explicit adult nudity may expose breasts, buttocks and genitals; bold erotic posing and consensual kink cues using period-plausible silk, rope and leather; commanding agency">IV · Private after hours</option>';
    const recipeStyle = familyMode ? FAMILY_STYLE : MASTER_STYLE;
    const characterRecipe = familyMode
      ? "An unmistakably adult woman (age 28+), a [ROLE — default: pirate queen], in [PORT], caught while [ACTION], fully dressed in clothing grounded in 1860 maritime trade, confident posture and clear agency, hands visible, original face, pose and garment design, no erotic framing, nudity or kink imagery, no text. " + FAMILY_STYLE
      : "An unmistakably adult woman (age 28+), a [ROLE — default: pirate queen], in [PORT], caught while [ACTION], commanding adult erotic confidence and clear agency; private-release nudity may expose breasts, buttocks or genitals, and consensual kink styling may use period-plausible silk, rope or leather; hands visible, original face, pose and garment design, no explicit sex act, no text. " + MASTER_STYLE;
    const heatList = familyMode ? [] : Array.from(heatOptions.matchAll(/value="([^"]+)"/g), m => m[1].replace(/&amp;/g, "&"));
    const G = cfg.graphics || {};
    CUR = cfg;
    SLOTS = {};
    defineSlots({ cfg, G, goods, ports, ships, familyMode, recipeStyle, heatList, subjectList: SUBJECTS });

    return `<div id="art-bible" data-family="${familyMode ? "true" : "false"}">
      <section class="ab-hero" style="--ab-mobile-image:url('${KEY_ART}');background-image:linear-gradient(90deg,rgba(13,9,7,.96) 0%,rgba(13,9,7,.74) 38%,rgba(13,9,7,.06) 76%),url('${KEY_ART}')">
        <div class="ab-hero-copy"><span class="ab-kicker">Historical mode · visual canon v1.1</span>
          <h1>Silk, salt<br><em>&amp; dangerous money.</em></h1>
          <p>Sea Trader is a private-release adult 1860s China Seas power fantasy: trade, appetite, kink, risk and ambition rendered with cinematic historical realism.</p>
          <div class="ab-tags"><span>1860 China Seas</span><span>Adults 25+ only</span><span>Nudity permitted</span><span>Private release</span></div>
        </div>
      </section>

      <nav class="ab-jump" aria-label="Art Bible sections">
        <a href="#ab-north-star">North star</a><a href="#ab-dna">Visual DNA</a><a href="#ab-people">People &amp; erotic tone</a>
        <a href="#ab-surfaces">Asset specs</a><a href="#ab-library">Cargo, ports &amp; ships</a><a href="#ab-prompts">Prompt studio</a><a href="#ab-qa">QA gate</a>
      </nav>
      <div class="ab-coverage" id="ab-coverage"></div>

      <div class="ab-callout"><b>${familyMode ? "Family-friendly switch is active" : "Historical private-release mode is active"}</b><p>${familyMode ? "The prompt studio is locked to dressed, non-erotic art. Existing uploaded graphics are not replaced automatically." : "Adult nudity, exposed breasts or genitals, erotic posing and consensual period-grounded kink direction are permitted. Family-friendly remains the sharing switch."}</p></div>

      <section class="card ab-section" id="ab-north-star">
        <div class="ab-title"><span>01</span><div><h2>Brand north star</h2><p>Every image should make wealth look tactile, danger feel close and the player feel one excellent decision away from owning the harbor.</p></div></div>
        <div class="ab-grid three">
          <article class="ab-rule"><b>World</b><h3>Romanticized history</h3><p>Anchor the world in 1856–1865: Qing-era treaty ports, junks, clippers, early coastal steamers, crowded warehouses and monsoon weather. Heighten the glamour; do not turn it into generic fantasy.</p></article>
          <article class="ab-rule"><b>Fantasy</b><h3>Power after dark</h3><p>The erotic charge comes from command, eye contact, naked skin, silk, leather, rope and expensive objects. Exposed bodies and kink cues serve the character's appetite and power; nobody is helpless decoration.</p></article>
          <article class="ab-rule"><b>Promise</b><h3>Luxury with teeth</h3><p>Beauty always shares the frame with consequence: ledgers, contraband, cannon smoke, storm fronts, customs seals, bruised timber or a rival ship on the horizon.</p></article>
        </div>
        <div class="ab-quote"><span>One-sentence art direction</span><p id="ab-master-line">${e(MASTER_STYLE)}.</p>${copyButton("ab-master-line", "Copy master style")}</div>
        <div class="ab-split">
          <div><h3>Accuracy hierarchy</h3><ol class="ab-list"><li><b>Must be credible:</b> ships, harbors, cargo, weather, tools, architecture and the material culture of trade.</li><li><b>Should feel period-aware:</b> clothing silhouette, grooming, weapons and furniture.</li><li><b>May be heightened:</b> couture fit, décolletage, nudity, erotic posing, dramatic hats, jewelry and improbable cleanliness.</li><li><b>Never modern:</b> latex, zippers, stilettos, neon, electric fixtures or twentieth-century vessels. Build kink language from period-plausible silk, rope, leather and power dynamics.</li></ol></div>
          <div><h3>Reference relationship</h3><p>The images in <code>Inspiration_Artwork</code> define confidence, finish, material richness and sensuality—not a character to copy. New work must use original faces, poses, garments and compositions. A theatrical tricorn silhouette may appear in hero portraits as a deliberate fantasy carryover; documentary scenes should favor 1860 headwear.</p></div>
        </div>
      </section>

      <section class="card ab-section" id="ab-dna">
        <div class="ab-title"><span>02</span><div><h2>Visual DNA</h2><p>A stable palette and material vocabulary keeps art from looking as if six unrelated games wandered into the same harbor.</p></div></div>
        <div class="ab-swatches">
          ${swatch("#15100C", "Night ink", "Deepest backgrounds")}
          ${swatch("#2A1B14", "Lacquer brown", "Panels, hull shadow")}
          ${swatch("#7B2428", "Oxblood silk", "Sensual focal accent")}
          ${swatch("#C9A34E", "Antique brass", "Primary accent and ornament")}
          ${swatch("#2F6B5A", "Imperial jade", "Trade, success, cool accent")}
          ${swatch("#F1E3C5", "Ivory linen", "Type, shirts, paper")}
          ${swatch("#385467", "Storm blue", "Sea and weather")}
          ${swatch("#6B452D", "Tobacco leather", "Wood, leather, warmth")}
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
        <div class="ab-type"><div><span>Game title</span><strong style="font-family:var(--title)">Uncial Antiqua</strong><p>The game's name only: title screens, harbor board, admin bar. Short words, mixed case.</p></div><div><span>Name headers</span><strong style="font-family:var(--serif)">MedievalSharp</strong><p>Section headings and the names of ports, ships and houses. One weight; never faux-bold.</p></div><div><span>General text</span><strong style="font-family:var(--sans)">Alegreya</strong><p>Body text, tables, buttons and forms. Regular, bold and italic, clear at phone size.</p></div><div><span>Special text</span><strong style="font-family:var(--special)">Almendra SC</strong><p>Taglines, ranks, the captain's log heading, the board headline. A few words at a time. All four are served as local WOFF2 files from web/fonts, never from a font CDN.</p></div><div><span>Figures / ledgers</span><strong>Consolas or IBM Plex Mono</strong><p>Prices, dates, coordinates and prompt metadata. Tabular numerals whenever available.</p></div></div>
      </section>

      <section class="card ab-section" id="ab-people">
        <div class="ab-title"><span>03</span><div><h2>People, wardrobe &amp; erotic tone</h2><p>Historical mode is unapologetically adult and may be fully nude. “Adult” is a production constraint, not an assumption.</p></div></div>
        <div class="ab-callout"><b>Non-negotiable character line</b><p id="ab-adult-line">Every depicted person is unmistakably adult, age 25 or older; mature facial structure and adult proportions; no youthful styling, age ambiguity, school-coded wardrobe or infantilized pose.</p>${copyButton("ab-adult-line")}</div>
        ${familyMode ? `<div class="ab-grid four ab-levels">${TIERS.map((t, i) => `<article class="${i === 3 ? "selected" : ""}"><span>${e(t[0])}</span><h3>${e(t[1])}</h3><p>${e(t[2])}</p></article>`).join("")}</div>`
          : `<div class="ab-tiers">${TIERS.map((t, i) => `<div class="ab-tier${i === 3 ? " selected" : ""}"><div class="ab-tier-copy"><span>${e(t[0])}</span><h3>${e(t[1])}</h3><p>${e(t[2])}</p></div>${card("heat_" + (i + 1), true)}</div>`).join("")}</div>`}
        <div class="ab-split">
          <div><h3>Cast direction</h3><ul class="ab-list"><li>Use adult women and men of varied East Asian, South Asian, Southeast Asian, European and mixed heritage appropriate to cosmopolitan trade ports.</li><li>Give each recurring figure a distinct silhouette, face, palette and status signal.</li><li>Favor merchants, captains, financiers, smugglers, performers and officials with agency.</li><li>Pose from intention: negotiating, surveying, concealing, commanding or celebrating—not merely standing near a ship.</li></ul></div>
          <div><h3>Cultural line</h3><ul class="ab-list"><li>No “mystic East” shorthand, racial caricature or generic pan-Asian costume.</li><li>No qipao/cheongsam in 1860 scenes; use Qing-era garments or clearly framed fantasy couture.</li><li>No fake Chinese text. Omit lettering unless a verified inscription is supplied verbatim.</li><li>Do not make every Asian character a servant or every European character the owner.</li></ul></div>
        </div>
        ${collection("arch", "Character archetypes", "One example per subject in the prompt studio, dressed so wardrobe and silhouette read clearly.", SUBJECTS.map(x => ({ slot: "arch_" + x[0].replace(/-/g, "_"), label: x[1] })))}
        ${collection("cast", "The cast", "Every recurring character beside the exact portrait prompt from Cast & Voices.", Object.entries(cfg.characters || {}).filter(([k]) => SLOTS["cast_" + k]).map(([k, v]) => ({ slot: "cast_" + k, label: v.name || k })))}
        <div class="ab-dont"><div><b>Do</b><p>Confident gaze · natural adult anatomy · exposed breasts or genitals when chosen · erotic poses with intention · period-plausible kink cues · visible agency · scene motivation</p></div><div><b>Do not</b><p>Minors or age ambiguity · coercion or sexual violence · helpless decoration · cultural fetish stereotype · copied reference faces · plastic anatomy · modern fetishwear</p></div></div>
      </section>

      <section class="card ab-section" id="ab-surfaces">
        <div class="ab-title"><span>04</span><div><h2>Asset system &amp; delivery specs</h2><p>Generate larger than display size, keep the focal subject inside the crop-safe area, then export web-ready derivatives.</p></div></div>
        <div class="ab-exlist">${["surf_logo", "surf_favicon", "surf_masthead", "surf_page", "surf_board", "surf_chart"].map(slot => card(slot, false)).join("")}</div>
        <details class="ab-details"><summary>All specs as a table</summary><div class="scroll"><table class="ab-spec"><thead><tr><th>Asset</th><th>Master size</th><th>Shape</th><th>Composition and delivery</th></tr></thead><tbody>
          ${spec("Logo / wordmark", "1600 × 500 PNG", "16:5 transparent", "No baked background. Test at 320 px wide and on dark teak.")}
          ${spec("Browser icon", "512 × 512 PNG", "1:1", "One brass mark: coin, sail or ST monogram. Must read at 32 px.")}
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
        <div class="ab-title"><span>05</span><div><h2>AI Farm prompt studio</h2><p>Build a production brief, copy it into the current local workflow, and preserve the returned workflow metadata with the asset.</p></div></div>
        <div class="ab-builder">
          <div class="ab-controls">
            <label>Asset type<select data-ab-field="asset"><option value="cinematic key art">Cinematic key art</option><option value="port banner">Port banner</option><option value="ship portrait">Ship portrait</option><option value="cargo icon">Cargo icon</option><option value="character or event portrait">Character / event portrait</option><option value="subtle UI background texture">UI background</option></select></label>
            <label>Subject<select data-ab-field="subject">${subjectOptions}</select></label>
            <label>Port / setting<select data-ab-field="place"><option value="Victoria Harbour, Hong Kong">Victoria Harbour, Hong Kong</option>${portOptions}</select></label>
            <label>Cargo focus<select data-ab-field="cargo"><option value="none">None</option>${cargoOptions}</select></label>
            <label>Ship focus<select data-ab-field="ship"><option value="period trading vessel">Period trading vessel</option>${shipOptions}</select></label>
            <label>Light<select data-ab-field="light"><option>golden hour through humid salt haze</option><option>lantern light against cool night sea</option><option>monsoon overcast with wet highlights</option><option>hard tropical noon with deep awning shade</option><option>storm break with a shaft of sun</option></select></label>
            <label>Sensuality<select data-ab-field="heat" ${familyMode ? "disabled" : ""}>${heatOptions}</select></label>
            <label>Composition<select data-ab-field="composition"><option>wide 16:9, subject in the right third, dark negative space on the left for UI</option><option>wide 18:7 environmental banner, no close foreground face, center crop safe</option><option>square centered object, clear silhouette, readable at icon size</option><option>vertical 3:4 full figure, hands visible, uncropped limbs</option><option>landscape 3:2, full vessel in bow three-quarter view</option></select></label>
            <label class="wide">Specific moment or object<input data-ab-field="moment" value="holding court on her quarterdeck at dusk, sizing up a rich merchant prize across the harbor" maxlength="220"></label>
          </div>
          <div class="ab-prompt-output">
            <div class="ab-code-head"><b>Positive prompt</b>${copyButton("ab-positive")}</div><textarea id="ab-positive" class="code" rows="16" readonly></textarea>
            <div class="ab-code-head"><b>Negative prompt</b>${copyButton("ab-negative")}</div><textarea id="ab-negative" class="code" rows="9" readonly>${e(familyMode ? FAMILY_NEGATIVE : NEGATIVE)}</textarea>
          </div>
          <div class="ab-studio-preview"><div class="ab-code-head"><b>What this brief generates</b><small>Sent to the farm exactly as shown, at the composition's aspect ratio</small></div>${card("studio", true)}</div>
        </div>
        <details class="ab-details"><summary>Production settings &amp; metadata card</summary><div class="ab-split"><div><h3>Farm starting point</h3><ul class="ab-list"><li>Use the farm’s best photoreal checkpoint/workflow; do not hard-code a model name into the brand.</li><li>Start at the master aspect ratio above, not square-and-crop for banners.</li><li>Keep CFG/steps at the workflow’s proven defaults; style consistency beats random knob theater.</li><li>Generate four drafts, select composition first, then iterate one change at a time.</li></ul></div><div><h3>Save beside every master</h3><p><code>asset_id · surface · mode=historical · prompt · negative · model · workflow · seed · width · height · sampler · steps · cfg · date · approval</code></p><p class="help">This is the minimum recipe needed to reproduce or repair an image six months later.</p></div></div></details>
        <details class="ab-details"><summary>Copy-ready specialist recipes</summary><div class="ab-recipes">
          ${recipe("Cargo icon", "A single historically plausible [CARGO] trade-goods arrangement on a lacquer-black surface: tactile material, antique brass merchant token for scale, three-quarter product view, soft directional lantern light, square composition, clean silhouette, no person, no label, readable at 30 pixels. " + recipeStyle)}
          ${recipe("Port banner", "A wide environmental portrait of [PORT] in the China Seas, 1860: recognizable geography and port activity, layered junks and merchant shipping, humid atmosphere, workers and traders as tiny supporting figures, strong depth, horizon in the upper third, center crop safe, no close-up face, no text. " + recipeStyle)}
          ${recipe("Ship portrait", "Full portrait of a historically plausible [SHIP] underway in the China Seas, 1860, bow three-quarter view, entire hull and rig visible, purposeful weather and sea state expressing its role, no modern fittings, no crew close-up, no text. " + recipeStyle)}
          ${recipe("Adult character", characterRecipe)}
          ${recipe("UI texture", "Seamless-feeling low-contrast field of dark lacquered teak, ledger paper fibers, faint salt bloom and restrained antique-brass corner ornament, no central object, no readable writing, no face, designed to sit behind light UI cards without competing. " + recipeStyle)}
        </div></details>
      </section>

      <section class="card ab-section" id="ab-qa">
        <div class="ab-title"><span>06</span><div><h2>Approval gate</h2><p>An image is not finished because the generator stopped. It ships only when every applicable check passes at actual UI size.</p></div></div>
        <div class="ab-checks">
          ${checkGroup("Canon", ["Reads as 1860 China Seas before it reads as generic pirate fantasy", "Matches the approved palette, materials and cinematic finish", "Adds trade, danger or ambition—not decoration alone"])}
          ${checkGroup("People", ["Every person is unmistakably adult and age 25+", "Anatomy, including exposed breasts or genitals, survives close inspection", "Erotic pose has intention, agency and no coercion", "No copied reference identity, costume or watermark"])}
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
    const familyMode = root.dataset.family === "true";
    const value = name => {
      const control = root.querySelector(`[data-ab-field="${name}"]`);
      return control ? control.value.trim() : "";
    };
    const subject = value("subject") === "none" ? "environment only, no foreground character" : value("subject");
    const cargo = value("cargo") === "none" ? "" : ` Cargo focus: ${value("cargo")}, shown accurately and secondary to the scene.`;
    const ship = value("ship") ? ` Vessel: ${value("ship")}, historically plausible for 1860.` : "";
    const mode = familyMode ? "Family-Friendly Mode" : "Historical Private-Release Mode";
    const style = familyMode ? FAMILY_STYLE : MASTER_STYLE;
    const constraints = familyMode
      ? "every person is unmistakably adult age 25 or older and fully dressed; no nudity, erotic framing, fetishwear or kink imagery; original faces, poses, garments and composition; natural skin; believable anatomy; historically plausible maritime details; no text, logo, border, signature or watermark"
      : "every person is unmistakably adult age 25 or older; adult nudity, exposed breasts, buttocks and genitals, erotic posing and period-plausible consensual kink cues are permitted when selected; clear agency; no explicit sex act, sexual violence or coercion; original faces, poses, garments and composition; natural skin; believable anatomy; historically plausible maritime details; no text, logo, border, signature or watermark";
    const prompt = `Use case: historical-scene\nAsset type: Sea Trader ${mode} ${value("asset")}\nPrimary request: ${subject} in ${value("place")}, ${value("moment")}.\nWorld and style: ${style}.\nLighting: ${value("light")}.\nTone: ${value("heat")}.\nComposition: ${value("composition")}.\nPalette: lacquer black, oxblood silk, antique brass, imperial jade, ivory linen, tobacco leather and storm blue.${cargo}${ship}\nConstraints: ${constraints}.`;
    const out = root.querySelector("#ab-positive");
    if (out) out.value = prompt;
    if (SLOTS.studio) {
      const comp = value("composition");
      const hit = STUDIO_ASPECT.find(x => comp.indexOf(x[0]) >= 0);
      SLOTS.studio.prompt = prompt;
      SLOTS.studio.aspect = hit ? hit[1] : "16:9";
      SLOTS.studio.size = SIZE[SLOTS.studio.aspect] || "";
      SLOTS.studio.negative = familyMode ? FAMILY_NEGATIVE : NEGATIVE;
      refreshStudio();
    }
    const negative = root.querySelector("#ab-negative");
    if (negative) negative.value = familyMode ? FAMILY_NEGATIVE : NEGATIVE;
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
