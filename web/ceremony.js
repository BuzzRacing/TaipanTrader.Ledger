"use strict";

const Ceremony = (() => {
  const openingLength = 11000;
  const finaleLength = 9000;
  let scene, sceneKey, dismissedKey, timer, behind;

  function close() {
    clearTimeout(timer);
    if (behind) behind.inert = false;
    scene?.remove();
    scene = behind = sceneKey = null;
  }

  function story(state, ports) {
    const voyage = state.voyage_story;
    if (!voyage) return "";
    const port = key => ports[key]?.name || key;
    const route = voyage.route;
    return `<h2>${te("ceremony.story")}</h2>
      <p>${te("ceremony.final_port", { name: voyage.name, firm: voyage.firm, port: port(voyage.port) })}</p>
      <ul class="story-facts">
        ${route ? `<li>${te("ceremony.route", { from: port(route.from), to: port(route.to), date: route.date })}</li>` : ""}
        <li>${te("ceremony.fleet", { ships: voyage.ships })}</li>
      </ul>`;
  }

  function ranked(state) {
    const first = state.voyage_story?.id;
    return state.players.slice().sort((a, b) =>
      Number(b.id === first) - Number(a.id === first) || b.worth - a.worth);
  }

  function play(kind, elapsed, state, data, app) {
    const clock = performance.now() - Math.max(0, elapsed);
    scene = document.createElement("div");
    scene.className = "ceremony";
    scene.dataset.scene = kind;
    scene.style.setProperty("--elapsed", Math.max(elapsed, 0) + "ms");
    scene.innerHTML = `<div class="scenery" aria-hidden="true"><div class="harbor"></div>
      <div class="clipper"><img src="/assets/ceremony-clipper.png" alt=""></div>
      <div class="mist"></div><div class="shade"></div></div><div class="frame"></div>`;
    document.body.append(scene);
    behind = app;
    behind.inert = true;
    const frame = scene.querySelector(".frame");
    const after = (target, next) => { timer = setTimeout(next, Math.max(0, target - (performance.now() - clock))); };

    if (kind === "opening") {
      frame.innerHTML = `<div class="wordmark"><h1 class="title">${esc(brandName(data.brand))}</h1>
        <div class="rule" aria-hidden="true">◆</div></div>
        <p class="place">${te("ceremony.opening")}</p><p class="cue" role="status"></p>`;
      const cue = frame.querySelector(".cue");
      function count() {
        const remaining = openingLength - (performance.now() - clock);
        if (remaining <= 0) {
          cue.textContent = t("ceremony.departing");
        } else if (remaining <= 3000) {
          const number = Math.ceil(remaining / 1000);
          cue.innerHTML = `<span class="count">${number}</span>`;
          after(openingLength - (number - 1) * 1000, count);
        } else {
          after(openingLength - 3000, count);
        }
      }
      count();
      return;
    }

    const standings = ranked(state);
    const winner = standings[0];
    frame.innerHTML = `<h1 class="title">${te("ceremony.finale")}</h1>
      <p class="place">${esc(state.date)}</p>`;
    function revealWinner() {
      frame.innerHTML = `<div class="winner" role="status"><p>${te("ceremony.winner")}</p>
        <h2>${esc(winner.firm)}</h2>
        <p>${te("ceremony.winner_detail", { name: winner.name, worth: money(winner.worth) })}</p></div>`;
      after(finaleLength, revealLedger);
    }
    function revealLedger() {
      scene.classList.add("has-results");
      frame.innerHTML = `<article class="ledger">
        <section>${story(state, data.ports)}</section>
        <section><h2>${te("ceremony.standings")}</h2><table><thead>
          <tr><th scope="col">${te("ceremony.house")}</th><th scope="col">${te("ceremony.worth")}</th></tr></thead>
          <tbody>${standings.map((house, i) =>
            `<tr><td>${i + 1}. ${esc(house.firm)}</td><td>${esc(money(house.worth))}</td></tr>`).join("")}</tbody>
        </table></section></article>
        <div class="actions"><button class="details" type="button">${te("ceremony.details")}</button>
        ${state.me ? `<button class="details free-play" type="button">${te("ceremony.free_play")}</button>` : ""}</div>`;
      const button = frame.querySelector("button.details");
      button.addEventListener("click", () => { dismissedKey = sceneKey; close(); });
      frame.querySelector("button.free-play")?.addEventListener("click", () => {
        dismissedKey = sceneKey; close();
        window.dispatchEvent(new CustomEvent("ceremony:free-play"));
      });
      button.focus({ preventScroll: true });
    }
    if (elapsed >= 5500) revealWinner();
    else after(5500, revealWinner);
  }

  function sync(state, data, app) {
    const watching = state.me || app.classList.contains("board-room");
    const opening = watching && state.phase === "lobby" && state.start_at;
    const ending = watching && (state.phase === "ended" || state.free_play) && state.ended_at && state.voyage_story;
    const key = opening ? state.game_id + ":start:" + state.start_at
      : ending ? state.game_id + ":end:" + state.ended_at : null;
    if (scene && sceneKey === key) {
      if (opening) {
        const heading = scene.querySelector(".wordmark h1");
        const name = brandName(data.brand);
        if (heading.textContent !== name) heading.textContent = name;
      }
      return;
    }
    close();
    if (!key || key === dismissedKey) return;
    const elapsed = opening ? openingLength - (state.start_at - state.server_time) * 1000
      : (state.server_time - state.ended_at) * 1000;
    if (ending && elapsed >= finaleLength) return;
    sceneKey = key;
    play(opening ? "opening" : "finale", elapsed, state, data, app);
  }

  return { sync, story, ranked };
})();
