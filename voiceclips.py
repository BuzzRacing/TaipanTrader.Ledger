"""Crimson Ledger voice clips: audit, rank, bin and re-record the saved voice lines.

Standard library only, like the rest of the server.

What this looks at. Every line the cast has read aloud is a saved MP3 in cache/voice/, noted
in cache/voice/index.jsonl (voice.py). This module turns that into one list for the Admin's
Voices > Clips page:
  * each saved clip is matched back to the game wording that produced it, and so to the persona
    who owns that line, and checked against her settings today (voice, speed, delivery note,
    wording): "current", or "out of date" with the reasons;
  * every speakable line that has no clip yet is listed as "missing" (lines with names or
    amounts in them are recorded on demand and are not listed);
  * a rank (1-5 stars), a Redo flag and a note can be kept on any clip;
  * a deleted clip goes to a Bin (cache/voice_bin/), never straight to oblivion, and can be
    restored; only "Empty the bin" removes audio for good;
  * per persona: clips, characters, share of everything spoken, stars, what needs attention.

Ranks, flags, notes, the bin list and the price per 1,000 characters live in
config/voice_clips.json. The audio and index.jsonl are never rewritten here, only moved.

The wording edit before recording is the Admin's existing spoken version (cfg voice.say), saved
with Save & apply like the rest of Cast & Voices; this module records with whatever it says.
"""
import json
import os
import re
import threading
import time

import cast
import strings
import voice

ROOT = os.path.dirname(os.path.abspath(__file__))
FILE = os.path.join(ROOT, "config", "voice_clips.json")
BIN_DIR = os.path.join(ROOT, "cache", "voice_bin")
NOTE_CHARS = 300
MIN_LITERAL = 6           # a wording template needs this many fixed letters to be matched to a clip

_lock = threading.RLock()


class ClipError(Exception):
    """Safe to show on the Admin page."""


# ------------------------------------------------------------------ store --
def _blank():
    return {"version": 1, "price_per_1k": 0.0, "clips": {}, "bin": {}}


