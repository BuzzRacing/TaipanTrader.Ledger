"""SeaTrader server.

Uses only the Python standard library, so there is nothing to install.
Run:  python server.py [--port 8765] [--new]

  /            player screen (phones, tablets, laptops)
  /board       harbor board for a big shared screen
  /events      live state stream (Server-Sent Events)
  /api/...     join and actions
"""
import argparse
import json
import os
import signal
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from engine import Game, GameError, static_data

ROOT = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(ROOT, "web")
SAVES = os.path.join(ROOT, "saves")
SAVE_FILE = os.path.join(SAVES, "current.json")
GRACE_SECONDS = 25   # a refreshing or briefly dropped device still counts as present
TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
         ".js": "application/javascript; charset=utf-8", ".svg": "image/svg+xml",
         ".png": "image/png", ".ico": "image/x-icon", ".json": "application/json"}


class Hub:
    """Holds the one running game and wakes every screen when it changes."""

    def __init__(self, game, join_url):
        self.game = game
        self.join_url = join_url
        self.cond = threading.Condition(threading.RLock())
        self.version = 0
        self.conns = {}       # player id -> open stream count
        self.last_seen = {}   # player id -> time the last stream closed

    def present(self):
        now = time.time()
        here = {pid for pid, n in self.conns.items() if n > 0}
        here |= {pid for pid, t in self.last_seen.items() if now - t < GRACE_SECONDS}
        return here

    def changed(self, save=True):
        """Call with the lock held after any change to the game."""
        if self.game.maybe_advance(self.present()):
            save = True
        if save:
            self.save()
        self.version += 1
        self.cond.notify_all()

    def save(self):
        os.makedirs(SAVES, exist_ok=True)
        tmp = SAVE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.game.s, f)
        os.replace(tmp, SAVE_FILE)

    def view(self, pid):
        v = self.game.view(pid, self.present())
        v["join_url"] = self.join_url
        return v

    def ticker(self):
        """Notices when a player drops out so the others are not left waiting."""
        seen = self.present()
        while True:
            time.sleep(3)
            with self.cond:
                now = self.present()
                advanced = self.game.maybe_advance(now)
                if advanced:
                    self.save()
                if advanced or now != seen:
                    seen = now
                    self.version += 1
                    self.cond.notify_all()


HUB = None


