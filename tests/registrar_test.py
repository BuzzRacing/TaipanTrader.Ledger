"""The Registrar (Mrs. Evelyn Marlowe, cast key "taxlady"): found only in a captain's own home port,
where she meets the house, waves it in and gives one tip, read aloud: a hot tip (a boom she knows is
coming, on half of homecomings) or otherwise a price tip. Anywhere else the port's own officer may give
a hot tip (one arrival in five). Never two hot tips at once per house.

Run from the project folder:  python tests/registrar_test.py
"""
import copy
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import cast  # noqa: E402
import config  # noqa: E402
import engine  # noqa: E402
import strings  # noqa: E402
import voice  # noqa: E402
from engine import Game, GOODS, PORTS  # noqa: E402


def setup(**registrar):
    """The price-tip tests run with hot tips off; the hot-tip tests turn them on."""
    base = config.defaults()
    base["rules"]["start"]["where"] = "home"
    base["rules"]["registrar"]["hot_enabled"] = False
    # The hot-tip tests below want a tip every time unless they say otherwise.
    base["rules"]["registrar"]["hot_home_chance"] = 1.0
    base["rules"]["registrar"]["hot_away_chance"] = 0.0
    base["rules"]["registrar"].update(registrar)
    engine.configure(base)
    return base


def anchor(port="singapore", home="singapore", cargo=(("tea", 30),), known=None, seed=5):
    """A house anchors in a port with cargo aboard and the desk opens."""
    game = Game(seed=seed)
    pid = game.pid_for_token(game.join("Ann", ""))
    game.act(pid, {"type": "start"})
    p = game.s["players"][pid]
    p["port"], p["home"] = port, home
    p["cargo"] = dict(cargo)
    p["known"] = known if known is not None else {}
    p["log"] = []
    game._open_customs(p)
    return game, p


def test_she_meets_a_house_in_its_own_home_port():
    setup()
    for home in PORTS:
        game, p = anchor(port=home, home=home)
        cu = p["customs"]
        assert cu["officer"] == "taxlady" and cu["home_free"] and cu["status"] == "welcome", home
        assert cu["say"].startswith("l.registrar_home."), cu["say"]
        v = game.customs_view(p)
        assert v["name"] == "Mrs. Evelyn Marlowe" and v["welcome"] and "{" not in v["welcome"]
        tip = v["tip"]
        assert tip and tip["port"] != home and tip["good"] in GOODS
        assert tip["price"] == int(round(game.s["prices"][tip["port"]][tip["good"]]))
        assert p["tips"][tip["port"]][tip["good"]] == {"turn": game.s["turn"], "price": tip["price"]}
        assert any(PORTS[tip["port"]]["name"] in line and GOODS[tip["good"]]["name"] in line for line in p["log"])
        assert game.view(p["id"])["me"]["tips"][tip["port"]][tip["good"]]["price"] == tip["price"]


def test_nowhere_else():
    setup()
    for port in PORTS:
        home = "calcutta" if port != "calcutta" else "manila"
        _, p = anchor(port=port, home=home)
        assert p["customs"]["officer"] != "taxlady", port
        assert not p["customs"].get("tip") and not p.get("tips"), port


def test_hong_kong_has_its_own_officer_for_visitors():
    setup()
    _, p = anchor(port="hongkong", home="manila")
    assert p["customs"]["officer"] == "officer_hongkong" and p["customs"]["status"] == "declare"
    _, p = anchor(port="hongkong", home="hongkong")
    assert p["customs"]["officer"] == "taxlady" and p["customs"]["tip"]


def test_empty_hold_still_tipped():
    setup()
    _, p = anchor(cargo=())
    assert p["customs"]["tip"]


def test_she_favours_cargo_held_and_ports_not_seen():
    setup()
    fresh = {k: {"turn": 0, "prices": {}} for k in PORTS if k not in ("singapore", "calcutta")}
    for seed in range(25):
        _, p = anchor(cargo=(("silk", 10),), known=fresh, seed=seed)
        tip = p["customs"]["tip"]
        assert tip["good"] == "silk" and tip["port"] == "calcutta", tip


