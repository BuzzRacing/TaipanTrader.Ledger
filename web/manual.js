"use strict";

/* THE CAPTAIN'S MANUAL (/Manual, 21 Nov 2026). A leather-bound book with one image tab per major part of the
   game. Left page: the chapter's persona, a line from her bank, then how it works, how to win and what to
   watch for. Right page: the practice bench (filled in chapter by chapter; Phase 1 is the book itself).

   - Only a captain with a seat can open it: the page sends the seat token the game screen keeps, and the
     server (manual_feed.view) answers with the layout or a short refusal.
   - All wording ("man.*") comes from /api/info like the rest of the game, so Admin > Language & Text edits it
     and a Family-friendly screen gets the family wording. Nothing is hard-coded here.
   - Voice is the player's own switch (default off). When it is on, opening a chapter or pressing "Another
     line" asks the server for that one line's clip and plays it through the game's Voice module, so a line is
     only recorded when somebody wants to hear it.
   - Persona pictures come from the Media Library (Media.speaker, tagged "help" first), else her cast portrait,
     else her initials. */
const KEY_VOICE = "seatrader_manual_voice";
const KEY_CHAPTER = "seatrader_manual_chapter";
const M = {
  token: store("seatrader_token") || "",
  info: null, cast: {}, book: null, chapter: "cover",
  voiceOn: store(KEY_VOICE) === "1", voiceReady: false,
  bag: {}, said: "", saidKey: "",
};
const app = document.getElementById("app");
const famQ = () => (screenFamily() ? "&family=1" : "");

function gate(message) {
  app.innerHTML = `<div class="mn-gate"><div><h1>${esc(t("man.title"))}</h1><p>${esc(message)}</p>
    <a class="mn-btn" href="/">${esc(t("man.back"))}</a></div></div>`;
}

