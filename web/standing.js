"use strict";

/* The Standing Story (Nov 2026): "Your name has risen / fallen", redone. It replaces the small band-change card
   that player.js used to draw (syncBands, muted 20 Nov 2026 by rules.standing.popup) and is told on a full screen
   like the Promotion Story, the Jail Story and the Storm card: the port's Mayor, big, is the picture behind, and the
   data lies over it (the five heat bands with a pin that slides from the old band to the new, the new band's name,
   why it moved and what the band now means).

   WHY THE OLD CARD WAS WRONG, AND WHAT THIS DOES INSTEAD
   - It came from nowhere: it opened whenever the port screen was up and any band move was unseen, with no check for
     other popups, a voice mid-line or the Captain still tapping about. Now it opens only at a quiet moment:
       * player.js says no sea battle, jail, storm, Legend, promotion, desk overlay or Captain's Log has the floor;
       * no <dialog> is open, no ceremony, no other full-screen story, the Port Authority desk is shut;
       * no voice is speaking, and the Captain has not touched the screen for IDLE_MS (never mid-trade);
       * all of that has held for SETTLE_MS, so it never lands the instant another screen closes.
     Anything else that arrives in the meantime simply waits; a new move redraws the page and asks again.
   - It fired too often: every band crossing was its own card, so a price hovering at a band's edge popped one each
     trade. Now the unseen moves are folded per port (first "from" to last "to"; a move that ended where it began is
     marked seen without a word), told as ONE story with the headline move large and the others listed, and a
     further story waits COOLDOWN_MS after the last was closed.
   - It was a small card. Now it is a screen: the Mayor's whole picture, large (stills only, never a mood picture;
     her "congratulations" picture for a rise into Warm or Favoured).

   It reads S.me.bands (server: engine._band_crossed; only sent while rules.standing.popup is on, so that switch,
   Admin > Rules > "Standing: the five bands and their luck", still mutes it). The Captain's Log still reads a fall
   into Hostile or a rise into Favoured aloud when she arrives; this story comes after the log is closed, so it adds
   no voice of its own. Seen moves are remembered per game and house (localStorage, memory when that fails).
   Browser only: no server, config or strings change (the wording is the existing band.* bank, with fallbacks).
   Called from player.js render() as Standing.sync(inGame, canShow). */
