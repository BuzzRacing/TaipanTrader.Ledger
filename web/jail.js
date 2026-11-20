"use strict";

/* The jail (jail.py, 19 Nov 2026).
   - While the Captain is inside, the whole player screen becomes the cell: the port's warden (her one
     photo, big) in front of that port's own jail cell, the charge, the month counter and the crew's news.
     Nothing can be done from here; the House is marked "set sail" every month.
   - A big fine may be swapped for time: the plea popup offers pay it all, 1 month and a share, or
     3 months and a smaller share.
   Reads the player screen's state (S.me.jail, S.me.plea) and is called from player.js render(). */
const Jail = (() => {
  let screen = null, shownKey = null, dialog = null, dialogId = null, busy = false;

  function castOf(cid) {
    const c = (typeof VS !== "undefined" && VS && VS.cast && VS.cast[cid]) || null;
    return c || {};
  }
  function goodsText(goods) {
    return Object.keys(goods || {}).filter(g => goods[g] > 0)
      .map(g => goods[g].toLocaleString("en-US") + " " + ((D.goods && D.goods[g] && D.goods[g].name) || g).toLowerCase())
      .join(", ");
  }
  function portName(k) { return (D.ports && D.ports[k] && D.ports[k].name) || k; }

  /* Her photo: the nude one first; a family-friendly screen never receives it, so it gets her clean
     photo (tagged "clean", tools/queue_jail_clean_pictures.py). One photo each: the newest of its kind. */
  function wardenItem(cid) {
    const all = Media.items("persona", cid, "portrait").filter(i => i.t === "image");
    const clean = i => (i.g || []).includes("clean");
    const pick = all.filter(i => !clean(i));
    const list = pick.length ? pick : all;
    return list.length ? list[list.length - 1] : null;
  }

  function wardenImg(cid, cls) {
    const item = wardenItem(cid) || Media.choose("persona", cid, "portrait", { mode: "fixed", slot: "jail-warden" });
    const url = item ? item.u : castOf(cid).portrait;
    return url ? `<img class="${cls}" src="${esc(url)}" alt="">` : `<div class="${cls} jl-noface" aria-hidden="true">⚿</div>`;
  }
  function cellUrl(port) {
    const item = Media.choose("port", port, "jail_cell", { mode: "fixed", slot: "jail-cell", strict: true })
      || Media.choose("port", port, "night", { slot: "jail-cell-night" });
    return item ? item.u : "";
  }

  /* ---- the cell ---------------------------------------------------------------------------- */
  function drawScreen(j) {
    const who = castOf(j.warden), port = portName(j.port);
    const s = j.left === 1 ? "" : "s";
    const counter = j.fresh ? te("jail.starts")
      : j.left <= 0 ? te("jail.left_now") : te("jail.left", { left: j.left, s });
    const n = Math.min(j.months, (j.served || 0) + (j.fresh ? 0 : 1));
    const bars = Array.from({ length: j.months }, (_, i) =>
      `<span class="jl-tick${i < (j.served || 0) ? " done" : ""}${i === (j.served || 0) && !j.fresh ? " now" : ""}"></span>`).join("");
    const news = [];
    if (j.drunk) news.push(te("jail.drunk", { lost: money(j.drunk) }));
    if (j.spoiled && Object.keys(j.spoiled).length) news.push(te("jail.spoiled", { goods: esc(goodsText(j.spoiled)) }));
    const log = (S.me.log || []).slice(-4).map(l => `<li>${esc(l)}</li>`).join("");
    const cell = cellUrl(j.port);
    return `<div class="jl-bg"${cell ? ` style="background-image:url('${esc(cell)}')"` : ""}></div>
      <div class="jl-shade"></div>
      <div class="jl-bars" aria-hidden="true"></div>
      <section class="jl-card" role="dialog" aria-modal="true" aria-labelledby="jl-title">
        <figure class="jl-warden">${wardenImg(j.warden, "jl-face")}
          <figcaption>${who.name ? `<strong>${esc(who.name)}</strong><span>${esc(who.title || "")}</span>` : ""}</figcaption></figure>
        <div class="jl-body">
          <p class="jl-eyebrow">${te("jail.eyebrow", { port })}</p>
          <h1 id="jl-title">${te("jail.title")}</h1>
          <p class="jl-month">${j.fresh ? "" : te("jail.month_of", { n, months: j.months })}</p>
          <div class="jl-ticks">${bars}</div>
          <p class="jl-left">${counter}</p>
          <dl class="jl-charge"><dt>${te("jail.charge")}</dt>
            <dd>${(j.charges || [j.charge]).map(c => te("jail.charge." + c)).join("<br>")}</dd></dl>
          ${who.catchphrase ? `<blockquote>“${esc(who.catchphrase)}”</blockquote>` : ""}
          <h2>${te("jail.crew")}</h2>
          ${news.length ? `<p class="jl-news">${news.join("<br>")}</p>` : `<p class="jl-news quiet">${te("jail.quiet")}</p>`}
          ${log ? `<ul class="jl-log">${log}</ul>` : ""}
          <p class="jl-foot">${te("jail.fleet", { port })}<br>${te("jail.wait")}</p>
        </div>
      </section>`;
  }

  function syncScreen() {
    const j = S && S.me && S.phase !== "lobby" && S.me.jail && S.me.jail.jail;
    document.body.classList.toggle("in-jail", !!j);
    if (!j) {
      if (screen) { screen.remove(); screen = null; shownKey = null; }
      return;
    }
    if (!screen) {
      screen = document.createElement("div");
      screen.id = "jail-screen";
      screen.className = "jl-screen";
      document.body.appendChild(screen);
    }
    const key = JSON.stringify([j, (S.me.log || []).slice(-4), S.turn, S.me.cash]);
    if (key !== shownKey) { shownKey = key; screen.innerHTML = drawScreen(j); }
  }

  /* ---- the plea deal ----------------------------------------------------------------------- */
  function closePlea() {
    if (dialog) { try { dialog.close(); } catch (e) { /* closed */ } dialog.remove(); }
    dialog = dialogId = null;
  }

  function drawPlea(pl) {
    const port = portName(pl.port), who = castOf(pl.warden);
    const opt = o => {
      if (!o.months) {
        return `<button type="button" class="jl-opt pay" data-m="0"><b>${te("plea.pay_all")}</b>
          <span class="jl-amt">${money(o.pay)}</span><small>${te("plea.share", { pct: 100 })}</small></button>`;
      }
      return `<button type="button" class="jl-opt cell" data-m="${o.months}">
        <b>${te("plea.months", { months: o.months, s: o.months === 1 ? "" : "s" })}</b>
        <span class="jl-amt">${te("plea.pay", { pay: money(o.pay) })}</span>
        <small>${te("plea.share", { pct: Math.round(o.share * 100) })}</small></button>`;
    };
    return `<section class="jl-plea">
      <figure class="jl-warden small">${wardenImg(pl.warden, "jl-face")}
        <figcaption>${who.name ? `<strong>${esc(who.name)}</strong><span>${esc(who.title || "")}</span>` : ""}</figcaption></figure>
      <div class="jl-body">
        <p class="jl-eyebrow">${te("plea.eyebrow", { port })}</p>
        <h2>${te("plea.title", { fine: money(pl.amount) })}</h2>
        <p class="jl-why">${te("plea.why." + pl.charge)}</p>
        <p class="jl-lead">“${te("plea.lead")}”</p>
        <div class="jl-opts">${pl.opts.map(opt).join("")}</div>
        <p class="jl-note">${te("plea.note")}</p>
        <p class="jl-note">${te("plea.auto")}</p>
      </div></section>`;
  }

  function syncPlea() {
    const pl = S && S.me && S.phase === "port" && S.me.jail && S.me.jail.plea;
    if (!pl) { closePlea(); return; }
    if (dialog && dialogId === pl.id) return;
    closePlea();
    dialogId = pl.id;
    dialog = document.createElement("dialog");
    dialog.className = "jl-dialog";
    dialog.innerHTML = drawPlea(pl);
    dialog.addEventListener("cancel", e => e.preventDefault());     // it must be answered
    dialog.querySelectorAll(".jl-opt").forEach(b => b.addEventListener("click", async () => {
      if (busy) return;
      busy = true;
      dialog.querySelectorAll(".jl-opt").forEach(x => { x.disabled = true; });
      const ok = await act("plea", { months: Number(b.dataset.m) });
      busy = false;
      if (!ok && dialog) dialog.querySelectorAll(".jl-opt").forEach(x => { x.disabled = false; });
    }));
    document.body.appendChild(dialog);
    try { dialog.showModal(); } catch (e) { dialog.setAttribute("open", ""); }
  }

  function sync() {
    if (typeof S === "undefined" || typeof D === "undefined" || !S || !D) return;
    syncScreen();
    syncPlea();
  }

  function busyNow() { return !!(screen || dialog); }

  return { sync, busy: busyNow };
})();
