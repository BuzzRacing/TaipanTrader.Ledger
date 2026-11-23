# Captain's Command Center — Phase 0 Field Inventory (first pass)

**Project:** Crimson Ledger / SeaTrader
**Prepared:** 22 November 2026
**Parent plan:** [dashboard-captain-command-center-plan.md](dashboard-captain-command-center-plan.md)
**Status:** Draft for Anthony's review. No game code has been changed.

This is the first Phase 0 deliverable: where every Command Center field comes
from in the code as it stands today. It was written from a read of
`dashboard_feed.py`, `harbor_view.py`, `engine.py` (`Game.view`, the view
helpers, `static_data`), `server.py` (the `/api/dashboard` route),
`config.py` (ports, seas, weather and bank rules) and `web/dashboard.*`.

## 1. Decisions already locked (22 Nov 2026)

| # | Decision | Choice |
|---|---|---|
| 1 | Primary tabs | Now, Atlas, Trade, Weather, Fleet, Treasury, Career, Wire |
| 2 | Control boundary | Strictly read-only; no write path of any kind |
| 3 | Mockup versus plan | Plan wins; mockup is the style target only |
| 4 | Persona art | Existing cast art, by the plan's ownership table |
| 5 | Migration | Replace `/dashboard` in place, step by step |
| 6 | Watch Mode | On by default; 12 s per tab, resume after 60 s idle |
| 7 | Primary device | iPad Pro 12.9/13 inch, 1366x1024 landscape |

## 2. What the dashboard is today

- **Page:** `web/dashboard.html` + `dashboard.js` (66 KB) + `dashboard.css`
  (36 KB) + `dashboard-whisper.js`. A fixed "pit wall" layout: timing tower,
  a three-page ledger book (`PAGES`: race, lanes, markets), dials, chalkboard,
  telegraph tape, and a controls strip (Hold page, Next page, Spotlights,
  Clicks, Voices, Quit).
- **Rotation:** the book turns every 25 s (`TURN_MS`). This becomes Watch Mode
  at 12 s.
- **Feed:** `GET /api/dashboard` builds `dashboard_feed.view()` and
  `dashboard_brief.build()` inside `with HUB.cond:`. So the "one snapshot under
  the game lock" rule (plan 6.3) is already how the route works; new builders
  only need to stay inside that block.
- **Visibility:** `harbor_view.level(game)` returns `open` for a solo game, a
  finished game or free play, otherwise `public`. Private blocks are left out
  of the response at `public`, which is the behaviour the plan requires.
- **Tests:** `tests/dashboard_test.py`, `dashboard_brief_test.py`,
  `dashboard_ui_test.cjs`, `dashboard_whisper_test.cjs`.

### Fields the feed sends now

| Field | Visibility | Source |
|---|---|---|
| `level`, `game_id`, `turn`, `phase`, `years`, `date` | public | `game.s`, `engine.date_label` |
| `houses[]`: firm, name, color, port, home, worth, months, ships, hull, legs, lanes | public | `game.worth`, journal walk (`stats._walk`) |
| `ghost` | open, solo | `stats.career` best game, else a 5%-a-month par curve |
| `tape[]` | public kinds; deals added at open | journal + `harbor_view.activity` |
| `lane_profit`, `deals` | open | journal trades |
| `ports{}`: shares held, total; prices, base | shares public; prices open | `harbor_view.ports` |
| `booms`, `market_effects` | open | journal windfalls; `s.windfalls` + `s.shocks` with turns left |
| `brief` | follows feed | `dashboard_brief.build` |
| `version` | public | `HUB.version` |

## 3. The real world the screens must draw

The mockup's map is not this game's map. These are the facts from `config.py`.

**Ten ports**

| Port | Sea | Bank | Lender | Warehouse | Shipyard |
|---|---|---|---|---|---|
| Hong Kong | South China Sea | yes | yes | yes | yes |
| Shanghai | Yellow Sea & Japan | yes | yes | yes | yes |
| Nagasaki | Yellow Sea & Japan | | | | |
| Manila | South China Sea | | | | |
| Foochow | South China Sea | | | | |
| Saigon | South China Sea | | | | |
| Bangkok | Straits & Java Sea | | | | |
| Singapore | Straits & Java Sea | yes | yes | yes | yes |
| Batavia | Straits & Java Sea | | | | |
| Calcutta | Bay of Bengal | yes | yes | yes | yes |

