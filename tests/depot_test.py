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


def test_sell_back_for_half():
    game, pid, p = fresh()
    f = R["fleet"]
    assert refused(game, pid, {"type": "depot", "op": "sell"})          # nothing open here yet
    game.act(pid, {"type": "depot", "op": "open"})
    game.act(pid, {"type": "depot", "op": "expand"})
    half = (f["depot_open_cost"] + f["depot_expand_cost"]) // 2
    assert game.view(pid)["me"]["depot_rules"]["sell"] == half
    p["cargo"]["tea"] = 5
    game.act(pid, {"type": "warehouse", "op": "store", "good": "tea", "qty": 5})
    assert refused(game, pid, {"type": "depot", "op": "sell"})          # stock must come out first
    game.act(pid, {"type": "warehouse", "op": "take", "good": "tea", "qty": 5})
    cash = p["cash"]
    game.act(pid, {"type": "depot", "op": "sell"})
    assert p["cash"] == cash + half and "shanghai" not in p["depots"]
    assert p["books"]["cur"]["depot"] == -half                          # spent the lot, got half back
    assert game.view(pid)["me"]["wh_here"] == "closed"
    game.act(pid, {"type": "depot", "op": "open"})                       # and it can be opened again
    assert game.view(pid)["me"]["wh_cap"] == f["depot_cap"]
    p["port"] = "hongkong"
    assert refused(game, pid, {"type": "depot", "op": "sell"})          # the home warehouse is not for sale


def test_rent_curve():
    r = engine.depot_rent
    assert [r(n) for n in range(5)] == [250, 750, 1500, 2500, 3750]


def test_rent_is_charged_monthly_and_empty_pays_half():
    game, pid, p = fresh()
    f = R["fleet"]
    game.act(pid, {"type": "depot", "op": "open"})
    p["bank"], p["cash"], p["debt"] = 0, 100000.0, 0.0
    game.s["turn"] = 0                                  # home is rent-free the first year; the away one is not
    (rent,) = game.warehouse_rents(p)
    assert rent["port"] == "shanghai" and rent["empty"] and rent["rent"] == f["rent_base"] * f["rent_empty_share"]
    game._pay_warehouse_rent(p)
    assert p["cash"] == 100000.0 - rent["rent"]
    assert p["books"]["cur"]["wh_rent"] == -rent["rent"] and p["books"]["cur"]["depot"] == -f["depot_open_cost"]
    p["depots"]["shanghai"]["goods"]["tea"] = 10
    assert game.warehouse_rents(p)[0]["rent"] == f["rent_base"]          # stock in it: full rent
    p["depots"]["shanghai"]["level"] = 2
    assert game.warehouse_rents(p)[0]["rent"] == engine.depot_rent(2) == 1500
    me = game.view(pid)["me"]
    assert me["wh_rent"]["here"] == 1500 and me["wh_rent"]["total"] == 1500
    assert me["wh_rent"]["more"] == engine.depot_rent(3) - 1500


def test_home_rent_starts_after_the_free_year():
    game, pid, p = fresh(port="hongkong")
    f = R["fleet"]
    p["wh"]["tea"] = 5
    level = (f["warehouse_cap"] - f["depot_cap"]) // f["depot_expand_cap"]
    game.s["turn"] = f["rent_home_free"] - 1
    assert game.warehouse_rents(p) == []
    assert game.view(pid)["me"]["wh_rent"]["home_free"] == 1
    game.s["turn"] = f["rent_home_free"]
    (rent,) = game.warehouse_rents(p)
    assert rent["home"] and rent["rent"] == int(round(engine.depot_rent(level) * f["rent_home_share"]))
    p["wh"].clear()
    assert game.warehouse_rents(p)[0]["rent"] == int(round(engine.depot_rent(level) * f["rent_home_share"] * f["rent_empty_share"]))


def test_unpaid_rent_goes_on_the_debt_and_selling_back_stops_it():
    game, pid, p = fresh()
    game.act(pid, {"type": "depot", "op": "open"})
    game.s["turn"] = 0
    p["cash"], p["bank"], p["debt"] = 0.0, 50.0, 1000.0
    rent = game.warehouse_rents(p)[0]["rent"]
    game._pay_warehouse_rent(p)
    assert p["cash"] == 0 and p["bank"] == 0 and p["debt"] == 1000.0 + rent - 50
    assert any("went on your debt" in line or "on your debt" in line for line in p["log"])
    p["cash"] = 5000.0
    game.act(pid, {"type": "depot", "op": "sell"})
    assert game.warehouse_rents(p) == []
    debt = p["debt"]
    game._pay_warehouse_rent(p)
    assert p["debt"] == debt


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
