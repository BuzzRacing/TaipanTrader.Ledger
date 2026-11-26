"""Media recipes: saved "fill to target" batches for Admin > Media Library (Anthony, 21 Nov 2026).

A recipe says what to fill (a kind, some subjects, some roles), how to count it (per subject or per subject and role),
and the target number of pictures. The Media Library page counts what is filed
and still queued, previews the shortfall and queues only that. Recipes live in config/media_recipes.json, so they are
the same from every browser and survive a restart. config/ is not touched by Deploy_To_Pi.bat.
"""
import json
import os
import re
import threading

ROOT = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(ROOT, "config", "media_recipes.json")
LOCK = threading.Lock()
KEY = re.compile(r"^[a-z0-9_]{1,40}$")
MOMENTS = ["sighting", "broadside", "enemy_hit", "we_are_hit", "ship_lost", "boarding", "got_away", "retreat",
           "victory", "defeat"]

STARTERS = [
    # Taipan Trader is clean only: every starter makes plain, fully dressed pictures.
    {"id": "starter_portpeople", "name": "Port people: 3 each", "kind": "port", "subjects": [],
     "roles": ["keeper", "shipmaster", "mayor", "taxlady"], "by": "role", "mode": "plain", "clean": 1, "nsfw": 0,
     "count": 3, "mood": "", "pose": True, "tag": "port-people"},
    {"id": "starter_battle", "name": "Sea battle moments: 3 each", "kind": "scene",
     "subjects": ["seafight_pirates", "seafight_lord"], "roles": MOMENTS, "by": "role", "mode": "plain",
     "clean": 1, "nsfw": 0, "count": 3, "mood": "", "pose": True, "tag": "battle-moments"},
    {"id": "starter_persona", "name": "Cast top-up: 3 each", "kind": "persona", "subjects": [],
     "roles": [], "by": "subject", "mode": "plain", "clean": 1, "nsfw": 0, "count": 3, "mood": "", "pose": True,
     "tag": "cast-topup"},
]


def _num(v, lo, hi, dflt):
    try:
        return max(lo, min(hi, int(v)))
    except (TypeError, ValueError):
        return dflt


def _keys(v, limit=300):
    return [x for x in (v or []) if isinstance(x, str) and KEY.match(x)][:limit]


ADULT = re.compile(r"nsfw|nude|naked|topless|sultry|boudoir", re.I)


def clean_one(r):
    if not isinstance(r, dict):
        return None
    # Taipan Trader: a recipe saved for adult pictures (by name or by its roles) is dropped, not converted.
    if ADULT.search(str(r.get("name") or "") + " " + " ".join(str(x) for x in r.get("roles") or [])):
        return None
    rid = str(r.get("id") or "")
    if not re.match(r"^[A-Za-z0-9_-]{1,40}$", rid):
        return None
    return {
        "id": rid,
        "name": str(r.get("name") or "Recipe").strip()[:80] or "Recipe",
        "kind": str(r.get("kind") or "persona")[:20],
        "subjects": _keys(r.get("subjects")),
        "roles": _keys(r.get("roles"), 60),
        "by": "role" if r.get("by") == "role" else "subject",
        "mode": "plain",                 # Taipan Trader: clean only, never NSFW + clean pairs
        "clean": _num(r.get("clean"), 0, 10, 1),
        "nsfw": 0,
        "count": _num(r.get("count"), 0, 20, 3),
        "mood": str(r.get("mood") or "").strip()[:400],
        "pose": bool(r.get("pose", True)),
        "tag": re.sub(r"[^a-z0-9_-]", "", str(r.get("tag") or "").lower())[:40],
        "last_run": str(r.get("last_run") or "")[:30],
        "last_made": _num(r.get("last_made"), 0, 100000, 0),
    }


def load():
    with LOCK:
        try:
            with open(PATH, encoding="utf-8") as f:
                data = json.load(f)
            out = [c for c in (clean_one(r) for r in data.get("recipes", [])) if c]
            return out
        except (OSError, ValueError, AttributeError):
            return [clean_one(r) for r in STARTERS]


def save(recipes):
    out, seen = [], set()
    for r in (recipes or [])[:100]:
        c = clean_one(r)
        if c and c["id"] not in seen:
            seen.add(c["id"])
            out.append(c)
    with LOCK:
        os.makedirs(os.path.dirname(PATH), exist_ok=True)
        tmp = PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"recipes": out}, f, indent=1, ensure_ascii=False)
        os.replace(tmp, PATH)
    return out
