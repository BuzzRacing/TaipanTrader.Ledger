"""Cargo Tiers, phase 2 (25 Nov 2026): the engine core. Each captain has a tier (0, 1 or 2) and trades the cargo of
that tier's table (table_of, sold_to). The luxuries' prices run on dice of their own, so the original nine keep their
dice. Phases 3 to 5 (the per-captain filter, the step and buyout, the promotion card) add their tests to this file.
Run: python tests/tiers_test.py
"""
import copy
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import config  # noqa: E402
import engine  # noqa: E402

NINE = ["opium", "gold", "silk", "porcelain", "arms", "spices", "tea", "rice", "general"]
LUX1 = ["camphor", "sandalwood", "ginseng"]
LUX2 = ["jade", "pearls", "ambergris"]
TABLE = {
    0: NINE,
    1: ["opium", "gold", "silk", "porcelain", "arms", "spices"] + LUX1,
    2: ["opium", "gold", "silk"] + LUX1 + LUX2,
}


def tiers_on(enabled=True, ready=True, mutate=None):
    cfg = copy.deepcopy(config.defaults())
    cfg["rules"]["tiers"]["enabled"] = enabled
    if mutate:
        mutate(cfg)
    engine.TIERS_READY = ready
    engine.configure(cfg)


def reset():
    engine.TIERS_READY = True                           # the shipped value since phase 5; the switch itself is off
    engine.configure(config.defaults())


def captain(game, name="Ada"):
    game.join(name, name + " & Co")
    return next(p for p in game.s["players"].values() if p["name"] == name)


def test_off_by_default_everyone_trades_the_nine():
    reset()
    assert not engine.tiers_on() and list(engine.GOODS) == NINE
    g = engine.Game(seed=3)
    p = captain(g)
    assert p["tier"] == 0 and engine.tier_of(p) == 0 and engine.table_of(p) == NINE
    p["tier"] = 2                                       # a stored tier does nothing while the tiers are off
    assert engine.tier_of(p) == 0 and engine.table_of(p) == NINE
    for port in engine.PORTS:
        assert engine.goods_for(p, port) == engine.goods_of(port)


def test_switch_without_ready_does_nothing():
    tiers_on(enabled=True, ready=False)
    assert not engine.tiers_on() and list(engine.GOODS) == NINE
    reset()


def test_the_three_tables():
    tiers_on()
    assert engine.tiers_on() and engine.tier_count() == 2
    assert len(engine.GOODS) == 15, "the catalog holds all fifteen"
    g = engine.Game(seed=5)
    p = captain(g)
    for tier, want in TABLE.items():
        p["tier"] = tier
        assert sorted(engine.table_of(p)) == sorted(want), (tier, engine.table_of(p))
        assert len(engine.table_of(p)) == 9, tier
    reset()


def test_tier_is_kept_within_the_steps():
    tiers_on()
    p = {"tier": 7}
    assert engine.tier_of(p) == 2
    p = {"tier": -3}
    assert engine.tier_of(p) == 0
    assert engine.tier_of({}) == 0
    reset()


def test_sold_to_needs_the_port_and_the_table():
    tiers_on()
    g = engine.Game(seed=5)
    p = captain(g)
    p["tier"] = 1
    assert engine.sold_to(p, "hongkong", "camphor") and engine.sold_to(p, "hongkong", "tea") is False
    assert engine.sold_to(p, "calcutta", "camphor") is False, "forbidden in the port stays forbidden at its tier"
    assert engine.sold_to(p, "calcutta", "sandalwood") is True
    p["tier"] = 0
    assert engine.sold_to(p, "hongkong", "camphor") is False and engine.sold_to(p, "hongkong", "tea") is True
    assert engine.sold_to(p, "hongkong", "no_such_cargo") is False
    reset()


def test_two_captains_two_tables_one_set_of_prices():
    tiers_on()
    g = engine.Game(seed=11)
    a, b = captain(g, "Ada"), captain(g, "Bo")
    b["tier"] = 2
    assert "tea" in engine.table_of(a) and "tea" not in engine.table_of(b)
    assert "jade" in engine.table_of(b) and "jade" not in engine.table_of(a)
    for port in engine.PORTS:
        for good in engine.goods_of(port):
            assert good in g.s["prices"][port], "prices run for the whole catalog, whoever can see them"
    reset()


def test_new_players_start_at_tier_0_and_old_saves_load_at_0():
    tiers_on()
    g = engine.Game(seed=2)
    p = captain(g)
    assert p["tier"] == 0
    state = copy.deepcopy(g.s)
    for q in state["players"].values():
        q.pop("tier")                                   # a save made before Cargo Tiers
    again = engine.Game(state=state, seed=9)
    assert all(q["tier"] == 0 for q in again.s["players"].values())
    state = copy.deepcopy(g.s)
    for q in state["players"].values():
        q["tier"] = 99
    again = engine.Game(state=state, seed=9)
    assert all(q["tier"] == 2 for q in again.s["players"].values()), "a tier past the steps is brought back"
    reset()


def test_the_nine_keep_their_dice_with_the_tiers_on():
    reset()
    off = engine.Game(seed=21)
    tiers_on()
    on = engine.Game(seed=21)
    for port in engine.PORTS:
        for good in NINE:
            if engine.sold_here(port, good):
                assert off.s["prices"][port][good] == on.s["prices"][port][good], (port, good)
    assert off.s["weather"] == on.s["weather"], "the dice after the opening prices are the same dice"
    assert off.rng.random() == on.rng.random(), "the game's one run of dice is not moved"
    reset()


