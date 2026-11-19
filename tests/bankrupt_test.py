"""Debt cap and bankruptcy (19 Nov 2026).

The cap: loan interest stops adding once the debt reaches rules.bank.debt_cap_mult x the collectors'
line. Bankruptcy: a house worth less than nothing for rules.bank.bankrupt_months in a row loses
everything, its debt is cleared, and it starts again at home with a sound junk and a stake.

Run from the project folder:  python -m pytest tests/bankrupt_test.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import engine  # noqa: E402
from engine import Game, R  # noqa: E402


def _game(**bank):
    keep = dict(R["bank"])
    R["bank"].update(bank)
    game = Game(seed=11)
    p = game.s["players"][game.pid_for_token(game.join("Tester", "Test House"))]
    return game, p, keep


def _restore(keep):
    R["bank"].clear()
    R["bank"].update(keep)


def test_interest_stops_at_the_cap_and_never_forgives():
    game, p, keep = _game(debt_cap_mult=3.0, bankrupt_enabled=False)
    try:
        cap = game.debt_cap(p)
        p["debt"] = cap * 0.999
        game.resolve("host")
        assert abs(p["debt"] - game.debt_cap(p)) < 1e-6 or p["debt"] <= game.debt_cap(p) + 1e-6
        assert any("stopped adding interest" in line for line in p["log"])
        p["debt"] = cap * 5                    # already past the cap: held, not cut
        before = p["debt"]
        game.resolve("host")
        assert p["debt"] == before
    finally:
        _restore(keep)


def test_no_cap_when_set_to_zero():
    game, p, keep = _game(debt_cap_mult=0, bankrupt_enabled=False)
    try:
        p["debt"] = 1e9
        game.resolve("host")
        assert p["debt"] > 1e9
    finally:
        _restore(keep)


def test_bankruptcy_after_the_months_under_water():
    game, p, keep = _game(bankrupt_enabled=True, bankrupt_months=4, bankrupt_warn=2,
                          bankrupt_stake=2000, bankrupt_rep=10)
    try:
        home = engine.home_of(p)
        p["debt"] = 1e6
        p["cargo"] = {"tea": 10}
        p["wh"] = {"silk": 5}
        p["estate"], p["estate_paid"] = 1, 500000.0
        game.s.setdefault("shares", {})[home] = {p["id"]: 2}
        p["share_paid"] = {home: 300000.0}
        warned = []
        for month in range(1, 4):
            game.resolve("host")
            assert p.get("under_water") == month
            assert p["debt"] > 0
            if any("declare you bankrupt" in line for line in p["log"]):
                warned.append(month)
        assert warned == [1, 2, 3], warned          # the first month, then the last 2
        rep0 = p["rep"][home]
        game.resolve("host")
        assert p["debt"] == 0 and p["bank"] == 0
        assert p["cash"] == 2000
        assert p["cargo"] == {} and p["wh"] == {}
        assert len(p["ships"]) == 1 and p["ships"][0]["type"] == R["wreck"]["ship"]
        assert p["estate"] == 0 and p["share_paid"] == {}
        assert p["id"] not in game.s["shares"][home]
        assert p["port"] == home
        assert p["rep"][home] <= rep0 - 10 + 1e-6 or p["rep"][home] == 0
        assert p["bankruptcies"] == 1 and "under_water" not in p
        assert game.worth(p) > 0
        assert any("bankrupt" in n for n in game.s["news"])
    finally:
        _restore(keep)


def test_climbing_back_above_water_resets_the_count():
    game, p, keep = _game(bankrupt_enabled=True, bankrupt_months=3)
    try:
        p["debt"] = 1e6
        game.resolve("host")
        assert p["under_water"] == 1
        p["debt"] = 0
        game.resolve("host")
        assert "under_water" not in p
    finally:
        _restore(keep)


def test_off_means_never():
    game, p, keep = _game(bankrupt_enabled=False)
    try:
        for _ in range(30):
            p["debt"] = 1e6
            game.resolve("host")
        assert p.get("bankruptcies", 0) == 0 and game.bankruptcy(p) is None
    finally:
        _restore(keep)


def test_rank_is_kept():
    game, p, keep = _game(bankrupt_enabled=True, bankrupt_months=1)
    try:
        p["rank_id"] = "taipan"
        p["debt"] = 1e7
        game.resolve("host")
        assert p["bankruptcies"] == 1 and p["rank_id"] == "taipan"
    finally:
        _restore(keep)


def test_save_and_reload_mid_count():
    import json
    game, p, keep = _game(bankrupt_enabled=True, bankrupt_months=3)
    try:
        p["debt"] = 1e6
        game.resolve("host")
        g2 = Game(state=json.loads(json.dumps(game.s)), seed=5)
        p2 = g2.s["players"][p["id"]]
        assert p2["under_water"] == 1
        g2.resolve("host")
        g2.resolve("host")
        assert p2["bankruptcies"] == 1
    finally:
        _restore(keep)
