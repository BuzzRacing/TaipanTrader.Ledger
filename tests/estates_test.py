"""Port shares and the great house (late game, 19 Nov 2026)."""
import copy

import pytest

import config
import engine


@pytest.fixture
def two_houses():
    original = engine.CFG
    cfg = config.defaults()
    cfg["rules"]["start"]["where"] = "home"
    engine.configure(cfg)
    game = engine.Game(seed=5)
    a = game.pid_for_token(game.join("Ana", "Red Junk"))
    b = game.pid_for_token(game.join("Bea", "Blue Lotus"))
    game.act(a, {"type": "start"})
    try:
        yield game, game.s["players"][a], game.s["players"][b]
    finally:
        engine.configure(original)


def _away(game, p):
    port = next(k for k in engine.PORTS if k != engine.home_of(p) and engine.PORTS[k]["tax_rate"] > 0)
    p["port"] = port
    return port


def test_share_price_follows_port_rate(two_houses):
    game, *_ = two_houses
    # 100,000 per 1% of base rate, kept between 150,000 and 400,000.
    assert game.share_price("singapore") == 150_000      # 1%
    assert game.share_price("hongkong") == 200_000       # 2%
    assert game.share_price("batavia") == 350_000        # 3.5%
    assert game.share_price("calcutta") == 400_000       # 4.5% -> capped


def test_shares_cut_tax_and_count_in_worth(two_houses):
    game, a, b = two_houses
    port = _away(game, a)
    a["cash"] = 5_000_000
    base = game.tax_rate_for(a, port)
    worth0 = game.worth(a)
    game.act(a["id"], {"type": "shares", "op": "buy", "n": 3})
    assert game.shares_held(a, port) == 3
    assert game.tax_rate_for(a, port) == pytest.approx(base * 0.7)
    assert game.worth(a) == pytest.approx(worth0)          # silver became shares at the same value
    view = game.view(a["id"])["me"]["shares"]
    assert view["here"] == 3 and view["left"] == 7 and view["patron_me"]


def test_ten_shares_shared_and_patron(two_houses):
    game, a, b = two_houses
    port = _away(game, a)
    b["port"] = port
    a["cash"] = b["cash"] = 10_000_000
    game.act(a["id"], {"type": "shares", "op": "buy", "n": 4})
    assert game.patron_of(port) == a["id"]
    game.act(b["id"], {"type": "shares", "op": "buy", "n": 4})
    assert game.patron_of(port) == a["id"]                  # a tie: the Patron keeps it
    game.act(b["id"], {"type": "shares", "op": "buy", "n": 5})   # only 2 left
    assert game.shares_held(b, port) == 6
    assert game.patron_of(port) == b["id"]
    assert any("Patron" in n for n in game.s["news"][:3])
    with pytest.raises(engine.GameError):
        game.act(a["id"], {"type": "shares", "op": "buy"})
    # All ten held between them; a full set means no tax.
    assert sum(game._share_book(port).values()) == 10


def test_sell_back_at_price_paid(two_houses):
    game, a, _ = two_houses
    port = _away(game, a)
    a["cash"] = 2_000_000
    price = game.share_price(port)
    game.act(a["id"], {"type": "shares", "op": "buy", "n": 2})
    cash = a["cash"]
    game.act(a["id"], {"type": "shares", "op": "sell", "n": 1})
    assert a["cash"] == cash + price
    assert engine.holdings_value(a) == price


def test_great_house_stages_at_home_only(two_houses):
    game, a, _ = two_houses
    home = engine.home_of(a)
    a["cash"] = 10_000_000
    a["port"] = next(k for k in engine.PORTS if k != home)
    with pytest.raises(engine.GameError):
        game.act(a["id"], {"type": "estate"})
    a["port"] = home
    rep0 = a["rep"][home]
    worth0 = game.worth(a)
    game.act(a["id"], {"type": "estate"})
    assert a["estate"] == 1 and a["estate_paid"] == 500_000
    assert a["rep"][home] == pytest.approx(min(100, rep0 + 5))
    assert game.earned_rep(a, home) == pytest.approx(rep0)   # bought standing: no extra borrowing
    assert game.worth(a) == pytest.approx(worth0)
    game.act(a["id"], {"type": "estate"})
    game.act(a["id"], {"type": "estate"})
    assert a["estate"] == 3 and a["estate_paid"] == 8_500_000
    assert game.house_rob_cut(a) == pytest.approx(0.9)
    with pytest.raises(engine.GameError):
        game.act(a["id"], {"type": "estate"})
    v = game.view(a["id"])["me"]["estate"]
    assert v["stage"] == 3 and v["title"] == "Palace" and v["next"] is None


def test_snapshot_worth_matches_live(two_houses):
    game, a, _ = two_houses
    a["cash"] = 3_000_000
    a["port"] = engine.home_of(a)
    game.act(a["id"], {"type": "estate"})
    _away(game, a)
    game.act(a["id"], {"type": "shares", "op": "buy", "n": 1})
    snap = next(f for f in game.firms() if f["id"] == a["id"])
    assert int(engine.worth_of(snap)) == int(game.worth(a))


def test_survives_reload(two_houses):
    game, a, _ = two_houses
    port = _away(game, a)
    a["cash"] = 1_000_000
    game.act(a["id"], {"type": "shares", "op": "buy"})
    again = engine.Game(copy.deepcopy(game.s), seed=9)
    q = again.s["players"][a["id"]]
    assert again.shares_held(q, port) == 1 and again.patron_of(port) == a["id"]
