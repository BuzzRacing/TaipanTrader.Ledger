/* The Sound tab of the Captain's Options (web/options.js asks for it).
   One compact mixer: a switch, a volume slider and a Test button per channel on a single line, then three
   extras (Night mode, lowering the music while someone speaks, Full or Brief dialogue). Every control acts
   at once and is remembered on this screen only. Loaded by audio.js. */
"use strict";

const SeaAudioPanel = (() => {
  const ICON = '<path d="M4 9v6h4l5 4V5L8 9zM16 9a4 4 0 0 1 0 6M18.5 6.5a8 8 0 0 1 0 11"/>';
  // [category, label key, label, note]
  const ROWS = [
    ["master", "snd.master", "All audio", "Muting keeps your other settings."],
    ["system", "snd.system", "System sounds", "Buttons, coins, bells, cannon fire."],
    ["music", "snd.music", "Music", "The harbor, the voyage and the fight."],
    ["atmosphere", "snd.atmosphere", "Atmosphere", "Water, wind and the harbor."],
    ["dialogue", "snd.dialogue", "Spoken dialogue", "Your crew, the Mayor, the Town Crier."],
  ];
  // [option, label key, label, note]
  const OPTS = [
    ["night", "snd.night", "Night mode", "Evens out loud sounds, so a cannon never startles the room."],
    ["duck", "snd.duck", "Lower the music while people speak", "Music and atmosphere ease down under spoken lines."],
  ];

  function html(tx) {
    tx = tx || ((k, f) => f);
    const s = SeaAudio.settings();
    const row = ([cat, key, label, note]) => {
      const c = s[cat], pct = Math.round(c.vol * 100), name = tx(key, label);
      return `<div class="snd-row${cat === "master" ? " snd-row--master" : ""}${c.on ? "" : " off"}">
        <label class="snd-sw"><input type="checkbox" data-snd="on" data-cat="${cat}" ${c.on ? "checked" : ""} aria-label="${name}"></label>
        <div class="snd-name"><b>${name}</b><small>${tx(key + "_note", note)}</small></div>
        <label class="snd-vol"><input type="range" min="0" max="100" step="5" value="${pct}" data-snd="vol" data-cat="${cat}" aria-label="${name}: ${tx("snd.volume", "Volume")}">
          <output>${pct}%</output></label>
        ${cat === "master" ? "<span></span>" : `<button type="button" class="snd-test" data-op="snd_test" data-cat="${cat}">${tx("snd.test", "Test")}</button>`}</div>`;
    };
    let out = `<div class="snd-mix">${ROWS.map(row).join("")}</div><div class="snd-opts">`;
    for (const [opt, key, label, note] of OPTS) {
      out += `<div class="snd-row snd-row--opt">
        <label class="snd-sw"><input type="checkbox" data-snd="opt" data-opt="${opt}" ${SeaAudio.option(opt) ? "checked" : ""} aria-label="${tx(key, label)}"></label>
        <div class="snd-name"><b>${tx(key, label)}</b><small>${tx(key + "_note", note)}</small></div></div>`;
    }
    if (typeof Voice !== "undefined" && Voice.setBrief) {
      const brief = !!(Voice.brief && Voice.brief());
      const btn = (val, key, text) => `<button type="button" data-op="snd_brief" data-val="${val}" aria-pressed="${(val === "1") === brief}">${tx(key, text)}</button>`;
      out += `<div class="snd-row snd-row--pick"><div class="snd-name"><b>${tx("opt.dialogue", "Dialogue")}</b>
          <small>${tx("snd.brief_note", "Brief reads only the first few lines of each batch aloud. Every line stays on screen.")}</small></div>
        <div class="op-seg" role="group" aria-label="${tx("opt.dialogue", "Dialogue")}">${btn("0", "opt.dialogue_full", "Full")}${btn("1", "opt.dialogue_brief", "Brief")}</div></div>`;
    }
    return out + `</div><p class="op-note snd-foot">${tx("snd.note", "These settings stay on this screen only.")}</p>`;
  }

  /* Returns true when the event was one of this tab's own. */
  function input(e) {
    const el = e.target, cat = el.dataset && el.dataset.cat, kind = el.dataset && el.dataset.snd;
    if (kind === "opt") { SeaAudio.setOption(el.dataset.opt, el.checked); return true; }
    if (!kind || !cat) return false;
    if (kind === "on") {
      SeaAudio.set(cat, { on: el.checked });
      const row = el.closest(".snd-row");
      if (row) row.classList.toggle("off", !el.checked);
    } else if (kind === "vol") {
      const v = Math.max(0, Math.min(100, parseInt(el.value, 10) || 0));
      SeaAudio.set(cat, { vol: v / 100 });
      const out = el.parentElement.querySelector("output");
      if (out) out.textContent = v + "%";
    }
    return true;
  }

  function click(e) {
    const b = e.target.closest && e.target.closest("[data-op^=snd_]");
    if (!b) return false;
    if (b.dataset.op === "snd_test") SeaAudio.test(b.dataset.cat);
    else if (b.dataset.op === "snd_brief" && typeof Voice !== "undefined" && Voice.setBrief) Voice.setBrief(b.dataset.val === "1");
    return true;
  }

  return { icon: ICON, html, input, click };
})();