def load():
    try:
        with open(FILE, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return _blank()
    out = _blank()
    if isinstance(data, dict):
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


def _cid(value):
    value = str(value or "")
    if not voice.CLIP_RE.match(value):
        raise ClipError("That is not a clip id.")
    return value


def index_rows():
    """Every clip ever paid for, newest record last-wins, from cache/voice/index.jsonl."""
    rows = {}
    try:
        with open(os.path.join(voice.CACHE_DIR, voice.INDEX_NAME), encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if isinstance(r, dict) and voice.CLIP_RE.match(str(r.get("clip") or "")):
                    rows[r["clip"]] = r
    except OSError:
        pass
    return rows


def _bin_path(cid):
    return os.path.join(BIN_DIR, cid + ".mp3")


def _mkdir(path):
    os.makedirs(path, exist_ok=True)


# --------------------------------------------------------------- matching --
def _variants(cfg, text, key):
    """The wordings a line has been read in: ("now", this wording as spoken today), ("family", the
    clean version, which Family-friendly screens still play), ("old", wording since replaced)."""
    out = [("now", cast.spoken_template(cfg, text, key)), ("now", text.get(key, ""))]
    for kind, src in (("family", strings.FAMILY), ("family", cast.SAY_FAMILY), ("old", cast.SAY), ("old", strings.EN)):
        if src.get(key):
            out.append((kind, src[key]))
    return out


def _patterns(cfg, text):
    """[(literal letters, key, kind, regex, has names)] for every spoken wording key, longest wording
    first. The regex matches the words as the voice says them (voice.speech_text), names filled in."""
    out = []
    for key in cast.spoken_keys(text):
        for kind, tpl in _variants(cfg, text, key):
            if not isinstance(tpl, str) or not tpl:
                continue
            marked = voice.speech_text(re.sub(r"\{\w+\}", "\x00", tpl))
            parts = marked.split("\x00")
            literal = sum(len(p.strip()) for p in parts)
            if literal < MIN_LITERAL:
                continue
            rx = "(.*?)".join(re.escape(p) for p in parts)
            try:
                out.append((literal, key, kind, re.compile("^" + rx + "$", re.DOTALL | re.IGNORECASE), len(parts) > 1))
            except re.error:
                continue
    out.sort(key=lambda p: -p[0])          # stable: at equal length, "now" is tried before the older wordings
    return out


def _key_of(patterns, said):
    """(key, has names, kind) for a clip's words, or ("", False, "")."""
    said = str(said or "").strip()
    for _lit, key, kind, rx, tokens in patterns:
        if rx.match(said):
            return key, tokens, kind
    return "", False, ""


def _speakers(cfg):
    """voice id -> [character ids] for characters that have a voice."""
    by = {}
    for cid, c in cfg["characters"].items():
        vid = (c.get("voice_id") or "").strip()
        if vid:
            by.setdefault(vid, []).append(cid)
    return by


def _owner(cfg, key, row, by_voice):
    """Who reads a line. Port Authority and jail lines belong to the officer or warden of the player's
    port, so for those the persona is the port character who has the clip's voice."""
    owner = cast.speaker_for(cfg, key)
    if key in cast.OFFICER_KEYS or key in getattr(cast, "WARDEN_KEYS", ()):
        cands = [c for c in by_voice.get(row.get("voice_id") or "", []) if c.startswith(("officer_", "warden_"))]
        return cands[0] if cands else ""       # an officer voiced before a recasting: who it was is not known
    return owner


def _reads(key):
    """Whether a line is ever read aloud by the Captain's Log rules (below the floor it is shown only)."""
    if not key.startswith("l."):
        return True
    if key in voice.ROUTINE_LOG:
        return False
    rank = max(voice.LOG_RANK.get(key, 10), voice.JAIL_RANK.get(key, 10))
    return rank >= voice.VOICE_FLOOR


def _params_for(cfg, cid, said):
    ch = cfg["characters"].get(cid) or {}
    return voice._params(said, ch, cfg["voice"])


def _diffs(cfg, row, cid, said):
    """What changed in her settings since a clip was recorded: voice, speed, delivery, model, variation."""
    cur = _params_for(cfg, cid, said)
    out = []
    if (row.get("voice_id") or "") != cur["voice_id"]:
        out.append("voice")
    if "rate" in row and abs(float(row.get("rate") or 1.0) - cur["rate"]) > 0.0005:
        out.append("speed")
    if "delivery" in row and (row.get("delivery") or "") != cur["delivery"]:
        out.append("delivery")
    if (row.get("model_id") or "") != cur["model_id"]:
        out.append("model")
    if "temperature" in row and abs(float(row.get("temperature") or 1.0) - cur["temperature"]) > 0.0005:
        out.append("temperature")
    return out


def view(cfg, text):
    """Everything the Clips page needs, in one answer."""
    store = load()
    rows = index_rows()
    pats = _patterns(cfg, text)
    chars = cfg["characters"]
    by_voice = _speakers(cfg)
    groups = cast.SPOKEN_GROUPS
    clips, covered_keys = [], set()
    for cid, r in rows.items():
        on_disk = os.path.isfile(voice.clip_path(cid))
        binned = cid in store["bin"] and os.path.isfile(_bin_path(cid))
        if not on_disk and not binned:
            continue                                   # the file is gone from both places
        key, tokens, kind = _key_of(pats, r.get("text"))
        owner = _owner(cfg, key, r, by_voice) if key else ""
        told = r.get("who") if r.get("who") in chars else ""     # newer clips say who spoke them
        owner = told or owner
        # The owner is whoever reads that line now; for a line we cannot place, the one persona who
        # has that voice (several: it is a shared voice and the clip is not pinned to one).
        shared = []
        if not owner:
            shared = by_voice.get(r.get("voice_id") or "", [])
            owner = shared[0] if len(shared) == 1 else ""
            shared = shared if len(shared) > 1 else []
        said = r.get("text") or ""
        diffs, status = [], "recorded"
        if (key or told) and owner and owner in chars:
            if "rate" in r or "delivery" in r:
                diffs = _diffs(cfg, r, owner, said)
                status = "stale" if diffs else "current"
            else:
                status = "early"                       # recorded before settings were noted: cannot be audited
            if key and kind == "old" and status != "early":
                if "wording" not in diffs:
                    diffs.append("wording")
                status = "stale"
            if key and kind == "now":
                covered_keys.add(key)
        meta = store["clips"].get(cid) or {}
        screen = text.get(key, "") if key else ""
        clips.append({
            "id": cid, "status": "binned" if binned and not on_disk else status, "binned": bool(binned and not on_disk),
            "text": said, "screen": screen, "key": key, "group": groups.get(key.split(".")[0], "") if key else "",
            "names": bool(tokens), "variant": kind, "current": (voice.speech_text(cast.spoken_template(cfg, text, key))
                                                              if key and not tokens else ""), "persona": owner, "shared": shared, "voice": r.get("voice_id") or "",
            "model": r.get("model_id") or "", "rate": r.get("rate"), "delivery": r.get("delivery") or "",
            "at": r.get("at") or "", "bytes": int(r.get("bytes") or 0), "chars": len(said), "diffs": diffs,
            "stars": int(meta.get("stars") or 0), "redo": bool(meta.get("redo")), "note": meta.get("note") or "",
            "binned_at": (store["bin"].get(cid) or {}).get("at", 0) if binned and not on_disk else 0,
        })
    # Lines with fixed wording and nobody's clip yet.
    missing, silent = [], 0
    for key in cast.spoken_keys(text):
        tpl = cast.spoken_template(cfg, text, key)
        if re.search(r"\{\w+\}", tpl) or key in covered_keys:
            continue
        if key in cast.OFFICER_KEYS or key in getattr(cast, "WARDEN_KEYS", ()):
            continue                                   # read by the officer or warden of the player's port
        if not _reads(key):
            silent += 1
            continue
        owner = cast.speaker_for(cfg, key)
        ch = chars.get(owner) or {}
        said = voice.speech_text(tpl)
        if not owner or not ch.get("voice_id") or not said:
            continue
        cid = voice.clip_id(_params_for(cfg, owner, said))
        if cid in rows and (os.path.isfile(voice.clip_path(cid)) or cid in store["bin"]):
            continue
        missing.append({"id": "", "status": "missing", "binned": False, "variant": "now", "text": said, "screen": text.get(key, ""),
                        "key": key, "group": groups.get(key.split(".")[0], ""), "names": False, "persona": owner,
                        "current": said, "shared": [], "voice": ch.get("voice_id") or "", "model": cfg["voice"]["model_id"],
                        "rate": ch.get("speaking_rate"), "delivery": "", "at": "", "bytes": 0, "chars": len(said),
                        "diffs": [], "stars": 0, "redo": False, "note": "", "binned_at": 0})
    return {"clips": clips, "missing": missing, "silent_lines": silent, "personas": _persona_stats(cfg, clips, missing),
            "price_per_1k": store["price_per_1k"], "bin_count": sum(1 for c in clips if c["binned"]),
            "totals": _totals(clips, missing), "diff_labels": DIFF_LABELS}


DIFF_LABELS = {"voice": "her voice changed", "speed": "speed changed", "delivery": "delivery note changed",
               "model": "model changed", "temperature": "variation changed", "wording": "wording changed"}


def _totals(clips, missing):
    live = [c for c in clips if not c["binned"]]
    return {"clips": len(live), "chars": sum(c["chars"] for c in live), "bytes": sum(c["bytes"] for c in live),
            "missing": len(missing), "stale": sum(c["status"] == "stale" for c in live),
            "redo": sum(c["redo"] for c in live), "unrated": sum(not c["stars"] for c in live)}


def _persona_stats(cfg, clips, missing):
    out = {}

    def slot(cid):
        return out.setdefault(cid or "", {"clips": 0, "chars": 0, "bytes": 0, "stale": 0, "redo": 0, "rated": 0,
                                          "star_sum": 0, "missing": 0, "low": 0})
    for c in clips:
        if c["binned"]:
            continue
        s = slot(c["persona"])
        s["clips"] += 1
        s["chars"] += c["chars"]
        s["bytes"] += c["bytes"]
        s["stale"] += c["status"] == "stale"
        s["redo"] += c["redo"]
        if c["stars"]:
            s["rated"] += 1
            s["star_sum"] += c["stars"]
            s["low"] += c["stars"] <= 2
    for m in missing:
        slot(m["persona"])["missing"] += 1
    total = sum(s["chars"] for s in out.values()) or 1
    for s in out.values():
        s["share"] = round(100.0 * s["chars"] / total, 1)
        s["avg_stars"] = round(s["star_sum"] / s["rated"], 2) if s["rated"] else 0
        del s["star_sum"]
    return out


# ---------------------------------------------------------------- actions --
def rate(cid, stars=None, redo=None, note=None):
    cid = _cid(cid)
    with _lock:
        data = load()
        m = dict(data["clips"].get(cid) or {})
        if stars is not None:
            try:
                n = int(stars)
            except (TypeError, ValueError):
                raise ClipError("Stars are 0 to 5.")
            if not 0 <= n <= 5:
                raise ClipError("Stars are 0 to 5.")
            m["stars"] = n
        if redo is not None:
            m["redo"] = bool(redo)
        if note is not None:
            m["note"] = " ".join(str(note).split())[:NOTE_CHARS]
        if not (m.get("stars") or m.get("redo") or m.get("note")):
            data["clips"].pop(cid, None)
        else:
            data["clips"][cid] = {"stars": int(m.get("stars") or 0), "redo": bool(m.get("redo")),
                                  "note": m.get("note") or ""}
        _save(data)
        return data["clips"].get(cid) or {"stars": 0, "redo": False, "note": ""}


def set_price(value):
    try:
        v = round(float(value), 4)
    except (TypeError, ValueError):
        raise ClipError("The price is a number (dollars per 1,000 characters).")
    if not 0 <= v <= 100:
        raise ClipError("The price is a number from 0 to 100.")
    with _lock:
        data = load()
        data["price_per_1k"] = v
        _save(data)
    return v


def bin_clip(cid, why=""):
    """Moves a clip's audio to the bin. The game pays for a fresh take if that line is spoken again."""
    cid = _cid(cid)
    src = voice.clip_path(cid)
    with _lock:
        if not os.path.isfile(src):
            raise ClipError("That clip is not in the saved clips (already in the bin?).")
        _mkdir(BIN_DIR)
        os.replace(src, _bin_path(cid))
        data = load()
        data["bin"][cid] = {"at": int(time.time()), "why": str(why or "")[:80]}
        _save(data)


def restore(cid):
    cid = _cid(cid)
    with _lock:
        data = load()
        if not os.path.isfile(_bin_path(cid)):
            data["bin"].pop(cid, None)
            _save(data)
            raise ClipError("That clip is not in the bin.")
        if os.path.isfile(voice.clip_path(cid)):
            raise ClipError("A newer take of that line has been recorded since, so it was not restored. "
                            "Empty the bin if you do not want the old one.")
        _mkdir(voice.CACHE_DIR)
        os.replace(_bin_path(cid), voice.clip_path(cid))
        data["bin"].pop(cid, None)
        _save(data)


def empty_bin():
    """Removes the binned audio for good. The only place paid audio is ever deleted."""
    n = 0
    with _lock:
        data = load()
        try:
            names = os.listdir(BIN_DIR)
        except OSError:
            names = []
        for f in names:
            if f.endswith(".mp3"):
                try:
                    os.remove(os.path.join(BIN_DIR, f))
                    n += 1
                except OSError:
                    pass
        data["bin"] = {}
        _save(data)
    return n


def bin_audio(cid):
    cid = _cid(cid)
    try:
        with open(_bin_path(cid), "rb") as f:
            return f.read()
    except OSError:
        raise ClipError("That clip is not in the bin.")


def record(cfg, text, cid="", key=""):
    """Records a line with the settings and spoken wording as they are now.

    cid: an existing clip to take again (it is moved to the bin first, so Inworld gives a new take
    even when nothing has changed). key: a line that has no clip yet. Returns the new clip id."""
    if cid:
        cid = _cid(cid)
        old = index_rows().get(cid)
        if not old:
            raise ClipError("That clip is not in the saved index.")
        said_old = old.get("text") or ""
        k, tokens, kind = _key_of(_patterns(cfg, text), said_old)
        if key and key in cast.spoken_keys(text):          # the page knows the line (its wording may just have been edited)
            k = key
            tokens = bool(re.search(r"\{\w+\}", cast.spoken_template(cfg, text, k)))
            kind = "now"
        owner = _owner(cfg, k, old, _speakers(cfg)) if k else ""
        if old.get("who") in cfg["characters"]:
            owner = old["who"]
        if not owner:
            by = _speakers(cfg).get(old.get("voice_id") or "", [])
            owner = by[0] if len(by) == 1 else ""
        if k and not tokens and kind != "family":
            said = voice.speech_text(cast.spoken_template(cfg, text, k))   # picks up an edited spoken version
        else:
            said = said_old
        if owner:
            params = _params_for(cfg, owner, said)
        else:                                         # a shared voice we cannot place: take it again as it was
            params = {"text": said, "voice_id": old.get("voice_id") or "",
                      "model_id": old.get("model_id") or cfg["voice"]["model_id"],
                      "rate": round(float(old.get("rate") or 1.0), 3),
                      "temperature": round(float(old.get("temperature") or cfg["voice"]["temperature"]), 3),
                      "delivery": old.get("delivery") or ""}
        had = os.path.isfile(voice.clip_path(cid))
        if had:
            bin_clip(cid, "re-recorded")
        try:
            voice.render(params)
        except voice.VoiceError:
            if had:
                try:
                    restore(cid)
                except ClipError:
                    pass
            raise
        new = voice.clip_id(params)
        rate(cid, redo=False)
        return new
    key = str(key or "")
    if key not in cast.spoken_keys(text):
        raise ClipError("That line is not in the game wording.")
    tpl = cast.spoken_template(cfg, text, key)
    if re.search(r"\{\w+\}", tpl):
        raise ClipError("That line has names or amounts in it; it is recorded the first time it comes up in play.")
    owner = cast.speaker_for(cfg, key)
    if not owner or not (cfg["characters"].get(owner) or {}).get("voice_id"):
        raise ClipError("Nobody with a voice reads that line yet.")
    params = _params_for(cfg, owner, voice.speech_text(tpl))
    voice.render(params)
    return voice.clip_id(params)


def handle(what, body, cfg, text):
    """The Admin's POST routes under voice/clips/. Returns the answer as a dict."""
    try:
        if what == "rate":
            return {"ok": True, "id": body.get("id"), "meta": rate(body.get("id"), body.get("stars"), body.get("redo"),
                                                                    body.get("note"))}
        if what == "bin":
            bin_clip(body.get("id"), body.get("why"))
            return {"ok": True}
        if what == "restore":
            restore(body.get("id"))
            return {"ok": True}
        if what == "empty_bin":
            return {"ok": True, "removed": empty_bin()}
        if what == "price":
            return {"ok": True, "price_per_1k": set_price(body.get("price"))}
        if what == "record":
            new = record(cfg, text, cid=body.get("id") or "", key=body.get("key") or "")
            return {"ok": True, "clip": new}
    except ClipError as e:
        return {"ok": False, "error": str(e)}
    except voice.VoiceError as e:
        return {"ok": False, "error": str(e)}
    except OSError as e:
        return {"ok": False, "error": "Could not change the saved clips: {}".format(e)}
    return {"ok": False, "error": "Not found"}
