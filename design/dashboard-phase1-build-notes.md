# Captain's Command Center — build notes (Phases 0 to 4)

**Project:** Crimson Ledger / SeaTrader
**Built:** 22 November 2026
**Plan:** [dashboard-captain-command-center-plan.md](dashboard-captain-command-center-plan.md)
**Source map:** [dashboard-phase0-field-inventory.md](dashboard-phase0-field-inventory.md)
**Status:** On this PC only. Not deployed to the Pi. Waiting for Anthony's review.

## What changed

| File | Change |
|---|---|
| `dashboard_feed.py` | New `context` block in `/api/dashboard`: date, months left, each sea's forecast, forecast accuracy, and (open solo game only) the Captain's port, destination, worth, change this month, rank and fleet condition |
| `web/dashboard-tabs.js` | New. The eight tabs, the five new pages, the context bar, Watch Mode's timing rule, the drawer |
| `web/dashboard.js` | Routes eight tabs instead of three pages; Watch Mode; touch, swipe, drawer and pin; tall-screen layout; nothing is polled or turned while the window is hidden |
| `web/dashboard.html` | Tab row under the masthead, context bar in the masthead, drawer dialog |
| `web/dashboard.css` | Styles for all of the above, appended at the end |
| `tests/dashboard_fixtures.py` | New. Deterministic games: lobby, early, middle, late, rivals |
| `tests/dashboard_privacy_test.py` | New. Sentinel and trap privacy checks, no-mutation, context bar, size budget, repeatability |
| `tests/dashboard_tabs_test.cjs` | New. Tabs, Watch Mode timing, pages, sealed pages, escaping |
| `tools/preview_command_center.py` | New. The real server on a fixture game, sandboxed |

No game rule, no saved game and no wording in `strings.py` was touched. `server.py`, `engine.py` and `config.py` are unchanged.

## The eight tabs today

| Tab | What it shows in this build | Still to come |
|---|---|---|
| Now | Net worth and change, months left, fleet, worst sea, running booms, bans, latest wire | Ranked alerts (Phase 7) |
| Atlas | The existing Sea Lanes page | Standing, shares, warehouses, dossiers (Phase 4) |
| Trade | The existing Markets & Booms page | Basis, purses, tips, opportunities (Phase 5) |
| Weather | This month's forecast on the chart and by sea, forecast accuracy, the rules' storm chance by level | Route exposure, history (Phase 3) |
| Fleet | Hull condition ship by ship, storms and fights from the wire | Names, guns, holds, wages, repairs (Phase 6) |
| Treasury | Net worth month by month, best and worst month | Balance sheet, bank tiers, debt, costs (Phase 6) |
| Career | The existing Race page with the ghost | Rank progress, honours, commissions (Phase 6) |
| Wire | Every recorded event, newest first; this month on the right | Filters (Phase 7) |

The timing tower, dials, chalkboard and telegraph tape are still in place around the stage. They fold into the tabs as those tabs are built (decision C).

## Watch Mode

- On by default. 12 seconds a tab, all eight in order.
- Any touch, key or scroll holds the page; the tour picks up again 60 seconds after the last one.
- Pin tab holds it until unpinned. An open dialog or a hidden window also holds it.
- The Watch Mode button turns it off and on for this screen. All tabs opens the drawer: jump to a tab, or untick a tab to leave it out of the tour. Both choices are kept on this device only.
- A new sea fight or boom still pulls the page, but not while the Captain is touching the screen.
- A sideways swipe on the stage turns one tab.

## With rivals at the table

All eight tabs stay in the bar. Trade is sealed; Treasury shows the public worth table and seals the books. The context bar shows table-wide chips (houses, leader, worst sea) and never one house's position.

## Checks run

