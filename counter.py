"""Under the Counter (20 Nov 2026): the port's tax lady sells a tip, for a price.

Anthony's request: a new tab on the left rail, with the port's tax lady as its face. Click it and she
offers what she knows, but only once you have paid. Her price is a share of what the tip is worth to
you, and the share rises with your rank (the richer the Captain, the more she charges).

She sees every manifest that crosses her desk, so her figures are better than the Price Book: this
month's real prices in every port, pulled toward where they should be next month (one voyage is one
month), the dealer's cut at your standing there, the dealers' purse, how far a big lot pushes the
price, and the Port Authority's tax where you land. She does not know the dice: a storm, a pirate or
a sudden glut can still spoil it. Her figure of the tip's worth already allows for the pirate risk on
the way (rules.counter.risk_loss of the profit, times the chance of a fight).

Her tips, so far (more will be added to this counter later):
  run   "A full hold": the best cargo to buy here with your silver and free hold, and where to sell it.
  hold  "What you're carrying": the best port to sell the cargo already aboard, against selling it here.

A tip is bought once per port visit and stays on her counter (free to read again) until you sail.
Nothing here uses the game's dice, so replays come out the same.

State on the house:  p["counter"] = {"turn", "port", "bought": {tip: reveal}}

Numbers come from rules.counter (Admin > Rules > Under the Counter) with DEFAULTS as the fallback.
"""
import math

DEFAULTS = {
    "enabled": False,         # hidden until the next phase (20 Nov 2026); Admin > Rules switches it on
    "fee_min": 0.10,          # her share of the tip's worth for the lowest rank...
    "fee_max": 0.30,          # ...rising evenly to this at the top rank
    "fee_floor": 25,          # she never gets out of bed for less than this
    "min_worth": 150,         # a tip worth less than this is not worth selling: she says so, free
    "risk_loss": 0.4,         # share of the profit a pirate fight is reckoned to cost, times its chance
}

TIPS = ("run", "hold")


def E():
    import engine
    return engine


def rules():
    r = dict(DEFAULTS)
    r.update((E().R.get("counter") or {}))
    return r


def enabled():
    return bool(rules().get("enabled", False))


# ------------------------------------------------------------------------------------------- the sums --

def fee_share(g, p):
    """Her share of the tip's worth for this house: fee_min at the lowest rank up to fee_max at the top,
    by the rank its net worth reaches now (the same ladder as promotions)."""
    e, r = E(), rules()
    ranks = e.CFG.get("ranks") or []
    top = max(1, len(ranks) - 1)
    idx = e.rank_index(g.worth(p), g.s.get("years")) if ranks else 0
    lo, hi = float(r["fee_min"]), float(r["fee_max"])
    return round(max(0.0, lo + (hi - lo) * min(1.0, idx / top)), 4)


def fee_for(g, p, worth):
    r = rules()
    return int(max(int(r["fee_floor"]), math.ceil(worth * fee_share(g, p))))


def arrival_mid(g, port, good):
    """Her figure for a cargo's price in a port next month, when a ship sailing now lands: this month's
    price pulled toward its target by the market's reversion (engine _move_markets), leaving out any
    glut, shortage, crash or boom that runs out before then, and holding a foretold boom that is still
    running at its level. The month's random swing averages out."""
    e, s = E(), g.s
    m, ev = e.R["market"], e.R["events"]
    base = e.GOODS[good]["base"] * e.PORTS[port]["mods"].get(good, 1.0)
    price = float(s["prices"][port][good])
    effects = [float(sh["mult"]) for sh in s.get("shocks", ()) if sh["port"] == port and sh["good"] == good
               and int(sh.get("turns", 1)) > 1]
    w = g._windfall(port, good)
    if w and int(w.get("turns", 1)) > 1:
        effects.append(float(w["mult"]))
    else:
        w = None
    if port in s.get("crackdown", {}) and good in g.banned(port):
        effects.append(float(ev["ban_price_mult"]))
    if not effects:
        lift = 1.0
    elif ev.get("stack_booms", False):
        lift = 1.0
        for x in effects:
            lift *= x
    else:
        lift = max(effects, key=lambda x: abs(math.log(max(1e-9, x))))
    target = base * lift
    price += e.reversion_of(good) * (target - price)
    floor, ceiling = e.price_limits(good)
    if w:
        if w.get("foretold") and w.get("kind") == "boom" and (e.R.get("registrar") or {}).get("hot_hold", True):
            price = max(price, base * float(w.get("mult", 1.0)))
        lo, hi = base * min(floor, lift), base * max(ceiling, lift)
        return max(1.0, lo, min(hi, price))
    return max(floor * base, min(ceiling * base, price))


