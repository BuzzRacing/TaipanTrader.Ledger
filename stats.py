"""SeaTrader statistics: the numbers behind a player's fortunes.

Everything here is worked out from the game journal (journal.py), which
already records every trade, voyage, battle, storm, interest charge and a
monthly snapshot of every house and every price. Nothing new is tracked, so
stats exist for every game recorded since records began.

Two views, both for one player:

  voyage(gid, ...)   one game, month by month
  career(name, ...)  every recorded game that player sat in, all-time

Fair play: while a game is still running, a player sees their own numbers,
the prices they actually saw (their own port each month and their own
trades) and rivals' net worth (already public on the standings). When the
game is over, or for any game no longer in progress, everything unlocks:
every price in every port and every rival's full breakdown.

Like the engine, this module never writes anything. It only reads the
journal and returns plain dictionaries for /api/stats.
"""
import json
import math
import os
import threading

import engine
import journal

_lock = threading.Lock()
_cache = {}          # gid -> (file size, parsed game)
_results = {}        # (gid, file size, house, running, language) -> worked-out voyage
_CACHE_MAX = 64

# Actions whose silver change counts as a cost or income line in "where the silver went".
ACTION_LINES = {"buy_gun": "guns", "repair": "repairs", "buy_ship": "ships_bought", "sell_ship": "ships_sold",
                "protection": "protection"}


# ------------------------------------------------------------- reading --
def _read(gid):
    """Every event of a game, without the bulky replay state, plus the seat
    colours found in the snapshots. Cached until the journal grows."""
    path = journal.events_path(gid)
    if not path or not os.path.isfile(path):
        return None
    size = os.path.getsize(path)
    with _lock:
        hit = _cache.get(gid)
        if hit and hit[0] == size:
            return hit[1]
    events, colors = [], {}
    try:
        with open(path, encoding="utf-8") as f:
            for raw in f:
                try:
                    e = json.loads(raw)
                except ValueError:
                    continue
                st = e.pop("state", None)
                if isinstance(st, dict):
                    for pid, p in (st.get("players") or {}).items():
                        if isinstance(p, dict) and "color" in p:
                            colors[pid] = p["color"]
                events.append(e)
    except OSError:
        return None
    game = {"events": events, "colors": colors, "size": size}
    with _lock:
        if len(_cache) >= _CACHE_MAX:
            _cache.pop(next(iter(_cache)))
        _cache[gid] = (size, game)
    return game


def _meta(gid):
    for m in journal.games():
        if m.get("id") == gid:
            return m
    return {"id": gid}


def _players(events, colors):
    """id -> name, firm, colour slot and seat order, from joins and snapshots."""
    out, order = {}, []
    for e in events:
        if e.get("type") in ("seat_new", "seat_reclaim") and e.get("pid"):
            p = out.setdefault(e["pid"], {"id": e["pid"]})
            p["name"] = e.get("name") or e.get("who") or p.get("name")
            p["firm"] = e.get("firm") or p.get("firm")
            if e["pid"] not in order:
                order.append(e["pid"])
        for f in e.get("firms") or ():
            p = out.setdefault(f["id"], {"id": f["id"]})
            p["name"], p["firm"] = f.get("name", p.get("name")), f.get("firm", p.get("firm"))
            if f["id"] not in order:
                order.append(f["id"])
    for i, pid in enumerate(order):
        out[pid]["seat"] = i
        out[pid]["color"] = colors.get(pid, i) % 8
    return [out[pid] for pid in order]


def _date(turn):
    return engine.date_label(turn)


def _ended(events):
    return any(e.get("type") == "game_over" for e in events)


