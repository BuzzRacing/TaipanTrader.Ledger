"""Crimson Ledger: the finale's book of the voyage.

When the books close, the finale ceremony (web/ceremony.js) opens a ledger. This module fills it:
for every house, the story of its voyage worked out from the game journal by stats.py (fortune
curve, passages, best sale, sea battles, perils), plus an epithet, a short chronicle of the big
moments, and the honours of the voyage shared out among the houses.

Only the journal up to the game_over event is read, so months sailed in free play afterwards never
change the book. Once a game has ended its book is worked out once and kept in memory.

Like stats.py this module never writes anything. GET /api/finale returns finale.book(game id).
"""
import threading

import engine
import stats

_lock = threading.Lock()
_books = {}          # game id -> finished book (only for games that have ended)
_KEEP = 16
_CURVE_POINTS = 96   # fortune curve points per house (thinned evenly, last month always kept)


def _thin(rows, n=_CURVE_POINTS):
    """Every month, or n evenly spaced ones, always keeping the first, last, highest and lowest."""
    if len(rows) <= n:
        return rows
    step = (len(rows) - 1) / (n - 1)
    keep = {round(i * step) for i in range(n)}
    keep |= {max(range(len(rows)), key=lambda i: rows[i]["worth"]), min(range(len(rows)), key=lambda i: rows[i]["worth"])}
    return [rows[i] for i in sorted(keep)]


def _rank_id(title):
    for r in engine.CFG["ranks"]:
        if r["title"] == title:
            return r["id"]
    return ""


def _rank_level(title):
    order = [r["title"] for r in engine.CFG["ranks"]]
    return order.index(title) if title in order else -1


def _epithet(k, perils):
    """A title for the house's captain, from how the voyage went (strings fin.epithet.*)."""
    voyages, won = k["voyages"] or 0, k["won"] or 0
    start, worth = max(k["start_worth"] or 0, 1), k["worth"] or 0
    if won >= 8 and won >= voyages * 0.15:
        return "breaker"
    if (k["score"] or 0) >= 70:
        return "shrewd"
    if worth >= start * 200 and worth >= 1_000_000:
        return "magnificent"
    if (perils.get("storms") or 0) >= 12:
        return "stormproof"
    if voyages >= 60:
        return "restless"
    if worth < start:
        return "unlucky"
    return "bold"


def _chronicle(h):
    """Up to eight big moments of the voyage, in order: rank firsts, debt cleared, the best sale,
    the richest prize at sea, the fortune's peak and the worst blow."""
    k, out = h["kpis"], []
    best_level, firsts = -1, []
    first_level = _rank_level(h["months"][0]["rank"]) if h["months"] else -1
    best_level = first_level
    for r in h["rankups"]:
        lvl = _rank_level(r["rank"])
        if r["up"] and lvl > best_level:
            best_level = lvl
            firsts.append({"turn": r["turn"], "date": r["date"], "kind": "rank", "rank": r["rank"],
                           "rank_id": _rank_id(r["rank"])})
    out += firsts[-3:]                      # the three highest ranks first reached
    if k.get("debt_free"):
        turn = next((m["turn"] for m in h["months"] if m["date"] == k["debt_free"]), 0)
        if turn > 0:
            out.append({"turn": turn, "date": k["debt_free"], "kind": "debt_free"})
    if h["best"] and h["best"][0].get("profit", 0) > 0:
        b = h["best"][0]
        out.append({"turn": b["turn"], "date": b["date"], "kind": "sale", "good": b["good"], "port": b["port"],
                    "qty": b["qty"], "value": b["profit"]})
    prizes = [b for b in h["battles"] if b["result"] == "won" and b.get("booty")]
    if prizes:
        b = max(prizes, key=lambda b: b["booty"])
        out.append({"turn": b["turn"], "date": b["date"], "kind": "prize", "count": b["count"],
                    "lord": b.get("lord"), "value": b["booty"]})
    if k.get("peak") and k.get("peak_date"):
        turn = next((m["turn"] for m in h["months"] if m["date"] == k["peak_date"]), None)
        if turn is not None:
            out.append({"turn": turn, "date": k["peak_date"], "kind": "peak", "value": k["peak"]})
    blows = [m for m in h["moments"] if m["kind"] in ("seized", "wreck", "robbed") and m.get("value")]
    if blows:
        m = max(blows, key=lambda m: m["value"])
        out.append({"turn": m["turn"], "date": stats._date(m["turn"]), "kind": "blow_" + m["kind"],
                    "value": m["value"]})
    out.sort(key=lambda e: e["turn"])
    return out[-8:]


