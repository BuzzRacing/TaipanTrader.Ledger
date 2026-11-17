"""Captains: saved player profiles that last from game to game.

Each Captain has a PIN (their id number, which they type to take the profile into a game),
a portrait, an Inworld voice id (stored for later use), a story, and one or more Houses
(the trading firms they sail as). Pictures of Captains and Houses live in the Media Library
(kinds "captain" and "house"), so they can be generated, regenerated, starred and swapped there
or on the Admin > Captains page. The starred (primary) picture is the one the game shows.

The record of every game a Captain plays is a link (game id, seat id, house) kept here; the
numbers themselves are worked out from the Captain's Report journal by stats.py, so there is
one source of truth. Time at the screen is counted here.

Stored in captains/captains.json (kept off GitHub: it holds the PINs).
Two guest Captains are always there; they need no PIN.
"""
import copy
import json
import os
import re
import secrets
import threading
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.join(ROOT, "captains")
FILE = os.path.join(DIR, "captains.json")
LOCK = threading.RLock()

PIN_RE = re.compile(r"^[0-9]{4,8}$")
CID_RE = re.compile(r"^c_[0-9a-f]{6}$")
HID_RE = re.compile(r"^h_[0-9a-f]{6}$")
COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
NAME_MAX, HOUSE_MAX = 20, 28

PROMPTS = {
    "portrait": ("Oil-painted portrait of {name}, {title}, a sea captain and merchant adventurer of the China "
                 "seas in 1860, three-quarter view, weathered confident face, period coat with brass buttons, "
                 "harbour of junks and clipper masts softly behind, warm lantern light, rich teak and crimson "
                 "palette, painterly brushwork, dramatic chiaroscuro, highly detailed"),
    "house": ("Heraldic crest and trading-house seal for '{house}', a merchant house of the China trade in 1860, "
              "{motto_part}engraved brass and crimson lacquer, a ship under full sail with {color_word} banners, "
              "ornate cartouche, Chinese and Victorian ornament combined, centred on aged parchment, "
              "clean symmetrical emblem, highly detailed illustration"),
}

GUESTS = [
    {"cid": "c_000001", "pin": "0001", "name": "Guest Marlowe", "title": "Guest Captain",
     "bio": "A tall stranger with a borrowed coat and a borrowed ship. Nobody asks where Marlowe came from.",
     "houses": [{"hid": "h_000001", "name": "Marlowe Trading Co.", "color": "#2f6f9f",
                 "motto": "Fair winds, fat holds"}]},
    {"cid": "c_000002", "pin": "0002", "name": "Guest Reyes", "title": "Guest Captain",
     "bio": "Off the Manila packet with a sea chest and a grin. Reyes trades by instinct and laughs at storms.",
     "houses": [{"hid": "h_000002", "name": "Reyes & Daughters", "color": "#9f2f4a",
                 "motto": "Bold at sea, honest ashore"}]},
]

_data = None
_pending = {}          # (cid, gid) -> seconds not yet written
_last_flush = time.time()
_fails = {}            # address -> [timestamps of wrong PINs]


class CaptainError(Exception):
    pass


# ---------------------------------------------------------------- storage --
def _now():
    return time.strftime("%Y-%m-%d %H:%M")


def _blank():
    return {"version": 1, "captains": {}, "prompts": dict(PROMPTS)}


def _clean_house(h, existing=None):
    h = h if isinstance(h, dict) else {}
    hid = str(h.get("hid") or "")
    if not HID_RE.match(hid):
        hid = "h_" + secrets.token_hex(3)
    out = dict(existing or {})
    out.update({
        "hid": hid,
        "name": " ".join(str(h.get("name") or "").split())[:HOUSE_MAX],
        "color": h.get("color") if COLOR_RE.match(str(h.get("color") or "")) else "#b8862b",
        "motto": " ".join(str(h.get("motto") or "").split())[:80],
        "home_port": re.sub(r"[^a-z0-9_]", "", str(h.get("home_port") or "").lower())[:24],
        "prompt": str(h.get("prompt") or "")[:6000],
        "retired": bool(h.get("retired")),
        "created": str(h.get("created") or (existing or {}).get("created") or _now())[:20],
    })
    return out