# ---------------------------------------------------------- one player --
class _House:
    """Running tally for one house while the journal is read in order."""

    def __init__(self, pid):
        self.pid = pid
        self.hold = {}          # good -> [units, total cost], cargo and warehouse together
        self.cargo = {}         # good -> per-cargo totals
        self.trades = []
        self.lines = {}         # where the silver went (positive = came in)
        self.legs = []
        self.leg = None
        self.battles = []
        self.battle = None
        self.perils = {"storms": 0, "storm_damage": 0, "typhoons": 0, "offcourse": 0, "battles": 0, "won": 0,
                       "escaped": 0, "broke_off": 0, "plundered": 0, "driven_off": 0, "ships_lost": 0,
                       "seizures": 0, "robbed": 0, "wrecks": 0, "booty": 0, "plunder_value": 0,
                       "seized_value": 0, "fines": 0, "robbed_value": 0, "wreck_cash": 0, "wreck_cargo_value": 0,
                       "cargo_lost_value": 0, "enemy_sunk": 0, "shots": 0, "hits": 0}
        self.events = []        # notable moments, for the timeline markers
        self.port_month = {}    # (port, turn) -> realised profit
        self.port_good = {}     # (port, good) -> realised profit
        self.port_stats = {}    # port -> visits, sales, buys, profit
        self.months = []        # snapshot rows
        self.seen = {}          # good -> list of (turn, port, price) this house saw

    def _c(self, good):
        return self.cargo.setdefault(good, {"good": good, "bought_qty": 0, "bought_cost": 0, "sold_qty": 0,
                                            "sold_rev": 0, "profit": 0, "trades": 0, "lost_qty": 0,
                                            "lost_value": 0, "margin_paid": 0, "impact": 0})

    def _ps(self, port):
        return self.port_stats.setdefault(port, {"port": port, "visits": 0, "buys": 0, "sales": 0, "spent": 0,
                                                 "revenue": 0, "profit": 0})

    def line(self, key, amount):
        if amount:
            self.lines[key] = self.lines.get(key, 0) + amount

    def avg(self, good):
        units, cost = self.hold.get(good, (0, 0))
        return cost / units if units > 0 else 0.0

    def remove(self, good, qty):
        """Takes units out of the hold at average cost and returns their cost."""
        units, cost = self.hold.get(good, (0, 0))
        qty = min(qty, units)
        if qty <= 0:
            return 0.0
        each = cost / units
        self.hold[good] = (units - qty, cost - each * qty)
        if self.hold[good][0] <= 0:
            self.hold.pop(good)
        return each * qty

    def lose(self, goods, why, turn):
        value = 0.0
        for g, q in (goods or {}).items():
            v = self.remove(g, q)
            c = self._c(g)
            c["lost_qty"] += q
            c["lost_value"] += v
            c["profit"] -= v
            value += v
        return value


