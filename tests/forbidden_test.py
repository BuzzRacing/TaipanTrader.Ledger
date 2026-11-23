"""Forbidden Cargo (22 Nov 2026): a port can forbid a cargo outright. In that port the cargo does not exist:
no price, no market row, no tip, no news, no tax line, no customs search, nothing to buy, sell or store. Cargo
already aboard just stays aboard. (A ban is a different thing: a crackdown event.) Run: python tests/forbidden_test.py

The sweep plays bot games and checks, every month, that a forbidden pair never shows up anywhere the game
makes or shows a (port, cargo) pair.
"""
import copy
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import config  # noqa: E402
import counter  # noqa: E402
import engine  # noqa: E402
import manual_feed  # noqa: E402
import sim_test  # noqa: E402
from engine import Game, GameError, GOODS, PORTS  # noqa: E402

MAP = {"shanghai": {"porcelain", "rice"}, "nagasaki": {"opium", "tea"}, "foochow": {"gold", "spices"},
       "manila": {"arms", "tea"}, "saigon": {"opium", "gold"}, "bangkok": {"porcelain", "opium"},
       "singapore": {"rice", "gold"}, "batavia": {"general", "porcelain"}, "calcutta": {"arms"}}


def setup(enabled=True):
    cfg = config.defaults()
    cfg["rules"]["customs"]["spot_home"] = 0.0
    cfg["rules"]["forbidden"]["enabled"] = enabled
    engine.configure(cfg)
    return cfg


def started(seed=3, port="nagasaki", cargo=None):
    game = Game(seed=seed)
    pid = game.pid_for_token(game.join("Ann", ""))
    game.act(pid, {"type": "start"})
    p = game.s["players"][pid]
    p["customs"] = None
    p["port"] = port
    p["cargo"] = dict(cargo or {})
    return game, pid, p


def test_the_shipped_map():
    setup()
    assert {k: v for k, v in engine.FORBIDDEN.items()} == MAP, engine.FORBIDDEN
    assert "hongkong" not in engine.FORBIDDEN                      # the free port forbids nothing
    for g in GOODS:
        assert sum(1 for k in PORTS if engine.sold_here(k, g)) >= 7, g     # every cargo still sells in 7 ports or more
    assert all(engine.goods_of(k) for k in PORTS)


def test_prices_exist_only_for_what_a_port_trades():
    setup()
    game = Game(seed=1)
    for port in PORTS:
        assert set(game.s["prices"][port]) == set(engine.goods_of(port)), port
    for port, gone in MAP.items():
        assert not (set(game.s["prices"][port]) & gone)


def test_the_cargo_average_leaves_forbidden_ports_out():
    setup()
    ports = [k for k in PORTS if engine.sold_here(k, "tea")]
    assert len(ports) == 8
    want = sum(GOODS["tea"]["base"] * PORTS[k]["mods"].get("tea", 1.0) for k in ports) / 8.0
    assert abs(engine.normal_price("tea") - want) < 1e-9
    setup(enabled=False)
    assert len([k for k in PORTS if engine.sold_here(k, "tea")]) == len(PORTS)
    allp = sum(GOODS["tea"]["base"] * PORTS[k]["mods"].get("tea", 1.0) for k in PORTS) / float(len(PORTS))
    assert abs(engine.normal_price("tea") - allp) < 1e-9


def test_cargo_aboard_stays_and_cannot_be_managed_there():
    setup()
    game, pid, p = started(port="nagasaki", cargo={"tea": 30, "silk": 10})
    for act in ({"type": "buy", "good": "tea", "qty": 1}, {"type": "sell", "good": "tea", "qty": 1},
                {"type": "warehouse", "op": "store", "good": "tea", "qty": 1},
                {"type": "sell", "good": "tea", "src": "all"}):
        try:
            game.act(pid, act)
            assert False, "should refuse: " + json.dumps(act)
        except GameError:
            pass
    assert p["cargo"]["tea"] == 30 and game.used(p) == 40       # still aboard, still taking room
    v = game.view(pid)["me"]
    assert "tea" not in v["prices"] and "silk" in v["prices"]
    assert "tea" not in (v.get("purse") or {})
    game.act(pid, {"type": "sell", "good": "silk", "qty": 1})   # what the port trades works as ever
    assert game.worth(p) > 0                                    # net worth still counts the tea aboard


def test_the_tax_desk_does_not_know_a_forbidden_cargo():
    cfg = setup()
    game, pid, p = started(port="manila", cargo={"tea": 20, "arms": 20, "silk": 20})
    game._open_customs(p)
    goods = {ln["good"] for ln in (p["customs"] or {}).get("lines", [])}
    assert goods == {"silk"}, goods                                # tea and arms are not on Manila's books


