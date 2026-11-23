"""Game 7 review (23 Nov 2026; project docs "SeaTrader Playtest Review - Game 7, $1.55 Billion in 10 Years"
and "SeaTrader Game 7 Decisions").

A calm wild-cargo market with rare, strong runs; Hong Master at $250M; commissions the fleet can carry for a
fair fee; great-house perks; a gift slider that stops at the useful amount; a desk that looks hard at a hold
declared at nothing; Li Yue priced on what she guards; savage storms that are not always the worst landing.

Run from the project folder:  python -m pytest tests/game7_test.py
"""
import copy
import math
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import config  # noqa: E402
import engine  # noqa: E402
import storm  # noqa: E402
from engine import Game, GOODS, PORTS  # noqa: E402


def setup(**rules):
    cfg = config.defaults()
    for path, value in rules.items():
        group, key = path.split("__")
        cfg["rules"][group][key] = value
    cfg, errors = config.validate(cfg)
    assert not errors, errors
    engine.configure(cfg)


def new_game(seed=1, cash=50000):
    g = Game(seed=seed)
    g.join("Ann", "")
    g.act("p1", {"type": "start"}, present=g.s["order"])
    p = g.s["players"]["p1"]
    p["cash"], p["bank"], p["debt"] = cash, 0, 0
    return g, p


def teardown_function(_fn):
    engine.configure(config.defaults())


def share_at(g, wild, level):
    xs = []
    for _ in range(360):
        g.s["windfalls"], g.s["shocks"] = [], []
        g._move_markets([])
        g.s["turn"] += 1
        for k in PORTS:
            if engine.sold_here(k, wild):
                xs.append(g.s["prices"][k][wild] / (GOODS[wild]["base"] * PORTS[k]["mods"].get(wild, 1.0)))
    return sum(1 for x in xs if x >= level) / float(len(xs)), max(xs)


# ---- 1. the market ----
def test_wild_cargo_is_calm_and_runs_carry_the_peaks():
    setup()
    wild = engine.R["market"]["wild_goods"][0]
    assert engine.vol_of(wild) == 0.12 and engine.reversion_of(wild) == 0.25
    assert engine.R["market"]["runs_chance"] == 0.03
    random.seed(3)
    g, _p = new_game()
    calm, top = share_at(g, wild, 3.0)
    assert calm < 0.12, calm                      # rarely at three times the usual price
    assert top > 3.0, top                         # but a run still gets there
    setup(market__game7_v1=True, market__wild_calm=False, market__wild_vol=0.5, market__wild_reversion=0.08,
          market__runs_chance=0.15)
    assert engine.vol_of(wild) >= 0.5             # the old rule is still there behind the switch
    random.seed(3)
    g, _p = new_game()
    old, _top = share_at(g, wild, 3.0)
    assert old > calm * 2, (old, calm)


def test_saved_settings_move_to_the_new_market_and_ranks_once():
    raw = config.defaults()
    raw["rules"]["market"].update(game7_v1=False, runs_chance=0.15, wild_reversion=0.08, runs_min=2, runs_max=4)
    for rank in raw["ranks"]:
        if rank["id"] == "hong_master":
            rank["worth"] = 100_000_000
        if rank["id"] == "taipan":
            rank["worth"] = 10_000_000
    cfg, errors = config.validate(copy.deepcopy(raw))
    assert not errors, errors
    mk = cfg["rules"]["market"]
    assert mk["game7_v1"] and mk["runs_chance"] == 0.03 and mk["wild_reversion"] == 0.25 and mk["runs_max"] == 5
    marks = {r["id"]: r["worth"] for r in cfg["ranks"]}
    assert marks["hong_master"] == 250_000_000 and marks["taipan"] == 15_000_000
    mk["runs_chance"] = 0.2                       # set by hand afterwards: it stays
    again, _errors = config.validate(copy.deepcopy(cfg))
    assert again["rules"]["market"]["runs_chance"] == 0.2


# ---- 2. ranks ----
def test_hong_master_sits_at_250_million_for_ten_years():
    setup()
    assert engine.rank_thresholds(10)[-3:] == [40_000_000, 100_000_000, 250_000_000]
    assert engine.rank_for(249_000_000, 10) == "Merchant Lord"


