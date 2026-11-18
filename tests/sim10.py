"""Ten-year, four-captain playtest of Crimson Ledger (SeaTrader).

Four bots with different temperaments play a full 10-year game through the real engine
(the same actions the player screen sends), and every engine event is captured for review.

    python tests/sim10.py [seed]          one game, final standings
    python tests/sim10_report.py [games]  many games, balance report
"""
import collections
import json
import math
import os
import random
import sys
import traceback

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
import engine  # noqa: E402
from engine import Game, GameError, GOODS, PORTS, SHIPS  # noqa: E402


def setup():
    with open(os.path.join(ROOT, "config", "settings.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    engine.configure(cfg)


class Bot:
    name = "?"
    style = "?"

    def __init__(self, game, pid, rng):
        self.g, self.pid, self.rng = game, pid, rng
        self.refused = collections.Counter()
        self.refused_msgs = collections.Counter()
        self.counts = collections.Counter()

    @property
    def p(self):
        return self.g.s["players"][self.pid]

    def act(self, a):
        try:
            self.g.act(self.pid, a, present=self.g.s["order"])
            self.counts[a["type"]] += 1
            return True
        except GameError as e:
            self.refused[a["type"]] += 1
            self.refused_msgs[(a["type"], str(e)[:90])] += 1
            return False

    # ---- knowledge: what a captain at the screen could know -------------------------------
    def est_price(self, port, g):
        """Last seen price there if seen within a year, else the port's usual level."""
        k = self.p["known"].get(port)
        usual = GOODS[g]["base"] * PORTS[port]["mods"].get(g, 1.0)
        if k and self.g.s["turn"] - k["turn"] <= 12:
            seen = k["prices"][g]
            age = self.g.s["turn"] - k["turn"]
            w = max(0.2, 1 - age * 0.15)
            return w * seen + (1 - w) * usual
        return usual

    def home(self):
        return engine.home_of(self.p)

    # ---- the Port Authority ---------------------------------------------------------------
    def declare_share(self):
        return 1.0

    def customs(self):
        p = self.p
        cu = p.get("customs")
        if not cu:
            return
        if cu["status"] == "declare":
            share = self.declare_share()
            vals = {ln["good"]: int(ln["value"] * share) for ln in cu["lines"]}
            sealed = self.seal_list(cu)
            bribe = self.bribe(cu)
            a = {"type": "customs_declare", "values": vals}
            if sealed:
                a["sealed"] = sealed
            if bribe:
                a["bribe"] = True
            if not self.act(a):
                self.act({"type": "customs_declare", "values": {}})
        cu = p.get("customs")
        if cu and cu["status"] == "verdict":
            for r in cu["result"]["lines"]:
                if r["units"] and not r.get("back"):
                    cost = self.g.buyback_cost(r)
                    if cost < p["cash"] * 0.4 and self.rng.random() < 0.5:
                        self.act({"type": "customs_buyback", "good": r["good"]})
        if p.get("customs"):
            self.act({"type": "customs_done"})

    def seal_list(self, cu):
        return []

    def bribe(self, cu):
        return False

    # ---- trading ------------------------------------------------------------------------------
    def sell_all_good(self, threshold=1.0):
        p, here = self.p, self.p["port"]
        for g, q in list(p["cargo"].items()):
            if self.g.sealed(p, g) >= q:
                continue
            price = self.g.s["prices"][here][g]
            best_else = max(self.est_price(k, g) for k in PORTS if k != here)
            if price >= best_else * threshold * 0.85 or price > GOODS[g]["base"] * 1.4:
                self.act({"type": "sell", "good": g, "qty": q - self.g.sealed(p, g)})

    def plan(self, goods_ok=None, budget_share=0.92):
        """Best (good, dest, qty) by expected profit per trip."""
        p, here = self.p, self.p["port"]
        room = self.g.capacity(p) - self.g.used(p)
        best = None
        for g in GOODS:
            if goods_ok and g not in goods_ok:
                continue
            buy = self.g.s["prices"][here][g]
            for dest in PORTS:
                if dest == here:
                    continue
                if g in self.g.banned(dest):
                    continue
                sell = self.est_price(dest, g)
                margin = sell * 0.92 - buy * 1.05
                if margin <= 0:
                    continue
                qty = room
                cash = p["cash"] * budget_share
                if qty <= 0:
                    continue
                qty = min(qty, int(cash / (buy * 1.1)) if buy > 0 else 0)
                qty = min(qty, int(GOODS[g]["depth"] * 0.8))
                if qty <= 0:
                    continue
                risk = engine.distance(here, dest) / 300.0
                score = margin * qty / (1 + risk)
                if best is None or score > best[0]:
                    best = (score, g, dest, qty)
        return best

    def buy(self, g, qty):
        p = self.p
        while qty > 0 and self.g.quote(p, g, qty, "buy")[0] > p["cash"] * 0.97:
            qty = int(qty * 0.85)
        if qty > 0:
            return self.act({"type": "buy", "good": g, "qty": qty})
        return False

    # ---- fleet --------------------------------------------------------------------------------
    def repair(self):
        p = self.p
        if any(sh["hull"] < SHIPS[sh["type"]]["hull"] for sh in p["ships"]):
            self.act({"type": "repair", "index": "all"})

    def maybe_ship(self, kinds, keep):
        p = self.p
        if not PORTS[p["port"]]["shipyard"] or len(p["ships"]) >= engine.R["fleet"]["max_fleet"]:
            return
        for k in kinds:
            if p["cash"] > SHIPS[k]["price"] + keep:
                if self.act({"type": "buy_ship", "ship": k}):
                    return

    def guns_up(self, keep, max_per_ship=None):
        p = self.p
        for i, sh in enumerate(p["ships"]):
            cap = SHIPS[sh["type"]]["slots"] if max_per_ship is None else min(max_per_ship, SHIPS[sh["type"]]["slots"])
            while sh["guns"] < cap and p["cash"] > keep + engine.R["fleet"]["gun_price"]:
                if not self.act({"type": "buy_gun", "index": i}):
                    break

    # ---- home business ---------------------------------------------------------------------------
    def at_home(self):
        return self.p["port"] == self.home()

    def bank_here(self):
        return engine.port_has(self.p, self.p["port"], "bank")

    def banking(self, keep):
        p = self.p
        if self.bank_here() and p["cash"] > keep * 1.5:
            self.act({"type": "bank", "op": "deposit", "amount": int(p["cash"] - keep)})
        elif self.bank_here() and p["cash"] < keep * 0.5 and p["bank"] > 0:
            self.act({"type": "bank", "op": "withdraw", "amount": int(min(p["bank"], keep - p["cash"]))})

    def battle(self, v):
        return "fight" if v["can_fight"] else "run"

    def sail(self, dest):
        self.act({"type": "sail", "dest": dest, "orders": self.orders})

    orders = "fight"

    def rescue(self):
        """Out of silver with one big ship: trade her down at a shipyard (or sail for the nearest yard)."""
        p = self.p
        offer = self.g.trade_down_offer(p)
        if not offer or p["cash"] + p["bank"] >= 1000:
            return False
        self.customs()
        if PORTS[p["port"]]["shipyard"]:
            for g, q in list(p["cargo"].items()):
                if self.g.used(p) > offer["hold"]:
                    self.act({"type": "sell", "good": g, "qty": q - self.g.sealed(p, g)})
            if self.act({"type": "trade_down"}):
                self.counts["rescued"] += 1
                return False          # back in business: carry on with a normal turn
            return False
        yards = [k for k in PORTS if PORTS[k]["shipyard"]]
        self.sail(min(yards, key=lambda k: engine.distance(p["port"], k)))
        return True

    def turn(self):
        raise NotImplementedError


class Merchant(Bot):
    """Careful trader: honest declarations, protection, repays debt, steady upgrades."""
    name, style = "Ada", "careful merchant"
    orders = "run"

    def turn(self):
        p = self.p
        self.customs()
        self.sell_all_good()
        self.repair()
        if self.at_home():
            if p["debt"] > 0 and p["cash"] > 4000:
                self.act({"type": "loan", "op": "repay", "amount": int(min(p["debt"] + 1, p["cash"] - 3000))})
            if p["protect"] <= 2 and p["cash"] > 3 * self.g.protection_cost(p):
                self.act({"type": "protection"})
        if self.bank_here() and p["bank"] > 0 and p["cash"] < 30000:
            self.act({"type": "bank", "op": "withdraw", "amount": int(min(p["bank"], 30000 - p["cash"]))})
        self.maybe_ship(["barque", "lorcha"], keep=25000)
        self.guns_up(keep=20000, max_per_ship=4)
        if self.rng.random() < 0.15 and p["cash"] > 20000:
            gv = self.g.gift_view(p)
            if not gv["given"] and gv["max"] >= gv["min"]:
                self.act({"type": "gift", "amount": max(gv["min"], int(gv["max"] * 0.3) // 50 * 50)})
        plan = self.plan(goods_ok=[g for g in GOODS if not GOODS[g].get("contraband")])
        if plan:
            _, g, dest, qty = plan
            self.buy(g, qty)
            if self.bank_here() and p["cash"] > 60000:
                self.act({"type": "bank", "op": "deposit", "amount": int(p["cash"] - 40000)})
            self.sail(dest)
        else:
            self.sail(self.rng.choice([k for k in PORTS if k != p["port"]]))

    def battle(self, v):
        if v["stage"] == "parley" and v["can_pay"] and v["price"] < self.p["cash"] * 0.25:
            return "pay"
        return "run"


class Smuggler(Bot):
    """Opium and gold, shaves declarations, bribes the odd officer, seals cargo in bond."""
    name, style = "Bao", "smuggler"
    orders = "run"

    def declare_share(self):
        return self.rng.choice([0.4, 0.55, 0.7, 0.85])

    def bribe(self, cu):
        return self.rng.random() < 0.25 and sum(ln["value"] for ln in cu["lines"]) > 30000

    def seal_list(self, cu):
        # Seal what isn't worth selling here (bound for a better market).
        here = self.p["port"]
        out = []
        for ln in cu["lines"]:
            g = ln["good"]
            if self.g.s["prices"][here][g] < max(self.est_price(k, g) for k in PORTS if k != here) * 0.8:
                out.append(g)
        return out

    def turn(self):
        p = self.p
        self.customs()
        self.sell_all_good(threshold=0.95)
        self.repair()
        if self.at_home():
            if p["debt"] > 0 and p["cash"] > 15000:
                self.act({"type": "loan", "op": "repay", "amount": int(min(p["debt"] + 1, p["cash"] - 10000))})
            if p["protect"] <= 1 and p["cash"] > 5 * self.g.protection_cost(p):
                self.act({"type": "protection"})
        self.maybe_ship(["clipper", "lorcha"], keep=40000)
        self.guns_up(keep=30000, max_per_ship=6)
        self.banking(keep=40000)
        plan = self.plan(goods_ok=["opium", "gold", "silk"]) or self.plan()
        if plan:
            _, g, dest, qty = plan
            self.buy(g, qty)
            self.sail(dest)
        else:
            self.sail(self.rng.choice([k for k in PORTS if k != p["port"]]))

    def battle(self, v):
        if v["stage"] == "parley" and v["can_pay"] and v["price"] < self.p["cash"] * 0.15:
            return "pay"
        if v["moods"]["run"] != "grim":
            return "run"
        return "fight" if v["can_fight"] else "retreat"


class Speculator(Bot):
    """Borrows hard, chases booms and crashes from the news, keeps warehouses in other ports."""
    name, style = "Cy", "leveraged speculator"
    orders = "fight"

    def turn(self):
        p, s = self.p, self.g.s
        self.customs()
        here = p["port"]
        # Windfalls: a crash here is a lottery buy; a boom here is a dump.
        for w in s.get("windfalls", []):
            if w["port"] == here and w["kind"] == "boom":
                for g, q in list(p["cargo"].items()):
                    if g == w["good"]:
                        self.act({"type": "sell", "good": g, "qty": q - self.g.sealed(p, g)})
                if self.g._store_here(p) and self.g._store_here(p)["goods"].get(w["good"]):
                    self.act({"type": "sell", "src": "all", "good": w["good"], "qty": 1})
        self.sell_all_good()
        self.repair()
        if self.at_home():
            c = self.g.collectors(p)
            if c and c["calls_in"] and p["cash"] > c["to_clear"] + 5000:
                self.act({"type": "loan", "op": "repay", "amount": c["to_clear"] + 1})
            elif p["cash"] < 80000 and s["turn"] < 100:
                self.act({"type": "loan", "op": "borrow", "amount": 50000})
            elif s["turn"] >= 96 and p["debt"] > 0:
                self.act({"type": "loan", "op": "repay", "amount": int(min(p["debt"] + 1, p["cash"]))})
        # Open a warehouse at a warehouse port that isn't home, once rich enough.
        if engine.port_has(p, here, "warehouse") and here != self.home() and here not in engine.depots_of(p) \
                and p["cash"] > 60000:
            self.act({"type": "depot", "op": "open"})
        store = self.g._store_here(p)
        if store:
            # store cheap goods ashore, take dear goods back aboard to sell
            for g in list(store["goods"]):
                if s["prices"][here][g] > GOODS[g]["base"] * PORTS[here]["mods"].get(g, 1.0) * 1.3:
                    self.act({"type": "warehouse", "op": "take", "good": g, "qty": store["goods"][g]})
                    self.act({"type": "sell", "good": g, "qty": p["cargo"].get(g, 0)})
            crash = [w for w in s.get("windfalls", []) if w["port"] == here and w["kind"] == "crash"]
            for w in crash:
                g = w["good"]
                qty = min(store["cap"] - sum(store["goods"].values()), int(p["cash"] * 0.5 / max(1, s["prices"][here][g])))
                if qty > 0 and self.buy(g, qty):
                    self.act({"type": "warehouse", "op": "store", "good": g, "qty": p["cargo"].get(g, 0)})
        self.maybe_ship(["indiaman", "barque"], keep=30000)
        self.guns_up(keep=25000, max_per_ship=3)
        # Chase booms seen in the news: sail cargo there.
        target = None
        for w in s.get("windfalls", []):
            if w["kind"] == "boom" and w["port"] != here and w["turns"] >= 2:
                target = w
        if target:
            g = target["good"]
            qty = self.g.capacity(p) - self.g.used(p)
            if g not in self.g.banned(target["port"]):
                self.buy(g, min(qty, int(GOODS[g]["depth"])))
            self.sail(target["port"])
            return
        plan = self.plan(budget_share=0.98)
        if plan:
            _, g, dest, qty = plan
            self.buy(g, qty)
            self.sail(dest)
        else:
            self.sail(self.rng.choice([k for k in PORTS if k != here]))

    def battle(self, v):
        return "fight" if v["can_fight"] else "run"


class Admiral(Bot):
    """Guns first: big armed fleet, never pays tribute, sometimes skips protection."""
    name, style = "Dee", "gunboat admiral"
    orders = "fight"

    def declare_share(self):
        return 0.9

    def turn(self):
        p = self.p
        self.customs()
        self.sell_all_good()
        self.repair()
        if self.at_home():
            if p["debt"] > 0 and p["cash"] > 8000:
                self.act({"type": "loan", "op": "repay", "amount": int(min(p["debt"] + 1, p["cash"] - 6000))})
            if self.g.s["turn"] < 6 and p["debt"] < 15000:
                self.act({"type": "loan", "op": "borrow", "amount": 10000})
        self.guns_up(keep=8000)
        self.maybe_ship(["barque", "lorcha"], keep=15000)
        self.banking(keep=50000)
        plan = self.plan()
        if plan:
            _, g, dest, qty = plan
            self.buy(g, qty)
            self.sail(dest)
        else:
            self.sail(self.rng.choice([k for k in PORTS if k != p["port"]]))

    def battle(self, v):
        if not v["can_fight"]:
            return "retreat" if v["moods"]["run"] == "grim" else "run"
        if v["moods"]["fight"] == "grim" and v["left"] > 8:
            return "retreat"
        return "fight"


BOTS = [Merchant, Smuggler, Speculator, Admiral]


def play(seed, years=10, verbose=False):
    rng = random.Random(seed * 7919)
    game = Game(seed=seed)
    events = []
    game.on_event = events.append
    bots = {}
    for cls in BOTS:
        tok = game.join(cls.name, "House of " + cls.name)
        pid = game.pid_for_token(tok)
        bots[pid] = cls(game, pid, rng)
    host = game.s["order"][0]
    game.act(host, {"type": "settings", "years": years}, present=game.s["order"])
    game.act(host, {"type": "start"}, present=game.s["order"])
    history = collections.defaultdict(list)
    crashes = []
    stuck = 0
    while game.s["phase"] in ("port", "sea"):
        t = game.s["turn"]
        for pid, bot in bots.items():
            try:
                if bot.rescue():
                    continue
                bot.turn()
            except Exception:
                crashes.append(("turn", t, bot.name, traceback.format_exc()))
            if not game.s["players"][pid]["ready"]:
                bot.act({"type": "sail", "dest": None})
        try:
            game.maybe_advance(set(game.s["order"]))
        except Exception:
            crashes.append(("advance", t, "", traceback.format_exc()))
            break
        guard = 0
        while game.s["phase"] == "sea" and guard < 500:
            guard += 1
            for pid, bot in bots.items():
                p = game.s["players"][pid]
                if p.get("battle") is None:
                    continue
                v = game.battle_view(p)
                if v is None:
                    game.act(pid, {"type": "sea", "choice": "skip"}, game.s["order"])
                    continue
                ch = bot.battle(v)
                if ch == "pay" and not v["can_pay"]:
                    ch = "run"
                if ch == "fight" and not v["can_fight"]:
                    ch = "run"
                try:
                    game.act(pid, {"type": "sea", "choice": ch}, game.s["order"])
                    bot.counts["sea_" + ch] += 1
                except GameError as e:
                    bot.refused_msgs[("sea_" + ch, str(e)[:90])] += 1
                    game.act(pid, {"type": "sea", "choice": "auto"}, game.s["order"])
        if game.s["turn"] == t:
            stuck += 1
            if stuck > 3:
                crashes.append(("stuck", t, "", "turn did not advance"))
                break
        else:
            stuck = 0
        for pid, bot in bots.items():
            p = game.s["players"][pid]
            history[bot.name].append({"turn": game.s["turn"], "worth": int(game.worth(p)), "cash": int(p["cash"]),
                                      "bank": int(p["bank"]), "debt": int(p["debt"]), "ships": len(p["ships"]),
                                      "hold": game.capacity(p), "guns": game.guns(p), "port": p["port"],
                                      "rep_home": round(p["rep"][engine.home_of(p)], 1)})
        # save / load round trip each month, as the server does
        state = json.loads(json.dumps(game.s))
        g2 = Game(state=state, seed=seed * 1000 + t)
        g2.on_event = events.append
        for bot in bots.values():
            bot.g = g2
        game = g2
    return game, bots, events, history, crashes


if __name__ == "__main__":
    setup()
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    game, bots, events, history, crashes = play(seed)
    for b in bots.values():
        p = game.s["players"][b.pid]
        print(b.name, b.style, "home", engine.home_of(p), "worth", int(game.worth(p)), "ships", len(p["ships"]),
              "wrecks", p["wrecks"])
    print("crashes", len(crashes))
    for c in crashes[:5]:
        print(c)
