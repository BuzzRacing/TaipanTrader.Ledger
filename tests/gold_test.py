"""Gold: legal cargo that a port's ban sometimes covers.

Run from the project folder:  python tests/gold_test.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import engine  # noqa: E402
from engine import Game, GOODS, PORTS  # noqa: E402


def ban(game, port, gold):
    game.s["crackdown"][port] = 3
    game.s["ban_goods"][port] = ["gold"] if gold else []


def test_gold_is_a_cargo():
    assert "gold" in GOODS and not GOODS["gold"]["contraband"]
    assert "gold" in engine.sometimes_contraband()
    assert "gold" not in engine.contraband()


def test_gold_legal_without_ban():
    game = Game(seed=1)
    port = next(iter(PORTS))
    game.s["crackdown"].clear()
    assert "gold" not in game.banned(port)
    assert "gold" not in game.at_risk(port)


def test_ban_may_or_may_not_cover_gold():
    game = Game(seed=2)
    port = next(k for k in PORTS if not PORTS[k].get("no_ban"))
    ban(game, port, gold=False)
    assert "gold" not in game.banned(port) and "opium" in game.banned(port)
    plain = game._target(port, "gold")
    ban(game, port, gold=True)
    assert "gold" in game.banned(port) and "gold" in game.at_risk(port)
    assert game._target(port, "gold") > plain  # banned gold fetches more


def test_bans_sometimes_cover_gold():
    covered = 0
    for seed in range(200):
        game = Game(seed=seed)
        covered += "gold" in game._roll_ban_goods("hongkong")
    assert 40 < covered < 160, covered  # about half at the default 50%


def test_seizure_takes_banned_gold():
    game = Game(seed=3)
    port = next(k for k in PORTS if not PORTS[k].get("no_ban"))
    ban(game, port, gold=True)
    p = {"cargo": {"gold": 10, "tea": 5}}
    risky = game.at_risk(port)
    taken = {g: p["cargo"].pop(g) for g in risky if p["cargo"].get(g)}
    assert taken == {"gold": 10} and p["cargo"] == {"tea": 5}
    assert engine.names_of(list(taken)) == "Gold"


def test_old_saves_still_load():
    game = Game(seed=4)
    state = dict(game.s)
    state.pop("ban_goods", None)
    state["crackdown"] = {"hongkong": 2}
    again = Game(state=state, seed=5)
    assert again.s["ban_goods"] == {}
    assert "gold" not in again.banned("hongkong")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
