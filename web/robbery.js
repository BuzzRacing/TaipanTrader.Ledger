"use strict";

/* The Robbery Story (owner's request, 22 Nov 2026: "a quick Robbery Story ... one screen for the robbery, the persona
   and what was taken, and then back to the game ... I like seeing them and I like the personas' verve").

   ONE screen, no choices, no game time. Magpie (the Thieves, cast key "thieves") is big on the left over the port
   where it happened, in a face that changes every few seconds (her whole Media Library deck, as the Jail Story's
   speakers do), and says her own line aloud (the log's l.robbed for the street, l.wh_robbed for the warehouse, found
   by the server in S.voice.robbery). On the right is a rough loss report: a caption, WHAT WAS TAKEN (the silver
   from the purse, or the goods from the godown with their worth), and "Back to the game", which sends robbery_ack.

   THE SERVER DECIDES WHETHER THERE IS A STORY (robbery.py): only when the month has no other story (no Sea Battle, jail,
   storm, Legend, honour story or promotion). Otherwise the robbery stays a line in the Captain's Log and S.me.robbery
   is empty, so this file never has to guess. The Captain's Log reading skips Magpie's line while this is waiting or
   open (player.js speak()), because the screen says it itself.

   Reads S.me.robbery and S.voice.robbery; called from player.js render() as Robbery.sync(inGame, canShow).
   canShow is false while a sea battle, jail, storm or Legend, or the Port Authority desk, has the floor: the story
   waits and opens when they are gone. A card already told on this page (a reload) opens without her voice. */