def sell_at(g, p, port, good, qty, mid):
    """What qty units fetch in another port at that price: the price pushed down as the lot sells, the
    dealer's cut at this house's standing there, and the dealers' purse (full again next month)."""
    e = E()
    if qty <= 0:
        return 0
    k = e.R["market"]["impact"] * qty / e.GOODS[good]["depth"]
    end = mid / (1 + k)
    total = qty * (mid + end) / 2 * (1 - g.spread(p, port))
    size = g.purse_size(port, good)
    if size is not None and total > size:
        over = max(0.0, min(1.0, float(e.R["market"].get("purse_over", 0.35))))
        total = size + (total - size) * over
    return int(math.floor(total))


def tax_at(g, p, port, good, qty, mid):
    """The Port Authority's tax on landing, declared honestly (Pay Correct), at the price there."""
    return int(round(qty * mid * g.tax_rate_for(p, port)))


def fight_odds(g, p, a, b):
    """The chance of a pirate fight between two ports: the same rolls the Danger monitor shows
    (player.js pirateRisk), from the engine's own tables."""
    e = E()
    w, pi, ly = e.R["weather"], e.R["pirates"], e.R["liyuen"]
    risk = max(w["risk_min"], min(w["risk_max"], e.distance(a, b) / float(w["risk_div"])))
    prot = p.get("protect", 0) > 0
    pirate = min(1.0, pi["chance"] * e.MULT["pirates"] * risk) * ((1 - ly["protect_save"]) if prot else 1.0)
    lord = 0.0 if prot else min(1.0, ly["chance"] * e.MULT["pirates"] * risk)
    return 1 - (1 - pirate) * (1 - lord)


def _free_hold(g, p):
    return max(0, g.capacity(p) - g.used(p))


def _max_buy(g, p, good, room, cash):
    lo, hi = 0, room
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if g.quote(p, good, mid, "buy")[0] <= cash:
            lo = mid
        else:
            hi = mid - 1
    return lo


def best_run(g, p):
    """The best cargo to buy here and where to sell it, or None. Every cargo the house can buy here,
    every other port that doesn't ban it, every lot size up to the free hold and the silver aboard:
    the lot that leaves the most after the dealers, the purse, the tax there and the pirate risk."""
    e, r = E(), rules()
    here = p["port"]
    room, cash = _free_hold(g, p), int(p["cash"])
    if room <= 0 or cash <= 0:
        return None
    best = None
    banned_here = set(g.banned(here))
    for good in e.GOODS:
        if good in banned_here:
            continue
        top = _max_buy(g, p, good, room, cash)
        if top <= 0:
            continue
        for port in e.PORTS:
            if port == here or good in g.banned(port):
                continue
            mid = arrival_mid(g, port, good)
            odds = fight_odds(g, p, here, port)
            keep = 1 - odds * float(r["risk_loss"])

            def value(q):
                if q <= 0:
                    return 0.0, 0, 0, 0
                cost = g.quote(p, good, q, "buy")[0]
                sale = sell_at(g, p, port, good, q, mid)
                tax = tax_at(g, p, port, good, q, mid)
                profit = sale - cost - tax
                return (profit * keep if profit > 0 else profit), cost, sale, tax

            # The profit rises then falls with the lot size (the price moves against a big lot): a
            # search over whole units finds the top.
            lo, hi = 1, top
            while hi - lo > 2:
                m1 = lo + (hi - lo) // 3
                m2 = hi - (hi - lo) // 3
                if value(m1)[0] < value(m2)[0]:
                    lo = m1
                else:
                    hi = m2
            q = max(range(lo, hi + 1), key=lambda n: value(n)[0])
            worth, cost, sale, tax = value(q)
            if worth > 0 and (best is None or worth > best["worth"]):
                best = {"good": good, "port": port, "qty": q, "cost": int(cost), "sale": int(sale), "tax": int(tax),
                        "profit": int(sale - cost - tax), "worth": int(worth), "risk": round(odds, 4),
                        "unit_buy": round(cost / q, 2), "unit_sell": round(sale / q, 2), "mid": round(mid, 2)}
    return best


