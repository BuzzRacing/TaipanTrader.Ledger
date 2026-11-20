"""The jail (owner's decisions, 19 Nov 2026; project doc "SeaTrader Jail").

Run from the project folder:  python -m pytest tests/jail_test.py
"""
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import config  # noqa: E402
import engine  # noqa: E402
import jail  # noqa: E402
from engine import Game, GOODS, PORTS  # noqa: E402


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


def new_game(seed=1, cash=5000, cargo=None):
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
    """Turn the month with the one captain present (sails if she gave orders)."""
    g.resolve("all_ready", {"p1"})


def sail_to(g, p, dest, **kw):
    g.act("p1", dict({"type": "sail", "dest": dest, "orders": "run"}, **kw), present=["p1"])
    month(g)


def test_rock_bottom_standing_is_arrest_on_arrival_and_the_month_is_served():
    setup(jail__drink_min=0.10, jail__drink_max=0.10)
    g, p = new_game(cash=10000, cargo={"rice": 100, "silk": 10})
    dest = next(k for k in PORTS if k != p["port"])
    p["rep"][dest] = 0.0
    sail_to(g, p, dest)
    assert p["port"] == dest
    assert jail.jailed(p) and p["jail"]["charge"] == "standing" and p["jail"]["left"] == 1
    assert p["ready"], "a jailed House is marked as sailed"
    assert any("locked up" in n for n in g.s["news"]), "the arrest is in the News for every House"
    v = g.view("p1")
    assert v["me"]["jail"]["jail"]["port"] == dest and v["players"][0]["jailed"]
    # nothing can be done from a cell
    for a in ({"type": "sail", "dest": p["home"] if "home" in p else dest, "orders": "run"},
              {"type": "unsail"}, {"type": "buy", "good": "rice", "qty": 1}):
        try:
            g.act("p1", a, present=["p1"])
        except engine.GameError as e:
            assert "gaol" in str(e)
        else:
            raise AssertionError("acted from a cell: {}".format(a))
    before = p["cash"]
    month(g)                                            # the month inside
    assert p["port"] == dest, "the fleet stays at anchor"
    assert not jail.jailed(p)
    assert p["jail_last"]["drunk"] == int(before * 0.10), "the crew drank 10% of the silver aboard"
    assert p["cargo"]["silk"] == 10 and p["cargo"]["rice"] < 100, "rice spoils, silk keeps"
    assert p["rep"][dest] >= 10, "standing lifted to the release floor"
    assert not p["ready"]
    assert any("swings open" in line for line in p["log"])


def test_three_months_counts_three_month_ends_and_bank_is_safe():
    setup()
    g, p = new_game(cash=0)
    p["bank"] = 50000
    jail.lock_up(g, p, 3, "debt", fresh=False)
    for left in (2, 1, 0):
        month(g)
        assert (p["jail"] or {}).get("left", 0) == left
    assert p["bank"] >= 50000
    assert not jail.jailed(p)


def test_the_plea_three_choices_and_the_three_month_deal():
    setup()
    g, p = new_game(cash=100000)
    assert jail.offer_plea(g, p, 40000, "desk", p["port"], "pa_fine")
    opts = p["plea"]["opts"]
    assert [o["months"] for o in opts] == [0, 1, 3]
    assert 0.40 <= opts[1]["share"] <= 0.60 and 0.10 <= opts[2]["share"] <= 0.25
    try:
        g.act("p1", {"type": "sail", "dest": next(k for k in PORTS if k != p["port"]), "orders": "run"}, present=["p1"])
    except engine.GameError:
        pass
    else:
        raise AssertionError("sailed without answering the plea")
    g.act("p1", {"type": "plea", "months": 3}, present=["p1"])
    assert p["cash"] == 100000 - opts[2]["pay"]
    assert jail.jailed(p) and p["jail"]["left"] == 3 and not p["jail"].get("fresh")
    assert p["ready"]


def test_paying_in_full_and_an_unanswered_plea():
    setup()
    g, p = new_game(cash=100000)
    jail.offer_plea(g, p, 40000, "contraband", p["port"], "fines")
    g.act("p1", {"type": "plea", "months": 0}, present=["p1"])
    assert p["cash"] == 60000 and not jail.jailed(p) and not jail.pending(p)
    jail.offer_plea(g, p, 30000, "slip", p["port"], "dues")
    month(g)
    assert p["cash"] <= 30000 and not jail.pending(p) and not jail.jailed(p)


def test_small_fines_get_no_plea():
    setup()
    g, p = new_game(cash=1000000)
    assert not jail.offer_plea(g, p, 500, "desk", p["port"], "pa_fine")
    assert not jail.offer_plea(g, p, 20000, "desk", p["port"], "pa_fine"), "under 5% of worth and affordable"


def test_caught_slipping_out_keeps_the_fleet_in_port():
    setup(dues__slip_caught=1.0, jail__slip_chance=1.0)
    g, p = new_game(cash=5000)
    here = p["port"]
    dest = next(k for k in PORTS if k != here)
    sail_to(g, p, dest, slip=True)
    assert p["port"] == here and jail.jailed(p) and p["jail"]["charge"] == "slip"


def test_contraband_seized_can_mean_jail_and_the_desk_is_filed_for_you():
    setup(contraband__seize_chance=1.0, contraband__seize_banned=1.0, contraband__seize_rep_relief=0.0,
          jail__contraband_chance=1.0, hide__enabled=False)
    for seed in range(30):
        g, p = new_game(seed=seed)
        dest = next((k for k in PORTS if k != p["port"] and g.at_risk(k)), None)
        if not dest:
            continue
        p["cargo"] = {k: 5 for k in g.at_risk(dest)}
        sail_to(g, p, dest)
        if p["port"] != dest:
            continue
        assert jail.jailed(p) and p["jail"]["charge"] == "contraband"
        assert not p.get("customs")
        return
    raise AssertionError("never made port")


def test_bankruptcy_is_three_months_at_home():
    setup()
    g, p = new_game()
    news = []
    g._bankrupt(p, news)
    assert jail.jailed(p) and p["jail"]["left"] == 3 and p["jail"]["port"] == engine.home_of(p)


def test_switched_off():
    setup(jail__enabled=False)
    g, p = new_game(cash=100000)
    dest = next(k for k in PORTS if k != p["port"])
    p["rep"][dest] = 0.0
    sail_to(g, p, dest)
    assert not jail.jailed(p)
    assert not jail.offer_plea(g, p, 99999999, "desk", p["port"], "pa_fine")


def test_difficulty_scales_the_odds():
    setup()
    engine.MULT["jail"] = 0.5
    assert jail.mult() == 0.5
    engine.MULT.pop("jail")
    engine.MULT["seizure"] = 1.5
    assert jail.mult() == 1.5, "a saved preset without the jail column reads the level"
