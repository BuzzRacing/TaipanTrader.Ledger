"""Legends (owner's decisions, 20 Nov 2026; project doc "SeaTrader Legends Library").

Run from the project folder:  python -m pytest tests/legend_test.py
"""
import copy
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import cast  # noqa: E402
import config  # noqa: E402
import engine  # noqa: E402
import legend  # noqa: E402
import legend_cast  # noqa: E402
import legend_tales  # noqa: E402
import strings  # noqa: E402
from engine import Game, GameError, GOODS, SHIPS  # noqa: E402


def setup(**rules):
    cfg = config.defaults()
    cfg["rules"]["weather"]["storm_chance"] = [0, 0, 0, 0]
    cfg["rules"]["weather"].update({"offcourse": 0.0})
    cfg["rules"]["pirates"].update({"chance": 0.0})
    cfg["rules"]["liyuen"]["chance"] = 0.0
    cfg["rules"]["fleet"]["upkeep_enabled"] = False
    cfg["rules"]["bank"]["mug_chance"] = 0.0
    cfg["rules"]["customs"]["enabled"] = False
    cfg["rules"]["jail"]["enabled"] = False
    cfg["rules"]["legend"]["eager"] = True
    for path, value in rules.items():
        group, key = path.split("__")
        cfg["rules"][group][key] = value
    cfg, errors = config.validate(cfg)
    assert not errors, errors
    engine.configure(cfg)


def new_game(seed=1, cash=50000, cargo=None, port="hongkong"):
    g = Game(seed=seed)
    g.join("Ann", "")
    g.act("p1", {"type": "start"}, present=g.s["order"])
    p = g.s["players"]["p1"]
    p["port"] = port
    p["cargo"] = dict(cargo or {})
    p["basis"] = {k: GOODS[k]["base"] for k in p["cargo"]}
    p["cash"] = cash
    return g, p


def teardown_function(_fn):
    engine.configure(config.defaults())


def sail(g, p, dest):
    g.act("p1", {"type": "sail", "dest": dest, "orders": "run"}, present=["p1"])
    g.resolve("all_ready", {"p1"})


def choose(g, key):
    return g.act("p1", {"type": "legend", "choice": key}, present=["p1"])


def done(g):
    return g.act("p1", {"type": "legend", "done": True}, present=["p1"])


def hop(g, p):
    """One voyage to anywhere but Nagasaki and where she lies."""
    sail(g, p, "manila" if p["port"] != "manila" else "hongkong")


def next_chapter(g, p, limit=60):
    """Sail about until the next chapter opens."""
    for _ in range(limit):
        hop(g, p)
        if p.get("legend"):
            return p["legend"]
    raise AssertionError("the next chapter never came")


def test_the_library_is_sound():
    assert legend_tales.check() == []
    en, fam, spoken = legend_tales.text_keys()
    for key, who in spoken.items():
        assert who == legend_tales.T or who in legend_cast.TELLERS, key
        assert not re.search(r"\d", en[key]), (key, en[key])          # no amounts in a spoken line
        assert set(re.findall(r"\{(\w+)\}", en[key])) <= {"port"}, key
        assert strings.EN[key] == en[key]
    for key in fam:
        assert strings.FAMILY[key] == fam[key] and fam[key] != en[key], key
    for cid in legend_cast.TELLERS:
        ch = cast.CHARACTERS[cid]
        assert ch["voice_id"] and ch["portrait_prompt"] and "{" not in ch["portrait_prompt"], cid
    for tale in legend_tales.TALES.values():
        assert tale["teller"] in legend_cast.STORYTELLERS
        assert 2 <= len(tale["chapters"]) <= 4


def test_no_legends_when_switched_off():
    setup(legend__enabled=False)
    g, p = new_game()
    sail(g, p, "nagasaki")
    assert not p.get("legend") and g.view("p1", {"p1"})["me"]["legend"] is None
    setup(legend__tale_palace=False)
    g, p = new_game()
    sail(g, p, "nagasaki")
    assert not p.get("legend")


