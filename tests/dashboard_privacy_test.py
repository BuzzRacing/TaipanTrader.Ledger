"""Phase 0 contracts for the Dashboard's feed (Command Center plan, sections 3.2, 3.3, 9.1 and 9.4).

Checked on the deterministic fixtures in dashboard_fixtures.py:

  - privacy by sentinel: with rivals at the table every house's silver, bank deposit, debt, cargo and price
    basis is set to a number that appears nowhere else. None of those numbers, and none of the private field
    names, may appear anywhere in the feed or the persona brief built from it;
  - privacy by trap: each house is swapped for a trap that raises if a private-only field is read while the
    public feed is being built. Building it must not touch them at all;
  - no mutation: building a feed leaves the game state exactly as it was, at every stage of a game;
  - the context bar: the table-wide facts are right, and the Captain's own block is sent only for an open solo
    game and agrees with the house row beside it;
  - size: every feed stays inside the compact-poll budget;
  - determinism: the same fixture built twice gives the same figures.

Run from the project folder:  python tests/dashboard_privacy_test.py
"""
import copy
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dashboard_brief  # noqa: E402
import dashboard_feed  # noqa: E402
import dashboard_fixtures as fx  # noqa: E402
import engine  # noqa: E402
import harbor_view  # noqa: E402

POLL_BUDGET = 100 * 1024          # plan 9.4: a compact poll response stays under 100 KB

# Field names that belong to one house alone. None may be a key anywhere in a public feed. ("dest" is not
# here: a voyage already sailed is public history. Where a house means to sail next is private, and travels
# only in context.captain, which the checks below require to be absent.)
PRIVATE_KEYS = {"cash", "bank", "debt", "cargo", "prices", "base", "deals", "lane_profit", "booms",
                "market_effects", "basis", "tips", "hot_tips", "known", "rep", "books", "purse",
                "contracts", "commissions", "log", "msg",
                # the Command Center's private suites (dashboard_suites.py) and what is inside them
                "atlas", "routes", "trade", "fleet", "treasury", "career", "parts", "slices", "opportunities",
                "known", "stored", "warehouse", "tax", "effects", "laid_up", "ledger", "estate"}

# Numbers planted in the private fields. Seven digits each and unlike any figure a 7-month game produces.
SENTINELS = {"cash": 7135791, "bank": 8246802, "debt": 9357913, "cargo": 4681357, "basis": 5792468}

# Fields nothing public depends on: reading one while the feed is "public" is a leak in the making.
TRAPPED = {"basis", "tips", "hot_tips", "known", "log", "books", "contracts", "offers", "bands", "customs"}


class Trap(dict):
    """A house whose private-only fields raise when read."""
    armed = False

    def _check(self, key):
        if Trap.armed and key in TRAPPED:
            raise AssertionError("the public feed read a private field: {}".format(key))

    def __getitem__(self, key):
        self._check(key)
        return dict.__getitem__(self, key)

    def get(self, key, default=None):
        self._check(key)
        return dict.get(self, key, default)


def walk_keys(x, found):
    if isinstance(x, dict):
        for k, v in x.items():
            found.add(k)
            walk_keys(v, found)
    elif isinstance(x, (list, tuple)):
        for v in x:
            walk_keys(v, found)


def response(game):
    """The feed with its brief, put together the way server.py does for /api/dashboard."""
    feed = dashboard_feed.view(game)
    state = game.s
    snapshot = {"phase": state["phase"], "weather": dict(state["weather"]),
                "bans": {k: game.banned(k) for k in state["crackdown"]}}
    feed["brief"] = dashboard_brief.build(feed, snapshot, engine.TEXT, engine.GOODS)
    return feed


