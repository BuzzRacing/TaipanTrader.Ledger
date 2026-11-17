"""Checks the account book behind the Port screen's profit and loss.

Every amount of silver a house gains or loses must be in its books, except buying cargo,
ships and guns and selling ships (those change what it owns, not what it has made).

Run from the project folder:  python tests/books_test.py
"""
import json
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import config  # noqa: E402
import engine  # noqa: E402
from engine import Game  # noqa: E402
import sim_test  # noqa: E402

NOT_CASH = {"cost", "seized", "plundered", "overboard", "ships_lost", "wreck_cargo"}
WORST = [0.0]
CAPITAL = {"buy", "buy_ship", "buy_gun", "sell_ship"}


def money(p):
    return p["cash"] + p["bank"] - p["debt"]


def play(seed, years=2):
    g = Game(seed=seed)
    capital = {}

    def on_event(e):
        if e.get("type") in CAPITAL and e.get("do") == "act" and "cash" in e:
            capital[e["pid"]] = capital.get(e["pid"], 0) + e["cash"][1] - e["cash"][0]
    g.on_event = on_event
    bots = {}
    for name, bot in (("Ada", sim_test.trader_bot), ("Bao", sim_test.trader_bot), ("Cy", sim_test.random_bot)):
        bots[g.pid_for_token(g.join(name, ""))] = bot
    host = g.s["order"][0]
    g.act(host, {"type": "settings", "years": years}, present=g.s["order"])
    g.act(host, {"type": "start"}, present=g.s["order"])
    start = {pid: money(p) for pid, p in g.s["players"].items()}
    rng = random.Random(seed)
    months = 0
    while g.s["phase"] == "port":
        for pid, bot in bots.items():
            bot(g, pid, rng)
        assert g.maybe_advance(set(g.s["order"]))
        g.fight_out(set(g.s["order"]))   # captains at their screens fight their battles
        months += 1
        for pid, p in g.s["players"].items():
            bk = p["books"]
            last = bk["last"]
            assert last and last["date"] and last["to"] == p["port"], last
            # Mayor's dues are on the statement of the voyage that paid them.
            v = g.view(pid, g.s["order"])["me"]["books"]
            json.dumps(v)
            cash_lines = sum(v for k, v in bk["game"].items() if k not in NOT_CASH)
            want = money(p) - start[pid] - capital.get(pid, 0)
            # Each booked amount is rounded to the cent and the debt carries fractions: allow a little slack.
            WORST[0] = max(WORST[0], abs(cash_lines - want))
            assert abs(cash_lines - want) < 0.1 * (months + 1), (p["name"], months, cash_lines, want, bk["game"])
        # A save and load keeps the books.
        state = json.loads(json.dumps(g.s))
        g2 = Game(state=state, seed=seed)
        assert g2.s["players"][host]["books"]["game"] == g.s["players"][host]["books"]["game"]
    # The year's book starts again each January; the game's book never does.
    for p in g.s["players"].values():
        yr, gm = p["books"]["year"], p["books"]["game"]
        assert sum(abs(x) for x in yr.values()) <= sum(abs(x) for x in gm.values()) + 1
    return months


def old_save():
    """A save from before the books were kept still loads and gets an empty book."""
    g = Game(seed=5)
    g.join("Ann", "")
    g.admin("start", {})
    state = json.loads(json.dumps(g.s))
    for p in state["players"].values():
        p.pop("books", None)
    g2 = Game(state=state, seed=6)
    me = g2.view("p1", ["p1"])["me"]
    assert me["books"]["last"] is None and me["books"]["game"] == {}
    g2.act("p1", {"type": "buy", "good": "tea", "qty": 5}, present=["p1"])
    g2.act("p1", {"type": "sell", "good": "tea", "qty": 5}, present=["p1"])
    b = g2.s["players"]["p1"]["books"]["cur"]
    assert b["sales"] > 0 and b["cost"] < 0 and b["sales"] + b["cost"] < 0   # the dealers' margins


def arrival_tax_on_last():
    """The Port Authority's tax goes on the statement of the landing that brought the cargo in."""
    seen = 0
    for seed in range(40):
        g, p = __import__("customs_test").arrive(seed, "calcutta")
        if not p.get("customs") or p["customs"]["status"] != "declare":
            continue
        assert p["books"]["start"]["worth"] is None and p["books"]["last"]["open"]
        vals = {ln["good"]: ln["value"] for ln in p["customs"]["lines"]}
        g.act("p1", {"type": "customs_declare", "values": vals}, present=["p1"])
        res = p["customs"]["result"]
        g.act("p1", {"type": "customs_done"}, present=["p1"])
        last = p["books"]["last"]
        assert -last["lines"].get("pa_tax", 0) == res["tax"], (last, res)
        assert "pa_tax" not in p["books"]["cur"]
        assert last["worth"][1] == int(g.worth(p)) and not last["open"]
        assert p["books"]["start"]["worth"] == int(g.worth(p))
        seen += 1
    assert seen > 10, seen


if __name__ == "__main__":
    engine.configure(config.defaults())
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    old_save()
    arrival_tax_on_last()
    total = sum(play(seed) for seed in range(1, 13))
    print("OK: account book checks passed ({} months played, books within {:.2f} of the silver)".format(total, WORST[0]))