def _walk(events, ps):
    """Reads one game's journal once and tallies every house."""
    houses = {p["id"]: _House(p["id"]) for p in ps}
    prices_by_turn = {}     # turn -> full price table (from snapshots)
    worth = {p["id"]: [] for p in ps}
    contraband = set(engine.contraband())
    last_cargo = {}
    for e in events:
        typ, cat, pid, turn = e.get("type"), e.get("cat"), e.get("pid"), e.get("turn", 0)
        h = houses.get(pid)

        if cat == "snapshot" and e.get("firms") is not None:
            if e.get("prices"):
                prices_by_turn[turn] = e["prices"]
            for f in e["firms"]:
                hh = houses.get(f["id"])
                if hh is None:
                    continue
                row = {"turn": turn, "date": e.get("date") or _date(turn), "cash": f["cash"], "bank": f["bank"],
                       "debt": f["debt"], "worth": f["worth"], "port": f["port"], "ships": len(f.get("ships") or ()),
                       "guns": f.get("guns", 0), "hold": f.get("hold", 0), "used": f.get("used", 0),
                       "rep": f.get("rep") or {}, "rank": engine.rank_for(f["worth"])}
                if hh.months and hh.months[-1]["turn"] == turn:
                    hh.months[-1] = row
                else:
                    hh.months.append(row)
                series = worth.setdefault(f["id"], [])
                if series and series[-1][0] == turn:
                    series[-1] = (turn, f["worth"])
                else:
                    series.append((turn, f["worth"]))
                if e.get("prices") and f["port"] in e["prices"] and e.get("phase") != "lobby":
                    for g, v in e["prices"][f["port"]].items():
                        hh.seen.setdefault(g, []).append((turn, f["port"], v))
            continue
        if h is None:
            continue

        if cat == "trade" and typ in ("buy", "sell") and e.get("good"):
            g, q, total = e["good"], int(e.get("qty") or 0), float(e.get("total") or 0)
            port = e.get("port")
            market = (e.get("price") or [0])[0]
            c = h._c(g)
            c["trades"] += 1
            ps_ = h._ps(port)
            t = {"turn": turn, "date": _date(turn), "port": port, "side": typ, "good": g, "qty": q,
                 "unit": e.get("unit"), "total": int(total), "market": market, "margin": e.get("margin")}
            m = float(e.get("margin") or 0)
            if typ == "buy":
                units, cost = h.hold.get(g, (0, 0))
                h.hold[g] = (units + q, cost + total)
                c["bought_qty"] += q
                c["bought_cost"] += total
                # What the trade cost beyond the market price: the dealer's cut, and the
                # price moving against a big order (the market's depth).
                bare = total / (1 + m)
                c["margin_paid"] += total - bare
                c["impact"] += max(0.0, bare - q * market)
                ps_["buys"] += 1
                ps_["spent"] += total
                h.line("purchases", -total)
            else:
                basis = h.remove(g, q)
                profit = total - basis
                c["sold_qty"] += q
                c["sold_rev"] += total
                c["profit"] += profit
                bare = total / (1 - m) if m < 1 else total
                c["margin_paid"] += bare - total
                c["impact"] += max(0.0, q * market - bare)
                t["basis"] = int(round(basis))
                t["profit"] = int(round(profit))
                t["pct"] = round(profit / basis, 4) if basis > 0 else None
                ps_["sales"] += 1
                ps_["revenue"] += total
                ps_["profit"] += profit
                key = (port, turn)
                h.port_month[key] = h.port_month.get(key, 0) + profit
                k2 = (port, g)
                h.port_good[k2] = h.port_good.get(k2, 0) + profit
                h.line("sales", total)
            if e.get("unit") is not None:
                h.seen.setdefault(g, []).append((turn, port, e["unit"]))
            h.trades.append(t)
            continue

        if typ in ("customs_declare", "customs_auto"):
            # The Port Authority: what she bought counts as a sale at the declared price; the rest of the
            # silver that changed hands (tax, fines, a sweetener) is the Port Authority's line.
            bought_in = 0
            for r in e.get("lines") or ():
                if r.get("units"):
                    g, q, paid = r["good"], int(r["units"]), float(r.get("paid") or 0)
                    basis = h.remove(g, q)
                    c = h._c(g)
                    c["sold_qty"] += q
                    c["sold_rev"] += paid
                    c["profit"] += paid - basis
                    bought_in += paid
                    h.line("sales", paid)
            if e.get("cash"):
                was, now = e["cash"]
                h.line("customs", now - was - bought_in)
            continue
        if typ == "customs_buyback" and e.get("good"):
            g, q, cost = e["good"], int(e.get("qty") or 0), float(e.get("cost") or 0)
            units, held = h.hold.get(g, (0, 0))
            h.hold[g] = (units + q, held + cost)
            c = h._c(g)
            c["bought_qty"] += q
            c["bought_cost"] += cost
            h.line("purchases", -cost)
            continue

        if typ in ACTION_LINES and e.get("cash"):
            was, now = e["cash"]
            h.line(ACTION_LINES[typ], now - was)
            continue

        if typ == "interest" and cat == "finance":
            b, d = e.get("bank") or [0, 0], e.get("debt") or [0, 0]
            h.line("bank_interest", b[1] - b[0])
            h.line("loan_interest", -(d[1] - d[0]))
            continue
        if typ == "robbed":
            lost = int(e.get("lost") or 0)
            h.perils["robbed"] += 1
            h.perils["robbed_value"] += lost
            h.line("robbed", -lost)
            h.events.append({"turn": turn, "kind": "robbed", "value": lost})
            continue

        if typ == "sailed":
            h.leg = {"turn": turn, "date": _date(turn), "origin": e.get("origin"), "dest": e.get("dest"),
                     "sea": e.get("sea", 0), "risk": e.get("risk", 0), "orders": e.get("orders"),
                     "cargo": sum((e.get("cargo") or {}).values()), "perils": [], "outcome": "arrived"}
            last_cargo[pid] = dict(e.get("cargo") or {})
            h.legs.append(h.leg)
            continue
        if typ == "anchor":
            continue
        if typ == "storm_damage":
            dmg = sum(x.get("damage", 0) for x in e.get("hits") or ())
            h.perils["storms"] += 1
            h.perils["storm_damage"] += dmg
            typhoon = "typhoon" in (e.get("msg") or "")
            if typhoon:
                h.perils["typhoons"] += 1
            if h.leg is not None:
                h.leg["perils"].append("typhoon" if typhoon else "storm")
            h.events.append({"turn": turn, "kind": "typhoon" if typhoon else "storm", "value": dmg})
            continue
        if typ == "offcourse":
            h.perils["offcourse"] += 1
            if h.leg is not None:
                h.leg["perils"].append("offcourse")
                h.leg["blown_to"] = e.get("dest")
            continue
        if cat == "dice" and typ == "protection" and e.get("hit"):
            h.perils["driven_off"] += 1
            if h.leg is not None:
                h.leg["perils"].append("driven_off")
            continue
        if cat == "battle":
            if typ == "battle":
                h.battle = {"turn": turn, "date": _date(turn), "enemy": e.get("enemy"), "count": e.get("count", 0),
                            "orders": e.get("orders"), "guns": e.get("guns", 0), "rounds": 0, "result": "fought",
                            "booty": 0, "plundered": 0, "damage": 0, "sunk": 0, "ships_lost": 0,
                            "lord": "war" in str(e.get("enemy") or "")}
                h.battles.append(h.battle)
                h.perils["battles"] += 1
                if h.leg is not None:
                    h.leg["perils"].append("battle")
                    h.battle["route"] = [h.leg["origin"], h.leg["dest"]]
            elif h.battle is not None:
                b = h.battle
                b["rounds"] = max(b["rounds"], int(e.get("round") or b["rounds"]))
                if typ == "round":
                    h.perils["shots"] += e.get("shots", 0)
                    h.perils["hits"] += e.get("hits", 0)
                    b["sunk"] = b["count"] - e.get("enemy_left", b["count"])
                elif typ == "enemy_fire":
                    b["damage"] += sum(x.get("damage", 0) for x in e.get("hits") or ())
                elif typ == "won":
                    b["result"], b["rounds"], b["booty"], b["sunk"] = "won", e.get("rounds", b["rounds"]), \
                        int(e.get("booty") or 0), b["count"]
                    h.perils["won"] += 1
                    h.perils["booty"] += b["booty"]
                    h.line("booty", b["booty"])
                elif typ == "broke_off":
                    b["result"], b["sunk"] = "broke_off", e.get("sunk", b["sunk"])
                    h.perils["broke_off"] += 1
                elif typ == "retreat":
                    v = h.lose(e.get("lost"), "overflow", turn)
                    b["result"], b["sunk"] = "retreated", b["count"] - e.get("enemy_left", b["count"])
                    b["damage"] += sum(x.get("damage", 0) for x in e.get("hits") or ())
                    b["overboard"] = int(round(v))
                    h.perils["retreated"] = h.perils.get("retreated", 0) + 1
                    h.perils["cargo_lost_value"] += v
                    h.line("cargo_lost", -v)
                elif typ == "paid":
                    b["result"], b["paid"] = "paid", int(e.get("price") or 0)
                    h.perils["paid_off"] = h.perils.get("paid_off", 0) + 1
                    h.line("protection" if e.get("tribute") else "parley", -b["paid"])
                elif typ == "plundered":
                    v = h.lose(e.get("lost"), "plunder", turn)
                    b["result"], b["plundered"] = "plundered", int(round(v))
                    h.perils["plundered"] += 1
                    h.perils["plunder_value"] += v
                    h.line("plundered", -v)
            continue
        if cat == "dice" and typ == "escape" and e.get("hit") and h.battle is not None:
            h.battle["result"] = "escaped"
            h.battle["rounds"] = int(e.get("round") or h.battle["rounds"])
            h.perils["escaped"] += 1
            continue
        if typ == "ship_lost":
            h.perils["ships_lost"] += 1
            if h.battle is not None and h.battle["turn"] == turn and h.battle["result"] == "fought":
                h.battle["ships_lost"] += 1
                h.battle["result"] = "sunk"
            h.events.append({"turn": turn, "kind": "ship_lost", "name": e.get("name")})
            continue
        if typ == "cargo_lost":
            v = h.lose(e.get("lost"), "overflow", turn)
            h.perils["cargo_lost_value"] += v
            h.line("cargo_lost", -v)
            continue
        if typ == "shipwreck":
            v = h.lose(e.get("cargo"), "wreck", turn)
            cash = int(e.get("lost") or 0)
            h.perils["wrecks"] += 1
            h.perils["wreck_cash"] += cash
            h.perils["wreck_cargo_value"] += v
            h.line("shipwreck", -(cash + v + int(e.get("debt") or 0)))
            if h.leg is not None:
                h.leg["outcome"] = "wrecked"
            h.events.append({"turn": turn, "kind": "wreck", "value": int(cash + v)})
            continue
        if typ == "arrived":
            port = e.get("port")
            if h.leg is not None:
                h.leg["arrived"] = port
                if port != h.leg["dest"]:
                    h.leg["outcome"] = "offcourse"
            h._ps(port)["visits"] += 1
            last_cargo[pid] = dict(e.get("cargo") or {})
            continue
        if typ == "seized":
            # newer journals list exactly what was taken (gold is only sometimes contraband)
            held = dict(e["goods"]) if isinstance(e.get("goods"), dict) else \
                {g: q for g, q in last_cargo.get(pid, {}).items() if g in contraband}
            v = h.lose(held, "seized", turn)
            fine = int(e.get("fine") or 0)
            h.perils["seizures"] += 1
            h.perils["fines"] += fine
            h.perils["seized_value"] += v
            h.line("seized", -(v + fine))
            if h.leg is not None:
                h.leg["perils"].append("seized")
            h.events.append({"turn": turn, "kind": "seized", "value": int(v + fine)})
            continue
    return houses, worth, prices_by_turn


