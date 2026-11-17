"""The sea battle played on screen: python tests/battle_test.py

Checks the fight a captain plays by hand (pay, fight, run, retreat), that nobody lands while a
fight is open, that the clock and the host can finish a fight on standing orders, that a retreat
never sinks the last ship, that every bit of silver and cargo lands in the account book, and that
a fight saved half-way comes out the same when the game is loaded again.
"""
import copy
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import engine
from engine import Game, GameError, GOODS, PORTS, R


def setup(level="normal", **rules):
    """Settings where the sea is as dangerous as the test needs."""
    cfg = config.defaults()
    cfg["difficulty"]["level"] = level
    cfg["rules"]["weather"]["storm_chance"] = [0, 0, 0, 0]
    cfg["rules"]["weather"].update({"risk_min": 1.0, "risk_max": 1.0})      # every voyage as risky as the next
    cfg["rules"]["pirates"].update({"chance": 1.0, "fleet_min": 6, "fleet_base": 6, "fleet_max": 6})
    cfg["rules"]["liyuen"]["chance"] = 0.0
    cfg["rules"]["customs"]["enabled"] = False
    cfg["rules"]["contraband"].update({"seize_chance": 0.0, "seize_banned": 0.0})
    for path, value in rules.items():
        group, key = path.split("__")
        cfg["rules"][group][key] = value
    cfg, errors = config.validate(cfg)
    assert not errors, errors
    engine.configure(cfg)
    engine.MULT["pirates"] = 1.0


def new_game(seed=1, names=("Ann", "Bo"), guns=4, cargo=None, cash=5000):
    g = Game(seed=seed)
    for n in names:
        g.join(n, "")
    g.act("p1", {"type": "start"}, present=g.s["order"])
    for p in g.s["players"].values():
        p["ships"][0]["guns"] = guns
        p["ships"][0]["hull"] = engine.SHIPS[p["ships"][0]["type"]]["hull"]
        p["cargo"] = dict(cargo if cargo is not None else {"rice": 20, "tea": 10, "silk": 5})
        p["basis"] = {k: GOODS[k]["base"] for k in p["cargo"]}
        p["cash"] = cash
    return g


def sail(g, present, orders="fight", dest=None):
    for pid in g.s["order"]:
        p = g.s["players"][pid]
        d = dest or next(k for k in PORTS if k != p["port"])
        g.act(pid, {"type": "sail", "dest": d, "orders": orders}, present=present)
    return g.maybe_advance(set(present))


def books(p):
    return dict(p["books"]["game"])


def test_automatic_fight_never_waits():
    setup()
    for present in (None, []):          # no word on who is present (the old call), or nobody at a screen
        g = new_game()
        for pid in g.s["order"]:
            g.act(pid, {"type": "sail", "dest": "shanghai", "orders": "fight"}, present=[])
        g.resolve("all_ready", present)
        assert g.s["phase"] == "port" and g.s["turn"] == 1 and "sea" not in g.s
        assert all("battle" not in p and "fights" not in p and "voy" not in p for p in g.s["players"].values())
    setup(battle__interactive=False)
    g = new_game()
    assert sail(g, present=g.s["order"])
    assert g.s["phase"] == "port" and g.s["turn"] == 1, "switched off, every fight is settled at once"


