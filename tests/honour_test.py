"""The last two shares (owner's decisions, 21 Nov 2026; project doc "SeaTrader Last Two Shares"; honour.py).

Share 9 is Li Yue's Flag (her whole war fleet sunk often enough for the game's length); share 10 is a Legend's
share (two of a Legend's three choices right). Both are hidden until earned, tell a quick story of their own,
and are never seized at bankruptcy.

Run from the project folder:  python -m pytest tests/honour_test.py
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import config  # noqa: E402
import engine  # noqa: E402
import honour  # noqa: E402
import legend  # noqa: E402
import legend_tales  # noqa: E402
import strings  # noqa: E402
from engine import Game, GameError, GOODS, PORTS  # noqa: E402


def setup(years=10, **rules):
    cfg = config.defaults()
    cfg["rules"]["weather"]["storm_chance"] = [0, 0, 0, 0]
    cfg["rules"]["weather"].update({"offcourse": 0.0, "risk_min": 1.0, "risk_max": 1.0})
    cfg["rules"]["pirates"].update({"chance": 0.0})
    cfg["rules"]["liyuen"].update({"chance": 0.0, "tribute": False})
    cfg["rules"]["fleet"]["upkeep_enabled"] = False
    cfg["rules"]["bank"]["mug_chance"] = 0.0
    cfg["rules"]["customs"]["enabled"] = False
    cfg["rules"]["jail"]["enabled"] = False
    cfg["rules"]["hide"]["enabled"] = False
    cfg["rules"]["legend"]["enabled"] = False
    cfg["rules"]["game"]["default_years"] = years
    for path, value in rules.items():
        group, key = path.split("__")
        cfg["rules"][group][key] = value
    cfg, errors = config.validate(cfg)
    assert not errors, errors
    engine.configure(cfg)
    engine.MULT["pirates"] = 1.0


def teardown_function(_fn):
    engine.configure(config.defaults())


def new_game(seed=1, years=None, port="hongkong", cash=50000):
    g = Game(seed=seed)
    g.join("Ann", "")
    if years:
        g.s["years"] = years
    g.act("p1", {"type": "start"}, present=g.s["order"])
    p = g.s["players"]["p1"]
    p["port"] = port
    p["cargo"], p["basis"] = {}, {}
    p["cash"] = cash
    return g, p


def sail(g, p, dest):
    g.act("p1", {"type": "sail", "dest": dest, "orders": "fight"}, present=["p1"])
    g.resolve("all_ready", {"p1"})


def arm(p):
    """A man-of-war's worth of guns and a hull to match: the war fleet goes down in a round or two."""
    for sh in p["ships"]:
        sh["guns"], sh["hull"] = 400, 100000


def meet_the_queen(g, p, pick="fight"):
    """One voyage into Li Yue's war fleet, played to the end with one answer. Returns the fight's record."""
    arm(p)
    p["protect"] = 0
    sail(g, p, "manila" if p["port"] != "manila" else "hongkong")
    assert g.s["phase"] == "sea" and p["battle"]["kind"] == "lord", g.s["phase"]
    g.fight_out(present=["p1"], pick=lambda v: pick)
    assert g.s["phase"] == "port" and p["fights"][-1]["kind"] == "lord"
    return p["fights"][-1]


def war():
    """Li Yue on every voyage, with her fleet at its plain size (not matched to ours) so the test fleet wins."""
    return dict(liyuen__chance=1.0, battle__limit_min=30, battle__limit_max=30, battle__match=False)


# ------------------------------------------------------------------ Li Yue's Flag --
def test_wins_needed_follow_the_games_length():
    setup()
    for years, need in ((1, 1), (5, 2), (7, 2), (10, 3), (15, 3), (20, 5), (30, 5), (50, 8)):
        g, _p = new_game(years=years)
        assert honour.flag_need(g) == need, (years, honour.flag_need(g))
    setup(estates__flag_wins_10=6)
    g, _p = new_game(years=10)
    assert honour.flag_need(g) == 6