def best_hold(g, p):
    """The best port to sell the cargo aboard, against selling it all here now, or None. Cargo sealed in
    bond can't be sold here this visit, so here it counts for nothing. A port that bans a cargo seizes
    it, so there it counts for nothing too."""
    e, r = E(), rules()
    here = p["port"]
    aboard = {gd: int(q) for gd, q in p["cargo"].items() if int(q) > 0}
    if not aboard:
        return None
    sealed = g.sealed(p) or {}
    banned_here = set(g.banned(here))
    here_total = 0
    for gd, q in aboard.items():
        q_free = max(0, q - int(sealed.get(gd, 0) or 0))
        if q_free and gd not in banned_here:
            here_total += g.quote(p, gd, q_free, "sell")[0]
    best = None
    for port in e.PORTS:
        if port == here:
            continue
        odds = fight_odds(g, p, here, port)
        lines, sale, tax = [], 0, 0
        for gd, q in sorted(aboard.items()):
            if gd in g.banned(port):
                lines.append({"good": gd, "qty": q, "sale": 0, "banned": True})
                continue
            mid = arrival_mid(g, port, gd)
            s_ = sell_at(g, p, port, gd, q, mid)
            t_ = tax_at(g, p, port, gd, q, mid)
            sale, tax = sale + s_, tax + t_
            lines.append({"good": gd, "qty": q, "sale": s_, "tax": t_, "unit": round(s_ / q, 2)})
        net = sale - tax
        gain = net - here_total
        worth = gain - odds * float(r["risk_loss"]) * max(0, net)
        if worth > 0 and (best is None or worth > best["worth"]):
            best = {"port": port, "sale": int(sale), "tax": int(tax), "net": int(net), "here": int(here_total),
                    "gain": int(gain), "worth": int(worth), "risk": round(odds, 4), "lines": lines}
    return best


TIP_FN = {"run": best_run, "hold": best_hold}

# Her sums run on every screen update, so the answer is kept until anything it depends on changes.
_MEMO = {}


def _memo_key(g, p, tip):
    s = g.s
    return (tip, s.get("game_id"), s["turn"], p["id"], p["port"], int(p["cash"]), int(p.get("protect", 0) > 0),
            g.capacity(p), tuple(sorted((k, int(v)) for k, v in p["cargo"].items() if v)),
            tuple(sorted(g.sealed(p).items())),
            tuple(round(v, 1) for k in sorted(p["rep"]) for v in (p["rep"][k],)),
            tuple(round(s["prices"][pt][gd], 2) for pt in sorted(s["prices"]) for gd in sorted(s["prices"][pt])),
            repr(sorted((pt, sorted(row.items())) for pt, row in (s.get("purse") or {}).items())),
            repr(s.get("windfalls")), repr(s.get("shocks")), repr(sorted(s.get("crackdown", {}).items())))


def tip_now(g, p, tip):
    key = _memo_key(g, p, tip)
    if key not in _MEMO:
        if len(_MEMO) > 64:
            _MEMO.clear()
        _MEMO[key] = TIP_FN[tip](g, p)
    return _MEMO[key]


# ------------------------------------------------------------------------------------- house state --

def _state(g, p):
    """This visit's counter: what has been bought here this month (cleared once the house sails)."""
    c = p.get("counter")
    if not isinstance(c, dict) or c.get("turn") != g.s["turn"] or c.get("port") != p["port"]:
        c = {"turn": g.s["turn"], "port": p["port"], "bought": {}}
    return c


def officer(g, p):
    return g.officer_of(p["port"])


