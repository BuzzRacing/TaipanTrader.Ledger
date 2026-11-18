"""Selling a cargo and buying it straight back (or the reverse) earns no standing.

Standing from trade counts only the part of a trade that adds to the house's net dealing in that
cargo this visit. Prices still move with every trade, as before.

Run from the project folder:  python tests/churn_test.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from engine import Game, PORTS  # noqa: E402


def setup():
    g = Game(seed=7)
    pid = g.pid_for_token(g.join("Ada", ""))
    g.act(pid, {"type": "start"}, present=[pid])
    p = g.s["players"][pid]
    p["customs"] = None
    p["cash"] = 50_000_000.0
    port = p["port"]
    p["rep"][port] = 20.0
    p["cargo"] = {}
    return g, pid, p, port


def act(g, pid, a):
    g.act(pid, a, present=g.s["order"])


def main():
    g, pid, p, port = setup()
    room = g.capacity(p)
    q = max(1, room // 2)

    # An honest first buy earns standing.
    r0 = p["rep"][port]
    act(g, pid, {"type": "buy", "good": "silk", "qty": q})
    r1 = p["rep"][port]
    assert r1 > r0, (r0, r1)

    # Selling it all back, then buying and selling again and again, earns nothing more.
    for _ in range(5):
        act(g, pid, {"type": "sell", "good": "silk", "qty": q})
        act(g, pid, {"type": "buy", "good": "silk", "qty": q})
    assert abs(p["rep"][port] - r1) < 1e-9, (r1, p["rep"][port])

    # Prices still move with the trades.
    mid = g.s["prices"][port]["silk"]
    act(g, pid, {"type": "sell", "good": "silk", "qty": q})
    assert g.s["prices"][port]["silk"] < mid
    assert abs(p["rep"][port] - r1) < 1e-9

    # A different cargo is its own account: buying tea still earns standing.
    act(g, pid, {"type": "buy", "good": "tea", "qty": q})
    r2 = p["rep"][port]
    assert r2 > r1

    # Buying more of the same cargo on top of what was bought this visit still earns.
    act(g, pid, {"type": "buy", "good": "tea", "qty": 1})
    assert p["rep"][port] > r2

    # Crossing over: hold extra silk from before the visit, sell more than was bought here.
    g2, pid2, p2, port2 = setup()
    k = max(2, room // 4)
    p2["cargo"] = {"silk": 2 * k}
    act(g2, pid2, {"type": "buy", "good": "silk", "qty": k})               # net +k
    a = p2["rep"][port2]
    act(g2, pid2, {"type": "sell", "good": "silk", "qty": 3 * k})          # unwinds k, then sells 2k fresh
    assert p2["rep"][port2] > a
    print("churn_test: all checks passed")


if __name__ == "__main__":
    main()