def test_three_war_fleets_sunk_earn_one_share_once():
    setup(**war())
    g, p = new_game()
    assert honour.flag_need(g) == 3
    for n in (1, 2):
        assert meet_the_queen(g, p)["outcome"] == "won"
        assert len(p["lord_wins"]) == n and g.shares_earned(p) == 0 and not p.get("honours")
        assert g.view("p1", ["p1"])["me"]["honour"] is None           # nothing shown before it is earned
    assert meet_the_queen(g, p)["outcome"] == "won"
    assert g.shares_earned(p) == 1 and g.shares_free(p) == 1 and "flag" in p["honours"]
    assert any("Li Yue's flag" in line for line in p["log"])
    assert not any("promotion" in line for line in p["log"])           # its own log line, not the promotion's
    # a fourth win pays nothing more
    assert meet_the_queen(g, p)["outcome"] == "won"
    assert len(p["lord_wins"]) == 4 and g.shares_earned(p) == 1 and len(p["honour_queue"]) == 1


def test_running_from_her_does_not_count():
    setup(**war())
    g, p = new_game()
    for _ in range(4):
        out = meet_the_queen(g, p, pick="run")["outcome"]
        assert out != "won"
    assert not p.get("lord_wins") and g.shares_earned(p) == 0


def test_ordinary_pirates_do_not_count():
    setup(pirates__chance=1.0, battle__limit_min=30, battle__limit_max=30, battle__match=False)
    g, p = new_game()
    won = 0
    for _ in range(4):
        arm(p)
        sail(g, p, "manila" if p["port"] != "manila" else "hongkong")
        g.fight_out(present=["p1"], pick=lambda v: "fight")
        won += p["fights"][-1]["outcome"] == "won" and p["fights"][-1]["kind"] == "pirates"
    assert won >= 3
    assert not p.get("lord_wins") and g.shares_earned(p) == 0 and not p.get("honours")


def test_the_flag_can_be_switched_off():
    setup(estates__flag_enabled=False, **war())
    g, p = new_game()
    for _ in range(3):
        meet_the_queen(g, p)
    assert len(p["lord_wins"]) == 3 and g.shares_earned(p) == 0 and not p.get("honours")


def test_the_flag_tells_its_own_story():
    setup(**war())
    g, p = new_game()
    for _ in range(3):
        meet_the_queen(g, p)
    h = g.view("p1", ["p1"])["me"]["honour"]
    assert h["kind"] == "flag" and h["who"] == "pirate" and h["title"] == "Li Yue's Flag"
    assert h["say"] and h["say"] in [strings.EN["legend.share.say.flag.{}".format(i)] for i in range(4)]
    assert len(h["rows"]) == 3 and all("war junks sunk" in r["text"] and r["head"] for r in h["rows"])
    assert h["earned"] == 1 and h["cap"] == 10 and h["free"] == 1 and h["safe"]
    with pytest.raises(GameError):
        g.act("p1", {"type": "legend", "share_done": h["id"] + 7}, present=["p1"])
    g.act("p1", {"type": "legend", "share_done": h["id"]}, present=["p1"])
    assert g.view("p1", ["p1"])["me"]["honour"] is None
    with pytest.raises(GameError):
        g.act("p1", {"type": "legend", "share_done": h["id"]}, present=["p1"])


def test_the_count_is_hidden_from_the_captain():
    """Owner's decision: hide both. No counter anywhere in what the Captain's screen is sent."""
    setup(**war())
    g, p = new_game()
    meet_the_queen(g, p)
    me = g.view("p1", ["p1"])["me"]
    assert "lord_wins" not in me and "honours" not in me and me["honour"] is None
    assert "wins" not in (me.get("shares") or {})


def test_the_story_survives_a_reload():
    setup(**war())
    g, p = new_game()
    for _ in range(3):
        meet_the_queen(g, p)
    again = Game(json.loads(json.dumps(g.s)), seed=9)          # saved and loaded, as the server does each month
    q = again.s["players"]["p1"]
    assert again.shares_earned(q) == 1 and again.view("p1", ["p1"])["me"]["honour"]["kind"] == "flag"


# ---------------------------------------------------------------- a Legend's share --
def legends(**rules):
    # Only the first Legend is on: these tests walk the Palace. The second set (25 Nov 2026) is tested in
    # tests/legend_test.py, including its shares.
    setup(legend__enabled=True, legend__eager=True, legend__tale_jonah=False, legend__tale_bond=False,
          legend__tale_hunger=False, legend__tale_robe=False, legend__tale_ledger=False, **rules)


def choose(g, key):
    return g.act("p1", {"type": "legend", "choice": key}, present=["p1"])


