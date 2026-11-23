# The Table — Cinematic Spectator View Development Plan

**Project:** Crimson Ledger / SeaTrader  
**Surface:** `http://crimson.ledger/table`  
**Prepared:** 22 November 2026  
**Status:** Proposed development plan

## 1. Vision

The Table should become a non-playable, cinematic view of the live game: a
spectator can sit back and watch a Captain's twenty-year trading career unfold
without needing to understand or operate the player screen.

The map remains the continuous stage. The camera moves between world, voyage,
fleet, event and port views as the game journal advances. Stories and cut scenes
appear over the relevant ship, route or port instead of replacing the world with
an unrelated card.

The intended viewing rhythm is:

> World map -> follow ship -> reveal fleet -> event over voyage -> enter port ->
> watch port activity -> depart

At wide scale, one ship symbol represents the fleet. As the camera approaches,
that symbol expands into the actual ships in formation. At a port, the view
settles into an animated harbour tableau whose movement reflects real game
activity. The camera then follows the fleet back to sea.

## 2. Why this fits the game

The Game 6 review describes the shape of a full twenty-year campaign that
reached $209 million. The repeated trading loop is punctuated by storms,
pirates, customs, repairs, banking, Mayor commissions, estate development and
larger financial decisions. These are not isolated menus from a spectator's
point of view; together they form the story of a maritime house becoming an
empire.

The spectator view therefore needs to communicate three things clearly:

1. **Where the Captain is and where the fleet is going.**
2. **What important event is happening now.**
3. **How the Captain's power and world have changed over time.**

## 3. Experience principles

### 3.1 The map is always the stage

The map may dim, crop, tilt or move out of focus, but it should remain spatially
present during normal play. Persona and cut-scene artwork is composited over the
map and anchored to the active ship or port.

### 3.2 One continuous camera language

Every scene uses the same camera model and easing rules. A voyage should feel
like one continuous movement from departure to arrival, not a sequence of page
transitions.

### 3.3 Show consequences, not decorative noise

Animation must represent recorded game state: fleet size, ship condition,
cargo, orders, weather, trade, repairs, customs, contracts or financial change.
Ambient movement may provide life, but it must not imply events that did not
happen.

### 3.4 Readable without player knowledge

A spectator should understand the major beat from image, movement and one short
line of text. Detailed figures remain available but secondary.

### 3.5 Preserve chronology and privacy

The Table continues to use frozen journal events in their original order. It
must never borrow current state to decorate an older event, trigger game actions,
reveal private multiplayer information or make additional random rolls.

### 3.6 Respect the room

This is primarily a second-monitor experience. Important action must remain
legible at a distance, work at 16:9 and stacked portrait layouts, and offer a
reduced-motion treatment without losing meaning.

## 4. Target camera system

The camera director should support five named shot levels.

| Shot | Purpose | Typical duration | Main content |
|---|---|---:|---|
| **World** | Establish geography and destination | 3-6s | Full route, one fleet symbol, port labels |
| **Voyage** | Follow progress across the sea | 6-16s | Tracking ship, wake, route, weather |
| **Fleet** | Reveal the actual fleet | 5-10s | Ship rows, formation, hull and cargo cues |
| **Event** | Present story or danger | Voice-led | Persona/cut-scene artwork over active world |
| **Port** | Show harbour activity and decisions | Until next event | Port artwork, animated activity, concise data |

The director selects a shot from the journal event, but the selected scene owns
only presentation. It cannot change game state. Each transition should have a
defined focus target, start and end framing, duration, easing curve and fallback
for missing artwork or data.

## 5. Development phases

### Phase 0 — Scene contract and camera prototype

**Goal:** Establish a stable cinematic vocabulary before adding more artwork.

#### Work

- Define a `TableScene` presentation contract containing:
  - event id and journal timestamp;
  - scene kind and shot level;
  - geographic focus target;
  - route and camera framing;
  - frozen fleet, weather and activity details;
  - artwork roles and text;
  - minimum duration, voice ownership and reduced-motion behavior.
- Extend the existing director so it describes a sequence of shots rather than
  one layout per event.
- Add deterministic camera interpolation for pan, zoom and focus.
- Keep the current scene clock as the single source of time for camera, ship,
  route, overlays and pause/resume.
- Add a developer preview that can step through every shot and transition.

#### Acceptance criteria

- A simulated departure-to-arrival sequence runs as one continuous camera move.
- Pause freezes the entire visual moment; resume does not jump.
- Skip completes the current beat cleanly and starts the next journal event.
- Reduced motion uses dissolves and immediate reframing rather than long travel.
- Missing optional data produces a simpler valid scene, not invented detail.

