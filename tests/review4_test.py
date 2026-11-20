"""Game 4 review fixes (20 Nov 2026), after the $5.8 million game: Maijiuana's runs and wide range, three
kinds of enemy (raiders, a small band to spare, the war fleet), a fair price to pass, crippled escorts,
the flagship's flat wage, laying ships up at home, wages carried by empty hold, net worth at what the
dealers would pay, bank interest at 1%, the patronage count and the Mayor's offers.
Run from the game folder: python -m pytest tests/review4_test.py"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import config  # noqa: E402
import engine  # noqa: E402
import strings  # noqa: E402
from engine import Game, GameError, GOODS, PORTS, R, SHIPS  # noqa: E402


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


# ---- 1. Maijiuana (porcelain) runs and swings wide ------------------------------------------------
def test_wild_cargo_runs_and_range():
    configure()
    assert engine.is_wild("porcelain") and not engine.is_wild("tea")
    assert engine.price_limits("porcelain") == (0.15, 6.0)
    assert engine.price_limits("tea") == (R["market"]["floor"], R["market"]["ceiling"])
    g, pid, p = one_house()
    port = p["port"]
    usual = GOODS["porcelain"]["base"] * PORTS[port]["mods"].get("porcelain", 1.0)
    lo = hi = 1.0
    runs = 0
    for _ in range(240):
        g.s["windfalls"], g.s["shocks"] = [], []
        before = set((k, x) for k, row in g.s.get("runs", {}).items() for x in row)
        g._move_markets([])
        g.s["turn"] += 1
        runs += len(set((k, x) for k, row in g.s.get("runs", {}).items() for x in row) - before)
        for k in PORTS:
            u = GOODS["porcelain"]["base"] * PORTS[k]["mods"].get("porcelain", 1.0)
            if g._lift(k, "porcelain") != 1.0:
                continue                                  # a boom or crash may run past the usual limits
            r = g.s["prices"][k]["porcelain"] / u
            lo, hi = min(lo, r), max(hi, r)
            assert 0.15 - 1e-9 <= r <= 6.0 + 1e-9
            if g._lift(k, "tea") == 1.0:                 # no glut, shortage, crash or boom on tea there
                t = g.s["prices"][k]["tea"] / (GOODS["tea"]["base"] * PORTS[k]["mods"].get("tea", 1.0))
                assert R["market"]["floor"] - 1e-9 <= t <= R["market"]["ceiling"] + 1e-9
    assert runs > 50, runs                        # runs start often across ten ports over 20 years
    assert hi > 3.0 and lo < 0.4, (lo, hi)        # and the price really travels
    assert usual > 0


def test_runs_keep_the_months_other_dice():
    """The run dice are their own: with the runs switched off the rest of the market moves the same."""
    configure()
    g1, _, _ = one_house(seed=9)
    configure(market__runs_chance=0.0)
    g2, _, _ = one_house(seed=9)
    configure()
    g1._move_markets([])
    configure(market__runs_chance=0.0)
    g2._move_markets([])
    assert g1.s["prices"][g1.s["players"]["p1"]["port"]]["tea"] == g2.s["prices"][g2.s["players"]["p1"]["port"]]["tea"]


# ---- 2. bank interest -------------------------------------------------------------------------------
def test_bank_interest_moves_to_one_percent_once():
    old = config.defaults()
    old["rules"]["bank"]["bank_rate"] = 0.005
    old["rules"]["market"]["review4_v1"] = False
    cfg, errors = config.validate(old)
    assert not errors and cfg["rules"]["bank"]["bank_rate"] == 0.01 and cfg["rules"]["market"]["review4_v1"]
    mine = config.defaults()
    mine["rules"]["bank"]["bank_rate"] = 0.007
    mine["rules"]["market"]["review4_v1"] = False
    cfg, _ = config.validate(mine)
    assert cfg["rules"]["bank"]["bank_rate"] == 0.007          # a rate set by hand stays
    again = config.defaults()
    again["rules"]["bank"]["bank_rate"] = 0.005
    again["rules"]["market"]["review4_v1"] = True
    cfg, _ = config.validate(again)
    assert cfg["rules"]["bank"]["bank_rate"] == 0.005          # only once


# ---- 3. the flagship's wage ------------------------------------------------------------------------
def test_flagship_wage_is_flat():
    configure()
    flag = ship_of("flagship")
    sh = {"type": flag, "guns": 0, "cannons": 0}
    assert Game.ship_wage(sh) == R["fleet"]["flagship_wage"]
    assert Game.ship_wage(sh) < 0.02 * SHIPS[flag]["price"] or SHIPS[flag]["price"] <= 300000
    trader = ship_of("trader")
    assert Game.ship_wage({"type": trader, "guns": 2, "cannons": 0}) == 0.02 * SHIPS[trader]["price"] + 30


# ---- 4. laying ships up, and the empty-hold note ------------------------------------------------------
def test_lay_up_and_call_back_at_home():
    configure()
    g, pid, p = one_house()
    p["cash"] = 10 ** 7
    p["ships"].append(g._new_ship(ship_of("trader")))
    p["ships"].append(g._new_ship(ship_of("escort")))
    cap, worth, wage = g.capacity(p), g.worth(p), g.upkeep(p)
    escorts = g.class_count(p, "escort")
    g.act(pid, {"type": "lay_up", "index": 2})
    assert len(p["laid_up"]) == 1 and g.class_count(p, "escort") == escorts
    assert abs(g.worth(p) - worth) < 1.0
    assert g.upkeep(p) < wage
    g.act(pid, {"type": "lay_up", "index": 1})
    assert g.capacity(p) < cap
    try:
        g.act(pid, {"type": "lay_up", "index": 0})
        assert False, "the last ship can't be laid up"
    except GameError:
        pass
    g.act(pid, {"type": "recall", "index": 0})
    assert len(p["ships"]) == 2 and len(p["laid_up"]) == 1
    view = g.view(pid)["me"]
    assert view["laid_up"][0]["wage"] < view["laid_up"][0]["full_wage"]
    p["port"] = next(k for k in PORTS if k != engine.home_of(p))
    try:
        g.act(pid, {"type": "recall", "index": 0})
        assert False, "called back at home only"
    except GameError:
        pass


def test_idle_wages_are_noted():
    configure()
    g, pid, p = one_house()
    p["ships"] += [g._new_ship(ship_of("trader")) for _ in range(3)]
    p["cargo"] = {}
    p["log"] = []
    g._pay_running_costs(p)
    idle, empty = g.idle_wages(p)
    assert empty == 1.0 and idle > 0
    assert p["idle"]["last"] == idle
    assert any("empty hold" in line for line in p["log"]) == (idle >= R["fleet"]["idle_note_min"])


# ---- 5. net worth at what the dealers would pay ----------------------------------------------------------
def test_worth_is_what_dealers_pay():
    configure()
    g, pid, p = one_house()
    p["cargo"] = {"silk": 5000}
    sale, _ = g.quote(p, "silk", 5000, "sell")
    assert abs(g.goods_value(p) - sale) < 1e-6
    assert g.goods_value(p) < 5000 * g.s["prices"][p["port"]]["silk"]     # a full hold doesn't fetch the posted price
    snap = [f for f in g.firms() if f["id"] == pid][0]
    assert snap["worth_rule"] == "dealer" and abs(engine.worth_of(snap) - g.worth(p)) < 1.0


# ---- 6. sea battles ---------------------------------------------------------------------------------------
def battle_game(**rules):
    configure(pirates__chance=1.0, liyuen__chance=0.0, battle__match=True, battle__lowball=False,
              battle__allure_base=5.0, weather__risk_min=1.0, weather__risk_max=1.0,
              contraband__seize_chance=0.0, contraband__seize_banned=0.0, **rules)
    g = Game(seed=3)
    pid = g.pid_for_token(g.join("Ann", ""))
    g.act(pid, {"type": "start"}, present=[pid])
    p = g.s["players"][pid]
    p["ships"][0]["guns"] = 4
    p["cargo"] = {"silk": 20, "rice": 30}
    p["cash"] = 0
    return g, pid, p


def sail_into_fight(g, pid, p):
    dest = next(k for k in PORTS if k != p["port"])
    g.act(pid, {"type": "sail", "dest": dest, "orders": "fight"}, present=[pid])
    g.maybe_advance({pid})
    return p.get("battle")


def test_fleet_types_and_a_fair_price():
    seen = set()
    for turn in range(40):
        g, pid, p = battle_game()
        g.s["turn"] = turn
        b = sail_into_fight(g, pid, p)
        if not b:
            continue
        seen.add(b.get("fleet"))
        value = sum(q * GOODS[k]["base"] for k, q in p["cargo"].items())
        if b["stage"] == "parley":
            assert b["price"] <= b["worth_n"] * R["battle"]["parley_per_junk"] + 0.10 * value + 1
            plan = g.toll_plan(p, b["price"])
            assert plan["can_pay"] or plan["can_cargo"], plan           # passing is always possible with a hold
        if b.get("fleet") == "band":
            assert b["n"] <= R["battle"]["band_ships_max"]
            assert b["label"] == strings.EN["w.band_junks"]
    assert {"raiders", "band"} <= seen, seen


def test_sparing_a_band_gives_a_price():
    for turn in range(80):
        g, pid, p = battle_game(battle__band_share=1.0, battle__parley=False)
        g.s["turn"] = turn
        b = sail_into_fight(g, pid, p)
        if not b or b.get("fleet") != "band":
            continue
        try:
            g.act(pid, {"type": "sea", "choice": "spare"}, present=[pid])
            assert False, "no sparing before the first broadside"
        except GameError:
            pass
        g.act(pid, {"type": "sea", "choice": "fight"}, present=[pid])
        if p.get("battle") is None:
            continue                                   # sunk them all in one round
        assert g.battle_view(p)["can_spare"]
        g.act(pid, {"type": "sea", "choice": "spare"}, present=[pid])
        fight = p["fights"][-1]
        assert fight["outcome"] == "spared"
        assert any("parting gift" in line for line in p["log"])
        return
    assert False, "never met a band to spare"


def test_escorts_limp_home_crippled():
    configure(fleet__cripple_chance=1.0)
    g, pid, p = one_house()
    esc = g._new_ship(ship_of("escort"))
    esc["guns"], esc["hull"] = 3, 0
    p["ships"].append(esc)
    b = {"step": 0}
    g._check_sunk(p, "was sunk", b)
    assert esc in p["ships"] and esc["hull"] == 1 and esc["guns"] == 0 and esc.get("crippled")
    assert b["crippled"] == [esc["name"]]
    # Mending her costs about a third of a new one.
    rate = g.repair_rate(p, esc)
    full = rate * (SHIPS[esc["type"]]["hull"] - 1)
    assert full >= SHIPS[esc["type"]]["price"] * R["fleet"]["cripple_repair"] * 0.99
    p["cash"] = 10 ** 7
    p["port"] = next(k for k in PORTS if engine.port_has(p, k, "shipyard"))
    g._act_repair(p, {"index": len(p["ships"]) - 1})
    assert not esc.get("crippled") and esc["hull"] == SHIPS[esc["type"]]["hull"]
    configure(fleet__cripple_chance=0.0)
    g, pid, p = one_house()
    esc = g._new_ship(ship_of("escort"))
    esc["hull"] = 0
    p["ships"].append(esc)
    g._check_sunk(p, "was sunk", {"step": 0})
    assert esc not in p["ships"]


# ---- 7. the patronage line and the Mayor's offers --------------------------------------------------------
def test_mayor_offers_are_announced_at_home():
    configure()
    g, pid, p = one_house()
    p["log"] = []
    for o in (p.get("offers") or {}).values():
        if o:
            o.pop("told", None)
    g._contracts_month(p)
    offers = [o for o in (p.get("offers") or {}).values() if o]
    if offers:
        assert any("commission" in line for line in p["log"])
        p["log"] = []
        g._contracts_month(p)
        assert not any("commission" in line for line in p["log"])      # once for each offer


def test_patronage_counts_free_shares():
    configure()
    g, pid, p = one_house()
    port = p["port"]
    g.s.setdefault("patrons", {})[port] = pid
    g.s.setdefault("shares", {})[port] = {pid: 1}
    p["estate_paid"] = 100000.0
    p["log"] = []
    g.s["turn"] = 11
    g._pay_running_costs(p)
    line = [x for x in p["log"] if "upkeep is paid" in x or "patronage" in x]
    assert line and "1 port" in line[-1], line


def test_new_wording_has_family_versions_where_it_flirts():
    for key in ("l.spared", "n.fight_spared", "battle.say.spared.0", "m.laid_up", "l.idle_wages"):
        assert key in strings.EN and key in strings.FAMILY
