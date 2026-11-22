"""A house that is stuck for good (21 Nov 2026): no silver, nothing aboard or stored, no loan, no ship to
sell or swap. The books close after rules.bank.stuck_months month-ends, with no gaol. A broke house that
still has a way out is told, never closed.

Run from the project folder:  python -m pytest tests/stuck_test.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import config  # noqa: E402
import engine  # noqa: E402
from engine import Game, R, SHIPS  # noqa: E402


def _game(ship="junk", hull=38, laid=0, debt=716000, cargo=None):
    cfg = config.defaults()
    cfg["rules"]["weather"]["storm_chance"] = [0, 0, 0, 0]
    cfg["rules"]["pirates"]["chance"] = 0.0
    cfg["rules"]["customs"]["enabled"] = False
    cfg["rules"]["hide"]["bankrupt"] = False
    cfg["rules"]["bank"]["bankrupt_months"] = 600           # only the stuck rule may close the books here
    cfg["rules"]["fleet"]["upkeep_enabled"] = False
    cfg, errors = config.validate(cfg)
    assert not errors, errors
    engine.configure(cfg)
    g = Game(seed=11)
    p = g.s["players"][g.pid_for_token(g.join("Tester", "Test House"))]
    p["ships"] = [{"type": ship, "name": "Limper", "hull": hull, "guns": 0, "cannons": 0}]
    p["laid_up"] = [{"type": "countryship", "name": "Rest%d" % i, "hull": 200, "guns": 0, "cannons": 0, "laid": 1}
                    for i in range(laid)]
    p["cash"] = p["bank"] = 0.0
    p["cargo"] = dict(cargo or {})
    p["debt"] = float(debt)
    p["under_water"] = 0
    return g, p


def test_a_house_with_nothing_and_no_way_out_is_stuck_and_closed_after_two_months():
    g, p = _game()
    assert g.stuck_state(p) == "stuck"
    g.resolve("host")
    assert p.get("stuck") == 1 and p["debt"] > 0 and not p.get("bankruptcies")
    assert any("stuck" in line.lower() for line in p["log"]), p["log"]
    g.resolve("host")
    assert p.get("bankruptcies") == 1
    assert p["debt"] == 0 and p["cash"] == R["bank"]["bankrupt_stake"] and p["ships"][0]["type"] == R["wreck"]["ship"]
    assert not p.get("jail"), "a stuck house is not locked up as well"
    assert "stuck" not in p
    assert g.stuck_state(p) is None


def test_a_laid_up_ship_is_a_way_out_so_nothing_is_closed():
    g, p = _game(laid=2)
    assert g.stuck_state(p) == "exit"
    for _ in range(4):
        g.resolve("host")
    assert not p.get("bankruptcies") and len(p["laid_up"]) == 2
    assert any("laid-up" in line or "laid up" in line for line in p["log"]), p["log"]


def test_a_junk_swap_is_a_way_out():
    g, p = _game(ship="countryship", hull=38)
    assert g.trade_down_offer(p) is not None
    assert g.stuck_state(p) == "exit"


def test_cargo_silver_or_a_loan_means_not_stuck():
    g, p = _game(cargo={"rice": 5})
    assert g.stuck_state(p) is None
    g, p = _game()
    p["cash"] = 5000.0
    assert g.stuck_state(p) is None
    g, p = _game(debt=0)
    assert g.stuck_state(p) is None             # the lender would still lend


def test_switched_off_nothing_happens():
    g, p = _game()
    R["bank"]["stuck_enabled"] = False
    assert g.stuck_state(p) is None
    for _ in range(3):
        g.resolve("host")
    assert not p.get("bankruptcies")


def test_stuck_count_resets_when_the_house_gets_going():
    g, p = _game()
    g.resolve("host")
    assert p.get("stuck") == 1
    p["cash"] = 5000.0
    g.resolve("host")
    assert "stuck" not in p and not p.get("bankruptcies")


def test_the_parley_journal_says_what_was_open_to_the_captain():
    import battle_test as bt
    for cargo, cash, debt, want in (({"silk": 5000}, 0, 0, "did not pay"), ({"rice": 1}, 0, 10 ** 9, "could not pay"),
                                    ({"rice": 20}, 100000, 0, "refused to pay")):
        bt.setup()
        g = bt.new_game(names=("Ann",), cash=cash, cargo=cargo)
        g.s["players"]["p1"]["debt"] = debt
        events = []
        g.on_event = events.append
        bt.sail(g, present=["p1"])
        assert g.battle_view(g.s["players"]["p1"])["stage"] == "parley"
        g.act("p1", {"type": "sea", "choice": "run"}, present=["p1"])
        refused = [e for e in events if e["type"] == "parley_refused"]
        assert refused and want in refused[0]["msg"], (want, [e["msg"] for e in refused])
    # the round timer: standing orders, never a payment, and the journal says so
    bt.setup()
    g = bt.new_game(names=("Ann",), cash=0, cargo={"silk": 5000})
    events = []
    g.on_event = events.append
    bt.sail(g, present=["p1"])
    g.act("p1", {"type": "sea", "choice": "auto"}, present=["p1"])
    refused = [e for e in events if e["type"] == "parley_refused"]
    assert refused and refused[0]["timer"] is True and refused[0]["could_cargo"] is True


def test_bankruptcy_off_switches_the_stuck_rule_off_too():
    g, p = _game()
    R["bank"]["bankrupt_enabled"] = False
    assert g.stuck_state(p) is None
