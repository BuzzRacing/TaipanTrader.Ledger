"use strict";

/* Storms and damage (storm.py, 20 Nov 2026).
   - A heavy or savage storm puts a full-screen card in front of the Captain, laid out like the sea battle's
     Reckoning (and the jail's cards): Roxana, battered, huge on the left with her line in the quote card at
     her feet, the broken ship of the class that was hit behind her, and the brass-cornered damage ledger on
     the right (hulls with the lost hull hatched, guns, cargo overboard, where the fleet landed). "Make port"
     closes it (storm_ack) after a short pause so a stray tap cannot skip it. It sits above the sea battle,
     so a pirate fight that follows waits behind it.
   - A rough storm is only a small banner with her line; it closes itself.
   Reads S.me.storm (the report) and is called from player.js render(). */
const Storm = (() => {
  let screen = null, banner = null, shownKey = null, armTimer = null, bannerTimer = null;
  let stage = null, armedAt = 0, busy = false, bannerFor = null;
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
  let picPick = { key: "", ids: [] };
  function roxanaItem(cid, st, idx) {
    const all = Media.items("persona", cid, "storm").filter(i => i.t === "image" && (i.r || []).includes("storm"));
    if (!all.length) return Media.choose("persona", cid, "angry", { strict: true, slot: "storm-who" })
      || Media.choose("persona", cid, "portrait", { slot: "storm-who" });
    const clean = i => (i.g || []).includes("clean");
    const pick = all.filter(i => !clean(i));
    const list = pick.length ? pick : all;
    const key = cid + "|" + st.id;
    if (picPick.key !== key || !picPick.ids.every(id => list.some(i => i.id === id))) {
      // a shuffled order for this storm, so each story screen can show a different picture of her
      const ids = list.map(i => i.id);
      for (let k = ids.length - 1; k > 0; k--) { const j = Math.floor(Math.random() * (k + 1)); [ids[k], ids[j]] = [ids[j], ids[k]]; }
      picPick = { key, ids };
    }
    return list.find(i => i.id === picPick.ids[(idx || 0) % picPick.ids.length]);
  }

  let shipPick = { key: "", id: "" };
  function shipItem(st) {
    const hit = st.ships.slice().sort((x, y) => (y.hull0 - (y.lost ? 0 : y.hull1)) - (x.hull0 - (x.lost ? 0 : x.hull1)))[0];
    if (!hit) return null;
    const own = Media.items("ship", hit.type, "wrecked").filter(i => i.t === "image" && (i.r || []).includes("wrecked"));
    if (own.length) {
      const key = hit.type + "|" + st.id;
      if (shipPick.key !== key || !own.some(i => i.id === shipPick.id)) {
        shipPick = { key, id: own[Math.floor(Math.random() * own.length)].id };
      }
      return own.find(i => i.id === shipPick.id);
    }
    return Media.choose("scene", ["voyage", "storm"], "background", { strict: true, slot: "storm-bg" })
      || Media.choose("ship", hit.type, "battle", { strict: true, slot: "storm-bg" });
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

  function whoFigure(st, o) {
    o = o || {};
    const cid = o.cid || "narrator", who = castOf(cid);
    const item = o.item !== undefined ? o.item : roxanaItem(cid, st, o.idx || 0);
    const url = item ? item.u : who.portrait || "";
    const say = o.nocap ? "" : line(st, "open", varsOf(st));
    const cap = say ? `<figcaption class="sf-rline st-line"><header><span class="sf-rsay">${SPEAKER}</span>
        <span>${esc(who.name || "")}${who.title ? " · " + esc(who.title) : ""}</span></header><p>“${say}”</p></figcaption>` : "";
    return `<figure class="sf-rwho st-who${url ? "" : " nopic"}">${url ? `<img src="${esc(url)}" alt="">` : ""}${cap}</figure>`;
  }

  function bgHtml(st) {
    const item = shipItem(st);
    return `<div class="st-bg"${item ? ` style="background-image:url('${esc(item.u)}')"` : ""}></div><div class="st-shade"></div>`;
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

    return `${bgHtml(st)}
      <div class="sf-result st-result">
        ${whoFigure(st, { idx: story ? story.beats.length : 0 })}
        <section class="sf-card st-card o-${esc(st.band)}" role="dialog" aria-modal="true" aria-labelledby="st-title">
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
        </section>
      </div>`;
  }

  /* ---- the story before the card (21 Nov 2026): Roxana tells it one screen at a time ----------------------
     The storm used to open straight on the ledger card. Now the opening, the cargo, the guns, the hull and the
     landing each get one big screen (a different picture of her each time, her line as a large caption), moving
     on by themselves after a reading time; a tap, Space or Enter moves them sooner. Then the card. Captions only,
     not spoken (the sea battle behind it stays quiet: Storm.holding()). */
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
      armedAt = Date.now();
      clearTimeout(armTimer);
      armTimer = setTimeout(() => { shownKey = null; sync(); }, ARM_MS + 50);
    } else schedule();
    shownKey = null;
    sync();
  }
  const telling = () => !!(story && story.i < story.beats.length);

  function drawBeat(st, b, i) {
    const who = castOf(b.cid);
    const item = b.cid === "narrator" ? roxanaItem("narrator", st, i)
      : (Media.choose("persona", b.cid, "portrait", { slot: "storm-bosun" }) || roxanaItem("narrator", st, i));
    const dots = story.beats.map((_, k) => `<i class="${k < i ? "done" : k === i ? "now" : ""}"></i>`).join("");
    return `${bgHtml(st)}
      <div class="sf-result st-result st-beat">
        ${whoFigure(st, { cid: b.cid, item, nocap: true })}
        <section class="st-cap o-${esc(st.band)}" role="status" aria-live="polite">
          <p class="st-eyebrow">${b.eyebrow}</p>
          <p class="st-say">“${b.text}”</p>
          <p class="st-by">${esc(who.name || "")}${who.title ? " · " + esc(who.title) : ""}</p>
          ${b.sub ? `<p class="st-sub ${b.cls}">${b.sub}</p>` : ""}
          <footer><span class="st-dots" aria-hidden="true">${dots}</span><span class="st-hint">${tl("storm.tap", "Tap to go on")}</span></footer>
        </section>
      </div>`;
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
      if (screen) { screen.remove(); screen = null; shownKey = null; stage = null; clearTimeout(armTimer); }
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
    if (nowKey !== stage) {
      stage = nowKey;
      shownKey = null;
      startStory(st);
      if (!telling()) {                           // no story lines to tell: straight to the card
        armedAt = Date.now();
        clearTimeout(armTimer);
        armTimer = setTimeout(() => { shownKey = null; sync(); }, ARM_MS + 50);
      }
    }
    if (telling()) {
      const key = "B" + st.id + ":" + story.i;
      if (key !== shownKey) { shownKey = key; screen.innerHTML = drawBeat(st, story.beats[story.i], story.i); }
      return;
    }
    const key = JSON.stringify([st, S.me.ships && S.me.ships.map(s => s.repair), armed()]);
    if (key !== shownKey) { shownKey = key; screen.innerHTML = drawCard(st); }
  }

  document.addEventListener("keydown", e => {
    if (!telling() || !(e.key === " " || e.key === "Enter" || e.key === "ArrowRight")) return;
    if (Date.now() - story.t0 < TAP_AFTER_MS) return;
    e.preventDefault();
    advance();
  });

  /* The rough storm: a small banner with her line, closing itself. */
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
    banner = document.createElement("div");
    banner.className = "st-banner";
    banner.setAttribute("role", "status");
    banner.innerHTML = `<span class="st-bemblem" aria-hidden="true">${WAVES}</span>
      <div><b>${tl("storm.banner.rough", "Squall")} · −${hullPct}%</b>
      <p>${say ? "“" + say + "” " : ""}<small>${esc(who.name || "")}</small></p></div>
      <button type="button" aria-label="OK">&times;</button>`;
    banner.querySelector("button").addEventListener("click", () => ack(null));
    document.body.appendChild(banner);
    clearTimeout(bannerTimer);
    bannerTimer = setTimeout(() => ack(null), 9000);
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
