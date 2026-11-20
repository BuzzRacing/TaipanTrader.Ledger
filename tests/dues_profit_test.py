"""Harbour dues: the Mayor's share of profit made selling cargo in her port this visit.

Run from the project folder:  python tests/dues_profit_test.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import engine  # noqa: E402
from engine import Game, R, PORTS  # noqa: E402


def fresh(port="calcutta", rep=50.0, cash=50000.0):
    game = Game(seed=7)
    pid = game.pid_for_token(game.join("Tester", ""))
    game.act(pid, {"type": "start"})
    p = game.s["players"][pid]
    p["customs"] = None
    p["port"] = port
    p["home"] = "hongkong"
    p["rep"][port] = rep
    p["cash"] = cash
    p["debt"] = 0.0
    p["tab"] = game._new_tab()
    game._share_book(port).pop(p["id"], None)
    return game, pid, p


def sold(game, p, good, sales, cost):
    game._tally_sale(p, good, float(sales), float(cost))


def line(game, p):
    return next((ln for ln in game.dues(p)["lines"] if ln["key"] == "profit"), None)


def expected(game, p, rows):
    """The rule written out a second way, for a check."""
    d, port = R["dues"], p["port"]
    net = sum(s - c for s, c in rows)
    gains = sum(s - c for s, c in rows if s > c)
    if net <= d["profit_free"]:
        return 0
    keep = min(1.0, (net - d["profit_free"]) / gains)
    w = sum((s - c) * keep * game.profit_margin_factor((s - c) / c if c else float("inf")) for s, c in rows if s > c)
    rep_f = 1 - d["profit_rep_cut"] * (p["rep"][port] - 50) / 50.0
    return int(round(w * game.profit_rate(port) * PORTS[port]["dues"] * rep_f * (1 - game.share_cut(p, port))))


def test_small_rice_and_tea_sales_pay_nothing():
    game, _, p = fresh()
    sold(game, p, "rice", 9000, 3000)        # 200% margin, but only $6,000 profit
    sold(game, p, "tea", 5000, 2000)         # $3,000 more: $9,000 in all, under the $10,000 free
    assert line(game, p) is None


def test_low_margins_pay_nothing():
    game, _, p = fresh()
    sold(game, p, "porcelain", 1200000, 1000000)   # $200,000 profit at 20%
    assert line(game, p) is None


def test_margin_curve():
    game, _, _ = fresh()
    f = game.profit_margin_factor
    assert f(0.25) == 0 and f(0.10) == 0
    assert abs(f(0.625) - 0.5) < 1e-9
    assert abs(f(1.0) - 1.0) < 1e-9
    assert abs(f(1.5) - 1.25) < 1e-9
    assert abs(f(2.0) - 1.5) < 1e-9 and abs(f(9.0) - 1.5) < 1e-9
    assert abs(f(float("inf")) - 1.5) < 1e-9          # captured cargo: no cost


def test_high_margin_pays_and_shows_on_the_bill():
    game, _, p = fresh()
    sold(game, p, "silk", 600000, 200000)          # $400,000 at 200%
    before = game.dues(p)
    ln = line(game, p)
    assert ln and ln["amount"] == expected(game, p, [(600000, 200000)]) > 0
    assert ln["basis"] == 400000 - R["dues"]["profit_free"]
    fees = sum(x["amount"] for x in before["lines"] if x["key"] != "profit")
    assert before["total"] == fees + ln["amount"]
    assert before["profit_rate"] == ln["month"]


def test_losses_offset_gains():
    game, _, p = fresh()
    sold(game, p, "silk", 300000, 100000)          # +200,000
    sold(game, p, "spices", 50000, 245000)         # -195,000: net 5,000, under the free amount
    assert line(game, p) is None
    sold(game, p, "opium", 160000, 40000)          # +120,000
    ln = line(game, p)
    assert ln["amount"] == expected(game, p, [(300000, 100000), (50000, 245000), (160000, 40000)])


def test_standing_cuts_or_raises_it():
    amounts = {}
    game, _, p = fresh()
    sold(game, p, "silk", 600000, 200000)
    for rep in (0, 50, 100):
        p["rep"]["calcutta"] = rep
        amounts[rep] = line(game, p)["amount"]
    assert abs(amounts[100] - amounts[50] * 0.5) <= 1
    assert abs(amounts[0] - amounts[50] * 1.5) <= 1
    # it stays out of the Mayor's courtesy line, which only discounts the fees
    game, _, p = fresh(rep=100)
    fees_only = game.dues(p)
    sold(game, p, "silk", 600000, 200000)
    bill = game.dues(p)
    std = lambda b: sum(x["amount"] for x in b["lines"] if x["key"] == "standing")
    assert std(bill) == std(fees_only)


def test_shares_in_the_port_cut_it():
    game, _, p = fresh()
    sold(game, p, "silk", 600000, 200000)
    full = line(game, p)["amount"]
    game._share_book("calcutta")[p["id"]] = 5
    assert abs(line(game, p)["amount"] - full * 0.5) <= 1
    game._share_book("calcutta")[p["id"]] = 10
    assert line(game, p) is None


def test_rate_moves_month_to_month_inside_the_range():
    game, _, p = fresh()
    d = R["dues"]
    seen = set()
    for turn in range(24):
        game.s["turn"] = turn
        r = game.profit_rate("calcutta")
        assert d["profit_rate_min"] <= r <= d["profit_rate_max"]
        assert r == game.profit_rate("calcutta")       # the same all month (and in a replay)
        seen.add(r)
    assert len(seen) > 20
    game.s["turn"] = 5
    assert game.profit_rate("calcutta") != game.profit_rate("shanghai")


def test_a_real_sale_fills_the_tally_and_paying_takes_it():
    game, pid, p = fresh(cash=0.0)
    p["cargo"]["silk"] = 100
    p.setdefault("basis", {})["silk"] = 100.0       # cheap silk: a big margin
    game.act(pid, {"type": "sell", "good": "silk", "qty": 100})
    row = p["tab"]["goods"]["silk"]
    assert row[1] == 10000.0 and row[0] > 10000.0
    bill = game.dues(p)
    cash = p["cash"]
    game._pay_dues(p)
    assert p["cash"] == cash - bill["total"]


def test_reconcile_keeps_the_tally():
    game, _, p = fresh()
    sold(game, p, "silk", 600000, 200000)
    game.reconcile()
    assert p["tab"]["goods"]["silk"] == [600000.0, 200000.0]
    p["tab"] = {"repair": 5}                         # a save from before this rule
    game.reconcile()
    assert p["tab"]["goods"] == {} and p["tab"]["repair"] == 5.0
    assert line(game, p) is None


def test_switched_off():
    game, _, p = fresh()
    sold(game, p, "silk", 600000, 200000)
    R["dues"]["profit_enabled"] = False
    try:
        assert line(game, p) is None
    finally:
        R["dues"]["profit_enabled"] = True


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
    print("all passed")
