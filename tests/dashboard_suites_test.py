"""The Command Center's private suites (dashboard_suites.py; Dashboard plan, Phase 2).

Checked on the deterministic fixtures in dashboard_fixtures.py:

  - reconciliation: every section agrees with the game. The balance sheet adds up to net worth; the bank's
    slices add up to the interest the engine pays; ships, warehouses, tax, standing and shares match what the
    Player screen is given; nothing ashore is counted as cargo aboard;
  - the month ahead: the bank interest, wages and rent the Treasury names are what the game then charges;
  - routes: real voyages are sailed, and the storm, pirate and pirate-queen chances this module gave before
    each one are checked against the odds the game's own dice recorded;
  - opportunities: a banned cargo is never offered, and a gap is never called a profit;
  - the storm history: every storm the journal recorded, once, newest first; a rival's losses are left out;
  - privacy: with rivals at the table, and in a finished game with more than one house, no private section is
    in the feed.

Run from the project folder:  python tests/dashboard_suites_test.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dashboard_feed  # noqa: E402
import dashboard_fixtures as fx  # noqa: E402
import dashboard_suites  # noqa: E402
import engine  # noqa: E402
import sim_test  # noqa: E402
import stats  # noqa: E402

PRIVATE = ("atlas", "routes", "trade", "fleet", "treasury", "career")
SOLO = ("early", "middle", "late")


def solo(game):
    pid = game.s["order"][0]
    return pid, game.s["players"][pid]


def check_reconciles():
    for name in SOLO:
        with fx.journal_sandbox():
            game = fx.build(name)
            pid, p = solo(game)
            feed = dashboard_feed.view(game)
            json.dumps(feed)
            for k in PRIVATE + ("weather",):
                assert k in feed, "{}: {} missing".format(name, k)
            me = game.view(pid)["me"]

            # ---- treasury: the balance sheet is net worth, to the silver
            tr = feed["treasury"]
            raw = dashboard_suites.worth_parts(game, p)
            assert abs(sum(raw.values()) - game.worth(p)) < 0.01, "{}: the parts are not net worth".format(name)
            assert tr["worth"] == int(game.worth(p)) == me["worth"]
            assert abs(sum(tr["parts"].values()) - tr["worth"]) <= len(tr["parts"]), "rounding only"
            assert tr["parts"]["debt"] <= 0 and tr["parts"]["cash"] == int(round(p["cash"]))
            # ---- the bank's slices are the engine's interest
            bonus = game.house_bank_bonus(p)
            slices = dashboard_suites.bank_slices(game, p)
            assert abs(sum(x["interest"] for x in slices) - game.bank_interest(p, extra=bonus)) < 1e-6
            assert abs(sum(x["amount"] for x in slices) - p["bank"]) <= len(slices)
            assert [x["to"] for x in slices] == [None if t is None else int(round(t)) for t, _ in game.bank_tiers()]
            assert tr["bank"]["interest"] == int(round(game.bank_interest(p, extra=bonus)))
            # ---- running costs are the engine's
            assert tr["costs"]["wages"] == game.upkeep(p) == me["fleet_ledger"]["bill"]
            assert tr["costs"]["rent"] == sum(r["rent"] for r in game.warehouse_rents(p)) == me["wh_rent"]["total"]
            assert tr["costs"]["december_in"] == 11 - game.s["turn"] % 12
            nm = tr["next_month"]
            assert nm["net"] == nm["bank_interest"] - nm["loan_interest"] - nm["costs"]
            assert tr["debt"]["collectors"] == me["collectors"] and tr["debt"]["bankrupt"] == me["bankrupt"]
            assert tr["estate"] == me["estate"]
            for part in ("last", "cur", "year", "game"):
                assert "log" not in (tr["books"][part] or {}), "the books carry money, not log lines"
            assert tr["books"]["year"] == me["books"]["year"] and tr["books"]["game"] == me["books"]["game"]

            # ---- fleet: ship for ship what the Player screen lists
            fl = feed["fleet"]
            assert fl["ships"] == me["ships"] and fl["laid_up"] == me["laid_up"]
            assert fl["capacity"] == game.capacity(p) and fl["used"] == game.used(p)
            assert fl["guns"] == game.guns(p) and fl["ledger"] == me["fleet_ledger"]
            assert abs(fl["hull"] - feed["context"]["captain"]["fleet"]["hull"]) <= 0.011, "one fleet condition"

            # ---- atlas: standing, tax and shares for every port; warehouses counted once
            at = feed["atlas"]
            assert set(at["ports"]) == set(engine.PORTS)
            assert sum(1 for row in at["ports"].values() if row["here"]) == 1
            assert sum(1 for row in at["ports"].values() if row["home"]) == 1
            ashore = {}
            for k, row in at["ports"].items():
                assert row["band"] == game.band_of(p["rep"].get(k, 50)) and 0 <= row["band"] <= 4
                assert row["rep"] == me["rep"][k]
                assert abs(row["tax"]["mine"] - game.tax_rate_for(p, k)) < 1e-9
                assert abs(row["tax"]["base"] - game.tax_rate(k)) < 1e-9
                sh = row["shares"]
                assert 0 <= sh["mine"] <= sh["total"] and 0 <= sh["left"] <= sh["total"]
                assert sh["patron_me"] == (game.patron_of(k) == pid)
                assert row["services"]["bank"] == engine.port_has(p, k, "bank")
                if row["warehouse"]:
                    assert row["warehouse"]["used"] == sum(row["warehouse"]["goods"].values()) <= row["warehouse"]["cap"]
                    for g, q in row["warehouse"]["goods"].items():
                        ashore[g] = ashore.get(g, 0) + q
            assert at["ports"][engine.home_of(p)]["warehouse"]["goods"] == p["wh"]
            assert {g: q for g, q in ashore.items() if q} == feed["trade"]["stored"], "warehouse stock, once"
            assert sum(row["shares"]["mine"] for row in at["ports"].values()) == at["shares"]["placed"]
            assert at["shares"]["earned"] == at["shares"]["placed"] + at["shares"]["free"] <= at["shares"]["cap"]

            # ---- trade: the hold is the hold, not the warehouses
            td = feed["trade"]
            assert td["cargo"] == p["cargo"] and td["used"] == game.used(p)
            assert td["basis"] == me["basis"] and td["purse"] == me["purse"]
            for row in td["opportunities"]:
                assert row["sell_price"] > row["buy_price"] and row["buy"] != row["sell"]
                assert "profit" not in row, "a price gap is not called a profit"
                for end in (row["buy"], row["sell"]):
                    assert row["good"] not in game.banned(end) and engine.sold_here(end, row["good"])
                assert abs(row["buy_price"] - round(game.s["prices"][row["buy"]][row["good"]], 2)) < 1e-9

            # ---- career
            cr = feed["career"]
            assert cr["rank"] == game.commissioned_rank(p)["title"] == feed["context"]["captain"]["rank"]
            assert cr["commissions"] == me["commissions"] and cr["shares"]["free"] == game.shares_free(p)

            # ---- weather: public, one forecast per sea, every port on exactly one sea
            wx = feed["weather"]
            assert {r: v["level"] for r, v in wx["seas"].items()} == feed["context"]["seas"]
            assert sorted(k for v in wx["seas"].values() for k in v["harbours"]) == sorted(engine.PORTS)
            rt = feed["routes"]
            assert rt["from"] == p["port"] and len(rt["routes"]) == len(engine.PORTS) - 1
            for row in rt["routes"]:
                seas = (engine.PORTS[p["port"]]["region"], engine.PORTS[row["dest"]]["region"])
                assert row["level"] == max(wx["seas"][r]["level"] for r in seas), "the worse of the two seas"
                assert 0 <= row["storm"] <= 1 and 0 <= row["pirates"] <= 1 and 0 <= row["lord"] <= 1
                assert "safe" not in row


def check_shares_and_bonus():
    """Shares placed, a Patron, and the great house's bank bonus: set by hand, then read back."""
    with fx.journal_sandbox():
        game = fx.build("late")
        pid, p = solo(game)
        port = next(k for k in engine.PORTS if k != engine.home_of(p) and game.tax_rate(k) > 0)
        game.s.setdefault("shares", {})[port] = {pid: 3}
        p["share_paid"], p["share_earned"] = {port: 900000.0}, 3
        feed = dashboard_feed.view(game)
        row = feed["atlas"]["ports"][port]
        assert row["shares"] == {"mine": 3, "total": 10, "left": 7, "patron": p["firm"], "patron_me": True}
        assert abs(row["tax"]["mine"] - game.tax_rate_for(p, port)) < 1e-9 and row["tax"]["mine"] < row["tax"]["base"]
        assert feed["atlas"]["shares"]["placed"] == 3 and feed["career"]["shares"]["by_port"] == {port: 3}
        assert feed["treasury"]["parts"]["shares"] == 900000
        assert abs(sum(dashboard_suites.worth_parts(game, p).values()) - game.worth(p)) < 0.01
        game.house_bank_bonus = lambda _p: 0.002          # as a Mansion would pay
        slices = dashboard_suites.bank_slices(game, p)
        assert abs(sum(x["interest"] for x in slices) - game.bank_interest(p, extra=0.002)) < 1e-6
        assert slices[0]["rate"] == round(game.bank_tiers()[0][1] + 0.002, 6)


