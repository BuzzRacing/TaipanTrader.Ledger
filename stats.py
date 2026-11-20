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
_commissions = {}
_CACHE_MAX = 64

# Actions whose silver change counts as a cost or income line in "where the silver went".
ACTION_LINES = {"buy_gun": "guns", "buy_cannon": "guns", "fill_cannons": "guns", "sell_gun": "guns_sold", "sell_cannon": "guns_sold",
                "repair": "repairs", "buy_ship": "ships_bought", "sell_ship": "ships_sold", "trade_down": "ships_sold",
                "protection": "protection", "gift": "gift", "depot": "depot"}

# Who took (or paid) each line, for "who got your silver": a cast member or port role the screen can picture.
TAKERS = {"dues": "mayor", "gift": "mayor", "customs": "officer", "loan_interest": "lender", "bank_interest": "banker",
          "repairs": "shipwright", "ships_bought": "shipwright", "guns": "shipwright", "protection": "agent",
          "parley": "pirates", "plundered": "pirates", "robbed": "thieves", "wh_robbed": "thieves",
          "seized": "officer", "depot": "warehouse"}


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
    events, colors, books = [], {}, {}
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
                        if not isinstance(p, dict):
                            continue
                        if "color" in p:
                            colors[pid] = p["color"]
                        # The engine's own account book (the Ledger tab's numbers), as of this saved month.
                        bk = p.get("books") if isinstance(p.get("books"), dict) else None
                        if bk and isinstance(bk.get("game"), dict):
                            books[pid] = {"turn": e.get("turn", 0), "n": len(events),
                                          "game": {k: round(float(v)) for k, v in bk["game"].items()},
                                          "home": p.get("home"), "captain": p.get("captain")}
                events.append(e)
    except OSError:
        return None
    game = {"events": events, "colors": colors, "size": size, "books": books, "gid": gid}
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


# The House is its id: a name is only its label. The server sets HOUSE_NAMES to a function
# (game id -> {seat id: the House's name now}) and NAMES_VERSION to one that changes with any rename,
# so records written under an old name show the new one.
HOUSE_NAMES = None
NAMES_VERSION = None


def _names_rev():
    try:
        return NAMES_VERSION() if NAMES_VERSION else None
    except Exception:
        return None


def _players(events, colors, gid=None):
    """id -> name, firm, colour slot and seat order, from joins and snapshots."""
    out, order = {}, []
    for e in events:
        if e.get("type") == "house" and e.get("pid") in out and e.get("firm"):
            out[e["pid"]]["firm"] = e["firm"]          # renamed in Options
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
    try:
        now = HOUSE_NAMES(gid) if (HOUSE_NAMES and gid) else {}
    except Exception:
        now = {}
    for pid, firm in now.items():
        if pid in out:
            out[pid]["firm"] = firm
    for i, pid in enumerate(order):
        out[pid]["seat"] = i
        out[pid]["color"] = colors.get(pid, i) % 8
    return [out[pid] for pid in order]


def _date(turn):
    return engine.date_label(turn)


def _rank_id(title):
    for r in engine.CFG.get("ranks", []):
        if r.get("title") == title:
            return r.get("id")
    return None


def _ended(events):
    return any(e.get("type") == "game_over" for e in events)


# ---------------------------------------------------------- one player --
class _House:
    """Running tally for one house while the journal is read in order."""

    def __init__(self, pid):
        self.pid = pid
        self.home = None
        self.ships_now = []
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
        self.takers = {}        # line -> port -> amount (who got the silver, and where)
        self.desk = []          # every Port Authority desk visit
        self.dues = {"paid": 0, "count": 0, "owed": 0, "slipped": 0, "slip_saved": 0, "caught": 0}
        self.tips = []          # hot tips and price tips from the Registrar and the port officers
        self.promotions = []    # commissions from the Mayor
        self.loans = {"borrowed": 0, "repaid": 0, "deposited": 0, "withdrawn": 0}

    def _c(self, good):
        return self.cargo.setdefault(good, {"good": good, "bought_qty": 0, "bought_cost": 0, "sold_qty": 0,
                                            "sold_rev": 0, "profit": 0, "trades": 0, "lost_qty": 0,
                                            "lost_value": 0, "margin_paid": 0, "impact": 0})

    def _ps(self, port):
        return self.port_stats.setdefault(port, {"port": port, "visits": 0, "buys": 0, "sales": 0, "spent": 0,
                                                 "revenue": 0, "profit": 0})

    def line(self, key, amount, port=None):
        if amount:
            self.lines[key] = self.lines.get(key, 0) + amount
            if key in TAKERS:
                row = self.takers.setdefault(key, {})
                where = port or "sea"
                row[where] = row.get(where, 0) + amount

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


