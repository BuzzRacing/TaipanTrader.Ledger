"""SeaTrader media library: every picture and video clip the game can show, tagged so it can be
picked, rotated or randomised on screen.

Each item in the library belongs to a *kind* and a *subject*:

    persona / narrator      the cast (keys from Admin > Cast & Voices)
    port    / hongkong      the ports (keys from Admin > Ports)
    ship    / clipper       the ship types
    cargo   / silk          the cargoes
    scene   / storm         events and moods (storm, battle, title, ...)
    brand   / logo          the main artwork slots (logo, page background, ...)
    reference / heat_1      Art Bible examples (style reference only, never shown in play)
    other   / ""            not sorted yet

and has *roles* (where it may be used: a persona's "portrait", "speaking" or "idle" pictures, a port's
"banner" or "night" pictures...), free *tags*, a *weight* for random picks, and an NSFW flag.
An item with no roles may be used for any role of its subject.

When the content rating is family-friendly (Admin > Ratings & Difficulty, or the switch at the top of
Admin > Media Library), every NSFW item disappears from the player screens and the harbor board, and
its file is refused to anyone who is not signed in to the Admin page.

Files live in web/media/<kind>/<subject>/ (older artwork stays in web/uploads/). The library itself is
config/media.json. Files dropped straight into web/media/<kind>/<subject>/ (or a <role> folder inside it)
are picked up by "Scan folders"; a folder or file name containing "nsfw" marks them NSFW.

Nothing here needs anything beyond the Python standard library.
"""
import copy
import json
import os
import re
import secrets
import shutil
import threading
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(ROOT, "web")
MEDIA_DIR = os.path.join(WEB, "media")
TRASH_DIR = os.path.join(MEDIA_DIR, "_trash")
UPLOAD_DIR = os.path.join(WEB, "uploads")
LIB_FILE = os.path.join(ROOT, "config", "media.json")
LOCK = threading.RLock()

IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg")
VIDEO_EXT = (".mp4", ".webm", ".m4v", ".mov")
MAX_IMAGE = 40 * 1024 * 1024
MAX_VIDEO = 600 * 1024 * 1024
ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,47}$")
ITEM_RE = re.compile(r"^m[0-9a-f]{10}$")
TAG_RE = re.compile(r"[^a-z0-9 _-]")
URL_RE = re.compile(r"^/(uploads|media|assets)/[A-Za-z0-9._/-]+$")

MODES = [["random", "Random each time it appears"], ["shuffle", "Shuffle on a timer (no repeats in a row)"],
         ["rotate", "Rotate in order on a timer"], ["fixed", "Fixed: always the starred (primary) item"]]
MODE_KEYS = [m[0] for m in MODES]

# What each kind is for, which roles it has, and where the game uses them.
KINDS = {
    "persona": {"label": "Personas", "one": "Persona", "subjects": "characters",
                "roles": [["portrait", "Profile picture: cast cards and the log"],
                          ["speaking", "While speaking: shown (or played) when they read a line"],
                          ["idle", "Idle: harbor board gallery between lines"],
                          ["happy", "Good news (sales, escapes, wins)"],
                          ["angry", "Bad news (losses, seizures, threats)"]],
                "default_role": "speaking"},
    "port": {"label": "Ports", "one": "Port", "subjects": "ports",
             "roles": [["banner", "Banner at the top of the market and port tabs"],
                       ["arrival", "Arrival: the log after landing here"],
                       ["night", "Night or mood pictures"],
                       ["board", "Harbor board gallery"],
                       ["keeper", "Market keeper: the woman behind the stalls, on the stage while the Market tab is open"],
                       ["shipmaster", "Ship master: the woman who runs the fleet, on the stage while the Fleet tab is open"],
                       ["mayor", "Mayor: the town's lady mayor who sees the ships off, on the stage and the tab while Set sail is open"],
                       ["taxlady", "Tax lady: the town's tax collector who keeps the books, on the stage and the tab while the Ledger is open"],
                       ["taxlady_bored", "Port Authority, her tell: bored (an honest or small lie). Several = a new one each time"],
                       ["taxlady_curious", "Port Authority, her tell: curious (a middling lie)"],
                       ["taxlady_hungry", "Port Authority, her tell: hungry (a big lie)"],
                       ["taxlady_tax", "Port Authority ruling: tax paid, papers stamped"],
                       ["taxlady_buyout", "Port Authority ruling: she buys your cargo"],
                       ["taxlady_caught", "Port Authority ruling: caught lying"]],
             "default_role": "banner"},
    "ship": {"label": "Ships", "one": "Ship type", "subjects": "ships",
             "roles": [["card", "Fleet cards and the shipyard"], ["sailing", "Under sail"], ["battle", "In battle"]],
             "default_role": "card"},
    "cargo": {"label": "Cargo", "one": "Cargo", "subjects": "goods",
              "roles": [["icon", "Beside the cargo in the market"]], "default_role": "icon"},
    "scene": {"label": "Scenes", "one": "Scene", "subjects": "scenes",
              "roles": [["background", "Full-screen or panel background"], ["event", "Shown with the event"],
                        # The ten moments of a sea battle (file them under "Sea battle: pirate junks" or
                        # "Sea battle: war junks"; a picture with no role fits every moment of its enemy).
                        ["sighting", "Sea battle: the enemy sighted"], ["broadside", "Sea battle: your guns fire"],
                        ["enemy_hit", "Sea battle: an enemy junk goes down"], ["we_are_hit", "Sea battle: your ships are hit"],
                        ["ship_lost", "Sea battle: one of your ships is lost"], ["boarding", "Sea battle: boarded and plundered"],
                        ["got_away", "Sea battle: got clear of them"], ["retreat", "Sea battle: breaking away, cargo overboard"],
                        ["victory", "Sea battle: victory"], ["defeat", "Sea battle: the fleet is lost"]],
              "default_role": "event"},
    "brand": {"label": "Brand", "one": "Brand slot", "subjects": "brand",
              "roles": [["main", "The main artwork slot"]], "default_role": "main"},
    "reference": {"label": "Art Bible", "one": "Example", "subjects": "free",
                  "roles": [["reference", "Style reference only: never shown in play"]], "default_role": "reference"},
    "other": {"label": "Unsorted", "one": "Unsorted", "subjects": "free", "roles": [], "default_role": ""},
}
SCENES = [["title", "Title & lobby"], ["loading", "Loading / holding screen"], ["storm", "Storm"],
          ["typhoon", "Typhoon"], ["battle", "Sea battle"], ["pirates", "Pirates sighted"],
          ["seafight_pirates", "Sea battle: pirate junks"], ["seafight_lord", "Sea battle: war junks"],
          ["wreck", "Shipwreck"], ["seizure", "Customs seizure"], ["robbery", "Robbery"],
          ["victory", "Game over / winner"], ["voyage", "At sea"], ["market", "Trading"]]
