"""Cargo Tiers balance, phase 8: how much room each cargo gives a trader, measured on the engine's own prices.

Plays idle games (no trading) for many months and records every port's price for every cargo. Per cargo it reports
the typical best spread between two ports in the same month, the profit one hold can make from it once the dealers'
margin and the market depth are taken off, and how far one ship-load moves the price.

    python tests/tiers_market_scan.py [games] [months]
"""
import copy
import os
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402
import engine  # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def scan(games=6, months=120):
    cfg = copy.deepcopy(config.defaults())
    cfg["rules"]["tiers"]["enabled"] = True
    engine.TIERS_READY = True
    engine.configure(cfg)
    rows = {g: {"spread": [], "level": [], "ports": []} for g in engine.GOODS}
    for seed in range(1, games + 1):
        game = engine.Game(seed=seed)
        tok = game.join("Idle", "Idle & Co")
        pid = game.pid_for_token(tok)
        game.act(pid, {"type": "settings", "years": 20}, present=game.s["order"])
        game.act(pid, {"type": "start"}, present=game.s["order"])
        for _ in range(months):
            if game.s["phase"] not in ("port", "sea"):
                break
            p = game.s["players"][pid]
            if p.get("jail") or p.get("battle") or p.get("customs"):
                game.act(pid, {"type": "sea", "choice": "auto"}, game.s["order"]) if p.get("battle") else None
            try:
                game.act(pid, {"type": "sail", "dest": None}, present=game.s["order"])
            except engine.GameError:
                pass
            game.maybe_advance(set(game.s["order"]))
            for g in engine.GOODS:
                quotes = [pr[g] for port, pr in game.s["prices"].items() if g in pr]
                if len(quotes) >= 2:
                    mean = sum(quotes) / len(quotes)
                    rows[g]["spread"].append((max(quotes) - min(quotes)) / mean)
                    rows[g]["level"].append(mean / engine.GOODS[g]["base"])
                    rows[g]["ports"].append(len(quotes))
    return rows


def main():
    games = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    months = int(sys.argv[2]) if len(sys.argv) > 2 else 120
    rows = scan(games, months)
    holds = {"junk": 60, "barque": 250, "indiaman": 500}
    print("{:<11}{:>8}{:>6}{:>7}{:>7}{:>9}{:>9}  {:>12}{:>12}".format(
        "cargo", "base", "vol", "depth", "ports", "spread", "level", "250 hold", "per trip $"))
    for g, r in rows.items():
        if not r["spread"]:
            continue
        spread, level = st.median(r["spread"]), st.mean(r["level"])
        spec = engine.GOODS[g]
        margin = 0.07                                       # the dealers' share, buying and selling
        units = min(250, int(spec["depth"] * 0.4))          # a load that moves the price about a tenth
        trip = units * spec["base"] * max(0.0, spread - margin - 0.10)
        print("{:<11}{:>8,.0f}{:>6.2f}{:>7}{:>7.1f}{:>8.0%}{:>9.2f}  {:>12}{:>12,.0f}".format(
            g, spec["base"], spec["vol"], spec["depth"], st.mean(r["ports"]), spread, level, units, trip))


if __name__ == "__main__" and not (len(sys.argv) > 1 and sys.argv[1] == "ceiling"):
    main()


def ceiling(games=6, months=120, mutate=None, units_share=0.4, per_game=False):
    """With perfect foresight and one load a month (buy at the cheapest port, sell at the dearest, a load that moves
    the price by about a tenth, the dealers' margin taken off), what can one cargo pay over the game? An upper bound,
    not a forecast: it shows which cargoes give the most room and whether a new one could run away with the money."""
    cfg = copy.deepcopy(config.defaults())
    cfg["rules"]["tiers"]["enabled"] = True
    if mutate:
        mutate(cfg)
    engine.TIERS_READY = True
    engine.configure(cfg)
    total = {g: 0.0 for g in engine.GOODS}
    each = {g: [] for g in engine.GOODS}
    for seed in range(1, games + 1):
        before = dict(total)
        game = engine.Game(seed=seed)
        pid = game.pid_for_token(game.join("Idle", "Idle & Co"))
        game.act(pid, {"type": "settings", "years": 20}, present=game.s["order"])
        game.act(pid, {"type": "start"}, present=game.s["order"])
        for _ in range(months):
            if game.s["phase"] not in ("port", "sea"):
                break
            try:
                game.act(pid, {"type": "sail", "dest": None}, present=game.s["order"])
            except engine.GameError:
                pass
            game.maybe_advance(set(game.s["order"]))
            for g in engine.GOODS:
                quotes = [pr[g] for pr in game.s["prices"].values() if g in pr]
                if len(quotes) < 2:
                    continue
                units = engine.GOODS[g]["depth"] * units_share
                gain = units * (max(quotes) * 0.93 - min(quotes) * 1.07 - 0.10 * (max(quotes) + min(quotes)) / 2)
                total[g] += max(0.0, gain)
        for g in engine.GOODS:
            each[g].append(total[g] - before[g])
    if per_game:
        return each
    return {g: v / games for g, v in total.items()}


def main_ceiling():
    games = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    import pi_economy
    for label, mutate in (("the Pi's economy (25 Nov 2026)", pi_economy.apply), ("shipped prices", None)):
        res = ceiling(games, 120, mutate)
        print("--", label, "(best case over 10 years, one load a month, per captain)")
        for g, v in res.items():
            print("   {:<11} {:>16,.0f}".format(g, v))


def live_like(cfg):
    for g, base in {"opium": 6200, "gold": 3400, "silk": 1520, "porcelain": 850, "arms": 433, "spices": 177,
                    "tea": 99, "rice": 40, "general": 10}.items():
        cfg["goods"][g]["base"] = base


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "ceiling":
    main_ceiling()
