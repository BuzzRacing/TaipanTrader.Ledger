"""The fixes from the review of Anthony's 10-year game (19 Nov 2026):  python tests/review2_test.py

1. Net worth counts cargo at its normal price (no booms, no Hong Kong live price).
2. Big trades: own price moves fade (70% next month, the rest the month after); deeper markets for old saves.
4. A boom never lowers a price, a crash never raises one.
5. Paying to pass: silver, then the bank; the rest in cargo or on Madam Wu's books (+fee).
   Pirate fleets vary in size and the old 12 / 16 caps move to 24 / 30.
6. Fill cannons on one ship or the whole fleet.
"""
import copy
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402
import engine  # noqa: E402
from engine import Game, GameError, GOODS, PORTS, R  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import battle_test as bt  # noqa: E402


def fresh():
    cfg, errors = config.validate(config.defaults())
    assert not errors, errors
    engine.configure(cfg)


def one_house(seed=3):
    g = Game(seed=seed)
    pid = g.pid_for_token(g.join("Ada", ""))
    g.act(pid, {"type": "start"}, present=[pid])
    p = g.s["players"][pid]
    p["customs"] = None
    return g, pid, p


def test_worth_counts_cargo_at_what_dealers_pay():
    """Game 4 review (20 Nov 2026) replaced the normal-price rule: cargo counts at what the dealers in the
    port the fleet is in would pay for all of it today. A price elsewhere still never moves it."""
    fresh()
    g, pid, p = one_house()
    p["cargo"] = {"silk": 100}
    p["wh"], p["depots"] = {}, {}
    before = g.worth(p)
    for port in PORTS:
        if port != p["port"]:
            g.s["prices"][port]["silk"] *= 10
    assert abs(g.worth(p) - before) < 1e-6, "a price somewhere else moved net worth"
    no_cargo = dict(p, cargo={})
    sale, _end = g.quote(p, "silk", 100, "sell")
    assert abs((g.worth(p) - g.worth(no_cargo)) - sale) < 1e-6
    # A journal snapshot keeps the figure it was taken with.
    snap = [f for f in g.firms() if f["id"] == pid][0]
    assert abs(engine.worth_of(snap) - g.worth(p)) < 1.0


def test_boom_never_lowers_and_crash_never_raises():
    fresh()
    assert Game._windfall_price("boom", 2516.0, 1975.0) == 2516.0
    assert Game._windfall_price("boom", 500.0, 1975.0) == 1975.0
    assert Game._windfall_price("crash", 50.0, 100.0) == 50.0
    assert Game._windfall_price("crash", 500.0, 100.0) == 100.0
    assert Game._windfall_price("crash", 0.2, 0.1) == 1.0


def test_own_price_moves_fade():
    fresh()
    g, pid, p = one_house()
    port, good = p["port"], "tea"
    p["ships"] = [g._new_ship("indiaman", guns=0)]
    p["cash"] = 10 ** 9
    mid = g.s["prices"][port][good]
    g.act(pid, {"type": "buy", "good": good, "qty": 400}, present=[pid])
    pushed = g.s["prices"][port][good]
    assert pushed > mid
    push = math.log(pushed / mid)
    assert abs(g.s["pushes"][port][good][0] - push) < 1e-9
    g._fade_pushes()
    one = g.s["prices"][port][good]
    assert abs(math.log(pushed / one) - 0.7 * push) < 1e-9, "70% of the move should fade first"
    assert abs(g.s["pushes"][port][good][1] - 0.3 * push) < 1e-9
    g._fade_pushes()
    assert abs(g.s["prices"][port][good] - mid) < 1e-6 * mid, "the rest fades the month after"
    assert not g.s["pushes"], "nothing left to fade"


def test_old_settings_upgrade_once():
    raw = config.defaults()
    for g, d in config.OLD_DEPTHS.items():
        raw["goods"][g]["depth"] = d
    raw["goods"]["tea"]["depth"] = 777          # set by hand: stays
    raw["rules"]["market"]["depth_v2"] = False
    raw["rules"]["battle"].update({"match_ships_max": 12, "match_lord_ships_max": 16, "match_v2": False})
    cfg, errors = config.validate(raw)
    assert not errors, errors
    d = config.defaults()
    assert cfg["goods"]["silk"]["depth"] == d["goods"]["silk"]["depth"] != 160
    assert cfg["goods"]["tea"]["depth"] == 777
    assert cfg["rules"]["battle"]["match_ships_max"] == 24 and cfg["rules"]["battle"]["match_lord_ships_max"] == 30
    # Once upgraded, a later hand-set cap of 12 stays 12.
    cfg["rules"]["battle"]["match_ships_max"] = 12
    cfg2, errors = config.validate(cfg)
    assert not errors and cfg2["rules"]["battle"]["match_ships_max"] == 12


