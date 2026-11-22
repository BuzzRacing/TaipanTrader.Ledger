# Table voyage and trade context — 22 November 2026

Implemented the first three recommendations from the player-screen review and
deployed at `http://crimson.ledger/table`, page/script version
`20261122context4b` (director/details module version `20261122context4`).

## Changes

- Departure manifests show fleet size and armament, hold used/capacity, lowest
  hull percentage, and cargo with its existing gallery artwork.
- Voyages show recorded sea conditions, fight/run orders and remaining
  protection. Calm/fair passages use the calm Roxana painting; squalls/typhoons
  use her storm painting and the rain overlay. Regional weather on the voyage
  chart comes from the departure event, not the latest month's weather.
- Buy/sell receipts show cargo, units, total paid or sale proceeds, silver after
  the transaction and its signed cash movement. No profit is inferred from sale
  proceeds. Existing game dialogue and voices remain the source of narration.
- Receipt and departure scenes receive at least 6.5 seconds for their figures.
  Stacked layouts use the small locator chart and full-height portrait when a
  cargo panel is present, keeping the speaker's face visible above the receipt.
- New `web/table-details.js` validates presentation fields and omits unavailable
  historical values. It never borrows a current manifest for an older event.

## Data and deployment

The engine's `sailed` event now includes `table_manifest` (fleet count, hold,
guns, cannons, cargo and lowest hull) and `table_weather`. These are captured at
departure without new random calls or game actions. `harbor_view.py` copies the
recorded conditions, orders, protection and manifest into `passage` only for a
single-seat game. The director carries the same passage through departure and
voyage. Trade figures come from the existing journal's qty/total/cash fields.

Local `engine.py` contained unrelated pending work. It was not copied to the
Pi. Deployment inserted only the exact departure-event metadata block into the
live file, with an exact single-anchor guard and compile checks. The updated
`harbor_view.py` and five Table static files were copied separately. The game
service was restarted once and returned active. An isolated in-memory voyage
on the Pi verified the manifest/weather/export before that restart; it never
opened a saved game.

Previous deployed files are backed up at
`/home/madlively/SeaTrader/backups/table-context-v4-20261122/` on the Pi.
All five served static files and the installed exporter matched local SHA-256
hashes. `/api/table` returned a healthy current game. Live browser confirmed the
new page version and loaded details module with no live-page warnings/errors.

## Verification

Passed JS syntax checks, Python compilation, scoped diff checks and:

- `node tests/table_details_test.cjs`
- `node tests/table_motion_test.cjs`
- `node tests/table_director_test.cjs`
- `node tests/table_routes_test.cjs` (90 directed routes)
- `python tests/table_manifest_test.py`
- `python tests/table_story_test.py`
- `python tests/harbor_view_test.py`
- `python tests/table_audio_test.py`

Tests cover frozen cargo/fleet/weather after later mutations, export copies not
aliasing the journal, solo-only passage metadata, receipt arithmetic, missing
or invalid values, rough/calm artwork, unchanged observed/unobserved voyage
outcomes, chronology and existing audio coordination.

Browser QA used the disposable theatre for real simulated buy/sell events,
departure manifest, rough passage, and 768x1024 receipt layout. Sale fixture
deliberately sells below purchase cost, confirming the UI labels proceeds rather
than profit. The temporary preview showed expected reconnect warnings during
its restarts; no live-page warnings/errors were captured. Preview audio is
disabled; listening QA was not performed.

Preview theatre adds Rough seas, Purchase and Sale. Direct scenes:
`?scene=rough-voyage`, `?scene=buy`, `?scene=sell`, and `?scene=journey`.

Screenshots: `design/table-manifest-v4.jpg`,
`design/table-rough-voyage-v4.jpg`, `design/table-sale-receipt-v4.jpg`,
`design/table-receipt-stacked-v4.jpg`, `design/table-live-context-v4.jpg`.

The remaining review ideas (local standing, rank progression and month-end
accounts) were not included in this pass.
