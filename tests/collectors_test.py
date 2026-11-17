"""Collectors: a grace period after debt passes the line, then a call every few months.

Run from the project folder:  python tests/collectors_test.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import engine  # noqa: E402
from engine import Game, HOME, R  # noqa: E402


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
            p["rep"][HOME] = 50.0
            game.resolve("host")
            if p["rep"][HOME] < 50.0:
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
            p["debt"], p["rep"][HOME] = 1e6, 50.0
            game.resolve("host")
            if any("has sent word" in line for line in p["log"]):
                warned.append(month)
                assert p["rep"][HOME] == 50.0
                assert any("within 3 months" in line for line in p["log"])
        assert warned == [1], warned
    finally:
        bank.clear()
        bank.update(keep)


def test_no_warning_when_there_is_no_grace():
    calls, p = play(2, grace=0, every=1)
    assert calls == [1, 2] and not any("has sent word" in line for line in p["log"])


def test_defaults_are_the_softer_rule():
    d = engine._config.DEFAULTS["rules"]["bank"]
    assert d["debt_grace_months"] == 3 and d["debt_call_every"] == 3
    assert d["debt_rep_penalty"] == 1 and d["debt_warn_mult"] == 2.5


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
