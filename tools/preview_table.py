"""Preview the real Table UI with disposable scenes and the live gallery; never opens a saved game."""
import argparse
import copy
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import time
from urllib.parse import parse_qs, unquote, urlparse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import config
import engine
import harbor_view


def journey_sample():
    cfg = config.defaults()
    cfg["rules"]["start"]["where"] = "home"
    cfg["rules"]["weather"]["storm_chance"] = [0, 0, 0, 0]
    cfg["rules"]["weather"]["offcourse"] = 0
    cfg["rules"]["pirates"]["chance"] = 0
    cfg["rules"]["liyuen"]["chance"] = 0
    engine.configure(cfg)
    game = engine.Game(seed=19)
    game.join("Anthony", "")
    game.admin("start", {})
    p = game.s["players"]["p1"]
    p["cash"] = 100000
    game.act("p1", {"type":"buy", "good":"tea", "qty":20}, present=["p1"])
    rows = []
    game.on_event = lambda e: rows.append(copy.deepcopy(e))
    game.act("p1", {"type":"sail", "dest":"singapore", "orders":"run"}, present=["p1"])
    game.maybe_advance({"p1"})
    game.fight_out({"p1"})
    values = {ln["good"]: ln["value"] for ln in p["customs"]["lines"]}
    game.act("p1", {"type":"customs_declare", "values":values}, present=["p1"])
    game.act("p1", {"type":"customs_done"}, present=["p1"])
    events = []
    for e in rows:
        if e["type"] not in ("sailed", "arrived", "customs_open", "customs_declare"):
            continue
        row = {"n":len(events)+1, "pid":"p1", "turn":e["turn"], "type":e["type"],
               "port":e.get("port"), "origin":e.get("origin"), "dest":e.get("dest"),
               "text":e.get("result") or e["msg"], "report":e.get("table_report"),
               "focus":e.get("table_focus"), "welcome":e.get("welcome"), "date":engine.date_label(e["turn"])}
        key = {"sailed":"gm.departure", "arrived":"gm.arrival", "customs_declare":"gm.customs_clear"}.get(e["type"])
        if key:
            row["bridge"] = {"text":engine.tx(key, port=engine.PORTS[e.get("dest") or e.get("port")]["name"])}
        if e["type"] == "sailed":
            row["narration"] = {"text":engine.tx("l.table_underway", port=engine.PORTS[e["dest"]]["name"])}
        events.append(row)
    return game, events


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gallery", required=True)
    ap.add_argument("--port", type=int, default=18884)
    ap.add_argument("--bind", default="127.0.0.1")
    args = ap.parse_args()
    gallery = args.gallery.rstrip("/")
    cache = {}

    def remote(path):
        if path not in cache:
            with urllib.request.urlopen(gallery + path, timeout=15) as response:
                cache[path] = (response.read(), response.headers.get("Content-Type", "application/octet-stream"))
        return cache[path]

    info = json.loads(remote("/api/info")[0])
    info["voice"]["enabled"] = False
    engine.configure(config.defaults())
    game = engine.Game(seed=19)
    game.join("Anthony", "")
    game.admin("start", {})
    p = game.s["players"]["p1"]
    p.update(firm="House Bombay", port="hongkong", cash=84600, bank=200000, debt=0)
    game.s["turn"] = 5
    snapshot = game.view("p1", ["p1"])
    snapshot.update(game_id="table-preview", cfg=info["cfg"], date="June 1860")
    base = harbor_view.view(game, ["p1"], snapshot)
    base.update(game_id="table-preview", voice={}, version=1)
    for key in ("gm.welcome", "gm.ask_sail", "gm.ask_battle", "gm.return", "gm.storm", "gm.finale", "gm.month_open.2"):
        base.setdefault("host", {})[key] = {"text": engine.tx(key, name="Anthony"), "clip": None}

    def fixture(kind, elapsed):
        feed = copy.deepcopy(base)
        f, s = feed["focus"], feed["state"]
        feed["events"] = []
        f["customs"] = None
        f["jail"] = None
        if kind in ("journey", "voyage"):
            feed["events"] = copy.deepcopy(journey_events) if elapsed >= 2 else []
            for e in feed["events"]:
                e["at"] = int(time.time() * 1000)
            if elapsed >= 2:
                f.update(port="singapore", customs=None)
                s["players"][0]["port"] = "singapore"
        elif kind == "battle-result":
            if elapsed >= 2:
                feed["events"] = [{"n":1, "pid":"p1", "turn":5, "type":"battle_result", "port":"manila", "report":fight_sample}]
        elif kind == "storm":
            f["storm"] = {"id": 1, "turn": 5, "band": "heavy", "card": True, "typhoon": False,
                          "lines": {"open": "storm.open.heavy.0", "close":"storm.close.0"}, "hull_lost": 24, "hull_full": 100,
                          "cargo_cost": 4600, "landing": {"port": "singapore"}}
        elif kind == "customs":
            f["customs"] = {"status": "declare", "turn":5, "port":"hongkong", "officer": "officer_hongkong", "welcome": "Declare what's in your hold, darling. All of it."}
        elif kind == "battle":
            s["phase"] = "sea"
            f["battle"] = {"kind": "pirates", "enemy": "Pirate junks", "left": 4, "n": 6, "round": 3,
                           "step": 2, "stage": "fight", "tell": "The enemy closes through the smoke.",
                           "beat": {"frames": [{"say": "That's how you kiss a junk goodbye.", "cap":"A broadside through the smoke", "moment": "broadside", "foe":"You make a charming target, Captain.", "foe_by":"agent", "foe_mood":"angry"}]}}
        elif kind == "legend":
            f["legend"] = {"id": 1, "chapter_id": "palace", "node": "start", "step": 1,
                           "title": "The Palace Beneath the Waves", "chapter": "A bargain below the tide",
                           "teller": "narrator", "scene": "legend", "beats": [{"who": "narrator", "text": "Some fortunes wait beneath the water, Captain."}]}
        elif kind == "trade":
            # The second poll produces a new event rather than replaying a pre-existing receipt on load.
            feed["events"] = [{"n": 1 if elapsed < 2 else 2, "turn": 5,
                               "at": int(time.time() * 1000), "type": "protect", "pid": "p1",
                               "port": "hongkong", "text": "Protection secured. Li Yue's fleets will honour the token.",
                               "cash": [96600, 84600]}]
        return feed

    journey_game, journey_events = journey_sample()
    from tools.preview_battle_results import simulate
    fight_sample = simulate(config.defaults(), 7)["result"]
    clients = {}

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(ROOT / "web"), **kw)

        def send(self, data, mime="application/json"):
            raw = json.dumps(data).encode() if isinstance(data, dict) else data.encode() if isinstance(data, str) else data
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            parsed = urlparse(self.path)
            path = unquote(parsed.path)
            if path == "/original-jail":
                from tools.preview_jail import build_preview
                html = build_preview(config.defaults()).replace("</head>", '<link rel="stylesheet" href="/battle.css"><link rel="stylesheet" href="/ceremony.css"></head>')
                start = html.index("const fixture=") + len("const fixture=")
                end = html.index(";T=fixture.strings", start)
                jail_fixture = {"strings":info["data"]["text"], "ports":info["data"]["ports"],
                           "cast":info["voice"]["cast"], "media":info["media"]}
                html = html[:start] + json.dumps(jail_fixture).replace("</", "<\\/") + html[end:]
                return self.send(html, "text/html; charset=utf-8")
            if path == "/preview":
                return self.send('''<!doctype html><html lang="en"><meta charset="utf-8"><title>Table Preview Theatre</title>
                <style>body{margin:0;background:#15100c;color:#f1e3c5;font:18px Georgia}header{padding:18px 26px;display:flex;gap:16px;align-items:center;flex-wrap:wrap}strong{color:#e8cf91}a{color:#f1e3c5;border:1px solid #c9a34e;padding:9px 16px;text-decoration:none}iframe{display:block;border:0;width:100%;height:calc(100vh - 125px)}p{margin:0 26px 15px;color:#c8b798}</style>
                <header><strong>Table Preview Theatre</strong><a href="/table?scene=journey" target="stage">Full voyage</a><a href="/table?scene=storm" target="stage">Storm</a><a href="/table?scene=battle" target="stage">Battle</a><a href="/table?scene=battle-result" target="stage">Battle ending</a><a href="/table?scene=customs" target="stage">Port Authority</a><a href="/table?scene=legend" target="stage">Legend</a><a href="/table?scene=host" target="stage">Madame Anahit</a></header>
                <p>Disposable sample game · Your saved game is untouched · Use Skip to step through, or Linger to study a scene.</p><iframe title="Table story preview" name="stage" src="/table?scene=journey"></iframe></html>''', "text/html; charset=utf-8")
            if path in ("/", "/table"):
                html = (ROOT / "web/table.html").read_text(encoding="utf-8")
                script = '<script>const realFetch=window.fetch.bind(window),previewClient=Math.random().toString(36).slice(2);window.fetch=(u,o)=>realFetch(u==="/api/table"?"/api/table?client="+previewClient+"&scene="+(new URLSearchParams(location.search).get("scene")||"host"):u,o);</script>'
                return self.send(html.replace('<script src="/table.js', script + '<script src="/table.js'), "text/html; charset=utf-8")
            if path == "/api/info":
                return self.send(info)
            if path == "/api/table":
                query = parse_qs(parsed.query)
                now = time.monotonic()
                elapsed = now - clients.setdefault(query.get("client", [""])[0], now)
                return self.send(fixture(query.get("scene", ["host"])[0], elapsed))
            if path == "/api/captains":
                return self.send({"ok": True, "captains": []})
            if path in ("/theme.css", "/fonts.css"):
                raw, mime = remote(path)
                return self.send(raw, mime)
            target = (ROOT / "web" / path.lstrip("/")).resolve()
            if not target.is_relative_to(ROOT / "web"):
                return self.send_error(404)
            if target.is_file():
                return super().do_GET()
            if path.startswith(("/media/", "/uploads/", "/fonts/")):
                try:
                    raw, mime = remote(path)
                    return self.send(raw, mime)
                except Exception as exc:
                    print("Preview asset failed: {}: {}".format(path, exc), flush=True)
            self.send_error(404)

        def do_POST(self):
            size = int(self.headers.get("Content-Length") or 0)
            self.rfile.read(min(size, 65536))
            self.send({"ok": True, "granted": True, "table_channels": []})

    print("Table preview: http://{}:{}/preview (disposable story theatre)".format(args.bind, args.port), flush=True)
    ThreadingHTTPServer((args.bind, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
