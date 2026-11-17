"""The Mayor's Parlour: a purse of silver for standing in a port, once per visit.

Run from the project folder:  python tests/mayor_test.py
"""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import engine  # noqa: E402
from engine import Game, GameError, R, PORTS  # noqa: E402


def fresh(port="shanghai", rep=34.0, cash=20000.0):
    game = Game(seed=11)
    pid = game.pid_for_token(game.join("Tester", ""))
    game.act(pid, {"type": "start"})
    p = game.s["players"][pid]
    p["customs"] = None
    p["port"] = port
    p["home"] = "hongkong" if port != "hongkong" else "singapore"
    p["rep"][port] = rep
    p["cash"] = cash
    p["tab"] = game._new_tab()
    return game, pid, p


def expected(port, rep, amount):
    g = R["gift"]
    appetite = g["appetite"] * PORTS[port]["dues"]
    soft = g["soft_from"]
    head = 1.0 if rep <= soft else max(0.0, (100 - rep) / (100 - soft))
    return g["cap"] * (1 - math.exp(-amount / appetite)) * head


def test_the_draft_examples():
    # Shanghai (harbour dues level 1.2, appetite 1,800) at standing 34.
    game, _, _ = fresh()
    assert round(game.gift_gain("shanghai", 34, 500)) == 4
    assert round(game.gift_gain("shanghai", 34, 1800)) == 9
    assert round(game.gift_gain("shanghai", 34, 5000)) == 14


def test_each_dollar_buys_less():
    game, _, _ = fresh()
    a = game.gift_gain("shanghai", 34, 1000)
    b = game.gift_gain("shanghai", 34, 2000) - a
    c = game.gift_gain("shanghai", 34, 3000) - a - b
    assert a > b > c > 0


def test_harder_above_fifty_and_nothing_at_100():
    game, _, _ = fresh()
    assert game.gift_gain("shanghai", 75, 1800) < game.gift_gain("shanghai", 50, 1800)
    assert game.gift_gain("shanghai", 50, 1800) == game.gift_gain("shanghai", 20, 1800)
    assert game.gift_gain("shanghai", 100, 9000) == 0


def test_a_gift_raises_standing_takes_silver_and_books_it():
    game, pid, p = fresh()
    msg = game.act(pid, {"type": "gift", "amount": 1800})
    gain = expected("shanghai", 34, 1800)
    assert abs(p["rep"]["shanghai"] - (34 + gain)) < 1e-6
    assert p["cash"] == 20000 - 1800
    assert p["books"]["cur"]["gift"] == -1800
    assert p["gift_last"]["tier"] == "warm" and p["gift_last"]["to"] == 43
    assert "1,800" in msg
    v = game.view(pid)["me"]["gift"]
    assert v["given"] and v["thanks"]["amount"] == 1800


def test_once_per_visit_then_again_after_sailing():
    game, pid, p = fresh()
    game.act(pid, {"type": "gift", "amount": 500})
    try:
        game.act(pid, {"type": "gift", "amount": 500})
        raise AssertionError("a second gift in one visit was accepted")
    except GameError:
        pass
    p["tab"] = game._new_tab()          # anchored in a new port
    game.act(pid, {"type": "gift", "amount": 500})


def test_limits():
    game, pid, p = fresh(cash=300)
    for amount in (50, 9001, 400):      # under the least, over five appetites, more than the silver
        try:
            game.act(pid, {"type": "gift", "amount": amount})
            raise AssertionError("accepted a gift of {}".format(amount))
        except GameError:
            pass
    assert p["cash"] == 300 and not p["tab"]["gift"]


def test_tiers():
    game, _, _ = fresh()
    assert game.gift_tier(1) == "cool"
    assert game.gift_tier(3) == "gracious"
    assert game.gift_tier(9.4) == "warm"
    assert game.gift_tier(14) == "delighted"


def test_home_gifts_do_not_buy_borrowing():
    game, pid, p = fresh(port="hongkong", rep=40.0)
    p["home"] = "hongkong"
    limit, line = game.loan_limit(p), game.collectors_line(p)
    game.act(pid, {"type": "gift", "amount": 5000})
    assert p["rep"]["hongkong"] > 40
    assert game.earned_rep(p, "hongkong") == 40.0
    # Only the silver handed over counts against the limit (its share of assets); the standing bought adds nothing.
    assert abs(game.loan_limit(p) - (limit - R["bank"]["loan_asset_share"] * 5000)) < 1e-6
    assert game.collectors_line(p) == line


def test_losses_lower_both_numbers_alike():
    game, pid, p = fresh(port="hongkong", rep=40.0)
    p["home"] = "hongkong"
    game.act(pid, {"type": "gift", "amount": 5000})
    bought = p["gift_rep"]["hongkong"]
    game._gain_rep(p, "hongkong", -10)
    assert abs(game.earned_rep(p, "hongkong") - 30.0) < 1e-9
    assert p["gift_rep"]["hongkong"] == bought
    game._gain_rep(p, "hongkong", -100)          # down to nothing: the bought share can't outlast it
    assert p["rep"]["hongkong"] == 0 and p["gift_rep"]["hongkong"] == 0


def test_switched_off():
    game, pid, _ = fresh()
    R["gift"]["enabled"] = False
    try:
        game.act(pid, {"type": "gift", "amount": 500})
        raise AssertionError("gift accepted while switched off")
    except GameError:
        pass
    finally:
        R["gift"]["enabled"] = True


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
