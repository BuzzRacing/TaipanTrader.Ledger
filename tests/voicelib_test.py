"""Checks the saved voice library (voicelib.py) without touching the internet:
    python tests/voicelib_test.py
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import voicelib  # noqa: E402

FAILS = []
voicelib.FILE = os.path.join(tempfile.mkdtemp(prefix="seatrader-voicelib-"), "voice_library.json")


def check(cond, what):
    if not cond:
        FAILS.append(what)
        print("FAIL:", what)


def v(vid, gender="female", lang="en-US", source="SYSTEM"):
    return {"id": vid, "name": vid, "description": "a voice", "gender": gender, "age": "young", "lang": lang,
            "source": source, "tags": ["warm"]}


check(voicelib.public()["voices"] == [], "starts empty")
check(voicelib.public()["sample_text"] == voicelib.DEFAULT_SAMPLE, "stock audition line by default")

d = voicelib.refresh([v("Asuka", lang="ja-JP"), v("Olivia"), v("Hades", "male")], now=1000)
check(d["first"] and d["added"] == [] and d["removed"] == [], "the first fetch reports nothing as new")
check([x["id"] for x in voicelib.public()["voices"]] == ["Hades", "Olivia", "Asuka"], "English first, then by name")

try:
    voicelib.refresh([], now=1500)
    check(False, "an empty list is refused")
except ValueError:
    pass
check(not any(x["gone_at"] for x in voicelib.public()["voices"]), "an empty answer marks nothing as gone")

d = voicelib.refresh([v("Olivia"), v("Hades", "male"), v("Yoona", lang="ko-KR")], now=2000)
check(d == {"added": ["Yoona"], "removed": ["Asuka"], "back": [], "first": False}, "a later check lists what is new and gone")
rows = {x["id"]: x for x in voicelib.public()["voices"]}
check(rows["Asuka"]["gone_at"] == 2000 and rows["Asuka"]["first_seen"] == 1000, "a retired voice is kept, marked gone")
check(rows["Yoona"]["first_seen"] == 2000 and rows["Olivia"]["first_seen"] == 1000, "first seen dates are kept")
check(voicelib.public()["voices"][-1]["id"] == "Asuka", "gone voices sort last")
check(voicelib.public()["history"][0]["added"] == ["Yoona"], "the change is in the history")

d = voicelib.refresh([v("Olivia"), v("Hades", "male"), v("Yoona", lang="ko-KR"), v("Asuka", lang="ja-JP")], now=3000)
check(d["back"] == ["Asuka"] and d["added"] == [], "a voice that returns is reported as back")
d = voicelib.refresh([v("Olivia"), v("Hades", "male"), v("Yoona", lang="ko-KR"), v("Asuka", lang="ja-JP")], now=3500)
check(len(voicelib.public()["history"]) == 2, "a check with no changes adds no history")
check(voicelib.public()["refreshed_at"] == 3500, "the check date moves on")

check(voicelib.mark("Olivia", rating="star") == {"rating": "star", "note": ""}, "shortlist mark saved")
check(voicelib.mark("Olivia", note="  dry,   Scots?  ")["note"] == "dry, Scots?", "note saved and tidied, mark kept")
check(voicelib.public()["marks"]["Olivia"]["rating"] == "star", "marks are in the page data")
voicelib.mark("Olivia", rating="", note="")
check("Olivia" not in voicelib.public()["marks"], "clearing mark and note removes the entry")
for bad in (("Nobody", "star"), ("Olivia", "five stars")):
    try:
        voicelib.mark(*bad)
        check(False, "bad mark refused: {}".format(bad))
    except ValueError:
        pass
voicelib.mark("Yoona", rating="no")
voicelib.refresh([v("Olivia"), v("Yoona", lang="ko-KR")], now=4000)
check(voicelib.public()["marks"]["Yoona"]["rating"] == "no", "marks survive a check")

check(voicelib.set_sample("  Hello,   Captain. ") == "Hello, Captain.", "audition line saved")
check(voicelib.public()["sample_text"] == "Hello, Captain.", "audition line read back")
check(voicelib.set_sample("") == voicelib.DEFAULT_SAMPLE, "empty goes back to the stock line")

cast = {"a": {"voice_id": "Olivia"}, "b": {"voice_id": "Olivia"}, "c": {"voice_id": "Hades"}, "d": {"voice_id": ""},
        "e": {"voice_id": "Mystery"}, "f": {"voice_id": "Yoona"}}
probs = {p["character"]: p["problem"] for p in voicelib.check_cast(cast)}
check(probs == {"a": "shared", "b": "shared", "c": "gone", "d": "none", "e": "unknown"}, "casting problems found: {}".format(probs))
check(voicelib.check_cast(cast)[0]["problem"] == "gone", "worst problem first")
voicelib.refresh([v("Olivia"), v("Yoona", lang="ko-KR"), v("Hades", "male")], now=5000)
check({p["character"]: p["problem"] for p in voicelib.check_cast({"c": {"voice_id": "Hades"}})} == {"c": "male"}, "a male voice is flagged")

print("voicelib_test: {}".format("FAILED ({})".format(len(FAILS)) if FAILS else "all checks passed"))
sys.exit(1 if FAILS else 0)
