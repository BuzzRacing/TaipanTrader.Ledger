"use strict";

/* The Voyage Certificate (21 Nov 2026; project doc "SeaTrader Voyage Certificate"; certificate.py, cert_text.py).

   When the books close each Captain is handed a certificate: a 1920 x 1080 wallpaper with the home port
   behind, the home Mayor fading in from the left, the speaker who defined the voyage fading in from the
   right, and the Captain's finish down the middle. It is PAINTED on a canvas at the true size, so the
   picture on screen is exactly the PNG that "Save as wallpaper" downloads.

     Certificate.show({ state, data, onDone, label })   opens it (the finale calls this between the winner
                                                        reveal and the Ledger of the Voyage)
     Certificate.open(state, data)                      opens it again from the end-of-game screen
     Certificate.close()                                closes it without calling onDone

   Pictures come from the Media Library, so they follow this screen's NSFW or family-friendly setting:
     backdrop   the home port's certificate backdrop (tag cert-backdrop), else its arrival picture, its
                banner, the Graphics port picture, the finale's harbor painting
     left       the home Mayor's certificate picture (tag cert-left), else one of her Mayor pictures
     right      the story persona's certificate picture (tag cert-right), else a portrait of her
   A wide picture (made by Queue_Certificate_Pictures.bat: she stands at one side of a dark, empty frame)
   is laid across the whole width; an ordinary upright portrait is set at the edge and feathered.

   The choice of pictures (the recipe) is kept by the server, so the certificate opens the same way next
   time. "Change the pictures" draws fresh ones and steps to the next speaker the voyage earned. */

var T_FALLBACK = Object.assign(typeof T_FALLBACK !== "undefined" ? T_FALLBACK : {}, {
  "cert.title": "Certificate of the Voyage", "cert.place": "{ord} of {n} Houses",
  "cert.ord_one": "{n}st", "cert.ord_two": "{n}nd", "cert.ord_few": "{n}rd", "cert.ord_other": "{n}th",
  "cert.career_best": "Best of {n} {len} voyages", "cert.career_place": "{ord} best of {n} {len} voyages",
  "cert.career_first": "A first {len} voyage", "cert.bad": "Survived the China Seas",
  "cert.len": "{years}-year", "cert.len_5": "five-year", "cert.len_10": "ten-year", "cert.len_20": "twenty-year", "cert.len_50": "fifty-year",
  "cert.captain": "Captain {name}", "cert.house": "of the House of {firm}", "cert.worth": "Final net worth",
  "cert.span": "{first} to {last} · a {len} voyage out of {port}", "cert.span_short": "{first} to {last} · out of {port}",
  "cert.best_sale": "Best sale", "cert.best_sale_value": "{profit} profit", "cert.best_sale_sub": "{qty} {good}, sold in {port}",
  "cert.best_sale_none": "None in profit", "cert.best_sale_none_sub": "The sea kept the margins",
  "cert.battles": "Battles won", "cert.battles_value": "{won} of {n}", "cert.battles_sub": "{sunk} enemy ships sunk",
  "cert.battles_none": "None fought", "cert.battles_none_sub": "A quiet sea all voyage",
  "cert.signed": "Her Worship the Mayor", "cert.mayor": "Mayor of {port}", "cert.closed": "The books are closed",
  "cert.save": "Save as wallpaper", "cert.change": "Change the pictures", "cert.continue": "Continue to the Ledger",
  "cert.close": "Close", "cert.again": "Hear the line again",
  "cert.hold": "On an iPad, press and hold the picture and choose Save to Photos.",
  "cert.working": "Sealing your certificate…",
  "cert.failed": "The certificate could not be drawn. The Ledger of the Voyage has every figure.",
  "cert.saved": "Saved. Set it as your wallpaper from your pictures.",
  "cert.file": "{brand} - Captain {name} - {date}", "end.certificate": "Open your Certificate of the Voyage",
});