def test_month_waits_and_nobody_lands():
    setup()
    g = new_game()
    g.s["players"]["p2"]["protect"] = 5
    R["liyuen"]["protect_save"] = 1.0                        # Bo is protected: no fight for him
    assert sail(g, present=["p1", "p2"])
    assert g.s["phase"] == "sea" and g.s["turn"] == 0
    p1, p2 = g.s["players"]["p1"], g.s["players"]["p2"]
    assert p1.get("battle") and not p2.get("battle")
    v = g.view("p1", ["p1", "p2"])
    assert v["phase"] == "sea" and v["me"]["battle"]["stage"] == "parley" and v["me"]["battle"]["left"] == 6
    assert [x["id"] for x in v["sea"]] == ["p1"] and g.view(None)["sea"][0]["where"]
    assert g.view("p2", ["p1", "p2"])["me"]["battle"] is None
    for action in ({"type": "buy", "good": "rice", "qty": 1}, {"type": "sail", "dest": "manila"}, {"type": "unsail"}):
        try:
            g.act("p2", action, present=["p1", "p2"])
            raise AssertionError("ashore business went through while a fight was open")
        except GameError as e:
            assert str(e) == engine.tx("e.at_sea"), e
    try:
        g.act("p2", {"type": "sea", "choice": "fight"}, present=["p1", "p2"])
        raise AssertionError("a house with no fight fought one")
    except GameError:
        pass
    assert not g.maybe_advance({"p1", "p2"}) and g.s["turn"] == 0
    while g.s["phase"] == "sea":
        g.act("p1", {"type": "sea", "choice": "fight"}, present=["p1", "p2"])
    assert g.s["turn"] == 1 and "sea" not in g.s and not p1.get("battle")
    assert len(p1["fights"]) == 1 and p1["fights"][0]["outcome"] in ("won", "broke_off", "wrecked")
    assert g.view("p1", ["p1"])["me"]["fights"][0]["beat"]["frames"]
    g.resolve("all_ready", [])                               # the next month clears the reckoning
    assert "fights" not in p1


def test_pay_the_pirates():
    setup()
    g = new_game(names=("Ann",), cash=5000)
    sail(g, present=["p1"])
    p = g.s["players"]["p1"]
    b = g.view("p1", ["p1"])["me"]["battle"]
    price, before, cargo = b["price"], books(p), dict(p["cargo"])
    assert b["can_pay"] and price > 0
    cash = p["cash"]
    g.act("p1", {"type": "sea", "choice": "pay"}, present=["p1"])
    f = p["fights"][0]
    assert g.s["phase"] == "port" and f["outcome"] == "paid" and f["paid"] == price and f["net"] == -price
    assert p["cash"] < cash, "silver went to the pirates"
    assert books(p).get("parley", 0) - before.get("parley", 0) == -price
    assert p["cargo"] == cargo and f["rounds"] == 0 and not f["cargo"]
    # too poor to pay: refused, and the fight is still there to be fought
    g = new_game(names=("Ann",), cash=1)
    sail(g, present=["p1"])
    assert not g.view("p1", ["p1"])["me"]["battle"]["can_pay"]
    try:
        g.act("p1", {"type": "sea", "choice": "pay"}, present=["p1"])
        raise AssertionError("paid without the silver")
    except GameError:
        pass
    assert g.s["phase"] == "sea"
    g.act("p1", {"type": "sea", "choice": "fight"}, present=["p1"])
    b = g.s["players"]["p1"].get("battle")
    assert b is None or b["stage"] == "fight"
    try:
        if b is not None:
            g.act("p1", {"type": "sea", "choice": "pay"}, present=["p1"])
            raise AssertionError("paid after the first shot")
    except GameError:
        pass
    # the pirate lord's fleet never names a price
    setup(pirates__chance=0.0, liyuen__chance=1.0)
    g = new_game(names=("Ann",))
    sail(g, present=["p1"])
    b = g.view("p1", ["p1"])["me"]["battle"]
    assert b["kind"] == "lord" and b["stage"] == "fight" and b["price"] == 0