def test_no_customs_search_for_a_forbidden_cargo():
    setup()
    game = Game(seed=2)
    assert "opium" in engine.contraband()
    assert "opium" not in game.at_risk("saigon") and "opium" in game.at_risk("shanghai")
    game.s["crackdown"]["saigon"] = 3
    assert "opium" not in game.banned("saigon")
    game.s["ban_goods"] = {"foochow": ["gold"]}
    game.s["crackdown"]["foochow"] = 3
    assert "gold" not in game.banned("foochow")
    assert not game._can_ban("saigon")                            # opium and gold are both forbidden there
    assert game._can_ban("shanghai")


def test_switched_off_every_port_trades_everything():
    setup(enabled=False)
    assert not engine.FORBIDDEN
    game = Game(seed=1)
    for port in PORTS:
        assert set(game.s["prices"][port]) == set(GOODS)


def test_an_old_save_loses_the_prices_a_port_no_longer_trades():
    setup(enabled=False)
    game, pid, p = started(port="shanghai", cargo={})
    p["known"]["nagasaki"] = {"turn": 1, "prices": {"tea": 100, "silk": 200}}
    p["tips"] = {"nagasaki": {"tea": {"turn": 1, "price": 90}, "silk": {"turn": 1, "price": 210}}}
    p["hot_tips"] = [{"good": "tea", "port": "nagasaki", "home": "shanghai", "ends": 99, "turn": 1, "lands": 2},
                     {"good": "silk", "port": "nagasaki", "home": "shanghai", "ends": 99, "turn": 1, "lands": 2}]
    state = json.loads(json.dumps(game.s))
    setup()
    g2 = Game(state=state)
    q = g2.s["players"][pid]
    assert "tea" not in g2.s["prices"]["nagasaki"] and "silk" in g2.s["prices"]["nagasaki"]
    assert set(q["known"]["nagasaki"]["prices"]) == {"silk"}
    assert set(q["tips"]["nagasaki"]) == {"silk"}
    assert [t["good"] for t in q["hot_tips"]] == ["silk"]


def test_counter_tips_never_use_a_forbidden_pair():
    cfg = setup()
    cfg["rules"]["counter"]["enabled"] = True
    engine.configure(cfg)
    for seed in range(1, 12):
        for port in ("nagasaki", "saigon", "manila", "bangkok", "batavia"):
            game, pid, p = started(seed=seed, port=port, cargo={"tea": 20, "opium": 15, "silk": 10, "gold": 5})
            p["cash"] = 50000
            run = counter.best_run(game, p)
            if run:
                assert engine.sold_here(port, run["good"]) and engine.sold_here(run["port"], run["good"]), (port, run)
            hold = counter.best_hold(game, p)
            if hold:
                for ln in hold["lines"]:
                    assert engine.sold_here(hold["port"], ln["good"]), (port, hold)


def test_contracts_ask_for_cargo_the_destination_trades():
    setup()
    game, pid, p = started(seed=4, port="hongkong")
    for turn in range(0, 60):
        game.s["turn"] = turn
        for slot in ("short", "year"):
            offer = game._new_offer(p, slot)
            if offer and offer.get("good") and offer.get("port"):
                assert engine.sold_here(offer["port"], offer["good"]), offer


def test_the_manual_lists_the_map():
    setup()
    rows = {r["port"]: set(r["goods"]) for r in manual_feed.forbidden_table()}
    want = {PORTS[k]["name"]: {GOODS[g]["name"] for g in gone} for k, gone in MAP.items()}
    assert rows == want, rows


def test_the_admin_form_keeps_and_checks_the_map():
    cfg = config.defaults()
    raw = copy.deepcopy(cfg)
    cfg2, errors = config.validate(raw)
    assert not errors, errors
    assert cfg2["ports"]["nagasaki"]["forbidden"] == ["opium", "tea"]
    raw = copy.deepcopy(cfg)
    del raw["ports"]["saigon"]["forbidden"]                          # settings saved before the feature
    cfg3, errors = config.validate(raw)
    assert not errors and cfg3["ports"]["saigon"]["forbidden"] == ["opium", "gold"], errors
    raw = copy.deepcopy(cfg)
    raw["ports"]["saigon"]["forbidden"] = list(raw["goods"])         # a port must keep one cargo
    _, errors = config.validate(raw)
    assert any("at least one cargo" in e for e in errors), errors
    raw = copy.deepcopy(cfg)
    raw["ports"]["saigon"]["forbidden"] = ["tea", "tea", "nonsense"]
    cfg4, errors = config.validate(raw)
    assert not errors and cfg4["ports"]["saigon"]["forbidden"] == ["tea"], errors


