"""Banks and warehouses away from home: one bank account at every bank counter, and warehouses
rented port by port (each keeps only what was left there).

Run from the project folder:  python tests/depot_test.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import engine  # noqa: E402
from engine import Game, GameError, R, PORTS  # noqa: E402


def fresh(port="shanghai", cash=500000.0):
    game = Game(seed=7)
    pid = game.pid_for_token(game.join("Tester", ""))
    game.act(pid, {"type": "start"})
    p = game.s["players"][pid]
    p["customs"] = None
    p["port"] = port
    p["home"] = "hongkong"
    p["cash"] = cash
    p["tab"] = game._new_tab()
    PORTS["shanghai"]["bank"] = PORTS["shanghai"]["warehouse"] = True
    PORTS["nagasaki"]["bank"] = PORTS["nagasaki"]["warehouse"] = False
    return game, pid, p


def refused(game, pid, a):
    try:
        game.act(pid, a)
    except GameError:
        return True
    return False


def test_bank_is_one_account():
    game, pid, p = fresh()
    game.act(pid, {"type": "bank", "op": "deposit", "amount": 1000})
    assert p["bank"] == 1000
    p["port"] = "nagasaki"
    assert refused(game, pid, {"type": "bank", "op": "withdraw", "amount": 10})
    p["port"] = "hongkong"
    game.act(pid, {"type": "bank", "op": "withdraw", "amount": 400})
    assert p["bank"] == 600


def test_open_store_expand_and_sell_all():
    game, pid, p = fresh()
    f = R["fleet"]
    assert refused(game, pid, {"type": "warehouse", "op": "store", "good": "tea", "qty": 1})
    cash = p["cash"]
    game.act(pid, {"type": "depot", "op": "open"})
    assert p["cash"] == cash - f["depot_open_cost"]
    assert refused(game, pid, {"type": "depot", "op": "open"})
    p["cargo"]["tea"] = 50
    game.act(pid, {"type": "warehouse", "op": "store", "good": "tea", "qty": 30})
    assert p["depots"]["shanghai"]["goods"]["tea"] == 30 and p["cargo"]["tea"] == 20
    assert not p["wh"].get("tea")                          # home warehouse untouched
    view = game.view(pid)["me"]
    assert view["wh_here"] == "open" and view["wh"]["tea"] == 30 and view["wh_cap"] == f["depot_cap"]
    game.act(pid, {"type": "depot", "op": "expand"})
    assert game.view(pid)["me"]["wh_cap"] == f["depot_cap"] + f["depot_expand_cap"]
    # Elsewhere the Shanghai stock cannot be reached.
    p["port"] = "singapore"
    PORTS["singapore"]["warehouse"] = True
    assert game.view(pid)["me"]["wh_here"] == "closed"
    assert refused(game, pid, {"type": "warehouse", "op": "take", "good": "tea", "qty": 1})
    p["port"] = "shanghai"
    cash = p["cash"]
    game.act(pid, {"type": "sell", "good": "tea", "src": "all"})
    assert p["cash"] > cash and not p["cargo"].get("tea") and not p["depots"]["shanghai"]["goods"].get("tea")


def test_home_needs_no_rent():
    game, pid, p = fresh(port="hongkong")
    assert refused(game, pid, {"type": "depot", "op": "open"})
    assert game.view(pid)["me"]["wh_here"] == "home"


def test_worth_counts_away_stock():
    game, pid, p = fresh()
    game.act(pid, {"type": "depot", "op": "open"})
    before = game.worth(p)
    p["depots"]["shanghai"]["goods"]["silk"] = 10
    assert game.worth(p) > before


def test_warehouse_robbery():
    game, pid, p = fresh()
    game.act(pid, {"type": "depot", "op": "open"})
    p["depots"]["shanghai"]["goods"]["tea"] = 400
    p["wh"]["silk"] = 200
    p.setdefault("basis", {}).update({"tea": 20.0, "silk": 300.0})
    b = R["bank"]
    keep = b["whrob_chance"], b["mug_chance"]
    b["whrob_chance"], b["mug_chance"] = 1.0, 0.0
    try:
        news = []
        game._rob_warehouses(p, news, b, game.rng)
    finally:
        b["whrob_chance"], b["mug_chance"] = keep
    tea, silk = p["depots"]["shanghai"]["goods"].get("tea", 0), p["wh"].get("silk", 0)
    assert 400 * (1 - b["whrob_max"]) - 1 <= tea < 400 and 200 * (1 - b["whrob_max"]) - 1 <= silk < 200
    assert len(news) == 2 and any("Shanghai" in n for n in news)
    assert sum("warehouse" in line for line in p["log"]) >= 2
    assert p["books"]["cur"]["wh_robbed"] < 0


def test_robbery_odds_are_low():
    assert 0 < R["bank"]["whrob_chance"] <= 0.05


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