def test_a_legend_opens_on_the_landfall_and_takes_no_time():
    setup()
    g, p = new_game()
    sail(g, p, "manila")
    assert not p.get("legend")                      # this one begins at Nagasaki
    sail(g, p, "nagasaki")
    turn = g.s["turn"]
    v = g.view("p1", {"p1"})["me"]["legend"]
    assert v["tale"] == "palace" and v["n"] == 1 and v["of"] == 3 and v["teller"] == "teller_drowned"
    assert len(v["beats"]) == 2 and all(b["text"] and b["side"] == "left" for b in v["beats"])
    assert [c["key"] for c in v["choices"]] == ["free", "sell", "keep"] and not v["done"]
    assert any("Palace Beneath the Waves" in line for line in p["log"])
    cash = p["cash"]
    choose(g, "sell")
    v = g.view("p1", {"p1"})["me"]["legend"]
    assert v["done"] and v["more"] and not v["choices"] and len(v["beats"]) == 1
    stake = legend.stake(g, p)
    gained = p["cash"] - cash
    assert 0.6 * 0.70 * v["stake"] <= gained <= 0.6 * 1.30 * v["stake"], (gained, stake)
    assert {"kind": "silver", "amount": gained} in v["tally"]
    done(g)
    assert not p.get("legend") and g.s["turn"] == turn and g.s["phase"] == "port"
    run = p["legends"]["runs"]["palace"]
    assert run["ch"] == 1 and run["flags"] == ["sold"] and run["due"] > turn
    assert g.view("p1", {"p1"})["me"]["legends"] == [
        {"tale": "palace", "title": "The Palace Beneath the Waves", "state": "running", "chapter": 1, "of": 3}]


def test_wrong_answers_are_refused():
    setup()
    g, p = new_game()
    with pytest.raises(GameError):
        choose(g, "free")                           # no Legend open
    sail(g, p, "nagasaki")
    with pytest.raises(GameError):
        choose(g, "burn it")
    with pytest.raises(GameError):
        done(g)                                     # not before the story is finished
    choose(g, "free")
    with pytest.raises(GameError):
        choose(g, "sell")                           # one answer only
    done(g)


def test_the_choice_comes_back_in_the_next_chapter():
    setup()
    g, p = new_game(cargo={"tea": 40})
    sail(g, p, "nagasaki")
    choose(g, "sell")
    done(g)
    due = p["legends"]["runs"]["palace"]["due"]
    L = next_chapter(g, p)
    assert g.s["turn"] >= due and L["ch"] == 1 and L["node"] == "sold"
    v = g.view("p1", {"p1"})["me"]["legend"]
    assert v["scene"] == "deep" and [c["key"] for c in v["choices"]] == ["pay", "serve", "refuse"]
    assert {b["who"] for b in v["beats"]} == {"teller_drowned", "legend_otohime"}
    assert [b["side"] for b in v["beats"] if b["who"] == "legend_otohime"] == ["right"]
    hull = [sh["hull"] for sh in p["ships"]]
    tea = p["cargo"]["tea"]
    choose(g, "refuse")
    assert all(0 < sh["hull"] < h for sh, h in zip(p["ships"], hull))        # hurt, never sunk
    assert p["cargo"].get("tea", 0) < tea
    done(g)
    assert p["legends"]["runs"]["palace"]["flags"] == ["sold", "enemy"]
    L = next_chapter(g, p)
    assert L["ch"] == 2 and L["node"] == "grudge"                             # no box: the sea is owed
    choose(g, "offer")
    done(g)
    assert p["legends"]["done"] == ["palace"] and not p["legends"]["runs"]
    assert any("is told" in line for line in p["log"])
    for _ in range(6):                                                       # told once, never again
        sail(g, p, "nagasaki" if p["port"] != "nagasaki" else "hongkong")
        assert not p.get("legend")


def test_sea_silk_fills_the_hold_and_the_rest_comes_as_silver():
    setup()
    g, p = new_game(cash=4000000)
    sail(g, p, "nagasaki")
    choose(g, "free")
    done(g)
    next_chapter(g, p)
    room = g.capacity(p) - g.used(p)
    cash = p["cash"]
    choose(g, "trade")
    tally = p["legend"]["tally"]
    silk = next(t for t in tally if t["kind"] == "cargo")
    assert silk["good"] == "silk" and silk["qty"] == room == p["cargo"]["silk"] and g.used(p) == g.capacity(p)
    assert p["basis"]["silk"] == 0                                           # a gift costs nothing
    assert p["cash"] > cash                                                  # what would not fit came as silver
    assert "box" in p["legends"]["runs"]["palace"]["flags"]


def test_a_price_too_big_for_the_purse_goes_to_the_bank_then_the_books():
    setup()
    g, p = new_game(cash=1000)
    sail(g, p, "nagasaki")
    choose(g, "sell")
    done(g)
    next_chapter(g, p)
    p["cash"], p["bank"], debt = 300, 500, p["debt"]
    owed_about = p["legend"]["stake"]
    choose(g, "pay")
    paid = next(t for t in p["legend"]["tally"] if t["kind"] == "silver")
    assert p["cash"] == 0 and p["bank"] == 0
    assert paid["amount"] < 0 and paid["debt"] == -paid["amount"] - 800 == round(p["debt"] - debt)
    assert 0.7 * owed_about <= -paid["amount"] <= 1.3 * owed_about


