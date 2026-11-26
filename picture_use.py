"""Picture use counter (25 Nov 2026).

Counts how many times each picture or clip is fetched from the server, so the
question "which picture has been used the most?" has an answer.

  record(path)   called by server.py for every GET of an image or clip
  report(n)      the busiest pictures, most used first, with what the Media Library knows of each
  python picture_use.py [N]    prints the report (reads journal/picture_use.json)

Counts live in journal/picture_use.json: {"since": <epoch>, "files": {url: {"n": count, "first": t, "last": t}}}.
Each request is one fetch. A browser that revalidates a cached picture still asks the server, so it still
counts; a browser that reuses a picture with no request at all does not. Treat the numbers as a ranking.
"""
import json
import os
import sys
import threading
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
FILE = os.path.join(ROOT, "journal", "picture_use.json")
EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".mp4", ".webm"}
PREFIXES = ("/media/", "/uploads/", "/assets/")
SAVE_EVERY = 20          # fetches between saves
SAVE_SECONDS = 60        # or this long since the last save

_lock = threading.Lock()
_data = None
_dirty = 0
_saved_at = 0.0


def counts_path(path):
    """True when this request is for a picture or clip we count."""
    return path.startswith(PREFIXES) and os.path.splitext(path)[1].lower() in EXT


def _load():
    global _data
    if _data is None:
        try:
            with open(FILE, "r", encoding="utf-8") as f:
                _data = json.load(f)
            if not isinstance(_data.get("files"), dict):
                raise ValueError("bad file")
        except Exception:
            _data = {"since": int(time.time()), "files": {}}
    return _data


def _save():
    global _dirty, _saved_at
    try:
        os.makedirs(os.path.dirname(FILE), exist_ok=True)
        tmp = FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(_data, f)
        os.replace(tmp, FILE)
    except OSError:
        return                       # counting must never break the game
    _dirty = 0
    _saved_at = time.time()


def record(path):
    """Add one to this picture's count. Safe to call from any thread; never raises."""
    global _dirty
    try:
        if not counts_path(path):
            return
        now = int(time.time())
        with _lock:
            d = _load()
            e = d["files"].setdefault(path, {"n": 0, "first": now, "last": now})
            e["n"] += 1
            e["last"] = now
            _dirty += 1
            if _dirty >= SAVE_EVERY or time.time() - _saved_at > SAVE_SECONDS:
                _save()
    except Exception:
        pass


def flush():
    with _lock:
        if _data is not None and _dirty:
            _save()


def _library():
    """{url: item} from the Media Library, for titles, subjects and roles."""
    try:
        with open(os.path.join(ROOT, "config", "media.json"), "r", encoding="utf-8") as f:
            items = json.load(f).get("items", [])
        return {i.get("url"): i for i in items if i.get("url")}
    except Exception:
        return {}


def report(n=20):
    """The n most-fetched pictures: [{url, n, first, last, title, kind, subject, roles, nsfw}]."""
    with _lock:
        d = _load()
        rows = sorted(d["files"].items(), key=lambda kv: -kv[1]["n"])[:max(1, int(n))]
        since = d.get("since")
        total = sum(e["n"] for e in d["files"].values())
        distinct = len(d["files"])
    lib = _library()
    out = []
    for url, e in rows:
        it = lib.get(url, {})
        out.append({"url": url, "n": e["n"], "first": e["first"], "last": e["last"],
                    "title": it.get("title", ""), "kind": it.get("kind", ""), "subject": it.get("subject", ""),
                    "roles": it.get("roles", []), "nsfw": bool(it.get("nsfw"))})
    return {"since": since, "total": total, "distinct": distinct, "top": out}


def main(argv):
    n = int(argv[1]) if len(argv) > 1 and argv[1].isdigit() else 20
    r = report(n)
    if not r["total"]:
        print("No pictures counted yet. The counter starts when the server runs the new code.")
        return
    print("Counting since {}: {} fetches, {} different pictures".format(
        time.strftime("%d %b %Y %H:%M", time.localtime(r["since"])), r["total"], r["distinct"]))
    for i, row in enumerate(r["top"], 1):
        label = row["title"] or "{} / {}".format(row["kind"], row["subject"]) if (row["title"] or row["kind"]) else ""
        print("{:>3}. {:>6}  {}  {}{}".format(i, row["n"], row["url"], label, "  [NSFW]" if row["nsfw"] else ""))


if __name__ == "__main__":
    main(sys.argv)
