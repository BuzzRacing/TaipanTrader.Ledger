"""Show the real Set Sail screen after submitting orders in a disposable game."""
import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
from time import sleep
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
GALLERY = "http://192.168.1.69:8765"
sys.path.insert(0, str(ROOT))
import engine


def main():
    with urlopen(GALLERY + "/api/info?family=1", timeout=15) as response:
        info = json.load(response)
    info["voice"]["enabled"] = False
    game = engine.Game(seed=17)
    for name, firm in [("Morgan", "House of the Compass"), ("Victoria", "Jade & Silk"), ("James", "East India Trading")]:
        game.join(name, firm)
    game.admin("start", {})
    players = game.s["order"]
    pid = players[0]
    origin = game.s["players"][pid]["port"]
    destination = "singapore" if origin != "singapore" else "manila"
    game.act(pid, {"type": "sail", "dest": destination, "orders": "run"}, present=players)
    state = game.view(pid, players)
    state.update(cfg=info["cfg"], game_id="turn-wait-preview")
    state["me"]["log"] = []
    assert state["me"]["ready"] and state["waiting"] == ["Victoria", "James"]
    html = (WEB / "index.html").read_text(encoding="utf-8")
    player = (WEB / "player.js").read_text(encoding="utf-8")
    player = player.replace('tab: "port", vals:', 'tab: "chart", vals:', 1)
    allowed = {urlsplit(item["u"]).path for subjects in info["media"]["items"].values()
               for items in subjects.values() for item in items}

    class Handler(SimpleHTTPRequestHandler):
        def do_GET(self):
            path = urlsplit(self.path).path
            if path == "/":
                return self.send_content(html, "text/html")
            if path == "/player.js":
                return self.send_content(player, "text/javascript")
            if path == "/api/info":
                return self.send_content(json.dumps(info), "application/json")
            if path == "/events":
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                try:
                    self.wfile.write(f"data: {json.dumps(state)}\n\n".encode("utf-8"))
                    while True:
                        sleep(10)
                        self.wfile.write(b": keepalive\n\n")
                except (BrokenPipeError, ConnectionResetError):
                    return
            if path == "/api/captains":
                return self.send_content('{"ok":true,"captains":[]}', "application/json")
            if path in allowed or path in {"/theme.css", "/fonts.css"} or path.startswith("/fonts/"):
                if ".." in path.split("/"):
                    return self.send_error(404)
                try:
                    headers = {"Range": self.headers["Range"]} if "Range" in self.headers else {}
                    with urlopen(Request(GALLERY + path, headers=headers), timeout=15) as response:
                        self.send_response(response.status)
                        for key in ("Content-Type", "Content-Length", "Content-Range", "Accept-Ranges"):
                            if key in response.headers:
                                self.send_header(key, response.headers[key])
                        self.end_headers()
                        while chunk := response.read(65536):
                            self.wfile.write(chunk)
                except URLError as exc:
                    self.log_error("Gallery %s: %s", path, exc)
                    self.send_error(502)
                except (BrokenPipeError, ConnectionResetError):
                    self.log_message("Browser closed the media stream for %s", path)
                return
            target = Path(self.translate_path(path)).resolve()
            if not target.is_relative_to(WEB) or not target.is_file() or target.suffix.lower() not in {
                ".js", ".css", ".svg", ".png", ".webp", ".jpg", ".woff2", ".mp3", ".ogg", ".mp4"
            }:
                return self.send_error(404)
            return super().do_GET()

        def send_content(self, content, mime):
            raw = content.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", mime + "; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    print("Turn wait preview: http://127.0.0.1:18887", flush=True)
    ThreadingHTTPServer(("127.0.0.1", 18887), partial(Handler, directory=str(WEB))).serve_forever()


if __name__ == "__main__":
    main()
