/* Where the game tells the mixer what is happening (web/audio.js does the playing).

   - sync(S, opts) runs at the end of every redraw. It names the scene (lobby, port, voyage, finale) and keeps
     overlays (battle, jail, storm, the Port Authority desk) on top of it while they are on screen. Calling it again with the same
     state changes nothing, so a redraw never restarts the music.
   - acted(type, res) and ran(done, last) run from the REPLY to the player's own action, so a poll, a redraw
     or a reconnect can never replay a cue. A refused action gets the low knock, whatever it was.
   - A Legend (web/legend.js) pushes the "legend" scene: its own music and bed over the port's, and four cues
     (legend.bell on opening, legend.choose on a road, legend.reckon on the reckoning card, legend.close on leaving).
   - Every button press gets a soft tick; tabs get their own. No hover sounds. */
"use strict";

const Soundscape = (() => {
  const mixer = () => (typeof SeaAudio !== "undefined" ? SeaAudio : null);
  const QUIET = new Set(["settings", "storm_ack", "free_play"]);       // no result cue: the screen change is the answer
  const ORDERS = new Set(["sail", "unsail", "stay", "slip", "recall"]);
  let lastTurn = null;
  const shown = new Set();
  let fightScene = "";             // which overlay the sea battle has on: "suspense" or "battle"
  let legendMode = null, legendSeen = false;   // the Legend screen's state last time round; null = not on screen

  function sceneFor(S) {
    const p = S && S.phase;
    return !p || p === "lobby" ? "lobby" : p === "ended" ? "finale" : p === "sea" ? "voyage" : "port";
  }

  const legendScreen = () => document.getElementById("legend-screen");

  /* A Legend has its own music and night-sea bed over the port, and a few cues of its own. It runs from sync() and
     on a short timer, because the story moves on by its own timers (the reckoning card appears with no redraw of
     the game). Not on the first look this screen takes (a reload in the middle of a story), so a redraw or a
     reconnect never rings the bell again. */
  function watchLegend() {
    const a = mixer();
    if (!a) return;
    const lg = legendScreen(), mode = lg ? lg.dataset.mode || "line" : null;
    if (mode !== legendMode) {
      if (legendSeen) {
        if (mode && !legendMode) a.play("legend.bell");
        else if (mode === "reckon") a.play("legend.reckon");
        else if (!mode) a.play("legend.close");
      }
      if (!!mode !== !!legendMode) { if (mode) a.push("legend"); else a.pop("legend"); }
      legendMode = mode;
    } else if (mode && !legendSeen) a.push("legend");     // a reload in the middle of a story: music, but no bell
    legendSeen = true;
  }
  setInterval(watchLegend, 400);

  function sync(S, opts) {
    const a = mixer();
    if (!a || !S) return;
    watchLegend();
    opts = opts || {};
    a.scene(sceneFor(S));
    for (const [name, on] of [["storm", opts.storm], ["jail", opts.jail], ["desk", opts.desk]]) {
      if (on && !shown.has(name)) { shown.add(name); a.push(name); }
      else if (!on && shown.has(name)) { shown.delete(name); a.pop(name); }
    }
    // The sea battle: the suspense bed while the price is weighed, the battle music while guns fire.
    const want = opts.battle ? ((typeof Battle !== "undefined" && Battle.mood && Battle.mood()) || "battle") : "";
    if (want !== fightScene) {
      if (fightScene) a.pop(fightScene);
      if (want) a.push(want);
      fightScene = want;
    }
    // The ship's bell for a new month: not on the first state this screen sees (a reload or a reconnect).
    if (opts.bell && S.turn !== undefined && S.phase === "port") {
      if (lastTurn !== null && S.turn !== lastTurn) a.playOnce("turn:" + S.turn, "turn.new");
      lastTurn = S.turn;
    }
  }

  function acted(type, res) {
    const a = mixer();
    if (!a || !res) return;
    if (!res.ok) { a.play("action.refused"); return; }
    if (QUIET.has(type)) return;
    a.play(type === "buy" ? "trade.buy.success" : type === "sell" ? "trade.sell.success"
      : ORDERS.has(type) ? "orders.submitted" : "ui.confirm");
  }

  /* A run of lined-up trades makes one cue, not one per trade. */
  function ran(done, last, side) {
    const a = mixer();
    if (!a || !last) return;
    if (!last.ok) { a.play("action.refused"); return; }
    a.play(done > 1 ? "trade.run.summary" : side === "sell" ? "trade.sell.success" : "trade.buy.success");
  }

  document.addEventListener("click", e => {
    const a = mixer();
    const t = e.target && e.target.closest && e.target.closest("button, [role=tab], [role=button]");
    if (!a || !t || t.disabled || t.id === "audio-enable" || t.dataset.op === "snd_test") return;
    a.play(t.closest("#seafight") ? "battle.select" : t.closest("#legend-screen") ? "legend.choose" : t.getAttribute("role") === "tab" ? "ui.tab" : "ui.click");
  }, true);

  return { sync, acted, ran };
})();
