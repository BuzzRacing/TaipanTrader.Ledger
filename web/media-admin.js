/* SeaTrader Admin: Media Library.
   Every picture and clip the game can show, filed by kind (persona, port, ship, cargo, scene, brand)
   and subject, with roles, tags, weights and an NSFW flag. Changes here are saved at once (no
   Save & apply needed) and every open screen picks them up straight away. */
(function () {
  "use strict";

  const M = {
    lib: null, loading: false, kind: "persona", subject: "", role: "", type: "", nsfw: "", review: false, q: "",
    sort: (() => { try { return localStorage.getItem("ml.sort") || "new"; } catch (_) { return "new"; } })(),
    sel: new Set(), last: null, genOpen: false, rulesOpen: false, jobs: [], jobsOpen: (() => { try { return localStorage.getItem("ml.jobsOpen") === "1"; } catch (_) { return false; } })(), poll: null, uploads: [],
    gen: { roles: [], aspect: "3:4", count: 2, nsfw: "auto", prompt: "", tags: "", forKey: "" },
    rulesDraft: null, timers: {},
  };
  const $ = id => document.getElementById(id);
  const e = s => esc(s);
  const KIND_ORDER = ["persona", "captain", "rank", "house", "port", "ship", "cargo", "service", "scene", "brand", "reference", "other"];
  const ASPECT_FOR = { persona: "3:4", captain: "3:4", house: "1:1", port: "16:9", ship: "3:2", cargo: "1:1", service: "16:9", scene: "16:9", brand: "16:9", reference: "1:1", other: "1:1" };

  /* --------------------------------------------------------- helpers -- */
  const kinds = () => (M.lib ? M.lib.kinds : {});
  const items = () => (M.lib ? M.lib.items : []);
  const byId = id => items().find(i => i.id === id);
  function subjectsFor(kind) {
    const known = ((M.lib && M.lib.subjects[kind]) || []).map(x => x.slice());
    const seen = new Set(known.map(x => x[0]));
    items().forEach(i => { if (i.kind === kind && i.subject && !seen.has(i.subject)) { seen.add(i.subject); known.push([i.subject, i.subject]); } });
    return known;
  }
  function subjectName(kind, subject) {
    const s = subjectsFor(kind).find(x => x[0] === subject);
    return s ? s[1] : (subject || "—");
  }
  function roleName(kind, role) {
    const r = ((kinds()[kind] || {}).roles || []).find(x => x[0] === role);
    return r ? r[1].split(":")[0] : role;
  }
  const fmtBytes = n => n >= 1 << 30 ? (n / (1 << 30)).toFixed(1) + " GB" : n >= 1 << 20 ? (n / (1 << 20)).toFixed(1) + " MB" : Math.max(1, Math.round(n / 1024)) + " KB";

  function filtered() {
    const q = M.q.trim().toLowerCase();
    return items().filter(i => {
      if (M.kind && i.kind !== M.kind) return false;
      if (M.subject && i.subject !== M.subject) return false;
      if (M.role && !(i.roles.includes(M.role) || !i.roles.length)) return false;
      if (M.type && i.type !== M.type) return false;
      if (M.nsfw === "sfw" && i.nsfw) return false;
      if (M.nsfw === "nsfw" && !i.nsfw) return false;
      if (M.nsfw === "off" && i.enabled) return false;
      if (M.review && i.reviewed) return false;
      if (q && ![i.title, i.subject, i.url, i.tags.join(" "), i.prompt].join(" ").toLowerCase().includes(q)) return false;
      return true;
    }).sort(SORTS[M.sort] || SORTS.new);
  }

  // Sort orders for the grid (Anthony, 17 Nov 2026: newest first to start). "added" is "YYYY-MM-DD HH:MM";
  // items with no date (old scanned files) go last on Newest and first on Oldest.
  const byAdded = (a, b) => String(b.added || "").localeCompare(String(a.added || ""));
  const byName = (a, b) => String(a.title || a.url || "").localeCompare(String(b.title || b.url || ""));
  const SORTS = {
    new: (a, b) => byAdded(a, b) || byName(a, b),
    old: (a, b) => byAdded(b, a) || byName(a, b),
    subject: (a, b) => (a.subject || "").localeCompare(b.subject || "") || (b.primary - a.primary) || byAdded(a, b),
    primary: (a, b) => (b.primary - a.primary) || byAdded(a, b),
    title: (a, b) => byName(a, b) || byAdded(a, b),
  };
  const SORT_NAMES = [["new", "Newest first"], ["old", "Oldest first"], ["subject", "By subject"], ["primary", "★ primary first"], ["title", "Title A–Z"]];

  function patchSaved(fn) {
    // The server changed a setting directly: keep this page's copy of the settings in step.
    fn(CFG);
    const saved = JSON.parse(SAVED);
    fn(saved);
    SAVED = JSON.stringify(saved);
    refreshDirty();
  }

  async function load(quiet) {
    if (M.loading) return;
    M.loading = true;
    const res = await api("media/library");
    M.loading = false;
    if (!res.ok) { if (!quiet) toast(res.error || "Could not read the media library.", true); return; }
    M.lib = res;
    M.jobs = res.jobs || [];
    [...M.sel].forEach(id => { if (!byId(id)) M.sel.delete(id); });
    if (!M.rulesDraft) M.rulesDraft = { rules: clone(res.rules), options: clone(res.options) };
    redraw();
    watchJobs();
  }

  function redraw() {
    if (section !== "media") return;
    const y = window.scrollY;
    const m = document.getElementById("main");
    const focus = document.activeElement && document.activeElement.id;
    m.innerHTML = render();
    window.scrollTo(0, y);
    if (focus && $(focus)) { const el = $(focus); el.focus(); if (el.setSelectionRange && el.value != null) try { el.setSelectionRange(el.value.length, el.value.length); } catch (x) { /* not a text box */ } }
  }

  /* ---------------------------------------------------------- render -- */
  function thumb(i, cls) {
    if (i.missing) return `<div class="${cls} ml-missing">file missing</div>`;
    return i.type === "video"
      ? `<video class="${cls}" src="${e(i.url)}#t=0.5" muted loop playsinline preload="metadata"></video>`
      : `<img class="${cls}" src="${e(i.url)}" alt="" loading="lazy">`;
  }

  function familySwitch() {
    const fam = CFG.content.rating === "family";
    return `<button type="button" class="ml-safe${fam ? " on" : ""}" data-mlsafe="${fam ? "0" : "1"}" title="Switch the whole game between the private adult release and family-friendly">
      <span class="ml-safe-knob"></span><span><b>${fam ? "Family-friendly ON" : "Family-friendly OFF"}</b>
      <small>${fam ? "NSFW is hidden on every screen" : "NSFW pictures and clips can show"}</small></span></button>`;
  }

  function kindTabs() {
    const n = k => items().filter(i => i.kind === k).length;
    return `<div class="ml-kinds">${KIND_ORDER.filter(k => kinds()[k]).map(k =>
      `<button type="button" data-mlkind="${k}" class="${M.kind === k ? "on" : ""}">${e(kinds()[k].label)} <i>${n(k)}</i></button>`).join("")}
      <button type="button" data-mlkind="" class="${M.kind === "" ? "on" : ""}">Everything <i>${items().length}</i></button></div>`;
  }

  function subjectCards() {
    if (!M.kind || M.subject || M.review) return "";
    const subs = subjectsFor(M.kind);
    if (!subs.length) return "";
    return `<div class="ml-subjects">${subs.map(([k, name]) => {
      const mine = items().filter(i => i.kind === M.kind && i.subject === k);
      const fam = CFG.content.rating === "family", ok = i => i.type === "image" && !(fam && i.nsfw);
      const face = mine.find(i => i.primary && ok(i)) || mine.find(ok);
      const vids = mine.filter(i => i.type === "video").length, nsfw = mine.filter(i => i.nsfw).length;
      return `<button type="button" class="ml-subject" data-mlsubject="${e(k)}">
        <span class="ml-subject-art">${face ? `<img src="${e(face.url)}" alt="" loading="lazy">` : `<i>${e(String(name).slice(0, 1))}</i>`}</span>
        <b>${e(name)}</b><small>${mine.length} item${mine.length === 1 ? "" : "s"}${vids ? ` · ${vids} video` : ""}${nsfw ? ` · <em>${nsfw} NSFW</em>` : ""}</small></button>`;
    }).join("")}</div>`;
  }

  function reviewButton() {
    // Toggle: show only items still waiting for review (in the current tab; on "Everything" it covers the whole library).
    const n = items().filter(i => !i.reviewed && (!M.kind || i.kind === M.kind) && (!M.subject || i.subject === M.subject)).length;
    return `<button type="button" data-mlreview="1" class="ml-review${M.review ? " on" : ""}${n ? " has" : ""}" title="${M.review ? "Show everything again" : "Show only items that still need review"}">` +
      `${M.review ? "✓ " : ""}Need review <i>${n}</i></button>`;
  }

  function toolbar() {
    const K = kinds()[M.kind];
    const subs = M.kind ? subjectsFor(M.kind) : [];
    const roles = K ? K.roles : [];
    return `<div class="ml-tools">
      ${M.kind ? `<label>${e(K.one)}<select id="mlsubject" data-mlf="subject"><option value="">All</option>${subs.map(([k, n]) =>
        `<option value="${e(k)}"${k === M.subject ? " selected" : ""}>${e(n)}</option>`).join("")}</select></label>` : ""}
      ${roles.length ? `<label>Role<select data-mlf="role"><option value="">Any</option>${roles.map(([k, n]) =>
        `<option value="${e(k)}"${k === M.role ? " selected" : ""}>${e(n.split(":")[0])}</option>`).join("")}</select></label>` : ""}
      <label>Type<select data-mlf="type"><option value="">Pictures & video</option><option value="image"${M.type === "image" ? " selected" : ""}>Pictures</option><option value="video"${M.type === "video" ? " selected" : ""}>Video</option></select></label>
      <label>Rating<select data-mlf="nsfw"><option value="">All</option><option value="sfw"${M.nsfw === "sfw" ? " selected" : ""}>Family-friendly only</option><option value="nsfw"${M.nsfw === "nsfw" ? " selected" : ""}>NSFW only</option><option value="off"${M.nsfw === "off" ? " selected" : ""}>Switched off</option></select></label>
      <label>Sort<select data-mlf="sort">${SORT_NAMES.map(([k, n]) => `<option value="${k}"${k === M.sort ? " selected" : ""}>${n}</option>`).join("")}</select></label>
      ${reviewButton()}
      <label class="ml-grow">Search<input type="search" id="mlq" data-mlf="q" value="${e(M.q)}" placeholder="tag, title, prompt…"></label>
      <div class="ml-actions">
        <label class="ml-check" title="Tag what you upload next as NSFW"><input type="checkbox" data-mlf="upNsfw"${M.upNsfw ? " checked" : ""}> upload as NSFW</label>
        <label class="pick ml-up">Upload…<input type="file" multiple accept="image/png,image/jpeg,image/webp,image/gif,image/svg+xml,video/mp4,video/webm,video/quicktime,.m4v" data-mlupload="1"></label>
        <button type="button" data-mlgen="1" class="${M.genOpen ? "on" : ""}">Generate…</button>
        <button type="button" data-mlscan="1" title="Pick up files dropped into web/media/&lt;kind&gt;/&lt;subject&gt;/">Scan folders</button>
        <button type="button" data-mlrules="1" class="${M.rulesOpen ? "on" : ""}">Playback rules…</button>
      </div></div>`;
  }

  function uploadBar() {
    if (!M.uploads.length) return "";
    return `<div class="ml-uploads">${M.uploads.map(u => `<div><span>${e(u.name)}</span><i style="width:${u.pct}%"></i><b>${u.err ? e(u.err) : u.pct >= 100 ? "filed" : u.pct + "%"}</b></div>`).join("")}</div>`;
  }

  // Starter prompts for the ten sea battle moments, one set per enemy (see SeaTrader Sea Battle).
  // Your fleet is always a small merchant trading fleet; the enemy changes.
  const BATTLE_ENEMY = {
    seafight_pirates: "a pack of ragged South China Sea pirate junks with patched rust-brown battened sails, painted eyes on their bows, swivel guns and crowded decks of fierce women pirates",
    seafight_lord: "the pirate queen's great war fleet of heavy black-lacquered war junks with blood-red battened sails, banners and pennants, gilded sterns, rows of bronze cannon, disciplined crews of women warriors"
  };
  const BATTLE_MOMENTS = {
    sighting: "Wide view from the quarterdeck of a merchant clipper crewed by women: on the hazy horizon {enemy} appear and close in, a woman lookout pointing from the rigging, women sailors rushing to the guns, tense calm before battle",
    broadside: "A merchant clipper fires a full broadside, a rippling line of cannon flashes and thick white powder smoke rolling over the water, women gun crews heaving at the guns, {enemy} beyond the smoke, low dynamic angle",
    enemy_hit: "One of {enemy} is struck and going down: shattered mast falling, sails torn and burning, hull listing into the sea, splinters and spray, the merchant fleet's guns still smoking in the foreground with women gunners cheering",
    we_are_hit: "Enemy roundshot slams into the deck of a merchant ship: splintering rail, a torn sail, rigging snapping, women sailors ducking and bracing, smoke and spray, {enemy} firing close alongside",
    ship_lost: "A merchant ship of the trading fleet is lost: broken-backed, dismasted and on fire, sinking stern first into a dark sea, women sailors in boats pulling away, {enemy} circling in the smoke, sombre mood",
    boarding: "{enemy} grapple alongside a merchant ship and the women pirates swarm aboard over the rail, cutlasses and boarding pikes raised, cargo chests and tea crates being hauled across, the merchant's women crew fighting back, chaos and smoke, dramatic but not gory",
    got_away: "A merchant clipper under every stitch of sail running clear before a fresh wind, wake foaming, {enemy} falling far behind in the haze, relief and triumph among the women crew on deck, golden light breaking through cloud",
    retreat: "A merchant ship breaking away from battle, her women crew heaving bales, chests and crates of cargo over the side to lighten her, crates floating in the wake, sails straining, {enemy} firing parting shots through the smoke",
    victory: "After the battle the merchant fleet sails on battered but victorious, women crews cheering in the rigging, the wreckage and smoke of {enemy} drifting on the water behind, warm sunset light",
    defeat: "Total defeat at sea: the whole merchant fleet burning and sinking under a darkening sky, only wreckage, floating cargo and an empty lifeboat left, {enemy} triumphant in the smoke with their women crews at the rails, grim and sombre"
  };
  // Pirate Queen sandbox: every crew on both sides is women only (Anthony, 17 Nov 2026).
  const BATTLE_WOMEN = "every sailor, gunner, officer and pirate in the picture is a woman, all-female crews of fierce sea-women with long braided or tied-back hair, women only";
  function battlePrompt(subject, role, style) {
    const enemy = BATTLE_ENEMY[subject];
    const moment = BATTLE_MOMENTS[role] || "A sea battle between a small merchant trading fleet and {enemy}, cannon smoke, spray and torn sails, wide cinematic view";
    return `${moment.replace("{enemy}", enemy)}, ${BATTLE_WOMEN}, 16:9 wide cinematic composition, ${style}`;
  }


  // Who each port's market keeper, ship master, mayor and tax lady is (Anthony, 17 Nov 2026): a real mix of
  // heritage, age, build and hair across the 40 women, so no two ports paint the same face.
  // who = age, heritage and build; hair; dress = her clothes. The role prompt adds her props and setting.
  const PORT_WOMEN = {
    hongkong: {
      keeper:     { who: "petite, slender Hakka Chinese woman of 26 with a heart-shaped face", hair: "glossy black hair coiled in twin buns bound with red silk cord", dress: "a close-fitting oxblood silk jacket with gold frogging, unbuttoned low at the throat" },
      shipmaster: { who: "tall, powerfully muscular Black Mozambican-Portuguese woman of 38 raised in Macau, deep brown skin, broad strong shoulders", hair: "close-cropped natural hair under a gold-braided black tricorn", dress: "a fitted black lacquer naval coat with oxblood silk lining worn open over a low-cut linen shirt, sleeves pushed up over sculpted forearms" },
      mayor:      { who: "heavyset, full-figured, deeply glamorous Cantonese matriarch of 58 with a soft double chin and shrewd eyes", hair: "silver-streaked black hair swept up with gold pins", dress: "a voluminous imperial-jade brocade robe falling open over a gold-embroidered bodice" },
      taxlady:    { who: "curvy, freckled Irish woman of 31 with green eyes", hair: "a riot of copper-red curls barely pinned up", dress: "a fitted black lacquer waistcoat over a loose ivory silk blouse slipping off one freckled shoulder" }
    },
    shanghai: {
      keeper:     { who: "plump, full-figured, voluptuous Ningbo Chinese woman of 44 with a round, rosy face", hair: "black hair in a lacquered bun with gold hairpins", dress: "a snug peony-red silk jacket straining across her bosom, top frog buttons left undone" },
      shipmaster: { who: "tall, broad-shouldered, athletic Punjabi Sikh woman of 35 with a strong jaw and kohl-dark eyes", hair: "a long thick black braid over one shoulder and a steel kara on her wrist", dress: "a fitted saffron-and-black naval coat open over a close silk kurti, cutlass at her hip" },
      mayor:      { who: "statuesque, curvaceous Swedish woman of 45 with ice-blue eyes", hair: "ash-blonde hair in a crown braid with loose tendrils", dress: "a low-cut midnight-blue velvet gown with bare shoulders under a black lacquer captain's coat" },
      taxlady:    { who: "slender, elegant Korean woman of 29 with a long neck and cool gaze", hair: "black hair in a low chignon held by a silver binyeo pin", dress: "a short cropped jeogori jacket in plum silk tied loosely over a high-waisted crimson skirt, bare collarbones" }
    },
    nagasaki: {
      keeper:     { who: "soft, full-figured, matronly Japanese woman of 52 with laughing eyes and fine smile lines", hair: "greying hair in a marumage with tortoiseshell combs", dress: "an indigo kimono worn loose and low off both shoulders, obi tied carelessly" },
      shipmaster: { who: "lean, wiry, hard-muscled Japanese woman of 33 with a thin scar on one cheek", hair: "black hair pulled into a high warrior's topknot", dress: "a black lacquer coat over a loosely wrapped dark kimono open to the sternum, a short sword at her sash" },
      mayor:      { who: "striking Dutch-Japanese Eurasian woman of 40 with hazel eyes and a slim, curvy figure", hair: "honey-brown hair swept up Dutch-fashion with a jade comb", dress: "a Dejima-merchant gown of ivory silk with a deep square neckline under a black lacquer coat" },
      taxlady:    { who: "curvy, buxom African-American woman of 34, a New Bedford whaler's widow, rich dark brown skin and full lips", hair: "hair wrapped high in an oxblood silk headscarf, gold hoops in her ears", dress: "a fitted black waistcoat over a loose white blouse falling off one shoulder" }
    },
    manila: {
      keeper:     { who: "petite, curvy Tagalog Filipina of 24 with warm brown skin and dimples", hair: "long loose black hair tucked with sampaguita flowers", dress: "a sheer piña-fibre baro blouse over a low bodice and a bright saya skirt" },
      shipmaster: { who: "muscular, sun-browned Tausug Moro woman of 41, a famed corsair, with fierce dark eyes", hair: "hair bound under a patterned headwrap with a gold pin", dress: "a fitted black jacket open over a wrapped silk breastcloth, a kris dagger in her sash" },
      mayor:      { who: "heavyset, imposing Spanish-Filipina mestiza grand dame of 62 with a commanding bosom and a wicked smile", hair: "silver hair under a tall tortoiseshell comb and black lace mantilla", dress: "a black lace off-shoulder gown with a deep neckline and a crimson sash" },
      taxlady:    { who: "slender, sharp-featured Chinese-Filipina mestiza of 30", hair: "a long black braid wound with gold thread", dress: "a fitted embroidered kimona blouse unbuttoned at the throat over a striped saya" }
    },
    saigon: {
      keeper:     { who: "slender, graceful Vietnamese woman of 28 with a long elegant neck", hair: "long black hair wound into a black velvet khăn vấn turban", dress: "a close-fitting silk áo tấc gown of deep teal, side slits to the hip, collar open" },
      shipmaster: { who: "tall, powerfully built Senegalese woman of 36 with very dark skin and high cheekbones", hair: "intricate braids under a madras-check headtie", dress: "a French naval coat with gold epaulettes worn open over bare skin and a wrapped indigo breastcloth" },
      mayor:      { who: "plump, voluptuous French woman of 50 with a sensual mouth and knowing eyes", hair: "strawberry-blonde curls going silver, piled high", dress: "a low-cut violet silk gown with a laced corset and a tricolour sash" },
      taxlady:    { who: "curvy, sun-gold Khmer woman of 33 with full lips", hair: "short cropped black hair in the Khmer fashion and gold earrings", dress: "a wrapped silk sampot and a fitted short jacket open over a sheer breastcloth" }
    },
    bangkok: {
      keeper:     { who: "heavy, round-faced, jolly Teochew-Thai woman of 47 with a generous figure", hair: "black hair in a neat bun with a jasmine sprig", dress: "a loose silk blouse slipping off one round shoulder over a pha nung wrap" },
      shipmaster: { who: "athletic, hard-bodied Malay woman of 31 with sun-browned skin", hair: "black hair in a tight knot under a songket headcloth", dress: "a short fitted baju jacket open over a wrapped breastcloth, sarong hitched to the knee" },
      mayor:      { who: "wiry, sharp-featured Siamese noblewoman of 55 with fine lines and steel in her eyes", hair: "short cropped grey hair in the old court style", dress: "a gold-threaded sabai draped over one bare shoulder and heavy gold court jewellery" },
      taxlady:    { who: "voluptuous Gujarati woman of 37 with a gold nose ring and kohl-lined eyes", hair: "long oiled black hair in a thick plait", dress: "a vivid bandhani silk sari draped low over a short fitted choli, bare midriff" }
    },
    singapore: {
      keeper:     { who: "full-figured, soft-curved Peranakan Nyonya of 39 with a coy smile", hair: "black hair in a sanggul bun with gold kerosang pins", dress: "a sheer lace-embroidered kebaya over a close batik sarong" },
      shipmaster: { who: "sinewy, scarred, sun-darkened Bugis sea-captain of 43", hair: "long black hair tied back with a red cord", dress: "a fitted black coat open over a wrapped silk breastcloth, a kris at her waist" },
      mayor:      { who: "heavyset, voluptuous Tamil woman of 49 with dark skin, a gold nose ring and commanding eyes", hair: "long black hair in a jasmine-wound plait", dress: "a deep crimson Kanchipuram silk sari draped low over a short fitted blouse, heavy gold temple jewellery" },
      taxlady:    { who: "tall, slender Swahili woman of 32 from Zanzibar with deep brown skin and an elegant neck", hair: "hair wrapped in a bright kanga headwrap, gold coins at her brow", dress: "a fitted black waistcoat over a loose white blouse open at the throat and a kanga wrapped at the hip" }
    },
    batavia: {
      keeper:     { who: "slender, golden-skinned Javanese woman of 30 with almond eyes", hair: "black hair in a konde bun ringed with melati jasmine", dress: "a sheer kebaya of pale rose over a close batik kain" },
      shipmaster: { who: "big-boned, muscular, sun-reddened Dutch woman of 37 with forearms like a stevedore's", hair: "a heavy flaxen-blonde braid", dress: "a VOC-blue coat open over a deeply unlaced linen shirt, sleeves rolled" },
      mayor:      { who: "plump, comfortable Indo (Dutch-Javanese) matriarch of 60 with a sly smile", hair: "grey hair in a neat bun with a gold pin", dress: "a white lace kebaya over a batik sarong, a gold chain heavy on her bosom" },
      taxlady:    { who: "curvy Malagasy woman of 28 with dark brown skin and wide-set eyes", hair: "tight curls pinned up in small knots", dress: "a fitted black bodice and a lamba shawl slipping from her shoulders" }
    },
    calcutta: {
      keeper:     { who: "plump, curvy Bengali woman of 35 with large dark eyes", hair: "long oiled black hair in a loose knot, sindoor in her parting", dress: "a red-bordered white sari draped without a blouse in the old Bengal fashion, bare shoulder" },
      shipmaster: { who: "tall, powerful Siddi (Afro-Indian) woman of 40 with very dark skin and broad shoulders", hair: "short tight curls and a silver ring in one ear", dress: "a black lacquer naval coat open over a fitted silk choli, cutlass at her hip" },
      mayor:      { who: "heavyset, imposing Bengali zamindar's widow of 64 with a heavy-lidded, appraising stare", hair: "white hair drawn back severely", dress: "a fine white muslin sari draped over one bare shoulder, heavy gold bangles" },
      taxlady:    { who: "slender Anglo-Indian woman of 27 with olive skin and grey eyes", hair: "chestnut hair in a loose Victorian chignon", dress: "a low-cut emerald silk bodice under a fitted black jacket" }
    },
    foochow: {
      keeper:     { who: "sun-browned, strong-armed Tanka boatwoman of 33 with a wide easy grin", hair: "black hair under a woven bamboo hat tied with ribbons", dress: "a faded blue jacket open over a red breastcloth and rolled trousers" },
      shipmaster: { who: "stocky, heavy, immensely strong Hoklo Chinese woman of 51 with a broken nose", hair: "an iron-grey braid", dress: "a black quilted jacket open over a tight bound breastcloth, sleeves torn off at the shoulders" },
      mayor:      { who: "full-figured, freckled Scottish woman of 42 from the tea trade", hair: "flame-red hair loose down her back", dress: "a tartan sash over a low-cut black silk gown and an open lacquer coat" },
      taxlady:    { who: "curvy Hui Muslim Chinese woman of 36 with grey-green eyes", hair: "hair under a dark silk cap and veil thrown back", dress: "a close-fitting dark green silk jacket with the collar open" }
    }
  };
  function portWoman(subject, role) {
    const w = (PORT_WOMEN[subject] || {})[role];
    return w || { who: "woman in her thirties", hair: "glossy black hair pinned with jade and gold", dress: "a close-fitting embroidered oxblood silk jacket open at the throat" };
  }

  // What each ship type looks like (18 Nov 2026: the fleet's three classes). The library lists a ship as
  // "her name · her class · what she does", and the starting prompt describes the class, not the name, so a
  // renamed type ("Blood Moon") still comes out as an East Indiaman. Unknown types fall back to the name.
  // Women only on deck (the Pirate Queen sandbox), as in the battle pictures.
  const SHIP_LOOK = {
    junk: "a Chinese trading junk with battened red-brown lug sails, a high carved stern and a painted eye on the bow, a few small guns on deck",
    lorcha: "a Macanese lorcha: a European-built hull with Chinese battened junk sails, trim and quick, a handful of brass guns along the rail",
    barque: "a three-masted merchant barque, square-rigged fore and main, fore-and-aft mizzen, a row of gunports, holds deep with cargo",
    clipper: "a sleek long-hulled opium clipper with towering raked masts and clouds of white canvas, a knife-sharp bow cutting the sea",
    indiaman: "a great black-and-gold East Indiaman, a towering three-decker merchant ship with a double row of gunports and a gilded stern gallery",
    gunboat: "a black-hulled paddle steam gunboat hired as a convoy escort: a tall smoking funnel amidships, big paddle boxes, two masts with furled sails, six heavy pivot cannons on deck and no cargo hatches, lean and menacing",
    countryship: "a huge teak-built Indian country ship, broad and deep-bellied, sitting low in the water under a mountain of cargo, bales and chests lashed on deck, no guns at all, slow and heavy"
  };
  const SHIP_ROLE_LOOK = {
    escort: "a black-hulled armed escort steamer with heavy deck cannons and no cargo, lean and menacing",
    cargo: "a broad, deep-bellied unarmed cargo ship sitting low in the water under a mountain of cargo",
    trader: "an armed merchant trading ship with cargo and guns"
  };
  const SHIP_WOMEN = "her crew are all women, sea-women in rolled shirtsleeves and sashes, women only";
  function shipPrompt(subject, role, style) {
    const spec = ((CFG && CFG.ships) || {})[subject] || {};
    const look = SHIP_LOOK[subject] || SHIP_ROLE_LOOK[spec.role || "trader"] || ("a " + (spec.name || subject));
    if (role === "battle") return `${look}, in the thick of a sea battle against pirate junks off the China coast in 1860, cannon smoke, muzzle flashes and spray, ${spec.role === "escort" ? "she steams ahead of the merchant convoy to take the enemy's fire" : spec.role === "cargo" ? "she lumbers at the back of the convoy behind the escorts as shot splashes around her" : "she fires a broadside from the line of the convoy"}, ${SHIP_WOMEN}, wide cinematic view, ${style}`;
    if (role === "sailing") return `${look}, under way on the South China Sea in 1860, ${spec.role === "escort" ? "steaming at the head of a merchant convoy, black smoke trailing" : spec.role === "cargo" ? "sailing at the rear of a merchant convoy, an escort steamer ahead" : "full sail, spray over the bow"}, golden late light, wide view, ${SHIP_WOMEN}, ${style}`;
    return `Ship portrait of ${look}, 1860s China Seas, the whole ship side-on and filling the frame, detailed rigging and weathered hull, calm harbour water, ${SHIP_WOMEN}, ${style}`;
  }

  const PERSONA_MOODS = {
    speaking: "caught mid-sentence, lips parted, one hand raised as she makes her point",
    happy: "a broad, triumphant, delighted smile, eyes bright, good news written all over her face",
    angry: "narrowed eyes, jaw set, a sharp warning gesture, plainly furious at bad news",
    sly: "a sly conspiratorial half-smile and a knowing wink, leaning in close as if sharing a secret, one finger raised to her lips",
    idle: "a relaxed, unguarded moment, looking off to one side, lost in thought"
  };
  function personaPrompt(subject, mood) {
    const base = (CFG.characters[subject] || {}).portrait_prompt || "";
    const clause = PERSONA_MOODS[mood];
    if (!clause || !base) return base;
    const at = base.indexOf(", romanticized");
    return at > 0 ? base.slice(0, at) + ", " + clause + base.slice(at) : base + ", " + clause;
  }

  function defaultPrompt(kind, subject, role) {
    if (kind === "persona" && CFG.characters[subject]) return CFG.characters[subject].portrait_prompt || "";
    // Captains and Houses (Admin > Captains): their own prompt, or the template filled in.
    if (kind === "captain" || kind === "house") return ((M.lib && M.lib.prompts && M.lib.prompts[kind]) || {})[subject] || "";
    const style = "romanticized cinematic historical realism, China Seas 1860, humid salt haze, weathered maritime materials, lacquer black, oxblood silk, antique brass, imperial jade, dramatic but plausible lighting, no text";
    const name = subjectName(kind, subject);
    if (kind === "scene" && BATTLE_ENEMY[subject]) return battlePrompt(subject, role, style);
    if (kind === "port" && role === "keeper") { const w = portWoman(subject, role); return `Waist-up portrait of a breathtakingly beautiful, sultry ${w.who}, who runs a trading stall in the ${name} market in 1860, looking straight into the camera with a slow, knowing, inviting half-smile and heavy-lidded bedroom eyes, ${w.hair}, ${w.dress}, bare skin glowing with humid heat, brass scales, tea chests, silk bolts and porcelain behind her, warm lantern glow and soft humid haze, shallow depth of field, she is the centre of the frame, sensual private-release erotic glamour, ${style}`; }
    if (kind === "port" && role === "shipmaster") { const w = portWoman(subject, role); return `Waist-up portrait of a breathtakingly beautiful, sultry, dangerous ${w.who}, the ship master who rules the ${name} shipyard in 1860, giving the viewer a cold, wicked evil eye: narrowed kohl-lined eyes, one brow raised, chin slightly lowered, a cruel knowing half-smile, direct eye contact, ${w.hair}, ${w.dress}, a brass spyglass in one gloved hand, sweat-sheened skin, a ship's hull on the slipway, rigging and coiled rope behind her, lantern glow and harbour haze, shallow depth of field, she is the centre of the frame, sensual private-release erotic glamour, ${style}`; }
    if (kind === "port" && role === "mayor") { const w = portWoman(subject, role); return `Waist-up portrait of a breathtakingly beautiful, sultry ${w.who}, a former pirate queen who is now the lady mayor of ${name} in 1860 and keeps the town's ledger and collects its taxes, seated at a heavy teak desk and looking straight into the camera with a sly, appraising, seductive half-smile, as if she already knows what you owe her and how you will pay, direct eye contact, ${w.hair}, ${w.dress}, worn open at the throat and shoulders, a gold mayor's chain of office across her bare décolletage, a quill in one ringed hand, an open leather-bound ledger, a brass strongbox spilling silver dollars, tax seals and a cutlass hung on the wall behind her, warm candle and lantern glow, harbour window haze, shallow depth of field, she is the centre of the frame, sensual private-release erotic glamour, ${style}`; }
    if (kind === "port" && role === "taxlady") { const w = portWoman(subject, role); return `Waist-up portrait of a breathtakingly beautiful, sultry ${w.who}, the tax collector who works the ${name} waterfront in 1860 and takes the town's cut of every cargo, standing at the foot of the gangway with an open tally book and a brass-bound strongbox, looking straight into the camera with a sweet, merciless, teasing smile and one raised eyebrow, direct eye contact, ${w.hair}, ${w.dress}, a jade customs seal on a cord resting against her bare skin, a brass stamp and a pen in her gloved hands, sacks of silver dollars, stamped cargo chests, a ship's hull and rigging behind her, warm lantern glow and harbour haze, shallow depth of field, she is the centre of the frame, sensual private-release erotic glamour, ${style}`; }
    if (kind === "port") return `The port of ${name} in the 1860s seen from the water, busy trading harbour with junks, lorchas and clipper ships at anchor, waterfront godowns and hongs, ${style}`;
    if (kind === "ship") return shipPrompt(subject, role, style);
    if (kind === "cargo") return `Still life of ${name} as 1860s trade cargo, crates, chests and bales on a teak deck, square composition, no person, ${style}`;
    if (kind === "service") return `The interior of the ${name} at a Hong Kong trading harbor in the 1860s, wide environmental shot, period details, no text or people, ${style}`;
    if (kind === "scene") return `${name} on the China Seas in 1860, a trading fleet caught in the moment, ${style}`;
    return `${name}, ${style}`;
  }

  function genPanel() {
    if (!M.genOpen) return "";
    const kind = M.kind || "persona", K = kinds()[kind];
    const subs = subjectsFor(kind);
    const subject = M.subject || (subs[0] ? subs[0][0] : "");
    const key = kind + ":" + subject;
    if (M.gen.forKey !== key) {
      M.gen.forKey = key;
      M.gen.prompt = defaultPrompt(kind, subject);
      M.gen.aspect = ASPECT_FOR[kind] || "3:4";
      M.gen.roles = K.default_role ? [K.default_role] : [];
    }
    const aspects = Object.keys((M.lib && M.lib.aspects) || { "3:4": 1 });
    const running = M.jobs.filter(j => ["waiting", "running", "cancelling"].includes(j.status));
    return `<section class="card ml-gen"><h2>Generate on the AI farm</h2>
      <p class="help">Pictures are painted one after another in the background and each is filed under
        <b>${e(K.one)} · ${e(subjectName(kind, subject))}</b> as soon as it finishes, so you can keep working.
        Prompts that ask for nudity or erotic styling are tagged NSFW automatically.</p>
      <div class="ml-gen-grid">
        <label>Subject<select data-mlgenf="subject">${subs.map(([k, n]) => `<option value="${e(k)}"${k === subject ? " selected" : ""}>${e(n)}</option>`).join("")}</select></label>
        <label>Shape<select data-mlgenf="aspect">${aspects.map(a => `<option${a === M.gen.aspect ? " selected" : ""}>${e(a)}</option>`).join("")}</select></label>
        <label>How many<input type="number" min="1" max="8" value="${M.gen.count}" data-mlgenf="count"></label>
        <label>NSFW tag<select data-mlgenf="nsfw">${[["auto", "Read the prompt"], ["yes", "Always NSFW"], ["no", "Never NSFW"]].map(([k, n]) =>
          `<option value="${k}"${k === M.gen.nsfw ? " selected" : ""}>${n}</option>`).join("")}</select></label>
        <label class="ml-grow">Tags<input type="text" value="${e(M.gen.tags)}" data-mlgenf="tags" placeholder="night, rain, close-up"></label>
      </div>
      ${K.roles.length ? `<div class="ml-roles">${K.roles.map(([k, n]) => `<label class="ml-check"><input type="checkbox" data-mlgenrole="${k}"${M.gen.roles.includes(k) ? " checked" : ""}> ${e(n)}</label>`).join("")}</div>` : ""}
      <textarea rows="5" class="code" data-mlgenf="prompt" id="mlgenprompt">${e(M.gen.prompt)}</textarea>
      <div class="row"><button type="button" class="primary" data-mlgo="${e(kind)}|${e(subject)}">Paint ${M.gen.count} picture${M.gen.count == 1 ? "" : "s"}</button>
        <button type="button" class="link" data-mlgenreset="1">reset prompt</button>
        <span class="help">${running.length ? `${running.length} job${running.length === 1 ? "" : "s"} in the queue` : "The farm is idle."}</span></div>
      ${jobList()}
    </section>`;
  }

  function jobList() {
    const active = j => ["waiting", "running", "cancelling"].includes(j.status);
    const finished = M.jobs.filter(j => !active(j)).length;
    const shown = (M.jobsOpen ? M.jobs : M.jobs.filter(active)).slice(0, 8);
    const toggle = finished ? `<button type="button" class="link ml-jobs-toggle" data-mljobs="1">${M.jobsOpen ? "hide finished" : `show ${finished} finished`}</button>` : "";
    const items = shown.length ? `<ul class="ml-jobs">${shown.map(j => `<li class="${e(j.status)}">
        <b>${e(subjectName(j.kind, j.subject))}</b> <span>${j.done}/${j.count} painted${j.failed ? `, ${j.failed} failed` : ""} · ${e(j.status)}</span>
        ${j.error ? `<small>${e(j.error)}</small>` : ""}
        ${["waiting", "running"].includes(j.status) ? `<button type="button" class="link" data-mlcancel="${e(j.id)}">stop</button>` : ""}</li>`).join("")}</ul>` : "";
    return toggle + items;
  }

  function rulesPanel() {
    if (!M.rulesOpen || !M.rulesDraft) return "";
    const R = M.rulesDraft.rules, O = M.rulesDraft.options, modes = M.lib.modes;
    const modeSel = (val, attr, blank) => `<select ${attr}>${blank ? `<option value="">(${e(blank)})</option>` : ""}${modes.map(([k, n]) =>
      `<option value="${k}"${k === val ? " selected" : ""}>${e(n)}</option>`).join("")}</select>`;
    const rows = KIND_ORDER.filter(k => !["reference", "other"].includes(k)).map(k => {
      const r = R.defaults[k];
      return `<tr><th>${e(kinds()[k].label)}</th><td>${modeSel(r.mode, `data-mlrule="${k}|mode"`)}</td>
        <td><input type="number" min="2" max="900" value="${r.seconds}" data-mlrule="${k}|seconds"> s</td>
        <td><input type="number" min="0" max="100" value="${r.video_chance}" data-mlrule="${k}|video_chance"> %</td></tr>`;
    }).join("");
    const kind = M.kind && !["reference", "other"].includes(M.kind) ? M.kind : "persona";
    const over = subjectsFor(kind).map(([s, name]) => {
      const o = R.subjects[kind + ":" + s] || {};
      return `<tr><th>${e(name)}</th><td>${modeSel(o.mode || "", `data-mlover="${kind}:${s}|mode"`, "as above")}</td>
        <td><input type="number" min="2" max="900" value="${o.seconds == null ? "" : o.seconds}" placeholder="${R.defaults[kind].seconds}" data-mlover="${kind}:${s}|seconds"> s</td>
        <td><input type="number" min="0" max="100" value="${o.video_chance == null ? "" : o.video_chance}" placeholder="${R.defaults[kind].video_chance}" data-mlover="${kind}:${s}|video_chance"> %</td></tr>`;
    }).join("");
    return `<section class="card ml-rules"><h2>Playback rules</h2>
      <p class="help">How screens choose among several pictures. <b>Random</b> picks again each time a picture comes on screen
        (and for every spoken line). <b>Shuffle</b> and <b>Rotate</b> change on a timer. <b>Fixed</b> always shows the starred item.
        <b>Video chance</b> is how often a clip is played instead of a picture when both exist.</p>
      <div class="ml-rules-cols"><div><h3>Every kind</h3><table class="ml-table"><thead><tr><th></th><th>Choose</th><th>Change every</th><th>Video chance</th></tr></thead><tbody>${rows}</tbody></table></div>
      <div><h3>Per ${e(kinds()[kind].one.toLowerCase())} (blank = as above)</h3><table class="ml-table"><tbody>${over}</tbody></table></div></div>
      <h3>Options</h3><div class="ml-gen-grid">
        <label>While a line is read<select data-mlopt="speaker_card"><option value="card"${O.speaker_card === "card" ? " selected" : ""}>Large speaker card (picture or clip)</option><option value="badge"${O.speaker_card === "badge" ? " selected" : ""}>Small round badge</option></select></label>
        <label>Harbor board gallery<select data-mlopt="board_gallery"><option value="1"${O.board_gallery ? " selected" : ""}>Show port pictures</option><option value="0"${!O.board_gallery ? " selected" : ""}>Off</option></select></label>
        <label>New generated pictures<select data-mlopt="new_nsfw"><option value="auto"${O.new_nsfw === "auto" ? " selected" : ""}>NSFW if the prompt asks for it</option><option value="yes"${O.new_nsfw === "yes" ? " selected" : ""}>Always start NSFW</option><option value="no"${O.new_nsfw === "no" ? " selected" : ""}>Never start NSFW</option></select></label>
      </div>
      <div class="row"><button type="button" class="primary" data-mlrulesave="1">Save rules</button><button type="button" class="link" data-mlrulereset="1">undo changes</button></div></section>`;
  }

  function tile(i) {
    const on = M.sel.has(i.id);
    const inUse = M.lib.in_use.includes(i.url);
    return `<div class="ml-tile${on ? " on" : ""}${i.enabled ? "" : " off"}${i.nsfw ? " nsfw" : ""}" data-mlitem="${e(i.id)}" tabindex="0">
      <div class="ml-art">${thumb(i, "ml-img")}
        <span class="ml-badges">${i.primary ? '<b class="star" title="Primary (used when the rule is Fixed)">★</b>' : ""}${i.type === "video" ? "<b>▶ video</b>" : ""}${i.nsfw ? '<b class="nsfw">NSFW</b>' : ""}${!i.reviewed ? '<b class="rev">review</b>' : ""}${inUse ? '<b class="use" title="Used by a setting (cast portrait or Graphics page)">in use</b>' : ""}${!i.enabled ? "<b>off</b>" : ""}</span></div>
      <div class="ml-cap"><b>${e(i.title || subjectName(i.kind, i.subject))}</b>
        <small>${i.roles.length ? i.roles.map(r => e(roleName(i.kind, r))).join(", ") : "any role"}${i.tags.length ? " · " + i.tags.map(e).join(", ") : ""}</small></div></div>`;
  }

  function detail() {
    if (M.sel.size !== 1) return "";
    const i = byId([...M.sel][0]);
    if (!i) return "";
    const K = kinds()[i.kind] || { roles: [] };
    const subs = subjectsFor(i.kind);
    const free = (K.subjects === "free" || i.kind === "scene");
    return `<aside class="card ml-detail">
      <div class="ml-big">${i.missing ? '<div class="ml-missing">file missing</div>' : i.type === "video"
        ? `<video src="${e(i.url)}" controls loop playsinline></video>` : `<a href="${e(i.url)}" target="_blank" rel="noopener"><img src="${e(i.url)}" alt=""></a>`}</div>
      <div class="ml-switches">
        <button type="button" class="ml-nsfw${i.nsfw ? " on" : ""}" data-mlset="nsfw" data-v="${i.nsfw ? "0" : "1"}">${i.nsfw ? "NSFW" : "Family-friendly"}</button>
        <button type="button" class="${i.primary ? "on" : ""}" data-mlset="primary" data-v="${i.primary ? "0" : "1"}" title="Shown when the rule is Fixed">★ ${i.primary ? "Primary" : "Make primary"}</button>
        <button type="button" class="${i.enabled ? "on" : ""}" data-mlset="enabled" data-v="${i.enabled ? "0" : "1"}">${i.enabled ? "In rotation" : "Switched off"}</button>
        ${!i.reviewed ? `<button type="button" data-mlset="reviewed" data-v="1">Mark reviewed</button>` : ""}
      </div>
      <div class="ml-fields">
        <label>Kind<select data-mlfield="kind">${KIND_ORDER.map(k => `<option value="${k}"${k === i.kind ? " selected" : ""}>${e(kinds()[k].one)}</option>`).join("")}</select></label>
        <label>${e(K.one || "Subject")}${free && !subs.length
          ? `<input type="text" data-mlfield="subject" value="${e(i.subject)}" placeholder="lower_case_key">`
          : `<select data-mlfield="subject"><option value="">(none)</option>${subs.map(([k, n]) => `<option value="${e(k)}"${k === i.subject ? " selected" : ""}>${e(n)}</option>`).join("")}</select>`}</label>
        ${K.roles.length ? `<div class="ml-roles"><span>Roles <small>(none ticked = any)</small></span>${K.roles.map(([k, n]) =>
          `<label class="ml-check" title="${e(n)}"><input type="checkbox" data-mlrole="${k}"${i.roles.includes(k) ? " checked" : ""}> ${e(n.split(":")[0])}</label>`).join("")}</div>` : ""}
        <label>Title<input type="text" data-mlfield="title" value="${e(i.title)}" maxlength="80"></label>
        <label>Tags<input type="text" data-mlfield="tags" value="${e(i.tags.join(", "))}" placeholder="comma, separated"></label>
        <label>Weight in random picks <b>${i.weight}</b><input type="range" min="1" max="10" value="${i.weight}" data-mlfield="weight"></label>
      </div>
      <p class="help ml-meta">${e(i.type === "video" ? "Video" : (i.width ? i.width + " × " + i.height : "Picture"))} · ${fmtBytes(i.bytes || 0)} · ${e(i.source)}${i.added ? " · " + e(i.added) : ""}${i.seed != null ? " · seed " + e(i.seed) : ""}<br><code>${e(i.url)}</code></p>
      ${i.prompt ? `<details><summary>Prompt</summary><p class="mono ml-prompt">${e(i.prompt)}</p><button type="button" class="link" data-mlmore="${e(i.id)}">Paint more like this</button></details>` : ""}
      <div class="row">${i.kind === "persona" && i.type === "image" && CFG.characters[i.subject]
        ? `<button type="button" data-mlprofile="${e(i.id)}"${CFG.characters[i.subject].portrait === i.url ? " disabled" : ""}>${CFG.characters[i.subject].portrait === i.url ? "Profile picture" : "Make profile picture"}</button>` : ""}
        <button type="button" class="danger" data-mldel="${e(i.id)}">Remove</button></div>
    </aside>`;
  }

  function bulk() {
    if (M.sel.size < 2) return "";
    const K = kinds()[M.kind];
    return `<div class="card ml-bulk"><b>${M.sel.size} selected</b>
      <button type="button" data-mlbulk="nsfw">Tag NSFW</button><button type="button" data-mlbulk="sfw">Family-friendly</button>
      <button type="button" data-mlbulk="on">In rotation</button><button type="button" data-mlbulk="off">Switch off</button>
      <button type="button" data-mlbulk="reviewed">Mark reviewed</button>
      <input type="text" id="mlbulktag" placeholder="tag">
      <button type="button" data-mlbulk="addtag">Add tag</button><button type="button" data-mlbulk="deltag">Remove tag</button>
      ${K && K.roles.length ? `<select id="mlbulkrole">${K.roles.map(([k, n]) => `<option value="${k}">${e(n.split(":")[0])}</option>`).join("")}</select>
        <button type="button" data-mlbulk="addrole">Add role</button><button type="button" data-mlbulk="delrole">Remove role</button>` : ""}
      ${M.kind ? `<select id="mlbulkmove">${subjectsFor(M.kind).map(([k, n]) => `<option value="${e(k)}">${e(n)}</option>`).join("")}</select>
        <button type="button" data-mlbulk="move">Move to</button>` : ""}
      <button type="button" class="danger" data-mlbulk="delete">Remove</button>
      <button type="button" class="link" data-mlbulk="none">clear selection</button></div>`;
  }

  function render() {
    if (!M.lib) {
      if (!M.loading) setTimeout(() => load(), 0);
      return head("Media Library", "Loading the library…");
    }
    const c = M.lib.counts, list = filtered();
    const crumbs = M.subject ? `<p class="ml-crumb"><button type="button" class="link" data-mlsubject="">← All ${e(kinds()[M.kind].label.toLowerCase())}</button>
      <b>${e(subjectName(M.kind, M.subject))}</b></p>` : "";
    return head("Media Library", "", familySwitch()) +
      `<div class="ml-stats"><span><b>${c.total}</b> items</span><span><b>${c.video}</b> video</span><span><b>${c.nsfw}</b> NSFW</span>
        ${c.review ? `<button type="button" class="link ml-stat-review" data-mlreviewall="1" title="Show every item that needs review"><b>${c.review}</b> need review</button>` : `<span><b>0</b> need review</span>`}<span><b>${fmtBytes(c.bytes)}</b> on disk</span>
        <span class="muted">Drop files into <code>web/media/&lt;kind&gt;/&lt;subject&gt;/</code> (a folder named <code>nsfw</code> tags them) and press Scan folders.</span></div>` +
      kindTabs() + toolbar() + uploadBar() + genPanel() + rulesPanel() + subjectCards() + crumbs + bulk() +
      `<div class="ml-body${M.sel.size === 1 ? " with-detail" : ""}${CFG.content.rating === "family" ? " ml-family" : ""}">
        <div class="ml-grid">${list.map(tile).join("") || `<p class="muted ml-empty">Nothing here yet. Upload pictures or clips, generate some, or drop files into the folder and scan.</p>`}</div>
        ${detail()}</div>`;
  }

  /* ---------------------------------------------------------- actions -- */
  async function change(ids, changes, extra) {
    const res = await api("media/update", Object.assign({ ids, changes }, extra || {}));
    if (!res.ok) { toast(res.error || "Not saved.", true); return; }
    await load(true);
  }

  function upload(files) {
    const kind = M.kind || "other";
    const K = kinds()[kind];
    const subject = M.subject || "";
    if (!subject && kind !== "other" && !confirm(`Upload to ${K.label} without choosing a ${K.one.toLowerCase()}? Choose one in the "${K.one}" box first to file them properly.\n\nOK uploads them unsorted.`)) return;
    const nsfw = M.upNsfw || M.nsfw === "nsfw" ? "1" : "0";
    const roles = M.role || (K.default_role || "");
    [...files].forEach(f => {
      const u = { name: f.name, pct: 0, err: "" };
      M.uploads.push(u);
      const qs = new URLSearchParams({ name: f.name, kind: subject ? kind : (kind === "other" ? "other" : kind), subject, roles: subject ? roles : "", nsfw });
      const xhr = new XMLHttpRequest();
      xhr.open("POST", "/api/admin/media/upload?" + qs.toString());
      xhr.setRequestHeader("X-SeaTrader", "admin");
      xhr.upload.onprogress = ev => { if (ev.lengthComputable) { u.pct = Math.round(ev.loaded / ev.total * 99); drawUploads(); } };
      xhr.onload = () => {
        let res = {};
        try { res = JSON.parse(xhr.responseText); } catch (x) { res = { ok: false, error: "The server did not answer." }; }
        if (res.ok) u.pct = 100; else u.err = res.error || "failed";
        drawUploads();
        if (M.uploads.every(x => x.pct >= 100 || x.err)) {
          setTimeout(() => { M.uploads = M.uploads.filter(x => x.err); redraw(); }, 1800);
          load(true);
        }
      };
      xhr.onerror = () => { u.err = "network error"; drawUploads(); };
      xhr.send(f);
    });
    redraw();
  }
  function drawUploads() {
    const bar = document.querySelector(".ml-uploads");
    if (bar) bar.outerHTML = uploadBar(); else redraw();
  }

  function watchJobs() {
    const busy = M.jobs.some(j => ["waiting", "running", "cancelling"].includes(j.status));
    if (busy && !M.poll) {
      M.poll = setInterval(async () => {
        if (section !== "media") return;
        const res = await api("media/jobs");
        if (!res.ok) return;
        const before = JSON.stringify(M.jobs.map(j => [j.id, j.done, j.status]));
        M.jobs = res.jobs;
        if (JSON.stringify(M.jobs.map(j => [j.id, j.done, j.status])) !== before) await load(true);
        if (!M.jobs.some(j => ["waiting", "running", "cancelling"].includes(j.status))) { clearInterval(M.poll); M.poll = null; }
      }, 4000);
    }
  }

  function goSubject(kind, subject) {
    M.kind = kind; M.subject = subject; M.role = ""; M.sel.clear();
    redraw();
  }

  async function onClick(ev) {
    if (section !== "media") return;
    const t = ev.target;
    const el = t.closest("[data-mlkind],[data-mlsubject],[data-mlitem],button");
    if (!el) return;
    const d = el.dataset;
    if (d.mlreview) { M.review = !M.review; M.sel.clear(); return redraw(); }
    if (d.mlreviewall) { M.review = true; M.kind = ""; M.subject = ""; M.role = ""; M.sel.clear(); M.gen.forKey = ""; return redraw(); }
    if (d.mlkind !== undefined) { M.kind = d.mlkind; M.subject = ""; M.role = ""; M.sel.clear(); M.gen.forKey = ""; return redraw(); }
    if (d.mlsubject !== undefined) { M.gen.forKey = ""; return goSubject(M.kind, d.mlsubject); }
    if (d.mlitem) {
      if (t.closest("video") && el.querySelector("video") && ev.detail > 1) return;
      const id = d.mlitem, list = filtered().map(i => i.id);
      if (ev.shiftKey && M.last && list.includes(M.last)) {
        const [a, b] = [list.indexOf(M.last), list.indexOf(id)].sort((x, y) => x - y);
        list.slice(a, b + 1).forEach(x => M.sel.add(x));
      } else if (ev.ctrlKey || ev.metaKey) {
        if (M.sel.has(id)) M.sel.delete(id); else M.sel.add(id);
      } else {
        const only = M.sel.size === 1 && M.sel.has(id);
        M.sel.clear();
        if (!only) M.sel.add(id);
      }
      M.last = id;
      return redraw();
    }
    if (d.mlsafe !== undefined) {
      const fam = d.mlsafe === "1";
      el.disabled = true;
      const res = await api("media/safe", { family: fam });
      if (!res.ok) { el.disabled = false; return toast(res.error, true); }
      patchSaved(c => { c.content.rating = res.rating; });
      toast(res.msg);
      return load(true);
    }
    if (d.mlgen) { M.genOpen = !M.genOpen; if (M.genOpen && !M.kind) M.kind = "persona"; return redraw(); }
    if (d.mljobs) { M.jobsOpen = !M.jobsOpen; try { localStorage.setItem("ml.jobsOpen", M.jobsOpen ? "1" : "0"); } catch (_) {} return redraw(); }
    if (d.mlrules) { M.rulesOpen = !M.rulesOpen; return redraw(); }
    if (d.mlscan) {
      const res = await api("media/scan", {});
      toast(res.ok ? res.msg : res.error, !res.ok);
      return load(true);
    }
    if (d.mlgenreset) { M.gen.forKey = ""; return redraw(); }
    if (d.mlgo) {
      const [kind, subject] = d.mlgo.split("|");
      const prompt = ($("mlgenprompt") || {}).value || M.gen.prompt;
      el.disabled = true;
      const res = await api("media/generate", { kind, subject, roles: M.gen.roles, prompt, aspect: M.gen.aspect,
        count: M.gen.count, nsfw: M.gen.nsfw, tags: M.gen.tags });
      el.disabled = false;
      toast(res.ok ? res.msg : res.error, !res.ok);
      if (res.ok) { M.kind = kind; M.subject = subject; return load(true); }
      return;
    }
    if (d.mlcancel) {
      const res = await api("media/cancel", { job: d.mlcancel });
      toast(res.ok ? res.msg : res.error, !res.ok);
      return load(true);
    }
    if (d.mlmore) {
      const i = byId(d.mlmore);
      if (!i) return;
      M.kind = i.kind; M.subject = i.subject; M.genOpen = true;
      M.gen.forKey = i.kind + ":" + i.subject; M.gen.prompt = i.prompt; M.gen.roles = i.roles.slice();
      redraw();
      return window.scrollTo(0, 0);
    }
    if (d.mlset) {
      const id = [...M.sel][0], v = d.v === "1";
      return change([id], { [d.mlset]: v });
    }
    if (d.mlprofile) {
      const res = await api("media/profile", { ids: [d.mlprofile] });
      if (!res.ok) return toast(res.error, true);
      patchSaved(c => { if (c.characters[res.cid]) c.characters[res.cid].portrait = res.url; });
      toast(res.msg);
      return load(true);
    }
    if (d.mldel) {
      if (!d.armed) { d.armed = "1"; el.textContent = "Click again to remove"; setTimeout(() => { if (el.isConnected) { delete d.armed; el.textContent = "Remove"; } }, 3500); return; }
      const res = await api("media/delete", { ids: [d.mldel] });
      toast(res.ok ? res.msg : res.error, !res.ok);
      M.sel.clear();
      return load(true);
    }
    if (d.mlrulesave) {
      const res = await api("media/rules", M.rulesDraft);
      toast(res.ok ? res.msg : res.error, !res.ok);
      M.rulesDraft = null;
      return load(true);
    }
    if (d.mlrulereset) { M.rulesDraft = { rules: clone(M.lib.rules), options: clone(M.lib.options) }; return redraw(); }
    if (d.mlbulk) {
      const ids = [...M.sel], op = d.mlbulk;
      const tag = ($("mlbulktag") || {}).value || "", role = ($("mlbulkrole") || {}).value || "", move = ($("mlbulkmove") || {}).value || "";
      if (op === "none") { M.sel.clear(); return redraw(); }
      if (op === "delete") {
        if (!d.armed) { d.armed = "1"; el.textContent = "Click again to remove " + ids.length; setTimeout(() => { if (el.isConnected) { delete d.armed; el.textContent = "Remove"; } }, 3500); return; }
        const res = await api("media/delete", { ids });
        toast(res.ok ? res.msg : res.error, !res.ok);
        M.sel.clear();
        return load(true);
      }
      const map = {
        nsfw: [{ nsfw: true }], sfw: [{ nsfw: false }], on: [{ enabled: true }], off: [{ enabled: false }], reviewed: [{ reviewed: true }],
        addtag: [{}, { add_tags: [tag] }], deltag: [{}, { remove_tags: [tag] }],
        addrole: [{}, { add_roles: [role] }], delrole: [{}, { remove_roles: [role] }],
        move: [{ kind: M.kind, subject: move }],
      }[op];
      if (!map) return;
      if ((op === "addtag" || op === "deltag") && !tag.trim()) return toast("Type a tag first.", true);
      return change(ids, map[0], map[1]);
    }
  }

  function onInput(ev) {
    if (section !== "media") return;
    const el = ev.target, d = el.dataset;
    if (d.mlf) {
      M[d.mlf] = el.type === "checkbox" ? el.checked : el.value;
      if (d.mlf === "upNsfw") return;
      if (d.mlf === "sort") { try { localStorage.setItem("ml.sort", M.sort); } catch (_) {} }
      if (d.mlf === "subject") { M.role = ""; M.gen.forKey = ""; }
      M.sel.clear();
      if (d.mlf === "q") { clearTimeout(M.timers.q); M.timers.q = setTimeout(redraw, 220); return; }
      return redraw();
    }
    if (d.mlupload && ev.type === "change") { upload(el.files); el.value = ""; return; }
    if (d.mlgenf) {
      const k = d.mlgenf;
      if (k === "subject") { M.subject = el.value; M.gen.forKey = ""; return redraw(); }
      M.gen[k] = k === "count" ? Math.max(1, Math.min(8, parseInt(el.value, 10) || 1)) : el.value;
      if (k === "count" && ev.type === "change") redraw();
      return;
    }
    if (d.mlgenrole) {
      M.gen.roles = M.gen.roles.filter(r => r !== d.mlgenrole);
      if (el.checked) M.gen.roles.push(d.mlgenrole);
      // A market keeper, ship master, mayor or tax lady is a portrait of her, not a harbour view: swap the starting prompt, shape and roles.
      const womanRoles = ["keeper", "shipmaster", "mayor", "taxlady"];
      if (womanRoles.includes(d.mlgenrole) && el.checked && (M.kind || "persona") === "port") {
        const subject = M.gen.forKey.split(":")[1] || "";
        const box = $("mlgenprompt"), now = (box && box.value) || M.gen.prompt;
        const stock = [undefined].concat(womanRoles).some(r => now === defaultPrompt("port", subject, r));
        if (!now.trim() || stock) M.gen.prompt = defaultPrompt("port", subject, d.mlgenrole);
        M.gen.roles = [d.mlgenrole]; M.gen.aspect = "3:4";
        return redraw();
      }
      // A persona's mood pictures (18 Nov 2026): ticking a mood puts that expression into her own portrait prompt
      // (stock prompts only), e.g. Sly for Powder's whisper when pirates misjudge the hold.
      if ((M.kind || "persona") === "persona" && PERSONA_MOODS[d.mlgenrole]) {
        const pid = M.gen.forKey.split(":")[1] || "";
        const box = $("mlgenprompt"), now = (box && box.value) || M.gen.prompt;
        const stock = [undefined].concat(Object.keys(PERSONA_MOODS)).some(r => now === personaPrompt(pid, r));
        if (el.checked) {
          if (!now.trim() || stock) M.gen.prompt = personaPrompt(pid, d.mlgenrole);
          M.gen.roles = [d.mlgenrole]; M.gen.aspect = "3:4";
        } else if (stock) {
          M.gen.prompt = personaPrompt(pid, M.gen.roles[0]);
        }
        return redraw();
      }
      // A ship's card, under-sail and in-battle pictures each get their own starting prompt (stock prompts only).
      const subj = M.gen.forKey.split(":")[1] || "";
      if ((M.kind || "persona") === "ship" && ["card", "sailing", "battle"].includes(d.mlgenrole)) {
        const box = $("mlgenprompt"), now = (box && box.value) || M.gen.prompt;
        const stock = [undefined, "card", "sailing", "battle"].some(r => now === defaultPrompt("ship", subj, r));
        if (el.checked) {
          if (!now.trim() || stock) M.gen.prompt = defaultPrompt("ship", subj, d.mlgenrole);
          M.gen.roles = [d.mlgenrole]; M.gen.aspect = d.mlgenrole === "card" ? "3:2" : "16:9";
        } else if (stock) {
          M.gen.prompt = defaultPrompt("ship", subj, M.gen.roles[0]);
        }
        return redraw();
      }
      // A sea battle moment gets its own starting prompt for that enemy (only replaces a stock prompt, never your own words).
      if ((M.kind || "persona") === "scene" && BATTLE_ENEMY[subj] && BATTLE_MOMENTS[d.mlgenrole]) {
        const box = $("mlgenprompt"), now = (box && box.value) || M.gen.prompt;
        const stock = [undefined].concat(Object.keys(BATTLE_MOMENTS)).some(r => now === defaultPrompt("scene", subj, r));
        if (el.checked) {
          if (!now.trim() || stock) M.gen.prompt = defaultPrompt("scene", subj, d.mlgenrole);
          M.gen.roles = [d.mlgenrole]; M.gen.aspect = "16:9";
        } else if (stock) {
          M.gen.prompt = defaultPrompt("scene", subj, M.gen.roles[0]);
        }
        return redraw();
      }
      return;
    }
    if (d.mlrule && ev.type === "change") {
      const [k, f] = d.mlrule.split("|");
      M.rulesDraft.rules.defaults[k][f] = f === "mode" ? el.value : Number(el.value);
      return;
    }
    if (d.mlover && ev.type === "change") {
      const [key, f] = d.mlover.split("|");
      const o = M.rulesDraft.rules.subjects[key] = M.rulesDraft.rules.subjects[key] || {};
      if (el.value === "") delete o[f]; else o[f] = f === "mode" ? el.value : Number(el.value);
      if (!Object.keys(o).length) delete M.rulesDraft.rules.subjects[key];
      return;
    }
    if (d.mlopt && ev.type === "change") {
      M.rulesDraft.options[d.mlopt] = d.mlopt === "board_gallery" ? el.value === "1" : el.value;
      return;
    }
    const id = [...M.sel][0];
    if (!id) return;
    if (d.mlrole && ev.type === "change") {
      return change([id], {}, el.checked ? { add_roles: [d.mlrole] } : { remove_roles: [d.mlrole] });
    }
    if (d.mlfield) {
      const f = d.mlfield;
      if (f === "weight") { const b = el.parentNode.querySelector("b"); if (b) b.textContent = el.value; }
      if (ev.type !== "change") return;
      const v = f === "weight" ? Number(el.value) : f === "tags" ? el.value.split(",") : el.value;
      const ch = { [f]: v };
      if (f === "kind") ch.subject = "";
      return change([id], ch);
    }
  }

  function onKey(ev) {
    if (section !== "media") return;
    if (ev.key === "Escape" && M.sel.size) { M.sel.clear(); redraw(); }
    const tileEl = ev.target.closest && ev.target.closest("[data-mlitem]");
    if (tileEl && (ev.key === "Enter" || ev.key === " ")) { ev.preventDefault(); tileEl.click(); }
  }

  /* The Cast page links straight to a persona's pictures. */
  document.addEventListener("click", ev => {
    const el = ev.target.closest && ev.target.closest("[data-medialib]");
    if (!el) return;
    ev.preventDefault();
    if (section === "cast" && window.SeaTraderCast) SeaTraderCast.leave();
    const [kind, subject] = el.dataset.medialib.split(":");
    M.kind = kind; M.subject = subject || ""; M.role = ""; M.sel.clear(); M.gen.forKey = "";
    if (typeof go === "function") return go("media");
    section = "media";
    history.replaceState(null, "", "#media");
    draw();
    window.scrollTo(0, 0);
  });

  document.addEventListener("DOMContentLoaded", () => {
    const m = document.getElementById("main");
    m.addEventListener("click", onClick);
    m.addEventListener("input", onInput);
    m.addEventListener("change", onInput);
    m.addEventListener("keydown", onKey);
    m.addEventListener("mouseover", ev => { const v = ev.target.closest && ev.target.closest(".ml-tile video"); if (v) v.play().catch(() => {}); });
    m.addEventListener("mouseout", ev => { const v = ev.target.closest && ev.target.closest(".ml-tile video"); if (v) v.pause(); });
  });

  window.SeaTraderMedia = {
    render,
    enter() { if (M.lib) load(true); },
    leave() { if (M.poll) { clearInterval(M.poll); M.poll = null; } },
  };
})();
