"""Checks the player statistics (stats.py) against recorded bot games.

Plays a few recorded games, one of them left running, then checks that:
  - the books balance: realised profit = sales - purchases + cost of cargo still held
  - fair play holds while a game runs (no rival detail, only prices that house saw)
  - everything unlocks once a game is over
  - the career view adds the games up and finds the records
  - the /api/stats answer is valid JSON

Run from the project folder:  python tests/stats_test.py
Keep the recorded games for a look in the browser:  python tests/stats_test.py --keep D:/somewhere
"""
import copy
import json
import os
import random
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine  # noqa: E402
import journal  # noqa: E402
import stats  # noqa: E402
from engine import Game  # noqa: E402
from sim_test import check, random_bot, trader_bot  # noqa: E402


def use_folder(tmp):
    journal.DIR = tmp
    journal.GAMES = os.path.join(tmp, "games")
    journal.SERVER = os.path.join(tmp, "server")
    journal._index_cache.clear()
    stats._cache.clear()
    stats._results.clear()


def play(seed, years=2, stop_at=None, names=("Anthony", "Ada", "Bao", "Cy")):
    engine.configure()
    cfg = copy.deepcopy(engine.CFG)
    game = Game(seed=seed)
    bot_rng = random.Random(seed)
    gid = journal.open_game(game, "new game", cfg, None, kind="game_start")
    bots = {}
    kinds = (trader_bot, trader_bot, random_bot, trader_bot)
    for name, bot in zip(names, kinds):
        bots[game.pid_for_token(game.join(name, "", via={"address": "test"}))] = bot
    order = game.s["order"]
    game.act(order[0], {"type": "settings", "years": years}, present=order)
    game.act(order[0], {"type": "start"}, present=order)
    while game.s["phase"] == "port":
        if stop_at is not None and game.s["turn"] >= stop_at:
            return gid, game
        for pid, bot in bots.items():
            bot(game, pid, bot_rng)
        assert game.maybe_advance(set(order))
        game.fight_out(set(order))   # captains at their screens fight their battles
        check(game)
    journal.close_game("test finished")
    return gid, game


def books_balance(gid, pid):
    game = stats._read(gid)
    ps = stats._players(game["events"], game["colors"])
    houses, _w, _p = stats._walk(game["events"], ps)
    h = houses[pid]
    sold = sum(c["sold_rev"] for c in h.cargo.values())
    bought = sum(c["bought_cost"] for c in h.cargo.values())
    held = sum(cost for _u, cost in h.hold.values())
    realised = sum(c["profit"] for c in h.cargo.values())
    assert abs(realised - (sold - bought + held)) < 0.5, (realised, sold, bought, held)
    assert all(u >= 0 for u, _c in h.hold.values())
    return realised


def main():
    keep = sys.argv[sys.argv.index("--keep") + 1] if "--keep" in sys.argv else None
    tmp = keep or tempfile.mkdtemp(prefix="seatrader-stats-")
    real = (journal.DIR, journal.GAMES, journal.SERVER)
    try:
        use_folder(tmp)
        finished = [play(seed, years=y)[0] for seed, y in ((21, 3), (22, 2), (23, 5))]
        running, game = play(24, years=3, stop_at=14)

        # Books balance for every house in every game.
        for gid in finished + [running]:
            g = stats._read(gid)
            for p in stats._players(g["events"], g["colors"]):
                books_balance(gid, p["id"])

        # A finished game unlocks everything.
        pid = stats.find_pid(finished[0], "anthony")
        v = stats.voyage(finished[0], pid, running=False)
        assert v["game"]["ended"] and v["game"]["reveal"]
        assert v["me"]["markets"]["full"]
        assert all("cargo" in r for r in v["rivals"]), "rivals should be unlocked after the game"
        assert len(v["me"]["markets"]["latest"]) == len(engine.PORTS)
        me = v["me"]
        assert me["months"] and me["months"][-1]["worth"] == me["kpis"]["worth"]
        assert me["kpis"]["voyages"] == len(me["legs"]) > 0
        assert 1 <= v["place"] <= 4
        total_heat = sum(sum(r.values()) for r in me["heat_port_good"].values())
        sold_profit = sum(t.get("profit", 0) for t in me["trades"] if t["side"] == "sell")
        assert abs(total_heat - sold_profit) <= len(me["trades"]), (total_heat, sold_profit)

        # The running game keeps to fair play.
        rp = stats.find_pid(running, "Anthony")
        v = stats.voyage(running, rp, running=True)
        assert not v["game"]["ended"] and not v["game"]["reveal"] and v["game"]["running"]
        assert all(r.get("public") for r in v["rivals"]), "rival detail leaked during play"
        assert all(set(r) <= {"id", "name", "firm", "color", "public", "kpis", "months"} for r in v["rivals"])
        visited = {m["port"] for m in v["me"]["months"]} | {t["port"] for t in v["me"]["trades"]}
        assert set(v["me"]["markets"]["latest"]) <= visited, "prices from ports never visited leaked"
        assert not v["me"]["markets"]["full"]

        # Career adds up and leaves out a running seat that is not yours.
        c = stats.career("Anthony", running_gid=running, running_pid=rp)
        assert c["totals"]["games"] == 4 and c["totals"]["finished"] == 3, c["totals"]
        assert c["totals"]["realised"] == sum(g["realised"] for g in c["games"])
        assert "best_finish" in c["records"] and "peak_worth" in c["records"]
        c2 = stats.career("Anthony", running_gid=running, running_pid=None)
        assert c2["totals"]["games"] == 3, "someone else could see the running game"
        assert "Ada" in stats.players_seen()
        json.dumps(c)
        json.dumps(v)
        print("OK: {} games; Anthony career {} games, realised {}, best finish {}, wins {}".format(
            len(finished) + 1, c["totals"]["games"], c["totals"]["realised"], c["totals"]["best"], c["totals"]["wins"]))
    finally:
        journal.DIR, journal.GAMES, journal.SERVER = real
        stats._cache.clear()
        if not keep:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
