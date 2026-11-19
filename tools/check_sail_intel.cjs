"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
const root = path.resolve(__dirname, "..");

async function check() {
  const clicks = {}, requests = [];
  const context = vm.createContext({
    console: { error() {} }, queueMicrotask,
    document: { fonts: null, querySelector: () => null, addEventListener: (name, fn) => { clicks[name] = fn; } },
    window: { matchMedia: () => ({ matches: false }) }, COLORS: [],
    esc: s => String(s ?? "").replaceAll("&", "&amp;").replaceAll('"', "&quot;").replaceAll("<", "&lt;"),
    te: s => s, CUR: "$", money: n => (n < 0 ? "-" : "") + "$" + Math.abs(Math.round(n)),
    hotGone: tp => tp.over != null && tp.over <= 10,
    pirateRisk: () => .25, tradeRun: () => null, token: "private seat",
    D: { ports: { a: { name: "A", x: 100, y: 200, region: "sea" }, b: { name: "B", x: 600, y: 200, region: "sea" } },
      goods: { tea: { name: "Tea" } }, regions: {}, graphics: {}, weather: ["Calm"] },
    S: { game_id: "one", turn: 10, weather: {}, crackdown: [], bans: {}, players: [], me: {
      id: "me", port: "a", rep: { a: 30, b: -10 }, shares: { total: 10, mine: { b: 3 } },
      hot_tips: [{ port: "b", good: "tea", lands: 11, ends: 13 }], books: {}, cargo: {} } }, ui: { dest: "b" },
    fetch: (url, options) => new Promise(resolve => requests.push({ url, options, resolve }))
  });
  vm.runInContext(fs.readFileSync(path.join(root, "web/chart.js"), "utf8"), context);
  vm.runInContext(fs.readFileSync(path.join(root, "web/sail-intel.js"), "utf8"), context);
  const draw = () => vm.runInContext("SailIntel.html(ui.dest)", context);
  const tick = () => new Promise(resolve => setImmediate(resolve));
  const lens = value => clicks.click({ target: { closest: () => ({ dataset: { intelLens: value } }) } });
  let html = draw();
  assert.match(html, /Loading your port record/);
  assert.match(html, /HOT TIP/);
  await tick();
  assert.equal(requests.length, 1);
  assert.match(requests[0].url, /token=private%20seat/);
  assert.equal(requests[0].options.cache, "no-store");
  requests[0].resolve({ ok: true, json: async () => ({ ok: true, voyage: { me: { ports: [
    { port: "a", visits: 4, profit: 2000 }, { port: "b", visits: 2, profit: -500 }
  ] } } }) });
  await tick();
  html = draw();
  assert.match(html, /stroke-dasharray="50.0 100"/);
  assert.match(html, /Trading P\/L/);
  assert.match(html, /-\$500/);
  lens("profit"); html = draw();
  assert.match(html, /intel-arc negative/);
  assert.match(html, /intel-arc positive/);
  assert.match(html, /stroke-dasharray="25.0 100"/);
  lens("shares"); html = draw();
  assert.match(html, /stroke-dasharray="30.0 100"/);
  assert.match(html, /3 \/ 10/);
  lens("standing"); html = draw();
  assert.match(html, /stroke-dasharray="10.0 100"/);
  lens("risk"); html = draw();
  assert.match(html, /25%/);
  assert.match(html, /role="button" tabindex="0"/);
  vm.runInContext("S.me.ready = true; S.me.dest = 'b'", context);
  assert.doesNotMatch(draw(), /data-act="dest"/);
  vm.runInContext("S.game_id = 'two'; S.me.books = { changed: true }", context);
  lens("visits"); html = draw();
  assert.match(html, /Loading your port record/);
  assert.doesNotMatch(html, /stroke-dasharray="50.0 100"/);
  await tick();
  requests[1].resolve({ ok: false, status: 503 });
  await tick();
  assert.match(draw(), /Port history unavailable/);
  lens("shares"); assert.match(draw(), /stroke-dasharray="30.0 100"/);
  console.log("PASS: loading, authenticated history, ring scales, signed P/L, hot tips, ready state, game isolation and history failure.");
}
check().catch(e => { console.error(e); process.exitCode = 1; });