def _fleet_row(f, prices):
    """Ships by type and class, guns and cannons, and how net worth splits into its parts, for one
    house in one monthly snapshot. Cargo (hold, home warehouse and depots) is valued as the engine
    values it for net worth; the fleet is what is left once silver, bank, debt and cargo are counted."""
    ships = f.get("ships") or ()
    types, roles = {}, {}
    for sh in ships:
        t = sh.get("type") or "?"
        types[t] = types.get(t, 0) + 1
        role = (engine.SHIPS.get(t) or {}).get("role") or "trader"
        roles[role] = roles.get(role, 0) + 1
    goods = {}
    for src in [f.get("cargo") or {}, f.get("wh") or {}] + [(d or {}).get("goods") or {} for d in (f.get("depots") or {}).values()]:
        for g, q in src.items():
            goods[g] = goods.get(g, 0) + q
    stored = sum((f.get("wh") or {}).values()) + sum(sum(((d or {}).get("goods") or {}).values())
                                                    for d in (f.get("depots") or {}).values())
    share = float(engine.R.get("market", {}).get("worth_cargo", 1.0))
    cargo_value = share * sum(q * engine.normal_price(g) for g, q in goods.items())
    if f.get("goods_value") is not None:            # snapshots under the dealer rule (Game 4 review) carry it
        cargo_value = float(f["goods_value"])
    fleet_value = f["worth"] - f["cash"] - f["bank"] + f["debt"] - cargo_value
    return {"types": types, "roles": roles, "cannons": sum(int(sh.get("cannons") or 0) for sh in ships),
            "hull": sum(int(sh.get("hull") or 0) for sh in ships), "stored": stored,
            "goods_value": int(round(cargo_value)), "fleet_value": int(round(max(0.0, fleet_value))),
            "protect": int(f.get("protect") or 0), "depots": len(f.get("depots") or {})}