def done(g):
    return g.act("p1", {"type": "legend", "done": True}, present=["p1"])


def next_chapter(g, p, limit=80):
    for _ in range(limit):
        sail(g, p, "manila" if p["port"] != "manila" else "hongkong")
        if p.get("legend"):
            return p["legend"]
    raise AssertionError("the next chapter never came")


def play(g, p, answers):
    """Open the Palace at Nagasaki and answer its chapters in turn. answers: one choice key for each chapter."""
    sail(g, p, "nagasaki")
    assert p["legend"]["tale"] == "palace"
    for i, key in enumerate(answers):
        if i:
            next_chapter(g, p)
        choose(g, key)
        done(g)


def test_every_question_marks_a_right_answer():
    assert legend_tales.check() == []
    for tale in legend_tales.TALES.values():
        for ch in tale["chapters"]:
            asking = [name for name, node in ch["nodes"].items() if node.get("choices")]
            assert set(asking) == set(ch["right"]), ch["id"]          # a chapter with no question marks none
        assert sum(1 for ch in tale["chapters"] if ch["right"]) >= 2, tale["title"]   # two can be answered rightly


def test_two_right_of_three_earn_the_share_as_the_second_chapter_closes():
    legends()
    g, p = new_game()
    sail(g, p, "nagasaki")
    choose(g, "free")                                   # right
    done(g)
    assert g.shares_earned(p) == 0 and not p.get("honours")
    next_chapter(g, p)
    choose(g, "home")                                   # right: two of three
    assert g.shares_earned(p) == 0                      # not before the chapter's reckoning is closed
    done(g)
    assert g.shares_earned(p) == 1 and "legend" in p["honours"]
    h = g.view("p1", ["p1"])["me"]["honour"]
    assert h["kind"] == "legend" and h["tale"] == "palace" and h["who"] == "teller_drowned"
    assert h["title"] == "The Legend's Share" and h["sub"] == "The Palace Beneath the Waves"
    assert [r["text"] for r in h["rows"]] == ["Cut her free", "Ask to be taken home"]
    assert h["rows"][0]["head"] == "Chapter 1 · The Turtle in the Net"
    assert h["chapter_id"] == "turtle" and h["port"] == "nagasaki"          # the picture that jogs the memory
    assert h["say"] in (strings.EN["legend.share.say.teller_drowned.0"], strings.EN["legend.share.say.teller_drowned.1"])
    # the third chapter still comes, and pays no second share
    g.act("p1", {"type": "legend", "share_done": h["id"]}, present=["p1"])
    next_chapter(g, p)
    choose(g, "keep")
    done(g)
    assert g.shares_earned(p) == 1 and not p.get("honour_queue")


def test_one_right_of_three_earns_nothing():
    legends()
    g, p = new_game()
    play(g, p, ["free", "stay", "open"])
    assert "palace" in p["legends"]["done"] and g.shares_earned(p) == 0 and not p.get("honours")


def test_a_bad_start_can_still_be_put_right():
    """Sell the turtle, then pay what is owed and keep the box shut: two right of three."""
    legends()
    g, p = new_game(cash=5_000_000)
    play(g, p, ["sell", "pay", "keep"])
    assert g.shares_earned(p) == 1 and "legend" in p["honours"]
    h = g.view("p1", ["p1"])["me"]["honour"]
    assert [r["text"] for r in h["rows"]] == ["Pay the blood-price", "Keep it shut"]
    assert h["chapter_id"] == "palace"


def test_the_number_of_right_answers_is_a_setting_and_the_share_a_switch():
    legends(legend__share_right=3)
    g, p = new_game()
    play(g, p, ["free", "home", "open"])
    assert g.shares_earned(p) == 0
    legends(legend__share_right=3)
    g, p = new_game()
    play(g, p, ["free", "home", "keep"])
    assert g.shares_earned(p) == 1
    legends(legend__share=False)
    g, p = new_game()
    play(g, p, ["free", "home", "keep"])
    assert g.shares_earned(p) == 0 and not p.get("honours")


def test_no_button_or_view_gives_the_right_answer_away():
    legends()
    g, p = new_game()
    sail(g, p, "nagasaki")
    L = g.view("p1", ["p1"])["me"]["legend"]
    assert all(set(c) == {"key", "label"} for c in L["choices"])
    assert "right" not in L and "answers" not in L
    choose(g, "free")
    me = g.view("p1", ["p1"])["me"]
    assert "right" not in str(me["legend"]) and me["honour"] is None