def test_the_luxuries_have_dice_of_their_own():
    tiers_on()
    a, b = engine.Game(seed=33), engine.Game(seed=33)
    assert a.s["prices"] == b.s["prices"], "same seed, same opening prices, luxuries included"
    c = engine.Game(seed=34)
    assert any(a.s["prices"][port][g] != c.s["prices"][port][g] for port in engine.PORTS for g in LUX1 + LUX2
               if engine.sold_here(port, g)), "another seed, other luxury prices"
    reset()


def _quiet(cfg):
    ev = cfg["rules"]["events"]
    ev["shock_chance"] = ev["windfall_chance"] = ev["ban_chance"] = 0.0     # leave only the monthly price draws
    cfg["rules"]["market"]["runs_chance"] = 0.0         # runs on the wild cargoes are seeded by game id, not by seed


def _one_month(on, seed):
    """Open a game, add a captain and move the markets one month. Returns (the game, its prices)."""
    if on:
        tiers_on(mutate=_quiet)
    else:
        reset()
        cfg = copy.deepcopy(config.defaults())
        _quiet(cfg)
        engine.configure(cfg)
    g = engine.Game(seed=seed)
    captain(g)
    g.s["phase"] = "port"
    g._move_markets([])
    return g, copy.deepcopy(g.s["prices"])


def test_a_month_moves_the_nine_the_same_and_the_luxuries_on_their_own_dice():
    off, p_off = _one_month(False, 41)
    on, p_on = _one_month(True, 41)
    for port in p_off:
        for good in NINE:
            if good in p_off[port]:
                assert p_off[port][good] == p_on[port][good], (port, good)
    assert off.rng.getstate() == on.rng.getstate(), "the luxuries drew nothing from the game's dice"
    moved = [(port, x) for port in p_on for x in LUX1 + LUX2 if x in p_on[port]]
    assert moved and all(p_on[port][x] > 0 for port, x in moved)
    again, p_again = _one_month(True, 41)
    assert p_again == p_on, "the luxuries' month is repeatable"
    reset()


def test_the_luxuries_run_all_game_with_a_resume():
    tiers_on()
    g = engine.Game(seed=51)
    captain(g)
    state = copy.deepcopy(g.s)
    again = engine.Game(state=state, seed=52)
    for port in engine.PORTS:
        for x in LUX1 + LUX2:
            if engine.sold_here(port, x):
                assert again.s["prices"][port][x] == g.s["prices"][port][x]
    reset()


def test_a_season_of_months_runs_with_the_tiers_on():
    tiers_on()
    g = engine.Game(seed=61)
    p = captain(g)
    p["tier"] = 2
    g.s["phase"] = "port"
    for _ in range(36):
        g._move_markets([])
        g.s["turn"] += 1
        for port in engine.PORTS:
            for x in engine.goods_of(port):
                v = g.s["prices"][port][x]
                assert v > 0 and v == v, (port, x, v)
    reset()


# ---- phase 3 (25 Nov 2026): the per-captain filter -----------------------------------------------------------

def started(tier, port="hongkong", seed=7, cash=None):
    """A started game with one captain at the given tier, in port, with a clean customs slate."""
    tiers_on()
    game = engine.Game(seed=seed)
    pid = game.pid_for_token(game.join("Ann", ""))
    game.act(pid, {"type": "start"})
    p = game.s["players"][pid]
    p["customs"] = None
    p["port"] = port
    p["tier"] = tier
    p["cargo"] = {}
    if cash is not None:
        p["cash"] = cash
    return game, pid, p


def cargo_keys(obj):
    """Every cargo key found in a {port: {good: ...}} or {good: ...} shape."""
    keys = set()
    for k, v in obj.items():
        if k in engine.GOODS:
            keys.add(k)
        elif isinstance(v, dict):
            keys |= {g for g in v if g in engine.GOODS}
    return keys


def test_the_view_shows_a_captain_only_their_own_table():
    for tier in (0, 1, 2):
        game, pid, p = started(tier)
        want = set(TABLE[tier])
        me = game.view(pid)["me"]
        assert me["tier"] == tier
        assert set(me["prices"]) <= want and set(me["prices"]) == want & set(engine.goods_of("hongkong")), (tier, set(me["prices"]))
        assert set(me["purse"]) <= want and want & set(me["purse"]), tier
        assert cargo_keys(me["known"]) <= want, tier
        for rows in me["market"]["hist"]:
            assert set(rows["prices"]) <= want, (tier, set(rows["prices"]))
    reset()


def test_what_the_house_already_knows_is_cut_to_its_table():
    game, pid, p = started(0)
    p["known"]["manila"] = {"turn": 1, "prices": {"tea": 70, "camphor": 6000}}
    p["tips"] = {"manila": {"tea": {"turn": 1, "price": 70}, "jade": {"turn": 1, "price": 9000}}}
    p["hot_tips"] = [{"good": "pearls", "port": "manila", "home": "hongkong", "turn": 1, "lands": 2, "ends": 99},
                     {"good": "tea", "port": "manila", "home": "hongkong", "turn": 1, "lands": 2, "ends": 99}]
    me = game.view(pid)["me"]
    assert set(me["known"]["manila"]["prices"]) == {"tea"}
    assert set(me["tips"]["manila"]) == {"tea"}
    assert [t["good"] for t in me["hot_tips"]] == ["tea"]
    p["tier"] = 2
    me = game.view(pid)["me"]
    assert set(me["known"]["manila"]["prices"]) == {"camphor"}
    assert set(me["tips"]["manila"]) == {"jade"}
    assert [t["good"] for t in me["hot_tips"]] == ["pearls"]
    assert p["known"]["manila"]["prices"] == {"tea": 70, "camphor": 6000}, "the stored book is not cut, only what is shown"
    reset()


