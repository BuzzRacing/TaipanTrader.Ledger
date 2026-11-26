/* SeaTrader: the Port Authority desk (engine.py, "port authority").

   On arrival in a port the house meets that port's tax officer before anything else. Four buttons
   decide the declaration for the whole hold (19 Nov 2026): Pay Nothing, Pay Less (a hidden share of
   each line's worth, drawn by the engine and shown only in her ruling), Pay Correct and Pay More (both
   fully safe). No odds are shown at any difficulty; her face and tell react to the button the captain
   hovers over (or has chosen): Pay Nothing sly, Pay Less sad/hungry, Pay Correct idle, Pay More happy.
   The ruling is revealed on her face (happy, or angry when caught) before the desk clears (22 Nov 2026).
   Any line can still be kept sealed in bond.

   Portraits belong to the active officer, including the Registrar at the house's home port.
   Persona media takes precedence over legacy port art. Legacy tax-lady art is only used for
   that port's configured officer when she has no persona media or profile portrait.
   Rulings use happy/angry portraits; declaration tells use bored/curious/hungry when available.
   The stage uses a second portrait of the same officer, or keeps the port when none is free.

   Needs from player.js: S, D, ui, act(), render(), portName(), pct(). */
"use strict";

/* A hot tip: a boom foretold by the Registrar at home or by a port's own officer elsewhere
   (engine _hot_tip; tp.by is "registrar" or "officer"). Shown at the desk when it is given (atDesk) and afterwards pinned at the top of the Port screen until the boom is over (the Price Book is gone). */
function hotWhen(n) { return n <= 1 ? t("l.when.next") : t("l.when.months", { n }); }
function hotTipHtml(tp, atDesk) {
  if (!tp || !D.goods[tp.good] || !D.ports[tp.port]) return "";
  const goods = D.goods[tp.good].name, where = portName(tp.port), home = portName(tp.home || S.me.home);
  /* At the desk her own words say it all, so no small-print recap under them. */
  let note = "";
  if (atDesk) { /* nothing */ }
  else if (S.turn < tp.lands) note = `<b>${te("hot.soon", { where, when: hotWhen(tp.lands - S.turn) })}</b> · ${te("hot.how_long")} · ${te("hot.from", { home })}`;
  else if (tp.over != null && S.turn >= tp.over) note = `<b>${te("hot.over", { where, goods })}</b>`;
  else note = `<b>${te("hot.on", { where })}</b> · ${te("hot.any_month")}`;
  const away = tp.by === "officer";
  const head = atDesk ? (away ? te("customs.hot_head_port", { who: tp.who || home }) : te("customs.hot_head"))
    : (away ? te("hot.head_port", { port: home }) : te("hot.head"));
  return `<aside class="cx-tip hot" aria-label="${head}">
      <span class="cx-tip-art" aria-hidden="true">${Media.html("cargo", tp.good, "icon", "cx-tip-img", (D.graphics.goods || {})[tp.good], { mode: "fixed" })}</span>
      <div><p class="eyebrow">${head}</p><p class="cx-tip-say">${esc(tp.text || "")}</p>
      ${note ? `<small>${note}</small>` : ""}</div></aside>`;
}

