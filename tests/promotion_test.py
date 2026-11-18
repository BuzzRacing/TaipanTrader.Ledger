import copy

import pytest

import config
import engine


@pytest.fixture
def captain_game():
    original = engine.CFG
    cfg = config.defaults()
    cfg["rules"]["start"]["where"] = "home"
    engine.configure(cfg)
    game = engine.Game(seed=12)
    pid = game.pid_for_token(game.join("Lin Wei", "Lin & Co."))
    game.act(pid, {"type": "start"})
    try:
        yield game, game.s["players"][pid]
    finally:
        engine.configure(original)


def test_commission_on_return_and_acknowledgment_survives_reload(captain_game, monkeypatch):
    game, captain = captain_game
    pid = captain["id"]
    captain["port"] = "shanghai"
    starting_rank = captain["rank_id"]
    captain["cash"] = 240000
    game.act(pid, {"type": "unsail"})
    away = game.view(pid)["me"]
    assert away["rank_id"] == starting_rank
    assert away["qualified_rank"] == "Senior Merchant"
    assert away["promotion"] is None

    monkeypatch.setattr(game, "_chance", lambda *args, **kwargs: False)
    game.act(pid, {"type": "sail", "dest": captain["home"]})
    game.resolve()
    arrived = game.view(pid)["me"]
    assert arrived["rank_id"] == "senior_merchant"
    assert arrived["next_rank"]["id"] == "merchant_prince"
    award = arrived["promotion"]
    assert award["port"] == captain["home"]
    assert game.view(None)["players"][0]["rank"] == "Senior Merchant"

    resumed = engine.Game(copy.deepcopy(game.s), seed=13)
    assert resumed.view(pid)["me"]["promotion"] == award
    resumed.act(pid, {"type": "promotion_ack", "id": award["id"] + 1})
    assert resumed.view(pid)["me"]["promotion"] == award
    resumed.act(pid, {"type": "promotion_ack", "id": award["id"]})
    resumed.act(pid, {"type": "promotion_ack", "id": award["id"]})
    assert resumed.view(pid)["me"]["promotion"] is None
    resumed.s["players"][pid]["cash"] = 0
    resumed.act(pid, {"type": "unsail"})
    assert resumed.view(pid)["me"]["rank"] == "Senior Merchant"


def test_recheck_after_arrival_settlement(captain_game):
    game, captain = captain_game
    pid = captain["id"]
    captain["cash"] = 240000
    captain["customs"] = {"port": captain["home"], "status": "verdict"}
    game.act(pid, {"type": "unsail"})
    assert not captain.get("promotions")

    captain["cash"] = 55000
    game.act(pid, {"type": "customs_done"})
    assert game.view(pid)["me"]["promotion"]["rank_id"] == "merchant"