def test_every_price_fresh_gives_the_oldest():
    setup(stale_months=6)
    game, p = anchor()
    game.s["turn"] = 10
    p["known"] = {k: {"turn": 9, "prices": {}} for k in PORTS if k != "singapore"}
    p["known"]["manila"]["turn"] = 7
    p["tips"], p["log"] = {}, []
    game._open_customs(p)
    assert p["customs"]["tip"]["port"] == "manila"


def test_switch_off_and_any_cargo():
    setup(enabled=False)
    _, p = anchor()
    assert p["customs"]["officer"] != "taxlady" and not p["customs"].get("tip")
    assert p["customs"].get("say") is None             # the port's officer: the stock home line
    setup(held_first=False)
    goods = {anchor(seed=seed)[1]["customs"]["tip"]["good"] for seed in range(40)}
    assert len(goods) > 1


def test_the_game_dice_are_untouched():
    rolls = []
    for on in (True, False):
        setup(enabled=on)
        game, _ = anchor()
        rolls.append([game.rng.random() for _ in range(5)])
    assert rolls[0] == rolls[1]


def test_the_same_game_gives_the_same_tip():
    """Drawn from the game's id, the house and the month, so a replay of the journal gives the same tip."""
    setup()
    game, p = anchor(seed=3)
    first = p["customs"]["tip"]
    again = Game(state=copy.deepcopy(game.s), seed=99)
    q = again.s["players"][p["id"]]
    q["tips"] = {}
    again._open_customs(q)
    assert (q["customs"]["tip"]["port"], q["customs"]["tip"]["good"]) == (first["port"], first["good"])


def test_her_lines_are_hers_and_the_tip_is_spoken_without_the_price():
    cfg = setup()
    ch = cfg["characters"]["taxlady"]
    assert ch["name"] == "Mrs. Evelyn Marlowe"
    assert not [k for k in strings.EN if k.startswith("l.customs_welcome.taxlady.")]
    home = [k for k in strings.EN if k.startswith("l.registrar_home.")]
    tips = [k for k in strings.EN if k.startswith("l.registrar_tip.")]
    assert len(home) == 15 and len(tips) == 10
    voice.PLAN.configure(cfg, engine.TEXT)
    for k in home + tips:
        assert cast.speaker_for(cfg, k) == "taxlady", k
        assert k not in cast.OFFICER_KEYS, k                     # never handed to the port's officer
    for k in tips:
        line = engine.tx(k, goods="Silk", where="Calcutta", price="$412")
        assert "Silk" in line and "Calcutta" in line and "$412" in line
        found, fields = voice.PLAN.matcher.match(line)
        assert found == k, (k, found)
        spoken = voice.PLAN.spoken(found, fields, line)
        assert "$412" not in spoken and "412" not in spoken and "Calcutta" in spoken, (k, spoken)
    for k in home:
        line = engine.tx(k, port="Manila")
        assert voice.PLAN.matcher.match(line)[0] == k, k
    assert cast.speaker_for(cfg, "l.registrar_logged") == ""
    for k in strings.FAMILY:
        assert k in strings.EN, k


# ------------------------------------------------------------------ hot tips --
def test_hot_tip_names_a_boom_elsewhere_in_a_cargo_cheap_at_home():
    setup(hot_enabled=True)
    for home in PORTS:
        game, p = anchor(port=home, home=home, cargo=(("tea", 30),))
        tip = p["customs"]["tip"]
        assert tip["hot"] and tip["port"] != home and tip["good"] in GOODS, tip
        assert "{" not in tip["text"] and GOODS[tip["good"]]["name"] in tip["text"] and PORTS[tip["port"]]["name"] in tip["text"]
        assert tip["key"].startswith("l.registrar_hot."), tip["key"]
        # cheap at home: in the cheaper half of the cargoes, by price against its normal price here
        ratio = {g: game.s["prices"][home][g] / (GOODS[g]["base"] * PORTS[home]["mods"].get(g, 1.0)) for g in GOODS}
        assert sorted(ratio, key=lambda g: (ratio[g], g)).index(tip["good"]) < (len(GOODS) + 1) // 2
        f = game.s["forecasts"][-1]
        assert (f["port"], f["good"], f["pid"]) == (tip["port"], tip["good"], p["id"])
        assert any("hot tip" in line and GOODS[tip["good"]]["name"] in line for line in p["log"])
        assert game.view(p["id"])["me"]["hot_tips"][-1]["port"] == tip["port"]


