"""Dialogue Banks: every bank of lines the game, Dashboard, Table and Manual pull in, by persona or story.

Admin > Language & Text > Dialogue Banks (web/banks-admin.js). Slice 1 (22 Nov 2026) is READ-ONLY: it builds a
catalogue from the wording the game already has (strings.EN and strings.FAMILY, plus the Language & Text
overrides) and audits it. Nothing here changes what the game says. Editing, adding and removing lines come in
slice 2, stored as an overlay in config/banks/ (decision A, 22 Nov 2026).

What a bank is
    A bank is the set of numbered lines of one stem: "m.borrowed.easy.0", ".1", ".2" is the bank
    "m.borrowed.easy". A spoken line that has no number (a single line a persona says) is shown as a bank of one,
    so thin spots are visible. Written-only banks (captions, page steps) are included and marked "written".

Spicy and clean
    spicy = the house-voice wording (strings.EN). clean = the family-friendly wording (strings.FAMILY). A line
    with no clean twin falls back to its spicy wording on a Family-friendly screen, so that is flagged.

Who owns a bank
    The persona who reads it aloud (cast.speaker_for, or manual_text.SPEAKER for the Manual); Port Authority
    officers and Jail wardens are grouped as one owner each; a bank nobody reads is filed under its story or
    part of the game (the prefix's name in strings.GROUPS).

Voice cost (decision, 22 Nov 2026): pay only when heard, as on the Captain's screen. VOICE_NOW below only
describes today's behaviour per surface; a per-bank Spoken setting (Off / On request / Automatic) and a cap on
new clips per bank are slice 2.
"""
import re

import cast
import manual_text
import strings

SURFACES = [("game", "Game screens"), ("dashboard", "Dashboard"), ("table", "Table"), ("manual", "Manual")]

# How each surface treats spoken lines today (code in web/voice.js, web/dashboard-whisper.js, manual_feed.py).
VOICE_NOW = {
    "game": "Read aloud as it appears; recorded the first time it is heard, then replayed free.",
    "table": "The Game Master reads it aloud on the Table; recorded the first time it is heard.",
    "dashboard": "Only when the viewer presses Listen (and a short teaser while voices are on); recorded when heard.",
    "manual": "Only when the player presses Hear it or turns the page voice on; recorded when heard.",
}

NUMBERED = re.compile(r"^(.*)\.(\d+)$")
FIELDS = re.compile(r"\{(\w+)\}")
LONG_SPOKEN = 240          # characters: a long spoken line costs more to record
DASH_ANY = "*dashboard"    # the Dashboard note is read by whichever persona the viewer picks
DASH_TEASER = ("gamemaster", "narrator", "bookmaker")
OFFICERS = ("officers", "Port Authority officers", "Her own officer in each port reads these")
WARDENS = ("wardens", "Jail wardens", "The warden of the port the house is in reads these")


def surface_of(key):
    if key.startswith("man."):
        return "manual"
    if key.startswith("gm."):
        return "table"
    if key.startswith("dash."):
        return "dashboard"
    return "game"


def speaker(cfg, key):
    """The character id who reads this line aloud ('' = nobody; DASH_ANY = the viewer's pick)."""
    if key.startswith("man."):
        return manual_text.SPEAKER.get(key, "")
    if key.startswith("dash."):
        parts = key.split(".")
        if len(parts) == 4 and parts[1] == "whisper" and parts[3] == "speech":
            return DASH_ANY
        if len(parts) == 4 and parts[1] == "whisper" and parts[2] == "teaser":
            return parts[3] if parts[3] in DASH_TEASER else DASH_ANY
        return ""
    return cast.speaker_for(cfg, key)


def _group_names():
    return {g[0]: g[1] for g in strings.GROUPS}


def _owner(cfg, key, who, groups):
    """(owner id, name, note) for a line."""
    if key in cast.WARDEN_KEYS:
        return WARDENS
    if key in cast.OFFICER_KEYS and "officer_" in key:
        return OFFICERS
    chars = cfg.get("characters", {})
    if who == DASH_ANY:
        return (DASH_ANY, "Dashboard personas", "Whichever persona the viewer picks reads the note")
    if who and who in chars:
        c = chars[who]
        return (who, c.get("name") or who, c.get("title", ""))
    prefix = key.split(".")[0]
    return ("story:" + prefix, groups.get(prefix, prefix), "Written text; nobody reads it aloud")


def _fields(text):
    return sorted(set(FIELDS.findall(text or "")))


def _norm(text):
    return " ".join((text or "").lower().split())


