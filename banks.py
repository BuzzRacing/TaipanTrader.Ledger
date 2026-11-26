"""Dialogue Banks: every bank of lines the game, Dashboard, Table and Manual pull in, by persona or story.

Admin > Language & Text > Dialogue Banks (web/banks-admin.js).

Slice 1 (22 Nov 2026): a read-only catalogue built from the wording the game already has (strings.EN and
strings.FAMILY, plus the Language & Text overrides), with an audit.

Slice 2 (22 Nov 2026): edit, add, remove (retire) and reset lines, stored as an OVERLAY in config/banks/overlay.json
(decision A). The shipped wording in the code is never touched. Decisions (Anthony, 22 Nov 2026):
  * every line has a permanent ID, its key ("m.borrowed.easy.2"); IDs are never reused or renumbered;
  * a change applies live, the moment it is saved (like the Clips page), to every open screen;
  * a new line needs a spicy and a clean version; Reset puts a shipped line back; Remove retires a line.

How the overlay reaches the game without touching the engine
    apply() lays the overlay over strings.EN and strings.FAMILY IN PLACE (and the spoken versions in cast.SAY /
    cast.SAY_FAMILY, and who reads a new line in cast.LINE_DEFAULTS), after first putting back every shipped
    value it changed. strings.resolve() calls it, so Save & apply, startup and a bank edit all pick it up, and
    engine.TEXT, the voice planner and the family screens all see the same wording.
    The engine finds a bank's length by counting prefix.0, prefix.1, ... until a key is missing and skips blank
    lines (engine._bank), and its no-repeat decks store keys. So: a new line takes the next number; a removed line
    is blanked (retired), never deleted, so there is never a gap; a deck that holds a retired key simply skips it.

Where a screen reads the whole bank
    Game banks (engine._bank) do, so adding a line works there. The Manual's banks (manual_text.BANK_SIZE = 3), the
    Table's (gm.month_open.<turn % 3>) and the Dashboard's single lines read a fixed count today, so a new line would
    never be used there: those surfaces are edit-only until slice 3 makes them read the whole bank.

Voice cost (decision, 22 Nov 2026): pay only when heard. A spoken line that carries an amount needs a number-free
spoken version, or every different amount would be a separate paid recording; a save without one is refused.
"""
import json
import os
import re
import shutil
import string
import threading
import time

import cast
import config
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
# Banks that exist but that no screen speaks yet, so a line added to one would never be heard.
NOT_PLAYED = {
    "gm.your_turn": "The Table does not speak these lines yet, so a new one would not be heard.",
    "gm.waiting": "The Table does not speak these lines yet, so a new one would not be heard.",
}

NUMBERED = re.compile(r"^(.*)\.(\d+)$")
FIELDS = re.compile(r"\{(\w+)\}")
LONG_SPOKEN = 240          # characters: a long spoken line costs more to record
MAX_LINE = 600
MAX_BANK = 100
DASH_ANY = "*dashboard"    # the Dashboard note is read by whichever persona the viewer picks
DASH_TEASER = ("gamemaster", "narrator", "bookmaker")
OFFICERS = ("officers", "Port Authority officers", "Her own officer in each port reads these")
WARDENS = ("wardens", "Jail wardens", "The warden of the port the house is in reads these")
# Placeholders that carry an amount: a spoken line using one needs a number-free spoken version.
AMOUNTS = {"amount", "cost", "cash", "qty", "fine", "total", "price", "tax", "paid", "lost", "gain", "value",
           "months", "rate", "debt", "stake", "worth", "declared", "suggest"}
# Tokens engine.tx fills in on every line (engine.TOKENS), so any line may use them.
GLOBAL_TOKENS = {"lender", "pirate", "bank", "winner", "title", "home", "Contraband", "contraband"}

OVERLAY_FILE = os.path.join(config.CONFIG_DIR, "banks", "overlay.json")
BACKUP_DIR = os.path.join(config.CONFIG_DIR, "banks", "backups")
KEEP_BACKUPS = 30

