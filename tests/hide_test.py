"""The crew hides a share before it is taken (owner's decision, 19 Nov 2026).

Whenever customs seize contraband, the Port Authority buys a cargo out, pirates plunder the hold or
the moneylender closes the books, the crew always gets a random rules.hide.min..max share out of
sight first (gold and opium hide rules.hide.dear_mult times as well). What they hide stays aboard.

Run from the project folder:  python -m pytest tests/hide_test.py
"""
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import config  # noqa: E402
import engine  # noqa: E402
from engine import Game, GOODS, PORTS, R  # noqa: E402


def setup(**rules):
    cfg = config.defaults()
    cfg["rules"]["weather"]["storm_chance"] = [0, 0, 0, 0]
    cfg["rules"]["weather"].update({"risk_min": 1.0, "risk_max": 1.0})
    cfg["rules"]["pirates"].update({"chance": 0.0})
    cfg["rules"]["liyuen"]["chance"] = 0.0
    cfg["rules"]["battle"]["match"] = False
    cfg["rules"]["battle"]["lowball"] = False
    cfg["rules"]["fleet"]["upkeep_enabled"] = False
    for path, value in rules.items():
        group, key = path.split("__")
        cfg["rules"][group][key] = value
    cfg, errors = config.validate(cfg)
    assert not errors, errors
    engine.configure(cfg)
    engine.MULT["pirates"] = 1.0
    engine.MULT["seizure"] = 1.0


def new_game(seed=1, cargo=None, cash=5000, guns=4):
    g = Game(seed=seed)
    g.join("Ann", "")
    g.act("p1", {"type": "start"}, present=g.s["order"])
    p = g.s["players"]["p1"]
    p["ships"][0]["guns"] = guns
    p["cargo"] = dict(cargo or {})
    p["basis"] = {k: GOODS[k]["base"] for k in p["cargo"]}
    p["cash"] = cash
    return g, p


def teardown_function(_fn):
    engine.configure(config.defaults())


def test_share_is_in_range_and_dear_goods_hide_better():
    setup()
    g, p = new_game()
    for seed in range(200):
        g.rng = random.Random(seed)
        hid = g._crew_hide(p, {"rice": 1000, "gold": 1000}, "pirates", "battle")
        assert 100 <= hid["rice"] <= 300, hid
        assert 150 <= hid["gold"] <= 450, hid
    # even a single unit is saved now and then, never more than there is
    got = [g._crew_hide(p, {"tea": 1}, "pirates", "battle").get("tea", 0) for _ in range(400)]
    assert set(got) == {0, 1}


def test_switched_off_hides_nothing():
    setup(hide__enabled=False)
    g, p = new_game()
    assert g._crew_hide(p, {"rice": 1000}, "pirates", "battle") == {}
    setup(hide__pirates=False)
    assert g._crew_hide(p, {"rice": 1000}, "pirates", "battle") == {}
    assert g._crew_hide(p, {"rice": 1000}, "customs", "voyage")


def test_pirates_plunder_less_and_the_reckoning_shows_it():
    setup(pirates__chance=1.0, pirates__fleet_min=6, pirates__fleet_base=6, pirates__fleet_max=6,
          pirates__run_base=0.0, pirates__run_fast=0.0, pirates__run_round=0.0, pirates__gun_hit=0.0,
          pirates__hit=0.0, pirates__plunder_min=1.0, pirates__plunder_max=1.0, battle__parley=False,
          customs__enabled=False)
    g, p = new_game(cargo={"rice": 25, "tea": 25})
    dest = next(k for k in PORTS if k != p["port"])
    g.act("p1", {"type": "sail", "dest": dest, "orders": "run"}, present=["p1"])
    g.maybe_advance({"p1"})
    for _ in range(6):
        g.act("p1", {"type": "sea", "choice": "run"}, present=["p1"])
    f = p["fights"][0]
    assert f["outcome"] == "plundered"
    # running every round, without the crew they would have taken all of it
    kept = {h["good"]: h["qty"] for h in f["hid"]}
    assert kept and all(2 <= q <= 8 for q in kept.values()), kept
    assert p["cargo"] == kept
    assert any("your crew stowed" in line for line in p["log"])


