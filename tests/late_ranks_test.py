"""Ranks above Taipan (19 Nov 2026): Tai-Pan of the China Seas, Merchant Lord and Hong Master.
Their worth is set for a 10-year game and scales with the game's length; the ceremony is the
same Mayor promotion, with her own grander lines."""
import copy

import pytest

import config
import engine


@pytest.fixture
def game10():
    original = engine.CFG
    cfg = config.defaults()
    cfg["rules"]["start"]["where"] = "home"
    engine.configure(cfg)
    game = engine.Game(seed=21)
    pid = game.pid_for_token(game.join("Mei", "Jade Sail"))
    game.s["years"] = 10
    game.act(pid, {"type": "start"})
    try:
        yield game, game.s["players"][pid]
    finally:
        engine.configure(original)


def _ids():
    return [r["id"] for r in engine.CFG["ranks"]]


def test_three_new_ranks_above_taipan():
    original = engine.CFG
    try:
        engine.configure(config.defaults())
        ids = _ids()
        assert ids[-4:] == ["taipan", "tai_pan_china_seas", "merchant_lord", "hong_master"]
        assert [r["worth"] for r in engine.CFG["ranks"][-3:]] == [40_000_000, 100_000_000, 250_000_000]
    finally:
        engine.configure(original)


def test_thresholds_scale_with_game_length():
    original = engine.CFG
    try:
        engine.configure(config.defaults())
        assert engine.rank_thresholds(10)[-3:] == [40_000_000, 100_000_000, 250_000_000]
        assert engine.rank_thresholds(5)[-3:] == [20_000_000, 50_000_000, 125_000_000]
        assert engine.rank_thresholds(1)[-3:] == [4_000_000, 10_000_000, 25_000_000]
        # Ranks up to Taipan never move.
        assert engine.rank_thresholds(1)[:-3] == engine.rank_thresholds(10)[:-3]
        assert engine.rank_for(5_000_000, 1) == "Tai-Pan of the China Seas"
        assert engine.rank_for(3_000_000, 10) == "Taipan"
        assert engine.rank_for(250_000_000, 10) == "Hong Master"
    finally:
        engine.configure(original)


def test_scaled_rank_never_drops_below_taipan():
    original = engine.CFG
    cfg = config.defaults()
    cfg["rules"]["game"]["rank_years"] = 100      # a 1-year game would put Tai-Pan at $250,000
    try:
        engine.configure(cfg)
        th = engine.rank_thresholds(1)
        assert th == sorted(th) and len(set(th)) == len(th)
        assert th[-3] > th[-4] == 1_000_000
    finally:
        engine.configure(original)


def test_promotion_to_top_rank_uses_mayor_ceremony_and_top_lines(game10):
    game, p = game10
    pid = p["id"]
    p["rank_id"] = "taipan"
    p["cash"] = 45_000_000
    game._check_promotions()
    me = game.view(pid)["me"]
    assert me["rank_id"] == "tai_pan_china_seas"
    award = me["promotion"]
    assert award["port"] == p["home"]
    assert award["text"] and award["record"]["next"]["id"] == "merchant_lord"
    assert award["record"]["next"]["worth"] == 100_000_000
    assert me["next_rank"]["worth"] == 100_000_000
    said = {engine.TEXT[k].format(name=p["name"], rank="Tai-Pan of the China Seas", firm=p["firm"],
                                   port=engine.PORTS[p["home"]]["name"])
            for k in engine.TEXT if k.startswith("m.promote_top.")}
    assert award["text"] in said


def test_short_game_shows_scaled_goal(game10):
    game, p = game10
    pid = p["id"]
    game.s["years"] = 5
    p["rank_id"] = "taipan"
    p["cash"] = 21_000_000
    game._check_promotions()
    me = game.view(pid)["me"]
    assert me["rank_id"] == "tai_pan_china_seas"
    assert me["next_rank"]["id"] == "merchant_lord" and me["next_rank"]["worth"] == 50_000_000


def test_saved_settings_gain_new_ranks_once():
    saved = config.defaults()
    saved["ranks"] = [r for r in saved["ranks"] if not r.get("scales")]
    for r in saved["ranks"]:
        r.pop("scales", None)
    saved["rules"]["game"].pop("late_ranks_v1", None)
    cfg, errors = config.validate(copy.deepcopy(saved))
    assert not errors
    assert [r["id"] for r in cfg["ranks"]][-3:] == ["tai_pan_china_seas", "merchant_lord", "hong_master"]
    assert cfg["rules"]["game"]["late_ranks_v1"] is True
    # Deleting one afterwards sticks.
    cfg["ranks"] = [r for r in cfg["ranks"] if r["id"] != "merchant_lord"]
    again, errors = config.validate(copy.deepcopy(cfg))
    assert not errors and "merchant_lord" not in [r["id"] for r in again["ranks"]]


def test_certificate_styles_and_badges_exist():
    import os
    styles = config.promotion_styles()
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for rid in ("tai_pan_china_seas", "merchant_lord", "hong_master"):
        assert rid in styles
        assert os.path.isfile(os.path.join(root, "web", "assets", "rank-badges", rid + ".png"))
