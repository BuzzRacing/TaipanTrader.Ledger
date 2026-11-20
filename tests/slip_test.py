"""Slipping out at night (owner's decisions, 19 Nov 2026; project doc "SeaTrader Slipping Out").

Run from the project folder:  python -m pytest tests/slip_test.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import config  # noqa: E402
import engine  # noqa: E402
import jail  # noqa: E402
from engine import PORTS  # noqa: E402
from jail_test import setup, new_game, sail_to, teardown_function  # noqa: E402,F401


def _ships(p, n):
    one = dict(p["ships"][0])
    p["ships"] = [dict(one, name="Ship {}".format(i)) for i in range(n)]


def test_odds_rise_with_the_fleet_and_fall_with_standing():
    setup()
    g, p = new_game()
    port = p["port"]
    p["rep"][port] = 50.0
    _ships(p, 1)
    assert abs(g.slip_odds(p) - 0.28) < 1e-9
    _ships(p, 10)
    assert abs(g.slip_odds(p) - 0.55) < 1e-9
    _ships(p, 20)
    assert abs(g.slip_odds(p) - 0.60) < 1e-9, "the fleet part stops at 60%"
    p["rep"][port] = 5.0
    assert abs(g.slip_odds(p) - 0.70) < 1e-9, "Hostile adds 10 (ceiling 70%)"
    _ships(p, 1)
    p["rep"][port] = 95.0
    assert abs(g.slip_odds(p) - 0.18) < 1e-9, "Favoured takes 10 away"


def test_the_fine_has_a_net_worth_floor():
    setup()
    g, p = new_game(cash=5000)
    port = p["port"]
    p["rep"][port] = 50.0
    p["bank"] = 10000000                       # a rich house slipping a small bill
    fine = g._slip_fine(p, port, 150)
    worth = g.worth(p)
    assert 0.005 * worth - 1 <= fine <= 0.0125 * worth + 1
    p["bank"] = 0
    assert g._slip_fine(p, port, 150) == 300, "a poor house pays twice the bill"


def test_caught_loses_band_rolled_standing_and_word_travels():
    setup(dues__slip_min=1.0, dues__slip_max=1.0, jail__slip_chance=0.0, jail__slip_repeat=0.0)
    g, p = new_game(cash=5000)
    here = p["port"]
    region = PORTS[here]["region"]
    near = [k for k in PORTS if k != here and PORTS[k]["region"] == region]
    for k in PORTS:
        p["rep"][k] = 50.0
    dest = next(k for k in PORTS if k != here)
    sail_to(g, p, dest, slip=True)
    lost = 50.0 - p["rep"][here]
    assert 7.0 - 1e-6 <= lost <= 15.0 + 1e-6, lost
    for k in near:
        if k != dest:
            assert p["rep"][k] < 50.0, "word travels in the region"
    assert p["slip_caught_at"][here], "the Mayor remembers"


def test_repeat_offenders_are_jailed_more_often():
    r = dict(jail.rules())
    assert abs(jail.slip_jail_odds(r, 0) - 0.20) < 1e-9
    assert abs(jail.slip_jail_odds(r, 2) - 0.50) < 1e-9
    assert abs(jail.slip_jail_odds(r, 9) - 0.65) < 1e-9


def test_old_catches_are_forgotten():
    setup()
    g, p = new_game()
    port = p["port"]
    g.s["turn"] = 40
    p["slip_caught_at"] = {port: [10, 20, 30, 39]}
    assert g._slip_prior(p, port) == 3, "catches within 24 months"


def test_the_set_sail_card_quotes_the_odds_and_fine():
    setup()
    g, p = new_game()
    q = g.slip_quote(p)
    assert 0.1 <= q["caught"] <= 0.7 and q["fine_min"] <= q["fine_max"]
