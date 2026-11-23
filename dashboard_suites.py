"""The Command Center's suites (Dashboard plan, Phase 2): what the tabs of /dashboard show beyond the public race.

dashboard_feed.py calls this module while it holds the game, so every section below is built from the same
moment of the game as the rest of the feed. Nothing here changes the game: no dice, no actions, no writes
(the private sections are cut from a copy; see private()).

Two kinds of section:

  weather(game)            public. Each sea's forecast for the month and the harbours on it. Anyone at the table may
                           see the weather glass, so this goes out at every visibility level.
  weather_history(...)     public. The storms that have landed and how often each sea came as forecast.
  private(game, pid)       one Captain's own position: atlas, routes, trade, fleet, treasury, career. Built only
                           for an open solo game (dashboard_feed decides). With rivals at the table it is never
                           called, so nothing private can be left in the response by mistake.

Every figure is the game's own. Sections are cut from Game.view(pid), the same view the Player screen draws, or
from the engine methods that view calls (tax_rate_for, band_here, bank_interest, warehouse_rents, fleet_ledger,
yearly_upkeep, collectors, ...). The browser formats these numbers; it never works one out.

One calculation is repeated here because the engine does it inline while a voyage sails: the chance of a storm,
of pirates and of the pirate queen on each route (routes()). tests/dashboard_suites_test.py sails real voyages
and checks these figures against the odds the game's own dice recorded.

Field notes for each section are in design/dashboard-feed-schemas.md.
"""
import copy

import engine
import storm

STORM_RISK_CAP = 1.4        # engine.Game._voyage_step: a storm's distance factor is capped here (pirates use it uncapped)
FIGHTS_KEEP = 12            # the newest sea fights sent with the fleet
OPPORTUNITIES = 8


def _int(x):
    return int(round(float(x or 0)))


# ------------------------------------------------------------------ weather (public) --
def weather(game):
    """{seas: {region: {level, harbours}}, forecast_accuracy, storm_chance}. harbours are the ports on that sea. level is this month's FORECAST (0-3);
    the sea itself is settled when the month sails and matches the forecast forecast_accuracy of the time.
    storm_chance is the rules' base chance at each level, with the difficulty already applied."""
    s, w = game.s, engine.R["weather"]
    seas = {r: {"level": int((s.get("weather") or {}).get(r, 0)),
                "harbours": [k for k, port in engine.PORTS.items() if port.get("region") == r]}
            for r in engine.REGIONS}
    return {"seas": seas, "forecast_accuracy": float(w["forecast_accuracy"]),
            "storm_chance": [round(float(c) * engine.MULT["storms"], 5) for c in w["storm_chance"]]}


HISTORY_KEEP = 24           # the newest storms listed in the weather history
_HIST = {"key": None, "val": None}


