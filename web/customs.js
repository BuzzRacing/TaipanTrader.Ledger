/* SeaTrader: the Port Authority desk (engine.py, "port authority").

   On arrival in a port the house meets that port's tax officer before anything else. One slider per
   line of cargo sets what the captain declares it is worth (0 to 150% of its true worth here). While a
   slider moves, the tax, what a buyout or an audit would cost, her odds and her face all change in
   place. How much of her odds the captain sees depends on the difficulty level (Admin > Ratings &
   Difficulty > "Port Authority odds shown"): exact numbers, a bar without numbers, or only her tell.

   Her pictures are the port's Media Library pictures with the roles taxlady_bored, taxlady_curious,
   taxlady_hungry (her tells) and taxlady_tax, taxlady_buyout, taxlady_caught (her ruling). With several
   in a role she shows a different one each time her mood changes. A port without its own uses its
   plain "Tax lady" pictures, then Hong Kong's, then the officer's profile picture.

   Needs from player.js: S, D, ui, act(), render(), portName(), pct(). */
"use strict";

const Customs = (() => {
  const pick = {};          // role -> id of the picture last shown
  let shownState = null;    // the mood her picture is showing now

  const cu = () => (S && S.me && S.me.customs) || null;
  const key = c => c.port + ":" + S.turn;

  /* The same sums as engine.Game.customs_odds. */
  function odds(c, line, declared, bribe) {
    const r = c.rules, x = c.cx, value = Math.max(1, line.value), q = declared / value;
    const k = x.greed * x.mood * line.appetite * (x.rep_buy == null ? 1 : x.rep_buy);
    let buy, audit;
    if (q > 1 + 1e-9) { buy = 0; audit = 0; }
    else if (q >= 1 - 1e-9) { buy = r.buy_base * k; audit = 0; }
    else {
      const gap = 1 - q;
      buy = (r.buy_base + r.buy_k * Math.pow(gap, r.buy_exp)) * k;
      audit = (r.audit_base + r.audit_k * gap) * x.cunning * x.rep * x.diff * x.mood * bribe;
    }
    buy = Math.min(r.buy_cap, Math.max(0, buy)); audit = Math.min(r.audit_cap, Math.max(0, audit));
    if (buy + audit > 0.95) { const f = 0.95 / (buy + audit); buy *= f; audit *= f; }
    return [buy, audit];
  }

  /* Percent declared for each line (100 = honest), kept in ui.vals while the desk is open. */
  function pctOf(c, g) {
    const v = ui.vals["cx_" + g];
    return v == null ? 100 : Math.max(0, Math.min(Math.round(c.rules.max_declare * 100), +v));
  }

  /* A cargo left sealed in bond: no tax and no risk on it, and none of it sold here this visit. */
  const sealedOn = (c, g) => !!c.bond && ui.vals["cxs_" + g] === "1";

  function numbers(c) {
    const r = c.rules, bribe = !!ui.cxBribe;
    const lines = c.lines.map(ln => {
      const p = pctOf(c, ln.good), sealed = sealedOn(c, ln.good), d = sealed ? 0 : Math.round(ln.value * p / 100);
      return { ln, p, d, sealed, tax: Math.ceil(c.rate * d - 1e-9) };
    });
    const declared = lines.reduce((n, l) => n + l.d, 0);
    const bribeCost = Math.max(r.bribe_min, Math.ceil(r.bribe_share * c.rate * declared));
    const mult = bribe ? 1 - r.bribe_cut : 1;
    let worth = 0, tax = 0, lose = 0, caught = 0, wb = 0, wa = 0, under = 0, over = 0, hungry = null;
    lines.forEach(l => {
      if (l.sealed) { l.buy = 0; l.audit = 0; return; }
      const [b, a] = odds(c, l.ln, l.d, mult);
      l.buy = b; l.audit = a;
      worth += l.ln.value; tax += l.tax; wb += b * l.ln.value; wa += a * l.ln.value;
      if (l.d < l.ln.value) {
        under++;
        lose += l.ln.value - l.d;
        caught += Math.ceil(c.rate * l.ln.value - 1e-9) + Math.ceil(r.fine_mult * c.rate * (l.ln.value - l.d) - 1e-9);
      } else {
        caught += l.tax;
        if (l.d > l.ln.value) over++;
      }
      if (!hungry || b > hungry.buy) hungry = l;
    });
    const pb = worth ? wb / worth : 0, pa = worth ? wa / worth : 0;
    const risk = pb + pa;
    const state = under === 0 && over > 0 ? "over" : risk < r.tell_curious ? "bored" : risk < r.tell_hungry ? "curious" : "hungry";
    return { lines, declared, worth, tax, lose, caught, pb, pa, pt: Math.max(0, 1 - pb - pa), state, under, over,
             hungry, bribe, bribeCost, total: tax + (bribe ? bribeCost : 0) };
  }

  /* ---------------------------------------------------------------- her face -- */
  function pool(port, role) {
    return Media.items("port", [port], role, true).filter(i => i.r.includes(role));
  }
  /* The officer's own persona pictures in one mood (e.g. "happy"), strictly that mood. */
  function moodPool(officer, mood) {
    return officer ? Media.items("persona", [officer], mood, true).filter(i => i.r.includes(mood)) : [];
  }
  /* Where to look for each mood, best first. Her ruling never falls back to another port's lady
     while this port has any picture of its own: a port with no "taxlady_tax" picture shows its own
     officer pleased (persona "happy"), then her profile picture, then her calmest tell. */
  const LADDER = {
    welcome: [["port", "taxlady_bored"], ["port", "taxlady"], ["officer", "portrait"]],
    bored:   [["port", "taxlady_bored"], ["port", "taxlady"], ["officer", "portrait"]],
    over:    [["port", "taxlady_bored"], ["port", "taxlady"], ["officer", "portrait"]],
    curious: [["port", "taxlady_curious"], ["port", "taxlady_bored"], ["port", "taxlady"], ["officer", "portrait"]],
    hungry:  [["port", "taxlady_hungry"], ["port", "taxlady_curious"], ["port", "taxlady"], ["officer", "portrait"]],
    tax:     [["port", "taxlady_tax"], ["officer", "happy"], ["port", "taxlady"], ["officer", "portrait"], ["port", "taxlady_curious"], ["port", "taxlady_bored"]],
    buyout:  [["port", "taxlady_buyout"], ["officer", "happy"], ["port", "taxlady_hungry"], ["port", "taxlady"], ["officer", "portrait"]],
    caught:  [["port", "taxlady_caught"], ["officer", "angry"], ["port", "taxlady_hungry"], ["port", "taxlady"], ["officer", "portrait"]],
  };
  function face(c, state, cls) {
    cls = cls || "stg-img stg-keeper stg-taxlady cx-img";
    const roles = { bored: "taxlady_bored", curious: "taxlady_curious", hungry: "taxlady_hungry", over: "taxlady_bored",
                    tax: "taxlady_tax", buyout: "taxlady_buyout", caught: "taxlady_caught", welcome: "taxlady_bored" };
    const role = roles[state] || "taxlady";
    let list = [];
    for (const [where, r] of (LADDER[state] || LADDER.bored)) {
      list = where === "port" ? pool(c.port, r) : moodPool(c.officer, r);
      if (list.length) break;
    }
    if (!list.length) list = pool(D.home || "hongkong", role);
    if (!list.length) list = pool(D.home || "hongkong", "taxlady");
    if (!list.length) {
      const html = Media.html("persona", c.officer, "portrait", cls, ((VS.cast || {})[c.officer] || {}).portrait || "", { slot: "cx" });
      return html || `<i class="stg-mono">${esc((c.name || "?").split(/\s+/).map(w => w[0]).slice(0, 2).join(""))}</i>`;
    }
    const memo = state + ":" + key(c);
    let it = list.find(i => i.id === pick[memo]);
    if (!it) {
      // A new mood (or a new visit) shows a new picture, never the one she wore last.
      const last = pick.last;
      const choices = list.length > 1 ? list.filter(i => i.id !== last) : list;
      it = choices[Math.floor(Math.random() * choices.length)];
      pick[memo] = it.id;
    }
    pick.last = it.id;
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
    return `<blockquote class="cx-say${portrait ? " has-face" : ""}">
      ${portrait ? `<span class="cl-portrait">${portrait}</span>` : ""}
      <div><div class="cl-reader"><span><i aria-hidden="true">${DECK_ICONS.speech_on}</i>${te("log.reading")}</span><b>${esc(c.name)}</b></div>${esc(c.welcome)}</div>
    </blockquote>`;
  }

  function oddsBar(c, n) {
    if (c.view === "tell") return `<p class="cx-hidden">${te("customs.odds_hidden")}</p>`;
    const showNum = c.view === "exact";
    const seg = (cls, v, label) => `<i class="${cls}" style="flex-basis:${(v * 100).toFixed(2)}%" title="${esc(label)}${showNum ? " " + pct(v) + "%" : ""}"></i>`;
    const legend = showNum ? `<div class="cx-legend">
        <span class="t"><i></i>${te("customs.odds_tax")} <b data-cx="pt">${pct(n.pt)}%</b></span>
        <span class="b"><i></i>${te("customs.odds_buy")} <b data-cx="pb">${pct(n.pb)}%</b></span>
        <span class="a"><i></i>${te("customs.odds_caught")} <b data-cx="pa">${pct(n.pa)}%</b></span></div>`
      : `<div class="cx-legend"><span class="t"><i></i>${te("customs.odds_tax")}</span><span class="b"><i></i>${te("customs.odds_buy")}</span><span class="a"><i></i>${te("customs.odds_caught")}</span></div>`;
    return `<div class="cx-odds"><small>${te("customs.odds_title")}</small><div class="cx-bar" data-cx="bar">${seg("t", n.pt, t("customs.odds_tax"))}${seg("b", n.pb, t("customs.odds_buy"))}${seg("a", n.pa, t("customs.odds_caught"))}</div>${legend}</div>`;
  }

  /* A line declared under half its worth: say plainly what she may do with it. */
  function lowWarn(l) {
    return !l.sealed && l.p < 50 ? te("customs.low_warn", { price: money(l.d), value: money(l.ln.value) }) : "";
  }

  function chip(p, sealed) {
    return sealed ? `<em class="cx-chip sealed">${te("customs.sealed")}</em>` : p > 100 ? `<em class="cx-chip over">${te("customs.over")} +${p - 100}%</em>`
      : p < 100 ? `<em class="cx-chip under">${te("customs.under")} −${100 - p}%</em>`
      : `<em class="cx-chip honest">${te("customs.honest")}</em>`;
  }

  function lineRow(c, l) {
    const g = l.ln.good, gi = (D.graphics.goods || {})[g];
    const max = Math.round(c.rules.max_declare * 100);
    // "Keep sealed aboard" is a small pill on the slider's own caption line (opposite her chip), so it
    // costs the row no height. Ticking it greys the slider; the chip then reads "sealed in bond".
    const seal = c.bond ? `<label class="cx-seal" title="${te("customs.seal_tip")}"><input type="checkbox" data-act="cx_seal" data-good="${g}" ${l.sealed ? "checked" : ""}>
        <span>${te("customs.seal")}</span></label>` : "";
    return `<div class="cx-line${l.sealed ? " sealed" : ""}" data-good="${g}">
      <span class="cx-good">${gi ? `<img src="${esc(gi)}" alt="">` : ""}<b>${esc(D.goods[g].name)}</b>
        <small title="${te("customs.worth")}">${l.ln.qty.toLocaleString()} × ${money(l.ln.unit)} = <i>${money(l.ln.value)}</i></small></span>
      <span class="cx-slide" style="--h:${(100 / max * 100).toFixed(1)}%"><input type="range" class="cx-range" data-k="cx_${g}" min="0" max="${max}" step="1" value="${l.p}" ${l.sealed ? "disabled" : ""}
        aria-label="${te("customs.declare")} ${esc(D.goods[g].name)}"><span class="cx-slide-foot"><span data-cx="chip_${g}">${chip(l.p, l.sealed)}</span>${seal}</span></span>
      <span class="cx-decl"><small>${te("customs.declare")}</small><b data-cx="d_${g}">${l.sealed ? "—" : money(l.d)}</b></span>
      <span class="cx-tax"><small>${te("customs.tax")}</small><b data-cx="t_${g}">${money(l.tax)}</b></span>
      <p class="cx-warn" data-cx="w_${g}">${lowWarn(l)}</p></div>`;
  }

  function declareHtml(c) {
    const n = numbers(c);
    shownState = n.state;
    const short = Math.max(0, n.total - S.me.cash);
    return `<div class="cx-body">
      ${head(c)}
      ${greeting(c)}
      <p class="cx-tell" data-cx="tell">${esc(tell(c, n))}</p>
      <div class="cx-lines">${n.lines.map(l => lineRow(c, l)).join("")}</div>
      <div class="cx-quick">${btn(te("customs.all_low"), "cx_all", 'data-p="90"', "ghost")}${btn(te("customs.all_honest"), "cx_all", 'data-p="100"', "ghost")}${btn(te("customs.all_over"), "cx_all", 'data-p="110"', "ghost")}</div>
      <div class="cx-sums">
        <span><small>${te("customs.total_worth")}</small><b>${money(n.worth)}</b></span>
        <span><small>${te("customs.total_declared")}</small><b data-cx="declared">${money(n.declared)}</b></span>
        <span class="due"><small>${te("customs.total_tax")}</small><b data-cx="tax">${money(n.tax)}</b></span>
        <span class="risk b" data-cx="ifb"><small>${te("customs.if_bought")}</small><b>${n.under ? te("customs.if_bought_sub", { amount: money(n.lose) }) : "—"}</b></span>
        <span class="risk a" data-cx="ifa"><small>${n.under ? te("customs.if_caught") : n.over ? te("customs.if_over") : te("customs.if_caught")}</small><b>${n.under ? te("customs.if_caught_sub", { amount: money(n.caught) }) : n.over ? te("customs.if_over_sub") : "—"}</b></span>
      </div>
      ${oddsBar(c, n)}
      <label class="cx-bribe${n.bribe ? " on" : ""}"><input type="checkbox" data-act="cx_bribe" ${n.bribe ? "checked" : ""}>
        <span><b data-cx="bribe">${te("customs.bribe", { cost: money(n.bribeCost) })}</b><small>${te("customs.bribe_note")}</small></span></label>
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
      return `<div class="cx-vline ${r.outcome}${r.back ? " back" : ""}"><span class="cx-good"><b>${name}</b><small>${r.outcome === "sealed" ? money(r.value) : money(r.declared) + " / " + money(r.value)}</small></span>
        <em class="cx-out ${r.outcome}">${te("customs.out." + out)}${r.outcome === "partial" ? ` (${r.units}/${r.qty})` : ""}</em>
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
    return `<div class="cx-body">${head(c)}${greeting(c)}</div>`;
  }

  function html() {
    const c = cu();
    if (!c || S.me.ready) return "";
    if (ui.cxKey !== key(c)) {            // a new visit: start honest, no sweetener
      ui.cxKey = key(c);
      Object.keys(ui.vals).filter(k => k.startsWith("cx_") || k.startsWith("cxs_")).forEach(k => delete ui.vals[k]);
      ui.cxBribe = false; ui.cxTell = null; ui.cxSpoken = null;
    }
    const body = c.status === "declare" ? declareHtml(c) : c.status === "verdict" ? verdictHtml(c) : welcomeHtml(c);
    const label = c.status === "declare" ? "customs.declare_btn" : c.status === "verdict" ? "customs.continue" : "customs.welcome_btn";
    return `<div class="veil cx-veil"><section class="modal cx-desk ${c.status}" role="dialog" aria-labelledby="cx-title" data-state="${shownState}" data-key="${esc(key(c))}">
      <div class="cl-art cx-art" aria-hidden="true">${face(c, shownState, "cl-art-media")}</div>
      ${body}<footer>${btn(te(label), c.status === "declare" ? "cx_declare" : "cx_done", "", "primary")}</footer>
    </section></div>`;
  }

  /* While a slider moves: rewrite the numbers, the odds, her tell and (if her mood changed) her face. */
  function live(el) {
    const c = cu();
    if (!c || c.status !== "declare") return;
    const n = numbers(c), box = app.querySelector(".cx-desk");
    if (!box) return;
    const set = (k, h) => { const o = box.querySelector(`[data-cx="${k}"]`); if (o) o.innerHTML = h; };
    n.lines.forEach(l => {
      const g = l.ln.good;
      set("d_" + g, l.sealed ? "—" : money(l.d)); set("t_" + g, money(l.tax)); set("chip_" + g, chip(l.p, l.sealed)); set("w_" + g, lowWarn(l));
    });
    set("declared", money(n.declared)); set("tax", money(n.tax));
    set("ifb", `<small>${te("customs.if_bought")}</small><b>${n.under ? te("customs.if_bought_sub", { amount: money(n.lose) }) : "—"}</b>`);
    set("ifa", `<small>${n.over && !n.under ? te("customs.if_over") : te("customs.if_caught")}</small><b>${n.under ? te("customs.if_caught_sub", { amount: money(n.caught) }) : n.over ? te("customs.if_over_sub") : "—"}</b>`);
    set("pt", pct(n.pt) + "%"); set("pb", pct(n.pb) + "%"); set("pa", pct(n.pa) + "%");
    const bar = box.querySelector('[data-cx="bar"]');
    if (bar) [n.pt, n.pb, n.pa].forEach((v, i) => { if (bar.children[i]) bar.children[i].style.flexBasis = (v * 100).toFixed(2) + "%"; });
    set("bribe", te("customs.bribe", { cost: money(n.bribeCost) }));
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

  /* The declaration desk already on screen is kept and brought up to date in place (sliders, the
     sweetener, every number), never rebuilt: rebuilding it restarts the veil's fade and reloads her
     picture, which reads as the whole screen blinking. True when the desk was kept. */
  function keep() {
    const c = cu(), box = app.querySelector(".cx-desk.declare");
    if (!c || S.me.ready || c.status !== "declare" || !box) return false;
    if (ui.cxKey !== key(c) || box.dataset.key !== key(c)) return false;
    if (box.querySelectorAll(".cx-line").length !== c.lines.length) return false;
    box.querySelectorAll(".cx-range").forEach(r => {
      const g = r.dataset.k.slice(3), p = String(pctOf(c, g)), sealed = sealedOn(c, g);
      if (r.value !== p) r.value = p;
      r.disabled = sealed;
      const row = r.closest(".cx-line"), seal = row && row.querySelector('[data-act="cx_seal"]');
      if (row) row.classList.toggle("sealed", sealed);
      if (seal) seal.checked = sealed;
    });
    const tick = box.querySelector('[data-act="cx_bribe"]');
    if (tick) {
      tick.checked = !!ui.cxBribe;
      tick.closest(".cx-bribe").classList.toggle("on", !!ui.cxBribe);
    }
    live();
    return true;
  }

  async function click(d) {
    const c = cu();
    if (!c) return false;
    switch (d.act) {
      case "cx_all":
        c.lines.forEach(ln => { ui.vals["cx_" + ln.good] = String(+d.p); });
        render();
        return true;
      case "cx_bribe": ui.cxBribe = !ui.cxBribe; render(); return true;
      case "cx_seal":
        if (sealedOn(c, d.good)) delete ui.vals["cxs_" + d.good]; else ui.vals["cxs_" + d.good] = "1";
        render();
        return true;
      case "cx_declare": {
        const values = {}, sealed = c.lines.filter(ln => sealedOn(c, ln.good)).map(ln => ln.good);
        c.lines.forEach(ln => { if (!sealed.includes(ln.good)) values[ln.good] = Math.round(ln.value * pctOf(c, ln.good) / 100); });
        await act("customs_declare", { values, sealed, bribe: !!ui.cxBribe });
        return true;
      }
      case "cx_back": await act("customs_buyback", { good: d.good }); return true;
      case "cx_done":
        if (await act("customs_done")) { ui.tab = "port"; ui.tally = false; render(); }
        return true;
    }
    return false;
  }

  /* The stage in the right-hand column shows her while the desk is open: a new picture each time
     her mood changes. */
  function stage() {
    const c = cu();
    if (!c) return null;
    const state = shownState || "welcome";
    return { key: "cx:" + key(c) + ":" + state, html: face(c, state), name: c.name, note: c.title };
  }
  function showOnStage() {
    const f = stage();
    if (f) Stage.idle(f.key, f.html, f.name, f.note);
  }

  /* Her greeting is read aloud once per visit, by the officer of that port, the moment her desk opens:
     ahead of any news still waiting. While the Captain's Log is still up, the clip is fetched early so
     Inworld has already recorded it by the time the desk appears. */
  let warmed = "";
  function speak() {
    const c = cu();
    if (!c || !S.voice || !S.voice.customs) return;
    if (c.home_free) return;   // the house's own home port: she only waves you in, so nothing is read aloud
    const plan = S.voice.customs[0];
    if (plan && plan.u && warmed !== plan.u) { warmed = plan.u; fetch(plan.u).catch(() => {}); }
    if (!document.querySelector(".cx-desk")) return;
    if (ui.cxSpoken === key(c)) return;
    ui.cxSpoken = key(c);
    if (plan) Voice.say([Object.assign({ text: c.welcome, tag: "customs:" + key(c) }, plan)],
                        { group: "msg", replace: "msg", front: true });
  }

  function markSpeaking(item) {
    const greeting = document.querySelector(".cx-desk .cx-say");
    if (!greeting) return;
    if (item && item.tag === "customs:" + key(cu())) greeting.setAttribute("aria-current", "true");
    else greeting.removeAttribute("aria-current");
  }

  return { html, live, keep, click, speak, stage, markSpeaking, isOpen: () => !!(cu() && !S.me.ready) };
})();
