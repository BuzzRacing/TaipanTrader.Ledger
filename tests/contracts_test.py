"""The Mayor's commissions (late game, 19 Nov 2026): the home Mayor offers one yearly goal and one
short contract at a time; deliveries, supply runs and standing goals; silver and home standing when
done; nothing lost when missed."""
import copy

import pytest

import config
import engine


@pytest.fixture
def house():
    original = engine.CFG
    cfg = config.defaults()
    cfg["rules"]["start"]["where"] = "home"
    engine.configure(cfg)
    game = engine.Game(seed=8)
    pid = game.pid_for_token(game.join("Sun", "Golden Tide"))
    game.act(pid, {"type": "start"})
    try:
        yield game, game.s["players"][pid]
    finally:
        engine.configure(original)


def _offer(game, p, slot, **fields):
    o = {"id": 99, "slot": slot, "turn": game.s["turn"], "until": game.s["turn"] + 3, "got": 0,
         "rep": 3.0 if slot == "short" else 8.0, "fee": 12345}
    o.update(fields)
    p.setdefault("offers", {})[slot] = o
    return o


def test_first_offers_made_at_start(house):
    game, p = house
    offers = p.get("offers") or {}
    assert offers.get("year") and offers.get("short")
    for o in offers.values():
        assert o["kind"] in ("delivery", "supply", "standing")
        assert o["port"] != engine.home_of(p) and o["fee"] > 0
    v = game.view(p["id"])["me"]["commissions"]
    assert v["home"] and set(v["offers"]) == {"year", "short"}


def test_take_at_home_only(house):
    game, p = house
    other = next(k for k in engine.PORTS if k != engine.home_of(p))
    _offer(game, p, "short", kind="delivery", port=other, good="tea", qty=20, due=game.s["turn"] + 3)
    p["port"] = other
    with pytest.raises(engine.GameError):
        game.act(p["id"], {"type": "contract", "op": "accept", "slot": "short"})
    p["port"] = engine.home_of(p)
    game.act(p["id"], {"type": "contract", "op": "accept", "slot": "short"})
    assert [k["slot"] for k in p["contracts"]] == ["short"]
    assert p["offers"]["short"] is None


def test_delivery_pays_silver_and_home_standing(house):
    game, p = house
    home = engine.home_of(p)
    other = next(k for k in engine.PORTS if k != home)
    _offer(game, p, "short", kind="delivery", port=other, good="tea", qty=20, due=game.s["turn"] + 3)
    game.act(p["id"], {"type": "contract", "op": "accept", "slot": "short"})
    p["port"] = other
    p["cargo"]["tea"] = 25
    rep0, cash0 = p["rep"][home], p["cash"]
    game.act(p["id"], {"type": "sell", "good": "tea", "qty": 10})
    assert p["contracts"][0]["got"] == 10 and p["cash"] - cash0 < 12345
    gain_cash = p["cash"]
    game.act(p["id"], {"type": "sell", "good": "tea", "qty": 10})
    assert not p["contracts"]
    assert p["cash"] - gain_cash > 12345 - 1               # the fee came with the sale
    assert p["rep"][home] == pytest.approx(min(100, rep0 + 3))
    assert p["contract_tally"]["done"] == 1


def test_selling_elsewhere_does_not_count(house):
    game, p = house
    home = engine.home_of(p)
    ports = [k for k in engine.PORTS if k != home]
    _offer(game, p, "short", kind="delivery", port=ports[0], good="tea", qty=20, due=game.s["turn"] + 3)
    game.act(p["id"], {"type": "contract", "op": "accept", "slot": "short"})
    p["port"] = ports[1]
    p["cargo"]["tea"] = 30
    game.act(p["id"], {"type": "sell", "good": "tea", "qty": 30})
    assert p["contracts"][0]["got"] == 0


def test_standing_goal(house):
    game, p = house
    home = engine.home_of(p)
    other = next(k for k in engine.PORTS if k != home)
    p["rep"][other] = 50.0
    _offer(game, p, "year", kind="standing", port=other, target=60, due=game.s["turn"] + 11)
    game.act(p["id"], {"type": "contract", "op": "accept", "slot": "year"})
    assert p["contracts"]
    p["rep"][other] = 61.0
    cash0 = p["cash"]
    game._check_contracts(p)
    assert not p["contracts"] and p["cash"] == cash0 + 12345


def test_missed_is_only_a_missed_chance(house):
    game, p = house
    home = engine.home_of(p)
    other = next(k for k in engine.PORTS if k != home)
    _offer(game, p, "short", kind="delivery", port=other, good="tea", qty=20, due=game.s["turn"])
    game.act(p["id"], {"type": "contract", "op": "accept", "slot": "short"})
    rep, cash, debt = dict(p["rep"]), p["cash"], p["debt"]
    game.s["turn"] += 1
    game._contracts_month(p)
    assert not p["contracts"] and p["contract_tally"]["missed"] == 1
    assert p["rep"] == rep and p["cash"] == cash and p["debt"] == debt
    assert p["offers"]["short"]                              # and a new offer follows


def test_one_of_each_at_a_time(house):
    game, p = house
    home = engine.home_of(p)
    other = next(k for k in engine.PORTS if k != home)
    _offer(game, p, "short", kind="delivery", port=other, good="tea", qty=20, due=game.s["turn"] + 3)
    game.act(p["id"], {"type": "contract", "op": "accept", "slot": "short"})
    game._contracts_month(p)
    assert p["offers"].get("short") is None                  # no second contract while one is open


def test_decline_and_reload(house):
    game, p = house
    game.act(p["id"], {"type": "contract", "op": "decline", "slot": "year"})
    assert p["offers"]["year"] is None
    again = engine.Game(copy.deepcopy(game.s), seed=1)
    assert again.view(p["id"])["me"]["commissions"]["offers"].keys() == {"short"}


def test_offers_survive_a_full_year_of_play(house):
    game, p = house
    for _ in range(14):
        game.act(p["id"], {"type": "sail", "dest": engine.home_of(p)})
        game.resolve()
        if game.s["phase"] == "sea":
            game._sea_force()
        for slot, o in (p.get("offers") or {}).items():
            if o and not any(k["slot"] == slot for k in p.get("contracts") or []) and p["port"] == engine.home_of(p):
                game.act(p["id"], {"type": "contract", "op": "accept", "slot": slot})
    assert len([k for k in p.get("contracts") or [] if k["slot"] == "year"]) <= 1
    assert len([k for k in p.get("contracts") or [] if k["slot"] == "short"]) <= 1
