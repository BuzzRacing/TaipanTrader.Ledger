"""Checks the voice clips page's backend (voiceclips.py) without Inworld or the internet:
    python tests/voiceclips_test.py
Uses a scratch cache folder; nothing in cache/voice/ is touched.
"""
import copy
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import cast  # noqa: E402
import engine  # noqa: E402
import voice  # noqa: E402
import voiceclips as vc  # noqa: E402

FAILS = []
TMP = tempfile.mkdtemp(prefix="seatrader-clips-")
voice.CACHE_DIR = os.path.join(TMP, "voice")
vc.BIN_DIR = os.path.join(TMP, "voice_bin")
vc.FILE = os.path.join(TMP, "voice_clips.json")
os.makedirs(voice.CACHE_DIR)
CALLS = []


def check(cond, what):
    if not cond:
        FAILS.append(what)
        print("FAIL:", what)


def fake_synth(text, voice_id, model_id, rate=1.0, temperature=1.0, delivery=""):
    CALLS.append((text, voice_id, rate))
    return b"ID3" + str(len(CALLS)).encode() * 20


voice.synthesize = fake_synth

CFG = copy.deepcopy(engine.CFG)
TEXT = engine.TEXT
fixed = [k for k in cast.spoken_keys(TEXT) if "{" not in cast.spoken_template(CFG, TEXT, k)
         and vc._reads(k) and k not in cast.OFFICER_KEYS and cast.speaker_for(CFG, k)]
key = fixed[0]
who = cast.speaker_for(CFG, key)
CFG["characters"][who]["voice_id"] = "Olivia"


def clips():
    return {c["id"]: c for c in vc.view(CFG, TEXT)["clips"]}


# A line nobody has recorded is listed as missing, with the persona who reads it.
v = vc.view(CFG, TEXT)
check(any(m["key"] == key and m["persona"] == who for m in v["missing"]), "an unrecorded fixed line is listed as missing")
check(v["totals"]["clips"] == 0, "no clips yet")

# Recording it makes a clip; it then leaves the missing list and is current.
cid = vc.record(CFG, TEXT, key=key)
check(len(CALLS) == 1 and os.path.isfile(voice.clip_path(cid)), "recording a missing line pays once and saves the clip")
c = clips()[cid]
check(c["key"] == key and c["persona"] == who and c["status"] == "current", "the clip is matched to its line and persona, current")
check(not any(m["key"] == key for m in vc.view(CFG, TEXT)["missing"]), "it is no longer missing")

# Changing her voice or speed makes it out of date, and says why.
CFG["characters"][who]["voice_id"] = "Yoona"
CFG["characters"][who]["speaking_rate"] = 0.9
c = clips()[cid]
check(c["status"] == "stale" and set(c["diffs"]) == {"voice", "speed"}, "a recasting shows the clip as out of date with reasons")
st = vc.view(CFG, TEXT)["personas"][who]
check(st["clips"] == 1 and st["stale"] == 1 and st["share"] == 100.0, "persona stats count it")

# Rank, redo flag, note.
check(vc.rate(cid, stars=2, redo=True, note="  too   fast ") == {"stars": 2, "redo": True, "note": "too fast"}, "rank saved")
c = clips()[cid]
check(c["stars"] == 2 and c["redo"] and c["note"] == "too fast", "rank shows in the list")
for bad in (6, -1, "x"):
    try:
        vc.rate(cid, stars=bad)
        check(False, "bad stars refused: {}".format(bad))
    except vc.ClipError:
        pass
try:
    vc.rate("../../etc/passwd", stars=3)
    check(False, "a clip id must look like one")
except vc.ClipError:
    pass

# Re-record: the old take goes to the bin, a new clip is made with today's settings.
new = vc.record(CFG, TEXT, cid=cid)
check(new != cid and os.path.isfile(voice.clip_path(new)), "re-recording after a change makes a new clip")
check(CALLS[-1][1] == "Yoona" and CALLS[-1][2] == 0.9, "the new take uses her current voice and speed")
after = clips()
check(after[cid]["binned"] and after[cid]["status"] == "binned", "the old take is in the bin")
check(not after[cid]["redo"], "the redo flag is cleared once re-recorded")
check(after[new]["status"] == "current", "the new take is current")

# Re-record with nothing changed still gives a fresh take (old one binned first).
n = len(CALLS)
again = vc.record(CFG, TEXT, cid=new)
check(len(CALLS) == n + 1 and again == new and os.path.isfile(voice.clip_path(new)), "an unchanged re-record is a new take")
check(os.path.isfile(vc._bin_path(new)), "the previous take is kept in the bin")

# Bin and restore.
vc.bin_clip(new)
check(not os.path.isfile(voice.clip_path(new)) and clips()[new]["binned"], "binning moves the audio")
check(vc.view(CFG, TEXT)["totals"]["clips"] == 0, "binned clips are not counted")
vc.restore(new)
check(os.path.isfile(voice.clip_path(new)) and not clips()[new]["binned"], "restoring brings it back")
vc.bin_clip(new)
voice.render(voice._params(clips()[new]["text"], CFG["characters"][who], CFG["voice"]))   # the line is spoken again
try:
    vc.restore(new)
    check(False, "restoring over a newer take is refused")
except vc.ClipError:
    pass

# Only emptying the bin deletes audio.
check(vc.empty_bin() >= 1 and not os.listdir(vc.BIN_DIR), "emptying the bin removes the files")

# Failure while re-recording puts the old take back.
cur = vc.view(CFG, TEXT)["clips"][0]["id"]


def boom(*a, **k):
    raise voice.VoiceError("Inworld is down")


voice.synthesize = boom
try:
    vc.record(CFG, TEXT, cid=cur)
    check(False, "a failed re-record reports the error")
except voice.VoiceError:
    pass
check(os.path.isfile(voice.clip_path(cur)), "a failed re-record leaves the old take in place")
voice.synthesize = fake_synth

# Lines with names filled in cannot be recorded by key; the price setting is checked.
named = [k for k in cast.spoken_keys(TEXT) if "{" in cast.spoken_template(CFG, TEXT, k)][0]
try:
    vc.record(CFG, TEXT, key=named)
    check(False, "a line with names is refused")
except vc.ClipError:
    pass
check(vc.set_price("0.05") == 0.05 and vc.load()["price_per_1k"] == 0.05, "price saved")
check(vc.handle("rate", {"id": "nope"}, CFG, TEXT)["ok"] is False, "route errors come back as messages")

if FAILS:
    print("\n{} check(s) failed.".format(len(FAILS)))
    sys.exit(1)
print("voiceclips: all checks passed")
