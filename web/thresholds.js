"use strict";

const Thresholds = (() => {
  let catalog = null, cast = {}, captains = [], version, busy = false, failed = false;
  let book = null, game, bookBusy = false, bookFailed = false;
  const active = () => S && (!S.me || S.phase === "lobby" || S.phase === "ended");
  function redraw() { if (active()) render(); }
  function ensure() {
    if (version !== S.cfg) {
      version = S.cfg; catalog = null; cast = {}; captains = []; failed = false;
    }
    if (busy || catalog || failed) return;
    busy = true;
    const requested = version;
    Promise.all([fetch("/api/info?family=1"), fetch("/api/captains")]).then(async responses => {
      if (responses.some(r => !r.ok)) throw new Error("Public screen catalog request failed");
      const [info, list] = await Promise.all(responses.map(r => r.json()));
      if (!info.ok || !info.media?.family || !list.ok) throw new Error("Clean public artwork catalog unavailable");
      if (S.cfg !== requested) return;
      catalog = info.media; cast = info.voice?.cast || {}; captains = list.captains || [];
    }).catch(error => {
      if (S.cfg === requested) failed = true;
      console.error("Public screen artwork:", error);
    }).finally(() => { busy = false; redraw(); });
  }
  function items(kind, subject) { return (catalog?.items?.[kind]?.[subject] || []).filter(i => i.t === "image"); }
  function clean(url) {
    if (!url || !catalog) return "";
    return Object.values(catalog.items).some(subjects => Object.values(subjects).some(list => list.some(i => i.t === "image" && i.u === url))) ? url : "";
  }
  function picture(kind, subject) {
    const list = items(kind, subject);
    return (list.find(i => i.g?.includes("clean") && i.r?.includes("portrait")) || list.find(i => i.r?.includes("portrait")) || list[0])?.u || "";
  }
  function image(url, name, cls = "") {
    const safe = clean(url);
    return safe ? `<img class="${esc(cls)}" src="${esc(safe)}" alt="${esc(name)}">`
      : `<span class="art-placeholder ${esc(cls)}" role="img" aria-label="${esc(name)}">${esc(capInitials(name))}</span>`;
  }
  function faces(p) {
    const c = captains.find(c => c.name.toLowerCase() === String(p.name).toLowerCase());
    const h = c?.houses?.find(h => h.name.toLowerCase() === String(p.firm).toLowerCase());
    return { portrait: clean(p.portrait) || (h && clean(c.portrait)) || "", crest: clean(p.crest) || clean(h?.image) };
  }
  function roster() {
    if (!S.players.length) return `<p class="muted">${te("join.none")}</p>`;
    return `<ul class="roster">${S.players.map(p => `<li>${image(faces(p).portrait, p.name)}<span><b>${esc(p.firm)}</b><small>${esc(p.name)}${p.host ? " · " + te("w.host") : ""}</small></span><span class="state">${te(p.present ? "threshold.connected" : "w.away")}</span></li>`).join("")}</ul>`;
  }
  function persona(id, quote) {
    const c = cast[id] || VS.cast?.[id] || {};
    return `<aside class="persona">${image(picture("persona", id), c.name || t("threshold.host"))}<div class="persona-copy"><div class="eyebrow">${esc(c.title || "")}</div><h2>${esc(c.name || "")}</h2><p>${te(quote)}</p></div></aside>`;
  }
  function shell(kind, id, quote, content, status) {
    ensure();
    const logo = D.graphics?.favicon || "/assets/branding/taipan-trader-mark.svg";
    const background = D.graphics?.page_bg || "/assets/ceremony-harbor.png";
    const utilities = `<footer class="footer"><span>${th("join.url", {url: "<b>" + esc(S.join_url) + "</b>"})}</span><a href="/board" target="_blank" rel="noopener">${te("threshold.board")}</a></footer>`;
    const notice = failed ? `<p class="note" role="status">${te("threshold.art_failed")} ${btn(te("threshold.retry"), "threshold_retry")}</p>` : "";
    return `<div class="threshold ${kind}"${background ? ` style="--threshold-bg:url('${esc(background)}')"` : ""}><div class="shell"><header class="brand"><div class="brand-left"><img src="${esc(logo)}" alt=""><div><div class="wordmark">${esc(brandName(D.brand))}</div><div class="caption">${esc(D.brand.tagline)}</div></div></div><span class="pill">${status}</span></header><main class="stage">${persona(id, quote)}<section class="work">${notice}${content}</section></main>${utilities}</div></div>`;
  }
  function join() {
    const late = S.phase === "port" ? `<p class="note">${te("join.late")}</p>` : S.phase === "ended" ? `<p class="note">${te("join.over")}</p>` : "";
    const typed = CAPS?.typed ? `<details class="howto cap-typed"${!CAPS.captains.length ? " open" : ""}><summary>${te("join.typed")}</summary><label>${te("join.name")}${input("name", t("join.name_ph"), 'maxlength="20"')}</label><label>${te("join.firm")}${input("firm", t("join.firm_ph"), 'maxlength="28"')}</label>${btn(te("join.button"), "join", "", "primary")}</details>` : "";
    return shell("threshold-join", "taxlady", "threshold.registrar_line", `<div class="eyebrow">${te("threshold.register")}</div><h1>${te(ui.capSel ? "join.captain_button" : "join.captain_title")}</h1>${late}${captainPicker()}${typed}<div class="support"><div class="support-title">${te("join.houses")}</div>${roster()}</div>`, te("threshold.registration"));
  }
  function lobby() {
    const host = S.me.host;
    const lengths = D.lengths.map(y => `<button type="button" data-act="years" data-y="${y}" aria-pressed="${S.years === y}" class="${S.years === y ? "on" : ""}"${!host || S.start_at ? " disabled" : ""}><b>${te(y === 1 ? "lobby.year" : "lobby.years", {n:y})}</b><small>${te("threshold.months", {n:y*12})}</small></button>`).join("");
    return shell("threshold-lobby", "gamemaster", "threshold.anahit_line", `<div class="eyebrow">${te("threshold.new_voyage")}</div><h1>${te(host ? "threshold.terms" : "lobby.wait_title")}</h1><p class="intro">${te(host ? "threshold.prepare" : "lobby.wait", {years:S.years})}</p><div class="columns"><div><h2>${te("lobby.length")}</h2><div class="lengths">${lengths}</div></div><div><h2>${te("join.houses")}</h2>${roster()}</div></div><div class="summary"><div><span>${te("threshold.duration")}</span><b>${te("threshold.months", {n:S.years*12})}</b></div><div><span>${te("threshold.difficulty")}</span><b>${esc(D.difficulty || "—")}</b></div><div><span>${te("threshold.victory")}</span><b>${te("threshold.net_worth")}</b></div></div><details class="howto"><summary>${te("threshold.month_help")}</summary><p>${te("threshold.month_rules")}</p></details><div class="actionbar">${btn(te("threshold.tally"), "tally", "", "ghost")}${host ? btn(te("threshold.open"), "start", "", "primary", !!S.start_at) : `<span class="pill">${te("lobby.wait_title")}</span>`}</div>`, te(host ? "lobby.host_title" : "threshold.guest"));
  }
  function loadBook() {
    if (game !== S.game_id) { game = S.game_id; book = null; bookFailed = false; bookBusy = false; }
    if (!game || book || bookBusy || bookFailed) return;
    const requested = game;
    bookBusy = true;
    fetch("/api/finale").then(r => { if (!r.ok) throw new Error("Voyage summary request failed"); return r.json(); }).then(r => {
      if (game !== requested || S.game_id !== requested) return;
      if (r.ok && r.game === requested && Array.isArray(r.houses)) book = r;
      else bookFailed = true;
    }).catch(error => { if (game === requested) bookFailed = true; console.error("Voyage summary:", error); }).finally(() => { if (game === requested) { bookBusy = false; redraw(); } });
  }
  function end() {
    loadBook();
    const order = S.players.slice().sort((a,b) => b.worth-a.worth), top = order[0];
    if (!top) return shell("threshold-end", "bookkeeper", "threshold.celeste_line", `<h1>${te("threshold.closed")}</h1>`, te("threshold.complete"));
    const ties = order.filter(p => p.worth === top.worth);
    const own = book?.houses?.find(h => h.id === S.me.id);
    const winner = ties.length > 1 ? te("threshold.tied", {houses:ties.map(p=>p.firm).join(" & ")}) : te("end.title", {name:top.name,firm:top.firm});
    let place = 0;
    const rows = order.map((p,i) => { if (!i || p.worth !== order[i-1].worth) place=i+1; return `<li><span class="place">${place}</span>${image(faces(p).crest,p.firm,"crest")}<span>${esc(p.firm)}<small>${esc(p.name)}${p.id === S.me.id ? " · "+te("race.you") : ""}</small></span><strong class="worth${p.worth < 0 ? " down" : ""}">${money(p.worth)}</strong></li>`; }).join("");
    const metrics = own ? `<div class="end-stats"><div><b>${esc(own.voyages)}</b><span>${te("fin.f.passages")}</span></div><div><b>${esc(own.won)}</b><span>${te("fin.f.battles")}</span></div>${own.best_sale ? `<div><b>${money(own.best_sale.profit)}</b><span>${te("threshold.best_profit")}</span></div>` : `<div><b>${esc(own.trades)}</b><span>${te("fin.f.trades")}</span></div>`}</div>` : `<p class="caption">${te(bookBusy ? "threshold.summary_loading" : "threshold.summary_missing")}${bookFailed ? " " + btn(te("threshold.retry"), "threshold_book_retry", "", "ghost") : ""}</p>`;
    const honours = (book?.honours || []).filter(h => h.id === S.me.id).map(h => `<span>${te("fin.h."+h.key)}</span>`).join(" · ");
    return shell("threshold-end", "bookkeeper", "threshold.celeste_line", `<div class="eyebrow">${te("end.sub", {date:S.date})}</div><p class="winner">${winner}</p><div class="end-columns"><div><div class="end-head">${image(faces(S.me).portrait,S.me.name)}<div><div class="caption">${esc(S.me.name)}</div><h1>${esc(S.me.firm)}</h1><div class="sub">${esc(S.me.rank)}</div></div></div><div class="fortune"><small>${te("threshold.final_worth")}</small>${money(S.me.worth)}</div>${metrics}${honours ? `<div class="honour">${te("fin.honours")} · ${honours}</div>` : ""}</div><div><h2>${te("threshold.standings")}</h2><ol class="standings">${rows}</ol>${btn(te("threshold.ledger"), "ledger", "", "ghost")}${S.voyage_story ? `<details class="howto"><summary>${te("threshold.highlights")}</summary>${Ceremony.story(S,D.ports)}</details>` : ""}</div></div><div class="support buttons">${typeof Certificate !== "undefined" ? btn(te("threshold.certificate"), "certificate") : ""}${btn(te("threshold.tally"), "tally", "", "ghost")}</div><div class="actionbar"><p>${te("end.free_play_note")}</p><div class="buttons">${btn(te("end.free_play"), "free_play")}${newGameControl(te("threshold.new_voyage")) || `<span class="caption">${te("end.host_can")}</span>`}</div></div>`, te("threshold.complete"));
  }
  function retry() { failed = false; ensure(); redraw(); }
  function retryBook() { bookFailed = false; loadBook(); redraw(); }
  /* Her own panel shows who is talking, since the floating speaker card is hidden on these screens. */
  if (typeof Voice !== "undefined" && Voice.onChange) Voice.onChange(item => document.querySelectorAll(".threshold .persona").forEach(p => p.classList.toggle("speaking", !!item)));
  return {join,lobby,end,clean,retry,retryBook};
})();