def _walk(events, ps, extra=None):
    """Reads one game's journal once and tallies every house. extra, when given, is filled with
    what belongs to the whole game: the booms and crashes ("windfalls")."""
    houses = {p["id"]: _House(p["id"]) for p in ps}
    windfalls = [] if extra is None else extra.setdefault("windfalls", [])
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
                # Net worth is recalculated with today's rule (cargo at its normal price, 19 Nov 2026), so
                # games recorded under the old rule (Hong Kong's live price) compare fairly.
                f = dict(f, worth=int(engine.worth_of(f)))
                row = {"turn": turn, "date": e.get("date") or _date(turn), "cash": f["cash"], "bank": f["bank"],
                       "debt": f["debt"], "worth": f["worth"], "port": f["port"], "ships": len(f.get("ships") or ()),
                       "guns": f.get("guns", 0), "hold": f.get("hold", 0), "used": f.get("used", 0),
                       "rep": f.get("rep") or {}, "rank": f.get("rank", engine.rank_for(f["worth"]))}
                row.update(_fleet_row(f, e.get("prices")))
                hh.ships_now = [{k: sh.get(k) for k in ("type", "name", "hull", "guns", "cannons")} for sh in f.get("ships") or ()]
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
        if cat == "market" and typ in ("windfall", "shock") and e.get("port") and e.get("good"):
            price = e.get("price") if isinstance(e.get("price"), list) else None
            windfalls.append({"turn": turn, "date": _date(turn), "port": e["port"], "good": e["good"],
                              "sort": e.get("sort") or ("boom" if float(e.get("mult") or 1) >= 1 else "crash"),
                              "big": typ == "windfall", "mult": round(float(e.get("mult") or 1), 2),
                              "turns": int(e.get("turns") or 1), "foretold": bool(e.get("foretold")),
                              "from": round(price[0]) if price else None, "to": round(price[1]) if price else None})
            continue
        if h is None:
            continue

        if typ in ("seat_new", "seat_reclaim") and e.get("start_port"):
            h.home = e["start_port"]
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
            port = e.get("port")
            bribe = e.get("bribe") if isinstance(e.get("bribe"), dict) else {}
            outcomes = [r.get("outcome") for r in e.get("lines") or ()]
            if "tax" in e:
                h.desk.append({"turn": turn, "date": _date(turn), "port": port, "rate": e.get("rate"),
                               "value": int(e.get("value") or 0),
                               "declared": int(sum((e.get("declared") or {}).values())) if isinstance(e.get("declared"), dict)
                               else int(e.get("declared") or 0),
                               "tax": int(e.get("tax") or 0), "fine": int(e.get("fine") or 0),
                               "bribe": int(bribe.get("cost") or 0) if bribe.get("taken") else 0,
                               "bribe_refused": bool(bribe) and not bribe.get("taken"),
                               "caught": "caught" in outcomes,
                               "bought": sum(int(r.get("paid") or 0) for r in e.get("lines") or ()),
                               "sealed": outcomes.count("sealed"), "auto": typ == "customs_auto"})
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
            if "tax" in e:
                # Newer journals give the bill itself (a shortfall goes on the debt, so silver alone misses it).
                h.line("customs", -(int(e.get("tax") or 0) + int(e.get("fine") or 0)
                                    + (int(bribe.get("cost") or 0) if bribe.get("taken") else 0)), port)
            elif e.get("cash"):
                was, now = e["cash"]
                h.line("customs", now - was - bought_in, port)
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

        if cat == "orders" and typ == "sea":
            if h.battle is not None and e.get("choice"):
                ch = h.battle.setdefault("choices", {})
                ch[e["choice"]] = ch.get(e["choice"], 0) + 1
            continue
        if cat == "finance" and typ in ("loan", "bank"):
            d = e.get("debt") or (e.get("bank") if typ == "bank" else None)
            if isinstance(d, list) and len(d) == 2:
                if typ == "loan":
                    h.loans["borrowed" if d[1] > d[0] else "repaid"] += abs(d[1] - d[0])
                else:
                    h.loans["deposited" if d[1] > d[0] else "withdrawn"] += abs(d[1] - d[0])
            continue
        if cat == "finance" and typ == "dues":
            total = int(e.get("total") or 0)
            h.dues["paid"] += total
            h.dues["count"] += 1
            h.dues["owed"] += int(e.get("owed") or 0)
            h.line("dues", -total, e.get("port"))
            continue
        if cat == "finance" and typ == "slip_away":
            h.dues["slipped"] += 1
            h.dues["slip_saved"] += int(e.get("bill") or 0)
            continue
        if cat == "finance" and typ == "slip_caught":
            h.dues["caught"] += 1
            continue
        if cat == "market" and typ in ("registrar_hot", "port_hot", "registrar_tip"):
            h.tips.append({"turn": turn, "date": _date(turn), "kind": "price" if typ == "registrar_tip" else "boom",
                           "by": e.get("by") or "registrar", "at": e.get("port"), "where": e.get("where"),
                           "good": e.get("good"), "mult": e.get("mult"), "lands": e.get("lands"), "ends": e.get("ends"),
                           "price": e.get("price")})
            continue
        if cat == "players" and typ == "promotion":
            h.promotions.append({"turn": turn, "date": _date(turn), "rank": e.get("rank"), "port": e.get("port"),
                                 "rank_id": _rank_id(e.get("rank"))})
            continue
        if typ in ACTION_LINES and e.get("cash"):
            was, now = e["cash"]
            h.line(ACTION_LINES[typ], now - was, e.get("port"))
            continue

        if cat == "finance" and typ in ("upkeep", "yearly_upkeep"):
            # Running costs (Game 3 review, 19 Nov 2026): crew wages monthly, the great house and patronage yearly.
            h.line("upkeep" if typ == "upkeep" else "estate_upkeep", -float(e.get("amount") or 0))
            continue
        if typ == "interest" and cat == "finance":
            b, d = e.get("bank") or [0, 0], e.get("debt") or [0, 0]
            h.line("bank_interest", b[1] - b[0])
            h.line("loan_interest", -(d[1] - d[0]), h.home)
            continue
        if typ == "wh_robbed":
            v = h.lose(e.get("lost"), "wh_robbed", turn)
            h.perils["robbed"] += 1
            h.perils["robbed_value"] += v
            h.line("wh_robbed", -v, e.get("port"))
            h.events.append({"turn": turn, "kind": "robbed", "value": int(round(v))})
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
        if typ == "offcourse" and cat == "voyage":
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
                h.battle = {"turn": turn, "date": _date(turn), "enemy": e.get("enemy"), "fleet": e.get("fleet"), "count": e.get("count", 0),
                            "orders": e.get("orders"), "guns": e.get("guns", 0), "rounds": 0, "result": "fought",
                            "booty": 0, "plundered": 0, "damage": 0, "sunk": 0, "ships_lost": 0,
                            "lord": "war" in str(e.get("enemy") or ""), "live": bool(e.get("live")),
                            "asked": int(e.get("parley") or 0), "odds": e.get("hit")}
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
                elif typ == "spared":               # Game 4 review: a small band let go for a price tip
                    b["result"] = "spared"
                    b["sunk"] = b["count"] - int(e.get("left") or 0)
                    h.perils["spared"] = h.perils.get("spared", 0) + 1

                elif typ == "retreat":
                    v = h.lose(e.get("lost"), "overflow", turn)
                    b["result"], b["sunk"] = "retreated", b["count"] - e.get("enemy_left", b["count"])
                    b["damage"] += sum(x.get("damage", 0) for x in e.get("hits") or ())
                    b["overboard"] = int(round(v))
                    h.perils["retreated"] = h.perils.get("retreated", 0) + 1
                    h.perils["cargo_lost_value"] += v
                    h.line("cargo_lost", -v)
                elif typ == "prize":
                    goods = {g: int(q) for g, q in (e.get("goods") or {}).items() if q}
                    for g, q in goods.items():            # stolen cargo comes aboard at no cost to the house
                        units, cost = h.hold.get(g, (0, 0))
                        h.hold[g] = (units + q, cost)
                        h._c(g)["prize_qty"] = h._c(g).get("prize_qty", 0) + q
                    b["prize"], b["prize_goods"], b["tier"] = int(e.get("worth") or 0), goods, e.get("tier")
                    h.perils["prizes"] = h.perils.get("prizes", 0) + 1
                    h.perils["prize_value"] = h.perils.get("prize_value", 0) + int(e.get("worth") or 0)
                    h.perils["prize_units"] = h.perils.get("prize_units", 0) + sum(goods.values())
                elif typ == "lowball":
                    b["lowball"], b["asked"] = int(e.get("price") or 0), int(e.get("price") or b.get("asked") or 0)
                    b["full"] = int(e.get("full") or 0)
                    h.perils["lowballs"] = h.perils.get("lowballs", 0) + 1
                elif typ in ("lowball_refused", "parley_refused"):
                    b["refused"] = int(e.get("bargain") or e.get("price") or 0)
                    if typ == "lowball_refused":
                        b["asked"] = int(e.get("price") or b.get("asked") or 0)
                    h.perils["refused"] = h.perils.get("refused", 0) + 1
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


