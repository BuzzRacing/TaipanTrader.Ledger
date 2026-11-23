"""The Dashboard's feed (/api/dashboard): history for the pit-wall screen at /dashboard.

The Table's feed (harbor_view.py) is a small snapshot of who is where. The Dashboard also wants history: every
house's net worth month by month, the voyages sailed, the booms and crashes, and (solo) the ghost of the
player's best game. This module reads the game and the game journal through stats.py and returns plain
dictionaries; it never changes anything.

Visibility follows harbor_view.level() (Harbor View decision 1):
  open    a solo game, or a game that has ended: nothing is secret from the one player watching
  public  rivals at the table: only what anyone looking at the harbour could see. Worth, port, ship count and
          hull wear, the voyages sailed, storms and fights, and the news. Never silver, bank, debt, cargo or
          prices. Blocks that need more are left out and the screen stamps them "locked until the finale".

The Command Center (22 Nov 2026) adds: "context" (the context bar, below), "weather" (public) and, for an open
solo game only, "atlas", "routes", "trade", "fleet", "treasury" and "career" from dashboard_suites.py.
"""
import os
import threading
import time

import dashboard_suites
import engine
import harbor_view
import journal
import stats

# With no past game to race, the ghost is a par pace: the starting worth grown by this much every month.
PAR_GROWTH = 0.05
GHOST_SECONDS = 60          # the career sums are not cheap: worked out at most this often
TAPE_KEEP = 60

_LOCK = threading.Lock()
_WALK = {"key": None, "val": None}
_GHOST = {"key": None, "at": 0.0, "val": None}

# What goes on the telegraph tape, by visibility. The wording is built on the screen from these fields, so a
# public item never carries the journal's own message (which can hold silver and cargo).
TAPE_PUBLIC = {"sailed", "arrived", "offcourse", "storm_damage", "ship_lost", "ship_crippled", "shipwreck",
               "battle", "won", "retreat", "broke_off", "paid", "plundered", "promotion", "band",
               "patron", "windfall", "shock", "ban", "ban_lifted"}


def _walked(gid):
    """stats.py's walk of the game's journal, kept until the journal grows."""
    path = journal.events_path(gid)
    if not path or not os.path.isfile(path):
        return None
    key = (gid, os.path.getsize(path))
    with _LOCK:
        if _WALK["key"] == key:
            return _WALK["val"]
    game = stats._read(gid)
    if not game:
        return None
    ps = stats._players(game["events"], game["colors"], gid)
    extra = {}
    houses, _worth, _prices = stats._walk(game["events"], ps, extra)
    val = (ps, houses, extra)
    with _LOCK:
        _WALK.update(key=key, val=val)
    return val


def _hull(p):
    ships = []
    for sh in p.get("ships") or ():
        spec = engine.SHIPS.get(sh["type"]) or {}
        full = max(1, int(spec.get("hull", 1) or 1))
        ships.append({"hull": round(max(0.0, min(1.0, float(sh["hull"]) / full)), 2),
                      "crippled": bool(sh.get("crippled"))})
    return ships


def _months(h, game, p):
    """[{turn, date, worth}] for one house, ending on the worth it has right now."""
    rows = [{"turn": m["turn"], "date": m["date"], "worth": int(m["worth"])} for m in (h.months if h else [])]
    now = int(game.worth(p))
    turn = game.s["turn"]
    if rows and rows[-1]["turn"] == turn:
        rows[-1]["worth"] = now
    elif game.s["phase"] != "lobby":
        rows.append({"turn": turn, "date": engine.date_label(turn), "worth": now})
    return rows