_LOCK = threading.RLock()
_SHIPPED = None            # the wording as the code ships it, taken before the first overlay is laid on
_ADDED = set()             # keys the overlay created
_TOUCHED = set()           # shipped keys the overlay changed
_APPLIED = False
_STAMP = None


class BankError(ValueError):
    """A change that cannot be made; the message is shown to the Admin."""


# ----------------------------------------------------------------------------------------------- the overlay --
def _snapshot():
    global _SHIPPED
    if _SHIPPED is None:
        _SHIPPED = {"en": dict(strings.EN), "family": dict(strings.FAMILY), "say": dict(cast.SAY),
                    "say_family": dict(cast.SAY_FAMILY), "who": dict(cast.LINE_DEFAULTS),
                    "man": dict(manual_text.SPEAKER)}
    return _SHIPPED


def _targets():
    return (("en", strings.EN), ("family", strings.FAMILY), ("say", cast.SAY), ("say_family", cast.SAY_FAMILY),
            ("who", cast.LINE_DEFAULTS), ("man", manual_text.SPEAKER))


def _restore():
    """Put back every shipped value the overlay changed, and drop every key it created."""
    snap = _snapshot()
    for key in list(_ADDED | _TOUCHED):
        for name, target in _targets():
            if key in snap[name]:
                target[key] = snap[name][key]
            else:
                target.pop(key, None)
    _ADDED.clear()
    _TOUCHED.clear()