def _clean(c, existing=None):
    c = c if isinstance(c, dict) else {}
    ex = existing or {}
    out = {
        "cid": c.get("cid") if CID_RE.match(str(c.get("cid") or "")) else ex.get("cid") or "c_" + secrets.token_hex(3),
        "pin": str(c.get("pin") if c.get("pin") is not None else ex.get("pin") or ""),
        "name": " ".join(str(c.get("name") or "").split())[:NAME_MAX],
        "title": " ".join(str(c.get("title") or "").split())[:40],
        "bio": str(c.get("bio") or "").strip()[:1200],
        "voice_id": str(c.get("voice_id") or "").strip()[:120],
        "prompt": str(c.get("prompt") or "")[:6000],
        "guest": bool(c.get("guest", ex.get("guest", False))),
        "retired": bool(c.get("retired")),
        "nsfw": bool(c.get("nsfw")),
        "created": str(ex.get("created") or c.get("created") or _now())[:20],
        "last_played": str(ex.get("last_played") or c.get("last_played") or "")[:20],
        "games": ex.get("games") if isinstance(ex.get("games"), list) else
        [g for g in (c.get("games") or []) if isinstance(g, dict)],
    }
    old = {h.get("hid"): h for h in ex.get("houses") or [] if isinstance(h, dict)}
    out["houses"] = [_clean_house(h, old.get(h.get("hid")) if isinstance(h, dict) else None)
                     for h in (c.get("houses") or []) if isinstance(h, dict)]
    return out


def _seed(data):
    for g in GUESTS:
        if g["cid"] not in data["captains"]:
            c = _clean(dict(g, guest=True))
            data["captains"][c["cid"]] = c
        else:
            data["captains"][g["cid"]]["guest"] = True