def _pctile(value, sample):
    if not sample:
        return None
    below = sum(1 for v in sample if v < value)
    equal = sum(1 for v in sample if v == value)
    return (below + 0.5 * equal) / len(sample)


def _score_trades(h, prices_by_turn, reveal):
    """'Bought low, sold high': where each trade's price sat among every price of
    that cargo the player saw this game (or, once unlocked, every price in every port)."""
    pool = {}
    if reveal:
        for row in prices_by_turn.values():
            for port, goods in row.items():
                for g, v in goods.items():
                    pool.setdefault(g, []).append(v)
    else:
        for g, rows in h.seen.items():
            pool[g] = [v for _t, _p, v in rows]
    scores = []
    for t in h.trades:
        p = _pctile(t["unit"] or 0, pool.get(t["good"]))
        if p is None:
            continue
        s = (1 - p) if t["side"] == "buy" else p
        t["score"] = int(round(100 * s))
        scores.append(t["score"])
    return int(round(sum(scores) / len(scores))) if scores else None


def _markets(h, prices_by_turn, reveal, goods, ports):
    """Latest price per port and cargo, and each cargo's price history.
    Fair play: only what this house saw. Unlocked: everything."""
    latest, history = {}, {g: {} for g in goods}
    if reveal:
        for turn in sorted(prices_by_turn):
            for port, row in prices_by_turn[turn].items():
                for g, v in row.items():
                    if g in history:
                        history[g].setdefault(port, []).append([turn, round(v, 2)])
                    latest.setdefault(port, {})[g] = {"price": round(v, 2), "turn": turn}
    else:
        for g, rows in h.seen.items():
            if g not in history:
                continue
            for turn, port, v in sorted(rows, key=lambda r: r[0]):
                lst = history[g].setdefault(port, [])
                if lst and lst[-1][0] == turn:
                    lst[-1] = [turn, round(v, 2)]
                else:
                    lst.append([turn, round(v, 2)])
                latest.setdefault(port, {})[g] = {"price": round(v, 2), "turn": turn}
    return {"latest": latest, "history": history, "full": bool(reveal)}