class Handler(BaseHTTPRequestHandler):
    server_version = "SeaTrader/1.0"

    def log_message(self, fmt, *args):   # keep the console quiet
        pass

    # ----------------------------------------------------------- helpers --
    def _send(self, code, body, ctype="application/json"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body)
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _file(self, name):
        path = os.path.normpath(os.path.join(WEB, name))
        if not path.startswith(WEB + os.sep) or not os.path.isfile(path):
            return self._send(404, "Not found", "text/plain")
        with open(path, "rb") as f:
            data = f.read()
        self._send(200, data, TYPES.get(os.path.splitext(path)[1].lower(), "application/octet-stream"))

    def _body(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            length = 0
        if length <= 0 or length > 20000:
            return {}
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8"))
            return data if isinstance(data, dict) else {}
        except (ValueError, UnicodeDecodeError):
            return {}

    # ------------------------------------------------------------ routes --
    def do_GET(self):
        url = urlparse(self.path)
        path = url.path
        if path == "/":
            return self._file("index.html")
        if path == "/board":
            return self._file("board.html")
        if path == "/api/info":
            return self._send(200, {"ok": True, "join_url": HUB.join_url, "data": static_data()})
        if path == "/events":
            return self._events(parse_qs(url.query).get("token", [""])[0])
        return self._file(path.lstrip("/"))

    def do_POST(self):
        path = urlparse(self.path).path
        body = self._body()
        try:
            if path == "/api/join":
                with HUB.cond:
                    token = HUB.game.join(body.get("name"), body.get("firm"), HUB.present())
                    HUB.changed()
                return self._send(200, {"ok": True, "token": token})
            if path == "/api/act":
                with HUB.cond:
                    pid = HUB.game.pid_for_token(body.get("token"))
                    if pid is None:
                        return self._send(200, {"ok": False, "error": "You are not in this game.",
                                                "rejoin": True})
                    present = HUB.present() | {pid}
                    if body.get("type") == "new_game":
                        if HUB.game.host_id(present) != pid:
                            raise GameError("Only the host can start a new game.")
                        HUB.save()
                        archive_save()
                        HUB.game = Game()
                        HUB.conns.clear()
                        HUB.last_seen.clear()
                        msg = "A new game is open. Everyone can join again."
                    else:
                        msg = HUB.game.act(pid, body, present)
                    HUB.changed()
                return self._send(200, {"ok": True, "msg": msg})
            if path == "/api/shutdown":
                if self.client_address[0] not in ("127.0.0.1", "::1"):
                    return self._send(403, {"ok": False, "error": "Only from the host computer."})
                with HUB.cond:
                    HUB.save()
                self._send(200, {"ok": True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
        except GameError as e:
            return self._send(200, {"ok": False, "error": str(e)})
        self._send(404, {"ok": False, "error": "Not found"})

    def _events(self, token):
        with HUB.cond:
            pid = HUB.game.pid_for_token(token) if token else None
            if pid:
                HUB.conns[pid] = HUB.conns.get(pid, 0) + 1
                HUB.last_seen.pop(pid, None)
                HUB.version += 1
                HUB.cond.notify_all()
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
            last = -1
            while True:
                with HUB.cond:
                    if HUB.version == last:
                        HUB.cond.wait(15)
                    payload = None
                    if HUB.version != last:
                        last = HUB.version
                        if pid and HUB.game.pid_for_token(token) != pid:
                            pid = None
                        view = HUB.view(pid)
                        view["unknown_token"] = bool(token) and pid is None
                        payload = json.dumps(view)
                if payload is None:
                    self.wfile.write(b": keepalive\n\n")
                else:
                    self.wfile.write(b"data: " + payload.encode("utf-8") + b"\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionError, OSError):
            pass
        finally:
            if pid:
                with HUB.cond:
                    if pid in HUB.conns:
                        HUB.conns[pid] = max(0, HUB.conns[pid] - 1)
                        if HUB.conns[pid] == 0:
                            HUB.last_seen[pid] = time.time()
                    HUB.version += 1
                    HUB.cond.notify_all()


def lan_address():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def archive_save():
    if os.path.isfile(SAVE_FILE):
        os.replace(SAVE_FILE, os.path.join(SAVES, time.strftime("game-%Y%m%d-%H%M%S.json")))
        return True
    return False


def main():
    global HUB
    ap = argparse.ArgumentParser(description="SeaTrader game server")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--new", action="store_true", help="archive the saved game and start a fresh one")
    ap.add_argument("--archive-only", action="store_true", help="archive the saved game and exit")
    args = ap.parse_args()

    if args.new or args.archive_only:
        if archive_save():
            print("Previous game archived in the saves folder.")
        if args.archive_only:
            return
    game = None
    if os.path.isfile(SAVE_FILE):
        try:
            with open(SAVE_FILE, encoding="utf-8") as f:
                game = Game(state=json.load(f))
            print("Resumed the saved game ({} players).".format(len(game.s["players"])))
        except (ValueError, KeyError, OSError) as e:
            print("Could not read the save ({}); starting a new game.".format(e))
            archive_save()
    if game is None:
        game = Game()
        print("Started a new game.")

    join_url = "http://{}:{}".format(lan_address(), args.port)
    HUB = Hub(game, join_url)
    try:
        httpd = ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    except OSError as e:
        print("Could not open port {}: {}".format(args.port, e))
        print("SeaTrader may already be running.")
        sys.exit(1)
    httpd.daemon_threads = True
    threading.Thread(target=HUB.ticker, daemon=True).start()
    print("")
    print("  SeaTrader is running.")
    print("  This computer:   http://localhost:{}".format(args.port))
    print("  Other devices:   {}".format(join_url))
    print("  Harbor board:    {}/board".format(join_url))
    print("")
    print("  Leave this window open while you play. Close it to stop the game.")
    def stop(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)   # systemd stop on the Pi: save, then exit
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    with HUB.cond:
        HUB.save()
    print("Game saved. Goodbye.")


if __name__ == "__main__":
    main()
