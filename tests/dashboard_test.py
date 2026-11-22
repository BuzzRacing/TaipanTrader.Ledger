"""Checks the Dashboard's feed (dashboard_feed.py) while real games are played and recorded.

  - a game with rivals: the feed is "public" and carries none of the private blocks (prices, deals, lane profit)
    and no silver, bank, debt or cargo anywhere in it;
  - a solo game: the feed is "open", has the Markets and deals blocks and a ghost (a par pace on a first game,
    the best finished game once one is on the books);
  - every feed can be saved as JSON.

Run from the project folder:  python tests/dashboard_test.py
"""
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import config  # noqa: E402
import dashboard_feed  # noqa: E402
import engine  # noqa: E402
import journal  # noqa: E402
import sim_test  # noqa: E402  (the bots)
from engine import Game  # noqa: E402

PRIVATE_KEYS = {"cash", "bank", "debt", "cargo", "prices", "base", "deals", "lane_profit", "booms", "ports", "msg"}


def walk_keys(x, found):
    if isinstance(x, dict):
        for k, v in x.items():
            found.add(k)
            walk_keys(v, found)
    elif isinstance(x, list):
        for v in x:
            walk_keys(v, found)


def play(names, years, seed, months=None):
    """Plays a recorded game and yields the game after every month."""
    game = Game(seed=seed)
    bots = {}
    for name in names:
        bots[game.pid_for_token(game.join(name, ""))] = sim_test.trader_bot
    host = game.s["order"][0]
    game.act(host, {"type": "settings", "years": years}, present=game.s["order"])
    game.act(host, {"type": "start"}, present=game.s["order"])
    journal.open_game(game, "dashboard test", engine.CFG, config.load_lang(engine.CFG["language"]["active"]))
    rng = game.rng
    done = 0
    while game.s["phase"] == "port" and (months is None or done < months):
        for pid, bot in bots.items():
            p = game.s["players"][pid]
            if sim_test.jail.pending(p):
                sim_test.try_act(game, pid, {"type": "plea", "months": 0})
            if sim_test.jail.jailed(p):
                if not p["ready"]:
                    sim_test.try_act(game, pid, {"type": "jail_serve"})
                continue
            if p.get("jail_freed"):
                sim_test.try_act(game, pid, {"type": "jail_free"})
            bot(game, pid, rng)
        game.maybe_advance(set(game.s["order"]))
        game.fight_out(set(game.s["order"]))
        done += 1
        yield game
    return


def main():
    tmp = tempfile.mkdtemp(prefix="dash_test_")
    journal.DIR = os.path.join(tmp, "journal")
    os.makedirs(journal.DIR, exist_ok=True)
    try:
        # ---- rivals at the table: public
        feeds = 0
        for game in play(["Ada", "Bao"], 5, seed=3, months=7):
            out = dashboard_feed.view(game)
            json.dumps(out)
            assert out["level"] == "public" and out["locked"], out["level"]
            keys = set()
            walk_keys(out, keys)
            leaked = keys & PRIVATE_KEYS
            assert not leaked, ("private keys in a public feed", leaked)
            assert out["ghost"] is None
            assert len(out["houses"]) == 2
            for h in out["houses"]:
                assert h["months"] and h["months"][-1]["worth"] == h["worth"], "worth now closes the curve"
            feeds += 1
        assert feeds
        journal.close_game("test over")

        # ---- solo, a first game: par pace ghost, open blocks
        last = None
        for game in play(["Solo"], 5, seed=5, months=8):
            last = dashboard_feed.view(game)
            json.dumps(last)
        assert last["level"] == "open" and not last["locked"]
        assert last["ghost"] and last["ghost"]["kind"] == "par", last["ghost"]
        assert last["ghost"]["curve"][0] > 0 and len(last["ghost"]["curve"]) >= 12
        for k in ("ports", "booms", "deals", "lane_profit"):
            assert k in last, k
        assert any(row["prices"] for row in last["ports"].values())
        assert last["tape"], "the tape has events"
        assert all(e["type"] in dashboard_feed.TAPE_PUBLIC or e["type"] == "deal" for e in last["tape"])
        journal.close_game("test over")

        # ---- a finished game on the books: the ghost becomes the best game
        for _ in play(["Solo"], 5, seed=7):
            pass
        journal.close_game("test over")
        for game in play(["Solo"], 5, seed=9, months=3):
            ghost = dashboard_feed.view(game)["ghost"]
        assert ghost and ghost["kind"] == "best", ghost
        assert len(ghost["curve"]) >= 40 and ghost["final"] == ghost["curve"][-1] or ghost["final"] > 0, ghost
        journal.close_game("test over")
        print("OK: public feed holds nothing private, solo feed is open with a par ghost, then a best-game ghost, {} months checked".format(feeds))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
