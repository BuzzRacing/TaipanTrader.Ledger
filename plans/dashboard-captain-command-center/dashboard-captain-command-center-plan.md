# The Dashboard — Captain's Command Center Development Plan

**Project:** Crimson Ledger / SeaTrader  
**Surface:** `http://crimson.ledger/dashboard`  
**Primary device:** iPad beside the main Player screen  
**Prepared:** 22 November 2026  
**Status:** Approved direction; implementation not started  

**Visual concept:** [Monsoon Observatory, Captain's Atlas and House Treasury](dashboard-command-center-three-screen-mockup.png)

## 1. Vision

The Dashboard should become the Captain's read-only second-screen operating
system: a living chart room that exposes the whole solo game without competing
with the Player screen for control.

It should feel useful when watched from across the room and rewarding when held
in the hand. At rest it automatically tours the voyage, markets, weather,
fleet, property and career. When the Captain touches it, the same information
opens into detailed, tabbed reports suitable for an iPad.

The Dashboard is not a larger scoreboard and not a second copy of the Player
screen. It answers five questions continuously:

1. **What deserves attention now?**
2. **Where is the opportunity or danger?**
3. **What does the Captain own, owe and influence?**
4. **Why did the house's fortune change?**
5. **How has this voyage become an empire?**

The intended rhythm is:

> Glance -> notice a change -> tap for evidence -> understand the consequence
> -> return to Watch Mode

## 2. Product evidence

The project document *SeaTrader Playtest Review - Game 6, $209M over 20 Years*
and its resulting code changes show that a long campaign changes character.
The opening years are dominated by cargo and routes. The later years are also
about progressive bank interest, estates, port shares, warehouses, contracts,
standing, recurring costs, protection and fleet exposure.

The Game 6 work specifically added or refined:

- tiered bank interest for very wealthy houses;
- estate bonuses to bank interest and home-port dues;
- larger Mayor commissions for richer houses and perks on yearly goals;
- bills drawing from banked silver before creating debt;
- lower pirate exposure after a fleet has already been battered by a storm;
- warnings before purchases that would liquidate badly.

The Dashboard must therefore reveal relationships between systems, not merely
repeat isolated values. A $209 million house needs to see capital allocation and
exposure as clearly as a young house sees cargo prices.

## 3. Experience principles

### 3.1 Read-only by design

The Dashboard may navigate, filter, compare, explain and play configured voice.
It must not buy, sell, sail, borrow, repay, accept contracts or mutate the game.
The Player screen remains the sole game-control surface. This makes an iPad safe
to touch casually and keeps the main game loop authoritative.

### 3.2 One truthful snapshot per refresh

Each Dashboard response must be assembled from one frozen game-state snapshot.
Derived comparisons must use that snapshot rather than re-reading live state
halfway through a calculation. Journal history and current state must be labeled
and kept distinct.

### 3.3 Solo-private first, multiplayer-safe always

The complete Command Center is a solo feature. It may expose the Captain's
private finances, cargo, basis, tips and holdings only when the existing Harbor
View visibility level is `open`.

In active multiplayer, the server must continue to omit private fields rather
than sending them and relying on CSS or JavaScript to hide them. Public pages
may remain available, visibly sealed where private evidence is required.

### 3.4 Consequence before decoration

Every animation, alert and persona observation must correspond to real state or
a recorded event. Weather art represents actual weather. A warehouse marker
means the Captain owns that warehouse. A warning names the calculation behind
it. The screen never invents an event to keep itself busy.

### 3.5 Progressive disclosure

Every page has three depths:

1. **Glance:** one headline and the few values that matter now.
2. **Inspect:** a useful chart, map or ranked list.
3. **Explain:** a drawer or dialog with the underlying calculation and history.

The automatic rotation uses Glance and Inspect. Explain appears only after a
tap.

### 3.6 Personas are informed correspondents

Personas remain large, blended and dramatic, but appear because they own the
subject:

- Anahit: voyage-wide priorities and major milestones;
- Narrator/Bosun: routes, weather and fleet risk;
- Bookmaker/Comprador/Registrar: markets, spreads and price intelligence;
- Bookkeeper/Banker/Madam Wu: books, liquidity, interest and debt;
- Mayors: standing, contracts, patronage and property in their ports.

They speak only deterministic, server-built observations. The readable fact is
always available without audio.

### 3.7 Designed for an iPad, still excellent at 16:9

- Touch targets: at least 44 CSS pixels.
- Primary figures remain readable at arm's length.
- No hover-only information.
- Landscape iPad is the primary interactive layout.
- Portrait iPad becomes one wide column with sticky tabs and bottom drawers.
- The existing 1920x1080 presentation remains supported for a television or
  desktop second monitor.
- Reduced motion preserves all meaning.

## 4. Information architecture

The main navigation should support more information than the current three-page
book without becoming a strip of microscopic buttons.

### 4.1 Primary tabs

| Tab | Purpose | Default owner |
|---|---|---|
| **Now** | Current priorities, alerts and voyage pulse | Anahit |
| **Atlas** | Ports, ownership, influence and services | Current port's Mayor |
| **Trade** | Prices, basis, inventory and route opportunities | Bookmaker / Comprador |
| **Weather** | Regional conditions, forecasts and route exposure | Bosun / Narrator |
| **Fleet** | Ships, cargo, repair, wages and battle history | Bosun |
| **Treasury** | Worth, books, bank, debt, property and recurring cost | Bookkeeper / Banker / Wu |
| **Career** | Rank, fame, honours, contracts and Captain history | Anahit / Mayor |
| **Wire** | Chronological journal, news and saved observations | Narrator |

Primary tabs may scroll horizontally on a tablet. The active tab and the next
two tabs must always remain obvious. A compact tab drawer provides direct
access to every page without repeated swiping.

### 4.2 Persistent context bar

Every page shares a compact context bar containing:

- game date and months remaining;
- current port or voyage destination;
- net worth and change this month;
- fleet condition;
- most severe current weather;
- current rank;
- connection and voice state.

The context bar is informative, not another collection of gauges. Tapping a
value opens the relevant detailed tab.

### 4.3 Watch Mode

Watch Mode is the default idle state.

- Rotate through configured primary tabs every 10-15 seconds.
- Pause immediately after any touch and resume only after an idle delay.
- Allow the Captain to pin, hide and reorder pages locally on that device.
- Preserve filters while a page is held; reset optional filters on the next
  automatic lap.
- Interrupt only for high-value changes: severe weather, fleet damage,
  contract deadline, promotion, band change, active boom/crash, debt danger or
  a material lead change.
- Never interrupt an open explanation dialog or a currently playing persona.
- Acknowledge an interruption once per meaningful event id.

## 5. The five major Command Center suites

### 5.1 Captain's Atlas

The Atlas is one map with selectable intelligence layers:

- standing and favorability band;
- effective tax and dues;
- shares held, shares available and Patron;
- owned warehouses, capacity, rent and cargo;
- active contracts and destinations;
- port services: bank, shipyard, warehouse and lender;
- best sale, visits and recorded route profit;
- bans, crackdown and current market effects.

Tapping a port opens a dossier with its evidence and the port's Mayor. The map
must support combined layers without turning into confetti: one primary layer,
one optional comparison layer and small status badges.

**Acceptance criteria**

- Every port displays the correct current standing band and effective tax.
- Placed and unplaced shares add up to the server's share allowance.
- Warehouse contents and capacity match the Player screen.
- A Patron is shown only when the server identifies one.
- Selecting a port never exposes another player's private holdings during an
  active multiplayer game.

### 5.2 Monsoon Observatory

The Weather suite is the visual centerpiece.

Subpages:

- **Now:** all regions and their current severity;
- **Routes:** destination-by-destination exposure from the Captain's port;
- **Forecast:** known outlook and forecast confidence;
- **History:** storms, off-course voyages, hull damage and recorded cost.

The map may use animated cloud, rain, lightning, wind and sea treatments, but
those effects must map to the four actual weather levels. Each destination
comparison should separate:

- storm probability;
- off-course exposure;
- pirate exposure known to the rules;
- current fleet condition;
- protection or flagship effects;
- cargo cost basis currently aboard;
- limits of the forecast.

The result is not a recommendation engine. It may say that one route has lower
known exposure than another; it must not claim a safe voyage or guaranteed
outcome.

**Acceptance criteria**

- Region art, labels and severity always describe the same snapshot.
- Route cards show the source values used in each risk calculation.
- Unknown forecast information is labeled unknown, never treated as calm.
- Reduced motion replaces atmospheric animation with static severity styling.
- The page remains readable with all regions at Typhoon severity.

### 5.3 Trade Exchange

Subpages:

- opportunity board;
- cargo heatmap;
- personal purchase basis;
- dealer purses;
- booms, crashes and bans;
- Price Book and hot tips;
- warehouse inventory by port;
- route and cargo performance;
- active commission requirements.

Opportunity cards should show a transparent calculation:

1. visible buy and sell quotes;
2. gross spread;
3. the Captain's known basis where relevant;
4. known taxes, bans and active market effects;
5. known recurring or arrival costs shown separately;
6. a clear statement that prices and voyage outcomes may change.

The Dashboard must not collapse uncertain costs into a false “guaranteed
profit.” A useful first release may rank gross legal spreads and provide the
cost context beneath them.

**Acceptance criteria**

- Banned destinations are excluded from “best legal spread.”
- Market effects use current remaining turns, not expired journal entries.
- Personal basis and private tips are absent outside an open solo view.
- Warehouse stock is not double-counted as cargo aboard.
- Every ranked opportunity can be traced to its quotes and assumptions.

### 5.4 House Treasury

Subpages:

- balance sheet;
- month, year and voyage books;
- net-worth composition and history;
- bank tiers and projected monthly interest;
- debt, loan room and collector danger;
- estate stage, benefits, upkeep and sell-back;
- warehouse rent and fleet wages;
- protection and other recurring obligations;
- largest gains and losses.

The first Treasury milestone should explain the next month:

> fixed costs + known obligations + projected interest + expiring benefits

Projection inputs must be labeled and use only deterministic current rules. The
actual next month may still contain trade, weather, battle and random events.

**Acceptance criteria**

- Balance-sheet components reconcile to server net worth within documented
  rounding.
- Month/year/game books match `books_view` totals.
- Bank tiers reproduce `bank_interest` exactly for the current balance and
  estate bonus.
- Recurring costs identify the assets responsible for them.
- Debt warnings use the existing collector and bankruptcy calculations rather
  than reimplementing their thresholds in JavaScript.

### 5.5 Admiralty and Captain's Legacy

Subpages:

- active fleet formation;
- laid-up ships;
- repairs and shipyard limitations;
- hold and cargo distribution;
- guns, cannons and battle readiness;
- wages and fleet value;
- battle record and losses;
- current rank and promotion progress;
- fame, honours and Legends;
- shares earned, placed and still free;
- active and completed Mayor commissions;
- Captain's log and voyage milestones;
- twelve-month “Form Guide” for profit, weather, battles and promotions.

Each named ship should have a detail card using only recorded history. If the
journal cannot attribute an old event to an individual ship, the UI must show
fleet-level history rather than invent a ship biography.

**Acceptance criteria**

- Ship count, hold, hull, armament, wages and repair cost match the Player
  screen.
- Laid-up ships are visually and financially distinct.
- Rank progress uses the configured ladder and current commissioned rank.
- Contract deadlines and progress match `contracts_view`.
- Honour, Legend and battle history remain chronological and deduplicated.

## 6. Data architecture

### 6.1 Current position

`dashboard_feed.py` currently supplies public standings, worth history, routes,
deals, market data, weather summaries and a privacy-aware event tape. The full
private Captain state already exists in `Game.view(pid)` but must not simply be
copied wholesale into the Dashboard response.

### 6.2 Recommended feed shape

Keep one endpoint family and add explicit, bounded sections:

```text
/api/dashboard
  context
  public
  alerts
  atlas        (solo/open only)
  trade        (solo/open only)
  weather
  fleet        (solo/open only)
  treasury     (solo/open only)
  career       (solo/open only)
  history
  brief
```

Each section should have a small server-side builder with a documented schema.
Builders may call existing engine view helpers, but should return only the
fields that the Dashboard uses. This avoids binding the second-screen API to
the entire Player-screen payload and makes privacy review practical.

### 6.3 Snapshot rule

Under the existing game condition lock:

1. identify visibility and the solo Captain;
2. freeze/copy the required state once;
3. build all current-state sections from that copy;
4. read journal-derived history using the game id and recorded event cursor;
5. attach a response sequence and state turn;
6. release the response as one coherent payload.

No builder may roll dice, call a mutating engine method or infer a private fact
from a public one.

### 6.4 Server-owned calculations

The server remains authoritative for:

- effective taxes, standing bands and band effects;
- share ownership, free shares and Patron status;
- net worth and balance-sheet reconciliation;
- bank tiers, interest and estate bonuses;
- collector, bankruptcy and debt thresholds;
- repair, wage, rent and upkeep values;
- contract progress and deadlines;
- voyage/weather risk inputs;
- opportunity assumptions and privacy filtering;
- persona observations.

JavaScript formats and visualizes these values. It must not maintain a second
version of financial or game rules.

### 6.5 Refresh strategy

- Poll the compact context/sequence frequently enough to feel live.
- Fetch heavy history and chart sections only when their revision changes.
- Cache immutable reference data and completed historical periods.
- Pause expensive redraws while the tab is hidden.
- Preserve the currently inspected page across feed refreshes.
- A reconnect performs a clean snapshot refresh; it does not replay stale
  alerts as new events.

The first implementation should remain polling-based. WebSockets or server-sent
events are an optional later optimization, not a prerequisite.

## 7. Visual and interaction system

### 7.1 Layout

- Replace the fixed three-page assumption with a responsive stage and page
  router.
- Keep the branded masthead compact.
- Retain burgundy/oxblood lacquer, antique brass and configured brand fonts.
- Use full-bleed persona art with broad transparency masks and no hard image
  edges.
- Prefer one dominant visualization per page and supporting evidence beneath or
  beside it.
- Use drawers on tablet instead of modal dialogs where practical.

### 7.2 Charts

- Use tabular numerals for all money and percentages.
- Every chart has a plain-language title, unit, time range and accessible text
  summary.
- Never use red for ordinary negative movement if it can be confused with a
  destructive or critical warning; use the established muted loss color.
- Comparisons begin at a meaningful baseline and disclose when a server restart
  shortened the available history.
- Tap targets, not hover, reveal exact values.

### 7.3 Alerts

Use four levels:

| Level | Behavior | Examples |
|---|---|---|
| **Critical** | Interrupt Watch Mode once | Typhoon on selected route, collector call, crippled fleet |
| **Opportunity** | Brief gold cue; no forced navigation | Boom, new private lot, contract nearly complete |
| **Change** | Enters Now and Wire | Standing band, Patron, promotion, material worth change |
| **Record** | Wire only | Ordinary arrival, routine trade, small monthly movement |

Alert ids must be stable across refreshes. The browser keeps a bounded set of
acknowledged ids so an iPad reconnect does not chatter through old news.

### 7.4 Audio

- Respect the existing Voice and SeaAudio floor.
- Never synthesize merely because a tab rotated.
- Automatic speech is reserved for Critical alerts and rare major milestones.
- Manual Hear More uses server-selected persona and server-built speech.
- Read always works silently.
- Muting or closing a page cancels Dashboard-owned queued audio.

## 8. Development phases

### Phase 0 — Contracts, fixtures and measurement

**Goal:** Make the target explicit before replacing the current layout.

#### Work

- Record baseline screenshots at 1920x1080, 1366x1024 landscape iPad and
  768x1024 portrait tablet.
- Write schemas for `context`, `alerts` and each private suite.
- Define a deterministic long-game fixture representing early, middle and
  $209M-style late-game states.
- Add a feed-size and render-time measurement to the preview harness.
- Add privacy tests that fail if private properties are read while visibility
  is public.

#### Exit gate

- Every proposed field has a source, owner, visibility and refresh policy.
- The preview can switch between early, middle, late, multiplayer-public,
  offline and empty-history cases.

---

### Phase 1 — Responsive shell and Watch Mode

**Goal:** Establish the iPad Command Center without changing game rules.

#### Work

- Build primary tab router and compact context bar.
- Add swipe, direct tab drawer, hold/pin and auto-rotation.
- Persist only device presentation preferences locally.
- Preserve the existing Race, Markets and instruments as temporary pages.
- Add page lifecycle hooks so hidden pages stop animation and expensive work.

#### Exit gate

- The Dashboard works without horizontal page overflow on landscape and
  portrait iPad.
- Watch Mode completes repeated laps without leaking timers, audio or DOM.
- Interaction pauses rotation and never loses the user's selected filter.

---

### Phase 2 — Solo-private feed foundation

**Goal:** Expose the Captain's complete information safely and coherently.

#### Work

- Add bounded server builders for Atlas, Trade, Fleet, Treasury and Career.
- Attach response sequence/revisions and stable alert ids.
- Reuse engine calculations rather than copying rules into the browser.
- Extend preview fixtures and contract tests for every suite.
- Keep multiplayer payloads structurally incapable of revealing private data.

#### Exit gate

- Feed builders are deterministic and side-effect free.
- Open solo responses reconcile with `Game.view(pid)`.
- Public response privacy tests use trap objects that throw on private access.
- Payload size and polling cost remain within the budget established in Phase 0.

---

### Phase 3 — Monsoon Observatory

**Goal:** Deliver the first spectacular, high-value new page.

#### Work

- Create animated weather map and accessible static treatment.
- Add current, routes, forecast and history subpages.
- Build route exposure explanations from server-owned risk inputs.
- Add Bosun/Narrator observations and weather alert thresholds.

#### Exit gate

- Current weather, forecast and route facts agree with the Player screen.
- The page is useful with audio off and reduced motion on.
- No route is called safe or profitable.

**Recommended first public milestone.**

---

### Phase 4 — Captain's Atlas

**Goal:** Make influence, ownership and property visible as one world.

#### Work

- Add standing, shares, property, services, contracts and tax layers.
- Build tappable port dossiers.
- Add Mayor ownership by selected port and deterministic observations.
- Add combined-layer collision and density handling.

#### Exit gate

- Every solo ownership and favorability value can be found within two taps.
- The map remains readable with all ten ports carrying several statuses.
- Public multiplayer never shows private overlays.

---

### Phase 5 — Trade Exchange

**Goal:** Turn prices and history into transparent decision support.

#### Work

- Expand Markets into Trade subpages.
- Add basis, purses, inventory, tips, effects and route history.
- Add gross legal opportunity ranking with disclosed cost context.
- Connect contract requirements to relevant cargo and ports.

#### Exit gate

- Every opportunity links to source quotes and assumptions.
- Bans, stale tips and uncertain costs are obvious.
- Results survive empty markets, missing history and a server restart.

---

### Phase 6 — Treasury, Admiralty and Career

**Goal:** Complete the late-game command system.

#### Work

- Build balance sheet, books, interest, obligation and debt pages.
- Build ship formation, repair, wage, cargo and battle pages.
- Build rank, honour, Legend, commission and log pages.
- Add next-month known-obligation summary and twelve-month Form Guide.

#### Exit gate

- Treasury reconciles and explains the Game 6 late-game systems.
- Fleet data matches ship-for-ship with the Player screen.
- Career chronology is stable after restart and free of duplicate events.

---

### Phase 7 — Now, Wire and editorial polish

**Goal:** Make all the information feel directed rather than dumped.

#### Work

- Build Now from ranked, deduplicated alerts across all suites.
- Expand the telegraph tape into a filterable chronological Wire.
- Add “what changed” explanations between feed revisions.
- Tune Watch Mode order based on current state: severe weather may place Weather
  next; an expiring commission may place Career next.
- Complete persona coverage and quiet-state behavior.

#### Exit gate

- A Captain can understand the current priority from Now in five seconds.
- Quiet months remain elegant without fabricated urgency.
- A twenty-year journal remains navigable and performant.

## 9. Test and verification plan

### 9.1 Server contracts

- Unit tests for every suite builder.
- Reconciliation tests against engine helpers.
- Trap-object privacy tests for public multiplayer.
- Stable-id and deduplication tests for alerts.
- No mutation: compare serialized state before and after building a feed.
- Restart tests for shortened history and seeded alert cursors.

### 9.2 Browser behavior

- Tab, swipe, drawer, pin and Watch Mode tests.
- Rotation pauses for touch, dialog, spotlight and voice.
- Reconnect and stale-response ordering tests.
- Silent Read, Hear More, mute, cancellation and audio-floor tests.
- Empty, loading, offline and unavailable-section states.

### 9.3 Visual QA matrix

| Viewport | Orientation | Required passes |
|---|---|---|
| 1920x1080 | landscape | Watch Mode, every suite, alerts |
| 1366x1024 | iPad landscape | primary interactive target |
| 1180x820 | compact landscape | tab density and drawers |
| 768x1024 | iPad portrait | single-column adaptation |
| 390x844 | phone fallback | readable status, no full feature parity required |

For each viewport, test early, middle and late game; all-calm and all-Typhoon
weather; empty and full warehouses; one and many ships; no debt and collector
danger; no shares and maximum shares; no history and twenty-year history.

### 9.4 Performance budgets

Phase 0 must record actual baselines, then set enforceable budgets. Initial
targets:

- compact poll response under 100 KB;
- heavy suite payloads fetched by revision, not on every poll;
- interactive page ready within two seconds on the local network;
- tab change visibly responds within 100 ms before optional chart animation;
- no continuous animation on a hidden tab;
- no unbounded arrays, timers, observers, audio queues or acknowledged ids.

## 10. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Too many tabs become another admin panel | Glance/Inspect/Explain hierarchy; one dominant question per page |
| Feed becomes a duplicate of `Game.view` | Explicit suite schemas and bounded builders |
| Private solo data leaks in multiplayer | Server omission, visibility tests and trap objects |
| Browser financial math drifts from engine | Server-owned calculations and reconciliation tests |
| Watch Mode becomes distracting | Strict alert levels, cooldowns and quiet-state design |
| Persona chatter becomes repetitive | Stable fact ids, rare auto-speech and manual Hear More |
| Weather animation implies false forecasts | Effects bind only to current/known server fields |
| Twenty-year history becomes slow | Revisions, aggregation, bounded detail and lazy loading |
| Existing Dashboard regressions block progress | Preserve current pages during shell migration; replace incrementally |

## 11. Definition of complete

The Captain's Command Center is complete when:

- every private solo data family exposed by the Player screen has an intentional
  Dashboard home or is explicitly documented as out of scope;
- the Captain can find current weather, holdings, influence, inventory, fleet,
  finances, obligations and career progress without returning to the Player
  screen for reference;
- the Dashboard cannot perform game actions;
- public multiplayer payloads contain no private Captain data;
- Watch Mode can run unattended for a complete play session;
- late-game finances remain legible at Game 6 scale;
- every persona statement is derived from verified state;
- all required viewports and reduced-motion behavior pass browser verification;
- local preview, automated tests and one live solo-game verification pass before
  deployment.

## 12. Recommended execution order

1. Phase 0 — contracts and fixtures.
2. Phase 1 — responsive shell and Watch Mode.
3. Phase 2 — solo-private feed foundation.
4. Phase 3 — Monsoon Observatory.
5. Phase 4 — Captain's Atlas.
6. Phase 5 — Trade Exchange.
7. Phase 6 — Treasury, Admiralty and Career.
8. Phase 7 — Now, Wire and editorial polish.

Do not build all data pages before proving the shell. Do not build the shell
against invented fixture fields before defining the server contracts. The first
convincing release is the responsive Command Center plus the Monsoon
Observatory on the real solo feed.

## 13. Working checklist

- [ ] Approve information architecture and primary tab names.
- [ ] Approve the read-only boundary.
- [ ] Complete Phase 0 field inventory and schemas.
- [ ] Create early/middle/late deterministic preview fixtures.
- [ ] Set measured feed and render budgets.
- [ ] Implement and verify responsive shell.
- [ ] Implement and privacy-test solo suite builders.
- [ ] Ship Monsoon Observatory milestone.
- [ ] Ship Captain's Atlas milestone.
- [ ] Ship Trade Exchange milestone.
- [ ] Ship Treasury, Admiralty and Career milestone.
- [ ] Complete Now/Wire editorial pass.
- [ ] Run live solo-game verification on iPad.
- [ ] Deploy only after Anthony approves the verified preview.