| Check | Result |
|---|---|
| `python tests/dashboard_privacy_test.py` | Pass |
| `python tests/dashboard_test.py` | Pass |
| `python tests/dashboard_brief_test.py` | Pass |
| `python tests/harbor_view_test.py` | Pass |
| `node tests/dashboard_tabs_test.cjs` | Pass |
| `node tests/dashboard_ui_test.cjs` | Pass |
| `node tests/dashboard_whisper_test.cjs` | Pass |
| Browser, 1366x1024, 1920x1080, 768x1024 | All eight tabs draw; no sideways overflow; tabs and buttons at least 44 px tall |
| Browser, live Watch Mode | Turned at 12 s untouched; held after a touch; off, on, pin, swipe, chip and drawer all behaved |

These ran in a cloud copy of the code with this folder's settings, without the Media Library pictures, so persona art, the chart background and voice were not seen. The rest of the test suite was not run.

Feed sizes on the fixtures (default rules): lobby 3.7 KB, early 11.4 KB, middle 22.2 KB, late (200 months) 48.9 KB, rivals 8.9 KB. Budget is 100 KB.

## How to look at it

- Live copy: start the test server (`Launch_Dev.bat`) and open `/dashboard`.
- Any state without touching a game: `python tools/preview_command_center.py --fixture late` then open `http://localhost:18890/dashboard`. Fixtures: `lobby`, `early`, `middle`, `late`, `rivals`.

## Known gaps

- Upright tablet: the tower, the host and her whisper, the dials and the chalkboard are hidden; only the head, tabs, stage and tape show.
- Reordering tabs is not built. Hiding a tab from the tour is.
- The three older pages keep their own titles (Sea Lanes, Markets & Booms, The Race) under the new tab names.
- Type inside the three older pages is not enlarged for the iPad yet; the new pages and controls are.
- The dials repeat facts that are now also in the context bar.
- Baseline screenshots of the old layout were not kept.
- Fixtures fix the game id as well as the seed, because hot tips are drawn from the game id.

## Phase 2 (22 Nov 2026): the private feed

`dashboard_suites.py` (new) adds to `/api/dashboard`: `weather` (public), and for an open solo game only
`atlas`, `routes`, `trade`, `fleet`, `treasury` and `career`. Field notes: [dashboard-feed-schemas.md](dashboard-feed-schemas.md).

- Every figure comes from `Game.view(pid)` or the engine methods it calls. The private sections are cut from a
  copy of the game, because some engine lookups tidy the state as they read it.
- Route odds (storm, pirates, pirate queen) repeat a calculation the engine does inline while a voyage sails.
  The test sails 60 months and checks them against the game's recorded dice: 26 storm, 29 pirate and 22
  pirate-queen rolls matched.
- The Treasury's month ahead was checked by closing a month at anchor: the bank paid, and the books charged,
  what it named.
- With rivals at the table, and in a finished game with several houses, none of the six sections is sent.
- `tests/dashboard_suites_test.py` is new. `tests/dashboard_fixtures.py` now plays each month through one
  shared `play_month()`; the fixture games changed with it and are still repeatable.
- Feed at month 200 is now 67.3 KB (budget 100 KB); about 4 ms a build.

When Phase 2 was written nothing on screen used these sections; Phase 3 below is the first to.

## Phase 3 (23 Nov 2026): the Monsoon Observatory

The Weather tab now has three pages, chosen by buttons at the top of the left leaf.

| Page | Shows |
|---|---|
| Now | This month's forecast on the chart and by sea, each sea's harbours, the sea the fleet is on, the rules' storm chance by forecast |
| Routes | A line from the fleet to every port, coloured by forecast and heavier where a storm is likelier; a table of storm, pirate and pirate-queen chances; fleet hull, cargo at cost and protection |
| History | Every storm that landed (newest 24), with ships hit, hull points lost, where the fleet was blown, cargo and guns lost; the tally; how often each sea's forecast came true |

- Tapping a route opens an explanation built from the server's own factors: distance factor, base storm chance
  at that forecast, the pirates' appetite, the queen's interest, protection, bans at the destination.
- No page calls a route safe or suggests one. Unknown is never shown as calm: with no routes block the page
  says so, and with rivals at the table Routes is sealed.