def _ghost(game, gid, pid, months_total):
    """Solo only. The best finished game this Captain has sailed, by net worth month by month; with none, a
    par pace. {kind: best|par, label, curve: [worth per month, month 0 first], final}."""
    key = (gid, len(journal.games()))
    now = time.time()
    with _LOCK:
        if _GHOST["key"] == key and now - _GHOST["at"] < GHOST_SECONDS:
            return _GHOST["val"]
    p = game.s["players"][pid]
    val = None
    try:
        import captains
        cap = captains.get(p["captain"]) if p.get("captain") else None
        # running_gid is this game and running_pid is nobody's: the game being played never races itself.
        data = stats.career(p.get("name") or "", running_gid=gid, running_pid=None,
                            links=captains.links(cap) if cap else None)
        done = [g for g in (data or {}).get("games", []) if g.get("ended") and g.get("curve")]
        if done:
            best = max(done, key=lambda g: g["worth"])
            val = {"kind": "best", "label": best.get("firm") or "", "date": best.get("last") or "",
                   "curve": [int(x) for x in best["curve"]], "final": int(best["worth"])}
    except Exception:       # a career that will not add up must never take the Dashboard down
        val = None
    if val is None:
        start = 0
        h = (_walked(gid) or (None, {}, None))[1].get(pid)
        if h and h.months:
            start = int(h.months[0]["worth"])
        start = start or int(game.worth(p))
        n = max(2, months_total + 1)
        curve = [int(round(start * (1 + PAR_GROWTH) ** i)) for i in range(n)]
        val = {"kind": "par", "label": "", "date": "", "curve": curve, "final": curve[-1]}
    with _LOCK:
        _GHOST.update(key=key, at=now, val=val)
    return val


def context(game, lvl, rows):
    """The Command Center's context bar (plan 4.2): the few facts every tab shows. Table-wide facts are public:
    the date, the months left, each sea's forecast and how often a forecast holds. The "captain" block is the
    one house's own position and is sent only for an open solo game; with rivals at the table it is None.
    Reads only; rows are the houses view() has already built from this same snapshot."""
    s = game.s
    total = int(s.get("years") or 0) * 12
    seas = {r: int((s.get("weather") or {}).get(r, 0)) for r in engine.REGIONS}
    worst = max(seas, key=lambda r: seas[r]) if seas else None
    out = {"date": engine.date_label(s["turn"]), "turn": s["turn"], "phase": s["phase"],
           "months_total": total, "months_left": max(0, total - s["turn"]) if total else None,
           "seas": seas, "worst_sea": {"region": worst, "level": seas[worst]} if worst else None,
           "forecast_accuracy": float((engine.R.get("weather") or {}).get("forecast_accuracy", 1.0)),
           "houses": len(rows), "captain": None}
    if lvl == "open" and len(s["order"]) == 1 and s["phase"] != "lobby" and rows:
        pid = s["order"][0]
        p, row = s["players"][pid], rows[0]
        months, hull = row["months"], row["hull"]
        out["captain"] = {
            "id": pid, "firm": row["firm"], "port": p.get("port"), "dest": p.get("dest") or None,
            "at_sea": s["phase"] == "sea", "worth": row["worth"],
            # this month so far: worth now less the worth the last month closed on (None in the first month)
            "worth_change": months[-1]["worth"] - months[-2]["worth"] if len(months) >= 2 else None,
            "rank": game.commissioned_rank(p)["title"],
            "fleet": {"ships": len(hull), "crippled": sum(1 for sh in hull if sh["crippled"]),
                      "hull": round(sum(sh["hull"] for sh in hull) / len(hull), 2) if hull else None}}
    return out


