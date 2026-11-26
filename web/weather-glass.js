/* Taipan Trader: the weather glass. Port > Newspaper, top of the right-hand column (21 Nov 2026).

   A television forecast built from 1860s parts: an oxblood title strap, one column per sea, a lower-third band
   for warnings. Behind each column stands the Gazette's own weather reporter, Tommy Marsh (cast key "crier"),
   reporting from the quay and plainly at the mercy of that sea's weather.

   HER PICTURES come from the Media Library: Personas > Tommy Marsh, role "weather", tagged weather-calm,
   weather-fair, weather-squalls or weather-typhoon. media.js keeps anything in that role or tagged weather to this one slot. A screen that may show NSFW
   prefers the pictures not tagged "clean"; a family-friendly screen is only ever sent the clean ones. Each sea
   keeps one picture for the month (so redraws do not reshuffle them), seas with the same weather get different
   pictures while there are enough, and a new month deals again.

   LAYOUT WITH A PICTURE: her face sits in the upper middle of the picture, so that part of the column is left
   clear. The sea's name is across the top; a big glyph, the weather, the force and the wind are stacked at the
   bottom left over a wash of the weather's own colour (blue calm, green fair, amber squalls, red typhoon), and
   the column's edge is that colour too. A column with no picture for its weather (none made yet) keeps the plain look:
   everything centred under a big glyph. Tap a column with a picture to see her full size with the forecast as
   a lower third; tap again (or Esc) to close.

   The house's own seas (where it is, where it is bound) wear a brass ring outside the weather-coloured edge; the
   "Your waters" and "Your course" ribbons were dropped (they got in the way) and are only the hover title.

   Used by portPaper() in player.js: WeatherGlass.html({ here: <sea key>, dest: <sea key or null> }).
   Styles: weather-glass.css. Wording: the port.news.* keys in strings.py, plus the two fallbacks below. */
"use strict";

var T_FALLBACK = Object.assign(typeof T_FALLBACK !== "undefined" ? T_FALLBACK : {}, {
  "port.paper.force": "Force", "port.paper.sea": "Sea {state}" });

