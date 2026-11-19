"""The fleet's three classes and matched sea battles: python tests/fleet_test.py

Merchantmen carry cargo and guns, escorts guns only, cargo ships cargo only. Escorts and cargo ships
open once the line of merchantmen is full, each class has its own limit, and the last merchantman
can't be sold. In a matched fight the enemy is sized from the house's own fleet; escorts in the van
take the fire, cargo ships in the rear lose cargo with every hit, and fame at sea grows and fades.
"""
import copy
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import engine
from engine import Game, GameError, GOODS, PORTS, SHIPS, R


def setup(**battle):
    cfg = config.defaults()
    cfg["rules"]["customs"]["enabled"] = False
    cfg["rules"]["weather"]["storm_chance"] = [0, 0, 0, 0]
    cfg["rules"]["battle"].update(battle)
    cfg, errors = config.validate(cfg)
    assert not errors, errors
    engine.configure(cfg)
    engine.MULT["pirates"] = 1.0


def house(seed=1, cash=10 ** 7):
    g = Game(seed=seed)
    g.join("Ann", "")
    g.act("p1", {"type": "start"}, present=["p1"])
    p = g.s["players"]["p1"]
    yard = next(k for k in PORTS if PORTS[k]["shipyard"])
    p["port"], p["cash"] = yard, cash
    return g, p


def buy(g, p, kind):
    return g.act("p1", {"type": "buy_ship", "ship": kind}, present=["p1"])


def fleet(g, p, spec, cargo=None):
    p["ships"] = []
    for kind, n, cannons in spec:
        for _ in range(n):
            sh = g._new_ship(kind)
            sh["cannons"] = cannons
            p["ships"].append(sh)
    p["cargo"] = dict(cargo or {})
    p["basis"] = {k: GOODS[k]["base"] for k in p["cargo"]}


def test_new_types_join_saved_settings_once():
    saved = config.defaults()
    del saved["ships"]["gunboat"], saved["ships"]["countryship"]
    saved["rules"]["fleet"]["seeded_ships"] = []
    for sh in saved["ships"].values():
        sh.pop("role", None)                        # saved before the column existed
    cfg, err = config.validate(saved)
    assert not err, err
    assert cfg["ships"]["gunboat"]["role"] == "escort" and cfg["ships"]["gunboat"]["hold"] == 0
    assert cfg["ships"]["countryship"]["role"] == "cargo" and cfg["ships"]["countryship"]["slots"] == 0
    assert all(cfg["ships"][k]["role"] == "trader" for k in ("junk", "lorcha", "barque", "clipper", "indiaman"))
    # deleted afterwards: stays deleted
    del cfg["ships"]["countryship"]
    again, err = config.validate(copy.deepcopy(cfg))
    assert not err and "countryship" not in again["ships"]
    # each class keeps to its job, even if Admin types a hold for an escort or guns for a cargo ship
    cfg["ships"]["gunboat"]["hold"] = 300
    cfg["ships"]["junk"]["role"] = "cargo"
    fixed, err = config.validate(cfg)
    assert fixed["ships"]["gunboat"]["hold"] == 0 and fixed["ships"]["junk"]["slots"] == 0
    assert err, "the starting ship must be a merchantman"


def test_classes_open_with_a_full_line_and_have_limits():
    setup()
    g, p = house()
    for kind in ("gunboat", "countryship"):
        try:
            buy(g, p, kind)
            raise AssertionError("sold before the line is full")
        except GameError as e:
            assert "merchantmen" in str(e)
    for _ in range(4):
        buy(g, p, "indiaman")
    try:
        buy(g, p, "junk")
        raise AssertionError("a sixth merchantman")
    except GameError:
        pass
    for _ in range(5):
        buy(g, p, "gunboat")
        buy(g, p, "countryship")
    assert len(p["ships"]) == 15
    for kind in ("gunboat", "countryship"):
        try:
            buy(g, p, kind)
            raise AssertionError("over the class limit")
        except GameError:
            pass
    assert g.capacity(p) == 60 + 4 * 500 + 5 * 750
    gb = next(i for i, sh in enumerate(p["ships"]) if sh["type"] == "gunboat")
    cs = next(i for i, sh in enumerate(p["ships"]) if sh["type"] == "countryship")
    for _ in range(6):
        g.act("p1", {"type": "buy_cannon", "index": gb}, present=["p1"])
    try:
        g.act("p1", {"type": "buy_cannon", "index": gb}, present=["p1"])
        raise AssertionError("a seventh cannon on a gunboat")
    except GameError:
        pass
    for action in ("buy_gun", "buy_cannon"):
        try:
            g.act("p1", {"type": action, "index": cs}, present=["p1"])
            raise AssertionError("guns on a cargo ship")
        except GameError:
            pass
    assert len({sh["name"] for sh in p["ships"]}) == 15, "every ship has her own name"
    view = g.view("p1")["me"]
    assert view["classes"]["escort"] == {"n": 5, "max": 5, "unlock": 5, "open": True}
    json.dumps(view)


