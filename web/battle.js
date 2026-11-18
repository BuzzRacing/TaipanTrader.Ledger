/* SeaTrader: the sea battle (battle.js, battle.css).

   When a house meets pirates while its captain is at this screen, the month waits "at sea" and the
   whole window becomes the fight: the enemy ahead, a picture and a large caption for each thing
   that happens, the bosun calling it out, and the captain's choice each round:

     Fight on    every gun fires
     Run for it  free if it works; a failed try lets them close
     Retreat     always works: cargo goes over the side and every junk afloat fires once more
     Pay         before the first shot, the pirates' price to let the fleet pass

   The server owns the fight (engine.py, "sea battles"). It sends S.me.battle while one is open
   (with the pictures and captions of the last step, a "beat"), S.me.fights for the ones that are
   over this month (each with its reckoning), and S.sea: every house still fighting, for the
   houses that are waiting. Nobody lands until every fight is over, so a house with no fight sees
   the waiting screen. A round clock runs on the server; when it runs out the round is played on
   the captain's standing orders.

   This file draws into its own layer (#seafight) over the deck, so the deck's redraws never
   disturb a picture or a line that is playing. player.js calls Battle.sync() after every redraw
   and holds the captain's log and the Port Authority back while Battle.busy(). */
"use strict";

const Battle = (() => {
  const MIN_FRAME_MS = 1500;      // a caption stays at least this long
  const PER_CHAR_MS = 42;         // plus reading time when nobody reads it aloud
  const VOICE_START_MS = 2600;    // a line that has not started by now is not coming (muted, no voices)
  const MAX_FRAME_MS = 9000;
  const JUNK = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M11 2.5v12M11 3.5c3.2.6 5.6 2.6 6.4 6.2H11M11 6.2c-2.4.5-4 1.9-4.7 4.4H11M3.5 15.5h17l-2.4 4.2H6z"/></svg>';

  const root = document.createElement("div");
  root.id = "seafight";
  root.hidden = true;
  root.innerHTML = `
    <div class="sf-bg" aria-hidden="true"><div class="sf-sea"></div><div class="sf-pic"></div><div class="sf-pic"></div><div class="sf-shade"></div></div>
    <header class="sf-top">
      <div class="sf-where"><small></small><b></b></div>
      <div class="sf-round"></div>
      <div class="sf-clock" hidden><span></span><i><b></b></i><small></small></div>
    </header>
    <div class="sf-enemy" hidden><div class="sf-junks"></div><p></p></div>
    <div class="sf-mid">
      <div class="sf-who" hidden></div>
      <p class="sf-cap" aria-live="assertive"></p>
      <p class="sf-tell"></p>
    </div>
    <footer class="sf-foot" hidden><div class="sf-fleet"></div><div class="sf-acts"></div></footer>
    <section class="sf-wait" hidden></section>
    <div class="sf-result" hidden></div>`;
  document.body.appendChild(root);
  const $ = sel => root.querySelector(sel);
  const pics = Array.from(root.querySelectorAll(".sf-pic"));

  let seen = new Set();           // beats already played on this screen
  let acked = new Set();          // fights whose reckoning the captain has closed
  let playing = null;             // {key, frames, clips, i, timer, tag, started, t0}
  let sending = false, clockEnd = 0, clockTotal = 1, clockKey = "", curPic = 0, picKey = "", drawnKey = "";
  try { acked = new Set(JSON.parse(sessionStorage.getItem("seatrader_fights") || "[]")); } catch (e) { /* a fresh page */ }

  const a = s => String(s == null ? "" : s).replace(/[&<>"']/g, c =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  /* ---------------------------------------------------------------- pictures -- */
  /* The picture for a moment of the fight: this enemy's own set (Media Library > Scenes >
     "Sea battle: pirate junks" / "Sea battle: war junks", one role per moment), then the other
     enemy's, then the older battle scenes, then a ship of the fleet in battle. With none of those
     the painted sea behind stays as it is. */
  function pictureFor(moment, kind) {
    if (typeof Media === "undefined") return null;
    const own = kind === "lord" ? "seafight_lord" : "seafight_pirates";
    const other = kind === "lord" ? "seafight_pirates" : "seafight_lord";
    const o = { video: true, fresh: true, mode: "random", slot: "seafight" };
    const strict = Object.assign({ strict: true }, o);
    return Media.choose("scene", own, moment, strict) || Media.choose("scene", other, moment, strict)
      || Media.choose("scene", own, moment, o) || Media.choose("scene", other, moment, o)
      || Media.choose("scene", ["battle", "pirates"], "event", o)
      || Media.choose("ship", (S.me.ships || []).map(s => s.type), "battle", strict)
      || Media.choose("scene", ["voyage", "storm"], "background", strict);
  }
  function showPicture(moment, kind, key) {
    root.dataset.moment = moment || "";
    if (key === picKey) return;
    picKey = key;
    const item = pictureFor(moment, kind);
    const next = pics[1 - curPic], prev = pics[curPic];
    if (!item) { prev.classList.remove("on"); return; }
    if (prev.dataset.mid === item.id && prev.classList.contains("on")) return;
    next.innerHTML = item.t === "video"
      ? `<video src="${a(item.u)}" muted autoplay loop playsinline preload="auto" disablepictureinpicture></video>`
      : `<img src="${a(item.u)}" alt="" decoding="async">`;
    next.dataset.mid = item.id;
    const media = next.firstElementChild;
    let done = false;
    const go = () => {
      if (done) return;
      done = true;
      next.classList.add("on");
      prev.classList.remove("on");
      curPic = 1 - curPic;
    };
    if (item.t === "video") media.addEventListener("loadeddata", go, { once: true });
    else if (media.complete && media.naturalWidth) go();
    else media.addEventListener("load", go, { once: true });
    media.addEventListener("error", () => { done = true; }, { once: true });
    setTimeout(go, 1800);
  }

  /* ------------------------------------------------------------- playing a beat -- */
  /* The speaker: a tall portrait on the left of the caption. It shows every picture that persona
     has in the media library, shuffled, crossfading to the next every few seconds while they talk.
     Each new line starts on a different picture from the one the last line ended on. */
  const WHO_ROTATE_MS = 3200;
  let whoTimer = null;
  const whoLast = {};             // persona -> last picture url shown
  function shuffled(list, notFirst) {
    const out = list.slice();
    for (let i = out.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [out[i], out[j]] = [out[j], out[i]];
    }
    if (out.length > 1 && out[0] === notFirst) out.push(out.shift());
    return out;
  }
  function speakerChip(clip) {
    const who = $(".sf-who");
    clearInterval(whoTimer);
    whoTimer = null;
    const c = clip && typeof VS !== "undefined" && VS.cast ? VS.cast[clip.c] : null;
    if (!c) { who.hidden = true; return; }
    let urls = typeof Media !== "undefined" ? Media.items("persona", clip.c, "", false).map(i => i.u) : [];
    urls = Array.from(new Set(urls));
    if (!urls.length && c.portrait) urls = [c.portrait];
    urls = shuffled(urls, whoLast[clip.c]);
    who.style.setProperty("--who", c.color || "var(--deck-brass)");
    const frame = urls.length
      ? `<div class="sf-frame"><img class="sf-face on" src="${a(urls[0])}" alt="">${urls.length > 1 ? '<img class="sf-face" alt="">' : ""}</div>`
      : "";
    who.innerHTML = `${frame}<div class="sf-plate"><b>${a(c.name)}</b><span>${a(c.title || "")}</span></div>`;
    who.classList.toggle("nopic", !urls.length);
    who.hidden = false;
    if (urls.length) whoLast[clip.c] = urls[0];
    if (urls.length < 2) return;
    let i = 0;
    whoTimer = setInterval(() => {
      if (who.hidden || !who.isConnected) { clearInterval(whoTimer); whoTimer = null; return; }
      i = (i + 1) % urls.length;
      const url = urls[i], faces = who.querySelectorAll(".sf-face");
      const on = who.querySelector(".sf-face.on"), off = Array.from(faces).find(x => x !== on);
      if (!on || !off) return;
      const pre = new Image();
      pre.onload = () => {
        off.src = url;
        off.classList.add("on");
        on.classList.remove("on");
        whoLast[clip.c] = url;
      };
      pre.src = url;
    }, WHO_ROTATE_MS);
  }

  function frameStep() {
    const p = playing;
    if (!p) return;
    const f = p.frames[p.i];
    if (!f) { playing = null; $(".sf-who").hidden = true; return sync(); }
    showPicture(f.moment, p.kind, p.key + ":" + p.i);
    const cap = $(".sf-cap");
    cap.textContent = f.cap || "";
    cap.classList.remove("in"); void cap.offsetWidth; cap.classList.add("in");
    $(".sf-tell").textContent = "";
    const clip = p.clips && p.clips[p.i];
    p.tag = "sf:" + p.key + ":" + p.i;
    p.started = false;
    p.t0 = Date.now();
    speakerChip(clip && f.say ? clip : null);
    if (clip && f.say && typeof Voice !== "undefined") {
      Voice.say([Object.assign({ tag: p.tag, text: f.say }, clip)], { group: "battle" });
    }
    clearInterval(p.timer);
    p.timer = setInterval(() => {
      if (playing !== p) return clearInterval(p.timer);
      const now = Date.now() - p.t0, cur = typeof Voice !== "undefined" ? Voice.current() : null;
      const mine = cur && cur.tag === p.tag;
      if (mine) p.started = true;
      const quiet = (f.cap || "").length * PER_CHAR_MS + MIN_FRAME_MS;
      const over = p.started ? !mine && now >= MIN_FRAME_MS
        : now >= (clip && f.say && now < VOICE_START_MS ? VOICE_START_MS : quiet);
      if (over || now >= MAX_FRAME_MS) nextFrame();
    }, 120);
  }
  function nextFrame() {
    if (!playing) return;
    clearInterval(playing.timer);
    if (typeof Voice !== "undefined") Voice.drop("battle");
    playing.i += 1;
    frameStep();
  }
  function play(key, kind, frames, clips) {
    seen.add(key);
    if (playing) clearInterval(playing.timer);
    playing = { key, kind, frames: frames || [], clips: clips || [], i: 0, timer: null };
    frameStep();
  }

  /* ------------------------------------------------------------------ drawing -- */
  function junks(n, left) {
    const show = Math.min(n, 60);
    const el = $(".sf-junks");
    const key = n + ":" + left;
    if (el.dataset.k !== key) {
      el.dataset.k = key;
      el.className = "sf-junks" + (show > 36 ? " tiny" : show > 16 ? " small" : "");
      el.innerHTML = Array.from({ length: show }, (_, i) =>
        `<i class="${i < Math.round(show * left / Math.max(1, n)) ? "" : "down"}">${JUNK}</i>`).join("");
    }
  }

  function fleetHtml() {
    const me = S.me;
    const ships = me.ships.map(s => {
      const spec = D.ships[s.type] || { hull: s.hull, slots: s.guns, name: s.type };
      const pct = Math.max(0, Math.min(100, Math.round(100 * s.hull / spec.hull)));
      const pips = Array.from({ length: spec.slots || 0 }, (_, j) => `<i class="${j < s.guns ? "on" : ""}"></i>`).join("");
      return `<li class="${pct <= 25 ? "low" : ""}"><b>${a(s.name)}</b><span class="sf-hull"><i style="width:${pct}%"></i></span>
        <small>${s.hull}/${spec.hull}</small><span class="sf-pips">${pips}</span></li>`;
    }).join("");
    const goods = Object.keys(me.cargo).sort((x, y) => me.cargo[y] - me.cargo[x]);
    const cargo = goods.length
      ? goods.slice(0, 4).map(g => `${me.cargo[g]} ${a(D.goods[g] ? D.goods[g].name : g)}`).join(" · ") + (goods.length > 4 ? " · +" + (goods.length - 4) : "")
      : te("battle.stake_none");
    return `<h3>${te("battle.fleet")}</h3><ul>${ships}</ul>
      <p class="sf-stake"><small>${te("battle.stake")}</small>${cargo}</p>`;
  }

  function riskBar(x) {
    const v = Math.max(0, Math.min(1, x));
    return `<span class="sf-risk" title="${te("battle.odds.risk")}"><i style="width:${Math.round(v * 100)}%"></i></span>`;
  }
  function action(choice, label, sub, extra, disabled, cls) {
    return `<button type="button" class="sf-btn ${cls || ""}" data-sf="${choice}" ${disabled ? "disabled" : ""}>
      <b>${label}</b><span>${sub || ""}</span>${extra || ""}</button>`;
  }
  function actsHtml(b) {
    const o = b.odds, exact = b.view === "exact", bar = b.view === "bar";
    const off = sending || !!playing || b.auto;
    const dump = Object.keys(b.dump || {}).map(g => `${b.dump[g]} ${a(D.goods[g] ? D.goods[g].name : g)}`).join(", ");
    const retreatSub = !b.dump_qty ? te("battle.odds.retreat_none")
      : exact && o ? te("battle.odds.retreat", { qty: b.dump_qty, points: o.retreat[2] })
      : te("battle.odds.retreat_cargo", { qty: b.dump_qty });
    const html = [];
    if (b.stage === "parley") {
      html.push(action("pay", te("battle.btn.pay", { price: money(b.price) }),
        b.can_pay ? te("battle.btn.pay_sub") : te("battle.btn.pay_short"), "", off || !b.can_pay, "pay"));
    }
    html.push(action("fight", te("battle.btn.fight"),
      !b.can_fight ? te("battle.btn.fight_none") : exact && o ? te("battle.odds.fight", { pct: Math.round(o.gun_hit * 100) + "%" }) : te("battle.btn.fight_sub"),
      b.can_fight && bar && o ? riskBar(o.danger) : "", off || !b.can_fight, "fight"));
    html.push(action("run", te("battle.btn.run"),
      exact && o ? te("battle.odds.run", { pct: Math.round(o.run * 100) + "%" }) : te("battle.btn.run_sub"),
      bar && o ? riskBar(1 - o.run) : "", off, "run"));
    html.push(action("retreat", te("battle.btn.retreat"), retreatSub + (dump ? `<small>${dump}</small>` : ""),
      bar && o ? riskBar(o.retreat[1] / Math.max(1, b.hull)) : "", off, "retreat"));
    const orders = t("w." + b.orders);
    return `<div class="sf-btns${b.stage === "parley" ? " four" : ""}">${html.join("")}</div>
      <p class="sf-skip"><span>${te("battle.timer_orders", { orders })}</span>
        <button type="button" class="sf-link" data-sf="skip" ${off ? "disabled" : ""} title="${te("battle.btn.skip_sub")}">${te("battle.btn.skip")} &raquo;</button></p>`;
  }

  function header(where, round) {
    $(".sf-where small").textContent = t("battle.title");
    $(".sf-where b").textContent = where ? t("battle.off", { port: where }) : "";
    $(".sf-round").textContent = round || "";
  }

  function setHtml(el, html) { if (el._h !== html) { el.innerHTML = html; el._h = html; } }

  /* A fight in progress. */
  function showBattle(b, index) {
    root.hidden = false;
    root.dataset.mode = "fight";
    $(".sf-wait").hidden = true;
    $(".sf-result").hidden = true;
    const key = S.turn + ":" + index + ":" + b.beat.id;
    if (!seen.has(key)) play(key, b.kind, b.beat.frames, ((S.voice || {}).battle || {}).now);
    header(b.where, b.stage === "parley" ? "" : t("battle.round", { n: Math.min(b.round, b.rounds), rounds: b.rounds }));
    $(".sf-enemy").hidden = false;
    junks(b.n, b.left);
    $(".sf-enemy p").textContent = b.n + " " + b.enemy + " · " + t("battle.enemy", { left: b.left, n: b.n });
    $(".sf-foot").hidden = false;
    setHtml($(".sf-fleet"), fleetHtml());
    setHtml($(".sf-acts"), actsHtml(b));
    if (!playing) {
      const last = b.beat.frames[b.beat.frames.length - 1];
      showPicture(last ? last.moment : "sighting", b.kind, key + ":rest");
      $(".sf-cap").textContent = b.stage === "parley" ? t("battle.parley", { price: money(b.price) }) : (last ? last.cap : "");
      $(".sf-tell").textContent = b.tell || "";
      $(".sf-who").hidden = true;
    }
    // the round clock (the server's; shown here)
    const ck = key + ":" + b.secs_total;
    if (ck !== clockKey || Math.abs(clockEnd - (Date.now() + b.secs_left * 1000)) > 1500) {
      clockKey = ck;
      clockEnd = Date.now() + (b.secs_left || 0) * 1000;
      clockTotal = Math.max(1, b.secs_total || 1);
    }
    $(".sf-clock").hidden = false;
    tick();
  }

  /* A fight that is over: its last pictures, then the reckoning. */
  function showFight(f, more) {
    root.hidden = false;
    $(".sf-wait").hidden = true;
    $(".sf-clock").hidden = true;
    $(".sf-foot").hidden = true;
    header(f.where, "");
    $(".sf-enemy").hidden = false;
    junks(f.n, f.n - f.sunk);
    $(".sf-enemy p").textContent = f.n + " " + f.enemy;
    if (!seen.has(f.id)) { root.dataset.mode = "fight"; $(".sf-result").hidden = true; return play(f.id, f.kind, f.beat.frames, ((S.voice || {}).battle || {})[f.id]); }
    if (playing) { root.dataset.mode = "fight"; $(".sf-result").hidden = true; return; }
    root.dataset.mode = "result";
    const last = f.beat.frames[f.beat.frames.length - 1];
    showPicture(last ? last.moment : "got_away", f.kind, f.id + ":rest");
    $(".sf-cap").textContent = "";
    $(".sf-tell").textContent = "";
    $(".sf-who").hidden = true;
    const gunsHit = s => s.guns0 != null && s.guns1 != null && s.guns1 < s.guns0;
    const ships = f.ships.map(s => `<li class="${s.lost ? "lost" : (s.hull1 < s.hull0 || gunsHit(s)) ? "hit" : ""}"><b>${a(s.name)}</b>
      <span>${s.lost ? te("battle.res.ship_lost") : te("battle.res.hull", { a: s.hull0, b: s.hull1 })
        + (!s.lost && gunsHit(s) ? " · " + te("battle.res.guns", { a: s.guns0, b: s.guns1 }) : "")}</span></li>`).join("");
    const cargo = f.cargo.length
      ? f.cargo.map(c => `<li>${te("battle.res.cargo_line", { qty: c.qty, good: D.goods[c.good] ? D.goods[c.good].name : c.good, cost: money(c.cost) })}</li>`).join("")
      : `<li class="none">${te(f.outcome === "wrecked" ? "battle.res.cargo_wreck" : "battle.res.cargo_none")}</li>`;
    const rows = [
      `<div><small>${te("battle.res.sunk")}</small><b>${te("battle.res.sunk_v", { sunk: f.sunk, n: f.n })}</b></div>`,
      `<div><small>${te("battle.res.rounds")}</small><b>${f.rounds}</b></div>`,
      f.booty ? `<div class="up"><small>${te("battle.res.booty")}</small><b>+${money(f.booty)}</b></div>` : "",
      f.paid ? `<div class="dn"><small>${te("battle.res.paid_line")}</small><b>-${money(f.paid)}</b></div>` : "",
    ].join("");
    const hurt = f.ships.some(s => !s.lost && (s.hull1 < s.hull0 || gunsHit(s)));
    setHtml($(".sf-result"), `<section class="sf-card o-${a(f.outcome)}" role="dialog" aria-labelledby="sfResTitle">
      <header><p class="eyebrow">${a(f.n + " " + f.enemy)}${f.where ? " · " + te("battle.off", { port: f.where }) : ""}</p>
        <h2 id="sfResTitle">${te("battle.res." + f.outcome)}</h2></header>
      <div class="sf-rows">${rows}</div>
      <div class="sf-cols">
        <div><h3>${te("battle.res.ships")}</h3><ul class="sf-rships">${ships}</ul></div>
        <div><h3>${te("battle.res.cargo")}</h3><ul class="sf-rcargo">${cargo}</ul></div>
      </div>
      <p class="sf-net ${f.net > 0 ? "up" : f.net < 0 ? "dn" : ""}"><span>${te("battle.res.net")}</span><b>${f.net > 0 ? "+" : ""}${money(f.net)}</b></p>
      <p class="sf-note">${f.outcome === "wrecked" ? te("battle.res.wreck_note") : hurt ? te("battle.res.repairs") : ""}${more ? " " + te("battle.res.next") : ""}</p>
      <footer><button type="button" class="primary" data-sf="ack" data-id="${a(f.id)}">${more ? te("battle.btn.next") : te("battle.res.port")} <span aria-hidden="true">&rarr;</span></button></footer>
    </section>`);
    $(".sf-result").hidden = false;
    const go = $(".sf-result [data-sf=ack]");
    if (go && document.activeElement !== go && drawnKey !== f.id) { drawnKey = f.id; try { go.focus({ preventScroll: true }); } catch (e) { /* older browsers */ } }
  }

  /* No fight of our own, but the month is waiting for somebody else's. */
  function showWait() {
    root.hidden = false;
    root.dataset.mode = "wait";
    $(".sf-result").hidden = true;
    $(".sf-clock").hidden = true;
    $(".sf-foot").hidden = true;
    $(".sf-enemy").hidden = true;
    $(".sf-who").hidden = true;
    $(".sf-cap").textContent = "";
    $(".sf-tell").textContent = "";
    header("", "");
    showPicture("sighting", "pirates", "wait:" + S.turn);
    const list = (S.sea || []).map(x => `<li style="--who:${COLORS[x.color % 8]}">${Faces.of(x).crest ? houseMark(x, "sf-crest") : ""}
      <b>${te("battle.wait.line", { name: x.name, firm: x.firm, port: x.where })}</b>
      <span>${x.stage === "parley" ? te("battle.wait.parley", { n: x.n, enemy: x.enemy })
        : te("battle.wait.detail", { left: x.left, n: x.n, enemy: x.enemy, round: Math.min(x.round, x.rounds), rounds: x.rounds })}</span>
      <i class="sf-wbar"><i style="width:${Math.round(100 * x.left / Math.max(1, x.n))}%"></i></i></li>`).join("");
    setHtml($(".sf-wait"), `<h2>${te("battle.wait.title")}</h2><p class="sf-lead">${te("battle.wait.lead")}</p>
      <ul>${list || `<li class="none">${te("battle.wait.none")}</li>`}</ul>`);
    $(".sf-wait").hidden = false;
  }

  function hide() {
    if (root.hidden) return;
    root.hidden = true;
    root.dataset.mode = "";
    if (playing) { clearInterval(playing.timer); playing = null; }
    picKey = "";
    pics.forEach(p => { p.classList.remove("on"); p.innerHTML = ""; p.dataset.mid = ""; });
  }

  function pending() {
    return (S.me.fights || []).filter(f => !acked.has(f.id));
  }
  function busy() {
    return !!(typeof S !== "undefined" && S && S.me && (S.phase === "sea" || (S.phase === "port" && pending().length)));
  }
  function sync() {
    if (typeof S === "undefined" || !S || !S.me || !D || (S.phase !== "sea" && S.phase !== "port")) return hide();
    const todo = pending();
    document.body.classList.toggle("seafighting", busy());
    if (todo.length) return showFight(todo[0], todo.length > 1 || !!S.me.battle);
    if (S.phase !== "sea") return hide();
    if (S.me.battle) return showBattle(S.me.battle, (S.me.fights || []).length);
    showWait();
  }

  /* --------------------------------------------------------------- the clock -- */
  function tick() {
    const clock = $(".sf-clock");
    if (root.hidden || clock.hidden) return;
    const left = Math.max(0, (clockEnd - Date.now()) / 1000);
    clock.querySelector("span").textContent = t("battle.timer", { secs: Math.ceil(left) });
    clock.querySelector("i b").style.width = Math.round(100 * Math.min(1, left / clockTotal)) + "%";
    clock.classList.toggle("late", left <= 5);
  }
  setInterval(tick, 250);

  /* ------------------------------------------------------------------ clicks -- */
  async function send(choice) {
    if (sending) return;
    sending = true;
    sync();
    const res = await post("/api/act", { token, type: "sea", choice });
    sending = false;
    if (!res.ok) toast(res.error, true);
    sync();
  }
  root.addEventListener("click", e => {
    const el = e.target.closest("[data-sf]");
    if (!el) {
      // a tap on the picture moves a caption along
      if (playing && !e.target.closest(".sf-result, .sf-foot, .sf-wait")) nextFrame();
      return;
    }
    if (el.disabled) return;
    const what = el.dataset.sf;
    if (what === "ack") {
      acked.add(el.dataset.id);
      try { sessionStorage.setItem("seatrader_fights", JSON.stringify(Array.from(acked).slice(-40))); } catch (err) { /* private browsing */ }
      if (typeof Voice !== "undefined") Voice.drop("battle");
      sync();
      if (typeof render === "function") render();     // the captain's log and the port come back
      if (typeof speak === "function") speak();
      return;
    }
    send(what);
  });
  document.addEventListener("keydown", e => {
    if (root.hidden || root.dataset.mode !== "fight" || e.metaKey || e.ctrlKey || e.altKey) return;
    if (playing && (e.key === " " || e.key === "Enter")) { e.preventDefault(); return nextFrame(); }
    const key = { f: "fight", r: "run", t: "retreat", p: "pay" }[e.key.toLowerCase()];
    const el = key && root.querySelector(`.sf-btn[data-sf="${key}"]`);
    if (el && !el.disabled) { e.preventDefault(); send(key); }
  });

  return { sync, busy };
})();