def test_prices_seen_are_only_noted_for_the_table():
    game, pid, p = started(0)
    game._note_prices(p)
    assert set(p["known"]["hongkong"]["prices"]) == set(NINE)
    p["tier"] = 2
    game._note_prices(p)
    assert set(p["known"]["hongkong"]["prices"]) == set(TABLE[2])
    reset()


def test_the_windfall_on_the_pulse_panel_is_for_cargo_the_house_trades():
    game, pid, p = started(0)
    game.s["windfalls"] = [{"port": "hongkong", "good": "jade", "kind": "boom", "mult": 3, "turns": 2},
                           {"port": "hongkong", "good": "tea", "kind": "crash", "mult": .1, "turns": 2}]
    assert game.view(pid)["me"]["market"]["windfalls"] == {"tea": "crash"}
    p["tier"] = 2
    assert game.view(pid)["me"]["market"]["windfalls"] == {"jade": "boom"}
    reset()


def test_news_names_only_cargo_the_house_trades():
    game, pid, p = started(0)
    game.s["news"] = ["Jan 1860: Shortage of Jade in Manila", "Jan 1860: Glut of Tea in Manila",
                      "Jan 1860: The harbour is quiet", "Jan 1860: Shortage of Ambergris and Rice in Manila"]
    news = game.view(pid)["news"]
    assert news == ["Jan 1860: Glut of Tea in Manila", "Jan 1860: The harbour is quiet"], news
    assert len(game.view(pid)["news_heat"]) == len(news)
    p["tier"] = 2
    news = game.view(pid)["news"]
    assert news == ["Jan 1860: Shortage of Jade in Manila", "Jan 1860: The harbour is quiet"], news
    assert len(game.s["news"]) == 4, "the board itself is whole"
    reset()


def test_the_tiers_off_the_view_is_what_it_was():
    reset()
    game = engine.Game(seed=7)
    pid = game.pid_for_token(game.join("Ann", ""))
    game.act(pid, {"type": "start"})
    p = game.s["players"][pid]
    p["tier"] = 2                                       # stored, but the tiers are off
    game.s["news"] = ["Jan 1860: Glut of Tea in Manila"]
    v = game.view(pid)
    assert set(v["me"]["prices"]) == set(game.s["prices"][p["port"]])
    assert v["news"] == game.s["news"][:14] and v["me"]["tier"] == 0


def test_a_cargo_outside_the_table_cannot_be_bought_sold_or_stored():
    game, pid, p = started(0, cash=10 ** 9)
    for kind in ({"type": "buy"}, {"type": "sell"}, {"type": "warehouse", "op": "store"}):
        try:
            game.act(pid, dict(kind, good="camphor", qty=1))
        except engine.GameError:
            pass
        else:
            raise AssertionError("tier 0 could use camphor: {}".format(kind))
    assert p["cargo"].get("camphor", 0) == 0
    game.act(pid, {"type": "buy", "good": "tea", "qty": 5})
    assert p["cargo"]["tea"] == 5
    p["tier"] = 1
    game.act(pid, {"type": "buy", "good": "camphor", "qty": 1})
    assert p["cargo"]["camphor"] == 1
    try:
        game.act(pid, {"type": "buy", "good": "tea", "qty": 1})
    except engine.GameError:
        pass
    else:
        raise AssertionError("tier 1 could buy tea")
    game.act(pid, {"type": "sell", "good": "camphor", "qty": 1})
    assert p["cargo"].get("camphor", 0) == 0
    reset()


def test_a_forbidden_luxury_is_still_forbidden_at_its_tier():
    game, pid, p = started(1, port="calcutta", cash=10 ** 9)
    try:
        game.act(pid, {"type": "buy", "good": "camphor", "qty": 1})
    except engine.GameError:
        pass
    else:
        raise AssertionError("camphor is forbidden in Calcutta")
    game.act(pid, {"type": "buy", "good": "sandalwood", "qty": 1})
    assert p["cargo"]["sandalwood"] == 1
    reset()


def test_the_registrar_only_tips_cargo_the_house_trades():
    for tier in (0, 1, 2):
        seen = set()
        for seed in range(1, 25):
            game, pid, p = started(tier, seed=seed)
            game.s["turn"] += seed % 5
            p["known"], p["tips"] = {}, {}
            tip = game._registrar_tip(p)
            if tip:
                seen.add(tip["good"])
                assert engine.sold_to(p, tip["port"], tip["good"]) and engine.sold_to(p, p["port"], tip["good"]), (tier, tip)
        assert seen and seen <= set(TABLE[tier]), (tier, seen)
    reset()


def test_hot_tips_are_only_for_cargo_the_house_trades():
    for tier in (0, 1, 2):
        seen = set()
        for seed in range(1, 40):
            game, pid, p = started(tier, seed=seed)
            game.s["forecasts"] = []
            tip = game._hot_tip(p, "taxlady")
            if tip:
                seen.add(tip["good"])
        assert seen <= set(TABLE[tier]), (tier, seen)
        assert seen, "some hot tip was given at tier {}".format(tier)
    reset()


def test_commissions_are_only_for_cargo_the_house_trades():
    for tier in (0, 1, 2):
        seen = set()
        for seed in range(1, 30):
            game, pid, p = started(tier, seed=seed)
            for slot in ("short", "year"):
                offer = game._new_offer(p, slot)
                if offer and offer.get("good"):
                    seen.add(offer["good"])
        assert seen <= set(TABLE[tier]), (tier, seen)
    reset()


def test_plunder_is_only_cargo_the_house_trades():
    for tier in (0, 1, 2):
        seen = set()
        for seed in range(1, 60):
            game, pid, p = started(tier, seed=seed)
            for kind in ("pirate", "lord"):
                b = {"kind": kind, "seed": seed, "n": 3}
                m = game._battle_prize_manifest(p, b)
                if m:
                    seen |= set(m[1])
        assert seen and seen <= set(TABLE[tier]), (tier, seen)
    reset()


