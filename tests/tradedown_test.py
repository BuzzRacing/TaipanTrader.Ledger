"""Trading down the last ship at a shipyard: the way back for a broke house.

Run from the project folder:  python tests/tradedown_test.py
"""
import json
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
    g = Game(seed=5)
    pid = g.pid_for_token(g.join("Ada", ""))
    g.act(pid, {"type": "start"}, present=[pid])
    p = g.s["players"][pid]
    yard = next(k for k in PORTS if PORTS[k]["shipyard"])
    noyard = next(k for k in PORTS if not PORTS[k]["shipyard"])
    p["customs"] = None
    return g, pid, p, yard, noyard


def main():
    g, pid, p, yard, noyard = setup()
    junk = R["wreck"]["ship"]
    # A junk is already the bottom rung: no offer.
    assert g.trade_down_offer(p) is None
    # Broke, deep in debt, one Indiaman.
    p["ships"] = [g._new_ship("indiaman", guns=6)]
    p["cash"], p["bank"], p["debt"] = 0.0, 0.0, 500000.0
    p["cargo"] = {}
    offer = g.trade_down_offer(p)
    assert offer and offer["kind"] == junk and offer["value"] > 0, offer
    expect = int(g.ship_value(p["ships"][0]) - SHIPS[junk]["price"] - offer["guns"] * R["fleet"]["gun_price"])
    assert offer["value"] == expect
    assert refused(g, pid, {"type": "sell_ship", "index": 0}), "last ship must not be sellable"
    p["port"] = noyard
    assert refused(g, pid, {"type": "trade_down"}), "no shipyard here"
    p["port"] = yard
    # The junk's guns take room in her hold (rules.fleet.gun_hold), so the cargo must fit what is left.
    assert offer["hold"] == SHIPS[junk]["hold"] - offer["guns"] * engine.gun_hold(), offer
    p["cargo"] = {"rice": offer["hold"] + 1}
    assert refused(g, pid, {"type": "trade_down"}), "cargo must fit the junk"
    p["cargo"] = {"rice": offer["hold"]}
    name = p["ships"][0]["name"]
    g.act(pid, {"type": "trade_down"}, present=[pid])
    assert p["cash"] == offer["value"]
    assert len(p["ships"]) == 1 and p["ships"][0]["type"] == junk and p["ships"][0]["name"] == name
    assert p["ships"][0]["hull"] == SHIPS[junk]["hull"] and p["ships"][0]["guns"] == offer["guns"]
    assert g.trade_down_offer(p) is None
    assert refused(g, pid, {"type": "trade_down"}), "a junk cannot trade down again"
    # With two ships, sell one instead.
    p["ships"].append(g._new_ship("barque"))
    assert g.trade_down_offer(p) is None and refused(g, pid, {"type": "trade_down"})
    json.dumps(g.view(pid, [pid]))
    print("OK: trade-down rules hold")


if __name__ == "__main__":
    engine.configure()
    main()
