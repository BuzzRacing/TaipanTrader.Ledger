"""The Fleet tab's monthly cost ledger (20 Nov 2026): each class of ship's crew and hull upkeep, guns and cannons,
rank pay, the share that carried empty hold, repairs owed and the ships laid up must add up to the month's real bill.
Run from the game folder: python -m pytest tests/fleet_ledger_test.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import config  # noqa: E402
import engine  # noqa: E402
import strings  # noqa: E402
from engine import Game, R, SHIPS  # noqa: E402


def configure(**rules):
    cfg = config.defaults()
    cfg["rules"]["start"]["where"] = "home"
    cfg["rules"]["customs"]["enabled"] = False
    cfg["rules"]["weather"]["storm_chance"] = [0, 0, 0, 0]
    for path, value in rules.items():
        group, key = path.split("__")
        cfg["rules"][group][key] = value
    cfg, errors = config.validate(cfg)
    assert not errors, errors
    engine.configure(cfg)
    engine.MULT["pirates"] = 1.0
    return cfg


def one_house(seed=4):
    g = Game(seed=seed)
    pid = g.pid_for_token(g.join("Ada", ""))
    g.act(pid, {"type": "start"}, present=[pid])
    return g, pid, g.s["players"][pid]


def ship_of(role):
    return next(k for k, v in SHIPS.items() if v.get("role", "trader") == role)


def fleet(g, p):
    p["cash"] = 10 ** 7
    p["ships"].append(g._new_ship(ship_of("trader")))
    p["ships"].append(g._new_ship(ship_of("escort")))
    p["ships"].append(g._new_ship(ship_of("cargo")))
    for sh in p["ships"]:                       # guns and cannons, so the guns line has something to say
        if SHIPS[sh["type"]].get("slots", 0) >= 4:
            sh["guns"], sh["cannons"] = 2, 1
    esc = next(sh for sh in p["ships"] if engine.role_of(sh["type"]) == "escort")
    esc["hull"] = max(1, esc["hull"] - 7)       # one hull owes the yard


def ledger_sum(L):
    return sum(c["total"] for c in L["classes"].values()) + L["laid"]["now"]


def test_classes_add_up_to_the_months_bill():
    configure()
    g, pid, p = one_house()
    fleet(g, p)
    L = g.view(pid)["me"]["fleet_ledger"]
    assert L["on"] and L["bill"] == g.upkeep(p) > 0
    assert ledger_sum(L) == L["bill"]
    for c in L["classes"].values():
        assert c["crew"] + c["guns"] + c["rank"] == c["total"]


def test_rank_pay_and_guns_are_split_out():
    configure()
    g, pid, p = one_house()
    fleet(g, p)
    f = R["fleet"]
    ids = [r["id"] for r in engine.CFG["ranks"]]
    p["rank_id"] = ids[min(len(ids) - 1, ids.index(f["upkeep_rank_from"]) + 2)]
    L = g.fleet_ledger(p)
    mult = g.upkeep_rank_mult(p)
    assert mult > 1 and L["rank_mult"] == round(mult, 4)
    assert ledger_sum(L) == g.upkeep(p)
    assert all(c["rank"] >= 0 for c in L["classes"].values())
    trader = L["classes"]["trader"]
    guns = sum(sh["guns"] + sh.get("cannons", 0) for sh in p["ships"] if engine.role_of(sh["type"]) == "trader")
    assert trader["guns"] == int(round(f["upkeep_gun"] * guns))


def test_empty_hold_share_adds_to_the_idle_wages():
    configure()
    g, pid, p = one_house()
    fleet(g, p)
    p["cargo"] = {}
    L = g.fleet_ledger(p)
    idle, empty = g.idle_wages(p)
    assert L["empty"] == empty == 1.0
    assert abs(sum(c["idle"] for c in L["classes"].values()) - idle) <= len(L["classes"])
    assert L["classes"]["escort"]["idle"] == 0          # an escort has no hold to leave empty
    assert L["classes"]["escort"]["hold"] == 0 and L["classes"]["trader"]["hold"] > 0
    # a full hold wastes nothing
    p["cargo"] = {"tea": g.capacity(p)}
    assert all(c["idle"] == 0 for c in g.fleet_ledger(p)["classes"].values())


def test_repairs_owed_are_per_class():
    configure()
    g, pid, p = one_house()
    fleet(g, p)
    me = g.view(pid)["me"]
    L = me["fleet_ledger"]
    by_role = {}
    for s in me["ships"]:
        by_role[s["role"]] = by_role.get(s["role"], 0) + s["repair"]
    assert {r: c["repair"] for r, c in L["classes"].items()} == by_role
    assert L["classes"]["escort"]["repair"] > 0


def test_ships_laid_up_are_counted_apart():
    configure()
    g, pid, p = one_house()
    fleet(g, p)
    g.act(pid, {"type": "lay_up", "index": len(p["ships"]) - 1})
    assert p["laid_up"]
    L = g.view(pid)["me"]["fleet_ledger"]
    assert L["laid"]["n"] == 1 and 0 < L["laid"]["now"] < L["laid"]["full"]
    assert abs(L["laid"]["now"] - L["laid"]["full"] * R["fleet"]["laid_up_wage"]) <= 1
    assert ledger_sum(L) == L["bill"] == g.upkeep(p)


def test_wages_switched_off_gives_an_empty_ledger():
    configure(fleet__upkeep_enabled=False)
    g, pid, p = one_house()
    fleet(g, p)
    L = g.view(pid)["me"]["fleet_ledger"]
    assert not L["on"] and L["bill"] == 0
    assert all(c["total"] == 0 for c in L["classes"].values())


def test_flagship_wage_is_flat_in_the_ledger():
    configure()
    g, pid, p = one_house()
    fleet(g, p)
    flag = ship_of("flagship")
    p["ships"].append(g._new_ship(flag))
    L = g.fleet_ledger(p)
    assert "flagship" in L["classes"] and L["classes"]["flagship"]["n"] == 1
    assert L["classes"]["flagship"]["crew"] == int(round(R["fleet"]["flagship_wage"]))
    assert ledger_sum(L) == g.upkeep(p)


def test_the_ledger_wording_is_there():
    for key in ("fleet.ledger.title", "fleet.ledger.fleet", "fleet.ledger.crew", "fleet.ledger.guns", "fleet.ledger.rank",
                "fleet.ledger.total", "fleet.ledger.year", "fleet.ledger.idle", "fleet.ledger.per_hold",
                "fleet.ledger.repair", "fleet.ledger.ships", "fleet.ledger.layup", "fleet.ledger.layup_save",
                "fleet.ledger.layup_tip", "fleet.ledger.laid", "fleet.ledger.flat"):
        assert strings.EN.get(key), key
