"""Preview the real Voyage Certificate with stand-in figures: python tools/preview_certificate.py
(or double-click Preview_Certificate.bat). It opens your browser by itself; --no-browser stops that.

Opens the game's own painter (web/certificate.js) on its own page, with this PC's Media Library, fonts,
wording and cast, and invented figures. No game is loaded and nothing is saved. If port 18883 is taken it
uses the next free one and says so. Each start, and any error that stops it, is written to
cache/preview_certificate.log.

    http://localhost:18883/                          a solo game, Hong Kong, a good finish
    http://localhost:18883/?port=saigon&who=pirate   another home port, another woman on the right
    http://localhost:18883/?rivals=3&place=2         a game with rivals
    http://localhost:18883/?bad=1                    a bad finish (kinder wording, her teasing line)
    http://localhost:18883/?family=1                 as a family-friendly screen sees it
    http://localhost:18883/?quick=1                  no arriving layers (as when reopened from the results)
who: bosun, pirate, agent, lender, taxlady, gamemaster, officer_<port>. "Change the pictures" steps through all.
"""
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import threading
import time
import traceback
from urllib.parse import parse_qs, unquote, urlparse
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
LOG = ROOT / "cache" / "preview_certificate.log"
PORT = 18883


def note(text):
    """A line on screen and in cache/preview_certificate.log (so a window that closed can still be read)."""
    print(text, flush=True)
    try:
        LOG.parent.mkdir(exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + text + "\n")
    except OSError:
        pass


try:
    import cast          # noqa: E402
    import certificate   # noqa: E402
    import config        # noqa: E402
    import fonts         # noqa: E402
    import media         # noqa: E402
    import strings       # noqa: E402
except Exception:
    note("The preview could not load the game's code (Python {}):\n{}".format(sys.version.split()[0], traceback.format_exc()))
    sys.exit(1)

WOMEN = ["bosun", "pirate", "agent", "lender", "taxlady", "gamemaster"]


def fixture(cfg, family):
    fcfg = dict(cfg, content=dict(cfg.get("content") or {}, rating="family")) if family else cfg
    text = dict(strings.resolve(cfg))
    if family:
        text.update(strings.FAMILY)
    lib = media.public(fcfg)
    crest = next((lst[0]["u"] for lst in (lib["items"].get("house") or {}).values() if lst), "")
    return {"strings": text, "ports": cfg["ports"], "goods": cfg["goods"], "brand": cfg["brand"],
            "graphics": media.safe_graphics(cfg.get("graphics"), fcfg), "ranks": cfg["ranks"],
            "cast": cast.public_cast(cfg), "media": lib, "crest": crest, "family": bool(family)}


def women(cfg, first, port, bad):
    """Every woman who can stand on the right, the asked-for one first, each with her line for this finish."""
    order = [first] + [w for w in WOMEN + ["officer_" + port] if w != first]
    out = []
    for cid in order:
        if cid not in cfg["characters"]:
            continue
        key = certificate._pick("preview", "p1", cid, "bad" if bad else "good")
        names = {"name": "Anthony", "firm": "Silver Fern"}
        out.append({"who": cid, "key": key, "name": cast.display_name(cfg, cid),
                    "text": strings.EN[key].format(**names), "family": strings.FAMILY[key].format(**names),
                    "port": cid[len("officer_"):] if cid.startswith("officer_") else ""})
    return out


def facts(cfg, q):
    one = lambda k, d="": q.get(k, [d])[0]
    port = one("port", "hongkong") if one("port", "hongkong") in cfg["ports"] else "hongkong"
    rivals = max(1, min(8, int(one("rivals", "1") or 1)))
    bad = one("bad") == "1"
    place = max(1, min(rivals, int(one("place", str(rivals if bad and rivals > 1 else 1)) or 1)))
    rank = cfg["ranks"][2 if bad else -1]
    return {"ok": True, "game": "preview", "id": "p1", "name": "Anthony", "firm": "Silver Fern", "color": 0,
            "place": place, "houses": rivals, "bad": bad, "rank": rank["title"], "rank_id": rank["id"],
            "epithet": "unlucky" if bad else "magnificent", "worth": 41_250 if bad else 110_400_000,
            "first": "Jan 1860", "last": "Dec 1869", "years": 10, "home": port, "home_name": cfg["ports"][port]["name"],
            "career": None if rivals > 1 else {"place": 3 if bad else 1, "of": 4, "years": 10},
            "best_sale": None if bad else {"good": "porcelain" if "porcelain" in cfg["goods"] else next(iter(cfg["goods"])),
                                           "port": "saigon" if "saigon" in cfg["ports"] else port, "qty": 6250,
                                           "profit": 18_200_000},
            "battles": 4 if bad else 31, "won": 1 if bad else 23, "sunk": 3 if bad else 47,
            "women": women(cfg, one("who", "bosun"), port, bad), "recipe": None}