Canton, Amoy, Swatow, Haiphong, Tourane, Cholon and Penang appear in the mockup
and do not exist in the game.

**Four seas:** Yellow Sea & Japan, South China Sea, Straits & Java Sea, Bay of
Bengal. Each has base typhoon and squall odds and a season that replaces them
(typhoon season June to October in the north and the South China Sea; squall
season November to March in the Straits).

**Weather**

- Four levels, 0 to 3, one per sea, rolled once a month (`_roll_weather`).
- What the Captain sees is a **forecast**. The actual sea is settled when the
  month sails, and the forecast holds with probability
  `rules.weather.forecast_accuracy` (0.8 by default).
- Storm chance by level: 0%, 2%, 10%, 30%, multiplied by a distance factor
  `distance / 350` clamped to 0.6–1.8, and by the difficulty multiplier.
- A voyage uses the worse of the origin's and the destination's sea.
- Off-course chance 15%. Pirate chance, pirate-lord chance and the protection
  saving are all in `static_data()["voyage_risk"]`.

**Bank:** the full rate (1% a month) on the first slice of a deposit, 0.5% on
the next, 0.25% above that. The slice limits are $25M and $100M for a
twenty-year game and scale with game length. The rate **falls** as the balance
rises; the mockup shows it rising.

**Shares:** ten per port. A house holds at most ten in all, earned by rank, and
places them in any port. There is no percentage-of-port ownership beyond
"n of 10".

## 4. Mockup panels against the engine

| Mockup panel | Verdict | What it becomes |
|---|---|---|
| Weather status (Calm / Fair / Squalls / Typhoon) | Real | Four seas, one level each, labelled as forecast |
| Storm map over the sea | Real | Weather art bound to the four sea levels |
| Route risk bands | Real, reworded | Storm chance per destination from the real formula, with its inputs shown |
| Forecast confidence 87% | Real, different number | `forecast_accuracy` (80% by default), one value for all seas |
| 10-day monsoon outlook | Not in the engine | See question A below |
| Key Risks & Advice ("Divert via...") | Forbidden by the plan | Facts only: which seas are at Typhoon, which routes cross them |
| Port map with 12 names | Wrong ports | The ten real ports at their config longitudes and latitudes |
| Share ownership % rings | Reworded | "n of 10 shares", holders, free shares, Patron |
| Warehouse (cargo) figures | Real at four ports | Only Hong Kong, Shanghai, Singapore and Calcutta have warehouses |
| Active commissions with Est. Profit | Partly real | `contracts_view` rows: text, port, progress, deadline, perk. No profit column |
| Port favorability ranking | Real | `rep` per port, band from `band_here` |
| Effective tax | Real | `tax_rate_for(p, port)` |
| Net worth composition donut | Real | The terms of `Game.worth`: silver, bank, debt, fleet, laid-up ships, shares and house, cargo |
| Monthly profit waterfall | Real | `books_view` (`last`, `cur`, `year`, `game`) |
| Bank interest tiers | Real, inverted | `bank_tiers()` and `bank_interest(p, extra)` |
| Recurring obligations | Real | Ship wages, laid-up wages, warehouse rent, estate upkeep, protection cost |
| Estate benefits | Real | `estate_view`: bank bonus, dues cut, robbery cut, upkeep, sell price |

## 5. Proposed feed sections and their sources

Every section is built inside the existing `HUB.cond` block. `open` means the
section is omitted entirely unless `harbor_view.level()` is `open` **and** the
game has exactly one seat.

