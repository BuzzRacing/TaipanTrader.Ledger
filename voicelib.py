"""Crimson Ledger voice library: the saved list of Inworld voices used to cast the personas.

Standard library only, like the rest of the server.

Why a saved list. Inworld's catalogue changes: voices are added, and now and then one is
retired. The game stores a voice ID on each character, and a voice ID never changes what it
sounds like, so a casting stays right for as long as the voice exists. This file keeps a
snapshot of the catalogue so that:
  * the Voice Library page works from one steady list, not whatever Inworld sends today;
  * "Check Inworld for changes" shows exactly what is new and what has gone since last time;
  * a character whose voice has gone from Inworld is flagged before her lines fall silent;
  * shortlist marks and notes about each voice are kept with the list.

Saved in config/voice_library.json. Every voice ever seen stays in the file: one that
leaves Inworld is marked gone, not dropped, so the page can still say what it was.
"""
import json
import os
import threading
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
FILE = os.path.join(ROOT, "config", "voice_library.json")
RATINGS = ("", "star", "maybe", "no")
NOTE_CHARS = 300
SAMPLE_CHARS = 300
HISTORY = 30
# The one line every voice reads when nobody in particular is being cast (house voice).
DEFAULT_SAMPLE = ("Welcome aboard, Captain. Stow your cargo wherever you like, darling. "
                  "I do so admire a man who knows how to fill a hold.")

_lock = threading.RLock()


def _blank():
    return {"version": 1, "refreshed_at": 0, "sample_text": "", "voices": {}, "marks": {}, "history": []}


def load():
    try:
        with open(FILE, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return _blank()
    if not isinstance(data, dict):
        return _blank()
    out = _blank()
    for k in out:
        if isinstance(data.get(k), type(out[k])):
            out[k] = data[k]
    return out


def _save(data):
    os.makedirs(os.path.dirname(FILE), exist_ok=True)
    tmp = FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
    os.replace(tmp, FILE)


def refresh(rows, now=None):
    """Folds a fresh voice list from Inworld (voice.list_voices) into the saved one.

    Returns {"added": [ids], "removed": [ids], "back": [ids], "first": bool}. An empty list is
    refused, so a bad answer from Inworld can never mark the whole library as gone."""
    rows = [r for r in (rows or []) if isinstance(r, dict) and r.get("id")]
    if not rows:
        raise ValueError("Inworld sent an empty voice list; the saved list was left as it is.")
    now = int(now or time.time())
    with _lock:
        data = load()
        first = not data["voices"]
        seen, added, back = set(), [], []
        for r in rows:
            vid = str(r["id"])
            seen.add(vid)
            old = data["voices"].get(vid)
            row = {k: r.get(k) for k in ("id", "name", "description", "gender", "age", "lang", "source", "tags")}
            row["first_seen"] = old["first_seen"] if old else now
            row["last_seen"] = now
            row["gone_at"] = 0
            if old is None:
                added.append(vid)
            elif old.get("gone_at"):
                back.append(vid)
            data["voices"][vid] = row
        removed = []
        for vid, old in data["voices"].items():
            if vid not in seen and not old.get("gone_at"):
                old["gone_at"] = now
                removed.append(vid)
        data["refreshed_at"] = now
        if not first and (added or removed or back):
            data["history"] = ([{"at": now, "added": added, "removed": removed, "back": back}]
                               + data["history"])[:HISTORY]
        _save(data)
    return {"added": [] if first else added, "removed": removed, "back": back, "first": first}


def mark(voice_id, rating=None, note=None):
    """Shortlist mark ("star", "maybe", "no" or "") and a note for one voice."""
    vid = str(voice_id or "").strip()
    with _lock:
        data = load()
        if vid not in data["voices"]:
            raise ValueError("That voice is not in the saved list.")
        m = dict(data["marks"].get(vid) or {})
        if rating is not None:
            if rating not in RATINGS:
                raise ValueError("Unknown mark.")
            m["rating"] = rating
        if note is not None:
            m["note"] = " ".join(str(note).split())[:NOTE_CHARS]
        if m.get("rating") or m.get("note"):
            data["marks"][vid] = {"rating": m.get("rating", ""), "note": m.get("note", "")}
        else:
            data["marks"].pop(vid, None)
        _save(data)
        return data["marks"].get(vid, {"rating": "", "note": ""})


def set_sample(text):
    """The line every voice reads on the Voice Library page. Empty goes back to the stock line."""
    text = " ".join(str(text or "").split())[:SAMPLE_CHARS]
    with _lock:
        data = load()
        data["sample_text"] = "" if text == DEFAULT_SAMPLE else text
        _save(data)
    return text or DEFAULT_SAMPLE


def public():
    """What the Admin page is given."""
    data = load()
    voices = sorted(data["voices"].values(),
                    key=lambda v: (bool(v.get("gone_at")), not str(v.get("lang") or "").lower().startswith("en"),
                                   str(v.get("name") or "").lower()))
    return {"refreshed_at": data["refreshed_at"], "sample_text": data["sample_text"] or DEFAULT_SAMPLE,
            "default_sample": DEFAULT_SAMPLE, "voices": voices, "marks": data["marks"],
            "history": data["history"][:5]}


def _men():
    import cast
    return cast.MEN


def check_cast(characters, data=None):
    """Casting problems, worst first: [{"character", "voice_id", "problem", "detail"}].

    problem is one of: none (no voice set), gone (left Inworld), unknown (never in the saved
    list), male (the voice is listed for the other gender: cast.MEN are the men), shared (several characters use the same voice)."""
    data = data or load()
    voices, have = data["voices"], bool(data["voices"])
    users, out = {}, []
    for cid, c in (characters or {}).items():
        vid = str((c or {}).get("voice_id") or "").strip()
        if vid:
            users.setdefault(vid, []).append(cid)
    for cid, c in (characters or {}).items():
        vid = str((c or {}).get("voice_id") or "").strip()
        v = voices.get(vid)
        if not vid:
            out.append({"character": cid, "voice_id": "", "problem": "none", "detail": "No voice set."})
        elif have and v is None:
            out.append({"character": cid, "voice_id": vid, "problem": "unknown",
                        "detail": "Not in the saved Inworld list."})
        elif v and v.get("gone_at"):
            out.append({"character": cid, "voice_id": vid, "problem": "gone",
                        "detail": "No longer offered by Inworld; new lines will fail."})
        elif v and v.get("gender") in ("male", "female") and (v["gender"] == "male") != (cid in _men()):
            out.append({"character": cid, "voice_id": vid, "problem": "male",
                        "detail": "Listed as a {} voice.".format(v["gender"])})
        elif len(users.get(vid, [])) > 1:
            out.append({"character": cid, "voice_id": vid, "problem": "shared",
                        "detail": "Also used by " + ", ".join(x for x in users[vid] if x != cid) + "."})
    order = {"gone": 0, "unknown": 1, "none": 2, "male": 3, "shared": 4}
    out.sort(key=lambda p: order[p["problem"]])
    return out
