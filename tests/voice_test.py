"""Checks the cast and the Inworld voice layer without touching the internet.

A fake Inworld answers every request, so this runs anywhere:
    python tests/voice_test.py
"""
import base64
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import cast      # noqa: E402
import config    # noqa: E402
import engine    # noqa: E402
import strings   # noqa: E402
import voice     # noqa: E402

FAILS = []
TMP = tempfile.mkdtemp(prefix="seatrader-voice-")
voice.CACHE_DIR = os.path.join(TMP, "cache")
voice.KEY_FILE = os.path.join(TMP, "voice_key.json")
os.environ.pop("INWORLD_API_KEY", None)
CALLS = []


def check(cond, what):
    if not cond:
        FAILS.append(what)
        print("FAIL:", what)


def fake(method, url, headers, body, timeout):
    CALLS.append((method, url, headers, json.loads(body) if body else None))
    if headers.get("Authorization") != "Basic dGVzdGtleTp0ZXN0c2VjcmV0MTIz":
        return 401, b'{"message":"bad key"}'
    if url.startswith(voice.TTS_URL):
        payload = json.loads(body)
        if payload["voice_id"] == "Nobody":
            return 400, b'{"code":3,"message":"Unknown voice: Nobody"}'
        a = base64.b64encode(b"ID3-first-").decode()
        b = base64.b64encode(("|" + payload["text"]).encode()).decode()
        return 200, ('{"result":{"audioContent":"%s"}}\n{"result":{"audioContent":"%s"}}\n' % (a, b)).encode()
    if url.startswith(voice.VOICES_URL):
        if "pageToken" not in url:
            return 200, json.dumps({"voices": [{"voiceId": "Hades", "displayName": "Hades", "description": "deep",
                                                "langCode": "EN_US", "languageCode": "en-US", "source": "SYSTEM",
                                                "gender": "male", "ageGroup": "middle_aged"}],
                                    "nextPageToken": "1-1"}).encode()
        return 200, json.dumps({"voices": [{"voiceId": "workspace__my_clone", "displayName": "My clone",
                                            "source": "IVC", "languageCode": "en-US"},
                                           {"voiceId": "Hades", "displayName": "Hades dup", "source": "SYSTEM"}]}).encode()
    return 404, b"{}"


voice._transport = fake

# --- defaults are valid and complete ------------------------------------------------
cfg, errs = config.validate(config.defaults())
check(not errs, "default settings validate: {}".format(errs[:3]))
check(len(cfg["characters"]) == 11, "eleven default characters")
for cid, c in cfg["characters"].items():
    check(c["voice_id"], "{} has a voice".format(cid))
    check(c["bio"] and c["catchphrase"] and c["secret"] and c["portrait_prompt"], "{} has a full profile".format(cid))
    check("adult" in c["portrait_prompt"], "{} portrait prompt states an adult".format(cid))
for key, who in cast.LINE_DEFAULTS.items():
    check(key in strings.EN, "line default '{}' is a real wording key".format(key))
    check(who in cfg["characters"], "line default '{}' goes to a real character".format(key))
spoken = cast.spoken_keys(strings.EN)
check("l.sea.0" not in spoken and "l.how_sunk" not in spoken, "fragments are never spoken on their own")
check("btn.buy" not in spoken, "buttons are never spoken")

# --- validation keeps bad input out -----------------------------------------------------
bad = config.defaults()
bad["characters"]["narrator"]["voice_id"] = "rm -rf /;"
bad["characters"]["Bad Key"] = {"name": "x"}
bad["characters"]["bosun"]["stats"] = {"cunning": 99, "nerve": "x"}
bad["characters"]["bosun"]["portrait"] = "javascript:alert(1)"
bad["voice"]["model_id"] = "nope"
bad["voice"]["lines"] = {"l.anchor": "ghost", "btn.buy": "bosun", "m.bought": ""}
c2, e2 = config.validate(bad)
check(any("voice ID" in e for e in e2), "odd voice IDs are refused")
check(any("Bad Key" in e for e in e2), "bad character keys are refused")
check(c2["characters"]["bosun"]["stats"]["cunning"] == 10, "stats are clamped to 10")
check(c2["characters"]["bosun"]["portrait"] == "", "unsafe portrait URLs are dropped")
check(c2["voice"]["model_id"] == "inworld-tts-2-flash", "unknown model falls back to flash")
check(c2["voice"]["lines"] == {"m.bought": ""}, "line map keeps only real speakers and spoken groups")