| Section | Visibility | Fields | Source | Refresh |
|---|---|---|---|---|
| `context` | public (worth change and fleet condition: open) | date, months left, port or destination, worth, change this month, fleet condition, worst sea, rank | `game.s`, `Game.worth`, `_rank_view`, `s.weather` | every poll |
| `alerts` | by alert | id, level, tab, fact, source ids | built from the other sections | every poll |
| `weather` | public | seas with level and season flag; forecast accuracy | `s.weather`, `REGIONS`, `rules.weather` | on turn change |
| `weather.routes` | open | per destination: distance factor, sea level used, storm chance, off-course, pirate and lord chance, protection months, fleet hull, cargo basis aboard | `static_data().voyage_risk` rules applied server-side, `storm.fleet_hull`, `p.protect`, `p.basis` | on turn or port change |
| `weather.history` | public events; costs open | storms, off-course voyages, damage | journal | on journal growth |
| `atlas` | shares public; the rest open | per port: services, rep and band, band effects, base and effective tax, shares held, free, Patron, warehouse stock and rent, contracts here, bans | `PORTS`, `p.rep`, `band_here`, `band_effects`, `tax_rate_for`, `shares_view` logic per port, `_store_view`, `contracts_view`, `banned` | on turn change or action |
| `trade` | open | prices by port and good, month-start base, known prices and tips, hot tips, basis, purse here, effects, bans | `harbor_view.ports`, `p.known`, `p.tips`, `p.hot_tips`, `p.basis`, `purse_view`, `s.windfalls`, `s.shocks` | on turn change or action |
| `fleet` | class and hull public; the rest open | ships and laid-up ships exactly as `Game.view` lists them; fights | `Game.view` ship rows, `fleet_ledger`, `p.fights` | on turn change or action |
| `treasury` | open | worth by component; books; bank tiers with this month's projected interest; debt, loan room, collectors, bankruptcy, debt cap; estate; recurring costs by asset | `Game.worth` terms, `books_view`, `bank_tiers`, `bank_interest`, `loan_limit`, `collectors`, `bankruptcy`, `debt_cap`, `estate_view`, wages, `protection_cost` | on turn change or action |
| `career` | rank public; the rest open | rank, next rank and its worth, fame, shares earned and placed, commissions, honours, Legends, log | `_rank_view`, `p.fame`, `contracts_view`, `honour`, `legend.book`, `p.log` | on turn change |
| `history` | as today | houses, months, legs, lanes, ghost, deals, lane profit | existing feed | on journal growth |
| `wire` | as today's tape | chronological events | existing `tape()` | on journal growth |
| `brief` | as today | persona observations | `dashboard_brief` | with the feed |

## 6. Gaps found

1. **Per-port standing, tax and shares.** `shares_view` and `band_effects`
   answer for the port the fleet is in. The Atlas needs them for all ten ports
   in one pass. The underlying methods take a port argument, so this is a new
   read-only builder, not a rule change.
2. **Route exposure is computed in the browser today** (from
   `static_data().voyage_risk`). The plan wants it server-owned, so the
   Observatory needs a server builder that applies the same formula.
3. **Worth by component.** `Game.worth` returns one total. The Treasury donut
   needs the same terms returned separately, with a reconciliation test that
   they sum to `worth()`.
4. **Recurring costs by asset** are spread across several helpers and are not
   collected anywhere yet.
5. **Ship-level history.** The journal records fleet-level events. Per-ship
   biographies will mostly fall back to fleet history, as the plan allows.
6. **Stable alert ids and a response sequence** do not exist yet; `version` is
   the only revision marker.
7. **No future weather.** Nothing is rolled beyond the current month.

## 7. Follow-up decisions (22 Nov 2026)

- **A. Weather outlook: this month only.** No outlook strip. The Observatory
  shows the current forecast for each sea and the forecast accuracy, and
  nothing about later months. The Weather tab's subpages become Now, Routes
  and History; the plan's Forecast subpage is dropped.
- **B. Map art: a new painted map in the mockup's style.** Brief and prompt in
  [dashboard-atlas-map-prompt.md](dashboard-atlas-map-prompt.md). Ports are
  drawn on top from their real coordinates, with a per-port nudge table for
  the chosen picture.
- **C. Old pieces: fold into the tabs.** The Race and the ghost go to Career,
  Sea Lanes to Atlas, Markets & Booms to Trade, the dials to the context bar,
  the chalkboard to Now, the telegraph tape to Wire. The pit-wall layout
  retires as each tab becomes ready.
- **D. Multiplayer: all eight tabs, sealed panels.** Every tab stays in the
  bar. Panels that need private data show a "Sealed until the finale" stamp.
  The server still omits the data; the stamp is drawn from the absence of the
  section, never from hidden fields.

## 8. Still to do in Phase 0

- [ ] Field-by-field schemas for each section (this document is the source map).
- [ ] Early, middle and late deterministic fixtures, including a Game 6-scale
      state, plus multiplayer-public, offline and empty-history cases.
- [ ] Baseline screenshots at 1920x1080, 1366x1024 and 768x1024.
- [ ] Feed-size and render-time measurements on the current dashboard.
- [ ] Trap-object privacy tests that fail if a private field is read at
      `public`.
