"""Under the Counter (counter.py): the port's tax lady sells a tip, priced as a share of its worth that
rises with rank; paid once a visit, then free to read again until the house sails.

Run from the project folder:  python tests/counter_test.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import cast  # noqa: E402
import config  # noqa: E402
import counter  # noqa: E402
import engine  # noqa: E402
import strings  # noqa: E402
import voice  # noqa: E402
from engine import Game, GameError, GOODS, PORTS  # noqa: E402


def setup():
    base = config.defaults()
    base["rules"]["customs"]["spot_home"] = 0.0
    base["rules"]["start"]["where"] = "home"
    base["rules"]["counter"]["enabled"] = True       # the tab is hidden by default until the next phase
    engine.configure(base)
    return base


def started(seed=3, cash=None):
    game = Game(seed=seed)
    pid = game.pid_for_token(game.join("Ann", ""))
    game.act(pid, {"type": "start"})
    p = game.s["players"][pid]
    p["customs"] = None
    if cash is not None:
        p["cash"] = cash
    return game, pid, p


def rig_run(game, p, good="silk", where=None):
    """Make one run plainly the best: cheap here, dear in one other port."""
    here = p["port"]
    where = where or next(k for k in PORTS if k != here)
    for port in PORTS:
        for g in list(game.s["prices"][port]):            # only what the port trades has a price
            base = GOODS[g]["base"] * PORTS[port]["mods"].get(g, 1.0)
            game.s["prices"][port][g] = base
    base_here = GOODS[good]["base"] * PORTS[here]["mods"].get(good, 1.0)
    base_there = GOODS[good]["base"] * PORTS[where]["mods"].get(good, 1.0)
    game.s["prices"][here][good] = base_here * engine.R["market"]["floor"]
    game.s["prices"][where][good] = base_there * engine.R["market"]["ceiling"]
    game.s["crackdown"] = {}
    return where


def test_hidden_until_switched_on():
    """Out of the box the tab is off: no counter in the view (so no rail tab) and no sale."""
    engine.configure(config.defaults())
    game, pid, p = started(cash=20000)
    assert game.view(pid)["me"].get("counter") is None
    try:
        game.act(pid, {"type": "counter", "tip": "run"})
        assert False, "should refuse"
    except GameError:
        pass


def test_offer_shows_worth_and_price_not_the_tip():
    setup()
    game, pid, p = started(cash=20000)
    where = rig_run(game, p)
    v = game.view(pid)["me"]["counter"]
    run = v["offers"]["run"]
    assert run["worth"] > 0 and run["fee"] > 0, run
    assert "good" not in run and "port" not in run          # the tip itself stays under the counter
    assert v["bought"] == {}
    assert v["hello"]
    t = counter.best_run(game, p)
    assert t["good"] == "silk" and t["port"] == where, t


def test_fee_rises_with_rank():
    setup()
    game, pid, p = started(cash=20000)
    low = counter.fee_share(game, p)
    assert counter.DEFAULTS["fee_min"] <= low < counter.DEFAULTS["fee_max"], low
    p["cash"], p["debt"] = 0, 10 ** 7                       # a debtor: the bottom of the ladder
    assert abs(counter.fee_share(game, p) - counter.DEFAULTS["fee_min"]) < 1e-9
    p["debt"] = 0
    p["bank"] = 10 ** 12                                    # the top of the ladder
    high = counter.fee_share(game, p)
    assert abs(high - counter.DEFAULTS["fee_max"]) < 1e-9, high
    assert counter.fee_for(game, p, 100000) == 30000


def test_paying_reveals_and_charges_once():
    setup()
    game, pid, p = started(cash=20000)
    where = rig_run(game, p)
    fee = game.view(pid)["me"]["counter"]["offers"]["run"]["fee"]
    cash0 = p["cash"]
    msg = game.act(pid, {"type": "counter", "tip": "run"})
    assert PORTS[where]["name"] in msg and GOODS["silk"]["name"] in msg, msg
    assert p["cash"] == cash0 - fee
    again = game.act(pid, {"type": "counter", "tip": "run"})
    assert again == msg and p["cash"] == cash0 - fee          # read again for nothing
    v = game.view(pid)["me"]["counter"]
    assert v["offers"]["run"] == {"bought": True}
    rv = v["bought"]["run"]
    assert rv["good"] == "silk" and rv["port"] == where and rv["fee"] == fee and rv["qty"] > 0
    assert game._books(p)["cur"].get("tips") == -fee


def test_tip_worth_matches_the_market():
    """Buying what she says costs what she said."""
    setup()
    game, pid, p = started(cash=20000)
    rig_run(game, p)
    game.act(pid, {"type": "counter", "tip": "run"})
    rv = p["counter"]["bought"]["run"]
    cash = p["cash"]
    game.act(pid, {"type": "buy", "good": rv["good"], "qty": rv["qty"]})
    assert cash - p["cash"] == rv["cost"], (cash - p["cash"], rv["cost"])


def test_too_poor_to_pay():
    setup()
    game, pid, p = started(cash=20000)
    rig_run(game, p)
    fee = game.view(pid)["me"]["counter"]["offers"]["run"]["fee"]
    # Fill the hold first, then leave less silver than her price: the run tip is gone, the hold one stays.
    game.act(pid, {"type": "buy", "good": "silk", "qty": counter._max_buy(game, p, "silk", game.capacity(p), p["cash"])})
    hold = game.view(pid)["me"]["counter"]["offers"]["hold"]
    assert hold.get("fee", 0) > 0, hold
    p["cash"] = 0         # her price follows the house's rank, so leave nothing at all to pay it with
    try:
        game.act(pid, {"type": "counter", "tip": "hold"})
        assert False, "should refuse"
    except GameError as e:
        assert "price" in str(e).lower()
    assert fee > 0


def test_nothing_pays_is_free():
    setup()
    game, pid, p = started(cash=20000)
    for port in PORTS:
        for g in GOODS:
            game.s["prices"][port][g] = GOODS[g]["base"] * PORTS[port]["mods"].get(g, 1.0)
    here = p["port"]
    for g in GOODS:                                         # everything dear here: nothing pays to buy
        game.s["prices"][here][g] *= 3
    off = game.view(pid)["me"]["counter"]["offers"]["run"]
    assert off.get("none"), off
    cash = p["cash"]
    msg = game.act(pid, {"type": "counter", "tip": "run"})
    assert p["cash"] == cash and msg


def test_hold_tip_beats_selling_here():
    setup()
    game, pid, p = started(cash=5000)
    here = p["port"]
    where = rig_run(game, p, good="tea")
    p["cargo"]["tea"] = 40
    t = counter.best_hold(game, p)
    assert t["port"] == where and t["net"] > t["here"], t


def test_new_visit_clears_the_counter():
    setup()
    game, pid, p = started(cash=20000)
    rig_run(game, p)
    game.act(pid, {"type": "counter", "tip": "run"})
    game.s["turn"] += 1
    v = game.view(pid)["me"]["counter"]
    assert v["bought"] == {} and "bought" not in v["offers"]["run"]


def test_her_lines_go_to_the_ports_officer():
    cfg = setup()
    text = strings.resolve(cfg)
    for k in [k for k in text if k.startswith("l.counter_")] + ["e.counter_cost"]:
        assert k in cast.OFFICER_KEYS, k
        assert cast.speaker_for(cfg, k) == "taxlady", k
    plan = voice.Planner()
    plan.configure(cfg, text)
    shown = text["l.counter_run.0"].replace("{goods}", "Silk").replace("{where}", "Manila")
    assert plan.matcher.key(shown) == "l.counter_run.0"
    officer = (cfg["ports"].get("manila") or {}).get("officer")
    if officer and (cfg["characters"].get(officer) or {}).get("voice_id"):
        assert plan._who("l.counter_run.0", "manila") == officer
    cost = text["e.counter_cost"].replace("{price}", "$500").replace("{cash}", "$20")
    k, f = plan.matcher.match(cost)
    assert k == "e.counter_cost" and "$" not in plan.spoken(k, f, cost)


def test_family_has_clean_lines():
    for k in strings.EN:
        if k.startswith("l.counter_"):
            fam = strings.FAMILY.get(k, strings.EN[k])
            assert "darling" not in fam and "bed" not in fam, k


if __name__ == "__main__":
    n = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            n += 1
            print("ok", name)
    print("{} counter tests passed".format(n))