def _tips_scored(h, now):
    """Each tip with what came of it: a boom tip is cashed when the house sold that cargo in that port
    while the boom was on, missed when the boom ended without it; a price tip is taken up when the house
    bought that cargo there within three months."""
    out = []
    for tp in h.tips:
        r = dict(tp)
        if tp["kind"] == "boom" and tp.get("where") and tp.get("lands") is not None:
            lo, hi = int(tp["lands"]), int(tp.get("ends") or tp["lands"])
            sells = [t for t in h.trades if t["side"] == "sell" and t["good"] == tp["good"]
                     and t["port"] == tp["where"] and lo <= t["turn"] <= hi]
            r["qty"] = sum(t["qty"] for t in sells)
            r["profit"] = int(sum(t.get("profit", 0) for t in sells))
            r["status"] = "cashed" if sells else ("missed" if now > hi else "open")
        else:
            buys = [t for t in h.trades if t["side"] == "buy" and t["good"] == tp.get("good")
                    and t["port"] == tp.get("where") and tp["turn"] <= t["turn"] <= tp["turn"] + 3]
            r["qty"] = sum(t["qty"] for t in buys)
            r["profit"] = None
            r["status"] = "taken" if buys else ("missed" if now > tp["turn"] + 3 else "open")
        out.append(r)
    return out