# ------------------------------------------------------------------- both together --
def test_both_honours_fill_the_last_two_shares_and_stop_at_ten():
    legends(liyuen__chance=0.0)
    g, p = new_game()
    g.award_shares(p, 8, "test")                        # the eight promotions
    play(g, p, ["free", "home", "keep"])
    assert g.shares_earned(p) == 9
    engine.R["liyuen"]["chance"] = 1.0
    engine.R["battle"].update({"limit_min": 30, "limit_max": 30, "match": False})
    engine.R["legend"]["enabled"] = False
    for _ in range(3):
        meet_the_queen(g, p)
    assert g.shares_earned(p) == 10 and set(p["honours"]) == {"flag", "legend"}
    assert [s["kind"] for s in p["honour_queue"]] == ["legend", "flag"]     # told one after the other
    first = g.view("p1", ["p1"])["me"]["honour"]
    g.act("p1", {"type": "legend", "share_done": first["id"]}, present=["p1"])
    assert g.view("p1", ["p1"])["me"]["honour"]["kind"] == "flag"


def test_no_honour_when_the_house_can_hold_no_more():
    setup(estates__shares_per_house=8, **war())
    g, p = new_game()
    g.award_shares(p, 8, "test")
    for _ in range(3):
        meet_the_queen(g, p)
    assert g.shares_earned(p) == 8 and not p.get("honours") and not p.get("honour_queue")


# ---------------------------------------------------------------------- bankruptcy --
def _place(g, p, port, n):
    g.s.setdefault("shares", {}).setdefault(port, {})[p["id"]] = n


def test_honour_shares_are_never_seized():
    setup(**war())
    g, p = new_game()
    g.award_shares(p, 4, "test")                        # four from promotions
    for _ in range(3):
        meet_the_queen(g, p)                            # and Li Yue's Flag
    assert g.shares_earned(p) == 5
    _place(g, p, "shanghai", 3)
    _place(g, p, "manila", 2)
    g._bankrupt(p, [])
    assert g.shares_held(p, "shanghai") == 1 and g.shares_held(p, "manila") == 0     # kept where she held most
    assert g.shares_total(p) == 1 and g.shares_earned(p) == 1 and "flag" in p["honours"]
    assert any("could not touch 1 share" in line and "Shanghai" in line for line in p["log"])


def test_two_honours_keep_two_shares():
    setup()
    g, p = new_game()
    g.award_shares(p, 10, "test")
    p["honours"] = {"flag": {"turn": 1}, "legend": {"turn": 2}}
    _place(g, p, "shanghai", 10)
    g._bankrupt(p, [])
    assert g.shares_held(p, "shanghai") == 2 and g.shares_earned(p) == 2


def test_the_moneylender_takes_them_when_the_rule_is_off():
    setup(estates__honours_safe=False)
    g, p = new_game()
    g.award_shares(p, 3, "test")
    p["honours"] = {"flag": {"turn": 1}}
    _place(g, p, "shanghai", 3)
    g._bankrupt(p, [])
    assert g.shares_total(p) == 0 and g.shares_earned(p) == 0


def test_a_house_with_no_honours_still_loses_every_share():
    setup()
    g, p = new_game()
    g.award_shares(p, 3, "test")
    _place(g, p, "shanghai", 3)
    g._bankrupt(p, [])
    assert g.shares_total(p) == 0 and g.shares_earned(p) == 0
    assert not any("could not touch" in line for line in p["log"])


# -------------------------------------------------------------------------- wording --
def test_every_speaker_has_her_lines_and_none_carries_an_amount():
    import re
    says = {k: v for k, v in strings.EN.items() if k.startswith("legend.share.say.")}
    for bank in ("flag", "teller_temple", "teller_tavern", "teller_drowned", "any"):
        assert any(k.startswith("legend.share.say.{}.".format(bank)) for k in says), bank
    for key, line in says.items():
        assert "port share" in line, key                 # the fact stays plain
        assert not re.search(r"\d|\{", line), key        # no amounts and no names to fill: recorded once
    for key in strings.FAMILY:
        if key.startswith("legend.share.say."):
            assert key in says and strings.FAMILY[key] != says[key], key