BRAND_SLOTS = [["logo", "Logo"], ["favicon", "Browser tab icon"], ["masthead_bg", "Title banner background"],
               ["page_bg", "Player screen background"], ["board_bg", "Harbor board background"],
               ["chart_bg", "Chart artwork"]]

RULE_DEFAULTS = {
    "persona": {"mode": "random", "seconds": 7, "video_chance": 35},
    "port": {"mode": "random", "seconds": 14, "video_chance": 0},
    "ship": {"mode": "random", "seconds": 14, "video_chance": 0},
    "cargo": {"mode": "fixed", "seconds": 20, "video_chance": 0},
    "scene": {"mode": "shuffle", "seconds": 12, "video_chance": 25},
    "brand": {"mode": "fixed", "seconds": 30, "video_chance": 0},
    "reference": {"mode": "fixed", "seconds": 30, "video_chance": 0},
    "other": {"mode": "fixed", "seconds": 30, "video_chance": 0},
}
OPTION_DEFAULTS = {
    "speaker_card": "card",       # "card" = large portrait while a line is read, "badge" = the small round badge
    "board_gallery": True,        # harbor board shows a rotating gallery of the ports players are in
    "new_nsfw": "auto",           # generated images: "auto" (read the prompt), "yes" or "no"
}
# Words in a prompt that mark a generated image NSFW until someone reviews it.
NSFW_WORDS = re.compile(r"\b(nude|nudity|naked|topless|bare[- ]breast\w*|breasts?|buttocks|genital\w*|full[- ]frontal|"
                        r"erotic\w*|lingerie|kink\w*|nsfw|explicit|undress\w*)\b", re.I)

_cache = {"mtime": None, "lib": None}
_on_change = []


class MediaError(Exception):
    pass


# ------------------------------------------------------------------ store --
def _blank():
    return {"version": 1, "items": [], "rules": {"defaults": copy.deepcopy(RULE_DEFAULTS), "subjects": {}},
            "options": dict(OPTION_DEFAULTS), "slots": {}}


def _read():
    try:
        mtime = os.path.getmtime(LIB_FILE)
    except OSError:
        return None
    if _cache["mtime"] == mtime and _cache["lib"] is not None:
        return _cache["lib"]
    try:
        with open(LIB_FILE, encoding="utf-8") as f:
            lib = json.load(f)
    except (OSError, ValueError):
        return None
    lib = _tidy(lib)
    _cache.update(mtime=mtime, lib=lib)
    return lib


def _write(lib):
    os.makedirs(os.path.dirname(LIB_FILE), exist_ok=True)
    tmp = LIB_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(lib, f, indent=1, ensure_ascii=False)
    os.replace(tmp, LIB_FILE)
    _cache.update(mtime=os.path.getmtime(LIB_FILE), lib=lib)
    _public_cache.clear()
    # Told from a fresh thread, so whoever is told never waits on this module's lock (and vice versa).
    for fn in list(_on_change):
        threading.Thread(target=_safe_call, args=(fn,), daemon=True).start()


def _safe_call(fn):
    try:
        fn()
    except Exception:
        pass


def on_change(fn):
    """Call fn() (no arguments) after every change to the library."""
    _on_change.append(fn)


def load(cfg=None):
    """The library (a dict). Built on first use from the artwork already in the game."""
    with LOCK:
        lib = _read()
        if lib is None:
            lib = _blank()
            _migrate(lib, cfg)
            _write(lib)
        return lib


def _clamp(v, lo, hi, default):
    try:
        v = int(round(float(v)))
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, v))


def _clean_rule(r, base):
    r = r if isinstance(r, dict) else {}
    return {"mode": r.get("mode") if r.get("mode") in MODE_KEYS else base["mode"],
            "seconds": _clamp(r.get("seconds"), 2, 900, base["seconds"]),
            "video_chance": _clamp(r.get("video_chance"), 0, 100, base["video_chance"])}


def _tags(v):
    if isinstance(v, str):
        v = v.split(",")
    out = []
    for t in v if isinstance(v, list) else []:
        t = " ".join(TAG_RE.sub("", str(t).lower()).split())[:32]
        if t and t not in out:
            out.append(t)
    return out[:24]