def test_retreat():
    setup(pirates__hit=1.0, pirates__gun_hit=0.0)
    for seed in range(1, 30):
        g = new_game(seed=seed, names=("Ann",), cargo={"rice": 40, "tea": 30, "silk": 20})
        p = g.s["players"]["p1"]
        p["ships"].append(g._new_ship("junk", guns=0))
        cap = g.capacity(p)
        for sh in p["ships"]:
            sh["hull"] = 3                                   # one hit sinks either of them
        sail(g, present=["p1"])
        v = g.view("p1", ["p1"])["me"]["battle"]
        used = g.used(p)
        share = v["dump_qty"] / float(used)
        assert R["battle"]["retreat_min"] - 0.02 <= share <= R["battle"]["retreat_max"] + 1e-9, share
        cheapest = sorted(p["cargo"], key=lambda k: GOODS[k]["base"])
        assert list(v["dump"])[0] == cheapest[0], "the cheapest cargo goes first"
        before, cargo0 = books(p), dict(p["cargo"])
        g.act("p1", {"type": "sea", "choice": "retreat"}, present=["p1"])
        f = p["fights"][0]
        assert f["outcome"] == "retreated" and g.s["phase"] == "port"
        assert len(p["ships"]) >= 1, "a retreat never takes the last ship"
        assert p["wrecks"] == 0, "a retreat is never a shipwreck"
        assert all(sh["hull"] >= 1 for sh in p["ships"])
        lost = {x["good"]: x["qty"] for x in f["cargo"]}
        for k, q in v["dump"].items():
            assert lost.get(k, 0) >= q, "what the button promised went over the side"
        assert sum(cargo0.values()) - sum(p["cargo"].values()) == sum(lost.values())
        delta = {k: round(books(p).get(k, 0) - before.get(k, 0), 2) for k in ("overboard", "ships_lost", "booty", "parley", "plundered")}
        assert abs(sum(delta.values()) - f["net"]) <= 1, (delta, f["net"])
        assert delta["overboard"] < 0 and delta["booty"] == 0
        if len(p["ships"]) == 1 and any(s["lost"] for s in f["ships"]):
            assert g.used(p) <= g.capacity(p) < cap


def test_run_and_plunder_in_proportion():
    setup(pirates__run_base=0.0, pirates__run_fast=0.0, pirates__run_round=0.0, pirates__gun_hit=0.0,
          pirates__hit=0.0, pirates__plunder_min=0.5, pirates__plunder_max=0.5, battle__parley=False)
    g = new_game(names=("Ann",), cargo={"rice": 20, "tea": 20})
    sail(g, present=["p1"])
    p = g.s["players"]["p1"]
    for choice in ("run", "fight", "run", "fight", "run", "fight"):
        assert g.s["phase"] == "sea"
        g.act("p1", {"type": "sea", "choice": choice}, present=["p1"])
    f = p["fights"][0]
    assert f["outcome"] == "plundered" and f["rounds"] == 6
    assert p["cargo"] == {"rice": 15, "tea": 15}, p["cargo"]      # half the rounds running: half of the half
    g = new_game(names=("Ann",), cargo={"rice": 20, "tea": 20})
    sail(g, present=["p1"])
    p = g.s["players"]["p1"]
    for _ in range(6):
        g.act("p1", {"type": "sea", "choice": "fight"}, present=["p1"])
    assert p["fights"][0]["outcome"] == "broke_off" and p["cargo"] == {"rice": 20, "tea": 20}
    setup(pirates__run_base=1.0, battle__parley=False)
    g = new_game(names=("Ann",))
    sail(g, present=["p1"])
    g.act("p1", {"type": "sea", "choice": "run"}, present=["p1"])
    assert g.s["players"]["p1"]["fights"][0]["outcome"] == "away" and g.s["phase"] == "port"


def test_win_and_no_guns():
    setup(pirates__gun_hit=1.0, pirates__hit=0.0, pirates__hp=1, battle__parley=False)
    g = new_game(names=("Ann",), guns=6)
    sail(g, present=["p1"])
    p = g.s["players"]["p1"]
    cash = p["cash"]
    g.act("p1", {"type": "sea", "choice": "fight"}, present=["p1"])
    f = p["fights"][0]
    assert f["outcome"] == "won" and f["sunk"] == 6 and f["booty"] > 0 and f["net"] == f["booty"]
    setup(battle__parley=False)
    g = new_game(names=("Ann",), guns=0)
    sail(g, present=["p1"], orders="fight")
    v = g.view("p1", ["p1"])["me"]["battle"]
    assert not v["can_fight"] and v["orders"] == "run"
    try:
        g.act("p1", {"type": "sea", "choice": "fight"}, present=["p1"])
        raise AssertionError("fought with no guns")
    except GameError:
        pass


