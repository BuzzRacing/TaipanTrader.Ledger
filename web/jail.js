"use strict";

/* The jail (jail.py, 19 Nov 2026).
   - While the Captain is inside, the whole player screen becomes the cell: the port's warden (her one
     photo, big) in front of that port's own jail cell, the charge, the month counter and the crew's news.
     Nothing can be done from here; the House is marked "set sail" every month.
   - A big fine may be swapped for time: the plea popup offers pay it all, 1 month and a share, or
     3 months and a smaller share.
   - Pacing (owner's decision, 19 Nov 2026, "Tap to serve each month"): the months used to turn on the
     server's 3-second watcher and flashed by. Now the arrest card waits for "Into the cell", each month
     for "Serve the month", and the release card for "Walk free" (back to the Port). Buttons arm after a
     short pause so a stray tap can't skip a card before the warden has spoken.
   Reads the player screen's state (S.me.jail, S.me.plea) and is called from player.js render(). */
const Jail = (() => {
  let screen = null, shownKey = null, dialog = null, dialogId = null, busy = false;
  let stage = null, armedAt = 0, armTimer = null;
  const ARM_MS = 2500;                       // a beat before a card's button can be pressed

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

  /* Her clip (owner's decision, 20 Nov 2026: video on the jail screen, "always the clip"): when she has a
     clip this screen may show, it plays instead of her photo, muted and looping, with the picture it was
     made from as its poster. Same preference as the photo: the non-clean one first (a family-friendly
     screen never receives NSFW clips, so it gets her clean one). A fresh pick for each card. */
  let clipPick = { key: "", id: "" };
  function wardenClip(cid) {
    const all = Media.items("persona", cid, "portrait", true).filter(i => i.t === "video");
    if (!all.length) return null;
    const clean = i => (i.g || []).includes("clean");
    const pick = all.filter(i => !clean(i));
    const list = pick.length ? pick : all;
    const key = cid + "|" + stage;
    if (clipPick.key !== key || !list.some(i => i.id === clipPick.id)) {
      const others = list.length > 1 ? list.filter(i => i.id !== clipPick.id) : list;
      clipPick = { key, id: others[Math.floor(Math.random() * others.length)].id };
    }
    return list.find(i => i.id === clipPick.id);
  }

  function wardenImg(cid, cls) {
    const clip = wardenClip(cid);
    const item = wardenItem(cid) || Media.choose("persona", cid, "portrait", { mode: "fixed", slot: "jail-warden" });
    const url = item ? item.u : castOf(cid).portrait;
    if (clip) {
      const poster = clip.po || url || "";
      return `<video class="${cls} jl-clip" data-jlclip="${esc(clip.id)}" src="${esc(clip.u)}"${poster ? ` poster="${esc(poster)}"` : ""} muted autoplay loop playsinline preload="auto" disablepictureinpicture></video>`;
    }
    return url ? `<img class="${cls}" src="${esc(url)}" alt="">` : `<div class="${cls} jl-noface" aria-hidden="true">⚿</div>`;
  }

  /* The screen is redrawn often (the log, the button arming): keep a clip that is already playing rather
     than restarting it from the top. */
  function redrawKeepingClip(html) {
    const old = screen.querySelector("video[data-jlclip]");
    screen.innerHTML = html;
    if (!old) return;
    const fresh = screen.querySelector(`video[data-jlclip="${old.dataset.jlclip}"]`);
    if (fresh) { fresh.replaceWith(old); old.play && old.play().catch(() => {}); }
  }
  function cellUrl(port) {
    const item = Media.choose("port", port, "jail_cell", { mode: "fixed", slot: "jail-cell", strict: true })
      || Media.choose("port", port, "night", { slot: "jail-cell-night" });
    return item ? item.u : "";
  }

  /* ---- the Reckoning look (owner's decision, 20 Nov 2026: "C4 should look like C3") -----------------
     Every jail card is laid out like the sea battle's result (battle.css .sf-result): the warden huge on
     the left, fading into the cell; her line in the quote card at her feet; the brass-cornered ledger
     card on the right with the title, four figure tiles, two columns and the button in its footer.
     The look comes from battle.css itself, so the two screens stay one family; jail.css only adds the
     jail's own accents (oxblood locked up, jade free, brass for the plea), the month ticks and the clip. */
  const tl = (key, fb, vars) => (T[key] == null ? esc(t(fb, vars)) : te(key, vars));
  const KEY_ICON = `<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="8" cy="8" r="4.5"/><path d="M11.2 11.2 20 20M16.5 16.5l2-2M14 14l2-2"/></svg>`;
  const BARS = `<svg viewBox="0 0 48 52" aria-hidden="true"><path d="M8 6h32M8 46h32M6 6v40M42 6v40"/><path d="M15 6v40M24 6v40M33 6v40"/><path d="M6 24h36" opacity=".55"/><circle cx="28.5" cy="27" r="2.2"/></svg>`;
  const OPEN = `<svg viewBox="0 0 48 52" aria-hidden="true"><path d="M8 6h20M8 46h20M6 6v40M15 6v40M24 6v40"/><path d="M28 6l14 5v34l-14 1z"/><path d="M33 8v37M38 10v34" opacity=".7"/></svg>`;
  const SCALES = `<svg viewBox="0 0 48 52" aria-hidden="true"><path d="M24 6v38M14 46h20M10 12h28"/><path d="M10 12 4 28h12zM38 12l-6 16h12z"/><path d="M4 28a6 6 0 0 0 12 0M32 28a6 6 0 0 0 12 0"/></svg>`;

  function bgHtml(port) {
    const cell = cellUrl(port);
    return `<div class="jl-bg"${cell ? ` style="background-image:url('${esc(cell)}')"` : ""}></div><div class="jl-shade"></div>`;
  }
  function wardenFigure(cid) {
    const who = castOf(cid);
    const face = wardenImg(cid, "jl-face");
    const nopic = face.includes("jl-noface");
    const line = who.catchphrase ? `<figcaption class="sf-rline jl-line"><header><span class="sf-rsay">${KEY_ICON}</span>
        <span>${esc(who.name || "")}${who.title ? " · " + esc(who.title) : ""}</span></header>
        <p>“${esc(who.catchphrase)}”</p></figcaption>`
      : who.name ? `<figcaption class="sf-rline jl-line"><header><span class="sf-rsay">${KEY_ICON}</span>
        <span>${esc(who.name)}${who.title ? " · " + esc(who.title) : ""}</span></header></figcaption>` : "";
    return `<figure class="sf-rwho jl-warden${nopic ? " nopic" : ""}">${nopic ? "" : face}${line}</figure>`;
  }
  function tile(label, value, cls) {
    return `<div class="${cls || ""}"><small>${label}</small><b>${value}</b></div>`;
  }
  function goodsCount(goods) {
    return Object.keys(goods || {}).reduce((n, g) => n + (goods[g] > 0 ? goods[g] : 0), 0);
  }

  /* ---- the cell ---------------------------------------------------------------------------- */
  function drawScreen(j) {
    const port = portName(j.port);
    const s = j.left === 1 ? "" : "s";
    const counter = j.fresh ? te("jail.starts")
      : j.left <= 0 ? te("jail.left_now") : te("jail.left", { left: j.left, s });
    const n = Math.min(j.months, (j.served || 0) + (j.fresh ? 0 : 1));
    const bars = Array.from({ length: j.months }, (_, i) =>
      `<span class="jl-tick${i < (j.served || 0) ? " done" : ""}${i === (j.served || 0) && !j.fresh ? " now" : ""}"></span>`).join("");
    const news = [];
    if (j.drunk) news.push(`<li><span>${te("jail.drunk", { lost: money(j.drunk) })}</span></li>`);
    if (j.spoiled && Object.keys(j.spoiled).length) news.push(`<li><span>${te("jail.spoiled", { goods: esc(goodsText(j.spoiled)) })}</span></li>`);
    const log = (S.me.log || []).slice(-4).map(l => `<li><span>${esc(l)}</span></li>`).join("");
    const months = m => tl("jail.tile.months", m === 1 ? "{n} month" : "{n} months", { n: m });
    const left = Math.max(0, j.fresh ? j.months : j.left);
    const rows = tile(tl("jail.tile.sentence", "Sentence"), months(j.months))
      + tile(tl("jail.tile.served", "Served"), months(j.served || 0), "gold")
      + tile(tl("jail.tile.left", "Still to serve"), months(left), left ? "dn" : "up")
      + tile(tl("jail.tile.drunk", "Silver lost aboard"), j.drunk ? "−" + money(j.drunk) : money(0), j.drunk ? "dn" : "");
    return `${bgHtml(j.port)}
      <div class="sf-result jl-result">
        ${wardenFigure(j.warden)}
        <section class="sf-card jl-card o-jailed" role="dialog" aria-modal="true" aria-labelledby="jl-title">
          <header><p class="eyebrow">${te("jail.eyebrow", { port })}</p>
            <div class="sf-rheading"><span class="sf-remblem" aria-hidden="true">${BARS}</span><h2 id="jl-title">${j.fresh ? te("jail.arrested") : te("jail.title")}</h2></div>
            <p class="sf-rreason">${j.fresh ? te("jail.arrest_lead", { months: j.months, s: j.months === 1 ? "" : "s", port })
              : te("jail.month_of", { n, months: j.months })}</p>
            <div class="jl-ticks">${bars}</div></header>
          <div class="sf-rows">${rows}</div>
          <div class="sf-cols">
            <div><h3>${te("jail.charge")}</h3><ul class="sf-rcargo jl-charges">${(j.charges || [j.charge]).map(c => `<li><span>${te("jail.charge." + c)}</span></li>`).join("")}</ul></div>
            <div class="sf-rledger"><h3>${te("jail.crew")}</h3><ul class="sf-rcargo">${news.join("") || `<li class="none">${te("jail.quiet")}</li>`}</ul>
              ${log ? `<h3>${tl("jail.log", "Captain's log")}</h3><ul class="sf-rcargo jl-log">${log}</ul>` : ""}</div>
          </div>
          <p class="sf-note">${te("jail.fleet", { port })} ${te("jail.wait")}</p>
          <footer>
            <p class="sf-net jl-net"><span>${counter}</span><b>${j.fresh ? months(j.months) : te("jail.month_of", { n, months: j.months })}</b></p>
            ${actButton(j)}
          </footer>
        </section>
      </div>`;
  }

  function armed() { return Date.now() - armedAt >= ARM_MS; }

  function actButton(j) {
    if (j.ready) {
      const names = (S.waiting || []).filter(n => n !== S.me.name);
      return `<p class="jl-waiting">${names.length ? te("jail.waiting", { names: esc(names.join(", ")) }) : te("jail.served")}</p>`;
    }
    const label = j.fresh ? te("jail.btn_into") : j.left <= 1 ? te("jail.btn_last") : te("jail.btn_serve");
    return `<button type="button" class="primary jl-go" data-go="jail_serve"${armed() ? "" : " disabled"}>${label} <span aria-hidden="true">&rarr;</span></button>`;
  }

  /* ---- the release card -------------------------------------------------------------------- */
  function drawFreed(f) {
    const port = portName(f.port), s = f.months === 1 ? "" : "s";
    const lines = [];
    if (f.drunk) lines.push(te("freed.drunk", { lost: money(f.drunk) }));
    if (f.spoiled && Object.keys(f.spoiled).length) lines.push(te("freed.spoiled", { goods: esc(goodsText(f.spoiled)) }));
    if (!lines.length) lines.push(te("freed.clean"));
    const months = m => tl("jail.tile.months", m === 1 ? "{n} month" : "{n} months", { n: m });
    const spoiled = goodsCount(f.spoiled);
    const rows = tile(tl("jail.tile.served", "Served"), months(f.months), "gold")
      + tile(tl("jail.tile.drunk", "Silver lost aboard"), f.drunk ? "−" + money(f.drunk) : money(0), f.drunk ? "dn" : "up")
      + tile(tl("jail.tile.spoiled", "Cargo spoiled"), spoiled ? spoiled.toLocaleString("en-US") : "0", spoiled ? "dn" : "up")
      + tile(tl("jail.tile.standing", "Standing"), tl("jail.tile.eased", "Eased"), "up");
    return `${bgHtml(f.port)}
      <div class="sf-result jl-result">
        ${wardenFigure(f.warden)}
        <section class="sf-card jl-card o-freed" role="dialog" aria-modal="true" aria-labelledby="jl-title">
          <header><p class="eyebrow">${te("freed.eyebrow", { port })}</p>
            <div class="sf-rheading"><span class="sf-remblem" aria-hidden="true">${OPEN}</span><h2 id="jl-title">${te("freed.title")}</h2></div>
            <p class="sf-rreason">${te("freed.lead", { months: f.months, s })}</p></header>
          <div class="sf-rows">${rows}</div>
          <div class="sf-cols">
            <div><h3>${te("jail.crew")}</h3><ul class="sf-rcargo">${lines.map(l => `<li><span>${l}</span></li>`).join("")}</ul></div>
            <div class="sf-rledger"><h3>${tl("jail.tile.standing", "Standing")}</h3><ul class="sf-rcargo"><li><span>${te("freed.standing", { port })}</span></li></ul></div>
          </div>
          <footer>
            <p class="sf-net up"><span>${tl("jail.tile.served", "Served")}</span><b>${months(f.months)}</b></p>
            <button type="button" class="primary jl-go free" data-go="jail_free"${armed() ? "" : " disabled"}>${te("freed.btn")} <span aria-hidden="true">&rarr;</span></button>
          </footer>
        </section>
      </div>`;
  }

  async function press(btn) {
    if (busy || !armed()) return;
    busy = true;
    btn.disabled = true;
    const ok = await act(btn.dataset.go, {});
    busy = false;
    if (!ok && btn.isConnected) btn.disabled = false;
  }

  function syncScreen() {
    const jv = S && S.me && S.phase !== "lobby" && S.me.jail;
    const j = jv && jv.jail;
    const f = !j && jv && S.phase === "port" && jv.freed;       // the release card, until "Walk free"
    document.body.classList.toggle("in-jail", !!(j || f));
    if (!j && !f) {
      if (screen) { screen.remove(); screen = null; shownKey = null; stage = null; }
      return;
    }
    if (!screen) {
      screen = document.createElement("div");
      screen.id = "jail-screen";
      screen.className = "jl-screen";
      screen.addEventListener("click", e => {
        const b = e.target.closest(".jl-go");
        if (b && !b.disabled) press(b);
      });
      document.body.appendChild(screen);
    }
    // each new card (arrest, each month, release) gets a fresh pause before its button arms
    const now = j ? ["jail", j.fresh, j.served, j.months] : ["free", f.turn, f.port];
    const nowKey = JSON.stringify(now);
    if (nowKey !== stage) {
      stage = nowKey;
      armedAt = Date.now();
      clearTimeout(armTimer);
      armTimer = setTimeout(() => { shownKey = null; syncScreen(); }, ARM_MS + 50);
    }
    const key = JSON.stringify([j || f, (S.me.log || []).slice(-4), S.turn, S.me.cash, S.waiting, armed()]);
    if (key !== shownKey) { shownKey = key; redrawKeepingClip(j ? drawScreen(j) : drawFreed(f)); }
  }

  /* ---- the plea deal ----------------------------------------------------------------------- */
  function closePlea() {
    if (dialog) { try { dialog.close(); } catch (e) { /* closed */ } dialog.remove(); }
    dialog = dialogId = null;
  }

  function drawPlea(pl) {
    const port = portName(pl.port);
    const opt = o => {
      if (!o.months) {
        return `<button type="button" class="jl-opt pay" data-m="0"><small>${te("plea.share", { pct: 100 })}</small>
          <b>${te("plea.pay_all")}</b><span class="jl-amt">${money(o.pay)}</span></button>`;
      }
      return `<button type="button" class="jl-opt cell" data-m="${o.months}"><small>${te("plea.share", { pct: Math.round(o.share * 100) })}</small>
        <b>${te("plea.months", { months: o.months, s: o.months === 1 ? "" : "s" })}</b>
        <span class="jl-amt">${te("plea.pay", { pay: money(o.pay) })}</span></button>`;
    };
    return `${bgHtml(pl.port)}
      <div class="sf-result jl-result">
        ${wardenFigure(pl.warden)}
        <section class="sf-card jl-card o-plea" aria-labelledby="jl-plea-title">
          <header><p class="eyebrow">${te("plea.eyebrow", { port })}</p>
            <div class="sf-rheading"><span class="sf-remblem" aria-hidden="true">${SCALES}</span><h2 id="jl-plea-title">${te("plea.title", { fine: money(pl.amount) })}</h2></div>
            <p class="sf-rreason">${te("plea.why." + pl.charge)}</p>
            <p class="jl-lead">“${te("plea.lead")}”</p></header>
          <div class="jl-opts">${pl.opts.map(opt).join("")}</div>
          <p class="sf-note">${te("plea.note")}</p>
          <footer><p class="sf-net dn"><span>${tl("jail.tile.fine", "The fine")}</span><b>${money(pl.amount)}</b></p>
            <p class="jl-auto">${te("plea.auto")}</p></footer>
        </section>
      </div>`;
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