def load_overlay():
    """{"lines": {key: entry}, "voice": {bank id: {"spoken", "cap"}}}. Never fails: a bad file reads as empty."""
    try:
        with open(OVERLAY_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {"lines": {}, "voice": {}}
    if not isinstance(data, dict):
        return {"lines": {}, "voice": {}}
    lines, vox = data.get("lines"), data.get("voice")
    return {"lines": {str(k): v for k, v in lines.items() if isinstance(v, dict)} if isinstance(lines, dict) else {},
            "voice": {str(k): v for k, v in vox.items() if isinstance(v, dict)} if isinstance(vox, dict) else {}}


def _save_overlay(overlay):
    os.makedirs(os.path.dirname(OVERLAY_FILE), exist_ok=True)
    if os.path.isfile(OVERLAY_FILE):
        os.makedirs(BACKUP_DIR, exist_ok=True)
        shutil.copyfile(OVERLAY_FILE, os.path.join(BACKUP_DIR, time.strftime("overlay-%Y%m%d-%H%M%S.json")))
        old = sorted(os.listdir(BACKUP_DIR))
        for name in old[:-KEEP_BACKUPS]:
            try:
                os.remove(os.path.join(BACKUP_DIR, name))
            except OSError:
                pass
    tmp = OVERLAY_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(overlay, f, indent=1, ensure_ascii=False)
    os.replace(tmp, OVERLAY_FILE)


def _mtime():
    try:
        return os.stat(OVERLAY_FILE).st_mtime_ns
    except OSError:
        return None


def apply(force=False):
    """Lay the overlay over the wording, in place. Cheap when the file has not changed."""
    global _APPLIED, _STAMP
    with _LOCK:
        _snapshot()
        stamp = _mtime()
        if _APPLIED and not force and stamp == _STAMP:
            return
        _restore()
        for key, e in load_overlay()["lines"].items():
            _apply_line(key, e)
        _APPLIED, _STAMP = True, stamp


def _apply_line(key, e):
    snap = _snapshot()
    if key in snap["en"]:
        _TOUCHED.add(key)
    elif e.get("added") and isinstance(e.get("spicy"), str):
        _ADDED.add(key)
        who = e.get("who") or ""
        cast.LINE_DEFAULTS[key] = who
        if key.startswith("man."):
            manual_text.SPEAKER[key] = who
    else:
        return
    if e.get("retired"):
        strings.EN[key] = ""
        strings.FAMILY[key] = ""
        cast.SAY.pop(key, None)
        cast.SAY_FAMILY.pop(key, None)
        return
    if isinstance(e.get("spicy"), str):
        strings.EN[key] = e["spicy"]
        # The stock spoken version is for the stock wording only; an edited line has its own or is read as shown.
        if e.get("say"):
            cast.SAY[key] = e["say"]
        else:
            cast.SAY.pop(key, None)
    if isinstance(e.get("clean"), str) and e["clean"]:
        strings.FAMILY[key] = e["clean"]
        if e.get("say_clean"):
            cast.SAY_FAMILY[key] = e["say_clean"]
        else:
            cast.SAY_FAMILY.pop(key, None)


# ------------------------------------------------------------------------- spoken setting and clip cap --
# Decisions (Anthony, 22 Nov 2026): every spoken bank has a Spoken setting and a cap on NEW recordings per game.
#   auto    = the screen plays the line by itself when it shows it (game screens, the Table);
#   request = only when the player presses the button (the Manual's "Hear it", the Dashboard's Listen);
#   off     = never voiced (the text still shows).
# With nothing set, a bank behaves as it does today. The cap counts only clips that must be paid for: a clip
# already in cache/voice/ always plays free, whatever the cap. 0 = no cap.
SPOKEN_MODES = {"game": ("auto", "off"), "table": ("auto", "off"),
                "manual": ("request", "off"), "dashboard": ("request", "off")}
SPOKEN_NAMES = {"auto": "Automatic", "request": "On request", "off": "Off"}
MAX_CAP = 500
SPEND_FILE = os.path.join(config.CONFIG_DIR, "banks", "spend.json")
KEEP_GAMES = 5
_SPENT = None
_VCACHE = {"stamp": None, "voice": {}}


def bank_id(key):
    m = NUMBERED.match(key or "")
    return m.group(1) if m else (key or "")


def voice_fields(bid, surface, kind, overlay_voice):
    if kind != "spoken":
        return {"spoken": "", "spoken_set": False, "spoken_options": [], "cap": 0, "used": 0}
    modes = SPOKEN_MODES.get(surface, ("auto", "off"))
    mine = overlay_voice.get(bid) or {}
    mode = mine.get("spoken") if mine.get("spoken") in modes else ""
    return {"spoken": mode or modes[0], "spoken_set": bool(mode),
            "spoken_options": [{"id": m, "name": SPOKEN_NAMES[m]} for m in modes],
            "cap": int(mine.get("cap") or 0), "used": spent(bid)}


def _set_spoken(cfg, overlay, body):
    bid = str(body.get("bank") or "")
    rows = _stem_rows(bid)
    first = rows[0] if rows and NUMBERED.match(rows[0]) else (bid if bid in strings.EN else "")
    if not first or not speaker(cfg, first):
        raise BankError("That bank is not read aloud.")
    modes = SPOKEN_MODES.get(surface_of(first), ("auto", "off"))
    mode = str(body.get("spoken") or "")
    if mode and mode not in modes:
        raise BankError("This screen can only be set to {}.".format(" or ".join(SPOKEN_NAMES[m] for m in modes)))
    try:
        cap = int(body.get("cap") or 0)
    except (TypeError, ValueError):
        raise BankError("The cap must be a whole number (0 for no cap).")
    if not 0 <= cap <= MAX_CAP:
        raise BankError("The cap must be between 0 and {}.".format(MAX_CAP))
    entry = {k: v for k, v in (("spoken", mode if mode != modes[0] else ""), ("cap", cap)) if v}
    if entry:
        overlay.setdefault("voice", {})[bid] = entry
    else:
        overlay.setdefault("voice", {}).pop(bid, None)
    return bid


def _voice_rules():
    stamp = _mtime()
    if stamp != _VCACHE["stamp"]:
        _VCACHE["voice"], _VCACHE["stamp"] = load_overlay()["voice"], stamp
    return _VCACHE["voice"]


def may_speak(key):
    """False when the bank this line belongs to is switched Off, so no clip is planned for it."""
    return (_voice_rules().get(bank_id(key)) or {}).get("spoken") != "off"


def _game_id():
    import sys
    for mod in (sys.modules.get("server"), sys.modules.get("__main__")):
        hub = getattr(mod, "HUB", None)
        game = getattr(hub, "game", None)
        if game is not None:
            return str(game.s.get("game_id") or "")
    return ""


def _spent():
    global _SPENT
    if _SPENT is None:
        try:
            with open(SPEND_FILE, encoding="utf-8") as f:
                data = json.load(f)
            _SPENT = data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            _SPENT = {}
    return _SPENT


def spent(bid, game=None):
    return int((_spent().get(game if game is not None else _game_id()) or {}).get(bid, 0))


def charge(key):
    """Called just before a NEW clip is paid for. True = go ahead (and it is counted); False = the bank's cap for
    this game is reached. Banks with no cap and lines with no bank always go ahead (nothing is counted)."""
    bid = bank_id(key)
    cap = int((_voice_rules().get(bid) or {}).get("cap") or 0)
    if not bid:
        return True
    with _LOCK:
        games = _spent()
        row = games.setdefault(_game_id(), {})
        if cap and row.get(bid, 0) >= cap:
            return False
        row[bid] = row.get(bid, 0) + 1
        while len(games) > KEEP_GAMES:
            games.pop(next(iter(games)))
        try:
            os.makedirs(os.path.dirname(SPEND_FILE), exist_ok=True)
            tmp = SPEND_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(games, f)
            os.replace(tmp, SPEND_FILE)
        except OSError:
            pass
    return True


# ---------------------------------------------------------------------------- drawing from a whole bank --
# Screens that are not the Captain's game (the Table host, the Dashboard whisper) pick a line from the WHOLE live
# bank: lines you add are used, retired (blank) lines are skipped, and no line repeats until all have been heard.
# The same moment always gets the same line (the screens poll), so a scope names the moment: (game id, turn, ...).
import random as _random

_DECKS = {}
MEMO_KEEP = 16


def live_keys(prefix, text=None):
    """Keys of the bank `prefix` (`prefix.0`, `prefix.1`, ...) that have wording right now, in order."""
    if text is None:
        apply()
        text = strings.EN
    keys, i = [], 0
    while "{}.{}".format(prefix, i) in text:
        k = "{}.{}".format(prefix, i)
        if text[k]:
            keys.append(k)
        i += 1
    return keys


def pick_stable(prefix, scope, text=None, rng=None):
    """The line for this moment: the same key every time it is asked, a fresh one for each new moment,
    through a shuffled deck so nothing repeats until the bank has been heard. '' when the bank is empty."""
    keys = live_keys(prefix, text)
    if not keys:
        return ""
    deck = _DECKS.setdefault(prefix, {"bag": [], "memo": {}, "last": ""})
    if scope in deck["memo"] and deck["memo"][scope] in keys:
        return deck["memo"][scope]
    bag = [k for k in deck["bag"] if k in keys]
    if not bag:
        bag = keys[:]
        (rng or _random).shuffle(bag)
        if len(bag) > 1 and bag[-1] == deck["last"]:
            bag.insert(0, bag.pop())            # never the line just heard, first
    key = bag.pop()
    deck["bag"], deck["last"] = bag, key
    deck["memo"][scope] = key
    while len(deck["memo"]) > MEMO_KEEP:
        deck["memo"].pop(next(iter(deck["memo"])))
    return key


# ------------------------------------------------------------------------------------------------- the model --
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
        if len(parts) == 5 and parts[1] == "whisper" and parts[3] == "speech":
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


def _line(key, n, spicy, clean, spoken, seen, entry=None, shipped=None):
    s = spicy.get(key, "")
    entry = entry or {}
    retired = bool(entry.get("retired"))
    twin = key in clean and bool(clean.get(key, "").strip())
    c = clean.get(key, s) if twin else s
    flags = []
    if not retired:
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
        if spoken and entry and (set(_fields(s)) & AMOUNTS) and not entry.get("say"):
            flags.append("no_spoken")
    line = {"key": key, "n": n, "spicy": s, "clean": c, "twin": twin, "same": twin and s == c,
            "flags": flags, "chars": len(s), "retired": retired, "added": bool(entry.get("added")),
            "edited": bool(entry) and not entry.get("added") and not retired,
            "say": cast.SAY.get(key, ""), "say_clean": cast.SAY_FAMILY.get(key, "")}
    if entry and not entry.get("added") and shipped:
        line["shipped"] = {"spicy": shipped["en"].get(key, ""), "clean": shipped["family"].get(key, "")}
    return line


def view(cfg, lang=None):
    """The catalogue: {"ok", "surfaces", "voice_now", "owners", "banks", "summary"}. `cfg` is the live
    configuration (it names the characters and who reads each line); `lang` is the English language file
    ({"strings": {...}, "family": {...}}) so Language & Text edits show here."""
    lang = lang or {}
    apply()
    shipped = _snapshot()
    loaded = load_overlay()
    overlay, overlay_voice = loaded["lines"], loaded["voice"]
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
        lines = [_line(k, n, spicy, clean, bool(who), seen, overlay.get(k), shipped) for n, k in rows]
        banks.append(_bank(stem, rows[0][1], owner, who, True, lines, groups, shipped))
    for key in singles:
        who = speaker(cfg, key)
        owner = _owner(cfg, key, who, groups)
        banks.append(_bank(key, key, owner, who, False,
                           [_line(key, 0, spicy, clean, True, set(), overlay.get(key), shipped)], groups, shipped))
    banks.sort(key=lambda b: (b["owner"], b["id"]))
    for b in banks:
        b.update(voice_fields(b["id"], b["surface"], b["kind"], overlay_voice))

    owners = {}
    for b in banks:
        o = owners.setdefault(b["owner"], {
            "id": b["owner"], "name": b["owner_name"], "note": b["owner_note"], "kind": b["kind"],
            "banks": 0, "lines": 0, "twins": 0, "issues": 0, "chars": 0, "surfaces": {}})
        o["banks"] += 1
        o["lines"] += b["active"]
        o["twins"] += b["twins"]
        o["issues"] += b["issues"]
        o["chars"] += b["chars"] if b["kind"] == "spoken" else 0
        o["surfaces"][b["surface"]] = o["surfaces"].get(b["surface"], 0) + b["active"]
        if b["kind"] == "spoken":
            o["kind"] = "spoken"
    order = sorted(owners.values(), key=lambda o: (o["kind"] != "spoken", -o["lines"], o["name"]))
    by_surface = {s: {"banks": 0, "lines": 0, "twins": 0, "issues": 0} for s, _ in SURFACES}
    for b in banks:
        t = by_surface[b["surface"]]
        t["banks"] += 1
        t["lines"] += b["active"]
        t["twins"] += b["twins"]
        t["issues"] += b["issues"]
    return {"ok": True, "surfaces": [{"id": s, "name": n, **by_surface[s]} for s, n in SURFACES],
            "voice_now": VOICE_NOW, "owners": order, "banks": banks, "generator": _generator_state(),
            "summary": {"banks": len(banks), "lines": sum(b["active"] for b in banks),
                        "twins": sum(b["twins"] for b in banks), "issues": sum(b["issues"] for b in banks),
                        "edited": sum(1 for x in overlay.values() if not x.get("added") and not x.get("retired")),
                        "added": sum(1 for x in overlay.values() if x.get("added") and not x.get("retired")),
                        "retired": sum(1 for x in overlay.values() if x.get("retired"))}}


def _generator_state():
    try:
        import banks_gen
        return banks_gen.state()
    except Exception:
        return None


def _bank(bid, first_key, owner, who, numbered, lines, groups, shipped):
    prefix = first_key.split(".")[0]
    moment = bid[len(prefix) + 1:] if "." in bid else bid
    surface = surface_of(first_key)
    live = [x for x in lines if not x["retired"]]
    allowed = sorted({f for x in lines if not x["retired"] for f in _fields(x["spicy"])} | GLOBAL_TOKENS)
    return {"id": bid, "owner": owner[0], "owner_name": owner[1], "owner_note": owner[2],
            "surface": surface, "group": groups.get(prefix, prefix),
            "kind": "spoken" if who else "written", "numbered": numbered, "moment": moment,
            "size": len(lines), "active": len(live), "twins": sum(1 for x in live if x["twin"]),
            "issues": sum(1 for x in lines if x["flags"]),
            "chars": sum(x["chars"] for x in live), "lines": lines,
            "addable": bool(numbered and bid not in NOT_PLAYED and len(lines) < MAX_BANK),
            "fixed_note": NOT_PLAYED.get(bid, ""),
            "fields": [f for f in allowed if f not in GLOBAL_TOKENS], "who": who}


# ------------------------------------------------------------------------------------------------- the edits --
def _stem_rows(stem):
    rows, n = [], 0
    while "{}.{}".format(stem, n) in strings.EN:
        rows.append("{}.{}".format(stem, n))
        n += 1
    return rows


def _check_text(label, text, allowed, specs):
    text = (text or "").strip()
    if not text:
        raise BankError("The {} wording is empty.".format(label))
    if len(text) > MAX_LINE:
        raise BankError("The {} wording is longer than {} characters.".format(label, MAX_LINE))
    try:
        parsed = list(string.Formatter().parse(text))
    except ValueError:
        raise BankError("The {} wording has a stray curly bracket. Names go in single {{ }} pairs, such as {{amount}}.".format(label))
    for _lit, name, spec, conv in parsed:
        if name is None:
            continue
        if not name.isidentifier():
            raise BankError("The {} wording uses {{{}}}, which is not a plain name.".format(label, name))
        if name not in allowed:
            raise BankError("The {} wording uses {{{}}}, which this bank's lines are not given. Allowed names: {}.".format(
                label, name, ", ".join("{" + a + "}" for a in sorted(allowed - GLOBAL_TOKENS)) or "none"))
        if (spec or conv) and (name, spec or "", conv or "") not in specs:
            raise BankError("The {} wording formats {{{}}} in a way no line of this bank does.".format(label, name))
    return text


def _bank_info(cfg, key):
    """(stem or key, sibling keys, allowed names, allowed format specs, speaker, numbered) for a key."""
    m = NUMBERED.match(key)
    stem = m.group(1) if m else key
    siblings = _stem_rows(stem) if m else [key]
    allowed, specs = set(GLOBAL_TOKENS), set()
    for k in siblings:
        for src in (strings.EN.get(k, ""), strings.FAMILY.get(k, "")):
            try:
                for _l, name, spec, conv in string.Formatter().parse(src):
                    if name:
                        allowed.add(name)
                        specs.add((name, spec or "", conv or ""))
            except ValueError:
                pass
    return stem, siblings, allowed, specs, speaker(cfg, siblings[0]), bool(m)


def _validate(cfg, key, body, shipped_line):
    """Checks one line's new wording. Returns the entry fields {spicy, clean, say, say_clean}."""
    stem, siblings, allowed, specs, who, numbered = _bank_info(cfg, key)
    if not (body.get("spicy") or "").strip():    # Taipan Trader hides the spicy field: the clean line stands in
        body = dict(body, spicy=body.get("clean") or "", say=body.get("say_clean") or "")
    spicy = _check_text("spicy", body.get("spicy"), allowed, specs)
    clean_raw = (body.get("clean") or "").strip()
    if not clean_raw and not shipped_line:
        raise BankError("A new line needs a clean (Family-friendly) version as well as the spicy one.")
    clean = _check_text("clean", clean_raw, allowed, specs) if clean_raw else ""
    if clean and _fields(spicy) != _fields(clean):
        raise BankError("The spicy and clean wording must use the same {names}.")
    out = {"spicy": spicy, "clean": clean}
    spoken = bool(who)
    snap = _snapshot()          # wording the code ships is spoken as it is today; only a change needs a spoken version
    for field, text, label in (("say", spicy, "spicy"), ("say_clean", clean, "clean")):
        said = (body.get(field) or "").strip()
        if said and said == snap["say" if field == "say" else "say_family"].get(key) and text != snap["en" if field == "say" else "family"].get(key):
            raise BankError("The spoken {} version is still the old line's. Rewrite it to match the new wording, or "
                            "clear it to have the line read as written.".format(label))
        if said:
            said = _check_text("spoken " + label, said, allowed, specs)
            if set(_fields(said)) & AMOUNTS:
                raise BankError("The spoken {} version must not carry an amount; say it without the figures.".format(label))
        elif spoken and text and (set(_fields(text)) & AMOUNTS) and text != snap["en" if field == "say" else "family"].get(key):
            raise BankError("This line carries an amount and is read aloud, so it needs a spoken {} version without the "
                            "figures (otherwise every different amount is a separate paid recording).".format(label))
        out[field] = said
    return out


def handle(op, body, cfg):
    """One Admin change. Returns {"ok": True, "changed": True, "key": ...} or {"ok": False, "error": ...}."""
    if op.startswith("gen_"):                    # the generator (banks_gen.py): a batch can take minutes, so no lock here
        import banks_gen
        if op not in banks_gen.OPS:
            return {"ok": False, "error": "Unknown change."}
        return banks_gen.handle(op, body, cfg)
    try:
        with _LOCK:
            apply()
            snap = _snapshot()
            overlay = load_overlay()
            lines = overlay["lines"]
            key = str(body.get("key") or "")
            if op == "add":
                stem = str(body.get("bank") or "")
                rows = _stem_rows(stem)
                if not rows or not NUMBERED.match(rows[0]):
                    raise BankError("That bank does not exist.")
                if stem in NOT_PLAYED:
                    raise BankError(NOT_PLAYED[stem])
                if len(rows) >= MAX_BANK:
                    raise BankError("A bank can hold up to {} lines.".format(MAX_BANK))
                key = "{}.{}".format(stem, len(rows))
                fields = _validate(cfg, rows[0], body, None)
                who = speaker(cfg, rows[0])
                lines[key] = dict(fields, added=True, who=who if who != DASH_ANY else "", t=int(time.time()))
            elif op in ("edit", "retire", "restore", "reset"):
                if key not in strings.EN:
                    raise BankError("That line does not exist.")
                entry = dict(lines.get(key) or {})
                added = bool(entry.get("added"))
                if op == "edit":
                    fields = _validate(cfg, key, body, key in snap["en"])
                    entry.update(fields)
                    entry.pop("retired", None)
                    if not added:
                        same = (fields["spicy"] == snap["en"].get(key) and fields["clean"] in ("", snap["family"].get(key, ""))
                                and not fields["say"] and not fields["say_clean"])
                        if same:
                            lines.pop(key, None)
                            entry = None
                    if entry is not None:
                        entry["t"] = int(time.time())
                        lines[key] = entry
                elif op == "retire":
                    stem, siblings, *_ = _bank_info(cfg, key)
                    if not NUMBERED.match(key):
                        raise BankError("A single line cannot be removed, only reworded: the screen needs it.")
                    live = [k for k in siblings if strings.EN.get(k, "").strip() and k != key]
                    if not live:
                        raise BankError("A bank needs at least one line. Add another before removing this one.")
                    entry["retired"] = True
                    entry["t"] = int(time.time())
                    lines[key] = entry
                elif op == "restore":
                    if key in snap["en"] or added:
                        entry.pop("retired", None)
                        if not added and not any(entry.get(f) for f in ("spicy", "clean", "say", "say_clean")):
                            lines.pop(key, None)
                        else:
                            lines[key] = entry
                else:   # reset
                    if added:
                        raise BankError("A line you added has no shipped wording to go back to. Remove it instead.")
                    lines.pop(key, None)
            elif op == "spoken":
                key = _set_spoken(cfg, overlay, body)
            else:
                raise BankError("Unknown change.")
            _save_overlay(overlay)
            apply(force=True)
            return {"ok": True, "changed": True, "key": key}
    except BankError as e:
        return {"ok": False, "error": str(e)}
