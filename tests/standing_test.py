"""Checks reputation swings (rules.standing, owner's decisions of 19 Nov 2026).

Standing in each port falls in five bands of 20. A caught lie costs a big fall (more for a bigger lie),
word travels to the same region, and the fine is set by the band the house falls into, at least a share
of its net worth. Honest desks, good business, beating pirates and clearing debt earn it back; drift pulls
every port toward 50 each month. Hostile ports search and gouge; Favoured ones cut the tax, warn of
pirates and offer private lots.

Run from the project folder:  python tests/standing_test.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import config  # noqa: E402
import engine  # noqa: E402
from engine import Game, PORTS  # noqa: E402


def base_cfg():
    cfg = config.defaults()
    cfg["rules"]["start"]["where"] = "home"
    cfg["rules"]["customs"]["spot_home"] = cfg["rules"]["customs"]["spot_shares"] = 0.0
    return cfg


def new_game(seed=1, cfg=None):
    engine.configure(cfg or base_cfg())
    g = Game(seed=seed)
    g.join("Ann", "")
    g.admin("start", {})
    p = g.s["players"]["p1"]
    p["cash"] = 200000
    return g, p


def arrive(g, p, dest, cargo=(("tea", 25), ("silk", 20))):
    for good, q in cargo:
        g.act("p1", {"type": "buy", "good": good, "qty": q}, present=["p1"])
    g.act("p1", {"type": "sail", "dest": dest, "orders": "run"}, present=["p1"])
    assert g.maybe_advance({"p1"})
    g.fight_out({"p1"})
    return p["port"] == dest and p.get("customs") and p["customs"].get("status") == "declare"


def desk_cfg(audit=True):
    """A desk that never buys out, and (audit) all but always searches a lie."""
    cfg = base_cfg()
    c = cfg["rules"]["customs"]
    c["buy_base"] = c["buy_k"] = 0.0
    if audit:
        c["audit_base"], c["audit_k"], c["audit_cap"] = 0.9, 0.0, 0.9
    else:
        c["audit_base"] = c["audit_k"] = 0.0
    cfg["rules"]["standing"]["drift"] = 0
    return cfg


def at_desk(cfg, rep, seed_from=0):
    """A house arriving at a taxed port's desk, with its standing there set to rep."""
    for seed in range(seed_from, seed_from + 60):
        g, p = new_game(seed, cfg)
        others = [k for k in PORTS if k != p["port"] and PORTS[k].get("tax_rate", 0) > 0]
        dest = others[seed % len(others)]
        p["rep"][dest] = rep
        if arrive(g, p, dest):
            return g, p, dest
    raise AssertionError("never reached a desk")


def declare(g, p, share):
    vals = {ln["good"]: int(ln["value"] * share) for ln in p["customs"]["lines"]}
    g.act("p1", {"type": "customs_declare", "values": vals}, present=["p1"])
    return p["customs"]["result"]


