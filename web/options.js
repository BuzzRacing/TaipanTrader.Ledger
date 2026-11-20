/* Captain button > Options. Uses the player screen's state and shared media library.
   Pages: Table settings and Sound. The x in the title bar closes it. */
"use strict";

const Options = (() => {
  const KEY_SECS = "seatrader_bg_secs", KEY_DIM = "seatrader_bg_dim", KEY_FAMILY = "seatrader_family", KEY_BRIEF = "seatrader_brief", KEY_IMG = "seatrader_images_only";
  const ICONS = {
    table: '<path d="M4 9h16v5H4zM6 14v7M18 14v7M8 9V4h8v5"/>',
    sound: '<path d="M4 9v6h4l5 4V5L8 9zM16 9a4 4 0 0 1 0 6M18.5 6.5a8 8 0 0 1 0 11"/>',
  };
  let dlg = null, info = null, mayorTimer = null, page = "table", opener = null, flip = null;
  let mayors = [], mayorIndex = 0;

  const get = k => { try { return localStorage.getItem(k); } catch (e) { return null; } };
  const put = (k, v) => { try { if (v === null) localStorage.removeItem(k); else localStorage.setItem(k, v); } catch (e) { /* private mode */ } };
  const tx = (key, fallback, vars) => {
    const s = typeof T !== "undefined" && T[key] != null ? t(key, vars) : fallback.replace(/\{(\w+)\}/g, (_, k) => (vars || {})[k] ?? "");
    return esc(s);
  };

  /* Background settings saved on this device keep applying (their controls left Options on 20 Nov 2026). */
  function applyBg() {
    const st = document.documentElement.style, secs = get(KEY_SECS), dim = get(KEY_DIM);
    if (secs) st.setProperty("--amb-seconds", String(parseInt(secs, 10))); else st.removeProperty("--amb-seconds");
    if (dim) st.setProperty("--amb-dim", String(parseInt(dim, 10) / 100)); else st.removeProperty("--amb-dim");
  }
  applyBg();

  /* ------------------------------------------- the Family Friendly picture -- */
  /* One square picture of a persona, Safe on one face and Unsafe on the other. Each time Options opens it picks a
     persona that has BOTH a safe and an unsafe picture tagged "nsfw-or-safe" in the Media Library (see
     Queue_Family_Flip_Pictures.bat); tapping the picture flips it and switches Family Friendly on this screen.
     Safe or unsafe is told by the NSFW flag: a picture the family-friendly library leaves out is the unsafe one. */
  const FLIP_TAG = "nsfw-or-safe";
  const pickOne = list => list[Math.floor(Math.random() * list.length)];

  async function loadFlip() {
    const current = dlg;
    let all = null, fam = null;
    try {
      [all, fam] = await Promise.all([fetch("/api/info").then(r => r.json()), fetch("/api/info?family=1").then(r => r.json())]);
    } catch (e) { /* offline: the card shows without a picture */ }
    if (!current || dlg !== current || !all || !fam) return;
    const persons = m => (m && m.items && m.items.persona) || {};
    const safeIds = new Set();
    Object.values(persons(fam.media)).forEach(list => list.forEach(it => safeIds.add(it.id)));
    const tableFam = !!(all.media && all.media.family);
    const tagged = it => it.t === "image" && (it.g || []).some(g => String(g).indexOf(FLIP_TAG) >= 0);
    const pairs = [];
    for (const [cid, list] of Object.entries(persons(all.media))) {
      const t = list.filter(tagged), safe = t.filter(it => safeIds.has(it.id)), unsafe = t.filter(it => !safeIds.has(it.id));
      if (safe.length && (unsafe.length || tableFam)) pairs.push({ cid, safe, unsafe });
    }
    if (!pairs.length) return;
    const p = pickOne(pairs), cast = (typeof VS !== "undefined" && VS.cast && VS.cast[p.cid]) || {};
    flip = { cid: p.cid, name: cast.name || "", safe: pickOne(p.safe).u, unsafe: p.unsafe.length ? pickOne(p.unsafe).u : "" };
    [flip.safe, flip.unsafe].forEach(u => { if (u) new Image().src = u; });
    draw(["table"]);
  }

  function flipFace(kind, url, side) {
    const word = kind === "safe" ? tx("opt.safe", "Safe") : tx("opt.unsafe", "Unsafe");
    return `<span class="op-flip-face op-flip-${side}">${url ? `<img src="${esc(url)}" alt="">` : `<span class="op-flip-blank"></span>`}<em class="op-flip-tag ${kind}">${word}</em></span>`;
  }

  function flipHtml(safeNow, locked) {
    const f = flip || {};
    const state = safeNow ? tx("opt.safe", "Safe") : tx("opt.unsafe", "Unsafe");
    return `<figure class="op-flip-wrap"><button type="button" class="op-flip${safeNow ? "" : " is-unsafe"}" data-op="famflip" ${locked ? "disabled" : ""} aria-pressed="${safeNow}"
        aria-label="${tx("opt.flip_label", "Family Friendly: {state}. Tap to switch.", { state })}">
        <span class="op-flip-inner">${flipFace("safe", f.safe, "front")}${locked ? "" : flipFace("unsafe", f.unsafe, "back")}</span></button>
      ${f.name ? `<figcaption>${esc(f.name)}</figcaption>` : ""}</figure>`;
  }

  /* Family Friendly on this screen, applied live: the choice is saved, the picture, switch and Safe / Unsafe word
     change at once, and the player screen re-opens its stream and fetches its info again in the new mode
     (connect and refreshInfo in player.js), so nothing reloads and Options stays open. */
  let applying = false, again = false;
  async function applyFamily() {
    try {
      if (typeof reloading !== "undefined") for (let i = 0; i < 30 && reloading; i++) await new Promise(r => setTimeout(r, 100));
      if (typeof connect === "function") connect();
      if (typeof refreshInfo === "function") await refreshInfo();
    } catch (e) { /* the next state brings the screen into line */ }
    const identity = dlg && dlg.querySelector(".op-identity");
    if (identity) identity.innerHTML = identityHtml();
  }
  function queueApply() {
    if (applying) { again = true; return; }
    applying = true;
    (async () => { do { again = false; await applyFamily(); } while (again); applying = false; })();
  }
  function setFamily(on) {
    put(KEY_FAMILY, on ? "1" : null);
    if (dlg) {
      const card = dlg.querySelector(".op-flip"), box = dlg.querySelector("[data-op=family]"), word = dlg.querySelector(".op-fam-state");
      if (card) { card.classList.toggle("is-unsafe", !on); card.setAttribute("aria-pressed", String(on)); }
      if (box) box.checked = on;
      if (word) { word.className = "op-fam-state " + (on ? "safe" : "unsafe"); word.innerHTML = on ? tx("opt.safe", "Safe") : tx("opt.unsafe", "Unsafe"); }
    }
    queueApply();
  }

  function tableHtml() {
    const tableFam = info ? info.table_family : (D && D.rating === "family" && !D.screen_family);
    const safeNow = !!(tableFam || screenFamily());
    return `<div class="op-fam"><div class="op-fam-text">
        <h4>${tx("opt.family_title", "Family Friendly")}</h4>
        <p class="op-fam-state ${safeNow ? "safe" : "unsafe"}">${safeNow ? tx("opt.safe", "Safe") : tx("opt.unsafe", "Unsafe")}</p>
        <label class="op-switch${tableFam ? " locked" : ""}">
          <input type="checkbox" data-op="family" ${safeNow ? "checked" : ""} ${tableFam ? "disabled" : ""}>
          <span>${tx("opt.family", "Family-friendly on this screen")}</span></label>
        <p class="op-note">${tableFam ? tx("opt.family_table", "Family-friendly is on for the whole table (set in Admin).")
          : tx("opt.family_note", "Hides NSFW pictures and uses the family names of cargo on this screen only. Spoken lines stay as the table has them.")}</p>
        ${tableFam ? "" : `<p class="op-hint">${tx("opt.flip_hint", "Tap the picture to switch.")}</p>`}
      </div>${flipHtml(safeNow, !!tableFam)}</div>`;
  }

  function soundHtml() {
    return typeof SeaAudio !== "undefined" && typeof SeaAudioPanel !== "undefined"
      ? SeaAudioPanel.html((k, f) => tx(k, f))
      : `<p class="op-note">${tx("snd.none", "Sound is not available on this screen.")}</p>`;
  }

  function section(id, title, body) {
    return `<section class="op-sec op-${id}" id="op-panel-${id}" role="tabpanel" aria-labelledby="op-tab-${id}" tabindex="0" ${id === page ? "" : "hidden"}><h3>${title}</h3><div data-sec="${id}">${body}</div></section>`;
  }

  function personaHtml() {
    const entry = mayors[mayorIndex];
    if (!entry) return "";
    const [portId, port] = entry, who = VS.cast[port.officer];
    const art = Media.html("persona", port.officer, "portrait", "op-persona-image", who.portrait || "", { mode: "fixed", strict: true, slot: "options-mayor" });
    const welcomes = {
      hongkong: "Welcome to Hong Kong, Captain {name}. May our harbour be the beginning of a prosperous voyage.",
      shanghai: "Welcome to Shanghai, Captain {name}. Our busy wharves have room for you and your ambitions.",
      nagasaki: "Welcome to Nagasaki, Captain {name}. May you find good company and fair trade beside our sheltered waters.",
      manila: "Welcome to Manila, Captain {name}. A warm harbour and a world of opportunity await you here.",
      saigon: "Welcome to Saigon, Captain {name}. Come ashore and enjoy the hospitality of our river port.",
      bangkok: "Welcome to Bangkok, Captain {name}. May the river bring you good fortune and lasting friendships.",
      singapore: "Welcome to Singapore, Captain {name}. The world's sea roads meet here, and we are delighted you have joined us.",
      batavia: "Welcome to Batavia, Captain {name}. May your stay be pleasant and your holds leave full of promise.",
      calcutta: "Welcome to Calcutta, Captain {name}. Our river is your road to new friends and flourishing trade.",
      foochow: "Welcome to Foochow, Captain {name}. May our tea country and welcoming quays reward your journey.",
    };
    return `<figure class="op-persona">${art}<figcaption><span>${tx("opt.mayor", "Mayor of {port}", { port: port.name })}</span>
      <strong>${esc(who.name)}</strong></figcaption></figure>
      <div class="op-welcome"><p>${tx("opt.welcome." + portId, welcomes[portId] || "Welcome to {port}, Captain {name}. May your visit bring good friends and fair trade.", { port: port.name, name: S.me.name })}</p></div>`;
  }

  function identityHtml() {
    const me = (S && S.me) || {}, faces = Faces.of(me);
    const portrait = info && (info.portraits || []).find(p => p.primary && !(screenFamily() && p.nsfw));
    const url = portrait ? portrait.url : faces.portrait;
    return `<figure class="op-persona">${url ? `<img class="op-persona-image" src="${esc(url)}" alt="">` : ""}<figcaption><span>${tx("opt.captain", "My Captain")}</span>
      <strong>${esc((info && info.captain && info.captain.name) || me.name || "")}</strong></figcaption></figure>
      <div class="op-welcome"><span class="op-eyebrow">${tx("opt.house", "My House")}</span><p>${esc((info && info.house && info.house.name) || me.firm || "")}</p></div>`;
  }

  function selectPage(id) {
    page = id;
    dlg.querySelectorAll("[data-page]").forEach(b => {
      const active = b.dataset.page === id;
      b.setAttribute("aria-selected", String(active)); b.tabIndex = active ? 0 : -1;
    });
    dlg.querySelectorAll("[role=tabpanel]").forEach(p => { p.hidden = p.id !== "op-panel-" + id; });
    dlg.querySelector(".op-body").scrollTop = 0;
  }

  function draw(only) {
    if (!dlg) return;
    const parts = { table: tableHtml, sound: soundHtml };
    for (const k of only || Object.keys(parts)) {
      const el = dlg.querySelector(`[data-sec="${k}"]`);
      if (!el) continue;
      const html = parts[k]();
      if (el.dataset.html !== html) { el.innerHTML = html; el.dataset.html = html; }
    }
  }

  async function load() {
    const current = dlg;
    try {
      const r = await fetch("/api/options?token=" + encodeURIComponent(token || ""));
      const res = await r.json();
      if (!current || dlg !== current) return;
      if (res.ok) info = res;
    } catch (e) { /* offline: keep what we have */ }
    if (dlg !== current) return;
    draw(["table"]);
    const identity = dlg && dlg.querySelector(".op-identity");
    if (identity) identity.innerHTML = identityHtml();
  }

  function onClick(e) {
    const nav = e.target.closest("[data-page]");
    if (nav) return selectPage(nav.dataset.page);
    const b = e.target.closest("[data-op]");
    if (!b || b.tagName === "FORM" || b.tagName === "INPUT") return;
    const op = b.dataset.op;
    if (op === "close") return close();
    if (op === "famflip") {
      if (!b.disabled) setFamily(!screenFamily());       // back and forth on every tap
      return;
    }
    if (op.indexOf("snd_") === 0) {          // the Sound tab's own buttons (Test, Full/Brief dialogue)
      if (typeof SeaAudioPanel !== "undefined" && SeaAudioPanel.click(e) && op === "snd_brief") draw(["sound"]);
    }
  }

  function onInput(e) {
    const el = e.target, op = el.dataset && el.dataset.op;
    if (el.dataset && el.dataset.snd) { if (typeof SeaAudioPanel !== "undefined") SeaAudioPanel.input(e); return; }
    if (op === "family" && e.type === "change") {
      setFamily(el.checked);
    }
  }

  function open() {
    if (dlg) return;
    info = null; flip = null; page = "table"; opener = document.activeElement;
    mayors = Object.entries(D.ports || {}).filter(([, p]) => p.officer && VS.cast && VS.cast[p.officer]);
    mayorIndex = Math.floor(Math.random() * mayors.length);
    dlg = document.createElement("dialog");
    dlg.className = "op";
    dlg.setAttribute("aria-labelledby", "op-title");
    dlg.innerHTML = `<div class="op-card">
      <header class="op-head"><div><p class="op-eyebrow">${esc(typeof brandName === "function" && D && D.brand ? brandName(D.brand) : "")}</p>
        <h2 id="op-title">${tx("opt.eyebrow", "The Captain's Options")}</h2></div>
        <button type="button" class="op-x" data-op="close" aria-label="${tx("opt.close", "Close")}">&times;</button></header>
      <aside class="op-companion">${personaHtml()}</aside>
      <div class="op-workspace"><aside class="op-identity">${identityHtml()}</aside>
      <div class="op-settings"><nav class="op-nav" role="tablist" aria-label="${tx("opt.eyebrow", "The Captain's Options")}">
      ${[["table", "opt.table", "Table settings"], ["sound", "opt.sound", "Sound"]].map(([id, key, label]) => `<button type="button" role="tab" id="op-tab-${id}" aria-controls="op-panel-${id}" aria-selected="${id === page}" aria-label="${tx(key, label)}" title="${tx(key, label)}" tabindex="${id === page ? 0 : -1}" data-page="${id}"><svg viewBox="0 0 24 24" aria-hidden="true">${ICONS[id]}</svg></button>`).join("")}</nav>
      <div class="op-body">
        ${section("table", tx("opt.table", "Table settings"), "")}
        ${section("sound", tx("opt.sound", "Sound"), "")}
      </div></div></div>
    </div>`;
    dlg.addEventListener("click", e => { if (e.target === dlg) close(); else onClick(e); });
    dlg.addEventListener("input", onInput);
    dlg.addEventListener("change", onInput);
    dlg.addEventListener("keydown", e => {
      if (!e.target.matches("[role=tab]") || !["ArrowLeft", "ArrowRight", "Home", "End"].includes(e.key)) return;
      e.preventDefault();
      const tabs = [...dlg.querySelectorAll("[role=tab]")], i = tabs.indexOf(e.target);
      const next = e.key === "Home" ? 0 : e.key === "End" ? tabs.length - 1 : (i + (e.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
      selectPage(tabs[next].dataset.page); tabs[next].focus();
    });
    dlg.addEventListener("close", () => { if (dlg) close(); });
    document.body.appendChild(dlg);
    draw();
    dlg.showModal();
    load();
    loadFlip();
    if (mayors.length > 1) mayorTimer = setInterval(() => {
      mayorIndex = (mayorIndex + 1) % mayors.length;
      dlg.querySelector(".op-companion").innerHTML = personaHtml();
    }, 12000);
  }

  function close() {
    clearInterval(mayorTimer);
    const d = dlg;
    dlg = null;
    if (d) { try { if (d.open) d.close(); } catch (e) { /* ignore */ } d.remove(); }
    if (typeof render === "function") render();
    const focus = opener && opener.isConnected && opener !== document.body ? opener : document.querySelector('[data-act="me"]');
    if (focus) focus.focus({ preventScroll: true });
  }

  return { open, close, isOpen: () => !!dlg };
})();
