# Captain's review (playtest reports)

One interactive page per recorded game.

**In the Admin:** Command Center > Captain's Report > Captain's review. Pick any game from the list;
the page is built from that game's journal when it is opened (`captain_review.py` at the top of the
project, route `/api/admin/journal/review?game=<id>`).

- `playtest_report.py` reads a game's `events.jsonl` and `meta.json` and works out every number.
- `report_template.html` is the page; the numbers are dropped into it.
- `findings\*.json` are the written reviews (headline, what went well, areas to improve, last game's
  fixes). A file is shown with the game whose id matches its `"game_id"`; `"game"` is its number.
  A game with no file shows the numbers only.

**By hand, to a file:**

    python playtest_report.py <journal\games\gYYYYMMDD-...> --game 8 --findings findings\game-08.json --out game-08.html

`history.json` is only used by this by-hand route; the Admin page reads the finished games from the journal.