def test_the_boom_lands_when_she_says_and_lasts():
    setup(hot_enabled=True, hot_lead=1, hot_months=2, hot_min=4.0, hot_max=4.0)
    game, p = anchor(port="hongkong", home="hongkong")
    tip = p["customs"]["tip"]
    port, g = tip["port"], tip["good"]
    normal = GOODS[g]["base"] * PORTS[port]["mods"].get(g, 1.0)
    seen = {}
    for _ in range(4):
        game._move_markets([])
        game.s["turn"] += 1
        seen[game.s["turn"]] = game.s["prices"][port][g] / normal
    assert seen[tip["lands"]] > 2.0 and seen[tip["ends"]] > 2.0, seen        # booming the months she named
    assert seen[tip["lands"] - 1] < 2.0 if tip["lands"] - 1 in seen else True, seen
    assert not [w for w in game.s["windfalls"] if w.get("foretold")] or game.s["turn"] <= tip["ends"], game.s["windfalls"]
    assert not game.s["forecasts"]


def test_at_most_one_hot_tip_at_a_time():
    setup(hot_enabled=True, hot_every=1, hot_lead=1, hot_months=2)
    game, p = anchor()
    tip = p["customs"]["tip"]
    assert tip.get("hot") and tip["ends"] == 3, tip
    for step, hot in ((1, False), (2, False), (3, False), (4, True)):    # none while hers runs (to month 3)
        game.s["turn"] = step
        p["log"] = []
        game._open_customs(p)
        assert bool(p["customs"]["tip"].get("hot")) == hot, (step, p["customs"]["tip"])
    assert len(game.s["forecasts"]) == 2


def test_hot_tips_leave_the_dice_alone_and_replay_the_same():
    rolls = []
    for on in (True, False):
        setup(hot_enabled=on)
        game, _ = anchor()
        rolls.append([game.rng.random() for _ in range(5)])
    assert rolls[0] == rolls[1]
    setup(hot_enabled=True)
    game, p = anchor(seed=3)
    first = p["customs"]["tip"]
    again = Game(state=copy.deepcopy(game.s), seed=99)
    q = again.s["players"][p["id"]]
    q.pop("hot_last", None)
    q.pop("hot_tips", None)
    again.s["forecasts"] = []
    again._open_customs(q)
    assert (q["customs"]["tip"]["port"], q["customs"]["tip"]["good"]) == (first["port"], first["good"])


def test_hot_lines_are_hers_and_spoken_whole():
    cfg = setup(hot_enabled=True)
    voice.PLAN.configure(cfg, engine.TEXT)
    hot = [k for k in strings.EN if k.startswith("l.registrar_hot.")]
    assert len(hot) == 10
    for k in hot:
        assert cast.speaker_for(cfg, k) == "taxlady" and k not in cast.OFFICER_KEYS, k
        line = engine.tx(k, goods="Silk", where="Calcutta", home="Manila", port="Manila", when="next month")
        assert "{" not in line and "Silk" in line and "Calcutta" in line, (k, line)
        assert voice.PLAN.matcher.match(line)[0] == k, k
    assert cast.speaker_for(cfg, "l.registrar_hot_logged") == ""


# ------------------------------------------------- hot tips from other ports --
def away_port(home="singapore"):
    return next(k for k in PORTS if k != home)


