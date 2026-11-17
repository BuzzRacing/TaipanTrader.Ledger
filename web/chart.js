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

  // Same drawings as the weather icons on the sail cards.
  const WX_ICONS = [
    '<path d="M3 13c2-2 4-2 6 0s4 2 6 0 4-2 6 0M5 17c2-1.7 4-1.7 6 0s4 1.7 6 0"/>',
    '<circle cx="12" cy="12" r="3.5"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2.1 2.1M16.9 16.9 19 19M19 5l-2.1 2.1M7.1 16.9 5 19"/>',
    '<path d="M6 15a4 4 0 0 1 .7-7.9A5.5 5.5 0 0 1 17.4 9 3.2 3.2 0 0 1 18 15H6Z"/><path d="m8 18-1 2M13 18l-1 2M18 18l-1 2"/>',
    '<path d="M20 7.5c-2.8-3.6-8.7-4.4-12.4-1.7C4.2 8.3 3.5 13 5.8 16.1c2 2.8 6 3.5 8.7 1.4 2.4-1.8 2.9-5.3 1.1-7.6-1.5-2-4.4-2.4-6.3-.9-1.6 1.2-1.9 3.6-.7 5.1"/>',
  ];

  /* opts: data (static), players, weather, crackdown, here (port key), dest (port key),
           clickable (bool), mine (player id), focusRoute (bool: frame a selected route on narrow screens),
           hideWeather (bool), hideRose (bool) */
  function svg(o) {
    const D = o.data, out = [];
    let viewBox = "0 0 1000 600", focused = false;
    if (o.focusRoute && o.here && o.dest && o.here !== o.dest &&
        typeof window !== "undefined" && window.matchMedia("(max-width: 600px)").matches) {
      const a = D.ports[o.here], b = D.ports[o.dest], pad = 70;
      let width = Math.abs(b.x - a.x) + pad * 2, height = Math.abs(b.y - a.y) + pad * 2;
      if (width / height < 5 / 3) width = height * 5 / 3; else height = width * 3 / 5;
      width = Math.min(1000, Math.max(420, width));
      height = Math.min(600, Math.max(252, height));
      const cx = (a.x + b.x) / 2, cy = (a.y + b.y) / 2;
      const x = Math.max(0, Math.min(1000 - width, cx - width / 2));
      const y = Math.max(0, Math.min(600 - height, cy - height / 2));
      viewBox = `${x.toFixed(1)} ${y.toFixed(1)} ${width.toFixed(1)} ${height.toFixed(1)}`;
      focused = true;
    }
    out.push(`<svg class="chart${focused ? " route-focused" : ""}" viewBox="${viewBox}" role="img" aria-label="${te("chart.aria")}">`);
    out.push('<defs>' +
      '<marker id="route-arrow" viewBox="0 0 12 12" refX="9" refY="6" markerWidth="12" markerHeight="12" orient="auto-start-reverse">' +
      '<path d="M1 1 L10 6 L1 11 Z"/></marker>' +
      '<filter id="chart-shadow" x="-40%" y="-40%" width="180%" height="180%">' +
      '<feDropShadow dx="0" dy="3" stdDeviation="3" flood-opacity=".38"/></filter></defs>');
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
    if (!o.hideRose) out.push('<g class="rose" transform="translate(900,500)"><circle r="34"/>' +
      '<path d="M0-44 L7 0 L0 44 L-7 0Z"/><path d="M-44 0 L0-7 L44 0 L0 7Z"/>' +
      '<text y="-50" text-anchor="middle">N</text></g>');
    // weather by sea region
    for (const r of o.hideWeather ? [] : Object.keys(D.regions)) {
      const reg = D.regions[r];
      const [x, y] = px(reg.label_lon, reg.label_lat);
      const lvl = o.weather && o.weather[r] != null ? o.weather[r] : 0;
      // Big weather icon, weather word underneath, sea name below that. No box: a soft halo keeps it legible.
      const icon = WX_ICONS[lvl] || WX_ICONS[0];
      out.push(`<g class="region wxt${lvl}">` +
        `<g class="rwx-icon" transform="translate(${x - 21} ${+y - 50}) scale(1.75)"><g class="halo">${icon}</g><g class="ink">${icon}</g></g>` +
        `<text class="rwx wxt${lvl}" x="${x}" y="${+y + 6}" text-anchor="middle">${esc(D.weather[lvl])}</text>` +
        `<text class="rname" x="${x}" y="${+y + 23}" text-anchor="middle">${esc(reg.name)}</text></g>`);
    }
    // Planned route. The forecast is the same worse-of-origin-and-destination value used by the engine.
    if (o.here && o.dest && o.here !== o.dest) {
      const a = D.ports[o.here], b = D.ports[o.dest];
      const level = Math.max((o.weather && o.weather[a.region]) || 0, (o.weather && o.weather[b.region]) || 0);
      const dx = b.x - a.x, dy = b.y - a.y, distance = Math.hypot(dx, dy) || 1;
      const inset = 22, x1 = a.x + dx / distance * inset, y1 = a.y + dy / distance * inset;
      const x2 = b.x - dx / distance * inset, y2 = b.y - dy / distance * inset;
      out.push(`<g class="planned-route wx${level}"><title>${te("chart.route_forecast", { weather: D.weather[level] })}</title>` +
        `<line class="route-halo" x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}"/>` +
        `<line class="route" x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" marker-end="url(#route-arrow)"/>`);
      if (level >= 2) {
        const mx = a.x + dx * .55, my = a.y + dy * .55;
        out.push(`<g class="route-alert wxt${level}" transform="translate(${mx.toFixed(1)} ${my.toFixed(1)})" filter="url(#chart-shadow)">` +
          '<rect x="-73" y="-25" width="146" height="50" rx="10"/>' +
          '<path class="alert-icon" d="M-58 9 L-47 -12 L-36 9 Z M-47 -5 V2 M-47 6 V7"/>' +
          `<text class="alert-kicker" x="-27" y="-5">${te("chart.route_warning")}</text>` +
          `<text class="alert-weather" x="-27" y="13">${esc(D.weather[level])}</text></g>`);
      }
      out.push('</g>');
    }
    // ports
    for (const k in D.ports) {
      const p = D.ports[k];
      const cls = ["port"];
      if (k === o.here) cls.push("here");
      if (k === o.dest) cls.push("dest");
      if (o.crackdown && o.crackdown.includes(k)) cls.push("ban");
      if (o.clickable && k !== o.here) cls.push("click");
      const labelW = Math.max(90, Math.min(230, p.name.length * 13 + 30));
      const labelH = k === o.here || k === o.dest ? 46 : 34;
      const labelX = p.label_left ? p.x - labelW - 19 : p.x + 19;
      const labelY = p.y - labelH / 2;
      const textX = p.label_left ? p.x - 31 : p.x + 31;
      const anchor = p.label_left ? "end" : "start";
      const act = o.clickable && k !== o.here ? ` data-act="dest" data-port="${k}"` : "";
      out.push(`<g class="${cls.join(" ")}"${act}>` +
        `<line class="label-leader" x1="${p.x}" y1="${p.y}" x2="${p.label_left ? p.x - 19 : p.x + 19}" y2="${p.y}"/>` +
        `<rect class="label-bg" x="${labelX}" y="${labelY}" width="${labelW}" height="${labelH}" rx="8"/>` +
        `<circle class="hit" cx="${p.x}" cy="${p.y}" r="30"/>` +
        `<circle class="pulse" cx="${p.x}" cy="${p.y}" r="19"/>` +
        `<circle class="ring" cx="${p.x}" cy="${p.y}" r="14"/>` +
        `<circle class="dot" cx="${p.x}" cy="${p.y}" r="8"/>` +
        (k === o.here ? `<g class="current-flag" transform="translate(${p.x - 3} ${p.y - 18})">` +
          '<line x1="0" y1="0" x2="0" y2="-31"/><path d="M0 -31 L29 -25 L0 -17 Z"/></g>' : '') +
        `<text class="port-name" x="${textX}" y="${k === o.here || k === o.dest ? p.y - 2 : p.y + 6}" text-anchor="${anchor}">${esc(p.name)}</text>` +
        (k === o.here ? `<text class="port-status" x="${textX}" y="${p.y + 14}" text-anchor="${anchor}">${te("chart.current")}</text>` :
          k === o.dest ? `<text class="port-status" x="${textX}" y="${p.y + 14}" text-anchor="${anchor}">${te("chart.destination")}</text>` : '') +
        `</g>`);
    }
    // house flags
    const at = {};
    for (const pl of (o.players || [])) (at[pl.port] = at[pl.port] || []).push(pl);
    for (const k in at) {
      const p = D.ports[k];
      if (!p) continue;
      at[k].forEach((pl, i) => {
        const x = p.x - 4 + (i % 4) * 17 - (Math.min(at[k].length, 4) - 1) * 8.5, y = p.y - 22 - Math.floor(i / 4) * 23;
        out.push(`<g class="flag${pl.id === o.mine ? " mine" : ""}${pl.ready ? " ready" : ""}">` +
          `<line x1="${x}" y1="${y}" x2="${x}" y2="${y - 21}"/>` +
          `<path d="M${x} ${y - 21} l15 5 l-15 5z" fill="${COLORS[pl.color % 8]}"/>` +
          `<title>${esc(pl.firm)}</title></g>`);
      });
    }
    out.push("</svg>");
    return out.join("");
  }

  function distance(D, a, b) {
    return Math.hypot(D.ports[a].x - D.ports[b].x, D.ports[a].y - D.ports[b].y);
  }

  /* Size every port label box to its text as actually drawn, so a wider font never spills out.
     Runs after each redraw and again once web fonts finish loading. Hidden charts are skipped. */
  function fit(root) {
    const scope = root || document;
    scope.querySelectorAll("svg.chart .port").forEach(g => {
      const rect = g.querySelector(".label-bg");
      const texts = g.querySelectorAll(".port-name, .port-status");
      if (!rect || !texts.length) return;
      let x0 = Infinity, x1 = -Infinity;
      texts.forEach(t => {
        let b;
        try { b = t.getBBox(); } catch (e) { return; }
        if (!b || !b.width) return;
        x0 = Math.min(x0, b.x); x1 = Math.max(x1, b.x + b.width);
      });
      if (!isFinite(x0)) return;
      rect.setAttribute("x", (x0 - 12).toFixed(1));
      rect.setAttribute("width", (x1 - x0 + 24).toFixed(1));
    });
  }
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => fit());

  return { svg, distance, fit };
})();
