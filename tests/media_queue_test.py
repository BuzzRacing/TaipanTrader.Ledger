"""Persistent render queue: lanes, reorder, pause, stop-all, ETA, restart recovery. Run: python tests/media_queue_test.py"""
import os, sys, time, json, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import media
tmp = tempfile.mkdtemp()
media.JOBS_FILE = os.path.join(tmp, "jobs.json")
J = media.Jobs()
def add(n, subj="a"): return J.add("port", subj, ["x"], "p"*30, 512, 512, n, False)
def vid(): return J.add_video({"kind": "port", "subject": "a", "id": "i1", "url": "/x.png"}, "m", [1, 2], "no")
a, b, c = add(2, "a"), add(1, "b"), add(1, "c")
v = vid()
assert [j["id"] for j in J.list()][:4] == [a["id"], b["id"], c["id"], v["id"]], [j["id"] for j in J.list()]
assert J.move(c["id"], "top") and J.list()[0]["id"] == c["id"]
assert J.move(c["id"], "down") and J.move(a["id"], "before:" + b["id"])
print([j["id"][-2:] + ":" + str(j["pos"]) for j in J.list()])
s = J.summary(); assert s["lanes"]["picture"]["waiting"] == 3 and s["lanes"]["video"]["items"] == 2
assert s["total_eta_s"] == int(4*45 + 2*1500), s
J.pause("picture", True)
assert J.list()[0]["eta_s"] is None and [j for j in J.list() if j["lane"]=="video"][0]["eta_s"] is not None
J.pause("picture", False)
# persistence: pretend one was running when the server died
J.jobs[0]["status"] = "running"; J.jobs[0]["done"] = 1; J._save()
K = media.Jobs(); K._restore()
st = {j["id"]: j for j in K.jobs}
assert st[J.jobs[0]["id"]]["status"] == "waiting" and st[J.jobs[0]["id"]]["resumed"]
# stop all
n = K.cancel_all(); assert n == 4 and all(j["status"] == "cancelled" for j in K.jobs)
# worker: pictures first, resumed job renders only what is left
L = media.Jobs(); L._restore()
for j in L.jobs: j["status"] = "waiting"
order = []
def fake(prompt, prefix, w, h, neg, **kw): order.append("pic"); return b"x", 1
media.compact_picture = lambda d: (d, ".png")
media.add_bytes = lambda *a, **k: {"id": "it%d" % len(order), "url": "/u.png"}
L.jobs = []
v2 = L.add_video({"kind": "port", "subject": "a", "id": "i1", "url": "/x.png"}, "m", [1], "no")
p2 = L.add("port", "a", [], "p"*30, 512, 512, 2, False)
L.render = fake; L.render_video = None
import threading
L.thread = threading.Thread(target=L._run, daemon=True); L.thread.start(); L.wake.set()
for _ in range(50):
    if all(j["status"] in ("done", "failed", "cancelled") for j in L.jobs): break
    time.sleep(0.1)
assert order == ["pic", "pic"], order
assert L.jobs[1]["status"] == "done" and L.jobs[0]["status"] == "failed", [j["status"] for j in L.jobs]
assert json.load(open(media.JOBS_FILE))["jobs"]
print("media queue tests passed")