def check_month_ahead():
    """The Treasury's month ahead against the month that follows, for a house that stays at anchor."""
    with fx.journal_sandbox():
        game = fx.build("late")
        pid, p = solo(game)
        sim_test.clear_customs(game, pid, game.rng)          # the Port Authority first; then nothing but waiting
        assert not sim_test.jail.jailed(p) and not sim_test.jail.pending(p)
        nm = dashboard_feed.view(game)["treasury"]["next_month"]
        bank0 = p["bank"]
        assert sim_test.try_act(game, pid, {"type": "sail", "dest": p["port"], "orders": "run"}), "the fleet stays at anchor"
        turn = game.s["turn"]
        game.maybe_advance(set(game.s["order"]))
        assert game.s["turn"] == turn + 1, "the month closed"
        assert abs((p["bank"] - bank0) - nm["bank_interest"]) <= 1, "the bank paid what the Treasury named"
        last = game.view(pid)["me"]["books"]["last"]["lines"]
        assert -int(round(last.get("upkeep", 0))) + -int(round(last.get("wh_rent", 0))) == nm["costs"], (last, nm)


def check_routes_against_the_dice():
    """Sails the middle game on. Just before each month closes the routes are read; afterwards the journal's own
    dice give the odds the game used. Where the sea came as forecast they must be the same."""
    with fx.journal_sandbox():
        game = fx.build("middle")
        pid, p = solo(game)
        gid = game.s["game_id"]
        seen = {"storm": 0, "pirates": 0, "pirate_lord": 0}
        after_attack = float(engine.storm.rules().get("after_attack", 1.0))
        for _ in range(60):
            if game.s["phase"] != "port":
                break
            turn, origin, got = game.s["turn"], p["port"], {}
            fx.play_month(game, lambda g: got.update({r["dest"]: r for r in dashboard_suites.routes(g, p)["routes"]}))
            rows = got
            events = [e for e in stats._read(gid)["events"] if e.get("turn") == turn]
            sailed = next((e for e in events if e.get("type") == "sailed" and e.get("origin") == origin), None)
            if not sailed or sailed["dest"] not in rows:
                continue
            row = rows[sailed["dest"]]
            assert abs(row["risk"] - sailed["risk"]) < 1e-3, "the distance factor is the engine's"
            dice = {e["type"]: e for e in events if e.get("cat") == "dice" and e.get("type") in seen}
            stormed = bool(dice.get("storm", {}).get("hit"))
            if "storm" in dice and sailed["sea"] == row["level"]:
                assert abs(dice["storm"]["odds"] - row["storm"]) < 2e-5, ("storm", dice["storm"]["odds"], row)
                seen["storm"] += 1
            # A storm that lands spills cargo and damages hulls before the pirates look, so the fleet they see is no
            # longer the one that sailed: after a storm the odds may only be lower (less cargo, and found less often).
            for kind, key in (("pirates", "pirates"), ("pirate_lord", "lord")):
                if kind not in dice:
                    continue
                odds, mine = dice[kind]["odds"], row[key]
                if stormed:
                    assert odds <= mine * after_attack * 1.02 + 2e-5, (kind, "after a storm", odds, row)
                else:
                    assert abs(odds - mine) <= 0.02 * max(mine, 1e-6) + 2e-5, (kind, odds, row)
                    seen[kind] += 1
        assert seen["storm"] >= 5 and seen["pirates"] >= 5, ("too few voyages checked", seen)
        return seen


