"""Checks the Port Authority (declaring cargo on arrival).

Run from the project folder:  python tests/customs_test.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import cast  # noqa: E402
import config  # noqa: E402
import engine  # noqa: E402
import voice  # noqa: E402
from engine import Game, GameError, PORTS  # noqa: E402


def arrive(seed, dest, cargo=(("tea", 30), ("general", 25))):
    """One house sails from Hong Kong with cargo and drops anchor (or is blown elsewhere)."""
    g = Game(seed=seed)
    g.join("Ann", "")
    g.admin("start", {})
    p = g.s["players"]["p1"]
    p["cash"] = 50000
    for good, q in cargo:
        g.act("p1", {"type": "buy", "good": good, "qty": q}, present=["p1"])
    g.act("p1", {"type": "sail", "dest": dest, "orders": "run"}, present=["p1"])
    assert g.maybe_advance({"p1"})
    return g, p


def main():
    engine.configure(config.defaults())
    # 1. Arriving with cargo opens her desk, and nothing else can be done until it is cleared.
    seen = 0
    for seed in range(40):
        g, p = arrive(seed, "calcutta")
        if not p["ships"] or p["port"] == "hongkong":
            continue
        cu = p["customs"]
        assert cu and cu["status"] == "declare" and cu["officer"] == PORTS[p["port"]]["officer"], cu
        assert cu["rate"] == g.tax_rate(p["port"]) > 0
        try:
            g.act("p1", {"type": "sell", "good": "tea", "qty": 1}, present=["p1"])
            raise AssertionError("traded before the declaration")
        except GameError:
            pass
        v = g.view("p1", ["p1"])["me"]["customs"]
        assert v["welcome"] and v["view"] in ("exact", "bar", "tell")
        seen += 1
        # Over-declaring: never bought, more tax, standing rises.
        rep0, cash0 = p["rep"][p["port"]], p["cash"]
        vals = {ln["good"]: int(ln["value"] * 1.5) for ln in cu["lines"]}
        g.act("p1", {"type": "customs_declare", "values": vals}, present=["p1"])
        res = p["customs"]["result"]
        assert all(r["outcome"] == "tax" for r in res["lines"]) and res["rep"] > 0 and p["rep"][p["port"]] > rep0
        assert cash0 - p["cash"] == res["tax"]
        g.act("p1", {"type": "customs_done"}, present=["p1"])
        assert p["customs"] is None
        g.act("p1", {"type": "sell", "good": "tea", "qty": 1}, present=["p1"])
    assert seen > 20, seen

    # 2. Declaring nothing at all: she buys it for nothing, or catches it; buy-back costs her price plus the premium.
    outcomes = {}
    for seed in range(60):
        g, p = arrive(seed, "shanghai")
        if not p.get("customs") or p["customs"]["status"] != "declare":
            continue
        g.act("p1", {"type": "customs_declare", "values": {ln["good"]: 0 for ln in p["customs"]["lines"]}}, present=["p1"])
        for r in p["customs"]["result"]["lines"]:
            outcomes[r["outcome"]] = outcomes.get(r["outcome"], 0) + 1
            if r["units"] and r["paid"]:
                held = p["cargo"].get(r["good"], 0)
                cost = g.buyback_cost(r)
                assert cost >= r["paid"]
                g.act("p1", {"type": "customs_buyback", "good": r["good"]}, present=["p1"])
                assert p["cargo"][r["good"]] == held + r["units"]
                try:
                    g.act("p1", {"type": "customs_buyback", "good": r["good"]}, present=["p1"])
                    raise AssertionError("bought back twice")
                except GameError:
                    pass
        g.act("p1", {"type": "customs_done"}, present=["p1"])
    assert outcomes.get("caught") and (outcomes.get("buyout") or outcomes.get("partial")), outcomes

    # 3. A declaration nobody made is filed honestly when the month ends, and saves round-trip.
    g, p = arrive(3, "nagasaki")
    if p.get("customs") and p["customs"]["status"] == "declare":
        port = p["port"]
        g = Game(state=json.loads(json.dumps(g.s)), seed=9)
        p = g.s["players"]["p1"]
        g.resolve("host")
        assert p["customs"] is None and p["port"] == port
        assert any("Port Authority of" in line for line in p["log"]), p["log"]

    # 4. Hong Kong is a free port: she waves the house in and trading is not held up.
    g = Game(seed=1)
    g.join("Ann", "")
    g.admin("start", {})
    p = g.s["players"]["p1"]
    p["port"] = "hongkong"
    p["cargo"] = {"tea": 10}
    g._open_customs(p)
    assert p["customs"]["status"] == "welcome" and p["customs"]["free"]
    g.act("p1", {"type": "sell", "good": "tea", "qty": 1}, present=["p1"])

    # 5. Rates drift but stay near each port's base, and a free port stays free.
    g = Game(seed=2)
    for _ in range(120):
        g._drift_tax_rates()
        for k, port in PORTS.items():
            r, base = g.tax_rate(k), port["tax_rate"]
            assert (r == 0) if base == 0 else abs(r - base) <= engine.R["customs"]["range"] + 1e-9, (k, r)

    # 6. Her lines are read by the officer of the port the house is in.
    cfg = config.defaults()
    voice.PLAN.configure(cfg, engine.TEXT)
    assert voice.PLAN._who("m.customs_clean", "batavia") == "officer_batavia"
    assert voice.PLAN._who("m.customs_clean", None) == "taxlady"
    assert voice.PLAN._who("l.anchored", "batavia") == cast.speaker_for(cfg, "l.anchored")
    print("OK: Port Authority checks passed")


if __name__ == "__main__":
    main()