def _tidy(lib):
    """Repair anything odd in a library read from disk."""
    lib = lib if isinstance(lib, dict) else {}
    out = _blank()
    rules = lib.get("rules") if isinstance(lib.get("rules"), dict) else {}
    defs = rules.get("defaults") if isinstance(rules.get("defaults"), dict) else {}
    out["rules"]["defaults"] = {k: _clean_rule(defs.get(k), RULE_DEFAULTS[k]) for k in KINDS}
    subs = rules.get("subjects") if isinstance(rules.get("subjects"), dict) else {}
    for key, r in subs.items():
        kind = str(key).split(":")[0]
        if kind in KINDS and isinstance(r, dict):
            out["rules"]["subjects"][key] = _clean_rule(r, out["rules"]["defaults"][kind])
    opt = lib.get("options") if isinstance(lib.get("options"), dict) else {}
    out["options"] = {
        "speaker_card": opt.get("speaker_card") if opt.get("speaker_card") in ("card", "badge") else "card",
        "board_gallery": bool(opt.get("board_gallery", True)),
        "new_nsfw": opt.get("new_nsfw") if opt.get("new_nsfw") in ("auto", "yes", "no") else "auto",
    }
    out["slots"] = _clean_slots(lib.get("slots"))
    seen = set()
    for it in lib.get("items") if isinstance(lib.get("items"), list) else []:
        it = _clean_item(it)
        if it and it["id"] not in seen:
            seen.add(it["id"])
            out["items"].append(it)
    return out


SLOT_KEY_RE = re.compile(r"^(brand|port|ship|cargo):[a-z][a-z0-9_]{0,47}$")
HOW = ("settings", "upload", "generated", "library", "removed", "file", "first")


def _clean_slots(v):
    """slots: {"port:hongkong": {url, item, since, bytes, mtime, history: [{at, from, to, item, how}]}}."""
    out = {}
    for key, s in (v.items() if isinstance(v, dict) else []):
        if not SLOT_KEY_RE.match(str(key)) or not isinstance(s, dict):
            continue
        url = str(s.get("url") or "")
        hist = []
        for h in s.get("history") if isinstance(s.get("history"), list) else []:
            if isinstance(h, dict):
                hist.append({"at": str(h.get("at") or "")[:20], "from": str(h.get("from") or "")[:300],
                             "to": str(h.get("to") or "")[:300], "item": str(h.get("item") or "")[:12],
                             "how": h.get("how") if h.get("how") in HOW else "settings"})
        out[key] = {"url": url if (not url or URL_RE.match(url)) else "", "item": str(s.get("item") or "")[:12],
                    "since": str(s.get("since") or "")[:20], "bytes": _clamp(s.get("bytes"), 0, 10 ** 10, 0),
                    "mtime": _clamp(s.get("mtime"), 0, 10 ** 12, 0), "history": hist[-25:]}
    return out


def _clean_item(it):
    if not isinstance(it, dict):
        return None
    url = str(it.get("url") or "")
    if not URL_RE.match(url) or ".." in url:
        return None
    iid = str(it.get("id") or "")
    if not ITEM_RE.match(iid):
        iid = new_id()
    kind = it.get("kind") if it.get("kind") in KINDS else "other"
    subject = str(it.get("subject") or "").lower()
    subject = subject if ID_RE.match(subject) else ""
    ext = os.path.splitext(url)[1].lower()
    roles_ok = {r[0] for r in KINDS[kind]["roles"]}
    roles = [r for r in (it.get("roles") or []) if r in roles_ok] if isinstance(it.get("roles"), list) else []
    out = {
        "id": iid, "url": url, "type": "video" if ext in VIDEO_EXT else "image",
        "kind": kind, "subject": subject, "roles": list(dict.fromkeys(roles)), "tags": _tags(it.get("tags")),
        "nsfw": bool(it.get("nsfw")), "reviewed": bool(it.get("reviewed")), "enabled": it.get("enabled", True) is not False,
        "primary": bool(it.get("primary")), "weight": _clamp(it.get("weight"), 1, 10, 3),
        "title": " ".join(str(it.get("title") or "").split())[:80],
        "prompt": str(it.get("prompt") or "")[:6000], "seed": it.get("seed") if isinstance(it.get("seed"), int) else None,
        "width": _clamp(it.get("width"), 0, 20000, 0), "height": _clamp(it.get("height"), 0, 20000, 0),
        "bytes": _clamp(it.get("bytes"), 0, 10 ** 10, 0),
        "source": it.get("source") if it.get("source") in ("generated", "upload", "scan", "import", "config") else "import",
        "added": str(it.get("added") or "")[:20],
        "replaces": str(it.get("replaces") or "") if ITEM_RE.match(str(it.get("replaces") or "")) else "",
    }
    return out


def new_id():
    return "m" + secrets.token_hex(5)


def path_for(url):
    """The file on disk behind a library URL (or None if it is outside the web folder)."""
    if not URL_RE.match(url or "") or ".." in url:
        return None
    p = os.path.normpath(os.path.join(WEB, url.lstrip("/")))
    return p if p.startswith(WEB + os.sep) else None


def _exists(url):
    p = path_for(url)
    return bool(p and os.path.isfile(p))


