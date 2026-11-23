"""Game 3 review fixes (19 Nov 2026), after the $110M game: booms no longer stack, selling into a boom
uses it up, the dealers' purse, calmer porcelain/tea/silk and fewer hot tips, running costs and prices
that grow with the house, and pirates that grow with it too."""
import math
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import config  # noqa: E402
import engine  # noqa: E402
from engine import Game, GOODS, PORTS, R  # noqa: E402


def configure(**rules):
    cfg = config.defaults()
    cfg["rules"]["start"]["where"] = "home"
    cfg["rules"]["customs"]["enabled"] = False
    for path, value in rules.items():
        group, key = path.split("__")
        cfg["rules"][group][key] = value
    cfg, errors = config.validate(cfg)
    assert not errors, errors
    engine.configure(cfg)


@pytest.fixture
def house():
    original = engine.CFG
    configure()
    g = Game(seed=11)
    pid = g.pid_for_token(g.join("Ana", "Red Junk"))
    g.act(pid, {"type": "start"}, present=[pid])
    p = g.s["players"][pid]
    p["customs"] = None
    try:
        yield g, p
    finally:
        engine.configure(original)


def usual(port, good):
    return GOODS[good]["base"] * PORTS[port]["mods"].get(good, 1.0)


# ---- 1. booms don't stack ------------------------------------------------------------------------
def test_biggest_effect_wins(house):
    g, p = house
    port, good = "batavia", "tea"
    g.s["shocks"] = [{"port": port, "good": good, "mult": 2.0, "turns": 2}]
    g.s["windfalls"] = [{"port": port, "good": good, "kind": "boom", "mult": 5.18, "turns": 2, "foretold": True}]
    assert g._target(port, good) == pytest.approx(usual(port, good) * 5.18)
    # and a boom's price never runs past its own size, however the month swings
    for _ in range(30):
        g.s["prices"][port][good] = usual(port, good) * 30
        g.s["shocks"] = [{"port": port, "good": good, "mult": 2.0, "turns": 5}]
        g.s["windfalls"] = [{"port": port, "good": good, "kind": "boom", "mult": 5.18, "turns": 5, "foretold": True}]
        g._move_markets([])
        assert g.s["prices"][port][good] <= usual(port, good) * 5.18 + 1e-6


def test_stacking_can_be_switched_back_on():
    original = engine.CFG
    try:
        configure(events__stack_booms=True)
        g = Game(seed=2)
        g.s["shocks"] = [{"port": "batavia", "good": "tea", "mult": 2.0, "turns": 2}]
        g.s["windfalls"] = [{"port": "batavia", "good": "tea", "kind": "boom", "mult": 5.0, "turns": 2}]
        assert g._target("batavia", "tea") == pytest.approx(usual("batavia", "tea") * 10.0)
    finally:
        engine.configure(original)


def test_a_shortage_landing_on_a_boom_cannot_push_past_it(house):
    g, p = house
    port, good = "shanghai", "silk"
    g.s["windfalls"] = [{"port": port, "good": good, "kind": "boom", "mult": 4.65, "turns": 3}]
    g.s["prices"][port][good] = usual(port, good) * 4.65
    assert g._clamp(port, good, usual(port, good) * 9) == pytest.approx(usual(port, good) * 4.65)


# ---- 2. selling into a boom uses it up -------------------------------------------------------------
def _boom_here(g, p, good, mult=5.0, foretold=False):
    port = p["port"]
    g.s["windfalls"] = [{"port": port, "good": good, "kind": "boom", "mult": mult, "turns": 3, "foretold": foretold}]
    g.s["prices"][port][good] = usual(port, good) * mult
    return port


def test_a_full_hold_ends_the_boom(house):
    g, p = house
    good = "rice"
    port = _boom_here(g, p, good, foretold=True)
    qty = int(R["events"]["boom_eat_depths"] * GOODS[good]["depth"])
    p["cargo"] = {good: qty}
    g.act(p["id"], {"type": "sell", "good": good, "qty": qty}, present=[p["id"]])
    assert not g._windfall(port, good)
    assert any("used up the boom" in line for line in p["log"])
    after = g.s["prices"][port][good]
    g._move_markets([])
    # the price does not spring back to the boom: the sale's drop stays and the boom is gone
    assert g.s["prices"][port][good] <= max(after * 1.6, usual(port, good) * R["market"]["ceiling"])


