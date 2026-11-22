"""Repaying the home moneylender from another port (engine._remit, 23 Nov 2026).

An away moneylender's office (Admin > Ports > Moneylender) takes repayments only. The silver goes home by a
merchant who keeps a fee, may be robbed on the road or may help himself, and only what arrives lowers the debt.

Run from the project folder:  python tests/remit_test.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import engine  # noqa: E402
from engine import Game, GameError, R  # noqa: E402


def house(seed=5, debt=10000, cash=8000, office=True, **rules):
    """A house away from home, in a port with (or without) a moneylender's office."""
    game = Game(seed=seed)
    pid = game.pid_for_token(game.join("Tester", ""))
    p = game.s["players"][pid]
    home = engine.home_of(p)
    away = next(k for k in sorted(engine.PORTS) if k != home)
    p["port"] = away
    p["debt"], p["cash"] = float(debt), float(cash)
    engine.PORTS[away]["lender"] = bool(office)
    base = dict(remit_fee=0.05, remit_rob_chance=0.0, remit_skim_chance=0.0)
    base.update(rules)
    R["bank"].update(base)
    return game, pid, p, away


def keep(fn):
    """Run a test and put the settings back."""
    def run():
        bank = dict(R["bank"])
        was = {k: v.get("lender") for k, v in engine.PORTS.items()}
        try:
            fn()
        finally:
            R["bank"].clear()
            R["bank"].update(bank)
            for k, v in was.items():
                if v is None:
                    engine.PORTS[k].pop("lender", None)
                else:
                    engine.PORTS[k]["lender"] = v
    run.__name__ = fn.__name__
    return run


def repay(game, pid, amount):
    return game._act_loan(game.s["players"][pid], {"op": "repay", "amount": amount})


@keep
def test_no_office_means_no_repaying_from_afar():
    game, pid, p, _ = house(office=False)
    try:
        repay(game, pid, 1000)
    except GameError as e:
        assert "only in" in str(e), e
    else:
        raise AssertionError("repaid with no office")
    assert p["debt"] == 10000 and p["cash"] == 8000


@keep
def test_an_away_office_never_lends():
    game, pid, p, _ = house()
    try:
        game._act_loan(p, {"op": "borrow", "amount": 1000})
    except GameError as e:
        assert "only takes repayments" in str(e), e
    else:
        raise AssertionError("borrowed from an away office")
    assert p["debt"] == 10000 and p["cash"] == 8000


@keep
def test_the_fee_comes_off_and_only_what_arrives_lowers_the_debt():
    game, pid, p, away = house()
    msg = repay(game, pid, 4000)
    assert p["cash"] == 4000
    assert abs(p["debt"] - (10000 - 3800)) < 0.01, p["debt"]      # 5% fee: 200 kept, 3,800 arrived
    r = p["remits"][-1]
    assert (r["sent"], r["fee"], r["lost"], r["arrived"], r["how"]) == (4000, 200.0, 0.0, 3800.0, "safe"), r
    assert "3,800" in msg and "200" in msg, msg
    v = game.view(pid, [pid])["me"]
    assert v["lender_here"] and v["remit"]["tot"]["n"] == 1 and v["remit"]["tot"]["arrived"] == 3800, v["remit"]
    assert v["remit"]["last"][0]["port"] == away


@keep
def test_a_robbed_merchant_loses_a_big_share_and_the_report_says_so():
    game, pid, p, _ = house(remit_rob_chance=1.0, remit_rob_min=0.5, remit_rob_max=0.5)
    msg = repay(game, pid, 4000)
    r = p["remits"][-1]
    assert r["how"] == "robbed" and r["fee"] == 200.0 and r["lost"] == 1900.0 and r["arrived"] == 1900.0, r
    assert abs(p["debt"] - 8100) < 0.01, p["debt"]
    assert "robbed" in msg and "1,900" in msg, msg
    tot = p["remit_tot"]
    assert tot["robbed"] == 1 and tot["lost"] == 1900.0 and tot["sent"] == 4000, tot


@keep
def test_a_skimming_merchant_takes_a_little():
    game, pid, p, _ = house(remit_skim_chance=1.0, remit_skim_min=0.1, remit_skim_max=0.1)
    repay(game, pid, 4000)
    r = p["remits"][-1]
    assert r["how"] == "skimmed" and r["lost"] == 380.0 and r["arrived"] == 3420.0, r


@keep
def test_every_silver_piece_is_accounted_for():
    game, pid, p, _ = house(remit_rob_chance=0.3, remit_skim_chance=0.4)
    for _ in range(6):
        cash0, debt0 = p["cash"], p["debt"]
        repay(game, pid, 1000)
        r = p["remits"][-1]
        assert abs((cash0 - p["cash"]) - (r["fee"] + r["lost"] + r["arrived"])) < 0.02, r
        assert abs((debt0 - p["debt"]) - r["arrived"]) < 0.02, r
    books = p["books"]["cur"]
    assert abs(books.get("remit_fee", 0) + sum(x["fee"] for x in p["remits"])) < 0.05, books
    assert abs(books.get("remit_lost", 0) + sum(x["lost"] for x in p["remits"])) < 0.05, books


@keep
def test_a_big_amount_sends_only_what_clears_the_debt():
    game, pid, p, _ = house(debt=1000, cash=50000)
    repay(game, pid, 40000)
    r = p["remits"][-1]
    assert p["debt"] == 0 and r["sent"] == 1053 and r["arrived"] >= 1000, (r, p["debt"])     # 1000 / 0.95, rounded up
    assert p["cash"] == 50000 - 1053


@keep
def test_nothing_to_repay_is_refused():
    game, pid, p, _ = house(debt=0)
    try:
        repay(game, pid, 100)
    except GameError:
        pass
    else:
        raise AssertionError("sent silver with no debt")


@keep
def test_same_seed_same_road():
    out = []
    for _ in range(2):
        game, pid, p, _ = house(seed=11, remit_rob_chance=0.3, remit_skim_chance=0.4)
        for _ in range(5):
            repay(game, pid, 500)
        out.append([(r["how"], r["lost"]) for r in p["remits"]])
    assert out[0] == out[1], out


@keep
def test_default_odds_come_out_near_the_settings():
    game, pid, p, _ = house(debt=10 ** 9, cash=10 ** 9, remit_rob_chance=0.05, remit_skim_chance=0.15)
    n = 4000
    for _ in range(n):
        p["cash"] = 1000.0
        repay(game, pid, 1000)
    tot = p["remit_tot"]
    robbed, skimmed = tot["robbed"] / n, tot["skimmed"] / n
    assert 0.03 < robbed < 0.07, robbed
    assert 0.10 < skimmed < 0.20, skimmed       # 15% of the 95% that were not robbed


@keep
def test_home_port_still_repays_in_full_with_no_fee():
    game = Game(seed=3)
    pid = game.pid_for_token(game.join("Tester", ""))
    p = game.s["players"][pid]
    p["port"] = engine.home_of(p)
    p["debt"], p["cash"] = 1000.0, 5000.0
    game._act_loan(p, {"op": "repay", "amount": 1000})
    assert p["debt"] == 0 and p["cash"] == 4000 and not p.get("remits")


if __name__ == "__main__":
    n = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            n += 1
    print("remit_test: {} checks passed".format(n))
