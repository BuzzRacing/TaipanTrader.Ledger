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
    g.fight_out({"p1"})   # captains at their screens fight their battles
    return g, p


def no_spot(cfg):
    """These checks are about the ordinary rules: no spot checks at free landings."""
    cfg["rules"]["customs"]["spot_home"] = cfg["rules"]["customs"]["spot_shares"] = 0.0
    return cfg


def main():
    base = no_spot(config.defaults())
    base["rules"]["start"]["where"] = "home"     # these voyages are written as leaving Hong Kong
    engine.configure(base)
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

    # 2. Declaring nothing at all: she buys it for nothing, or catches it; buy-back costs her price plus the premium, never less than the goods are worth.
    outcomes = {}
    for seed in range(60):
        g, p = arrive(seed, "shanghai")
        if not p.get("customs") or p["customs"]["status"] != "declare":
            continue
        g.act("p1", {"type": "customs_declare", "values": {ln["good"]: 0 for ln in p["customs"]["lines"]}}, present=["p1"])
        for r in p["customs"]["result"]["lines"]:
            outcomes[r["outcome"]] = outcomes.get(r["outcome"], 0) + 1
            if r["units"]:
                held = p["cargo"].get(r["good"], 0)
                cost = g.buyback_cost(r)
                assert cost >= r["paid"]
                # Never cheaper than the goods are worth: a $0 declaration can't be bought back for $0.
                assert cost >= int(r["value"] * r["units"] / r["qty"]), (cost, r)
                assert cost > 0, r
                p["cash"] = max(p["cash"], cost)
                g.act("p1", {"type": "customs_buyback", "good": r["good"]}, present=["p1"])
                assert p["cargo"][r["good"]] == held + r["units"]
                try:
                    g.act("p1", {"type": "customs_buyback", "good": r["good"]}, present=["p1"])
                    raise AssertionError("bought back twice")
                except GameError:
                    pass
        g.act("p1", {"type": "customs_done"}, present=["p1"])
    assert outcomes.get("caught") and (outcomes.get("buyout") or outcomes.get("partial")), outcomes

    # 2b. Sealed in bond: no tax, no roll and no risk on that cargo; none of it sells here; a new arrival clears it.
    done = 0
    for seed in range(40):
        g, p = arrive(seed, "calcutta")
        cu = p.get("customs")
        if not cu or cu["status"] != "declare" or len(cu["lines"]) < 2:
            continue
        keep, rest = cu["lines"][0]["good"], [ln["good"] for ln in cu["lines"][1:]]
        qty, cash, debt = p["cargo"][keep], p["cash"], p["debt"]
        assert g.view("p1", ["p1"])["me"]["customs"]["bond"]
        g.act("p1", {"type": "customs_declare", "values": {keep: 0}, "sealed": [keep]}, present=["p1"])
        res = {r["good"]: r for r in p["customs"]["result"]["lines"]}
        assert res[keep]["outcome"] == "sealed" and res[keep]["tax"] == 0 and p["cargo"][keep] == qty, res[keep]
        assert set(res) == {keep} | set(rest)
        assert p["customs"]["result"]["value"] == sum(ln["value"] for ln in cu["lines"][1:])
        g.act("p1", {"type": "customs_done"}, present=["p1"])
        assert g.sealed(p) == {keep: qty} and g.view("p1", ["p1"])["me"]["bond"] == {keep: qty}
        try:
            g.act("p1", {"type": "sell", "good": keep, "qty": 1}, present=["p1"])
            raise AssertionError("sold cargo sealed in bond")
        except GameError:
            pass
        if p["cash"] > 2 * g.quote(p, keep, 1, "buy")[0] and g.capacity(p) > g.used(p):
            g.act("p1", {"type": "buy", "good": keep, "qty": 1}, present=["p1"])       # what is bought here is free to sell
            g.act("p1", {"type": "sell", "good": keep, "qty": 1}, present=["p1"])
        g = Game(state=json.loads(json.dumps(g.s)), seed=seed)                        # saves round-trip
        p = g.s["players"]["p1"]
        assert g.sealed(p) == {keep: qty}
        g._open_customs(p)
        assert g.sealed(p) == {}
        done += 1
    assert done > 5, done
    # everything sealed: nothing owed at all
    g, p = arrive(1, "calcutta")
    if p.get("customs") and p["customs"]["status"] == "declare":
        cash, debt = p["cash"], p["debt"]
        g.act("p1", {"type": "customs_declare", "sealed": [ln["good"] for ln in p["customs"]["lines"]]}, present=["p1"])
        assert p["cash"] == cash and p["debt"] == debt and p["customs"]["result"]["tax"] == 0
    # switched off in Admin, a "sealed" list is ignored and the cargo is taxed as declared
    cfg = json.loads(json.dumps(base))
    cfg["rules"]["customs"]["bond"] = False
    engine.configure(cfg)
    g, p = arrive(1, "calcutta")
    if p.get("customs") and p["customs"]["status"] == "declare":
        g.act("p1", {"type": "customs_declare", "sealed": [ln["good"] for ln in p["customs"]["lines"]]}, present=["p1"])
        assert all(r["outcome"] != "sealed" for r in p["customs"]["result"]["lines"])
    engine.configure(base)

    # 3. A declaration nobody made is filed honestly when the month ends, and saves round-trip.
    g, p = arrive(3, "nagasaki")
    if p.get("customs") and p["customs"]["status"] == "declare":
        port = p["port"]
        g = Game(state=json.loads(json.dumps(g.s)), seed=9)
        p = g.s["players"]["p1"]
        g.resolve("host")
        assert p["customs"] is None and p["port"] == port
        assert any("Port Authority of" in line for line in p["log"]), p["log"]

    # 4. Hong Kong is not a free port: a house whose home is elsewhere declares there like
    #    anywhere else. Only a house whose home is Hong Kong is waved in (and can trade at once).
    g = Game(seed=1)
    g.join("Ann", "")
    g.admin("start", {})
    p = g.s["players"]["p1"]
    assert PORTS["hongkong"]["tax_rate"] > 0 and g.tax_rate("hongkong") > 0
    p["home"] = "shanghai"
    p["port"] = "hongkong"
    p["cargo"] = {"tea": 10}
    g._open_customs(p)
    assert p["customs"]["status"] == "declare" and not p["customs"]["free"] and not p["customs"]["home_free"]
    assert p["customs"]["rate"] == g.tax_rate("hongkong") > 0
    p["home"], p["customs"] = "hongkong", None
    g._open_customs(p)
    assert p["customs"]["status"] == "welcome" and p["customs"]["home_free"] and p["customs"]["rate"] == 0
    g.act("p1", {"type": "sell", "good": "tea", "qty": 1}, present=["p1"])

    # 4b. A save made while Hong Kong was free (its rate stored as 0) charges the base rate as
    #     soon as it is loaded, not a month later.
    st = json.loads(json.dumps(g.s))
    st["tax_rates"]["hongkong"] = 0.0
    g2 = Game(state=st, seed=3)
    assert g2.tax_rate("hongkong") == PORTS["hongkong"]["tax_rate"]

    # 5. Rates drift but stay near each port's base, and a free port stays free.
    g = Game(seed=2)
    for _ in range(120):
        g._drift_tax_rates()
        for k, port in PORTS.items():
            r, base = g.tax_rate(k), port["tax_rate"]
            assert (r == 0) if base == 0 else abs(r - base) <= engine.R["customs"]["range"] + 1e-9, (k, r)

    # 5b. A house pays no cargo tax in its own home port, whatever that port charges others;
    #     everywhere else it pays as usual, and the Admin switch turns the favour off.
    def land(game, pid, port):
        q = game.s["players"][pid]
        q["port"], q["cargo"], q["customs"] = port, {"tea": 20}, None
        game._open_customs(q)
        return q["customs"], game.view(pid, [pid])["me"]

    engine.configure(no_spot(config.defaults()))      # random starts
    homes = set()
    for seed in range(30):
        g = Game(seed=seed)
        g.join("Ann", "")
        g.admin("start", {})
        p = g.s["players"]["p1"]
        home = p["home"]
        homes.add(home)
        cu, me = land(g, "p1", home)
        assert cu["status"] == "welcome" and cu["free"] and cu["home_free"] and cu["rate"] == 0, (home, cu)
        assert me["home_free"] and me["customs"]["home_free"] and PORTS[home]["name"] in me["customs"]["welcome"]
        assert g.tax_rate_for(p, home) == 0
        for away in PORTS:
            if away == home:
                continue
            cu, me = land(g, "p1", away)
            assert not cu["home_free"] and cu["rate"] == g.tax_rate(away) == g.tax_rate_for(p, away)
            assert cu["status"] == ("declare" if PORTS[away]["tax_rate"] > 0 else "welcome")
    assert len(homes) > 5 and homes - {"hongkong"}, homes
    off = no_spot(config.defaults())
    off["rules"]["customs"]["home_free"] = False
    assert not config.validate(off)[1]
    engine.configure(off)
    for seed in range(30):
        g = Game(seed=seed)
        g.join("Ann", "")
        g.admin("start", {})
        p = g.s["players"]["p1"]
        cu, me = land(g, "p1", p["home"])
        assert not cu["home_free"] and not me["home_free"] and cu["rate"] == g.tax_rate(p["home"])
    back = config.defaults()
    back["rules"]["start"]["where"] = "home"
    engine.configure(back)

    # 5c. Spot checks: a house that would pay nothing (home port, or shares that cut the tax to
    #     nothing) is now and then stopped anyway and declares at the port's full rate, that
    #     landing only. Its own seed: the same landing always comes out the same.
    spot = config.defaults()
    spot["rules"]["customs"]["spot_home"] = spot["rules"]["customs"]["spot_shares"] = 0.25
    assert not config.validate(spot)[1]
    engine.configure(spot)
    stopped = {"home": 0, "shares": 0}
    for seed in range(80):
        g = Game(seed=seed)
        g.join("Ann", "")
        g.admin("start", {})
        p = g.s["players"]["p1"]
        home = p["home"]
        cu, me = land(g, "p1", home)
        again, _ = land(g, "p1", home)
        assert cu["spot"] == again["spot"], "the same landing must come out the same"
        if cu["spot"]:
            stopped["home"] += 1
            assert cu["spot"] == "home" and cu["status"] == "declare" and not cu["free"] and not cu["home_free"]
            assert cu["rate"] == round(g.tax_rate(home), 4) > 0 and cu["say"] == "l.customs_spot_home"
            assert me["customs"]["spot"] == "home" and "spot check" in me["customs"]["welcome"].lower()
            assert g.tax_rate_for(p, home) == 0          # the waiver itself stands for every other landing
        else:
            assert cu["status"] == "welcome" and cu["home_free"] and cu["rate"] == 0
        # A port this house holds every share of (100% cut): free, but a spot check charges the full rate.
        away = next(k for k in PORTS if k != home and PORTS[k]["tax_rate"] > 0)
        g._share_book(away)[p["id"]] = 10**3
        assert g.tax_rate_for(p, away) == 0
        cu, _ = land(g, "p1", away)
        if cu["spot"]:
            stopped["shares"] += 1
            assert cu["spot"] == "shares" and cu["status"] == "declare" and cu["rate"] == round(g.tax_rate(away), 4)
            assert cu["say"] == "l.customs_spot_shares"
        else:
            assert cu["status"] == "welcome" and cu["rate"] == 0
        # Partly-cut tax is charged anyway: no spot roll, the cut rate stands.
        g._share_book(away)[p["id"]] = 1
        cu, _ = land(g, "p1", away)
        assert not cu["spot"] and cu["rate"] == round(g.tax_rate_for(p, away), 4) > 0
    assert 8 <= stopped["home"] <= 36 and 8 <= stopped["shares"] <= 36, stopped
    # An empty hold or a free port is never stopped; 0 turns spot checks off.
    g = Game(seed=5)
    g.join("Ann", "")
    g.admin("start", {})
    p = g.s["players"]["p1"]
    p["port"], p["cargo"], p["customs"] = p["home"], {}, None
    g._open_customs(p)
    assert not p["customs"]["spot"] and p["customs"]["status"] == "welcome"
    engine.configure(no_spot(config.defaults()))
    for seed in range(40):
        g = Game(seed=seed)
        g.join("Ann", "")
        g.admin("start", {})
        cu, _ = land(g, "p1", g.s["players"]["p1"]["home"])
        assert not cu["spot"] and cu["status"] == "welcome"
    engine.configure(back)

    # 6. Her lines are read by the officer of the port the house is in.
    cfg = config.defaults()
    voice.PLAN.configure(cfg, engine.TEXT)
    assert voice.PLAN._who("m.customs_clean", "batavia") == "officer_batavia"
    assert voice.PLAN._who("m.customs_clean", None) == "taxlady"
    assert voice.PLAN._who("l.anchored", "batavia") == cast.speaker_for(cfg, "l.anchored")
    # 7. Standing in the port cuts both her buyouts and her audits; low standing raises both.
    g = Game(seed=7)
    g.join("Ann", "")
    g.admin("start", {})
    p = g.s["players"]["p1"]
    line = {"value": 10000, "appetite": 1.0}
    odds = {}
    for rep in (0, 50, 100):
        p["rep"]["calcutta"] = rep
        cx = dict(g._officer_ctx(p, "calcutta"), mood=1.0)
        odds[rep] = Game.customs_odds(cx, line, 8000)
    assert odds[100][0] < odds[50][0] < odds[0][0], odds
    assert odds[100][1] < odds[50][1] < odds[0][1], odds
    # A small lie at average standing in the dearest port is now a fair gamble: tax saved beats expected loss.
    c, rate = engine.R["customs"], PORTS["calcutta"]["tax_rate"]
    buy, audit = odds[50]
    assert rate * 2000 > buy * 2000 + audit * c["fine_mult"] * rate * 2000, (rate, odds[50])
    # 8. Her greetings: 30 shared plus 15 of each officer's own. A house hears all of an officer's lines
    #    before any comes round again, never the same one twice running, and every one is matched back
    #    to its key and read by that port's officer.
    keys = ["l.customs_welcome.{}".format(i) for i in range(30)]
    assert all(k in engine.TEXT for k in keys) and "l.customs_welcome.30" not in engine.TEXT
    words = [len(engine.TEXT[k].split()) for k in keys]
    assert max(words[:10]) <= 9 < min(words[10:20]), words                 # short, then medium
    assert all("{line}" in engine.TEXT[k] and "{rate}" in engine.TEXT[k] for k in keys[20:])   # full
    voice.PLAN.configure(cfg, engine.TEXT)
    chars = cfg["characters"]
    officers = sorted({info.get("officer") for info in PORTS.values() if info.get("officer") in chars} - {"taxlady"})
    assert len(officers) == 10, officers
    g = Game(seed=11)
    g.join("Ann", "")
    g.admin("start", {})
    p = g.s["players"]["p1"]
    for officer in officers:
        own = ["l.customs_welcome.{}.{}".format(officer, i) for i in range(15)]
        assert all(k in engine.TEXT for k in own) and "l.customs_welcome.{}.15".format(officer) not in engine.TEXT
        said = [g._pa_greeting(p, officer) for _ in range(135)]
        for n in range(3):
            assert sorted(said[n * 45:(n + 1) * 45]) == sorted(keys + own), officer
        assert all(a != b for a, b in zip(said, said[1:])), officer
        assert said[:45] != said[45:90]                                   # each deck is shuffled afresh
    for port, info in PORTS.items():
        officer = cfg["ports"].get(port, {}).get("officer") or info.get("officer")
        if not officer or officer not in chars:
            continue
        for k in keys + ["l.customs_welcome.{}.{}".format(officer, i) for i in range(15) if officer != "taxlady"]:
            line = engine.tx(k, line=chars[officer].get("catchphrase", ""), port=info["name"], rate="3%")
            found, fields = voice.PLAN.matcher.match(line)
            assert found == k, (port, k, found)
            assert voice.PLAN._who(k, port) == officer, (port, k)
            assert "3%" not in voice.PLAN.spoken(found, fields, line), (port, k)
    # The desk shows the greeting drawn when she opened it, and keeps it while the house looks at her.
    for seed in range(40):
        g, p = arrive(seed, "calcutta")
        cu = p.get("customs")
        if cu and cu["status"] == "declare":
            v1 = g.view("p1", ["p1"])["me"]["customs"]["welcome"]
            assert isinstance(cu["say"], str) and v1 == g.view("p1", ["p1"])["me"]["customs"]["welcome"]
            assert voice.PLAN.matcher.match(v1)[0] == cu["say"], v1
            break
    else:
        raise AssertionError("no taxed arrival to greet")
    # A desk opened before the officers' own lines (a number) still shows its shared greeting.
    cu["say"] = 4
    assert g.view("p1", ["p1"])["me"]["customs"]["welcome"] == engine.tx(keys[4], port=PORTS[cu["port"]]["name"])
    print("OK: Port Authority checks passed")


if __name__ == "__main__":
    main()