---

### Phase 1 — Cinematic God-Camera

**Goal:** Make the current map, ship movement, personas and cut scenes feel like
one spectator production.

#### Work

- Begin each voyage at World level, framing the complete origin-to-destination
  route.
- Ease toward the moving ship and transition into Voyage tracking.
- Anchor story/cut-scene artwork to the active ship or destination using a
  restrained cinematic overlay:
  - map visible underneath;
  - localized vignette rather than a full-screen opaque panel;
  - white caption treatment already used by the Table;
  - portrait positioned away from the route and active ship;
  - dialogue timed by the existing voice floor.
- On approach, let the destination expand from map marker to port artwork.
- Return to World level before the next departure so geography remains clear.
- Add subtle depth using separate map, weather, ship, artwork and caption layers.

#### Acceptance criteria

- Story and cut-scene moments never obscure both the active ship and destination.
- The viewer can identify origin, destination and current event without reading
  the player screen.
- Persona artwork does not cause a hard page-like cut away from the map.
- Arrival visibly ends at the correct port and hands off to the Port shot.
- Camera behavior remains stable at 1920x1080, 1600x900 and 768x1024.

**Recommended first release.** This phase creates the foundation and delivers a
substantial improvement without waiting for every port or fleet asset.

---

### Phase 2 — Fleet Bloom

**Goal:** Change smoothly between a readable world symbol and a close-up fleet
made from the Captain's actual ships.

#### Work

- Use one flagship token at World and distant Voyage scale.
- Define a zoom threshold at which the token separates into individual ships.
- Populate the close formation from frozen departure data:
  - ship type and artwork;
  - relative size;
  - hull condition;
  - cargo or escort role;
  - guns and cannons where useful.
- Arrange vessels in cinematic rows, with large ships central and escorts on the
  flanks. Preserve stable positions during a passage so ships do not shuffle.
- Represent condition without adding extra labels:
  - damaged ships trail or show restrained smoke/torn-sail treatments;
  - laden cargo ships sit slightly lower;
  - empty holds ride higher;
  - new purchases enter from the shipyard side;
  - lost ships leave a visible gap before formation closes.
- Collapse back to the single symbol as the camera pulls out.

#### Acceptance criteria

- The close formation contains exactly the ships recorded for that event.
- No current fleet data is substituted into an older voyage.
- A one-ship fleet still looks intentional.
- Large fleets remain legible without covering the destination or story artwork.
- Bloom/collapse works while paused, skipped and in reduced-motion mode.

---

### Phase 3 — Living Port Dioramas

**Goal:** Give each port a readable animated state that reflects what the Captain
is doing there.

#### Work

- Create a shared port stage with reusable activity lanes:
  - harbour water and anchorage;
  - dock and cargo lane;
  - market/warehouse lane;
  - bank/treasury lane;
  - customs or authority lane;
  - shipyard/repair lane.
- Use port-specific paintings as the visual base while activity silhouettes and
  props provide movement above it.
- Map journal events to activity beats:

| Event | Port activity |
|---|---|
| Buy | Crates/carts move market -> dock -> fleet |
| Sell | Cargo moves fleet -> dock; silver moves toward treasury |
| Deposit/withdraw | Silver moves between fleet and bank |
| Repair | Scaffolding, sail work and restrained sparks on affected ships |
| Buy ship | Vessel launches and joins the close fleet |
| Customs | Inspection launch, lanterns and authority pennant |
| Mayor commission | Mayor portrait and marked destination route |
| Pay dues/tax | Ledger seal and silver movement to authority |

- Keep figures secondary to the artwork. Prefer a few deliberate movements over
  a busy crowd simulation.
- Show the current port's most important facts only: cargo movement, silver
  change, fleet work and active commission.

#### Acceptance criteria

- Every animated activity is justified by a journal event.
- Repeated buys/sells remain understandable and do not create an unbounded queue.
- At most one primary activity plays at a time; related secondary activity may
  overlap only when it improves comprehension.
- A port with no new event settles into low-cost ambient motion.
- The stage remains readable if only the generic activity assets are available.

---

### Phase 4 — Danger Moving Through the World

**Goal:** Let weather, pursuit and battle form visibly around the fleet before
the close-up event artwork appears.

#### Work

- Render recorded regional weather as moving map fronts rather than static
  decoration.