# --- removing a character never leaves a line orphaned ---------------------------------
gone = config.defaults()
del gone["characters"]["bosun"]
gone, e3 = config.validate(gone)
check(not e3, "removing a character validates")
check(cast.speaker_for(gone, "l.typhoon") == "narrator", "a removed speaker's lines go to the narrator")
check(cast.speaker_for(gone, "n.glut") == "crier", "news goes to the crier")

# --- brand names follow the Brand page ---------------------------------------------------
gone["brand"]["lender"] = "Uncle Chen"
check(cast.public_cast(gone)["lender"]["name"] == "Uncle Chen", "brand-linked names follow Brand")

# --- matcher and planner ------------------------------------------------------------------
engine.configure(cfg, strings.resolve(cfg))
voice.PLAN.configure(cfg, engine.TEXT)
tx = engine.tx
samples = {
    tx("l.typhoon"): "bosun",
    tx("l.sailed", origin="Hong Kong", dest="Manila", weather=tx("l.sea.2")): "narrator",
    tx("l.lord_found"): "pirate",
    tx("l.seized", qty=12, fine="$3,600"): "customs",
    tx("l.sank_all", n=4, rounds=3, s="s", booty="$1,200"): "bosun",
    tx("l.ship_lost", ship="Junk", name="Lucky Star", how=tx("l.how_foundered")): "narrator",
    tx("l.robbed", lost="$4,000"): "narrator",
}
for line, who in samples.items():
    key = voice.PLAN.matcher.key(line)
    check(key is not None and cast.speaker_for(cfg, key) == who, "'{}' is read by {} (got {})".format(line[:40], who, key))
check(voice.PLAN.lines(["x"], "log") is None, "no key: nothing is planned")

voice.set_key("Basic dGVzdGtleTp0ZXN0c2VjcmV0MTIz")
st = voice.key_status()
check(st == {"has_key": True, "source": "admin", "tail": "MTIz"}, "key saved from Admin, Basic prefix stripped: {}".format(st))
check(voice.PLAN.ready(), "planner ready with a key")

log = [tx("l.typhoon"), tx("l.anchored", port="Manila")]
plan = voice.PLAN.lines(log, "log")
check([p["c"] for p in plan] == ["bosun", "narrator"], "log plan speakers: {}".format(plan))
check(all(p["u"].startswith("/voice/") for p in plan), "log plan has audio links")
check(not CALLS, "planning alone never calls Inworld")

news = ["Mar 1861: " + tx("n.glut", good_lower="tea", port="Manila"), "Apr 1861: " + tx("n.ban", port="Batavia"),
        "May 1861: The governor's ball is tonight."]
np = voice.PLAN.lines(news, "news")
check([p["c"] for p in np] == ["crier", "customs", "crier"], "news speakers incl. custom news: {}".format(np))

check(voice.PLAN.msg(tx("m.bought", qty=10, good="Silk", cost="$5,200"))["c"] == "comprador", "purchases: comprador")
check(voice.PLAN.msg(tx("m.borrowed", amount="$1,000", rate="6"))["c"] == "lender", "loans: moneylender")
check(voice.PLAN.msg("Something the game never says") is None, "text the game never says is not voiced")
cfg["voice"]["read_confirmations"] = False
check(voice.PLAN.msg(tx("m.sold", qty=1, good="Tea", gain="$70")) is None, "confirmations can be switched off")
cfg["voice"]["read_confirmations"] = True
cfg["voice"]["lines"]["m.sold"] = ""
check(voice.PLAN.msg(tx("m.sold", qty=1, good="Tea", gain="$70")) is None, "a line set to silent stays silent")
del cfg["voice"]["lines"]["m.sold"]

