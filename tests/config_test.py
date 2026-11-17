"""Checks that the game still plays when the Admin settings are changed,
including in the middle of a game.

Run from the project folder:  python tests/config_test.py
"""
import copy
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import config  # noqa: E402
import engine  # noqa: E402
import strings  # noqa: E402
from engine import Game, GameError  # noqa: E402
from sim_test import check, random_bot  # noqa: E402


def variant():
    c = config.defaults()
    c["content"]["rating"] = "family"
    c["difficulty"]["level"] = "hard"
    c["brand"].update({"currency": "£", "lender": "Uncle Chen", "pirate": "Madame Ching"})
    del c["ports"]["manila"]
    del c["goods"]["general"]
    del c["ships"]["lorcha"]
    c["goods"]["cotton"] = {"name": "Cotton", "family_name": "", "base": 40, "vol": 0.08, "depth": 600, "contraband": True}
    c["ports"]["macao"] = {"name": "Macao", "lon": 113.5, "lat": 22.2, "region": "china", "shipyard": True,
                           "no_ban": False, "label_left": True, "mods": {"cotton": 1.4, "general": 2}}
    c["ships"]["sloop"] = {"name": "Sloop", "hold": 90, "hull": 80, "slots": 6, "price": 5000, "fast": True}
    c["rules"]["game"].update({"home": "macao", "lengths": [1, 2], "default_years": 2})
    c["rules"]["start"].update({"ship": "sloop", "guns": 99, "cash": 10000})
    c["rules"]["wreck"]["ship"] = "sloop"
    c["rules"]["pirates"]["chance"] = 0.9
    c["rules"]["events"].update({"ban_chance": 0.6, "shock_chance": 0.9})
    return c


def play(game, turns, seed):
    pids = list(game.s["order"])
    for _ in range(turns):
        if game.s["phase"] != "port":
            break
        for pid in pids:
            random_bot(game, pid, game.rng)
        assert game.maybe_advance(set(pids))
        check(game)
        for pid in pids:
            json.dumps(game.view(pid, pids))
        json.dumps(game.admin_view(pids))
        json.dumps(engine.static_data())


if __name__ == "__main__":
    # 1. every default passes its own checks
    cfg, errors = config.validate(copy.deepcopy(config.DEFAULTS))
    assert not errors, errors
    # 2. nonsense is refused rather than applied
    for bad in ({"rules": {"start": {"cash": "lots"}}}, {"rules": {"game": {"home": "atlantis"}}},
                {"goods": {}}, {"ports": {"Bad Key": {}}}, {"theme": {"colors": {"paper": "red"}}}, "junk"):
        assert config.validate(bad)[1], bad
    # 3. every wording key formats without error under both ratings
    for rating in ("historical", "family"):
        c = config.defaults()
        c["content"]["rating"] = rating
        engine.configure(c)
        for key in strings.EN:
            assert "{" not in engine.tx(key, **{k: 1 for k in (
                "n name firm list years free cost cash qty good what port ship price months amount rate value "
                "lost origin dest weather enemy orders rounds s booty points debt worth good_lower fine gain "
                "url date margin rep buy sell used cap balance room hold_used hold type hull max guns slots "
                "yards pct names turns ports how " + "a b buys dmg first last o off place players ran rank result sales sunk v visits when won " +
                "total paid owed declared profit tax caught chance level from to after now cargo line goods value base "
                "age distance gap").split()}), key
    # 4. a changed world plays to the end
    cfg, errors = config.validate(variant())
    assert not errors, errors
    engine.configure(cfg)
    game = Game(seed=7)
    for name in ("Ann", "Bo", "Cy"):
        game.join(name, "")
    assert game.s["players"]["p1"]["port"] == "macao" and game.s["players"]["p1"]["ships"][0]["guns"] == 6
    game.admin("start", {})
    play(game, 30, 7)
    assert game.s["phase"] == "ended"
    # 5. settings changed under a running game: the game adapts
    engine.configure(config.defaults())
    game = Game(seed=3)
    for name in ("Ann", "Bo", "Cy"):
        game.join(name, "")
    game.admin("start", {})
    play(game, 10, 3)
    engine.configure(cfg)
    game.reconcile()
    check(game)
    assert all(p["port"] in engine.PORTS for p in game.s["players"].values())
    play(game, 10, 3)
    engine.configure(config.defaults())
    game = Game(state=json.loads(json.dumps(game.s)), seed=4)
    check(game)
    play(game, 10, 4)
    for op, a in (("price", {"port": "hongkong", "good": "tea", "value": 5}), ("weather", {"region": "north", "level": 3}),
                  ("ban", {"port": "shanghai", "turns": 3}), ("news", {"text": "x"}), ("years", {"years": 9}),
                  ("adjust", {"pid": "p1", "cash": 5, "port": "calcutta"}), ("kick", {"pid": "p2"})):
        game.admin(op, a)
    check(game)
    try:
        game.admin("adjust", {"pid": "nobody"})
        raise AssertionError("expected an error")
    except GameError:
        pass
    engine.configure(config.defaults())
    print("OK: settings checks passed")