def weather_history(game, events, lvl):
    """What the weather has done this game, from the journal: every storm that landed (newest first, the newest
    HISTORY_KEEP of them), the totals, and how often each sea came as it was forecast.

    A storm, a fleet blown off course and a shipwreck are public news (they run on the telegraph tape), and so is
    how much hull a fleet lost. The cargo and guns a storm took are one house's own loss and are sent only at
    the open level. `events` is the game's recorded journal; None before a game has one."""
    s = game.s
    events = events or []
    key = (s.get("game_id"), len(events), lvl, tuple(s["order"]))
    if _HIST["key"] == key:
        return _HIST["val"]
    players, storms, by = s["players"], [], {}
    totals = {"voyages": 0, "storms": 0, "typhoons": 0, "offcourse": 0, "wrecks": 0}
    seas = {r: {"months": 0, "held": 0} for r in engine.REGIONS}
    for e in events:
        kind, cat = e.get("type"), e.get("cat")
        if cat == "weather" and kind == "weather" and e.get("region") in seas:
            seas[e["region"]]["months"] += 1
            seas[e["region"]]["held"] += 1 if e.get("forecast") == e.get("actual") else 0
            continue
        if cat != "voyage" or e.get("pid") not in players:
            continue
        if kind == "sailed":
            totals["voyages"] += 1
        elif kind == "storm_damage":
            hits = e.get("hits") or []
            typhoon = (e.get("parts") or {}).get("sea") == 3 or "typhoon damage" in str(e.get("msg") or "")
            row = {"turn": e.get("turn"), "date": engine.date_label(e.get("turn") or 0), "pid": e["pid"],
                   "band": e.get("band"), "typhoon": bool(typhoon), "ships": len(hits),
                   "damage": sum(int(h.get("damage") or 0) for h in hits),
                   "worst": min((int(h.get("hull") or 0) for h in hits), default=None), "offcourse": None}
            if lvl == "open":
                row["cargo"] = sum(int(n) for n in (e.get("cargo") or {}).values())
                row["guns"] = int(e.get("guns") or 0) + int(e.get("cannons") or 0)
            storms.append(row)
            by[(e.get("turn"), e["pid"])] = row
            totals["storms"] += 1
            totals["typhoons"] += 1 if typhoon else 0
        elif kind == "offcourse":
            totals["offcourse"] += 1
            row = by.get((e.get("turn"), e["pid"]))
            if row is not None:
                row["offcourse"] = e.get("dest")
        elif kind == "shipwreck":
            totals["wrecks"] += 1
    val = {"storms": storms[::-1][:HISTORY_KEEP], "totals": totals, "seas": seas}
    _HIST["key"], _HIST["val"] = key, val
    return val


# ------------------------------------------------------------------ routes (private) --
def routes(game, p):
    """What the rules say about sailing from where the fleet is to every other port this month, on the forecast.

    Each route: distance, the distance factor ("risk"), the forecast used (the worse of the two seas), and the
    chance of a storm, of a pirate attack and of being found by the pirate queen. These are chances on the
    FORECAST: if the sea turns out different, the storm chance is the one for the sea that came. A fleet a storm
    has hit is then found less often (rules.storm.after_attack), which is not in the pirate figures here.
    Nothing here says a route is safe; it says what the odds are and what went into them."""
    R, s = engine.R, game.s
    w, pi, ly, bt = R["weather"], R["pirates"], R["liyuen"], R["battle"]
    here, seas = p["port"], s.get("weather") or {}
    matched = bool(bt.get("match"))
    allure = game._allure(p) if matched else 1.0
    pull = game.lord_pull(p) if matched else 1.0
    deter = game.flag_deter(p)
    protect = max(0, int(p.get("protect", 0) or 0))
    rows = []
    for dest in engine.PORTS:
        if dest == here or here not in engine.PORTS:
            continue
        dist = engine.distance(here, dest)
        risk = max(w["risk_min"], min(w["risk_max"], dist / float(w["risk_div"])))
        level = max(int(seas.get(engine.PORTS[here]["region"], 0)), int(seas.get(engine.PORTS[dest]["region"], 0)))
        storm_p = w["storm_chance"][level] * min(risk, STORM_RISK_CAP) * engine.MULT["storms"]
        pirates = pi["chance"] * risk * engine.MULT["pirates"] * allure * deter
        lord = 0.0 if protect > 0 else ly["chance"] * risk * engine.MULT["pirates"] * deter * pull
        rows.append({"dest": dest, "distance": _int(dist), "risk": round(risk, 4), "level": level,
                     "storm": round(min(1.0, storm_p), 5), "pirates": round(min(1.0, pirates), 5),
                     "lord": round(min(1.0, lord), 5), "banned": sorted(game.banned(dest))})
    basis = p.get("basis") or {}
    return {"from": here, "at_sea": s["phase"] == "sea", "dest": p.get("dest") or None, "routes": rows,
            "inputs": {"forecast_accuracy": float(w["forecast_accuracy"]), "storm_risk_cap": STORM_RISK_CAP,
                       "risk_min": w["risk_min"], "risk_max": w["risk_max"],
                       "allure": round(allure, 4), "flag_deter": round(deter, 4), "lord_pull": round(pull, 4),
                       "protect": protect, "protect_save": float(ly["protect_save"]),
                       "offcourse": float(w.get("offcourse", 0)),
                       "hull": round(storm.fleet_hull(p), 4),
                       # what the cargo aboard cost: what a storm or a fight puts at stake
                       "cargo_cost": _int(sum(q * float(basis.get(g, 0)) for g, q in (p.get("cargo") or {}).items()))}}