# --- lines with amounts are spoken without them, so they are paid for once --------
said = lambda r: voice._registry[r["u"][len("/voice/"):-4]]["text"]
a1 = voice.PLAN.msg(tx("m.bought", qty=60, good="Rice", cost="$951"))
a2 = voice.PLAN.msg(tx("m.bought", qty=20, good="Rice", cost="$300"))
check(a1["u"] == a2["u"] and said(a1) == "Bought Rice.", "different amounts share one spoken clip: {}".format(said(a1)))
check(voice.PLAN.msg(tx("m.bought", qty=5, good="Tea", cost="$9"))["u"] != a1["u"], "a different good is its own clip")
check(said(voice.PLAN.msg(tx("e.cost", cost="$5", cash="$1"))) == "You cannot afford that.", "refusals lose their amounts")
for k, v in cast.SAY.items():
    check(all("{" + n + "}" in strings.EN[k] for n in re.findall(r"\{(\w+)\}", v)), "spoken {} uses only its own names".format(k))
cfg["voice"]["say"] = {"m.bought": "", "m.sold": "Sold the {good}, Captain."}
check(said(voice.PLAN.msg(tx("m.bought", qty=60, good="Rice", cost="$951"))) == "Bought 60 Rice for $951.",
      "an empty spoken version reads the line as shown")
check(said(voice.PLAN.msg(tx("m.sold", qty=1, good="Tea", gain="$70"))) == "Sold the Tea, Captain.", "Admin spoken version")
cfg["voice"]["say"] = {}

# --- clips are made on request, once ------------------------------------------------------
cid = plan[0]["u"].split("/")[-1][:-4]
audio = voice.get_clip(cid)
check(audio and audio.startswith(b"ID3-first-|"), "chunks are joined into one MP3")
sent = CALLS[-1][3]
check(sent["voice_id"] == "Ashley" and sent["model_id"] == "inworld-tts-2-flash", "bosun's voice and model sent")
check(sent["audio_config"]["audio_encoding"] == "MP3", "MP3 requested")
check(not sent["text"].startswith("["), "flash gets no delivery note")
n = len(CALLS)
check(voice.get_clip(cid) == audio and len(CALLS) == n, "second request comes from the cache")
check(voice.get_clip("0" * 24) is None, "unplanned clips are refused")
check(voice.get_clip("../../etc/passwd") is None, "odd clip names are refused")

# Many screens asking at once pay once.
p3 = voice.PLAN.lines([tx("l.storm")], "log")[0]
cid3 = p3["u"].split("/")[-1][:-4]
n = len(CALLS)
threads = [threading.Thread(target=voice.get_clip, args=(cid3,)) for _ in range(6)]
[t.start() for t in threads]
[t.join() for t in threads]
check(len(CALLS) == n + 1, "six screens asking at once make one Inworld call (made {})".format(len(CALLS) - n))

# Full TTS-2 follows the delivery note.
cfg["voice"]["model_id"] = "inworld-tts-2"
p4 = voice.PLAN.lines([tx("l.lord_found")], "log")[0]
voice.get_clip(p4["u"].split("/")[-1][:-4])
check(CALLS[-1][3]["text"].startswith("[low, slow and cold"), "TTS-2 gets Li Yuen's delivery note")
cfg["voice"]["model_id"] = "inworld-tts-2-flash"

# Errors are readable and nothing is cached.
cfg["characters"]["crier"]["voice_id"] = "Nobody"
p5 = voice.PLAN.msg(tx("m.begin"))
try:
    voice.get_clip(p5["u"].split("/")[-1][:-4])
    check(False, "a bad voice raises")
except voice.VoiceError as e:
    check("Unknown voice" in str(e), "Inworld's message is passed on: {}".format(e))
check(voice.STATS["errors"] >= 1, "errors are counted")
cfg["characters"]["crier"]["voice_id"] = "Sarah"