# ---- 3. commissions ----
def test_a_commission_fits_one_hold_for_a_fair_fee():
    setup()
    g, p = new_game()
    p["bank"] = 400_000_000
    hold = g.capacity(p)
    seen = 0
    for turn in range(1, 60):
        g.s["turn"] = turn
        for slot in ("short", "year"):
            offer = g._new_offer(p, slot)
            if not offer or offer["kind"] == "standing":
                continue
            seen += 1
            assert offer["qty"] <= max(hold, engine.R["contracts"]["min_qty"]), offer
            assert offer["fee"] <= 0.5 * offer["qty"] * engine.normal_price(offer["good"]) + 100, offer
    assert seen > 10


# ---- 4. the great house ----
def test_mansion_and_palace_have_a_dock_and_li_yues_ear():
    setup()
    g, p = new_game()
    p["port"] = engine.home_of(p)
    sh = p["ships"][0]
    plain, price = g.repair_rate(p, sh), g.protection_cost(p)
    p["estate"] = 3
    if g.house_stage(p) == 3:
        assert g.repair_rate(p, sh) < plain * 0.2
        assert g.house_perk(p, "protect") == 0.3
        assert g.protection_cost(p) <= price
    view = g.estate_view(p)
    assert view["stages"][1]["repair"] == 0.5 and view["stages"][2]["protect"] == 0.3


# ---- 5. gifts ----
def test_the_gift_slider_stops_where_silver_stops_buying_standing():
    setup()
    g, p = new_game(cash=10 ** 9)
    port = p["port"]
    p["rep"][port] = 75.0
    view = g.gift_view(p)
    appetite = g.gift_appetite(port, p)
    assert view["max"] < appetite * engine.R["gift"]["max_x"]
    most = g.gift_gain(port, 75.0, appetite * 1000, p)
    assert most - g.gift_gain(port, 75.0, view["max"], p) <= 0.5 + 1e-6
    setup(gift__useful_within=0)
    g, p = new_game(cash=10 ** 9)
    p["rep"][p["port"]] = 75.0
    assert g.gift_view(p)["max"] >= g.gift_appetite(p["port"], p) * engine.R["gift"]["max_x"] * 0.9


# ---- 6. the desk ----
def test_declaring_nothing_on_a_rich_hold_is_usually_stopped():
    setup()
    cx = {"greed": 1.0, "cunning": 1.0, "rep": 0.2, "rep_buy": 0.4, "diff": 1.0, "mood": 1.0}
    line = lambda v: {"value": v, "appetite": 1.0}
    small = sum(Game.customs_odds(cx, line(10_000), 0))
    big = sum(Game.customs_odds(cx, line(150_000_000), 0))
    assert big > 0.5 > small, (small, big)
    less_before = Game.customs_odds(cx, line(150_000_000), 120_000_000)
    setup(customs__zero_audit=False)
    assert sum(Game.customs_odds(cx, line(150_000_000), 0)) < big
    assert Game.customs_odds(cx, line(150_000_000), 120_000_000) == less_before      # Pay Less is untouched
    assert "m.customs_nothing" in engine.TEXT


# ---- 7. protection ----
def test_li_yue_prices_what_she_guards_not_the_bank():
    setup()
    g, p = new_game()
    lean = g.protection_cost(p)
    p["bank"] = 500_000_000
    assert g.protection_cost(p) == lean           # banked silver no longer moves her price
    p["carried"] = [20_000_000] * 8
    assert g.protection_cost(p) > lean            # a rich hold on recent sailings does
    setup(liyuen__cost_basis="worth")
    g, p = new_game()
    lean = g.protection_cost(p)
    p["bank"] = 500_000_000
    assert g.protection_cost(p) > lean


# ---- 8. savage storms ----
def test_a_savage_storm_is_not_always_the_worst_landing():
    setup()
    ranked = [{"port": "a", "yard": True}, {"port": "b", "yard": False}, {"port": "c", "yard": True},
              {"port": "d", "yard": False}]
    assert storm.pick_port(ranked, "savage", 0.10)["port"] == "d"
    assert storm.pick_port(ranked, "savage", 0.90)["port"] == "c"
    assert storm.pick_port(ranked, "savage")["port"] == "d"
    assert storm.pick_port(ranked[:1], "savage", 0.99)["port"] == "a"