def _windfalls_for(h, windfalls, reveal):
    """The booms and crashes, each with what this house made selling (or spent buying) that cargo in that
    port while it lasted. In fair play only those the house could know of: it was in that port while it
    lasted, traded there, or was tipped about it."""
    at = {m["turn"]: m["port"] for m in h.months}
    tipped = {(tp.get("where"), tp.get("good")) for tp in h.tips}
    out = []
    for w in windfalls:
        lo, hi = w["turn"], w["turn"] + max(1, w["turns"]) - 1
        mine = [t for t in h.trades if t["good"] == w["good"] and t["port"] == w["port"] and lo <= t["turn"] <= hi]
        known = reveal or mine or (w["port"], w["good"]) in tipped or any(at.get(tn) == w["port"] for tn in range(lo, hi + 1))
        if not known:
            continue
        r = dict(w)
        r["end"] = hi
        r["sold"] = sum(t["qty"] for t in mine if t["side"] == "sell")
        r["bought"] = sum(t["qty"] for t in mine if t["side"] == "buy")
        r["profit"] = int(sum(t.get("profit", 0) for t in mine if t["side"] == "sell"))
        r["spent"] = int(sum(t["total"] for t in mine if t["side"] == "buy"))
        out.append(r)
    return out


def _desk_summary(h):
    d = {"visits": len(h.desk), "value": 0, "declared": 0, "tax": 0, "fine": 0, "bribe": 0, "caught": 0,
         "bought": 0, "sealed": 0, "bribe_refused": 0, "ports": {}}
    for v in h.desk:
        for k in ("value", "declared", "tax", "fine", "bribe", "bought", "sealed"):
            d[k] += v[k]
        d["caught"] += 1 if v["caught"] else 0
        d["bribe_refused"] += 1 if v["bribe_refused"] else 0
        p = d["ports"].setdefault(v["port"], {"port": v["port"], "visits": 0, "tax": 0, "fine": 0, "caught": 0,
                                              "value": 0, "declared": 0, "bought": 0})
        p["visits"] += 1
        for k in ("tax", "fine", "value", "declared", "bought"):
            p[k] += v[k]
        p["caught"] += 1 if v["caught"] else 0
    d["ports"] = sorted(d["ports"].values(), key=lambda p: -(p["tax"] + p["fine"]))
    d["honesty"] = round(d["declared"] / d["value"], 3) if d["value"] else None
    d["recent"] = h.desk[-12:]
    return d


def _takers(h):
    """Who got the silver (or paid it): one row per cast member or port role, with the lines and ports."""
    out = {}
    for key, by in h.takers.items():
        amount = sum(by.values())
        if not round(amount):
            continue
        who = TAKERS.get(key, key)
        r = out.setdefault(who, {"who": who, "amount": 0.0, "lines": {}, "ports": {}})
        r["amount"] += amount
        r["lines"][key] = int(round(amount))
        for p, v in by.items():
            r["ports"][p] = r["ports"].get(p, 0) + v
    rows = []
    for r in out.values():
        r["amount"] = int(round(r["amount"]))
        r["ports"] = {p: int(round(v)) for p, v in sorted(r["ports"].items(), key=lambda x: abs(x[1]), reverse=True)
                      if round(v)}
        rows.append(r)
    return sorted(rows, key=lambda r: -abs(r["amount"]))


def _house_summary(h, ps_row, prices_by_turn, reveal, goods, ports, months_total, windfalls=(), books=None):
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
    h.perils["enemy_sunk"] = sum(int(b.get("sunk") or 0) for b in h.battles)
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
        "enemy_sunk": sum(int(b.get("sunk") or 0) for b in h.battles),
        "prizes": perils.get("prizes", 0), "prize_value": perils.get("prize_value", 0),
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
        "takers": _takers(h), "desk": _desk_summary(h), "dues": dict(h.dues), "loans": dict(h.loans),
        "tips": _tips_scored(h, last["turn"] if last else 0), "windfalls": _windfalls_for(h, windfalls, reveal),
        "promotions": h.promotions, "fleet": h.ships_now, "home": h.home,
        "books": books,
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
    for p in _players(game["events"], game["colors"], gid):
        if (p.get("name") or "").strip().lower() == want:
            return p["id"]
    return None


