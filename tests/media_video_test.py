"""Videos in the Media Library (20 Nov 2026): a clip made from a picture on a pretend AI farm, the clean +
NSFW pair rule, posters, and the Admin route. Runs in a scratch copy of the folders.
Run:  python tests/media_video_test.py"""
import json
import os
import shutil
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config    # noqa: E402
import imagegen  # noqa: E402
import media     # noqa: E402

FAKE_MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 200
SEEN = {"uploads": [], "prompts": []}


class Farm(BaseHTTPRequestHandler):
    """Just enough of ComfyUI: /upload/image, /prompt, /history/<id>, /view."""
    def log_message(self, *a):
        pass

    def _json(self, obj):
        b = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n)
        if self.path == "/upload/image":
            assert b'name="image"' in body and b"multipart" not in body[:2]
            SEEN["uploads"].append(len(body))
            return self._json({"name": "seatrader-x.png", "subfolder": "", "type": "input"})
        if self.path == "/prompt":
            SEEN["prompts"].append(json.loads(body)["prompt"])
            return self._json({"prompt_id": "p{}".format(len(SEEN["prompts"])), "number": 1, "node_errors": {}})
        self.send_error(404)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path.startswith("/history/"):
            pid = u.path.split("/")[-1]
            return self._json({pid: {"status": {"status_str": "success"},
                                     "outputs": {"22": {"images": [{"filename": "clip_00001.mp4", "subfolder": "seatrader",
                                                                    "type": "output"}], "animated": [True]}}}})
        if u.path == "/view":
            assert parse_qs(u.query)["filename"] == ["clip_00001.mp4"]
            self.send_response(200)
            self.send_header("Content-Length", str(len(FAKE_MP4)))
            self.end_headers()
            self.wfile.write(FAKE_MP4)
            return
        self.send_error(404)


