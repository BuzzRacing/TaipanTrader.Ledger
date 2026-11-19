"""Spiteful crews (19 Nov 2026): some enemy crews aim for the dearest cargo aboard.

Rolled once at the sighting (rules.battle.spite_chance; spite_chance_lord for Li Yue's war junks) on
dice of their own. A spiteful crew hits the hold spite_hold times as often, and a hold hit lands on the
dearest good aboard spite_aim of the time. Powder and the enemy say so at the sighting.

Run from the project folder:  python tests/spite_test.py
"""
import copy
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from battle_test import setup, new_game, sail  # noqa: E402
from engine import GOODS, R  # noqa: E402

CARGO = {"rice": 40, "tea": 20, "silk": 10, "opium": 6}
DEAREST = max(CARGO, key=lambda g: GOODS[g]["base"])


def fight_for(g, pid="p1"):
    return {"kind": "pirates", "n": 4, "hit": 1.0, "dmg": [5, 5], "seed": 4242, "hp": [50] * 4}


def test_a_spiteful_crew_shoots_the_dearest_good():
    setup(battle__spite_chance=1.0, battle__spite_aim=1.0, battle__cargo_hit=1.0, battle__gun_loss=0.0)
    g = new_game(names=("Ann",), cargo=CARGO)
    p = g.s["players"]["p1"]
    b = fight_for(g)
    g._spite_roll(p, b)
    assert b.get("spite") and b["spite"]["aim"] == DEAREST, b
    before = dict(p["cargo"])
    hits = g._enemy_fire(p, b, [1, 1, 1, 1])
    assert hits and all(h.get("aimed") and list(h["cargo"]) == [DEAREST] for h in hits if h.get("cargo")), hits
    for k in CARGO:
        if k != DEAREST:
            assert p["cargo"].get(k) == before[k], "only the dearest good is shot away"
    assert p["cargo"].get(DEAREST, 0) < before[DEAREST]


def test_an_ordinary_crew_is_not_spiteful():
    setup(battle__spite_chance=0.0)
    g = new_game(names=("Ann",), cargo=CARGO)
    b = fight_for(g)
    g._spite_roll(g.s["players"]["p1"], b)
    assert "spite" not in b
    setup(battle__spite=False, battle__spite_chance=1.0)
    g = new_game(names=("Ann",), cargo=CARGO)
    b = fight_for(g)
    g._spite_roll(g.s["players"]["p1"], b)
    assert "spite" not in b, "the switch turns it off"


def test_an_empty_hold_draws_no_spite():
    setup(battle__spite_chance=1.0)
    g = new_game(names=("Ann",), cargo={})
    b = fight_for(g)
    g._spite_roll(g.s["players"]["p1"], b)
    assert "spite" not in b


def test_spite_doubles_the_hold_hits():
    setup(battle__cargo_hit=0.2, battle__spite_hold=2.0)
    assert abs(g_hold({"spite": {"aim": "gold"}}) - 0.4) < 1e-9 and abs(g_hold({}) - 0.2) < 1e-9


def g_hold(b):
    from engine import Game
    return Game._hold_chance(b)


def test_powder_and_the_enemy_call_it_at_the_sighting():
    setup(battle__spite_chance=1.0)
    g = new_game(names=("Ann",), cargo=CARGO)
    sail(g, present=["p1"])
    p = g.s["players"]["p1"]
    frames = p["battle"]["beat"]["frames"]
    spite = [f for f in frames if f.get("mood") == "sly" and GOODS[DEAREST]["name"] in f["cap"]]
    assert spite, frames
    assert spite[0].get("say") and spite[0].get("foe") and spite[0]["foe_mood"] == "sly"
    assert frames[1].get("foe") != spite[0]["foe"], "the price stays the second picture"
    assert any(GOODS[DEAREST]["name"] in line for line in p["log"]), p["log"]


def test_an_ordinary_crew_rolls_exactly_as_before():
    """The spite dice are their own: with no spiteful crew the fight comes out as it did before."""
    results = []
    for rules in ({"battle__spite": False}, {"battle__spite_chance": 0.0}):
        setup(**rules)
        g = new_game(seed=7, names=("Ann", "Bo"), cargo=CARGO)
        g.s["game_id"] = "spite-test"              # the prize dice are seeded from it
        for pid in g.s["order"]:
            g.act(pid, {"type": "sail", "dest": "shanghai", "orders": "fight"}, present=[])
        g.resolve("all_ready", [])
        state = copy.deepcopy(g.s)
        assert state["turn"] == 1
        results.append(repr(sorted((k, v["cash"], v["cargo"], [s["hull"] for s in v["ships"]], v["books"])
                                   for k, v in state["players"].items())))
    assert results[0] == results[1]


def test_no_spoken_spite_line_has_a_number():
    from strings import EN
    for k, v in EN.items():
        if ".spite." in k or ".cargo_aimed." in k:
            assert not any(ch.isdigit() for ch in v), k


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print("ok", fn.__name__)
    print(len(tests), "pass")