def test_a_small_sale_leaves_most_of_it(house):
    g, p = house
    good = "rice"
    port = _boom_here(g, p, good)
    qty = int(0.1 * R["events"]["boom_eat_depths"] * GOODS[good]["depth"])
    p["cargo"] = {good: qty}
    g.act(p["id"], {"type": "sell", "good": good, "qty": qty}, present=[p["id"]])
    w = g._windfall(port, good)
    assert w and w["mult"] == pytest.approx(math.exp(math.log(5.0) * 0.9), rel=1e-3)


def test_selling_fills_a_shortage_too(house):
    g, p = house
    good, port = "rice", house[1]["port"]
    g.s["shocks"] = [{"port": port, "good": good, "mult": 3.0, "turns": 3}]
    qty = int(R["events"]["boom_eat_depths"] * GOODS[good]["depth"])
    p["cargo"] = {good: qty}
    g.act(p["id"], {"type": "sell", "good": good, "qty": qty}, present=[p["id"]])
    assert not [sh for sh in g.s["shocks"] if sh["port"] == port and sh["good"] == good]


# ---- 3. the dealers' purse -----------------------------------------------------------------------
def test_dealers_run_out_of_silver(house):
    g, p = house
    port, good = p["port"], "opium"
    size = g.purse_size(port, good)
    assert size == pytest.approx(R["market"]["purse_depths"] * GOODS[good]["depth"] * usual(port, good)
                                 * PORTS[port]["purse"])
    qty = 4000
    k = R["market"]["impact"] * qty / GOODS[good]["depth"]
    mid = g.s["prices"][port][good]
    full = int(math.floor(qty * (mid + mid / (1 + k)) / 2 * (1 - g.spread(p, port))))
    assert full > size, "the test lot must be bigger than the purse"
    paid, _ = g.quote(p, good, qty, "sell")
    assert paid == int(math.floor(size + (full - size) * R["market"]["purse_over"]))
    p["cargo"] = {good: qty}
    g.act(p["id"], {"type": "sell", "good": good, "qty": qty}, present=[p["id"]])
    assert g.purse_left(port, good) == 0
    view = g.view(p["id"], [p["id"]])["me"]["purse"]
    assert view[good][0] == 0 and view[good][1] == int(size)
    g._move_markets([])                          # a new month: the purse is full again
    assert g.purse_left(port, good) == pytest.approx(size)


def test_purse_off_pays_in_full():
    original = engine.CFG
    try:
        configure(market__purse_enabled=False)
        g = Game(seed=4)
        pid = g.pid_for_token(g.join("Bo", ""))
        g.act(pid, {"type": "start"}, present=[pid])
        p = g.s["players"][pid]
        assert g.purse_left(p["port"], "opium") is None and g.view(pid, [pid])["me"]["purse"] is None
        assert engine.static_data()["market"]["purse_over"] is None
    finally:
        engine.configure(original)


# ---- 4. calmer wild cargoes, fewer hot tips (saved settings, once) -------------------------------------
def test_saved_settings_calm_once():
    raw = config.defaults()
    raw["goods"]["tea"]["vol"], raw["goods"]["porcelain"]["vol"], raw["goods"]["silk"]["vol"] = 0.6, 0.4, 0.3
    raw["goods"]["opium"]["vol"] = 0.2
    raw["rules"]["registrar"].update({"hot_home_chance": 0.5, "hot_away_chance": 0.2})
    raw["rules"]["market"]["review3_v1"] = False
    cfg, errors = config.validate(raw)
    assert not errors, errors
    assert [cfg["goods"][g]["vol"] for g in ("porcelain", "tea", "silk", "opium")] == [0.2, 0.3, 0.2, 0.2]
    assert cfg["rules"]["registrar"]["hot_home_chance"] == 0.25 and cfg["rules"]["registrar"]["hot_away_chance"] == 0.1
    # saved and loaded again: nothing halves twice, and a later hand-set value stays
    cfg["rules"]["registrar"]["hot_home_chance"] = 0.4
    cfg["goods"]["tea"]["vol"] = 0.5
    cfg2, errors = config.validate(cfg)
    assert not errors and cfg2["rules"]["registrar"]["hot_home_chance"] == 0.4 and cfg2["goods"]["tea"]["vol"] == 0.5


def test_fresh_settings_have_the_new_chances():
    cfg, errors = config.validate({"rules": {"market": {"review3_v1": False}}})
    assert not errors
    assert cfg["rules"]["registrar"]["hot_home_chance"] == 0.25 and cfg["rules"]["registrar"]["hot_away_chance"] == 0.1


