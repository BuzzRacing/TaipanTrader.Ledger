"use strict";

/* The Promotion Story (owner's decision, 20 Nov 2026: "Promotion needs to be changed to a Story style ... its own
   Story version, the Promotion Story"). It replaces the letter-of-commission popup that player.js used to draw,
   and follows the Jail Story (jail.js) and the Sea Battle: large-screen story screens, one idea each, the figures
   only at the end on the Reckoning's own card.

   (23 Nov 2026: screen 4 is now a certificate from the Mayor, with her name in white on her picture, parchment,
   lettering, a personal word from her, a wax seal and the Key to the Port, filling only the right half.)

   A promotion is four screens:
     1. SUMMONED: the Mayor of the port where the commission is given, big on the left over the port's picture,
        and a large caption about being sent for.
     2. THE RANK: the new rank's seal is stamped (sunburst, gleam), the rank in the game-title lettering,
        "previous > new", and a caption. The rank ladder runs along the top, one tick per rank.
     3. HER WORDS: the Mayor's congratulations (m.promote.N, chosen by engine._promote and stored as promotion.text)
        large on the screen while she says them. It moves on when her line has been said.
     4. THE COMMISSION: the Reckoning-style card over the last picture. "By order of the Mayor of {port}", the new
        rank, who is commissioned, the figures (net worth, ships, voyages, battles or ports), the citation, the
        road ahead (the ladder and the next commission), her signature and "Accept the commission".
   Screens 1 to 3 move on by themselves when the caption has been read or her line has been said (a tap moves them
   sooner); screen 4 waits for the Captain, and its button arms after a moment.

   It opens only at a quiet moment (no other popup open, no other voice mid-line, and player.js says nothing else
   such as a sea battle, jail, storm or Legend has the floor) and, while it is open, only the Mayor is heard
   (Voice.only("promotion")); everything else waits and is read afterwards. Seen stories are remembered in
   sessionStorage so a reload goes straight to the card. Reads S.me.promotion and S.voice.promotion; called from
   player.js render() through syncPromotion().  Browser only: no server change. */
