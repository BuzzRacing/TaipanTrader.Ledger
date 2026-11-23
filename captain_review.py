"""Captain's review: the one-page, captain-friendly report of a recorded game.

Admin > Captain's Report > Captain's review shows it for any game in the journal.
The numbers are worked out from the game's journal by tools/playtest/playtest_report.py
and dropped into tools/playtest/report_template.html. A written review (what went
well, what to improve) is added when tools/playtest/findings/ holds a file whose
"game_id" matches the game; without one the page shows the numbers only.
"""
import glob
import importlib.util
import json
import os
import threading

import journal

ROOT = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.join(ROOT, "tools", "playtest")
_lock = threading.Lock()
_cache = {}                 # (gid, pid) -> (stamp, html)
_kit = None


def _builder():
    global _kit
    if _kit is None:
        spec = importlib.util.spec_from_file_location("playtest_report", os.path.join(KIT, "playtest_report.py"))
        _kit = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_kit)
    return _kit


def findings():
    """Every written review on disk, by game id."""
    out = {}
    for path in sorted(glob.glob(os.path.join(KIT, "findings", "*.json"))):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and data.get("game_id"):
            out[data["game_id"]] = data
    return out


def history(written=None):
    """Final net worth of every finished game on record, oldest first."""
    written = findings() if written is None else written
    rows = []
    for g in journal.games():
        years = g.get("years") or 0
        top = (g.get("standings") or [None])[0]
        if not top or not years or (g.get("turn") or 0) < years * 12:
            continue
        w = written.get(g["id"], {})
        rows.append({"id": g["id"], "game": w.get("game"), "years": years, "final": top.get("worth", 0),
                     "label": "" if w.get("game") else _day(g.get("started")), "started": g.get("started", 0),
                     "note": "{} of House {}".format(top.get("name", ""), top.get("firm", ""))})
    rows.sort(key=lambda r: r["started"])
    return rows


def _day(stamp):
    import time
    return time.strftime("%d %b %Y", time.localtime(stamp or 0))


def reviewed():
    """Game ids that have a written review, for the Admin list."""
    return {gid: w.get("game") for gid, w in findings().items()}


def page(gid, pid=None):
    """The review page for one game as HTML, or None when there is nothing to show."""
    path = journal.events_path(gid)
    if not path or not os.path.isfile(path):
        return None
    written = findings()
    mine = written.get(gid, {})
    template = os.path.join(KIT, "report_template.html")
    stamp = (os.path.getsize(path), os.path.getmtime(template), json.dumps(mine, sort_keys=True), len(journal.games()))
    with _lock:
        hit = _cache.get((gid, pid))
        if hit and hit[0] == stamp:
            return hit[1]
    kit = _builder()
    data = kit.build(os.path.dirname(path), mine.get("game"), pid)
    if data is None:
        return None
    data["findings"] = mine
    data["history"] = history(written)
    with open(template, encoding="utf-8") as f:
        html = kit.render(data, f.read())
    with _lock:
        if len(_cache) > 12:
            _cache.clear()
        _cache[(gid, pid)] = (stamp, html)
    return html