def _image_size(path):
    """(width, height) of a PNG, JPEG, GIF or WebP, read from its header; (0, 0) if unknown."""
    try:
        with open(path, "rb") as f:
            head = f.read(64 * 1024)
    except OSError:
        return 0, 0
    try:
        if head[:8] == b"\x89PNG\r\n\x1a\n":
            return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")
        if head[:6] in (b"GIF87a", b"GIF89a"):
            return int.from_bytes(head[6:8], "little"), int.from_bytes(head[8:10], "little")
        if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
            chunk = head[12:16]
            if chunk == b"VP8X":
                return 1 + int.from_bytes(head[24:27], "little"), 1 + int.from_bytes(head[27:30], "little")
            if chunk == b"VP8 ":
                return int.from_bytes(head[26:28], "little") & 0x3FFF, int.from_bytes(head[28:30], "little") & 0x3FFF
            if chunk == b"VP8L":
                b = head[21:25]
                return 1 + (((b[1] & 0x3F) << 8) | b[0]), 1 + (((b[3] & 0xF) << 10) | (b[2] << 2) | ((b[1] & 0xC0) >> 6))
        if head[:2] == b"\xff\xd8":
            i = 2
            while i < len(head) - 9:
                if head[i] != 0xFF:
                    i += 1
                    continue
                marker = head[i + 1]
                if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                    return int.from_bytes(head[i + 7:i + 9], "big"), int.from_bytes(head[i + 5:i + 7], "big")
                i += 2 + int.from_bytes(head[i + 2:i + 4], "big")
    except (IndexError, ValueError):
        pass
    return 0, 0


def _make_item(url, kind, subject, roles=(), tags=(), nsfw=False, source="import", prompt="", seed=None,
               title="", reviewed=None, replaces=""):
    p = path_for(url)
    size = os.path.getsize(p) if p and os.path.isfile(p) else 0
    w, h = _image_size(p) if p and os.path.splitext(p)[1].lower() in IMAGE_EXT else (0, 0)
    return _clean_item({
        "id": new_id(), "url": url, "kind": kind, "subject": subject, "roles": list(roles), "tags": list(tags),
        "nsfw": nsfw, "reviewed": (not nsfw) if reviewed is None else reviewed, "enabled": True, "primary": False,
        "weight": 3, "title": title, "prompt": prompt, "seed": seed, "width": w, "height": h, "bytes": size,
        "source": source, "added": time.strftime("%Y-%m-%d %H:%M"), "replaces": replaces,
    })


def nsfw_from_prompt(prompt, options=None):
    mode = (options or {}).get("new_nsfw", "auto")
    if mode == "yes":
        return True
    if mode == "no":
        return False
    return bool(NSFW_WORDS.search(prompt or ""))


# -------------------------------------------------------------- subjects --
def subjects(cfg):
    """Known subjects for each kind: {kind: [[key, label], ...]}."""
    cfg = cfg or {}

    def names(table):
        return [[k, (v or {}).get("name") or k] for k, v in (cfg.get(table) or {}).items()]
    chars = []
    for cid, c in (cfg.get("characters") or {}).items():
        link = c.get("brand_link") or ""
        name = (cfg.get("brand") or {}).get(link) if link else ""
        chars.append([cid, name or c.get("name") or cid])
    return {"persona": chars, "port": names("ports"), "ship": names("ships"), "cargo": names("goods"),
            "scene": [list(s) for s in SCENES], "brand": [list(s) for s in BRAND_SLOTS], "reference": [], "other": []}


def _guess(fname):
    """(kind, subject, roles) for an existing artwork file name."""
    stem = os.path.splitext(fname)[0].lower()
    for pat, kind, roles in ((r"^portrait-([a-z0-9_]+)-[0-9a-f]{6,}$", "persona", ["portrait"]),
                             (r"^historical-port-([a-z0-9_]+)$", "port", ["banner"]),
                             (r"^historical-ship-([a-z0-9_]+)$", "ship", ["card"]),
                             (r"^historical-cargo-([a-z0-9_]+)$", "cargo", ["icon"]),
                             (r"^artbible-([a-z0-9-]+)-[0-9a-f]{6,}$", "reference", ["reference"])):
        m = re.match(pat, stem)
        if m:
            return kind, m.group(1).replace("-", "_")[:48], roles
    for slot, _label in BRAND_SLOTS:
        if stem in ("historical-" + slot.replace("_bg", ""), "historical-" + slot):
            return "brand", slot, ["main"]
    if stem.startswith("historical-chart"):
        return "brand", "chart_bg", ["main"]
    return "other", "", []


def _config_refs(cfg):
    """[(url, kind, subject, roles)] for every picture the settings use."""
    out = []
    if not cfg:
        return out
    for cid, c in (cfg.get("characters") or {}).items():
        if c.get("portrait"):
            out.append((c["portrait"], "persona", cid, ["portrait"]))
    gr = cfg.get("graphics") or {}
    for slot, _label in BRAND_SLOTS:
        if gr.get(slot):
            out.append((gr[slot], "brand", slot, ["main"]))
    for group, kind, role in (("ports", "port", "banner"), ("ships", "ship", "card"), ("goods", "cargo", "icon")):
        for k, url in (gr.get(group) or {}).items():
            if url:
                out.append((url, kind, k, [role]))
    return [r for r in out if URL_RE.match(r[0] or "")]