const Promotion = (() => {
  let screen = null, story = null, busy = false, armTimer = null;
  let last = { inGame: false, canShow: false };
  let waitKey = null, waitSince = 0, waitTimer = null;

  /* There is no rubber-stamp clip in the pack yet (Sound Effects Mapping, gap 1), so the seal lands with the
     ledger's heavy close. Name another catalog event here once a real stamp is converted. */
  const STAMP_CUE = "ledger.close";
  const ARM_MS = 1500;                          // a beat before the card's button can be pressed
  const TAP_AFTER_MS = 900;                     // a tap cannot skip a screen before it has had this long
  const MIN_BEAT_MS = 3400, PER_CHAR_MS = 40;   // a caption stays at least this long, plus reading time
  const VOICE_START_MS = 5000;                  // a line that has not started by now is not coming
  const MAX_BEAT_MS = 16000, AFTER_VOICE_MS = 900;
  const QUIET_MS = 8000;                        // waits at most this long for another voice to finish
  const TOLD_KEY = "seatrader_promo_told";
  let told = new Set();
  try { told = new Set(JSON.parse(sessionStorage.getItem(TOLD_KEY) || "[]")); } catch (e) { /* a fresh page */ }
  const remember = key => {
    told.add(key);
    try { sessionStorage.setItem(TOLD_KEY, JSON.stringify(Array.from(told).slice(-40))); } catch (e) { /* memory only */ }
  };

  const castOf = cid => (typeof VS !== "undefined" && VS && VS.cast && VS.cast[cid]) || {};
  const portName = k => (D.ports && D.ports[k] && D.ports[k].name) || k;
  const tl = (key, fb, vars) => (T[key] == null ? esc(t(fb, vars)) : te(key, vars));
  const plain = (key, fb, vars) => (T[key] == null ? t(fb, vars) : t(key, vars));
  const hash = s => { let h = 7; for (const c of String(s)) h = (h * 31 + c.charCodeAt(0)) >>> 0; return h; };
  /* one line of a bank (promo.summons.0, .1, ...), chosen from a seed so a redraw never changes it */
  function bankLine(prefix, seed, vars) {
    const keys = Object.keys(T).filter(k => k.startsWith(prefix + ".") && T[k] != null && String(T[k]).trim()).sort();
    if (!keys.length) return "";
    return te(keys[hash(seed) % keys.length], vars);
  }
  const hasBank = prefix => Object.keys(T).some(k => k.startsWith(prefix + ".") && T[k] != null && String(T[k]).trim());
  const numeral = n => {
    let out = "";
    for (const [value, mark] of [[1000, "M"], [900, "CM"], [500, "D"], [400, "CD"], [100, "C"], [90, "XC"],
      [50, "L"], [40, "XL"], [10, "X"], [9, "IX"], [5, "V"], [4, "IV"], [1, "I"]]) {
      while (n >= value) { out += mark; n -= value; }
    }
    return out;
  };

  /* ---- pictures ----------------------------------------------------------------------------------- */
  /* The Mayor's picture, best first: this rank's own portrait, then her congratulations pictures (Media Library >
     Ports > "Mayor congratulations": a new one each ceremony), then her everyday mayor portrait. Only pictures
     ticked for the role count (no untagged harbour views). A clip of her is chosen as often as the persona rule's
     video chance allows (Media.pickFace, as the Captain screen does); "Images only" leaves the clips out. */
  function mayorItem(port, rank) {
    const tagged = role => Media.items("port", port, role, true).filter(i => i.r.includes(role));
    return Media.pickFace(tagged("mayor_" + rank), "mayor", { primary: true })
      || Media.pickFace(tagged("mayor_congrats"), "mayor")
      || Media.choose("port", port, "mayor", { mode: "fixed", strict: true, slot: "promo-mayor" });
  }
  /* The picture behind: the port's arrival picture, else its banner, else its night scene, else the Graphics port picture. */
  function sceneUrl(port) {
    for (const role of ["arrival", "banner", "night"]) {
      const item = Media.choose("port", port, role, { strict: true, slot: "promo-scene" });
      if (item && item.t === "image" && item.u) return item.u;
    }
    return ((D.graphics || {}).ports || {})[port] || "";
  }

  /* ---- the picture behind (two layers that crossfade, as the Sea Battle's) ---------------------------- */
  let pics = [], curPic = 0, picUrl = "";
  function setBg(url) {
    if (url === picUrl) return;
    picUrl = url;
    const next = pics[1 - curPic], prev = pics[curPic];
    if (!url) { prev.classList.remove("on"); return; }
    next.innerHTML = `<img src="${esc(url)}" alt="" decoding="async">`;
    const img = next.firstElementChild;
    let done = false;
    const go = () => { if (done) return; done = true; next.classList.add("on"); prev.classList.remove("on"); curPic = 1 - curPic; };
    if (img.complete && img.naturalWidth) go(); else img.addEventListener("load", go, { once: true });
    img.addEventListener("error", () => { done = true; }, { once: true });
    setTimeout(go, 1800);
  }

  /* ---- the speaker: the Mayor, tall on the left with her name plate, as the Sea Battle's ------------- */
  function figureHtml(port, rank) {
    const who = castOf("mayor");
    const item = mayorItem(port, rank);
    const face = item ? Media.faceMarkup(item, "sf-face on")
      : who.portrait ? `<img class="sf-face on" src="${esc(who.portrait)}" alt="">` : "";
    const label = te("fleet.promotion_mayor", { port: portName(port) });
    return `<div class="sf-who pm-who${face ? "" : " nopic"}" style="--who:${esc(who.color || "var(--deck-brass)")}">${face ? `<div class="sf-frame">${face}</div>` : ""}
      <div class="sf-plate"><b>${label}</b>${who.name ? `<span>${esc(who.name)}</span>` : ""}</div></div>`;
  }
  let whoKey = "";
  function setWho(mid, port, rank, seed) {
    const key = port + "|" + rank + "|" + seed;
    if (key === whoKey && mid.querySelector(".pm-who")) return;
    whoKey = key;
    const old = mid.querySelector(".pm-who");
    if (old) old.remove();
    mid.insertAdjacentHTML("afterbegin", figureHtml(port, rank));
  }

  /* ---- the screen: built once, redrawn beat by beat --------------------------------------------------- */
  const SAY_ICON = `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M11 5 6 9H2v6h4l5 4V5z"/><path d="M15.5 8.5a5 5 0 0 1 0 7"/><path d="M19 5a10 10 0 0 1 0 14"/></svg>`;

  function build() {
    screen = document.createElement("div");
    screen.id = "promo-screen";
    screen.className = "pm-screen";
    screen.innerHTML = `
      <div class="sf-bg" aria-hidden="true"><div class="sf-pic"></div><div class="sf-pic"></div><div class="sf-shade"></div></div>
      <header class="pm-top"><div class="pm-where"><small></small><b></b></div><div class="pm-ticks" aria-hidden="true"></div><span></span></header>
      <div class="sf-mid pm-mid">
        <div class="pm-seal" aria-hidden="true" hidden><span class="pm-rays"></span><img class="pm-badge-img" alt=""></div>
        <h2 class="pm-rank" hidden></h2>
        <p class="pm-prev" hidden></p>
        <p class="sf-cap" aria-live="polite"></p>
        <p class="pm-say" hidden></p>
      </div>
      <footer class="pm-foot"><p class="pm-hint"></p><div class="pm-act"></div></footer>
      <div class="sf-result pm-result" hidden></div>`;
    pics = Array.from(screen.querySelectorAll(".sf-pic"));
    curPic = 0; picUrl = ""; whoKey = "";
    screen.addEventListener("click", e => {
      const b = e.target.closest("button");
      if (b) {
        if (b.dataset.pm === "go") { if (!b.disabled) accept(b); }
        else if (b.dataset.pm === "say") { e.stopPropagation(); sayAgain(); }
        return;
      }
      if (e.target.closest(".sf-rline")) return;
      tapOn();
    });
    document.body.appendChild(screen);
    document.body.classList.add("in-promo");
  }
  const $ = sel => screen.querySelector(sel);

  /* ---- the four screens ------------------------------------------------------------------------------- */
  function beatsFor(p, key) {
    const me = S.me, record = p.record || {};
    const ranks = record.ranks || D.ranks || [];
    const rankIndex = ranks.findIndex(r => r.id === p.rank_id);
    const name = portName(p.port);
    const captain = { name: record.name || me.name, firm: record.firm || me.firm };
    const vars = { port: name, name: captain.name, firm: captain.firm || captain.name, rank: p.title };
    const said = p.text || t("fleet.promotion_quote", { name: captain.name, rank: p.title });
    const clip = ((S.voice || {}).promotion || [])[0] || null;
    const base = { port: p.port, rank_id: p.rank_id, bg: sceneUrl(p.port), count: ranks.length, at: rankIndex, vars };
    const beats = [];
    if (p.kind === "tier") {
      // Cargo Tiers (25 Nov 2026): no rank-up this time, only the dealers closing out the old stock (p.tier).
      beats.push(Object.assign({}, base, { kind: "tier", title: tl("promo.tier.title", "The market turns"),
        cap: hasBank("promo.tier.open") ? bankLine("promo.tier.open", key, vars) : "" }));
      beats.push(Object.assign({}, base, { kind: "tiercard", last: true, promo: p, said: "", clip: null, ranks, rankIndex,
        captain }));
      return beats;
    }
    if (hasBank("promo.summons")) {
      beats.push(Object.assign({}, base, { kind: "summons", title: tl("promo.title.summons", "Summoned"),
        cap: bankLine("promo.summons", key, vars) }));
    }
    beats.push(Object.assign({}, base, { kind: "rank", title: te("fleet.promotion_title"), rank: p.title,
      prev: record.previous ? record.previous.title : "", cap: hasBank("promo.rank") ? bankLine("promo.rank", key, vars) : "" }));
    beats.push(Object.assign({}, base, { kind: "words", title: tl("promo.title.words", "The Mayor's congratulations"),
      say: { text: said, clip } }));
    if (p.tier && hasBank("promo.tier.cap")) {
      beats.push(Object.assign({}, base, { kind: "tier", title: tl("promo.tier.title", "The market turns"),
        cap: bankLine("promo.tier.cap", key, vars) }));
    }
    beats.push(Object.assign({}, base, { kind: "commission", last: true, promo: p, said, clip, ranks, rankIndex, captain }));
    return beats;
  }

  /* A wavy-edged wax seal, so the stamp does not look like a plain circle. */
  function waxPath() {
    let d = "";
    for (let i = 0; i <= 90; i++) {
      const a = i / 90 * Math.PI * 2, r = 55 + 2.3 * Math.sin(a * 11) + 1.3 * Math.sin(a * 5 + 1);
      d += (i ? "L" : "M") + (60 + r * Math.cos(a)).toFixed(1) + " " + (60 + r * Math.sin(a)).toFixed(1);
    }
    return d + "Z";
  }
  /* Her bedroom key: a brass key on a red ribbon, drawn in SVG (decorative, there is no key in the rules). */
  const KEY_SVG = `<svg class="pm-key" viewBox="0 0 170 64" aria-hidden="true"><defs>
      <linearGradient id="pmBrassKey" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f6e2a0"/><stop offset=".5" stop-color="#c0902f"/><stop offset="1" stop-color="#7a5416"/></linearGradient></defs>
    <g fill="url(#pmBrassKey)" stroke="#5b3d0e" stroke-width="1.6" stroke-linejoin="round">
      <circle cx="28" cy="32" r="22"/><circle cx="28" cy="32" r="10" fill="#eadcb8"/><circle cx="14" cy="32" r="5"/><circle cx="42" cy="32" r="5"/><circle cx="28" cy="18" r="5"/><circle cx="28" cy="46" r="5"/>
      <rect x="50" y="28" width="108" height="8" rx="2"/><rect x="62" y="22" width="8" height="20" rx="2"/>
      <rect x="132" y="36" width="10" height="16" rx="1"/><rect x="146" y="36" width="10" height="11" rx="1"/></g>
      <path d="M16 12 C2 2 0 22 12 22 C0 26 6 44 18 30 Z M40 12 C54 2 56 22 44 22 C56 26 50 44 38 30 Z" fill="#a8282e" stroke="#5d1013" stroke-width="1.2" transform="translate(0 -6) scale(1 .9)"/></svg>`;

  /* The cargo the dealers closed out and the cargo now on the market (p.tier, Cargo Tiers 25 Nov 2026). */
  const goodLabel = k => (D.goods && D.goods[k] && D.goods[k].name) || k;
  function tierBlockHtml(tier) {
    if (!tier) return "";
    const sold = (tier.sold || []).map(r => `<li><span>${esc(r.qty.toLocaleString())} ${esc(goodLabel(r.good))}</span><i>${esc(money(r.gain))}</i></li>`).join("");
    const out = (tier.goods_out || []).map(g => esc(goodLabel(g))).join(", ");
    const inn = (tier.goods_in || []).map(g => esc(goodLabel(g))).join(", ");
    return `<div class="pm-c-tier">
      <p class="pm-c-tier-h"><small>${tfb("promo.tier.closed", "Closed out by the dealers")}</small></p>
      ${sold ? `<ul class="pm-c-sold">${sold}</ul><p class="pm-c-paid"><span>${tfb("promo.tier.paid", "Paid to you")}</span><b>${esc(money(tier.total || 0))}</b></p>`
        : `<p class="pm-c-none">${tfb("promo.tier.none", "Nothing of yours was left on the old shelves.")}</p>`}
      ${out ? `<p class="pm-c-gone"><s>${out}</s></p>` : ""}
      ${inn ? `<p class="pm-c-tier-h"><small>${tfb("promo.tier.opened", "Now on the market")}</small></p><p class="pm-c-new">${inn}</p>` : ""}
      ${tier.cancelled ? `<p class="pm-c-drop">${tfb("promo.tier.dropped", "Commissions for the old cargo were cancelled, with no fee and no blame.")}</p>` : ""}
    </div>`;
  }

  /* The card for a tier step with no rank-up beside it: the Mayor beside a notice from the dealers. */
  function tierCardHtml(b) {
    const p = b.promo, record = p.record || {}, port = portName(p.port), captain = b.captain;
    const mayor = te("fleet.promotion_mayor", { port });
    const mayorName = castOf("mayor").name || "";
    const mayorItm = mayorItem(p.port, p.rank_id);
    const mayorPic = mayorItm ? Media.faceMarkup(mayorItm, "", `alt="${mayor}"`)
      : castOf("mayor").portrait ? `<img src="${esc(castOf("mayor").portrait)}" alt="${mayor}">` : "";
    const date = record.date || S.date || "";
    const house = captain.firm || captain.name;
    return `<figure class="sf-rwho pm-rwho${mayorPic ? "" : " nopic"}">${mayorPic}
        <figcaption class="pm-line"><b>${mayor}</b>${mayorName ? `<span>${esc(mayorName)}</span>` : ""}</figcaption></figure>
      <div class="pm-right">
        <section class="pm-cert pm-tiercert" role="dialog" aria-modal="true" aria-labelledby="pm-title">
          <i class="pm-co tl"></i><i class="pm-co tr"></i><i class="pm-co bl"></i><i class="pm-co br"></i>
          <p class="pm-c-order">${tfb("promo.tier.order", "By order of the {mayor}, and with the dealers' compliments", { mayor })}</p>
          <p class="pm-c-game">${tfb("promo.cert.game", "Crimson Ledger")}</p>
          <p class="pm-c-kind"><span id="pm-title">${tfb("promo.tier.kind", "Notice from the Dealers")}</span></p>
          <p class="pm-c-to">${tfb("fleet.promotion_to", "Captain {name}", { name: captain.name })}</p>
          <p class="pm-c-house">${tfb("fleet.promotion_house", "of {firm}", { firm: house })}</p>
          <p class="pm-c-cite">${tfb("promo.tier.cite", "The old dealers have closed out their stock and paid you in full. Nothing was lost in the swap.")}</p>
          ${tierBlockHtml(p.tier)}
          <div class="pm-c-foot"><div class="pm-c-sign"><span class="pm-c-pen">${esc(mayorName || mayor)}</span><small>${mayor} · ${esc(date)}</small></div></div>
        </section>
        <button type="button" class="primary pm-go" data-pm="go" disabled>${tfb("promo.tier.accept", "Understood, Captain")} <span aria-hidden="true">&rarr;</span></button>
        <div class="fleet-promotion-error pm-error" role="alert"></div>
      </div>`;
  }

  function commissionHtml(b) {
    const p = b.promo, me = S.me, record = p.record || {}, port = portName(p.port);
    const ach = p.achievements, captain = b.captain;
    const next = Object.hasOwn(record, "next") ? record.next : me.next_rank;
    const mayor = te("fleet.promotion_mayor", { port });
    const mayorName = castOf("mayor").name || "";
    const mayorItm = mayorItem(p.port, p.rank_id);
    const mayorPic = mayorItm ? Media.faceMarkup(mayorItm, "", `alt="${mayor}"`)
      : castOf("mayor").portrait ? `<img src="${esc(castOf("mayor").portrait)}" alt="${mayor}">` : "";
    const fig = (label, value) => `<div><dt>${esc(label)}</dt><dd>${esc(value)}</dd></div>`;
    const figs = [fig(t("fleet.captain_worth"), money(record.worth ?? me.worth)),
      fig(t("fleet.promotion_ships"), String(record.ships ?? me.ships.length))];
    if (ach) {
      if (ach.voyages != null) figs.push(fig(t("fleet.promotion_voyages"), String(ach.voyages)));
      else if (ach.won) figs.push(fig(plain("promo.tile.won", "Battles won"), String(ach.won)));
      else if (ach.ports) figs.push(fig(plain("promo.tile.ports", "Ports visited"), String(ach.ports)));
    }
    const badge = Ranks.url(p.rank_id);
    const emblem = badge ? `<img src="${esc(badge)}" alt="" onerror="this.remove()">` : `<span>${esc(numeral(b.rankIndex + 1))}</span>`;
    const hear = b.clip && typeof Voice !== "undefined"
      ? `<button type="button" class="sf-rsay pm-say-btn" data-pm="say" aria-label="${tfb("fleet.promotion_say", "Hear her again")}">${SAY_ICON}</button>` : "";
    const ring = plain("promo.cert.ring", "Mayor of {port} · Commissioned · ", { port }).toUpperCase();
    const date = record.date || S.date || "";
    const house = captain.firm || captain.name;
    return `<figure class="sf-rwho pm-rwho${mayorPic ? "" : " nopic"}">${mayorPic}
        <figcaption class="pm-line"><b>${mayor}</b>${mayorName ? `<span>${esc(mayorName)}</span>` : ""}
          <small>${te("fleet.promotion_audience", { rank: p.title })}</small>${hear}</figcaption></figure>
      <div class="pm-right">
        <section class="pm-cert" role="dialog" aria-modal="true" aria-labelledby="pm-title">
          <i class="pm-co tl"></i><i class="pm-co tr"></i><i class="pm-co bl"></i><i class="pm-co br"></i>
          <p class="pm-c-order">${tfb("fleet.promotion_order", "By order of the {mayor}", { mayor })}</p>
          <p class="pm-c-game">${tfb("promo.cert.game", "Crimson Ledger")}</p>
          <p class="pm-c-kind"><span>${tfb("promo.cert.kind", "Certificate of Commission")}</span></p>
          <p class="pm-c-to">${tfb("fleet.promotion_to", "Captain {name}", { name: captain.name })}</p>
          <p class="pm-c-house">${tfb("fleet.promotion_house", "of {firm}", { firm: house })}</p>
          <p class="pm-c-is">${tfb("fleet.promotion_commissioned", "is hereby commissioned")}</p>
          <h2 class="pm-c-rank" id="pm-title">${esc(p.title)}</h2>
          ${record.previous ? `<p class="pm-c-elev">${esc(record.previous.title)} <span aria-hidden="true">&rarr;</span> ${esc(p.title)}</p>` : ""}
          <p class="pm-c-cite">${te(next ? "fleet.promotion_citation" : "fleet.promotion_citation_top", { firm: house })}</p>
          <dl class="pm-c-figs">${figs.join("")}</dl>
          ${tierBlockHtml(p.tier)}
          <blockquote class="pm-c-note"><small>${tfb("promo.cert.note", "A word from the Mayor")}</small>
            <p>“${esc(b.said)}”</p></blockquote>
          <div class="pm-c-foot">
            <div class="pm-c-key">${KEY_SVG}<small>${tfb("promo.cert.key", "With the Key to the Mayor's Bedchamber. Knock twice, Captain.", { port })}</small></div>
            <div class="pm-c-sign"><span class="pm-c-pen">${esc(mayorName || mayor)}</span><small>${mayor} · ${esc(date)}</small></div>
          </div>
          <div class="pm-stamp" aria-hidden="true">
            <svg viewBox="0 0 120 120"><defs><radialGradient id="pmWax" cx=".38" cy=".3" r=".85"><stop offset="0" stop-color="#d4484d"/><stop offset=".55" stop-color="#9c262b"/><stop offset="1" stop-color="#5d1013"/></radialGradient>
              <path id="pmArc" d="M60 60 m-41 0 a41 41 0 1 1 82 0 a41 41 0 1 1 -82 0"/></defs>
              <path d="${waxPath()}" fill="url(#pmWax)"/>
              <circle cx="60" cy="60" r="47" fill="none" stroke="#f1c9b8" stroke-opacity=".5" stroke-width="1.4"/>
              <circle cx="60" cy="60" r="30" fill="none" stroke="#f1c9b8" stroke-opacity=".35" stroke-width="1"/>
              <text font-size="8.4" font-family="Georgia, serif" font-weight="700" fill="#f6dccb" fill-opacity=".85" letter-spacing="1"><textPath href="#pmArc" textLength="252" lengthAdjust="spacing">${esc(ring)}</textPath></text></svg>
            <span class="pm-stamp-em">${emblem}</span></div>
        </section>
        <button type="button" class="primary pm-go" data-pm="go" disabled>${te("fleet.promotion_accept")} <span aria-hidden="true">&rarr;</span></button>
        <div class="fleet-promotion-error pm-error" role="alert"></div>
      </div>`;
  }

  /* ---- playing the story ------------------------------------------------------------------------------ */
  function startCard(key, p, inGame) {
    const beats = beatsFor(p, key);
    story = { key, promo: p, beats, i: 0, t0: 0, timer: null, started: false, armedAt: 0, inGame, tag: "promo:" + key };
    // a story this page has already told (a reload) goes straight to the card
    if (told.has("C|" + key)) story.i = beats.length - 1;
    if (typeof Voice !== "undefined") Voice.only("promotion");     // only the Mayor is heard until Continue
    enter();
  }

  function enter() {
    const me = story, b = me.beats[me.i];
    me.t0 = Date.now();
    me.started = false;
    me.armedAt = b.last ? Date.now() : 0;
    drawBeat(b);
    // the fanfare on the commission, once per promotion; the stamp sounds with the rank (drawBeat)
    if (b.kind === "commission" && typeof SeaAudio !== "undefined") SeaAudio.playOnce("pm:" + me.key + ":fanfare", "stinger.promotion");
    if (b.last) {
      remember("C|" + me.key);
      clearTimeout(armTimer);
      armTimer = setTimeout(() => { if (story === me) refreshFoot(); }, ARM_MS + 50);
      return;
    }
    // the line this screen waits for, as the Sea Battle's pictures do: until it has been said
    const voiced = !!(b.say && b.say.clip && typeof Voice !== "undefined" && Voice.enabled() && !Voice.muted());
    if (voiced) sayIt(b.say);
    const text = (b.say && b.say.text) || b.cap || "";
    const quiet = Math.min(9000, Math.max(MIN_BEAT_MS, String(text).replace(/<[^>]*>/g, "").length * PER_CHAR_MS + 1600));
    const idx = me.i;
    let lastEnd = 0;
    me.timer = setInterval(() => {
      if (story !== me || me.i !== idx) return clearInterval(me.timer);
      const now = Date.now() - me.t0, cur = typeof Voice !== "undefined" ? Voice.current() : null;
      const mine = !!(cur && cur.tag === me.tag);
      screen.classList.toggle("talking", mine);
      let over;
      if (!voiced) over = now >= quiet;
      else if (mine) { me.started = true; lastEnd = now; over = false; }
      else if (me.started) over = now - lastEnd >= AFTER_VOICE_MS && now >= MIN_BEAT_MS;
      else over = now >= VOICE_START_MS && now >= quiet;                 // muted, or the line never came
      if (over || now >= MAX_BEAT_MS + (voiced ? VOICE_START_MS : 0)) advance();
    }, 120);
  }

  function sayIt(say) {
    if (!story || !say || !say.clip || typeof Voice === "undefined") return;
    Voice.drop("promotion");
    Voice.say([Object.assign({ tag: story.tag, text: say.text }, say.clip)], { group: "promotion", front: true });
  }
  function sayAgain() {
    const b = story && story.beats[story.beats.length - 1];
    if (b && b.clip) sayIt({ text: b.said, clip: b.clip });
  }

  function advance() {
    if (!story) return;
    const me = story;
    if (me.i >= me.beats.length - 1) return;
    clearInterval(me.timer);
    if (typeof Voice !== "undefined") Voice.drop("promotion");
    screen.classList.remove("talking");
    me.i += 1;
    enter();
  }
  function tapOn() {
    if (!story) return;
    const b = story.beats[story.i];
    if (!b || b.last || Date.now() - story.t0 < TAP_AFTER_MS) return;
    advance();
  }
  document.addEventListener("keydown", e => {
    if (!story || !(e.key === " " || e.key === "Enter" || e.key === "ArrowRight")) return;
    if (e.target && /^(input|textarea|select|button)$/i.test(e.target.tagName)) return;
    const b = story.beats[story.i];
    if (b && !b.last) { e.preventDefault(); tapOn(); }
  });

  /* ---- drawing one screen ------------------------------------------------------------------------------ */
  function ticksHtml(b) {
    if (!b.count) return "";
    return Array.from({ length: b.count }, (_, i) => {
      const done = b.kind === "summons" ? i < b.at : i <= b.at;
      const now = i === b.at;
      return `<span class="pm-tick${done ? " done" : ""}${now ? (b.kind === "summons" ? " pend" : " now") : ""}"></span>`;
    }).join("");
  }

  function drawBeat(b) {
    const card = b.kind === "commission" || b.kind === "tiercard";
    screen.dataset.kind = b.kind;
    screen.classList.toggle("costs", card);
    screen.classList.remove("talking");
    setBg(b.bg);
    const result = $(".pm-result");
    if (card) {
      result.innerHTML = b.kind === "tiercard" ? tierCardHtml(b) : commissionHtml(b);
      result.hidden = false;
      refreshFoot();
      return;
    }
    result.hidden = true;
    result.innerHTML = "";
    $(".pm-where small").textContent = portName(b.port);
    $(".pm-where b").innerHTML = b.title || "";
    $(".pm-ticks").innerHTML = ticksHtml(b);
    const mid = $(".pm-mid");
    setWho(mid, b.port, b.rank_id, story.key);
    const seal = $(".pm-seal"), rank = $(".pm-rank"), prev = $(".pm-prev"), cap = $(".sf-cap"), say = $(".pm-say");
    const isRank = b.kind === "rank";
    seal.hidden = !isRank;
    rank.hidden = !isRank;
    prev.hidden = !(isRank && b.prev);
    if (isRank) {
      const badge = Ranks.url(b.rank_id);
      const img = seal.querySelector(".pm-badge-img");
      seal.classList.remove("noart");
      seal.dataset.n = numeral(b.at + 1);
      img.onerror = () => { seal.classList.add("noart"); img.removeAttribute("src"); };
      if (badge) img.src = badge; else img.onerror();
      // restart the stamp
      seal.classList.remove("stamp"); void seal.offsetWidth; seal.classList.add("stamp");
      if (typeof SeaAudio !== "undefined") SeaAudio.playOnce("pm:" + story.key + ":stamp", STAMP_CUE);
      rank.textContent = b.rank;
      prev.innerHTML = b.prev ? `${esc(b.prev)} <span aria-hidden="true">&rarr;</span> ${esc(b.rank)}` : "";
    }
    cap.innerHTML = b.cap || "";
    cap.classList.remove("in"); void cap.offsetWidth; cap.classList.add("in");
    say.innerHTML = b.say && b.say.text ? `<span>“${esc(b.say.text)}”</span>` : "";
    say.hidden = !say.innerHTML;
    say.classList.remove("in"); void say.offsetWidth; say.classList.add("in");
    refreshFoot();
  }

  /* The footer: a hint while the story moves on by itself, the card's own button once it waits for the Captain. */
  function refreshFoot() {
    if (!screen || !story) return;
    const b = story.beats[story.i];
    const hint = $(".pm-hint"), act = $(".pm-act");
    if (!b.last) {
      hint.textContent = tl("promo.story.next", "Tap to go on").replace(/<[^>]*>/g, "");
      hint.hidden = false;
      act.innerHTML = "";
      return;
    }
    hint.hidden = true;
    const btn = screen.querySelector(".pm-go");
    if (btn && !busy) btn.disabled = Date.now() - story.armedAt < ARM_MS;
  }

  async function accept(btn) {
    if (busy || !story) return;
    busy = true;
    btn.disabled = true;
    const me = story, error = screen.querySelector(".pm-error");
    if (error) error.textContent = "";
    if (typeof Voice !== "undefined") Voice.drop("promotion");
    const result = await post("/api/act", { token, type: "promotion_ack", id: me.promo.id });
    busy = false;
    if (!result.ok) {
      if (btn.isConnected) btn.disabled = false;
      if (error) error.textContent = result.error;
      return;
    }
    if (S.me && S.game_id + ":" + (S.me.promotion || {}).id === me.key) S.me.promotion = null;
    if (me.inGame && S.phase === "port") {
      ui.tally = false;
      ui.tab = "fleet";
    }
    teardown();
    render();
  }

  function teardown() {
    if (story) clearInterval(story.timer);
    clearTimeout(armTimer);
    story = null;
    if (screen) { screen.remove(); screen = null; }
    document.body.classList.remove("in-promo");
    if (typeof Voice !== "undefined") { Voice.drop("promotion"); Voice.only(null); }
  }

  /* ---- the quiet moment ------------------------------------------------------------------------------- */
  /* It waits for a quiet moment (19 Nov 2026): no other popup open and no other voice mid-line (the Port
     Authority's ruling, a headline). It waits at most QUIET_MS for a voice; a popup it waits for until it is closed. */
  function quiet(key) {
    if (waitKey !== key) { waitKey = key; waitSince = Date.now(); }
    const popup = document.querySelector("dialog[open]") || document.querySelector(".ceremony");
    const line = typeof Voice !== "undefined" ? Voice.current() : null;
    const talking = line && line.group !== "promotion" && Date.now() - waitSince < QUIET_MS;
    if (!popup && !talking) return true;
    clearTimeout(waitTimer);
    // look again shortly with the latest arguments (any new state redraws and calls sync() again anyway)
    waitTimer = setTimeout(() => { if (typeof S !== "undefined" && S) sync(last.inGame, last.canShow); }, 400);
    return false;
  }

  function sync(inGame, canShow) {
    if (typeof S === "undefined" || typeof D === "undefined" || !S || !D) return;
    last = { inGame, canShow };
    clearTimeout(waitTimer);
    const p = canShow && S.me && S.me.promotion;
    if (!p) { if (screen) teardown(); return; }
    const key = S.game_id + ":" + p.id;
    if (screen && story && story.key === key) { refreshFoot(); return; }
    if (screen) teardown();
    if (!quiet(key)) return;
    build();
    startCard(key, p, inGame);
  }

  /* True while the story is on screen: it reads the Mayor's line itself, so the Captain's Log stays quiet. */
  const busyNow = () => !!screen;
  return { sync, busy: busyNow, telling: busyNow };
})();