def _house(h, place):
    k, p = h["kpis"], h["perils"]
    sells = [t for t in h["trades"] if t["side"] == "sell"]
    best = h["best"][0] if h["best"] and h["best"][0].get("profit", 0) > 0 else None
    routes = h["routes"]
    visits = sorted(h["ports"], key=lambda r: (-r["visits"], -r["profit"]))
    cargo = [c for c in h["cargo"] if c["profit"] > 0][:3]
    highest = max((m["rank"] for m in h["months"]), key=_rank_level, default=k["rank"])
    sunk = sum(b.get("sunk", 0) for b in h["battles"])
    lines = h["lines"]
    return {
        "id": h["id"], "name": h["name"], "firm": h["firm"], "color": h["color"], "place": place,
        "worth": k["worth"], "start": k["start_worth"], "peak": k["peak"], "peak_date": k["peak_date"],
        "low": k["low"], "low_date": k["low_date"],
        "rank": k["rank"], "rank_id": _rank_id(k["rank"]), "highest": highest, "highest_id": _rank_id(highest),
        "months": k["months"], "voyages": k["voyages"], "ports": k["ports_visited"],
        "trades": k["trades"], "sells": k["sells"], "win_rate": k["win_rate"], "score": k["score"],
        "realised": k["realised"], "debt_free": k["debt_free"],
        "battles": k["battles"], "won": k["won"], "sunk": sunk, "booty": k["booty"], "accuracy": k["accuracy"],
        "storms": p.get("storms", 0), "typhoons": p.get("typhoons", 0), "wrecks": k["wrecks"],
        "seizures": p.get("seizures", 0), "robbed": p.get("robbed", 0), "ships_lost": p.get("ships_lost", 0),
        "losses": k["losses"],
        "taxes": max(0, -int(lines.get("customs", 0))), "interest": max(0, -int(lines.get("loan_interest", 0))),
        "best_sale": best and {"good": best["good"], "port": best["port"], "qty": best["qty"],
                               "profit": best["profit"], "date": best["date"], "pct": best.get("pct")},
        "cargo": [{"good": c["good"], "profit": c["profit"], "sold": c["sold_qty"]} for c in cargo],
        "route": routes[0] and {"from": routes[0]["origin"], "to": routes[0]["dest"],
                                "count": routes[0]["count"]} if routes else None,
        "haunt": visits[0] and {"port": visits[0]["port"], "visits": visits[0]["visits"]} if visits else None,
        "best_port": h["ports"][0] and {"port": h["ports"][0]["port"], "profit": h["ports"][0]["profit"]}
        if h["ports"] and h["ports"][0]["profit"] > 0 else None,
        "epithet": _epithet(k, p),
        "curve": [[m["turn"], int(m["worth"])] for m in _thin(h["months"])],
        "chronicle": _chronicle(h),
        "biggest_sale": max((t.get("total", 0) for t in sells), default=0),
    }


# The honours of the voyage: (key, field, needs at least). Each goes to the house with the most.
HONOURS = [("golden_sale", lambda h: (h["best_sale"] or {}).get("profit", 0), 1),
           ("sea_wolf", lambda h: h["won"], 1),
           ("sharp_eye", lambda h: h["score"] or 0, 1),
           ("far_sailed", lambda h: h["voyages"], 1),
           ("weathered", lambda h: h["storms"] + h["typhoons"], 1),
           ("hard_luck", lambda h: h["losses"], 1)]


def _honours(houses):
    out = []
    for key, value, least in HONOURS:
        best = max(houses, key=value, default=None)
        if best is not None and value(best) >= least:
            out.append({"key": key, "id": best["id"], "value": value(best)})
    return out


def _work(gid):
    game = stats._read(gid)
    if not game:
        return None
    events = game["events"]
    end = next((i for i, e in enumerate(events) if e.get("type") == "game_over"), None)
    if end is None:
        return None
    events = events[:end + 1]               # free play after the close never changes the book
    over = events[end]
    ps = stats._players(events, game["colors"])
    if not ps:
        return None
    houses, _worth, prices = stats._walk(events, ps)
    goods, ports = list(engine.GOODS), list(engine.PORTS)
    total = max((len(h.months) for h in houses.values()), default=0)
    order = [q.get("id") for q in over.get("standings") or []]
    rows = []
    for p in ps:
        h = stats._house_summary(houses[p["id"]], p, prices, True, goods, ports, total)
        if over.get("standings"):
            final = next((q for q in over["standings"] if q.get("id") == p["id"]), None)
            if final:
                h["kpis"]["worth"] = final.get("worth", h["kpis"]["worth"])
        place = 1 + order.index(p["id"]) if p["id"] in order else None
        rows.append(_house(h, place))
    rows.sort(key=lambda r: (r["place"] or 99, -r["worth"]))
    for i, r in enumerate(rows):
        r["place"] = r["place"] or i + 1
    turns = [e.get("turn", 0) for e in events if e.get("cat") == "snapshot"]
    first, last = (min(turns), max(turns)) if turns else (0, 0)
    return {"ok": True, "game": gid, "first": stats._date(first), "last": stats._date(last),
            "months": last - first, "houses": rows, "honours": _honours(rows)}


def book(gid):
    """The finished game's book, or None while the game is still running (or not found)."""
    if not gid:
        return None
    with _lock:
        hit = _books.get(gid)
    if hit is not None:
        return hit
    out = _work(gid)
    if out is not None:
        with _lock:
            if len(_books) >= _KEEP:
                _books.pop(next(iter(_books)))
            _books[gid] = out
    return out