def test_clock_skip_and_host():
    setup(battle__parley=False)
    g = new_game(names=("Ann",))
    sail(g, present=["p1"], orders="run")
    p = g.s["players"]["p1"]
    g.act("p1", {"type": "sea", "choice": "auto"}, present=["p1"])        # the clock ran out: one round on orders
    b = p.get("battle")
    assert b is None or (b["round"] == 1 and b["runs"] == 1)
    if g.s["phase"] == "sea":
        g.act("p1", {"type": "sea", "choice": "skip"}, present=["p1"])    # the rest on standing orders
    assert g.s["phase"] == "port" and g.s["turn"] == 1 and p["fights"][0]["outcome"] in ("away", "plundered", "wrecked")
    g = new_game()
    sail(g, present=["p1", "p2"])
    assert g.s["phase"] == "sea" and all(q.get("battle") for q in g.s["players"].values())
    g.act("p1", {"type": "force"}, present=["p1", "p2"])                  # the host ends the month
    assert g.s["phase"] == "port" and g.s["turn"] == 1
    g = new_game()
    sail(g, present=["p1", "p2"])
    g.admin("force", {})
    assert g.s["phase"] == "port" and g.s["turn"] == 1
    g = new_game()
    sail(g, present=["p1", "p2"])
    g.admin("kick", {"pid": "p2"})                                        # the month is finished first
    assert g.s["phase"] == "port" and "p2" not in g.s["players"]


def test_two_fights_and_wreck():
    setup(liyuen__chance=1.0, battle__parley=False, pirates__run_base=1.0)
    g = new_game(names=("Ann",))
    sail(g, present=["p1"])
    p = g.s["players"]["p1"]
    assert p["battle"]["kind"] == "pirates"
    g.act("p1", {"type": "sea", "choice": "run"}, present=["p1"])
    assert g.s["phase"] == "sea" and p["battle"]["kind"] == "lord" and len(p["fights"]) == 1
    g.act("p1", {"type": "sea", "choice": "run"}, present=["p1"])
    assert g.s["phase"] == "port" and [f["kind"] for f in p["fights"]] == ["pirates", "lord"]
    assert p["fights"][0]["id"] != p["fights"][1]["id"]
    setup(pirates__hit=1.0, pirates__dmg_min=500, pirates__dmg_max=500, pirates__gun_hit=0.0, battle__parley=False)
    g = new_game(names=("Ann",))
    sail(g, present=["p1"])
    p = g.s["players"]["p1"]
    g.act("p1", {"type": "sea", "choice": "fight"}, present=["p1"])
    f = p["fights"][0]
    assert f["outcome"] == "wrecked" and all(s["lost"] for s in f["ships"])
    assert g.s["phase"] == "port" and p["port"] == engine.home_of(p) and p["wrecks"] == 1 and len(p["ships"]) == 1


def test_saved_half_way():
    setup(battle__parley=False)
    script = ["fight", "run", "fight", "fight", "run", "fight"]
    def play(reload_at):
        g = new_game(seed=11, names=("Ann",))
        sail(g, present=["p1"])
        for i, choice in enumerate(script):
            if g.s["phase"] != "sea":
                break
            if i == reload_at:
                state = json.loads(json.dumps(g.s))
                assert state["phase"] == "sea" and state["players"]["p1"]["battle"]
                g = Game(state=state, seed=999)
                assert g.s["phase"] == "sea"
            g.act("p1", {"type": "sea", "choice": choice}, present=["p1"])
        if g.s["phase"] == "sea":
            g.act("p1", {"type": "sea", "choice": "skip"}, present=["p1"])
        fight = dict(g.s["players"]["p1"]["fights"][0])
        fight.pop("id")                      # carries the game's own id, new for every game
        return fight
    whole = play(None)
    assert whole["rounds"] >= 1
    for k in (1, 2, 3):
        assert play(k) == whole, "a fight loaded from a save came out differently"
    # an older save, from before the battle existed, still loads; a stray phase is put right
    g = new_game(names=("Ann",))
    state = json.loads(json.dumps(g.s))
    state["phase"] = "sea"
    g = Game(state=state, seed=1)
    assert g.s["phase"] == "port"