def promotion_record(gid, pid, award):
    """Only this captain's history, cut at the award event rather than the current month."""
    key = (gid, pid, award["id"], award["rank_id"])
    with _lock:
        if key in _commissions:
            return _commissions[key]
    game = _read(gid)
    if not game:
        return None
    events = []
    for event in game["events"]:
        events.append(event)
        if event.get("type") == "promotion" and event.get("pid") == pid and \
                (event.get("promotion_id") == award["id"] if "promotion_id" in event
                 else event.get("rank") == award["title"]):
            break
    else:
        return None
    players = _players(events, game["colors"], gid)
    if pid not in {p["id"] for p in players}:
        return None
    houses, _worth, _prices = _walk(events, players)
    house = houses[pid]
    sales = [t for t in house.trades if t["side"] == "sell" and t.get("profit", 0) > 0]
    best = max(sales, key=lambda t: t["profit"], default=None)
    record = {"voyages": sum(bool(leg.get("arrived")) for leg in house.legs),
              "ports": sum(bool(port["visits"]) for port in house.port_stats.values()),
              "profit": int(round(sum(c["profit"] for c in house.cargo.values()))),
              "won": house.perils["won"],
              "best": {k: best[k] for k in ("good", "port", "qty", "profit", "date")} if best else None}
    with _lock:
        if len(_commissions) >= _CACHE_MAX * 4:
            _commissions.clear()
        _commissions[key] = record
    return record


def voyage(gid, pid, running=False, meta=None):
    """One game for one house. running=True means the game is still being played
    and has not ended, so fair-play rules apply."""
    game = _read(gid)
    if not game:
        return None
    key = (gid, game["size"], pid, bool(running), id(engine.CFG), _names_rev())      # settings change -> work it out again
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
    ps = _players(events, game["colors"], gid)
    if pid not in {p["id"] for p in ps}:
        return None
    ended = _ended(events)
    reveal = ended or not running
    extra = {}
    houses, worth, prices_by_turn = _walk(events, ps, extra)
    goods, ports = list(engine.GOODS), list(engine.PORTS)
    months_total = max((len(h.months) for h in houses.values()), default=0)
    rows = {p["id"]: p for p in ps}
    bk = (game.get("books") or {}).get(pid)
    books = {"lines": bk["game"], "turn": bk["turn"], "date": _date(bk["turn"])} if bk else None
    if bk and not houses[pid].home:
        houses[pid].home = bk.get("home")
    me = _house_summary(houses[pid], rows[pid], prices_by_turn, reveal, goods, ports, months_total,
                        extra.get("windfalls", ()), books)
    rivals = []
    for p in ps:
        if p["id"] == pid:
            continue
        if reveal:
            r = _house_summary(houses[p["id"]], p, prices_by_turn, True, goods, ports, months_total)
            for k in ("trades", "markets", "legs", "heat_port_month", "rep", "tips", "windfalls", "desk", "takers",
                      "books", "fleet"):
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
            "place": _final_place(events, pid) or 1 + [r["id"] for r in standing].index(pid)}


def _final_place(events, pid):
    """The place recorded when the books closed. Months sailed in free play afterwards never change it."""
    over = next((e for e in events if e.get("type") == "game_over"), None)
    ids = [q.get("id") for q in (over or {}).get("standings") or []]
    return 1 + ids.index(pid) if pid in ids else None