const Certificate = (() => {
  const W = 1920, H = 1080, CX = W / 2;
  const COL = 1076;                       // the words keep to the middle 56% (desktop icons only ever cover the speakers)
  const INK = "#0b161d", IVORY = "#eef1e2", CREAM = "#fff1cf", BRASS = "#d6a84e", GOLD = "#e7bf72", PALE = "#e9dcc0";
  const HARBOR = "/assets/ceremony-harbor.png";
  const SIDE_SLIDE = 260;                 // how far a picture made for its side is slid toward the edge (px of 1920)
  const PLAIN_SLIDE = 420;                // the same for an ordinary wide picture, which has her nearer the middle
  const STAGE_MS = 430;                   // between the layers as the certificate arrives

  let el = null, facts = null, factsFor = null, D = null, S = null, opts = {};
  let step = 0, pick = { bg: null, mayor: null, persona: null }, last = { bg: "", mayor: "", persona: "" };
  let run = 0, pngUrl = "", pngBlob = null, busy = false, hush = false;

  /* ------------------------------------------------------------ words -- */
  const has = key => typeof T !== "undefined" && T[key] != null;
  const tx = (key, vars) => (has(key) ? t(key, vars) : String(T_FALLBACK[key] || key).replace(/\{(\w+)\}/g, (m, k) => (vars && vars[k] != null ? vars[k] : m)));
  const num = n => Math.round(Number(n) || 0).toLocaleString("en-US");
  function short(n) {
    const v = Math.abs(Number(n) || 0), cur = typeof CUR === "string" ? CUR : "$";
    const f = (x, s) => cur + String(x >= 100 ? Math.round(x) : x >= 10 ? x.toFixed(1) : x.toFixed(2)).replace(/\.0+$|(\.\d*[1-9])0+$/, "$1") + s;
    if (v >= 1e9) return f(v / 1e9, "B");
    if (v >= 1e6) return f(v / 1e6, "M");
    if (v >= 1e4) return f(v / 1e3, "K");
    return money(n);
  }
  const PLURAL = typeof Intl !== "undefined" && Intl.PluralRules ? new Intl.PluralRules("en", { type: "ordinal" }) : null;
  const ordinal = n => tx("cert.ord_" + (PLURAL ? PLURAL.select(n) : "other"), { n });
  const lengthOf = years => (has("cert.len_" + years) || T_FALLBACK["cert.len_" + years] ? tx("cert.len_" + years) : tx("cert.len", { years }));
  const portName = key => (D && D.ports && D.ports[key] && D.ports[key].name) || key || "";
  const goodName = key => (D && D.goods && D.goods[key] && D.goods[key].name) || key || "";
  const reduced = () => typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;
  const family = () => (typeof screenFamily === "function" && screenFamily()) || (typeof Media !== "undefined" && Media.family());
  const castOf = who => (typeof VS !== "undefined" && VS && VS.cast && VS.cast[who]) || {};

  /* --------------------------------------------------------- pictures -- */
  const tagged = (i, tag) => (i.g || []).some(g => String(g).toLowerCase() === tag);
  function library(kind, subject, role, tag) {
    if (typeof Media === "undefined" || !subject) return [];
    if (tag) {
      const by = scene => Media.items(kind, subject, "", false, scene).filter(i => tagged(i, tag));
      const mine = by("certificate");
      // pictures made by the batch for a side carry `side`: the speaker already stands at that edge of the frame
      return (mine.length ? mine : by("wallpaper")).map(i => Object.assign({}, i, { side: true }));   // a media.js from before the certificate files them there
    }
    return Media.items(kind, subject, role, false).filter(i => !role || i.r.includes(role));
  }
  /* The first of these lists that has anything; each entry is {id, u}. */
  function pool(...lists) {
    for (const list of lists) if (list && list.length) return list;
    return [];
  }
  function draw1(list, want, avoid) {
    if (!list.length) return null;
    const kept = want && list.find(i => i.id === want);
    if (kept) return kept;
    const fresh = list.length > 1 && avoid ? list.filter(i => i.id !== avoid) : list;
    const total = fresh.reduce((n, i) => n + (i.w || 1), 0);
    let r = Math.random() * total;
    for (const i of fresh) { r -= i.w || 1; if (r <= 0) return i; }
    return fresh[fresh.length - 1];
  }
  const plain = url => (url ? [{ id: "", u: url }] : []);

  function choose(recipe) {
    const home = facts.home, speaker = facts.speakers[step] || facts.speakers[0];
    pick.bg = draw1(pool(library("port", home, "", "cert-backdrop"), plain(HARBOR)), recipe && recipe.bg, last.bg);
    pick.mayor = draw1(pool(library("port", home, "", "cert-left"), library("port", home, "mayor"), plain(castOf("mayor").portrait)),
      recipe && recipe.mayor, last.mayor);
    pick.persona = draw1(pool(library("persona", speaker.who, "", "cert-right"), library("persona", speaker.who, "portrait"),
      library("persona", speaker.who, ""), plain(castOf(speaker.who).portrait)), recipe && recipe.persona, last.persona);
    last = { bg: (pick.bg || {}).id || "", mayor: (pick.mayor || {}).id || "", persona: (pick.persona || {}).id || "" };
  }

  const mark = (im, item) => { if (im) im.sideMade = !!(item && item.side); return im; };

  function load(url) {
    return new Promise(done => {
      if (!url) return done(null);
      const im = new Image();
      im.decoding = "async";
      im.onload = () => done(im.naturalWidth ? im : null);
      im.onerror = () => done(null);
      im.src = url;
    });
  }

  /* ------------------------------------------------------------ fonts -- */
  function fonts() {
    const cs = getComputedStyle(document.documentElement);
    const v = name => (cs.getPropertyValue(name) || "").trim();
    // The certificate keeps its own faces (the game hosts all four), whatever the screens are themed with;
    // where one is not hosted it falls back to the theme's own serif, never to the screens' plain text face.
    const stack = (face, theme) => [face, theme, "Georgia", "serif"].filter(Boolean).join(", ");
    return { title: stack('"Uncial Antiqua"', v("--title")), head: stack('"MedievalSharp"', v("--serif")),
             body: stack('"Alegreya"', v("--serif")), caps: stack('"Alegreya SC"', v("--special")) };
  }
  function fontsReady(F) {
    if (!document.fonts || !document.fonts.load) return Promise.resolve();
    const asks = [`96px ${F.title}`, `34px ${F.head}`, `28px ${F.caps}`, `30px ${F.body}`, `bold 50px ${F.body}`, `italic 30px ${F.body}`]
      .map(f => document.fonts.load(f, "Certificate of the Voyage 0123456789").catch(() => null));
    return Promise.race([Promise.all(asks), new Promise(r => setTimeout(r, 4000))]);
  }

  /* --------------------------------------------------------- painting -- */
  /* Text with letter spacing, centred (or left) on x. Returns its width. */
  function spaced(c, text, x, y, gap, align) {
    const chars = Array.from(String(text));
    const widths = chars.map(ch => c.measureText(ch).width);
    const total = widths.reduce((a, b) => a + b, 0) + gap * Math.max(0, chars.length - 1);
    let at = align === "left" ? x : x - total / 2;
    const was = c.textAlign;
    c.textAlign = "left";
    chars.forEach((ch, i) => { c.fillText(ch, at, y); at += widths[i] + gap; });
    c.textAlign = was;
    return total;
  }
  /* The largest size from px down to min at which text fits max; sets c.font. */
  function fit(c, text, max, px, make, min) {
    for (let s = px; s >= (min || 14); s -= 2) {
      c.font = make(s);
      if (c.measureText(text).width <= max) return s;
    }
    return min || 14;
  }
  function cover(c, im, x, y, w, h, px, py) {
    const s = Math.max(w / im.naturalWidth, h / im.naturalHeight);
    const dw = im.naturalWidth * s, dh = im.naturalHeight * s;
    c.drawImage(im, x + (w - dw) * (px == null ? .5 : px), y + (h - dh) * (py == null ? .5 : py), dw, dh);
  }
  function scratch() {
    const k = document.createElement("canvas");
    k.width = W; k.height = H;
    return k;
  }

  function paintBackdrop(c, im) {
    c.fillStyle = INK;
    c.fillRect(0, 0, W, H);
    if (im) {
      cover(c, im, 0, 0, W, H, .5, .4);
      c.fillStyle = "rgba(18, 40, 58, .38)";            // dusk: the picture sits back so the words can stand on it
      c.fillRect(0, 0, W, H);
    }
    const g = c.createRadialGradient(CX, 518, 0, CX, 518, 845);
    g.addColorStop(0, "rgba(11, 22, 29, .62)");
    g.addColorStop(.58, "rgba(11, 22, 29, .50)");
    g.addColorStop(1, "rgba(11, 22, 29, .10)");
    c.fillStyle = g;
    c.fillRect(0, 0, W, H);
  }

  /* One speaker, feathered toward the centre. A wide picture lies across the whole frame (the figure was composed at
     that side of it); an upright portrait stands at the edge. */
  function paintPortrait(c, im, side) {
    if (!im) return;
    const k = scratch(), x = k.getContext("2d");
    const wide = im.naturalWidth / im.naturalHeight > 1.2;
    const left = side === "left";
    let from, to, solid = .5, soft = .78;
    if (wide && im.sideMade) {
      // made for this side: she already stands in her third of the frame, but that is still too near the words,
      // so the whole picture is slid out by SIDE_SLIDE and fades out sooner
      x.save(); x.translate(left ? -SIDE_SLIDE : SIDE_SLIDE, 0); cover(x, im, 0, 0, W, H, left ? 0 : 1, .5); x.restore();
      from = left ? 0 : W; to = left ? 640 : W - 640;   // the dark, empty side never covers the port
      solid = .7; soft = .9;
    } else if (wide) {
      // An ordinary wide picture is laid across the whole frame and she lands near the middle, behind the words.
      // Slide the picture out toward her own edge so she stands in the outer fifth, clear of the words, and let it
      // fade out before the middle so the port shows.
      const SLIDE = PLAIN_SLIDE;
      x.save(); x.translate(left ? -SLIDE : SLIDE, 0); cover(x, im, 0, 0, W, H, left ? 0 : 1, .5); x.restore();
      from = left ? 0 : W; to = left ? 700 : W - 700;
      solid = .62; soft = .86;
    } else {
      const bw = 760, bx = left ? -40 : W - bw + 40;
      x.save();
      x.beginPath(); x.rect(bx, 0, bw, H); x.clip();
      cover(x, im, bx, 0, bw, H, .5, .12);
      x.restore();
      from = left ? bx : bx + bw; to = left ? bx + bw * .9 : bx + bw * .1;
      solid = .42; soft = .71;
    }
    const m = x.createLinearGradient(from, 0, to, 0);
    m.addColorStop(0, "rgba(0,0,0,1)");
    m.addColorStop(solid, "rgba(0,0,0,1)");
    m.addColorStop(soft, "rgba(0,0,0,.45)");
    m.addColorStop(1, "rgba(0,0,0,0)");
    x.globalCompositeOperation = "destination-in";
    x.fillStyle = m;
    x.fillRect(0, 0, W, H);
    c.drawImage(k, 0, 0);
  }

  function paintFrame(c) {
    const g = c.createLinearGradient(0, 0, 0, H);
    g.addColorStop(0, "rgba(11, 22, 29, .55)");
    g.addColorStop(.16, "rgba(11, 22, 29, 0)");
    g.addColorStop(.74, "rgba(11, 22, 29, 0)");
    g.addColorStop(1, "rgba(11, 22, 29, .88)");
    c.fillStyle = g;
    c.fillRect(0, 0, W, H);
    c.lineWidth = 2; c.strokeStyle = "rgba(201, 162, 90, .55)"; c.strokeRect(19, 19, W - 38, H - 38);
    c.lineWidth = 1; c.strokeStyle = "rgba(201, 162, 90, .3)"; c.strokeRect(26.5, 26.5, W - 53, H - 53);
  }

  function shadow(c, color, blur, dy) { c.shadowColor = color; c.shadowBlur = blur; c.shadowOffsetX = 0; c.shadowOffsetY = dy; }
  function calm(c) { c.shadowColor = "transparent"; c.shadowBlur = 0; c.shadowOffsetY = 0; }

  function paintTitle(c, F) {
    const brand = (typeof brandName === "function" && D && D.brand && brandName(D.brand)) || "Taipan Trader";
    c.textAlign = "center"; c.textBaseline = "alphabetic";
    const px = fit(c, brand, 1000, 96, s => `${s}px ${F.title}`, 48), y = 122;
    shadow(c, "#07090e", 14, 6);
    c.fillStyle = "#2c4655";
    c.fillText(brand, CX, y + 3);
    calm(c);
    const g = c.createLinearGradient(0, y - px * .82, 0, y + px * .2);
    g.addColorStop(.12, "#fff5d8"); g.addColorStop(.52, "#e6bd68"); g.addColorStop(.54, "#ac6e28");
    g.addColorStop(.78, "#efd18e"); g.addColorStop(1, "#ffd99b");
    c.fillStyle = g;
    c.fillText(brand, CX, y);
    c.lineWidth = 1; c.strokeStyle = "rgba(255, 223, 161, .45)";
    c.strokeText(brand, CX, y);
    // the rule and its diamond
    const rule = (x0, x1) => {
      const r = c.createLinearGradient(x0, 0, x1, 0);
      r.addColorStop(0, "rgba(231, 191, 114, 0)"); r.addColorStop(1, "#e7bf72");
      c.fillStyle = r; c.fillRect(Math.min(x0, x1), 157, Math.abs(x1 - x0), 1);
    };
    rule(CX - 260, CX - 22); rule(CX + 260, CX + 22);
    c.fillStyle = "#f6cf80";
    c.save(); c.translate(CX, 157.5); c.rotate(Math.PI / 4); c.fillRect(-6, -6, 12, 12); c.restore();
    c.fillStyle = IVORY;
    shadow(c, "rgba(0,0,0,.8)", 8, 2);
    c.font = `34px ${F.head}`;
    spaced(c, tx("cert.title").toUpperCase(), CX, 209, 6);
    calm(c);
  }

  function headline() {
    const f = facts, rivals = f.houses > 1;
    const place = tx("cert.place", { ord: ordinal(f.place), n: f.houses });
    const k = f.career;
    const len = k ? lengthOf(k.years) : "";
    const career = !k ? "" : k.of <= 1 ? tx("cert.career_first", { len, years: k.years })
      : k.place === 1 ? tx("cert.career_best", { n: k.of, len, years: k.years })
      : tx("cert.career_place", { ord: ordinal(k.place), n: k.of, len, years: k.years });
    if (f.bad) return { big: tx("cert.bad"), sub: rivals ? `${f.rank || ""} · ${place}` : (f.rank || "") };
    if (rivals) return { big: place, sub: f.rank || "" };
    return { big: f.rank || "", sub: career };
  }

  function paintHeadline(c, F) {
    const h = headline();
    c.textAlign = "center"; c.textBaseline = "alphabetic";
    fit(c, h.big, COL - 60, 72, s => `${s}px ${F.title}`, 40);
    shadow(c, "#000", 22, 8);
    c.fillStyle = "#3d1a12"; c.fillText(h.big, CX, 305);
    calm(c);
    c.fillStyle = CREAM; c.fillText(h.big, CX, 302);
    if (h.sub) {
      c.fillStyle = GOLD;
      shadow(c, "rgba(0,0,0,.8)", 8, 2);
      const px = fit(c, h.sub, COL - 160, 32, s => `${s}px ${F.caps}`, 20);
      c.font = `${px}px ${F.caps}`;
      spaced(c, h.sub, CX, 358, 3);
      calm(c);
    }
  }

  function paintWho(c, F, art) {
    const f = facts, size = 140;
    c.textBaseline = "alphabetic";
    const name = tx("cert.captain", { name: f.name }), house = tx("cert.house", { firm: f.firm });
    const epithet = f.epithet && (has("fin.epithet." + f.epithet) ? t("fin.epithet." + f.epithet) : "");
    // Without an epithet the block is two lines, so it sits a little higher and tighter, leaving air above the net worth.
    const top = epithet ? 392 : 380, cy = top + size / 2;
    c.font = `bold 50px ${F.body}`;
    const nameW = Math.min(520, c.measureText(name).width);
    c.font = `28px ${F.caps}`;
    const houseW = Math.min(560, c.measureText(house).width + 2 * Array.from(house).length);
    const block = Math.max(430, nameW, houseW), gap = 36;
    // The words always stand on the centre line, like everything else on the certificate; the crest stays on
    // their left and the rank badge on their right, so a lone badge no longer drags the name off to one side.
    let x = CX - block / 2 - gap - size;
    if (art.crest) {
      c.save();
      shadow(c, "rgba(0,0,0,.7)", 24, 8);
      c.fillStyle = INK; roundRect(c, x, top, size, size, 10); c.fill();
      calm(c);
      roundRect(c, x, top, size, size, 10); c.clip();
      cover(c, art.crest, x, top, size, size);
      c.restore();
      c.lineWidth = 2; c.strokeStyle = "rgba(201, 162, 90, .7)";
      roundRect(c, x + 1, top + 1, size - 2, size - 2, 9); c.stroke();
    }
    const mid = CX;
    c.textAlign = "center";
    shadow(c, "rgba(0,0,0,.85)", 10, 3);
    c.fillStyle = "#fff7e2";
    fit(c, name, 520, 50, s => `bold ${s}px ${F.body}`, 30);
    c.fillText(name, mid, epithet ? top + 42 : top + 56);
    if (epithet) {
      c.fillStyle = GOLD; c.font = `italic 34px ${F.body}`;
      c.fillText(epithet, mid, top + 91);
    }
    c.fillStyle = IVORY;
    const hp = fit(c, house, 520, 28, s => `${s}px ${F.caps}`, 18);
    c.font = `${hp}px ${F.caps}`;
    spaced(c, house, mid, top + (epithet ? 137 : 118), 2);
    calm(c);
    x = CX + block / 2 + gap;
    if (art.badge) {
      c.save();
      shadow(c, "rgba(0,0,0,.75)", 18, 8);
      if (art.badgeRound) {               // a farm-made badge is a square picture of a round medallion
        c.beginPath(); c.arc(x + size / 2, cy, size / 2, 0, Math.PI * 2); c.closePath();
        c.fillStyle = INK; c.fill(); calm(c); c.clip();
        cover(c, art.badge, x, top, size, size);
      } else {
        const s = Math.min(size / art.badge.naturalWidth, size / art.badge.naturalHeight);
        const dw = art.badge.naturalWidth * s, dh = art.badge.naturalHeight * s;
        c.drawImage(art.badge, x + (size - dw) / 2, top + (size - dh) / 2, dw, dh);
      }
      c.restore();
    }
  }
  function roundRect(c, x, y, w, h, r) {
    c.beginPath();
    c.moveTo(x + r, y); c.arcTo(x + w, y, x + w, y + h, r); c.arcTo(x + w, y + h, x, y + h, r);
    c.arcTo(x, y + h, x, y, r); c.arcTo(x, y, x + w, y, r); c.closePath();
  }

  function paintFigures(c, F) {
    const f = facts;
    c.textAlign = "center"; c.textBaseline = "alphabetic";
    shadow(c, "rgba(0,0,0,.8)", 8, 2);
    c.fillStyle = BRASS; c.font = `22px ${F.caps}`;
    spaced(c, tx("cert.worth"), CX, 580, 4);
    calm(c);
    const worth = money(f.worth);
    fit(c, worth, COL - 200, 86, s => `bold ${s}px ${F.body}`, 48);
    shadow(c, "#000", 26, 10);
    c.fillStyle = "#2c4655"; c.fillText(worth, CX, 668);
    calm(c);
    c.fillStyle = "#ffe6ad"; c.fillText(worth, CX, 665);
    const span = tx(f.years ? "cert.span" : "cert.span_short", { first: f.first || "", last: f.last || "", years: f.years, len: lengthOf(f.years), port: f.home_name || portName(f.home) });
    shadow(c, "rgba(0,0,0,.85)", 8, 2);
    c.fillStyle = PALE;
    fit(c, span, COL - 120, 26, s => `${s}px ${F.body}`, 18);
    c.fillText(span, CX, 714);
    calm(c);
    const s = f.best_sale;
    box(c, F, CX - 414, tx("cert.best_sale"),
      s ? tx("cert.best_sale_value", { profit: short(s.profit) }) : tx("cert.best_sale_none"),
      s ? tx("cert.best_sale_sub", { qty: num(s.qty), good: goodName(s.good), port: portName(s.port) }) : tx("cert.best_sale_none_sub"));
    box(c, F, CX + 14, tx("cert.battles"),
      f.battles ? tx("cert.battles_value", { won: num(f.won), n: num(f.battles) }) : tx("cert.battles_none"),
      f.battles ? tx("cert.battles_sub", { sunk: num(f.sunk) }) : tx("cert.battles_none_sub"));
  }
  function box(c, F, x, label, value, sub) {
    const y = 741, w = 400, h = 129, mid = x + w / 2;
    c.fillStyle = "rgba(20, 12, 9, .6)"; c.fillRect(x, y, w, h);
    c.lineWidth = 1; c.strokeStyle = "rgba(201, 162, 90, .65)"; c.strokeRect(x + .5, y + .5, w - 1, h - 1);
    c.textAlign = "center";
    c.fillStyle = BRASS; c.font = `21px ${F.caps}`;
    spaced(c, label, mid, y + 34, 3);
    c.fillStyle = CREAM;
    fit(c, value, w - 36, 42, s => `bold ${s}px ${F.body}`, 24);
    c.fillText(value, mid, y + 80);
    c.fillStyle = PALE;
    fit(c, sub, w - 36, 23, s => `italic ${s}px ${F.body}`, 15);
    c.fillText(sub, mid, y + 112);
  }

  function paintFoot(c, F) {
    const f = facts, line = 956;
    c.textAlign = "center"; c.textBaseline = "alphabetic";
    const side = (mid, top, cap) => {
      shadow(c, "rgba(0,0,0,.85)", 8, 2);
      c.fillStyle = CREAM;
      fit(c, top, 320, 30, s => `italic ${s}px ${F.body}`, 18);
      c.fillText(top, mid, line - 12);
      calm(c);
      c.fillStyle = BRASS; c.fillRect(mid - 160, line, 320, 1);
      const px = fit(c, cap, 300, 19, s => `${s}px ${F.caps}`, 13);
      c.font = `${px}px ${F.caps}`;
      spaced(c, cap, mid, line + 25, 2);
    };
    side(CX - 270, tx("cert.signed"), tx("cert.mayor", { port: f.home_name || portName(f.home) }));
    side(CX + 270, f.last || "", has("voy.closed") ? t("voy.closed") : tx("cert.closed"));
    // the wax seal
    const sy = 938, r = 48;
    c.save();
    shadow(c, "rgba(0,0,0,.7)", 16, 6);
    const g = c.createRadialGradient(CX - 14, sy - 18, 4, CX, sy, r);
    g.addColorStop(0, "#3f9a7f"); g.addColorStop(.62, "#1f5f7a"); g.addColorStop(1, "#12283a");
    c.fillStyle = g; c.beginPath(); c.arc(CX, sy, r, 0, Math.PI * 2); c.fill();
    c.restore();
    c.lineWidth = 2; c.strokeStyle = BRASS; c.beginPath(); c.arc(CX, sy, r - 1, 0, Math.PI * 2); c.stroke();
    c.fillStyle = IVORY; c.font = `46px ${F.body}`;
    c.textBaseline = "middle";
    c.fillText(has("voy.seal") ? t("voy.seal") : "終", CX, sy + 2);
    c.textBaseline = "alphabetic";
  }

  /* ------------------------------------------------------- the screen -- */
  function mount() {
    el = document.createElement("div");
    el.className = "cert" + (opts.onDone ? " cert-finale" : "");
    el.setAttribute("role", "dialog");
    el.setAttribute("aria-modal", "true");
    el.setAttribute("aria-label", tx("cert.title"));
    el.innerHTML = `<div class="cert-stage"><canvas class="cert-canvas" width="${W}" height="${H}"></canvas>
        <img class="cert-img" alt="${esc(tx("cert.title"))}" hidden>
        <p class="cert-status" role="status">${esc(tx("cert.working"))}</p></div>
      <p class="cert-line" hidden></p>
      <div class="cert-actions">
        <button type="button" class="cert-btn cert-save" disabled>${esc(tx("cert.save"))}</button>
        <button type="button" class="cert-btn cert-change" disabled>${esc(tx("cert.change"))}</button>
        <button type="button" class="cert-btn cert-go primary">${esc(opts.label || tx(opts.onDone ? "cert.continue" : "cert.close"))}</button>
      </div>
      <p class="cert-hint" hidden></p>`;
    document.body.append(el);
    el.querySelector(".cert-go").addEventListener("click", finish);
    el.querySelector(".cert-save").addEventListener("click", save);
    el.querySelector(".cert-change").addEventListener("click", change);
    el.addEventListener("keydown", e => { if (e.key === "Escape" && !opts.onDone) finish(); });
    el.querySelector(".cert-go").focus({ preventScroll: true });
  }
  const q = sel => el && el.querySelector(sel);
  function status(text) {
    const s = q(".cert-status");
    if (!s) return;
    s.textContent = text || "";
    s.hidden = !text;
  }
  function hint(text) {
    const h = q(".cert-hint");
    if (!h) return;
    h.textContent = text || "";
    h.hidden = !text;
  }

  function fetchFacts(state) {
    const gid = state && state.game_id;
    if (facts && factsFor === gid) return Promise.resolve(facts);
    const tok = typeof store === "function" ? store("seatrader_token") : "";
    const url = "/api/certificate?token=" + encodeURIComponent(tok || "") + (typeof screenFamily === "function" && screenFamily() ? "&family=1" : "");
    return fetch(url).then(r => r.json()).then(r => {
      if (!r || !r.ok || !r.speakers || !r.speakers.length) return null;
      facts = r; factsFor = gid;
      return r;
    }).catch(() => null);
  }

  /* Paints the certificate onto the canvas, layer by layer, then swaps in the finished PNG. */
  async function paint(staged) {
    const me = ++run, canvas = q(".cert-canvas"), img = q(".cert-img");
    if (!canvas) return;
    busy = true;
    el.classList.remove("cert-done");
    q(".cert-save").disabled = q(".cert-change").disabled = true;
    const F = fonts(), speaker = facts.speakers[step] || facts.speakers[0];
    const seat = ((S && S.players) || []).find(p => p.id === facts.id) || (S && S.me) || {};
    const crestUrl = typeof Faces !== "undefined" ? Faces.of(Object.assign({ name: facts.name, firm: facts.firm }, seat)).crest : "";
    const badgeUrl = facts.rank_id && typeof Ranks !== "undefined" ? Ranks.url(facts.rank_id) : "";
    const [bg, mayor, persona, crest, badge] = await Promise.all([
      load((pick.bg || {}).u).then(im => im || load(HARBOR)), load((pick.mayor || {}).u).then(im => mark(im, pick.mayor)), load((pick.persona || {}).u).then(im => mark(im, pick.persona)),
      load(crestUrl), load(badgeUrl), fontsReady(F)]);
    if (me !== run || !el) return;
    const art = { crest, badge, badgeRound: /\/media\/rank\//.test(badgeUrl) };
    const c = canvas.getContext("2d");
    const wait = ms => new Promise(r => setTimeout(r, staged && !reduced() ? ms : 0));
    const layers = [
      () => paintBackdrop(c, bg),
      () => { paintPortrait(c, mayor, "left"); paintPortrait(c, persona, "right"); paintFrame(c); },
      () => paintTitle(c, F),
      () => { paintHeadline(c, F); paintWho(c, F, art); },
      () => paintFigures(c, F),
      () => paintFoot(c, F),
    ];
    status("");
    canvas.hidden = false; img.hidden = true;
    c.clearRect(0, 0, W, H);
    for (let i = 0; i < layers.length; i++) {
      c.save();
      try { layers[i](); } catch (e) { /* one layer failing never loses the rest */ }
      c.restore();
      if (me !== run || !el) return;
      if (i < layers.length - 1) await wait(STAGE_MS);
    }
    if (staged && !reduced()) { el.classList.remove("cert-thump"); void el.offsetWidth; el.classList.add("cert-thump"); }
    const blob = await new Promise(done => { try { canvas.toBlob(done, "image/png"); } catch (e) { done(null); } });
    if (me !== run || !el) return;
    if (pngUrl) URL.revokeObjectURL(pngUrl);
    pngBlob = blob; pngUrl = blob ? URL.createObjectURL(blob) : "";
    if (pngUrl) {                         // the picture itself: a long press on an iPad saves the real PNG
      await new Promise(done => { img.onload = img.onerror = done; img.src = pngUrl; });
      if (me !== run || !el) return;
      img.hidden = false; canvas.hidden = true;
    }
    busy = false;
    el.classList.add("cert-done");
    q(".cert-save").disabled = !pngUrl;
    q(".cert-change").disabled = false;
    caption(speaker);
    speak(speaker);
    remember(speaker);
  }

  function caption(speaker) {
    const p = q(".cert-line");
    if (!p) return;
    const text = family() ? speaker.family || speaker.text : speaker.text;
    if (!text) { p.hidden = true; return; }
    const name = speaker.name || castOf(speaker.who).name || "";
    p.innerHTML = `<b>${esc(name)}</b><span>${esc(text)}</span>` +
      (speaker.clip && typeof Voice !== "undefined" && Voice.enabled() ? `<button type="button" class="cert-again" aria-label="${esc(tx("cert.again"))}" title="${esc(tx("cert.again"))}">&#9834;</button>` : "");
    p.hidden = false;
    const again = p.querySelector(".cert-again");
    if (again) again.addEventListener("click", () => speak(speaker));
  }
  function speak(speaker) {
    if (!speaker || !speaker.clip || typeof Voice === "undefined") return;
    Voice.only("certificate");            // only she is heard while the certificate is open
    hush = true;
    Voice.drop("certificate");
    Voice.say([Object.assign({ tag: speaker.name || "", text: speaker.text }, speaker.clip)], { group: "certificate", front: true });
  }
  function remember(speaker) {
    const rec = { bg: last.bg, mayor: last.mayor, persona: last.persona, who: speaker.who };
    const was = facts.recipe || {};
    if (["bg", "mayor", "persona", "who"].every(k => (was[k] || "") === (rec[k] || ""))) return;
    facts.recipe = rec;
    const tok = typeof store === "function" ? store("seatrader_token") : "";
    fetch("/api/certificate", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token: tok, recipe: rec }) }).catch(() => { /* kept for this visit only */ });
  }

  function change() {
    if (busy || !facts) return;
    step = (step + 1) % facts.speakers.length;
    choose(null);
    hint("");
    paint(false);
  }

  function save() {
    if (!pngUrl || !facts) return;
    const brand = (typeof brandName === "function" && D && D.brand && brandName(D.brand)) || "Taipan Trader";
    const name = tx("cert.file", { brand, name: facts.name, date: facts.last || "" }).replace(/[\\/:*?"<>|]+/g, " ").replace(/\s+/g, " ").trim();
    const a = document.createElement("a");
    a.href = pngUrl; a.download = name + ".png"; a.rel = "noopener";
    document.body.append(a); a.click(); a.remove();
    const touch = (navigator.maxTouchPoints || 0) > 1;
    hint(touch ? tx("cert.hold") : tx("cert.saved"));
  }

  function shut() {
    run++;
    if (hush && typeof Voice !== "undefined") { Voice.drop("certificate"); Voice.only(null); }   // let the other lines go on
    hush = false;
    if (pngUrl) URL.revokeObjectURL(pngUrl);
    pngUrl = ""; pngBlob = null; busy = false;
    if (el) el.remove();
    el = null;
  }
  function finish() {
    const done = opts.onDone;
    shut();
    opts = {};
    if (done) done();
  }

  async function show(o) {
    shut();
    opts = o || {};
    S = opts.state || S; D = opts.data || D;
    mount();
    const mine = el;
    const f = await fetchFacts(S);
    if (el !== mine) return;
    if (!f) { status(tx("cert.failed")); return; }
    const recipe = f.recipe || null;
    step = Math.max(0, f.speakers.findIndex(w => recipe && w.who === recipe.who));
    last = { bg: "", mayor: "", persona: "" };
    choose(recipe);
    paint(!opts.quick);
  }

  /* ------------------------------------------------- the Certificate Studio -- */
  /* The admin's Certificate Studio (web/certificate-studio.js) paints any facts with any pictures onto a canvas
     of its own, with no screen, voice or server call. Every painter above is shared, so the studio's picture is
     the finale's picture. */
  let studioRun = 0;
  const union = (...lists) => {
    const seen = new Set(), out = [];
    lists.forEach(l => (l || []).forEach(i => { const k = i.id || i.u; if (i.u && !seen.has(k)) { seen.add(k); out.push(i); } }));
    return out;
  };
  const studio = {
    /* The library (Media.setup shape), the world (ports, goods, graphics, brand) and the money sign. */
    world(w) { D = w; },
    /* Every picture that can stand in each place for these facts and this speaker, certificate pictures first. */
    pictures(f, who) {
      const home = f.home;
      return {
        bg: union(library("port", home, "", "cert-backdrop"), plain(HARBOR)),
        mayor: union(library("port", home, "", "cert-left"), library("port", home, "mayor")),
        persona: union(library("persona", who, "", "cert-right"), library("persona", who, "portrait"), library("persona", who, "")),
      };
    },
    /* Paints the facts onto the canvas; resolves true when this is still the latest paint, false when a newer one took over. */
    async paint(canvas, f, sel) {
      const me = ++studioRun;
      facts = f;
      const F = fonts();
      const badgeUrl = f.rank_id && typeof Ranks !== "undefined" ? Ranks.url(f.rank_id) : "";
      // the House's crest from the Media Library, found by Captain and House name (Faces is in common.js)
      const crestUrl = typeof Faces !== "undefined" ? Faces.of({ name: f.name, firm: f.firm }).crest : "";
      const [bg, mayor, persona, badge, crest] = await Promise.all([
        load((sel.bg || {}).u).then(im => im || load(HARBOR)), load((sel.mayor || {}).u).then(im => mark(im, sel.mayor)), load((sel.persona || {}).u).then(im => mark(im, sel.persona)),
        load(badgeUrl), load(crestUrl), fontsReady(F)]);
      if (me !== studioRun) return false;
      facts = f;
      const art = { crest, badge, badgeRound: /\/media\/rank\//.test(badgeUrl) };
      const c = canvas.getContext("2d");
      c.clearRect(0, 0, W, H);
      [() => paintBackdrop(c, bg), () => { paintPortrait(c, mayor, "left"); paintPortrait(c, persona, "right"); paintFrame(c); },
        () => paintTitle(c, F), () => { paintHeadline(c, F); paintWho(c, F, art); }, () => paintFigures(c, F), () => paintFoot(c, F),
      ].forEach(layer => { c.save(); try { layer(); } catch (e) { /* one layer failing never loses the rest */ } c.restore(); });
      return true;
    },
    headline: () => headline(),
  };

  return {
    show,
    studio,
    open(state, data) { return show({ state, data, quick: true }); },
    close() { opts = {}; shut(); },
    isOpen: () => !!el,
    /* For the preview tool and tests: the facts to draw instead of asking the server. */
    use(f, gid) { facts = f; factsFor = gid; },
    png: () => pngBlob,
  };
})();