def test_last_merchantman_is_kept():
    setup()
    g, p = house()
    fleet(g, p, [("junk", 1, 0), ("gunboat", 1, 0), ("countryship", 1, 0)])
    try:
        g.act("p1", {"type": "sell_ship", "index": 0}, present=["p1"])
        raise AssertionError("sold the last merchantman")
    except GameError as e:
        assert "merchantman" in str(e)
    g.act("p1", {"type": "sell_ship", "index": 1}, present=["p1"])      # an escort can go


def test_enemy_is_matched_to_the_fleet():
    setup()
    g, p = house()
    p["port"] = "hongkong"
    sizes = {}
    for name, spec in (("small", [("junk", 2, 0)]), ("big", [("indiaman", 5, 12)])):
        fleet(g, p, spec)
        if name == "small":
            for sh in p["ships"]:
                sh["guns"] = 4
        hull = [sum(g._muster(p, "pirates", "shanghai")["hp"]) for _ in range(40)]
        guns = [sum(g._muster(p, "pirates", "shanghai")["guns"]) for _ in range(40)]
        n = [g._muster(p, "pirates", "shanghai")["n"] for _ in range(40)]
        sizes[name] = (sum(hull) / 40.0, sum(guns) / 40.0, max(n))
    assert sizes["big"][0] > 5 * sizes["small"][0] and sizes["big"][1] > 5 * sizes["small"][1], sizes
    assert sizes["big"][2] <= R["battle"]["match_ships_max"], "a few tough junks, never sixty"
    # a rich hold and fame bring a closer fight
    fleet(g, p, [("indiaman", 5, 12)])
    empty = sum(g._muster(p, "pirates", "shanghai")["match"] for _ in range(60)) / 60
    p["cargo"] = {"opium": 400}
    p["fame"] = 20
    rich = sum(g._muster(p, "pirates", "shanghai")["match"] for _ in range(60)) / 60
    assert rich > empty + 0.3, (empty, rich)
    assert g._allure(p) > 1.0 > g._allure(dict(p, cargo={}, fame=0))


def _fight(g, p, kind="pirates"):
    g.s["sea"] = {"present": ["p1"], "news": [], "actual": {}}
    p["voy"] = {"origin": "hongkong", "dest": "shanghai", "stage": 3}
    m = g._muster(p, kind, "shanghai")
    g._battle_open(p, m["n"], kind, m)
    p["battle"]["stage"] = "fight"
    hits = []
    keep = g._enemy_fire_formed

    def spy(p_, b_, pirates):
        out = keep(p_, b_, pirates)
        hits.extend(out)
        return out
    g._enemy_fire_formed = spy
    while p.get("battle"):
        g._battle_step(p, "fight" if g.firepower(p) else "run")
    return p["fights"][-1], hits


def test_escorts_take_the_fire_and_the_rear_loses_cargo():
    setup()
    by_role, spilled_rear, rounds = {"escort": 0, "trader": 0, "cargo": 0}, 0, 0
    for seed in range(12):
        g, p = house(seed=seed)
        fleet(g, p, [("gunboat", 5, 6), ("indiaman", 5, 12), ("countryship", 5, 0)], {"silk": 2000, "tea": 2000})
        f, hits = _fight(g, p)
        for h in hits:
            by_role[h["role"]] += 1
            if h["role"] == "cargo":
                assert h.get("cargo") or not g.used(p), h      # every hit on a cargo ship sends cargo down
                spilled_rear += sum((h.get("cargo") or {}).values())
        assert f["match"] and f["enemy_hull"]
        json.dumps(f)
    assert by_role["escort"] > by_role["trader"] > by_role["cargo"] > 0, by_role
    assert spilled_rear > 0