def test_the_crew_tip_after_a_spared_fight_is_for_cargo_the_house_trades():
    for tier in (0, 2):
        game, pid, p = started(tier)
        tip = game._band_tip(p, {"dest": None})
        assert tip and tip["good"] in TABLE[tier], (tier, tip)
    reset()


def test_the_private_lot_is_for_cargo_the_house_trades():
    for tier in (0, 1, 2):
        for seed in range(1, 25):
            game, pid, p = started(tier, seed=seed)
            game.s["rules_standing"] = None
            lot = None
            orig = game.standing_on, game.band_here, game._band_rng
            game.standing_on = lambda: True
            game.band_here = lambda *_a, **_k: 4
            import random as _r
            game._band_rng = lambda *_a, **_k: _r.Random(seed)
            engine.R["standing"]["lot_chance"] = 1.0
            game._offer_lot(p, "hongkong")
            lot = p.get("lot")
            if lot:
                assert lot["good"] in TABLE[tier], (tier, lot)
    reset()


def test_under_the_counter_deals_only_in_the_house_table():
    import counter
    for tier in (0, 1, 2):
        game, pid, p = started(tier, cash=10 ** 7)
        run = counter.best_run(game, p)
        assert run is None or run["good"] in TABLE[tier], (tier, run)
    reset()


def test_bot_games_with_the_tiers_on_break_no_rule():
    """Four bots at tiers 0, 1, 2, 1 play 5 years each over two seeds, saved and loaded every month. A buy or sell
    of a cargo outside a captain's table is refused, never made; nothing aboard is ever outside its table."""
    import json
    import sim_test
    for seed in (5, 6):
        tiers_on()
        game = engine.Game(seed=seed)
        rng = game.rng
        bots = {}
        for (name, bot), tier in zip([("Ada", sim_test.trader_bot), ("Bao", sim_test.trader_bot),
                                      ("Cy", sim_test.random_bot), ("Dee", sim_test.random_bot)], (0, 1, 2, 1)):
            pid = game.pid_for_token(game.join(name, ""))
            game.s["players"][pid]["tier"] = tier
            bots[pid] = bot
        host = game.s["order"][0]
        game.act(host, {"type": "settings", "years": 5}, present=game.s["order"])
        game.act(host, {"type": "start"}, present=game.s["order"])
        while game.s["phase"] == "port":
            for pid, bot in bots.items():
                p = game.s["players"][pid]
                if sim_test.jail.pending(p):
                    sim_test.try_act(game, pid, {"type": "plea", "months": 0})
                if sim_test.jail.jailed(p):
                    if not p["ready"]:
                        sim_test.try_act(game, pid, {"type": "jail_serve"})
                    continue
                if p.get("jail_freed"):
                    sim_test.try_act(game, pid, {"type": "jail_free"})
                bot(game, pid, rng)
            assert game.maybe_advance(set(game.s["order"]))
            game.fight_out(set(game.s["order"]))
            for p in game.s["players"].values():
                mine = set(engine.table_of(p))
                assert set(p["cargo"]) <= mine, (p["name"], p["tier"], p["cargo"])
                assert set(p["wh"]) <= mine, (p["name"], p["tier"], p["wh"])
            game = engine.Game(state=json.loads(json.dumps(game.s)), seed=seed * 1000 + game.s["turn"])
            rng = game.rng
            for pid in bots:
                v = game.view(pid, game.s["order"])["me"]
                assert set(v["prices"]) <= set(engine.table_of(game.s["players"][pid]))
            game.view(None, [])
        assert game.s["phase"] == "ended"
    reset()


# ---- phase 4 (25 Nov 2026): the step, the buyout and the bankruptcy reset ----------------------------------------

def home_house(tier=0, cash=60000, seed=7):
    """A started house at its home port, in port, tiers on, with the given silver (60,000 makes a Merchant)."""
    game, pid, p = started(tier, seed=seed)
    p["port"] = engine.home_of(p)
    p["cash"] = cash
    return game, pid, p


def test_the_step_comes_with_the_rank_and_only_at_home():
    game, pid, p = home_house(0, cash=1000)
    game._check_tier(p)
    assert p["tier"] == 0, "a Clerk stays at the start"
    p["cash"] = 60000
    away = next(k for k in engine.PORTS if k != engine.home_of(p))
    p["port"] = away
    game._check_tier(p)
    assert p["tier"] == 0, "not away from home"
    p["port"] = engine.home_of(p)
    p["voy"] = {"dest": away}
    game._check_tier(p)
    assert p["tier"] == 0, "not at sea"
    p.pop("voy")
    game._check_tier(p)
    assert p["tier"] == 1 and len(p["tier_steps"]) == 1
    game._check_tier(p)
    assert p["tier"] == 1 and len(p["tier_steps"]) == 1, "once"
    p["cash"] = 600000
    game._check_tier(p)
    assert p["tier"] == 2 and len(p["tier_steps"]) == 2
    p["cash"] = 100
    game._check_tier(p)
    assert p["tier"] == 2, "it only goes up"
    reset()


def test_both_steps_at_once_make_one_record():
    game, pid, p = home_house(0, cash=600000)
    game._check_tier(p)
    assert p["tier"] == 2 and len(p["tier_steps"]) == 1
    rec = p["tier_steps"][0]
    assert (rec["from"], rec["to"]) == (0, 2)
    assert sorted(rec["goods_in"]) == sorted(LUX1 + LUX2) and sorted(rec["goods_out"]) == sorted(
        ["general", "rice", "tea", "spices", "arms", "porcelain"])
    reset()


