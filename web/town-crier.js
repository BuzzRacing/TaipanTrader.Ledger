"use strict";

const TownCrier = (() => {
  const acknowledged = new Set();
  let dialog = null, showing = null;

  function close() {
    if (dialog) { dialog.close(); dialog.remove(); }
    dialog = showing = null;
  }

  function sync(state, data, canShow) {
    const left = state.turns_left;
    const eligible = state.me && state.game_id && state.phase === "port" && !state.free_play
      && Number.isInteger(left) && left > 0 && left <= 10;
    const key = eligible ? state.game_id + ":" + state.me.id : null;
    if (!eligible || (dialog && showing !== key)) close();
    if (!eligible || dialog || !canShow || acknowledged.has(key) || store("seatrader_crier_ack:" + key) === "1") return;

    const art = Media.choose("persona", "crier", "portrait", { mode: "fixed", slot: "closing-notice" });
    const total = Math.round(state.years * 12);
    const date = t("mon." + ((total - 1) % 12)) + " " + (data.start_year + Math.floor((total - 1) / 12));
    showing = key;
    dialog = document.createElement("dialog");
    dialog.className = "tc-alert";
    dialog.setAttribute("aria-labelledby", "tc-title");
    dialog.setAttribute("aria-describedby", "tc-message");
    dialog.innerHTML = `<section class="tc-card" tabindex="-1" autofocus>
      <figure class="tc-portrait">${art ? `<img src="${esc(art.u)}" alt="">` : `<span class="tc-no-art" aria-hidden="true">❧</span>`}
        <figcaption><span>${te("crier_alert.proclamation")}</span><strong>${te("crier_alert.speaker")}</strong></figcaption></figure>
      <div class="tc-content">
        <p class="tc-eyebrow"><svg viewBox="0 0 24 28" aria-hidden="true"><path d="M5 20h14l-2-4v-6a5 5 0 0 0-10 0v6zM10 23q2 4 4 0M12 2v3M3 7 1 5m20 2 2-2"/></svg>${te("crier_alert.hear")}</p>
        <h2 id="tc-title">${te("crier_alert.title")}</h2><div class="tc-ornament" aria-hidden="true">◆</div>
        <div class="tc-count">${left}</div><p class="tc-months">${te(left === 1 ? "crier_alert.month" : "crier_alert.months")}</p>
        <blockquote id="tc-message">“${te(left === 1 ? "crier_alert.quote_one" : "crier_alert.quote", { n: left === 10 ? t("crier_alert.ten") : left })}”</blockquote>
        <p class="tc-detail">${te("crier_alert.detail")}</p>
        <button type="button" class="tc-continue">${te("crier_alert.continue")} <span aria-hidden="true">→</span></button>
        <p class="tc-date">${te("voy.close", { date })}</p>
      </div>
    </section>`;
    const dismiss = () => {
      acknowledged.add(key);
      store("seatrader_crier_ack:" + key, "1");
      close();
    };
    dialog.querySelector("button").addEventListener("click", dismiss);
    dialog.addEventListener("cancel", event => { event.preventDefault(); dismiss(); });
    document.body.appendChild(dialog);
    dialog.showModal();
  }

  return { sync };
})();
