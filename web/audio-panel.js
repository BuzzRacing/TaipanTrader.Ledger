/* The Sound tab of the Captain's Options (web/options.js asks for it).
   One switch and one volume slider per control, plus a Test button. Every control acts at once and is
   remembered on this screen only. Loaded by audio.js. */
"use strict";

const SeaAudioPanel = (() => {
  const ICON = '<path d="M4 9v6h4l5 4V5L8 9zM16 9a4 4 0 0 1 0 6M18.5 6.5a8 8 0 0 1 0 11"/>';
  // [category, label key, label, note]
  const ROWS = [
    ["master", "snd.master", "All audio", ""],
    ["system", "snd.system", "System sounds", "Buttons, coins, bells, stamps, cannon fire and timber."],
    ["music", "snd.music", "Music", "The soundtrack for the harbor, the voyage and the fight."],
    ["atmosphere", "snd.atmosphere", "Atmosphere", "Water, wind and the harbor around you."],
    ["dialogue", "snd.dialogue", "Spoken dialogue", "The voices of your crew, the Mayor and the Town Crier."],
  ];

  function html(tx) {
    tx = tx || ((k, f) => f);
    const s = SeaAudio.settings();
    let out = `<p class="op-note">${tx("snd.note", "These settings stay on this screen only. Muting everything keeps your other settings, so unmuting brings them back.")}</p>`;
    for (const [cat, key, label, note] of ROWS) {
      const c = s[cat], pct = Math.round(c.vol * 100);
      out += `<label class="op-switch"><input type="checkbox" data-snd="on" data-cat="${cat}" ${c.on ? "checked" : ""}>
          <span>${tx(key, label)}</span></label>
        <label class="op-range"><span>${tx("snd.volume", "Volume")}</span>
          <input type="range" min="0" max="100" step="5" value="${pct}" data-snd="vol" data-cat="${cat}" aria-label="${tx(key, label)}: ${tx("snd.volume", "Volume")}">
          <output>${pct}%</output></label>`;
      if (note) out += `<p class="op-note">${tx(key + "_note", note)}</p>`;
      if (cat !== "master") out += `<div class="op-row"><button type="button" data-op="snd_test" data-cat="${cat}">${tx("snd.test", "Test")}</button></div>`;
    }
    return out;
  }

  /* Returns true when the event was one of this tab's own. */
  function input(e) {
    const el = e.target, cat = el.dataset && el.dataset.cat, kind = el.dataset && el.dataset.snd;
    if (!kind || !cat) return false;
    if (kind === "on") {
      SeaAudio.set(cat, { on: el.checked });
    } else if (kind === "vol") {
      const v = Math.max(0, Math.min(100, parseInt(el.value, 10) || 0));
      SeaAudio.set(cat, { vol: v / 100 });
      const out = el.parentElement.querySelector("output");
      if (out) out.textContent = v + "%";
    }
    return true;
  }

  function click(e) {
    const b = e.target.closest && e.target.closest("[data-op=snd_test]");
    if (!b) return false;
    SeaAudio.test(b.dataset.cat);
    return true;
  }

  return { icon: ICON, html, input, click };
})();