def view(game, present=()):
    s = game.s
    lvl = harbor_view.level(game)
    gid = journal.current() or s.get("game_id")
    walked = _walked(gid) if gid else None
    ps, houses, extra = walked if walked else ([], {}, {})
    open_ = lvl == "open"
    out = {"ok": True, "level": lvl, "game_id": gid, "turn": s["turn"], "phase": s["phase"],
           "years": s.get("years"), "date": engine.date_label(s["turn"])}

    rows = []
    for pid in s["order"]:
        p = s["players"][pid]
        h = houses.get(pid)
        ships = _hull(p)
        legs = [{"origin": lg.get("origin"), "dest": lg.get("dest"), "turn": lg.get("turn"),
                 "outcome": lg.get("outcome"), "arrived": lg.get("arrived")} for lg in (h.legs if h else [])]
        rows.append({"id": pid, "firm": p.get("firm") or p.get("name"), "name": p.get("name"),
                     "color": p.get("color", 0), "port": p.get("port"), "home": engine.home_of(p),
                     "worth": int(game.worth(p)), "months": _months(h, game, p),
                     "ships": len(ships), "hull": ships, "legs": legs,
                     "lanes": [{"origin": r["origin"], "dest": r["dest"], "count": r["count"],
                                "wrecks": r["wrecks"]} for r in stats._routes(h)] if h else []})
    out["houses"] = rows
    out["context"] = context(game, lvl, rows)
    # The Command Center's suites (dashboard_suites.py). The weather glass is public. One Captain's own position
    # (atlas, routes, trade, fleet, treasury, career) is built only for an open solo game: with rivals at the table
    # the builder is not called at all, so those sections cannot be in the response.
    out["weather"] = dashboard_suites.weather(game)
    read = stats._read(gid) if gid else None
    out["weather"]["history"] = dashboard_suites.weather_history(game, read["events"] if read else None, lvl)
    if lvl == "open" and len(s["order"]) == 1 and s["phase"] != "lobby":
        out.update(dashboard_suites.private(game, s["order"][0]))

    months_total = int(s.get("years") or 0) * 12 or max([len(r["months"]) for r in rows] or [0])
    if open_ and len(s["order"]) == 1 and s["phase"] != "lobby":
        out["ghost"] = _ghost(game, gid, s["order"][0], months_total)
    else:
        out["ghost"] = None

    out["tape"] = tape(game, gid, lvl)
    out["locked"] = not open_
    if open_:
        lane_profit, deals = {}, []
        for pid, h in houses.items():
            if pid not in s["players"]:
                continue
            for r in stats._routes(h):
                k = "{}>{}".format(r["origin"], r["dest"])
                lane_profit[k] = lane_profit.get(k, 0) + int(r["profit"])
            for t in h.trades:
                if t.get("side") == "sell" and t.get("profit") is not None:
                    deals.append({"pid": pid, "date": t["date"], "turn": t["turn"], "port": t["port"],
                                  "good": t["good"], "qty": t["qty"], "total": t["total"], "profit": t["profit"]})
        deals.sort(key=lambda d: -d["profit"])
        out["lane_profit"] = lane_profit
        out["deals"] = deals[:8]
        out["ports"] = harbor_view.ports(game, lvl)
        out["booms"] = [w for w in (extra.get("windfalls") or [])][-14:]
        out["market_effects"] = [
            {"port": w["port"], "good": w["good"],
             "sort": w.get("kind") or ("boom" if float(w["mult"]) >= 1 else "crash"),
             "mult": round(float(w["mult"]), 2), "turns": int(w["turns"])}
            for w in list(s.get("windfalls") or []) + list(s.get("shocks") or [])
            if int(w.get("turns") or 0) > 0
        ]
    return out


def tape(game, gid, lvl):
    """The newest events of this game for the telegraph tape: what the lane's visibility allows."""
    if not gid:
        return []
    # From the recorded journal, not the live console list, so the tape is full again after a restart.
    read = stats._read(gid)
    recent = read["events"][-600:] if read else []
    players = game.s["players"]
    rows = []
    for e in recent:
        kind = e.get("type")
        if kind not in TAPE_PUBLIC or e.get("cat") in ("rejected", "dice", "admin"):
            continue
        pid = e.get("pid")
        if pid is not None and pid not in players:
            continue
        a = e.get("a") or {}
        row = {"n": e["n"], "turn": e.get("turn"), "type": kind, "pid": pid,
               "port": e.get("port") or a.get("port"), "origin": e.get("origin"), "dest": e.get("dest"),
               "good": e.get("good"), "sort": e.get("sort")}
        rows.append(row)
    if lvl == "open":
        for d in harbor_view.activity(game, lvl, keep=TAPE_KEEP):
            rows.append({"n": d["n"], "turn": game.s["turn"], "type": "deal", "pid": d["pid"], "port": d["port"],
                         "good": d["good"], "qty": d["qty"], "value": d["value"], "cash_out": d["cash_out"],
                         "deal": d["type"]})
    rows.sort(key=lambda r: r["n"])
    return rows[-TAPE_KEEP:]