def _routes(h):
    agg = {}
    for leg in h.legs:
        k = (leg["origin"], leg["dest"])
        r = agg.setdefault(k, {"origin": k[0], "dest": k[1], "count": 0, "perils": 0, "wrecks": 0, "profit": 0})
        r["count"] += 1
        r["perils"] += len([x for x in leg["perils"] if x != "driven_off"])
        if leg["outcome"] == "wrecked":
            r["wrecks"] += 1
    # A route earns what the house made selling at the destination in the month it arrived.
    for leg in h.legs:
        if leg.get("arrived") and leg["outcome"] != "wrecked":
            p = h.port_month.get((leg["arrived"], leg["turn"] + 1), 0)
            agg[(leg["origin"], leg["dest"])]["profit"] += p
    return sorted(agg.values(), key=lambda r: -r["count"])


def _house_summary(h, ps_row, prices_by_turn, reveal, goods, ports, months_total):
    first = h.months[0] if h.months else None
    last = h.months[-1] if h.months else None
    peak = max(h.months, key=lambda m: m["worth"]) if h.months else None
    low = min(h.months, key=lambda m: m["worth"]) if h.months else None
    sells = [t for t in h.trades if t["side"] == "sell"]
    wins = [t for t in sells if t.get("profit", 0) > 0]
    realised = sum(c["profit"] for c in h.cargo.values())
    score = _score_trades(h, prices_by_turn, reveal)
    rankups, prev = [], None
    order = [r["title"] for r in engine.CFG["ranks"]]
    level = lambda title: order.index(title) if title in order else -1
    for m in h.months:
        if m["rank"] != prev:
            if prev is not None:
                rankups.append({"turn": m["turn"], "date": m["date"], "rank": m["rank"], "from": prev,
                                "up": level(m["rank"]) > level(prev)})
            prev = m["rank"]
    cargo = []
    for g, c in h.cargo.items():
        c = dict(c)
        for k in ("bought_cost", "sold_rev", "profit", "lost_value", "margin_paid", "impact"):
            c[k] = int(round(c[k]))
        c["avg_buy"] = round(c["bought_cost"] / c["bought_qty"], 2) if c["bought_qty"] else None
        c["avg_sell"] = round(c["sold_rev"] / c["sold_qty"], 2) if c["sold_qty"] else None
        cargo.append(c)
    cargo.sort(key=lambda c: -c["profit"])
    perils = {k: int(round(v)) for k, v in h.perils.items()}
    lines = {k: int(round(v)) for k, v in h.lines.items()}
    margin = int(round(sum(c["margin_paid"] for c in h.cargo.values())))
    impact = int(round(sum(c["impact"] for c in h.cargo.values())))
    kpis = {
        "worth": last["worth"] if last else 0,
        "start_worth": first["worth"] if first else 0,
        "peak": peak["worth"] if peak else 0, "peak_date": peak["date"] if peak else "",
        "low": low["worth"] if low else 0, "low_date": low["date"] if low else "",
        "rank": last["rank"] if last else "",
        "months": len(h.months), "trades": len(h.trades), "sells": len(sells),
        "win_rate": round(len(wins) / len(sells), 3) if sells else None,
        "realised": int(round(realised)), "score": score, "margin_paid": margin, "impact": impact,
        "voyages": len(h.legs), "ports_visited": len([p for p in h.port_stats.values() if p["visits"]]),
        "best_cargo": cargo[0]["good"] if cargo and cargo[0]["profit"] > 0 else None,
        "battles": perils["battles"], "won": perils["won"], "wrecks": perils["wrecks"],
        "booty": perils["booty"],
        "losses": int(round(h.perils["plunder_value"] + h.perils["seized_value"] + h.perils["fines"]
                            + h.perils["robbed_value"] + h.perils["wreck_cash"] + h.perils["wreck_cargo_value"]
                            + h.perils["cargo_lost_value"])),
        "accuracy": round(h.perils["hits"] / h.perils["shots"], 3) if h.perils["shots"] else None,
        "debt_free": next((m["date"] for m in h.months if m["debt"] <= 0), None),
    }
    best = sorted(sells, key=lambda t: -t.get("profit", 0))[:6]
    worst = sorted([t for t in sells if t.get("profit", 0) < 0], key=lambda t: t["profit"])[:6]
    turns = sorted({m["turn"] for m in h.months})
    heat_pm = {p: {} for p in ports}
    for (port, turn), v in h.port_month.items():
        if port in heat_pm:
            heat_pm[port][turn] = int(round(v))
    heat_pg = {p: {} for p in ports}
    for (port, g), v in h.port_good.items():
        if port in heat_pg:
            heat_pg[port][g] = int(round(v))
    for ps_ in h.port_stats.values():
        for k in ("spent", "revenue", "profit"):
            ps_[k] = int(round(ps_[k]))
    rep = {p: [m["rep"].get(p) for m in h.months] for p in ports}
    return {
        "id": ps_row["id"], "name": ps_row.get("name"), "firm": ps_row.get("firm"), "color": ps_row.get("color", 0),
        "kpis": kpis, "months": [{k: v for k, v in m.items() if k != "rep"} for m in h.months],
        "rankups": rankups, "cargo": cargo, "lines": lines, "trades": h.trades[-400:], "best": best, "worst": worst,
        "legs": h.legs, "routes": _routes(h), "battles": h.battles, "perils": perils, "moments": h.events,
        "ports": sorted(h.port_stats.values(), key=lambda p: -p["profit"]),
        "heat_port_month": heat_pm, "heat_port_good": heat_pg, "turns": turns, "rep": rep,
        "markets": _markets(h, prices_by_turn, reveal, goods, ports),
    }


