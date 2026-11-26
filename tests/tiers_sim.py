"""Cargo Tiers balance sweep (phase 8, 25 Nov 2026): the four bots of sim10.py play whole games with the tiers on
and off, on the shipped rank ladder or on a "live" ladder, and the report shows where the money came from.

    python tests/tiers_sim.py [games] [years] [ladder] [on|off|both]
        ladder: shipped | pi | live
            shipped = the shipped defaults; pi = the Pi's whole economy as read on 25 Nov 2026 (tests/pi_economy.py:
            its cargo, market rules, port multipliers, Merchant $10M, Prince $50M); live = shipped economy with an
            older guess at the ladder (Merchant $1M, Prince $6M)

The bots are told to trade only their own table (sim10's own bots pick from every cargo).
"""
import collections
import copy
import os
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sim10  # noqa: E402
import pi_economy  # noqa: E402
import config  # noqa: E402
import engine  # noqa: E402

LIVE = {"merchant": 1_000_000, "senior_merchant": 3_000_000, "merchant_prince": 6_000_000, "taipan": 15_000_000,
        "tai_pan_china_seas": 40_000_000, "merchant_lord": 100_000_000, "hong_master": 250_000_000}
LUX = ("camphor", "sandalwood", "ginseng", "jade", "pearls", "ambergris")


def build(ladder, on, mutate=None):
    cfg = copy.deepcopy(config.defaults())
    cfg["rules"]["tiers"]["enabled"] = on
    if ladder == "pi":
        pi_economy.apply(cfg)
    if ladder == "live":
        for r in cfg["ranks"]:
            if r["id"] in LIVE:
                r["worth"] = LIVE[r["id"]]
        cfg["ranks"].sort(key=lambda r: r["worth"])
    cfg["rules"]["customs"]["enabled"] = False          # sim10's bots stall on the verdict screen; not what is measured here
    if mutate:
        mutate(cfg)
    cfg["rules"]["tiers"]["enabled"] = on               # last, so a fixture that switches the tiers on cannot win
    engine.TIERS_READY = True
    engine.configure(cfg)


def patch_bots():
    old_plan, old_est = sim10.Bot.plan, sim10.Bot.est_price

    def plan(self, goods_ok=None, budget_share=0.92):
        table = engine.table_of(self.p)
        here = self.p["port"]
        ok = [g for g in (goods_ok if goods_ok is not None else engine.GOODS)
              if g in table and g in self.g.s["prices"][here]]
        return old_plan(self, goods_ok=ok or list(table), budget_share=budget_share)

    def est(self, port, g):
        if not engine.sold_here(port, g):
            return 0.0                              # a port that does not trade it is no market
        k = self.p["known"].get(port)
        if k and g not in (k.get("prices") or {}):
            return engine.GOODS[g]["base"] * engine.PORTS[port]["mods"].get(g, 1.0)
        return old_est(self, port, g)

    def sell_all_good(self, threshold=1.0):
        # sim10 predates Forbidden Cargo: the real screen has no price for a cargo this port does not trade
        p, here = self.p, self.p["port"]
        for g, q in list(p["cargo"].items()):
            if g not in self.g.s["prices"][here] or self.g.sealed(p, g) >= q:
                continue
            price = self.g.s["prices"][here][g]
            best_else = max(self.est_price(k, g) for k in engine.PORTS if k != here)
            if price >= best_else * threshold * 0.85 or price > engine.GOODS[g]["base"] * 1.4:
                self.act({"type": "sell", "good": g, "qty": q - self.g.sealed(p, g)})

    sim10.Bot.plan, sim10.Bot.est_price, sim10.Bot.sell_all_good = plan, est, sell_all_good

    # a bot in the cells serves its time (sim10 left this to the host); a cargo that is no longer sold is skipped
    for cls in sim10.BOTS:
        def wrap(cls=cls, inner=cls.turn):
            def turn(self):
                if self.p.get("jail"):
                    self.act({"type": "jail_serve"})
                    return
                try:
                    inner(self)
                except engine.GameError:
                    pass
            return turn
        cls.turn = wrap()


def one(seed, years):
    game, bots, events, history, crashes = sim10.play(seed, years=years)
    out = {"crashes": len(crashes), "bots": {}, "good": collections.defaultdict(lambda: [0, 0.0, 0.0])}
    for e in events:
        if e.get("cat") == "trade" and e.get("type") in ("buy", "sell"):
            row = out["good"][e.get("good")]
            row[0 if e["type"] == "buy" else 1] += 1
            amount = e.get("total")
            row[2 if e["type"] == "sell" else 2] += 0
            out.setdefault("amt", collections.defaultdict(float))[(e.get("good"), e["type"])] += float(amount or 0)
    for b in bots.values():
        p = game.s["players"][b.pid]
        steps = [(r["turn"], r["to"]) for r in (p.get("tier_steps") or [])]
        out["bots"][b.name] = {"worth": int(game.worth(p)), "tier": p.get("tier", 0), "steps": steps}
    return out


def report(label, runs):
    print("==", label, len(runs), "games")
    worth = [b["worth"] for r in runs for b in r["bots"].values()]
    print("  worth  median {:>14,} mean {:>14,} max {:>14,}".format(int(st.median(worth)), int(st.mean(worth)), max(worth)))
    for name in sorted(runs[0]["bots"]):
        w = [r["bots"][name]["worth"] for r in runs]
        s1 = [t for r in runs for t, to in r["bots"][name]["steps"] if to >= 1]
        s2 = [t for r in runs for t, to in r["bots"][name]["steps"] if to >= 2]
        print("  {:<4} median {:>13,} max {:>14,}   tier1 at month {} ({}/{})  tier2 at month {} ({}/{})".format(
            name, int(st.median(w)), max(w), int(st.median(s1)) if s1 else "-", len(s1), len(runs),
            int(st.median(s2)) if s2 else "-", len(s2), len(runs)))
    amt = collections.defaultdict(float)
    for r in runs:
        for k, v in (r.get("amt") or {}).items():
            amt[k] += v
    goods = sorted({g for g, _ in amt}, key=lambda g: list(engine.GOODS).index(g) if g in engine.GOODS else 99)
    print("  net trading by cargo (sold minus bought, all games):")
    for g in goods:
        print("    {:<11} bought {:>16,.0f}  sold {:>16,.0f}  net {:>16,.0f}".format(
            g, amt[(g, "buy")], amt[(g, "sell")], amt[(g, "sell")] - amt[(g, "buy")]))
    print("  crashes", sum(r["crashes"] for r in runs))


def main():
    games = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    years = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    ladder = sys.argv[3] if len(sys.argv) > 3 else "shipped"
    mode = sys.argv[4] if len(sys.argv) > 4 else "both"
    patch_bots()
    for on in ((False, True) if mode == "both" else (mode == "on",)):
        build(ladder, on)
        report("{} ladder, tiers {}, {} years".format(ladder, "ON" if on else "off", years),
               [one(seed, years) for seed in range(1, games + 1)])


if __name__ == "__main__":
    main()