def test_no_step_with_the_tiers_off():
    reset()
    game = engine.Game(seed=7)
    pid = game.pid_for_token(game.join("Ann", ""))
    game.act(pid, {"type": "start"})
    p = game.s["players"][pid]
    p["cash"] = 600000
    game._check_tier(p)
    assert p["tier"] == 0 and not p.get("tier_steps")


def test_the_step_happens_when_a_house_makes_its_next_move():
    """A house at home worth a Merchant moves up through an ordinary action, not only through a direct call."""
    game, pid, p = home_house(0, cash=60000)
    game.act(pid, {"type": "bank", "op": "deposit", "amount": 1})
    assert p["tier"] == 1
    reset()


def test_the_buyout_is_worth_neutral_and_pays_each_lot_at_its_own_port():
    game, pid, p = home_house(0, cash=60000)
    home = engine.home_of(p)
    other = next(k for k in engine.PORTS if k != home and engine.sold_here(k, "tea") and engine.sold_here(k, "rice"))
    p["cargo"] = {"tea": 300, "opium": 40, "rice": 100}
    p["wh"] = {"tea": 200, "silk": 10}
    p["depots"] = {other: {"goods": {"rice": 500, "gold": 5}, "level": 0}}
    p["basis"] = {"tea": 60.0, "rice": 12.0, "opium": 900.0, "silk": 1500.0, "gold": 5000.0}
    p["net"] = {"tea": [5, 5], "opium": [1, 1]}
    p["tab"]["goods"] = {"tea": [10, 5], "silk": [2, 1]}
    want = {("tea", home, "hold"): game.dealer_value(p, home, "tea", 300),
            ("rice", home, "hold"): game.dealer_value(p, home, "rice", 100),
            ("tea", home, "wh"): game.dealer_value(p, home, "tea", 200),
            ("rice", other, "depot"): game.dealer_value(p, other, "rice", 500)}
    worth0, cash0 = game.worth(p), p["cash"]
    prices0, purse0 = copy.deepcopy(game.s["prices"]), copy.deepcopy(game.s.get("purse"))
    game._check_tier(p)
    assert p["tier"] == 1
    got = {(ln["good"], ln["port"], ln["where"]): ln["gain"] for ln in p["tier_steps"][0]["lines"]}
    assert set(got) == set(want), got
    for key, v in want.items():
        assert abs(got[key] - v) <= 1, (key, got[key], v)
    assert abs(p["cash"] - cash0 - sum(want.values())) <= 4
    assert abs(game.worth(p) - worth0) <= 4, (game.worth(p), worth0)
    assert game.s["prices"] == prices0 and game.s.get("purse") == purse0, "no sale into the market"
    assert p["cargo"] == {"opium": 40} and p["wh"] == {"silk": 10} and p["depots"][other]["goods"] == {"gold": 5}
    assert set(p["basis"]) == {"opium", "silk", "gold"} and set(p["net"]) == {"opium"} and set(p["tab"]["goods"]) == {"silk"}
    reset()


def test_the_second_step_buys_out_what_the_first_left():
    game, pid, p = home_house(1, cash=600000)
    p["cargo"] = {"spices": 100, "arms": 20, "porcelain": 10, "silk": 5, "camphor": 3}
    p["wh"] = {"arms": 50}
    worth0 = game.worth(p)
    game._check_tier(p)
    assert p["tier"] == 2
    assert p["cargo"] == {"silk": 5, "camphor": 3} and not p["wh"]
    assert abs(game.worth(p) - worth0) <= 4
    reset()


def test_a_house_cannot_hold_cargo_outside_its_table_after_a_step():
    game, pid, p = home_house(0, cash=600000)
    p["cargo"] = {g: 1 for g in NINE}
    game._check_tier(p)
    assert set(p["cargo"]) <= set(TABLE[2]), p["cargo"]
    reset()


def test_contracts_offers_lots_and_tips_for_a_retired_cargo_are_dropped_without_penalty():
    game, pid, p = home_house(0, cash=60000)
    turn = game.s["turn"]
    p["contracts"] = [{"slot": "year", "kind": "delivery", "good": "tea", "qty": 100, "got": 20, "port": "manila",
                       "due": turn + 9, "fee": 5000, "rep": 5.0, "until": turn + 9},
                      {"slot": "short", "kind": "delivery", "good": "opium", "qty": 10, "got": 0, "port": "manila",
                       "due": turn + 3, "fee": 900, "rep": 2.0, "until": turn + 3}]
    p["year_goal"] = turn // 12
    p["offers"] = {"year": None, "short": {"slot": "short", "kind": "supply", "good": "rice", "qty": 50, "got": 0,
                                           "port": "manila", "due": turn + 2, "fee": 500, "rep": 1.0, "until": turn + 2}}
    p["lot"] = {"port": engine.home_of(p), "good": "rice", "qty": 5, "unit": 100.0, "price": 90.0}
    p["tips"] = {"manila": {"tea": {"turn": turn, "price": 70}, "silk": {"turn": turn, "price": 700}}}
    p["hot_tips"] = [{"good": "tea", "port": "manila", "ends": turn + 5}, {"good": "gold", "port": "manila", "ends": turn + 5}]
    cash0, rep0 = p["cash"], dict(p["rep"])
    game._check_tier(p)
    assert [k["good"] for k in p["contracts"]] == ["opium"], "the opium commission stays"
    assert "year_goal" not in p, "the year's commission counts as not taken"
    assert p["offers"]["short"] is None and "lot" not in p
    assert set(p["tips"]["manila"]) == {"silk"} and [t["good"] for t in p["hot_tips"]] == ["gold"]
    assert len(p["tier_steps"][0]["cancelled"]) == 1
    assert p["rep"] == rep0 and p["cash"] == cash0, "no penalty, no fee"
    reset()


