"""Game 5 review, Phase 2 (21 Nov 2026): the sell-back price on big buys and the confirm before a sale
runs past the dealers' purse.

The screen's maths lives in web/player.js (the same quote and purse rule as engine.Game). These tests pull
the real functions out of player.js, run them under node on a state taken from a real Game, and check them
against what the engine actually pays when the lot is bought and then sold back."""
import json
import math
import os
import shutil
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
import config  # noqa: E402
import engine  # noqa: E402
from engine import Game, GOODS, R  # noqa: E402

NODE = shutil.which("node")
PLAYER = os.path.join(ROOT, "web", "player.js")
NAMES = ["quote", "purseLeft", "purseCut", "fullSale", "fullSellBack", "sellBackOf", "bigBuy", "backHeat", "pursePast", "buyPast", "sellPast", "needsAsk"]

# Pull named top-level functions out of player.js by matching their braces, and run a JSON list of calls.
RUNNER = r"""
const fs = require('fs'), vm = require('vm');
const src = fs.readFileSync(process.argv[1], 'utf8'), input = JSON.parse(fs.readFileSync(0, 'utf8'));
function grab(name) {
  const at = src.indexOf('\nfunction ' + name + '(');
  if (at < 0) throw new Error('no function ' + name);
  let i = src.indexOf('{', src.indexOf(')', at)), depth = 0;
  for (let j = i; j < src.length; j++) {
    if (src[j] === '{') depth++;
    else if (src[j] === '}' && --depth === 0) return src.slice(at, j + 1);
  }
  throw new Error('unbalanced ' + name);
}
const ctx = { S: input.S, D: input.D, Math, Number, Object };
vm.createContext(ctx);
vm.runInContext(input.names.map(grab).join('\n') + '\nglobalThis.api = { ' + input.names.join(', ') + ' };', ctx);
console.log(JSON.stringify(input.calls.map(([fn, ...args]) => ctx.api[fn](...args))));
"""


def configure(**rules):
    cfg = config.defaults()
    cfg["rules"]["start"]["where"] = "home"
    cfg["rules"]["customs"]["enabled"] = False
    for path, value in rules.items():
        group, key = path.split("__")
        cfg["rules"][group][key] = value
    cfg, errors = config.validate(cfg)
    assert not errors, errors
    engine.configure(cfg)


def new_house(**rules):
    configure(**rules)
    g = Game(seed=11)
    pid = g.pid_for_token(g.join("Ana", "Red Junk"))
    g.act(pid, {"type": "start"}, present=[pid])
    p = g.s["players"][pid]
    p["customs"] = None
    g.capacity = lambda _p: 10 ** 9              # room for any lot: the test is about silver, not the hold
    p["cash"] = 10 ** 12
    return g, p


@pytest.fixture(autouse=True)
def restore_config():
    original = engine.CFG
    yield
    engine.CFG = original
    engine.configure(original)


def screen(g, p):
    """The browser's S and D for this house, built from the engine the same way the server sends them."""
    port = p["port"]
    return ({"me": {"prices": dict(g.s["prices"][port]), "spread": g.spread(p, port), "purse": g.purse_view(port), "ready": False},
             "turn": 1},
            {"impact": R["market"]["impact"], "goods": {k: {"depth": v["depth"], "name": v["name"]} for k, v in GOODS.items()},
             "market": engine.static_data()["market"]})


def run_js(S, D, calls, names=NAMES):
    out = subprocess.run([NODE, "-e", RUNNER, PLAYER], input=json.dumps({"S": S, "D": D, "names": names, "calls": calls}),
                         capture_output=True, text=True, check=True, cwd=HERE)
    return json.loads(out.stdout)


needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")


# ---- settings ------------------------------------------------------------------------------------------
def test_settings_default_and_reach_the_screen():
    configure()
    mk = engine.static_data()["market"]
    assert mk["sellback_depths"] == 0.25 and mk["purse_confirm"] is True
    assert R["market"]["purse_over"] == 0.35, "the overflow rate is left for tuning after real play"
    configure(market__purse_confirm=False, market__sellback_depths=1.5)
    mk = engine.static_data()["market"]
    assert mk["sellback_depths"] == 1.5 and mk["purse_confirm"] is False