const Robbery = (() => {
  let screen = null, story = null, armTimer = null, swapTimer = null, busy = false;
  let face = null;                              // Magpie's deck: {deck, i}
  let last = { inGame: false, canShow: false };

  const ARM_MS = 1200;                          // a beat before "Back to the game" can be pressed
  const SWAP_MS = 3500;                         // her face changes this often
  const TOLD_KEY = "seatrader_robbery_told";
  const WHO = "thieves";
  const MOODS = ["sly", "happy", "speaking", "idle", "angry"];
  let told = new Set();
  try { told = new Set(JSON.parse(sessionStorage.getItem(TOLD_KEY) || "[]")); } catch (e) { /* a fresh page */ }
  const remember = key => {
    told.add(key);
    try { sessionStorage.setItem(TOLD_KEY, JSON.stringify(Array.from(told).slice(-40))); } catch (e) { /* memory only */ }
  };

  const castOf = cid => (typeof VS !== "undefined" && VS && VS.cast && VS.cast[cid]) || {};
  const portName = k => (D.ports && D.ports[k] && D.ports[k].name) || k;
  const goodName = g => (D.goods && D.goods[g] && D.goods[g].name) || g;
  const tl = (key, fb, vars) => (T[key] == null ? esc(t(fb, vars)) : te(key, vars));
  const hash = s => { let h = 7; for (const c of String(s)) h = (h * 31 + c.charCodeAt(0)) >>> 0; return h; };
  /* one line of a bank (rob.cap.street.0, .1, ...), chosen from a seed so a redraw never changes it */
  function bankLine(prefix, seed, vars) {
    const keys = Object.keys(T).filter(k => k.startsWith(prefix + ".") && T[k] != null && String(T[k]).trim()).sort();
    if (!keys.length) return "";
    return te(keys[hash(seed) % keys.length], vars);
  }

  /* ---- pictures ---------------------------------------------------------------------------------------- */
  const hasRole = (i, r) => (i.r || []).includes(r);
  const clean = i => (i.g || []).includes("clean");
  const shuffle = a => { const r = a.slice(); for (let i = r.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [r[i], r[j]] = [r[j], r[i]]; } return r; };
  /* Everything she has in the Media Library, dealt round-robin across her moods so two faces in a row are never the
     same mood or the same picture; stills and clips together ("Images only" in Options leaves the clips out). */
  function faceDeck(avoidId) {
    const all = Media.items("persona", WHO, "", true);
    const lists = MOODS.map(m => shuffle(all.filter(i => hasRole(i, m))));
    const seen = new Set(), deck = [];
    const add = i => { if (i && !seen.has(i.id)) { seen.add(i.id); deck.push(i); } };
    for (let k = 0, more = true; more; k++) {
      more = false;
      lists.forEach(l => { if (k < l.length) { more = true; add(l[k]); } });
    }
    shuffle(all.filter(i => hasRole(i, "portrait") || !(i.r || []).length)).forEach(add);
    const bare = deck.filter(i => !clean(i));          // the clean copy of a nude photo is for family screens
    const out = bare.length >= 3 ? bare : deck;
    if (out.length > 1 && avoidId && out[0].id === avoidId) out.push(out.shift());
    return out;
  }
  function faceMarkup(item) {
    if (!item) return "";
    if (item.t === "video") {
      return `<video class="rb-face rb-clip" src="${esc(item.u)}"${item.po ? ` poster="${esc(item.po)}"` : ""} muted autoplay loop playsinline preload="auto" disablepictureinpicture></video>`;
    }
    return `<img class="rb-face" src="${esc(item.u)}" alt="">`;
  }
  function showFace(i) {
    if (!face || !face.deck.length || !screen) return;
    face.i = ((i % face.deck.length) + face.deck.length) % face.deck.length;
    const host = screen.querySelector(".rb-who");
    if (!host) return;
    const old = host.querySelector(".rb-face");
    const html = faceMarkup(face.deck[face.i]);
    if (old) old.insertAdjacentHTML("afterend", html); else host.insertAdjacentHTML("afterbegin", html);
    const fresh = old ? old.nextElementSibling : host.firstElementChild;
    if (fresh && fresh.classList) fresh.classList.add("rb-in");
    if (old) setTimeout(() => old.remove(), 900);
  }
  function startSwap() {
    if (swapTimer) return;
    swapTimer = setInterval(() => { if (!document.hidden && face && face.deck.length > 1) showFace(face.i + 1); }, SWAP_MS);
  }
  function sceneUrl(port) {
    const item = Media.choose("port", port, "night", { slot: "robbery-scene-night" })
      || Media.choose("port", port, "banner", { slot: "robbery-scene" });
    return (item && item.t === "image" && item.u) || "";
  }

  /* ---- what the screen says ----------------------------------------------------------------------------- */
  const SAY_ICON = `<svg viewBox="0 0 40 40" aria-hidden="true"><circle class="rb-say-ring" cx="20" cy="20" r="17"/><path class="rb-say-horn" d="M10 17h5l7-6v18l-7-6h-5z"/><path class="rb-say-wave" d="M26 15q5 5 0 10M30 11q9 9 0 18"/></svg>`;
  const PURSE = `<svg viewBox="0 0 48 52" aria-hidden="true"><path d="M17 12c0-4 2.5-6 7-6s7 2 7 6"/><path d="M14 16h20l5 7c3 6 1 17-6 21H15c-7-4-9-15-6-21z"/><path d="M19 28c2 3 8 3 10 0M24 20v4" opacity=".7"/></svg>`;
  const CRATE = `<svg viewBox="0 0 48 52" aria-hidden="true"><path d="M6 20 24 10l18 10v22L24 50 6 42z"/><path d="M6 20l18 10 18-10M24 30v20"/><path d="M13 16l17 9" opacity=".6"/></svg>`;
  const tile = (label, value, cls) => `<div class="${cls || ""}"><small>${label}</small><b>${value}</b></div>`;

  function sayOf() {
    const v = (typeof S !== "undefined" && S && S.voice && S.voice.robbery) || null;
    return v || null;
  }
  function cardHtml(r) {
    const port = portName(r.port), house = r.kind === "house";
    const vars = { port };
    const cap = bankLine(house ? "rob.cap.house" : "rob.cap.street", "R" + r.id + "|" + r.turn, vars);
    let rows = "", taken = "", net = "";
    if (house) {
      const goods = Object.keys(r.goods || {}).filter(g => r.goods[g] > 0);
      rows = tile(tl("rob.tile.units", "Units carried off"), (r.qty || 0).toLocaleString("en-US"), "dn")
        + (r.pct ? tile(tl("rob.tile.share", "Of the stock"), r.pct + "%", "gold") : "");
      taken = goods.map(g => `<li><span>${esc(goodName(g))}</span><em class="dn">−${(r.goods[g]).toLocaleString("en-US")}</em></li>`).join("");
      net = `<p class="rb-net dn"><span>${tl("rob.tile.value", "Worth, at cost")}</span><b>−${money(r.value || 0)}</b></p>`;
    } else {
      taken = `<li><span>${tl("rob.silver_purse", "Silver, from your purse")}</span><em class="dn">−${money(r.silver || r.value || 0)}</em></li>
        <li><span>${tl("rob.tile.left", "Silver left in hand")}</span><em>${money(r.left || 0)}</em></li>
        <li class="none"><span>${tl("rob.feather", "She left a peacock feather where it was.")}</span></li>`;
      net = `<p class="rb-net dn"><span>${tl("rob.tile.silver", "Silver taken")}</span><b>−${money(r.silver || r.value || 0)}</b></p>`;
    }
    const tip = house ? "" : `<p class="rb-tip">${tl("rob.tip.street", "Silver in the bank cannot be lifted from a pocket.")}</p>`;
    return `<section class="rb-report rb-card o-robbed${house ? " house" : ""}" role="dialog" aria-modal="true" aria-labelledby="rb-title">
        <header><p class="eyebrow">${te(house ? "rob.eyebrow.house" : "rob.eyebrow.street", vars)}</p>
          <div class="rb-heading"><span class="rb-emblem" aria-hidden="true">${house ? CRATE : PURSE}</span><h2 id="rb-title">${te(house ? "rob.title.house" : "rob.title.street")}</h2></div>
          ${cap ? `<p class="rb-reason">${cap}</p>` : ""}</header>
        ${net}
        <div class="rb-evidence">${rows ? `<div class="rb-rows">${rows}</div>` : ""}
        <div class="rb-taken"><h3>${tl("rob.taken", "What was taken")}</h3><ul class="rb-cargo">${taken}</ul>${tip}</div>
        </div>
        <footer>
          <button type="button" class="rb-go" disabled>${tl("rob.btn", "Back to the game")} <span aria-hidden="true">&rarr;</span></button>
        </footer>
      </section>`;
  }
  /* The quote stays directly on the portrait; no identity plaque. */
  function whoHtml(line) {
    const who = castOf(WHO);
    const text = line || who.catchphrase || "";
    const first = face && face.deck[0] ? faceMarkup(face.deck[0]).replace('class="rb-face', 'class="rb-face rb-in')
      : who.portrait ? `<img class="rb-face" src="${esc(who.portrait)}" alt="">` : "";
    return `<figure class="rb-persona rb-who${first ? "" : " nopic"}" style="--who:${esc(who.color || "var(--deck-brass)")}">${first}
        <figcaption class="rb-quote rb-line">
          ${text ? `<p>“${esc(text)}”</p>` : ""}
          <button type="button" class="rb-say" data-say aria-label="${esc(tl("rob.hear", "Hear her again"))}">${SAY_ICON}</button>
        </figcaption>
      </figure>`;
  }

  /* ---- speaking ------------------------------------------------------------------------------------------ */
  function say() {
    const v = sayOf();
    if (!(v && v.clip && typeof Voice !== "undefined" && Voice.enabled() && !Voice.muted())) return;
    Voice.say([Object.assign({ tag: "robbery:" + story.key, text: v.text }, v.clip)], { group: "robbery", front: true });
  }

  /* ---- the screen ---------------------------------------------------------------------------------------- */
  function build(r) {
    const line = (sayOf() || {}).text || "";
    face = { deck: faceDeck(""), i: 0 };
    screen = document.createElement("div");
    screen.id = "robbery-screen";
    screen.className = "rb-screen" + (r.kind === "house" ? " rb-house" : " rb-street");
    const bg = sceneUrl(r.port);
    screen.innerHTML = `<div class="rb-bg"${bg ? ` style="background-image:url('${esc(bg)}')"` : ""}></div><div class="rb-shade"></div>
      <div class="rb-layout rb-result">${whoHtml(line)}${cardHtml(r)}</div>`;
    screen.addEventListener("click", e => {
      const b = e.target.closest(".rb-go");
      if (b) { if (!b.disabled) press(b); return; }
      if (e.target.closest("[data-say]")) say();
    });
    document.body.appendChild(screen);
    document.body.classList.add("in-robbery");
    startSwap();
  }
  function arm() {
    const b = screen && screen.querySelector(".rb-go");
    if (!b) return;
    b.disabled = Date.now() - story.openedAt < ARM_MS;
    if (b.disabled) { clearTimeout(armTimer); armTimer = setTimeout(arm, ARM_MS + 50 - (Date.now() - story.openedAt)); }
    else if (!busy) { try { b.focus({ preventScroll: true }); } catch (e) { /* no focus */ } }
  }
  async function press(btn) {
    if (busy || !story) return;
    busy = true;
    btn.disabled = true;
    const ok = await act("robbery_ack", {});
    busy = false;
    if (!ok && btn.isConnected) btn.disabled = false;
  }
  function teardown() {
    clearTimeout(armTimer);
    clearInterval(swapTimer); swapTimer = null;
    if (story && typeof Voice !== "undefined") Voice.drop("robbery");
    story = null; face = null;
    if (screen) { screen.remove(); screen = null; }
    document.body.classList.remove("in-robbery");
  }

  function sync(inGame, canShow) {
    last = { inGame, canShow };
    const r = inGame && S && S.me && S.phase !== "lobby" && S.me.robbery;
    if (!r) { if (screen) teardown(); return; }
    if (!screen && !canShow) return;                      // wait for the sea battle, jail, storm, Legend or desk to be gone
    const key = ["R", S.game_id || "", r.id, r.turn].join("|");
    if (story && story.key === key) return;
    if (screen) teardown();
    story = { key, openedAt: Date.now() };
    build(r);
    if (!told.has(key)) { remember(key); say(); }         // a reload shows the card without repeating her voice
    arm();
  }

  const pending = () => !!(typeof S !== "undefined" && S && S.me && S.me.robbery);
  /* busy: the screen is open (others wait). pending: the story exists, open or waiting (the log leaves her line out). */
  return { sync, busy: () => !!screen, telling: () => !!screen, pending };
})();