# ------------------------------------------------------------------ atlas (private) --
def atlas(game, p, me):
    """One row for every port: services, the house's standing and what it does, the tax the house would pay,
    who holds the port's shares, the house's warehouse there, commissions that end there, and bans."""
    R, s = engine.R, game.s
    e = R["estates"]
    total = int(e.get("shares_per_port", 10) or 10)
    home = engine.home_of(p)
    rents = (me.get("wh_rent") or {}).get("by_port") or {}
    away = me.get("wh_away") or {}
    active = (me.get("commissions") or {}).get("active") or []
    ports = {}
    for k, port in engine.PORTS.items():
        book = game._share_book(k)
        pat = game.patron_of(k)
        effects = game.band_effects(p, k)
        store = None
        if k == home:
            store = {"goods": dict(me.get("wh_home") or {}), "cap": int(R["fleet"].get("warehouse_cap", 10000)), "home": True}
        elif k in away:
            store = {"goods": dict(away[k]["goods"]), "cap": int(away[k]["cap"]), "home": False}
        if store:
            store["used"] = sum(store["goods"].values())
            store["rent"] = int((rents.get(k) or {}).get("rent", 0))
            store["empty"] = bool((rents.get(k) or {}).get("empty", store["used"] <= 0))
        ports[k] = {
            "here": k == p["port"], "home": k == home,
            # what this house can use there (its home port keeps a bank and a warehouse for it)
            "services": {x: bool(engine.port_has(p, k, x)) for x in ("bank", "lender", "warehouse", "shipyard")},
            "rep": _int(p["rep"].get(k, 50)), "band": game.band_here(p, k),
            "effects": {x: effects[x] for x in ("audit", "margin", "yard", "match", "tax_cut", "avoid")},
            "tax": {"base": round(game.tax_rate(k), 6), "mine": round(game.tax_rate_for(p, k), 6),
                    "home_free": game.home_free(p, k), "share_cut": round(game.share_cut(p, k), 4)},
            "shares": {"mine": game.shares_held(p, k), "total": total, "left": total - sum(int(v) for v in book.values()),
                       "patron": s["players"][pat]["firm"] if pat else None, "patron_me": pat == p["id"]},
            "warehouse": store,
            "commissions": [c["id"] for c in active if c.get("port") == k],
            "crackdown": k in s["crackdown"], "banned": sorted(game.banned(k)),
        }
    sh = me.get("shares") or {}
    return {"ports": ports, "standing_on": game.standing_on(), "tax_holiday": game.tax_holiday(p),
            "shares": {"earned": game.shares_earned(p), "placed": game.shares_total(p), "free": game.shares_free(p),
                       "cap": game.share_cap(), "value": int(sh.get("value", 0) or 0)}}


# ------------------------------------------------------------------ trade (private) --
def opportunities(game):
    """The widest gaps between two ports' posted prices, one per cargo, legal at both ends. A gap is not a
    profit: it leaves out the dealers' margin, the tax, the price moving as the cargo sells, and the voyage."""
    prices = game.s["prices"]
    rows = []
    for g in engine.GOODS:
        legal = [(float(prices[k][g]), k) for k in engine.PORTS
                 if g in (prices.get(k) or {}) and engine.sold_here(k, g) and g not in game.banned(k)]
        if len(legal) < 2:
            continue
        (low, buy), (high, sell) = min(legal), max(legal)
        if buy == sell or low <= 0 or high <= low:
            continue
        rows.append({"good": g, "buy": buy, "buy_price": round(low, 2), "sell": sell, "sell_price": round(high, 2),
                     "gap": round(high - low, 2), "pct": round(high / low - 1, 4)})
    rows.sort(key=lambda r: (-r["pct"], r["good"]))
    return rows[:OPPORTUNITIES]


