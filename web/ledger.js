"use strict";

/* THE ACCOUNTING LEDGER (20 Nov 2026). The House's own books, kept by the bookkeeper, Mademoiselle Céleste
   Vautrin (cast "bookkeeper"). It replaced Port > Accounts and opens full screen from its own button on
   the tab rail, under the Tally Book. It looks like the finale's Ledger of the Voyage: a leather-bound book
   of two facing pages, a stitched gutter, pages that turn, figures that count up and charts drawn in ink.

     Spread 1  The Purse          left: what the House owns and owes (net worth), worth month by month
                                  right: profit and loss (last voyage / this year / whole game) as a waterfall
     Spread 2  The Counting House left: silver, bank and moneylender, with the sliders and a live projection
                                  right: the fleet's accounts (worth, wages, repairs; sell, lay up, recall,
                                  repair), the wage chart, protection
     Spread 3  Dues & Duties      left: housing (warehouses, the great house), the Mayor's bill if you sail now
                                  right: who got your silver, dues and Port Authority tax port by port

   21 Nov 2026 redesign: every page is two layers. Underneath, a big faded persona "wall" (her wide wallpaper
   picture, else her portrait) bleeds into the linen; on top, the page's own scroller, laid out in TWO columns
   (CSS multicol, so a narrow window falls back to one) with the pictures made large: the bookkeeper stands
   over the left page, the banker and lender sit behind their desks, every taker and warehouse has a big card.
   The wall roles: Purse bookkeeper + banker, Counting House lender + shipwright, Dues comprador + Port Authority.

   Live figures come from the state (S.me). The month-by-month history, who got the silver and tax by port
   come from the Tally Book's own numbers (/api/stats), fetched when the Ledger opens and once a month.
   Every button is an action the game already has (bank, loan, sell_ship, lay_up, recall, repair,
   protection), sent through player.js, so the rules are the server's. Nothing in the engine changed.
   It is drawn into the "ledger" region by player.js render(); Ledger.after() runs the count-ups and hooks
   the charts; Ledger.drag() keeps the projection in step with the bank and loan sliders. */