def test_bankruptcy_takes_the_tier_back_and_the_climb_starts_again():
    game, pid, p = home_house(0, cash=600000)
    game._check_tier(p)
    assert p["tier"] == 2
    rank0 = p["rank_id"] = "merchant_prince"
    p["cargo"] = {"jade": 5, "camphor": 5, "silk": 5}
    p["cash"] = p["bank"] = 0.0                         # nothing for the crew to hide: the new stake is all there is
    news = []
    game._bankrupt(p, news)
    assert p["tier"] == 0 and p["rank_id"] == rank0, "the tier goes, the rank is kept"
    assert set(p["cargo"]) <= set(NINE), "the luxuries were seized, not hidden"
    game._check_tier(p)
    assert p["tier"] == 0, "a house with a new stake is a Clerk"
    p["cash"] = 60000
    p["rank_id"] = "merchant_prince"
    game._check_tier(p)
    assert p["tier"] == 1 and len(p["tier_steps"]) == 2, "the step is made again, with a record of its own"
    reset()


def test_the_stuck_rescue_resets_the_tier_too():
    game, pid, p = home_house(0, cash=600000)
    game._check_tier(p)
    assert p["tier"] == 2
    game._bankrupt(p, [], stuck=True)
    assert p["tier"] == 0
    reset()


def test_a_step_survives_a_save_and_load():
    game, pid, p = home_house(0, cash=600000)
    p["cargo"] = {"tea": 50}
    game._check_tier(p)
    state = json.loads(json.dumps(game.s))
    again = engine.Game(state=state, seed=3)
    q = again.s["players"][pid]
    assert q["tier"] == 2 and q["tier_steps"][0]["to"] == 2 and "tea" not in q["cargo"]
    assert set(again.view(pid)["me"]["prices"]) <= set(TABLE[2])
    again._check_tier(q)
    assert len(q["tier_steps"]) == 1
    reset()


def test_switching_the_tiers_on_in_a_running_game_gives_everyone_their_steps():
    reset()
    game = engine.Game(seed=12)
    a, b = game.pid_for_token(game.join("Ann", "")), game.pid_for_token(game.join("Bo", ""))
    game.act(game.s["order"][0], {"type": "start"}, present=game.s["order"])
    pa, pb = game.s["players"][a], game.s["players"][b]
    pa["cash"], pb["cash"] = 60000, 1000
    for q in (pa, pb):
        q["port"] = engine.home_of(q)
        q["customs"] = None
    pa["cargo"] = {"tea": 10}
    tiers_on()
    state = json.loads(json.dumps(game.s))
    game = engine.Game(state=state, seed=13)
    game._check_promotions()
    assert game.s["players"][a]["tier"] == 1 and "tea" not in game.s["players"][a]["cargo"]
    assert game.s["players"][b]["tier"] == 0
    reset()


def test_every_port_trades_something_at_every_tier():
    tiers_on()
    for tier in (0, 1, 2):
        for port in engine.PORTS:
            assert [g for g in engine.GOODS if engine.in_table(tier, g) and engine.sold_here(port, g)], (tier, port)
    reset()


def test_bot_games_climb_the_tiers_without_breaking_a_rule():
    """Bots start rich enough to climb: every month nothing held is outside its house's table, and a house's tier
    only ever goes up except through bankruptcy."""
    import sim_test
    climbed = set()
    for seed in (5, 6):
        tiers_on()
        game = engine.Game(seed=seed)
        rng = game.rng
        bots = {}
        for name, bot in (("Ada", sim_test.trader_bot), ("Bao", sim_test.trader_bot),
                          ("Cy", sim_test.random_bot), ("Dee", sim_test.random_bot)):
            pid = game.pid_for_token(game.join(name, ""))
            bots[pid] = bot
        host = game.s["order"][0]
        game.act(host, {"type": "settings", "years": 5}, present=game.s["order"])
        game.act(host, {"type": "start"}, present=game.s["order"])
        for pid in bots:
            game.s["players"][pid]["cash"] = 30000          # a Trader; a good run makes a Merchant in a year or so
        last = {pid: 0 for pid in bots}
        while game.s["phase"] == "port":
            for pid, bot in bots.items():
                p = game.s["players"][pid]
                if sim_test.jail.pending(p):
                    sim_test.try_act(game, pid, {"type": "plea", "months": 0})
                if sim_test.jail.jailed(p):
                    if not p["ready"]:
                        sim_test.try_act(game, pid, {"type": "jail_serve"})
                    continue
                if p.get("jail_freed"):
                    sim_test.try_act(game, pid, {"type": "jail_free"})
                bot(game, pid, rng)
            assert game.maybe_advance(set(game.s["order"]))
            game.fight_out(set(game.s["order"]))
            for pid, p in game.s["players"].items():
                mine = set(engine.table_of(p))
                assert set(p["cargo"]) <= mine and set(p["wh"]) <= mine, (p["name"], p["tier"], p["cargo"], p["wh"])
                for d in (p.get("depots") or {}).values():
                    assert set(d.get("goods") or {}) <= mine
                if p["tier"] < last[pid]:
                    assert p["bankruptcies"] > 0, "the tier only falls through bankruptcy"
                last[pid] = p["tier"]
                climbed.add(p["tier"])
            game = engine.Game(state=json.loads(json.dumps(game.s)), seed=seed * 1000 + game.s["turn"])
            rng = game.rng
    assert 1 in climbed or 2 in climbed, "no house climbed in either game: the bots' start needs a boost"
    reset()


