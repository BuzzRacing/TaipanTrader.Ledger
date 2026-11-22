"""Crimson Ledger: the Voyage Certificate (21 Nov 2026; project doc "SeaTrader Voyage Certificate").

When the books close every Captain is handed a certificate: a 1920 x 1080 wallpaper drawn in the browser
(web/certificate.js) with the home port behind, the home Mayor on the left and, on the right, the woman who
defined the voyage. This module works out what is written on it and who she is:

    facts(gid, pid, ...)   one house's certificate: the figures (from finale.book), the headline, the women
                           who could stand on the right (in order, first = the one the voyage earned), each
                           with her one spoken line, and the saved recipe if this certificate was drawn before
    recipe_get / recipe_set   which pictures a certificate used, so it opens the same way next time

Who she is, first rule that fits (candidates(); the rest follow as "Change the pictures" steps through them):
    8 or more fights won                                     Powder O'Rourke        (bosun)
    most fights were against the war fleet                   Admiral Li Yue         (pirate)
    4 or more fights, mostly against ordinary pirates        Madam Shek Yu-lan      (agent)
    went bankrupt, or loan interest was the biggest cost     Madam Wu               (lender)
    tax, fines and seizures were the biggest cost            the Port Authority officer of the port that
                                                             took the most          (officer_<port>)
    a best sale worth a fifth of the final fortune or more   Mrs. Marlowe           (taxlady)
    always, last                                             Madame Anahit          (gamemaster)

Everything comes from the journal up to the close (finale.py), so free play never changes a certificate.
Like stats.py and finale.py this module never touches the game; it only writes its own small recipe file.
"""
import hashlib
import json
import os
import re
import threading
import time

import cert_text
import engine
import finale
import strings

ROOT = os.path.dirname(os.path.abspath(__file__))
RECIPES = os.path.join(ROOT, "saves", "certificates.json")     # {"<game id>:<seat id>": recipe}
_lock = threading.Lock()
_KEEP = 400                                                     # recipes kept (oldest dropped first)
ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,48}$")

FIGHTS_WON = 8            # this many fights won: Powder
PIRATE_FIGHTS = 4         # this many fights, mostly against ordinary pirates: Madam Shek
BIG_SALE = 0.20           # a best sale worth this share of the final fortune: Mrs. Marlowe
FALLBACK = "gamemaster"   # Madame Anahit, when nothing else fits (and always the last step)


def _cast(cid):
    return cid in (engine.CFG.get("characters") or {})


def candidates(h):
    """The women who could stand on the right of this house's certificate, the earned one first."""
    out = []
    won, war, pir = h.get("won") or 0, h.get("fights_war") or 0, h.get("fights_pirate") or 0
    interest = h.get("interest") or 0
    seized = h.get("seized_value") or 0
    customs = (h.get("taxes") or 0) + seized
    other = max(0, (h.get("losses") or 0) - seized)            # pirates, storms and thieves
    if won >= FIGHTS_WON:
        out.append("bosun")
    if war and war > pir:
        out.append("pirate")
    if pir >= PIRATE_FIGHTS and pir >= war:
        out.append("agent")
    if h.get("bankrupt") or (interest > 0 and interest >= customs and interest >= other):
        out.append("lender")
    port = (h.get("tax_port") or {}).get("port")
    if port and customs > 0 and customs > interest and customs >= other:
        out.append("officer_" + port)
    sale = h.get("best_sale") or {}
    if (h.get("worth") or 0) > 0 and (sale.get("profit") or 0) >= BIG_SALE * h["worth"]:
        out.append("taxlady")
    out.append(FALLBACK)
    seen, keep = set(), []
    for cid in out:
        if cid not in seen and _cast(cid):
            seen.add(cid)
            keep.append(cid)
    return keep or [FALLBACK]


def bad_finish(h, houses):
    """Last among rivals, bankrupt during the game, or ended below where it started."""
    last = houses > 1 and (h.get("place") or 1) >= houses
    return bool(last or h.get("bankrupt") or (h.get("worth") or 0) < (h.get("start") or 0))


def career_place(worth, years, games):
    """Where this voyage ranks among the Captain's finished games of the same length.
    games: stats.career()["games"] (this game included). {"place", "of", "years"}, or None when unknown."""
    same = [g for g in games or [] if g.get("ended") and g.get("years") == years]
    if not years or not same:
        return None
    return {"place": 1 + sum(1 for g in same if (g.get("worth") or 0) > (worth or 0)), "of": len(same), "years": years}