def _migrate(lib, cfg):
    """First run: put everything already in the game into the library."""
    by_url = {}
    for url, kind, subject, roles in _config_refs(cfg):
        if url in by_url or not _exists(url):
            continue
        it = _make_item(url, kind, subject, roles, source="config")
        by_url[url] = it
    # Art Bible examples keep their prompts.
    book = {}
    try:
        with open(os.path.join(ROOT, "config", "artbible_examples.json"), encoding="utf-8") as f:
            book = json.load(f)
    except (OSError, ValueError):
        pass
    prompts = {}
    for slot, entries in (book.items() if isinstance(book, dict) else []):
        for e in entries if isinstance(entries, list) else []:
            if isinstance(e, dict) and e.get("url"):
                prompts[e["url"]] = (slot, e.get("prompt") or "", e.get("seed"))
    # Cast prompts tell us how portraits were painted.
    cast_prompts = {cid: c.get("portrait_prompt") or "" for cid, c in ((cfg or {}).get("characters") or {}).items()}
    if os.path.isdir(UPLOAD_DIR):
        for fname in sorted(os.listdir(UPLOAD_DIR)):
            ext = os.path.splitext(fname)[1].lower()
            if ext not in IMAGE_EXT + VIDEO_EXT:
                continue
            url = "/uploads/" + fname
            kind, subject, roles = _guess(fname)
            if url in by_url:
                continue
            prompt, seed = "", None
            if url in prompts:
                kind, subject, roles = "reference", prompts[url][0], ["reference"]
                prompt, seed = prompts[url][1], prompts[url][2]
            by_url[url] = _make_item(url, kind, subject, roles, source="import", prompt=prompt, seed=seed)
    for url, it in by_url.items():
        if it["kind"] == "persona" and not it["prompt"]:
            it["prompt"] = cast_prompts.get(it["subject"], "")
        if it["prompt"] and nsfw_from_prompt(it["prompt"]):
            it["nsfw"], it["reviewed"] = True, False
    # One primary per subject: the one the settings use.
    used = {u for u, *_ in _config_refs(cfg)}
    lib["items"] = sorted(by_url.values(), key=lambda i: (i["kind"], i["subject"], i["url"]))
    for it in lib["items"]:
        it["primary"] = it["url"] in used
    _scan_media_dir(lib)


def graphic_slots(cfg):
    """Every picture slot on Admin > Graphics: [(key, kind, subject, role, url)].
    key is "<kind>:<subject>", the same pair the library files the picture under."""
    cfg = cfg or {}
    gr = cfg.get("graphics") or {}
    out = []
    for slot, _label in BRAND_SLOTS:
        out.append(("brand:" + slot, "brand", slot, "main", gr.get(slot) or ""))
    for group, table, kind, role in (("ports", "ports", "port", "banner"), ("ships", "ships", "ship", "card"),
                                     ("goods", "goods", "cargo", "icon")):
        g = gr.get(group) or {}
        for k in (cfg.get(table) or {}):
            if ID_RE.match(k):
                out.append(("{}:{}".format(kind, k), kind, k, role, g.get(k) or ""))
    return out


def _fingerprint(url):
    p = path_for(url)
    try:
        st = os.stat(p) if p else None
    except OSError:
        st = None
    return (st.st_size, int(st.st_mtime)) if st else (0, 0)


def sync_from_config(cfg, how="settings"):
    """After Save & apply: every picture the settings use is in the library, filed (tagged) under the slot
    it fills, and every change to a Graphics slot is written into that slot's history.
    Returns {"added": n, "retagged": n, "changes": [(key, from_url, to_url, how)]}."""
    with LOCK:
        lib = load(cfg)
        by_url = {i["url"]: i for i in lib["items"]}
        added = retagged = 0
        dirty = False
        # Cast portraits: just make sure they are in the library.
        for cid, c in ((cfg or {}).get("characters") or {}).items():
            url = c.get("portrait") or ""
            if url and URL_RE.match(url) and url not in by_url and _exists(url):
                it = _make_item(url, "persona", cid, ["portrait"], source="config")
                if it:
                    lib["items"].append(it)
                    by_url[url] = it
                    added += 1
        # Graphics slots: file, tag and track.
        now = time.strftime("%Y-%m-%d %H:%M")
        slots = lib.setdefault("slots", {})
        changes = []
        live_keys = set()
        for key, kind, subject, role, url in graphic_slots(cfg):
            live_keys.add(key)
            it = None
            if url and URL_RE.match(url) and _exists(url):
                it = by_url.get(url)
                if it is None:
                    it = _make_item(url, kind, subject, [role], ["graphics"], source="config")
                    if it:
                        lib["items"].append(it)
                        by_url[url] = it
                        added += 1
                elif it["kind"] != kind or it["subject"] != subject or role not in it["roles"] \
                        or "graphics" not in it["tags"]:
                    if it["kind"] != kind:
                        it["kind"], it["roles"] = kind, []
                    it["subject"] = subject
                    if role not in it["roles"]:
                        it["roles"].append(role)
                    if "graphics" not in it["tags"]:
                        it["tags"] = (it["tags"] + ["graphics"])[:24]
                    fixed = _clean_item(it)
                    it.clear()
                    it.update(fixed)
                    retagged += 1
                    dirty = True
                if it and not it["primary"] and not any(o["kind"] == kind and o["subject"] == subject and o["primary"]
                                                        for o in lib["items"]):
                    it["primary"] = True
                    dirty = True
            size, mtime = _fingerprint(url) if url else (0, 0)
            prev = slots.get(key)
            if prev is None:
                slots[key] = {"url": url, "item": it["id"] if it else "", "since": now, "bytes": size, "mtime": mtime,
                              "history": [{"at": now, "from": "", "to": url, "item": it["id"] if it else "",
                                           "how": "first"}] if url else []}
                dirty = True
                continue
            if prev["url"] != url:
                h = how
                if not url:
                    h = "removed"
                elif it and how == "settings":
                    h = {"upload": "upload", "generated": "generated"}.get(it["source"], "library")
                prev["history"] = (prev["history"] + [{"at": now, "from": prev["url"], "to": url,
                                                       "item": it["id"] if it else "", "how": h}])[-25:]
                changes.append((key, prev["url"], url, h))
                prev.update(url=url, item=it["id"] if it else "", since=now, bytes=size, mtime=mtime)
                dirty = True
            elif url and (prev["bytes"], prev["mtime"]) != (size, mtime) and size:
                prev["history"] = (prev["history"] + [{"at": now, "from": url, "to": url,
                                                       "item": it["id"] if it else "", "how": "file"}])[-25:]
                changes.append((key, url, url, "file"))
                prev.update(item=it["id"] if it else prev["item"], since=now, bytes=size, mtime=mtime)
                if it:
                    w, hgt = _image_size(path_for(url)) if os.path.splitext(url)[1].lower() in IMAGE_EXT else (0, 0)
                    it.update(bytes=size, width=w, height=hgt)
                dirty = True
            elif it and prev["item"] != it["id"]:
                prev["item"] = it["id"]
                dirty = True
        for key in [k for k in slots if k not in live_keys]:
            del slots[key]
            dirty = True
        if added or dirty:
            _write(lib)
        return {"added": added, "retagged": retagged, "changes": changes}


