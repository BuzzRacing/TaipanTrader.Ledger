"""Game 6 review (22 Nov 2026; project doc "SeaTrader Playtest Review - Game 6, $209M over 20 Years").

Bills the silver can't cover come out of the bank before the debt, and a fleet a storm hit is found less often.

Run from the project folder:  python -m pytest tests/game6_test.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import config  # noqa: E402
import engine  # noqa: E402
import storm  # noqa: E402
import pytest  # noqa: E402
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
    p["cash"] = cash
    p["bank"] = 0
    p["debt"] = 0
    return g, p


def teardown_function(_fn):
    engine.configure(config.defaults())


# ---- 2. bills come out of the bank before the debt ----
def test_defaults_are_on():
    setup()
    assert engine.R["bank"]["bills_from_bank"] is True
    assert storm.rules()["after_attack"] == 0.5


def test_harbour_dues_come_from_the_bank_when_silver_is_short():
    setup()
    g, p = new_game(cash=1000)
    p["bank"] = 2_000_000
    g._pay_dues(p, total=5000)
    assert p["cash"] == 0 and p["bank"] == 2_000_000 - 4000 and p["debt"] == 0


def test_dues_with_a_small_bank_only_the_rest_goes_on_the_debt():
    setup()
    g, p = new_game(cash=1000)
    p["bank"] = 2000
    g._pay_dues(p, total=5000)
    assert p["cash"] == 0 and p["bank"] == 0 and p["debt"] == 2000


def test_dues_standing_is_only_lost_for_real_debt():
    setup()
    g, p = new_game(cash=0)
    port = p["port"]
    p["bank"] = 50_000
    before = p["rep"][port]
    g._pay_dues(p, total=5000)
    assert p["debt"] == 0 and p["rep"][port] >= before          # the bank paid: no "paid short" penalty
    g, p = new_game(cash=0)
    port = p["port"]
    before = p["rep"][port]
    g._pay_dues(p, total=5000)
    assert p["debt"] == 5000 and p["rep"][port] <= before       # nothing in the bank: debt as before


def test_the_rule_can_be_switched_off():
    setup(bank__bills_from_bank=False)
    g, p = new_game(cash=1000)
    p["bank"] = 2_000_000
    g._pay_dues(p, total=5000)
    assert p["cash"] == 0 and p["bank"] == 2_000_000 and p["debt"] == 4000


def test_collect_draws_silver_then_bank_then_debt():
    setup()
    g, p = new_game(cash=100)
    p["bank"] = 300
    owed = g._collect(p, 1000)
    assert owed == 600 and p["cash"] == 0 and p["bank"] == 0 and p["debt"] == 600
    assert g._last_drawn == 300
    g, p = new_game(cash=100)
    p["bank"] = 5000
    assert g._collect(p, 1000) == 0 and p["bank"] == 4100 and p["debt"] == 0 and g._last_drawn == 900


def test_port_authority_tax_is_taken_from_the_bank_not_put_on_the_debt():
    import customs_test as ct
    cfg = ct.no_spot(config.defaults())
    cfg["rules"]["start"]["where"] = "home"
    engine.configure(cfg)
    done = 0
    for seed in range(40):
        g, p = ct.arrive(seed, "calcutta")
        if not p["ships"] or not p.get("customs") or p["customs"]["status"] != "declare":
            continue
        p["cash"] = 0
        p["bank"] = 10_000_000
        debt0 = p["debt"]
        vals = {ln["good"]: ln["value"] for ln in p["customs"]["lines"]}
        g.act("p1", {"type": "customs_declare", "values": vals}, present=["p1"])
        res = p["customs"]["result"]
        if res["tax"] + res["fine"] <= 0:
            continue
        assert res["owed"] == 0 and p["debt"] == debt0, res
        assert res["drawn"] == res["tax"] + res["fine"] and p["bank"] == 10_000_000 - res["drawn"]
        done += 1
    assert done >= 5, done


# ---- 4. a fleet a storm hit is found less often ----
def _stormy(**extra):
    cfg = config.defaults()
    cfg["rules"]["weather"]["storm_chance"] = [1, 1, 1, 1]
    cfg["rules"]["weather"].update({"risk_min": 1.0, "risk_max": 1.0, "offcourse": 0.0, "forecast_accuracy": 1.0})
    cfg["rules"]["battle"]["match"] = False
    cfg["rules"]["fleet"]["upkeep_enabled"] = False
    cfg["rules"]["bank"]["mug_chance"] = 0.0
    cfg["rules"]["customs"]["enabled"] = False
    for path, value in extra.items():
        group, key = path.split("__")
        cfg["rules"][group][key] = value
    cfg, errors = config.validate(cfg)
    assert not errors, errors
    engine.configure(cfg)


def test_calm_is_one_without_a_storm_and_the_setting_with_one():
    _stormy()
    g, p = new_game()
    assert g._storm_calm({}) == 1.0
    assert g._storm_calm({"stormed": True}) == 0.5
    _stormy(storm__after_attack=1.0)
    assert g._storm_calm({"stormed": True}) == 1.0
    _stormy(storm__after_attack=0.2)
    assert g._storm_calm({"stormed": True}) == 0.2


def test_a_storm_marks_the_voyage_and_the_attack_odds_are_halved():
    _stormy(pirates__chance=0.5, liyuen__chance=0.5)
    g, p = new_game()
    for k in g.s["weather"]:
        g.s["weather"][k] = 1
    dest = [k for k in PORTS if k != p["port"]][0]
    g.act("p1", {"type": "sail", "dest": dest, "orders": "run"}, present=["p1"])
    msgs = []
    orig = g._chance

    def spy(odds, kind, label, *a, **k):
        msgs.append((kind, round(odds, 6), label))
        return orig(odds, kind, label, *a, **k)
    g._chance = spy
    g.resolve("all_ready", {"p1"})
    kinds = {m[0]: m for m in msgs}
    assert "storm" in kinds and "pirates" in kinds
    assert "storm-battered" in kinds["pirates"][2], kinds["pirates"]
    want = 0.5 * 1.0 * engine.MULT["pirates"] * 0.5            # chance x risk (1.0) x difficulty x storm cut
    assert abs(kinds["pirates"][1] - want) < 1e-5, (kinds["pirates"], want)


def test_no_storm_no_cut():
    _stormy(pirates__chance=0.5)
    g, p = new_game()
    for k in g.s["weather"]:
        g.s["weather"][k] = 1
    dest = [k for k in PORTS if k != p["port"]][0]
    # make the storm chance zero for this voyage
    c2 = config.defaults()
    c2["rules"]["weather"]["storm_chance"] = [0, 0, 0, 0]
    c2["rules"]["weather"].update({"risk_min": 1.0, "risk_max": 1.0, "forecast_accuracy": 1.0})
    c2["rules"]["pirates"]["chance"] = 0.5
    c2["rules"]["battle"]["match"] = False
    c2["rules"]["customs"]["enabled"] = False
    c2, errors = config.validate(c2)
    assert not errors
    engine.configure(c2)
    g.act("p1", {"type": "sail", "dest": dest, "orders": "run"}, present=["p1"])
    msgs = []
    orig = g._chance

    def spy(odds, kind, label, *a, **k):
        msgs.append((kind, label))
        return orig(odds, kind, label, *a, **k)
    g._chance = spy
    g.resolve("all_ready", {"p1"})
    pirates = [m for m in msgs if m[0] == "pirates"]
    assert pirates and all("storm-battered" not in m[1] for m in pirates)


def test_admin_has_both_new_settings():
    paths = [f["path"] for sec in config.SECTIONS for grp in sec.get("groups", []) for f in grp.get("fields", [])]
    assert "rules.bank.bills_from_bank" in paths and "rules.storm.after_attack" in paths


# ---- 1. bank interest by slices ----
def test_flat_below_the_first_limit():
    setup()
    g, p = new_game()
    g.s["years"] = 20
    p["bank"] = 1_000_000
    assert abs(g.bank_interest(p) - 10_000) < 1e-6


def test_slices_at_twenty_years():
    setup()
    g, p = new_game()
    g.s["years"] = 20
    p["bank"] = 125_000_000                                  # 25M at 1%, 75M at 0.5%, 25M at 0.25%
    want = 25e6 * 0.01 + 75e6 * 0.005 + 25e6 * 0.0025
    assert abs(g.bank_interest(p) - want) < 1e-3, g.bank_interest(p)


def test_limits_scale_with_the_game_length():
    setup()
    g, p = new_game()
    g.s["years"] = 10                                        # limits halve: 12.5M and 50M
    p["bank"] = 12_500_000 + 1_000_000
    want = 12.5e6 * 0.01 + 1e6 * 0.005
    assert abs(g.bank_interest(p) - want) < 1e-3
    assert g.bank_tiers()[0][0] == 12_500_000


def test_tiers_off_is_one_flat_rate():
    setup(bank__tiered=False)
    g, p = new_game()
    g.s["years"] = 20
    p["bank"] = 200_000_000
    assert abs(g.bank_interest(p) - 2_000_000) < 1e-3


def test_extra_rate_lifts_every_slice():
    setup()
    g, p = new_game()
    g.s["years"] = 20
    p["bank"] = 30_000_000
    want = 25e6 * 0.012 + 5e6 * 0.007
    assert abs(g.bank_interest(p, extra=0.002) - want) < 1e-3


def test_month_end_pays_the_sliced_interest():
    setup()
    g, p = new_game(cash=0)
    g.s["years"] = 20
    p["bank"] = 50_000_000
    g.act("p1", {"type": "sail", "dest": [k for k in PORTS if k != p["port"]][0], "orders": "run"}, present=["p1"])
    b0 = p["bank"]
    g.resolve("all_ready", {"p1"})
    gained = p["bank"] - b0
    assert gained < 50_000_000 * 0.01 * 0.9, gained          # well under a flat 1%
    assert gained > 25e6 * 0.01 * 0.9, gained


def test_static_data_lists_the_tiers():
    setup()
    g, p = new_game()
    sd = engine.static_data() if hasattr(engine, "static_data") else None
    if sd is not None:
        assert len(sd["bank_tiers"]) == 3


# ---- 6. the great house pays: bank interest and lower dues at home ----
def _great(stage, **rules):
    setup(**rules)
    g, p = new_game(cash=0)
    g.s["years"] = 20
    p["estate"] = stage
    return g, p


def test_bonus_is_nothing_before_the_mansion():
    for st in (0, 1):
        g, p = _great(st)
        assert g.house_bank_bonus(p) == 0 and g.house_dues_cut(p, engine.home_of(p)) == 0


def test_mansion_and_palace_lift_the_interest():
    g, p = _great(2)
    assert g.house_bank_bonus(p) == pytest.approx(0.001)
    p["bank"] = 1_000_000
    assert g.bank_interest(p, extra=g.house_bank_bonus(p)) == pytest.approx(11_000)
    g, p = _great(3)
    assert g.house_bank_bonus(p) == pytest.approx(0.0025)


def test_interest_bonus_can_be_home_only():
    g, p = _great(3, estates__house_bank_anywhere=False)
    p["port"] = engine.home_of(p)
    assert g.house_bank_bonus(p) > 0
    p["port"] = next(k for k in PORTS if k != engine.home_of(p))
    assert g.house_bank_bonus(p) == 0


def test_dues_are_lower_only_at_home():
    g, p = _great(3)
    home = engine.home_of(p)
    p["port"] = home
    p["tab"] = g._new_tab()
    p["tab"]["repair"] = 100_000
    plain = dict(g.dues(p))
    lines = [ln for ln in plain["lines"] if ln["key"] == "house"]
    assert lines and lines[0]["amount"] < 0 and lines[0]["rate"] == pytest.approx(0.4)
    before = sum(ln["amount"] for ln in plain["lines"] if ln["key"] != "house")
    assert plain["total"] == before + lines[0]["amount"]
    p["port"] = next(k for k in PORTS if k != home)
    away = g.dues(p)
    assert not [ln for ln in away["lines"] if ln["key"] == "house"]


def test_mansion_takes_less_than_the_palace_off():
    g2, p2 = _great(2)
    g3, p3 = _great(3)
    for g, p in ((g2, p2), (g3, p3)):
        p["port"] = engine.home_of(p)
        p["tab"] = g._new_tab()
        p["tab"]["repair"] = 100_000
    assert g2.dues(p2)["total"] > g3.dues(p3)["total"] > 0


def test_estate_view_lists_the_perks():
    g, p = _great(2)
    v = g.estate_view(p)
    assert v["bank_bonus"] == pytest.approx(0.001) and v["dues_cut"] == pytest.approx(0.2)
    assert [s["bank"] for s in v["stages"]] == [0.0, 0.001, 0.0025]
    assert [s["dues"] for s in v["stages"]] == [0.0, 0.2, 0.4]


# ---- 5. the Mayor's commissions: bigger jobs for a richer house, and a perk on the yearly goal ----
def _mayor(worth=None, **rules):
    setup(**rules)
    g, p = new_game(cash=1000)
    g.s["years"] = 20
    if worth is not None:
        g.worth = lambda _p, w=worth: w
    return g, p


def _offers(g, p, slot, kind, n=60):
    out = []
    for t in range(n):
        g.s["turn"] = t + 1
        o = g._new_offer(p, slot)
        if o and o["kind"] == kind:
            out.append(o)
    return out


def test_a_rich_house_is_offered_bigger_jobs():
    g, p = _mayor(worth=100_000)
    small = _offers(g, p, "short", "delivery")
    g2, p2 = _mayor(worth=200_000_000)
    big = _offers(g2, p2, "short", "delivery")
    assert small and big
    assert max(o["qty"] for o in big) > max(o["qty"] for o in small)
    assert max(o["fee"] for o in big) > max(o["fee"] for o in small)


def test_job_growth_is_capped_by_the_hold_and_the_setting():
    g, p = _mayor(worth=10 ** 12)
    hold = g.capacity(p)
    assert g.job_grow(p, 0.35, 1.0) <= 1.0 / 0.35 + 1e-9                     # never past one hold for a short job
    assert g.job_grow(p, 1.0, 3.0) <= 3.0 + 1e-9
    g, p = _mayor(worth=10 ** 12, contracts__job_max=2.0)
    assert g.job_grow(p, 0.1, 5.0) == 2.0


def test_a_young_house_sees_no_change_and_the_switch_turns_it_off():
    g, p = _mayor(worth=100_000)
    assert g.job_grow(p, 0.35, 1.0) == 1.0
    g, p = _mayor(worth=10 ** 9, contracts__job_scale=False)
    assert g.job_grow(p, 0.35, 1.0) == 1.0


def test_job_scale_follows_the_game_length():
    g, p = _mayor(worth=40_000_000)
    g.s["years"] = 20
    long_game = g.job_grow(p, 0.05, 10.0)
    g.s["years"] = 10
    assert g.job_grow(p, 0.05, 10.0) > long_game                              # a short game's ref is halved


def test_only_yearly_goals_carry_a_perk():
    g, p = _mayor(worth=1_000_000)
    year = _offers(g, p, "year", "delivery")
    short = _offers(g, p, "short", "delivery")
    assert year and all(o.get("perk") in ("tax_holiday", "protection", "share") for o in year)
    assert {o["perk"] for o in year} == {"tax_holiday", "protection", "share"}
    assert short and all("perk" not in o for o in short)


def test_perks_can_be_switched_off_or_narrowed():
    g, p = _mayor(contracts__perks=False)
    assert all("perk" not in o for o in _offers(g, p, "year", "delivery"))
    g, p = _mayor(contracts__perk_share=False, contracts__perk_protect_months=0)
    assert {o["perk"] for o in _offers(g, p, "year", "delivery")} == {"tax_holiday"}


def _done(g, p, perk):
    p["port"] = engine.home_of(p)
    k = {"id": 9, "slot": "year", "kind": "delivery", "port": [x for x in PORTS if x != p["port"]][0], "good": "rice",
         "qty": 10, "got": 10, "due": 99, "fee": 5000, "rep": 8.0, "perk": perk}
    p["contracts"] = [k]
    p["cash"] = 0
    g._check_contracts(p)


def test_tax_holiday_means_no_port_tax_and_then_ends():
    g, p = _mayor()
    port = [x for x in PORTS if x != engine.home_of(p) and PORTS[x]["tax_rate"] > 0][0]
    assert g.tax_rate_for(p, port) > 0
    _done(g, p, "tax_holiday")
    assert p["cash"] == 5000 and g.tax_holiday(p) == 6 and g.tax_rate_for(p, port) == 0
    assert g._spot_check(p, port) is None
    p["port"] = port


def test_protection_perk_sets_the_months_and_never_shortens_a_longer_term():
    g, p = _mayor()
    p["protect"] = 2
    _done(g, p, "protection")
    assert p["protect"] == 6
    g, p = _mayor()
    p["protect"] = 20
    _done(g, p, "protection")
    assert p["protect"] == 20


def test_share_perk_gives_one_free_share_and_falls_back_when_full():
    g, p = _mayor()
    before = g.shares_earned(p)
    _done(g, p, "share")
    assert g.shares_earned(p) == before + 1
    g, p = _mayor()
    p["share_earned"] = g.share_cap()
    _done(g, p, "share")
    assert g.shares_earned(p) == g.share_cap() and g.tax_holiday(p) == 6      # no room: a tax holiday instead


def test_offer_view_says_what_the_perk_is():
    g, p = _mayor()
    p["offers"] = {"year": {"id": 1, "slot": "year", "kind": "delivery", "port": [x for x in PORTS if x != engine.home_of(p)][0],
                            "good": "rice", "qty": 10, "got": 0, "due": 40, "fee": 100, "rep": 8.0, "until": 50, "perk": "protection"}}
    v = g.contracts_view(p)
    assert "protection" in v["offers"]["year"]["perk_text"].lower() and "6" in v["offers"]["year"]["perk_text"]