# --------------------------------------------------------------- career --
def career(name, running_gid=None, running_pid=None, links=None):
    """Every recorded game in which a player of this name sat. The running game
    counts with fair-play rules and only for the player holding that seat.
    links ({game id: seat id}, from a saved Captain) picks the games by Captain instead of by name."""
    want = (name or "").strip().lower()
    if not want and links is None:
        return None
    games, cargo, ports, records, promos, takers = [], {}, {}, {}, [], {}
    heat = {}
    totals = {"games": 0, "finished": 0, "wins": 0, "months": 0, "trades": 0, "sells": 0, "realised": 0,
              "voyages": 0, "battles": 0, "won": 0, "wrecks": 0, "booty": 0, "losses": 0, "margin_paid": 0, "impact": 0,
              "seizures": 0, "storms": 0, "ships_lost": 0, "podiums": 0, "prizes": 0, "prize_value": 0,
              "enemy_sunk": 0, "dues": 0, "pa_paid": 0, "desk_visits": 0, "caught": 0, "tips": 0, "tips_cashed": 0,
              "tip_profit": 0, "promotions": 0}
    score_sum = score_n = 0
    for m in journal.games():
        gid = m.get("id")
        pid = links.get(gid) if links is not None else find_pid(gid, name)
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
        promos.extend(dict(pr, game=gid, firm=me["firm"]) for pr in me["promotions"])
        for r in me["takers"]:
            t = takers.setdefault(r["who"], {"who": r["who"], "amount": 0, "lines": {}, "ports": {}})
            t["amount"] += r["amount"]
            for key, amt in r["lines"].items():
                t["lines"][key] = t["lines"].get(key, 0) + amt
            for port, amt in r["ports"].items():
                t["ports"][port] = t["ports"].get(port, 0) + amt
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
        totals["prizes"] += k.get("prizes") or 0
        totals["prize_value"] += k.get("prize_value") or 0
        totals["enemy_sunk"] += k.get("enemy_sunk") or 0
        totals["dues"] += me["dues"]["paid"]
        totals["pa_paid"] += me["desk"]["tax"] + me["desk"]["fine"] + me["desk"]["bribe"]
        totals["desk_visits"] += me["desk"]["visits"]
        totals["caught"] += me["desk"]["caught"]
        totals["tips"] += len(me["tips"])
        cashed = [tp for tp in me["tips"] if tp["status"] == "cashed"]
        totals["tips_cashed"] += len(cashed)
        totals["tip_profit"] += sum(tp["profit"] or 0 for tp in cashed)
        totals["promotions"] += len(me["promotions"])
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
        prized = [b for b in me["battles"] if b.get("prize")]
        if prized:
            bp = max(prized, key=lambda b: b["prize"])
            rec("biggest_prize", bp["prize"], {"date": bp["date"], "tier": bp.get("tier"),
                                               "units": sum((bp.get("prize_goods") or {}).values())})
        booms = [w for w in me["windfalls"] if w["sort"] == "boom" and w["profit"] > 0]
        if booms:
            bw = max(booms, key=lambda w: w["profit"])
            rec("best_boom", bw["profit"], {"date": bw["date"], "good": bw["good"], "port": bw["port"]})
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
        return {"name": name, "games": [], "totals": totals, "cargo": [], "ports": [], "records": {}, "heat": {},
                "promotions": [], "takers": []}
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
            "records": records, "heat": heat, "promotions": promos,
            "takers": sorted(takers.values(), key=lambda r: -abs(r["amount"]))}


def players_seen():
    """Every player name in the records, for the 'whose stats?' picker."""
    names = {}
    for m in journal.games():
        for p in m.get("players") or ():
            n = (p.get("name") or "").strip()
            if n:
                names.setdefault(n.lower(), n)
    return sorted(names.values(), key=str.lower)


# ------------------------------------------------- market pulse backfill --
def backfill_market(game):
    """Once per saved game: fill the market keepers' price book (s["price_hist"]) and each house's best
    sale per port (p["best_sale"]) from the journal, for games played before the engine kept them.
    Safe to call on any game; does nothing once done or when there is no journal."""
    s = game.s
    if s.get("market_backfilled") or s.get("phase") == "lobby":
        return False
    gid = s.get("game_id")
    data = _read(gid) if gid else None
    if not data:
        s["market_backfilled"] = True
        return False
    events = data["events"]
    first = {}
    for e in events:
        if e.get("cat") == "snapshot" and e.get("prices") and e.get("phase") != "lobby":
            first.setdefault(e.get("turn", 0), e["prices"])
    have = {r.get("turn") for r in s.get("price_hist", [])}
    rows = [{"turn": t, "prices": first[t]} for t in sorted(first) if t not in have and t <= s.get("turn", 0)]
    if rows:
        merged = sorted(rows + list(s.get("price_hist", [])), key=lambda r: r["turn"])
        s["price_hist"] = merged[-(engine.HIST_MONTHS + 1):]
    ps = _players(events, data["colors"], gid)
    houses = _walk(events, ps)[0] if ps else {}
    for pid, p in s.get("players", {}).items():
        h = houses.get(pid)
        if h is None:
            continue
        best = p.setdefault("best_sale", {})
        for t in h.trades:
            if t.get("side") != "sell" or not t.get("port") or (t.get("profit") or 0) <= 0:
                continue
            old = best.get(t["port"])
            if not old or old.get("profit", 0) < t["profit"]:
                best[t["port"]] = {"profit": int(t["profit"]), "good": t["good"], "qty": int(t["qty"]),
                                   "turn": int(t["turn"])}
    s["market_backfilled"] = True
    return True