def slot_status(cfg):
    """For Admin > Graphics: each slot's library link, history and whether its file changed on disk."""
    lib = load(cfg)
    slots = lib.get("slots") or {}
    out = {}
    for key, kind, subject, role, url in graphic_slots(cfg):
        s = slots.get(key) or {}
        size, mtime = _fingerprint(url) if url else (0, 0)
        out[key] = {"url": s.get("url", ""), "item": s.get("item", ""), "since": s.get("since", ""),
                    "history": s.get("history", []),
                    "file_changed": bool(url and s.get("url") == url and size and
                                         (s.get("bytes"), s.get("mtime")) != (size, mtime))}
    return out


def _scan_media_dir(lib):
    """Register files dropped into web/media/<kind>/<subject>/[<role>/]. Returns how many were new."""
    have = {i["url"] for i in lib["items"]}
    added = 0
    if not os.path.isdir(MEDIA_DIR):
        return 0
    for dirpath, dirnames, filenames in os.walk(MEDIA_DIR):
        dirnames[:] = [d for d in dirnames if d != "_trash" and not d.startswith(".")]
        rel = os.path.relpath(dirpath, MEDIA_DIR).replace(os.sep, "/")
        parts = [] if rel == "." else rel.split("/")
        for fname in sorted(filenames):
            ext = os.path.splitext(fname)[1].lower()
            if ext not in IMAGE_EXT + VIDEO_EXT or fname.startswith("."):
                continue
            url = "/media/" + "/".join(parts + [fname])
            if url in have or not URL_RE.match(url):
                continue
            low = [p.lower() for p in parts]
            kind = low[0] if low and low[0] in KINDS else "other"
            subject = low[1] if kind != "other" and len(low) > 1 and ID_RE.match(low[1]) else ""
            role_ok = {r[0] for r in KINDS[kind]["roles"]}
            roles = [p for p in low[2:] if p in role_ok]
            nsfw = any("nsfw" in p for p in low) or "nsfw" in fname.lower()
            it = _make_item(url, kind, subject, roles, nsfw=nsfw, source="scan", reviewed=True)
            lib["items"].append(it)
            have.add(url)
            added += 1
    return added


def scan(cfg=None):
    """Pick up new files in web/media and web/uploads, and drop entries whose file has gone."""
    with LOCK:
        lib = load(cfg)
        added = _scan_media_dir(lib)
        have = {i["url"] for i in lib["items"]}
        if os.path.isdir(UPLOAD_DIR):
            for fname in sorted(os.listdir(UPLOAD_DIR)):
                ext = os.path.splitext(fname)[1].lower()
                url = "/uploads/" + fname
                if ext in IMAGE_EXT + VIDEO_EXT and url not in have and URL_RE.match(url):
                    kind, subject, roles = _guess(fname)
                    lib["items"].append(_make_item(url, kind, subject, roles, source="scan",
                                                   nsfw="nsfw" in fname.lower(), reviewed=True))
                    added += 1
        before = len(lib["items"])
        lib["items"] = [i for i in lib["items"] if _exists(i["url"])]
        missing = before - len(lib["items"])
        if added or missing:
            _write(lib)
        return added, missing


# ---------------------------------------------------------------- adding --
def folder_for(kind, subject):
    kind = kind if kind in KINDS else "other"
    parts = [MEDIA_DIR, kind] + ([subject] if subject and ID_RE.match(subject) else [])
    d = os.path.join(*parts)
    os.makedirs(d, exist_ok=True)
    return d


def _url_for(path):
    return "/" + os.path.relpath(path, WEB).replace(os.sep, "/")


def add_bytes(data, ext, kind, subject, roles=(), tags=(), nsfw=False, source="upload", prompt="", seed=None,
              title="", stem=None, reviewed=None, primary=False, replaces=""):
    """Save a file into web/media/<kind>/<subject>/ and register it. Returns the new item."""
    ext = ext.lower()
    if ext not in IMAGE_EXT + VIDEO_EXT:
        raise MediaError("Use a PNG, JPG, WebP, GIF or SVG picture, or an MP4, WebM or MOV video.")
    kind = kind if kind in KINDS else "other"
    subject = subject if ID_RE.match(subject or "") else ""
    folder = folder_for(kind, subject)
    base = re.sub(r"[^a-z0-9_-]", "", (stem or "{}-{}".format(kind, subject or "item")).lower())[:48] or "item"
    fname = "{}-{}{}".format(base, secrets.token_hex(4), ext)
    path = os.path.join(folder, fname)
    with open(path, "wb") as f:
        f.write(data)
    return register_file(path, kind, subject, roles, tags, nsfw, source, prompt, seed, title, reviewed, primary,
                         replaces)


def register_file(path, kind, subject, roles=(), tags=(), nsfw=False, source="upload", prompt="", seed=None,
                  title="", reviewed=None, primary=False, replaces=""):
    url = _url_for(path)
    with LOCK:
        lib = load()
        it = _make_item(url, kind, subject, roles, tags, nsfw, source, prompt, seed, title, reviewed, replaces)
        if it is None:
            raise MediaError("That file name cannot be used.")
        if primary or not any(i["kind"] == it["kind"] and i["subject"] == it["subject"] and i["primary"]
                              for i in lib["items"]):
            for i in lib["items"]:
                if primary and i["kind"] == it["kind"] and i["subject"] == it["subject"]:
                    i["primary"] = False
            it["primary"] = True
        lib["items"].append(it)
        _write(lib)
        return it