- With rivals, History still lists storms (they are public news) but not what a rival lost.
- Watch Mode shows the next of the three pages each time it comes round to Weather.
- The feed gained `weather.history`, read from the journal and cached until the journal grows.
- Files: `dashboard_suites.py`, `dashboard_feed.py`, `web/dashboard-tabs.js`, `web/dashboard.js`,
  `web/dashboard.css`, `web/dashboard.html` (new cache stamp), and the two test files.

Checked: all eight dashboard tests pass. In a browser at 1366x1024, 1920x1080 and 768x1024, on the late and
rivals fixtures, the three pages and the explanation drew with no errors and no sideways overflow, and Watch
Mode toured Routes, History and Now on successive laps. Not seen with the Media Library or the painted chart.

Still open in Phase 3:
- The chart is the dashboard's existing one. On the iPad's tall leaf it sits small in its frame.
- Weather art (cloud, rain, lightning) is not animated; the four forecasts are shown by colour, word and icon.
- Weather alerts and the Bosun's own observations wait for the alert work in Phase 7.

## Phase 4 (23 Nov 2026): the Captain's Atlas

Decisions: the sea-lane threads are dropped; the map opens on Standing and Watch Mode tours the layers; a tapped
port's dossier fills the right-hand leaf.

- The Atlas tab is a new page (`pageAtlas` in `web/dashboard-tabs.js`). The old Sea Lanes page is no longer
  shown; its code is still in `dashboard.js` for the older tests.
- Six layers, one at a time, chosen by buttons: Standing, Tax, Shares, Warehouses, Commissions, Bans. Each puts
  a figure under every port it has something to say about, and a ranked list in the right leaf.
- Tapping a port, on the chart or in the list, opens its dossier: services, standing and what the band does,
  the tax paid and why, shares and Patron, the warehouse and its stock and rent, commissions in hand or on
  offer there, and bans. "All ports" goes back to the list. Ports on the chart work from the keyboard too.
- Watch Mode shows the next layer each lap, over the dossier of the port the fleet is in.
- With rivals at the table, Shares and Bans still draw (both are public knowledge); the other four layers and
  the private parts of a dossier are sealed.
- A new sea fight now turns the page to Fleet instead of the Atlas.
- No feed change: everything comes from the `atlas` and `career` sections built in Phase 2.

Checked: all eight dashboard tests pass. In a browser at 1366x1024, 1920x1080 and 768x1024, on the late and
rivals fixtures, the layers, list, dossier and back button worked with no errors and no sideways overflow.

Still open in Phase 4:
- (Done in the full-width stage below.) The figures on the chart were small on the iPad while the tower and
  the instruments took a third of the width.
- The dossier does not yet show that port's own Mayor; the page's host is the generic Mayor.
- The layers cannot be combined (the plan allows one comparison layer).
- Best sale, visits and route profit by port are not in the dossier.

## The full-width stage (23 Nov 2026)

Decisions: do this before Trade; the persona blends into the stage; the dials are retired.

- The stage now takes the width the timing tower and the instruments held. On the iPad the book went from
  about 1,100 to about 1,560 of the stage's 1,920 units.
- The timing tower stands on the Career tab's right leaf, above the lead changes.
- The chalkboard of month times is on the Now tab, under the latest wire.
- The three dials and their pop-ups are retired. The date in the masthead opens Now; the weather and fleet
  chips open their tabs. The dial code remains for the older tests and is not run with the Command Center.
- The host keeps a 300-unit column at the right edge. Her picture runs under the stage's edge and fades out,
  and her Read / Hear more line sits at the foot of that column.
- The Now page's fact cards are three across.

Checked: all eight dashboard tests pass. In a browser at 1366x1024, 1920x1080 and 768x1024, on the late and
rivals fixtures, every tab drew with no sideways overflow.

Not checked: how the fade looks over a real portrait. The test copy has no Media Library, so only her
monogram was seen. The persona's line is in her column, not along the whole foot of the stage as first
described.

## Next

Phase 5, the Trade Exchange, on the `trade` section. Then Treasury, Fleet and Career (Phase 6).
