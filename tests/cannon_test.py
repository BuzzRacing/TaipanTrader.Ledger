"""Cannons on the big ships: worth ten guns in a fight, cost seven and a half, take two mounts.

Run from the project folder:  python tests/cannon_test.py
"""
import os
import random
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
    g = Game(seed=7)
    pid = g.pid_for_token(g.join("Ada", ""))
    g.act(pid, {"type": "start"}, present=[pid])
    p = g.s["players"][pid]
    p["customs"] = None
    p["port"] = next(k for k in PORTS if PORTS[k]["shipyard"])
    return g, pid, p


def main():
    f = R["fleet"]
    assert SHIPS["barque"]["cannons"] and SHIPS["indiaman"]["cannons"]
    assert not any(SHIPS[k]["cannons"] for k in ("junk", "lorcha", "clipper"))
    price = engine.cannon_price()
    assert price == int(round(f["gun_price"] * 7.5)), price
    assert engine.cannon_power() == 10 and engine.cannon_slots() == 2

    g, pid, p = setup()
    # A junk cannot carry one.
    p["cash"] = 10 ** 6
    assert p["ships"][0]["type"] == "junk"
    assert refused(g, pid, {"type": "buy_cannon", "index": 0}), "junk took a cannon"

    # A full barque has to sell two guns to make room for one cannon.
    p["ships"] = [g._new_ship("barque", guns=SHIPS["barque"]["slots"])]
    assert refused(g, pid, {"type": "buy_cannon", "index": 0}), "no room, yet a cannon was mounted"
    g.act(pid, {"type": "sell_gun", "index": 0}, present=[pid])
    assert refused(g, pid, {"type": "buy_cannon", "index": 0}), "one free mount is not enough"
    g.act(pid, {"type": "sell_gun", "index": 0}, present=[pid])
    cash = p["cash"]
    g.act(pid, {"type": "buy_cannon", "index": 0}, present=[pid])
    sh = p["ships"][0]
    assert sh["cannons"] == 1 and sh["guns"] == SHIPS["barque"]["slots"] - 2
    assert p["cash"] == cash - price
    assert g.mounts_free(sh) == 0
    assert refused(g, pid, {"type": "buy_gun", "index": 0}), "deck full, yet a gun was mounted"
    # Firepower: ten guns' worth per cannon.
    assert g.firepower(p) == sh["guns"] + 10, g.firepower(p)
    # Short of silver.
    g.act(pid, {"type": "sell_gun", "index": 0}, present=[pid])
    g.act(pid, {"type": "sell_gun", "index": 0}, present=[pid])
    p["cash"] = price - 1
    assert refused(g, pid, {"type": "buy_cannon", "index": 0}), "bought a cannon it could not pay for"
    # Selling a cannon pays its resale share and frees two mounts.
    p["cash"] = 0
    g.act(pid, {"type": "sell_cannon", "index": 0}, present=[pid])
    assert sh["cannons"] == 0 and p["cash"] == int(price * f["gun_resale"])
    assert refused(g, pid, {"type": "sell_cannon", "index": 0})

    # Ship value counts the cannons.
    sh["guns"], sh["cannons"] = 0, 3
    base = g.ship_value(dict(sh, cannons=0))
    assert abs(g.ship_value(sh) - base - 3 * price * f["gun_resale"]) < 1e-6

    # An Indiaman holds twelve cannons on her twenty-four mounts.
    p["ships"] = [g._new_ship("indiaman")]
    p["cash"] = 10 ** 7
    for _ in range(SHIPS["indiaman"]["slots"] // 2):
        g.act(pid, {"type": "buy_cannon", "index": 0}, present=[pid])
    assert p["ships"][0]["cannons"] == 12 and g.firepower(p) == 120
    assert refused(g, pid, {"type": "buy_cannon", "index": 0})

    # Saves and settings that disagree are put right: no cannons on a ship that cannot carry them,
    # and never more mounts filled than she has.
    p["ships"] = [dict(g._new_ship("lorcha"), cannons=2),
                  dict(g._new_ship("barque", guns=12), cannons=3),
                  {k: v for k, v in g._new_ship("barque", guns=4).items() if k != "cannons"}]
    g.reconcile()
    lorcha, barque, old = p["ships"]
    assert lorcha["cannons"] == 0
    assert barque["cannons"] == 3 and barque["guns"] == 6, barque
    assert old["cannons"] == 0 and old["guns"] == 4

    # Enemy shot can smash a cannon off her deck.
    p["ships"] = [dict(g._new_ship("barque"), cannons=6)]
    g.rng = random.Random(1)
    saved = dict(R["battle"])
    R["battle"]["gun_loss"] = 1.0
    try:
        hits = g._enemy_fire(p, {"hit": 1.0, "dmg": [5, 5]}, [2] * 4)
    finally:
        R["battle"].clear()
        R["battle"].update(saved)
    assert sum(h.get("cannons", 0) for h in hits) == 4 and p["ships"][0]["cannons"] == 2, hits

    # The ship list sent to the screen carries the cannons and the free mounts.
    ships = g.view(pid, [pid])["me"]["ships"]
    assert ships[0]["cannons"] == 2 and ships[0]["free"] == SHIPS["barque"]["slots"] - 4
    assert engine.static_data()["cannon_price"] == price
    print("cannon tests passed")


def test_cannons():
    main()


if __name__ == "__main__":
    main()