PAGE = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Voyage Certificate preview</title><link rel="stylesheet" href="/style.css"><link rel="stylesheet" href="/deck.css">
<link rel="stylesheet" href="/certificate.css"><link rel="stylesheet" href="/theme.css"><link rel="stylesheet" href="/fonts.css">
<style>body{margin:0;min-height:100vh;background:#15100c url("/assets/ceremony-harbor.png") center/cover fixed}</style>
</head><body class="player"><div id="app"></div>
<script src="/ranks.js"></script><script src="/common.js"></script><script src="/media.js"></script><script src="/certificate.js"></script>
<script>
const fixture = FIXTURE, certFacts = FACTS;
if (fixture.family) { try { localStorage.setItem("seatrader_family", "1"); } catch (e) {} }
else { try { localStorage.removeItem("seatrader_family"); } catch (e) {} }
T = Object.assign({}, T_FALLBACK, fixture.strings); CUR = fixture.brand.currency || "$";
Ranks.configure({ ranks: fixture.ranks, promotion_styles: {} });
Media.setup(fixture.media);
var VS = { cast: fixture.cast };
const D = { ports: fixture.ports, goods: fixture.goods, brand: fixture.brand, graphics: fixture.graphics };
const S = { game_id: "preview", players: [{ id: "p1", name: "Anthony", firm: "Silver Fern", portrait: "", crest: fixture.crest }], me: { id: "p1" } };
function open() {
  Certificate.use(certFacts, "preview");
  Certificate.show({ state: S, data: D, quick: QUICK, onDone: () => { document.getElementById("app").innerHTML =
    '<p style="color:#f3e6c8;padding:2rem;font:1.2rem Georgia,serif">The Ledger of the Voyage would open here. <button onclick="open()">Open the certificate again</button></p>'; } });
}
open();
</script></body></html>'''


def handler(cfg):
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(ROOT / "web"), **kwargs)

        def log_message(self, *a):
            pass

        def _send(self, body, ctype):
            raw = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", ctype + "; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)

        def do_POST(self):          # the recipe: accepted and forgotten
            self.rfile.read(int(self.headers.get("Content-Length") or 0))
            self._send(json.dumps({"ok": True}), "application/json")

        def do_GET(self):
            url = urlparse(self.path)
            path, q = url.path, parse_qs(url.query)
            if path == "/":
                family = q.get("family", [""])[0] == "1"
                safe = lambda o: json.dumps(o, ensure_ascii=True).replace("</", "<\\/")
                html = PAGE.replace("FIXTURE", safe(fixture(cfg, family))).replace("FACTS", safe(facts(cfg, q)))
                html = html.replace("QUICK", "true" if q.get("quick", [""])[0] == "1" else "false")
                return self._send(html, "text/html")
            if path == "/theme.css":
                return self._send(config.theme_css(cfg), "text/css")
            if path == "/fonts.css":
                return self._send(config.fonts_css(cfg, fonts.local_css()), "text/css")
            web = (ROOT / "web").resolve()
            target = (web / unquote(path).lstrip("/")).resolve()
            inside = web == target or web in target.parents
            if not inside or not target.is_file() or target.suffix.lower() not in {
                    ".css", ".js", ".png", ".jpg", ".jpeg", ".webp", ".woff", ".woff2", ".ttf"}:
                return self.send_error(404)
            return super().do_GET()

    return Handler


def main():
    cfg = config.load()
    httpd, why = None, None
    for port in range(PORT, PORT + 8):           # 18883, or the next free one
        try:
            httpd = ThreadingHTTPServer(("127.0.0.1", port), handler(cfg))
            break
        except OSError as e:
            why = e
    if httpd is None:
        raise OSError("no free port from {} to {}: {}".format(PORT, PORT + 7, why))
    url = "http://localhost:{}/".format(httpd.server_address[1])
    note("Voyage Certificate preview is running at {}  (Python {})".format(url, sys.version.split()[0]))
    print("Leave this window open while you look. Close it to stop the preview.")
    print("Other looks, typed after the address:")
    for tail, what in (("?bad=1", "a bad finish: kinder wording and her teasing line"),
                       ("?rivals=3&place=2", "a game with rivals"),
                       ("?port=saigon&who=pirate", "another home port and another woman on the right"),
                       ("?family=1", "as a family-friendly screen sees it"),
                       ("?quick=1", "no arriving layers")):
        print("  {}{:26} {}".format(url, tail, what))
    sys.stdout.flush()
    if "--no-browser" not in sys.argv:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    try:
        main()
    except Exception:
        note("The preview stopped with an error (Python {}):\n{}".format(sys.version.split()[0], traceback.format_exc()))
        sys.exit(1)