def test_what_the_captain_is_shown():
    for level, want in (("easy", "exact"), ("normal", "bar"), ("hard", "tell")):
        setup(level=level)
        g = new_game(names=("Ann",))
        sail(g, present=["p1"])
        v = g.view("p1", ["p1"])["me"]["battle"]
        assert v["view"] == want
        assert ("odds" in v) == (want != "tell")
        assert v["tell"] and v["mood"] in ("calm", "worried", "grim") and set(v["moods"]) == {"fight", "run", "retreat"}
        assert v["dump_qty"] == sum(v["dump"].values()) > 0, "the cargo a retreat costs is always shown exactly"
        frames = v["beat"]["frames"]
        assert frames[0]["moment"] == "sighting" and frames[0]["say"] and "{" not in frames[0]["cap"]
        json.dumps(v)
    for rating in ("historical", "family"):
        cfg = config.defaults()
        cfg["content"]["rating"] = rating
        engine.configure(cfg)
        moments = {k.split(".")[2] for k in engine.TEXT if k.startswith("battle.say.")}
        assert moments >= {"sighting", "parley", "paid", "broadside", "miss", "enemy_hit", "we_are_hit", "ship_lost",
                           "run_fail", "got_away", "retreat", "victory", "broke_off", "plundered", "defeat"}
        for k, line in engine.TEXT.items():
            if k.startswith("battle.say."):
                assert not any(ch.isdigit() for ch in line) and "{" not in line, "spoken lines carry no amounts: " + k


def test_bot_games_keep_the_books():
    """Whole games with captains fighting by hand: the silver in hand always matches the books."""
    engine.configure(config.defaults())
    import random
    for seed in range(1, 9):
        g = Game(seed=seed)
        for n in ("Ann", "Bo", "Cy"):
            g.join(n, "")
        order = g.s["order"]
        g.act("p1", {"type": "settings", "years": 2}, present=order)
        g.act("p1", {"type": "start"}, present=order)
        r, fights, kinds = random.Random(seed), 0, set()
        while g.s["phase"] == "port":
            for pid in order:
                p = g.s["players"][pid]
                cu = p.get("customs")
                if cu and cu.get("status") == "declare":
                    g.act(pid, {"type": "customs_declare", "values": {ln["good"]: ln["value"] for ln in cu["lines"]}}, present=order)
                if p.get("customs"):
                    g.act(pid, {"type": "customs_done"}, present=order)
                for _ in range(3):
                    try:
                        g.act(pid, {"type": r.choice(["buy", "sell"]), "good": r.choice(list(GOODS)), "qty": r.randint(1, 25)}, present=order)
                    except GameError:
                        pass
                g.act(pid, {"type": "sail", "dest": r.choice([k for k in PORTS if k != p["port"]]),
                            "orders": r.choice(["fight", "run"])}, present=order)
            assert g.maybe_advance(set(order))
            if g.s["phase"] == "sea":
                for pid in order:
                    for action in ({"type": "buy", "good": "rice", "qty": 1},):
                        try:
                            g.act(pid, action, present=order)
                            raise AssertionError("traded at sea")
                        except GameError:
                            pass
            g.fight_out(order)
            for p in g.s["players"].values():
                for f in p.get("fights") or []:
                    fights += 1
                    kinds.add(f["outcome"])
                    assert f["rounds"] <= R["pirates"]["rounds"] and f["sunk"] <= f["n"]
                assert g.used(p) <= g.capacity(p) and all(q > 0 for q in p["cargo"].values())
            g = Game(state=json.loads(json.dumps(g.s)), seed=seed * 100 + g.s["turn"])
        assert fights > 3, fights
    assert kinds >= {"away", "retreated"}, kinds


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print("ok", fn.__name__)
    engine.configure(config.defaults())
    print("OK: sea battle checks passed ({} tests)".format(len(tests)))
