"""Preview a Legend on the real story screen, played by the real engine on a throwaway game:

    python tools/preview_legend.py            then open  http://localhost:18882/
    http://localhost:18882/?teller=teller_tavern     hand the Legend to another storyteller
    http://localhost:18882/?pics=1                   placeholder figures where the Media Library has none

Nothing is saved and the live game is not touched. Each choice is sent to legend.py exactly as the game sends
it; "Ring the bell" sails the throwaway fleet about until the next chapter opens. No voices (the preview has no
voice plan), so each line stays up for its reading time; tap to go on sooner."""
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import cast      # noqa: E402
import config    # noqa: E402
import engine    # noqa: E402
import fonts     # noqa: E402
import media     # noqa: E402
import strings   # noqa: E402

PORT = 18882


def quiet_rules(cfg, teller):
    r = cfg["rules"]
    r["weather"]["storm_chance"] = [0, 0, 0, 0]
    r["weather"]["offcourse"] = 0.0
    r["pirates"]["chance"] = 0.0
    r["liyuen"]["chance"] = 0.0
    r["customs"]["enabled"] = False
    r["jail"]["enabled"] = False
    r["bank"]["mug_chance"] = 0.0
    r["legend"].update({"enabled": True, "eager": True, "gap_min": 1, "gap_max": 1})
    if teller:
        r["legend"]["teller"] = teller
    return cfg


class Table:
    """One throwaway game with one Captain, sailed about until a Legend opens."""

    def __init__(self, cfg, teller=None):
        cfg, errors = config.validate(quiet_rules(cfg, teller))
        if errors:
            raise SystemExit("\n".join(errors))
        engine.configure(cfg)
        self.g = engine.Game(seed=7)
        self.g.join("Preview Captain", "")
        self.g.act("p1", {"type": "start"}, present=self.g.s["order"])
        self.p = self.g.s["players"]["p1"]
        self.p["cash"] = 250000
        self.p["cargo"] = {"tea": 40, "rice": 30}
        self.p["basis"] = {k: engine.GOODS[k]["base"] for k in self.p["cargo"]}
        self.p["port"] = "hongkong"
        self.seek()

    def seek(self, limit=80):
        for _ in range(limit):
            if self.p.get("legend"):
                return
            dest = "nagasaki" if self.p["port"] != "nagasaki" else "hongkong"
            self.g.act("p1", {"type": "sail", "dest": dest, "orders": "run"}, present=["p1"])
            self.g.resolve("all_ready", {"p1"})

    def state(self):
        v = self.g.view("p1", {"p1"})
        v["game_id"] = self.g.s["game_id"]
        v["told"] = not self.p.get("legend")
        return v

    def act(self, a):
        try:
            self.g.act("p1", dict(a, type="legend"), present=["p1"])
        except engine.GameError as e:
            return {"ok": False, "error": str(e)}
        if a.get("done"):
            self.seek()
        return {"ok": True}


PAGE = '''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Legend preview</title><link rel="stylesheet" href="/style.css"><link rel="stylesheet" href="/deck.css">
<link rel="stylesheet" href="/battle.css"><link rel="stylesheet" href="/legend.css"><link rel="stylesheet" href="/theme.css">
<link rel="stylesheet" href="/fonts.css"></head><body class="player"><div id="app"></div>
<script src="/common.js"></script><script src="/media.js"></script>
<script>const fixture=FIXTURE;T=fixture.strings;Media.setup(fixture.media);
const D={ports:fixture.ports,goods:fixture.goods},VS={cast:fixture.cast};
if(new URLSearchParams(location.search).get('pics')){for(const k in VS.cast){const c=VS.cast[k];if(!c.portrait)c.portrait=
 'data:image/svg+xml,'+encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 600"><rect width="300" height="600" fill="'+(c.color||'#555')+
 '"/><circle cx="150" cy="170" r="70" fill="#f1e3c5" opacity=".8"/><path d="M40 600c0-190 50-270 110-270s110 80 110 270z" fill="#f1e3c5" opacity=".8"/></svg>');}}
let S=fixture.state;
async function refresh(){S=await (await fetch('/state')).json();draw();}
function draw(){if(S.told){document.querySelector('#app').innerHTML='<p style="padding:3rem;font:1.4rem serif;color:#f1e3c5">The Legend is told. Reload to hear it again.</p>';}Legend.sync();}
async function act(type,data){const r=await (await fetch('/act',{method:'POST',body:JSON.stringify(data)})).json();await refresh();return r.ok;}
</script><script src="/legend.js"></script><script>draw();</script></body></html>'''


def main():
    cfg = config.load()
    tables = {}

    def table(teller):
        if teller not in tables:
            tables[teller] = Table(json.loads(json.dumps(cfg)), teller)
        return tables[teller]

    current = {"t": None}

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(ROOT / "web"), **kwargs)

        def log_message(self, *_a):
            pass

        def _send(self, body, kind):
            raw = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", kind + "; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            url = urlparse(self.path)
            if url.path == "/":
                teller = (parse_qs(url.query).get("teller") or [None])[0]
                tables.pop(teller, None)                     # a fresh telling on every load
                tb = current["t"] = table(teller)
                live = engine.CFG if hasattr(engine, "CFG") else cfg
                fixture = json.dumps({"strings": strings.resolve(live), "ports": live["ports"], "goods": live["goods"],
                                      "cast": cast.public_cast(live), "media": media.public(live), "state": tb.state()},
                                     ensure_ascii=True).replace("</", "<\\/")
                return self._send(PAGE.replace("FIXTURE", fixture), "text/html")
            if url.path == "/state":
                return self._send(json.dumps(current["t"].state()), "application/json")
            if url.path == "/theme.css":
                return self._send(config.theme_css(cfg), "text/css")
            if url.path == "/fonts.css":
                return self._send(config.fonts_css(cfg, fonts.local_css()), "text/css")
            target = (ROOT / "web" / unquote(url.path).lstrip("/")).resolve()
            if not target.is_relative_to(ROOT / "web") or not target.is_file() or target.suffix.lower() not in {
                    ".css", ".js", ".png", ".jpg", ".jpeg", ".webp", ".woff", ".woff2", ".ttf", ".mp4", ".webm"}:
                return self.send_error(404)
            return super().do_GET()

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            return self._send(json.dumps(current["t"].act(body)), "application/json")

    print("Legend preview: http://localhost:{}/  (also ?teller=teller_temple, teller_tavern, teller_drowned; ?pics=1)".format(PORT), flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