- Increase sea motion and route uncertainty during recorded rough passages.
- Introduce event-specific approach beats after the journal event is known:
  - pirate sails or silhouettes emerge at the edge of the fleet shot;
  - protection adds an escort pennant or patrol vessel;
  - `run` orders tighten formation and increase speed;
  - `fight` orders turn the fleet toward broadside formation;
  - storm clouds, rain and wave motion intensify before storm artwork arrives.
- Present battle, storm, customs and robbery personas over the active map/fleet,
  followed by a visible consequence beat.
- Never show an attack or outcome before it exists in the journal; the Table is
  omniscient in presentation, not prophetic in game logic.

#### Acceptance criteria

- Calm voyages never receive danger cues.
- Orders, protection and weather match the frozen passage event.
- The sequence clearly distinguishes approach, encounter and result.
- Consequences such as hull damage or ship loss persist into the next fleet
  reveal when supported by recorded data.
- Animations remain synchronized with voice playback and scene pacing.

---

### Phase 5 — Twenty-Year World Transformation

**Goal:** Make long-term success visible in the world so Year 20 looks different
from Year 1.

#### Work

- Maintain a presentation-only campaign layer derived from journal history:
  - frequently travelled routes become brighter established trade lanes;
  - completed major contracts leave restrained route ribbons or seals;
  - favoured ports gain house pennants or influence accents;
  - home-port artwork evolves with estate stage;
  - mansion/palace milestones change heraldry and harbour presence;
  - important wealth, rank, fleet and estate milestones receive short chapter
    cards.
- Use a limited visual history window for ordinary route wakes while preserving
  major campaign achievements.
- Add optional Year/Chapter transitions so long quiet stretches still communicate
  progress.
- Derive all persistent decoration from journal/state facts; do not create new
  gameplay bonuses or rankings.

#### Acceptance criteria

- A fresh game shows a clean, restrained map.
- A late game visibly communicates greater reach, influence and fleet power.
- Historic decoration never blocks the live route or active event.
- Reconnect/reload reconstructs the same campaign layer deterministically.
- Long campaigns stay within defined DOM, canvas and animation budgets.

## 6. Event-to-shot examples

### Ordinary trade voyage

1. Port shot shows cargo purchase and silver leaving the fleet.
2. Camera pulls to World; destination and route illuminate.
3. One fleet symbol departs.
4. Camera tracks closer; Fleet Bloom reveals the formation.
5. Voyage facts appear briefly over the map.
6. Camera follows the approach and settles into destination Port view.
7. Cargo sale plays as dock movement with the existing trade receipt.

### Storm and pirate encounter

1. World shot establishes route and recorded rough region.
2. Camera moves to Voyage; weather front reaches the fleet.
3. Fleet Bloom reveals ships entering rough water.
4. Storm persona/cut scene appears over the live map.
5. Pirate sails emerge only after the attack event exists.
6. Fleet responds according to recorded run/fight orders.
7. Battle result appears, then the formation reflects recorded consequences.
8. Camera continues toward the actual destination.

### Major home-port milestone

1. Fleet arrives and Port view opens wider than normal.
2. Estate/contract/rank artwork appears over the harbour.
3. A short chapter card states the achievement.
4. Home-port stage gains its persistent new visual treatment.
5. Camera returns to normal port activity without trapping the spectator in a
   modal scene.

## 7. Data requirements

The first implementation should reuse existing frozen Table exports wherever
possible. New export fields should be added only when the visual cannot be
truthfully derived from current journal data.

### Already available or substantially available

- Origin, destination and route geometry.
- Recorded sea and regional weather.
- Fight/run orders and protection.
- Fleet count, type, hull, guns, cannons and capacity information.
- Cargo at departure and trade quantities/totals.
- Cash, bank, debt and total where journaled.
- Persona/cut-scene artwork roles and dialogue/voice ownership.
- Estate, rank, standing, contract and port information in game state or related
  views, subject to spectator privacy rules.

### Likely additions

- Stable ship ids and frozen per-ship presentation snapshots for Fleet Bloom.
- Explicit repair, ship purchase/loss and bank-transfer journal presentation
  fields when current events do not preserve enough detail.
- Consequence snapshots for post-battle fleet condition.
- Milestone events or deterministic milestone derivation for campaign history.

### Data rules

- Snapshot once at the game-event boundary.
- Deep-copy exports so Table presentation cannot alias mutable engine state.
- Validate every optional field in the presentation layer.
- Omit unavailable detail rather than infer it from later state.
- Keep solo/public visibility behavior unchanged unless separately designed and
  approved.

## 8. Technical approach

### Existing responsibilities to preserve