const Standing = (() => {
  const BANDS = ["hostile", "cool", "neutral", "warm", "favoured"];
  const SETTLE_MS = 1800;       // quiet must have held this long before it opens
  const IDLE_MS = 2500;         // the Captain has not touched the screen for this long
  const COOLDOWN_MS = 60000;    // after one is closed, the next waits at least this long
  const ARM_MS = 1200;          // a beat before "Understood" can be pressed
  const POLL_MS = 500;

  let screen = null, story = null, armTimer = null, pollTimer = null;
  let last = { inGame: false, canShow: false };
  let quietSince = 0, closedAt = 0, lastInput = 0;

  /* ---- what the Captain has touched lately ------------------------------------------------------------- */
  ["pointerdown", "keydown", "wheel", "touchstart"].forEach(ev =>
    document.addEventListener(ev, () => { lastInput = Date.now(); }, { passive: true, capture: true }));

  /* ---- seen moves ---------------------------------------------------------------------------------------- */
  const seen = (() => {
    let mem = {};
    const key = () => "ct.bands." + ((S && S.game_id) || "") + "." + ((S && S.me && S.me.id) || "");
    const load = () => { try { return JSON.parse(localStorage.getItem(key()) || "{}") || {}; } catch (e) { return mem; } };
    return {
      has: id => !!load()[id],
      add: ids => {
        const all = load();
        ids.forEach(id => { all[id] = 1; });
        mem = all;
        try { localStorage.setItem(key(), JSON.stringify(all)); } catch (e) { /* memory only */ }
      }
    };
  })();

  const portName = k => (D.ports && D.ports[k] && D.ports[k].name) || k;
  const tl = (key, fb, vars) => (T[key] == null ? esc(t(fb, vars)) : te(key, vars));
  const castOf = cid => (typeof VS !== "undefined" && VS && VS.cast && VS.cast[cid]) || {};
  const heat = i => (typeof standingHeat === "function" ? standingHeat(i) : "var(--deck-brass)");
  const bandWord = i => te("stat.standing_" + BANDS[i]);

  /* ---- folding the unseen moves into one story ------------------------------------------------------------ */
  /* Per port: the first "from" to the last "to". Returns { fold: [..net moves..], ids: [every unseen id] }. */
  function unseenMoves() {
    const raw = ((S.me && S.me.bands) || []).filter(e => e && !seen.has(e.id)).sort((a, b) => a.id - b.id);
    const ids = raw.map(e => e.id);
    const byPort = new Map();
    raw.forEach(e => {
      const cur = byPort.get(e.port);
      if (!cur) byPort.set(e.port, { port: e.port, from: e.from, to: e.to, rep: e.rep, why: e.why, id: e.id, steps: 1, jump: Math.abs(e.to - e.from) });
      else {
        cur.to = e.to; cur.rep = e.rep; cur.id = e.id; cur.steps += 1;
        // the reason shown is the one that did the most: the biggest single jump, the newest on a tie
        const j = Math.abs(e.to - e.from);
        if (j >= cur.jump) { cur.why = e.why; cur.jump = j; }
      }
    });
    const fold = Array.from(byPort.values()).filter(m => m.to !== m.from);
    return { fold, ids, quiet: raw.filter(e => !fold.some(m => m.port === e.port)).map(e => e.id) };
  }

  /* ---- pictures --------------------------------------------------------------------------------------------- */
  /* A clip of the Mayor is chosen as often as the persona rule's video chance allows (Media.pickFace, the Captain
     screen's rule); "Images only" leaves the clips out. Returns an item, her cast portrait as an item, or null. */
  function mayorArt(port, rose, to) {
    const tagged = role => Media.items("port", port, role, true).filter(i => i.r.includes(role));
    const pick = (rose && to >= 3 ? Media.pickFace(tagged("mayor_congrats"), "mayor") : null)
      || Media.pickFace(tagged("mayor"), "mayor")
      || Media.choose("port", port, "mayor", { strict: true, slot: "band" });
    if (pick) return pick;
    const portrait = castOf("mayor").portrait;
    return portrait ? { t: "image", u: portrait, id: "cast-portrait" } : null;
  }

  /* ---- the screen ------------------------------------------------------------------------------------------- */
  function whyText(why) {
    const w = String(why || "");
    if (T["band.why." + w] != null) return te("band.why." + w);
    const stem = w.replace(/_word$/, "");
    return T["band.why." + stem] != null ? te("band.why." + stem) : te("band.why.other");
  }

  function ladderHtml(m) {
    const rose = m.to > m.from;
    const cells = BANDS.map((b, i) => {
      const cls = [i === m.to ? "now" : "", i === m.from ? "was" : ""].filter(Boolean).join(" ");
      return `<li class="${cls}" style="--heat:${heat(i)}"><i></i><span>${esc(bandWord(i))}</span></li>`;
    }).join("");
    const pct = i => (i * 20 + 10);
    return `<ol class="st-ladder" style="--from:${pct(m.from)}%;--to:${pct(m.to)}%" aria-label="${te("band.title", { port: esc(portName(m.port)) })}">
        ${cells}<span class="st-pin ${rose ? "up" : "down"}" aria-hidden="true"></span></ol>`;
  }

  function build(m, others, ids, key) {
    const rose = m.to > m.from, port = portName(m.port), band = BANDS[m.to];
    const art = mayorArt(m.port, rose, m.to);
    const mayorLabel = te("fleet.promotion_mayor", { port });
    const who = castOf("mayor");
    screen = document.createElement("div");
    screen.id = "standing-screen";
    screen.className = "st-screen " + (rose ? "rose" : "fell") + " to-" + band + (art ? "" : " nopic");
    screen.style.setProperty("--heat", heat(m.to));
    screen.setAttribute("role", "dialog");
    screen.setAttribute("aria-modal", "true");
    screen.setAttribute("aria-labelledby", "st-title");
    screen.innerHTML = `
      <div class="st-bg" aria-hidden="true">${art ? Media.faceMarkup(art, "") : ""}<div class="st-shade"></div></div>
      <figure class="st-plate"><b>${mayorLabel}</b>${who.name ? `<span>${esc(who.name)}</span>` : ""}</figure>
      <section class="st-data">
        <p class="st-eyebrow">${te("band.title", { port: esc(port) })}</p>
        <h2 id="st-title">${te(rose ? "band.rose" : "band.fell")}</h2>
        <p class="st-now">${te("band.now", { port: esc(port) })}</p>
        <p class="st-word"><strong>${esc(bandWord(m.to))}</strong><em>${Math.round(m.rep)}</em></p>
        ${ladderHtml(m)}
        <p class="st-was">${esc(bandWord(m.from))} <span aria-hidden="true">${rose ? "&uarr;" : "&darr;"}</span> ${esc(bandWord(m.to))}</p>
        <p class="st-why">${whyText(m.why)}</p>
        <p class="st-effect">${te("band.effect." + m.to)}</p>
        ${others.length ? `<ul class="st-others">${others.map(e => `<li style="--heat:${heat(e.to)}"><b>${esc(portName(e.port))}</b> ${esc(bandWord(e.from))} <span aria-hidden="true">${e.to > e.from ? "&uarr;" : "&darr;"}</span> ${esc(bandWord(e.to))}</li>`).join("")}</ul>` : ""}
        <button type="button" class="primary st-ok" disabled>${te("band.ok")}</button>
      </section>`;
    const ok = screen.querySelector(".st-ok");
    ok.addEventListener("click", () => { if (!ok.disabled) close(); });
    screen.addEventListener("keydown", e => { if (e.key === "Escape") { e.preventDefault(); if (!ok.disabled) close(); } });
    document.body.appendChild(screen);
    document.body.classList.add("in-standing");
    story = { key, ids, born: Date.now() };
    clearTimeout(armTimer);
    armTimer = setTimeout(() => { if (screen && story && story.key === key) { ok.disabled = false; ok.focus({ preventScroll: true }); } }, ARM_MS);
    // the pin slides on the next frame so the move is seen, not just the end state
    requestAnimationFrame(() => requestAnimationFrame(() => { if (screen) screen.classList.add("go"); }));
  }

  function teardown() {
    clearTimeout(armTimer);
    story = null;
    if (screen) { screen.remove(); screen = null; }
    document.body.classList.remove("in-standing");
  }

  function close() {
    if (!story) return;
    seen.add(story.ids);
    closedAt = Date.now();
    teardown();
    render();
  }

  /* ---- the quiet moment ------------------------------------------------------------------------------------ */
  function elsewhere() {
    // a popup, the ceremony, the Captain's Log, another full-screen story or the Port Authority desk has the floor
    if (document.querySelector("dialog[open], .ceremony, .captains-log")) return true;
    if (Array.from(document.body.classList).some(c => /^in-/.test(c) && c !== "in-standing")) return true;
    if (typeof Customs !== "undefined" && Customs.isOpen && Customs.isOpen()) return true;
    // (top-level const modules are not window properties, so each is named directly)
    if ((typeof Battle !== "undefined" && Battle.busy()) || (typeof Jail !== "undefined" && Jail.busy())
      || (typeof Storm !== "undefined" && Storm.busy()) || (typeof Legend !== "undefined" && Legend.busy())
      || (typeof Promotion !== "undefined" && Promotion.busy())) return true;
    const line = typeof Voice !== "undefined" && Voice.current ? Voice.current() : null;
    return !!line;
  }

  function again() {
    clearTimeout(pollTimer);
    pollTimer = setTimeout(() => { if (typeof S !== "undefined" && S) sync(last.inGame, last.canShow); }, POLL_MS);
  }

  function sync(inGame, canShow) {
    if (typeof S === "undefined" || typeof D === "undefined" || !S || !D) return;
    last = { inGame, canShow };
    clearTimeout(pollTimer);
    const m = canShow && S.me ? unseenMoves() : null;
    // moves that ended where they began, or that nobody will be told about, are marked seen in silence
    if (m && m.quiet.length) seen.add(m.quiet);
    if (!m || !m.fold.length) { quietSince = 0; if (screen) teardown(); return; }
    // already on screen: keep it (a new move waits for the next story) unless something else takes the floor
    if (screen && story) {
      if (!canShow) teardown(); else return;
    }
    const now = Date.now();
    if (elsewhere() || now - lastInput < IDLE_MS || now - closedAt < COOLDOWN_MS) { quietSince = 0; return again(); }
    if (!quietSince) quietSince = now;
    if (now - quietSince < SETTLE_MS) return again();
    // the headline: a move in the port the house is in, the biggest band jump first, then the newest
    const here = m.fold.filter(e => e.port === S.me.port);
    const pool = here.length ? here : m.fold;
    const top = pool.slice().sort((a, b) => Math.abs(b.to - b.from) - Math.abs(a.to - a.from) || b.id - a.id)[0];
    const others = m.fold.filter(e => e !== top).sort((a, b) => b.id - a.id);
    build(top, others, m.ids, S.game_id + ":" + m.ids.join(","));
    quietSince = 0;
  }

  const busyNow = () => !!screen;
  return { sync, busy: busyNow, telling: busyNow };
})();