def _parley(cash, bank, cargo, debt=0.0):
    bt.setup()
    g = bt.new_game(names=("Ann",), cash=cash, cargo=cargo)
    p = g.s["players"]["p1"]
    p["bank"], p["debt"] = float(bank), float(debt)
    bt.sail(g, present=["p1"])
    assert g.s["phase"] == "sea"
    return g, p, g.view("p1", ["p1"])["me"]["battle"]


def test_pay_from_silver_and_bank():
    g, p, b = _parley(cash=0, bank=10 ** 6, cargo={"rice": 20})
    price = b["price"]
    assert price > 0 and b["can_pay"] and b["toll"]["bank"] == price, b["toll"]
    before = bt.books(p)
    g.act("p1", {"type": "sea", "choice": "pay"}, present=["p1"])
    # the bank paid it (the month's bank interest is added on top once the voyage ends)
    assert abs(p["bank"] - (10 ** 6 - price) * (1 + R["bank"]["bank_rate"])) < 1.0, p["bank"]
    assert p["cash"] == 0 and p["fights"][0]["outcome"] == "paid"
    assert bt.books(p).get("parley", 0) - before.get("parley", 0) == -price


def test_pay_the_rest_in_cargo():
    g, p, b = _parley(cash=0, bank=0, cargo={"silk": 50, "rice": 20})
    t = b["toll"]
    assert not b["can_pay"] and t["short"] == b["price"] and t["can_cargo"], t
    assert list(t["cargo"]) == ["silk"], "their pick: the dearest cargo first"
    try:
        g.act("p1", {"type": "sea", "choice": "pay"}, present=["p1"])
        raise AssertionError("paid in silver without the silver")
    except GameError:
        pass
    silk = p["cargo"]["silk"]
    g.act("p1", {"type": "sea", "choice": "pay_cargo"}, present=["p1"])
    assert p["cargo"]["silk"] == silk - t["cargo"]["silk"] and p["cargo"]["rice"] == 20
    assert p["fights"][0]["outcome"] == "paid"


def test_pay_the_rest_on_madam_wu():
    g, p, b = _parley(cash=0, bank=0, cargo={"rice": 20})
    t = b["toll"]
    assert t["can_wu"] and t["fee"] == math.ceil(t["short"] * 0.10), t
    g.act("p1", {"type": "sea", "choice": "pay_wu"}, present=["p1"])
    # the shortfall plus her fee became debt (with the month's interest on it once the voyage ends)
    # (unpaid harbour dues may land on the debt too, so allow a little over)
    low = t["wu"] * (1 + engine.loan_rate())
    assert low - 1.0 <= p["debt"] <= low + 100, (p["debt"], t)
    assert p["cargo"] == {"rice": 20}
    # Over the loan limit she won't cover it.
    g, p, b = _parley(cash=0, bank=0, cargo={"rice": 20}, debt=10 ** 9)
    assert not b["toll"]["can_wu"]


def test_pirate_fleets_vary():
    fresh()
    g, pid, p = one_house()
    p["ships"] = [g._new_ship("indiaman", guns=0) for _ in range(5)]
    for sh in p["ships"]:
        sh["cannons"] = 12
    sizes = []
    for i in range(60):
        g.rng = random.Random(i)
        sizes.append(g._muster(p, "pirates")["n"])
    assert max(sizes) <= R["battle"]["match_ships_max"]
    assert len(set(sizes)) >= 5, sizes
    assert sum(1 for n in sizes if n == max(sizes)) < len(sizes) / 2, "most fights should not sit at the cap"


def test_fill_cannons():
    fresh()
    g, pid, p = one_house()
    p["ships"] = [g._new_ship("indiaman", guns=0), g._new_ship("indiaman", guns=0)]
    price, cs = engine.cannon_price(), engine.cannon_slots()
    slots = engine.SHIPS["indiaman"]["slots"]
    p["cash"] = price * 100
    g.act(pid, {"type": "fill_cannons", "index": 0}, present=[pid])
    assert p["ships"][0]["cannons"] == slots // cs and p["ships"][1].get("cannons", 0) == 0
    p["cash"] = price * 3 + 1
    g.act(pid, {"type": "fill_cannons", "index": "all"}, present=[pid])
    assert p["ships"][1]["cannons"] == 3 and p["cash"] == 1, "stops when silver runs out"
    p["cash"] = 0
    try:
        g.act(pid, {"type": "fill_cannons", "index": "all"}, present=[pid])
        raise AssertionError("filled with no silver")
    except GameError:
        pass


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("ok", t.__name__)
    print("OK: review fixes ({} tests)".format(len(tests)))


if __name__ == "__main__":
    main()
