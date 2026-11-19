"""Isolated engine simulations and browser preview: python tools/preview_battle_results.py.

Never loads or writes a saved game. Serves the real result renderer and configured fonts.
"""
import argparse
import copy
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import config
import engine
import strings


def simulate(cfg, seed, choice="fight", armament="guns", scenario="matched"):
    engine.configure(cfg)
    game = engine.Game(seed=seed)
    game.join("Preview Captain", "")
    game.act("p1", {"type": "start"}, present=["p1"])
    player = game.s["players"]["p1"]
    player["ships"] = []
    limits = cfg["rules"]["fleet"]
    for role, limit in (("trader", "max_fleet"), ("escort", "max_escorts"), ("cargo", "max_cargo")):
        kind = max((k for k, v in engine.SHIPS.items() if engine.role_of(k) == role),
                   key=lambda k: (engine.SHIPS[k]["slots"], engine.SHIPS[k]["hold"]))
        for _ in range(limits[limit]):
            spec = engine.SHIPS[kind]
            cannons = spec["slots"] // limits["cannon_slots"] if armament == "cannons" and spec["cannons"] else 0
            ship = game._new_ship(kind, guns=spec["slots"] - cannons * limits["cannon_slots"])
            ship["cannons"] = cannons
            player["ships"].append(ship)
    capacity = game.capacity(player)
    goods = list(engine.GOODS)
    player["cargo"] = {k: capacity // len(goods) + (i < capacity % len(goods)) for i, k in enumerate(goods)}
    player["basis"] = {k: engine.GOODS[k]["base"] for k in goods}
    player["cash"] = 10_000_000
    player["voy"] = {"dest": "manila"}
    game.s["sea"] = {"present": ["p1"], "news": []}
    muster = game._muster(player, "pirates", "manila")
    game._battle_open(player, muster["n"], "pirates", muster)
    before = {"ships": len(player["ships"]), "guns": game.guns(player), "cannons": game.cannons(player),
              "cargo": game.used(player), "capacity": capacity}
    battle = player["battle"]
    # Controlled extremes exercise outcomes a fully armed fleet rarely encounters.
    if scenario in ("wrecked", "plundered", "broke_off"):
        battle["hp"] = [10 ** 9] * battle["n"]
        battle["eg"] = [10000 if scenario == "wrecked" else 1] * battle["n"]
        battle["hit"] = 1 if scenario == "wrecked" else 0
        battle["focus"] = 0
        if scenario == "plundered":
            battle["runs"] = 100
            battle["fast"] = False
            engine.R["pirates"]["run_base"] = 0
            engine.R["pirates"]["run_fast"] = 0
            engine.R["pirates"]["run_round"] = 0
    for _ in range(50):
        if "battle" not in player:
            break
        game._battle_step(player, choice)
    if "battle" in player:
        raise RuntimeError("Preview battle did not finish")
    result = player["fights"][-1]
    result["id"] = f"preview:{seed}:{choice}:{armament}:{scenario}"
    return {"before": before, "result": result, "scenario": scenario}


def fixtures(cfg):
    cases = []
    for armament in ("guns", "cannons"):
        for seed in (1, 7, 23):
            cases.append(simulate(copy.deepcopy(cfg), seed, armament=armament))
    for choice, scenario in (("pay", "matched"), ("retreat", "matched"), ("run", "matched"),
                             ("fight", "wrecked"), ("run", "plundered"), ("fight", "broke_off")):
        cases.append(simulate(copy.deepcopy(cfg), 11, choice, scenario=scenario))
    return cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8877)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    cfg = config.load()
    cases = fixtures(cfg)
    for case in cases:
        f = case["result"]
        print(f"{f['id']}: {f['outcome']}, {f['rounds']} rounds, {len(f['ships'])} ships, "
              f"{len(f['cargo'])} cargo loss lines, net {f['net']}")
    if args.check:
        assert {c["result"]["outcome"] for c in cases} == {
            "won", "away", "retreated", "paid", "wrecked", "plundered", "broke_off"}
        return
    payload = json.dumps({"cases": cases, "strings": strings.resolve(cfg),
                          "ships": cfg["ships"], "goods": cfg["goods"], "currency": cfg["brand"]["currency"]})
    html = '''<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Battle results · isolated simulations</title>
<link rel="stylesheet" href="/style.css"><link rel="stylesheet" href="/deck.css">
<link rel="stylesheet" href="/battle.css"><link rel="stylesheet" href="/fonts/fonts.css"><link rel="stylesheet" href="/preview-theme.css">
<style>#preview-controls{position:fixed;top:0;left:0;z-index:1000;background:#15100c;padding:.3rem;color:#f1e3c5;font:12px system-ui;max-width:100%}#preview-controls select{max-width:65vw} .sf-result{padding-top:3rem}</style>
<body class="player"><nav id="preview-controls"><label>Simulation <select id="cases"></select></label> <span id="size"></span></nav>
<script>const preview=PAYLOAD;const T=preview.strings,D={ships:preview.ships,goods:preview.goods};
const S={voice:{}};const te=(key,vars={})=>(T[key]||key).replace(/\\{(\\w+)\\}/g,(_,k)=>String(vars[k]??''));
const money=n=>preview.currency+Number(n).toLocaleString('en-US');</script>
<script src="/preview-renderer.js"></script><script>
const select=document.getElementById('cases');
preview.cases.forEach((c,i)=>select.add(new Option(c.result.outcome+' · '+c.before.guns+' guns / '+c.before.cannons+' cannons · '+c.scenario+' · seed '+c.result.id.split(':')[1],i)));
function draw(){const c=preview.cases[select.value];Battle.preview(c.result);document.getElementById('size').textContent=c.before.ships+' ships · '+c.before.cargo+' cargo';}
select.onchange=draw;draw();</script>'''.replace("PAYLOAD", payload)

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(ROOT / "web"), **kw)

        def do_GET(self):
            path = self.path.split("?")[0]
            if path == "/preview":
                body, mime = html, "text/html"
            elif path == "/preview-theme.css":
                body, mime = config.theme_css(cfg), "text/css"
            elif path == "/preview-renderer.js":
                body = (ROOT / "web/battle.js").read_text(encoding="utf-8").replace(
                    "return { sync, busy };", '''return { preview(f) {
                      root.hidden=false;root.dataset.mode="result";
                      $(".sf-result").hidden=false;$(".sf-result").innerHTML=reckoningHtml(f,false);
                    }};''')
                mime = "text/javascript"
            else:
                return super().do_GET()
            data = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", mime + "; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    print(f"Preview: http://localhost:{args.port}/preview (no saved game is touched)", flush=True)
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
