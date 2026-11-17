"""The Registrar (Mrs. Evelyn Marlowe, cast key "taxlady"): found only in a captain's own home port,
where she meets the house, waves it in and gives one price tip, read aloud.

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
    base = config.defaults()
    base["rules"]["start"]["where"] = "home"
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


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