const WeatherGlass = (() => {
  const KINDS = ["calm", "fair", "squalls", "typhoon"];
  const WHO = "crier";
  let picks = {};       // sea -> { turn, lv, id }: the picture each sea shows this month
  let shown = {};       // sea -> what its column shows now (for the full-size view)
  let live = null;      // the full-size view's element, while open

  /* The forecast glyphs (0 calm, 1 fair, 2 squalls, 3 typhoon): engraved line drawings on a 48 grid. The parts
     named wxg-* move slowly (weather-glass.css); they hold still under reduced motion. */
  function glyph(level) {
    const art = [
      `<path d="M3 30h42"/><path class="wxg-body" d="M13 30a11 11 0 0 1 22 0Z"/><path d="M18.5 30a5.5 5.5 0 0 1 5.5-5.5" opacity=".5"/>
       <path d="M24 10v5M9.9 15.9l3.5 3.5M38.1 15.9l-3.5 3.5M4.5 25.5h4.5M39 25.5h4.5"/>
       <g class="wxg-drift"><path d="M6 36c3-1.9 6-1.9 9 0s6 1.9 9 0 6-1.9 9 0 6 1.9 9 0"/><path d="M11 42c2.9-1.8 5.8-1.8 8.7 0s5.8 1.8 8.6 0 5.8-1.8 8.7 0" opacity=".65"/></g>`,
      `<circle class="wxg-body" cx="24" cy="24" r="10"/><path d="M17.5 24a6.5 6.5 0 0 1 6.5-6.5" opacity=".5"/>
       <g class="wxg-turn"><path d="M24 2v8M24 38v8M2 24h8M38 24h8"/><path d="M9.2 9.2l4.6 4.6M34.2 34.2l4.6 4.6M38.8 9.2l-4.6 4.6M13.8 34.2l-4.6 4.6" opacity=".7"/></g>`,
      `<path class="wxg-body" d="M10.5 28a8.5 8.5 0 0 1 1.5-16.8A11.7 11.7 0 0 1 34.8 15.3 6.9 6.9 0 0 1 36.1 28H10.5Z"/><path d="M15 21.5a5.6 5.6 0 0 1 5.2-5.2" opacity=".55"/>
       <path d="M40 17.5c2.9 0 4.5 1.6 4.5 3.4s-1.5 3-3 3" opacity=".6"/>
       <g class="wxg-rain"><path d="M15 32.5l-3 7M23 32.5l-3 7M31 32.5l-3 7"/><path d="M18.8 41l-2 4.5M26.8 41l-2 4.5" opacity=".65"/></g>`,
      `<g class="wxg-spin"><path transform="translate(24 24) scale(2.2) translate(-11.6 -11.6)" stroke-width=".72" d="M20 7.5c-2.8-3.6-8.7-4.4-12.4-1.7C4.2 8.3 3.5 13 5.8 16.1c2 2.8 6 3.5 8.7 1.4 2.4-1.8 2.9-5.3 1.1-7.6-1.5-2-4.4-2.4-6.3-.9-1.6 1.2-1.9 3.6-.7 5.1"/></g>
       <path d="M0 6h7M41 43h7M1 12h4M43 37h4" opacity=".6"/>`,
    ];
    return `<svg class="wxb-glyph" viewBox="0 0 48 48" aria-hidden="true" focusable="false">${art[level] || art[1]}</svg>`;
  }

  /* Tommy's pictures for one kind of weather that this screen may show. */
  function shots(lv) {
    if (typeof Media === "undefined" || !Media.items) return [];
    const has = (i, word) => (i.g || []).some(t => String(t).split(/[\s,]+/).includes(word));
    const all = Media.items("persona", WHO, "", false, "weather").filter(i => has(i, "weather-" + KINDS[lv]));
    const bare = all.filter(i => !has(i, "clean"));
    return bare.length ? bare : all;
  }

  /* One of a list, by the Media Library's weights. */
  function draw(list) {
    let r = Math.random() * list.reduce((n, i) => n + (i.w || 1), 0);
    for (const i of list) { r -= i.w || 1; if (r <= 0) return i; }
    return list[list.length - 1];
  }

  /* A picture for every sea: what it already shows this month if that still fits, otherwise a fresh draw. Seas
     with the same weather share the pictures out evenly (four fair seas and two pictures is two each, never
     three and one), a sea avoids the picture of the sea on its left, and a picture shown more than once is
     mirrored every other time so repeats do not read as copies. Returns { pics: sea -> item, flip: sea -> bool }. */
  function deal(seas, level) {
    const turn = S.turn, uses = {}, pics = {}, lists = {}, flip = {}, next = {}, seen = {};
    const take = (r, it) => { pics[r] = it; uses[it.id] = (uses[it.id] || 0) + 1; };
    seas.forEach(r => {
      const lv = level(r), had = picks[r];
      lists[r] = shots(lv);
      const keep = had && had.turn === turn && had.lv === lv && lists[r].find(i => i.id === had.id);
      if (keep) take(r, keep);
    });
    seas.forEach((r, j) => {
      if (pics[r] || !lists[r].length) return;
      const least = Math.min(...lists[r].map(i => uses[i.id] || 0));
      const fewest = lists[r].filter(i => (uses[i.id] || 0) === least);
      const left = j > 0 ? pics[seas[j - 1]] : null, apart = fewest.filter(i => !left || i.id !== left.id);
      take(r, draw(apart.length ? apart : fewest));
    });
    seas.forEach(r => {
      if (!pics[r]) return;
      seen[pics[r].id] = (seen[pics[r].id] || 0) + 1;
      flip[r] = seen[pics[r].id] % 2 === 0;
      next[r] = { turn, lv: level(r), id: pics[r].id };
    });
    picks = next;
    return { pics, flip };
  }

  /* "Steady breeze, Force 4 to 5" gives the big figure 4–5 and the line "Steady breeze" (the wording is the
     Language & Text page's; a wind line with no force in it is shown whole, with no big figure). */
  function reading(lv) {
    const wind = te("port.news.wx_wind." + lv);
    const m = /^(.*?)[,;:]?\s*\bforce\s+(\d+)(?:\s*(?:to|-|–)\s*(\d+))?\s*$/i.exec(wind);
    return { force: m ? m[2] + (m[3] ? "–" + m[3] : "") : "", wind: m ? m[1].trim() || wind : wind,
      swell: te("port.paper.sea", { state: te("port.news.wx_sea." + lv).toLowerCase() }) };
  }

  function html(o) {
    o = o || {};
    const level = r => Math.max(0, Math.min(3, (S.weather || {})[r] || 0));
    const seas = Object.keys(D.regions || {});
    const { pics, flip } = deal(seas, level);
    shown = {};
    const cols = seas.map(r => {
      const lv = level(r), mark = r === o.here ? "here" : r === o.dest ? "dest" : "", pic = pics[r] || null;
      const name = esc(D.regions[r].name || r), word = esc(D.weather[lv]), rd = reading(lv);
      const figure = rd.force ? `<span class="wxb-force"><b>${rd.force}</b><small>${te("port.paper.force")}</small></span>` : "";
      const tip = mark ? te(mark === "here" ? "port.news.wx_here" : "port.paper.tag.dest") : "";
      if (pic) shown[r] = { u: pic.u, lv, name, word, rd };
      return `<li class="wxb-sea wx${lv}${mark ? " " + mark : ""}${pic ? " has-pic" : ""}"${tip ? ` title="${tip}"` : ""}${
        pic ? ` data-wxsea="${esc(r)}" role="button" tabindex="0"` : ""}>
        ${pic ? `<img class="wxb-shot${flip[r] ? " flip" : ""}" src="${esc(pic.u)}" alt="" draggable="false">` : ""}<h3>${name}</h3>
        <div class="wxb-read"><span class="wxb-now">${glyph(lv)}<strong>${word}</strong></span>${figure}
          <span class="wxb-wind">${rd.wind}</span><span class="wxb-swell">${rd.swell}</span></div></li>`;
    }).join("");
    const worst = Math.max(0, ...seas.map(level));
    const warning = worst >= 3 ? `<p class="wxb-band alarm">${glyph(3)}<span>${te("port.news.wx_warning")}</span></p>` : "";
    const advice = [o.here, o.dest].filter((r, j, all) => r && all.indexOf(r) === j && D.regions[r] && level(r) >= 2)
      .map(r => `<p class="wxb-band wx${level(r)}"><b>${esc(D.regions[r].name || r)}</b><span>${te("port.news.wx_advice." + level(r))}</span></p>`).join("");
    const right = Math.round((+D.forecast_accuracy || 0) * 100);
    if (live && live.dataset.turn !== String(S.turn)) close();      // the month turned under an open picture
    return `<section class="card pt-wxboard${worst >= 3 ? " alert" : ""}" aria-label="${te("port.news.weather")}">
      <header class="wxb-strap"><h2>${te("port.news.weather")}</h2><span>${te("port.news.wx_issued", { date: esc(S.date) })}</span></header>
      <ul class="wxb-seas" style="--wxb-n:${seas.length || 1}">${cols}</ul>
      ${warning}${advice}
      <p class="wxb-foot">${te("port.news.wx_bureau")}. ${te("port.news.weather_note", { right })}</p></section>`;
  }

  /* Her picture full size, the forecast as a lower third. It hangs off <body>, outside the screen's redraws. */
  function open(sea) {
    const p = shown[sea];
    close();
    if (!p) return;
    live = document.createElement("div");
    live.className = "wxb-live wx" + p.lv;
    live.dataset.turn = String(S.turn);
    live.setAttribute("role", "dialog");
    live.setAttribute("aria-label", p.name);
    live.innerHTML = `<figure><img src="${esc(p.u)}" alt=""><figcaption class="wxb-third"><b>${p.name}</b>
      <span>${glyph(p.lv)}<strong>${p.word}</strong>${p.rd.force ? `<i>${te("port.paper.force")} ${p.rd.force}</i>` : ""}<em>${p.rd.wind} · ${p.rd.swell}</em></span></figcaption></figure>`;
    live.addEventListener("click", close);
    document.body.appendChild(live);
  }
  function close() {
    if (live) live.remove();
    live = null;
  }
  if (typeof document !== "undefined") {
    document.addEventListener("click", e => {
      const li = e.target && e.target.closest && e.target.closest("[data-wxsea]");
      if (li) open(li.dataset.wxsea);
    });
    document.addEventListener("keydown", e => {
      if (e.key === "Escape" && live) return close();
      const li = (e.key === "Enter" || e.key === " ") && e.target && e.target.matches && e.target.matches("[data-wxsea]") ? e.target : null;
      if (li) { e.preventDefault(); open(li.dataset.wxsea); }
    });
  }

  return { html, glyph, open, close };
})();