def trade(game, p, me):
    """What the house holds and knows: the hold, what each cargo cost, warehouse stock by cargo, remembered and
    tipped prices, the dealers' purse where the fleet is, and the widest posted price gaps."""
    return {"port": p["port"], "cargo": dict(me["cargo"]), "capacity": me["capacity"], "used": me["used"],
            "basis": dict(me["basis"]), "stored": dict(me.get("stored") or {}), "rot": me.get("rot"),
            "spread": me["spread"], "purse": me.get("purse"),
            "known": me.get("known") or {}, "tips": me.get("tips") or {}, "hot_tips": me.get("hot_tips") or [],
            "lot": me.get("lot"), "opportunities": opportunities(game)}


# ------------------------------------------------------------------ fleet (private) --
def fleet(game, p, me):
    """Every ship as the Player screen lists her, the ships laid up at home, and what the fleet costs a month."""
    return {"ships": me["ships"], "laid_up": me["laid_up"], "capacity": me["capacity"], "used": me["used"],
            "guns": game.guns(p), "cannons": game.cannons(p), "hull": round(storm.fleet_hull(p), 4),
            "classes": me.get("classes"), "ledger": me.get("fleet_ledger"),
            "protect": me["protect"], "protect_cost": me["protect_cost"], "wrecks": int(p.get("wrecks", 0) or 0),
            "fights": list(me.get("fights") or [])[-FIGHTS_KEEP:]}


# ------------------------------------------------------------------ treasury (private) --
def bank_slices(game, p):
    """The deposit cut into the bank's interest slices: [{to, rate, amount, interest}]. `rate` already holds the
    great house's bonus. The interests add up to engine.Game.bank_interest(p, extra=house_bank_bonus(p))."""
    extra = game.house_bank_bonus(p)
    left, low, out = max(0.0, float(p["bank"])), 0.0, []
    for top, rate in game.bank_tiers():
        part = left if top is None else min(left, max(0.0, top - low))
        out.append({"to": None if top is None else _int(top), "rate": round(max(0.0, rate + extra), 6),
                    "amount": _int(part), "interest": part * max(0.0, rate + extra)})
        left -= part
        if top is not None:
            low = top
    return out


def worth_parts(game, p):
    """Net worth split the way engine.Game.worth() adds it up. The parts sum to worth (debt is negative)."""
    paid = p.get("share_paid") if isinstance(p.get("share_paid"), dict) else {}
    return {"cash": float(p.get("cash", 0)), "bank": float(p.get("bank", 0)), "debt": -float(p.get("debt", 0)),
            "fleet": sum(engine.ship_value(sh) for sh in p.get("ships") or ()),
            "laid_up": sum(engine.ship_value(sh) for sh in p.get("laid_up") or ()),
            "shares": float(sum(float(v) for v in paid.values())),
            "estate": float(p.get("estate_paid", 0) or 0),
            "cargo": game.goods_value(p)}


def _statement(st):
    """A month's statement without its log lines (the Wire has the story; this is the money)."""
    if not isinstance(st, dict):
        return None
    return {k: v for k, v in st.items() if k != "log"}


