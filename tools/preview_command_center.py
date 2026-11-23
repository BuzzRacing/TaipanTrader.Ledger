"""Read-only preview of the Dashboard (the Command Center) on a deterministic fixture game.

Starts the real web server on a spare port with one of the fixture games from tests/dashboard_fixtures.py in
place of the live game, so /dashboard can be looked at in every state without touching the game in play:

    python tools/preview_command_center.py                 the late solo game, on http://localhost:18890/dashboard
    python tools/preview_command_center.py --fixture rivals     two houses: the public, sealed view
    python tools/preview_command_center.py --fixture lobby      before anyone has sailed
    python tools/preview_command_center.py --list

Fixtures: lobby, early, middle, late, rivals (see dashboard_fixtures.py for what each one is).

Safe to run beside the live game: the journal and the save file are pointed at a throwaway folder that is deleted
on exit, and the month timer, the image queue and the autosave are never started. Nothing under saves/ or
journal/ is read or written. Pictures and wording come from this folder's own settings and Media Library.
"""
import argparse
import os
import sys
import threading
from http.server import ThreadingHTTPServer

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
import dashboard_fixtures as fx  # noqa: E402
import engine  # noqa: E402
import media  # noqa: E402
import server  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fixture", default="late", choices=fx.NAMES)
    ap.add_argument("--port", type=int, default=18890)
    ap.add_argument("--list", action="store_true", help="list the fixtures and exit")
    args = ap.parse_args()
    if args.list:
        return fx.main()
    server.apply_settings()
    media.load(engine.CFG)
    with fx.journal_sandbox() as tmp:
        server.SAVES = os.path.join(tmp, "saves")
        server.SAVE_FILE = os.path.join(server.SAVES, "current.json")
        os.makedirs(server.SAVES, exist_ok=True)
        game = fx.build(args.fixture)
        server.HUB = server.Hub(game, "http://localhost:{}".format(args.port))
        httpd = ThreadingHTTPServer(("127.0.0.1", args.port), server.Handler)
        httpd.daemon_threads = True
        print("Command Center preview, fixture '{}': http://localhost:{}/dashboard".format(args.fixture, args.port))
        print("Ctrl+C stops it. Nothing is saved.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            threading.Thread(target=httpd.shutdown, daemon=True).start()


if __name__ == "__main__":
    main()