const Ledger = (() => {
  const SPREADS = ["purse", "house", "dues"];
  const hist = { turn: null, gid: null, busy: false, data: null, failed: false };
  // animUntil: the page's own motion (on opening and on a page turn); drawUntil: only the charts, when the
  // history arrives a moment later; openedAt: the one fade-in, when the book is first opened. A redraw for any
  // other reason (a state update, a slider let go) shows the page settled, so nothing blinks.
  let animUntil = 0, animKey = "", flip = "", counted = "", drawUntil = 0, openedAt = 0;
  let lastBody = "", lastOut = "";     // the book as last drawn: unchanged contents keep the same markup
  const charts = {};          // chart id -> what its hover read-out needs

  /* ------------------------------------------------------------ helpers -- */
  const me = () => S.me;
  const signedMoney = n => (n > 0.5 ? "+" : n < -0.5 ? "−" : "") + money(Math.abs(n));
  const toneOf = n => n > 0.5 ? "up" : n < -0.5 ? "down" : "";
  const fig = (n, cls, plain) => `<span class="ldg-fig ${cls || ""}"${plain ? "" : ` data-count="${Math.round(n)}"`}>${money(n)}</span>`;
  const keeperName = () => ((VS.cast || {}).bookkeeper || {}).name || "Céleste Vautrin";
  const yardHere = () => typeof yardAt === "function" ? yardAt(S.me.port) : !!(D.ports[S.me.port] || {}).shipyard;
  const isHome = () => S.me.port === myHome();

  /* Pictures go through Media.html, so the Media Library knows they are on screen: in "random" mode the
     pick holds while the Ledger is open (a fresh one each time it is opened) and any swap happens in place.
     Picking them by hand made each redraw choose again, which changed the page and redrew the whole book:
     the flicker on the Counting House and Dues pages (20 Nov 2026). */
  const PIC = { mode: "random" };
  function keeperHtml(mood) {
    const role = mood && Media.has("persona", "bookkeeper", mood) ? mood : "portrait";
    return Media.html("persona", "bookkeeper", role, "pz", ((VS.cast || {}).bookkeeper || {}).portrait || "",
      Object.assign({ slot: "ldg-keeper" }, PIC));
  }
  function personaHtml(key, slot) {
    return Media.html("persona", key, "portrait", "ldg-ph", ((VS.cast || {})[key] || {}).portrait || "",
      Object.assign({ slot: "ldg-who:" + key + (slot || "") }, PIC));
  }
  // The big faded picture under a page: her wide "wallpaper" shot (the only place one is used), else her portrait.
  // Masthead pictures are Dashboard-only and are never picked here.
  const WALLS = { purse: ["bookkeeper", "banker"], house: ["lender", "shipwright"], dues: ["comprador", "taxlady"] };
  function wallHtml(key, slot) {
    const pic = Media.html("persona", key, "wallpaper", "ldg-wallimg", ((VS.cast || {})[key] || {}).portrait || "",
      Object.assign({ slot: "ldg-wall:" + slot, scene: "wallpaper" }, PIC));
    return pic ? `<div class="ldg-wall" aria-hidden="true">${pic}</div>` : "";
  }
  const boxArt = (key, slot) => { const p = personaHtml(key, slot); return p ? `<div class="ldg-boxart" aria-hidden="true">${p}</div>` : ""; };

  /* --------------------------------------------------- opening, history -- */
  function open(spread) {
    if (!ui.ledger) openedAt = Date.now();
    ui.ledger = true; ui.tally = false; ui.meOpen = false;
    if (spread && SPREADS.includes(spread)) ui.ledgerSpread = spread;
    if (!ui.ledgerSpread) ui.ledgerSpread = "purse";
    animUntil = 0;
    load();
    render();
    hello();
  }
  function close() { ui.ledger = false; render(); }
  function turnTo(spread) {
    const from = SPREADS.indexOf(ui.ledgerSpread), to = SPREADS.indexOf(spread);
    if (to < 0 || to === from) return;
    flip = to > from ? "fwd" : "back";
    ui.ledgerSpread = spread;
    animUntil = 0;
    render();
  }
  function step(d) {
    const i = SPREADS.indexOf(ui.ledgerSpread) + d;
    if (i >= 0 && i < SPREADS.length) turnTo(SPREADS[i]);
  }

  async function load() {
    if (hist.busy || (hist.turn === S.turn && hist.gid === S.game_id && (hist.data || hist.failed))) return;
    hist.busy = true;
    try {
      const r = await fetch("/api/stats?scope=voyage&token=" + encodeURIComponent(token || ""));
      const j = await r.json();
      hist.data = j && j.ok ? j.voyage : null;
      hist.failed = !hist.data;
    } catch (e) {
      hist.data = null; hist.failed = true;
    }
    hist.busy = false; hist.turn = S.turn; hist.gid = S.game_id;
    drawUntil = Date.now() + 2600;      // the charts that just arrived draw themselves in; nothing else moves
    if (ui.ledger) render();
  }

  // Her greeting, read aloud once a month when the Ledger opens (server.py _acct_hello).
  function hello() {
    const a = S.me && S.me.acct, plan = S.voice && S.voice.acct;
    if (!a || !a.hello || !plan || !plan[0]) return;
    const tag = "acct:" + S.game_id + ":" + S.turn;
    if (ui.acctSpoken === tag) return;
    ui.acctSpoken = tag;
    Voice.say([Object.assign({ text: a.hello, tag }, plan[0])], { group: "msg", replace: "msg", front: true });
  }

  /* --------------------------------------------------------------- frame -- */
  function html() {
    if (!ui.ledger || !S.me) return "";
    if (hist.turn !== S.turn || hist.gid !== S.game_id) load();
    const spread = ui.ledgerSpread || "purse", i = SPREADS.indexOf(spread);
    const key = spread + ":" + S.turn;
    if (key !== animKey) { animKey = key; animUntil = 0; }
    const fresh = !animUntil;            // just opened, or a page just turned
    if (fresh) animUntil = Date.now() + 2600;
    const now = Date.now(), anim = now < animUntil, draw = !anim && now < drawUntil, opening = now - openedAt < 450;
    const turn = anim && flip ? " ldg-turn-" + flip : "";
    if (!anim) flip = "";
    const a = S.me.acct || {}, mood = a.mood || "sly";
    const pic = keeperHtml(mood);
    const tabs = SPREADS.map((k, n) => `<button type="button" class="ldg-tab${k === spread ? " on" : ""}" data-act="acct_spread" data-v="${k}"
        aria-pressed="${k === spread}"><i>${["I", "II", "III"][n]}</i><span>${te("acct.spread." + k)}</span></button>`).join("");
    const pages = spread === "purse" ? [purseLeft(), purseRight()] : spread === "house" ? [houseLeft(), houseRight()] : [duesLeft(), duesRight()];
    const body = `" role="dialog" aria-modal="true" aria-label="${te("acct.title")}">
      <div class="ldg-frame">
        <header class="ldg-head">
          <figure class="ldg-keeper mood-${esc(mood)}">${pic || `<span class="ldg-quill" aria-hidden="true">${QUILL}</span>`}</figure>
          <div class="ldg-who">
            <span class="ldg-kicker">${te("acct.keeper", { name: keeperName() })}</span>
            <h1>${te("acct.title")}</h1>
            ${a.hello ? `<p class="ldg-line">“${esc(a.hello)}”</p>` : ""}
            <small>${te("acct.date", { port: esc(portName(S.me.port)), date: esc(S.date) })}</small>
          </div>
          <nav class="ldg-tabs" aria-label="${te("acct.title")}">${tabs}</nav>
          <button type="button" class="ldg-x" data-act="acct_close" aria-label="${te("acct.close")}" title="${te("acct.close")}">✕</button>
        </header>
        ${S.me.ready ? `<p class="ldg-locked">${te("acct.locked")}</p>` : ""}
        <article class="ldg-book${turn}" data-spread="${spread}">
          <section class="ldg-page ldg-left">${wallHtml(WALLS[spread][0], spread + "L")}<div class="ldg-scroll">${pages[0]}</div></section>
          <section class="ldg-page ldg-right">${wallHtml(WALLS[spread][1], spread + "R")}<div class="ldg-scroll">${pages[1]}</div></section>
        </article>
        <footer class="ldg-foot">
          <button type="button" class="ldg-flip" data-act="acct_step" data-d="-1"${i === 0 ? " disabled" : ""}>‹ ${te("acct.prev")}</button>
          <span>${te("acct.folio", { n: i + 1, of: SPREADS.length })}</span>
          <button type="button" class="ldg-flip" data-act="acct_step" data-d="1"${i === SPREADS.length - 1 ? " disabled" : ""}>${te("acct.next")} ›</button>
        </footer>
      </div></div>`;
    // Same contents as last time: hand back the very same markup, animation classes and all, so player.js
    // sees nothing new and leaves the book alone (switching an animation off is no reason to rebuild it).
    if (!fresh && body.replace(/ ldg-turn-(fwd|back)/, "") === lastBody) return lastOut;
    lastBody = body.replace(/ ldg-turn-(fwd|back)/, "");
    lastOut = `<div class="ldg${anim ? " ldg-anim" : ""}${draw ? " ldg-draw" : ""}${opening ? " ldg-opening" : ""}` + body;
    return lastOut;
  }

  /* ---------------------------------------------------- spread 1: purse -- */
  function balance() {
    const m = me();
    let cargo = 0;
    Object.keys(m.cargo || {}).forEach(g => {
      const q = m.cargo[g] || 0;
      if (q > 0 && Number.isFinite(m.prices[g])) cargo += quote(g, q, "sell");
    });
    const fleet = (m.ships || []).reduce((n, s) => n + (s.value || 0), 0);
    const other = m.worth - m.cash - m.bank + m.debt - cargo - fleet;
    return { cash: m.cash, bank: m.bank, cargo, fleet, other, debt: m.debt, worth: m.worth };
  }

  function purseLeft() {
    const b = balance(), m = me();
    const row = (label, sub, n, cls) => `<li class="${cls || ""}"><span><b>${label}</b>${sub ? `<small>${sub}</small>` : ""}</span>${fig(n, cls)}</li>`;
    const owns = [
      row(te("acct.bs.cash"), "", b.cash),
      row(te("acct.bs.bank"), "", b.bank),
      b.cargo ? row(te("acct.bs.cargo"), te("acct.bs.cargo_sub", { port: esc(portName(m.port)) }), b.cargo) : "",
      row(te("acct.bs.fleet"), te("acct.bs.fleet_sub", { n: (m.ships || []).length }), b.fleet),
      Math.abs(b.other) >= 1 ? row(te("acct.bs.other"), te("acct.bs.other_sub"), b.other) : "",
    ].join("");
    const owes = b.debt > 0 ? row(te("acct.bs.debt"), te("acct.bs.debt_sub", { rate: pct(D.loan_rate, 2) }), -b.debt, "down") : "";
    // The proportions bar: what the worth is made of, with the debt hanging below it.
    const parts = [["cash", b.cash], ["bank", b.bank], ["cargo", b.cargo], ["fleet", b.fleet], ["other", Math.max(0, b.other)]];
    const gross = parts.reduce((n, p) => n + Math.max(0, p[1]), 0) || 1;
    const bar = parts.filter(p => p[1] > 0).map(([k, v], n) =>
      `<i class="ldg-seg s-${k}" style="--w:${(100 * v / gross).toFixed(2)}%;--d:${n * 0.12}s" title="${esc(t("acct.chart." + (k === "other" ? "fleet" : k)))}: ${esc(money(v))}"></i>`).join("");
    const debtBar = b.debt > 0 ? `<i class="ldg-seg s-debt" style="--w:${Math.min(100, 100 * b.debt / gross).toFixed(2)}%"></i>` : "";
    return `<div class="ldg-top"><h2>${te("acct.bs.title")}</h2>
        <div class="ldg-worth ${toneOf(b.worth)}"><span>${te("acct.bs.worth")}</span>${fig(b.worth, "big")}${Ranks.label(m)}</div></div>
      <div class="ldg-parts" aria-hidden="true"><div class="ldg-bar">${bar}</div>${debtBar ? `<div class="ldg-bar debt">${debtBar}</div>` : ""}</div>
      <div class="ldg-cols">
        <section class="ldg-blk"><h3>${te("acct.bs.owns")}</h3><ul class="ldg-sheet">${owns}</ul></section>
        <section class="ldg-blk">${owes ? `<h3>${te("acct.bs.owes")}</h3><ul class="ldg-sheet">${owes}</ul>` : `<h3>${te("acct.bs.worth")}</h3>`}
          <ul class="ldg-sheet total"><li><span><b>${te("acct.bs.worth")}</b></span>${fig(b.worth, toneOf(b.worth))}</li></ul></section>
        <section class="ldg-blk ldg-span"><h3>${te("acct.chart.title")}</h3>${worthChart()}</section>
      </div>`;
  }

  function months() {
    const v = hist.data && hist.data.me;
    return v && Array.isArray(v.months) ? v.months.filter(r => r && Number.isFinite(r.worth)) : [];
  }

  /* Worth, month by month: silver, bank, cargo and fleet stacked, the debt hanging below the line, net
     worth drawn on top in red ink. A finger or the mouse along it reads any month. */
  function worthChart() {
    if (!hist.data) return `<p class="ldg-muted">${te(hist.failed ? "acct.chart.none" : "acct.chart.loading")}</p>`;
    const rows = months();
    if (rows.length < 2) return `<p class="ldg-muted">${te("acct.chart.none")}</p>`;
    const W = 520, H = 190, padL = 46, padR = 8, padT = 10, padB = 22;
    const parts = r => {
      const cargo = Math.max(0, r.goods_value || 0), fleet = Math.max(0, r.fleet_value || 0);
      return { cash: Math.max(0, r.cash || 0), bank: Math.max(0, r.bank || 0), cargo, fleet, debt: Math.max(0, r.debt || 0), worth: r.worth };
    };
    const P = rows.map(parts);
    const top = Math.max(1, ...P.map(p => Math.max(p.cash + p.bank + p.cargo + p.fleet, p.worth)));
    const bot = Math.max(0, ...P.map(p => Math.max(p.debt, -p.worth)));
    const span = top + bot || 1;
    const x = i => padL + (W - padL - padR) * (rows.length === 1 ? 0 : i / (rows.length - 1));
    const y = v => padT + (H - padT - padB) * (top - v) / span;
    const keys = ["cash", "bank", "cargo", "fleet"];
    let below = P.map(() => 0);
    const areas = keys.map((k, n) => {
      const upper = P.map((p, i) => below[i] + p[k]);
      const d = "M" + upper.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join("L") +
        "L" + below.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).reverse().join("L") + "Z";
      below = upper;
      return `<path class="ldg-area a-${k}" style="--d:${0.2 + n * 0.15}s" d="${d}"/>`;
    }).join("");
    const debt = bot > 0 ? `<path class="ldg-area a-debt" d="M${P.map((p, i) => `${x(i).toFixed(1)},${y(0).toFixed(1)}`).join("L")}L${P.map((p, i) => `${x(i).toFixed(1)},${y(-p.debt).toFixed(1)}`).reverse().join("L")}Z"/>` : "";
    const line = `<path class="ldg-line" pathLength="1" d="M${P.map((p, i) => `${x(i).toFixed(1)},${y(p.worth).toFixed(1)}`).join("L")}"/>`;
    const zero = `<line class="ldg-zero" x1="${padL}" x2="${W - padR}" y1="${y(0).toFixed(1)}" y2="${y(0).toFixed(1)}"/>`;
    const ticks = [top, top / 2, 0].concat(bot > 0 && y(-bot) - y(0) > 14 ? [-bot] : []).map(v =>
      `<text class="ldg-axis" x="${padL - 6}" y="${(y(v) + 3).toFixed(1)}" text-anchor="end">${esc(moneyShort(v))}</text>`).join("");
    const every = Math.max(1, Math.ceil(rows.length / 6));
    const dates = rows.map((r, i) => i % every === 0 || i === rows.length - 1
      ? `<text class="ldg-axis" x="${x(i).toFixed(1)}" y="${H - 6}" text-anchor="${i === 0 ? "start" : i === rows.length - 1 ? "end" : "middle"}">${esc(r.date || "")}</text>` : "").join("");
    const last = P[P.length - 1];
    const end = `<circle class="ldg-end" cx="${x(P.length - 1).toFixed(1)}" cy="${y(last.worth).toFixed(1)}" r="4"/>`;
    const id = "worth";
    charts[id] = { xs: rows.map((r, i) => x(i)), W, rows: rows.map((r, i) => ({ date: r.date, ...P[i] })), y, kind: "worth" };
    const legend = keys.concat(bot > 0 ? ["debt"] : []).map(k => `<span class="lg-${k}"><i></i>${te("acct.chart." + k)}</span>`).join("") +
      `<span class="lg-worth"><i></i>${te("acct.chart.worth")}</span>`;
    return `<figure class="ldg-chart" data-chart="${id}">
        <svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="${te("acct.chart.title")}">
          ${areas}${debt}${zero}${line}${end}${ticks}${dates}<line class="ldg-cursor" x1="0" x2="0" y1="${padT}" y2="${H - padB}"/></svg>
        <div class="ldg-tip" hidden></div>
        <figcaption><span class="ldg-legend">${legend}</span><small>${te("acct.chart.hint")}</small></figcaption></figure>`;
  }

  function plLines() {
    const bk = me().books || {}, range = ui.plRange || "voyage";
    return range === "year" ? bk.year : range === "game" ? bk.game : (bk.last || {}).lines;
  }

  function purseRight() {
    const bk = me().books || {}, range = ui.plRange || "voyage", lines = plLines();
    const seg = `<div class="ldg-seg3" role="group" aria-label="${te("port.pl.range")}">${["voyage", "year", "game"].map(r =>
      `<button type="button" data-act="pl_range" data-v="${r}" aria-pressed="${range === r}">${te("port.pl.range_" + r)}</button>`).join("")}</div>`;
    const title = range === "voyage" && bk.last
      ? te(bk.last.sailed ? "port.pl.title_voyage" : "port.pl.title_month", { from: esc(portName(bk.last.from)), to: esc(portName(bk.last.to)), date: esc(bk.last.date) })
      : te("port.pl.title");
    if (!lines || !Object.keys(lines).length) {
      return `<div class="ldg-top"><h2>${te("acct.pl.title")}</h2>${seg}<p class="ldg-muted">${te(range === "voyage" && !bk.last ? "port.pl.none_yet" : "port.pl.empty")}</p></div>`;
    }
    const known = new Set(PL_GROUPS.flatMap(g => g[1]));
    const groups = PL_GROUPS.concat([["other", Object.keys(lines).filter(k => !known.has(k))]]);
    let blocks = "";
    const steps = [];
    groups.forEach(([grp, keys]) => {
      const here = keys.filter(k => Math.round(lines[k] || 0) !== 0);
      if (!here.length) return;
      const sub = here.reduce((n, k) => n + lines[k], 0);
      const name = grp === "other" ? te("acct.pl.grp_other") : te("port.pl.grp_" + grp);
      steps.push({ grp, name, sub, lines: here.map(k => [T["port.pl." + k] != null ? t("port.pl." + k) : k, lines[k]]) });
      blocks += `<section class="ldg-blk"><table class="ldg-table ldg-pl"><tr class="ldg-grp g-${grp}"><td colspan="2">${name}</td></tr>` +
        here.map(k => `<tr><td>${T["port.pl." + k] != null ? te("port.pl." + k) : esc(k)}</td><td class="n ${toneOf(lines[k])}">${esc(signedMoney(lines[k]))}</td></tr>`).join("") +
        `<tr class="ldg-sub"><td>${grp === "other" ? name : te("port.pl.sub_" + grp)}</td><td class="n ${toneOf(sub)}">${esc(signedMoney(sub))}</td></tr></table></section>`;
    });
    const total = plTotal(lines);
    return `<div class="ldg-top"><h2>${te("acct.pl.title")}</h2>${seg}<p class="ldg-caption">${title}</p></div>
      <div class="ldg-cols">
        <section class="ldg-blk ldg-span"><h3>${te("acct.pl.flow")}</h3>${waterfall(steps, total)}</section>
        ${blocks}
        <section class="ldg-blk ldg-span"><table class="ldg-table"><tr class="ldg-total"><td>${te("port.pl.total_" + range)}</td><td class="n ${toneOf(total)}">${fig(total, toneOf(total))}</td></tr></table>
          ${portUnrealised()}${portIdle()}<p class="ldg-fine">${te("port.pl.note")}</p></section>
      </div>`;
  }

  /* The waterfall: each group of the profit and loss steps the running total up (jade) or down (oxblood),
     ending on the net. Tap or hover a bar for its lines. */
  function waterfall(steps, total) {
    if (!steps.length) return "";
    const W = 520, H = 170, padT = 16, padB = 34, padL = 8, padR = 8;
    let run = 0;
    const bars = steps.map(s => { const from = run; run += s.sub; return Object.assign({ from, to: run }, s); });
    bars.push({ grp: "net", name: t("acct.pl.net"), from: 0, to: total, sub: total, net: true, lines: [] });
    const hi = Math.max(0, ...bars.map(b => Math.max(b.from, b.to))), lo = Math.min(0, ...bars.map(b => Math.min(b.from, b.to)));
    const span = hi - lo || 1;
    const y = v => padT + (H - padT - padB) * (hi - v) / span;
    const slot = (W - padL - padR) / bars.length, bw = Math.min(64, slot * 0.62);
    const id = "flow";
    charts[id] = { kind: "flow", bars: bars.map(b => ({ name: b.name, sub: b.sub, lines: b.lines })), slot, padL };
    const body = bars.map((b, i) => {
      const x0 = padL + slot * i + (slot - bw) / 2, top = y(Math.max(b.from, b.to)), h = Math.max(1.5, Math.abs(y(b.from) - y(b.to)));
      const cls = b.net ? (b.to >= 0 ? "net up" : "net down") : b.sub >= 0 ? "up" : "down";
      const join = i < bars.length - 1 ? `<line class="ldg-join" x1="${(x0 + bw).toFixed(1)}" x2="${(x0 + slot).toFixed(1)}" y1="${y(b.to).toFixed(1)}" y2="${y(b.to).toFixed(1)}"/>` : "";
      const label = `<text class="ldg-wf-v ${b.sub >= 0 ? "up" : "down"}" x="${(x0 + bw / 2).toFixed(1)}" y="${(top - 4).toFixed(1)}" text-anchor="middle">${esc(moneyShort(b.sub))}</text>`;
      const name = `<text class="ldg-axis" x="${(x0 + bw / 2).toFixed(1)}" y="${H - 18}" text-anchor="middle">${esc(b.name.length > 14 ? b.name.split(" ")[0] : b.name)}</text>`;
      return `<g class="ldg-wf ${cls}" data-i="${i}" style="--d:${0.15 + i * 0.18}s"><rect x="${x0.toFixed(1)}" y="${top.toFixed(1)}" width="${bw.toFixed(1)}" height="${h.toFixed(1)}" rx="2"/>${label}${name}</g>${join}`;
    }).join("");
    const zero = `<line class="ldg-zero" x1="${padL}" x2="${W - padR}" y1="${y(0).toFixed(1)}" y2="${y(0).toFixed(1)}"/>`;
    return `<figure class="ldg-chart" data-chart="${id}"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${te("acct.pl.flow")}">${zero}${body}</svg>
      <div class="ldg-tip" hidden></div><figcaption><small>${te("acct.pl.hint")}</small></figcaption></figure>`;
  }

  /* ------------------------------------------- spread 2: counting house -- */
  function houseLeft() {
    const m = me(), home = isHome(), bankHere = home || m.bank_here;
    const stat = (label, n, cls) => `<div class="ldg-stat ${cls || ""}"><span>${label}</span>${fig(n, cls)}</div>`;
    const stats = `<div class="ldg-stats">${stat(te("acct.money.cash"), m.cash)}${stat(te("acct.money.bank"), m.bank, "up")}${stat(te("acct.money.debt"), m.debt, m.debt > 0 ? "down" : "")}</div>`;
    const bank = bankHere
      ? desk("banker", te("bank.title"), serviceSlider("bank", t("bank.title")))
      : `<p class="ldg-away ldg-blk">${te("acct.away.bank", { home: esc(portName(myHome())), rate: pct(D.bank_rate, 2) })}</p>`;
    const loan = home
      ? desk("lender", te("loan.title"), `${serviceSlider("loan", t("loan.title"))}
          <p class="ldg-fine">${te("acct.money.room")} <b class="ldg-fig up">${money(m.loan_room)}</b></p>`)
      : `<p class="ldg-away ldg-blk">${te("acct.away.loan", { home: esc(portName(myHome())) })}</p>`;
    const rest = typeof bankRestHtml === "function" ? bankRestHtml("ldg-rest") : "";
    return `<div class="ldg-top"><h2>${te("acct.money.title")}</h2>${stats}</div>
      <div class="ldg-cols">${rest ? `<div class="ldg-blk ldg-span">${rest}</div>` : ""}${bank}${loan}</div>
      <h3>${te("acct.proj.title")}</h3><div class="ldg-proj" id="ldgProj">${projection()}</div>
      <p class="ldg-fine">${te("acct.proj.hint")}</p>`;
  }

  /* A desk: a dark panel with the person behind it, large and faded in from the right. */
  function desk(who, title, inner, cls) {
    const pic = personaHtml(who, ":desk");
    return `<div class="ldg-desk ldg-blk ${cls || ""}">${pic ? `<div class="ldg-deskart" aria-hidden="true">${pic}</div>` : ""}
      <header class="ldg-deskhead"><b>${title}</b></header>${inner}</div>`;
  }

  /* Next month's figures for whatever the bank and loan sliders are set to right now. */
  function projected() {
    const m = me();
    let bank = m.bank, debt = m.debt, cash = m.cash;
    if (m.port === myHome() || m.bank_here) {
      const tr = serviceTransfer("bank");
      bank = tr.at; cash -= tr.at - tr.have;
    }
    if (m.port === myHome()) {
      const tr = serviceTransfer("loan");
      const d = tr.at - tr.have;          // + borrow, − repay
      debt = Math.max(0, m.debt + d); cash += d;
    }
    return { bank, debt, cash };
  }
  function projection() {
    const m = me(), p = projected();
    const bankInt = p.bank * D.bank_rate, loanInt = p.debt * D.loan_rate, net = bankInt - loanInt;
    const row = (label, value, cls) => `<div class="ldg-prow ${cls || ""}"><span>${label}</span><b>${value}</b></div>`;
    const c = m.collectors;
    const line = c && c.line ? (p.debt > c.line
      ? row(te("acct.proj.line"), te("acct.proj.over", { amount: money(p.debt - c.line) }), "down")
      : row(te("acct.proj.line"), te("acct.proj.under", { amount: money(c.line - p.debt) }), "up")) : "";
    const mug = D.mug || {};
    const risky = p.cash > (mug.mug_threshold || Infinity);
    return row(te("acct.proj.bank_int"), esc(signedMoney(bankInt)), "up") +
      (p.debt > 0 || m.debt > 0 ? row(te("acct.proj.loan_int"), esc(signedMoney(-loanInt)), "down") : "") +
      row(te("acct.proj.net_int"), esc(signedMoney(net)), toneOf(net)) +
      row(te("acct.proj.debt_next"), p.debt > 0 ? esc(money(p.debt * (1 + D.loan_rate))) : te("acct.proj.never"), p.debt > 0 ? "down" : "up") +
      line +
      row(te("acct.proj.ashore"), esc(money(p.cash)) + ` <small>${risky
        ? te("acct.proj.risk", { lo: Math.round((mug.mug_min || 0) * 100), hi: Math.round((mug.mug_max || 0) * 100) })
        : te("acct.proj.safe")}</small>`, risky ? "warn" : "");
  }
  function drag() {
    const el = document.getElementById("ldgProj");
    if (el) el.innerHTML = projection();
  }

  function houseRight() {
    const m = me(), home = isHome(), yard = yardHere(), locked = m.ready;
    const traders = (m.ships || []).filter(s => roleOf(s.type) === "trader").length;
    const free = Math.max(0, m.capacity - m.used);
    const layPct = Math.round(100 * (D.laid_up_wage != null ? D.laid_up_wage : 0.25));
    const rows = (m.ships || []).map((s, i) => {
      const spec = D.ships[s.type] || {}, role = roleOf(s.type);
      const lastTrader = D.keep_trader !== false && role === "trader" && traders <= 1;
      const acts = [
        s.repair ? btn(te("acct.fleet.repair_btn", { cost: money(s.repair) }), "repair", `data-i="${i}"`, "ldg-btn", locked || s.repair > m.cash) : "",
        yard ? btn(te("acct.fleet.sell", { value: money(s.value) }), "sellship", `data-i="${i}"`, "ldg-btn ghost", locked || m.ships.length < 2 || lastTrader) : "",
        home && m.ships.length > 1 && !lastTrader ? btn(te("acct.fleet.layup"), "layup",
          `data-i="${i}" title="${esc(t("acct.fleet.saving", { amount: money(Math.round((s.wage || 0) * (1 - layPct / 100))) }))}"`,
          "ldg-btn ghost", locked || (s.hold || 0) > free) : "",
      ].join("");
      return `<tr class="r-${role}"><td class="ldg-ship"><span class="ldg-shipimg">${Media.html("ship", s.type, "card", "", D.graphics.ships[s.type], Object.assign({ slot: "ldg:" + s.name }, PIC))}</span>
          <span><b>${esc(s.name)}</b><small>${esc(spec.name || s.type)}${s.crippled ? " · " + te("fleet.crippled") : ""}</small></span></td>
        <td class="n">${money(s.value)}</td><td class="n down">${money(s.wage || 0)}</td><td class="n ${s.repair ? "warn" : ""}">${s.repair ? money(s.repair) : "—"}</td></tr>
        ${acts ? `<tr class="ldg-acts"><td colspan="4"><div class="ldg-actrow">${acts}</div></td></tr>` : ""}`;
    }).join("");
    const wage = (m.ships || []).reduce((n, s) => n + (s.wage || 0), 0);
    const laid = m.laid_up || [];
    const laidRows = laid.map((s, i) => `<li><span><b>${esc(s.name)}</b><small>${esc((D.ships[s.type] || {}).name || s.type)} ·
        ${te("acct.fleet.saving", { amount: money((s.full_wage || 0) - (s.wage || 0)) })}</small></span>
        <span class="ldg-fig down">${money(s.wage)}</span>${home ? btn(te("acct.fleet.recall"), "recall", `data-i="${i}"`, "ldg-btn", locked) : ""}</li>`).join("");
    const repairAll = (m.ships || []).reduce((n, s) => n + (s.repair || 0), 0);
    const notes = [yard ? "" : te("acct.fleet.no_yard"), home ? "" : te("acct.fleet.home_only", { home: esc(portName(myHome())) })].filter(Boolean).join(" ");
    return `<div class="ldg-top"><h2>${te("acct.fleet.title")}</h2></div>
      <table class="ldg-table ldg-fleet"><thead><tr><th>${te("acct.fleet.ship")}</th><th class="n">${te("acct.fleet.value")}</th>
        <th class="n">${te("acct.fleet.wage")}</th><th class="n">${te("acct.fleet.repair")}</th></tr></thead><tbody>${rows}</tbody>
        <tfoot><tr class="ldg-total"><td>${te("acct.fleet.total")}</td><td></td><td class="n down">${fig(wage + laid.reduce((n, s) => n + (s.wage || 0), 0), "down")}</td>
        <td class="n">${repairAll ? btn(te("acct.fleet.repair_all", { cost: money(repairAll) }), "repair", 'data-i="all"', "ldg-btn primary", locked || repairAll > m.cash) : ""}</td></tr></tfoot></table>
      ${notes ? `<p class="ldg-fine">${notes}</p>` : ""}
      <div class="ldg-cols">
        ${laid.length ? `<section class="ldg-blk"><h3>${te("acct.fleet.laid", { home: esc(portName(myHome())) })}</h3><ul class="ldg-laid">${laidRows}</ul>
          <p class="ldg-fine">${te("acct.fleet.laid_note", { pct: layPct, home: esc(portName(myHome())) })}</p></section>` : ""}
        <section class="ldg-blk ${laid.length ? "" : "ldg-span"}"><h3>${te("acct.fleet.chart")}</h3>${wageBars()}</section>
      </div>
      ${protection()}`;
  }

  function wageBars() {
    const m = me(), list = (m.ships || []).map(s => [s.name, s.wage || 0, roleOf(s.type)])
      .concat((m.laid_up || []).map(s => [s.name, s.wage || 0, "laid"])).filter(r => r[1] > 0).sort((a, b) => b[1] - a[1]);
    if (!list.length) return "";
    const top = list[0][1] || 1;
    return `<ul class="ldg-bars">${list.slice(0, 12).map(([name, w, role], i) => `<li class="b-${role}" style="--w:${(100 * w / top).toFixed(1)}%;--d:${0.1 + i * 0.06}s">
      <span>${esc(name)}</span><i></i><b>${money(w)}</b></li>`).join("")}</ul>`;
  }

  function protection() {
    const m = me(), home = isHome();
    const left = m.protect > 0 ? te(m.protect === 1 && T["acct.prot.left_1"] != null ? "acct.prot.left_1" : "acct.prot.left", { n: m.protect }) : te("acct.prot.none");
    const pay = home && m.protect <= D.renew_at
      ? btn(te("acct.prot.pay", { cost: money(m.protect_cost) }), "protection", "", "ldg-btn primary", m.ready || m.protect_cost > m.cash) : "";
    return desk("agent", te("acct.prot.title"), `<p><b>${left}</b> ${home ? "" : `<small>${te("acct.prot.home", { home: esc(portName(myHome())) })}</small>`}</p>${pay}`,
      "ldg-prot " + (m.protect > D.renew_at ? "up" : "down"));
  }

  /* --------------------------------------------- spread 3: dues & duties -- */
  function duesLeft() {
    const m = me(), bk = m.books || {}, home = myHome();
    const stores = [];
    const homeGoods = m.port === home ? (m.wh || {}) : (m.wh_home || {});
    stores.push({ port: home, goods: homeGoods, cap: m.port === home ? m.wh_cap : null });
    if (m.wh_here === "open") stores.push({ port: m.port, goods: m.wh || {}, cap: m.wh_cap });
    Object.entries(m.wh_away || {}).forEach(([k, d]) => { if (k !== m.port && k !== home) stores.push({ port: k, goods: (d && d.goods) || {}, cap: d && d.cap }); });
    const cards = stores.filter(st => st.cap || Object.keys(st.goods).length).map(st => {
      const used = Object.values(st.goods).reduce((a, b) => a + b, 0);
      const goods = Object.entries(st.goods).filter(([, q]) => q > 0).map(([g, q]) =>
        `<span class="ldg-chip">${q.toLocaleString()} ${esc((D.goods[g] || {}).name || g)}</span>`).join("");
      const fill = st.cap ? Math.min(100, 100 * used / st.cap) : 0;
      const wr = m.wh_rent || {}, rent = (wr.by_port || {})[st.port], isHome = st.port === home;
      const rentNote = rent
        ? `<small class="ldg-rent">${te("acct.house.rent_now", { rent: money(rent.rent), note: rent.empty ? te("acct.house.rent_half") : "" })}</small>`
        : (isHome && wr.home_free > 0 ? `<small class="ldg-rent">${te("acct.house.rent_free", { months: wr.home_free, s: wr.home_free === 1 ? "" : "s" })}</small>` : "");
      return `<div class="ldg-store ldg-blk">
        <div class="ldg-storeimg">${Media.html("port", st.port, "banner", "", (D.graphics.ports || {})[st.port], Object.assign({ slot: "ldg-wh:" + st.port }, PIC))}
          <b class="ldg-sname">${te("acct.house.wh", { port: esc(portName(st.port)) })}</b></div>
        <div class="ldg-storebody">
        ${st.cap ? `<small>${te("acct.house.used", { used: used.toLocaleString(), cap: st.cap.toLocaleString() })}</small><div class="ldg-fill"><i style="--w:${fill.toFixed(1)}%"></i></div>` : ""}
        ${rentNote}
        <div class="ldg-chips">${goods || `<small>—</small>`}</div></div></div>`;
    }).join("") || `<p class="ldg-muted">${te("acct.house.none")}</p>`;
    const cost = range => {
      const l = (range === "year" ? bk.year : bk.game) || {};
      return [["wh_rent", "acct.house.rent"], ["depot", "acct.house.depot"], ["estate_upkeep", "acct.house.estate"]].filter(([k]) => Math.round(l[k] || 0))
        .map(([k, label]) => `<li><span><b>${te(label)}</b><small>${te("port.pl.range_" + range)}</small></span>${fig(l[k], "down")}</li>`).join("");
    };
    const costs = cost("year") + cost("game");
    const due = (m.wh_rent || {}).total > 0 ? `<p class="ldg-caption">${te("acct.house.rent_total", { total: money(m.wh_rent.total) })}</p>` : "";
    const estate = m.estate && m.estate.stage ? `<p class="ldg-caption">${te("acct.house.estate_now", { n: m.estate.stage })}</p>` : "";
    return `<div class="ldg-top"><h2>${te("acct.house.title")}</h2>${estate}${due}</div>
      <div class="ldg-cols">${cards}</div>
      ${costs ? `<ul class="ldg-sheet ldg-two">${costs}</ul>` : ""}
      <h3>${te("acct.bill.title", { port: esc(portName(m.port)) })}</h3>
      <div class="ldg-artbox">${boxArt("mayor", ":bill")}${bill()}</div>`;
  }

  function bill() {
    const m = me(), b = m.dues;
    if (!b || !b.lines || !b.lines.length || !b.total) return `<p class="ldg-muted">${te("acct.bill.none")}</p>`;
    const label = ln => ln.key === "standing" ? te(ln.amount < 0 ? "dues.standing_off" : "dues.standing_on") : te("dues." + ln.key);
    const rows = b.lines.map((ln, i) => `<li style="--d:${0.05 * i}s"><span><b>${label(ln)}</b></span><span class="ldg-fig ${ln.amount < 0 ? "up" : "down"}">${esc(signedMoney(-ln.amount))}</span></li>`).join("");
    return `<ul class="ldg-sheet ldg-bill">${rows}</ul>
      <ul class="ldg-sheet total"><li><span><b>${te("acct.bill.total")}</b></span>${fig(-b.total, "down")}</li>
        <li><span>${te("acct.bill.after")}</span>${fig(m.cash - b.total, toneOf(m.cash - b.total))}</li></ul>`;
  }

  const WHO_FACE = { mayor: "mayor", officer: "taxlady", lender: "lender", banker: "banker", shipwright: "shipwright",
                     agent: "agent", pirates: "pirate", thieves: "", warehouse: "comprador" };
  function duesRight() {
    const v = hist.data && hist.data.me;
    if (!v) return `<div class="ldg-top"><h2>${te("acct.takers.title")}</h2></div><p class="ldg-muted">${te(hist.failed ? "acct.takers.none" : "acct.chart.loading")}</p>`;
    const takers = (v.takers || []).filter(r => Math.abs(r.amount) >= 1);
    const top = Math.max(1, ...takers.map(r => Math.abs(r.amount)));
    const cards = takers.length ? takers.slice(0, 9).map((r, i) => {
      const pic = WHO_FACE[r.who] ? personaHtml(WHO_FACE[r.who], ":taker") : "";
      const ports = Object.entries(r.ports || {}).slice(0, 3).map(([p, n]) => `${esc(portName(p))} ${esc(moneyShort(Math.abs(n)))}`).join(" · ");
      const label = T["acct.who." + r.who] != null ? te("acct.who." + r.who) : esc(r.who);
      const sub = T["acct.who." + r.who + "_sub"] != null ? te("acct.who." + r.who + "_sub") : "";
      // Silver going out is a loss (oxblood); the bank's interest comes in (jade).
      const inward = r.who === "banker";
      return `<li class="ldg-taker${inward ? " in" : ""}" style="--w:${(100 * Math.abs(r.amount) / top).toFixed(1)}%;--d:${0.1 + i * 0.08}s">
        ${pic ? `<span class="ldg-face big">${pic}</span>` : `<span class="ldg-face big none" aria-hidden="true">✦</span>`}
        <div class="ldg-tk"><b>${label}</b><small>${sub}</small>
          <span class="ldg-fig ${inward ? "up" : "down"}">${money(Math.abs(r.amount))}</span>
          <div class="ldg-meter"><i></i></div><small class="ldg-ports">${ports}</small></div></li>`;
    }).join("") : "";
    const desk_ = v.desk || {}, dues = v.dues || {};
    const taxRows = (desk_.ports || []).filter(p => p.tax || p.fine).slice(0, 8).map(p => `<tr><td>${esc(portName(p.port))}</td><td class="n">${p.visits}</td>
        <td class="n down">${money(p.tax)}</td><td class="n ${p.fine ? "down" : ""}">${p.fine ? money(p.fine) : "—"}</td></tr>`).join("");
    const wages = ((me().books || {}).game || {}).upkeep;
    return `<div class="ldg-top"><h2>${te("acct.takers.title")}</h2></div>
      ${cards ? `<ul class="ldg-takers">${cards}</ul>` : `<p class="ldg-muted">${te("acct.takers.none")}</p>`}
      <h3>${te("acct.tax.title")}</h3>
      ${taxRows ? `<table class="ldg-table"><thead><tr><th>${te("acct.tax.port")}</th><th class="n">${te("acct.tax.visits")}</th><th class="n">${te("acct.tax.tax")}</th><th class="n">${te("acct.tax.fine")}</th></tr></thead><tbody>${taxRows}</tbody></table>`
        : `<p class="ldg-muted">${te("acct.tax.none")}</p>`}
      ${dues.count ? `<p class="ldg-caption">${te("acct.tax.dues", { paid: money(dues.paid || 0), count: dues.count })}${dues.slipped ? " · " + te("acct.tax.slipped", { n: dues.slipped, saved: money(dues.slip_saved || 0) }) : ""}</p>` : ""}
      ${wages ? `<p class="ldg-caption">${te("acct.wages", { amount: money(Math.abs(wages)) })}</p>` : ""}
      <p class="ldg-fine">${te("acct.game_only")}</p>`;
  }

  /* --------------------------------------------- after drawing: motion -- */
  function after(root) {
    const el = root && root.querySelector(".ldg");
    if (!el) return;
    // Figures count up once per page and month; a redraw after that shows them settled.
    if (el.classList.contains("ldg-anim") && counted !== animKey) { counted = animKey; countUp(el); }
  }
  function countUp(el) {
    const reduce = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
    el.querySelectorAll("[data-count]").forEach(n => {
      if (n.dataset.done) return;
      n.dataset.done = "1";
      const to = +n.dataset.count;
      if (reduce || !to) return;
      const t0 = performance.now(), dur = 900 + Math.min(700, Math.log10(Math.abs(to) + 1) * 90);
      const tick = now => {
        const k = Math.min(1, (now - t0) / dur), e = 1 - Math.pow(1 - k, 3);
        n.textContent = money(to * e);
        if (k < 1 && n.isConnected) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    });
  }

  // Chart read-outs: one listener for every Ledger chart (they are redrawn often).
  function readout(e) {
    const fig_ = e.target.closest && e.target.closest(".ldg-chart");
    if (!fig_) return;
    const c = charts[fig_.dataset.chart], svg = fig_.querySelector("svg"), tip = fig_.querySelector(".ldg-tip");
    if (!c || !svg || !tip) return;
    const box = svg.getBoundingClientRect();
    if (c.kind === "worth") {
      const vx = (e.clientX - box.left) / box.width * c.W;
      let i = 0;
      c.xs.forEach((x, n) => { if (Math.abs(x - vx) < Math.abs(c.xs[i] - vx)) i = n; });
      const r = c.rows[i], cur = svg.querySelector(".ldg-cursor");
      if (cur) { cur.setAttribute("x1", c.xs[i]); cur.setAttribute("x2", c.xs[i]); cur.classList.add("on"); }
      tip.innerHTML = `<b>${esc(r.date || "")}</b>` + ["cash", "bank", "cargo", "fleet"].map(k => `<span class="lg-${k}"><i></i>${te("acct.chart." + k)} <em>${money(r[k])}</em></span>`).join("") +
        (r.debt ? `<span class="lg-debt"><i></i>${te("acct.chart.debt")} <em>−${money(r.debt)}</em></span>` : "") +
        `<span class="lg-worth"><i></i>${te("acct.chart.worth")} <em>${money(r.worth)}</em></span>`;
      tip.hidden = false;
      tip.style.left = Math.min(box.width - tip.offsetWidth - 4, Math.max(4, c.xs[i] / c.W * box.width + 10)) + "px";
    } else if (c.kind === "flow") {
      const g = e.target.closest(".ldg-wf");
      if (!g) { tip.hidden = true; return; }
      const b = c.bars[+g.dataset.i];
      fig_.querySelectorAll(".ldg-wf.on").forEach(x => x.classList.remove("on"));
      g.classList.add("on");
      tip.innerHTML = `<b>${esc(b.name)} <em class="${toneOf(b.sub)}">${esc(signedMoney(b.sub))}</em></b>` +
        b.lines.map(([name, n]) => `<span>${esc(name)} <em class="${toneOf(n)}">${esc(signedMoney(n))}</em></span>`).join("");
      tip.hidden = false;
      const gb = g.getBoundingClientRect();
      tip.style.left = Math.min(box.width - tip.offsetWidth - 4, Math.max(4, gb.left - box.left + gb.width / 2 - tip.offsetWidth / 2)) + "px";
    }
  }
  function leave(e) {
    const fig_ = e.target.closest && e.target.closest(".ldg-chart");
    if (!fig_ || fig_.contains(e.relatedTarget)) return;
    const tip = fig_.querySelector(".ldg-tip"), cur = fig_.querySelector(".ldg-cursor");
    if (tip) tip.hidden = true;
    if (cur) cur.classList.remove("on");
    fig_.querySelectorAll(".ldg-wf.on").forEach(x => x.classList.remove("on"));
  }
  document.addEventListener("pointermove", readout);
  document.addEventListener("pointerdown", readout);
  document.addEventListener("pointerout", leave);
  document.addEventListener("keydown", e => {
    if (!ui || !ui.ledger) return;
    if (e.key === "Escape" && !ui.meOpen) { e.preventDefault(); close(); }
    if (e.target && /INPUT|TEXTAREA/.test(e.target.tagName)) return;
    if (e.key === "ArrowRight" || e.key === "PageDown") step(1);
    if (e.key === "ArrowLeft" || e.key === "PageUp") step(-1);
  });

  // The quill drawn on the rail button until her pictures are filed.
  const QUILL = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 3c-6 1-11 6-13 13l-2 5 2-1c1-3 3-5 5-6l3-1-2-1 3-2-1-1c3-1 5-3 5-6z" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M4 21h9" stroke="currentColor" stroke-width="1.6"/></svg>';

  return { html, open, close, turnTo, step, after, drag, load, hello, QUILL, SPREADS };
})();
