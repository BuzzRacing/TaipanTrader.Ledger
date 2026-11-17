"""Collectors: a grace period after debt passes the line, then a call every few months.

Run from the project folder:  python tests/collectors_test.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import engine  # noqa: E402
from engine import Game, R  # noqa: E402


def play(months, grace, every, debt=10 ** 6, penalty=1.0):
    """Months (1 = first month over the line) in which the collectors called."""
    bank = R["bank"]
    keep = dict(bank)
    bank.update(debt_grace_months=grace, debt_call_every=every, debt_rep_penalty=penalty)
    try:
        game = Game(seed=7)
        p = game.s["players"][game.pid_for_token(game.join("Tester", ""))]
        calls = []
        for month in range(1, months + 1):
            p["debt"] = float(debt)
            p["rep"][engine.home_of(p)] = 50.0
            game.resolve("host")
            if p["rep"][engine.home_of(p)] < 50.0:
                calls.append(month)
        return calls, p
    finally:
        bank.clear()
        bank.update(keep)


def test_grace_then_every_third_month():
    calls, _ = play(12, grace=3, every=3)
    assert calls == [4, 7, 10], calls


def test_no_grace_every_month_is_the_old_rule():
    calls, _ = play(5, grace=0, every=1)
    assert calls == [1, 2, 3, 4, 5], calls


def test_small_debt_never_calls_and_resets_the_count():
    calls, p = play(6, grace=0, every=1, debt=100)
    assert calls == [] and p["debt_over"] == 0


def test_old_save_without_the_counter_gets_a_fresh_grace():
    bank = R["bank"]
    keep = dict(bank)
    bank.update(debt_grace_months=3, debt_call_every=3)
    try:
        game = Game(seed=8)
        p = game.s["players"][game.pid_for_token(game.join("Tester", ""))]
        p.pop("debt_over", None)
        p["debt"] = 1e6
        game.resolve("host")
        assert p["debt_over"] == 1
        assert not any("asking about you" in line for line in p["log"])
        assert any("has sent word" in line for line in p["log"])  # warned, not penalised
    finally:
        bank.clear()
        bank.update(keep)


def test_first_month_over_the_line_is_a_warning_with_no_penalty():
    bank = R["bank"]
    keep = dict(bank)
    bank.update(debt_grace_months=3, debt_call_every=3, debt_rep_penalty=1.0)
    try:
        game = Game(seed=9)
        p = game.s["players"][game.pid_for_token(game.join("Tester", ""))]
        warned = []
        for month in range(1, 8):
            p["debt"], p["rep"][engine.home_of(p)] = 1e6, 50.0
            game.resolve("host")
            if any("has sent word" in line for line in p["log"]):
                warned.append(month)
                assert p["rep"][engine.home_of(p)] == 50.0
                assert any("within 3 months" in line for line in p["log"])
        assert warned == [1], warned
    finally:
        bank.clear()
        bank.update(keep)


def test_no_warning_when_there_is_no_grace():
    calls, p = play(2, grace=0, every=1)
    assert calls == [1, 2] and not any("has sent word" in line for line in p["log"])


def test_the_debt_clock_matches_what_happens():
    """The screen's "collectors in N months" is the month they really call."""
    bank = R["bank"]
    keep = dict(bank)
    bank.update(debt_grace_months=3, debt_call_every=3, debt_rep_penalty=1.0)
    try:
        game = Game(seed=11)
        p = game.s["players"][game.pid_for_token(game.join("Tester", ""))]
        p["debt"] = 0.0
        assert game.collectors(p) is None                      # no debt, no clock
        p["debt"] = 100.0
        c = game.collectors(p)
        assert c["calls_in"] is None and not c["over"] and c["line"] > 100
        p["debt"] = 1e6
        for month in range(1, 12):
            p["debt"], p["rep"][engine.home_of(p)] = 1e6, 50.0
            said = game.collectors(p)["calls_in"]
            game.resolve("host")
            called = p["rep"][engine.home_of(p)] < 50.0
            assert (said == 1) == called, (month, said, called)
            assert 1 <= said <= 4
        assert game.view(p["id"])["me"]["collectors"]["calls_in"] == game.collectors(p)["calls_in"]
    finally:
        bank.clear()
        bank.update(keep)


def test_the_line_ignores_silver_so_repaying_always_helps():
    game = Game(seed=12)
    p = game.s["players"][game.pid_for_token(game.join("Tester", ""))]
    home = engine.home_of(p)
    p["debt"], p["rep"][home] = 60000.0, 50.0
    p["cash"], line = 0.0, game.collectors_line(p)
    p["cash"] = 50000.0
    assert game.collectors_line(p) == line            # silver in hand does not move the line
    p["bank"] = 50000.0
    assert game.collectors_line(p) == line            # nor does the bank
    assert game.loan_limit(p) > line / R["bank"]["debt_warn_mult"]   # the loan limit still counts them
    c = game.collectors(p)
    assert c["calls_in"] and 0 < c["to_clear"] <= p["debt"]
    p["debt"] -= c["to_clear"]                          # repay what the screen says...
    p["cash"] -= c["to_clear"]
    assert game.collectors(p)["calls_in"] is None       # ...and the clock stops
    game.resolve("host")
    assert p["rep"][home] == 50.0 and p.get("debt_over", 0) == 0
    assert not any("has sent word" in line for line in p["log"])


def test_defaults_are_the_softer_rule():
    d = engine._config.DEFAULTS["rules"]["bank"]
    assert d["debt_grace_months"] == 3 and d["debt_call_every"] == 3
    assert d["debt_rep_penalty"] == 1 and d["debt_warn_mult"] == 2.5


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
