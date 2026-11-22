# Table polish — 21 November 2026

Reviewed the live `/table`, README continuity, Table director, preview theatre,
and the six completed compositions in `design/table-concepts-v01/farm/`.

This pass is deployed to the Pi at `192.168.1.69`, using only Table static files.
No service restart, game-state mutation, shared media-library changes, or other
sessions' pending files were included.

## Changes

- Bundled the six completed paintings under `web/assets/table/`, configured by
  `art.json`. The current Pi catalog did not expose their Table tags. Explicit
  tagged gallery paintings take priority over the bundled compositions.
- Fixed explicit Table paintings being excluded by their shared wallpaper role.
- Preloaded character paintings and dissolved between them, retaining the old
  image until its replacement loads and logging failures.
- Replaced independent SVG motion with scene-clock travel: eased departure and
  arrival, heading along the curve, a revealed course, wake and destination ring.
  Pausing preserves position; reduced motion shows the destination immediately.
- Added dialogue entrance, stronger glass/brass separation, chart inset shading,
  quieter controls and full-width dialogue in stacked layouts.
- Pausing completes finite reveal animations so dialogue remains readable.

## Verification

Passed `node --check web/table.js`, `node tests/table_motion_test.cjs`,
`node tests/table_director_test.cjs`, `python tests/harbor_view_test.py`,
`python tests/table_story_test.py`, `python tests/table_audio_test.py`,
and scoped `git diff --check`.

Browser checks used the disposable preview with the Pi gallery: host, journey,
battle, storm and 768×1024 stacked layout. Two successive DOM observations showed
identical ship transforms and course progress during pause. Live browser check
confirmed the new script version, loaded bundled host art and no captured
warnings/errors. All eleven deployed files matched local SHA-256 hashes through
the Pi's HTTP server. Preview audio is disabled; listening QA was not performed.

Live screenshot: `design/table-polish-live-20261121.jpg`.
Previous live page/script/style backed up on the Pi at
`/home/madlively/SeaTrader/backups/table-polish-20261121/web/`.

## Recommended next pass

Art-direct matching calm-underway and port-arrival paintings for Roxana and the
Mayors. These still draw from the existing general gallery. Review coast-aware
routes: current travel follows the existing illustrative quadratic course,
not navigable sea waypoints. Use the isolated theatre for approval and testing.
