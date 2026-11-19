"""The flagship (late game, 19 Nov 2026): one per house, outside the class limits, a big hold and heavy
guns, pirates think twice, she always sinks last, and a sunk one can be bought again at full price."""
import pytest

import config
import engine


@pytest.fixture
def house():
    original = engine.CFG
    cfg = config.defaults()
    cfg["rules"]["start"]["where"] = "home"
    engine.configure(cfg)
    game = engine.Game(seed=3)
    pid = game.pid_for_token(game.join("Kit", "Pearl River"))
    game.act(pid, {"type": "start"})
    p = game.s["players"][pid]
    p["port"] = next(k for k in engine.PORTS if engine.PORTS[k]["shipyard"])
    try:
        yield game, p
    finally:
        engine.configure(original)


def test_flagship_in_settings_and_saved_tables_gain_her():
    cfg = config.defaults()
    assert cfg["ships"]["flagship"]["role"] == "flagship"
    saved = config.defaults()
    del saved["ships"]["flagship"]
    saved["rules"]["fleet"]["seeded_ships"] = ["gunboat", "countryship"]
    again, errors = config.validate(saved)
    assert not errors and "flagship" in again["ships"]


def test_buy_one_named_outside_limits(house):
    game, p = house
    p["cash"] = 10_000_000
    # A full line of merchantmen does not stop her: she is outside the limits.
    for _ in range(4):
        game.act(p["id"], {"type": "buy_ship", "ship": "junk"})
    with pytest.raises(engine.GameError):
        game.act(p["id"], {"type": "buy_ship", "ship": "junk"})
    game.act(p["id"], {"type": "buy_ship", "ship": "flagship", "name": "Crimson Empress"})
    flag = [sh for sh in p["ships"] if sh["type"] == "flagship"]
    assert len(flag) == 1 and flag[0]["name"] == "Crimson Empress"
    assert game.capacity(p) >= 1500
    with pytest.raises(engine.GameError):
        game.act(p["id"], {"type": "buy_ship", "ship": "flagship"})
    classes = game.view(p["id"])["me"]["classes"]
    assert classes["flagship"] == {"n": 1, "max": 1, "unlock": 0, "open": True}
    assert classes["trader"]["n"] == 5


def test_name_must_be_free(house):
    game, p = house
    p["cash"] = 10_000_000
    taken = p["ships"][0]["name"]
    with pytest.raises(engine.GameError):
        game.act(p["id"], {"type": "buy_ship", "ship": "flagship", "name": taken})


def test_pirates_think_twice(house):
    game, p = house
    assert game.flag_deter(p) == 1.0
    p["ships"].append(game._new_ship("flagship", name="Iron Lotus"))
    assert game.flag_deter(p) == pytest.approx(0.6)


def test_she_sinks_last(house):
    game, p = house
    flag = game._new_ship("flagship", name="Iron Lotus")
    p["ships"].append(flag)
    flag["hull"] = -50
    game._flag_floor(p, flag)
    assert flag["hull"] == 1                      # the junk is still afloat
    p["ships"][0]["hull"] = 0
    flag["hull"] = -5
    game._flag_floor(p, flag)
    assert flag["hull"] == -5                     # nothing else afloat: she goes down


def test_she_sinks_last_in_a_real_fight(house):
    game, p = house
    flag = game._new_ship("flagship", name="Iron Lotus")
    p["ships"].append(flag)
    flag["hull"] = 5                              # nearly gone, beside a sound junk
    b = {"hit": 1.0, "dmg": [40, 40], "formation": True, "focus": 0.0, "eg": [6] * 6}
    for _ in range(3):
        game._enemy_fire(p, b, [1] * 6)
        if any(sh is not flag and sh["hull"] > 0 for sh in p["ships"]):
            assert flag["hull"] >= 1


def test_rebuy_after_loss(house):
    game, p = house
    p["cash"] = 10_000_000
    game.act(p["id"], {"type": "buy_ship", "ship": "flagship"})
    flag = next(sh for sh in p["ships"] if sh["type"] == "flagship")
    flag["hull"] = 0
    game._check_sunk(p, "test")
    assert not any(sh["type"] == "flagship" for sh in p["ships"])
    cash = p["cash"]
    game.act(p["id"], {"type": "buy_ship", "ship": "flagship"})
    assert cash - p["cash"] == engine.SHIPS["flagship"]["price"]
