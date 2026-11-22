# Compact Table captions — 22 November 2026

User requested the Captain screen's white text-over-artwork treatment for Table
persona names and statements, saving space.

Deployed `20261122captions5` to `http://crimson.ledger/table` using only
`web/table.html`, `web/table.js` and `web/table.css`; no service restart.

- Removed the framed/outlined/blurred story-card treatment and long role line.
- Grouped caption and data markup separately. Compact white headings, straight
  white dialogue and smaller white bylines sit over the existing artwork.
- Kept a soft bottom gradient and text shadows for contrast, without a card edge.
- Tightened facts, cargo thumbnails and spacing, preserving complete text and
  all receipt/manifest figures. Cash movement text is white too.
- The sale preview's total block measured about 327 screen pixels at 1600x900,
  roughly a fifth shorter than its previous framed presentation.

Browser QA: host, sale receipt, battle duet and 768x1024 stacked receipt. Checked
computed white dialogue, zero border and visible caption bounds. No truncation
or line clamping was introduced. JS syntax, existing Table details/motion tests
and scoped diff checks passed.

All three served files matched local SHA-256 hashes. Live browser verified the
new version, white text, zero border and no captured live warnings/errors.

Screenshots: `design/table-white-captions-v5.jpg` (sale preview),
`design/table-white-captions-live-v5.jpg` (live host).

Prior deployed files are backed up on the Pi at
`/home/madlively/SeaTrader/backups/table-captions-v5-20261122/`.