def test_customs_seizure_misses_what_the_crew_hid():
    setup(contraband__seize_chance=1.0, contraband__seize_banned=1.0, contraband__seize_rep_relief=0.0,
          customs__enabled=False)
    for seed in range(30):
        g, p = new_game(seed=seed)
        dest = next(k for k in PORTS if k != p["port"] and g.at_risk(k))
        risky = sorted(g.at_risk(dest))
        p["cargo"] = {k: 20 for k in risky}
        p["basis"] = {k: GOODS[k]["base"] for k in risky}
        g.act("p1", {"type": "sail", "dest": dest, "orders": "run"}, present=["p1"])
        assert g.maybe_advance({"p1"})
        if p["port"] != dest:
            continue                                   # blown off course
        assert p["cargo"], "the crew always hides something from 20 units"
        assert all(2 <= q <= 9 for q in p["cargo"].values()), p["cargo"]
        assert any("under the ballast" in line for line in p["log"])
        return
    raise AssertionError("never made port")


def test_desk_buyout_leaves_the_hidden_units_aboard_untaxed():
    base = config.defaults()
    base["rules"]["customs"]["spot_home"] = base["rules"]["customs"]["spot_shares"] = 0.0
    base["rules"]["start"]["where"] = "home"
    base["rules"]["pirates"]["chance"] = 0.0
    base["rules"]["liyuen"]["chance"] = 0.0
    base["rules"]["weather"]["storm_chance"] = [0, 0, 0, 0]
    engine.configure(base)
    for seed in range(40):
        g = Game(seed=seed)
        g.join("Ann", "")
        g.admin("start", {})
        p = g.s["players"]["p1"]
        p["cash"] = 50000
        g.act("p1", {"type": "buy", "good": "tea", "qty": 50}, present=["p1"])
        g.act("p1", {"type": "sail", "dest": "calcutta", "orders": "run"}, present=["p1"])
        assert g.maybe_advance({"p1"})
        cu = p.get("customs")
        if not cu or cu.get("status") != "declare":
            continue
        g.customs_odds = lambda cx, ln, d, bribe_mult: (1.0, 0.0)     # she buys every line
        cu["box"] = 10 ** 9
        g.act("p1", {"type": "customs_declare", "values": {ln["good"]: ln["value"] for ln in cu["lines"]}},
              present=["p1"])
        res = next(r for r in p["customs"]["result"]["lines"] if r["good"] == "tea")
        assert res["outcome"] == "buyout" and res.get("hid"), res
        assert 5 <= res["hid"] <= 15 and res["units"] == 50 - res["hid"]
        assert res["tax"] == 0
        assert p["cargo"].get("tea") == res["hid"]
        assert any("slipped" in line for line in p["log"])
        return
    raise AssertionError("never reached her desk")


def test_bankruptcy_keeps_a_little_silver_and_cargo():
    setup(bank__bankrupt_enabled=True, bank__bankrupt_months=1, bank__bankrupt_stake=2000)
    g, p = new_game(cargo={"gold": 5, "rice": 30}, cash=10000)
    p["debt"] = 1e7
    g.resolve("host")
    assert p["bankruptcies"] == 1 and p["debt"] == 0 and p["bank"] == 0
    assert 2000 + 1000 <= p["cash"] <= 2000 + 3000, p["cash"]
    assert p["cargo"] and sum(p["cargo"].values()) <= g.capacity(p)
    assert p["cargo"].get("rice", 0) <= 30 and p["cargo"].get("gold", 0) <= 5
    assert any("squirrelled away" in line for line in p["log"])
