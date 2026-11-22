"""Harbor View's spectator feed (/api/table): what the Table may show about every house at the table.

The public stream (engine.view with no seat) carries standings only. The Table also wants each house's
Captain, home port and the classes of ship in its fleet, so it can mark home ports and paint the right ship
pieces. This module reads the game and returns plain dictionaries; it never changes anything.

Visibility (Harbor View decision 1):
  open    a solo game, or a game that has ended: nothing here is secret from the one player watching
  public  rivals at the table: only what anyone looking at the harbor could see (this slice sends no more
          than that: the house's Captain, home port, and the class and state of each ship, never a ship's
          name, cash, cargo or prices)
Later slices (port prices, share rings, trades for the zoom popup) are held back at "public" until the finale.
"""
import engine
import journal

# Prices at the start of the month, for "movers": kept from the last month's close (module memory; a restart
# just starts the comparison again from the first prices seen).
_BASE = {"game": None, "turn": None, "prices": {}, "last": {}}



def level(game):
    s = game.s
    if s["phase"] == "ended" or s.get("free_play") or len(s["order"]) <= 1:
        return "open"
    return "public"


def view(game, present=(), seat_view=None):
    s = game.s
    houses = {}
    for pid in s["order"]:
        p = s["players"][pid]
        ships = []
        for sh in p["ships"]:
            spec = engine.SHIPS.get(sh["type"]) or {}
            full = max(1, int(spec.get("hull", 1) or 1))
            ships.append({"type": sh["type"], "role": engine.role_of(sh["type"]),
                          "hull": round(max(0.0, min(1.0, float(sh["hull"]) / full)), 2),
                          "crippled": bool(sh.get("crippled"))})
        houses[pid] = {"captain": p.get("captain") or "", "home": engine.home_of(p), "ships": ships}
    lvl = level(game)
    out = {"ok": True, "level": lvl, "game_id": s.get("game_id"), "turn": s["turn"], "houses": houses,
           "ports": ports(game, lvl), "activity": activity(game, lvl)}
    snapshot = seat_view or game.view(None, present)
    out["state"] = dict(snapshot, me=None, voice={"news": (snapshot.get("voice") or {}).get("news")})
    # Only a single-seat game can export a live private scene. An ended multiplayer game is still not a solo seat.
    if lvl == "open" and len(s["order"]) == 1 and snapshot.get("me"):
        me = snapshot["me"]
        fields = ("id", "name", "firm", "port", "home", "dest", "ready", "cash", "bank", "debt", "worth",
                  "ships", "storm", "battle", "fights", "jail", "legend", "customs", "promotion", "log")
        out["focus"] = {k: me.get(k) for k in fields}
        out["voice"] = snapshot.get("voice") or {}
    out["events"] = story_events(game, lvl)
    return out


STORY_TYPES = {"buy", "sell", "bank", "loan", "shares", "estate", "repair", "ship", "guns", "protect",
               "sail", "stay", "arrived", "depart", "offcourse", "storm", "seized", "ship_lost", "shipwreck",
               "battle", "round", "won", "retreat", "broke_off", "plundered", "paid", "promotion", "promoted",
               "band", "patron", "jail", "released", "gift", "customs", "declare", "tax", "legend",
               "sailed", "storm_report", "battle_result", "customs_open", "customs_declare"}


def story_events(game, lvl):
    if lvl != "open":
        return []
    if not journal._cur or journal._cur.get("gid") != game.s.get("game_id"):
        return []
    with journal._lock:
        recent = list(journal._recent)
    rows = []
    for e in recent:
        if e.get("cat") in ("rejected", "dice", "admin") or e.get("type") not in STORY_TYPES:
            continue
        if e.get("pid") not in game.s["players"]:
            continue
        a = e.get("a") or {}
        row = {"n": e["n"], "at": e.get("t", 0), "turn": e.get("turn"), "type": e["type"],
               "pid": e["pid"], "port": e.get("port") or a.get("port"),
               "dest": e.get("dest") or a.get("dest"), "text": e.get("result") or e.get("msg") or "",
               "good": e.get("good") or a.get("good"), "qty": e.get("qty") or a.get("qty") or 0}
        for k in ("cash", "bank", "debt", "total"):
            if k in e:
                row[k] = e[k]
        for k in ("origin", "sea", "ships", "welcome"):
            if k in e:
                row[k] = e[k]
        row["date"] = engine.date_label(e.get("turn") if e.get("turn") is not None else game.s["turn"])
        if e.get("table_report"):
            row["report"] = e["table_report"]
        if e.get("table_focus"):
            row["focus"] = e["table_focus"]
        rows.append(row)
    return rows[-80:]


# What counts as a big deal for the Table's zoom: a trade or money move of at least half the cash the captain
# held before it (and at least 1,000). Read from the game journal's recent events (journal.py): each action
# event carries the silver, bank and debt before and after.
BIG_SHARE = 0.5
BIG_MIN = 1000
_ACTS = ("buy", "sell", "bank", "loan", "shares", "estate")


def activity(game, lvl, keep=12):
    if lvl != "open":
        return []                                   # with rivals at the table, nothing about deals leaves the Table
    if not journal._cur or journal._cur.get("gid") != game.s.get("game_id"):
        return []
    with journal._lock:
        recent = list(journal._recent)[-300:]
    players = game.s["players"]
    out = []
    for e in recent:
        kind = e.get("type")
        if e.get("do") != "act" or kind not in _ACTS or e.get("pid") not in players:
            continue
        cash = e.get("cash")
        if not cash:
            continue
        moves = [abs(d[1] - d[0]) for d in (cash, e.get("bank"), e.get("debt")) if d]
        value = float(e.get("total") or 0) if kind in ("buy", "sell") else float(max(moves) if moves else 0)
        before = float(cash[0])
        if value < BIG_MIN or value < BIG_SHARE * before:
            continue
        out.append({"n": e.get("n", 0), "pid": e["pid"], "port": e.get("port"), "type": kind, "value": int(value),
                    "cash_out": cash[1] < cash[0], "qty": int(e.get("qty") or 0), "good": e.get("good") or ""})
    return out[-keep:]


def ports(game, lvl):
    """Per port: who holds its shares (public: it is on every Port screen), and at the open level the cargo
    prices now and at the start of the month."""
    s = game.s
    e = engine.R.get("estates") or {}
    total = int(e.get("shares_per_port", 10) or 10)
    book = s.get("shares") or {}
    out = {}
    cur = {k: {g: round(float(v), 2) for g, v in (s["prices"].get(k) or {}).items()} for k in engine.PORTS}
    if _BASE["game"] != s.get("game_id"):
        _BASE.update(game=s.get("game_id"), turn=s["turn"], prices=cur, last=cur)
    elif _BASE["turn"] != s["turn"]:
        _BASE.update(turn=s["turn"], prices=_BASE["last"] or cur)
    _BASE["last"] = cur
    for k in engine.PORTS:
        held = {pid: int(n) for pid, n in (book.get(k) or {}).items() if pid in s["players"] and int(n) > 0}
        row = {"shares": held, "total": total}
        if lvl == "open":
            row["prices"] = cur[k]
            row["base"] = _BASE["prices"].get(k) or cur[k]
        out[k] = row
    return out
