"""Plays full games with bots and checks the rules never break.

Run from the project folder:  python tests/sim_test.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from engine import Game, GameError, GOODS, PORTS, SHIPS  # noqa: E402


def check(game):
    for p in game.s["players"].values():
        assert p["cash"] >= 0, ("negative cash", p["name"], p["cash"])
        assert p["bank"] >= 0 and p["debt"] >= 0
        assert p["ships"], "player with no ship"
        assert game.used(p) <= game.capacity(p), "cargo over capacity"
        assert all(q > 0 for q in p["cargo"].values())
        assert all(sh["hull"] > 0 and 0 <= sh["guns"] <= SHIPS[sh["type"]]["slots"] for sh in p["ships"])
        assert all(0 <= v <= 100 for v in p["rep"].values())
    for port in PORTS:
        for g in GOODS:
            assert game.s["prices"][port][g] > 0
    json.dumps(game.s)  # must always be saveable


def try_act(game, pid, action):
    try:
        game.act(pid, action, present=game.s["order"])
        return True
    except GameError:
        return False


def trader_bot(game, pid, rng):
    """Sells what is dear here, buys what is cheap here, sails to the best market."""
    p = game.s["players"][pid]
    here = p["port"]
    for g, q in list(p["cargo"].items()):
        if game.s["prices"][here][g] > GOODS[g]["base"] * 1.05:
            try_act(game, pid, {"type": "sell", "good": g, "qty": q})
    if here == "hongkong":
        if p["debt"] > 0 and p["cash"] > 6000:
            try_act(game, pid, {"type": "loan", "op": "repay", "amount": int(p["cash"] - 4000)})
        if p["protect"] <= 2 and p["cash"] > 4 * game.protection_cost(p):
            try_act(game, pid, {"type": "protection"})
    try_act(game, pid, {"type": "repair", "index": "all"})
    if PORTS[here]["shipyard"] and p["cash"] > 30000:
        try_act(game, pid, {"type": "buy_ship", "ship": "barque" if p["cash"] > 60000 else "lorcha"})
    for i in range(len(p["ships"])):
        if p["cash"] > 5000:
            try_act(game, pid, {"type": "buy_gun", "index": i})
    best = None
    for g, spec in GOODS.items():
        ratio = game.s["prices"][here][g] / spec["base"]
        if best is None or ratio < best[1]:
            best = (g, ratio)
    g = best[0]
    room = game.capacity(p) - game.used(p)
    qty = room
    while qty > 0 and game.quote(p, g, qty, "buy")[0] > p["cash"] * 0.9:
        qty = int(qty * 0.7)
    if qty > 0:
        try_act(game, pid, {"type": "buy", "good": g, "qty": qty})
    dests = [k for k in PORTS if k != here]
    dest = max(dests, key=lambda k: PORTS[k]["mods"].get(g, 1.0) + rng.random() * 0.2)
    assert try_act(game, pid, {"type": "sail", "dest": dest, "orders": rng.choice(["fight", "run"])})


def random_bot(game, pid, rng):
    """Presses every button with nonsense to make sure nothing breaks."""
    p = game.s["players"][pid]
    for _ in range(12):
        action = rng.choice([
            {"type": "buy", "good": rng.choice(list(GOODS)), "qty": rng.randint(1, 400)},
            {"type": "sell", "good": rng.choice(list(GOODS)), "qty": rng.randint(1, 400)},
            {"type": "bank", "op": rng.choice(["deposit", "withdraw"]), "amount": rng.randint(1, 90000)},
            {"type": "loan", "op": rng.choice(["borrow", "repay"]), "amount": rng.randint(1, 90000)},
            {"type": "warehouse", "op": rng.choice(["store", "take"]), "good": rng.choice(list(GOODS)),
             "qty": rng.randint(1, 300)},
            {"type": "buy_ship", "ship": rng.choice(list(SHIPS))},
            {"type": "sell_ship", "index": rng.randint(0, 5)},
            {"type": "buy_gun", "index": rng.randint(0, 5)},
            {"type": "repair", "index": rng.choice(["all", 0, 1, 7])},
            {"type": "protection"},
            {"type": "buy", "good": "nonsense", "qty": "abc"},
            {"type": "sell", "good": "tea", "qty": -5},
        ])
        try_act(game, pid, action)
        check(game)
    dest = rng.choice(list(PORTS) + [None])
    assert try_act(game, pid, {"type": "sail", "dest": dest, "orders": rng.choice(["fight", "run"])})
    assert p["ready"]


def play(seed, years=5):
    game = Game(seed=seed)
    rng = game.rng
    bots = {}
    for i, (name, bot) in enumerate([("Ada", trader_bot), ("Bao", trader_bot),
                                     ("Cy", random_bot), ("Dee", random_bot)]):
        token = game.join(name, "")
        bots[game.pid_for_token(token)] = bot
    host = game.s["order"][0]
    game.act(host, {"type": "settings", "years": years}, present=game.s["order"])
    game.act(host, {"type": "start"}, present=game.s["order"])
    while game.s["phase"] == "port":
        turn = game.s["turn"]
        for pid, bot in bots.items():
            bot(game, pid, rng)
        assert game.maybe_advance(set(game.s["order"])), "turn did not advance"
        assert game.s["turn"] == turn + 1
        check(game)
        game = Game(state=json.loads(json.dumps(game.s)), seed=seed * 1000 + turn)  # save/load round trip
        rng = game.rng
        for pid in bots:
            game.view(pid, game.s["order"])
        game.view(None, [])
    assert game.s["phase"] == "ended"
    return {p["name"]: (int(game.worth(p)), len(p["ships"]), p["wrecks"]) for p in game.s["players"].values()}


if __name__ == "__main__":
    results = [play(seed) for seed in range(1, 41)]
    for name in ("Ada", "Bao", "Cy", "Dee"):
        worths = sorted(r[name][0] for r in results)
        wrecks = sum(r[name][2] for r in results)
        print("{:4s} median worth {:>12,}  min {:>12,}  max {:>14,}  wrecks {}".format(
            name, worths[len(worths) // 2], worths[0], worths[-1], wrecks))
    print("OK: {} full games played without a rule violation".format(len(results)))
