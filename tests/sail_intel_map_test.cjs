"use strict";

const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const root = path.join(__dirname, "..");
const chartSource = fs.readFileSync(path.join(root, "web", "chart.js"), "utf8");
const intelSource = fs.readFileSync(path.join(root, "web", "sail-intel.js"), "utf8");
const intelCss = fs.readFileSync(path.join(root, "web", "sail-intel.css"), "utf8");

const context = {
  COLORS: ["#fff"],
  esc: value => String(value),
  te: key => key,
  document: { addEventListener() {}, fonts: null },
  window: { matchMedia: () => ({ matches: false }) },
};
vm.createContext(context);
vm.runInContext(chartSource + "\nthis.ChartRef = Chart;", context);

const ring = fill => ({ fill, negative: false });
const data = {
  ports: {
    home: { name: "Home", x: 500, y: 300, region: "sea" },
    away: { name: "Away", x: 760, y: 180, region: "sea", label_left: true },
  },
  regions: {}, graphics: {}, weather: ["Calm"],
};
const intel = {
  home: { title: "Home metrics", value: "4 arrivals", rings: { visits: ring(.4), profit: ring(.7), shares: ring(.2), standing: ring(1) }, risk: null, riskTier: 0, opportunity: 0, hot: false },
  away: { title: "Away metrics", value: "8 arrivals", rings: { visits: ring(.8), profit: ring(.3), shares: ring(.1), standing: ring(.6) }, risk: .25, riskTier: 2, opportunity: .5, hot: true },
};
const html = context.ChartRef.svg({ data, players: [], weather: {}, crackdown: [], here: "home", dest: "away", clickable: true, intel, intelRoutes: true, focusPort: "home", focusScale: .82, hideRose: true });

assert.match(html, /class="intel-route risk-2 selected"/);
assert.match(html, /class="intel-heat"/);
assert.match(html, /class="intel-arc intel-visits/);
assert.match(html, /class="intel-arc intel-profit/);
assert.match(html, /class="intel-arc intel-shares/);
assert.match(html, /class="intel-arc intel-standing/);
assert.match(html, /class="intel-risk risk-2"/);
assert.doesNotMatch(html, /viewBox="0 0 1000 600"/);
assert.doesNotMatch(intelSource, /data-intel-lens|si-detail/);
assert.match(intelSource, /intelRoutes: true/);
assert.match(intelSource, /class="si-summary"/);
assert.match(intelSource, /focus === S\.me\.port \? summary/);
assert.doesNotMatch(intelSource, /si-controls|data-intel-zoom/);
assert.match(intelCss, /\.si-stage/);
assert.doesNotMatch(intelCss, /\.si-detail/);
assert.doesNotMatch(intelCss, /\.si-controls/);

console.log("PASS map-only Captain's Chart with simultaneous rings, routes, heat, focus and in-map summary");