def _pick(gid, pid, who, mood):
    """One line of hers for this certificate: the same one every time it is opened."""
    keys = cert_text.bank(who, mood)
    if not keys:
        return None
    n = int(hashlib.sha256("{}|{}|{}".format(gid, pid, who).encode("utf-8")).hexdigest()[:8], 16)
    return keys[n % len(keys)]


def _say(key, **names):
    """(the line as shown and read, its family-friendly wording) for a key."""
    if key not in engine.TEXT:                       # wording not merged into strings yet: her own bank
        text = cert_text.EN.get(key, "").format_map(engine._Safe(dict(engine.TOKENS, **names)))
    else:
        text = engine.tx(key, **names)
    fam = strings.FAMILY.get(key) or cert_text.FAMILY.get(key)
    if fam:
        try:
            fam = fam.format_map(engine._Safe(dict(engine.TOKENS, **names)))
        except Exception:
            fam = None
    return text, fam or text


def facts(gid, pid, career_games=None):
    """One house's certificate, or None while the game is still running (or the seat is not in it)."""
    book = finale.book(gid)
    if not book:
        return None
    h = next((x for x in book["houses"] if x["id"] == pid), None)
    if not h:
        return None
    # What the books closed on (the standings' own figures), not the last month the walk reached.
    h = dict(h, worth=h.get("final_worth", h.get("worth") or 0), rank=h.get("final_rank") or h.get("rank"),
             rank_id=h.get("final_rank_id") or h.get("rank_id"))
    houses = len(book["houses"])
    years = book.get("years") or max(1, int(round((book.get("months") or 0) / 12.0)))
    bad = bad_finish(h, houses)
    mood = "bad" if bad else "good"
    ports = engine.PORTS
    home = h.get("home") if h.get("home") in ports else ""
    women = []
    for cid in candidates(h):
        key = _pick(gid, pid, cid, mood)
        text, fam = _say(key, name=h["name"], firm=h["firm"]) if key else ("", "")
        women.append({"who": cid, "key": key, "text": text, "family": fam,
                      "port": cid[len("officer_"):] if cid.startswith("officer_") else ""})
    sale = h.get("best_sale")
    return {
        "ok": True, "game": gid, "id": pid, "name": h["name"], "firm": h["firm"], "color": h.get("color", 0),
        "place": h.get("place") or 1, "houses": houses, "bad": bad,
        "rank": h.get("rank"), "rank_id": h.get("rank_id"), "epithet": h.get("epithet"),
        "worth": h.get("worth") or 0, "first": book.get("first"), "last": book.get("last"), "years": years,
        "home": home, "home_name": (ports.get(home) or {}).get("name", ""),
        "career": career_place(h.get("worth") or 0, years, career_games),
        "best_sale": sale and {"good": sale["good"], "port": sale["port"], "qty": sale["qty"], "profit": sale["profit"]},
        "battles": h.get("battles") or 0, "won": h.get("won") or 0, "sunk": h.get("sunk") or 0,
        "women": women, "recipe": recipe_get(gid, pid),
    }


# ----------------------------------------------------------------- recipes --
def _load():
    try:
        with open(RECIPES, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _clean(raw):
    """A recipe as the screen may send it: which pictures were used and which woman stood on the right."""
    raw = raw if isinstance(raw, dict) else {}
    out = {}
    for k in ("bg", "mayor", "persona"):
        v = raw.get(k)
        if isinstance(v, str) and (ID_RE.match(v) or v == ""):
            out[k] = v
    who = raw.get("who")
    if isinstance(who, str) and ID_RE.match(who) and _cast(who):
        out["who"] = who
    return out


def recipe_get(gid, pid):
    with _lock:
        r = _load().get("{}:{}".format(gid, pid))
    return _clean(r) if r else None


def recipe_set(gid, pid, raw):
    """Keep the pictures a certificate was drawn with. Returns the recipe as saved."""
    rec = _clean(raw)
    if not rec or not gid or not pid:
        return None
    rec["at"] = int(time.time())
    with _lock:
        data = _load()
        data["{}:{}".format(gid, pid)] = rec
        if len(data) > _KEEP:
            for k in sorted(data, key=lambda k: (data[k] or {}).get("at", 0))[:len(data) - _KEEP]:
                data.pop(k, None)
        os.makedirs(os.path.dirname(RECIPES), exist_ok=True)
        tmp = RECIPES + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp, RECIPES)
    return _clean(rec)