def main():
    st = engine.R["standing"] if engine.R.get("standing") else config.defaults()["rules"]["standing"]
    # 1. The bands, as the heat bars show them.
    assert [Game.band_of(r) for r in (0, 19, 19.4, 20, 39, 40, 59, 60, 79, 80, 100)] == [0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4]

    # 2. Caught paying nothing on the whole hold from Favoured: a fall of about 26-48, word through the region,
    #    and a fine set by the new band, never less than its share of net worth.
    cfg = desk_cfg(audit=True)
    falls, n = [], 0
    for start in range(0, 600, 60):
        g, p, port = at_desk(cfg, 85.0, start)
        region = [k for k in PORTS if k != port and PORTS[k]["region"] == PORTS[port]["region"]]
        others = [k for k in PORTS if k != port and PORTS[k]["region"] != PORTS[port]["region"]]
        before = {k: p["rep"][k] for k in PORTS}
        worth0 = g.worth(p)
        res = declare(g, p, 0.0)
        if not res["caught"]:
            continue
        n += 1
        fall = before[port] - p["rep"][port]
        falls.append(fall)
        assert 12 * 0.7 - 1e-6 <= fall <= 37 * 1.3 + 1e-6, fall
        for k in region:
            assert abs((before[k] - p["rep"][k]) - fall / 3.0) < 0.5 or p["rep"][k] == 0.0, (k, before[k], p["rep"][k], fall)
        for k in others:
            assert p["rep"][k] == before[k], k
        band = engine.Game.BANDS[Game.band_of(p["rep"][port])]
        floor = st[band + "_floor_lo"] * worth0
        assert res["fine"] >= int(floor) - 1, (res["fine"], floor, band)
        hidden = sum(r["value"] - r["declared"] for r in res["lines"] if r["outcome"] == "caught")
        assert res["fine"] >= int(st["fine_hidden"] * hidden * st[band + "_pen_lo"]) - 1
        assert res["fine"] > 10 * sum(r["tax"] for r in res["lines"]), res     # it hurts now
        assert any(e["why"] == "caught" and e["port"] == port for e in p["bands"]), p["bands"]
        assert p["honest_run"] == 0
    assert n >= 3, n
    assert min(falls) > 20, falls        # a full lie always costs more than one band's width

    # 3. A small lie caught costs less than a big one.
    g, p, port = at_desk(cfg, 70.0, 7)
    r0 = p["rep"][port]                       # the voyage itself may have moved it (a fight on the way in)
    res = declare(g, p, 0.9)
    if res["caught"]:
        assert r0 - p["rep"][port] <= (12 + 25 * 0.1) * 1.3 + 1e-6

    # 4. An honest desk earns standing (times the band's gain roll); paying more earns more; a run adds.
    cfg = desk_cfg(audit=False)
    g, p, port = at_desk(cfg, 50.0, 3)
    p["rep"][port] = 50.0
    declare(g, p, 1.0)
    gain = p["rep"][port] - 50.0
    assert st["pay_correct"] * st["neutral_rew_lo"] - 1e-6 <= gain <= st["pay_correct"] * st["neutral_rew_hi"] + 1e-6, gain
    assert p["honest_run"] == 1
    g, p, port = at_desk(cfg, 50.0, 11)
    p["rep"][port] = 50.0
    p["honest_run"] = 4
    res = declare(g, p, 1.12)
    gain = p["rep"][port] - 50.0
    want = st["pay_more"] + min(st["honest_run_max"], st["honest_run"] * 4)
    assert want * st["neutral_rew_lo"] - 1e-6 <= gain <= want * st["neutral_rew_hi"] + 1e-6, gain

    # 5. Good business only: buying at an ordinary price earns nothing; a sale at a profit does, at most
    #    trade_cap a visit before the roll.
    g, p = new_game(5)
    p["customs"] = None
    port = p["port"]
    p["rep"][port] = 50.0
    usual = engine.GOODS["silk"]["base"] * PORTS[port]["mods"].get("silk", 1.0)
    g.s["prices"][port]["silk"] = usual
    g.act("p1", {"type": "buy", "good": "silk", "qty": 10}, present=["p1"])
    assert p["rep"][port] == 50.0, p["rep"][port]
    p["basis"]["silk"] = 1.0                  # bought dirt cheap: every sale is a profit
    p["cargo"] = {"silk": 40}
    for _ in range(8):
        p["net"] = {}                         # a fresh lot each time, so churn rules don't stop it
        g.act("p1", {"type": "sell", "good": "silk", "qty": 5}, present=["p1"])
    gained = p["rep"][port] - 50.0
    assert 0 < gained <= st["trade_cap"] * st["neutral_rew_hi"] + 1e-6, gained
    # Buying from a glut earns.
    g.s["prices"][port]["tea"] = 0.5 * engine.GOODS["tea"]["base"] * PORTS[port]["mods"].get("tea", 1.0)
    p["tab"]["rep_trade"] = 0.0
    p["cargo"] = {}
    r0 = p["rep"][port]
    g.act("p1", {"type": "buy", "good": "tea", "qty": 30}, present=["p1"])
    assert p["rep"][port] > r0

    # 6. Drift: rules.standing.drift points a month toward 50, both ways, never past it.
    g, p = new_game(9)
    p["customs"] = None
    ports = list(PORTS)
    p["rep"][ports[0]], p["rep"][ports[1]], p["rep"][ports[2]] = 90.0, 10.0, 51.0
    g._drift_standing(p)
    d = engine.R["standing"]["drift"]
    assert (p["rep"][ports[0]], p["rep"][ports[1]], p["rep"][ports[2]]) == (90.0 - d, 10.0 + d, max(50.0, 51.0 - d))

    # 7. What the bands do.
    g, p = new_game(2)
    port = p["port"]
    p["rep"][port] = 50.0
    s50, rep50 = g.spread(p, port), g.repair_rate(p, p["ships"][0])
    p["rep"][port] = 19.0
    assert g.band_effects(p, port)["band"] == 0
    s19 = g.spread(p, port)
    assert s19 > s50 + st["hostile_margin"] - 1e-9
    assert abs(g.yard_mult(p) - (1 + st["hostile_yard"])) < 1e-9
    assert g._officer_ctx(p, port)["rep"] > 2 * (1 + engine.R["customs"]["rep_audit"] * (50 - 19) / 50.0) - 0.01
    taxed = [k for k in PORTS if k != engine.home_of(p) and PORTS[k].get("tax_rate", 0) > 0][0]
    p["rep"][taxed] = 50.0
    full = g.tax_rate_for(p, taxed)
    p["rep"][taxed] = 85.0
    assert abs(g.tax_rate_for(p, taxed) - full * (1 - st["favoured_tax_cut"])) < 1e-9
    p["rep"][taxed] = 65.0
    assert abs(g.tax_rate_for(p, taxed) - full * (1 - st["warm_tax_cut"])) < 1e-9
    # A Hostile yard charges more for a ship.
    p["rep"][port] = 10.0
    p["cash"] = 10 ** 7
    cash0 = p["cash"]
    if engine.port_has(p, port, "shipyard"):
        kind = min(engine.SHIPS, key=lambda k: engine.SHIPS[k]["price"] if engine.role_of(k) == "trader" else 10 ** 12)
        g.act("p1", {"type": "buy_ship", "ship": kind}, present=["p1"])
        assert cash0 - p["cash"] == int(round(engine.SHIPS[kind]["price"] * (1 + st["hostile_yard"])))

    # 8. A private lot in a Favoured port: offered on arrival, bought below market, never moves the market.
    cfg = base_cfg()
    cfg["rules"]["standing"]["lot_chance"] = 1.0
    engine.configure(cfg)
    g, p = new_game(4, cfg)
    p["customs"] = None
    for k in PORTS:
        p["rep"][k] = 95.0
    g._offer_lot(p, p["port"])
    lot = g.view("p1", ["p1"])["me"]["lot"]
    assert lot and lot["unit"] < lot["price"] and lot["qty"] >= 5, lot
    price0 = g.s["prices"][p["port"]][lot["good"]]
    have = p["cargo"].get(lot["good"], 0)
    cash0 = p["cash"]
    g.act("p1", {"type": "buy_lot", "qty": 3}, present=["p1"])
    assert p["cargo"][lot["good"]] == have + 3
    assert cash0 - p["cash"] == int(-(-3 * lot["unit"] // 1))
    assert g.s["prices"][p["port"]][lot["good"]] == price0
    p["rep"][p["port"]] = 50.0
    g._offer_lot(p, p["port"])
    assert g.view("p1", ["p1"])["me"]["lot"] is None          # only Favoured houses are offered one

    # 9. Debt cleared: home standing up; borrowing and repaying in the same month earns nothing.
    g, p = new_game(6)
    p["customs"] = None
    home = engine.home_of(p)
    p["rep"][home] = 50.0
    p["debt"] = 5000.0
    g.act("p1", {"type": "loan", "op": "repay", "amount": 5000}, present=["p1"])
    assert p["rep"][home] > 50.0
    r = p["rep"][home]
    g.act("p1", {"type": "loan", "op": "borrow", "amount": 2000}, present=["p1"])
    g.act("p1", {"type": "loan", "op": "repay", "amount": 2000}, present=["p1"])
    assert p["rep"][home] == r

    # 10. Off: the old rules (a caught lie is caught_rep, every trade earns).
    cfg = desk_cfg(audit=True)
    cfg["rules"]["standing"]["enabled"] = False
    g, p, port = at_desk(cfg, 85.0, 0)
    res = declare(g, p, 0.0)
    if res["caught"]:
        assert abs(85.0 - p["rep"][port] - engine.R["customs"]["caught_rep"]) < 1e-9
    assert g.view("p1", ["p1"])["me"]["bands"] == []
    print("standing_test: all checks passed")


if __name__ == "__main__":
    main()
