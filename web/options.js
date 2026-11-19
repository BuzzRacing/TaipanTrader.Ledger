/* The Captain's Options popup (captain button > Options), decided with Anthony 19 Nov 2026
   (project doc "SeaTrader Captain Options"):

     The Voyage Clock   game date, month n of N, months left, the season's end; who has set sail
     My Captain         pick a portrait from the Media Library, or have a new one painted
     My House           rename and re-colour the House, pick or make its seal. The House is its id:
                        a new name shows everywhere, old log lines, news and records included
     Table settings     Mode is shown, locked (the host changes it in Admin); Family-friendly for
                        this screen only
     This screen        how fast the backgrounds change and how dark they are (this device only)
     Exit Game          closes the game on this screen only; the House stays and the table waits

   Uses the player screen's globals (S, D, token, stream, post, t, te, esc, toast). */
"use strict";

const Options = (() => {
  const KEY_SECS = "seatrader_bg_secs", KEY_DIM = "seatrader_bg_dim", KEY_FAMILY = "seatrader_family";
  let dlg = null, info = null, timer = null, poll = null, exiting = false, busy = false;

  const get = k => { try { return localStorage.getItem(k); } catch (e) { return null; } };
  const put = (k, v) => { try { if (v === null) localStorage.removeItem(k); else localStorage.setItem(k, v); } catch (e) { /* private mode */ } };
  const tx = (key, fallback, vars) => {
    const s = typeof T !== "undefined" && T[key] != null ? t(key, vars) : fallback.replace(/\{(\w+)\}/g, (_, k) => (vars || {})[k] ?? "");
    return esc(s);
  };

  /* ------------------------------------------------ this screen's background -- */
  function tableBg() {
    const root = document.documentElement, st = root.style;
    const keep = [st.getPropertyValue("--amb-seconds"), st.getPropertyValue("--amb-dim")];
    st.removeProperty("--amb-seconds"); st.removeProperty("--amb-dim");
    const cs = getComputedStyle(root);
    const out = { secs: Math.round(parseFloat(cs.getPropertyValue("--amb-seconds")) || 40),
                  dim: Math.round((parseFloat(cs.getPropertyValue("--amb-dim")) || .55) * 100) };
    if (keep[0]) st.setProperty("--amb-seconds", keep[0]);
    if (keep[1]) st.setProperty("--amb-dim", keep[1]);
    return out;
  }
  function applyBg() {
    const st = document.documentElement.style, secs = get(KEY_SECS), dim = get(KEY_DIM);
    if (secs) st.setProperty("--amb-seconds", String(parseInt(secs, 10))); else st.removeProperty("--amb-seconds");
    if (dim) st.setProperty("--amb-dim", String(parseInt(dim, 10) / 100)); else st.removeProperty("--amb-dim");
  }
  applyBg();

  /* ------------------------------------------------------------ the clock -- */
  function monthLabel(turn) {
    const y = ((D && D.start_year) || 1860) + Math.floor(turn / 12);
    return t("mon." + (turn % 12)) + " " + y;
  }
  function clockHtml() {
    if (!S || !S.me) return "";
    const total = (S.years || 0) * 12, n = Math.min(total || S.turn + 1, S.turn + 1);
    const left = Math.max(0, (S.turns_left || 0) - 1);
    const end = total ? monthLabel(total - 1) : "";
    const lines = S.free_play
      ? `<p class="op-note">${tx("opt.free", "Free play: the season is over and the trading goes on.")}</p>`
      : `<p class="op-big">${tx("opt.month", "Month {n} of {total}", { n, total })}</p>
         <p>${left ? tx("opt.left", "{n} months left", { n: left }) : tx("opt.left_one", "The last month of the season")}
           ${end ? ` · ${tx("opt.ends", "The season ends {date}", { date: end })}` : ""}</p>`;
    const seats = (S.players || []).map(q => {
      const state = q.ready ? "sailed" : q.present ? "in_port" : "away";
      const word = state === "sailed" ? tx("opt.sailed", "Set sail") : state === "in_port" ? tx("opt.in_port", "Still in port") : tx("opt.away", "Not at a screen");
      return `<li class="op-seat ${state}"><b>${esc(q.firm)}</b><span>${esc(q.name)}${q.id === S.me.id ? ` (${tx("opt.you", "you")})` : ""}</span><em>${word}</em></li>`;
    }).join("");
    const all = (S.players || []).length && (S.players || []).every(q => q.ready);
    return `<p class="op-date">${esc(S.date || "")}</p>${lines}
      <ul class="op-seats">${seats}</ul>${all ? `<p class="op-note">${tx("opt.all_sailed", "Everyone has set sail.")}</p>` : ""}`;
  }

  /* ------------------------------------------------------- the pictures -- */
  function tiles(list, what) {
    const fam = screenFamily();
    const shown = list.filter(i => !(fam && i.nsfw));
    if (!shown.length) return "";
    return `<div class="op-tiles ${what}">${shown.map(i =>
      `<button type="button" class="op-tile${i.primary ? " on" : ""}" data-op="pick" data-what="${what}" data-id="${esc(i.id)}" aria-pressed="${i.primary}">
         <img src="${esc(i.url)}" alt="" loading="lazy"></button>`).join("")}</div>`;
  }

  function captainHtml() {
    if (!info) return `<p class="op-note">…</p>`;
    if (!info.captain) return `<p class="op-note">${tx("opt.no_captain", "Join with a saved Captain (PIN) to choose a portrait and a seal.")}</p>`;
    const list = tiles(info.portraits || [], "portrait");
    const painting = (info.painting || {}).captain;
    return `<p class="op-who"><b>${esc(info.captain.name)}</b>${info.captain.title ? ` <span>${esc(info.captain.title)}</span>` : ""}</p>
      ${list ? `<p class="op-hint">${tx("opt.photo_pick", "Tap a portrait to make it yours.")}</p>${list}` : `<p class="op-note">${tx("opt.photo_none", "No portraits yet.")}</p>`}
      <div class="op-row">${painting
        ? `<p class="op-note op-busy">${tx("opt.generating", "A new picture is being made. It appears here when it is done.")}</p>`
        : `<button type="button" data-op="generate" data-what="portrait">${tx("opt.generate", "Paint a new portrait")}</button>`}</div>`;
  }

  function houseHtml() {
    const me = (S && S.me) || {};
    const h = info && info.house;
    const name = h ? h.name : me.firm || "";
    const crests = h ? tiles(info.crests || [], "crest") : "";
    const painting = h && (info.painting || {}).house;
    return `<form class="op-house" data-op="house">
        <label><span>${tx("opt.house_name", "House name")}</span>
          <input type="text" name="name" maxlength="28" value="${esc(name)}" autocomplete="off" spellcheck="true"></label>
        ${h ? `<label class="op-color"><span>${tx("opt.house_color", "House colour")}</span>
          <input type="color" name="color" value="${esc(h.color || "#b8862b")}"></label>` : ""}
        <button type="submit" class="primary">${tx("opt.save_house", "Save House")}</button>
      </form>
      <p class="op-note">${h ? tx("opt.house_note", "The new name shows everywhere, old log lines, news and records included.")
                             : info ? tx("opt.house_game_only", "This House was joined by name, so the new name applies to this game only.") : ""}</p>
      ${h ? `<h4>${tx("opt.crest", "The House seal")}</h4>
        ${crests ? `<p class="op-hint">${tx("opt.crest_pick", "Tap a seal to make it your stamp.")}</p>${crests}` : `<p class="op-note">${tx("opt.crest_none", "No seal yet.")}</p>`}
        <div class="op-row">${painting
          ? `<p class="op-note op-busy">${tx("opt.generating", "A new picture is being made. It appears here when it is done.")}</p>`
          : `<button type="button" data-op="generate" data-what="crest">${tx("opt.crest_generate", "Make a new seal")}</button>`}</div>` : ""}`;
  }

  function tableHtml() {
    const mode = (info && info.mode) || (D && D.difficulty) || "";
    const tableFam = info ? info.table_family : (D && D.rating === "family" && !D.screen_family);
    return `<div class="op-mode"><span>${tx("opt.mode", "Mode")}</span><b>${esc(mode)}</b>
        <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="11" width="14" height="9" rx="1.5"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/></svg></div>
      <p class="op-note">${tx("opt.mode_note", "Set by the host in Admin. Locked during a game.")}
        ${info && info.admin ? ` <a href="/admin" target="_blank" rel="noopener">${tx("opt.mode_admin", "Open Admin")}</a>` : ""}</p>
      <label class="op-switch${tableFam ? " locked" : ""}">
        <input type="checkbox" data-op="family" ${tableFam || screenFamily() ? "checked" : ""} ${tableFam ? "disabled" : ""}>
        <span>${tx("opt.family", "Family-friendly on this screen")}</span></label>
      <p class="op-note">${tableFam ? tx("opt.family_table", "Family-friendly is on for the whole table (set in Admin).")
        : tx("opt.family_note", "Hides NSFW pictures and uses the family names of cargo on this screen only. Spoken lines stay as the table has them.") + " " + tx("opt.reload", "This screen reloads to apply it.")}</p>`;
  }

  function screenHtml() {
    const tb = tableBg();
    const secs = parseInt(get(KEY_SECS), 10) || tb.secs, dim = parseInt(get(KEY_DIM), 10);
    const d = isNaN(dim) ? tb.dim : dim;
    const own = get(KEY_SECS) || get(KEY_DIM);
    return `<label class="op-range"><span>${tx("opt.bg_secs", "Backgrounds change every")}</span>
        <input type="range" min="10" max="180" step="5" value="${secs}" data-op="bg_secs"><output>${tx("opt.secs", "{n} s", { n: secs })}</output></label>
      <label class="op-range"><span>${tx("opt.bg_dim", "Background darkness")}</span>
        <input type="range" min="0" max="90" step="5" value="${d}" data-op="bg_dim"><output>${tx("opt.pct", "{n}%", { n: d })}</output></label>
      <div class="op-row"><button type="button" data-op="bg_reset" ${own ? "" : "disabled"}>${tx("opt.bg_reset", "Use the table's settings")}</button></div>`;
  }

  function exitHtml() {
    return `<p class="op-note">${tx("opt.exit_note", "Closes the game on this screen only. Your House stays in the game, and the table waits for you to set sail.")}</p>
      <div class="op-row">${exiting
        ? `<button type="button" class="bad" data-op="exit_yes">${tx("opt.exit_yes", "Leave this screen")}</button>
           <button type="button" data-op="exit_no">${tx("opt.exit_no", "Stay")}</button>`
        : `<button type="button" data-op="exit_ask">${tx("opt.exit", "Exit Game")}</button>`}</div>`;
  }

  function section(id, title, body) {
    return `<section class="op-sec op-${id}"><h3>${title}</h3><div data-sec="${id}">${body}</div></section>`;
  }

  function draw(only) {
    if (!dlg) return;
    const parts = { clock: clockHtml, captain: captainHtml, house: houseHtml, table: tableHtml, screen: screenHtml, exit: exitHtml };
    for (const k of only || Object.keys(parts)) {
      const el = dlg.querySelector(`[data-sec="${k}"]`);
      if (!el) continue;
      if (k === "house" && el.contains(document.activeElement) && document.activeElement.tagName === "INPUT") continue;
      const html = parts[k]();
      if (el.dataset.html !== html) { el.innerHTML = html; el.dataset.html = html; }
    }
  }

  async function load() {
    try {
      const r = await fetch("/api/options?token=" + encodeURIComponent(token || ""));
      const res = await r.json();
      if (res.ok) info = res;
    } catch (e) { /* offline: keep what we have */ }
    draw(["captain", "house", "table"]);
    const painting = info && info.painting && (info.painting.captain || info.painting.house);
    clearTimeout(poll);
    if (painting && dlg) poll = setTimeout(load, 5000);
  }

  async function send(body) {
    if (busy) return null;
    busy = true;
    try {
      const res = await post("/api/options", Object.assign({ token }, body));
      if (res.ok) { if (res.msg) toast(res.msg); } else toast(res.error, true);
      return res;
    } finally { busy = false; }
  }

  function leave() {
    close();
    try { if (typeof stream !== "undefined" && stream) stream.close(); } catch (e) { /* already closed */ }
    try { if (typeof Voice !== "undefined") { if (Voice.stop) Voice.stop(); else if (Voice.drop) Voice.drop(); } } catch (e) { /* ignore */ }
    const curtain = document.createElement("div");
    curtain.className = "op-curtain";
    curtain.innerHTML = `<div><p class="op-eyebrow">${esc(typeof brandName === "function" && D && D.brand ? brandName(D.brand) : "")}</p>
      <h2>${tx("opt.exit_done", "You have left the game on this screen.")}</h2>
      <p>${tx("opt.exit_done_note", "Your House is still in the game. The table waits for you to set sail.")}</p>
      <button type="button" class="primary">${tx("opt.rejoin", "Take the helm again")}</button></div>`;
    curtain.querySelector("button").addEventListener("click", () => location.reload());
    document.body.appendChild(curtain);
  }

  function onClick(e) {
    const b = e.target.closest("[data-op]");
    if (!b || b.tagName === "FORM" || b.tagName === "INPUT") return;
    const op = b.dataset.op;
    if (op === "close") return close();
    if (op === "pick") {
      send({ op: "pick", what: b.dataset.what, id: b.dataset.id }).then(res => { if (res && res.ok) load(); });
    } else if (op === "generate") {
      send({ op: "generate", what: b.dataset.what }).then(res => { if (res && res.ok) load(); });
    } else if (op === "bg_reset") {
      put(KEY_SECS, null); put(KEY_DIM, null); applyBg(); draw(["screen"]);
    } else if (op === "exit_ask" || op === "exit_no") {
      exiting = op === "exit_ask"; draw(["exit"]);
    } else if (op === "exit_yes") {
      leave();
    }
  }

  function onInput(e) {
    const el = e.target, op = el.dataset && el.dataset.op;
    if (op === "bg_secs" || op === "bg_dim") {
      put(op === "bg_secs" ? KEY_SECS : KEY_DIM, el.value);
      applyBg();
      const out = el.parentElement.querySelector("output");
      if (out) out.innerHTML = op === "bg_secs" ? tx("opt.secs", "{n} s", { n: el.value }) : tx("opt.pct", "{n}%", { n: el.value });
      if (e.type === "change") draw(["screen"]);
    } else if (op === "family" && e.type === "change") {
      put(KEY_FAMILY, el.checked ? "1" : null);
      setTimeout(() => location.reload(), 350);
    }
  }

  function onSubmit(e) {
    const form = e.target.closest("form[data-op=house]");
    if (!form) return;
    e.preventDefault();
    const name = form.elements.name.value.trim();
    const color = form.elements.color ? form.elements.color.value : "";
    if (document.activeElement) document.activeElement.blur();
    send({ op: "house", name, color }).then(res => { if (res && res.ok) load(); });
  }

  function open() {
    if (dlg) return;
    exiting = false;
    dlg = document.createElement("dialog");
    dlg.className = "op";
    dlg.setAttribute("aria-labelledby", "op-title");
    dlg.innerHTML = `<div class="op-card">
      <header class="op-head"><div><p class="op-eyebrow">${tx("opt.eyebrow", "The Captain's Options")}</p>
        <h2 id="op-title">${esc((S && S.me && (S.me.firm || S.me.name)) || "")}</h2></div>
        <button type="button" class="op-x" data-op="close" aria-label="${tx("opt.close", "Close")}">&times;</button></header>
      <div class="op-body">
        ${section("clock", tx("opt.clock", "The Voyage Clock"), "")}
        ${section("captain", tx("opt.captain", "My Captain"), "")}
        ${section("house", tx("opt.house", "My House"), "")}
        ${section("table", tx("opt.table", "Table settings"), "")}
        ${section("screen", tx("opt.screen", "This screen"), "")}
        ${section("exit", tx("opt.exit", "Exit Game"), "")}
      </div>
      <footer class="op-foot"><button type="button" class="primary" data-op="close">${tx("opt.close", "Close")} <span aria-hidden="true">&rarr;</span></button></footer>
    </div>`;
    dlg.addEventListener("click", e => { if (e.target === dlg) close(); else onClick(e); });
    dlg.addEventListener("input", onInput);
    dlg.addEventListener("change", onInput);
    dlg.addEventListener("submit", onSubmit);
    dlg.addEventListener("close", () => { if (dlg) close(); });
    document.body.appendChild(dlg);
    draw();
    dlg.showModal();
    load();
    timer = setInterval(() => {
      draw(["clock"]);
      const h2 = dlg && dlg.querySelector("#op-title");
      const firm = S && S.me && (S.me.firm || S.me.name);
      if (h2 && firm && h2.textContent !== firm) h2.textContent = firm;
    }, 1500);
  }

  function close() {
    clearInterval(timer); clearTimeout(poll);
    const d = dlg;
    dlg = null;
    if (d) { try { if (d.open) d.close(); } catch (e) { /* ignore */ } d.remove(); }
    if (typeof render === "function") render();
  }

  return { open, close, isOpen: () => !!dlg };
})();