def check_public_sentinels():
    with fx.journal_sandbox():
        game = fx.build("rivals")
        assert harbor_view.level(game) == "public"
        good = next(iter(engine.GOODS))
        for p in game.s["players"].values():
            p["cash"], p["bank"], p["debt"] = float(SENTINELS["cash"]), float(SENTINELS["bank"]), float(SENTINELS["debt"])
            p["cargo"][good] = SENTINELS["cargo"]
            p.setdefault("basis", {})[good] = float(SENTINELS["basis"])
        out = response(game)
        text = json.dumps(out)
        for name, n in SENTINELS.items():
            assert str(n) not in text, "a house's {} is in the public feed".format(name)
        keys = set()
        walk_keys(out, keys)
        assert not keys & PRIVATE_KEYS, ("private field names in a public feed", sorted(keys & PRIVATE_KEYS))
        assert out["locked"] and out["ghost"] is None
        assert out["context"]["captain"] is None, "no house's own position goes out with rivals at the table"
        assert out["context"]["houses"] == 2


def check_public_trap():
    with fx.journal_sandbox():
        game = fx.build("rivals")
        for pid in list(game.s["players"]):
            game.s["players"][pid] = Trap(game.s["players"][pid])
        Trap.armed = True
        try:
            out = response(game)
        finally:
            Trap.armed = False
        assert out["level"] == "public" and len(out["houses"]) == 2


def check_no_mutation():
    for name in fx.NAMES:
        with fx.journal_sandbox():
            game = fx.build(name)
            before = copy.deepcopy(game.s)
            response(game)
            response(game)
            assert game.s == before, "building the {} feed changed the game".format(name)


def check_context():
    for name in fx.NAMES:
        with fx.journal_sandbox():
            game = fx.build(name)
            out = dashboard_feed.view(game)
            c, s = out["context"], game.s
            json.dumps(c)
            total = int(s.get("years") or 0) * 12
            assert c["turn"] == s["turn"] and c["phase"] == s["phase"] and c["date"] == out["date"]
            assert c["months_total"] == total
            assert c["months_left"] == (max(0, total - s["turn"]) if total else None), name
            assert set(c["seas"]) == set(engine.REGIONS), "one forecast for every sea"
            assert all(0 <= lv <= 3 for lv in c["seas"].values())
            assert c["worst_sea"]["level"] == max(c["seas"].values())
            assert c["seas"][c["worst_sea"]["region"]] == c["worst_sea"]["level"]
            assert 0 < c["forecast_accuracy"] <= 1
            assert c["houses"] == len(out["houses"])
            cap = c["captain"]
            if name in ("early", "middle", "late"):
                row = out["houses"][0]
                p = s["players"][s["order"][0]]
                assert cap and cap["id"] == row["id"] and cap["firm"] == row["firm"]
                assert cap["worth"] == row["worth"] == int(game.worth(p)), "the bar and the tower agree"
                assert cap["port"] == p["port"]
                assert cap["rank"] == game.commissioned_rank(p)["title"]
                months = row["months"]
                assert cap["worth_change"] == months[-1]["worth"] - months[-2]["worth"]
                assert cap["fleet"]["ships"] == len(p["ships"]) == len(row["hull"])
                assert cap["fleet"]["crippled"] == sum(1 for sh in p["ships"] if sh.get("crippled"))
                assert 0 <= cap["fleet"]["hull"] <= 1
            else:
                assert cap is None, "{}: no Captain's block".format(name)


def check_budget_and_determinism():
    sizes = {}
    for name in fx.NAMES:
        with fx.journal_sandbox():
            first = response(fx.build(name))
        with fx.journal_sandbox():
            second = response(fx.build(name))
        sizes[name] = len(json.dumps(first))
        assert sizes[name] < POLL_BUDGET, "{} feed is {} bytes".format(name, sizes[name])
        pick = lambda f: ([(h["firm"], h["worth"], len(h["months"]), len(h["legs"])) for h in f["houses"]],
                          f["turn"], f["context"]["seas"])
        assert pick(first) == pick(second), "{} is not the same game twice".format(name)
    return sizes


def main():
    check_public_sentinels()
    check_public_trap()
    check_no_mutation()
    check_context()
    sizes = check_budget_and_determinism()
    print("OK: nothing private in the public feed (sentinels and traps), feeds change nothing, the context bar "
          "agrees with the game, fixtures repeat; feed sizes " +
          ", ".join("{} {:.1f} KB".format(k, v / 1024) for k, v in sizes.items()))


if __name__ == "__main__":
    main()
