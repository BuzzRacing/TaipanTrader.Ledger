"""Isolated Set Sail chart preview with labelled sample history; no saved game is opened."""
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import config
import engine
import fonts


def main():
    cfg = config.load()
    engine.configure(cfg)
    game = engine.Game(seed=17)
    game.join("Preview Captain", "")
    game.act("p1", {"type": "start"}, present=["p1"])
    state = game.view("p1", ["p1"])
    state["game_id"] = "preview"
    state["turn"] = 10
    me = state["me"]
    ports = list(engine.PORTS)
    me["port"] = "foochow"
    me["hot_tips"] = [{"port": "manila", "good": next(iter(engine.GOODS)), "lands": 11, "ends": 14}]
    me["shares"]["mine"] = {"hongkong": 3, "manila": 1}
    for i, k in enumerate(ports):
        me["known"][k] = {"turn": 8, "prices": {g: v["base"] * (1 + i / 10) for g, v in engine.GOODS.items()}}
    history = [{"port": k, "visits": i % 5, "profit": (i - 3) * 2370, "sales": i} for i, k in enumerate(ports)]
    fixture = json.dumps({"data": engine.static_data(), "state": state}, ensure_ascii=True).replace("</", "<\\/")
    source = (ROOT / "web/player.js").read_text(encoding="utf-8")
    helpers = source[source.index("function pirateRisk("):source.index("/* The house's standing")]
    html = '''<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Set Sail · isolated preview</title><link rel="stylesheet" href="/style.css"><link rel="stylesheet" href="/deck.css">
    <link rel="stylesheet" href="/sail-intel.css"><link rel="stylesheet" href="/theme.css"><link rel="stylesheet" href="/fonts.css">
    <style>body.player{overflow:auto;height:auto}main{max-width:1080px;margin:auto;padding:16px}h1{font-size:2rem}.preview-note{color:var(--brass-hi)}</style></head>
    <body class="player"><main><h1>Set Sail</h1><p class="preview-note">ISOLATED PREVIEW · sample history and holdings · no saved game changes</p><div id="app"></div></main>
    <script src="/common.js"></script><script>const fixture=FIXTURE;let D=fixture.data,S=fixture.state,token='preview';
    const ui={dest:null};T=D.text;CUR=D.brand.currency;
    const hotGone=tp=>tp.over!=null&&S.turn>=tp.over;
    function quote(g,q){return S.me.prices[g]*q*(1+S.me.spread);}
    HELPERS
    </script><script src="/chart.js"></script><script src="/sail-intel.js"></script><script>
    function render(){document.querySelector('#app').innerHTML=SailIntel.html(ui.dest);Chart.fit();}
    document.addEventListener('click',e=>{const el=e.target.closest('[data-act="dest"]');if(el){ui.dest=el.dataset.port;render();}});
    render();</script></body></html>'''.replace("FIXTURE", fixture).replace("HELPERS", helpers)

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(ROOT / "web"), **kwargs)

        def do_GET(self):
            path = self.path.split("?")[0]
            content = {"/": (html, "text/html"), "/theme.css": (config.theme_css(cfg), "text/css"),
                       "/fonts.css": (config.fonts_css(cfg, fonts.local_css()), "text/css"),
                       "/api/stats": (json.dumps({"ok": True, "voyage": {"me": {"ports": history}}}), "application/json")}.get(path)
            if not content:
                target = (ROOT / "web" / unquote(path).lstrip("/")).resolve()
                if not target.is_relative_to((ROOT / "web").resolve()) or not target.is_file() or target.suffix.lower() not in {
                    ".css", ".js", ".png", ".jpg", ".jpeg", ".webp", ".woff", ".woff2", ".ttf"}:
                    return self.send_error(404)
                return super().do_GET()
            raw = content[0].encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", content[1] + "; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    print("Set Sail preview: http://localhost:18879 (sample data only)", flush=True)
    ThreadingHTTPServer(("127.0.0.1", 18879), Handler).serve_forever()


if __name__ == "__main__":
    main()
