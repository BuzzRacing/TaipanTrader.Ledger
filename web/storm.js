"use strict";

/* Storms and damage (storm.py, 20 Nov 2026).
   - A heavy or savage storm puts a full-screen card in front of the Captain, laid out like the sea battle's
     Reckoning (and the jail's cards): Roxana, battered, huge on the left with her line in the quote card at
     her feet, the broken ship of the class that was hit behind her, and the brass-cornered damage ledger on
     the right (hulls with the lost hull hatched, guns, cargo overboard, where the fleet landed). "Make port"
     closes it (storm_ack) after a short pause so a stray tap cannot skip it. It sits above the sea battle,
     so a pirate fight that follows waits behind it.
   - A rough storm is a notice under the top edge with her picture and her line; it fades out by itself.
   Reads S.me.storm (the report) and is called from player.js render(). */
const Storm = (() => {
  let screen = null, banner = null, shownKey = null, armTimer = null, bannerTimer = null;
  let stage = null, armedAt = 0, busy = false, bannerFor = null;
  let pane = null, cardUp = false;           // the part of the screen that changes (story caption, then the card)
  const ARM_MS = 2500;                       // a beat before the button can be pressed
  const TAP_AFTER_MS = 900;                  // a tap cannot skip a story screen before it has had this long
  const MIN_BEAT_MS = 2500, VOICE_START_MS = 5000, MAX_BEAT_MS = 22000, AFTER_VOICE_MS = 900;
  const clipOf = name => (typeof S !== "undefined" && S && S.voice && S.voice.storm && S.voice.storm[name]) || null;
  const canSpeak = () => typeof Voice !== "undefined" && Voice.enabled() && !Voice.muted();
  let story = null;                          // the story before the card: {id, beats, i, t0, timer}

  const tl = (key, fb, vars) => (T[key] == null ? esc(t(fb, vars)) : te(key, vars));
  const castOf = cid => (typeof VS !== "undefined" && VS && VS.cast && VS.cast[cid]) || {};
  const portName = k => (D.ports && D.ports[k] && D.ports[k].name) || k;
  const goodName = g => (D.goods && D.goods[g] && D.goods[g].name) || g;
  const n0 = v => Math.round(Number(v) || 0).toLocaleString("en-US");
  const SPEAKER = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M11 5 6 9H2v6h4l5 4V5z"/><path d="M15.5 8.5a5 5 0 0 1 0 7"/><path d="M19 5a10 10 0 0 1 0 14"/></svg>';
  const WAVES = '<svg viewBox="0 0 76 80" aria-hidden="true"><path d="m38 10 5 18-10 9 12 10-7 20M31 16a25 25 0 0 0-8 44m24-44a25 25 0 0 1 8 44M13 38h12m26 0h12M21 21l8 8m18 18 8 8M21 55l8-8m18-18 8-8M9 70q9-5 18 0t18 0 18 0"/></svg>';

  /* Her pictures: the battered ones first (Personas > Roxana, role "storm"); a family-friendly screen never
     receives the sexy set, so it gets the clean one (tagged "clean", tools/queue_storm_clean_pictures.py). */
  function roxanaItem(cid) {
    const all = Media.items("persona", cid, "storm").filter(i => i.t === "image" && (i.r || []).includes("storm"));
    if (!all.length) return Media.choose("persona", cid, "angry", { strict: true, slot: "storm-who" })
      || Media.choose("persona", cid, "portrait", { slot: "storm-who" });
    const clean = i => (i.g || []).includes("clean");
    const pick = all.filter(i => !clean(i));
    const list = pick.length ? pick : all;
    return list[Math.floor(Math.random() * list.length)];
  }

  function shipItem(st) {
    const hit = st.ships.slice().sort((x, y) => (y.hull0 - (y.lost ? 0 : y.hull1)) - (x.hull0 - (x.lost ? 0 : x.hull1)))[0];
    if (!hit) return null;
    const own = Media.items("ship", hit.type, "wrecked").filter(i => i.t === "image" && (i.r || []).includes("wrecked"));
    if (own.length) return own[Math.floor(Math.random() * own.length)];
    return Media.choose("scene", ["voyage", "storm"], "background", { strict: true, slot: "storm-bg" })
      || Media.choose("ship", hit.type, "battle", { strict: true, slot: "storm-bg" });
  }

  /* The two pictures of a storm (her, and the broken ship behind her) are picked ONCE, when the storm first comes
     on screen, and kept until "Make port". They used to be asked for again on every redraw, and the Media Library
     hands out a fresh random picture once the last one is 2.5 s old, which is exactly when the card was redrawn
     to arm its button: the card blinked to another picture (21 Nov 2026). */
  let pics = { id: null, who: null, bg: null };
  function picsFor(st) {
    if (pics.id !== st.id) pics = { id: st.id, who: roxanaItem("narrator") || null, bg: shipItem(st) || null };
    return pics;
  }

  const line = (st, key, vars) => (st.lines && st.lines[key]) ? te(st.lines[key], vars) : "";
  function varsOf(st) {
    const L = st.landing || {};
    return {
      goods: esc((st.cargo || []).map(c => n0(c.qty) + " " + goodName(c.good).toLowerCase()).join(", ")),
      port: esc(portName(L.port)),
      yard: esc(L.yard_port ? portName(L.yard_port) : ""),
    };
  }

  function hullBar(s) {
    const max = Math.max(1, s.max || s.hull0 || 1);
    const now = s.lost ? 0 : Math.max(0, Math.min(max, s.hull1));
    const was = Math.max(now, Math.min(max, s.hull0));
    const pct = v => (100 * v / max).toFixed(1) + "%";
    const low = now / max <= .25 ? " low" : "";
    return `<span class="sf-rhull${low}" aria-hidden="true"><i class="now" style="--before:${pct(was)};width:${pct(now)}"></i><i class="gone" style="left:${pct(now)};width:${pct(was - now)}"></i></span>`;
  }
  function armsCount(s) {
    const count = (key, label) => {
      const before = s[key + "0"] || 0, after = s.lost ? 0 : s[key + "1"] || 0;
      return before || after ? `<span>${te(label, { n: after })}${before > after ? ` <em>−${before - after}</em>` : ""}</span>` : "";
    };
    return count("guns", "battle.res.gun_count") + count("cannons", "battle.res.cannon_count")
      || `<span class="unarmed">${te("battle.res.unarmed")}</span>`;
  }
  const tile = (label, value, cls) => `<div class="${cls || ""}"><small>${label}</small><b>${value}</b></div>`;

  /* Built once per storm and never rebuilt: the broken ship, the shade over it, and Roxana with her line at her
     feet (the line stays hidden while the story screen says it in the big caption). */
  function frameHtml(st, beat) {
    const who = castOf("narrator"), P = picsFor(st);
    const url = P.who ? P.who.u : who.portrait || "";
    const say = line(st, "open", varsOf(st));
    const cap = say ? `<figcaption class="sf-rline st-line"${beat ? " hidden" : ""}><header><span class="sf-rsay">${SPEAKER}</span>
        <span>${esc(who.name || "")}${who.title ? " · " + esc(who.title) : ""}</span></header><p>“${say}”</p></figcaption>` : "";
    return `<div class="st-bg"${P.bg ? ` style="background-image:url('${esc(P.bg.u)}')"` : ""}></div><div class="st-shade"></div>
      <div class="sf-result st-result${beat ? " st-beat" : ""}">
        <figure class="sf-rwho st-who${url ? "" : " nopic"}">${url ? `<img src="${esc(url)}" alt="">` : ""}${cap}</figure>
        <div class="st-pane"></div>
      </div>`;
  }

  function armed() { return Date.now() - armedAt >= ARM_MS; }

  function drawCard(st) {
    const V = varsOf(st), L = st.landing || {};
    const savage = st.band === "savage";
    const hullPct = st.hull_full ? Math.round(100 * st.hull_lost / st.hull_full) : 0;
    const sunk = st.ships.filter(s => s.lost).length;
    const repair = (S.me.ships || []).reduce((n, s) => n + (s.repair || 0), 0);
    const needYard = (S.me.ships || []).some(s => s.needs_yard);
    const armsLost = (st.guns_lost || 0) + (st.cannons_lost || 0);
    const rows = tile(tl("storm.t.hull", "Hull lost"), hullPct + "%", hullPct ? "dn" : "")
      + tile(tl("storm.t.cargo", "Cargo lost"), st.cargo_cost ? "−" + money(st.cargo_cost) : money(0), st.cargo_cost ? "dn" : "up")
      + tile(tl("storm.t.guns", "Guns lost"), n0(armsLost), armsLost ? "dn" : "up")
      + tile(tl("storm.t.repair", "Mending"), repair ? money(repair) : money(0), "gold");

    const ships = st.ships.map(s => `<li class="sf-rship ${s.lost ? "lost" : (s.hull1 < s.hull0 || (s.guns1 < s.guns0)) ? "hit" : ""}">
        <b>${esc(s.name)}</b><div class="sf-rcondition"><span>${s.lost ? te("battle.res.ship_lost") : `${n0(s.hull0)} → ${n0(s.hull1)}`}</span>${hullBar(s)}</div>
        <div class="sf-rarms">${armsCount(s)}</div></li>`).join("");

    const cargo = (st.cargo || []).length
      ? st.cargo.map(c => `<li><span><b>${n0(c.qty)}</b> ${esc(goodName(c.good))}</span><i></i><em class="dn">−${money(c.cost)}</em></li>`).join("")
      : `<li class="none">${tl("storm.nocargo", "The hold came through with nothing lost.")}</li>`;
    const stamp = (st.cargo || []).length ? `<p class="st-stamp">${tl("storm.stamp.over", "Washed overboard")}</p>` : "";
    const notes = ["cargo", "guns", "hull"].map(k => line(st, k, V)).filter(Boolean)
      .map(x => `<li><span>${x}</span></li>`).join("");

    const landed = L.diverted
      ? `<li class="${L.yard ? "ok" : "bad"}"><span><b>${esc(portName(L.port))}</b> · ${tl(L.yard ? "storm.yard.yes" : "storm.yard.no", L.yard ? "A shipyard here" : "No shipyard here")}</span></li>`
        + (!L.yard && L.yard_port ? `<li><span>${tl("storm.yard.near", "Nearest shipyard: {port}", { port: esc(portName(L.yard_port)) })}</span></li>` : "")
        + `<li><span>${tl("storm.fetch", "The hold fetches {pct}% of its best price here", { pct: L.ratio })}</span></li>`
        + `<li><span>${tl("storm.rank", "Ranked {rank} of {of} nearby ports for your hold", { rank: L.rank, of: L.of })}</span></li>`
        + ((L.banned || []).length ? `<li class="bad"><span>${tl("storm.banned", "Banned here: {goods}", { goods: esc(L.banned.map(goodName).join(", ")) })}</span></li>` : "")
      : `<li class="ok"><span>${tl("storm.course", "Still bound for {port}", { port: esc(portName(L.port)) })}</span></li>`;
    const patch = needYard || (!L.yard && L.diverted)
      ? `<p class="sf-note">${tl("storm.patch", "No shipyard: a ship here can only be patched to {pct}% of her hull", { pct: st.patch_pct || 50 })}</p>` : "";
    const reason = line(st, "land", V);

    return `<section class="sf-card st-card o-${esc(st.band)}" role="dialog" aria-modal="true" aria-labelledby="st-title">
          <header><p class="eyebrow">${te("storm.eyebrow." + st.band)} · ${te("storm.severity", { score: st.score })}</p>
            <div class="sf-rheading"><span class="sf-remblem" aria-hidden="true">${WAVES}</span><h2 id="st-title">${te("storm.title." + st.band)}</h2></div>
            ${reason ? `<p class="sf-rreason">${reason}</p>` : ""}</header>
          <div class="sf-rows">${rows}</div>
          <div class="sf-cols">
            <div><h3>${tl("storm.hull", "Hulls")}${sunk ? ` · ${te("storm.lost_ship")}: ${sunk}` : ""}</h3>
              <div class="sf-rcolumns"><span>${te("battle.res.vessel")}</span><span>${te("battle.res.hull_label")}</span><span>${te("battle.res.armament")}</span></div>
              <ul class="sf-rships">${ships}</ul></div>
            <div class="sf-rledger"><h3>${tl("storm.cargo", "Cargo")}</h3><ul class="sf-rcargo">${cargo}</ul>${stamp}
              ${notes ? `<h3>${tl("storm.ledger", "Damage ledger")}</h3><ul class="sf-rcargo st-notes">${notes}</ul>` : ""}
              <h3>${tl("storm.landed", "Where you landed")}</h3><ul class="sf-rcargo st-landed">${landed}</ul></div>
          </div>
          ${patch}
          <footer>
            <p class="sf-net st-net"><span>${line(st, "close", V)}</span></p>
            <button type="button" class="primary st-go" data-go="storm_ack"${armed() ? "" : " disabled"}>${tl("storm.btn", "Make port")} <span aria-hidden="true">&rarr;</span></button>
          </footer>
        </section>`;
  }

  /* ---- the story before the card (21 Nov 2026): Roxana tells it one screen at a time ----------------------
     The storm used to open straight on the ledger card. Now the opening, the cargo, the guns, the hull and the
     landing each get one big screen (her line as a large caption), moving on by themselves; a tap, Space or Enter
     moves them sooner. Then the card. Since 21 Nov 2026 it is one screen (the opening), read aloud by Roxana, and
     her closing line is read as the card comes up. The sea battle behind it stays quiet: Storm.holding(). */
  const readMs = txt => Math.max(2800, Math.min(5500, 1400 + String(txt).replace(/<[^>]*>/g, "").length * 40));

  function buildBeats(st) {
    const V = varsOf(st), L = st.landing || {};
    const hullPct = st.hull_full ? Math.round(100 * st.hull_lost / st.hull_full) : 0;
    const sunk = st.ships.filter(s => s.lost).length;
    const armsLost = (st.guns_lost || 0) + (st.cannons_lost || 0);
    const beats = [];
    const add = (key, eyebrow, sub, cls) => {
      let text = line(st, key, V), cid = "narrator";
      if (!text) return;
      if (/^Powder: /.test(text)) { text = text.slice(8); cid = "bosun"; }
      beats.push({ kind: key, name: key, cid, text, eyebrow, sub: sub || "", cls: cls || "" });
    };
    /* One story screen only (21 Nov 2026, Anthony: "one screen and then the result"): her opening line, then the
       card carries the cargo, guns, hull and landing. */
    add("open", te("storm.eyebrow." + st.band) + " · " + te("storm.severity", { score: st.score }), "");
    return beats;
  }

  function endStory() {
    if (story) { clearTimeout(story.timer); clearInterval(story.timer); story = null; }
    if (typeof Voice !== "undefined") Voice.drop("storm");
  }

  function startStory(st) {
    endStory();
    const beats = buildBeats(st);
    story = { id: st.id, beats, i: 0, t0: Date.now(), timer: null };
    if (!beats.length) return;
    schedule();
  }
  /* Each screen waits for its line to be said (the way the jail story and the sea battle do); with voices off or
     muted, or a line that never comes, it moves on after a reading time. */
  function schedule() {
    const me = story;
    clearTimeout(me.timer); clearInterval(me.timer);
    me.t0 = Date.now();
    me.started = false; me.lastEnd = 0;
    const idx = me.i, b = me.beats[idx];
    const clip = b ? clipOf(b.name) : null;
    const voiced = !!(clip && canSpeak());
    const tag = "storm:" + me.id + ":" + idx;
    const quiet = readMs(b ? b.text : "");
    if (voiced) Voice.say([Object.assign({ tag, text: b.text.replace(/<[^>]*>/g, "") }, clip)], { group: "storm", front: true });
    me.timer = setInterval(() => {
      if (story !== me || me.i !== idx) return clearInterval(me.timer);
      const now = Date.now() - me.t0, cur = typeof Voice !== "undefined" ? Voice.current() : null;
      const mine = !!(cur && cur.tag === tag);
      let over;
      if (!voiced) over = now >= quiet;
      else if (mine) { me.started = true; me.lastEnd = now; over = false; }
      else if (me.started) over = now - me.lastEnd >= AFTER_VOICE_MS && now >= MIN_BEAT_MS;
      else over = now >= VOICE_START_MS && now >= quiet;
      if (over || now >= MAX_BEAT_MS + (voiced ? VOICE_START_MS : 0)) { clearInterval(me.timer); advance(); }
    }, 120);
  }
  function advance() {
    if (!story || story.i >= story.beats.length) return;
    clearInterval(story.timer);
    if (typeof Voice !== "undefined") Voice.drop("storm");
    story.i += 1;
    if (story.i >= story.beats.length) {          // the card comes up; its button arms after a beat
      const close = clipOf("close"), L = line(S.me.storm || {}, "close", varsOf(S.me.storm || {}));
      if (close && canSpeak() && L) Voice.say([Object.assign({ tag: "storm:" + story.id + ":close", text: L.replace(/<[^>]*>/g, "") }, close)], { group: "storm", front: true });
      arm();
    } else schedule();
    sync();
  }
  /* The button arms in place, a beat after the card comes up. Arming used to redraw the whole card, which replayed
     its entrance and showed as a blink about 2.5 s in (21 Nov 2026). */
  function arm() {
    armedAt = Date.now();
    clearTimeout(armTimer);
    armTimer = setTimeout(() => {
      const b = screen && screen.querySelector(".st-go");
      if (b && !busy) b.disabled = false;
    }, ARM_MS + 50);
  }
  const telling = () => !!(story && story.i < story.beats.length);

  function drawBeat(st, b, i) {
    const who = castOf(b.cid);
    const dots = story.beats.length > 1 ? story.beats.map((_, k) => `<i class="${k < i ? "done" : k === i ? "now" : ""}"></i>`).join("") : "";
    return `<section class="st-cap o-${esc(st.band)}" role="status" aria-live="polite">
          <p class="st-eyebrow">${b.eyebrow}</p>
          <p class="st-say">“${b.text}”</p>
          <p class="st-by">${esc(who.name || "")}${who.title ? " · " + esc(who.title) : ""}</p>
          ${b.sub ? `<p class="st-sub ${b.cls}">${b.sub}</p>` : ""}
          <footer><span class="st-dots" aria-hidden="true">${dots}</span><span class="st-hint">${tl("storm.tap", "Tap to go on")}</span></footer>
        </section>`;
  }

  async function ack(btn) {
    if (busy) return;
    busy = true;
    if (btn) btn.disabled = true;
    const ok = await act("storm_ack", {});
    busy = false;
    if (!ok && btn && btn.isConnected) btn.disabled = false;
  }

  function syncScreen(st) {
    const on = !!(st && st.card);
    document.body.classList.toggle("in-storm", on);
    if (!on) {
      endStory();
      if (screen) { screen.remove(); screen = null; pane = null; cardUp = false; shownKey = null; stage = null; clearTimeout(armTimer); }
      return;
    }
    if (!screen) {
      screen = document.createElement("div");
      screen.id = "storm-screen";
      screen.className = "st-screen";
      screen.addEventListener("click", e => {
        const b = e.target.closest(".st-go");
        if (b) { if (!b.disabled && armed()) ack(b); return; }
        if (telling() && Date.now() - story.t0 >= TAP_AFTER_MS) advance();
      });
      document.body.appendChild(screen);
    }
    const nowKey = String(st.id);
    if (nowKey !== stage) {                       // a new storm: the frame is built here, once
      stage = nowKey;
      shownKey = null;
      cardUp = false;
      startStory(st);
      screen.innerHTML = frameHtml(st, telling());
      pane = screen.querySelector(".st-pane");
      if (!telling()) arm();                      // no story lines to tell: straight to the card
    }
    if (telling()) {
      const key = "B" + st.id + ":" + story.i;
      if (key !== shownKey) { shownKey = key; pane.innerHTML = drawBeat(st, story.beats[story.i], story.i); }
      return;
    }
    /* The card. It is drawn once; only the pane changes, so the ship and Roxana stay exactly as they were. If the
       figures on it change while it is up (the mending bill, say) the pane is redrawn without its entrance. */
    const key = JSON.stringify([st, S.me.ships && S.me.ships.map(s => s.repair)]);
    if (key === shownKey) return;
    shownKey = key;
    if (!cardUp) {
      cardUp = true;
      const res = screen.querySelector(".st-result"), cap = screen.querySelector(".st-line");
      if (res) res.classList.remove("st-beat");
      if (cap) cap.hidden = false;
    } else pane.classList.add("st-still");
    pane.innerHTML = drawCard(st);
  }

  document.addEventListener("keydown", e => {
    if (!telling() || !(e.key === " " || e.key === "Enter" || e.key === "ArrowRight")) return;
    if (Date.now() - story.t0 < TAP_AFTER_MS) return;
    e.preventDefault();
    advance();
  });

  /* The rough storm: a notice under the top edge with Roxana's picture and her line (21 Nov 2026, Anthony: the
     small banner was easy to miss). It stays BANNER_MS, with a thin bar running down the time left, then fades
     out over BANNER_FADE_MS; resting the mouse on it holds it open, and the cross closes it at once. */
  const BANNER_MS = 20000, BANNER_FADE_MS = 1400;
  function syncBanner(st) {
    const on = !!(st && !st.card);
    if (!on) {
      if (banner) { banner.remove(); banner = null; }
      bannerFor = null;
      clearTimeout(bannerTimer);
      return;
    }
    if (bannerFor === st.id) return;
    bannerFor = st.id;
    if (banner) banner.remove();
    const who = castOf("narrator");
    const say = line(st, "open", varsOf(st));
    const hullPct = st.hull_full ? Math.round(100 * st.hull_lost / st.hull_full) : 0;
    const repair = (S.me.ships || []).reduce((n, s) => n + (s.repair || 0), 0);
    const item = picsFor(st).who;
    const url = item ? item.u : who.portrait || "";
    const el = banner = document.createElement("div");
    el.className = "st-banner" + (url ? "" : " nopic");
    el.setAttribute("role", "status");
    el.style.setProperty("--st-stay", BANNER_MS + "ms");
    el.style.setProperty("--st-fade", BANNER_FADE_MS + "ms");
    el.innerHTML = `${url ? `<img class="st-bwho" src="${esc(url)}" alt="">` : ""}
      <div class="st-bbody">
        <b><span class="st-bemblem" aria-hidden="true">${WAVES}</span>${tl("storm.banner.rough", "Squall")}</b>
        ${say ? `<p class="st-bsay">“${say}”</p>` : ""}
        <p class="st-bby">${esc(who.name || "")}${who.title ? " · " + esc(who.title) : ""}</p>
        <p class="st-bfacts"><span>${tl("storm.t.hull", "Hull lost")} <em>−${hullPct}%</em></span>${repair
          ? `<span>${tl("storm.t.repair", "Mending")} <em>${money(repair)}</em></span>` : ""}</p>
      </div>
      <button type="button" aria-label="OK">&times;</button>
      <i class="st-btime" aria-hidden="true"></i>`;
    let left = BANNER_MS, since = 0, leaving = false;
    const leave = async ms => {
      if (leaving || banner !== el) return;
      leaving = true;
      clearTimeout(bannerTimer);
      el.style.setProperty("--st-fade", ms + "ms");
      el.classList.add("leaving");
      await new Promise(r => setTimeout(r, ms));
      if (banner !== el) return;
      const ok = await act("storm_ack", {});
      if (!ok && banner === el) { leaving = false; el.classList.remove("leaving"); }   // not taken: show it again
    };
    const run = () => { since = Date.now(); clearTimeout(bannerTimer); bannerTimer = setTimeout(() => leave(BANNER_FADE_MS), left); };
    el.querySelector("button").addEventListener("click", () => leave(250));
    el.addEventListener("pointerenter", e => {
      if (e.pointerType !== "mouse" || leaving) return;
      clearTimeout(bannerTimer);
      left = Math.max(2500, left - (Date.now() - since));
      el.classList.add("held");
    });
    el.addEventListener("pointerleave", e => {
      if (e.pointerType !== "mouse" || leaving) return;
      el.classList.remove("held");
      run();
    });
    document.body.appendChild(el);
    run();
  }

  function sync() {
    if (typeof S === "undefined" || typeof D === "undefined" || !S || !D) return;
    const st = S.me && S.phase !== "lobby" && S.me.storm;
    syncScreen(st || null);
    syncBanner(st || null);
  }

  function busyNow() { return !!screen; }

  /* True from the moment the report says there is a card, before the card is even drawn (Battle.sync runs ahead of
     Storm.sync in player.js render()). The sea battle behind it waits on this: no pictures, no voices, no music
     until "Make port" (the server holds the fight's round clock the same way). */
  function holding() {
    return !!(typeof S !== "undefined" && S && S.me && S.phase !== "lobby" && S.me.storm && S.me.storm.card);
  }

  return { sync, busy: busyNow, holding };
})();