function monogram(name) {
  return String(name || "?").replace(/[“”"']/g, "").split(/\s+/).filter(Boolean).slice(0, 2).map(w => w[0]).join("").toUpperCase();
}

/* A persona's face: her "help" picture, else any picture of her, else her cast portrait, else initials. */
function face(cid, cls) {
  const c = M.cast[cid] || {};
  let html = "";
  try { html = (typeof Media !== "undefined" && Media.speaker) ? (Media.speaker(cid, cls, "help") || "") : ""; } catch (e) { html = ""; }
  if (!html && c.portrait) html = `<img class="${cls}" src="${esc(c.portrait)}" alt="">`;
  return html || `<i>${esc(monogram(c.name))}</i>`;
}

/* The next line of a bank: shuffled, and none repeats until all have been heard. */
function pick(ch, moment) {
  const keys = (ch.bank && ch.bank[moment]) || [];
  if (!keys.length) return "";
  const id = ch.id + ":" + moment;
  let bag = M.bag[id];
  if (!bag || !bag.length) {
    bag = keys.slice();
    for (let i = bag.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [bag[i], bag[j]] = [bag[j], bag[i]]; }
    if (bag.length > 1 && bag[bag.length - 1] === M.saidKey) bag.unshift(bag.pop());   // never the line just heard, first
  }
  M.bag[id] = bag;
  return bag.pop();
}

function chapter() { return (M.book.chapters || []).find(c => c.id === M.chapter) || M.book.chapters[0]; }

function voiceUsable() {
  const v = M.info && M.info.voice;
  return !!(v && v.enabled);
}

/* Play one line, if the player has voices on and the table has voice switched on. */
async function hear(key) {
  if (!M.voiceOn || !key || !voiceUsable()) return;
  try {
    const r = await (await fetch("/api/manual/say?token=" + encodeURIComponent(M.token) + "&key=" + encodeURIComponent(key) + famQ())).json();
    if (r && r.ok && r.item) {
      if (typeof Voice.setMuted === "function" && Voice.muted && Voice.muted()) Voice.setMuted(false);
      Voice.say([r.item], { group: "manual", replace: "manual", front: true });
    }
  } catch (e) { /* the line stays on the page as text */ }
}

function say(ch, speak) {
  const key = pick(ch, "open");
  M.saidKey = key;
  const el = document.getElementById("mn-say");
  if (el) el.textContent = key ? t(key) : "";
  if (speak) hear(key);
}

function tabHtml(c) {
  const p = M.cast[c.who] || {};
  const lvl = c.ready ? (c.level ? t("man.level." + c.level) : "") : t("man.soon");
  return `<button type="button" class="mn-tab${c.id === M.chapter ? " on" : ""}${c.ready ? "" : " soon"}" data-ch="${esc(c.id)}"
      style="--who:${esc(p.color || "#c9a34e")}" aria-current="${c.id === M.chapter ? "page" : "false"}">
      <span class="mn-face">${face(c.who, "mn-art")}</span><span><b>${esc(t("man." + c.id + ".tab"))}</b>${lvl ? `<em>${esc(lvl)}</em>` : ""}</span></button>`;
}

function leftPage(c) {
  const p = M.cast[c.who] || {};
  let h = `<div class="mn-who" style="--who:${esc(p.color || "#c9a34e")}">
      <div class="mn-keeper">${face(c.who, "mn-art")}</div>
      <div><div class="mn-kicker">${esc(t("man." + c.id + ".kicker"))}</div>
        <h2>${esc(t("man." + c.id + ".title"))}</h2>
        <div class="mn-name">${esc(p.name || "")}${p.title ? " · " + esc(p.title) : ""}</div>
        <p class="mn-say" id="mn-say"></p>
        <div class="mn-say-tools">
          <button type="button" class="mn-btn" id="mn-another">${esc(t("man.another"))}</button>
          <button type="button" class="mn-btn" id="mn-hear">${esc(t("man.hear"))}</button>
        </div>
        <p class="mn-note" id="mn-vnote" hidden>${esc(t("man.voice_unavailable"))}</p>
      </div></div>`;
  if (!c.ready) return h + `<p class="mn-soon">${esc(t("man.chapter_soon"))}</p>`;
  h += `<h3>${esc(t("man.how"))}</h3><ol class="mn-how">`;
  for (let i = 0; i < c.how; i++) h += `<li>${esc(t("man." + c.id + ".how." + i))}</li>`;
  h += `</ol><p class="mn-tip"><b>${esc(t("man.win"))}.</b> ${esc(t("man." + c.id + ".win"))}</p>
        <p class="mn-warn"><b>${esc(t("man.watch"))}.</b> ${esc(t("man." + c.id + ".watch"))}</p>`;
  const fb = (M.book.forbidden || []);
  if (c.id === "market" && fb.length) {
    h += `<h3>${esc(t("man.forbid.title"))}</h3><p class="mn-note">${esc(t("man.forbid.note"))}</p>
      <table class="mn-forbid"><tbody>${fb.map(r => `<tr><th>${esc(r.port)}</th><td>${r.goods.map(esc).join(", ")}</td></tr>`).join("")}</tbody></table>`;
  }
  const tb = (M.book.tiers || []);
  if (c.id === "market" && tb.length) {
    h += `<h3>${esc(t("man.tiers.title"))}</h3><p class="mn-note">${esc(t("man.tiers.note"))}</p>
      <table class="mn-forbid mn-tiers"><tbody>${tb.map(r => `<tr${r.here ? ' class="mn-here"' : ""}><th>${esc(r.rank || t("man.tiers.start"))}${r.here ? ` <small>${esc(t("man.tiers.here"))}</small>` : ""}</th><td>${r.goods.map(esc).join(", ")}</td></tr>`).join("")}</tbody></table>`;
  }
  return h;
}

function rightPage(c) {
  const title = t("man." + c.id + ".bench_title");
  const known = title !== "man." + c.id + ".bench_title";
  return `<div class="mn-bench"><h2>${esc(known ? title : t("man.bench"))}</h2>
    <div class="mn-bench-frame"><p>${esc(c.ready ? t("man.bench_soon") : t("man.chapter_soon"))}</p></div></div>`;
}

function draw(turn) {
  const c = chapter();
  const name = M.book.name || "";
  app.innerHTML = `<div class="mn${turn ? " mn-turning" : ""}">
    <header class="mn-head"><div><h1>${esc(t("man.title"))}</h1><small>${esc(t("man.subtitle"))}${name ? " · " + esc(name) : ""}</small></div>
      <div class="mn-tools">
        <button type="button" class="mn-btn" id="mn-voice" aria-pressed="${M.voiceOn ? "true" : "false"}" title="${esc(t("man.voice_hint"))}">${M.voiceOn ? "🔊 " + esc(t("man.voice_on")) : "🔇 " + esc(t("man.voice_off"))}</button>
        <a class="mn-btn" href="/">${esc(t("man.back"))}</a></div></header>
    <div class="mn-body"><nav class="mn-tabs" aria-label="${esc(t("man.title"))}">${M.book.chapters.map(tabHtml).join("")}</nav>
      <div class="mn-book"><section class="mn-page mn-left">${leftPage(c)}</section><section class="mn-page mn-right">${rightPage(c)}</section></div></div></div>`;
  wire(c);
  say(c, turn);
}

function wire(c) {
  app.querySelectorAll(".mn-tab").forEach(b => b.addEventListener("click", () => open(b.dataset.ch)));
  document.getElementById("mn-another").addEventListener("click", () => say(c, true));
  document.getElementById("mn-hear").addEventListener("click", () => {
    const note = document.getElementById("mn-vnote");
    if (!voiceUsable()) { note.textContent = t("man.voice_unavailable"); note.hidden = false; return; }
    if (!M.voiceOn) { note.textContent = t("man.voice_turn_on"); note.hidden = false; return; }
    note.hidden = true;
    hear(M.saidKey);
  });
  document.getElementById("mn-voice").addEventListener("click", () => {
    M.voiceOn = !M.voiceOn;
    store(KEY_VOICE, M.voiceOn ? "1" : null);
    if (!M.voiceOn && typeof Voice.stop === "function") Voice.stop();
    const b = document.getElementById("mn-voice");
    b.setAttribute("aria-pressed", M.voiceOn ? "true" : "false");
    b.textContent = M.voiceOn ? "🔊 " + t("man.voice_on") : "🔇 " + t("man.voice_off");
    const note = document.getElementById("mn-vnote");
    if (M.voiceOn) {
      note.textContent = t("man.voice_unavailable");
      note.hidden = voiceUsable();
      hear(M.saidKey);
    } else note.hidden = true;
  });
}

/* The switch is the player's control: with it off nothing is ever spoken, "Hear it" included. */
function open(id) {
  if (id === M.chapter && document.querySelector(".mn")) return;
  M.chapter = id;
  store(KEY_CHAPTER, id);
  draw(true);
}

async function boot() {
  try {
    M.info = await loadInfo();
    Voice.setup(M.info.voice);
    M.cast = (M.info.voice && M.info.voice.cast) || {};
  } catch (e) { gate("…"); return; }
  if (!M.token) { gate(t("man.e_seat")); return; }
  let r;
  try { r = await (await fetch("/api/manual?token=" + encodeURIComponent(M.token) + famQ())).json(); }
  catch (e) { gate(t("man.e_gate")); return; }
  if (!r || !r.ok) { gate((r && r.error) || t("man.e_seat")); return; }
  M.book = r;
  const wanted = store(KEY_CHAPTER);
  if (wanted && r.chapters.some(c => c.id === wanted)) M.chapter = wanted;
  draw(false);
}
boot();