def test_a_thin_screen_exposes_the_rear():
    setup()
    share = {}
    for name, escorts in (("screened", 5), ("bare", 0)):
        rear = total = 0
        for seed in range(10):
            g, p = house(seed=seed)
            fleet(g, p, [("gunboat", escorts, 6), ("indiaman", 5, 12), ("countryship", 5, 0)], {"silk": 3000})
            _f, hits = _fight(g, p)
            rear += sum(1 for h in hits if h["role"] == "cargo")
            total += len(hits)
        share[name] = rear / float(max(1, total))
    assert share["bare"] > 2 * share["screened"], share


def test_fame_grows_with_wins_and_fades():
    setup()
    g, p = house()
    fleet(g, p, [("indiaman", 5, 12)])
    p["fame"] = 0.0
    f, _ = _fight(g, p)
    if f["outcome"] == "won":
        assert p["fame"] == R["battle"]["fame_win"]
    g.s.pop("sea", None)
    p.pop("voy", None)
    # a quiet month at sea: no pirates, and the fame fades by fame_decay
    R["pirates"]["chance"] = 0.0
    R["liyuen"]["chance"] = 0.0
    p["fame"] = 10.0
    dest = next(k for k in PORTS if k != p["port"])
    g.act("p1", {"type": "sail", "dest": dest, "orders": "fight"}, present=["p1"])
    g.maybe_advance({"p1"})
    assert abs(p["fame"] - 10.0 * (1 - R["battle"]["fame_decay"])) < 1e-6, p["fame"]


def _parley(g, p):
    g.s["sea"] = {"present": ["p1"], "news": [], "actual": {}}
    p["voy"] = {"origin": "hongkong", "dest": "shanghai", "stage": 3}
    m = g._muster(p, "pirates", "shanghai")
    g._battle_open(p, m["n"], "pirates", m)
    return p["battle"]


def test_they_misjudge_a_hold_of_gold():
    """Now and then they take a rich fleet for a poor coaster: gold fools them more often than rice, the
    price is a fraction of the true one, and refusing it shows them the hold (full price, once more)."""
    setup()
    hits = {}
    for cargo in ("gold", "rice"):
        n = 0
        for seed in range(300):
            g, p = house(seed=seed)
            fleet(g, p, [("indiaman", 5, 12)], {cargo: 2000})
            b = _parley(g, p)
            if b.get("lowball"):
                n += 1
                assert b["price"] < (0.5 if cargo == "gold" else 1.0) * b["lowball"]["full"], b["lowball"]
                assert g.battle_view(p)["bargain"]
        hits[cargo] = n
    assert hits["gold"] > 1.4 * hits["rice"] > 0, hits
    # refuse the bargain: they ask the full price once, then the fight starts
    for seed in range(300):
        g, p = house(seed=seed)
        fleet(g, p, [("indiaman", 5, 12)], {"gold": 2000})
        b = _parley(g, p)
        if b.get("lowball"):
            break
    cheap, full = b["price"], b["lowball"]["full"]
    g._battle_step(p, "fight")
    assert b["stage"] == "parley" and b["price"] == full > cheap and b["round"] == 0
    v = g.battle_view(p)
    assert v["repriced"] and not v["bargain"]
    assert any(fr.get("mood") == "angry" for fr in b["beat"]["frames"])
    g._battle_step(p, "fight")
    assert b["stage"] == "fight" and b["round"] == 1
    # famous fleets are seldom fooled
    setup(lowball_fame=1.0)
    g, p = house(seed=1)
    fleet(g, p, [("indiaman", 5, 12)], {"gold": 2000})
    p["fame"] = 100
    fooled = 0
    for seed in range(100):
        g, p = house(seed=seed)
        fleet(g, p, [("indiaman", 5, 12)], {"gold": 2000})
        p["fame"] = 100
        fooled += bool(_parley(g, p).get("lowball"))
    assert fooled == 0


def test_old_style_fights_still_work():
    setup(match=False)
    g, p = house()
    fleet(g, p, [("junk", 2, 0)], {"rice": 10})
    for sh in p["ships"]:
        sh["guns"] = 4
    g._battle_open(p, 6, "pirates")
    assert p["battle"]["hp"] == [R["pirates"]["hp"]] * 6 and not p["battle"].get("match")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print("ok", fn.__name__)
    engine.configure(config.defaults())
    print("OK: fleet classes and matched battles ({} tests)".format(len(tests)))