def load():
    global _data
    with LOCK:
        if _data is not None:
            return _data
        data = None
        try:
            with open(FILE, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            data = None
        if not isinstance(data, dict) or not isinstance(data.get("captains"), dict):
            data = _blank()
        data.setdefault("prompts", {})
        for k, v in PROMPTS.items():
            if not str(data["prompts"].get(k) or "").strip():
                data["prompts"][k] = v
        caps = {}
        for cid, c in data["captains"].items():
            if isinstance(c, dict):
                cc = _clean(c, c)
                caps[cc["cid"]] = cc
        data["captains"] = caps
        _seed(data)
        _data = data
        _write()
        return _data


def _write():
    os.makedirs(DIR, exist_ok=True)
    tmp = FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(_data, f, indent=1, ensure_ascii=False)
    os.replace(tmp, FILE)


def reset_cache():
    """Forget what is in memory (tests point FILE somewhere else and call this)."""
    global _data
    with LOCK:
        _data = None
        _pending.clear()
        _fails.clear()


# --------------------------------------------------------------- pictures --
def _pick(kind, subject, cfg, family=None):
    """The picture the game shows for a Captain or House: the starred one in the Media Library,
    else the best enabled one; NSFW ones are skipped when the table is family-friendly."""
    try:
        import media
    except ImportError:
        return ""
    fam = media.family(cfg) if family is None else family
    best = None
    for it in media.load(cfg)["items"]:
        if it["kind"] != kind or it["subject"] != subject or not it["enabled"] or it["type"] != "image":
            continue
        if fam and it["nsfw"]:
            continue
        score = (it["primary"], it["weight"], it.get("added") or "")
        if best is None or score > best[0]:
            best = (score, it["url"])
    return best[1] if best else ""


def urls_in_use(cfg=None):
    """Pictures currently shown for a Captain or House. Not protected from deleting: when the shown one
    is removed, the next best picture of that Captain or House is shown instead."""
    out = []
    for c in load()["captains"].values():
        u = _pick("captain", c["cid"], cfg, family=False)
        if u:
            out.append(u)
        for h in c["houses"]:
            u = _pick("house", h["hid"], cfg, family=False)
            if u:
                out.append(u)
    return out


def media_subjects():
    """For the Media Library's 'what is it of' lists."""
    caps, houses = [], []
    for c in sorted(load()["captains"].values(), key=lambda c: (c["guest"], c["name"].lower())):
        caps.append([c["cid"], c["name"] + (" (guest)" if c["guest"] else "")])
        for h in c["houses"]:
            houses.append([h["hid"], "{} ({})".format(h["name"] or "Unnamed house", c["name"])])
    return caps, houses


def base_prompts():
    """{"captain": {cid: prompt}, "house": {hid: prompt}}: what the Media Library's Generate form starts from."""
    out = {"captain": {}, "house": {}}
    for c in load()["captains"].values():
        out["captain"][c["cid"]] = prompt_for(c)
        for h in c["houses"]:
            out["house"][h["hid"]] = prompt_for(c, h)
    return out


def prompt_for(c, house=None, base=False):
    """The image prompt for a Captain's portrait or one of their Houses (their own, or the template).
    base=True: always the template filled in, ignoring a prompt of their own."""
    data = load()
    if house is None:
        if c.get("prompt", "").strip() and not base:
            return c["prompt"]
        return data["prompts"]["portrait"].format(name=c["name"] or "a captain", title=c["title"] or "merchant captain")
    if house.get("prompt", "").strip() and not base:
        return house["prompt"]
    motto = house.get("motto") or ""
    return data["prompts"]["house"].format(
        house=house.get("name") or "a merchant house", motto_part=("with the motto '{}' on a ribbon, ".format(motto)
                                                                  if motto else ""),
        color_word=_color_word(house.get("color") or ""))


def _color_word(hexcol):
    try:
        r, g, b = (int(hexcol[i:i + 2], 16) for i in (1, 3, 5))
    except (ValueError, TypeError):
        return "crimson"
    if max(r, g, b) < 60:
        return "black"
    if min(r, g, b) > 200:
        return "white"
    if r > g and r > b:
        return "gold" if g > 0.6 * r else "crimson"
    if g >= r and g > b:
        return "jade green"
    return "deep blue" if b > r else "violet"


# ------------------------------------------------------------- the views --
def _house_view(h, cfg, family):
    return {"hid": h["hid"], "name": h["name"], "color": h["color"], "motto": h["motto"],
            "home_port": h["home_port"], "image": _pick("house", h["hid"], cfg, family)}


def faces(players, gid=None, cfg=None):
    """{seat id: {"portrait": url, "crest": url}} for every seat at the table ("" where there is none),
    for the game screens: the Captain's portrait and the crest of the House they sail under. The House is
    the one written on the seat (hid), else the one this game's link records, else the one named like
    the seat's firm."""
    caps = load()["captains"]
    out = {}
    for p in players:
        c = caps.get(p.get("captain") or "")
        if not c:
            out[p["id"]] = {"portrait": "", "crest": ""}
            continue
        hid = p.get("hid") or next((g.get("hid") for g in c["games"]
                                    if gid and g.get("gid") == gid and g.get("pid") == p["id"] and g.get("hid")), "")
        if not hid:
            firm = (p.get("firm") or "").strip().lower()
            hid = next((h["hid"] for h in c["houses"] if (h["name"] or "").strip().lower()[:28] == firm), "")
        out[p["id"]] = {"portrait": _pick("captain", c["cid"], cfg),
                        "crest": _pick("house", hid, cfg) if hid else ""}
    return out


def public_list(cfg=None):
    """What the join screen shows: no PINs, no retired Captains or Houses."""
    out = []
    for c in load()["captains"].values():
        if c["retired"]:
            continue
        out.append({"cid": c["cid"], "name": c["name"], "title": c["title"], "guest": c["guest"],
                    "portrait": _pick("captain", c["cid"], cfg),
                    "houses": [_house_view(h, cfg, None) for h in c["houses"] if not h["retired"]],
                    "games": len(c["games"])})
    out.sort(key=lambda c: (c["guest"], c["name"].lower()))
    return out


def admin_list(cfg=None, career=None):
    """Everything, for Admin > Captains. career(c) gives the numbers from the journal."""
    with LOCK:
        flush(force=True)
        caps = copy.deepcopy(list(load()["captains"].values()))
    out = []
    for c in caps:
        c["portrait"] = _pick("captain", c["cid"], cfg, family=False)
        c["prompt_shown"] = prompt_for(c)
        c["prompt_base"] = prompt_for(c, base=True)
        for h in c["houses"]:
            h["image"] = _pick("house", h["hid"], cfg, family=False)
            h["prompt_shown"] = prompt_for(c, h)
            h["prompt_base"] = prompt_for(c, h, base=True)
        c["seconds"] = sum(int(g.get("seconds") or 0) for g in c["games"])
        c["career"] = career(c) if career else None
        out.append(c)
    out.sort(key=lambda c: (c["guest"], c["name"].lower()))
    return out


def get(cid):
    c = load()["captains"].get(cid)
    return copy.deepcopy(c) if c else None


def prompts():
    return dict(load()["prompts"])


# ---------------------------------------------------------------- editing --
def save_captain(raw):
    """Create or update a Captain from the Admin page. Returns the saved Captain."""
    with LOCK:
        data = load()
        cid = str((raw or {}).get("cid") or "")
        ex = data["captains"].get(cid)
        c = _clean(raw, ex)
        if ex and ex["guest"]:
            c["guest"], c["pin"] = True, ex["pin"]
        if not c["name"]:
            raise CaptainError("Give the Captain a name.")
        for o in data["captains"].values():
            if o["cid"] != c["cid"] and o["name"].lower() == c["name"].lower():
                raise CaptainError("There is already a Captain called {}.".format(o["name"]))
        if not c["guest"]:
            if not PIN_RE.match(c["pin"]):
                raise CaptainError("The PIN must be 4 to 8 digits.")
            for o in data["captains"].values():
                if o["cid"] != c["cid"] and o["pin"] == c["pin"]:
                    raise CaptainError("That PIN belongs to {}. Every Captain needs their own.".format(o["name"]))
        names = set()
        for h in c["houses"]:
            if not h["name"]:
                raise CaptainError("Every House needs a name.")
            if h["name"].lower() in names:
                raise CaptainError("{} has two Houses called {}.".format(c["name"], h["name"]))
            names.add(h["name"].lower())
        if not c["houses"]:
            c["houses"] = [_clean_house({"name": "{} & Co.".format(c["name"])[:HOUSE_MAX]})]
        data["captains"][c["cid"]] = c
        _write()
        return copy.deepcopy(c)


def delete_captain(cid):
    with LOCK:
        data = load()
        c = data["captains"].get(cid)
        if not c:
            raise CaptainError("That Captain is not on the list.")
        if c["guest"]:
            raise CaptainError("The guest Captains stay. You can retire one instead.")
        del data["captains"][cid]
        _write()
        return c


def free_pin():
    """A PIN nobody has yet (for the 'new Captain' form)."""
    used = {c["pin"] for c in load()["captains"].values()}
    rng = secrets.SystemRandom()
    for _ in range(1000):
        pin = "{:04d}".format(rng.randint(1000, 9999))
        if pin not in used:
            return pin
    return ""


def set_prompts(p):
    with LOCK:
        data = load()
        for k in PROMPTS:
            v = str((p or {}).get(k) or "").strip()
            data["prompts"][k] = v[:6000] or PROMPTS[k]
            try:
                v and v.format(name="", title="", house="", motto_part="", color_word="")
            except (KeyError, IndexError, ValueError):
                raise CaptainError("A prompt template may use only {name} {title} {house} {motto_part} {color_word}.")
        _write()


# ------------------------------------------------------------ taking part --
def verify(cid, pin, house=None, address=""):
    """Check a Captain may sail now. Returns (captain, house). Raises CaptainError."""
    now = time.time()
    tries = [t for t in _fails.get(address, []) if now - t < 60]
    _fails[address] = tries
    if len(tries) >= 5:
        raise CaptainError("Too many wrong PINs. Wait a minute and try again.")
    c = load()["captains"].get(str(cid or ""))
    if not c or c["retired"]:
        raise CaptainError("Choose your Captain first.")
    if not c["guest"]:
        if not secrets.compare_digest(str(pin or "").strip(), c["pin"]):
            _fails.setdefault(address, []).append(now)
            raise CaptainError("That PIN is not right for {}.".format(c["name"]))
    houses = [h for h in c["houses"] if not h["retired"]]
    h = next((h for h in houses if h["hid"] == house), None) or (houses[0] if houses else None)
    if h is None:
        raise CaptainError("{} has no House to sail under. Add one in Admin > Captains.".format(c["name"]))
    _fails.pop(address, None)
    return copy.deepcopy(c), copy.deepcopy(h)


def link_game(cid, gid, pid, house):
    """Write down that this Captain sat in this game (once per game)."""
    with LOCK:
        c = load()["captains"].get(cid)
        if not c or not gid:
            return
        for g in c["games"]:
            if g.get("gid") == gid:
                g.update(pid=pid, hid=house["hid"], house=house["name"])
                break
        else:
            c["games"].append({"gid": gid, "pid": pid, "hid": house["hid"], "house": house["name"],
                               "joined": _now(), "seconds": 0})
        c["last_played"] = _now()
        _write()


def links(c):
    """{game id: seat id} for stats.career."""
    return {g["gid"]: g["pid"] for g in (c or {}).get("games", []) if g.get("gid") and g.get("pid")}


def tick(seated, secs):
    """seated: [(cid, gid)] at a screen right now; secs since the last tick. Written once a minute."""
    with LOCK:
        for key in seated:
            _pending[key] = _pending.get(key, 0.0) + secs
        flush()


def flush(force=False):
    global _last_flush
    with LOCK:
        if not _pending or (not force and time.time() - _last_flush < 60):
            return
        caps = load()["captains"]
        for (cid, gid), secs in _pending.items():
            c = caps.get(cid)
            if not c:
                continue
            for g in c["games"]:
                if g.get("gid") == gid:
                    g["seconds"] = int(g.get("seconds") or 0) + int(round(secs))
        _pending.clear()
        _last_flush = time.time()
        _write()