def _public(h, ps_row):
    """What anyone can see of a rival while the game runs: the worth curve and rank."""
    last = h.months[-1] if h.months else None
    return {"id": ps_row["id"], "name": ps_row.get("name"), "firm": ps_row.get("firm"),
            "color": ps_row.get("color", 0), "public": True,
            "kpis": {"worth": last["worth"] if last else 0, "rank": last["rank"] if last else "",
                     "peak": max((m["worth"] for m in h.months), default=0)},
            "months": [{"turn": m["turn"], "date": m["date"], "worth": m["worth"]} for m in h.months]}


def find_pid(gid, name):
    game = _read(gid)
    if not game:
        return None
    want = (name or "").strip().lower()
    for p in _players(game["events"], game["colors"]):
        if (p.get("name") or "").strip().lower() == want:
            return p["id"]
    return None


def voyage(gid, pid, running=False, meta=None):
    """One game for one house. running=True means the game is still being played
    and has not ended, so fair-play rules apply."""
    game = _read(gid)
    if not game:
        return None
    key = (gid, game["size"], pid, bool(running), id(engine.CFG))      # settings change -> work it out again
    with _lock:
        hit = _results.get(key)
    if hit is not None:
        return hit
    out = _voyage(gid, pid, running, meta, game)
    with _lock:
        if len(_results) >= _CACHE_MAX * 4:
            _results.clear()
        _results[key] = out
    return out