def check_banned_cargo_is_not_offered():
    with fx.journal_sandbox():
        game = fx.build("middle")
        first = dashboard_suites.opportunities(game)
        assert first, "the middle game has price gaps"
        top = first[0]
        real = game.banned
        game.banned = lambda port: [top["good"]] if port == top["sell"] else real(port)
        for row in dashboard_suites.opportunities(game):
            assert not (row["good"] == top["good"] and top["sell"] in (row["buy"], row["sell"])), "a banned port was offered"


def check_weather_history():
    """The storm history is the journal's: every storm that landed, counted once, newest first."""
    with fx.journal_sandbox():
        game = fx.build("middle")
        pid, p = solo(game)
        events = stats._read(game.s["game_id"])["events"]
        feed = dashboard_feed.view(game)
        h = feed["weather"]["history"]
        landed = [e for e in events if e.get("cat") == "voyage" and e.get("type") == "storm_damage"]
        assert h["totals"]["storms"] == len(landed) > 0, "the middle game has met storms"
        assert h["totals"]["voyages"] == sum(1 for e in events if e.get("cat") == "voyage" and e.get("type") == "sailed")
        assert h["totals"]["offcourse"] == sum(1 for e in events if e.get("type") == "offcourse" and e.get("cat") == "voyage")
        assert len(h["storms"]) == min(len(landed), dashboard_suites.HISTORY_KEEP)
        assert [x["turn"] for x in h["storms"]] == sorted((x["turn"] for x in h["storms"]), reverse=True)
        newest = landed[-1]
        assert h["storms"][0]["turn"] == newest["turn"] and h["storms"][0]["ships"] == len(newest["hits"])
        assert h["storms"][0]["damage"] == sum(x["damage"] for x in newest["hits"])
        assert "cargo" in h["storms"][0], "a solo Captain sees what the storm took"
        for r, v in h["seas"].items():
            rolls = [e for e in events if e.get("cat") == "weather" and e.get("region") == r]
            assert v["months"] == len(rolls) and v["held"] == sum(1 for e in rolls if e["forecast"] == e["actual"])
            assert 0 < v["held"] <= v["months"]
    with fx.journal_sandbox():
        h = dashboard_feed.view(fx.build("rivals"))["weather"]["history"]
        assert h["totals"]["storms"] == len(h["storms"]) > 0
        assert all("cargo" not in x and "guns" not in x for x in h["storms"]), "a rival's losses are not public"
    with fx.journal_sandbox():
        h = dashboard_feed.view(fx.build("lobby"))["weather"]["history"]
        assert h["storms"] == [] and h["totals"]["voyages"] == 0


