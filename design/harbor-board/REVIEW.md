# Crimson Ledger Harbor Board review

Open [Chart Room](chart-room.html) and [Harbor Gazette](harbor-gazette.html) from the SeaTrader checkout. Both load the local chart renderer, fonts and configured historical artwork. The sample-state selector and layout link are review controls. The names, fortunes, notices and join address are sample data.

## Recommendation

Start with **Chart Room** for the second monitor or TV. The date and join address stay in the masthead. The turn banner answers who the game is waiting for before the eye reaches the map. The large chart retains readable port labels and ties the house flags to the same colors in the standings. Forecasts and customs notices sit together beneath it. On shorter displays, prioritize the map, standings and active hazards, then let earlier news scroll inside its panel.

Use **Harbor Gazette** if the board is primarily a room display that people glance at between turns. Larger roster space, a port image and a paper news panel make it feel like a publication from the game world. The compact chart costs legibility at TV distance. The port image slot could use the existing Board role, with a stable image during a battle or while reconnecting.

## Current screen and redesign

| Area | Current board | Proposed treatment |
| --- | --- | --- |
| Visual identity | The older board shell uses brown panels and parchment chart labels. The Player Window uses night ink, lacquer, brass seams and stronger contrast. | Carry over the Player Window's shell and active font settings. Keep the configured logo, with the masthead as a shallow image strip. Use storm blue for water, jade for orders received and oxblood for urgent states. |
| Turn and connection | The status is below the map; reconnection appears at the end of the same line. Multiple encounters can lengthen the block. | Give turn status its own band above the chart. Show a separate stale-state notice while reconnecting. During sea resolution, show each fight with its location and enemy count. |
| Standings | Rank, firm, captain, title, port, readiness and net worth compete within tightly stacked rows. A full roster and enabled gallery leave less room for news. | Lead with firm and net worth. Give the caption line to captain and port, with written status adjacent to the amount. Keep house rank titles on the final standings. The lobby emphasizes who joined and who hosts. |
| Chart and forecast | Weather appears both on the map and in the forecast. Color is the main map cue for a crackdown. | Use the chart for location and the forecast for readable weather words. Pair restricted-port markers with a list that names the banned cargo. Describe the flags as last known ports, especially during battles. |
| News and media | The gallery sits above standings and can push content down. The news panel clips its overflow. The crier reads fresh public news. | Keep the latest headline readable in full. Give earlier items a bounded area and keep the crier, mute and Quit controls reachable. Use a capped art slot in Gazette and the existing board backdrop in Chart Room. |
| End of voyage | The standings stay visible and the winner is named below the chart. | Put the winning house and the configured title in the banner. Hold the final rankings on screen. |

## What the project already supports

- **Public stream** supplies phase, date, time remaining, join URL, house firm/captain/numeric worth/rank/ship count, current port, ready/present/host, waiting names, weather, port bans and news. Battle summaries include the opposing force, destination, round and counts. Readiness should count ready houses among present houses once per update. Use the authoritative phase for transition and passive sailing states.
- **Chart and art** can use the existing chart coordinates and drawing, configured chart upload, eight house colors, historical logo and board backdrop. The media catalog already supports port image and video rotation under the Board role.
- **Voice and configuration** can use the existing news plans, local mute, translated strings, currency formatting, configurable theme and refresh-on-settings-change. The source art bible names a few different fonts from the active Player Window. The mockups use the active settings for headings, labels and body copy, with tabular Consolas figures from the bible.
- **Fair play** follows the public board view and Tally Book rules. Live market prices, cash, debt, manifest, customs desk details and planned destinations belong on the relevant player's screen or in Admin. The battle destination is already published through the public encounter summary.

## Before wiring

Use the existing board route and stream. Test an empty lobby, solo play, all eight houses at one port, missing artwork, long translations, long names and balances, an empty bulletin, multiple simultaneous fights, reconnection, and final standings. The HTML is a layout prototype. Final TV sizing should be checked on the actual display with an eight-house game and the existing mute and Quit controls.

References in this checkout include [README.md](../../README.md), [the Art Bible](../../web/art-bible.js), [Player Window styles](../../web/deck.css), [the active settings](../../config/settings.json), [the current Harbor Board](../../web/board.js), and [the public game view](../../engine.py). The README documents current scope and behavior. A separate project plan was unavailable in the checkout.
