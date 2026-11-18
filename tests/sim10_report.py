"""Balance report from many 10-year, four-captain bot games (see sim10.py)."""
import collections
import json
import statistics as st
import sys

import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sim10  # noqa: E402
import engine  # noqa: E402

sim10.setup()
N = int(sys.argv[1]) if len(sys.argv) > 1 else 30
agg = collections.defaultdict(list)
ev_counts = collections.Counter()
by_bot = collections.defaultdict(collections.Counter)
refusals = collections.defaultdict(collections.Counter)
crashes = []
milestones = collections.defaultdict(list)     # name -> turn first reached 1M
books_total = collections.defaultdict(collections.Counter)
winners = collections.Counter()
fight_outcomes = collections.Counter()
customs_outcomes = collections.Counter()
max_fleet_turn = collections.defaultdict(list)
late_idle = collections.defaultdict(list)
cash_end = collections.defaultdict(list)
deadmoney = collections.defaultdict(list)
turn_hist = None
for seed in range(1, N + 1):
    game, bots, events, history, cr = sim10.play(seed)
    crashes += [(seed,) + c for c in cr]
    names = {b.pid: b.name for b in bots.values()}
    ranked = sorted(bots.values(), key=lambda b: -game.worth(game.s["players"][b.pid]))
    winners[ranked[0].name] += 1
    for b in bots.values():
        p = game.s["players"][b.pid]
        agg[b.name].append(int(game.worth(p)))
        for k, v in (p["books"].get("game") or {}).items():
            books_total[b.name][k] += v
        for k, v in b.refused_msgs.items():
            refusals[b.name][k] += v
        for k, v in b.counts.items():
            by_bot[b.name]["do_" + k] += v
        h = history[b.name]
        m = next((x["turn"] for x in h if x["worth"] >= 1_000_000), None)
        milestones[b.name].append(m)
        f = next((x["turn"] for x in h if x["ships"] >= 5), None)
        max_fleet_turn[b.name].append(f)
        cash_end[b.name].append((int(p["cash"]), int(p["bank"])))
        by_bot[b.name]["wrecks"] += p["wrecks"]
    if seed == 1:
        turn_hist = history
    for e in events:
        ev_counts[(e["cat"], e["type"])] += 1
        who = e.get("who")
        if who:
            by_bot[who][e["type"]] += 1
        if e["type"] in ("fight_end", "battle_end", "fight") or e["type"].startswith("battle_"):
            fight_outcomes[(e["type"], e.get("outcome"))] += 1
        if e["type"] == "customs_declare":
            customs_outcomes[str(e.get("rulings") or e.get("result"))[:60]] += 1

print("=== FINAL WORTH over", N, "ten-year games ===")
for n, ws in agg.items():
    ws.sort()
    ms = [m for m in milestones[n] if m is not None]
    fl = [m for m in max_fleet_turn[n] if m is not None]
    print("{:4s} median {:>12,} min {:>12,} max {:>13,}  1M reached in {}/{} games (median month {})  5-ship fleet {}/{} (median month {})  wins {}".format(
        n, ws[len(ws) // 2], ws[0], ws[-1], len(ms), N, st.median(ms) if ms else "-", len(fl), N, st.median(fl) if fl else "-", winners[n]))
print("crashes", len(crashes))
for c in crashes[:3]:
    print(c)
print("\n=== EVENT TYPES (all games) ===")
for k, v in sorted(ev_counts.items(), key=lambda kv: -kv[1]):
    print(k, v)
print("\n=== PER-BOT counters ===")
for n, c in by_bot.items():
    print(n, dict(sorted(c.items(), key=lambda kv: -kv[1])))
print("\n=== REFUSED actions (top) ===")
for n, c in refusals.items():
    print(n, c.most_common(8))
print("\n=== BOOKS (game totals summed over all games, /N) ===")
for n, c in books_total.items():
    print(n, {k: int(v / N) for k, v in sorted(c.items(), key=lambda kv: kv[1])})
print("\n=== cash/bank at end (seed1..5) ===")
for n, v in cash_end.items():
    print(n, v[:5])
print("\n=== seed 1 worth by year ===")
for n, h in turn_hist.items():
    print(n, [x["worth"] for x in h[11::12]], "ships", [x["ships"] for x in h[11::12]], "debt", [x["debt"] for x in h[11::12]])
