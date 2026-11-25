"""tools/picture_batch.py (24 Nov 2026): check, queue, wait, file, retire, against a stand-in game server."""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import sys
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import picture_batch as pb  # noqa: E402

STATE = {}


class Fake(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def log_message(self, *a):
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n) or b"{}") if n else {}
        path = self.path.replace("/api/admin/", "")
        STATE.setdefault("calls", []).append((path, body))
        if path == "all":
            res = {"ok": True, "config": {"graphics": {"ships": {}}}}
        elif path == "media/generate":
            res = {"ok": True, "job": "J1"}
        elif path == "media/jobs":
            res = {"jobs": [{"id": "J1", "status": "done", "items": ["new1"]}], "queue": {}}
        elif path == "media/library":
            res = {"items": [{"id": "new1", "url": "/media/new1.png"}]}
        elif path == "save":
            res = {"ok": True}
        elif path == "media/update":
            res = {"ok": True, "changed": len(body.get("ids") or [])}
        else:
            res = {"ok": False}
        out = json.dumps(res).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    do_GET = do_POST


class PictureBatchTest(unittest.TestCase):
    def setUp(self):
        STATE.clear()
        self.httpd = HTTPServer(("127.0.0.1", 0), Fake)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.server = "http://127.0.0.1:%d" % self.httpd.server_port
        pb.POLL_SECONDS = 0.01

    def tearDown(self):
        self.httpd.shutdown()

    def job(self, prompt="a harbour at dawn, 1860 China Seas"):
        return {"label": "Hong Kong card", "body": {"kind": "ship", "subject": "x", "roles": ["card"], "prompt": prompt,
                "aspect": "3:4", "count": 1, "nsfw": "no", "tags": ""}, "old": ["old1"], "slot": ("ships", "junk")}

    def test_the_game_is_found(self):
        self.assertEqual(pb.find_server(self.server), self.server)
        self.assertEqual(pb.find_server("http://127.0.0.1:1"), "")

    def test_a_modern_word_stops_everything_before_anything_is_queued(self):
        self.assertEqual(pb.run(self.server, [self.job("a stealth drone over the harbour")]), 1)
        self.assertFalse(any(p == "media/generate" for p, _ in STATE.get("calls", [])))

    def test_dry_run_queues_nothing(self):
        self.assertEqual(pb.run(self.server, [self.job()], dry=True), 0)
        self.assertFalse(STATE.get("calls"))

    def test_queue_wait_slot_and_retire(self):
        self.assertEqual(pb.run(self.server, [self.job()]), 0)
        saved = [b for p, b in STATE["calls"] if p == "save"]
        self.assertEqual(saved[0]["config"]["graphics"]["ships"]["junk"], "/media/new1.png")
        updates = [b for p, b in STATE["calls"] if p == "media/update"]
        self.assertEqual(updates[0]["changes"], {"primary": True, "enabled": True})
        self.assertEqual(updates[1], {"ids": ["old1"], "changes": {"enabled": False}})   # switched off, never deleted


if __name__ == "__main__":
    unittest.main()