def check_private_only_when_solo():
    with fx.journal_sandbox():
        game = fx.build("rivals")
        feed = dashboard_feed.view(game)
        assert feed["level"] == "public" and not any(k in feed for k in PRIVATE)
        assert set(feed["weather"]["seas"]) == set(engine.REGIONS), "the weather glass is public"
        game.s["phase"] = "ended"                  # the finale opens the table, but two houses are not one Captain
        feed = dashboard_feed.view(game)
        assert feed["level"] == "open" and not any(k in feed for k in PRIVATE)
    with fx.journal_sandbox():
        feed = dashboard_feed.view(fx.build("lobby"))
        assert not any(k in feed for k in PRIVATE), "nothing to show before a game starts"


def main():
    check_reconciles()
    check_shares_and_bonus()
    check_month_ahead()
    seen = check_routes_against_the_dice()
    check_banned_cargo_is_not_offered()
    check_weather_history()
    check_private_only_when_solo()
    print("OK: suites reconcile with the game (worth, bank slices, costs, fleet, atlas, trade, career), the month "
          "ahead matched the month that came, route odds matched the dice on {} storm, {} pirate and {} pirate-queen "
          "rolls, banned cargo is never offered, the storm history is the journal's, private sections only for a solo "
          "Captain".format(
              seen["storm"], seen["pirates"], seen["pirate_lord"]))


if __name__ == "__main__":
    main()
