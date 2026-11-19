import copy

import pytest

import config
import engine
import stats


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


def test_commission_keeps_award_figures_when_captain_changes(captain_game):
    game, captain = captain_game
    captain["cash"] = 55000
    game._check_promotions()
    award = copy.deepcopy(captain["promotions"][0])
    assert award["record"]["worth"] == int(game.worth(captain))
    assert award["record"]["ships"] == len(captain["ships"])
    assert award["record"]["next"]["id"] == "senior_merchant"
    assert award["record"]["ranks"][3]["id"] == "merchant"
    captain["cash"] = 2000000
    captain["name"] = "Changed name"
    game.s["turn"] += 3
    game._check_promotions()
    assert captain["promotions"][0] == award
    assert captain["promotions"][-1]["record"]["next"] is None
    assert captain["promotions"][-1]["record"]["previous"]["id"] == "merchant"


def test_history_stops_at_award_even_with_later_trades_and_voyages(monkeypatch):
    events = [
        {"type": "seat_new", "pid": "p1", "name": "Lin", "firm": "Lin & Co."},
        {"type": "seat_new", "pid": "p2", "name": "Bao", "firm": "Bao & Co."},
        {"cat": "trade", "type": "buy", "pid": "p1", "good": "tea", "qty": 10, "total": 100, "port": "hongkong"},
        {"cat": "trade", "type": "sell", "pid": "p1", "good": "tea", "qty": 10, "total": 200, "port": "shanghai"},
        {"cat": "voyage", "type": "sailed", "pid": "p1", "origin": "hongkong", "dest": "shanghai"},
        {"cat": "voyage", "type": "arrived", "pid": "p1", "port": "shanghai"},
        {"cat": "trade", "type": "sell", "pid": "p2", "good": "tea", "qty": 1000, "total": 1000000, "port": "shanghai"},
        {"type": "promotion", "pid": "p1", "promotion_id": 2, "rank": "Merchant"},
        {"cat": "trade", "type": "sell", "pid": "p1", "good": "tea", "qty": 1000, "total": 2000000, "port": "shanghai"},
        {"cat": "voyage", "type": "sailed", "pid": "p1", "origin": "shanghai", "dest": "hongkong"},
        {"cat": "voyage", "type": "arrived", "pid": "p1", "port": "hongkong"},
    ]
    monkeypatch.setattr(stats, "_commissions", {})
    monkeypatch.setattr(stats, "_read", lambda gid: {"events": events, "colors": {}})
    award = {"id": 2, "rank_id": "merchant", "title": "Merchant"}
    record = stats.promotion_record("test", "p1", award)
    assert record["voyages"] == 1
    assert record["ports"] == 1
    assert record["profit"] == 100
    assert record["best"]["profit"] == 100
    assert record["best"]["qty"] == 10
    assert stats.promotion_record("test", "p1", dict(award, id=3)) is None


def test_rank_styles_and_portrait_roles_cover_every_commission():
    import media

    styles = config.promotion_styles()
    roles = {role for role, _label in media.KINDS["port"]["roles"]}
    for rank in config.defaults()["ranks"][1:]:
        assert rank["id"] in styles
        assert "mayor_" + rank["id"] in roles
    assert len({tuple(styles[r][k] for k in ("tone", "paper", "metal")) for r in styles if r != "debtor"}) == 6


def test_server_adds_only_the_captains_award_history_without_mutating_save(captain_game, monkeypatch):
    import server

    game, captain = captain_game
    captain["cash"] = 55000
    game._check_promotions()
    original = copy.deepcopy(captain["promotions"][0])
    history = {"voyages": 3, "ports": 2, "won": 0, "best": None}
    calls = []
    def award_history(gid, pid, award):
        calls.append((gid, pid, award["id"]))
        return history
    monkeypatch.setattr(server.stats, "promotion_record", award_history)
    monkeypatch.setattr(server.voice.PLAN, "lines", lambda *args, **kwargs: [])
    monkeypatch.setattr(server.captains, "faces", lambda *args: {})
    hub = server.Hub(game, "http://test")
    view = hub.view(captain["id"])
    assert view["me"]["promotion"]["achievements"] == history
    assert calls == [(game.s["game_id"], captain["id"], original["id"])]
    assert captain["promotions"][0] == original