def test_the_odds_half_at_home_a_fifth_elsewhere():
    setup(hot_enabled=True, hot_home_chance=0.5, hot_away_chance=0.2)
    n, home_hot, away_hot = 300, 0, 0
    for seed in range(n):
        game, p = anchor(seed=seed)
        home_hot += bool((p["customs"].get("tip") or {}).get("hot"))
        assert p["customs"].get("tip"), seed                       # at home: a price tip when no hot tip
        game, p = anchor(port=away_port(), seed=seed)
        tip = p["customs"].get("tip")
        away_hot += bool(tip)
        assert not tip or tip["hot"], tip                          # elsewhere: a hot tip or nothing
    assert 0.40 < home_hot / n < 0.60, home_hot
    assert 0.12 < away_hot / n < 0.28, away_hot
    setup(hot_enabled=True, hot_home_chance=0.0, hot_away_chance=0.0)
    _, p = anchor()
    assert not p["customs"]["tip"].get("hot")
    _, p = anchor(port=away_port())
    assert not p["customs"].get("tip")


def test_a_port_officer_gives_a_hot_tip_away_from_home():
    setup(hot_enabled=True, hot_away_chance=1.0)
    for port in PORTS:
        home = "calcutta" if port != "calcutta" else "manila"
        game, p = anchor(port=port, home=home)
        cu = p["customs"]
        tip = cu["tip"]
        assert cu["officer"] != "taxlady" and tip["hot"] and tip["by"] == "officer", (port, tip)
        assert tip["officer"] == cu["officer"] and tip["home"] == port and tip["port"] != port
        assert tip["key"].startswith("l.officer_hot."), tip["key"]
        assert "{" not in tip["text"] and GOODS[tip["good"]]["name"] in tip["text"]
        ratio = {g: game.s["prices"][port][g] / (GOODS[g]["base"] * PORTS[port]["mods"].get(g, 1.0)) for g in GOODS}
        assert sorted(ratio, key=lambda g: (ratio[g], g)).index(tip["good"]) < (len(GOODS) + 1) // 2
        assert game.s["forecasts"][-1]["pid"] == p["id"]
        assert any("hot tip" in line and GOODS[tip["good"]]["name"] in line for line in p["log"])
        assert game.customs_view(p)["tip"]["by"] == "officer"
        assert game.view(p["id"])["me"]["hot_tips"][-1]["home"] == port


def test_never_two_hot_tips_at_once_whoever_gives_it():
    setup(hot_enabled=True, hot_every=1, hot_home_chance=1.0, hot_away_chance=1.0)
    game, p = anchor(port=away_port())                             # an officer's tip first
    first = p["customs"]["tip"]
    assert first["by"] == "officer"
    p["port"] = "singapore"                                         # then home, while it still runs
    for step in (1, 2, first["ends"]):
        game.s["turn"] = step
        game._open_customs(p)
        assert not p["customs"]["tip"].get("hot"), (step, p["customs"]["tip"])   # her price tip instead
        p["port"] = away_port()
        game._open_customs(p)
        assert not p["customs"].get("tip"), step
        p["port"] = "singapore"
    game.s["turn"] = first["ends"] + 1                              # over: the Registrar may give one now
    game._open_customs(p)
    assert p["customs"]["tip"]["by"] == "registrar"
    assert len([t for t in p["hot_tips"] if t["ends"] >= game.s["turn"]]) == 1


def test_officer_hot_lines_are_read_by_the_ports_officer():
    cfg = setup(hot_enabled=True)
    voice.PLAN.configure(cfg, engine.TEXT)
    keys = [k for k in strings.EN if k.startswith("l.officer_hot.")]
    assert len(keys) == 10
    for k in keys:
        assert k in cast.OFFICER_KEYS, k                             # handed to the officer of the port
        line = engine.tx(k, goods="Silk", where="Calcutta", home="Manila", port="Manila", when="next month")
        assert "{" not in line and "Silk" in line and "Calcutta" in line, (k, line)
        assert voice.PLAN.matcher.match(line)[0] == k, k
    assert cast.speaker_for(cfg, "l.officer_hot_logged") == ""


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