voice.set_key("")
os.environ["INWORLD_API_KEY"] = "wrongwrongwrongwrongkey"
check(voice.key_status()["source"] == "env", "falls back to INWORLD_API_KEY")
try:
    voice.synthesize("hello", "Hades", "inworld-tts-2-flash")
    check(False, "wrong key raises")
except voice.VoiceError as e:
    check("did not accept" in str(e), "a rejected key says so")
os.environ.pop("INWORLD_API_KEY")
voice.set_key("dGVzdGtleTp0ZXN0c2VjcmV0MTIz")

# --- voice list --------------------------------------------------------------------------
vs = voice.list_voices(force=True)
check([v["id"] for v in vs] == ["workspace__my_clone", "Hades"], "own voices first, pages followed, dupes dropped: {}".format(vs))
check(vs[1]["lang"] == "en-US" and vs[1]["age"] == "middle aged", "voice rows are tidied")

# --- the server end to end ----------------------------------------------------------------
import server  # noqa: E402
from http.server import ThreadingHTTPServer  # noqa: E402

config.CONFIG_DIR = os.path.join(TMP, "config")
config.SETTINGS_FILE = os.path.join(config.CONFIG_DIR, "settings.json")
config.BACKUP_DIR = os.path.join(config.CONFIG_DIR, "backups")
server.SAVES = os.path.join(TMP, "saves")
server.SAVE_FILE = os.path.join(server.SAVES, "current.json")
server.apply_settings()
server.HUB = server.Hub(engine.Game(), "http://test")
httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()
base = "http://127.0.0.1:{}".format(httpd.server_address[1])


def call(path, body=None, admin=False):
    req = urllib.request.Request(base + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", **({"X-SeaTrader": "admin"} if admin else {})})
    with urllib.request.urlopen(req) as r:
        raw = r.read()
        return json.loads(raw) if r.headers.get("Content-Type", "").startswith("application/json") else raw


info = call("/api/info")
check(info["voice"]["enabled"] and info["voice"]["cast"]["pirate"]["name"] == "Admiral Li Yue", "info carries the cast")
tok = call("/api/join", {"name": "Ann", "firm": "Ann & Co"})["token"]
call("/api/act", {"token": tok, "type": "start"})
res = call("/api/act", {"token": tok, "type": "buy", "good": "rice", "qty": 5})
check(res["ok"] and res["voice"] and res["voice"]["c"] == "comprador", "buying answers with the comprador's voice")
res = call("/api/act", {"token": tok, "type": "buy", "good": "rice", "qty": 999999})
check(not res["ok"] and res["voice"] and res["voice"]["c"] == "comprador", "refusals are voiced too")
clip = call(res["voice"]["u"])
check(isinstance(clip, bytes) and clip.startswith(b"ID3"), "clip served as audio")
call("/api/act", {"token": tok, "type": "sail", "dest": "manila", "orders": "run"})
with server.HUB.cond:
    view = server.HUB.view(server.HUB.game.pid_for_token(tok))
check(view["voice"]["log"] and all(x is None or x["c"] in cfg["characters"] for x in view["voice"]["log"]),
      "the month's log comes with speakers")
check(len(view["voice"]["news"]) == len(view["news"][:14]), "news comes with speakers")
adm = call("/api/admin/all")
check(adm["cast"]["lines"] and adm["cast"]["key"]["has_key"], "admin gets the line list and key status")
prev = call("/api/admin/voice/preview", {"character": cfg["characters"]["pirate"], "text": "Li Yuen waits."}, admin=True)
check(isinstance(prev, bytes) and b"Li Yuen waits." in prev, "admin audition returns audio")
vl = call("/api/admin/voice/voices")
check(vl["ok"] and vl["voices"], "admin voice list")
httpd.shutdown()

shutil.rmtree(TMP, ignore_errors=True)
if FAILS:
    print("{} problem(s).".format(len(FAILS)))
    sys.exit(1)
print("OK: cast and voices checks passed")
