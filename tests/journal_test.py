"""Checks the records: the game journal, the server log and the replay check.

Plays bot games with everything being written down (including a server
restart in the middle of a month, an admin correction and a settings change),
then replays every month from the journal and checks each one comes out
exactly as recorded.

Run from the project folder:  python tests/journal_test.py
"""
import copy
import json
import os
import random
import shutil
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine  # noqa: E402
import journal  # noqa: E402
import replay  # noqa: E402
from engine import Game  # noqa: E402
from sim_test import check, random_bot, trader_bot  # noqa: E402


def use_folder(tmp):
    journal.DIR = tmp
    journal.GAMES = os.path.join(tmp, "games")
    journal.SERVER = os.path.join(tmp, "server")
    journal._index_cache.clear()


def play(seed, years=2):
    """One recorded game. Returns its id."""
    engine.configure()
    cfg = copy.deepcopy(engine.CFG)
    game = Game(seed=seed)
    bot_rng = random.Random(seed)      # the bots' own dice; the game's dice are only for the rules
    gid = journal.open_game(game, "new game", cfg, None, kind="game_start")
    bots = {}
    for name, bot in (("Ada", trader_bot), ("Bao", trader_bot), ("Cy", random_bot), ("Dee", random_bot)):
        bots[game.pid_for_token(game.join(name, "", via={"address": "test"}))] = bot
    order = game.s["order"]
    host = order[0]
    game.act(host, {"type": "settings", "years": years, "token": "SECRET-SEAT-TOKEN"}, present=order)
    game.act(host, {"type": "start"}, present=order)
    while game.s["phase"] == "port":
        turn = game.s["turn"]
        for i, (pid, bot) in enumerate(bots.items()):
            bot(game, pid, bot_rng)
            if turn == 3 and i == 1:
                # The server is stopped and started again in the middle of a month.
                journal.note("system", "server_stop", "The server stopped; the game was saved")
                game = Game(state=json.loads(json.dumps(game.s)))
                journal.open_game(game, "resumed after a server restart", cfg, None)
            if turn == 5 and i == 0:
                game.admin("adjust", {"op": "adjust", "pid": order[1], "cash": "50000"})
                game.admin("price", {"op": "price", "port": "manila", "good": "tea", "value": "400"})
            if turn == 7 and i == 2:
                old, cfg = cfg, copy.deepcopy(cfg)
                cfg["rules"]["pirates"]["chance"] = 0.6
                cfg["rules"]["bank"]["loan_rate"] = 0.09
                engine.configure(cfg)
                changes = journal.settings_changed(old, cfg, None)
                assert [c[0] for c in changes] == ["rules.bank.loan_rate", "rules.pirates.chance"], changes
                game.reconcile()
        assert game.maybe_advance(set(order)), "turn did not advance"
        game.fight_out(set(order))   # captains at their screens fight their battles
        check(game)
    journal.close_game("test finished")
    return gid


def main():
    tmp = tempfile.mkdtemp(prefix="seatrader-journal-")
    real = (journal.DIR, journal.GAMES, journal.SERVER)
    try:
        use_folder(tmp)
        gids = [play(seed) for seed in (11, 12, 13)]

        # Every month replays exactly, through the restart, the admin changes and the settings change.
        for gid in gids:
            res = replay.replay(gid)
            bad = [s for s in res["segments"] if s["result"] == "different"]
            assert res["ok"] and res["checked"] >= 24 and not bad, (gid, bad[:2])
        one = replay.replay(gids[0], turn=7)
        assert one["ok"] and one["checked"] == 1, one

        # A change to the rules shows up as a difference.
        real_rate = engine.loan_rate
        engine.loan_rate = lambda: real_rate() * 2
        try:
            changed = replay.replay(gids[0], turn=2)
        finally:
            engine.loan_rate = real_rate
        assert not changed["ok"] and any("debt" in d for d in changed["segments"][0]["diffs"]), changed

        # What is written down.
        gid = gids[0]
        raw = open(journal.events_path(gid), encoding="utf-8").read()
        assert "SECRET-SEAT-TOKEN" not in raw and '"token"' not in raw, "a seat token reached the journal"
        lines = [json.loads(x) for x in raw.splitlines()]
        assert [e["n"] for e in lines] == list(range(1, len(lines) + 1)), "event numbers must run 1, 2, 3..."
        cats = {e["cat"] for e in lines}
        for want in ("players", "trade", "finance", "fleet", "orders", "host", "turn", "weather", "voyage", "dice",
                     "battle", "market", "snapshot", "admin", "settings", "rejected", "system"):
            assert want in cats, "nothing recorded under " + want
        dice = [e for e in lines if e["cat"] == "dice"]
        assert all(0 <= e["roll"] <= 1 and e["hit"] == (e["roll"] < e["odds"]) for e in dice)
        trade = next(e for e in lines if e["type"] == "buy")
        assert trade["qty"] > 0 and len(trade["price"]) == 2 and "cash" in trade and trade["do"] == "act"
        snaps = [e for e in lines if e["type"] == "turn_begin"]
        assert len(snaps) == 24 and all(len(e["firms"]) == 4 and e["state"]["seed"] == e["seed"] for e in snaps)

        # Reading it back.
        idx = journal.index(gid)
        assert idx["total"] == len(lines) and len(idx["turns"]) == 25
        month = journal.events(gid, turn=5)["events"]
        assert month and all(e["turn"] == 5 and "state" not in e for e in month)
        assert all(e["cat"] == "admin" for e in journal.events(gid, cats=["admin"])["events"])
        assert all(e["pid"] == "p1" for e in journal.events(gid, pid="p1")["events"])
        assert len(journal.events(gid, tail=True, limit=7)["events"]) == 7
        assert journal.events(gid, after=len(lines) - 3)["events"][0]["n"] == len(lines) - 2
        text = journal.report_text(gid)
        assert "=== Month 5 ===" in text and "Ada" in text
        meta = next(m for m in journal.games() if m["id"] == gid)
        assert meta["phase"] == "ended" and meta["standings"] and meta["events"] == len(lines)

        # Keeping and pruning.
        journal.configure({"journal": {"keep_games": 2, "server_days": 30}})
        journal.set_keep(gids[0], True)
        time.sleep(0.01)
        journal.prune()
        left = {m["id"] for m in journal.games()}
        assert gids[0] in left and len(left) == 2, left
        os.makedirs(journal.SERVER, exist_ok=True)
        old_day = time.strftime("%Y-%m-%d", time.localtime(time.time() - 40 * 86400))
        with open(os.path.join(journal.SERVER, "server-{}.log".format(old_day)), "w") as f:
            f.write("{}\n")
        journal.log("ERROR", "crash", "boom", traceback="Traceback...", password="hunter2")
        journal.prune()
        days = [d["day"] for d in journal.server_days()]
        assert old_day not in days and time.strftime("%Y-%m-%d") in days, days
        today = journal.server_log(level="ERROR")["lines"]
        assert today and today[-1]["msg"] == "boom" and today[-1]["password"] == "(hidden)"
        assert not journal.delete("not-a-game") and journal.delete(gids[0])
        print("OK: 3 recorded games, {} events in the first, every month replayed exactly".format(len(lines)))
    finally:
        journal.close_game("test over")
        journal.DIR, journal.GAMES, journal.SERVER = real
        journal.configure(None)
        engine.configure()
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