const Customs = (() => {
  const pick = {};          // role -> id of the picture last shown
  let shownState = null;    // the mood her tell and the desk's colours show now
  let shownMood = null;     // the expression her picture shows now
  const onScreen = { art: "", greet: "", stage: "" };   // picture URLs showing now, so none repeat
  const stagePick = {};     // visit key -> URL of her picture on the stage
  const srcOf = h => { const m = /src="([^"]+)"/.exec(h || ""); return m ? m[1].replace(/&amp;/g, "&") : ""; };

  const cu = () => (S && S.me && S.me.customs) || null;
  const key = c => c.port + ":" + S.turn + ":" + c.officer;
  /* The coin on her desk when tax is paid: once per visit, whether the ruling shows or the receipt flashes. */
  const coin = k => { if (typeof SeaAudio !== "undefined") SeaAudio.playOnce("cx:" + k + ":coin", "desk.coin"); };

  /* The four buttons and the face each one puts on her (no odds: the button chosen is the tell). */
  const PAYS = ["nothing", "less", "correct", "more"];
  const PAY_STATE = { nothing: "hungry", less: "curious", correct: "bored", more: "over" };
  const payOf = () => (PAYS.includes(ui.cxPay) ? ui.cxPay : null);
  /* The face follows the button under the captain's pointer (or the one chosen): sly for Pay Nothing, sad or
     hungry for Pay Less, idle for Pay Correct, happy for Pay More. */
  const FACE_MOOD = { nothing: "sly", less: "sad", correct: "idle", more: "happy" };
  const feel = () => (PAYS.includes(ui.cxHover) ? ui.cxHover : payOf());

  /* A cargo left sealed in bond: no tax and no risk on it, and none of it sold here this visit. */
  const sealedOn = (c, g) => !!c.bond && ui.vals["cxs_" + g] === "1";

  function numbers(c) {
    const more = (c.rules && c.rules.pay_more_share) || 1.1;
    const lines = c.lines.map(ln => ({ ln, sealed: sealedOn(c, ln.good) }));
    const open = lines.filter(l => !l.sealed);
    /* The desk never shows what the cargo is worth: only the tax on each button, worked out by the engine from
       the Authority's own (hidden) assessment (engine _hide_worth). */
    const taxOf = l => l.ln.tax;
    const taxMore = l => l.ln.tax_more;
    const tax = { nothing: 0, less: open.reduce((n, l) => n + taxOf(l), 0),
                  correct: open.reduce((n, l) => n + taxOf(l), 0), more: open.reduce((n, l) => n + taxMore(l), 0) };
    const pay = payOf();
    // The cargo she would like best (for "eyeing your {good}"): the dearest line not sealed.
    const hungry = open.slice().sort((a, b) => (b.ln.pull || 0) - (a.ln.pull || 0))[0] || null;
    const fe = feel();
    const state = fe ? PAY_STATE[fe] : "bored";
    const mood = fe ? FACE_MOOD[fe] : "idle";
    // "less" owes less than the correct tax, by a share the player does not see; "due" is what is sure.
    const due = pay === "less" ? null : pay ? tax[pay] : null;
    return { lines, open, tax, pay, due, state, mood, hungry, more,
             total: pay === "less" ? tax.correct : due || 0 };
  }

  /* ---------------------------------------------------------------- her face -- */
  const RULING = { tax: ["happy", "taxlady_tax"], buyout: ["happy", "taxlady_buyout"], caught: ["angry", "taxlady_caught"] };
  function inMood(i, mood) {
    return i.r.includes(mood) || (i.g || []).some(t => String(t).toLowerCase().split(/[^a-z]+/).includes(mood));
  }
  /* Which pictures say which mood. A mood is matched by a persona role or a tag word; a missing mood falls
     back (sly -> hungry, a wolfish smile) and then to any picture of her. */
  const MOOD_SETS = { sly: ["sly"], sad: ["sad", "hungry"], idle: ["idle", "bored"], happy: ["happy"], over: ["bored"] };
  const MOOD_FALLBACK = { sly: ["hungry"] };
  function moodPictures(c, state) {
    const list = herPictures(c);
    if (state === "welcome") return list;
    const pool = (words, roles) => list.filter(i => words.some(w => inMood(i, w)) || roles.some(r => i.r.includes(r)));
    let m;
    if (RULING[state]) m = pool([RULING[state][0]], [RULING[state][1]]);
    else {
      const words = MOOD_SETS[state] || [state];
      m = pool(words, words.map(w => "taxlady_" + w));
      if (!m.length && MOOD_FALLBACK[state]) m = pool(MOOD_FALLBACK[state], MOOD_FALLBACK[state].map(w => "taxlady_" + w));
    }
    return m.length ? m : list;
  }
  const loaded = new Set();
  /* Fetch her expression pictures when the desk opens, so a hover swaps at once. */
  function preload(c) {
    ["sly", "sad", "idle", "happy"].forEach(st => moodPictures(c, st).forEach(i => {
      if (i.t !== "video" && !loaded.has(i.u)) { loaded.add(i.u); new Image().src = i.u; }
    }));
  }
  /* Take turns through a pool: every picture is shown once before any repeats, never the one she wore
     last, never the one the stage is showing. */
  const bags = {};
  function nextInTurn(bagKey, list) {
    const shown = bags[bagKey] || (bags[bagKey] = new Set());
    let fresh = list.filter(i => !shown.has(i.u));
    if (!fresh.length) { shown.clear(); fresh = list; }
    const tries = [fresh.filter(i => i.id !== pick.last && i.u !== onScreen.stage),
                   fresh.filter(i => i.u !== onScreen.stage),
                   list.filter(i => i.id !== pick.last && i.u !== onScreen.stage),
                   list.filter(i => i.u !== onScreen.stage), list];
    const choices = tries.find(t => t.length);
    const it = choices[Math.floor(Math.random() * choices.length)];
    shown.add(it.u);
    return it;
  }
  function face(c, state, cls) {
    cls = cls || "stg-img stg-keeper stg-taxlady cx-img";
    const list = moodPictures(c, state);
    if (!list.length) {
      onScreen.art = "";
      return `<i class="stg-mono">${esc((c.name || "?").split(/\s+/).map(w => w[0]).slice(0, 2).join(""))}</i>`;
    }
    const memo = state + ":" + key(c);
    let it = list.find(i => i.id === pick[memo]);
    if (!it) {
      // A new mood (or a new visit) shows the next picture in turn for that mood at this port.
      const group = RULING[state] ? RULING[state][0] : state;
      it = nextInTurn(group + ":" + c.port + ":" + (c.officer || ""), list);
      pick[memo] = it.id;
    }
    pick.last = it.id;
    onScreen.art = it.u;
    const u = esc(it.u);
    return it.t === "video"
      ? `<video class="${cls}" src="${u}" muted autoplay loop playsinline preload="auto" disablepictureinpicture></video>`
      : `<img class="${cls}" src="${u}" alt="">`;
  }

  /* Her own wide 16:9 result picture (Media Library > Personas > her name, role "Tax result, good" or
     "Tax result, bad"; tax_results.py). media.js keeps these off every other screen. One pick per visit,
     taking turns; "" when she has none yet, and the reveal then crops one of her mood pictures. */
  const RESULT_ROLE = { tax: "tax_good", buyout: "tax_good", caught: "tax_bad" };
  function resultArt(c, state) {
    const role = RESULT_ROLE[state];
    if (!role || !c.officer) return "";
    const list = Media.items("persona", [c.officer], role, false, "ruling").filter(i => i.r.includes(role));
    if (!list.length) return "";
    const memo = "result:" + state + ":" + key(c);
    let it = list.find(i => i.id === pick[memo]);
    if (!it) { it = nextInTurn("result:" + role + ":" + c.officer, list); pick[memo] = it.id; }
    onScreen.art = it.u;
    return `<img class="cl-art-media" src="${esc(it.u)}" alt="">`;
  }

  /* Her manner, in words. A new line each time her mood changes. */
  function tell(c, n) {
    const k = "customs.tell_" + n.state;
    if (ui.cxTell == null || ui.cxTellState !== n.state) {
      ui.cxTellState = n.state;
      ui.cxTell = Math.floor(Math.random() * 3);
    }
    const good = n.hungry ? D.goods[n.hungry.ln.good].name.toLowerCase() : "";
    const line = t(k + "." + ui.cxTell, { good });
    return line === k + "." + ui.cxTell ? t(k + ".0", { good }) : line;
  }

  /* ------------------------------------------------------------------- html -- */
  /* The tax badge's heat: 0% is cool jade, about 3% brass, RATE_HOT (6%) and above red. Base rates run
     1% to 4.5% and drift up to 1.25 points either side, so the whole scale is in use. */
  const RATE_HOT = 0.06;
  function heatColor(h) {
    const stops = [[0, [127, 211, 168]], [0.5, [226, 186, 96]], [1, [230, 92, 80]]];
    const i = h <= 0.5 ? 0 : 1, a = stops[i], b = stops[i + 1], f = (h - a[0]) / (b[0] - a[0]);
    return "rgb(" + a[1].map((v, k) => Math.round(v + (b[1][k] - v) * f)).join(",") + ")";
  }

  function head(c) {
    const port = esc(portName(c.port));
    let rate = "";
    if (!c.free) {
      const diff = Math.round((c.rate - c.base) * 1000) / 10;
      const move = Math.abs(diff) < 0.05 ? te("customs.rate_base") : te(diff > 0 ? "customs.rate_up" : "customs.rate_down", { base: pct(c.base) + "%" });
      // D4 (owner's decision, 20 Nov 2026): a small badge pinned top right, heat-mapped from a low rate (jade)
      // through brass to a high one (red), with the number and a marker on the low-to-high scale.
      const heat = Math.max(0, Math.min(1, (Number(c.rate) || 0) / RATE_HOT));
      const arrow = diff > 0.05 ? "&#9650;" : diff < -0.05 ? "&#9660;" : "";
      rate = `<div class="cx-rate heat${diff > 0.05 ? " up" : diff < -0.05 ? " dn" : ""}" style="--heat:${heatColor(heat)};--at:${Math.round(heat * 100)}%" title="${move}">` +
        `<small>${te("customs.rate")}</small><b>${pct(c.rate)}%${arrow ? `<i aria-hidden="true">${arrow}</i>` : ""}</b>` +
        `<span class="cx-heat" aria-hidden="true"><i></i></span></div>`;
    } else {
      rate = `<div class="cx-rate free"><b>${te(c.home_free ? "port.glance.home_free" : "customs.free")}</b></div>`;
    }
    return `<header class="cx-head"><div><p class="eyebrow">${te("customs.authority", { port })}</p>
      <p class="cx-title" id="cx-title">${esc(c.title)}</p></div>${rate}</header>`;
  }

  function greeting(c) {
    const portrait = Media.html("persona", c.officer, "portrait", "cl-face", ((VS.cast || {})[c.officer] || {}).portrait, { strict: true });
    onScreen.greet = srcOf(portrait);
    return `<blockquote class="cx-say${portrait ? " has-face" : ""}">
      ${portrait ? `<span class="cl-portrait">${portrait}</span>` : ""}
      <div><div class="cl-reader"><span><i aria-hidden="true">${DECK_ICONS.speech_on}</i>${te("log.reading")}</span><b>${esc(c.name)}</b></div>${esc(c.welcome)}</div>
    </blockquote>`;
  }

  /* The Registrar's price tip (Hong Kong): one fresh price from her register, under her greeting.
     Text only; the price is already noted for Best known (Market) and Best (Set sail). */
  function tipHtml(c) {
    const tp = c.tip;
    if (!tp || !D.goods[tp.good] || !D.ports[tp.port]) return "";
    if (tp.hot) return hotTipHtml(tp, true);
    return `<aside class="cx-tip" aria-label="${te("customs.tip_head")}">
      <span class="cx-tip-art" aria-hidden="true">${Media.html("cargo", tp.good, "icon", "cx-tip-img", (D.graphics.goods || {})[tp.good], { mode: "fixed" })}</span>
      <div><p class="eyebrow">${te("customs.tip_head")}</p><p class="cx-tip-say">${esc(tp.text || "")}</p></div></aside>`;
  }

  /* Pay Nothing or Pay Less: say plainly, in silver, what she may do with the cargo (no odds). */
  function payWarn(c, n) {
    if (!n.pay || n.pay === "correct" || n.pay === "more" || !n.open.length) return "";
    return te("customs.pay_warn." + n.pay);
  }

  function paySub(n, k) {
    return te("customs.pay_sub." + k, { tax: money(n.tax[k]), over: Math.round((n.more - 1) * 100) });
  }

  function payButtons(c, n) {
    return `<div class="cx-pay" role="radiogroup" aria-label="${te("customs.pay_head")}">
      ${PAYS.map(k => `<button type="button" class="cx-pay-btn ${k}${n.pay === k ? " on" : ""}" data-act="cx_pay" data-pay="${k}"
          role="radio" aria-checked="${n.pay === k}"${n.open.length ? "" : " disabled"}><b>${te("customs.pay." + k)}</b><small data-cx="ps_${k}">${paySub(n, k)}</small></button>`).join("")}
    </div>`;
  }

  function lineRow(c, l) {
    const g = l.ln.good, gi = (D.graphics.goods || {})[g];
    const seal = c.bond ? `<label class="cx-seal" title="${te("customs.seal_tip")}"><input type="checkbox" data-act="cx_seal" data-good="${g}" ${l.sealed ? "checked" : ""}>
        <span>${te("customs.seal")}</span></label>` : "";
    return `<div class="cx-line cx-line-pay${l.sealed ? " sealed" : ""}" data-good="${g}">
      <span class="cx-good">${gi ? `<img src="${esc(gi)}" alt="">` : ""}<b>${esc(D.goods[g].name)}</b>
        <small>${l.ln.qty.toLocaleString()} ${te("customs.qty").toLowerCase()}</small></span>
      <span class="cx-line-foot">${l.sealed ? `<em class="cx-chip sealed">${te("customs.sealed")}</em>` : ""}${seal}</span></div>`;
  }

  function dueText(n) {
    if (!n.pay) return "—";
    return n.pay === "less" ? "< " + money(n.tax.correct) : money(n.due);
  }

  /* What his standing and shares are worth against her padding (engine padding_odds): whole percents, never an amount. */
  function padLine(c) {
    const p = c.pad;
    if (!p || (!p.standing && !p.shares)) return "";
    const sgn = v => (v > 0 ? "−" : "+") + Math.abs(v) + "%";
    const bits = [];
    if (p.standing) bits.push(`<span class="${p.standing > 0 ? "up" : "dn"}">${te("customs.pad_standing", { pct: sgn(p.standing) })}</span>`);
    if (p.shares) bits.push(`<span class="up">${te("customs.pad_shares", { n: p.held, pct: sgn(p.shares) })}</span>`);
    return `<p class="cx-pad" title="${te("customs.pad_tip")}"><small>${te("customs.pad_head")}</small> ${bits.join(" · ")}</p>`;
  }

  function declareHtml(c) {
    const n = numbers(c);
    shownState = n.state; shownMood = n.mood;
    const short = Math.max(0, n.total - S.me.cash);
    return `<div class="cx-body">
      ${head(c)}
      ${greeting(c)}
      ${tipHtml(c)}
      <p class="cx-tell" data-cx="tell">${esc(tell(c, n))}</p>
      ${padLine(c)}
      <div class="cx-lines">${n.lines.map(l => lineRow(c, l)).join("")}</div>
      <p class="eyebrow cx-pay-head">${te(n.pay ? "customs.pay_head" : "customs.pay_pick")}</p>
      ${payButtons(c, n)}
      <p class="cx-warn" data-cx="warn">${payWarn(c, n)}</p>
      <div class="cx-sums">
        <span class="due"><small>${te("customs.total_tax")}</small><b data-cx="tax">${dueText(n)}</b></span>
      </div>
      <p class="cx-short" data-cx="short">${short ? te("customs.debt", { amount: money(short) }) : ""}</p>
    </div>`;
  }

  function verdictHtml(c) {
    const res = c.result;
    const state = verdictState(c);
    shownState = state;
    const rows = res.lines.map(r => {
      const g = r.good, name = esc(D.goods[g].name);
      const out = r.empty ? "empty" : r.outcome;
      let amount = "";
      if (r.outcome === "sealed") amount = "—";
      else if (r.outcome === "caught") amount = money(r.tax + r.fine);
      else if (r.units) amount = (r.back ? te("customs.bought_back") : "+" + money(r.paid)) + (r.tax ? " · " + money(r.tax) : "");
      else amount = money(r.tax);
      const back = r.units && !r.back
        ? btn(te("customs.buyback", { cost: money(r.back_price) }), "cx_back", `data-good="${g}"`, "ghost", r.back_price > S.me.cash) : "";
      return `<div class="cx-vline ${r.outcome}${r.back ? " back" : ""}"><span class="cx-good"><b>${name}</b><small>${res.choice === "less" && r.share != null && r.outcome !== "sealed" ? te("customs.share", { pct: Math.round(r.share * 100) }) : ""}</small></span>
        <em class="cx-out ${r.outcome}">${te("customs.out." + out)}${r.outcome === "partial" ? ` (${r.units}/${r.qty})` : ""}${r.hid ? ` · <span class="cx-hid" title="${te("customs.hid_tip")}">${te("customs.hid", { qty: r.hid })}</span>` : ""}</em>
        <b class="cx-amt">${amount}</b>${back}</div>`;
    }).join("");
    const bribe = res.bribe ? `<p class="cx-note ${res.bribe.taken ? "" : "bad"}">${te(res.bribe.taken ? "customs.bribe_taken" : "customs.bribe_refused", { cost: money(res.bribe.cost) })}</p>` : "";
    const rep = res.rep ? `<span class="${res.rep > 0 ? "up" : "dn"}"><small>${te("customs.standing", { port: esc(portName(c.port)) })}</small><b>${res.rep > 0 ? "+" : ""}${Math.round(res.rep * 10) / 10}</b></span>` : "";
    return `<div class="cx-body">
      ${head(c)}
      <h3 class="cx-verdict ${state}">${rulingLine(c, state)}</h3>
      <div class="cx-vlines">${rows}</div>${bribe}
      <div class="cx-sums">
        <span class="due"><small>${te("customs.paid_her")}</small><b>${money(res.tax + res.fine)}</b></span>
        ${res.paid ? `<span class="b"><small>${te("customs.she_paid")}</small><b>${money(res.paid)}</b></span>` : ""}${rep}
      </div>
      ${res.owed ? `<p class="cx-short">${te("customs.debt", { amount: money(res.owed) })}</p>` : ""}
    </div>`;
  }

  const verdictState = c => (c.result.caught ? "caught" : c.result.lines.some(r => r.units && !r.back) ? "buyout" : "tax");
  const tl = (k, fb, v) => (T[k] != null ? te(k, v)
    : esc(String(fb).replace(/\{(\w+)\}/g, (m, x) => (v && v[x] != null ? v[x] : m))));

  /* The ruling, in one line: the headline of the verdict card. */
  function rulingLine(c, state) {
    const total = Math.round(c.result.tax + c.result.fine);
    return state === "caught" ? tl("customs.reveal.caught", "Caught! {amount}", { amount: money(total) })
      : state === "buyout" ? tl("customs.reveal.buyout", "She buys your cargo")
      : total ? tl("customs.reveal.tax", "Tax paid: {amount}", { amount: money(total) }) : tl("customs.reveal.none", "Nothing to pay");
  }

  function welcomeHtml(c) {
    shownState = "welcome";
    return `<div class="cx-body">${head(c)}${greeting(c)}${tipHtml(c)}</div>`;
  }

  /* One card for the whole visit (24 Nov 2026): the same desk stays on screen from her greeting to her ruling.
     When she rules, keep() changes it in place (her picture cross-fades, the panel text swaps), so nothing is
     rebuilt, reloaded or faded out and back in. */
  function html() {
    const c = cu();
    if (!c || S.me.ready) return "";
    if (c.status === "welcome") return "";      // no stop: her greeting is read over the Port screen (auto)
    if (ui.cxKey !== key(c)) {            // a new visit: start honest, no sweetener
      ui.cxKey = key(c);
      Object.keys(ui.vals).filter(k => k.startsWith("cx_") || k.startsWith("cxs_")).forEach(k => delete ui.vals[k]);
      ui.cxBribe = false; ui.cxPay = null; ui.cxHover = null; ui.cxTell = null; ui.cxSpoken = null;
    }
    const declare = c.status === "declare";
    if (declare) preload(c);
    const body = declare ? declareHtml(c) : verdictHtml(c);
    const art = declare ? face(c, shownMood, "cl-art-media") : (resultArt(c, shownState) || face(c, shownState, "cl-art-media"));
    const label = declare ? "customs.declare_btn" : "customs.continue";
    return `<div class="veil cx-veil"><section class="modal cx-desk ${declare ? "declare" : "verdict " + shownState}" role="dialog" aria-labelledby="cx-title" data-state="${shownState}" data-key="${esc(key(c))}">
      <div class="cx-art" aria-hidden="true">${art}</div>
      <div class="cx-panel">${body}<footer>${btn(te(label), declare ? "cx_declare" : "cx_done", "", "primary", declare && !payOf() && c.lines.some(ln => !sealedOn(c, ln.good)))}</footer></div>
    </section></div>`;
  }

  /* Put a new picture of her on the card without a blink: the new one loads, fades in over the old one, and
     only then is the old one removed. The same picture is left alone. */
  function swapArt(art, htmlText) {
    const tmp = document.createElement("div");
    tmp.innerHTML = htmlText;
    const next = tmp.firstElementChild, cur = art.lastElementChild;
    if (!next) return;
    if (cur && cur.tagName === next.tagName && (cur.getAttribute("src") || "") === (next.getAttribute("src") || "")) return;
    const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!cur || still) { art.innerHTML = htmlText; return; }
    next.classList.add("cx-art-in");
    art.appendChild(next);
    const show = () => requestAnimationFrame(() => {
      next.classList.add("on");
      setTimeout(() => { while (next.previousElementSibling) next.previousElementSibling.remove(); next.classList.remove("cx-art-in", "on"); }, 420);
    });
    if (next.tagName === "IMG" && !next.complete) { next.addEventListener("load", show, { once: true }); next.addEventListener("error", show, { once: true }); }
    else show();
  }

  /* Declare -> ruling (and any later change to the ruling, such as Buy back) on the desk already on screen. */
  function keepVerdict(box, htmlText) {
    const tpl = document.createElement("template");
    tpl.innerHTML = htmlText.trim();
    const nb = tpl.content.querySelector(".cx-desk");
    if (!nb) return false;
    const first = box.className !== nb.className;
    if (first) box.className = nb.className;
    box.dataset.state = nb.dataset.state;
    swapArt(box.querySelector(".cx-art"), nb.querySelector(".cx-art").innerHTML);
    const body = box.querySelector(".cx-body"), nbody = nb.querySelector(".cx-body");
    if (body && nbody && body.innerHTML !== nbody.innerHTML) {
      body.innerHTML = nbody.innerHTML;
      if (first && body.animate && !matchMedia("(prefers-reduced-motion: reduce)").matches) body.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 260, easing: "ease-out" });
    }
    const foot = box.querySelector("footer"), nfoot = nb.querySelector("footer");
    if (foot && nfoot && foot.innerHTML !== nfoot.innerHTML) foot.innerHTML = nfoot.innerHTML;
    return true;
  }

  /* After a button or a seal changes: rewrite the numbers, the warning, her tell and (if her mood
     changed) her face, in place. */
  function live() {
    const c = cu();
    if (!c || c.status !== "declare") return;
    const n = numbers(c), box = app.querySelector(".cx-desk");
    if (!box) return;
    const set = (k, h) => { const o = box.querySelector(`[data-cx="${k}"]`); if (o) o.innerHTML = h; };
    PAYS.forEach(k => set("ps_" + k, paySub(n, k)));
    set("tax", dueText(n)); set("warn", payWarn(c, n));
    const short = Math.max(0, n.total - S.me.cash);
    set("short", short ? te("customs.debt", { amount: money(short) }) : "");
    const was = shownState;
    set("tell", esc(tell(c, n)));
    if (n.state !== was) { shownState = n.state; box.dataset.state = n.state; }
    if (n.mood !== shownMood) {
      shownMood = n.mood;
      box.querySelector(".cx-art").innerHTML = face(c, n.mood, "cl-art-media");
      showOnStage();
    }
  }

  /* The declaration desk already on screen is kept and brought up to date in place (buttons, seals,
     every number), never rebuilt: rebuilding it restarts the veil's fade and reloads her picture,
     which reads as the whole screen blinking. True when the desk was kept. */
  function keep(htmlText) {
    const c = cu(), box = app.querySelector(".cx-desk");
    if (!c || S.me.ready || !box || (c.status !== "declare" && c.status !== "verdict")) return false;
    if (ui.cxKey !== key(c) || box.dataset.key !== key(c)) return false;
    if (c.status === "verdict") return keepVerdict(box, htmlText || "");
    if (!box.classList.contains("declare")) return false;
    if (box.querySelectorAll(".cx-line").length !== c.lines.length) return false;
    const pay = payOf();
    box.querySelectorAll(".cx-line").forEach(row => {
      const g = row.dataset.good, sealed = sealedOn(c, g), seal = row.querySelector('[data-act="cx_seal"]');
      row.classList.toggle("sealed", sealed);
      if (seal) seal.checked = sealed;
      const foot = row.querySelector(".cx-line-foot"), chip = foot && foot.querySelector(".cx-chip");
      if (sealed && foot && !chip) foot.insertAdjacentHTML("afterbegin", `<em class="cx-chip sealed">${te("customs.sealed")}</em>`);
      if (!sealed && chip) chip.remove();
    });
    const anyOpen = c.lines.some(ln => !sealedOn(c, ln.good));
    box.querySelectorAll(".cx-pay-btn").forEach(b => {
      const on = b.dataset.pay === pay;
      b.classList.toggle("on", on); b.setAttribute("aria-checked", String(on)); b.disabled = !anyOpen;
    });
    const headLine = box.querySelector(".cx-pay-head");
    if (headLine) headLine.innerHTML = te(pay ? "customs.pay_head" : "customs.pay_pick");
    const go = box.querySelector('footer [data-act="cx_declare"]');
    if (go) go.disabled = !pay && anyOpen;
    live();
    return true;
  }

  let hoverTimer = null;
  /* Hover (or keyboard focus) on a pay button changes her face; leaving puts it back to the chosen one. */
  function hover(e, on) {
    const b = e.target && e.target.closest && e.target.closest(".cx-pay-btn");
    if (!b || b.disabled) return;
    if (!on && e.relatedTarget && b.contains(e.relatedTarget)) return;
    const next = on ? b.dataset.pay : null;
    if ((ui.cxHover || null) === next) return;
    ui.cxHover = next;
    // Moving from one button to the next fires leave then enter: wait a beat so her face changes once, not twice.
    clearTimeout(hoverTimer); hoverTimer = setTimeout(live, 70);
  }
  document.addEventListener("mouseover", e => hover(e, true));
  document.addEventListener("mouseout", e => hover(e, false));
  document.addEventListener("focusin", e => hover(e, true));
  document.addEventListener("focusout", e => hover(e, false));

  async function click(d) {
    const c = cu();
    if (!c) return false;
    switch (d.act) {
      case "cx_pay":
        if (PAYS.includes(d.pay)) { ui.cxPay = d.pay; ui.cxHover = d.pay; }
        render();
        return true;
      case "cx_seal":
        if (sealedOn(c, d.good)) delete ui.vals["cxs_" + d.good]; else ui.vals["cxs_" + d.good] = "1";
        render();
        return true;
      case "cx_declare": {
        const sealed = c.lines.filter(ln => sealedOn(c, ln.good)).map(ln => ln.good);
        const choice = payOf();
        if (!choice && sealed.length < c.lines.length) return true;          // pick a button first
        await act("customs_declare", { choice: choice || "correct", sealed });
        const after = cu();
        if (after && after.result && Math.round((after.result.tax || 0) + (after.result.fine || 0)) > 0) coin(key(after));
        return true;
      }
      case "cx_back": await act("customs_buyback", { good: d.good }); return true;
      case "cx_done": release(c); return true;
    }
    return false;
  }

  function herPictures(c) {
    const seen = new Set(), own = [];
    const add = i => { if (i && i.u && !seen.has(i.u)) { seen.add(i.u); own.push(i); } };
    if (c.officer) Media.items("persona", [c.officer], "", true).forEach(add);
    const prof = ((VS.cast || {})[c.officer] || {}).portrait;
    if (prof) add({ id: prof, u: prof, t: "image", r: [] });
    // A homecoming Registrar is not the local port officer, even when they share a desk.
    if (!own.length && c.officer && (D.ports[c.port] || {}).officer === c.officer) {
      Media.items("port", [c.port], "", true)
        .filter(i => i.r.some(r => r === "taxlady" || r.startsWith("taxlady_"))).forEach(add);
    }
    return own;
  }

  /* Her picture on the right-hand stage while the desk is open: one pick per visit, never the picture
     in the popup or beside her greeting. Null when no other picture of her is free (the stage then
     keeps the port). */
  function stage() {
    const c = cu();
    if (!c || S.me.ready) { onScreen.stage = ""; return null; }
    const own = herPictures(c);
    const busy = u => u === onScreen.art || u === onScreen.greet;
    const k = key(c);
    let it = own.find(i => i.u === stagePick[k] && !busy(i.u));
    if (!it) {
      let free = own.filter(i => !busy(i.u));
      if (!free.length) { onScreen.stage = ""; delete stagePick[k]; return null; }
      it = free[Math.floor(Math.random() * free.length)];
      stagePick[k] = it.u;
    }
    onScreen.stage = it.u;
    const u = esc(it.u), cls = "stg-img stg-keeper stg-taxlady";
    const html = it.t === "video"
      ? `<video class="${cls}" src="${u}" muted autoplay loop playsinline preload="auto" disablepictureinpicture></video>`
      : `<img class="${cls}" src="${u}" alt="">`;
    return { key: "cx:" + k + ":" + it.u, html, name: c.name, note: c.title };
  }
  /* Her mood changed the popup's picture: if it now matches the stage's, the stage picks another. */
  function showOnStage() {
    if (typeof deckArt === "function") deckArt(true);
  }

  /* Her greeting is read aloud once per visit, by the officer of that port, the moment her desk opens:
     ahead of any news still waiting. While the Captain's Log is still up, the clip is fetched early so
     Inworld has already recorded it by the time the desk appears. */
  let warmed = "";
  function speak() {
    const c = cu();
    if (!c || !S.voice || !S.voice.customs) return;
    // The house's own home port: the port's officer only waves you in, so nothing is read aloud;
    // but where the Registrar meets the house (officer "taxlady") she reads her welcome and her tip.
    if (c.home_free && c.officer !== "taxlady") return;
    const plans = S.voice.customs, plan = plans[0];
    plans.forEach(pl => { if (pl && pl.u && !warmed.includes(pl.u)) { warmed += " " + pl.u; fetch(pl.u).catch(() => {}); } });
    // A welcome has no desk on screen: she speaks over the Port screen once the log is closed and no
    // fight, storm or jail card is up (the stage shows her and her words while she does).
    if (c.status === "welcome" ? (document.querySelector(".captains-log") || otherScreenUp()) : !document.querySelector(".cx-desk")) return;
    if (ui.cxSpoken === key(c)) return;
    ui.cxSpoken = key(c);
    const texts = [c.welcome, c.tip && c.tip.text];
    const items = plans.map((pl, i) => pl && texts[i] ? Object.assign({ text: texts[i], tag: "customs:" + key(c) + (i ? ":tip" : "") }, pl) : null)
      .filter(Boolean);
    if (items.length) Voice.say(items, { group: "msg", replace: "msg", front: true });
  }

  function markSpeaking(item) {
    const greeting = document.querySelector(".cx-desk .cx-say");
    if (!greeting) return;
    if (item && item.tag === "customs:" + key(cu())) greeting.setAttribute("aria-current", "true");
    else greeting.removeAttribute("aria-current");
    const tip = document.querySelector(".cx-desk .cx-tip");
    if (tip) {
      if (item && item.tag === "customs:" + key(cu()) + ":tip") tip.setAttribute("aria-current", "true");
      else tip.removeAttribute("aria-current");
    }
  }

  /* ------------------------------------------------- stops that were only a click (20 Nov 2026) --
     Two stages of the desk had nothing to decide, so they no longer stop the game:
       - the WELCOME (home port, a free port, an empty hold): no popup. Her greeting (and her tip) is still
         read aloud, with her face and words on the stage, and the desk is cleared at once. The tip is in
         the month's log and the Price Book already; a hot tip is pinned on the Port screen.
       - a plain VERDICT (tax paid, nothing bought, nobody caught): no popup. The Port screen opens and a
         small receipt flashes with her happy picture. A ruling with a choice or a story keeps its screen:
         she bought cargo (Buy back is on it) or the house was caught (fine, jail plea).
     The server still gets customs_done, so the cargo she bought is sold on and the books settle as before. */
  const otherScreenUp = () => (typeof Battle !== "undefined" && Battle.busy())
    || (typeof Jail !== "undefined" && Jail.busy()) || (typeof Storm !== "undefined" && Storm.busy());
  /* A ruling with nothing left to decide (no cargo bought) stays on the card long enough to read, then the
     card fades away to the Port screen; Continue closes it at once. Caught holds a little longer (the fine).
     The jail's plea, if any, is its own card. */
  const autoVerdict = c => !!(c && c.status === "verdict" && c.result && !c.result.lines.some(r => r.units));
  const HOLD_MS = 3200, HOLD_CAUGHT_MS = 5200, FADE_MS = 350;
  let closing = "";              // the visit being cleared now, so a redraw never sends it twice
  let holdTimer = null, holdKey = "";

  /* Called from every redraw. */
  function auto() {
    const c = cu();
    if (!c || S.me.ready || closing === key(c)) return;
    if (document.querySelector(".captains-log") || otherScreenUp()) return;   // wait for the log, a fight, a storm
    if (c.status === "welcome") { speak(); release(c); }
    else if (autoVerdict(c) && holdKey !== key(c)) {
      holdKey = key(c);
      clearTimeout(holdTimer);
      holdTimer = setTimeout(() => { const x = cu(); if (x && key(x) === holdKey && autoVerdict(x)) release(x); }, verdictState(c) === "caught" ? HOLD_CAUGHT_MS : HOLD_MS);
    }
  }

  async function release(c) {
    const k = closing = key(c);
    clearTimeout(holdTimer);
    const veil = document.querySelector(".cx-veil");
    if (veil && !matchMedia("(prefers-reduced-motion: reduce)").matches) {
      veil.classList.add("cx-out");          // customs.css cxOut: a plain fade to the Port screen
      await new Promise(r => setTimeout(r, FADE_MS));
    }
    const res = await post("/api/act", { token, type: "customs_done" });   // silent: no toast, no cue
    if (res && res.ok) {
      ui.tab = "port"; ui.tally = false; ui.ledger = false;
      render();
    } else {
      if (veil) veil.classList.remove("cx-out");
      setTimeout(() => { if (closing === k) closing = ""; }, 2500);     // try again on a later redraw
    }
  }

  return { html, live, keep, click, speak, stage, markSpeaking, auto, hideReceipt: () => {},
           isOpen: () => !!(cu() && cu().status !== "welcome" && !S.me.ready) };
})();