tmp = tempfile.mkdtemp()
farm = ThreadingHTTPServer(("127.0.0.1", 0), Farm)
threading.Thread(target=farm.serve_forever, daemon=True).start()
try:
    # The real Wan workflow file, pointed at the pretend farm.
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfgfile = os.path.join(tmp, "imagegen.json")
    with open(cfgfile, "w") as f:
        json.dump({"base_url": "http://127.0.0.1:{}".format(farm.server_address[1]),
                   "workflow": "imagegen/wan22_i2v_loop.json", "video": {"short_side": 480}}, f)
    imagegen.CONFIG_FILE = cfgfile

    media.WEB = os.path.join(tmp, "web")
    media.MEDIA_DIR = os.path.join(media.WEB, "media")
    media.TRASH_DIR = os.path.join(media.MEDIA_DIR, "_trash")
    media.UPLOAD_DIR = os.path.join(media.WEB, "uploads")
    media.LIB_FILE = os.path.join(tmp, "config", "media.json")
    os.makedirs(media.UPLOAD_DIR)
    cfg = config.defaults()
    cfg["content"]["rating"] = "historical"
    PNG = bytes.fromhex("89504e470d0a1a0a0000000d494844520000030000000400080200000000000000000000")
    nude = media.add_bytes(PNG, ".png", "persona", "warden_hongkong", ["portrait", "speaking"], ["jail warden"], True,
                           "generated")
    clean = media.add_bytes(PNG, ".png", "persona", "warden_hongkong", ["portrait", "speaking"],
                            ["jail warden", "clean"], False, "generated")
    assert (nude["width"], nude["height"]) == (768, 1024), nude

    # 1. The farm call itself: placeholders filled, shape kept, 12 s from three 81-frame passes.
    data, info = imagegen.generate_video(media.path_for(nude["url"]), "She walks toward the camera spinning keys",
                                         768, 1024, 10, 1234, "seatrader/test")
    wf = SEEN["prompts"][-1]
    assert data == FAKE_MP4 and info["ext"] == ".mp4" and info["seconds"] == 12, info  # 239 frames played at 20 fps
    assert "{{" not in json.dumps(wf), "every placeholder is filled"
    assert wf["30"]["inputs"]["start_image"] == ["14", 0] and wf["15"]["inputs"]["start_image"] == ["35", 0], "three passes chain"
    assert wf["30"]["inputs"]["length"] == 81 and wf["34"]["inputs"]["length"] == 79
    assert wf["21"]["inputs"]["fps"] == 20 and wf["21"]["inputs"]["images"] == ["24", 0], "plays at 20 fps, after sharpen"
    assert wf["23"]["inputs"]["scale_by"] == 1.25 and wf["24"]["inputs"]["alpha"] == 0.4
    assert imagegen.VIDEO_DEFAULTS["short_side"] == 640, "clips render at 640 unless the config says otherwise"
    assert (info["width"], info["height"]) == (600, 800), info
    assert wf["10"]["inputs"]["width"] == 480 and wf["10"]["inputs"]["height"] == 640 and wf["10"]["inputs"]["length"] == 81
    assert wf["5"]["inputs"]["image"] == "seatrader-x.png" and wf["11"]["inputs"]["noise_seed"] == 1234
    assert wf["15"]["inputs"]["end_image"] == ["5", 0], "the second pass ends on the picture, so the clip loops"
    assert wf["6"]["inputs"]["text"].startswith("She walks")

    # 2. A pair through the queue: the pair button decides the rating, both share the seeds.
    media.JOBS.start(lambda *a, **k: (PNG, 1), None, render_video=imagegen.generate_video)
    seeds = [11, 22]
    jn = media.JOBS.add_video(nude, "She walks toward the camera spinning keys", seeds, "yes", ["motion-keys"],
                              pair="pabcdef12", width=768, height=1024)
    jc = media.JOBS.add_video(clean, "She walks toward the camera spinning keys", seeds, "no", ["motion-keys", "clean"],
                              pair="pabcdef12", width=768, height=1024)
    for _ in range(200):
        if all(j["status"] in ("done", "failed") for j in (jn, jc)):
            break
        time.sleep(0.05)
    assert jn["status"] == "done" and jc["status"] == "done", (jn, jc)
    clips = [i for i in media.load(cfg)["items"] if i["type"] == "video"]
    assert len(clips) == 4, clips
    by = {(c["from_item"], c["seed"]): c for c in clips}
    for sd in seeds:
        a, b = by[(nude["id"], sd)], by[(clean["id"], sd)]
        assert a["nsfw"] and not b["nsfw"], "NSFW clip from the NSFW picture, clean clip from the clean one"
        assert a["pair"] == b["pair"] == "pabcdef12" and a["seconds"] == 12 and a["loop"]
        assert not a["reviewed"] and not b["reviewed"], "new clips wait for review"
        assert a["roles"] == ["portrait", "speaking"] and "clean" in b["tags"]
        assert a["model"].startswith("Wan 2.2") and a["motion"].startswith("She walks")

    # 3. Player screens: clips carry their picture as poster; family-friendly drops the NSFW clip and picture.
    pub = {i["id"]: i for i in media.public(cfg)["items"]["persona"]["warden_hongkong"]}
    c0 = by[(nude["id"], 11)]
    assert pub[c0["id"]]["po"] == nude["url"]
    cfg["content"]["rating"] = "family"
    pub = {i["id"]: i for i in media.public(cfg)["items"]["persona"]["warden_hongkong"]}
    assert c0["id"] not in pub and nude["id"] not in pub
    assert pub[by[(clean["id"], 22)]["id"]]["po"] == clean["url"]

    # 4. A single clip copies its picture's flag; clips survive a reload with their links.
    j1 = media.JOBS.add_video(nude, "She stands swinging a ring of keys", [5], "auto", [], width=768, height=1024)
    for _ in range(200):
        if j1["status"] in ("done", "failed"):
            break
        time.sleep(0.05)
    single = [i for i in media.load(cfg)["items"] if i["type"] == "video" and i["seed"] == 5][0]
    assert single["nsfw"] and single["pair"] == "" and single["from_item"] == nude["id"]
    media._cache["mtime"] = None
    again = [i for i in media.load(cfg)["items"] if i["id"] == single["id"]][0]
    assert again["from_item"] == nude["id"] and again["seconds"] == 12

    # 5. A missing picture fails cleanly, and the farm being down never stops the queue.
    gone = dict(nude, url="/media/persona/warden_hongkong/nope.png")
    j2 = media.JOBS.add_video(gone, "She stands swinging a ring of keys", [6], "auto")
    for _ in range(100):
        if j2["status"] in ("done", "failed"):
            break
        time.sleep(0.05)
    assert j2["status"] == "failed" and "gone" in j2["error"]
    print("OK: media video checks passed ({} farm calls)".format(len(SEEN["prompts"])))
finally:
    farm.shutdown()
    shutil.rmtree(tmp, ignore_errors=True)
