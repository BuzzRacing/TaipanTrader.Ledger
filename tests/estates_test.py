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
    # The listed prices themselves; how they grow with a rich house is in review3_test.
    cfg["rules"]["estates"]["wealth_scale"] = False
    cfg["rules"]["fleet"]["upkeep_enabled"] = False
    # The silver sale (the old rule): the captain's share allowance has its own tests below.
    cfg["rules"]["estates"]["shares_buy"] = True
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


# ---- Captain's share allowance (19 Nov 2026) -------------------------------------------------

@pytest.fixture
def earned():
    """The rule as shipped: no silver sale, shares earned by promotion, 10 per captain."""
    original = engine.CFG
    cfg = config.defaults()
    cfg["rules"]["start"]["where"] = "home"
    cfg["rules"]["fleet"]["upkeep_enabled"] = False
    engine.configure(cfg)
    game = engine.Game(seed=5)
    a = game.pid_for_token(game.join("Ana", "Red Junk"))
    b = game.pid_for_token(game.join("Bea", "Blue Lotus"))
    game.act(a, {"type": "start"})
    try:
        yield game, game.s["players"][a], game.s["players"][b]
    finally:
        engine.configure(original)


def _promote_to(game, p, rank_id):
    p["port"] = engine.home_of(p)
    target = next(r for r in engine.CFG["ranks"] if r["id"] == rank_id)
    p["cash"] = engine.rank_worth(target, game.s.get("years")) + p["debt"] + 1000
    game._promote(p)
    assert p["rank_id"] == rank_id


def test_no_silver_sale_and_none_earned_at_start(earned):
    game, a, _ = earned
    assert engine.R["estates"]["shares_buy"] is False
    assert game.shares_earned(a) == 0
    _away(game, a)
    a["cash"] = 50_000_000
    with pytest.raises(engine.GameError):
        game.act(a["id"], {"type": "shares", "op": "buy"})
    assert game.shares_total(a) == 0 and a["cash"] == 50_000_000


def test_each_promotion_earns_one_free_share(earned):
    game, a, _ = earned
    _promote_to(game, a, "trader")
    assert game.shares_earned(a) == 1 and game.shares_free(a) == 1
    port = _away(game, a)
    cash = a["cash"]
    game.act(a["id"], {"type": "shares", "op": "buy"})
    assert game.shares_held(a, port) == 1 and a["cash"] == cash      # free
    assert game.shares_free(a) == 0
    with pytest.raises(engine.GameError):                            # nothing left to place
        game.act(a["id"], {"type": "shares", "op": "buy"})
    v = game.view(a["id"])["me"]["shares"]
    assert v["earned"] == 1 and v["free"] == 0 and v["placed"] == 1 and v["cap"] == 10 and not v["buy"]


def test_a_jump_of_several_ranks_earns_one_per_rank(earned):
    game, a, _ = earned
    _promote_to(game, a, "merchant_prince")          # Clerk -> Merchant Prince: four ranks
    assert game.shares_earned(a) == 4
    _promote_to(game, a, "hong_master")              # four more
    assert game.shares_earned(a) == 8                # the top of today's ladder; two awards to come


def test_awards_stop_at_ten(earned):
    game, a, _ = earned
    assert game.award_shares(a, 8, "test") == 8
    assert game.award_shares(a, 5, "test") == 2
    assert game.award_shares(a, 1, "test") == 0
    assert game.shares_earned(a) == 10


def test_ten_in_all_one_port_or_spread(earned):
    game, a, _ = earned
    game.award_shares(a, 10, "test")
    port = _away(game, a)
    game.act(a["id"], {"type": "shares", "op": "buy", "n": 10})
    assert game.shares_held(a, port) == 10 and game.tax_rate_for(a, port) == 0
    other = next(k for k in engine.PORTS if k not in (port, engine.home_of(a)))
    a["port"] = other
    with pytest.raises(engine.GameError):
        game.act(a["id"], {"type": "shares", "op": "buy"})
    # Take some back in the first port and spread them.
    a["port"] = port
    game.act(a["id"], {"type": "shares", "op": "sell", "n": 4})
    assert game.shares_free(a) == 4 and a["cash"] >= 0
    a["port"] = other
    game.act(a["id"], {"type": "shares", "op": "buy", "n": 4})
    assert game.shares_held(a, port) == 6 and game.shares_held(a, other) == 4
    assert game.shares_total(a) == 10


