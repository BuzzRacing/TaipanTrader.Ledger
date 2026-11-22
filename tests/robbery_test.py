"""The Robbery Story (owner's request, 22 Nov 2026; robbery.py).

One screen when the Captain is robbed, but ONLY when the month has no other story (no Sea Battle, jail, storm, Legend,
honour story or promotion). Run from the project folder:  python -m pytest tests/robbery_test.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import config  # noqa: E402
import engine  # noqa: E402
import robbery  # noqa: E402
import strings  # noqa: E402
from engine import Game, GOODS, PORTS  # noqa: E402


def setup(**rules):
    cfg = config.defaults()
    cfg["rules"]["weather"]["storm_chance"] = [0, 0, 0, 0]
    cfg["rules"]["pirates"].update({"chance": 0.0})
    cfg["rules"]["liyuen"]["chance"] = 0.0
    cfg["rules"]["fleet"]["upkeep_enabled"] = False
    cfg["rules"]["customs"]["enabled"] = False
    cfg["rules"]["jail"]["hostile_chance"] = 0.0
    cfg["rules"]["bank"].update({"mug_chance": 0.0, "mug_threshold": 100})
    cfg["rules"]["bank"]["whrob_chance"] = 0.0
    for path, value in rules.items():
        group, key = path.split("__")
        cfg["rules"][group][key] = value
    cfg, errors = config.validate(cfg)
    assert not errors, errors
    engine.configure(cfg)


def new_game(seed=1, cash=5000):
    """A started game, one quiet month in: the first month brings the Captain's first promotion, so it is played and
    closed here; the months the tests care about then have no story of their own."""
    g = Game(seed=seed)
    g.join("Ann", "")
    g.act("p1", {"type": "start"}, present=g.s["order"])
    p = g.s["players"]["p1"]
    g.resolve("all_ready", {"p1"})
    p["promotions"] = []
    p.pop("robbery", None)
    p["cash"] = cash
    return g, p


def hot(**rules):
    """Switch a rule on once the game is past its first month (engine.R is read live)."""
    for path, value in rules.items():
        group, key = path.split("__")
        engine.R[group][key] = value


def teardown_function(_fn):
    engine.configure(config.defaults())


def month(g):
    g.resolve("all_ready", {"p1"})


def test_a_mugging_is_told_as_one_screen():
    setup()
    g, p = new_game(cash=3000)
    hot(bank__mug_chance=1.0)
    month(g)
    r = p.get("robbery")
    assert r and r["kind"] == "street" and r["silver"] > 0 and r["port"] == p["port"]
    assert r["left"] == int(p["cash"]) and "rob_cand" not in p
    v = g.view("p1")["me"]["robbery"]
    assert v and v["id"] == r["id"] and v["silver"] == r["silver"]
    assert any("feather" in line for line in p["log"]), "the Captain's Log still has its line"
    g.act("p1", {"type": "robbery_ack"}, present=["p1"])
    assert "robbery" not in p and g.view("p1")["me"]["robbery"] is None


def test_a_warehouse_break_in_names_what_was_taken():
    setup()
    g, p = new_game()
    hot(bank__whrob_chance=1.0)
    p["wh"] = {"rice": 100, "silk": 20}
    month(g)
    r = p.get("robbery")
    assert r and r["kind"] == "house" and r["goods"] and r["qty"] == sum(r["goods"].values())
    assert r["value"] > 0 and 0 < r["pct"] <= 100
    assert set(r["goods"]) <= {"rice", "silk"} and p["wh"]["rice"] < 100


def test_no_robbery_story_when_the_month_has_another_story():
    for other in ({"storm": {"card": True}}, {"legend": {"tale": "x"}}, {"jail_freed": {"port": "x"}},
                  {"honour_queue": [{"id": 1}]}, {"promotions": [{"id": 1}]}, {"robbery": {"id": 9}}):
        setup()
        g, p = new_game(cash=3000)
        hot(bank__mug_chance=1.0)
        p.update(other)
        month(g)
        mine = p.get("robbery")
        assert mine is None or mine == other.get("robbery"), other
        assert any("feather" in line for line in p["log"]), "it is still in the log: " + str(other)


def test_a_sea_battle_this_month_keeps_the_robbery_in_the_log():
    setup()
    g, p = new_game()
    p["rob_cand"] = [{"kind": "street", "port": p["port"], "value": 500, "silver": 500, "left": 100}]
    p["fights"] = [{"outcome": "won"}]
    assert robbery.settle(g, p) is None and "robbery" not in p and "rob_cand" not in p


def test_a_jailed_captain_is_not_told_a_robbery_story():
    setup()
    g, p = new_game()
    p["rob_cand"] = [{"kind": "house", "port": p["port"], "value": 500, "goods": {"rice": 5}, "qty": 5, "pct": 10}]
    p["jail"] = {"port": p["port"], "months": 3, "left": 2, "charge": "slip", "charges": ["slip"], "since": 0, "served": 1}
    assert robbery.settle(g, p) is None and "robbery" not in p


def test_the_bigger_loss_is_the_one_told_and_a_quiet_month_opens_it():
    setup()
    g, p = new_game()
    p["rob_cand"] = [{"kind": "street", "port": p["port"], "value": 300, "silver": 300, "left": 10},
                     {"kind": "house", "port": p["port"], "value": 900, "goods": {"rice": 5}, "qty": 5, "pct": 10}]
    s = robbery.settle(g, p)
    assert s and s["kind"] == "house" and s["id"] == 1 and p["robbery"] == s and "rob_cand" not in p
    g.act("p1", {"type": "robbery_ack"}, present=["p1"])
    p["rob_cand"] = [{"kind": "street", "port": p["port"], "value": 1, "silver": 1, "left": 0}]
    assert robbery.settle(g, p)["id"] == 2


def test_switched_off():
    setup()
    engine.R["robbery"] = {"enabled": False}
    try:
        g, p = new_game(cash=3000)
        hot(bank__mug_chance=1.0)
        month(g)
        assert "robbery" not in p and "rob_cand" not in p
    finally:
        engine.R.pop("robbery", None)


def test_the_wording_is_there_and_family_twins_keep_their_names():
    import re
    names = lambda t: sorted(set(re.findall(r"\{(\w+)\}", t)))   # noqa: E731
    for key in ("rob.eyebrow.street", "rob.eyebrow.house", "rob.title.street", "rob.title.house", "rob.btn",
                "rob.tile.silver", "rob.tile.left", "rob.tile.units", "rob.tile.value", "rob.taken", "m.robbery_ack"):
        assert key in strings.EN, key
    assert any(k.startswith("rob.cap.street.") for k in strings.EN) and any(k.startswith("rob.cap.house.") for k in strings.EN)
    for key, clean in strings.FAMILY.items():
        if key.startswith("rob."):
            assert names(clean) == names(strings.EN[key]), key
