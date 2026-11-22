/* SeaTrader Admin: Captain's Report.
   Everything the game writes down (journal.py): a live console of the game in
   progress, a month-by-month review of any recorded game, the server's
   technical log, and the records kept on disk. Nothing here is part of
   "Save & apply"; it only reads, apart from Keep, Delete and the replay check. */
(function () {
  "use strict";

  const CATS = [
    ["players", "Players"], ["host", "Host"], ["trade", "Trade"], ["finance", "Money"], ["fleet", "Fleet"],
    ["orders", "Orders"], ["turn", "Month"], ["weather", "Weather"], ["voyage", "Voyage"], ["dice", "Dice"],
    ["battle", "Battle"], ["market", "Market"], ["news", "News"], ["snapshot", "Snapshot"], ["admin", "Admin"],
    ["settings", "Settings"], ["rejected", "Refused"], ["error", "Error"], ["system", "System"],
  ];
  const CAT_NAME = Object.fromEntries(CATS);
  const HIDE = new Set(["n", "t", "at", "turn", "cat", "type", "msg", "who", "pid", "firms", "prices", "traceback", "session", "level"]);
  const TABS = [["live", "Live console"], ["review", "Review a game"], ["server", "Server log"], ["records", "Records kept"]];

  const st = {
    tab: "live", games: [], stats: null, days: [], loaded: false,
    off: new Set(), pid: "", q: "", problems: false, open: new Set(),
    live: { events: [], last: 0, follow: true, more: false },
    rev: { game: "", index: null, turn: null, events: [], more: false, replay: {}, whole: null, busy: false },
    srv: { day: "", level: "INFO", q: "", lines: [], total: 0, open: new Set() },
    timer: null, seq: 0,
  };
  const $m = () => document.getElementById("main");
  const e = s => esc(s);
  const here = () => section === "report";

  async function getj(path) {
    try { return await (await fetch("/api/admin/journal/" + path)).json(); }
    catch (err) { return { ok: false, error: "Cannot reach the game server." }; }
  }
  async function postj(body) {
    try {
      const r = await fetch("/api/admin/journal", { method: "POST", headers: { "X-SeaTrader": "admin" }, body: JSON.stringify(body) });
      return await r.json();
    } catch (err) { return { ok: false, error: "Cannot reach the game server." }; }
  }
  const clock = t => new Date(t).toLocaleTimeString([], { hour12: false });
  const day = t => new Date(t).toLocaleDateString([], { weekday: "short", day: "numeric", month: "short" });
  const size = b => b > 1048576 ? (b / 1048576).toFixed(1) + " MB" : Math.max(1, Math.round(b / 1024)) + " KB";
  const cash = n => (n < 0 ? "-" : "") + CFG.brand.currency + Math.abs(Math.round(n)).toLocaleString("en-US");
  const pname = k => (CFG.ports[k] || {}).name || k;
  const gname = k => (CFG.goods[k] || {}).name || k;

  /* --------------------------------------------------------- loading -- */
  async function loadGames() {
    const res = await getj("games");
    if (!res.ok) return;
    st.games = res.games; st.stats = res.stats; st.days = res.days; st.loaded = true;
    if (!st.rev.game || !st.games.some(g => g.id === st.rev.game)) st.rev.game = (st.games[0] || {}).id || "";
  }
  async function pollLive() {
    const L = st.live;
    const first = !L.last;
    const res = await getj(first ? "events?tail=1&limit=400" : "events?after=" + L.last + "&limit=1500");
    if (!res.ok) return;
    if (res.game !== L.game) { L.events = []; L.last = 0; L.game = res.game; if (!first) return pollLive(); }
    if (res.events.length) {
      L.events = L.events.concat(res.events).slice(-1500);
      L.last = res.events[res.events.length - 1].n;
      if (first) L.more = res.more;
      if (here() && st.tab === "live") drawList();
    } else if (first && here() && st.tab === "live") drawList();
  }
  async function loadReview() {
    const R = st.rev, my = ++st.seq;
    if (!R.game) { R.events = []; R.index = null; return redraw(); }
    if (!R.index || R.index.game !== R.game) {
      const idx = await getj("index?game=" + encodeURIComponent(R.game));
      if (my !== st.seq) return;
      R.index = idx.ok ? idx : { game: R.game, turns: [], cats: {}, total: 0 };
      R.replay = {}; R.whole = null;
      const turns = R.index.turns;
      if (R.turn !== "all" && !turns.some(t => t.turn === R.turn)) R.turn = turns.length ? turns[turns.length - 1].turn : 0;
    }
    let path = "events?game=" + encodeURIComponent(R.game) + "&limit=2500";
    if (R.turn === "all") {
      const on = CATS.map(c => c[0]).filter(c => !st.off.has(c) && (!st.problems || c === "error" || c === "rejected"));
      if (st.off.size || st.problems) path += "&cat=" + on.join(",");
      if (st.pid) path += "&pid=" + encodeURIComponent(st.pid);
      if (st.q) path += "&q=" + encodeURIComponent(st.q);
    } else path += "&turn=" + R.turn;
    const res = await getj(path);
    if (my !== st.seq) return;
    R.events = res.ok ? res.events : [];
    R.more = !!res.more;
    if (here() && st.tab === "review") redraw();
  }
  async function loadServer() {
    const S = st.srv;
    const res = await getj("server?day=" + encodeURIComponent(S.day) + "&level=" + S.level + "&q=" + encodeURIComponent(S.q));
    if (!res.ok) return;
    S.lines = res.lines; S.total = res.total; S.day = res.day; st.days = res.days;
    if (here() && st.tab === "server") redraw();
  }
  async function refresh() {
    if (st.tab === "live") { st.live.last = 0; st.live.events = []; await pollLive(); }
    else if (st.tab === "review") { await loadGames(); st.rev.index = null; await loadReview(); }
    else if (st.tab === "server") await loadServer();
    else { await loadGames(); redraw(); }
  }
  function tick() {
    if (!here()) return leave();
    if (st.tab === "live") pollLive();
  }
  async function enter() {
    if (!st.timer) st.timer = setInterval(tick, 2000);
    if (!st.loaded) { await loadGames(); if (here()) redraw(); }
    if (st.tab === "live") pollLive();
    else if (st.tab === "review" && !st.rev.index) loadReview();
    else if (st.tab === "server" && !st.srv.lines.length) loadServer();
  }
  function leave() { clearInterval(st.timer); st.timer = null; }

  /* -------------------------------------------------------- rendering -- */
  function shown(ev) {
    if (st.off.has(ev.cat)) return false;
    if (st.problems && ev.cat !== "error" && ev.cat !== "rejected") return false;
    if (st.pid && ev.pid !== st.pid) return false;
    if (st.q && !(ev.msg + " " + ev.type).toLowerCase().includes(st.q.toLowerCase())) return false;
    return true;
  }
  function snapshot(ev) {
    const goods = Object.keys((ev.prices && ev.prices[Object.keys(ev.prices)[0]]) || {});
    const firms = (ev.firms || []).map(f => `<tr><td><b>${e(f.name)}</b><br><span class="muted">${e(f.firm)}</span></td><td>${e(pname(f.port))}</td>
        <td class="n">${cash(f.cash)}</td><td class="n">${cash(f.bank)}</td><td class="n">${cash(f.debt)}</td><td class="n"><b>${cash(f.worth)}</b></td>
        <td class="small">${f.ships.map(s => `${e(s.name)} (${e((CFG.ships[s.type] || {}).name || s.type)}, hull ${s.hull}, ${s.guns} guns)`).join("<br>")}</td>
        <td class="small">Hold ${f.used}/${f.hold}: ${e(Object.keys(f.cargo).map(g => f.cargo[g] + " " + gname(g)).join(", ") || "empty")}
          ${Object.keys(f.wh).length ? "<br>Warehouse: " + e(Object.keys(f.wh).map(g => f.wh[g] + " " + gname(g)).join(", ")) : ""}
          ${f.protect ? "<br>Protected " + f.protect + " mo" : ""}${f.wrecks ? "<br>Wrecks: " + f.wrecks : ""}</td></tr>`).join("");
    const prices = Object.keys(ev.prices || {}).map(port => `<tr><td><b>${e(pname(port))}</b>${ev.crackdown && ev.crackdown[port] ? ` <span class="err small">ban ${ev.crackdown[port]} mo</span>` : ""}</td>` +
      goods.map(g => {
        const sh = (ev.shocks || []).find(s => s.port === port && s.good === g);
        return `<td class="n ${sh ? (sh.mult > 1 ? "err" : "ok") : ""}" ${sh ? `title="${sh.mult > 1 ? "Shortage" : "Glut"} x${sh.mult}, ${sh.turns} more months"` : ""}>${Math.round(ev.prices[port][g]).toLocaleString("en-US")}</td>`;
      }).join("") + "</tr>").join("");
    return (firms ? `<div class="scroll"><table><thead><tr><th>House</th><th>Port</th><th class="n">Silver</th><th class="n">Bank</th><th class="n">Debt</th><th class="n">Net worth</th><th>Fleet</th><th>Cargo</th></tr></thead><tbody>${firms}</tbody></table></div>` : '<p class="muted">Nobody had joined yet.</p>') +
      `<div class="scroll" style="margin-top:.6rem"><table><thead><tr><th>Prices</th>${goods.map(g => `<th class="n">${e(gname(g))}</th>`).join("")}</tr></thead><tbody>${prices}</tbody></table></div>`;
  }
  function detail(ev) {
    const rows = Object.keys(ev).filter(k => !HIDE.has(k)).map(k => {
      const v = ev[k];
      return `<tr><td class="muted">${e(k)}</td><td class="mono">${e(typeof v === "object" ? JSON.stringify(v) : v)}</td></tr>`;
    }).join("");
    return `<div class="cr-d">${ev.firms ? snapshot(ev) : ""}${ev.traceback ? `<pre>${e(ev.traceback)}</pre>` : ""}
      <table class="cr-kv"><tbody><tr><td class="muted">when</td><td class="mono">${e(ev.at || "")} · event #${ev.n || ""} · ${e(ev.type || ev.level || "")}</td></tr>${rows}</tbody></table></div>`;
  }
  function rowHtml(ev, key, open) {
    const cat = ev.cat || "";
    return `<div class="cr-e c-${e(cat)}${open ? " on" : ""}" data-crrow="${key}" tabindex="0" role="button" aria-expanded="${open ? "true" : "false"}">
        <span class="t" title="${e(ev.at || "")}">${clock(ev.t)}</span><span class="n">${ev.n ? "#" + ev.n : e(ev.level || "")}</span>
        <span class="c">${e(CAT_NAME[cat] || cat)}</span><span class="m">${e(ev.msg)}</span></div>${open ? detail(ev) : ""}`;
  }
  function monthHead(turn, idx, withReplay) {
    const t = idx && idx.turns.find(x => x.turn === turn);
    const r = st.rev.replay[turn];
    let res = "";
    if (r === "busy") res = '<span class="muted">Replaying…</span>';
    else if (r) res = r.map(s => s.result === "same" ? `<span class="ok">Replays the same${s.note ? " (" + e(s.note.replace(/\.$/, "").toLowerCase()) + ")" : ""}</span>`
      : s.result === "different" ? `<span class="err">Replay differs:</span><ul class="cr-diff">${s.errors.concat(s.diffs).map(d => "<li>" + e(d) + "</li>").join("")}</ul>`
      : `<span class="muted">${e(s.note || s.result)}</span>`).join(" ");
    return `<div class="cr-month"><b>Month ${turn}${t && t.date ? " · " + e(t.date) : ""}</b>
      ${withReplay ? `<button type="button" class="link" data-crreplay="${turn}">Replay check</button>` : ""}<span class="res">${res}</span></div>`;
  }
  function listHtml(events, idx, withReplay) {
    let out = "", turn = null, n = 0;
    events.forEach(ev => {
      if (!shown(ev)) return;
      if (ev.turn !== turn) { turn = ev.turn; out += monthHead(turn, idx, withReplay); }
      out += rowHtml(ev, ev.n, st.open.has(ev.n));
      n++;
    });
    return { html: out || '<p class="muted" style="padding:.8rem">Nothing to show with these filters.</p>', n };
  }
  function drawList() {
    const box = document.getElementById("crlist");
    if (!box) return;
    const live = st.tab === "live";
    const res = listHtml(live ? st.live.events : st.rev.events, live ? null : st.rev.index, !live);
    const atEnd = box.scrollHeight - box.scrollTop - box.clientHeight < 40;
    box.innerHTML = res.html;
    const c = document.getElementById("crcount");
    if (c) c.textContent = res.n + " shown";
    if (live && st.live.follow && (atEnd || !box.dataset.seen)) box.scrollTop = box.scrollHeight;
    box.dataset.seen = "1";
  }
  function filters(players) {
    const chips = CATS.map(([id, label]) => `<button type="button" class="cr-chip c-${id}${st.off.has(id) ? "" : " on"}" data-crcat="${id}" aria-pressed="${st.off.has(id) ? "false" : "true"}">${label}</button>`).join("");
    return `<div class="cr-filters">
      <div class="row" style="margin-top:0"><input type="search" id="crq" placeholder="Search the report…" value="${e(st.q)}" style="flex:1 1 14rem">
        <select id="crpid"><option value="">Every player</option>${players.map(p => `<option value="${e(p.id)}" ${p.id === st.pid ? "selected" : ""}>${e(p.name)}</option>`).join("")}</select>
        <label class="cr-check"><input type="checkbox" id="crproblems" ${st.problems ? "checked" : ""}> Problems only</label>
        <span class="muted small" id="crcount"></span></div>
      <div class="cr-chips">${chips}<button type="button" class="link" data-crcats="all">all</button><button type="button" class="link" data-crcats="none">none</button><button type="button" class="link" data-crcats="quiet">hide dice and weather</button></div></div>`;
  }
  function liveTab() {
    const g = st.games.find(x => x.current) || {};
    return `<section class="card"><p class="help" style="margin-top:0">The game in progress as it happens. Click any line for its full details. ${st.live.more ? "Showing the newest 400 events; open Review a game for the rest." : ""}</p>
      ${filters(g.players || [])}
      <div class="cr-list cr-live" id="crlist"></div>
      <div class="row"><label class="cr-check"><input type="checkbox" id="crfollow" ${st.live.follow ? "checked" : ""}> Follow new events</label>
        <span class="muted small">Game ${e(g.id || "")}</span></div></section>`;
  }
  function gameLabel(g) {
    const who = (g.players || []).map(p => p.name).join(", ") || "no players";
    return `${new Date((g.started || 0) * 1000).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })} · ${who} · month ${g.turn || 0}${g.phase === "ended" ? " · finished" : g.current ? " · in progress" : ""}${g.current ? " · current game" : ""}`;
  }
  function reviewTab() {
    const R = st.rev, g = st.games.find(x => x.id === R.game);
    if (!st.games.length) return '<section class="card"><p class="muted">No games have been recorded yet.</p></section>';
    const turns = R.index ? R.index.turns : [];
    const pos = turns.findIndex(t => t.turn === R.turn);
    const whole = R.whole === "busy" ? '<span class="muted">Replaying every month…</span>' : R.whole
      ? (R.whole.error ? `<span class="err">${e(R.whole.error)}</span>` : `<span class="${R.whole.different ? "err" : "ok"}">${R.whole.checked} stretches replayed, ${R.whole.different} different${R.whole.different ? ": months " + [...new Set(R.whole.segments.filter(s => s.result === "different").map(s => s.turn))].join(", ") : ""}</span>`) : "";
    return `<section class="card">
      <div class="row" style="margin-top:0"><select id="crgame" style="flex:1 1 22rem">${st.games.map(x => `<option value="${e(x.id)}" ${x.id === R.game ? "selected" : ""}>${e(gameLabel(x))}</option>`).join("")}</select>
        <a href="/api/admin/journal/download?as=txt&game=${encodeURIComponent(R.game)}"><button type="button">Download as text</button></a>
        <a href="/api/admin/journal/download?game=${encodeURIComponent(R.game)}"><button type="button">Download raw journal</button></a>
        <button type="button" data-crcert="1" title="Open this game in the Certificate Studio">Make a certificate</button></div>
      <div class="row"><button type="button" data-crstep="-1" ${pos <= 0 ? "disabled" : ""} aria-label="Previous month">◀</button>
        <select id="crturn">${turns.map(t => `<option value="${t.turn}" ${t.turn === R.turn ? "selected" : ""}>Month ${t.turn}${t.date ? " · " + e(t.date) : ""} (${t.count} events${t.problems ? ", " + t.problems + " problems" : ""})</option>`).join("")}
          <option value="all" ${R.turn === "all" ? "selected" : ""}>Every month (${R.index ? R.index.total : 0} events)</option></select>
        <button type="button" data-crstep="1" ${pos < 0 || pos >= turns.length - 1 ? "disabled" : ""} aria-label="Next month">▶</button>
        <button type="button" data-crwhole="1">Replay-check the whole game</button><span class="small">${whole}</span></div>
      ${g && g.standings && g.standings.length ? `<p class="small muted">Final standings: ${g.standings.map((s, i) => `${i + 1}. ${e(s.name)} ${cash(s.worth)}`).join(" · ")}</p>` : ""}
      ${filters(g ? g.players || [] : [])}
      ${R.more ? '<p class="warn small">Showing the first 2,500 matching events. Narrow the filters or pick a single month to see the rest.</p>' : ""}
      <div class="cr-list" id="crlist"></div>
      <p class="help">A replay check plays the month again from its snapshot with the recorded dice and actions, and compares the outcome. After a change to the rules, a difference shows what the change would have done.</p></section>`;
  }
  function serverTab() {
    const S = st.srv;
    const lines = S.lines.length ? S.lines.map((l, i) => rowHtml({ t: l.t, at: l.at, level: l.level, cat: l.cat, msg: l.msg, traceback: l.traceback, ...l, n: 0 }, "s" + i, S.open.has(i))
      .replace('class="cr-e ', `class="cr-e lv-${l.level} `)).join("") : '<p class="muted" style="padding:.8rem">Nothing logged for this day at this level.</p>';
    return `<section class="card"><p class="help" style="margin-top:0">The technical log: start-ups and shutdowns, errors with full detail, sign-ins, voice requests and font downloads. One file per day.</p>
      <div class="row" style="margin-top:0"><select id="crday">${(st.days.length ? st.days : [{ day: S.day }]).map(d => `<option value="${e(d.day)}" ${d.day === S.day ? "selected" : ""}>${e(d.day)}${d.size ? " (" + size(d.size) + ")" : ""}</option>`).join("")}</select>
        <select id="crlevel">${[["DEBUG", "Everything"], ["INFO", "Normal and above"], ["WARN", "Warnings and errors"], ["ERROR", "Errors only"]].map(([v, l]) => `<option value="${v}" ${v === S.level ? "selected" : ""}>${l}</option>`).join("")}</select>
        <input type="search" id="crsq" placeholder="Search this day…" value="${e(S.q)}" style="flex:1 1 14rem">
        <span class="muted small">${S.total} lines${S.total > S.lines.length ? ", newest " + S.lines.length + " shown" : ""}</span></div>
      <div class="cr-list" id="crslist">${lines}</div></section>`;
  }
  function recordsTab() {
    const s = st.stats || {};
    const rows = st.games.map(g => `<tr><td><b>${e(new Date((g.started || 0) * 1000).toLocaleString([], { dateStyle: "medium", timeStyle: "short" }))}</b><br><span class="mono muted">${e(g.id)}</span></td>
        <td>${e((g.players || []).map(p => p.name).join(", ") || "no players")}</td>
        <td>${g.phase === "ended" ? "finished" : g.current ? '<span class="ok">in progress</span>' : "set aside"}, month ${g.turn || 0}${g.current ? ' <span class="muted">(current game)</span>' : ""}</td>
        <td class="n">${(g.events || 0).toLocaleString("en-US")}</td><td class="n">${size(g.size || 0)}</td>
        <td>${g.errors ? `<span class="err">${g.errors} errors</span>` : ""}</td>
        <td class="n"><label class="cr-check"><input type="checkbox" data-crkeep="${e(g.id)}" ${g.keep ? "checked" : ""}> Keep</label>
          <button type="button" data-cropen="${e(g.id)}">Review</button>
          ${g.current ? "" : `<button type="button" class="danger" data-crdel="${e(g.id)}">Delete</button>`}</td></tr>`).join("");
    return `<section class="card"><h2>Game journals</h2>
      <p class="help" style="margin-top:0">One journal per game, kept until deleted. ${s.keep_games ? `When there are more than <b>${s.keep_games}</b>, the oldest are removed, except the game in progress and any marked Keep.` : "None are ever removed automatically."}
        Change the limits under <b>Game Setup → Records</b>.</p>
      <div class="scroll"><table><thead><tr><th>Started</th><th>Players</th><th>Status</th><th class="n">Events</th><th class="n">Size</th><th></th><th></th></tr></thead>
        <tbody>${rows || '<tr><td colspan="7" class="muted">None yet.</td></tr>'}</tbody></table></div></section>
      <section class="card"><h2>Server log</h2><p class="help" style="margin-top:0">One file per day. ${s.server_days ? `Files older than <b>${s.server_days} days</b> are deleted.` : "Files are never deleted automatically."}</p>
        <p>${st.days.length} day${st.days.length === 1 ? "" : "s"} on file${st.days.length ? ", from " + e(st.days[st.days.length - 1].day) + " to " + e(st.days[0].day) : ""}.</p>
        <div class="row"><button type="button" data-crprune="1">Remove records past their keep-by date now</button></div></section>
      <section class="card"><h2>Where it is kept</h2><table><tbody>
        <tr><td class="muted">Folder</td><td class="mono">${e(s.folder || "")}</td></tr>
        <tr><td class="muted">Size on disk</td><td>${size(s.bytes || 0)}</td></tr>
        <tr><td class="muted">This run of the server</td><td class="mono">${e(s.session || "")}</td></tr></tbody></table>
        <p class="help">The files are plain text. Copy the <code>journal</code> folder along with <code>saves</code> to take the records to another machine. From a terminal, <code>python replay.py</code> runs the replay check without the Admin page.</p></section>`;
  }
  function render() {
    const tabs = TABS.map(([id, label]) => `<button type="button" class="cr-tab${st.tab === id ? " on" : ""}" data-crtab="${id}" role="tab" aria-selected="${st.tab === id}">${label}</button>`).join("");
    const body = st.tab === "live" ? liveTab() : st.tab === "review" ? reviewTab() : st.tab === "server" ? serverTab() : recordsTab();
    return head("Captain's Report", "Everything that happens is written down: every action, every roll of the dice with its odds, every month's standings, every admin change and every error. Read it live, review any game month by month, and replay a month to check it.",
        '<button type="button" data-crrefresh="1">Refresh</button>') +
      `<div class="cr-tabs" role="tablist">${tabs}</div>${body}`;
  }
  function redraw() {
    if (!here()) return;
    const q = document.activeElement && document.activeElement.id;
    const pos = q && document.activeElement.selectionStart;
    $m().innerHTML = render();
    drawList();
    if (q && document.getElementById(q)) {
      const el = document.getElementById(q);
      el.focus();
      if (pos != null && el.setSelectionRange) { try { el.setSelectionRange(pos, pos); } catch (err) { /* not a text field */ } }
    }
  }

  /* ----------------------------------------------------------- events -- */
  let typing = null;
  function later(fn) { clearTimeout(typing); typing = setTimeout(fn, 250); }
  function filtersChanged() {
    if (st.tab === "review" && st.rev.turn === "all") loadReview(); else drawList();
  }
  function onInput(ev) {
    if (!here()) return;
    const el = ev.target;
    if (el.id === "crq") { st.q = el.value; return later(filtersChanged); }
    if (el.id === "crsq") { st.srv.q = el.value; return later(loadServer); }
    if (ev.type !== "change") return;
    if (el.id === "crpid") { st.pid = el.value; return filtersChanged(); }
    if (el.id === "crproblems") { st.problems = el.checked; return filtersChanged(); }
    if (el.id === "crfollow") { st.live.follow = el.checked; if (el.checked) { const b = document.getElementById("crlist"); b.scrollTop = b.scrollHeight; } return; }
    if (el.id === "crgame") { st.rev.game = el.value; st.rev.index = null; st.rev.turn = null; st.pid = ""; st.open.clear(); return loadReview(); }
    if (el.id === "crturn") { st.rev.turn = el.value === "all" ? "all" : Number(el.value); st.open.clear(); return loadReview(); }
    if (el.id === "crday") { st.srv.day = el.value; st.srv.open.clear(); return loadServer(); }
    if (el.id === "crlevel") { st.srv.level = el.value; st.srv.open.clear(); return loadServer(); }
    if (el.dataset.crkeep) return postj({ op: "keep", game: el.dataset.crkeep, keep: el.checked }).then(res => { toast(res.ok ? res.msg : res.error, !res.ok); loadGames(); });
  }
  function toggleRow(row) {
    const key = row.dataset.crrow;
    if (key[0] === "s") {
      const i = Number(key.slice(1));
      st.srv.open.has(i) ? st.srv.open.delete(i) : st.srv.open.add(i);
      return redraw();
    }
    const n = Number(key);
    st.open.has(n) ? st.open.delete(n) : st.open.add(n);
    const box = document.getElementById("crlist"), top = box.scrollTop;
    drawList();
    box.scrollTop = top;
  }
  async function onClick(ev) {
    if (!here()) return;
    const row = ev.target.closest("[data-crrow]");
    if (row && !ev.target.closest(".cr-d")) return toggleRow(row);
    const el = ev.target.closest("button");
    if (!el || el.disabled) return;
    const d = el.dataset;
    if (d.crtab) { st.tab = d.crtab; redraw(); return enter(); }
    if (d.crrefresh) { await refresh(); return toast("Refreshed."); }
    if (d.crcat) { st.off.has(d.crcat) ? st.off.delete(d.crcat) : st.off.add(d.crcat); el.classList.toggle("on"); el.setAttribute("aria-pressed", !st.off.has(d.crcat)); return filtersChanged(); }
    if (d.crcats) {
      st.off = new Set(d.crcats === "all" ? [] : d.crcats === "none" ? CATS.map(c => c[0]) : ["dice", "weather"]);
      redraw();
      return filtersChanged();
    }
    if (d.crstep) {
      const turns = st.rev.index.turns, pos = turns.findIndex(t => t.turn === st.rev.turn) + Number(d.crstep);
      if (turns[pos]) { st.rev.turn = turns[pos].turn; st.open.clear(); loadReview(); }
      return;
    }
    if (d.crreplay !== undefined) {
      const turn = Number(d.crreplay);
      st.rev.replay[turn] = "busy"; drawList();
      const res = await postj({ op: "replay", game: st.rev.game, turn });
      st.rev.replay[turn] = res.ok ? (res.replay.segments.length ? res.replay.segments : [{ result: "open", note: res.replay.error || "No snapshot to replay from." }])
        : [{ result: "open", note: res.error }];
      return drawList();
    }
    if (d.crcert) { window.CertStudioGame = st.rev.game; return go("certificate"); }
    if (d.crwhole) {
      st.rev.whole = "busy"; redraw();
      const res = await postj({ op: "replay", game: st.rev.game });
      st.rev.whole = res.ok ? res.replay : { error: res.error };
      if (res.ok) {
        st.rev.replay = {};
        res.replay.segments.forEach(s => { (st.rev.replay[s.turn] = st.rev.replay[s.turn] || []).push(s); });
      }
      return redraw();
    }
    if (d.cropen) { st.tab = "review"; st.rev.game = d.cropen; st.rev.index = null; st.rev.turn = null; redraw(); return loadReview(); }
    if (d.crdel) {
      if (!d.armed) {
        d.armed = "1"; d.label = el.textContent; el.textContent = "Click again to delete";
        setTimeout(() => { if (el.isConnected && d.armed) { delete d.armed; el.textContent = d.label; } }, 3500);
        return;
      }
      const res = await postj({ op: "delete", game: d.crdel });
      toast(res.ok ? res.msg : res.error, !res.ok);
      await loadGames();
      return redraw();
    }
    if (d.crprune) {
      const res = await postj({ op: "prune" });
      toast(res.ok ? res.msg : res.error, !res.ok);
      await loadGames();
      return redraw();
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    const m = $m();
    m.addEventListener("input", onInput);
    m.addEventListener("change", onInput);
    m.addEventListener("click", onClick);
    m.addEventListener("keydown", ev => {
      const row = ev.target.closest && ev.target.closest("[data-crrow]");
      if (row && ev.target === row && (ev.key === "Enter" || ev.key === " ")) { ev.preventDefault(); toggleRow(row); }
    });
  });

  window.SeaTraderReport = { render, enter, leave };
})();