def _lines(en, family, lang_strings, lang_family):
    spicy = dict(en)
    spicy.update({k: v for k, v in (lang_strings or {}).items() if k in en})
    clean = dict(family)
    clean.update({k: v for k, v in (lang_family or {}).items() if k in en})
    return spicy, clean


def _line(key, n, spicy, clean, spoken, seen):
    s = spicy.get(key, "")
    twin = key in clean
    c = clean.get(key, s)
    flags = []
    if not s.strip():
        flags.append("empty")
    if not twin:
        flags.append("no_clean")
    elif _fields(s) != _fields(c):
        flags.append("fields")
    if _norm(s) in seen:
        flags.append("dup")
    seen.add(_norm(s))
    if spoken and len(s) > LONG_SPOKEN:
        flags.append("long")
    return {"key": key, "n": n, "spicy": s, "clean": c, "twin": twin, "same": twin and s == c,
            "flags": flags, "chars": len(s)}


def view(cfg, lang=None):
    """The catalogue: {"ok", "surfaces", "voice_now", "owners", "banks", "summary"}. `cfg` is the live
    configuration (it names the characters and who reads each line); `lang` is the English language file
    ({"strings": {...}, "family": {...}}) so Language & Text edits show here."""
    lang = lang or {}
    spicy, clean = _lines(strings.EN, strings.FAMILY, lang.get("strings"), lang.get("family"))
    groups = _group_names()
    stems = {}
    singles = []
    for key in strings.EN:
        m = NUMBERED.match(key)
        if m:
            stems.setdefault(m.group(1), []).append((int(m.group(2)), key))
        elif speaker(cfg, key):
            singles.append(key)

    banks = []
    for stem, rows in stems.items():
        rows.sort()
        who = speaker(cfg, rows[0][1])
        owner = _owner(cfg, rows[0][1], who, groups)
        seen = set()
        lines = [_line(k, n, spicy, clean, bool(who), seen) for n, k in rows]
        banks.append(_bank(stem, rows[0][1], owner, who, True, lines, groups))
    for key in singles:
        who = speaker(cfg, key)
        owner = _owner(cfg, key, who, groups)
        banks.append(_bank(key, key, owner, who, False, [_line(key, 0, spicy, clean, True, set())], groups))
    banks.sort(key=lambda b: (b["owner"], b["id"]))

    owners = {}
    for b in banks:
        o = owners.setdefault(b["owner"], {
            "id": b["owner"], "name": b["owner_name"], "note": b["owner_note"], "kind": b["kind"],
            "banks": 0, "lines": 0, "twins": 0, "issues": 0, "chars": 0, "surfaces": {}})
        o["banks"] += 1
        o["lines"] += b["size"]
        o["twins"] += b["twins"]
        o["issues"] += b["issues"]
        o["chars"] += b["chars"] if b["kind"] == "spoken" else 0
        o["surfaces"][b["surface"]] = o["surfaces"].get(b["surface"], 0) + b["size"]
        if b["kind"] == "spoken":
            o["kind"] = "spoken"
    order = sorted(owners.values(), key=lambda o: (o["kind"] != "spoken", -o["lines"], o["name"]))
    by_surface = {s: {"banks": 0, "lines": 0, "twins": 0, "issues": 0} for s, _ in SURFACES}
    for b in banks:
        t = by_surface[b["surface"]]
        t["banks"] += 1
        t["lines"] += b["size"]
        t["twins"] += b["twins"]
        t["issues"] += b["issues"]
    return {"ok": True, "surfaces": [{"id": s, "name": n, **by_surface[s]} for s, n in SURFACES],
            "voice_now": VOICE_NOW, "owners": order, "banks": banks,
            "summary": {"banks": len(banks), "lines": sum(b["size"] for b in banks),
                        "twins": sum(b["twins"] for b in banks), "issues": sum(b["issues"] for b in banks)}}


def _bank(bid, first_key, owner, who, numbered, lines, groups):
    prefix = first_key.split(".")[0]
    moment = bid[len(prefix) + 1:] if "." in bid else bid
    return {"id": bid, "owner": owner[0], "owner_name": owner[1], "owner_note": owner[2],
            "surface": surface_of(first_key), "group": groups.get(prefix, prefix),
            "kind": "spoken" if who else "written", "numbered": numbered, "moment": moment,
            "size": len(lines), "twins": sum(1 for x in lines if x["twin"]),
            "issues": sum(1 for x in lines if x["flags"]),
            "chars": sum(x["chars"] for x in lines), "lines": lines}