def _voyage(gid, pid, running, meta, game):
    events = game["events"]
    ps = _players(events, game["colors"])
    if pid not in {p["id"] for p in ps}:
        return None
    ended = _ended(events)
    reveal = ended or not running
    houses, worth, prices_by_turn = _walk(events, ps)
    goods, ports = list(engine.GOODS), list(engine.PORTS)
    months_total = max((len(h.months) for h in houses.values()), default=0)
    rows = {p["id"]: p for p in ps}
    me = _house_summary(houses[pid], rows[pid], prices_by_turn, reveal, goods, ports, months_total)
    rivals = []
    for p in ps:
        if p["id"] == pid:
            continue
        if reveal:
            r = _house_summary(houses[p["id"]], p, prices_by_turn, True, goods, ports, months_total)
            for k in ("trades", "markets", "legs", "heat_port_month", "rep"):
                r.pop(k, None)
            rivals.append(r)
        else:
            rivals.append(_public(houses[p["id"]], p))
    standing = sorted([me] + rivals, key=lambda r: -r["kpis"]["worth"])
    meta = meta or _meta(gid)
    turns = [e.get("turn", 0) for e in events if e.get("cat") == "snapshot"]
    return {"game": {"id": gid, "years": meta.get("years"), "started": meta.get("started"),
                     "first": _date(min(turns)) if turns else "", "last": _date(max(turns)) if turns else "",
                     "turn": max(turns) if turns else 0, "ended": ended, "running": bool(running and not ended),
                     "reveal": reveal, "players": len(ps)},
            "me": me, "rivals": rivals,
            "place": 1 + [r["id"] for r in standing].index(pid)}


