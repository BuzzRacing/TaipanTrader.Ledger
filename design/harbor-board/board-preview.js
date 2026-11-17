"use strict";

const board = document.querySelector("#board");
const scene = document.querySelector("#scene");
const gazette = document.body.classList.contains("gazette");
const houseFixtures = [
  ["Jade Compass", "Mei Lin", "hongkong", 48720, "Merchant", "Orders in", 2],
  ["Red Lantern", "Eleanor Shaw", "shanghai", 34560, "Merchant", "In port", 0],
  ["Salt & Silk", "Rafael Santos", "manila", 28140, "Trader", "Orders in", 1],
  ["Golden Wake", "Sofia Rao", "singapore", 19380, "Trader", "In port", 3],
  ["White Crane", "Isabel Chan", "hongkong", 15200, "Trader", "In port", 4],
  ["Southern Star", "Amara Fernando", "calcutta", 12160, "Trader", "Orders in", 5],
  ["Pearl River", "Daniel Lam", "hongkong", 9700, "Trader", "Orders in", 6],
  ["Eastern Wind", "Hana Mori", "nagasaki", -240, "Peddler", "Away", 7],
];
const news = [
  "Shanghai customs have banned opium and gold.",
  "A typhoon is forecast for the Yellow Sea and waters off Japan.",
  "Tea prices rise in Singapore.",
];
const weather = { north: 3, china: 2, south: 1, bengal: 0 };
const bans = { shanghai: ["Opium", "Gold"], manila: ["Opium"] };

function render() {
  const mode = scene.value;
  const lobby = mode === "lobby", ended = mode === "ended", sea = mode === "sea";
  const houses = houseFixtures.slice(0, mode === "full" ? 8 : 4);
  const ready = houses.filter(house => house[5] === "Orders in").length;
  const present = houses.filter(house => house[5] !== "Away").length;
  const heading = lobby ? "The harbor is open" : ended ? "Jade Compass wins the voyage"
    : sea ? "Two houses are under attack" : `${ready} of ${present} houses ready to sail`;
  const detail = lobby ? "Join on your device. The host starts the voyage." : ended ? "Mei Lin earns the title of Taipan."
    : sea ? "The month advances after both encounters resolve."
    : "Waiting on " + houses.filter(house => house[5] === "In port").map(house => house[1]).join(", ");
  const chartHouses = houses.map(([firm, , port, , , status, color], id) =>
    ({ firm, port, color, id, ready: !lobby && !ended && status === "Orders in" }));
  const map = `<section class="panel map">
    <header class="section-head"><h2>Sea chart</h2><span>Flags show last known port</span></header>
    <div class="chart-frame">${Chart.svg({data: chartData, players: chartHouses, weather: lobby ? {} : weather, crackdown: lobby ? [] : Object.keys(bans)})}</div>
  </section>`;
  const ledger = `<section class="panel ledger">
    <header class="section-head"><h2>${lobby ? "Houses in harbor" : ended ? "Final standings" : "House standings"}</h2>${lobby ? "" : "<span>Net worth</span>"}</header>
    <ol>${houses.map(([firm, name, port, worth, rank, status, color], i) => {
      const state = lobby ? (i === 0 ? "Host" : "Joined") : ended ? rank : sea && [0, 2].includes(i) ? "In battle" : status;
      return `<li style="--house:${chartData.colors[color]}">
        <span class="place">${lobby ? "" : String(i + 1).padStart(2, "0")}</span>
        <div class="house"><strong>${esc(firm)}</strong><small>${esc(name)} · ${esc(chartData.ports[port].name)}</small></div>
        <div class="result">${lobby ? "" : `<b>${money(worth)}</b>`}<small class="${state === "Orders in" ? "ready" : state === "In battle" ? "danger" : ""}">${esc(state)}</small></div>
      </li>`;
    }).join("")}</ol>
  </section>`;
  const outlook = lobby ? "" : `<section class="panel outlook">
    <header class="section-head"><h2>Sea forecast</h2></header>
    <ul>${Object.entries(weather).map(([key, level]) => `<li><span>${esc(chartData.regions[key].name)}</span><b class="wx${level}">${esc(chartData.weather[level])}</b></li>`).join("")}</ul>
  </section>`;
  const notices = lobby ? "" : `<section class="panel notices">
    <header class="section-head"><h2>Customs notices</h2></header>
    <ul>${Object.entries(bans).map(([port, cargo]) => `<li><strong>${esc(chartData.ports[port].name)}</strong><span>${cargo.join(" &amp; ")} banned</span></li>`).join("")}</ul>
  </section>`;
  const dispatch = lobby ? "" : `<section class="panel dispatch">
    <header class="section-head"><h2>Harbor news</h2></header>
    <ul>${news.map(line => `<li>${esc(line)}</li>`).join("")}</ul>
  </section>`;
  const status = `<section class="panel status ${sea ? "combat" : ""}">
    <div><span class="label">${lobby ? "Before departure" : sea ? "Battle at sea" : ended ? "Voyage complete" : "Sailing orders"}</span>
    <h2>${esc(heading)}</h2><p>${esc(detail)}</p></div>
    ${sea ? '<ul class="encounters"><li><strong>Jade Compass</strong><span>Off Hong Kong · 3 of 5 pirate ships left</span></li><li><strong>Salt &amp; Silk</strong><span>Off Manila · 1 of 4 pirate ships left</span></li></ul>' : ""}
  </section>`;
  board.innerHTML = `<header class="masthead">
    <div class="identity"><img src="../../web/uploads/historical-logo.svg" alt="Crimson Ledger"><h1>Harbor Board</h1></div>
    <div class="edition"><time datetime="${lobby ? "1860-01" : "1860-07"}">${lobby ? "January" : "July"} 1860</time>
      <small>${lobby ? "1-year voyage" : ended ? "Final edition" : "6 months remaining"}</small></div>
    <div class="join"><span class="label">Join on your device</span><strong>192.168.1.20:8765</strong></div>
  </header>
  ${mode === "offline" ? '<p class="connection" role="status">Reconnecting · showing the last received update</p>' : ""}
  ${status}
  ${gazette ? `<div class="layout"><div class="column">${ledger}${outlook}${notices}</div>
    <div class="column"><figure class="harbor"><img src="../../web/uploads/historical-port-hongkong.webp" alt="Sailing ships at anchor"><figcaption>Hong Kong</figcaption></figure>${dispatch}${map}</div></div>`
  : `<div class="layout"><div class="column">${map}<div class="advisories">${outlook}${notices}</div></div><div class="column">${ledger}${dispatch}</div></div>`}`;
  Chart.fit(board);
}

COLORS = chartData.colors;
T["chart.aria"] = "China Seas chart showing ports, house flags and regional weather";
scene.value = [...scene.options].some(option => option.value === location.hash.slice(1)) ? location.hash.slice(1) : "port";
scene.addEventListener("change", () => {
  location.hash = scene.value;
  document.querySelector(".preview a").hash = scene.value;
  render();
});
document.querySelector(".preview a").hash = scene.value;
render();
