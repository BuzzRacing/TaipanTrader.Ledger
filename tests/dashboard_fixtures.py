"""Deterministic game states for the Dashboard's tests, measurements and previews (Command Center plan, Phase 0).

Every fixture is a real game played by the test bots from a fixed seed, so the same call always gives the same
state and the same feed. Nothing here is hand-written sample data.

  early    a solo five-year game, 6 months in: one small fleet, little history
  middle   a solo five-year game, 30 months in: routes, deals, booms and a worth curve to draw
  late     a solo twenty-year game, 200 months in, with the treasury raised to Game 6 scale (silver and a bank
           deposit past the first interest slice) so late-game figures can be checked for fit
  rivals   two houses, 7 months in: the "public" level, where nothing private may leave the server
  lobby    a game nobody has started: empty history

Use:
    import dashboard_fixtures as fx
    with fx.journal_sandbox():
        game = fx.build("late")
        feed = dashboard_feed.view(game)

Run from the project folder to list them:  python tests/dashboard_fixtures.py
"""
import contextlib
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config  # noqa: E402
import engine  # noqa: E402
import journal  # noqa: E402
import sim_test  # noqa: E402  (the bots)
from engine import Game  # noqa: E402

# name: (captains, years, seed, months played)
SPECS = {
    "early": (["Solo"], 5, 21, 6),
    "middle": (["Solo"], 5, 22, 30),
    "late": (["Solo"], 20, 23, 200),
    "rivals": (["Ada", "Bao"], 5, 24, 7),
}
NAMES = ("lobby",) + tuple(SPECS)

# Game 6 scale for the late fixture: silver in hand, and a deposit past the first slice of the tiered interest.
LATE_CASH = 18_600_000
LATE_BANK = 34_100_000


@contextlib.contextmanager
def journal_sandbox():
    """Points the game journal at a throwaway folder, so fixtures never write into the real journal."""
    keep = (journal.DIR, journal.GAMES, journal.SERVER)
    tmp = tempfile.mkdtemp(prefix="dash_fixture_")
    journal.DIR = os.path.join(tmp, "journal")
    journal.GAMES = os.path.join(journal.DIR, "games")
    journal.SERVER = os.path.join(journal.DIR, "server")
    os.makedirs(journal.DIR, exist_ok=True)
    try:
        yield tmp
    finally:
        try:
            journal.close_game("fixture over")
        except Exception:
            pass
        journal.DIR, journal.GAMES, journal.SERVER = keep
        shutil.rmtree(tmp, ignore_errors=True)


def play_month(game, before_close=None):
    """One month for every house, played by the trader bot (a captain in gaol pleads, serves and walks free as
    the bots in dashboard_test do). before_close(game) is called once every house has given its orders and
    before the month is resolved: the moment a route's odds are what the dice will use."""
    rng = game.rng
    for pid in game.s["order"]:
        p = game.s["players"][pid]
        if sim_test.jail.pending(p):
            sim_test.try_act(game, pid, {"type": "plea", "months": 0})
        if sim_test.jail.jailed(p):
            if not p["ready"]:
                sim_test.try_act(game, pid, {"type": "jail_serve"})
            continue
        if p.get("jail_freed"):
            sim_test.try_act(game, pid, {"type": "jail_free"})
        sim_test.trader_bot(game, pid, rng)
    if before_close:
        before_close(game)
    game.maybe_advance(set(game.s["order"]))
    game.fight_out(set(game.s["order"]))


def _play(name, names, years, seed, months):
    """Plays a recorded bot game for so many months. The game id is fixed as well as the seed: hot tips are
    drawn from the game's id, not its dice, so a fresh id would make a different game."""
    game = Game(seed=seed)
    game.s["game_id"] = "gfixture-" + name
    for who in names:
        game.join(who, "")
    host = game.s["order"][0]
    game.act(host, {"type": "settings", "years": years}, present=game.s["order"])
    game.act(host, {"type": "start"}, present=game.s["order"])
    journal.open_game(game, "dashboard fixture " + name, engine.CFG, config.load_lang(engine.CFG["language"]["active"]))
    done = 0
    while game.s["phase"] == "port" and done < months:
        play_month(game)
        done += 1
    return game


def build(name):
    """The game for one fixture, left open in the journal (call inside journal_sandbox())."""
    if name == "lobby":
        game = Game(seed=20)
        game.s["game_id"] = "gfixture-lobby"
        game.join("Solo", "")
        return game
    names, years, seed, months = SPECS[name]
    game = _play(name, names, years, seed, months)
    if name == "late":
        p = game.s["players"][game.s["order"][0]]
        p["cash"], p["bank"] = float(LATE_CASH), float(LATE_BANK)
    return game


def main():
    import dashboard_feed
    for name in NAMES:
        with journal_sandbox():
            game = build(name)
            feed = dashboard_feed.view(game)
            houses = feed["houses"]
            print("{:7} level {:6} phase {:5} turn {:3}  houses {}  worth {}".format(
                name, feed["level"], feed["phase"], feed["turn"], len(houses),
                ", ".join("{:,}".format(h["worth"]) for h in houses) or "-"))


if __name__ == "__main__":
    main()
