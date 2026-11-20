"""Perishable cargo rots (owner's decisions, 20 Nov 2026; rot.py).

Run from the project folder:  python -m pytest tests/rot_test.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import config  # noqa: E402
import engine  # noqa: E402
import jail  # noqa: E402
import rot  # noqa: E402
from engine import Game, GOODS  # noqa: E402


def setup(**rules):
    cfg = config.defaults()
    cfg["rules"]["weather"]["storm_chance"] = [0, 0, 0, 0]
    cfg["rules"]["weather"].update({"risk_min": 1.0, "risk_max": 1.0, "offcourse": 0.0})
    cfg["rules"]["pirates"].update({"chance": 0.0})
    cfg["rules"]["liyuen"]["chance"] = 0.0
    cfg["rules"]["battle"]["match"] = False
    cfg["rules"]["fleet"]["upkeep_enabled"] = False
    cfg["rules"]["bank"]["mug_chance"] = 0.0
    cfg["rules"]["customs"]["enabled"] = False
    cfg["rules"]["jail"]["hostile_chance"] = 0.0
    for path, value in rules.items():
        group, key = path.split("__")
        cfg["rules"][group][key] = value
    cfg, errors = config.validate(cfg)
    assert not errors, errors
    engine.configure(cfg)


def new_game(seed=1, cash=50000, cargo=None):
    g = Game(seed=seed)
    g.join("Ann", "")
    g.act("p1", {"type": "start"}, present=g.s["order"])
    p = g.s["players"]["p1"]
    p["cargo"] = dict(cargo or {})
    p["basis"] = {k: GOODS[k]["base"] for k in p["cargo"]}
    p["cash"] = cash
    return g, p


def teardown_function(_fn):
    engine.configure(config.defaults())


def month(g):
    g.resolve("all_ready", {"p1"})


def test_the_defaults_and_the_shared_list():
    setup()
    r = rot.rules()
    assert r["enabled"] and r["grace_months"] == 3 and r["min"] == 0.05 and r["max"] == 0.15
    assert rot.perishables() == ["rice", "tea", "spices"]
    assert rot.perishables() == [k for k in jail.rules()["perishables"]]       # one list for both rules


def test_new_units_blend_the_age_down():
    setup()
    g, p = new_game(cargo={"tea": 100})
    p["age"] = {"tea": 4.0}
    rot.add(p, "tea", 100)                       # 100 old + 100 new: (4*100 + 0*100) / 200
    assert abs(p["age"]["tea"] - 2.0) < 1e-9
    p["cargo"]["tea"] = 200
    rot.add(p, "tea", 200)
    assert abs(p["age"]["tea"] - 1.0) < 1e-9


def test_buying_goes_through_the_blend_and_other_goods_have_no_age():
    setup()
    g, p = new_game(cargo={"tea": 20})                           # the starting hold takes 50
    p["age"] = {"tea": 3.0}
    g.act("p1", {"type": "buy", "good": "tea", "qty": 20}, present=["p1"])
    assert abs(p["age"]["tea"] - 1.5) < 1e-9
    g.act("p1", {"type": "buy", "good": "silk", "qty": 5}, present=["p1"])
    assert "silk" not in p["age"]


def test_it_is_safe_through_the_grace_period_then_a_share_rots():
    setup()
    g, p = new_game(cargo={"tea": 1000})
    p["age"] = {"tea": 0.0}
    for n in (1, 2, 3):
        month(g)
        assert p["cargo"]["tea"] == 1000, "month %d" % n          # safe for 3 month-ends aboard
        assert abs(p["age"]["tea"] - n) < 1e-9
    month(g)                                                       # the 4th: past the grace period
    left = p["cargo"]["tea"]
    assert 850 <= left <= 950, left                                # 5-15% of 1000 rotted
    assert abs(p["age"]["tea"] - 4) < 1e-9
    month(g)
    assert p["cargo"]["tea"] < left                                # and again every month after


def test_the_loss_is_written_off_at_cost_and_the_log_says_so():
    setup()
    g, p = new_game(cargo={"tea": 1000})
    p["age"] = {"tea": 3.5}
    cash = p["cash"]
    month(g)
    lost = 1000 - p["cargo"]["tea"]
    assert lost > 0
    last = g._books(p)["last"]
    assert abs(last["lines"]["rot"] + lost * GOODS["tea"]["base"]) < 1.0
    assert p["cash"] == cash                                       # nothing paid, nothing refunded
    assert any("tea" in x.lower() or "Tea" in x for x in last["log"])


def test_only_perishables_rot_and_the_list_is_the_jails_list():
    setup()
    g, p = new_game(cargo={"tea": 500, "silk": 500})
    p["age"] = {"tea": 9.0, "silk": 9.0}
    month(g)
    assert p["cargo"]["silk"] == 500 and "silk" not in p["age"]
    assert p["cargo"]["tea"] < 500
    setup(jail__perishables=["porcelain"])                         # Maijiuana is the key porcelain
    g, p = new_game(cargo={"tea": 500, "porcelain": 500})
    p["age"] = {"tea": 9.0, "porcelain": 9.0}
    month(g)
    assert p["cargo"]["tea"] == 500 and p["cargo"]["porcelain"] < 500


def test_the_clock_stops_when_the_hold_is_empty_and_warehouses_do_not_age():
    setup()
    g, p = new_game(cargo={"tea": 100})
    p["age"] = {"tea": 2.0}
    p["wh"] = {"rice": 400}
    del p["cargo"]["tea"]
    month(g)
    assert "tea" not in p["age"] and "rice" not in p["age"]
    assert p["wh"]["rice"] == 400


def test_jail_replaces_rot_and_the_age_still_advances():
    setup()
    g, p = new_game(cargo={"tea": 1000})
    p["age"] = {"tea": 10.0}
    assert rot.month(g, p, None, skip=True) == {}
    assert p["cargo"]["tea"] == 1000 and abs(p["age"]["tea"] - 11.0) < 1e-9


def test_a_jailed_month_is_not_hit_twice(monkeypatch=None):
    setup(jail__spoil_min=0.0, jail__spoil_max=0.0)                 # the jail's own spoilage off: only rot could hit
    g, p = new_game(cargo={"tea": 1000})
    p["age"] = {"tea": 10.0}
    p["jail"] = {"port": p["port"], "months": 3, "left": 3, "since": g.s["turn"], "served": 0, "fresh": False,
                 "drunk": 0, "spoiled": {}}
    assert jail.jailed(p)
    month(g)
    assert p["cargo"]["tea"] == 1000                                # inside: rot skipped
    assert abs(p["age"]["tea"] - 11.0) < 1e-9


def test_switching_it_off_changes_nothing():
    setup(rot__enabled=False)
    g, p = new_game(cargo={"tea": 1000})
    p["age"] = {"tea": 9.0}
    month(g)
    assert p["cargo"]["tea"] == 1000
    assert g.view("p1")["me"]["rot"] == {"on": False}


def test_the_player_screen_gets_the_ages_and_the_grace_period():
    setup()
    g, p = new_game(cargo={"tea": 100, "silk": 10})
    p["age"] = {"tea": 2.0}
    v = g.view("p1")["me"]["rot"]
    assert v == {"on": True, "grace": 3, "age": {"tea": 2.0}}


def test_same_game_same_rot():
    out = []
    for _ in range(2):
        setup()
        g, p = new_game(seed=7, cargo={"tea": 777, "rice": 321})
        g.s["game_id"] = "fixed"                       # the dice are seeded from the game's id
        p["age"] = {"tea": 5.0, "rice": 5.0}
        month(g)
        out.append((p["cargo"]["tea"], p["cargo"]["rice"]))
    assert out[0] == out[1]


def test_old_saves_without_ages_start_fresh():
    setup()
    g, p = new_game(cargo={"tea": 1000})
    p.pop("age", None)
    month(g)
    assert p["cargo"]["tea"] == 1000 and abs(p["age"]["tea"] - 1.0) < 1e-9
