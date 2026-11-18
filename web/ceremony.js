"use strict";

/* The opening and the finale. The finale ends on the Ledger of the Voyage: a two-spread book filled
   from GET /api/finale (finale.py), worked out from the game journal when the books close.

     Spread 1  left: the story of one house (port picture, captain's portrait, crest and rank seal,
                     epithet, the tale in a sentence or two, the fortune curve)
               right: final standings (with each house's curve) and the honours of the voyage
     Spread 2  left: by the numbers (counting-up tiles)
               right: the chronicle of big moments, and the cargoes that made the fortune

   On a seated screen the story opens on your own house; tap a house in the standings to read its
   story instead. Everything in the book comes from the journal up to the close, so free play never
   changes it. */
const Ceremony = (() => {
  const openingLength = 11000;
  const finaleLength = 9000;
  let scene, sceneKey, dismissedKey, timer, behind;
  let D = null, S = null;
  // The finale book: one per finished game, fetched once.
  const book = { gid: null, data: null, busy: false, failed: false };
  let view = { spread: 0, house: null };

  function close() {
    clearTimeout(timer);
    if (behind) behind.inert = false;
    scene?.remove();
    scene = behind = sceneKey = null;
  }

  /* ---------------------------------------------------------- helpers -- */
  const portName = key => (D && D.ports && D.ports[key] && D.ports[key].name) || key || "";
  const goodName = key => (D && D.goods && D.goods[key] && D.goods[key].name) || key || "";
  const num = n => Math.round(Number(n) || 0).toLocaleString("en-US");
  function short(n) {
    const v = Math.abs(Number(n) || 0), sign = n < 0 ? "-" : "";
    const fmt = (x, s) => sign + CUR + String(x >= 100 ? Math.round(x) : x >= 10 ? x.toFixed(1) : x.toFixed(2)).replace(/\.0+$|(\.\d*[1-9])0+$/, "$1") + s;
    if (v >= 1e9) return fmt(v / 1e9, "B");
    if (v >= 1e6) return fmt(v / 1e6, "M");
    if (v >= 1e4) return fmt(v / 1e3, "K");
    return money(n);
  }
  const reduced = () => typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;
  const houseOf = id => book.data && book.data.houses.find(h => h.id === id);
  const seat = id => (S && S.players || []).find(p => p.id === id) || {};

  function rankSeal(id, cls) {
    if (!id) return "";
    const art = typeof Media !== "undefined" && Media.choose("rank", id, "badge", { mode: "fixed", strict: true });
    return `<img class="${cls}" src="${esc(art ? art.u : "/assets/rank-badges/" + id + ".png")}" alt="" onerror="this.remove()">`;
  }
  function portPicture(port) {
    if (typeof Media === "undefined") return "";
    return Media.html("port", port, "banner", "lg-hero-img", ((D && D.graphics || {}).ports || {})[port], { slot: "finale", mode: "fixed" });
  }
  function cargoIcon(good) {
    if (typeof Media === "undefined") return "";
    return Media.html("cargo", good, "icon", "lg-gicon", ((D && D.graphics || {}).goods || {})[good]);
  }
  function portrait(p) {
    const u = Faces.of(p).portrait;
    return u ? `<img src="${esc(u)}" alt="">` : `<span class="lg-initial">${esc((p.name || "?").slice(0, 1))}</span>`;
  }

  /* A fortune curve as an SVG path. big=true adds the area, the peak mark and the labels. */
  function curve(points, w, h, big) {
    if (!points || points.length < 2) return "";
    const xs = points.map(p => p[0]), ys = points.map(p => p[1]);
    const x0 = Math.min(...xs), x1 = Math.max(...xs), lo = Math.min(0, ...ys), hi = Math.max(...ys, 1);
    const pad = big ? 6 : 1.5;
    const X = x => pad + (x - x0) / Math.max(1, x1 - x0) * (w - 2 * pad);
    const Y = y => h - pad - (y - lo) / Math.max(1, hi - lo) * (h - 2 * pad - (big ? 14 : 0));
    const line = points.map((p, i) => (i ? "L" : "M") + X(p[0]).toFixed(1) + " " + Y(p[1]).toFixed(1)).join("");
    if (!big) return `<svg class="lg-spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-hidden="true"><path d="${line}"/></svg>`;
    const peak = points.reduce((a, b) => b[1] > a[1] ? b : a), end = points[points.length - 1];
    const area = line + `L${X(end[0]).toFixed(1)} ${Y(lo).toFixed(1)}L${X(points[0][0]).toFixed(1)} ${Y(lo).toFixed(1)}Z`;
    const px = X(peak[0]), py = Y(peak[1]), anchor = px > w * .75 ? "end" : px < w * .25 ? "start" : "middle";
    const zero = lo < 0 ? `<line class="lg-zero" x1="${pad}" x2="${w - pad}" y1="${Y(0)}" y2="${Y(0)}"/>` : "";
    return `<svg class="lg-fortune" viewBox="0 0 ${w} ${h}" role="img" aria-label="${te("fin.fortune")}">
      <defs><linearGradient id="lg-fill" x1="0" x2="0" y1="0" y2="1">
        <stop offset="0" stop-color="#8c2a1c" stop-opacity=".42"/><stop offset="1" stop-color="#8c2a1c" stop-opacity="0"/></linearGradient></defs>
      ${zero}<path class="lg-area" d="${area}" fill="url(#lg-fill)"/>
      <path class="lg-line" d="${line}" pathLength="1"/>
      <circle class="lg-peak" cx="${px}" cy="${py}" r="3.4"/>
      <text class="lg-peak-label" x="${px}" y="${py - 7}" text-anchor="${anchor}">${te("fin.peak_label", { value: short(peak[1]) })}</text>
      <circle class="lg-end" cx="${X(end[0])}" cy="${Y(end[1])}" r="2.6"/></svg>`;
  }

  /* ------------------------------------------------------------ pages -- */
  function storyPage(h) {
    const p = Object.assign({ color: h.color }, seat(h.id), { name: h.name, firm: h.firm });
    const port = seat(h.id).port || (h.haunt && h.haunt.port) || "";
    const first = (book.data.first || ""), last = (book.data.last || "");
    const tale = [te("fin.tale", { name: h.name, months: num(h.months), voyages: num(h.voyages), ports: num(h.ports),
                                   start: short(h.start), worth: short(h.worth) })];
    if (h.highest) tale.push(te("fin.tale_rank", { rank: h.highest }));
    if (h.peak > h.worth * 1.15) tale.push(te("fin.tale_peak", { peak: short(h.peak), date: h.peak_date }));
    return `<div class="lg-hero"><div class="lg-portrait">${portrait(p)}</div>
        <div class="lg-hero-clip">${portPicture(port)}<div class="lg-hero-shade"></div>
        <p class="lg-hero-cap">${te("fin.finished", { port: portName(port), date: last })}</p></div></div>
      <header class="lg-who">
        <h2>${esc(h.name)} <em>${te("fin.epithet." + h.epithet)}</em></h2>
        <p class="lg-firm">${houseMark(p, "lg-crest")}<b>${esc(h.firm)}</b>${rankSeal(h.rank_id, "lg-seal")}<span>${esc(h.rank)}</span></p>
      </header>
      <p class="lg-tale">${tale.join(" ")}</p>
      <figure class="lg-chart">${curve(h.curve, 360, 80, true)}
        <figcaption><span>${esc(first)} · ${esc(short(h.start))}</span><span>${esc(last)} · <b>${esc(short(h.worth))}</b></span></figcaption></figure>`;
  }

  function standingsPage(current) {
    const rows = book.data.houses.map(h => {
      const p = Object.assign({ color: h.color }, seat(h.id), { name: h.name, firm: h.firm });
      return `<li class="lg-row${h.id === current ? " on" : ""}${h.place <= 3 ? " p" + h.place : ""}" data-house="${esc(h.id)}" tabindex="0" role="button"
          aria-pressed="${h.id === current}">
        <span class="lg-place">${h.place}</span>${houseMark(p, "lg-crest")}
        <span class="lg-row-who"><b>${esc(h.firm)}</b><small>${esc(h.name)} · ${esc(h.rank)}</small></span>
        ${curve(h.curve, 80, 22, false)}
        <span class="lg-row-worth">${esc(money(h.worth))}</span></li>`;
    }).join("");
    const honours = book.data.honours.map(o => {
      const h = houseOf(o.id) || {};
      const value = /golden_sale|hard_luck/.test(o.key) ? short(o.value) : num(o.value);
      return `<li class="lg-honour h-${o.key}"><i aria-hidden="true">${HONOUR_GLYPH[o.key] || "✦"}</i>
        <b>${te("fin.h." + o.key)}</b><span>${esc(h.firm || "")}</span><small>${te("fin.h." + o.key + ".d", { value })}</small></li>`;
    }).join("");
    return `<h2>${te("ceremony.standings")}</h2><ol class="lg-standings">${rows}</ol>
      ${honours ? `<h3>${te("fin.honours")}</h3><ul class="lg-honours">${honours}</ul>` : ""}`;
  }

  const HONOUR_GLYPH = { golden_sale: "⚖︎", sea_wolf: "⚔︎", sharp_eye: "◉", far_sailed: "⚓︎",
                         weathered: "☂︎", hard_luck: "☠︎" };

  function numbersPage(h) {
    const tile = (label, value, sub, extra) => {
      const pic = extra && extra.icon ? `<div class="lg-tile-pic">${extra.icon}</div>` : "";
      return `<div class="lg-tile${extra && extra.cls ? " " + extra.cls : ""}${pic ? " has-pic" : ""}">${pic}<div class="lg-tile-text">
        <small>${label}</small><b>${value}</b>${sub ? `<span>${sub}</span>` : ""}</div></div>`;
    };
    const count = (n, fmt) => `<span class="lg-count" data-to="${Number(n) || 0}" data-fmt="${fmt || "num"}">${fmt === "money" ? esc(short(n)) : num(n)}</span>`;
    const t = [];
    t.push(tile(te("fin.f.passages"), count(h.voyages), te("fin.f.passages_sub", { ports: num(h.ports), months: num(h.months) })));
    t.push(tile(te("fin.f.trades"), count(h.trades), h.win_rate != null ? te("fin.f.trades_sub", { pct: Math.round(h.win_rate * 100) + "%" }) : ""));
    if (h.best_sale) t.push(tile(te("fin.f.best_sale"), count(h.best_sale.profit, "money"),
      te("fin.f.best_sale_sub", { qty: num(h.best_sale.qty), good: goodName(h.best_sale.good), port: portName(h.best_sale.port), date: h.best_sale.date }),
      { cls: "wide gold", icon: cargoIcon(h.best_sale.good) }));
    if (h.cargo[0]) t.push(tile(te("fin.f.best_cargo"), esc(goodName(h.cargo[0].good)),
      te("fin.f.best_cargo_sub", { profit: short(h.cargo[0].profit) }), { cls: "wide", icon: cargoIcon(h.cargo[0].good) }));
    t.push(tile(te("fin.f.battles"), h.battles ? `${count(h.won)}<i>/${num(h.battles)}</i>` : "0",
      h.battles ? te("fin.f.battles_sub", { sunk: num(h.sunk) }) : te("fin.f.battles_none"), { cls: "red" }));
    if (h.booty) t.push(tile(te("fin.f.booty"), count(h.booty, "money"), h.accuracy != null ? te("fin.f.booty_sub", { pct: Math.round(h.accuracy * 100) + "%" }) : ""));
    t.push(tile(te("fin.f.storms"), count(h.storms), te("fin.f.storms_sub", { n: num(h.typhoons) })));
    if (h.haunt) t.push(tile(te("fin.f.haunt"), esc(portName(h.haunt.port)), te("fin.f.haunt_sub", { n: num(h.haunt.visits) })));
    if (h.route) t.push(tile(te("fin.f.route"), `${esc(portName(h.route.from))} <i>→</i> ${esc(portName(h.route.to))}`,
      te("fin.f.route_sub", { n: num(h.route.count) }), { cls: "wide" }));
    t.push(tile(te("fin.f.losses"), count(h.losses, "money"),
      te("fin.f.losses_sub", { seized: num(h.seizures), robbed: num(h.robbed), wrecks: num(h.wrecks) }), { cls: "red" }));
    if (h.taxes) t.push(tile(te("fin.f.taxes"), count(h.taxes, "money"), h.interest ? te("fin.f.taxes_sub", { interest: short(h.interest) }) : ""));
    if (h.score != null) t.push(tile(te("fin.f.score"), `${count(h.score)}<i>/100</i>`, te("fin.f.score_sub")));
    if (h.debt_free) t.push(tile(te("fin.f.debt_free"), esc(h.debt_free), ""));
    return `<h2>${te("fin.numbers")}</h2><div class="lg-tiles">${t.join("")}</div>`;
  }

  const CHRON_GLYPH = { debt_free: "✓", prize: "⚔︎", peak: "▲", blow_seized: "☠︎", blow_wreck: "☠︎",
                        blow_robbed: "☠︎" };
  function chroniclePage(h) {
    const items = h.chronicle.map(c => {
      const icon = c.kind === "rank" ? rankSeal(c.rank_id, "lg-ch-seal")
        : c.kind === "sale" ? cargoIcon(c.good) : `<i>${CHRON_GLYPH[c.kind] || "✦"}</i>`;
      const key = c.kind === "prize" && c.lord ? "fin.c.prize_lord" : "fin.c." + c.kind;
      const text = te(key, { rank: c.rank || "", qty: num(c.qty), good: goodName(c.good), port: portName(c.port),
                             value: short(c.value), count: num(c.count) });
      return `<li class="ch-${esc(c.kind.replace(/_.*/, ""))}"><span class="lg-ch-icon">${icon}</span>
        <time>${esc(c.date)}</time><p>${text}</p></li>`;
    }).join("");
    const top = h.cargo.length ? Math.max(...h.cargo.map(c => c.profit)) : 0;
    const bars = h.cargo.map(c => `<li>${cargoIcon(c.good)}<span class="lg-bar-name">${esc(goodName(c.good))}</span>
        <span class="lg-bar"><i style="--w:${(c.profit / (top || 1) * 100).toFixed(1)}%"></i></span>
        <b>${esc(short(c.profit))}</b></li>`).join("");
    return `<h2>${te("fin.chronicle")}</h2>${items ? `<ol class="lg-chronicle">${items}</ol>` : `<p>${te("fin.chronicle_none")}</p>`}
      ${bars ? `<h3>${te("fin.cargoes")}</h3><ul class="lg-bars">${bars}</ul>` : ""}`;
  }

  /* The old two-line story, for when the book is not in (yet): still used on the results screen. */
  function plainStory(state, ports) {
    const voyage = state.voyage_story;
    if (!voyage) return "";
    const port = key => ports[key]?.name || key;
    const route = voyage.route;
    return `<h2>${te("ceremony.story")}</h2>
      <p>${te("ceremony.final_port", { name: voyage.name, firm: voyage.firm, port: port(voyage.port) })}</p>
      <ul class="story-facts">
        ${route ? `<li>${te("ceremony.route", { from: port(route.from), to: port(route.to), date: route.date })}</li>` : ""}
        <li>${te("ceremony.fleet", { ships: voyage.ships })}</li>
      </ul>`;
  }

  /* The story card on the results screen and the harbor board: the winner's tale and a few facts. */
  function story(state, ports) {
    S = state;
    load(state);
    const h = book.gid === state.game_id && book.data && houseOf(state.voyage_story?.id);
    if (!h) return plainStory(state, ports);
    const facts = [
      te("fin.f.passages") + " · " + num(h.voyages),
      h.best_sale && te("fin.f.best_sale") + " · " + short(h.best_sale.profit) + " (" + esc(goodName(h.best_sale.good)) + ")",
      h.battles && te("fin.f.battles") + " · " + te("fin.won_of", { won: num(h.won), n: num(h.battles) }),
      te("fin.f.storms") + " · " + num(h.storms),
    ].filter(Boolean);
    return `<h2>${te("ceremony.story")}</h2>
      <p><b>${esc(h.name)} ${te("fin.epithet." + h.epithet)}</b> · ${te("fin.tale", { name: h.name, months: num(h.months),
        voyages: num(h.voyages), ports: num(h.ports), start: short(h.start), worth: short(h.worth) })}</p>
      <ul class="story-facts">${facts.map(f => `<li>${f}</li>`).join("")}</ul>`;
  }

  function ranked(state) {
    const first = state.voyage_story?.id;
    return state.players.slice().sort((a, b) =>
      Number(b.id === first) - Number(a.id === first) || b.worth - a.worth);
  }

  /* ------------------------------------------------------------- data -- */
  function load(state) {
    const gid = state && state.game_id;
    if (!gid || !(state.phase === "ended" || state.free_play)) return;
    if (book.gid === gid && (book.data || book.busy || book.failed)) return;
    book.gid = gid; book.data = null; book.busy = true; book.failed = false;
    fetch("/api/finale").then(r => r.json()).then(r => {
      if (book.gid !== gid) return;
      if (r && r.ok && r.houses && r.houses.length) book.data = r; else book.failed = true;
    }).catch(() => { book.failed = true; }).finally(() => {
      book.busy = false;
      if (book.gid !== gid || !book.data) return;
      if (scene && scene.classList.contains("has-results")) drawLedger();
      if (scene && scene.querySelector(".winner")) drawWinnerExtras();
      if (typeof render === "function") { try { render(); } catch (e) { /* the screen draws itself next tick */ } }
    });
  }

  /* --------------------------------------------------------- the book -- */
  function spreadHtml(h) {
    if (view.spread === 0) {
      return `<section class="lg-page lg-left">${storyPage(h)}</section>
        <section class="lg-page lg-right">${standingsPage(h.id)}</section>`;
    }
    return `<section class="lg-page lg-left">${numbersPage(h)}</section>
      <section class="lg-page lg-right">${chroniclePage(h)}</section>`;
  }

  function countUp(root) {
    const els = root.querySelectorAll(".lg-count");
    if (reduced()) return;
    const start = performance.now(), length = 1400;
    els.forEach(el => { el.dataset.final = el.textContent; });
    function step(now) {
      const k = Math.min(1, (now - start) / length), ease = 1 - Math.pow(1 - k, 3);
      els.forEach(el => {
        const to = Number(el.dataset.to) || 0, v = to * ease;
        el.textContent = k >= 1 ? el.dataset.final : el.dataset.fmt === "money" ? short(v) : num(v);
      });
      if (k < 1 && root.isConnected) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  function drawLedger(turn) {
    const frame = scene && scene.querySelector(".frame");
    if (!frame) return;
    const article = frame.querySelector(".ledger");
    if (!book.data) return;            // the plain ledger stays up until the book arrives
    const h = houseOf(view.house) || houseOf(S.me && S.me.id) || book.data.houses[0];
    view.house = h.id;
    const book2 = document.createElement("article");
    book2.className = "ledger lg-book" + (turn ? " lg-turn-" + turn : "");
    book2.dataset.spread = view.spread;
    book2.innerHTML = spreadHtml(h);
    if (article) article.replaceWith(book2); else frame.prepend(book2);
    let nav = frame.querySelector(".lg-nav");
    if (!nav) {
      nav = document.createElement("div");
      nav.className = "lg-nav";
      frame.querySelector(".actions").before(nav);
    }
    nav.innerHTML = `<button type="button" class="lg-flip" data-go="-1"${view.spread === 0 ? " disabled" : ""}>‹ ${te("fin.page_prev")}</button>
      <span class="lg-dots">${[0, 1].map(i => `<i class="${i === view.spread ? "on" : ""}"></i>`).join("")}</span>
      <button type="button" class="lg-flip" data-go="1"${view.spread === 1 ? " disabled" : ""}>${te("fin.page_next")} ›</button>`;
    nav.querySelectorAll("[data-go]").forEach(b => b.addEventListener("click", () => {
      const to = Math.max(0, Math.min(1, view.spread + Number(b.dataset.go)));
      if (to === view.spread) return;
      view.spread = to;
      drawLedger(b.dataset.go > 0 ? "fwd" : "back");
    }));
    book2.querySelectorAll(".lg-row[data-house]").forEach(row => {
      const pick = () => { view.house = row.dataset.house; drawLedger("swap"); };
      row.addEventListener("click", pick);
      row.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(); } });
    });
    if (view.spread === 1) countUp(book2);
  }

  function drawWinnerExtras() {
    const box = scene && scene.querySelector(".winner");
    if (!box || box.querySelector(".lg-win-card") || !book.data) return;
    const h = book.data.houses[0];
    const p = Object.assign({ color: h.color }, seat(h.id), { name: h.name, firm: h.firm });
    box.insertAdjacentHTML("afterbegin", `<div class="lg-win-card">${portrait(p)}${rankSeal(h.rank_id, "lg-win-seal")}</div>`);
    const sub = box.querySelector(".lg-win-epithet");
    if (!sub) box.insertAdjacentHTML("beforeend",
      `<p class="lg-win-epithet">${esc(h.name)} ${te("fin.epithet." + h.epithet)}</p>`);
  }

  /* ----------------------------------------------------------- scenes -- */
  function play(kind, elapsed, state, data, app) {
    const clock = performance.now() - Math.max(0, elapsed);
    scene = document.createElement("div");
    scene.className = "ceremony";
    scene.dataset.scene = kind;
    scene.style.setProperty("--elapsed", Math.max(elapsed, 0) + "ms");
    scene.innerHTML = `<div class="scenery" aria-hidden="true"><div class="harbor"></div>
      <div class="clipper"><img src="/assets/ceremony-clipper.png" alt=""></div>
      <div class="mist"></div><div class="shade"></div></div><div class="frame"></div>`;
    document.body.append(scene);
    behind = app;
    behind.inert = true;
    const frame = scene.querySelector(".frame");
    const after = (target, next) => { timer = setTimeout(next, Math.max(0, target - (performance.now() - clock))); };

    if (kind === "opening") {
      frame.innerHTML = `<div class="wordmark"><h1 class="title">${brandHtml(data)}</h1>
        <div class="rule" aria-hidden="true">◆</div></div>
        <p class="place">${te("ceremony.opening")}</p><p class="cue" role="status"></p>`;
      const cue = frame.querySelector(".cue");
      function count() {
        const remaining = openingLength - (performance.now() - clock);
        if (remaining <= 0) {
          cue.textContent = t("ceremony.departing");
        } else if (remaining <= 3000) {
          const number = Math.ceil(remaining / 1000);
          cue.innerHTML = `<span class="count">${number}</span>`;
          after(openingLength - (number - 1) * 1000, count);
        } else {
          after(openingLength - 3000, count);
        }
      }
      count();
      return;
    }

    load(state);
    view = { spread: 0, house: (state.me && state.me.id) || null };
    const standings = ranked(state);
    const winner = standings[0];
    frame.innerHTML = `<h1 class="title">${te("ceremony.finale")}</h1>
      <p class="place">${esc(state.date)}</p>`;
    function revealWinner() {
      frame.innerHTML = `<div class="winner" role="status"><p>${te("ceremony.winner")}</p>
        <h2>${esc(winner.firm)}</h2>
        <p>${te("ceremony.winner_detail", { name: winner.name, worth: money(winner.worth) })}</p></div>`;
      drawWinnerExtras();
      after(finaleLength, revealLedger);
    }
    function revealLedger() {
      scene.classList.add("has-results");
      frame.innerHTML = `<article class="ledger lg-wait">
        <section>${plainStory(state, data.ports)}</section>
        <section><h2>${te("ceremony.standings")}</h2><table><thead>
          <tr><th scope="col">${te("ceremony.house")}</th><th scope="col">${te("ceremony.worth")}</th></tr></thead>
          <tbody>${standings.map((house, i) =>
            `<tr><td>${i + 1}. ${esc(house.firm)}</td><td>${esc(money(house.worth))}</td></tr>`).join("")}</tbody>
        </table></section></article>
        <div class="actions"><button class="details" type="button">${te("ceremony.details")}</button>
        ${state.me ? `<button class="details free-play" type="button">${te("ceremony.free_play")}</button>` : ""}</div>`;
      const button = frame.querySelector("button.details");
      button.addEventListener("click", () => { dismissedKey = sceneKey; close(); });
      frame.querySelector("button.free-play")?.addEventListener("click", () => {
        dismissedKey = sceneKey; close();
        window.dispatchEvent(new CustomEvent("ceremony:free-play"));
      });
      drawLedger();
      button.focus({ preventScroll: true });
    }
    if (elapsed >= 5500) revealWinner();
    else after(5500, revealWinner);
  }

  function sync(state, data, app) {
    D = data; S = state;
    const watching = state.me || app.classList.contains("board-room");
    const opening = watching && state.phase === "lobby" && state.start_at;
    const ending = watching && (state.phase === "ended" || state.free_play) && state.ended_at && state.voyage_story;
    if (state.phase === "ended" || state.free_play) load(state);
    const key = opening ? state.game_id + ":start:" + state.start_at
      : ending ? state.game_id + ":end:" + state.ended_at : null;
    // The ledger opened from the results screen stays open while the game is still over.
    if (scene && sceneKey === state.game_id + ":ledger" && (state.phase === "ended" || state.free_play)) return;
    if (scene && sceneKey === key) {
      if (opening) {
        const heading = scene.querySelector(".wordmark h1");
        const markup = brandHtml(data);
        if (heading.innerHTML !== markup) heading.innerHTML = markup;
      }
      return;
    }
    close();
    if (!key || key === dismissedKey) return;
    const elapsed = opening ? openingLength - (state.start_at - state.server_time) * 1000
      : (state.server_time - state.ended_at) * 1000;
    if (ending && elapsed >= finaleLength) return;
    sceneKey = key;
    play(opening ? "opening" : "finale", elapsed, state, data, app);
  }

  /* Opens the finale's ledger on demand (the results screen's "Ledger of the Voyage" button), straight
     to the book with no ceremony before it. */
  function openLedger(state, data, app) {
    D = data; S = state;
    if (scene) close();
    load(state);
    sceneKey = state.game_id + ":ledger";
    play("finale", finaleLength + 6000, state, data, app);
  }

  return { sync, story, ranked, openLedger };
})();