def walk(g, seen):
    """Play every road from here to the end of the chapter (on copies), collecting the end nodes."""
    L = g.s["players"]["p1"]["legend"]
    if L["done"]:
        seen.add(L["node"])
        done(g)
        return
    node = legend_tales.TALES[L["tale"]]["chapters"][L["ch"]]["nodes"][L["node"]]
    for key, _label, _to in node["choices"]:
        g2 = copy.deepcopy(g)
        choose(g2, key)
        walk(g2, seen)


def test_every_road_of_every_chapter_can_be_walked():
    setup()
    for first, second in (("free", ("stay", "home", "trade")), ("sell", ("pay", "serve", "refuse")),
                          ("keep", ("give", "ransom"))):
        for nxt in second:
            g, p = new_game(seed=3, cargo={"rice": 30})
            sail(g, p, "nagasaki")
            choose(g, first)
            done(g)
            next_chapter(g, p)
            choose(g, nxt)
            assert p["legend"]["done"]
            done(g)
            next_chapter(g, p)
            ends = set()
            walk(g, ends)
            assert ends, (first, nxt)
            assert p["cash"] >= 0 and all(sh["hull"] > 0 for sh in p["ships"])


def test_the_dice_in_the_box_are_the_legends_own():
    setup()
    outcomes = set()
    for seed in range(1, 13):
        g, p = new_game(seed=seed)
        g.s["game_id"] = "g{}".format(seed)
        sail(g, p, "nagasaki")
        choose(g, "keep")
        done(g)
        next_chapter(g, p)
        choose(g, "give")
        done(g)
        next_chapter(g, p)
        g2 = copy.deepcopy(g)
        choose(g, "open")
        choose(g2, "open")
        assert p["legend"]["node"] == g2.s["players"]["p1"]["legend"]["node"]      # the same roll every time
        outcomes.add(p["legend"]["node"])
    assert outcomes <= {"open_bad", "open_good", "open_empty"} and len(outcomes) >= 2


def test_legends_are_rare_in_a_real_game():
    setup(legend__eager=False)
    g, p = new_game()
    sail(g, p, "nagasaki")
    assert not p.get("legend")                      # none before the first month set in Admin
    while g.s["turn"] < 100 and not p.get("legend"):
        sail(g, p, "nagasaki" if p["port"] != "nagasaki" else "hongkong")
    assert p.get("legend") and g.s["turn"] >= legend.rules()["first_month"]
    setup(legend__eager=False, legend__per_game=0)
    g, p = new_game()
    for _ in range(30):
        sail(g, p, "nagasaki" if p["port"] != "nagasaki" else "hongkong")
        assert not p.get("legend")


def test_the_storyteller_follows_the_admin_setting():
    setup(legend__teller="teller_tavern")
    g, p = new_game()
    sail(g, p, "nagasaki")
    assert p["legend"]["teller"] == "teller_tavern"
    assert all(b["who"] == "teller_tavern" for b in g.view("p1", {"p1"})["me"]["legend"]["beats"])
    setup(legend__teller="random")
    g, p = new_game()
    sail(g, p, "nagasaki")
    assert p["legend"]["teller"] in legend_cast.STORYTELLERS


def test_every_road_is_told_quickly():
    """Owner's decision, 21 Nov 2026: the Legends ran about half too long. An opening is at most 3 lines and no
    road through a chapter, from the bell stopping to the Reckoning card, is more than 6."""
    def longest(nodes, name):
        node = nodes[name]
        n = len(node.get("beats") or ())
        nxt = [c[2] for c in node.get("choices") or ()] + ([node["goto"]] if node.get("goto") else [])
        nxt += [t for _w, t in node.get("roll") or ()]
        for opts in (node.get("roll_if") or {}).values():
            nxt += [t for _w, t in opts]
        return n + max([longest(nodes, t) for t in nxt] or [0])
    for tid, tale in legend_tales.TALES.items():
        for ch in tale["chapters"]:
            for _flag, start in ch["start"]:
                assert len(ch["nodes"][start]["beats"]) <= 3, (tid, ch["id"], start)
                assert longest(ch["nodes"], start) <= 6, (tid, ch["id"], start)
