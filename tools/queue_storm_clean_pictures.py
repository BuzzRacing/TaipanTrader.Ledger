"""Queue 6 clean (not NSFW) battered Roxana Cama pictures on the live game (the Pi): the same six storm scenes as
tools/queue_storm_pictures.py, dressed, with a clean style line, filed as NOT NSFW and tagged "storm, clean". They
go in Media Library > Personas > Roxana with the role "storm", next to the sexy set. Family-friendly screens show
only these; other screens show the sexy set first (web/storm.js), and these if she has no other.

The Pi must already run the storm update (Deploy_To_Pi.bat), or it doesn't know the role "storm".
Run from BIGBOX (the Pi trusts its Admin requests): Queue_Storm_Clean_Pictures.bat, or
    python tools/queue_storm_clean_pictures.py [server]      (default http://192.168.1.69:8765)
"""
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from queue_storm_pictures import HEAD, SERVER, post  # noqa: E402

STYLE = (", fully and modestly clothed, no nudity, romanticized cinematic historical realism, China Seas 1860, "
         "humid salt haze, natural skin, weathered maritime materials, lacquer black, oxblood silk, antique brass, "
         "imperial jade, knees-up 3:4 portrait, hands visible, original face and garment design, no text")

# The six scenes, dressed: soaked and scuffed, not torn open.
SCENES = [
    "clinging to the splintered mainmast rail in a lightning night, her coat soaked and buttoned, a bruise on her "
    "cheek and a split lip, her black logbook held high above the sea water, defiant",
    "slumped on a sea chest in the wrecked captain's cabin, soaked in her coat and sash, one forearm bandaged, a "
    "cracked brass chronometer in her lap, a worn, sly smile",
    "at the broken ship's helm in driving rain, hair loose and streaming, her coat torn at one sleeve, "
    "rope-burned wrists, shouting into the gale",
    "sitting on a cargo hatch bandaging her ankle over her boot, long skirt muddy and scuffed, looking up with a "
    "rueful smile, rain dripping from her topi",
    "knee-deep in the flooded hold by lantern light, the lantern held high, counting the loss in her black log, "
    "soaked through in her coat, a smear of tar on her cheek",
    "leaning against a smashed gun carriage, smoke and rain around her, her coat scuffed, a rueful half-smile",
]


def main():
    # Clean HEAD: the house HEAD describes a corset; keep it dressed.
    head = HEAD.replace("open over an ivory angrakha-cut corset", "buttoned over an ivory angrakha blouse")
    head = head.replace("sensual calculating gaze", "calculating gaze")
    ok = 0
    for i, scene in enumerate(SCENES, 1):
        job = {"kind": "persona", "subject": "narrator", "roles": ["storm"], "prompt": head + ", " + scene + STYLE,
               "aspect": "3:4", "count": 1, "nsfw": "no", "tags": "storm, clean"}
        res = post(job)
        print("clean {}  {}".format(i, res.get("msg") if res.get("ok") else "FAILED: " + str(res.get("error"))))
        ok += bool(res.get("ok"))
    print()
    print("{} of {} jobs queued. Watch them in Admin > Media Library (jobs).".format(ok, len(SCENES)))
    return 0 if ok == len(SCENES) else 1


if __name__ == "__main__":
    sys.exit(main())