def register_url(url, kind, subject, roles=(), nsfw=False, source="generated", prompt="", seed=None, title=""):
    """Register a file that was saved somewhere else (for example an Art Bible example in web/uploads)."""
    p = path_for(url)
    if not p or not os.path.isfile(p):
        return None
    with LOCK:
        lib = load()
        if any(i["url"] == url for i in lib["items"]):
            return None
        it = _make_item(url, kind, subject, roles, (), nsfw, source, prompt, seed, title, reviewed=not nsfw)
        lib["items"].append(it)
        _write(lib)
        return it


# --------------------------------------------------------------- editing --
EDITABLE = ("kind", "subject", "roles", "tags", "nsfw", "reviewed", "enabled", "primary", "weight", "title")


def update(ids, changes, add_tags=(), remove_tags=(), add_roles=(), remove_roles=()):
    """Change fields on one or more items. Returns how many changed."""
    ids = set(ids)
    with LOCK:
        lib = load()
        n = 0
        for it in lib["items"]:
            if it["id"] not in ids:
                continue
            for k, v in changes.items():
                if k in EDITABLE:
                    it[k] = v
            if add_tags or remove_tags:
                it["tags"] = [t for t in it["tags"] if t not in set(_tags(list(remove_tags)))] + \
                             [t for t in _tags(list(add_tags)) if t not in it["tags"]]
            if add_roles or remove_roles:
                it["roles"] = [r for r in it["roles"] if r not in remove_roles] + \
                              [r for r in add_roles if r not in it["roles"]]
            fixed = _clean_item(it)
            it.clear()
            it.update(fixed)
            if "nsfw" in changes and "reviewed" not in changes:
                it["reviewed"] = True
            n += 1
        if changes.get("primary"):
            # Only one primary per subject: the last one marked wins.
            winners = {}
            for it in lib["items"]:
                if it["id"] in ids:
                    winners[(it["kind"], it["subject"])] = it["id"]
            for it in lib["items"]:
                key = (it["kind"], it["subject"])
                if key in winners and it["id"] != winners[key]:
                    it["primary"] = False
        if n:
            _write(lib)
        return n


def remove(ids, in_use=()):
    """Move items' files to web/media/_trash and drop them from the library.
    Files the settings still use are kept on disk (only the library entry goes)."""
    ids = set(ids)
    in_use = set(in_use)
    with LOCK:
        lib = load()
        keep, gone = [], []
        for it in lib["items"]:
            (gone if it["id"] in ids else keep).append(it)
        for it in gone:
            p = path_for(it["url"])
            if it["url"] in in_use or not p or not os.path.isfile(p):
                continue
            os.makedirs(TRASH_DIR, exist_ok=True)
            dst = os.path.join(TRASH_DIR, os.path.basename(p))
            if os.path.exists(dst):
                dst = os.path.join(TRASH_DIR, "{}-{}".format(secrets.token_hex(2), os.path.basename(p)))
            try:
                shutil.move(p, dst)
            except OSError:
                pass
        lib["items"] = keep
        if gone:
            _write(lib)
        return len(gone)


def set_rules(rules, options=None):
    with LOCK:
        lib = load()
        merged = {"rules": rules if isinstance(rules, dict) else lib["rules"],
                  "options": options if isinstance(options, dict) else lib["options"], "items": lib["items"]}
        fresh = _tidy(merged)
        lib["rules"], lib["options"] = fresh["rules"], fresh["options"]
        _write(lib)
        return lib


# -------------------------------------------------------- what screens see --
_public_cache = {}


def family(cfg):
    return ((cfg or {}).get("content") or {}).get("rating") == "family"


def blocked_urls(cfg):
    """Files that must not be shown right now (NSFW while family-friendly is on)."""
    if not family(cfg):
        return frozenset()
    lib = load(cfg)
    return frozenset(i["url"] for i in lib["items"] if i["nsfw"])


def is_blocked(url, cfg):
    return url in blocked_urls(cfg)


def public(cfg):
    """The library as the player screens and harbor board need it, with NSFW removed when family-friendly."""
    lib = load(cfg)
    key = (_cache["mtime"], family(cfg))
    if key in _public_cache:
        return _public_cache[key]
    fam = family(cfg)
    items = {}
    for it in lib["items"]:
        if not it["enabled"] or (fam and it["nsfw"]) or it["kind"] in ("reference", "other") or not it["subject"]:
            continue
        if not _exists(it["url"]):
            continue
        items.setdefault(it["kind"], {}).setdefault(it["subject"], []).append(
            {"id": it["id"], "u": it["url"], "t": it["type"], "r": it["roles"], "w": it["weight"],
             "p": it["primary"], "g": it["tags"]})
    out = {"items": items, "rules": lib["rules"], "options": lib["options"], "family": fam,
           "fallback": {k: v["default_role"] for k, v in KINDS.items()}}
    _public_cache.clear()
    _public_cache[key] = out
    return out


def safe_url(url, kind, subject, cfg, role=None):
    """url if it may be shown now; otherwise a family-friendly picture of the same subject, or ''."""
    blocked = blocked_urls(cfg)
    if url and url not in blocked:
        return url
    if not blocked:
        return url or ""
    best = None
    for it in load(cfg)["items"]:
        if it["kind"] != kind or it["subject"] != subject or it["nsfw"] or not it["enabled"] or it["type"] != "image":
            continue
        if not _exists(it["url"]):
            continue
        score = (role in it["roles"] or not it["roles"], it["primary"], it["weight"])
        if best is None or score > best[0]:
            best = (score, it["url"])
    return best[1] if best else ""


