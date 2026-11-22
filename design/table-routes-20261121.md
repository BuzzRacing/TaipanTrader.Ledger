# Table routes and arrival artwork — 21 November 2026

Deployed the next Table pass to `http://crimson.ledger/table`, version
`20261121routes3`, without restarting the service or changing game state.

## Presentation

- Added `web/assets/table/routes.json`: an authored sea-waypoint network for all
  ten existing ports. The Table uses shortest connected courses with rounded
  corners, distance-based sampling and matching ship headings. Port approaches
  terminate at the game's existing markers. These are visual courses, not a
  change to voyage costs, weather, events or gameplay routing.
- Framed the entire course, including southern detours. All 90 directed voyages
  have finite positions, matching endpoints, reversible geometry and visible
  camera bounds. Automated checks sample against `web/chart.js` coast polygons,
  allowing the short harbour approaches around inland port markers. The painted
  chart is approximate; browser inspection prompted additional clearance around
  the painted southern Vietnam cape.
- Longer courses receive 6.5–16 seconds, with a brief settled arrival. Narration
  finishing early no longer advances before the voyage presentation finishes.
  Pause and reduced-motion behavior are retained.
- Generated a new calm-voyage Roxana painting with the built-in `image_gen`
  tool, using the existing storm painting as an identity/costume reference.
  Final asset: `web/assets/table/table-underway-v1.webp`. Exact generation prompt
  and source reference: `design/table-underway-prompt.txt`. This painting is used
  for the Table's `underway` mood; other screens and storm art are unchanged.
- Arrival backgrounds now request the exact arrival role, then the port's banner
  role. They cannot fall through to an unrelated Mayor portrait as a background.
  Arrival respects the port's primary Mayor, retains explicit `table-arrival`
  gallery replacements, and adds a larger port title with a jade dialogue panel.
- Explicit tagged Table wallpaper compositions are fetched from the library's
  wallpaper slot, preserving ordinary speaker-slot filtering everywhere else.

## Preview and verification

`python tools/preview_table.py --gallery http://192.168.1.69:8765`

The disposable preview now includes `/routes`, with From/To selectors, and an
arrival scene. Direct examples:

- `/table?scene=route&from=calcutta&to=hongkong`
- `/table?scene=route&from=bangkok&to=hongkong`
- `/table?scene=arrival`

Browser QA covered Calcutta–Hong Kong, Bangkok–Hong Kong, Singapore arrival,
the new portrait loading, panorama/Mayor pairing, Linger, full-course framing
and a 768×1024 stacked layout. No captured browser warnings/errors. Preview
audio is disabled; audio listening QA was not performed.

Passed syntax checks, `tests/table_motion_test.cjs`, `tests/table_routes_test.cjs`,
`tests/table_director_test.cjs`, `tests/harbor_view_test.py`,
`tests/table_story_test.py`, `tests/table_audio_test.py`, and scoped diff checks.
Tests cover short narration not cutting travel short, primary Mayor selection,
strict arrival background selection, wallpaper-slot retrieval, all 90 courses,
pause timing and reduced motion.

All seven deployed files matched local SHA-256 hashes over the Pi's HTTP server.
Live browser confirmed `/table.js?v=20261121routes3`, loaded host art and no
captured warnings/errors. Backups of the prior deployed files are on the Pi at
`/home/madlively/SeaTrader/backups/table-routes-v3-20261121/web/`.

Screenshots: `design/table-voyage-preview-v3.jpg`,
`design/table-arrival-preview-v3.jpg`, and `design/table-live-v3.jpg`.

Other sessions' pending source changes were not included in deployment.