# ---- phase 5 (25 Nov 2026): telling the captain ---------------------------------------------------------------

def test_a_step_with_no_promotion_makes_its_own_card_and_the_ack_clears_it():
    game, pid, p = home_house(0, cash=60000)
    p["rank_id"] = "merchant"                         # the commission was made earlier: no promotion this pass
    p["cargo"] = {"tea": 40}
    serial0 = p.get("promotion_serial", 0)
    game._check_tier(p)
    queue = p["promotions"]
    assert len(queue) == 1 and queue[0]["kind"] == "tier" and queue[0]["id"] == serial0 + 1
    card = queue[0]
    assert card["tier"]["to"] == 1 and card["tier"]["total"] == p["tier_steps"][0]["total"] > 0
    assert card["tier"]["goods_out"] == ["general", "rice", "tea"] or set(card["tier"]["goods_out"]) == {"general", "rice", "tea"}
    assert [r["good"] for r in card["tier"]["sold"]] == ["tea"] and card["tier"]["sold"][0]["qty"] == 40
    assert p["tier_steps"][0]["told"] is True
    assert game.view(pid)["me"]["promotion"]["id"] == card["id"]
    game.act(pid, {"type": "promotion_ack", "id": card["id"]})
    assert not p["promotions"] and not game.view(pid)["me"].get("promotion")
    reset()


def test_a_step_made_with_a_promotion_rides_on_that_card():
    game, pid, p = home_house(0, cash=60000)
    p["rank_id"] = "clerk"
    game._check_promotions()
    assert p["rank_id"] == "merchant" and p["tier"] == 1
    assert len(p["promotions"]) == 1, "one card, not two"
    card = p["promotions"][0]
    assert card.get("kind") != "tier" and card["title"] and card["tier"]["to"] == 1
    reset()


def test_both_steps_at_once_make_one_card():
    game, pid, p = home_house(0, cash=600000)
    p["rank_id"] = "clerk"
    game._check_promotions()
    assert p["tier"] == 2 and len(p["promotions"]) == 1 and len(p["tier_steps"]) == 1
    tier = p["promotions"][0]["tier"]
    assert (tier["from"], tier["to"]) == (0, 2)
    assert sorted(tier["goods_in"]) == sorted(LUX1 + LUX2)
    reset()


def test_the_log_line_names_the_cargo_and_the_money():
    game, pid, p = home_house(0, cash=60000)
    p["cargo"] = {"tea": 40}
    p["log"] = []
    game._check_tier(p)
    line = [x for x in p["log"] if "closed out" in x]
    assert len(line) == 1 and "Tea" in line[0] and "$" in line[0], p["log"]
    assert all(engine.GOODS[g]["name"] in line[0] for g in LUX1)
    game, pid, p = home_house(0, cash=60000, seed=11)
    p["log"] = []
    game._check_tier(p)                                # nothing held: the second wording
    assert any("Nothing of yours was left" in x for x in p["log"]), p["log"]
    reset()


def test_the_new_wording_has_a_clean_version_and_keeps_its_names():
    import re
    import strings
    names = lambda t: sorted(set(re.findall(r"\{(\w+)\}", t)))
    for key in ("l.tier_buyout", "l.tier_step"):
        assert key in strings.EN and key in strings.FAMILY, key
        assert names(strings.FAMILY[key]) and set(names(strings.FAMILY[key])) <= set(names(strings.EN[key])), key
    assert "st.line.tier_buyout" in strings.EN
    assert strings.EN["promo.tier.open.0"] and strings.EN["promo.tier.cap.0"]
    for k in [k for k in strings.EN if k.startswith("promo.tier.open.") or k.startswith("promo.tier.cap.")]:
        assert set(names(strings.EN[k])) <= {"port", "name", "firm", "rank"}, k


def test_the_tally_book_gets_a_closed_out_line():
    import stats
    ev = {"type": "tier_step", "cat": "finance", "pid": 1, "turn": 5, "total": 400,
          "lines": [{"good": "tea", "qty": 10, "gain": 400, "port": "hongkong", "where": "hold"}]}
    houses, _w, _p = stats._walk([ev], [{"id": 1}])
    assert houses[1].lines.get("tier_buyout") == 400


def test_the_log_line_is_not_read_aloud():
    import voice
    assert "l.tier_buyout" not in voice.LOG_RANK and "l.tier_step" not in voice.LOG_RANK


# ---- phase 6 (25 Nov 2026): Admin advice, the Manual's table, held luxuries when the switch goes off ---------

def test_the_admin_warning_names_a_port_with_nothing_to_trade_at_a_tier():
    assert config.tier_gaps(config.defaults()) == []
    cfg = copy.deepcopy(config.defaults())
    cfg["ports"]["manila"]["forbidden"] = ["opium", "gold", "silk"] + LUX1 + LUX2         # all of tier 2's table
    assert config.tier_gaps(cfg) == [("manila", 2)]
    cfg["goods"]["jade"]["enters"] = 1                                                    # a cargo joining sooner fixes tier 1 too
    cfg["ports"]["manila"]["forbidden"] = ["opium", "gold", "silk", "porcelain", "arms", "spices"] + LUX1 + ["jade"]
    assert config.tier_gaps(cfg) == [("manila", 1)] or ("manila", 1) in config.tier_gaps(cfg)
    checked, errors = config.validate(cfg)
    assert not any("tier" in e.lower() and "no cargo" in e.lower() for e in errors), "advice only: it never blocks a save"


