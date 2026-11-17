/* SeaTrader Admin: Media Library.
   Every picture and clip the game can show, filed by kind (persona, port, ship, cargo, scene, brand)
   and subject, with roles, tags, weights and an NSFW flag. Changes here are saved at once (no
   Save & apply needed) and every open screen picks them up straight away. */
(function () {
  "use strict";

  const M = {
    lib: null, loading: false, kind: "persona", subject: "", role: "", type: "", nsfw: "", review: false, q: "",
    sel: new Set(), last: null, genOpen: false, rulesOpen: false, jobs: [], poll: null, uploads: [],
    gen: { roles: [], aspect: "3:4", count: 2, nsfw: "auto", prompt: "", tags: "", forKey: "" },
    rulesDraft: null, timers: {},
  };
  const $ = id => document.getElementById(id);
  const e = s => esc(s);
  const KIND_ORDER = ["persona", "port", "ship", "cargo", "scene", "brand", "reference", "other"];
  const ASPECT_FOR = { persona: "3:4", port: "16:9", ship: "3:2", cargo: "1:1", scene: "16:9", brand: "16:9", reference: "1:1", other: "1:1" };

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
    }).sort((a, b) => (a.subject || "").localeCompare(b.subject || "") || (b.primary - a.primary) || String(b.added).localeCompare(String(a.added)));
  }

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
    if (!M.kind || M.subject) return "";
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
      <label class="ml-check"><input type="checkbox" data-mlf="review"${M.review ? " checked" : ""}> Needs review</label>
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

  function defaultPrompt(kind, subject, role) {
    if (kind === "persona" && CFG.characters[subject]) return CFG.characters[subject].portrait_prompt || "";
    const style = "romanticized cinematic historical realism, China Seas 1860, humid salt haze, weathered maritime materials, lacquer black, oxblood silk, antique brass, imperial jade, dramatic but plausible lighting, no text";
    const name = subjectName(kind, subject);
    if (kind === "port" && role === "keeper") return `Waist-up portrait of a breathtakingly beautiful, sultry woman in her late twenties who runs a trading stall in the ${name} market in 1860, looking straight into the camera with a slow, knowing half-smile and direct eye contact, glossy black hair pinned with jade and gold, close-fitting embroidered oxblood silk jacket with a high collar and gold frogging, a little open at the throat, brass scales, tea chests, silk bolts and porcelain behind her, warm lantern glow and soft humid haze, shallow depth of field, she is the centre of the frame, ${style}`;
    if (kind === "port" && role === "shipmaster") return `Waist-up portrait of a breathtakingly beautiful, sultry, dangerous woman in her early thirties, the ship master who rules the ${name} shipyard in 1860, giving the viewer a cold, wicked evil eye: narrowed kohl-lined eyes, one brow raised, chin slightly lowered, a cruel knowing half-smile, direct eye contact, glossy black hair pinned up with a jade comb and loose strands, fitted black lacquer naval coat with oxblood silk lining, brass buttons and gold braid, worn open at the throat, a brass spyglass in one gloved hand, a ship's hull on the slipway, rigging and coiled rope behind her, lantern glow and harbour haze, shallow depth of field, she is the centre of the frame, ${style}`;
    if (kind === "port" && role === "mayor") return `Waist-up portrait of a breathtakingly beautiful, sultry woman in her mid-thirties, a former pirate queen who is now the lady mayor of ${name} in 1860 and keeps the town's ledger and collects its taxes, seated at a heavy teak desk and looking straight into the camera with a sly, appraising, amused half-smile, as if she already knows what you owe her, direct eye contact, glossy black hair swept up with a gold pin and one loose curl, a gold hoop earring, a fitted oxblood silk brocade bodice under a black lacquer pirate captain's coat with gold braid, worn open at the throat and shoulders, a gold mayor's chain of office across her chest, a quill in one ringed hand, an open leather-bound ledger, a brass strongbox spilling silver dollars, tax seals and a cutlass hung on the wall behind her, warm candle and lantern glow, harbour window haze, shallow depth of field, she is the centre of the frame, ${style}`;
    if (kind === "port" && role === "taxlady") return `Waist-up portrait of a breathtakingly beautiful, sultry woman in her early thirties, the tax collector who works the ${name} waterfront in 1860 and takes the town's cut of every cargo, standing at the foot of the gangway with an open tally book and a brass-bound strongbox, looking straight into the camera with a sweet, merciless smile and one raised eyebrow, direct eye contact, glossy black hair in a low braid wound with an oxblood silk ribbon, a fitted black lacquer waistcoat over a loose ivory silk blouse slipping off one shoulder, a jade customs seal on a cord at her throat, a brass stamp and a pen in her gloved hands, sacks of silver dollars, stamped cargo chests, a ship's hull and rigging behind her, warm lantern glow and harbour haze, shallow depth of field, she is the centre of the frame, ${style}`;
    if (kind === "port") return `The port of ${name} in the 1860s seen from the water, busy trading harbour with junks, lorchas and clipper ships at anchor, waterfront godowns and hongs, ${style}`;
    if (kind === "ship") return `A ${name} under full sail on the South China Sea, 1860s, detailed rigging and weathered hull, ${style}`;
    if (kind === "cargo") return `Still life of ${name} as 1860s trade cargo, crates, chests and bales on a teak deck, square composition, no person, ${style}`;
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
      ${M.jobs.length ? `<ul class="ml-jobs">${M.jobs.slice(0, 8).map(j => `<li class="${e(j.status)}">
        <b>${e(subjectName(j.kind, j.subject))}</b> <span>${j.done}/${j.count} painted${j.failed ? `, ${j.failed} failed` : ""} · ${e(j.status)}</span>
        ${j.error ? `<small>${e(j.error)}</small>` : ""}
        ${["waiting", "running"].includes(j.status) ? `<button type="button" class="link" data-mlcancel="${e(j.id)}">stop</button>` : ""}</li>`).join("")}</ul>` : ""}
    </section>`;
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
    return head("Media Library", "Every picture and video clip the game can show, filed by who or what it is of. Several pictures for one persona, port or ship " +
        "are rotated or picked at random by the playback rules; NSFW items disappear from every screen while the game is family-friendly. " +
        "Changes here are saved at once.", familySwitch()) +
      `<div class="ml-stats"><span><b>${c.total}</b> items</span><span><b>${c.video}</b> video</span><span><b>${c.nsfw}</b> NSFW</span>
        <span${c.review ? ' class="warn"' : ""}><b>${c.review}</b> need review</span><span><b>${fmtBytes(c.bytes)}</b> on disk</span>
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
