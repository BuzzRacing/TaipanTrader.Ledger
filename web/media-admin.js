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
    gen: { kind: "", subject: "", roles: [], aspect: "3:4", count: 2, nsfw: "auto", prompt: "", tags: "", forKey: "" },
    // Gallery 2 (Anthony, 21 Nov 2026): filter rail + chips, Pictures/Videos/Pairs toggle, generate drawer, density, left menu collapse.
    port: "", job: "", tag: "", density: (() => { try { return localStorage.getItem("ml.density") || "m"; } catch (_) { return "m"; } })(),
    railOpen: (() => { try { return localStorage.getItem("ml.rail") !== "0"; } catch (_) { return true; } })(),
    navMin: (() => { try { return localStorage.getItem("ml.navmin") !== "0"; } catch (_) { return true; } })(),
    ab: { find: "", alts: "", view: "", expect: 0 }, motion: "",
    dsize: (() => { try { return localStorage.getItem("ml.dsize") || "wide"; } catch (_) { return "wide"; } })(),
    drawer: { open: false, mode: "gen", src: "" }, pickQ: "", jobsPop: false, cov: false,
    rec: { open: false, draft: null, busy: false, prog: "" }, recipes: [],
    rulesDraft: null, timers: {},
    // Videos (Anthony, 20 Nov 2026): the Make video panel and the side-by-side Compare of a clean + NSFW pair.
    vid: { open: false, src: "", partner: "", pair: true, motion: "", clean: "", preset: "idle", count: 2, tags: "" },
    cmp: "",
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

  /* ------------------------------------------------------------ video -- */
  // Clips made from a picture keep its id (from_item); a clean + NSFW pair made together shares a pair id.
  const clipsOf = id => items().filter(i => i.type === "video" && i.from_item === id);
  const posterOf = i => { const p = i && i.from_item ? byId(i.from_item) : null; return p && !p.missing ? p.url : ""; };
  const pairOf = pid => items().filter(i => i.type === "video" && i.pair === pid);
  // Motion prompts describe movement only: the look, the clothes and the rating come from the picture.
  // Anthony, 22 Nov 2026: 20 general presets, blunt and exact so the video model has nothing to guess.
  // [label, motion, group, clean twin]. A NSFW preset carries a tamer "clean twin" for the clean half of a pair.
  const END = " Steady camera, smooth natural motion.";
  const MOTIONS = {
    idle: ["Breathe and blink", "She stands still and breathes slowly, chest and shoulders rising and falling gently, blinks every two to three seconds, a faint closed-mouth smile, loose strands of hair stirring in a light breeze. Nothing else moves." + END, "clean"],
    look: ["Turn to camera", "She starts looking slightly away, turns her head to look straight into the camera, holds eye contact for three seconds with a slow smile, then looks away again to where she began. Her body stays still." + END, "clean"],
    speaking: ["Talk to camera", "She talks directly to the camera, lips moving steadily as if telling a story, head tilting, eyebrows lifting, one hand gesturing to stress each point, a playful smile between sentences, then she goes still." + END, "clean"],
    wave: ["Wave hello", "She raises one hand to shoulder height and waves at the camera with three slow side-to-side waves, smiling warmly and nodding once, then lowers her hand to where it began." + END, "clean"],
    walk: ["Walk toward camera", "She walks slowly toward the camera with a confident hip sway, four unhurried steps, skirts swishing, then stops, smiles and holds eye contact, then walks backward to where she began." + END, "clean"],
    prop: ["Play with what she holds", "She plays with the object in her hand: turns it over, tosses it a few inches into the air and catches it, then holds it up beside her face with a knowing smile and lowers it again. Her other hand rests on her hip." + END, "clean"],
    kiss: ["Wink and blow a kiss", "She winks at the camera, presses two fingertips to her lips, blows a kiss toward the camera with a small forward lean, smiles, and returns to her starting pose." + END, "clean"],
    hair: ["Flick her hair", "She tosses her head and flicks her hair back over one shoulder with one hand, runs her fingers through it from temple to ends, glances at the camera with a smile, and lets her hand drop." + END, "clean"],
    laugh: ["Laugh out loud", "She laughs out loud, shoulders shaking, head tipping back a little, the back of one hand pressed to her mouth, eyes crinkled, then catches her breath, grins at the camera and settles." + END, "clean"],
    hips: ["Hands on hips, sway", "She plants both hands on her hips and sways slowly from one hip to the other, chin lifted, one eyebrow raised, a knowing smile, holding eye contact with the camera, then stops centred." + END, "clean"],
    gust: ["Wind lifts her skirt (breezy business)", "A strong gust hits her from the side. Her skirt and petticoats blow up to her waist, showing her stockings, garters and bloomered backside. She gasps, laughs, grabs the hem with both hands and pushes it back down, hair whipping across her face, then smooths it flat." + END, "nsfw",
      "A strong gust hits her from the side. Her skirt and hair blow sideways. She laughs, grabs the hem with both hands and holds it down at her knees so nothing shows, then smooths it flat." + END],
    bend: ["Bend over (the rear view)", "She turns her back to the camera, bends forward at the waist with straight legs and her backside toward the camera, skirt riding up to show her stockings and bloomers, hips swaying slowly, then looks back over her shoulder with a wink and straightens up." + END, "nsfw",
      "She turns her back to the camera, bends forward at the waist as if picking something off the ground, skirt staying down, then looks back over her shoulder with a wink and straightens up." + END],
    unbutton: ["Unbutton her blouse (loose ends)", "Looking into the camera, she undoes her blouse buttons one at a time from the collar down, four buttons, slowly, then parts the fabric with both hands to show her cleavage and bites her lower lip." + END, "nsfw",
      "Looking into the camera, she undoes just the top button at her collar, fans her neck with one hand as if the room is warm, and smiles." + END],
    shimmy: ["Shimmy her bust (a bustling trade)", "She presses her upper arms together to push her breasts together and up, then shimmies her shoulders fast from side to side so her breasts bounce and jiggle, grinning at the camera, then stops and lets her arms drop." + END, "nsfw",
      "She shimmies her shoulders fast from side to side, laughing, hands on her hips, grinning at the camera, then stops." + END],
    hitch: ["Hitch her skirt (hem and haw)", "She grips her skirt hem in both hands and slowly hitches it up to the top of her thighs, showing stocking tops and garters, holds it there for two seconds with a cheeky smile, then drops it with a laugh." + END, "nsfw",
      "She grips her skirt hem in both hands and lifts it just to the ankle to show her boots, holds it for two seconds with a cheeky smile, then lets it drop." + END],
    peekaboo: ["Flash and cover (peek-a-boo)", "She pulls her neckline down with both hands for one second to flash her breasts, then covers them with her forearms, laughing and wide-eyed, then lowers her arms, tugs the neckline back up and winks." + END, "nsfw",
      "She tugs her neckline modestly higher with both hands, smooths her collar, laughs and winks at the camera." + END],
    wiggle: ["Wiggle her backside (tail wind)", "She turns her back to the camera and wiggles her hips side to side, her bottom jiggling under her skirt, one hand lifting the hem at the back for a second, then glances over her shoulder with a grin and turns back to face the camera." + END, "nsfw",
      "She turns her back to the camera and sways her hips side to side, skirt swishing, glances over her shoulder with a grin and turns back to face the camera." + END],
    garter: ["Adjust her garter (tied up)", "She lifts one foot onto a nearby chair or crate, slides her skirt up her thigh and adjusts her stocking garter, runs her hand up her thigh, looks at the camera with a slow smile, then puts her foot down and drops the skirt." + END, "nsfw",
      "She lifts one foot onto a nearby chair or crate and fixes the lace of her boot, brushes her skirt flat over her knee, looks at the camera with a slow smile, then puts her foot down." + END],
    lean: ["Lean in (cleavage on deck)", "She leans forward toward the camera with her forearms resting on a surface so her cleavage fills the lower frame, whispers something with a wink, holds for two seconds, then leans back upright." + END, "nsfw",
      "She leans forward toward the camera with her elbows on a surface and her chin on her hands, whispers something with a wink, then leans back upright." + END],
    spank: ["Slap her own backside (a stern word)", "She turns her back to the camera and gives her own backside a firm playful slap with one hand, the flesh and skirt jiggling, then looks back over her shoulder with a wink and a smirk and turns to face the camera." + END, "nsfw",
      "She turns her back to the camera and gives her skirt a playful pat with one hand as if dusting it off, then looks back over her shoulder with a wink and turns to face the camera." + END],
  };
  // Which movement a clip was made with (Anthony, 22 Nov 2026): its motion-<name> tag, else matched from the movement text
  // it saved (so clips made before the tags existed still filter). Old Jailer clips group under "keys".
  function motionKeyOf(i) {
    if (!i || i.type !== "video") return "";
    const t = (i.tags || []).find(x => String(x).startsWith("motion-"));
    if (t) return String(t).slice(7);
    const m = String(i.motion || "").trim();
    if (!m) return "";
    const hit = Object.entries(MOTIONS).find(([, v]) => v[1] === m || v[3] === m);
    if (hit) return hit[0];
    return /heavy iron keys/.test(m) ? "keys" : "custom";
  }
  const motionLabel = k => MOTIONS[k] ? MOTIONS[k][0].replace(/\s*\(.*\)$/, "") : k === "keys" ? "Keys (old Jailer)" : k === "custom" ? "Own words" : String(k).replace(/[-_]/g, " ");
  const motionSel = cur => {
    const opts = grp => Object.entries(MOTIONS).filter(([, v]) => v[2] === grp).map(([k, v]) => `<option value="${k}"${k === cur ? " selected" : ""}>${e(v[0])}</option>`).join("");
    return `<optgroup label="Everyday (clean)">${opts("clean")}</optgroup><optgroup label="Cheeky (NSFW)">${opts("nsfw")}</optgroup><option value="own"${cur === "own" ? " selected" : ""}>My own words</option>`;
  };
  // The other half of a pair: the newest picture of the same subject on the other side of the NSFW line
  // (a "clean" tag counts as clean), else any other picture of that subject.
  function suggestPartner(src) {
    if (!src || !src.tags) return "";
    const pics = items().filter(i => i.type === "image" && i.kind === src.kind && i.subject === src.subject && i.id !== src.id && !i.missing);
    const isClean = i => !i.nsfw || i.tags.includes("clean");
    const want = pics.filter(i => isClean(i) !== isClean(src));
    const pool = (want.length ? want : pics).slice().sort((a, b) => String(b.added).localeCompare(String(a.added)));
    return pool[0] ? pool[0].id : "";
  }
  function openVideo(id) {
    const i = byId(id);
    if (!i || i.type !== "image") return;
    M.vid.open = true; M.vid.src = id; M.vid.partner = suggestPartner(i); M.cmp = "";
    M.drawer = { open: true, mode: "vid", src: id };
    M.vid.pair = !!M.vid.partner;
    if (!M.vid.motion) { M.vid.motion = MOTIONS[M.vid.preset][1]; M.vid.clean = MOTIONS[M.vid.preset][3] || ""; }
    if (!M.vid.tags && i.tags.some(t => t.includes("jail"))) M.vid.tags = "jail warden";
  }

  function vidPanel() {
    if (!M.vid.open) return "";
    const src = byId(M.vid.src);
    if (!src) return "";
    const pics = items().filter(i => i.type === "image" && i.kind === src.kind && i.subject === src.subject && i.id !== src.id && !i.missing);
    const partner = M.vid.pair ? byId(M.vid.partner) : null;
    // In a pair the pair button decides the rating: the NSFW-flagged picture makes the NSFW clip.
    const [nsfwPic, cleanPic] = partner ? ((src.nsfw && !src.tags.includes("clean")) || !partner.nsfw || partner.tags.includes("clean") ? [src, partner] : [partner, src]) : [src, null];
    const n = M.vid.count * (partner ? 2 : 1);
    const face = (i, label) => `<figure class="ml-vid-pic"><img src="${e(i.url)}" alt=""><figcaption><b>${label}</b>${i.nsfw ? ' <em class="nsfw">NSFW</em>' : ""}${i.tags.includes("clean") ? " <em>clean</em>" : ""}</figcaption></figure>`;
    const running = M.jobs.filter(j => j.type === "video" && ["waiting", "running", "cancelling"].includes(j.status));
    return `<section class="card ml-vid"><h2>▶ Make video <small>Wan 2.2 · 12 s loop</small></h2>
      <p class="help">The clip starts and ends on the picture, so it loops without a jump. Describe the <b>movement only</b>:
        her look, clothes and rating come from the picture. Each clip takes a while on the farm and is filed under
        <b>${e(kinds()[src.kind].one)} · ${e(subjectName(src.kind, src.subject))}</b> with the picture's roles, marked "needs review".</p>
      <div class="ml-vid-pics">${partner ? face(nsfwPic, "NSFW clip from") + face(cleanPic, "Clean clip from") : face(src, "Clip from")}</div>
      <div class="ml-gen-grid">
        <label class="ml-check"><input type="checkbox" data-mlvidf="pair"${M.vid.pair ? " checked" : ""}${pics.length ? "" : " disabled"}> Make a pair (clean + NSFW)</label>
        ${M.vid.pair ? `<label>Other picture<select data-mlvidf="partner">${pics.map(i => `<option value="${e(i.id)}"${i.id === M.vid.partner ? " selected" : ""}>${e((i.title || i.tags.join(", ") || i.url.split("/").pop()).slice(0, 60))}${i.nsfw ? " (NSFW)" : ""}</option>`).join("")}</select></label>` : ""}
        <label>Movement<select data-mlvidf="preset">${motionSel(M.vid.preset)}</select></label>
        <label>Takes${partner ? " each" : ""}<input type="number" min="1" max="4" value="${M.vid.count}" data-mlvidf="count"></label>
        <label class="ml-grow">Tags<input type="text" value="${e(M.vid.tags)}" data-mlvidf="tags" placeholder="jail warden, night"></label>
      </div>
      <textarea rows="4" class="code" data-mlvidf="motion" id="mlvidmotion">${e(M.vid.motion)}</textarea>
      ${M.vid.pair && M.vid.clean ? `<label class="ml-cleantwin"><span>Clean half uses this softer movement <small>(the NSFW half uses the one above)</small></span><textarea rows="3" class="code" data-mlvidf="clean" id="mlvidclean">${e(M.vid.clean)}</textarea></label>` : ""}
      <div class="row"><button type="button" class="primary" data-mlvidgo="1">Make ${n} clip${n === 1 ? "" : "s"}</button>
        <button type="button" class="link" data-mlvidclose="1">close</button>
        <span class="help">${partner ? "Both halves use the same movement and the same seeds, so you compare like with like. " : ""}${running.length ? `${running.length} video job${running.length === 1 ? "" : "s"} in the queue.` : ""}</span></div>
    </section>`;
  }

  // Side by side: every take of a pair, NSFW on the left, clean on the right, matched by seed.
  // ---- A/B test a phrase (Anthony, 22 Nov 2026): same seed, one wording change, side by side ----
  function abVariants(srcId) {
    const src = byId(srcId);
    if (!src) return [];
    return items().filter(i => i.type === "image" && i.replaces === srcId && i.tags.includes("ab-test") && i.seed === src.seed)
      .sort((a, b) => String(a.added).localeCompare(String(b.added)) || String(a.id).localeCompare(String(b.id)));
  }
  // Word-level diff of the original prompt against a variant: html with <del>/<ins>, plus a short "what changed" label.
  function wordDiff(a, b) {
    const x = String(a || "").split(/\s+/).filter(Boolean), y = String(b || "").split(/\s+/).filter(Boolean);
    const n = x.length, m = y.length;
    if (n * m > 360000) return { html: e(b || ""), label: "changed" };
    const L = Array.from({ length: n + 1 }, () => new Uint16Array(m + 1));
    for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--) L[i][j] = x[i] === y[j] ? L[i + 1][j + 1] + 1 : Math.max(L[i + 1][j], L[i][j + 1]);
    const out = [], added = [], cut = [];
    let i = 0, j = 0;
    while (i < n && j < m) {
      if (x[i] === y[j]) { out.push(e(y[j])); i++; j++; }
      else if (L[i + 1][j] >= L[i][j + 1]) { out.push(`<del>${e(x[i])}</del>`); cut.push(x[i]); i++; }
      else { out.push(`<ins>${e(y[j])}</ins>`); added.push(y[j]); j++; }
    }
    while (i < n) { out.push(`<del>${e(x[i])}</del>`); cut.push(x[i]); i++; }
    while (j < m) { out.push(`<ins>${e(y[j])}</ins>`); added.push(y[j]); j++; }
    const label = added.length ? added.join(" ") : cut.length ? "cut: " + cut.join(" ") : "same wording";
    return { html: out.join(" "), label: label.length > 48 ? label.slice(0, 47) + "…" : label };
  }
  function abPanel() {
    if (!M.ab.view) return "";
    const src = byId(M.ab.view);
    if (!src) return "";
    const vars = abVariants(src.id), wait = Math.max(0, M.ab.expect - vars.length);
    const card = (it, tag, label, diff) => `<figure class="ml-ab-card"><div class="ml-ab-pic"><img src="${e(it.url)}" alt=""><b>${tag}</b></div>
      <figcaption><span class="ml-ab-what">${e(label)}</span>
      ${diff ? `<details><summary>whole prompt, changes marked</summary><p class="ml-ab-diff">${diff}</p></details>` : `<small>Original prompt, seed ${e(it.seed)}</small>`}
      <div class="row">${diff ? `<button type="button" data-mlcmpset="${e(it.id)}" data-f="reviewed" data-v="1"${it.reviewed ? " disabled" : ""}>✓ Keep</button>
        <button type="button" data-mlabuse="${e(it.id)}" title="Open this wording in the generator">✎ Use this wording</button>
        <button type="button" class="danger" data-mlcmpdel="${e(it.id)}">🗑</button>` : `<button type="button" data-mlabuse="${e(it.id)}">✎ Edit</button>`}</div></figcaption></figure>`;
    return `<section class="card ml-ab"><h2>⚖ A/B: ${e(subjectName(src.kind, src.subject))} <small>same seed ${e(src.seed)}, only the wording differs</small></h2>
      <div class="ml-ab-grid">${card(src, "A", "Original")}${vars.map((v, n) => { const d = wordDiff(src.prompt, v.prompt); return card(v, "B" + (n + 1), d.label, d.html); }).join("")}</div>
      ${wait ? `<p class="help">⏳ ${wait} more painting. They appear here as they finish.</p>` : ""}
      <div class="row"><button type="button" class="link" data-mlabclose="1">Close A/B</button></div></section>`;
  }
  function abBox(src) {
    const a = M.ab, made = abVariants(src.id).length;
    return `<details class="ml-abbox"${a.alts || made ? " open" : ""}><summary>⚖ A/B test a phrase <small>same seed ${e(src.seed)}</small></summary>
      <p class="help">Swap one phrase for several alternatives. Every one is painted on this picture's seed, so you see exactly what the words did.</p>
      <label>Swap this phrase <small>(blank = add to the end)</small><input type="text" data-mlabf="find" value="${e(a.find)}" placeholder="golden hour"></label>
      <label>For each of these <small>(one per line, up to 6)</small><textarea rows="4" class="code" data-mlabf="alts" placeholder="blue dusk&#10;heavy fog&#10;harsh noon sun">${e(a.alts)}</textarea></label>
      <div class="row"><button type="button" class="primary" data-mlabgo="${e(src.id)}">⚖ Paint the variants</button>
        ${made ? `<button type="button" data-mlabview="${e(src.id)}">Compare ${made} so far</button>` : ""}</div></details>`;
  }

  function comparePanel() {
    if (!M.cmp) return "";
    const clips = pairOf(M.cmp);
    if (!clips.length) return "";
    const seeds = [...new Set(clips.map(c => c.seed))];
    const cell = c => !c ? `<div class="ml-cmp-cell empty">not made yet</div>` : `<div class="ml-cmp-cell${c.enabled ? "" : " off"}">
        <video src="${e(c.url)}"${posterOf(c) ? ` poster="${e(posterOf(c))}"` : ""} muted loop playsinline preload="auto" data-mlcmpv="1"></video>
        <p><b>${c.nsfw ? "NSFW" : "Clean"}</b> · ${c.seconds || "?"} s${c.loop ? " loop" : ""} · ${fmtBytes(c.bytes || 0)}${c.render_s ? ` · ${Math.round(c.render_s / 60)} min to render` : ""}${!c.reviewed ? ' · <em>needs review</em>' : ""}</p>
        ${c.motion ? `<details><summary>movement</summary><p class="mono ml-prompt">${e(c.motion)}</p></details>` : ""}
        <div class="row"><button type="button" data-mlcmpset="${e(c.id)}" data-f="reviewed" data-v="1"${c.reviewed ? " disabled" : ""}>✓ Keep</button>
          <button type="button" data-mlcmpset="${e(c.id)}" data-f="enabled" data-v="${c.enabled ? "0" : "1"}">${c.enabled ? "Switch off" : "Switch on"}</button>
          <button type="button" class="danger" data-mlcmpdel="${e(c.id)}">🗑</button></div></div>`;
    const first = clips[0];
    return `<section class="card ml-cmp"><h2>Compare: ${e(subjectName(first.kind, first.subject))} <small>${e(first.model || "")}</small></h2>
      <p class="help mono">${e(first.motion || "")}</p>
      <div class="row"><button type="button" class="primary" data-mlcmpplay="1">▶ Play all from the start</button><button type="button" data-mlcmppause="1">❚❚ Pause</button><button type="button" class="link" data-mlcmpclose="1">close</button></div>
      ${seeds.map(sd => `<div class="ml-cmp-row"><span class="ml-cmp-seed">seed ${e(sd)}</span>${cell(clips.find(c => c.seed === sd && c.nsfw))}${cell(clips.find(c => c.seed === sd && !c.nsfw))}</div>`).join("")}
    </section>`;
  }

  /* ---- Find by port & job (Anthony, 22 Nov 2026) ----
     A woman is filed under her own name (Personas) or under her port (Ports > port, role mayor, keeper...), so the
     Kind > Subject rail could never show "the Mayor of Hong Kong" or "the Jailer of Bangkok" in one view.
     portOf() and jobOf() read both places, so Port + Job pull every picture of her together. */
  const portKeys = () => ((M.lib && M.lib.subjects.port) || []).map(x => x[0]);
  const JOBS = [["mayor", "Mayor"], ["jailer", "Jailer / warden"], ["taxlady", "Tax lady / customs"], ["keeper", "Market keeper"], ["shipmaster", "Ship master"],
    ["lender", "Moneylender"], ["banker", "Banker"], ["comprador", "Comprador"], ["shipwright", "Shipwright"], ["crier", "Crier"],
    ["bookmaker", "Bookmaker"], ["agent", "Pirate queen's agent"], ["pirate", "Pirate queen"], ["bosun", "Bosun"], ["narrator", "First mate"],
    ["thieves", "Thieves (Magpie)"], ["legend", "Legends: storytellers, characters, scenes"], ["bookkeeper", "Bookkeeper"], ["gamemaster", "Game Master"]];
  const jobLabel = j => (JOBS.find(x => x[0] === j) || [0, subjectName("persona", j)])[1];
  function portOf(i) {
    if (i.kind === "port") return i.subject;
    if (i.kind !== "persona") return "";
    const m = /_([a-z]+)$/.exec(i.subject || "");
    if (m && portKeys().includes(m[1])) return m[1];
    const c = ((typeof CFG !== "undefined" && CFG.characters) || {})[i.subject];
    return (c && c.home_port) || "";
  }
  function jobOf(i) {
    if (i.kind === "persona") {
      const k = i.subject || "";
      if (/^(teller|legend)_/.test(k)) return ["legend"];
      return [k === "mayor" ? "mayor" : /^warden_/.test(k) ? "jailer" : (k === "taxlady" || k === "customs" || /^officer_/.test(k)) ? "taxlady" : k];
    }
    if (i.kind === "scene") return i.roles.some(r => r === "legend" || r.startsWith("legend_")) ? ["legend"] : [];
    if (i.kind !== "port") return [];
    const out = [];
    i.roles.forEach(r => {
      if (r === "mayor" || r.startsWith("mayor_")) out.push("mayor");
      else if (r === "taxlady" || r.startsWith("taxlady_")) out.push("taxlady");
      else if (r === "keeper" || r === "shipmaster") out.push(r);
      else if (r === "jail_cell") out.push("jailer");
    });
    return out;
  }
  // Every picture role in the game, grouped by kind, for the Role list when no Kind is chosen.
  function allRoles() {
    const out = [];
    KIND_ORDER.forEach(k => {
      const K = kinds()[k]; if (!K || !K.roles || !K.roles.length) return;
      const short = K.roles.map(r => r[1].split(":")[0]);
      out.push([K.label, K.roles.map((r, ix) => [r[0], short.filter(x => x === short[ix]).length > 1 ? r[1].slice(0, 70) : short[ix]])]);
    });
    return out;
  }
  const roleHit = (i, r) => i.roles.some(x => x === r || x.startsWith(r + "_")) || i.tags.some(t => String(t).toLowerCase() === r);
  // Wallpapers, weather pictures and storm pictures belong to a woman's scenery, not to her port. With a Port or Job
  // chosen and no Role picked, they stay out of the way; pick the Role (Wallpaper, Weather, Storm) to see them.
  const SCENERY = ["wallpaper", "weather", "storm"];
  const isScenery = i => i.kind === "persona" && ((i.roles.length && i.roles.every(r => SCENERY.includes(r)))
    || i.tags.some(t => /^(weather|master-shot|wallpaper)/i.test(String(t))));
  // Only a Port on its own hides scenery: a whole port's cast has hundreds of wallpapers and weather pictures. Once
  // a Job is chosen it is one woman's pictures, so all of hers show (Game Master, Mayor of Hong Kong...).
  const hideScenery = i => !!M.port && !M.job && !M.role && isScenery(i);
  const inFind = i => (!M.port || portOf(i) === M.port) && (!M.job || jobOf(i).includes(M.job))
    && !hideScenery(i);

  function filtered() {
    const q = M.q.trim().toLowerCase();
    return items().filter(i => {
      if (!inFind(i)) return false;
      if (M.kind && i.kind !== M.kind) return false;
      if (M.subject && i.subject !== M.subject) return false;
      // A role also takes in its moods and variants (Anthony, 19 Nov 2026): "mayor" picks up mayor_congrats and
      // mayor_<rank>, "taxlady" picks up taxlady_bored, _caught and the rest, and a tag naming the role counts too.
      if (M.role && (i.roles.length || !M.kind) && !roleHit(i, M.role)) return false;
      if (M.type === "pair") { if (i.type !== "video" || !i.pair) return false; }
      else if (M.type === "hasvid") { if (i.type !== "image" || !clipsOf(i.id).length) return false; }
      else if (M.type && i.type !== M.type) return false;
      if (M.nsfw === "sfw" && i.nsfw) return false;
      if (M.nsfw === "nsfw" && !i.nsfw) return false;
      if (M.nsfw === "off" && i.enabled) return false;
      if (M.review && i.reviewed) return false;
      if (M.tag && !i.tags.includes(M.tag)) return false;
      if (M.motion && motionKeyOf(i) !== M.motion) return false;
      if (q && ![i.title, i.subject, i.url, i.tags.join(" "), i.prompt, i.motion || "", i.model || ""].join(" ").toLowerCase().includes(q)) return false;
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
    M.queue = res.queue || M.queue;
    if (res.recipes) M.recipes = res.recipes;
    [...M.sel].forEach(id => { if (!byId(id)) M.sel.delete(id); });
    if (!M.rulesDraft) M.rulesDraft = { rules: clone(res.rules), options: clone(res.options) };
    // A background refresh must not steal focus while you type in the drawer or search box.
    const ae = document.activeElement;
    if (quiet && ae && ae.closest && ae.closest(".ml-drawer, .ml-top") && /^(INPUT|TEXTAREA|SELECT)$/.test(ae.tagName)) { watchJobs(); return; }
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
      ? `<video class="${cls}" src="${e(i.url)}#t=0.5"${posterOf(i) ? ` poster="${e(posterOf(i))}"` : ""} muted loop playsinline preload="metadata"></video>`
      : `<img class="${cls}" src="${e(i.url)}" alt="" loading="lazy">`;
  }

  function familySwitch() {
    const fam = CFG.content.rating === "family";
    return `<button type="button" class="ml-safe${fam ? " on" : ""}" data-mlsafe="${fam ? "0" : "1"}" title="Switch the whole game between the private adult release and family-friendly">
      <span class="ml-safe-knob"></span><span><b>${fam ? "Family-friendly ON" : "Family-friendly OFF"}</b>
      <small>${fam ? "NSFW is hidden on every screen" : "NSFW pictures and clips can show"}</small></span></button>`;
  }


  // Anthony, 20 Nov 2026: quick Regen (same prompt + seed) and Reroll (same prompt, new seed), beside Trash and Approve.
  // tag is "button" on grid tiles and "span" inside subject cards (those are buttons already).
  function quickRedo(i, tag) {
    if (!i || i.type === "video" || !i.prompt || i.prompt.length < 20) return "";
    const attr = tag === "span" ? ' role="button" tabindex="0"' : ' type="button"';
    const noSeed = i.seed == null;
    return `<${tag}${attr} class="ml-quickredo${noSeed ? " none" : ""}" data-mlquickredo="${e(i.id)}" data-mode="same"
        title="${noSeed ? "Regen needs a saved seed (this picture has none). Use Reroll." : "Regen this: same prompt, same seed " + e(i.seed)}" aria-label="Regen this picture">↻</${tag}>` +
      `<${tag}${attr} class="ml-quickredo" data-mlquickredo="${e(i.id)}" data-mode="new" title="Reroll this: same prompt, new seed" aria-label="Reroll this picture">🎲</${tag}>`;
  }

  /* ---- Gallery 2: filter rail, view toggle, chips ---- */
  const scopeItems = () => items().filter(i => inFind(i) && (!M.kind || i.kind === M.kind) && (!M.subject || i.subject === M.subject));
  const RATINGS = [["", "All"], ["sfw", "Family-friendly"], ["nsfw", "NSFW"], ["off", "Switched off"]];

  function findBox() {
    const all = items();
    const portN = {};
    all.forEach(i => { const p = portOf(i); if (p && (!M.job || jobOf(i).includes(M.job)) && !(!M.job && !M.role && isScenery(i))) portN[p] = (portN[p] || 0) + 1; });
    const jobN = {};
    all.filter(i => !M.port || portOf(i) === M.port).forEach(i => jobOf(i).forEach(j => { if (j) jobN[j] = (jobN[j] || 0) + 1; }));
    const known = JOBS.map(x => x[0]);
    const jobs = known.concat(Object.keys(jobN).filter(j => !known.includes(j)).sort()).filter(j => jobN[j] || j === M.job);
    const ports = ((M.lib && M.lib.subjects.port) || []).filter(([k]) => portN[k] || k === M.port);
    return `<div class="ml-rail-sec ml-find"><h3>Find by port &amp; job</h3>
      <label>Port<select data-mlfind="port"><option value="">Any port</option>${ports.map(([k, n]) => `<option value="${e(k)}"${k === M.port ? " selected" : ""}>${e(n)} (${portN[k] || 0})</option>`).join("")}</select></label>
      <label>Job<select data-mlfind="job"><option value="">Any job</option>${jobs.map(j => `<option value="${e(j)}"${j === M.job ? " selected" : ""}>${e(jobLabel(j))} (${jobN[j] || 0})</option>`).join("")}</select></label>
      <p class="help">Pulls her pictures from Personas <em>and</em> Ports together, in any kind. With a Port alone, wallpapers, weather and storm pictures stay hidden until you pick that Role below; pick a Job and all of her pictures show.</p></div>`;
  }

  function rail() {
    const all = items();
    const kindBtns = KIND_ORDER.filter(k => kinds()[k]).map(k =>
      `<button type="button" data-mlkind="${k}" class="${M.kind === k ? "on" : ""}"><span>${e(kinds()[k].label)}</span><i>${all.filter(i => i.kind === k).length}</i></button>`).join("");
    const subs = M.kind ? subjectsFor(M.kind) : [];
    const subBtns = subs.map(([k, n]) => `<button type="button" data-mlsubject="${M.subject === k ? "" : e(k)}" class="${M.subject === k ? "on" : ""}"><span>${e(n)}</span><i>${all.filter(i => i.kind === M.kind && i.subject === k).length}</i></button>`).join("");
    const K = kinds()[M.kind];
    const roles = K ? K.roles : [];
    const sc = scopeItems();
    const nReview = sc.filter(i => !i.reviewed).length, nClips = sc.filter(i => i.type === "image" && clipsOf(i.id).length).length;
    const tagCount = {};
    sc.forEach(i => i.tags.forEach(t => { if (t && !String(t).startsWith("motion-")) tagCount[t] = (tagCount[t] || 0) + 1; }));
    const mcount = {};
    sc.forEach(i => { const k = motionKeyOf(i); if (k) mcount[k] = (mcount[k] || 0) + 1; });
    const mkeys = Object.keys(MOTIONS).concat(Object.keys(mcount).filter(k => !MOTIONS[k])).filter(k => mcount[k] || k === M.motion);
    const tags = Object.entries(tagCount).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).slice(0, 18);
    return `<aside class="ml-rail" aria-label="Filters">
      <div class="ml-rail-sec"><h3>Quick views</h3><div class="ml-presets">
        <button type="button" data-mlpreset="review">Needs review</button><button type="button" data-mlpreset="vidreview">Videos to review</button>
        <button type="button" data-mlpreset="clips">Pictures with clips</button><button type="button" data-mlpreset="nsfw">NSFW</button><button type="button" data-mlpreset="off">Switched off</button>
        <button type="button" data-mlcovtoggle="1" class="${M.cov ? "on" : ""}">Coverage &amp; gaps</button>
        <button type="button" data-mlrecopen="1" class="${M.rec.open ? "on" : ""}">Recipes</button>
        <button type="button" data-mlpreset="clear" class="link">Clear all</button></div></div>
      ${findBox()}
      <div class="ml-rail-sec"><h3>Kind</h3><div class="ml-list">${kindBtns}<button type="button" data-mlkind="" class="${M.kind === "" ? "on" : ""}"><span>Everything</span><i>${all.length}</i></button></div></div>
      ${subs.length ? `<div class="ml-rail-sec"><h3>${e(K.one)}</h3><div class="ml-list ml-scroll">${subBtns}</div></div>` : ""}
      <div class="ml-rail-sec"><h3>Role</h3><select data-mlf="role"><option value="">Any</option>${K ? roles.map(([k, n]) => `<option value="${e(k)}"${k === M.role ? " selected" : ""}>${e(n.split(":")[0])}</option>`).join("") : allRoles().map(([g, rs]) => `<optgroup label="${e(g)}">${rs.map(([k, n]) => `<option value="${e(k)}"${k === M.role ? " selected" : ""}>${e(n)}</option>`).join("")}</optgroup>`).join("")}</select></div>
      <div class="ml-rail-sec"><h3>Rating</h3><div class="ml-seg ml-seg-v">${RATINGS.map(([k, n]) => `<button type="button" data-mlrating="${k}" class="${M.nsfw === k ? "on" : ""}">${n}</button>`).join("")}</div></div>
      <div class="ml-rail-sec"><h3>Status</h3><div class="ml-list">
        <button type="button" data-mlreview="1" class="${M.review ? "on" : ""}"><span>Needs review</span><i>${nReview}</i></button>
        <button type="button" data-mlstatus="hasvid" class="${M.type === "hasvid" ? "on" : ""}"><span>Has clips</span><i>${nClips}</i></button></div></div>
      ${mkeys.length ? `<div class="ml-rail-sec"><h3>Movement</h3><div class="ml-list ml-scroll">${mkeys.map(k => `<button type="button" data-mlmotion="${M.motion === k ? "" : e(k)}" class="${M.motion === k ? "on" : ""}"><span>${e(motionLabel(k))}${MOTIONS[k] && MOTIONS[k][2] === "nsfw" ? ' <em class="nsfw">NSFW</em>' : ""}</span><i>${mcount[k] || 0}</i></button>`).join("")}</div></div>` : ""}
      ${tags.length ? `<div class="ml-rail-sec"><h3>Tags</h3><div class="ml-tagcloud">${tags.map(([t, n]) => `<button type="button" data-mltag="${e(M.tag === t ? "" : t)}" class="${M.tag === t ? "on" : ""}">${e(t)} <i>${n}</i></button>`).join("")}</div></div>` : ""}
    </aside>`;
  }

  function viewToggle() {
    const sc = scopeItems();
    const n = { "": sc.length, image: sc.filter(i => i.type === "image").length, video: sc.filter(i => i.type === "video").length, pair: sc.filter(i => i.type === "video" && i.pair).length };
    const cur = ["", "image", "video", "pair"].includes(M.type) ? M.type : "";
    return `<div class="ml-seg ml-view">${[["", "All"], ["image", "Pictures"], ["video", "Videos"], ["pair", "Pairs"]].map(([k, t]) =>
      `<button type="button" data-mlview="${k}" class="${cur === k ? "on" : ""}">${t} <i>${n[k]}</i></button>`).join("")}</div>`;
  }

  function chips() {
    const out = [];
    const add = (f, label) => out.push(`<button type="button" class="ml-chip" data-mlchipx="${f}" title="Remove this filter">${e(label)} <b>×</b></button>`);
    if (M.port) add("port", "Port: " + subjectName("port", M.port));
    if (M.job) add("job", "Job: " + jobLabel(M.job));
    if (M.kind) add("kind", kinds()[M.kind].label);
    if (M.subject) add("subject", subjectName(M.kind, M.subject));
    if (M.role) add("role", "Role: " + (M.kind ? roleName(M.kind, M.role) : (allRoles().flatMap(g => g[1]).find(r => r[0] === M.role) || [0, M.role])[1]));
    if (M.type === "hasvid") add("type", "Has clips");
    if (M.nsfw) add("nsfw", (RATINGS.find(r => r[0] === M.nsfw) || [0, M.nsfw])[1]);
    if (M.review) add("review", "Needs review");
    if (M.tag) add("tag", "#" + M.tag);
    if (M.motion) add("motion", "Movement: " + motionLabel(M.motion));
    if (M.q.trim()) add("q", "“" + M.q.trim() + "”");
    return out.length ? `<div class="ml-chips">${out.join("")}<button type="button" class="link" data-mlpreset="clear">clear all</button></div>` : "";
  }

  function toolbar() {
    return `<div class="ml-tools ml-top">
      <button type="button" data-mlrailtoggle="1" class="${M.railOpen ? "on" : ""}" title="Show or hide the filter rail">☰ Filters</button>
      ${viewToggle()}
      <input type="search" id="mlq" class="ml-search" data-mlf="q" value="${e(M.q)}" placeholder="Search tag, title, prompt, movement…">
      <label class="ml-mini">Sort<select data-mlf="sort">${SORT_NAMES.map(([k, n]) => `<option value="${k}"${k === M.sort ? " selected" : ""}>${n}</option>`).join("")}</select></label>
      <div class="ml-seg ml-dens" title="Tile size">${[["s", "S"], ["m", "M"], ["l", "L"]].map(([k, t]) => `<button type="button" data-mldens="${k}" class="${M.density === k ? "on" : ""}">${t}</button>`).join("")}</div>
      <div class="ml-actions">
        <button type="button" class="primary" data-mlnew="1">+ New</button>
        <label class="ml-check" title="Tag what you upload next as NSFW"><input type="checkbox" data-mlf="upNsfw"${M.upNsfw ? " checked" : ""}> NSFW</label>
        <label class="pick ml-up">Upload…<input type="file" multiple accept="image/png,image/jpeg,image/webp,image/gif,image/svg+xml,video/mp4,video/webm,video/quicktime,.m4v" data-mlupload="1"></label>
        <button type="button" data-mlscan="1" title="Pick up files dropped into web/media/&lt;kind&gt;/&lt;subject&gt;/ (a folder named nsfw tags them)">Scan</button>
        <button type="button" data-mlrules="1" class="${M.rulesOpen ? "on" : ""}">Rules</button>
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
    if (kind === "port" && role === "mayor_congrats") {
      const w = portWoman(subject, "mayor");
      return `Waist-up portrait of a breathtakingly beautiful, sultry ${w.who}, a former pirate queen who is now the lady mayor of ${name} in 1860, standing in her harbour-office parlour and congratulating the viewer on a hard-won promotion: both arms opened wide toward the camera in warm, generous gratitude and welcome, palms turned up, a radiant proud smile, eyes shining, direct eye contact, ${w.hair}, ${w.dress}, worn open at the throat and shoulders, a gold mayor's chain of office across her bare décolletage, a sealed ivory letter of commission with a red wax seal on the teak desk behind her, a brass strongbox, a harbour window with masts beyond, warm candle and lantern glow, her head, both outstretched hands and her waist all inside the frame with room around them, shallow depth of field, sensual private-release erotic glamour, ${style}`;
    }
    if (kind === "port" && role && role.startsWith("mayor_")) {
      const rank = role.slice(6), title = (CFG.ranks.find(r => r.id === rank) || {}).title || rank;
      const audience = ((M.lib.promotion_styles || {})[rank] || {}).audience || "a formal harbour-office commission";
      const w = portWoman(subject, "mayor");
      return `Bespoke ceremonial portrait of the lady mayor of ${name}, for the ${title} promotion certificate. Keep the same recognizable adult mayor as her other portraits: ${w.who}, ${w.hair}, her own civic gold chain. ${audience}. Proud warm acknowledgement, direct eye contact, waist-up composition with her face in the upper third, fully dressed, a period ivory commission on a teak desk, richly textured believable materials, no modern objects, no text, no frame, ${style}`;
    }
    if (kind === "scene" && BATTLE_ENEMY[subject]) return battlePrompt(subject, role, style);
    if (kind === "port" && role === "keeper") { const w = portWoman(subject, role); return `Waist-up portrait of a breathtakingly beautiful, sultry ${w.who}, who runs a trading stall in the ${name} market in 1860, looking straight into the camera with a slow, knowing, inviting half-smile and heavy-lidded bedroom eyes, ${w.hair}, ${w.dress}, bare skin glowing with humid heat, brass scales, tea chests, silk bolts and porcelain behind her, warm lantern glow and soft humid haze, shallow depth of field, she is the centre of the frame, sensual private-release erotic glamour, ${style}`; }
    if (kind === "port" && role === "shipmaster") { const w = portWoman(subject, role); return `Waist-up portrait of a breathtakingly beautiful, sultry, dangerous ${w.who}, the ship master who rules the ${name} shipyard in 1860, giving the viewer a cold, wicked evil eye: narrowed kohl-lined eyes, one brow raised, chin slightly lowered, a cruel knowing half-smile, direct eye contact, ${w.hair}, ${w.dress}, a brass spyglass in one gloved hand, sweat-sheened skin, a ship's hull on the slipway, rigging and coiled rope behind her, lantern glow and harbour haze, shallow depth of field, she is the centre of the frame, sensual private-release erotic glamour, ${style}`; }
    if (kind === "port" && role === "mayor") { const w = portWoman(subject, role); return `Waist-up portrait of a breathtakingly beautiful, sultry ${w.who}, a former pirate queen who is now the lady mayor of ${name} in 1860 and keeps the town's ledger and collects its taxes, seated at a heavy teak desk and looking straight into the camera with a sly, appraising, seductive half-smile, as if she already knows what you owe her and how you will pay, direct eye contact, ${w.hair}, ${w.dress}, worn open at the throat and shoulders, a gold mayor's chain of office across her bare décolletage, a quill in one ringed hand, an open leather-bound ledger, a brass strongbox spilling silver dollars, tax seals and a cutlass hung on the wall behind her, warm candle and lantern glow, harbour window haze, shallow depth of field, she is the centre of the frame, sensual private-release erotic glamour, ${style}`; }
    if (kind === "port" && role === "taxlady") { const w = portWoman(subject, role); return `Waist-up portrait of a breathtakingly beautiful, sultry ${w.who}, the tax collector who works the ${name} waterfront in 1860 and takes the town's cut of every cargo, standing at the foot of the gangway with an open tally book and a brass-bound strongbox, looking straight into the camera with a sweet, merciless, teasing smile and one raised eyebrow, direct eye contact, ${w.hair}, ${w.dress}, a jade customs seal on a cord resting against her bare skin, a brass stamp and a pen in her gloved hands, sacks of silver dollars, stamped cargo chests, a ship's hull and rigging behind her, warm lantern glow and harbour haze, shallow depth of field, she is the centre of the frame, sensual private-release erotic glamour, ${style}`; }
    if (kind === "port") return `The port of ${name} in the 1860s seen from the water, busy trading harbour with junks, lorchas and clipper ships at anchor, waterfront godowns and hongs, ${style}`;
    if (kind === "ship") return shipPrompt(subject, role, style);
    // A family picture is of the cargo's family-friendly name (Opium -> Fireworks), not the cargo itself.
    if (kind === "cargo" && role === "family") {
      const fam = ((CFG.goods || {})[subject] || {}).family_name || name;
      return `Still life of ${fam} as 1860s trade cargo, crates, chests and bales on a teak deck, square composition, no person, family-friendly, ${style}`;
    }
    if (kind === "cargo") return `Still life of ${name} as 1860s trade cargo, crates, chests and bales on a teak deck, square composition, no person, ${style}`;
    if (kind === "service") return `The interior of the ${name} at a Hong Kong trading harbor in the 1860s, wide environmental shot, period details, no text or people, ${style}`;
    if (kind === "scene") return `${name} on the China Seas in 1860, a trading fleet caught in the moment, ${style}`;
    return `${name}, ${style}`;
  }

  /* ---- Coverage grid + clean-twin check (Anthony, 21 Nov 2026) ---- */
  const isClean = i => !i.nsfw || i.tags.includes("clean");
  // Starting prompt and shape for one subject + role (the same ones ticking that role in the drawer would give).
  function roleStart(kind, subject, role) {
    let prompt = defaultPrompt(kind, subject, role || undefined), aspect = ASPECT_FOR[kind] || "3:4";
    if (kind === "persona" && role && PERSONA_MOODS[role]) prompt = personaPrompt(subject, role);
    if (kind === "port" && role && (["keeper", "shipmaster", "mayor", "taxlady"].includes(role) || role.startsWith("mayor_"))) aspect = "3:4";
    if (kind === "ship" && role) aspect = role === "card" ? "3:2" : "16:9";
    if (kind === "scene" && BATTLE_ENEMY[subject] && role) aspect = "16:9";
    return { prompt, aspect };
  }
  function coverage() {
    const kind = M.kind, K = kinds()[kind];
    let grid;
    if (!K) grid = `<p class="help">Pick a kind in the rail (Personas, Ports, Scenes…) to see its subject × role grid.</p>`;
    else {
      const subs = subjectsFor(kind), roles = K.roles;
      const pics = items().filter(i => i.kind === kind && i.type === "image" && !i.missing);
      const cell = (s, r, list) => {
        const n = list.length, c = list.filter(isClean).length;
        const cls = n === 0 ? "c0" : c === 0 ? "cnsfw" : n < 2 ? "c1" : "c2";
        return `<td><button type="button" class="ml-cov ${cls}" data-mlcov="${e(s)}|${e(r)}" title="${n} picture${n === 1 ? "" : "s"}, ${c} family-friendly. Click to generate one${r ? " for this role" : ""}.">${n}<small>${c} clean</small></button></td>`;
      };
      grid = `<div class="ml-covwrap"><table class="ml-covtable"><thead><tr><th></th><th>Any role</th>${roles.map(([k, n]) => `<th title="${e(n)}">${e(n.replace(/^[^:]*:\s*/, "").slice(0, 40) || n)}</th>`).join("")}<th>Total</th></tr></thead><tbody>
        ${subs.map(([s, name]) => { const mine = pics.filter(i => i.subject === s);
          return `<tr><th><button type="button" class="link" data-mlsubject="${e(s)}" data-mlcovoff="1">${e(name)}</button></th>${cell(s, "", mine.filter(i => !i.roles.length))}${roles.map(([k]) => cell(s, k, mine.filter(i => i.roles.includes(k)))).join("")}<td class="ml-covtot">${mine.length}</td></tr>`; }).join("")}
        </tbody></table></div>
        <p class="help"><span class="ml-covkey c0"></span> none <span class="ml-covkey cnsfw"></span> only NSFW (vanishes when family-friendly is on) <span class="ml-covkey c1"></span> one <span class="ml-covkey c2"></span> two or more. Click any cell to open the drawer with that role's prompt.</p>`;
    }
    // Subjects with NSFW pictures but no family-friendly one: invisible to player screens while family-friendly is on.
    const groups = {};
    items().filter(i => i.type === "image" && !i.missing).forEach(i => { const k = i.kind + ":" + i.subject; (groups[k] = groups[k] || []).push(i); });
    const gaps = Object.values(groups).filter(g => g[0].subject && g.some(i => i.nsfw) && !g.some(isClean))
      .sort((a, b) => b.length - a.length).slice(0, 40);
    const twins = gaps.length ? `<h3>No family-friendly picture yet <small>${gaps.length}${gaps.length === 40 ? "+" : ""} subject${gaps.length === 1 ? "" : "s"}</small></h3>
      <div class="ml-twins">${gaps.map(g => { const n = g.filter(i => i.nsfw).sort(byAdded)[0], src = g.filter(i => i.prompt).sort(byAdded)[0];
        return `<div class="ml-twin"><img src="${e(n.url)}" alt="" loading="lazy"><span><b>${e(subjectName(n.kind, n.subject))}</b><small>${e((kinds()[n.kind] || {}).one || n.kind)} · ${g.length} NSFW</small></span>
          ${src ? `<button type="button" data-mltwin="${e(src.id)}">Make clean twin</button>` : `<small>no saved prompt</small>`}</div>`; }).join("")}</div>`
      : `<p class="help">Every subject with an NSFW picture also has a family-friendly one.</p>`;
    return `<section class="card ml-coverage"><h2>Coverage <small>${K ? e(K.label) : "pick a kind"}</small> ${K ? `<button type="button" data-mlcovrec="1" title="Open a recipe that fills this grid up to a target">Fill gaps with a recipe…</button>` : ""}</h2>${grid}${twins}</section>`;
  }

  /* ---- Recipes: saved "fill to target" batches (Anthony, 21 Nov 2026) ---- */
  const NUDE = "completely nude, her clothes fallen away, bare breasts and body shown openly, only her jewellery and the props of her trade left on her";
  const CLEAN_STYLE = "fully and modestly clothed, high neckline, no nudity, no cleavage, romanticized cinematic historical realism, China Seas 1860, humid salt haze, natural skin, weathered maritime materials, lacquer black, oxblood silk, antique brass, imperial jade, waist-up 3:4 portrait, hands visible, original face and garment design, no text";
  // Undressed wording in the profile prompts, made decent for the clean version (same list as tools/queue_persona_pairs.py).
  const DECENT = [
    [/worn loose off both shoulders with the obi half undone/g, "neatly worn and tied"], [/off-shoulder /g, ""], [/slipping from one shoulder/g, "worn neatly"],
    [/draped over one bare shoulder/g, "draped neatly"], [/half-laced /g, ""], [/loosened /g, ""],
    [/with a thigh-high slit unbuttoned at the collar/g, "buttoned to the collar"], [/open over a black lace corset/g, "buttoned over a black lace blouse"],
    [/open over a black silk corset, high collar undone/g, "with the high collar buttoned"], [/with a laced leather corset over it/g, ""],
    [/plunging /g, "high-necked "], [/with a deep neckline/g, ""], [/\bundone\b/g, "fastened"], [/across her skin/g, "across the room"], [/bedroom gaze/g, "gaze"],
    [/sensual private-release erotic glamour,? ?/g, ""],
    [/black silk blouse unbuttoned to the waist and slipping off one shoulder over an oxblood lace corset/g, "black silk blouse buttoned to the collar under an oxblood waistcoat"],
    [/sheer black stockings and one knee drawn up, /g, ""], [/reclining in/g, "seated in"], [/a smouldering heavy-lidded gaze/g, "a knowing gaze"], [/ deliciously/g, ""],
  ];
  const POSES = ["a three-quarter view glancing back over one shoulder", "leaning a hip against a table, hands visible", "seated and leaning forward with her elbows on the table",
    "a closer framing on her face and shoulders", "standing tall, chin lifted, hands clasped in front", "caught turning toward the camera mid-step",
    "one hand on her hip, head tilted, a knowing look", "a low camera angle looking slightly up at her"];
  const CAMERAS = ["a different camera angle from a higher viewpoint", "a closer, tighter framing", "a wider view showing more of the scene", "a low, dramatic camera angle"];
  // A copied prompt may already end with a pose from an earlier run: strip those so poses never pile up.
  function stripPose(p) {
    p = String(p || "");
    for (let again = true; again;) { again = false; for (const x of POSES.concat(CAMERAS)) if (p.endsWith(", " + x)) { p = p.slice(0, -(x.length + 2)); again = true; } }
    return p;
  }
  const stylePart = p => { const at = p.indexOf(", romanticized"); return at > 0 ? [p.slice(0, at), p.slice(at + 2)] : [p, ""]; };
  const nsfwText = (base, mood) => { const [d, t] = stylePart(base); return `${d}${mood ? ", " + mood : ""}, ${NUDE}${t ? ", " + t : ""}`; };
  function cleanText(base, mood) {
    let [d] = stylePart(base);
    DECENT.forEach(([re, rep]) => { d = d.replace(re, rep); });
    d = d.replace(/ {2,}/g, " ").replace(/\s+,/g, ",");
    return `${d}${mood ? ", " + mood : ""}, ${CLEAN_STYLE}`;
  }
  const slug = t => String(t || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 30);
  const newRecipe = () => ({ id: "r" + Math.random().toString(36).slice(2, 9), name: "New recipe", kind: M.kind || "persona", subjects: [], roles: [], by: "subject", mode: "pairs",
    clean: 1, nsfw: 5, count: 3, mood: "", pose: true, tag: "", last_run: "", last_made: 0 });
  const womanRole = r => !!r && (["keeper", "shipmaster", "mayor", "taxlady"].includes(r) || r.startsWith("mayor_"));

  function recTargets(r) {
    const K = kinds()[r.kind]; if (!K) return [];
    const subs = r.subjects.length ? r.subjects : subjectsFor(r.kind).map(x => x[0]);
    const roles = r.by === "role" ? (r.roles.length ? r.roles : K.roles.map(x => x[0])) : [""];
    const out = [];
    subs.forEach(s => roles.forEach(role => out.push({ s, role })));
    return out;
  }
  const recRoleOk = (r, t, roles) => t.role ? roles.includes(t.role) : (r.roles.length ? roles.some(x => r.roles.includes(x)) : true);
  function recPics(r, t) {
    return items().filter(i => i.type === "image" && !i.missing && i.kind === r.kind && i.subject === t.s && recRoleOk(r, t, i.roles));
  }
  const ACTIVE = ["waiting", "running", "cancelling"];
  function recPlan(r) {
    return recTargets(r).map(t => {
      const have = recPics(r, t).filter(i => i.enabled);
      let pendC = 0, pendN = 0;
      M.jobs.filter(j => j.type !== "video" && ACTIVE.includes(j.status) && j.kind === r.kind && j.subject === t.s && recRoleOk(r, t, j.roles || []))
        .forEach(j => { const left = Math.max(0, (j.count || 0) - (j.done || 0) - (j.failed || 0)); if (j.nsfw === "no") pendC += left; else pendN += left; });
      const haveC = have.filter(isClean).length, haveN = have.length - haveC;
      let needC, needN;
      if (r.mode === "plain") { needC = 0; needN = Math.max(0, r.count - have.length - pendC - pendN); }
      else { needC = Math.max(0, r.clean - haveC - pendC); needN = Math.max(0, r.nsfw - haveN - pendN); }
      const K = kinds()[r.kind] || {};
      const label = subjectName(r.kind, t.s) + (t.role ? " · " + roleName(r.kind, t.role) : "");
      return { t, label, haveC, haveN, pendC, pendN, needC, needN, plain: r.mode === "plain" };
    });
  }
  // The prompts for one target: personas use their own cast prompt (pair rule), everything else copies its own pictures.
  function recPrompts(r, t) {
    const pics = recPics(r, t).filter(i => i.prompt && i.prompt.length >= 20).sort(byAdded);
    const loose = pics.length ? pics : items().filter(i => i.type === "image" && !i.missing && i.kind === r.kind && i.subject === t.s && i.prompt && i.prompt.length >= 20).sort(byAdded);
    const persona = r.kind === "persona" && CFG.characters[t.s] && CFG.characters[t.s].portrait_prompt;
    const rs = roleStart(r.kind, t.s, t.role);
    let mood = r.mood;
    if (persona && !mood && t.role && PERSONA_MOODS[t.role]) mood = PERSONA_MOODS[t.role];
    let nsfwP, cleanP, plainP;
    if (persona) { nsfwP = nsfwText(persona, mood); cleanP = cleanText(persona, mood); plainP = persona + (mood ? ", " + mood : ""); }
    else {
      const nPic = loose.find(i => i.nsfw) || loose[0], cPic = loose.find(isClean);
      const nBase = stripPose((nPic && nPic.prompt) || rs.prompt);
      nsfwP = nBase + (r.mood ? ", " + r.mood : "");
      cleanP = cPic ? stripPose(cPic.prompt) + (r.mood ? ", " + r.mood : "") : cleanText(nBase, r.mood);
      plainP = stripPose((loose[0] && loose[0].prompt) || rs.prompt) + (r.mood ? ", " + r.mood : "");
    }
    const sample = loose[0];
    const aspect = persona ? "3:4" : (t.role ? rs.aspect : (sample ? shapeOf(sample) : rs.aspect));
    const person = r.kind === "persona" || r.kind === "captain" || womanRole(t.role);
    return { nsfwP, cleanP, plainP, aspect, person };
  }

  function recipesPanel() {
    const R = M.rec; if (!R.open) return "";
    const d = R.draft;
    const list = M.recipes.map(x => `<button type="button" data-mlrec="pick" data-id="${e(x.id)}" class="${d && d.id === x.id ? "on" : ""}"><b>${e(x.name)}</b><small>${e((kinds()[x.kind] || {}).label || x.kind)} · ${x.mode === "plain" ? x.count + " each" : x.clean + " clean + " + x.nsfw + " NSFW"}${x.last_run ? " · ran " + e(x.last_run) : ""}</small></button>`).join("");
    let form = `<p class="help">Pick a recipe, or start a new one. A recipe counts what is already filed or waiting on the farm and paints only what is short.</p>`, prev = "";
    if (d) {
      const K = kinds()[d.kind] || { roles: [], one: "Subject", label: d.kind };
      const subs = subjectsFor(d.kind);
      const ports = d.kind === "persona" ? [...new Set(Object.values(CFG.characters).map(c => c.home_port).filter(Boolean))] : [];
      const saved = M.recipes.some(x => x.id === d.id);
      const plan = recPlan(d);
      const needC = plan.reduce((a, p) => a + p.needC, 0), needN = plan.reduce((a, p) => a + p.needN, 0), total = needC + needN;
      form = `<div class="ml-rec-grid">
        <label class="wide">Name<input type="text" value="${e(d.name)}" data-mlrecf="name"></label>
        <label>What<select data-mlrecf="kind">${KIND_ORDER.filter(k => kinds()[k]).map(k => `<option value="${k}"${k === d.kind ? " selected" : ""}>${e(kinds()[k].label)}</option>`).join("")}</select></label>
        <label>Count<select data-mlrecf="by"><option value="subject"${d.by === "subject" ? " selected" : ""}>per ${e((K.one || "subject").toLowerCase())}</option><option value="role"${d.by === "role" ? " selected" : ""}>per ${e((K.one || "subject").toLowerCase())} and role</option></select></label>
        <label>Kind of picture<select data-mlrecf="mode"><option value="pairs"${d.mode === "pairs" ? " selected" : ""}>Pairs: NSFW + clean</option><option value="plain"${d.mode === "plain" ? " selected" : ""}>Plain pictures (no rating split)</option></select></label>
      </div>
      <div class="ml-rec-pick"><div class="ml-rec-pickhead"><b>${e(K.one || "Subjects")}s</b> <small>${d.subjects.length ? d.subjects.length + " chosen" : "all " + subs.length}</small>
        <button type="button" class="link" data-mlrec="allsubs">all</button><button type="button" class="link" data-mlrec="nosubs">none</button>
        ${ports.length ? `<select data-mlrecport="1"><option value="">By home port…</option>${ports.map(p => `<option value="${e(p)}">${e(subjectName("port", p))}</option>`).join("")}</select>` : ""}</div>
        <div class="ml-rec-checks">${subs.map(([k, n]) => `<label class="ml-check"><input type="checkbox" data-mlrecsub="${e(k)}"${d.subjects.includes(k) ? " checked" : ""}> ${e(n)}</label>`).join("")}</div></div>
      ${K.roles.length ? `<div class="ml-rec-pick"><div class="ml-rec-pickhead"><b>Roles</b> <small>${d.roles.length ? d.roles.length + " chosen" : "any role"}</small>
        <button type="button" class="link" data-mlrec="allroles">all</button><button type="button" class="link" data-mlrec="noroles">none</button></div>
        <div class="ml-rec-checks">${K.roles.map(([k, n]) => `<label class="ml-check" title="${e(n)}"><input type="checkbox" data-mlrecrole="${k}"${d.roles.includes(k) ? " checked" : ""}> ${e(n.split(":")[0])}</label>`).join("")}</div></div>` : ""}
      <div class="ml-rec-sliders">
        ${d.mode === "plain"
          ? `<label>Pictures each <b id="mlrecv-count">${d.count}</b><input type="range" min="0" max="20" value="${d.count}" data-mlrecf="count"></label>`
          : `<label>Clean each <b id="mlrecv-clean">${d.clean}</b><input type="range" min="0" max="10" value="${d.clean}" data-mlrecf="clean"></label>
             <label>NSFW each <b id="mlrecv-nsfw">${d.nsfw}</b><input type="range" min="0" max="20" value="${d.nsfw}" data-mlrecf="nsfw"></label>`}</div>
      <div class="ml-rec-grid">
        <label class="wide">Mood or extra wording <small>(optional, added to every prompt)</small><input type="text" value="${e(d.mood)}" data-mlrecf="mood" placeholder="e.g. hungry, a hungry predatory smile"></label>
        <label>Tag new pictures<input type="text" value="${e(d.tag)}" data-mlrecf="tag" placeholder="${e(slug(d.name) || "recipe")}"></label>
        <label class="ml-check"><input type="checkbox" data-mlrecf="pose"${d.pose ? " checked" : ""}> Vary the pose or camera for each picture</label>
      </div>
      <div class="row"><button type="button" class="primary" data-mlrec="save">${saved ? "Save" : "Save recipe"}</button>
        <button type="button" data-mlrec="dup">Save as copy</button>${saved ? `<button type="button" class="danger" data-mlrec="del">Delete</button>` : ""}</div>`;
      const rows = plan.filter(p => p.needC || p.needN || p.pendC || p.pendN).slice(0, 80);
      const first = plan.filter(p => p.needC || p.needN).slice(0, 4).map(p => { const pr = recPrompts(d, p.t);
        return `<details class="ml-rec-pr"><summary>${e(p.label)}</summary>${p.plain ? `<p class="mono">${e(pr.plainP)}</p>` : `${p.needN ? `<p class="mono"><b>NSFW:</b> ${e(pr.nsfwP)}</p>` : ""}${p.needC ? `<p class="mono"><b>Clean:</b> ${e(pr.cleanP)}</p>` : ""}`}</details>`; }).join("");
      prev = `<h3>Preview <small>${plan.length} target${plan.length === 1 ? "" : "s"} · ${total ? `<b>${total}</b> picture${total === 1 ? "" : "s"} short (${needC} clean, ${needN} ${d.mode === "plain" ? "plain" : "NSFW"})` : "nothing short"}</small></h3>
        ${rows.length ? `<div class="ml-covwrap ml-rec-table"><table class="ml-covtable"><thead><tr><th></th><th>Have</th><th>Waiting</th><th>Short</th></tr></thead><tbody>${rows.map(p => `<tr><th>${e(p.label)}</th>
          <td>${p.plain ? p.haveC + p.haveN : `${p.haveC} clean · ${p.haveN} NSFW`}</td><td>${p.pendC + p.pendN || "–"}</td><td class="${p.needC || p.needN ? "ml-short" : ""}">${p.plain ? p.needN : `${p.needC} clean · ${p.needN} NSFW`}</td></tr>`).join("")}</tbody></table></div>` : `<p class="help">Everything is at or above target (counting pictures waiting on the farm).</p>`}
        ${first ? `<p class="help">Prompts for the first few:</p>${first}` : ""}
        <div class="row"><button type="button" class="primary" data-mlrec="run"${total && !R.busy ? "" : " disabled"}>${R.busy ? e(R.prog || "Queueing…") : `Queue ${total} picture${total === 1 ? "" : "s"}`}</button>
          <span class="help">Only the shortfall is queued, so running it again won't double up.</span></div>`;
    }
    return `<section class="card ml-recipes"><h2>Recipes <small>fill to target</small> <button type="button" class="link" data-mlrec="close">close</button></h2>
      <div class="ml-rec-cols"><div class="ml-rec-list">${list}<button type="button" data-mlrec="new" class="primary">+ New recipe</button></div><div class="ml-rec-edit">${form}</div></div>${prev}</section>`;
  }
  function drawRec() { const el = document.querySelector(".ml-recipes"); if (el) el.outerHTML = recipesPanel(); else redraw(); }
  async function recStore(list) {
    const res = await api("media/recipes", { recipes: list });
    if (!res.ok) { toast(res.error || "Not saved.", true); return false; }
    M.recipes = res.recipes || []; return true;
  }
  async function recRun() {
    const d = M.rec.draft, R = M.rec;
    await load(true);                     // fresh counts, including anything the farm has finished or queued since
    const plan = recPlan(d), total = plan.reduce((a, p) => a + p.needC + p.needN, 0);
    if (!total) { toast("Nothing is short."); return drawRec(); }
    if (total > 60 && !confirm(`This queues ${total} pictures on the farm. Go ahead?`)) return;
    R.busy = true; let made = 0, failed = 0, last = "";
    const tag = d.tag || slug(d.name) || "recipe";
    for (const p of plan) {
      if (!p.needC && !p.needN) continue;
      const pr = recPrompts(d, p.t), pool = pr.person ? POSES : CAMERAS;
      const roles = p.t.role ? [p.t.role] : d.roles.slice();
      const batches = p.plain ? [["auto", p.needN, pr.plainP, ""]] : [["yes", p.needN, pr.nsfwP, ""], ["no", p.needC, pr.cleanP, "clean"]];
      for (const [nsfw, n, base, extra] of batches) {
        if (!n) continue;
        const have = nsfw === "no" ? p.haveC + p.pendC : p.haveN + p.pendN;
        const jobs = d.pose ? Array.from({ length: n }, (_, i) => [1, `${base}, ${pool[(have + i) % pool.length]}`]) : [[n, base]];
        for (const [count, prompt] of jobs) {
          const tags = [tag, extra].filter(Boolean).join(", ");
          const res = await api("media/generate", { kind: d.kind, subject: p.t.s, roles, prompt, aspect: pr.aspect, count: Math.min(8, count), nsfw, tags });
          if (res.ok) made += count; else { failed += count; last = res.error || last; }
          R.prog = `Queued ${made} of ${total}…`; drawRec();
        }
      }
    }
    R.busy = false; R.prog = "";
    { const n = new Date(), p2 = x => String(x).padStart(2, "0"); d.last_run = `${n.getFullYear()}-${p2(n.getMonth() + 1)}-${p2(n.getDate())} ${p2(n.getHours())}:${p2(n.getMinutes())}`; } d.last_made = made;
    if (M.recipes.some(x => x.id === d.id)) await recStore(M.recipes.map(x => x.id === d.id ? Object.assign({}, d) : x));
    toast(failed ? `Queued ${made}; ${failed} were refused (${last}).` : `Queued ${made} picture${made === 1 ? "" : "s"}. They file themselves as they finish.`, !!failed);
    return load(true);
  }
  function recClick(el) {
    const d = el.dataset, R = M.rec, dr = R.draft;
    if (d.mlrec === "close") { R.open = false; return redraw(); }
    if (d.mlrec === "new") { R.draft = newRecipe(); return drawRec(); }
    if (d.mlrec === "pick") { const x = M.recipes.find(r => r.id === d.id); R.draft = x ? JSON.parse(JSON.stringify(x)) : null; return drawRec(); }
    if (!dr) return;
    if (d.mlrec === "allsubs") { dr.subjects = []; return drawRec(); }
    if (d.mlrec === "nosubs") { dr.subjects = []; return drawRec(); }
    if (d.mlrec === "allroles" || d.mlrec === "noroles") { dr.roles = d.mlrec === "allroles" ? ((kinds()[dr.kind] || {}).roles || []).map(x => x[0]) : []; return drawRec(); }
    if (d.mlrec === "save" || d.mlrec === "dup") {
      const copy = d.mlrec === "dup";
      const rec = Object.assign({}, dr, copy ? { id: "r" + Math.random().toString(36).slice(2, 9), name: dr.name + " (copy)", last_run: "", last_made: 0 } : {});
      const list = copy || !M.recipes.some(x => x.id === rec.id) ? M.recipes.concat(rec) : M.recipes.map(x => x.id === rec.id ? rec : x);
      return recStore(list).then(ok => { if (ok) { R.draft = JSON.parse(JSON.stringify(M.recipes.find(x => x.id === rec.id) || rec)); toast(copy ? "Saved as a copy." : "Recipe saved."); drawRec(); } });
    }
    if (d.mlrec === "del") {
      if (!el.dataset.armed) { el.dataset.armed = "1"; el.textContent = "Click again to delete"; setTimeout(() => { if (el.isConnected) { delete el.dataset.armed; el.textContent = "Delete"; } }, 3500); return; }
      return recStore(M.recipes.filter(x => x.id !== dr.id)).then(ok => { if (ok) { R.draft = null; toast("Recipe deleted."); drawRec(); } });
    }
    if (d.mlrec === "run") return recRun();
  }
  function recField(el, ev) {
    const d = el.dataset, dr = M.rec.draft; if (!dr) return;
    if (d.mlrecsub !== undefined) { dr.subjects = dr.subjects.filter(x => x !== d.mlrecsub); if (el.checked) dr.subjects.push(d.mlrecsub); return drawRec(); }
    if (d.mlrecrole !== undefined) { dr.roles = dr.roles.filter(x => x !== d.mlrecrole); if (el.checked) dr.roles.push(d.mlrecrole); return drawRec(); }
    if (d.mlrecport !== undefined) {
      if (el.value) dr.subjects = Object.entries(CFG.characters).filter(([k, c]) => c.home_port === el.value).map(([k]) => k);
      return drawRec();
    }
    const k = d.mlrecf, num = ["clean", "nsfw", "count"].includes(k);
    dr[k] = el.type === "checkbox" ? el.checked : num ? Number(el.value) : el.value;
    if (num) { const b = $("mlrecv-" + k); if (b) b.textContent = el.value; if (ev.type === "change") drawRec(); return; }
    if (k === "kind") { dr.subjects = []; dr.roles = []; return drawRec(); }
    if (ev.type === "change") drawRec();
  }

  /* ---- Generate drawer ---- */
  function shapeOf(it) {
    const list = Object.keys((M.lib && M.lib.aspects) || { "3:4": 1 });
    if (!it || !it.width || !it.height) return ASPECT_FOR[it && it.kind] || "3:4";
    const r = it.width / it.height;
    const val = a => { const [x, y] = a.split(":").map(Number); return x / y; };
    return list.slice().sort((a, b) => Math.abs(val(a) - r) - Math.abs(val(b) - r))[0] || "3:4";
  }
  // Open the drawer: from a picture (its prompt, shape, roles, tags) or fresh for the current kind/subject.
  function openGen(it) {
    const kind = it ? it.kind : (M.kind || "persona"), K = kinds()[kind] || { roles: [] };
    const subs = subjectsFor(kind);
    const subject = it ? it.subject : (M.subject || (subs[0] ? subs[0][0] : ""));
    Object.assign(M.gen, { kind, subject, forKey: kind + ":" + subject });
    if (it) {
      M.gen.prompt = it.prompt || defaultPrompt(kind, subject);
      M.gen.roles = it.roles.slice(); M.gen.aspect = shapeOf(it); M.gen.tags = it.tags.join(", ");
    } else {
      M.gen.prompt = defaultPrompt(kind, subject); M.gen.aspect = ASPECT_FOR[kind] || "3:4";
      M.gen.roles = K.default_role ? [K.default_role] : []; M.gen.tags = "";
    }
    M.vid.open = false; M.gen.twin = false;
    M.drawer = { open: true, mode: "gen", src: it ? it.id : "" };
  }

  function genBody(src) {
    const g = M.gen;
    const kind = g.kind || M.kind || "persona", K = kinds()[kind] || { roles: [], one: "Subject" };
    const subs = subjectsFor(kind);
    const subject = g.subject || (subs[0] ? subs[0][0] : "");
    const key = kind + ":" + subject;
    if (g.forKey !== key) {
      Object.assign(g, { kind, subject, forKey: key, prompt: defaultPrompt(kind, subject), aspect: ASPECT_FOR[kind] || "3:4", roles: K.default_role ? [K.default_role] : [] });
    }
    const aspects = Object.keys((M.lib && M.lib.aspects) || { "3:4": 1 });
    const q = M.pickQ.trim().toLowerCase();
    const found = !M.pickOpen ? [] : items().filter(i => i.type === "image" && i.prompt && (!q || [i.title, i.subject, i.prompt, i.tags.join(" ")].join(" ").toLowerCase().includes(q)))
      .sort(byAdded).slice(0, 6);
    const noSeed = src && src.seed == null;
    return `<div class="ml-dcols"><div class="ml-dleft">
      ${g.twin ? `<p class="ml-twinhint"><b>Clean twin.</b> NSFW tag is set to <b>Never</b> and the tag <i>clean</i> is added. Reword the prompt to remove nudity or erotic styling before painting.</p>` : ""}
      ${src ? `<div class="ml-src"><img src="${e(src.url)}" alt=""><div><b>${e(src.title || subjectName(src.kind, src.subject))}</b><small>${e(subjectName(src.kind, src.subject))}${src.seed != null ? " · seed " + e(src.seed) : ""}</small>
        <div class="row"><button type="button" data-mlquickredo="${e(src.id)}" data-mode="same" class="${noSeed ? "none" : ""}" title="Same prompt, same seed">↻ Regen</button>
        <button type="button" data-mlquickredo="${e(src.id)}" data-mode="new" title="Same prompt, new seed">🎲 Reroll</button>
        ${!src.missing && src.subject ? `<button type="button" data-mldtab="vid">▶ Video</button>` : ""}</div></div></div>` : ""}
      <div class="ml-start"><span>Start from</span>
        <button type="button" data-mlstart="blank">Clean slate</button><button type="button" data-mlstart="stock">Stock prompt</button>
        ${src && src.prompt ? `<button type="button" data-mlstart="src">This picture</button>` : ""}
        <button type="button" data-mlpickopen="1" class="${M.pickOpen ? "on" : ""}">Existing prompt…</button></div>
      ${M.pickOpen ? `<div class="ml-pick"><input type="search" id="mlpickq" data-mlpickq="1" value="${e(M.pickQ)}" placeholder="Search prompts you already have">
        ${found.length ? found.map(i => `<button type="button" class="ml-pickrow" data-mluse="${e(i.id)}"><img src="${e(i.url)}" alt="" loading="lazy"><span><b>${e(subjectName(i.kind, i.subject))}</b><small>${e(String(i.prompt).slice(0, 90))}</small></span></button>`).join("") : '<p class="help">No matching prompts.</p>'}</div>` : ""}
      <div class="ml-dgrid">
        <label>Kind<select data-mlgenf="kind">${KIND_ORDER.filter(k => kinds()[k]).map(k => `<option value="${k}"${k === kind ? " selected" : ""}>${e(kinds()[k].one)}</option>`).join("")}</select></label>
        <label>${e(K.one || "Subject")}<select data-mlgenf="subject">${subs.map(([k, n]) => `<option value="${e(k)}"${k === subject ? " selected" : ""}>${e(n)}</option>`).join("")}</select></label>
        <label>Shape<select data-mlgenf="aspect">${aspects.map(a => `<option${a === g.aspect ? " selected" : ""}>${e(a)}</option>`).join("")}</select></label>
        <label>How many<input type="number" min="1" max="8" value="${g.count}" data-mlgenf="count"></label>
        <label class="wide">NSFW tag<select data-mlgenf="nsfw">${[["auto", "Read the prompt"], ["yes", "Always NSFW"], ["no", "Never NSFW"]].map(([k, n]) => `<option value="${k}"${k === g.nsfw ? " selected" : ""}>${n}</option>`).join("")}</select></label>
        <label class="wide">Tags<input type="text" value="${e(g.tags)}" data-mlgenf="tags" placeholder="night, rain, close-up"></label>
      </div>
      ${K.roles.length ? `<details class="ml-rolesbox"${g.roles.length ? "" : " open"}><summary>Roles <small>${g.roles.length ? g.roles.map(r => e(roleName(kind, r))).join(", ") : "any"}</small></summary><div class="ml-roles">${K.roles.map(([k, n]) => `<label class="ml-check"><input type="checkbox" data-mlgenrole="${k}"${g.roles.includes(k) ? " checked" : ""}> ${e(n)}</label>`).join("")}</div></details>` : ""}
      ${src && src.type === "image" && src.seed != null ? abBox(src) : ""}
      </div><div class="ml-dright">
      <textarea rows="9" class="code ml-prompt-box" data-mlgenf="prompt" id="mlgenprompt" placeholder="Describe the picture…">${e(g.prompt)}</textarea>
      <div class="row"><button type="button" class="primary" data-mlgo="${e(kind)}|${e(subject)}">Paint ${g.count} picture${g.count == 1 ? "" : "s"}</button>
        <span class="help">Filed under ${e(K.one || "")} · ${e(subjectName(kind, subject))}</span></div>
      </div></div>`;
  }

  function drawer() {
    if (!M.drawer.open) return "";
    const src = M.drawer.src ? byId(M.drawer.src) : null;
    const vid = M.drawer.mode === "vid" && M.vid.open;
    const tabs = src && src.type === "image" && !src.missing && src.subject
      ? `<div class="ml-seg ml-dtabs"><button type="button" data-mldtab="gen" class="${vid ? "" : "on"}">Picture</button><button type="button" data-mldtab="vid" class="${vid ? "on" : ""}">Video</button></div>` : "";
    const sz = ["side", "wide", "full"].includes(M.dsize) ? M.dsize : "wide";
    const sizes = `<div class="ml-seg ml-dsize" title="How much room the generator gets">${[["side", "▭ Side"], ["wide", "◧ Wide"], ["full", "⛶ Popup"]].map(([k, n]) => `<button type="button" data-mldsize="${k}" class="${k === sz ? "on" : ""}">${n}</button>`).join("")}</div>`;
    return `${sz === "full" ? '<button type="button" class="ml-dback" data-mldclose="1" aria-label="Close generator" tabindex="-1"></button>' : ""}<aside class="ml-drawer card ml-d-${sz}"><div class="ml-dhead"><b>${vid ? "Make video" : src ? "Edit &amp; regenerate" : "New picture"}</b>${tabs}${sizes}<button type="button" class="link" data-mldclose="1" aria-label="Close">✕</button></div>
      <div class="ml-dbody">${vid ? vidPanel() : genBody(src)}</div></aside>`;
  }

  const LIVE = ["waiting", "running", "cancelling"];
  function eta(sec) {
    if (sec == null) return "paused";
    if (sec < 90) return "~" + Math.max(5, Math.round(sec / 5) * 5) + " s";
    if (sec < 5400) return "~" + Math.round(sec / 60) + " min";
    return "~" + Math.floor(sec / 3600) + " h " + (Math.round(sec / 60) % 60) + " min";
  }

  function jobsPill() {
    if (!M.jobs.length) return "";
    const active = M.jobs.filter(j => LIVE.includes(j.status)), q = M.queue || {};
    const label = active.length ? `⏳ Farm: ${active.length} job${active.length === 1 ? "" : "s"}${q.total_eta_s ? " · " + eta(q.total_eta_s) : ""}` : "Farm idle";
    return `<div class="ml-jobspill"><button type="button" data-mljobspop="1" class="${active.length ? "busy" : ""}">${label}</button>
      ${M.jobsPop ? `<div class="ml-jobspop">${jobList()}</div>` : ""}</div>`;
  }

  function laneBlock(lane, title) {
    const q = ((M.queue || {}).lanes || {})[lane] || {}, rows = M.jobs.filter(j => (j.lane || (j.type === "video" ? "video" : "picture")) === lane && LIVE.includes(j.status));
    if (!rows.length && !q.paused) return "";
    const head = `<div class="ml-lane-h"><b>${title}</b> <span>${rows.length} job${rows.length === 1 ? "" : "s"} · ${q.items || 0} to make · ${q.paused ? "paused" : eta(q.eta_s)}</span>
      <button type="button" class="link" data-mlq="${q.paused ? "resume" : "pause"}|${lane}">${q.paused ? "resume" : "pause"}</button></div>`;
    const items = rows.map(j => {
      const waiting = j.status === "waiting", n = j.type === "video";
      const when = j.status === "running" ? "running now · done " + eta(j.eta_s) : waiting ? (j.eta_s == null ? "on hold" : "starts in " + eta(j.start_s) + " · done " + eta(j.eta_s)) : "stopping after this one";
      return `<li class="${e(j.status)}" data-jid="${e(j.id)}">
        <b>${waiting ? "#" + (j.pos || "") + " " : ""}${e(subjectName(j.kind, j.subject))}</b>
        <span>${n ? "▶ " : ""}${j.done}/${j.count} ${n ? (j.nsfw === "yes" ? "NSFW clips" : j.nsfw === "no" ? "clean clips" : "clips") : "painted"}${j.failed ? `, ${j.failed} failed` : ""}${j.resumed ? " · resumed after restart" : ""} · ${when}${j.progress ? " · " + e(j.progress) : ""}</span>
        ${j.error ? `<small>${e(j.error)}</small>` : ""}
        <i class="ml-jobbtns">${waiting ? `<button type="button" class="link" title="Run first" data-mlq="top|${e(j.id)}">⤒</button><button type="button" class="link" title="Move up" data-mlq="up|${e(j.id)}">▲</button><button type="button" class="link" title="Move down" data-mlq="down|${e(j.id)}">▼</button>` : ""}
        ${["waiting", "running"].includes(j.status) ? `<button type="button" class="link" data-mlcancel="${e(j.id)}">stop</button>` : ""}</i></li>`;
    }).join("");
    return head + `<ul class="ml-jobs">${items}</ul>`;
  }

  function jobList() {
    const finishedRows = M.jobs.filter(j => !LIVE.includes(j.status));
    const live = M.jobs.length - finishedRows.length;
    const top = `<div class="ml-qtop"><b>Render queue</b>${live ? `<button type="button" class="danger" data-mlq="cancel_all|">Stop all</button>` : ""}
      <span>Pictures run first, so they never wait behind a clip; the queue survives a restart.</span></div>`;
    const lanes = laneBlock("picture", "Pictures") + laneBlock("video", "Videos") || '<p class="help">Nothing waiting.</p>';
    const shown = M.jobsOpen ? finishedRows.slice(0, 10) : [];
    const toggle = finishedRows.length ? `<div class="ml-lane-h"><button type="button" class="link ml-jobs-toggle" data-mljobs="1">${M.jobsOpen ? "hide finished" : `show ${finishedRows.length} finished`}</button>${M.jobsOpen ? `<button type="button" class="link" data-mlq="clear|">clear</button>` : ""}</div>` : "";
    const done = shown.length ? `<ul class="ml-jobs">${shown.map(j => `<li class="${e(j.status)}"><b>${e(subjectName(j.kind, j.subject))}</b> <span>${j.type === "video" ? "▶ " : ""}${j.done}/${j.count}${j.failed ? `, ${j.failed} failed` : ""} · ${e(j.status)}</span>${j.error ? `<small>${e(j.error)}</small>` : ""}</li>`).join("")}</ul>` : "";
    return top + lanes + toggle + done;
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
      <div class="ml-art"${i.width && i.height ? ` style="aspect-ratio:${i.width} / ${i.height}"` : ""}>${thumb(i, "ml-img")}
        <span class="ml-badges">${i.primary && i.kind !== "persona" ? '<b class="star" title="Primary (used when the rule is Fixed)">★</b>' : ""}${i.type === "video" ? `<b>▶ ${i.seconds ? i.seconds + " s" : "video"}${i.loop ? " ⟲" : ""}</b>` : ""}${i.type === "video" && i.pair ? '<b class="pair" title="Part of a clean + NSFW pair">pair</b>' : ""}${i.type === "image" && clipsOf(i.id).length ? `<b title="Clips made from this picture">▶ ${clipsOf(i.id).length}</b>` : ""}${i.nsfw ? '<b class="nsfw">NSFW</b>' : ""}${!i.reviewed ? '<b class="rev">review</b>' : ""}${inUse ? '<b class="use" title="Used by a setting (cast portrait or Graphics page)">in use</b>' : ""}${!i.enabled ? "<b>off</b>" : ""}</span>
        <span class="ml-quick"><button type="button" class="ml-quickdel" data-mlquickdel="${e(i.id)}" title="Delete (moves it to the media trash)" aria-label="Delete">🗑</button>
        ${!i.reviewed ? `<button type="button" class="ml-quickok" data-mlquickok="${e(i.id)}" title="Approve (marks it reviewed)" aria-label="Approve">✓</button>` : ""}${quickRedo(i, "button")}${i.type === "image" && !i.missing ? `<button type="button" class="ml-quickvid ml-quickedit" data-mledit="${e(i.id)}" title="Edit the prompt and regenerate" aria-label="Edit and regenerate">✎</button>` : ""}${i.type === "image" && !i.missing && i.subject ? `<button type="button" class="ml-quickvid" data-mlvidfrom="${e(i.id)}" title="Make a video from this picture" aria-label="Make a video">▶</button>` : ""}</span></div>
      <div class="ml-cap"><b>${e(i.title || subjectName(i.kind, i.subject))}</b>
        ${M.port || M.job ? `<small class="ml-where">${e((kinds()[i.kind] || {}).one || i.kind)} · ${e(subjectName(i.kind, i.subject))}</small>` : ""}<small>${i.roles.length ? i.roles.map(r => e(roleName(i.kind, r))).join(", ") : "any role"}${i.tags.length ? " · " + i.tags.map(e).join(", ") : ""}</small></div></div>`;
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
        ? `<video src="${e(i.url)}"${posterOf(i) ? ` poster="${e(posterOf(i))}"` : ""} controls loop playsinline></video>` : `<a href="${e(i.url)}" target="_blank" rel="noopener"><img src="${e(i.url)}" alt=""></a>`}</div>
      ${videoBits(i)}
      <div class="ml-switches">
        <button type="button" class="ml-nsfw${i.nsfw ? " on" : ""}" data-mlset="nsfw" data-v="${i.nsfw ? "0" : "1"}">${i.nsfw ? "NSFW" : "Family-friendly"}</button>
        ${i.kind !== "persona" ? `<button type="button" class="${i.primary ? "on" : ""}" data-mlset="primary" data-v="${i.primary ? "0" : "1"}" title="Shown when the rule is Fixed">★ ${i.primary ? "Primary" : "Make primary"}</button>` : ""}
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
      ${i.prompt && i.type === "image" ? `<button type="button" class="primary ml-editbtn" data-mledit="${e(i.id)}">✎ Edit prompt &amp; regenerate</button>` : ""}
      ${i.prompt ? `<details><summary>Prompt</summary><p class="mono ml-prompt">${e(i.prompt)}</p><button type="button" class="link" data-mlmore="${e(i.id)}">Edit &amp; regenerate</button></details>` : ""}
      <div class="row">${i.kind === "persona" && i.type === "image" && CFG.characters[i.subject]
        ? `<button type="button" data-mlprofile="${e(i.id)}"${CFG.characters[i.subject].portrait === i.url ? " disabled" : ""}>${CFG.characters[i.subject].portrait === i.url ? "Profile picture" : "Make profile picture"}</button>` : ""}
        <button type="button" class="danger" data-mldel="${e(i.id)}">Remove</button></div>
    </aside>`;
  }

  // In a picture's panel: Make video and the clips made from it. In a clip's panel: where it came from and Compare.
  function videoBits(i) {
    if (i.type === "image") {
      const clips = clipsOf(i.id);
      return `<div class="ml-vidbits">${!i.missing && i.subject ? `<button type="button" class="primary" data-mlvidfrom="${e(i.id)}">▶ Make video…</button>` : ""}
        ${clips.length ? `<span>Clips from this picture:</span><span class="ml-vidstrip">${clips.map(c => `<button type="button" class="ml-vidthumb" data-mlpick="${e(c.id)}" title="${e((c.nsfw ? "NSFW · " : "") + (c.seconds || "") + " s")}"><img src="${e(i.url)}" alt=""><b>▶</b></button>`).join("")}</span>` : ""}</div>`;
    }
    const src = i.from_item ? byId(i.from_item) : null;
    return `<div class="ml-vidbits">
      ${src ? `<span>Made from</span><button type="button" class="ml-vidthumb" data-mlpick="${e(src.id)}"><img src="${e(src.url)}" alt=""></button>` : ""}
      ${i.pair ? `<button type="button" class="primary" data-mlcmp="${e(i.pair)}">Compare the pair</button>` : ""}
      <p class="help">${[i.seconds ? i.seconds + " s" : "", i.loop ? "loops" : "", i.model, i.render_s ? Math.round(i.render_s / 60) + " min to render" : "", i.width ? i.width + " × " + i.height : ""].filter(Boolean).map(e).join(" · ")}</p>
      ${i.motion ? `<details><summary>Movement</summary><p class="mono ml-prompt">${e(i.motion)}</p></details>` : ""}</div>`;
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
    document.body.classList.add("ml-active");
    document.body.classList.toggle("ml-navmin", M.navMin);
    const c = M.lib.counts, list = filtered();
    return head("Media Library", "", familySwitch()) +
      `<div class="ml-stats"><span><b>${c.total}</b> items</span><span><b>${c.video}</b> video</span><span><b>${c.nsfw}</b> NSFW</span>
        ${c.review ? `<button type="button" class="link ml-stat-review" data-mlreviewall="1" title="Show every item that needs review"><b>${c.review}</b> need review</button>` : `<span><b>0</b> need review</span>`}<span><b>${fmtBytes(c.bytes)}</b> on disk</span>
        <span class="ml-showing">showing <b>${list.length}</b></span></div>
      <div class="ml-shell2${M.railOpen ? "" : " norail"}${M.drawer.open && M.dsize !== "full" ? " withdrawer" : ""}${M.drawer.open ? " dz-" + (M.dsize || "wide") : ""}">
        ${M.railOpen ? rail() : ""}
        <div class="ml-main">
          ${toolbar()}${chips()}${uploadBar()}${comparePanel()}${abPanel()}${rulesPanel()}${bulk()}
          ${recipesPanel()}${M.cov ? coverage() : ""}
          <div class="ml-body${M.sel.size === 1 ? " with-detail" : ""}${CFG.content.rating === "family" ? " ml-family" : ""}"${M.cov ? " hidden" : ""}>
            <div class="ml-grid d-${M.density}">${list.map(tile).join("") || `<p class="muted ml-empty">Nothing matches. Clear a filter, upload, or press + New to generate.</p>`}</div>
            ${detail()}</div>
        </div>
        ${drawer()}
      </div>` + jobsPill() +
      `<button type="button" class="ml-navtab" data-mlnav="1" title="Show or hide the admin menu">${M.navMin ? "☰ Menu" : "« Hide menu"}</button>`;
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

  function repaintPill() {
    const p = document.querySelector(".ml-jobspill");
    if (p) { const pop = p.querySelector(".ml-jobspop"), y = pop ? pop.scrollTop : 0; p.outerHTML = jobsPill(); const np = document.querySelector(".ml-jobspop"); if (np) np.scrollTop = y; }
  }

  function watchJobs() {
    const busy = M.jobs.some(j => ["waiting", "running", "cancelling"].includes(j.status));
    if (busy && !M.poll) {
      M.poll = setInterval(async () => {
        if (section !== "media") return;
        const res = await api("media/jobs");
        if (!res.ok) return;
        const sig = () => JSON.stringify(M.jobs.map(j => [j.id, j.done, j.status]));
        const before = sig(), pill = JSON.stringify([M.jobs.map(j => [j.id, j.pos, j.eta_s, j.progress, j.status]), M.queue]);
        M.jobs = res.jobs; M.queue = res.queue || M.queue;
        if (sig() !== before) await load(true);
        else if (JSON.stringify([M.jobs.map(j => [j.id, j.pos, j.eta_s, j.progress, j.status]), M.queue]) !== pill) repaintPill();
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
    const el = t.closest("[data-mlquickdel],[data-mlquickok],[data-mlquickredo],[data-mlvidfrom],[data-mlkind],[data-mlsubject],[data-mlitem],button");
    if (!el) return;
    const d = el.dataset;
    if (d.mlnav) { M.navMin = !M.navMin; try { localStorage.setItem("ml.navmin", M.navMin ? "1" : "0"); } catch (_) {} return redraw(); }
    if (d.mlrailtoggle) { M.railOpen = !M.railOpen; try { localStorage.setItem("ml.rail", M.railOpen ? "1" : "0"); } catch (_) {} return redraw(); }
    if (d.mldens) { M.density = d.mldens; try { localStorage.setItem("ml.density", M.density); } catch (_) {} return redraw(); }
    if (d.mlview !== undefined) { M.type = d.mlview; M.sel.clear(); return redraw(); }
    if (d.mlrating !== undefined) { M.nsfw = d.mlrating; M.sel.clear(); return redraw(); }
    if (d.mlstatus) { M.type = M.type === d.mlstatus ? "" : d.mlstatus; M.sel.clear(); return redraw(); }
    if (d.mlmotion !== undefined) { M.motion = d.mlmotion; if (M.motion && M.type !== "video" && M.type !== "pair") M.type = "video"; M.sel.clear(); return redraw(); }
    if (d.mltag !== undefined) { M.tag = d.mltag; M.sel.clear(); return redraw(); }
    if (d.mlchipx) {
      const f = d.mlchipx;
      if (f === "port") M.port = ""; else if (f === "job") M.job = "";
      else if (f === "kind") { M.kind = ""; M.subject = ""; M.role = ""; } else if (f === "subject") { M.subject = ""; M.role = ""; }
      else if (f === "role") M.role = ""; else if (f === "type") M.type = ""; else if (f === "nsfw") M.nsfw = "";
      else if (f === "review") M.review = false; else if (f === "tag") M.tag = ""; else if (f === "motion") M.motion = ""; else if (f === "q") M.q = "";
      M.sel.clear(); return redraw();
    }
    if (d.mlpreset) {
      const p = d.mlpreset;
      M.kind = ""; M.subject = ""; M.role = ""; M.port = ""; M.job = ""; M.type = ""; M.nsfw = ""; M.review = false; M.tag = ""; M.motion = ""; M.q = ""; M.sel.clear(); M.cov = false;
      if (p === "review") M.review = true; else if (p === "vidreview") { M.review = true; M.type = "video"; }
      else if (p === "clips") M.type = "hasvid"; else if (p === "nsfw") M.nsfw = "nsfw"; else if (p === "off") M.nsfw = "off";
      return redraw();
    }
    if (d.mlcovtoggle) { M.cov = !M.cov; return redraw(); }
    if (d.mlrecopen) { M.rec.open = !M.rec.open; if (M.rec.open && !M.rec.draft) M.rec.draft = M.recipes[0] ? JSON.parse(JSON.stringify(M.recipes[0])) : null; return redraw(); }
    if (d.mlcovrec) {
      const r = newRecipe(); r.kind = M.kind; r.name = (kinds()[M.kind] || {}).label + " gap fill"; r.by = "role"; r.roles = ((kinds()[M.kind] || {}).roles || []).map(x => x[0]); r.clean = 1; r.nsfw = 2;
      M.rec = { open: true, draft: r, busy: false, prog: "" }; M.cov = false; redraw(); return window.scrollTo(0, 0);
    }
    if (d.mlrec !== undefined) { ev.preventDefault(); return recClick(el); }
    if (d.mlcov !== undefined) {
      const [sub, role] = d.mlcov.split("|"), kind = M.kind, rs = roleStart(kind, sub, role);
      Object.assign(M.gen, { kind, subject: sub, forKey: kind + ":" + sub, prompt: rs.prompt, aspect: rs.aspect, roles: role ? [role] : [], tags: "", nsfw: "auto", twin: false });
      M.vid.open = false; M.drawer = { open: true, mode: "gen", src: "" };
      return redraw();
    }
    if (d.mltwin) {
      const it = byId(d.mltwin); if (!it) return;
      openGen(it); M.gen.nsfw = "no"; M.gen.twin = true;
      M.gen.tags = it.tags.filter(t => t !== "clean").concat("clean").join(", ");
      return redraw();
    }
    if (d.mlnew) { openGen(null); return redraw(); }
    if (d.mledit) { ev.preventDefault(); ev.stopPropagation(); const it = byId(d.mledit); if (it) { openGen(it); redraw(); } return; }
    if (d.mldsize) { M.dsize = d.mldsize; try { localStorage.setItem("ml.dsize", M.dsize); } catch (_) {} return redraw(); }
    if (d.mldclose) { M.drawer.open = false; M.vid.open = false; return redraw(); }
    if (d.mldtab) {
      const src = byId(M.drawer.src);
      if (d.mldtab === "vid" && src) { openVideo(src.id); return redraw(); }
      M.vid.open = false; M.drawer.mode = "gen"; return redraw();
    }
    if (d.mlstart) {
      const src = byId(M.drawer.src), g = M.gen;
      if (d.mlstart === "blank") g.prompt = "";
      else if (d.mlstart === "stock") g.prompt = defaultPrompt(g.kind, g.subject);
      else if (d.mlstart === "src" && src) g.prompt = src.prompt || "";
      return redraw();
    }
    if (d.mlpickopen) { M.pickOpen = !M.pickOpen; return redraw(); }
    if (d.mluse) { const it = byId(d.mluse); if (it) { M.pickOpen = false; M.pickQ = ""; openGen(it); redraw(); } return; }
    if (d.mljobspop) { M.jobsPop = !M.jobsPop; return redraw(); }
    if (d.mlreview) { M.review = !M.review; M.sel.clear(); return redraw(); }
    if (d.mlreviewall) { M.review = true; M.kind = ""; M.subject = ""; M.role = ""; M.sel.clear(); return redraw(); }
    if (d.mlkind !== undefined) { M.kind = d.mlkind; M.subject = ""; M.role = ""; M.tag = ""; M.sel.clear(); return redraw(); }
    if (d.mlsubject !== undefined) { M.tag = ""; if (d.mlcovoff) M.cov = false; return goSubject(M.kind, d.mlsubject); }
    if (d.mlquickdel) {
      // Anthony, 19 Nov 2026: one-click delete from the grid. The file goes to web/media/_trash, not gone for good.
      ev.preventDefault(); ev.stopPropagation();
      if (el.dataset.busy) return;
      el.dataset.busy = "1"; el.disabled = true; el.classList.add("busy");
      const res = await api("media/delete", { ids: [d.mlquickdel] });
      toast(res.ok ? res.msg : res.error, !res.ok);
      M.sel.delete(d.mlquickdel);
      return load(true);
    }
    if (d.mlquickok) {
      // Anthony, 19 Nov 2026: one-click approve from the grid, the twin of Quick Trash. Same as "Mark reviewed".
      ev.preventDefault(); ev.stopPropagation();
      if (el.dataset.busy) return;
      el.dataset.busy = "1"; el.disabled = true; el.classList.add("busy");
      const res = await api("media/update", { ids: [d.mlquickok], changes: { reviewed: true } });
      toast(res.ok ? "Approved." : (res.error || "Not saved."), !res.ok);
      if (M.review) M.sel.delete(d.mlquickok);
      return load(true);
    }
    if (d.mlquickredo) {
      // Anthony, 20 Nov 2026: one-click Regen (same seed) / Reroll (new seed). Queues one picture beside the original.
      ev.preventDefault(); ev.stopPropagation();
      if (el.classList.contains("none")) return toast("No seed was saved with this picture. Use Reroll instead.", true);
      if (el.dataset.busy) return;
      el.dataset.busy = "1"; el.disabled = true; el.classList.add("busy");
      const res = await api("media/redo", { id: d.mlquickredo, mode: d.mode === "same" ? "same" : "new" });
      toast(res.ok ? res.msg : res.error, !res.ok);
      return load(true);
    }
    if (d.mlvidfrom) {
      ev.preventDefault(); ev.stopPropagation();
      openVideo(d.mlvidfrom);
      return redraw();
    }
    if (d.mlpick) { M.sel.clear(); M.sel.add(d.mlpick); M.last = d.mlpick; return redraw(); }
    if (d.mlvidclose) { M.vid.open = false; M.drawer.open = false; return redraw(); }
    if (d.mlvidgo) {
      const motion = (($("mlvidmotion") || {}).value || M.vid.motion).trim();
      const src = byId(M.vid.src), partner = M.vid.pair ? byId(M.vid.partner) : null;
      if (!src) return toast("That picture is no longer in the library.", true);
      const mk = MOTIONS[M.vid.preset] && motion === MOTIONS[M.vid.preset][1] ? M.vid.preset : "custom";
      let body = { motion, count: M.vid.count, tags: [M.vid.tags, "motion-" + mk].filter(Boolean).join(", ") };
      if (partner) {
        const srcNsfw = src.nsfw && !src.tags.includes("clean"), partnerClean = !partner.nsfw || partner.tags.includes("clean");
        const [n, c] = srcNsfw || partnerClean ? [src, partner] : [partner, src];
        body = Object.assign(body, { nsfw_id: n.id, clean_id: c.id });
        const clean = (($("mlvidclean") || {}).value || M.vid.clean || "").trim();
        if (clean.length >= 10) body.clean_motion = clean;
      } else {
        body.id = src.id;
        const preset = MOTIONS[M.vid.preset];
        if (preset && preset[2] === "nsfw" && motion === preset[1] && (!src.nsfw || src.tags.includes("clean")) &&
            !confirm("This movement is the NSFW one but the picture is clean. Make it anyway? (Tick Make a pair to give the clean half its softer twin.)")) return;
      }
      el.disabled = true;
      const res = await api("media/video", body);
      el.disabled = false;
      toast(res.ok ? res.msg : res.error, !res.ok);
      if (res.ok) { M.drawer.open = false; M.vid.open = false; M.type = "video"; return load(true); }
      return;
    }
    if (d.mlcmp) { M.cmp = d.mlcmp; M.vid.open = false; M.drawer.open = false; redraw(); return window.scrollTo(0, 0); }
    if (d.mlcmpclose) { M.cmp = ""; return redraw(); }
    if (d.mlcmpplay || d.mlcmppause) {
      document.querySelectorAll("[data-mlcmpv]").forEach(v => { if (d.mlcmpplay) { v.currentTime = 0; v.play().catch(() => {}); } else v.pause(); });
      return;
    }
    if (d.mlabgo) {
      const src = byId(d.mlabgo);
      if (!src) return;
      const base = (($("mlgenprompt") || {}).value || M.gen.prompt || "").trim(), find = M.ab.find.trim();
      const alts = [...new Set(M.ab.alts.split("\n").map(s => s.trim()).filter(Boolean))].slice(0, 6);
      if (!alts.length) return toast("Type at least one alternative, one per line.", true);
      if (find && !base.includes(find)) return toast("That phrase is not in the prompt box. Copy it exactly.", true);
      const prompts = alts.map(a => find ? base.replace(find, () => a) : base.replace(/[\s,.;]+$/, "") + ", " + a);
      el.disabled = true;
      const res = await api("media/ab", { id: src.id, prompts });
      el.disabled = false;
      toast(res.ok ? res.msg : res.error, !res.ok);
      if (!res.ok) return;
      M.ab.expect = abVariants(src.id).length + res.queued; M.ab.view = src.id;
      if (M.dsize === "full") M.drawer.open = false;
      await load(true); return window.scrollTo(0, 0);
    }
    if (d.mlabview) {
      M.ab.view = d.mlabview; M.ab.expect = abVariants(d.mlabview).length;
      if (M.dsize === "full") M.drawer.open = false;
      redraw(); return window.scrollTo(0, 0);
    }
    if (d.mlabclose) { M.ab.view = ""; return redraw(); }
    if (d.mlabuse) { const it = byId(d.mlabuse); if (it) { openGen(it); redraw(); } return; }
    if (d.mlcmpset) return change([d.mlcmpset], { [d.f]: d.v === "1" });
    if (d.mlcmpdel) {
      if (!d.armed) { d.armed = "1"; el.textContent = "Again to delete"; setTimeout(() => { if (el.isConnected) { delete d.armed; el.textContent = "🗑"; } }, 3500); return; }
      const res = await api("media/delete", { ids: [d.mlcmpdel] });
      toast(res.ok ? res.msg : res.error, !res.ok);
      return load(true);
    }
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
      if (res.ok) return load(true);
      return;
    }
    if (d.mlq !== undefined) {
      const [act, arg] = d.mlq.split("|");
      if (act === "cancel_all" && !confirm("Stop every waiting and running job? The picture being painted right now finishes first.")) return;
      const body = { action: act === "top" || act === "up" || act === "down" ? "move" : act };
      if (body.action === "move") { body.job = arg; body.to = act; } else if (arg) body.lane = arg;
      const res = await api("media/queue", body);
      toast(res.ok ? res.msg : res.error, !res.ok);
      return load(true);
    }
    if (d.mlcancel) {
      const res = await api("media/cancel", { job: d.mlcancel });
      toast(res.ok ? res.msg : res.error, !res.ok);
      return load(true);
    }
    if (d.mlmore) {
      const i = byId(d.mlmore);
      if (!i) return;
      openGen(i);
      return redraw();
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
    if (d.mlfind) {
      M[d.mlfind] = el.value; M.kind = ""; M.subject = ""; M.tag = ""; M.sel.clear();
      if (d.mlfind === "port" && M.job && !items().some(i => portOf(i) === M.port && jobOf(i).includes(M.job))) M.job = "";
      return redraw();
    }
    if (d.mlf) {
      M[d.mlf] = el.type === "checkbox" ? el.checked : el.value;
      if (d.mlf === "upNsfw") return;
      if (d.mlf === "sort") { try { localStorage.setItem("ml.sort", M.sort); } catch (_) {} }
      if (d.mlf === "subject") { M.role = ""; }
      M.sel.clear();
      if (d.mlf === "q") { clearTimeout(M.timers.q); M.timers.q = setTimeout(redraw, 220); return; }
      return redraw();
    }
    if (d.mlupload && ev.type === "change") { upload(el.files); el.value = ""; return; }
    if (d.mlabf) { M.ab[d.mlabf] = el.value; return; }
    if (d.mlgenf) {
      const k = d.mlgenf;
      if (k === "subject") { M.gen.subject = el.value; M.gen.forKey = ""; return redraw(); }
      if (k === "kind") { M.gen.kind = el.value; const sb = subjectsFor(el.value); M.gen.subject = sb[0] ? sb[0][0] : ""; M.gen.forKey = ""; return redraw(); }
      M.gen[k] = k === "count" ? Math.max(1, Math.min(8, parseInt(el.value, 10) || 1)) : el.value;
      if (k === "count" && ev.type === "change") redraw();
      return;
    }
    if (d.mlgenrole) {
      M.gen.roles = M.gen.roles.filter(r => r !== d.mlgenrole);
      if (el.checked) M.gen.roles.push(d.mlgenrole);
      // A market keeper, ship master, mayor or tax lady is a portrait of her, not a harbour view: swap the starting prompt, shape and roles.
      const womanRoles = ["keeper", "shipmaster", "mayor", "taxlady"].concat(
        (kinds().port.roles || []).map(r => r[0]).filter(r => r.startsWith("mayor_")));
      if (womanRoles.includes(d.mlgenrole) && el.checked && M.gen.kind === "port") {
        const subject = M.gen.forKey.split(":")[1] || "";
        const box = $("mlgenprompt"), now = (box && box.value) || M.gen.prompt;
        const stock = [undefined].concat(womanRoles).some(r => now === defaultPrompt("port", subject, r));
        if (!now.trim() || stock) M.gen.prompt = defaultPrompt("port", subject, d.mlgenrole);
        M.gen.roles = [d.mlgenrole]; M.gen.aspect = "3:4";
        return redraw();
      }
      // A persona's mood pictures (18 Nov 2026): ticking a mood puts that expression into her own portrait prompt
      // (stock prompts only), e.g. Sly for Powder's whisper when pirates misjudge the hold.
      if (M.gen.kind === "persona" && PERSONA_MOODS[d.mlgenrole]) {
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
      if (M.gen.kind === "ship" && ["card", "sailing", "battle"].includes(d.mlgenrole)) {
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
      if (M.gen.kind === "scene" && BATTLE_ENEMY[subj] && BATTLE_MOMENTS[d.mlgenrole]) {
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
    if (d.mlrecf !== undefined || d.mlrecsub !== undefined || d.mlrecrole !== undefined || d.mlrecport !== undefined) return recField(el, ev);
    if (d.mlpickq) { M.pickQ = el.value; clearTimeout(M.timers.p); M.timers.p = setTimeout(redraw, 200); return; }
    if (d.mlvidf) {
      const k = d.mlvidf;
      if (k === "pair") { M.vid.pair = el.checked; if (M.vid.pair && !M.vid.partner) M.vid.partner = suggestPartner(byId(M.vid.src) || {}); return redraw(); }
      if (k === "partner") { M.vid.partner = el.value; return redraw(); }
      if (k === "preset") { M.vid.preset = el.value; if (MOTIONS[el.value]) { M.vid.motion = MOTIONS[el.value][1]; M.vid.clean = MOTIONS[el.value][3] || ""; } return redraw(); }
      if (k === "count") { M.vid.count = Math.max(1, Math.min(4, parseInt(el.value, 10) || 1)); if (ev.type === "change") redraw(); return; }
      if (k === "motion") { M.vid.motion = el.value; if (M.vid.preset !== "own" && MOTIONS[M.vid.preset] && el.value !== MOTIONS[M.vid.preset][1]) M.vid.preset = "own"; return; }
      M.vid[k] = el.value;
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
    if (ev.key === "Escape" && M.drawer.open && !(ev.target.matches && ev.target.matches("textarea"))) { M.drawer.open = false; M.vid.open = false; return redraw(); }
    if (ev.key === "Escape" && M.sel.size) { M.sel.clear(); redraw(); }
    const quick = ev.target.closest && ev.target.closest("[data-mlquickdel],[data-mlquickok]");
    if (quick && (ev.key === "Enter" || ev.key === " ")) { ev.preventDefault(); ev.stopPropagation(); quick.click(); return; }
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
    M.kind = kind; M.subject = subject || ""; M.role = ""; M.sel.clear();
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
    leave() { document.body.classList.remove("ml-active", "ml-navmin"); if (M.poll) { clearInterval(M.poll); M.poll = null; } },
  };
})();