# --------------------------------------------------------------- career --
def career(name, running_gid=None, running_pid=None):
    """Every recorded game in which a player of this name sat. The running game
    counts with fair-play rules and only for the player holding that seat."""
    want = (name or "").strip().lower()
    if not want:
        return None
    games, cargo, ports, records = [], {}, {}, {}
    heat = {}
    totals = {"games": 0, "finished": 0, "wins": 0, "months": 0, "trades": 0, "sells": 0, "realised": 0,
              "voyages": 0, "battles": 0, "won": 0, "wrecks": 0, "booty": 0, "losses": 0, "margin_paid": 0, "impact": 0,
              "seizures": 0, "storms": 0, "ships_lost": 0, "podiums": 0}
    score_sum = score_n = 0
    for m in journal.games():
        gid = m.get("id")
        pid = find_pid(gid, name)
        if not pid:
            continue
        running = gid == running_gid
        if running and pid != running_pid:
            continue
        v = voyage(gid, pid, running=running, meta=m)
        if not v or not v["me"]["months"]:
            continue
        me, k = v["me"], v["me"]["kpis"]
        if k["months"] < 1:
            continue
        g = {"id": gid, "first": v["game"]["first"], "last": v["game"]["last"], "years": v["game"]["years"],
             "ended": v["game"]["ended"], "running": v["game"]["running"], "players": v["game"]["players"],
             "place": v["place"], "worth": k["worth"], "peak": k["peak"], "realised": k["realised"],
             "months": k["months"], "rank": k["rank"], "trades": k["trades"], "battles": k["battles"],
             "wrecks": k["wrecks"], "started": v["game"]["started"], "firm": me["firm"],
             "curve": [mm["worth"] for mm in me["months"]], "score": k["score"]}
        games.append(g)
        totals["games"] += 1
        if v["game"]["ended"]:
            totals["finished"] += 1
            if v["place"] == 1:
                totals["wins"] += 1
            if v["place"] <= 3 and v["game"]["players"] > 1:
                totals["podiums"] += 1
        for key in ("months", "trades", "sells", "realised", "voyages", "battles", "won", "wrecks", "booty",
                    "losses", "margin_paid", "impact"):
            totals[key] += k.get(key) or 0
        for key in ("seizures", "storms", "ships_lost"):
            totals[key] += me["perils"].get(key, 0)
        if k["score"] is not None:
            score_sum += k["score"] * k["trades"]
            score_n += k["trades"]
        for c in me["cargo"]:
            t = cargo.setdefault(c["good"], {"good": c["good"], "profit": 0, "sold_qty": 0, "bought_qty": 0,
                                             "trades": 0, "lost_value": 0})
            for key in ("profit", "sold_qty", "bought_qty", "trades", "lost_value"):
                t[key] += c[key]
        for p in me["ports"]:
            t = ports.setdefault(p["port"], {"port": p["port"], "visits": 0, "profit": 0, "sales": 0, "buys": 0})
            for key in ("visits", "profit", "sales", "buys"):
                t[key] += p[key]
        for port, row in me["heat_port_good"].items():
            for good, val in row.items():
                heat.setdefault(port, {})
                heat[port][good] = heat[port].get(good, 0) + val

        def rec(key, value, detail, better=max):
            if value is None:
                return
            cur = records.get(key)
            if cur is None or better(value, cur["value"]) == value and value != cur["value"]:
                records[key] = dict(detail, value=value, game=gid, firm=me["firm"], date=detail.get("date", g["last"]))
        rec("best_finish", k["worth"], {"date": g["last"]})
        rec("peak_worth", k["peak"], {"date": k["peak_date"]})
        if me["best"]:
            b = me["best"][0]
            rec("best_sale", b.get("profit", 0), {"date": b["date"], "good": b["good"], "port": b["port"],
                                                  "qty": b["qty"]})
        if me["worst"]:
            w = me["worst"][0]
            rec("worst_sale", w.get("profit", 0), {"date": w["date"], "good": w["good"], "port": w["port"],
                                                   "qty": w["qty"]}, better=min)
        if me["battles"]:
            bb = max(me["battles"], key=lambda b: b["booty"])
            rec("biggest_booty", bb["booty"], {"date": bb["date"], "count": bb["count"]})
            big = max(me["battles"], key=lambda b: b["count"])
            rec("biggest_fight", big["count"], {"date": big["date"], "result": big["result"]})
        rec("most_won", k["won"], {})
        rec("best_score", k["score"], {})
        for ru in me["rankups"]:
            if not ru.get("up"):
                continue
            r = records.get("rank_" + ru["rank"])
            months_in = ru["turn"] - (me["months"][0]["turn"] if me["months"] else 0)
            if r is None or months_in < r["value"]:
                records["rank_" + ru["rank"]] = {"value": months_in, "game": gid, "firm": me["firm"],
                                                 "date": ru["date"], "rank": ru["rank"]}
    if not games:
        return {"name": name, "games": [], "totals": totals, "cargo": [], "ports": [], "records": {}, "heat": {}}
    games.sort(key=lambda g: g.get("started") or 0, reverse=True)
    totals["score"] = int(round(score_sum / score_n)) if score_n else None
    totals["win_rate"] = round(totals["wins"] / totals["finished"], 3) if totals["finished"] else None
    totals["best"] = max(g["worth"] for g in games)
    totals["average"] = int(round(sum(g["worth"] for g in games) / len(games)))
    for c in cargo.values():
        c["profit"] = int(round(c["profit"]))
        c["lost_value"] = int(round(c["lost_value"]))
    for p in ports.values():
        p["profit"] = int(round(p["profit"]))
    heat = {p: {g: int(round(v)) for g, v in row.items()} for p, row in heat.items()}
    return {"name": name, "games": games, "totals": totals,
            "cargo": sorted(cargo.values(), key=lambda c: -c["profit"]),
            "ports": sorted(ports.values(), key=lambda p: -p["profit"]),
            "records": records, "heat": heat}


def players_seen():
    """Every player name in the records, for the 'whose stats?' picker."""
    names = {}
    for m in journal.games():
        for p in m.get("players") or ():
            n = (p.get("name") or "").strip()
            if n:
                names.setdefault(n.lower(), n)
    return sorted(names.values(), key=str.lower)