def test_old_saved_settings_pick_up_the_new_ones():
    cfg = config.defaults()
    saved = {"rules": {"market": {k: v for k, v in cfg["rules"]["market"].items() if k not in ("sellback_depths", "purse_confirm")}}}
    merged = config._merge(cfg, saved)
    assert merged["rules"]["market"]["sellback_depths"] == 0.25 and merged["rules"]["market"]["purse_confirm"] is True


def test_admin_has_both_fields():
    fields = {f["path"]: f for sec in config.SECTIONS for grp in sec.get("groups", []) for f in grp["fields"]}
    assert fields["rules.market.purse_confirm"]["type"] == "bool"
    assert fields["rules.market.sellback_depths"]["type"] == "num"


# ---- the sell-back price matches what the engine really pays ---------------------------------------------
@needs_node
@pytest.mark.parametrize("purse_depths", [0.75, 0.05, 0.01])
@pytest.mark.parametrize("good", ["opium", "silk", "gold"])
def test_sell_back_matches_a_real_buy_then_sale(purse_depths, good):
    g, p = new_house(market__purse_depths=purse_depths)
    port = p["port"]
    for depths in (0.05, 0.3, 1.0, 3.0):
        qty = max(1, int(GOODS[good]["depth"] * depths))
        S, D = screen(g, p)
        want_cost, want_back = run_js(S, D, [["quote", good, qty, "buy"], ["sellBackOf", good, qty]])
        # the same on the real engine: buy the lot, then ask what selling it straight back pays
        g2, p2 = new_house(market__purse_depths=purse_depths)
        g2.s["prices"][port][good] = g.s["prices"][port][good]
        g2.s["purse"] = json.loads(json.dumps(g.s.get("purse") or {}))
        cost, _ = g2.quote(p2, good, qty, "buy")
        g2.act(p2["id"], {"type": "buy", "good": good, "qty": qty}, present=[p2["id"]])
        back, _ = g2.quote(p2, good, qty, "sell")
        assert want_cost == cost
        # buying earns a little standing, which narrows the dealers' margin a touch: the screen may only be
        # slightly under the engine, never over
        assert want_back <= back + 1, (good, qty, want_back, back)
        assert back - want_back <= max(2, 0.01 * back), (good, qty, want_back, back)


@needs_node
def test_sell_back_is_exact_when_standing_does_not_move_the_margin():
    g, p = new_house(market__spread_swing=0.0)
    port, good = p["port"], "opium"
    qty = 500
    S, D = screen(g, p)
    (want,) = run_js(S, D, [["sellBackOf", good, qty]])
    g.act(p["id"], {"type": "buy", "good": good, "qty": qty}, present=[p["id"]])
    back, _ = g.quote(p, good, qty, "sell")
    assert want == back


@needs_node
def test_a_buy_never_uses_the_purse_up():
    g, p = new_house()
    port, good = p["port"], "opium"
    before = g.purse_left(port, good)
    g.act(p["id"], {"type": "buy", "good": good, "qty": 800}, present=[p["id"]])
    assert g.purse_left(port, good) == before


# ---- which buys are "big", and how red the sell-back is ---------------------------------------------------
@needs_node
def test_big_buy_threshold_follows_the_setting():
    g, p = new_house()
    S, D = screen(g, p)
    depth = GOODS["opium"]["depth"]
    small, edge, big = run_js(S, D, [["bigBuy", "opium", int(depth * 0.25) - 1], ["bigBuy", "opium", int(math.ceil(depth * 0.25))],
                                     ["bigBuy", "opium", depth]])
    assert (small, edge, big) == (False, True, True)
    D["market"]["sellback_depths"] = 2
    assert run_js(S, D, [["bigBuy", "opium", depth]]) == [False]
    assert run_js(S, D, [["bigBuy", "opium", 0]]) == [False]


@needs_node
def test_sell_back_heat_uses_the_trade_bar_lines():
    g, p = new_house()
    S, D = screen(g, p)           # avg_amber 1.5, avg_red 2.5
    ok, amber, red, free = run_js(S, D, [["backHeat", 100, 90], ["backHeat", 100, 60], ["backHeat", 100, 40], ["backHeat", 0, 0]])
    assert (ok, amber, red, free) == ("ok", "amber", "red", "ok")


