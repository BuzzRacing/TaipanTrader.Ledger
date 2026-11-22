"use strict";

const DashWhisper = (() => {
  const COOLDOWN_MS = 90000;
  const cue = document.getElementById("pw-whisper");
  const dialog = document.getElementById("pw-whisper-detail");
  const status = document.getElementById("whisper-status");
  const heard = new Set();
  let notice = null, persona = "gamemaster", options = {}, stamp = "", serial = 0;
  let lastTeaser = -Infinity, pending = false, blocked = false, pendingController = null, runningSubscribed = false;
  const word = key => t("dash.whisper." + key);
  const voices = () => typeof Voice !== "undefined" && Voice.enabled();
  const muted = () => !voices() || Voice.muted();
  const playing = () => voices() && Voice.current()?.group === "dash-whisper";

  function paint() {
    cue.hidden = !notice;
    const html = notice ? `<button type="button" class="whisper-note" data-whisper="read" aria-haspopup="dialog"><strong>${esc(notice.title)}</strong></button><div class="whisper-actions"><button type="button" data-whisper="read">${esc(word("read"))}</button><button type="button" data-whisper="hear" ${voices() ? "" : "disabled"}>${esc(word("hear"))}</button></div>` : "";
    if (stamp !== html) { cue.innerHTML = html; stamp = html; }
    cue.classList.toggle("speaking", voices() && ["dash-teaser", "dash-whisper"].includes(Voice.current()?.group));
    const toggle = document.getElementById("pw-voices");
    toggle.textContent = word(muted() ? "off" : "on");
    toggle.setAttribute("aria-pressed", String(!muted()));
    toggle.disabled = !voices();
    if (dialog.open && notice) {
      document.getElementById("whisper-title").textContent = notice.title;
      document.getElementById("whisper-text").textContent = notice.text;
      document.getElementById("whisper-eyebrow").textContent = "";
      document.getElementById("whisper-close").textContent = word("close");
      document.getElementById("whisper-show").textContent = word("show");
      const listen = document.getElementById("whisper-listen");
      listen.textContent = word(!voices() ? "listen" : playing() ? "stop" : muted() ? "enable" : "listen");
      listen.disabled = !voices() || pending;
    }
  }
  function stop() {
    serial++; pending = false;
    pendingController?.abort(); pendingController = null;
    if (voices()) { Voice.drop("dash-whisper"); Voice.drop("dash-teaser"); }
  }
  function sync(next, cid, state = {}) {
    blocked = !!state.blocked;
    if (next?.id !== notice?.id || cid && cid !== persona) {
      stop();
      if (dialog.open) status.textContent = word("stale");
    }
    notice = next || null; persona = cid || "gamemaster";
    if (!notice && dialog.open) dialog.close();
    paint();
    announce();
  }
  async function speak(part, automatic = false) {
    if (!notice || !voices() || automatic && muted()) return;
    if (!automatic && muted()) Voice.setMuted(false);
    const wanted = notice.id, speaker = persona, request = ++serial;
    const controller = new AbortController();
    pendingController = controller;
    const watchdog = setTimeout(() => controller.abort(), 30000);
    pending = true;
    if (!automatic) status.textContent = word("loading");
    paint();
    try {
      const query = new URLSearchParams({ persona: speaker, part });
      if (screenFamily()) query.set("family", "1");
      const response = await fetch("/api/dashboard/brief?" + query, { cache: "no-store", signal: controller.signal });
      if (!response.ok) throw new Error("Dashboard voice request: HTTP " + response.status);
      const answer = await response.json();
      if (request !== serial || notice?.id !== wanted || persona !== speaker || muted()) return;
      if (!answer.ok) throw new Error(answer.error || "Dashboard voice request failed");
      if (answer.brief?.id !== wanted) {
        sync(answer.brief, speaker, { blocked: true });
        if (dialog.open) status.textContent = word("stale");
        return;
      }
      notice = answer.brief; paint();
      if (!answer.clip) { if (!automatic) status.textContent = word("unavailable"); return; }
      // Fetching first makes a synthesis/network failure visible without replacing readable facts.
      const audio = await fetch(screenFamily() && answer.clip.f ? answer.clip.f : answer.clip.u, { signal: controller.signal });
      if (!audio.ok) throw new Error("Dashboard clip: HTTP " + audio.status);
      await audio.arrayBuffer();
      if (request !== serial || notice?.id !== wanted || persona !== speaker || muted()) return;
      Voice.say([answer.clip], { group: automatic ? "dash-teaser" : "dash-whisper", front: !automatic,
        replace: automatic ? "dash-teaser" : "dash-whisper" });
      if (automatic) {
        heard.add(wanted);
        if (heard.size > 100) heard.delete(heard.values().next().value);
      }
      if (!automatic) status.textContent = "";
    } catch (error) {
      console.error("Dashboard persona voice:", error);
      if (request === serial && !automatic) status.textContent = word("failed");
    } finally {
      clearTimeout(watchdog);
      if (pendingController === controller) pendingController = null;
      if (request === serial) { pending = false; paint(); }
    }
  }
  function announce() {
    if (!notice || blocked || dialog.open || pending || muted() || Voice.busy()
        || typeof SeaAudio !== "undefined" && !SeaAudio.running()
        || heard.has(notice.id) || Date.now() - lastTeaser < COOLDOWN_MS) return;
    lastTeaser = Date.now();
    speak("teaser", true);
  }
  function open(aloud) {
    if (!notice) return;
    heard.add(notice.id);
    stop(); status.textContent = "";
    if (!dialog.open) dialog.showModal();
    paint();
    if (!voices()) status.textContent = word("unavailable");
    if (aloud) speak("detail");
  }
  cue.addEventListener("click", event => {
    const button = event.target.closest("[data-whisper]");
    if (button) open(button.dataset.whisper === "hear");
  });
  document.getElementById("whisper-close").addEventListener("click", () => dialog.close());
  dialog.addEventListener("close", () => { stop(); options.closed?.(); });
  document.getElementById("whisper-listen").addEventListener("click", () => {
    if (playing() || pending) { stop(); paint(); } else speak("detail");
  });
  document.getElementById("whisper-show").addEventListener("click", () => {
    const target = notice?.target;
    dialog.close();
    if (target) options.navigate?.(target);
  });
  document.getElementById("pw-voices").addEventListener("click", () => {
    if (!voices()) return;
    const off = !Voice.muted();
    if (off) stop();
    Voice.setMuted(off); paint();
    if (!off) announce();
  });
  return {
    sync, isOpen: () => dialog.open,
    setup(config) {
      options = config || {}; Voice.onChange(paint);
      if (!runningSubscribed && typeof SeaAudio !== "undefined") { SeaAudio.onRunning(announce); runningSubscribed = true; }
      paint();
    },
  };
})();