def test_old_save_hands_back_shares_above_rank(earned):
    game, a, _ = earned
    a["rank_id"] = "trader"                          # one share earned at this rank
    port = _away(game, a)
    engine.R["estates"]["shares_buy"] = True
    a["cash"] = 200_000_000
    game.act(a["id"], {"type": "shares", "op": "buy", "n": 10})
    paid = a["share_paid"][port]
    engine.R["estates"]["shares_buy"] = False
    state = copy.deepcopy(game.s)
    for p in state["players"].values():
        p.pop("share_earned", None)                  # as saved before the allowance
    again = engine.Game(state, seed=9)
    q = again.s["players"][a["id"]]
    assert again.shares_earned(q) == 1 and again.shares_held(q, port) == 1
    assert q["cash"] == pytest.approx(a["cash"] + paid * 9 / 10, abs=10)
    assert any("handed back" in line for line in q["log"])


def test_bankruptcy_loses_seized_shares(earned):
    game, a, _ = earned
    game.award_shares(a, 3, "test")
    _away(game, a)
    game.act(a["id"], {"type": "shares", "op": "buy", "n": 3})
    game._bankrupt(a, [])
    assert game.shares_total(a) == 0 and game.shares_earned(a) == 0


def test_great_house_sells_back_at_half(two_houses):
    """Selling back (19 Nov 2026): the top stage goes for half of what it cost, with its standing,
    its cut in robbery and its share of December's upkeep."""
    game, a, _ = two_houses
    home = engine.home_of(a)
    a["port"] = home
    a["cash"] = 10_000_000
    a["rep"][home] = 50.0
    for _ in range(3):
        game.act(a["id"], {"type": "estate"})
    assert a["estate"] == 3 and a["rep"][home] == pytest.approx(75)
    v = game.view(a["id"])["me"]["estate"]
    assert v["sell"] and v["sell_price"] == 3_000_000 and v["sell_share"] == 0.5
    assert v["upkeep"] == 510_000 and v["upkeep_after"] == 150_000
    cash0 = a["cash"]
    game.act(a["id"], {"type": "estate", "op": "sell"})
    assert a["estate"] == 2 and a["estate_paid"] == 2_500_000
    assert a["cash"] == cash0 + 3_000_000
    assert a["rep"][home] == pytest.approx(63)
    assert game.earned_rep(a, home) == pytest.approx(50)
    assert game.house_rob_cut(a) == pytest.approx(0.6)
    assert [b for b in game.yearly_upkeep(a) if b[0] == "house"] == [("house", None, 150_000)]
    game.act(a["id"], {"type": "estate", "op": "sell"})
    game.act(a["id"], {"type": "estate", "op": "sell"})
    assert a["estate"] == 0 and a["estate_paid"] == 0
    assert a["cash"] == cash0 + 3_000_000 + 1_000_000 + 250_000
    assert a["rep"][home] == pytest.approx(50)
    assert game.house_rob_cut(a) == 0 and not game.yearly_upkeep(a)
    with pytest.raises(engine.GameError):
        game.act(a["id"], {"type": "estate", "op": "sell"})
    # And it can be built again, at full price.
    game.act(a["id"], {"type": "estate"})
    assert a["estate"] == 1 and a["estate_paid"] == 500_000


def test_great_house_sell_home_only_and_switch(two_houses):
    game, a, _ = two_houses
    home = engine.home_of(a)
    a["port"], a["cash"] = home, 1_000_000
    game.act(a["id"], {"type": "estate"})
    a["port"] = next(k for k in engine.PORTS if k != home)
    with pytest.raises(engine.GameError):
        game.act(a["id"], {"type": "estate", "op": "sell"})
    a["port"] = home
    engine.R["estates"]["house_sell"] = False
    try:
        with pytest.raises(engine.GameError):
            game.act(a["id"], {"type": "estate", "op": "sell"})
        assert game.view(a["id"])["me"]["estate"]["sell"] is False
    finally:
        engine.R["estates"]["house_sell"] = True


def test_great_house_sell_old_save(two_houses):
    """A save from before the sell-back kept only the total paid: it is split by the listed prices."""
    game, a, _ = two_houses
    home = engine.home_of(a)
    a["port"] = home
    a["estate"], a["estate_paid"] = 2, 5_000_000      # paid 2x the listed 2.5M (a richer house)
    a.pop("estate_costs", None)
    a.pop("estate_rep", None)
    a["rep"][home] = 70.0
    cash0 = a["cash"]
    game.act(a["id"], {"type": "estate", "op": "sell"})
    assert a["cash"] == cash0 + 2_000_000             # half of the Mansion's 4M share
    assert a["estate"] == 1 and a["estate_paid"] == pytest.approx(1_000_000)
    assert a["rep"][home] == pytest.approx(62)