# ---- the confirm fires exactly when the red warning shows --------------------------------------------------
@needs_node
@pytest.mark.parametrize("purse_depths", [0.75, 0.02])
def test_confirm_asks_exactly_when_the_sale_runs_past_the_purse(purse_depths):
    g, p = new_house(market__purse_depths=purse_depths)
    port, good = p["port"], "opium"
    S, D = screen(g, p)
    qtys = [1, 10, 50, 100, 300, 800, 2000, 4000]
    asks = run_js(S, D, [["pursePast", good, q] for q in qtys])
    for q, ask in zip(qtys, asks):
        total, _ = g.quote(p, good, q, "sell")
        k = R["market"]["impact"] * q / GOODS[good]["depth"]
        mid = g.s["prices"][port][good]
        full = int(math.floor(q * (mid + mid / (1 + k)) / 2 * (1 - g.spread(p, port))))
        assert ask == (total < full), (q, total, full)          # short exactly when the engine cuts the sale
    if purse_depths == 0.02:
        assert any(asks) and not all(asks), "the test lots must cross the purse"


@needs_node
def test_no_purse_rule_means_no_confirm_and_no_cut():
    g, p = new_house(market__purse_enabled=False)
    S, D = screen(g, p)
    assert D["market"]["purse_over"] is None
    ask, cut, back = run_js(S, D, [["pursePast", "opium", 4000], ["purseCut", "opium", 12345], ["sellBackOf", "opium", 500]])
    assert ask is False and cut == 12345 and back > 0


@needs_node
def test_a_sale_inside_a_part_used_purse_is_judged_on_what_is_left():
    g, p = new_house()
    port, good = p["port"], "opium"
    p["cargo"] = {good: 2000}
    g.act(p["id"], {"type": "sell", "good": good, "qty": 600}, present=[p["id"]])       # uses part of the purse
    left = g.purse_left(port, good)
    assert 0 < left < g.purse_size(port, good)
    S, D = screen(g, p)
    qtys = [10, 100, 1000, 1400]
    asks = run_js(S, D, [["pursePast", good, q] for q in qtys])
    sell_total = [g.quote(p, good, q, "sell")[0] for q in qtys]
    full = run_js(S, D, [["fullSale", good, q] for q in qtys])
    assert [a for a in asks] == [t < f for t, f in zip(sell_total, full)]


# ---- Game 6 review (22 Nov 2026): the big-buy confirm ----
@needs_node
def test_buy_confirm_settings_reach_the_screen():
    configure()
    mk = engine.static_data()["market"]
    assert mk["buy_confirm"] is True and mk["buy_confirm_share"] == 0.67
    configure(market__buy_confirm=False, market__buy_confirm_share=0.5)
    mk = engine.static_data()["market"]
    assert mk["buy_confirm"] is False and mk["buy_confirm_share"] == 0.5


@needs_node
def test_a_big_buy_that_sells_back_cheap_asks_and_a_small_one_does_not():
    g, p = new_house()
    port, good = p["port"], "rice"
    S, D = screen(g, p)
    depth = GOODS[good]["depth"]
    big, small = int(depth * 3), max(1, int(depth * 0.02))
    asks = run_js(S, D, [["buyPast", good, big], ["buyPast", good, small], ["needsAsk", {"g": good, "side": "buy", "qty": big}],
                         ["needsAsk", {"g": good, "side": "buy", "qty": small}]])
    assert asks == [True, False, True, False], asks
    # the screen's share is the one the engine pays: bought then sold back.
    cost, back = run_js(S, D, [["quote", good, big, "buy"], ["sellBackOf", good, big]])
    assert back / cost <= 0.67, (cost, back)


@needs_node
def test_buy_confirm_off_or_a_lower_bar_never_asks():
    g, p = new_house(market__buy_confirm=False)
    S, D = screen(g, p)
    big = int(GOODS["rice"]["depth"] * 3)
    assert run_js(S, D, [["buyPast", "rice", big]]) == [False]
    g, p = new_house(market__buy_confirm_share=0.05)
    S, D = screen(g, p)
    assert run_js(S, D, [["buyPast", "rice", big]]) == [False]


@needs_node
def test_sales_still_ask_by_their_own_switch():
    g, p = new_house(market__buy_confirm=False)
    S, D = screen(g, p)
    S["me"]["purse"]["rice"] = [1, 1000]
    assert run_js(S, D, [["needsAsk", {"g": "rice", "side": "sell", "qty": 500}]]) == [True]
    g, p = new_house(market__purse_confirm=False)
    S, D = screen(g, p)
    S["me"]["purse"]["rice"] = [1, 1000]
    assert run_js(S, D, [["needsAsk", {"g": "rice", "side": "sell", "qty": 500}]]) == [False]
