"""Media recipes: saved "fill to target" batches for Admin > Media Library (Anthony, 21 Nov 2026).

A recipe says what to fill (a kind, some subjects, some roles), how to count it (per subject or per subject and role),
and the target (for pairs: N clean + N NSFW; for plain pictures: N). The Media Library page counts what is filed
and still queued, previews the shortfall and queues only that. Recipes live in config/media_recipes.json, so they are
the same from every browser and survive a restart. config/ is not touched by Deploy_To_Pi.bat.
"""
import json
import os
import re
import threading

import recipe_scenes

ROOT = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(ROOT, "config", "media_recipes.json")
LOCK = threading.Lock()
KEY = re.compile(r"^[a-z0-9_]{1,40}$")
MOMENTS = ["sighting", "broadside", "enemy_hit", "we_are_hit", "ship_lost", "boarding", "got_away", "retreat",
           "victory", "defeat"]

STARTERS = [
    {"id": "starter_portwomen", "name": "Port women: 1 clean + 5 NSFW each", "kind": "port", "subjects": [],
     "roles": ["keeper", "shipmaster", "mayor", "taxlady"], "by": "role", "mode": "pairs", "clean": 1, "nsfw": 5,
     "count": 3, "mood": "", "pose": True, "tag": "port-women"},
    {"id": "starter_battle", "name": "Sea battle moments: 3 each", "kind": "scene",
     "subjects": ["seafight_pirates", "seafight_lord"], "roles": MOMENTS, "by": "role", "mode": "plain",
     "clean": 1, "nsfw": 0, "count": 3, "mood": "", "pose": True, "tag": "battle-moments"},
    # The tax-lady desk tells and the weather pictures, as recipes (24 Nov 2026). Prompts come from recipe_scenes.py, which
    # runs the same code as the Queue_TaxLady_*_Pairs.bat and Queue_Weather_*.bat files. The roles are recipe_scenes' own
    # names for each exact picture; only an officer (or the crier) has prompts for them, so the others are skipped.
    {"id": "tax_desk_faces", "name": "Port Authority desk tells: 1 clean + 1 NSFW each", "kind": "persona",
     "subjects": [], "roles": recipe_scenes.TAX_ENTRY_ROLES, "by": "role", "mode": "pairs", "clean": 1, "nsfw": 1,
     "count": 1, "mood": "", "pose": False, "tag": "tax-desk"},
    {"id": "weather_nude_looks", "name": "Newspaper weather NSFW: nude, 4 poses each weather", "kind": "persona",
     "subjects": ["crier"], "roles": recipe_scenes.WEATHER_NUDE_ROLES, "by": "role", "mode": "pairs", "clean": 0,
     "nsfw": 4, "count": 1, "mood": "", "pose": True, "tag": "weather"},
    {"id": "weather_topless_looks", "name": "Newspaper weather NSFW: topless, 5 poses each weather", "kind": "persona",
     "subjects": ["crier"], "roles": recipe_scenes.WEATHER_TOPLESS_ROLES, "by": "role", "mode": "pairs", "clean": 0,
     "nsfw": 5, "count": 1, "mood": "", "pose": True, "tag": "weather"},
    {"id": "weather_clean_looks", "name": "Newspaper weather clean: 5 poses each weather", "kind": "persona",
     "subjects": ["crier"], "roles": recipe_scenes.WEATHER_CLEAN_ROLES, "by": "role", "mode": "pairs", "clean": 5,
     "nsfw": 0, "count": 1, "mood": "", "pose": True, "tag": "weather"},
    {"id": "starter_persona", "name": "Cast top-up: 2 clean + 2 NSFW each", "kind": "persona", "subjects": [],
     "roles": [], "by": "subject", "mode": "pairs", "clean": 2, "nsfw": 2, "count": 3, "mood": "", "pose": True,
     "tag": "cast-topup"},
]


def _num(v, lo, hi, dflt):
    try:
        return max(lo, min(hi, int(v)))
    except (TypeError, ValueError):
        return dflt


def _keys(v, limit=300):
    return [x for x in (v or []) if isinstance(x, str) and KEY.match(x)][:limit]


def clean_one(r):
    if not isinstance(r, dict):
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
        "mode": "plain" if r.get("mode") == "plain" else "pairs",
        "clean": _num(r.get("clean"), 0, 10, 1),
        "nsfw": _num(r.get("nsfw"), 0, 20, 5),
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
