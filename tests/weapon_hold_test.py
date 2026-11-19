"""Weapons take cargo space (19 Nov 2026): each gun takes rules.fleet.gun_hold units of her hold and
each cannon rules.fleet.cannon_hold. A gun or cannon cannot be mounted while cargo needs the space.

Run from the project folder:  python tests/weapon_hold_test.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import engine  # noqa: E402
from engine import Game, GameError, PORTS, SHIPS, R  # noqa: E402


def refused(game, pid, a):
    try:
        game.act(pid, a, present=game.s["order"])
    except GameError:
        return True
    return False


def setup():
    g = Game(seed=11)
    pid = g.pid_for_token(g.join("Ada", ""))
    g.act(pid, {"type": "start"}, present=[pid])
    p = g.s["players"][pid]
    p["customs"] = None
    p["port"] = next(k for k in PORTS if PORTS[k]["shipyard"])
    return g, pid, p


def main():
    f = R["fleet"]
    f["gun_hold"], f["cannon_hold"] = 5, 10
    gh, ch = engine.gun_hold(), engine.cannon_hold()

    g, pid, p = setup()
    p["cash"] = 10 ** 7
    p["cargo"] = {}

    # The starting junk: her hold is cut by the guns she carries.
    junk = p["ships"][0]
    assert g.capacity(p) == SHIPS["junk"]["hold"] - gh * junk["guns"], g.capacity(p)

    # Mounting a gun takes gun_hold of her hold; selling it gives it back.
    before = g.capacity(p)
    g.act(pid, {"type": "buy_gun", "index": 0}, present=[pid])
    assert g.capacity(p) == before - gh
    g.act(pid, {"type": "sell_gun", "index": 0}, present=[pid])
    assert g.capacity(p) == before

    # A full hold refuses a gun: the cargo needs the space.
    good = next(iter(engine.GOODS))
    p["cargo"] = {good: g.capacity(p)}
    assert refused(g, pid, {"type": "buy_gun", "index": 0}), "gun mounted over cargo"
    p["cargo"] = {good: g.capacity(p) - gh}
    g.act(pid, {"type": "buy_gun", "index": 0}, present=[pid])
    assert g.used(p) == g.capacity(p)
    p["cargo"] = {}

    # Cannons take cannon_hold each, and Fill stops where the cargo needs the space.
    p["ships"] = [g._new_ship("barque", guns=0)]
    full = SHIPS["barque"]["hold"]
    assert g.capacity(p) == full
    g.act(pid, {"type": "buy_cannon", "index": 0}, present=[pid])
    assert g.capacity(p) == full - ch
    p["cargo"] = {good: g.capacity(p) - 2 * ch}       # room for two more cannons only
    plan, _cost = g.fill_plan(p, 0)
    assert plan == [(0, 2)], plan
    g.act(pid, {"type": "fill_cannons", "index": 0}, present=[pid])
    assert p["ships"][0]["cannons"] == 3 and g.used(p) <= g.capacity(p)
    assert refused(g, pid, {"type": "buy_cannon", "index": 0}), "cannon mounted over cargo"

    # A ship's hold never drops below 0; an escort has none to lose.
    esc = next((k for k, s in SHIPS.items() if s.get("role") == "escort"), None)
    if esc:
        sh = g._new_ship(esc, guns=SHIPS[esc]["slots"])
        assert engine.ship_hold(sh) == 0

    # The shipyard screen gets each ship's armed hold and the rule numbers.
    v = g.view(pid)
    assert v["me"]["ships"][0]["hold"] == engine.ship_hold(p["ships"][0])
    styles = engine._config.promotion_styles
    engine._config.promotion_styles = lambda: {"plain": {}}    # the certificate art is not needed here
    try:
        d = engine.static_data()
    finally:
        engine._config.promotion_styles = styles
    assert d["gun_hold"] == gh and d["cannon_hold"] == ch

    # 0 turns the rule off.
    f["gun_hold"] = f["cannon_hold"] = 0
    assert g.capacity(p) == full
    print("weapon hold test passed")


if __name__ == "__main__":
    main()
