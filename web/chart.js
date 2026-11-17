/* The sea chart: a stylised 1000 x 600 map of the trading waters, drawn as SVG.
   Uses the same projection as engine.py. Coastlines are rough sketches;
   Admin > Graphics can replace them with a painted chart. */
"use strict";

const Chart = (() => {
  const px = (lon, lat) => [((lon - 85) / 50 * 1000).toFixed(1), ((35 - lat) / 45 * 600).toFixed(1)];

  const LAND = [
    // Mainland Asia, from Bengal round to the Yangtze
    [[70, 50], [119, 50], [119, 35], [120.8, 33], [122, 31], [121.6, 28.5], [119.6, 25.5], [116.6, 23], [114, 22.3],
     [110.5, 21.2], [108.6, 21.7], [106.6, 20], [106, 18], [108.8, 15.5], [109.2, 12], [107.2, 10.4],
     [105, 8.7], [104.8, 10.3], [102.6, 12], [101, 12.8], [100.5, 13.5], [100, 12], [99.3, 9.5],
     [100.5, 7], [102.6, 5], [103.5, 2.6], [104, 1.35], [103.3, 1.5], [101.3, 2.8], [100.3, 5.6],
     [98.3, 8], [98.7, 11], [97.7, 15.5], [97, 16.8], [95.3, 15.8], [94.3, 17.6], [92, 21],
     [90.5, 22.2], [88.4, 21.7], [87, 20.5], [85, 19.5], [70, 17]],
    // Korea
    [[125, 50], [126.2, 35], [126.3, 34.4], [127.6, 34.6], [129.3, 35], [130, 50]],
    // Kyushu and western Honshu
    [[129.7, 33.6], [131, 33.9], [132, 33], [131.4, 31.4], [130.2, 31.2], [129.7, 32.6]],
    [[131, 34.3], [133, 35.5], [137, 37.5], [150, 40], [150, 35], [135, 33.6], [133, 33.9]],
    // Taiwan, Hainan
    [[121.5, 25.3], [122, 24.7], [120.9, 22], [120.1, 23], [120.8, 24.6]],
    [[108.7, 19.3], [110.3, 20.1], [111, 19.6], [110, 18.4], [108.7, 18.6]],
    // Luzon, Visayas, Mindanao
    [[120.5, 18.5], [122, 18.3], [122.3, 16.5], [121.6, 14.2], [124, 13], [123.5, 12.6],
     [121.5, 13.6], [120.7, 14.5], [119.9, 16.2], [120.4, 17.5]],
    [[122, 11.6], [123.2, 11.4], [124.6, 11.2], [125.2, 10.2], [123.4, 9.4], [122.4, 10.4]],
    [[122, 7], [123.5, 8.5], [125.5, 9.7], [126.5, 7.5], [125.5, 6], [124, 6.2]],
    [[117.3, 8.3], [119.5, 10.6], [119.6, 11.3], [118.6, 10], [117.2, 8.7]],
    // Borneo
    [[109, 1.5], [111, 2.5], [113.5, 4.5], [116, 6.8], [117.5, 6], [119, 5], [117.8, 2.5],
     [117.6, 0], [116, -3.5], [114.5, -4], [111.5, -3.2], [110, -1.5], [109, 0.3]],
    // Sumatra, Java
    [[95.3, 5.5], [98, 3.8], [101, 1.7], [104, -1], [106, -3.5], [105.7, -5.8], [104.3, -5.7],
     [102, -3.8], [100.3, -0.8], [98.5, 1.7], [96, 4]],
    [[105.2, -6.5], [107, -5.9], [108.7, -6.7], [111, -6.5], [113, -7], [114.5, -7.8],
     [114.4, -8.7], [111, -8.3], [108, -7.8], [106, -7]],
    // Celebes
    [[119.5, 0.8], [121, 1.2], [124.5, 1.3], [123, 0.4], [120.8, 0.4], [121.8, -1], [123.2, -1],
     [121.6, -2], [122.6, -4.6], [121.4, -4.6], [120.4, -2.8], [120.2, -5.5], [119.4, -5.4], [119.2, -2.5]]
  ];

  /* opts: data (static), players, weather, crackdown, here (port key), dest (port key),
           clickable (bool), mine (player id) */
  function svg(o) {
    const D = o.data, out = [];
    out.push('<svg class="chart" viewBox="0 0 1000 600" role="img" aria-label="' + te("chart.aria") + '">');
    out.push('<rect class="sea" x="-1000" y="-600" width="3000" height="1800"/>');
    for (let lon = 60; lon <= 160; lon += 5) {
      const x = px(lon, 0)[0];
      out.push(`<line class="grat" x1="${x}" y1="-600" x2="${x}" y2="1200"/>`);
    }
    for (let lat = -30; lat <= 60; lat += 5) {
      const y = px(0, lat)[1];
      out.push(`<line class="grat" x1="-1000" y1="${y}" x2="2000" y2="${y}"/>`);
    }
    if (D.graphics.chart_bg) {
      out.push(`<image href="${esc(D.graphics.chart_bg)}" x="0" y="0" width="1000" height="600" preserveAspectRatio="none"/>`);
    } else {
      for (const poly of LAND) {
        out.push('<polygon class="land" points="' + poly.map(p => px(p[0], p[1]).join(",")).join(" ") + '"/>');
      }
    }
    // compass rose
    out.push('<g class="rose" transform="translate(900,500)"><circle r="34"/>' +
      '<path d="M0-44 L7 0 L0 44 L-7 0Z"/><path d="M-44 0 L0-7 L44 0 L0 7Z"/>' +
      '<text y="-50" text-anchor="middle">N</text></g>');
    // weather by sea region
    for (const r in D.regions) {
      const reg = D.regions[r];
      const [x, y] = px(reg.label_lon, reg.label_lat);
      const lvl = o.weather && o.weather[r] != null ? o.weather[r] : 0;
      out.push(`<g class="region"><text class="rname" x="${x}" y="${y}" text-anchor="middle">${esc(reg.name)}</text>` +
        `<text class="rwx wxt${lvl}" x="${x}" y="${+y + 17}" text-anchor="middle">${esc(D.weather[lvl])}</text></g>`);
    }
    // planned route
    if (o.here && o.dest && o.here !== o.dest) {
      const a = D.ports[o.here], b = D.ports[o.dest];
      out.push(`<line class="route" x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}"/>`);
    }
    // ports
    for (const k in D.ports) {
      const p = D.ports[k];
      const cls = ["port"];
      if (k === o.here) cls.push("here");
      if (k === o.dest) cls.push("dest");
      if (o.crackdown && o.crackdown.includes(k)) cls.push("ban");
      if (o.clickable && k !== o.here) cls.push("click");
      const dx = p.label_left ? -12 : 12;
      const act = o.clickable && k !== o.here ? ` data-act="dest" data-port="${k}"` : "";
      out.push(`<g class="${cls.join(" ")}"${act}>` +
        `<circle class="hit" cx="${p.x}" cy="${p.y}" r="26"/>` +
        `<circle class="ring" cx="${p.x}" cy="${p.y}" r="11"/>` +
        `<circle class="dot" cx="${p.x}" cy="${p.y}" r="5.5"/>` +
        `<text x="${p.x + dx}" y="${p.y + 5}" text-anchor="${dx < 0 ? "end" : "start"}">${esc(p.name)}</text></g>`);
    }
    // house flags
    const at = {};
    for (const pl of (o.players || [])) (at[pl.port] = at[pl.port] || []).push(pl);
    for (const k in at) {
      const p = D.ports[k];
      if (!p) continue;
      at[k].forEach((pl, i) => {
        const x = p.x - 4 + (i % 4) * 15 - (Math.min(at[k].length, 4) - 1) * 7.5, y = p.y - 16 - Math.floor(i / 4) * 20;
        out.push(`<g class="flag${pl.id === o.mine ? " mine" : ""}${pl.ready ? " ready" : ""}">` +
          `<line x1="${x}" y1="${y}" x2="${x}" y2="${y - 17}"/>` +
          `<path d="M${x} ${y - 17} l12 4 l-12 4z" fill="${COLORS[pl.color % 8]}"/>` +
          `<title>${esc(pl.firm)}</title></g>`);
      });
    }
    out.push("</svg>");
    return out.join("");
  }

  function distance(D, a, b) {
    return Math.hypot(D.ports[a].x - D.ports[b].x, D.ports[a].y - D.ports[b].y);
  }

  return { svg, distance };
})();