# ---- 5. running costs and prices that grow with the house ------------------------------------------
def test_monthly_wages(house):
    g, p = house
    f = R["fleet"]
    expect = sum(f["upkeep_rate"] * engine.SHIPS[sh["type"]]["price"] + f["upkeep_gun"] * (sh["guns"] + sh.get("cannons", 0))
                 for sh in p["ships"])
    assert g.upkeep(p) == int(round(expect))
    p["rank_id"] = "taipan"
    ids = [r["id"] for r in engine.CFG["ranks"]]
    steps = ids.index("taipan") - ids.index(f["upkeep_rank_from"])
    assert g.upkeep_rank_mult(p) == pytest.approx(1 + f["upkeep_rank"] * steps)


def test_costs_come_from_silver_then_bank_then_debt(house):
    g, p = house
    p["cash"], p["bank"], p["debt"] = 100.0, 50.0, 0.0
    owed = g._charge(p, 400)
    assert (p["cash"], p["bank"], p["debt"], owed) == (0.0, 0.0, 250.0, 250)


def test_december_bills_the_great_house_and_patronage(house):
    g, p = house
    e = R["estates"]
    p["estate"], p["estate_paid"] = 1, 500000.0
    g.s["patrons"] = {"singapore": p["id"]}
    p["share_paid"] = {"singapore": 300000.0}
    bills = g.yearly_upkeep(p)
    assert ("house", None, int(500000 * e["house_upkeep"])) in bills
    assert ("patron", "singapore", int(300000 * e["patron_upkeep"])) in bills
    g.s["turn"] = 11
    p["cash"], p["bank"], p["debt"] = 10 ** 7, 0.0, 0.0
    g._pay_running_costs(p)
    total = sum(b[2] for b in bills) + g.upkeep(p)
    assert p["cash"] == 10 ** 7 - total
    g.s["turn"] = 5                               # any other month: wages only
    p["cash"] = 10 ** 7
    g._pay_running_costs(p)
    assert p["cash"] == 10 ** 7 - g.upkeep(p)


def test_prices_grow_with_the_house(house):
    g, p = house
    e = R["estates"]
    p["cash"], p["bank"], p["debt"] = 0.0, 0.0, 0.0
    assert g.wealth_mult(p) == 1.0
    base = g.share_price("hongkong")
    p["bank"] = 25 * e["wealth_ref"]               # sqrt(25) = 5
    mult = g.wealth_mult(p)
    assert mult == pytest.approx(5.0, rel=0.02)
    assert g.share_price("hongkong", p) == pytest.approx(base * mult, rel=0.01)
    assert g.house_cost(p, 1) == pytest.approx(e["house_cost_1"] * mult, rel=0.01)
    assert g.estate_view(p)["stages"][0]["cost"] == g.house_cost(p, 1)
    p["bank"] = 10 ** 12
    assert g.wealth_mult(p) == e["wealth_max"]


def test_contract_fees_grow_with_the_house(house):
    g, p = house
    p["cash"], p["bank"], p["debt"] = 0.0, 0.0, 0.0
    scale = R["contracts"]["job_scale"]
    R["contracts"]["job_scale"] = False      # this is about the fee multiplier alone; bigger jobs are in game6_test.py
    cap = R["contracts"].get("fee_cap_share")
    R["contracts"]["fee_cap_share"] = 0      # and the fair-fee cap (Game 7 review) is in game7_test.py
    try:
        poor = [g._new_offer(p, "short") for _ in range(1)][0]
        p["bank"] = 16 * R["estates"]["wealth_ref"]
        rich = g._new_offer(p, "short")          # same month, same slot: the same dice
    finally:
        R["contracts"]["job_scale"] = scale
        R["contracts"]["fee_cap_share"] = cap
    if poor["kind"] != "standing":
        assert rich["fee"] == pytest.approx(poor["fee"] * g.wealth_mult(p), rel=0.05)


# ---- 6. pirates grow with the house -------------------------------------------------------------------
def test_rich_houses_draw_bigger_fleets(house):
    g, p = house
    p["cash"], p["bank"], p["debt"] = 0.0, 0.0, 0.0
    poor_allure, poor_pull, poor_share = g._allure(p), g.lord_pull(p), g.worth_share(p)
    g.rng.seed(7)
    poor = g._muster(p, "pirates")
    p["bank"] = 10 ** 9
    assert g.worth_share(p) > 0.99
    assert g._allure(p) == pytest.approx(poor_allure + R["battle"]["allure_worth"] * (g.worth_share(p) - poor_share), rel=1e-6)
    assert g.lord_pull(p) > poor_pull
    g.rng.seed(7)
    rich = g._muster(p, "pirates")
    assert rich["match"] > poor["match"] and rich["rounds"] > poor["rounds"]
    assert sum(rich["guns"]) >= sum(poor["guns"])
