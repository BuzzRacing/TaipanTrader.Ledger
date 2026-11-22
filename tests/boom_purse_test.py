"""22 Nov 2026: the dealers' purse follows the price. A boom at x4 of usual gives the dealers x4 the silver, so a
full hold sold into it is paid in full instead of a third of it. Fixed at the month turn; settings in Admin >
Economy > The dealers' purse (rules.market.purse_boom, purse_boom_cap)."""
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import config  # noqa: E402
import engine  # noqa: E402
from engine import Game, GOODS, R  # noqa: E402


def configure(**rules):
    cfg = config.defaults()
    cfg["rules"]["start"]["where"] = "home"
    cfg["rules"]["customs"]["enabled"] = False
    for path, value in rules.items():
        group, key = path.split("__")
        cfg["rules"][group][key] = value
    cfg, errors = config.validate(cfg)
    assert not errors, errors
    engine.configure(cfg)


def new_house(**rules):
    configure(**rules)
    g = Game(seed=11)
    pid = g.pid_for_token(g.join("Ana", "Red Junk"))
    g.act(pid, {"type": "start"}, present=[pid])
    p = g.s["players"][pid]
    p["customs"] = None
    g.capacity = lambda _p: 10 ** 9
    p["cash"] = 10 ** 12
    return g, p


@pytest.fixture(autouse=True)
def restore_config():
    original = engine.CFG
    yield
    engine.CFG = original
    engine.configure(original)


def boom(g, port, good, mult, turns=2):
    """Put a boom of this size on a cargo, price at the boom, as the month turn would leave it."""
    g.s["windfalls"] = [w for w in g.s["windfalls"] if not (w["port"] == port and w["good"] == good)]
    g.s["windfalls"].append({"port": port, "good": good, "kind": "boom", "mult": mult, "turns": turns})
    usual = GOODS[good]["base"] * engine.PORTS[port]["mods"].get(good, 1.0)
    g.s["prices"][port][good] = usual * mult
    g._snapshot_purse_lift()


def test_defaults_and_admin_fields():
    configure()
    assert R["market"]["purse_boom"] == 1.0 and R["market"]["purse_boom_cap"] == 10.0
    fields = {f["path"] for sec in config.SECTIONS for grp in sec.get("groups", []) for f in grp["fields"]}
    assert "rules.market.purse_boom" in fields and "rules.market.purse_boom_cap" in fields


def test_old_saved_settings_pick_up_the_new_ones():
    cfg = config.defaults()
    saved = {"rules": {"market": {k: v for k, v in cfg["rules"]["market"].items() if not k.startswith("purse_boom")}}}
    merged = config._merge(cfg, saved)
    assert merged["rules"]["market"]["purse_boom"] == 1.0


def test_a_boom_makes_the_purse_that_much_bigger():
    g, p = new_house()
    port, good = p["port"], "silk"
    normal = g.purse_size(port, good)
    boom(g, port, good, 4.0)
    assert g.purse_size(port, good) == pytest.approx(normal * 4.0, rel=0.01)
    other = "tea" if good != "tea" else "silk"
    assert g.purse_size(port, other) == pytest.approx(engine.Game.purse_size(g, port, other))


@pytest.mark.parametrize("share,want", [(0.0, 1.0), (0.5, 2.5), (1.0, 4.0)])
def test_the_share_setting(share, want):
    g, p = new_house(market__purse_boom=share)
    port, good = p["port"], "silk"
    base = g.purse_size(port, good)
    boom(g, port, good, 4.0)
    assert g.purse_size(port, good) == pytest.approx(base * want, rel=0.01)


def test_the_cap_holds():
    g, p = new_house(market__purse_boom_cap=3.0)
    port, good = p["port"], "silk"
    base = g.purse_size(port, good)
    boom(g, port, good, 6.0)
    assert g.purse_size(port, good) == pytest.approx(base * 3.0, rel=0.01)


def test_a_crash_does_not_shrink_the_purse():
    g, p = new_house()
    port, good = p["port"], "silk"
    base = g.purse_size(port, good)
    g.s["prices"][port][good] = GOODS[good]["base"] * engine.PORTS[port]["mods"].get(good, 1.0) * 0.3
    g._snapshot_purse_lift()
    assert g.purse_size(port, good) == pytest.approx(base)


def test_a_full_hold_sells_in_full_into_a_boom():
    """The point of it: a depth-sized lot into a x4 boom was cut to ~35% past the purse; now it is paid in full."""
    port_good = ("silk",)
    g, p = new_house(market__purse_boom=0.0)
    port, good = p["port"], port_good[0]
    qty = int(GOODS[good]["depth"] * 0.7)
    boom(g, port, good, 4.0)
    old_total, _ = g.quote(p, good, qty, "sell")
    g2, p2 = new_house()
    boom(g2, port, good, 4.0)
    new_total, _ = g2.quote(p2, good, qty, "sell")
    full = int(qty * g2.s["prices"][port][good] * 0.5)         # well under the unclipped value
    assert new_total > old_total * 1.5, (old_total, new_total)
    # and the new purse covers the whole sale
    assert g2.purse_left(port, good) > new_total


def test_selling_into_the_boom_does_not_shrink_the_purse():
    g, p = new_house()
    port, good = p["port"], "silk"
    boom(g, port, good, 4.0)
    size = g.purse_size(port, good)
    g._eat_boom(p, good, int(GOODS[good]["depth"]))             # a big sale eats most of the boom
    assert g.purse_size(port, good) == size


def test_buying_up_the_market_does_not_grow_the_purse():
    g, p = new_house()
    port, good = p["port"], "opium"
    size = g.purse_size(port, good)
    g.act(p["id"], {"type": "buy", "good": good, "qty": 800}, present=[p["id"]])
    assert g.purse_size(port, good) == size


def test_the_month_turn_refreshes_it():
    g, p = new_house()
    port, good = p["port"], "silk"
    boom(g, port, good, 4.0)
    g.s["windfalls"] = []
    g.s["prices"][port][good] = GOODS[good]["base"] * engine.PORTS[port]["mods"].get(good, 1.0)
    g._snapshot_purse_lift()
    assert g.purse_lift(port, good) == pytest.approx(1.0)


def test_screen_shows_the_bigger_purse():
    g, p = new_house()
    port, good = p["port"], "silk"
    before = g.purse_view(port)[good][1]
    boom(g, port, good, 4.0)
    after = g.purse_view(port)[good][1]
    assert after >= before * 3.9
