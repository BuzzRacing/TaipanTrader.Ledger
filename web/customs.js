/* SeaTrader: the Port Authority desk (engine.py, "port authority").

   On arrival in a port the house meets that port's tax officer before anything else. Four buttons
   decide the declaration for the whole hold (19 Nov 2026): Pay Nothing, Pay Less (a hidden share of
   each line's worth, drawn by the engine and shown only in her ruling), Pay Correct and Pay More (both
   fully safe). No odds are shown at any difficulty; her face and tell react to the button chosen.
   Any line can still be kept sealed in bond.

   Portraits belong to the active officer, including the Registrar at the house's home port.
   Persona media takes precedence over legacy port art. Legacy tax-lady art is only used for
   that port's configured officer when she has no persona media or profile portrait.
   Rulings use happy/angry portraits; declaration tells use bored/curious/hungry when available.
   The stage uses a second portrait of the same officer, or keeps the port when none is free.

   Needs from player.js: S, D, ui, act(), render(), portName(), pct(). */
"use strict";

/* A hot tip: a boom foretold by the Registrar at home or by a port's own officer elsewhere
   (engine _hot_tip; tp.by is "registrar" or "officer"). Shown at the desk when it is given (atDesk) and afterwards under Port > Arrival and in the Price Book until the boom is over. */
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
  let shownState = null;    // the mood her picture is showing now
  const onScreen = { art: "", greet: "", stage: "" };   // picture URLs showing now, so none repeat
  const stagePick = {};     // visit key -> URL of her picture on the stage
  const srcOf = h => { const m = /src="([^"]+)"/.exec(h || ""); return m ? m[1].replace(/&amp;/g, "&") : ""; };

  const cu = () => (S && S.me && S.me.customs) || null;
  const key = c => c.port + ":" + S.turn + ":" + c.officer;

  /* The four buttons and the face each one puts on her (no odds: the button chosen is the tell). */
  const PAYS = ["nothing", "less", "correct", "more"];
  const PAY_STATE = { nothing: "hungry", less: "curious", correct: "bored", more: "over" };
  const payOf = () => (PAYS.includes(ui.cxPay) ? ui.cxPay : null);

  /* A cargo left sealed in bond: no tax and no risk on it, and none of it sold here this visit. */
  const sealedOn = (c, g) => !!c.bond && ui.vals["cxs_" + g] === "1";

  function numbers(c) {
    const more = (c.rules && c.rules.pay_more_share) || 1.1;
    const lines = c.lines.map(ln => ({ ln, sealed: sealedOn(c, ln.good) }));
    const open = lines.filter(l => !l.sealed);
    const worth = open.reduce((n, l) => n + l.ln.value, 0);
    const taxOf = l => Math.ceil(c.rate * l.ln.value - 1e-9);
    const taxMore = l => Math.ceil(c.rate * Math.ceil(l.ln.value * more - 1e-9) - 1e-9);
    const tax = { nothing: 0, less: open.reduce((n, l) => n + taxOf(l), 0),
                  correct: open.reduce((n, l) => n + taxOf(l), 0), more: open.reduce((n, l) => n + taxMore(l), 0) };
    const pay = payOf();
    // The cargo she would like best (for "eyeing your {good}"): the dearest line not sealed.
    const hungry = open.slice().sort((a, b) => b.ln.value * (b.ln.appetite || 1) - a.ln.value * (a.ln.appetite || 1))[0] || null;
    const state = pay ? PAY_STATE[pay] : "bored";
    // "less" owes less than the correct tax, by a share the player does not see; "due" is what is sure.
    const due = pay === "less" ? null : pay ? tax[pay] : null;
    return { lines, open, worth, tax, pay, due, state, hungry, more,
             total: pay === "less" ? tax.correct : due || 0 };
  }

  /* ---------------------------------------------------------------- her face -- */
  const RULING = { tax: ["happy", "taxlady_tax"], buyout: ["happy", "taxlady_buyout"], caught: ["angry", "taxlady_caught"] };
  function inMood(i, mood) {
    return i.r.includes(mood) || (i.g || []).some(t => String(t).toLowerCase().split(/[^a-z]+/).includes(mood));
  }
  function moodPictures(c, state) {
    const list = herPictures(c);
    if (state === "welcome") return list;
    const [mood, role] = RULING[state] || [state === "over" ? "bored" : state, "taxlady_" + (state === "over" ? "bored" : state)];
    const matching = list.filter(i => inMood(i, mood) || i.r.includes(role));
    return matching.length ? matching : list;
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
  function head(c) {
    const port = esc(portName(c.port));
    let rate = "";
    if (!c.free) {
      const diff = Math.round((c.rate - c.base) * 1000) / 10;
      const move = Math.abs(diff) < 0.05 ? te("customs.rate_base") : te(diff > 0 ? "customs.rate_up" : "customs.rate_down", { base: pct(c.base) + "%" });
      rate = `<div class="cx-rate${diff > 0.05 ? " up" : diff < -0.05 ? " dn" : ""}"><small>${te("customs.rate")}</small><b>${pct(c.rate)}%</b><em>${move}</em></div>`;
    } else {
      rate = `<div class="cx-rate free"><b>${te(c.home_free ? "port.glance.home_free" : "customs.free")}</b></div>`;
    }
    return `<header class="cx-head"><div><p class="eyebrow">${te("customs.authority", { port })}</p>
      <h2 id="cx-title">${esc(c.name)}</h2><p class="cx-title">${esc(c.title)}</p></div>${rate}</header>`;
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
     Text only; it is already written into the Price Book. */
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
    if (!n.pay || n.pay === "correct" || n.pay === "more" || !n.worth) return "";
    return te("customs.pay_warn." + n.pay, { value: money(n.worth) });
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
        <small title="${te("customs.worth")}">${l.ln.qty.toLocaleString()} × ${money(l.ln.unit)} = <i>${money(l.ln.value)}</i></small></span>
      <span class="cx-line-foot">${l.sealed ? `<em class="cx-chip sealed">${te("customs.sealed")}</em>` : ""}${seal}</span></div>`;
  }

  function dueText(n) {
    if (!n.pay) return "—";
    return n.pay === "less" ? "< " + money(n.tax.correct) : money(n.due);
  }

  function declareHtml(c) {
    const n = numbers(c);
    shownState = n.state;
    const short = Math.max(0, n.total - S.me.cash);
    return `<div class="cx-body">
      ${head(c)}
      ${greeting(c)}
      ${tipHtml(c)}
      <p class="cx-tell" data-cx="tell">${esc(tell(c, n))}</p>
      <div class="cx-lines">${n.lines.map(l => lineRow(c, l)).join("")}</div>
      <p class="eyebrow cx-pay-head">${te(n.pay ? "customs.pay_head" : "customs.pay_pick")}</p>
      ${payButtons(c, n)}
      <p class="cx-warn" data-cx="warn">${payWarn(c, n)}</p>
      <div class="cx-sums">
        <span><small>${te("customs.total_worth")}</small><b data-cx="worth">${money(n.worth)}</b></span>
        <span class="due"><small>${te("customs.total_tax")}</small><b data-cx="tax">${dueText(n)}</b></span>
      </div>
      <p class="cx-short" data-cx="short">${short ? te("customs.debt", { amount: money(short) }) : ""}</p>
    </div>`;
  }

  function verdictHtml(c) {
    const res = c.result;
    const state = res.caught ? "caught" : res.lines.some(r => r.units && !r.back) ? "buyout" : "tax";
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
      return `<div class="cx-vline ${r.outcome}${r.back ? " back" : ""}"><span class="cx-good"><b>${name}</b><small>${r.outcome === "sealed" ? money(r.value) : money(r.declared) + " / " + money(r.value)}${res.choice === "less" && r.share != null ? " · " + te("customs.share", { pct: Math.round(r.share * 100) }) : ""}</small></span>
        <em class="cx-out ${r.outcome}">${te("customs.out." + out)}${r.outcome === "partial" ? ` (${r.units}/${r.qty})` : ""}${r.hid ? ` · <span class="cx-hid" title="${te("customs.hid_tip")}">${te("customs.hid", { qty: r.hid })}</span>` : ""}</em>
        <b class="cx-amt">${amount}</b>${back}</div>`;
    }).join("");
    const bribe = res.bribe ? `<p class="cx-note ${res.bribe.taken ? "" : "bad"}">${te(res.bribe.taken ? "customs.bribe_taken" : "customs.bribe_refused", { cost: money(res.bribe.cost) })}</p>` : "";
    const rep = res.rep ? `<span class="${res.rep > 0 ? "up" : "dn"}"><small>${te("customs.standing", { port: esc(portName(c.port)) })}</small><b>${res.rep > 0 ? "+" : ""}${Math.round(res.rep * 10) / 10}</b></span>` : "";
    return `<div class="cx-body">
      ${head(c)}
      <h3 class="cx-verdict ${state}">${te("customs.verdict")}</h3>
      <div class="cx-vlines">${rows}</div>${bribe}
      <div class="cx-sums">
        <span class="due"><small>${te("customs.paid_her")}</small><b>${money(res.tax + res.fine)}</b></span>
        ${res.paid ? `<span class="b"><small>${te("customs.she_paid")}</small><b>${money(res.paid)}</b></span>` : ""}${rep}
      </div>
      ${res.owed ? `<p class="cx-short">${te("customs.debt", { amount: money(res.owed) })}</p>` : ""}
    </div>`;
  }

  function welcomeHtml(c) {
    shownState = "welcome";
    return `<div class="cx-body">${head(c)}${greeting(c)}${tipHtml(c)}</div>`;
  }

  function html() {
    const c = cu();
    if (!c || S.me.ready) return "";
    if (ui.cxKey !== key(c)) {            // a new visit: start honest, no sweetener
      ui.cxKey = key(c);
      Object.keys(ui.vals).filter(k => k.startsWith("cx_") || k.startsWith("cxs_")).forEach(k => delete ui.vals[k]);
      ui.cxBribe = false; ui.cxPay = null; ui.cxTell = null; ui.cxSpoken = null;
    }
    const body = c.status === "declare" ? declareHtml(c) : c.status === "verdict" ? verdictHtml(c) : welcomeHtml(c);
    const label = c.status === "declare" ? "customs.declare_btn" : c.status === "verdict" ? "customs.continue" : "customs.welcome_btn";
    return `<div class="veil cx-veil"><section class="modal cx-desk ${c.status}" role="dialog" aria-labelledby="cx-title" data-state="${shownState}" data-key="${esc(key(c))}">
      <div class="cx-art" aria-hidden="true">${face(c, shownState, "cl-art-media")}</div>
      <div class="cx-panel">${body}<footer>${btn(te(label), c.status === "declare" ? "cx_declare" : "cx_done", "", "primary", c.status === "declare" && !payOf() && c.lines.some(ln => !sealedOn(c, ln.good)))}</footer></div>
    </section></div>`;
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
    set("worth", money(n.worth)); set("tax", dueText(n)); set("warn", payWarn(c, n));
    const short = Math.max(0, n.total - S.me.cash);
    set("short", short ? te("customs.debt", { amount: money(short) }) : "");
    const was = shownState;
    set("tell", esc(tell(c, n)));
    if (n.state !== was) {
      shownState = n.state;
      box.dataset.state = n.state;
      box.querySelector(".cx-art").innerHTML = face(c, n.state, "cl-art-media");
      showOnStage();
    }
  }

  /* The declaration desk already on screen is kept and brought up to date in place (buttons, seals,
     every number), never rebuilt: rebuilding it restarts the veil's fade and reloads her picture,
     which reads as the whole screen blinking. True when the desk was kept. */
  function keep() {
    const c = cu(), box = app.querySelector(".cx-desk.declare");
    if (!c || S.me.ready || c.status !== "declare" || !box) return false;
    if (ui.cxKey !== key(c) || box.dataset.key !== key(c)) return false;
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

  async function click(d) {
    const c = cu();
    if (!c) return false;
    switch (d.act) {
      case "cx_pay":
        if (PAYS.includes(d.pay)) ui.cxPay = d.pay;
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
        return true;
      }
      case "cx_back": await act("customs_buyback", { good: d.good }); return true;
      case "cx_done":
        if (await act("customs_done")) { ui.tab = "port"; ui.tally = false; render(); }
        return true;
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
    if (!document.querySelector(".cx-desk")) return;
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

  return { html, live, keep, click, speak, stage, markSpeaking, isOpen: () => !!(cu() && !S.me.ready) };
})();
