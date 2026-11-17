"""Madam Wu's word when a house borrows or repays: the receipt, then advice that follows how close the
debt is to the collectors' line.

Run from the project folder:  python tests/lender_test.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import cast     # noqa: E402
import config   # noqa: E402
import engine   # noqa: E402
import strings  # noqa: E402
import voice    # noqa: E402
from engine import Game, R  # noqa: E402

TIERS = {"borrowed": ("easy", "careful", "danger"), "repaid": ("part", "still", "under", "clear")}


def tier(msg, op):
    """Which of Madam Wu's tiers a message came from (None: the plain receipt)."""
    key = voice.Matcher(engine.TEXT).key(msg)
    if key and key.startswith("m.{}.".format(op)) and key.count(".") == 3:
        return key.split(".")[2]
    return None


def house(seed, debt, cash=0.0):
    game = Game(seed=seed)
    p = game.s["players"][game.pid_for_token(game.join("Tester", ""))]
    p["port"] = engine.home_of(p)
    p["rep"][p["port"]] = 50.0
    p["debt"], p["cash"] = float(debt), float(cash)
    return game, p


def test_every_tier_has_three_lines_and_a_spoken_version():
    for op, tiers in TIERS.items():
        for t in tiers:
            for i in range(3):
                key = "m.{}.{}.{}".format(op, t, i)
                assert key in strings.EN, key
                assert cast.LINE_DEFAULTS[key] == "lender", key
                say = cast.SAY[key]
                assert "{amount}" not in say and "{suggest}" not in say and "{rate}" not in say, key
                if key in strings.FAMILY:
                    assert key in cast.SAY_FAMILY, key


def test_borrow_tiers_follow_the_line():
    game, p = house(21, 0)
    line = game.collectors_line(p)
    share = R["bank"]["wu_easy_share"]
    assert tier(game._act_loan(p, {"op": "borrow", "amount": 100}), "borrowed") == "easy"
    p["debt"] = (share + 0.05) * line        # still inside what she lends a house with no silver
    assert game.loan_limit(p) > p["debt"] + 100
    assert tier(game._act_loan(p, {"op": "borrow", "amount": 100}), "borrowed") == "careful"


def test_borrow_danger_when_the_clock_runs():
    game, p = house(22, 0, cash=10 ** 6)     # silver raises what she will lend, not the collectors' line
    p["debt"] = game.collectors_line(p)      # month-end interest takes it over
    msg = game._act_loan(p, {"op": "borrow", "amount": 100})
    assert tier(msg, "borrowed") == "danger", msg
    assert "{home}" not in msg


def test_repay_tiers():
    game, p = house(23, 0, cash=10 ** 6)
    line = game.collectors_line(p)
    p["debt"] = 0.2 * line
    assert tier(game._act_loan(p, {"op": "repay", "amount": 100}), "repaid") == "part"
    p["debt"] = 2 * line
    msg = game._act_loan(p, {"op": "repay", "amount": 100})
    assert tier(msg, "repaid") == "still" and "$" in msg.split("Repaid", 1)[1].split(".", 1)[1], msg
    c = game.collectors(p)
    assert tier(game._act_loan(p, {"op": "repay", "amount": c["to_clear"]}), "repaid") == "under"
    assert tier(game._act_loan(p, {"op": "repay", "amount": int(p["debt"]) + 1}), "repaid") == "clear"
    assert p["debt"] == 0


def test_lines_rotate_and_switch_off():
    game, p = house(24, 0)
    seen = {game._act_loan(p, {"op": "borrow", "amount": 10}) for _ in range(3)}
    assert len(seen) == 3
    R["bank"]["wu_advice"] = False
    try:
        msg = game._act_loan(p, {"op": "borrow", "amount": 10})
    finally:
        R["bank"]["wu_advice"] = True
    assert msg == "Borrowed $10 at {:g}% a month.".format(round(engine.loan_rate() * 100, 2)), msg


def test_she_reads_it_without_the_amounts():
    cfg = config.defaults()
    engine.configure(cfg)
    plan = voice.Planner()
    plan.configure(cfg, engine.TEXT)
    game, p = house(25, 0, cash=10 ** 6)
    p["debt"] = 2 * game.collectors_line(p)
    msg = game._act_loan(p, {"op": "repay", "amount": 100})
    key, fields = plan.matcher.match(msg)
    assert cast.speaker_for(cfg, key) == "lender"
    spoken = plan.spoken(key, fields, msg)
    assert "$" not in spoken and "Repaid" not in spoken, spoken
    assert cfg["characters"]["lender"]["voice_id"] == "Xinyi"


def test_family_wording():
    cfg = config.defaults()
    cfg["content"]["rating"] = "family"
    engine.configure(cfg)
    try:
        game, p = house(26, 0)
        msg = game._act_loan(p, {"op": "borrow", "amount": 10})
        assert "darling" not in msg and tier(msg, "borrowed") == "easy", msg
    finally:
        engine.configure(config.defaults())


if __name__ == "__main__":
    engine.configure(config.defaults())
    n = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
            n += 1
    print("OK: moneylender checks passed ({} tests)".format(n))