- `engine.py`: records immutable facts at the event boundary.
- `harbor_view.py`: exports a privacy-safe spectator view without game actions.
- `web/table-director.js`: orders journal events and creates cinematic shots.
- `web/table-motion.js`: route geometry, progress, camera framing and easing.
- `web/table-details.js`: validates display-only event facts.
- `web/table.js`: renders scene layers and coordinates the scene clock.
- `web/table.css`: visual composition and responsive/reduced-motion treatment.
- `tools/preview_table.py`: disposable visual theatre; never opens a saved game.

### Proposed presentation layers

From back to front:

1. Map and port base artwork.
2. Persistent campaign history.
3. Weather and sea conditions.
4. Route, destination and world fleet symbol.
5. Close fleet formation and port activity.
6. Persona/cut-scene artwork.
7. Captions, receipts and essential facts.
8. Playback controls and connection state.

Canvas or SVG should be chosen per layer rather than forcing the whole Table
into one technology. Existing DOM-based captions and image dissolves should
remain accessible; repeated map particles, wakes and activity silhouettes may
benefit from a bounded canvas layer.

## 9. Performance and motion budget

- Target smooth playback on the existing Pi-served LAN experience and common
  second-monitor hardware.
- Keep one `requestAnimationFrame` owner for scene movement.
- Pause animations when the page is hidden or playback is paused.
- Cap particles, route-history marks, port actors and simultaneous artwork.
- Preload only the next likely scene assets, not the entire gallery.
- Do not start a new camera transition until the previous scene clock state is
  resolved.
- Use CSS transforms/opacity for large artwork; avoid layout-heavy animation.
- Reduced motion must preserve chronology and information with short dissolves.

## 10. Testing strategy

### Automated

- Director tests for event-to-shot chronology and cursor seeding.
- Motion tests for camera interpolation, route framing, pause/resume and reduced
  motion.
- Fleet layout tests for one ship, mixed fleets, large fleets and stable slots.
- Detail validation tests for incomplete or malformed journal metadata.
- Export/privacy tests proving frozen snapshots and no multiplayer leakage.
- Port-activity tests proving each animation maps to an actual journal event.
- Campaign-layer reconstruction tests across reloads and long histories.
- Syntax/compile tests for every changed JS and Python file.

### Browser QA

Each phase should be exercised in the disposable Table theatre at:

- 1920x1080 primary display;
- 1600x900 common monitor;
- 768x1024 stacked/portrait display;
- normal and reduced motion;
- pause, resume and skip during every transition;
- missing artwork and missing optional data;
- reconnect while a scene is active.

Required preview scenarios should include calm voyage, rough voyage, buy, sell,
repair, bank transfer, ship purchase, customs, storm, battle, battle result,
Mayor commission, estate milestone and late-campaign world state.

### Live verification

- Never advance or alter the live saved game for testing.
- Verify served static file versions and hashes after deployment.
- Restart the backend only when Python/export changes require it.
- Confirm `/api/table` remains healthy and privacy-safe.
- Watch at least one natural live transition after each major release.
- Perform listening QA when voice timing or ownership changes.

## 11. Deployment plan

Each phase should ship independently behind a Table presentation version.

1. Back up only the specific Pi files being replaced.
2. Run focused automated tests and syntax/compile checks.
3. Exercise the full phase in the disposable preview theatre.
4. Copy only authorized files; never copy a locally dirty shared engine file
   wholesale.
5. Verify remote hashes and compile Python before any service restart.
6. Confirm the service is active and the live page reports the expected version.
7. Browser-test the live Table without taking game actions.
8. Record the release, screenshots, tests and backup location in `design/`.

A phase may be rolled back without reverting unrelated Table improvements.

## 12. Recommended implementation order

1. **Phase 0 — Scene contract and camera prototype**
2. **Phase 1 — Cinematic God-Camera**
3. **Phase 2 — Fleet Bloom**
4. **Phase 3 — Living Port Dioramas**
5. **Phase 4 — Danger Moving Through the World**
6. **Phase 5 — Twenty-Year World Transformation**

Phases 0 and 1 should be treated as the next development pass. They provide the
camera foundation on which every later idea depends and will immediately make
the existing artwork, routes, dialogue and voyage data feel like one unfolding
game rather than a collection of scenes.

## 13. Definition of success

The Table succeeds when a spectator who never touches the controls can watch a
complete sequence and correctly describe:

- where the Captain travelled;
- what the fleet looked like;
- what happened on the voyage;
- what changed at the destination;
- whether the Captain's maritime house is growing or struggling.

The final experience should feel like a historical strategy campaign being
directed live: the map provides continuity, the fleet provides scale, the
personas provide drama, the ports provide activity, and the changing world
provides the long story.