def _hello_key(g, p):
    """Her greeting this visit: picked from the house and the month, never the game's dice."""
    e = E()
    bank = g._bank("l.counter_hello")
    if not bank:
        return None
    n = sum(ord(ch) for ch in (p.get("name", "") + p["port"])) + 7 * g.s["turn"]
    return "l.counter_hello.{}".format(bank[n % len(bank)])


def view(g, p):
    """What the Under the Counter tab shows: her offers (worth and price, the tip itself hidden) and the
    tips already bought this visit (in full)."""
    e = E()
    if not enabled() or g.s.get("phase") != "port":
        return None
    c = _state(g, p)
    share = fee_share(g, p)
    offers = {}
    for tip in TIPS:
        if tip in c["bought"]:
            offers[tip] = {"bought": True}
            continue
        t = tip_now(g, p, tip)
        worth = int(t["worth"]) if t else 0
        if worth < int(rules()["min_worth"]):
            offers[tip] = {"worth": worth, "fee": 0, "none": True}
        else:
            fee = fee_for(g, p, worth)
            offers[tip] = {"worth": worth, "fee": fee, "short": max(0, fee - int(p["cash"]))}
    hello = _hello_key(g, p)
    off = officer(g, p)
    return {"officer": off, "name": ((e.CFG.get("characters") or {}).get(off) or {}).get("name", ""),
            "share": share, "rank": e.rank_for(g.worth(p), g.s.get("years")),
            "offers": offers, "bought": c["bought"],
            "hello": e.tx(hello, port=e.PORTS[p["port"]]["name"]) if hello else ""}


def _words(t, tip):
    e = E()
    w = {"where": e.PORTS[t["port"]]["name"]}
    if tip == "run":
        w["goods"] = e.GOODS[t["good"]]["name"]
    return w


def act(g, p, a):
    """{"type": "counter", "tip": "run" | "hold"}: pay her price and hear the tip. Bought once per visit;
    asking again reads it back for nothing."""
    e = E()
    if not enabled():
        raise e.GameError(e.tx("e.counter_off"))
    tip = str(a.get("tip") or "")
    if tip not in TIPS:
        raise e.GameError(e.tx("e.unknown_action"))
    c = _state(g, p)
    if tip in c["bought"]:
        return c["bought"][tip]["text"]
    t = tip_now(g, p, tip)
    worth = int(t["worth"]) if t else 0
    if worth < int(rules()["min_worth"]):
        key = g._draw(p, "l.counter_none") or "l.counter_none.0"
        return e.tx(key, port=e.PORTS[p["port"]]["name"])
    fee = fee_for(g, p, worth)
    if int(p["cash"]) < fee:
        raise e.GameError(e.tx("e.counter_cost", price=e.money(fee), cash=e.money(p["cash"])))
    p["cash"] -= fee
    g._book(p, "tips", -fee)
    key = g._draw(p, "l.counter_" + tip) or "l.counter_{}.0".format(tip)
    text = e.tx(key, **_words(t, tip))
    reveal = dict(t, tip=tip, fee=fee, share=fee_share(g, p), text=text, key=key)
    c["bought"][tip] = reveal
    p["counter"] = c
    if tip == "run":
        what = "buy {} {} here for {}, sell in {} for about {} (tax {}), profit about {}".format(
            t["qty"], e.GOODS[t["good"]]["name"], e.money(t["cost"]), e.PORTS[t["port"]]["name"],
            e.money(t["sale"]), e.money(t["tax"]), e.money(t["profit"]))
    else:
        what = "sell the hold in {} for about {} after tax, against {} here".format(
            e.PORTS[t["port"]]["name"], e.money(t["net"]), e.money(t["here"]))
    g._ev("market", "counter_tip", "{}: bought a tip under the counter in {} for {} ({:.0%} of its worth, {}): {}; "
          "pirate risk {:.0%}".format(p["name"], e.PORTS[p["port"]]["name"], e.money(fee), reveal["share"],
                                      e.money(worth), what, t["risk"]),
          p, port=p["port"], tip=tip, fee=fee, worth=worth, where=t["port"], good=t.get("good"))
    g._detail = {"fee": fee, "tip": tip}
    return text