def safe_graphics(graphics, cfg):
    """A copy of the graphics settings with NSFW pictures swapped for family-friendly ones."""
    g = copy.deepcopy(graphics or {})
    if not family(cfg):
        return g
    for slot, _label in BRAND_SLOTS:
        if slot in g:
            g[slot] = safe_url(g.get(slot) or "", "brand", slot, cfg, "main")
    for group, kind, role in (("ports", "port", "banner"), ("ships", "ship", "card"), ("goods", "cargo", "icon")):
        for k in list((g.get(group) or {}).keys()):
            g[group][k] = safe_url(g[group][k], kind, k, cfg, role)
    return g


def safe_cast(public_cast, cfg):
    """Swap NSFW cast portraits for family-friendly ones (or none)."""
    out = copy.deepcopy(public_cast or {})
    for cid, c in out.items():
        c["portrait"] = safe_url(c.get("portrait") or "", "persona", cid, cfg, "portrait")
    return out


def admin_view(cfg):
    lib = load(cfg)
    items = []
    for it in lib["items"]:
        d = dict(it)
        d["missing"] = not _exists(it["url"])
        items.append(d)
    in_use = {u for u, *_ in _config_refs(cfg)}
    counts = {"total": len(items), "nsfw": sum(1 for i in items if i["nsfw"]),
              "video": sum(1 for i in items if i["type"] == "video"),
              "review": sum(1 for i in items if not i["reviewed"]),
              "bytes": sum(i["bytes"] for i in items)}
    return {"items": items, "rules": lib["rules"], "options": lib["options"], "kinds": KINDS, "modes": MODES,
            "subjects": subjects(cfg), "in_use": sorted(in_use), "counts": counts, "family": family(cfg),
            "rule_defaults": RULE_DEFAULTS, "slots": slot_status(cfg)}


# ------------------------------------------------------------ generation --
class Jobs:
    """Generates pictures one after another in the background, saving each into the library as it finishes."""

    def __init__(self):
        self.lock = threading.Lock()
        self.jobs = []
        self.wake = threading.Event()
        self.thread = None
        self.render = None      # function(prompt, prefix, width, height, negative) -> (bytes, seed)
        self.log = None         # function(level, text)

    def start(self, render, log=None):
        self.render, self.log = render, log
        if self.thread is None:
            self.thread = threading.Thread(target=self._run, daemon=True, name="media-jobs")
            self.thread.start()

    def add(self, kind, subject, roles, prompt, width, height, count, nsfw, negative=None, tags=(), aspect="",
            replaces=""):
        job = {"id": "j" + secrets.token_hex(4), "kind": kind, "subject": subject, "roles": list(roles),
               "tags": list(tags), "prompt": prompt, "negative": negative, "width": width, "height": height,
               "aspect": aspect, "count": count, "done": 0, "failed": 0, "items": [], "nsfw": nsfw,
               "status": "waiting", "error": "", "started": time.time(), "finished": None,
               "replaces": replaces if ITEM_RE.match(replaces or "") else ""}
        with self.lock:
            self.jobs.append(job)
            self.jobs = [j for j in self.jobs if j["status"] in ("waiting", "running")] + \
                        [j for j in self.jobs if j["status"] not in ("waiting", "running")][-30:]
        self.wake.set()
        return job

    def cancel(self, jid):
        with self.lock:
            for j in self.jobs:
                if j["id"] == jid and j["status"] in ("waiting", "running"):
                    j["status"] = "cancelling" if j["status"] == "running" else "cancelled"
                    return True
        return False

    def list(self):
        with self.lock:
            return [{k: v for k, v in j.items() if k != "negative"} for j in reversed(self.jobs)]

    def _next(self):
        with self.lock:
            for j in self.jobs:
                if j["status"] == "waiting":
                    j["status"] = "running"
                    return j
        return None

    def _run(self):
        while True:
            job = self._next()
            if job is None:
                self.wake.wait(5)
                self.wake.clear()
                continue
            for _n in range(job["count"]):
                if job["status"] == "cancelling":
                    break
                try:
                    data, seed = self.render(job["prompt"], "seatrader/{}-{}".format(job["kind"], job["subject"] or "item"),
                                             job["width"], job["height"], job["negative"])
                    nsfw = nsfw_from_prompt(job["prompt"], {"new_nsfw": job["nsfw"]})
                    it = add_bytes(data, ".png", job["kind"], job["subject"], job["roles"], job["tags"], nsfw,
                                   "generated", job["prompt"], seed, stem="{}-{}".format(job["kind"], job["subject"]),
                                   reviewed=not nsfw, replaces=job.get("replaces") or "")
                    job["items"].append(it["id"])
                    job["done"] += 1
                    if self.log:
                        self.log("INFO", "Media library: generated {} for {}/{} (seed {}{})".format(
                            it["url"], job["kind"], job["subject"], seed, ", NSFW" if nsfw else ""))
                except Exception as e:      # the farm being down must not stop the queue
                    job["failed"] += 1
                    job["error"] = str(e)[:300]
                    if self.log:
                        self.log("ERROR", "Media library: generation failed for {}/{}: {}".format(
                            job["kind"], job["subject"], e))
                    if job["failed"] >= 2 and job["done"] == 0:
                        break
            job["status"] = "cancelled" if job["status"] == "cancelling" else ("failed" if not job["done"] else "done")
            job["finished"] = time.time()


JOBS = Jobs()