def test_the_manual_table_follows_the_switch_and_marks_the_captains_row():
    import manual_feed
    tiers_on()
    g = engine.Game(seed=3)
    p = captain(g)
    p["tier"] = 1
    rows = manual_feed.tiers_table(p)
    assert [r["rank"] for r in rows] == [None, "Merchant", "Merchant Prince"], rows
    assert [r["here"] for r in rows] == [False, True, False]
    names = lambda t: [engine.GOODS[k]["name"] for k in TABLE[t]]
    assert [r["goods"] for r in rows] == [names(0), names(1), names(2)]
    reset()
    assert manual_feed.tiers_table(p) == [], "off: the Manual has no table of ranks"


def test_the_manual_page_and_wording_carry_the_table():
    import re
    import manual_text
    js = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web", "manual.js"), encoding="utf-8").read()
    assert "book.tiers" in js
    for key in re.findall(r'"(man\.tiers\.[a-z_]+)"', js):
        assert key in manual_text.EN, key
    assert not any("{" in v for k, v in manual_text.EN.items() if k.startswith("man.tiers."))


def test_luxuries_are_bought_out_when_the_switch_goes_off_in_a_running_game():
    tiers_on()
    game, pid, p = home_house(0, cash=600000)
    game._check_tier(p)
    assert p["tier"] == 2
    home = engine.home_of(p)
    other = next(k for k in engine.PORTS if k != home and engine.sold_here(k, "jade") and engine.sold_here(k, "silk"))
    p["cargo"] = {"jade": 30, "silk": 20}
    p["wh"] = {"pearls": 10, "gold": 2}
    p["depots"] = {other: {"goods": {"camphor": 40, "opium": 3}, "level": 0}}
    p["basis"] = {"jade": 10000.0, "pearls": 14000.0, "camphor": 5000.0, "silk": 500.0, "gold": 2400.0, "opium": 4000.0}
    p["log"] = []
    worth0, cash0 = game.worth(p), p["cash"]
    state = json.loads(json.dumps(game.s))
    reset()                                             # an Admin turns the switch off; the running game is reconciled
    again = engine.Game(state=state, seed=3)
    q = again.s["players"][pid]
    assert q["cargo"] == {"silk": 20} and q["wh"] == {"gold": 2} and q["depots"][other]["goods"] == {"opium": 3}
    assert set(q["basis"]) == {"silk", "gold", "opium"}
    paid = q["cash"] - cash0
    assert paid > 0 and abs(again.worth(q) - worth0) <= 1, (paid, worth0, again.worth(q))
    assert engine.tier_of(q) == 0 and q["tier"] == 2, "off: everyone trades the nine, but the stored tier is kept"
    assert any("luxury dealers" in x for x in q["log"]), q["log"]
    # switched on again: the captain is still at their tier, so no second step and no second card
    tiers_on()
    again2 = engine.Game(state=json.loads(json.dumps(again.s)), seed=4)
    r = again2.s["players"][pid]
    n = len(r.get("tier_steps") or [])
    again2._check_tier(r)
    assert engine.tier_of(r) == 2 and len(r.get("tier_steps") or []) == n
    reset()


def test_deleting_a_non_luxury_cargo_is_left_as_it_was():
    """Only the six luxuries are bought out: any other cargo that vanishes from the settings is dropped as before."""
    tiers_on()
    game, pid, p = home_house(0, cash=1000)
    p["cargo"] = {"tea": 5}
    cfg = copy.deepcopy(config.defaults())
    cfg["rules"]["tiers"]["enabled"] = True
    cfg["goods"].pop("tea")
    for port in cfg["ports"].values():
        port["forbidden"] = [g for g in (port.get("forbidden") or []) if g != "tea"]
        (port.get("mods") or {}).pop("tea", None)
    engine.configure(cfg)
    again = engine.Game(state=json.loads(json.dumps(game.s)), seed=5)
    assert "tea" not in again.s["players"][pid]["cargo"] and again.s["players"][pid]["cash"] == 1000
    reset()


def test_each_luxury_has_its_own_buy_and_sell_lines():
    """Phase 7: every trade in a luxury draws from that cargo's own bank, in both the house voice and the family one."""
    import trade_text
    reset()
    for good in LUX1 + LUX2:
        for prefix in ("m.bought", "m.sold"):
            keys = [k for k in trade_text.KEYS if k.startswith("{}.{}.".format(prefix, good))]
            assert len(keys) >= 4, (good, prefix)
            for k in keys:
                assert trade_text.FAMILY[k] and trade_text.SAY[k] and trade_text.SAY_FAMILY[k], k
    g = engine.Game(seed=4)
    p = captain(g)
    for good in LUX1 + LUX2:
        got = g._trade_say(p, "m.bought", good=good, qty=1)
        assert got.startswith("m.bought.{}.".format(good)), (good, got)
        got = g._trade_say(p, "m.sold", "m.sold", good=good, qty=1)
        assert got.startswith("m.sold.{}.".format(good)), (good, got)
    # the nine still use the general banks for a small trade, and nothing about them changed
    assert g._trade_say(p, "m.bought", good="silk", qty=1).startswith("m.bought.") and \
        not g._trade_say(p, "m.bought", good="silk", qty=1).split(".")[2:3] == ["silk"]
    # a luxury's spoken lines carry no amounts, and the family versions keep the cargo's name
    for k in trade_text.KEYS:
        if k.split(".")[2:3] and k.split(".")[2] in trade_text.BULK_MIN_OF:
            for text in (trade_text.SAY[k], trade_text.SAY_FAMILY[k]):
                assert "{qty}" not in text and "{cost}" not in text and "{gain}" not in text, k


if __name__ == "__main__":
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("ok", name)
            except Exception as exc:  # noqa: BLE001
                failed += 1
                reset()
                print("FAIL", name, repr(exc))
    reset()
    sys.exit(1 if failed else 0)