def treasury(game, p, me):
    """The balance sheet, the books, the bank's slices and the month's interest, debt and the debt clock, the
    great house, and every cost that comes round without the Captain doing anything.

    next_month holds only what the rules already fix: the wages and rents due at this month's end, the interest
    the bank will pay on today's deposit and the moneylender will add to today's debt, and December's bills if
    this month is December. Trade, weather, fights and events are not in it."""
    s = game.s
    parts = worth_parts(game, p)
    slices = bank_slices(game, p)
    interest = sum(x["interest"] for x in slices)
    for x in slices:
        x["interest"] = _int(x["interest"])
    rate = engine.loan_rate()
    debt = float(p["debt"])
    cap = game.debt_cap(p)
    grown = debt * (1 + rate)
    loan_interest = max(0.0, (grown if cap is None or grown <= cap else max(debt, cap)) - debt)
    ledger = me.get("fleet_ledger") or {}
    rents = game.warehouse_rents(p)
    yearly = [{"line": line, "port": port, "amount": int(amount)} for line, port, amount in game.yearly_upkeep(p)]
    december_in = 11 - s["turn"] % 12
    wages, rent = int(ledger.get("bill", 0) or 0), sum(int(r["rent"]) for r in rents)
    due_yearly = sum(y["amount"] for y in yearly) if december_in == 0 else 0
    bk = me.get("books") or {}
    return {
        "worth": int(game.worth(p)), "parts": {k: _int(v) for k, v in parts.items()},
        "books": {"last": _statement(bk.get("last")), "cur": bk.get("cur") or {}, "year": bk.get("year") or {},
                  "game": bk.get("game") or {}, "year_no": bk.get("year_no")},
        "bank": {"balance": _int(p["bank"]), "bonus": round(game.house_bank_bonus(p), 6), "slices": slices,
                 "interest": _int(interest), "here": bool(me.get("bank_here"))},
        "debt": {"debt": me["debt"], "rate": rate, "interest": _int(loan_interest), "loan_room": me["loan_room"],
                 "lender_here": bool(me.get("lender_here")), "collectors": me.get("collectors"),
                 "bankrupt": me.get("bankrupt"), "cap": me.get("debt_cap") or None},
        "estate": me.get("estate"),
        "costs": {"wages": wages, "classes": ledger.get("classes") or {}, "laid": ledger.get("laid") or {},
                  "rents": [dict(r) for r in rents], "rent": rent,
                  "yearly": yearly, "december_in": december_in,
                  "protect": {"months": me["protect"], "cost": me["protect_cost"]}},
        "next_month": {"costs": wages + rent + due_yearly, "bank_interest": _int(interest),
                       "loan_interest": _int(loan_interest),
                       "net": _int(interest) - _int(loan_interest) - wages - rent - due_yearly},
    }


# ------------------------------------------------------------------ career (private) --
def career(game, p, me):
    """Rank and the road to the next one, fame, shares earned, the Mayor's commissions, Legends met."""
    sh = me.get("shares") or {}
    return {"rank": me["rank"], "rank_id": me["rank_id"], "next_rank": me.get("next_rank"),
            "qualified_rank": me.get("qualified_rank"), "worth": me["worth"], "fame": me.get("fame", 0),
            "home": me["home"], "captain": me.get("captain") or "",
            "shares": {"earned": game.shares_earned(p), "placed": game.shares_total(p), "free": game.shares_free(p),
                       "cap": game.share_cap(), "by_port": sh.get("mine") or {}, "patron_of": sh.get("patron_of") or []},
            "commissions": me.get("commissions"), "legends": me.get("legends") or [],
            "promotions": len(p.get("promotions") or [])}


def private(game, pid):
    """Every private section for one Captain: {atlas, routes, trade, fleet, treasury, career}.

    Built from a copy of the game taken once, here. Some of the engine's own lookups tidy the state as they read
    it (an empty share book for a port nobody has bought into, the Patron of a port worked out on first asking).
    On a copy that tidying cannot reach the game in play, and every section is cut from the same moment."""
    shadow = engine.Game(state=copy.deepcopy(game.s), seed=0)
    p = shadow.s["players"][pid]
    me = shadow.view(pid)["me"]
    return {"atlas": atlas(shadow, p, me), "routes": routes(shadow, p), "trade": trade(shadow, p, me),
            "fleet": fleet(shadow, p, me), "treasury": treasury(shadow, p, me), "career": career(shadow, p, me)}