def scan_text(game, lines, where):
    """No line of news may name a cargo together with a port that forbids it."""
    for port, gone in MAP.items():
        for g in gone:
            for line in lines:
                low = line.lower()
                has = lambda word: re.search(r"\b" + re.escape(word.lower()) + r"\b", low) is not None    # "rice" is not "prices"
                assert not (has(PORTS[port]["name"]) and has(GOODS[g]["name"])), (where, port, g, line)


def sweep(seed, years=5):
    """Bot games: a forbidden pair must never appear in anything the game makes or shows."""
    seen_events = []
    game = Game(seed=seed)
    game.on_event = seen_events.append
    rng = game.rng
    bots = {}
    for name, bot in (("Ada", sim_test.trader_bot), ("Bao", sim_test.trader_bot), ("Cy", sim_test.random_bot)):
        bots[game.pid_for_token(game.join(name, ""))] = bot
    host = game.s["order"][0]
    game.act(host, {"type": "settings", "years": years}, present=game.s["order"])
    game.act(host, {"type": "start"}, present=game.s["order"])
    months = 0
    while game.s["phase"] == "port":
        for pid, bot in bots.items():
            p = game.s["players"][pid]
            if sim_test.jail.pending(p):
                sim_test.try_act(game, pid, {"type": "plea", "months": rng.choice([0, 1, 3])})
            if sim_test.jail.jailed(p):
                if not p["ready"]:
                    sim_test.try_act(game, pid, {"type": "jail_serve"})
                continue
            if p.get("jail_freed"):
                sim_test.try_act(game, pid, {"type": "jail_free"})
            bot(game, pid, rng)
        assert game.maybe_advance(set(game.s["order"]))
        game.fight_out(set(game.s["order"]))
        months += 1
        s = game.s
        for port in PORTS:
            assert not (set(s["prices"][port]) & MAP.get(port, set())), (port, "price")
        for kind in ("shocks", "windfalls", "forecasts"):
            for row in s.get(kind) or ():
                assert engine.sold_here(row["port"], row["good"]), (kind, row)
        for port, goods in s["ban_goods"].items():
            assert not set(goods) & MAP.get(port, set()), ("ban_goods", port, goods)
        for port in s["crackdown"]:
            assert not set(game.banned(port)) & MAP.get(port, set()), ("banned", port)
        for pid in bots:
            p = s["players"][pid]
            for port, row in (p.get("known") or {}).items():
                assert not set(row.get("prices") or {}) & MAP.get(port, set()), ("known", port)
            for port, row in (p.get("tips") or {}).items():
                assert not set(row) & MAP.get(port, set()), ("tips", port)
            for t in p.get("hot_tips") or ():
                assert engine.sold_here(t["port"], t["good"]) and engine.sold_here(t["home"], t["good"]), ("hot", t)
            cu = p.get("customs") or {}
            assert not {ln["good"] for ln in cu.get("lines", [])} & MAP.get(cu.get("port"), set()), ("desk", cu.get("port"))
            for port, row in (game.view(pid, s["order"])["me"].get("known") or {}).items():
                assert not set(row.get("prices") or {}) & MAP.get(port, set())
            v = game.view(pid, s["order"])["me"]
            assert set(v["prices"]) == set(engine.goods_of(v["port"])), v["port"]
            scan_text(game, [t["text"] for t in p.get("hot_tips") or ()], "hot tips")
        scan_text(game, s["news"][:6], "news")
        for e in seen_events:
            if e.get("cat") == "market" and e.get("good") and e.get("port") in PORTS:
                assert engine.sold_here(e["port"], e["good"]), e
            if e.get("type") in ("registrar_hot", "port_hot") and e.get("where"):
                assert engine.sold_here(e["where"], e["good"]) and engine.sold_here(e["port"], e["good"]), e
        seen_events.clear()
        game = Game(state=json.loads(json.dumps(game.s)), seed=seed * 1000 + months)     # save and load
        game.on_event = seen_events.append
        rng = game.rng
    return months


def test_nothing_forbidden_ever_appears_in_a_bot_game():
    setup()
    total = sum(sweep(seed) for seed in range(1, 7))
    assert total >= 6 * 55, total


if __name__ == "__main__":
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("ok", name)
            except Exception as exc:  # noqa: BLE001
                failed += 1
                import traceback
                traceback.print_exc()
                print("FAIL", name, exc)
    sys.exit(1 if failed else 0)
