"""Queue the storm pictures on the live game (the Pi): 6 battered Roxana Cama pictures (cast key "narrator", the
sexy set) and 8 broken ships, one per ship class. 14 jobs. (The 6 clean Roxana pictures are
tools/queue_storm_clean_pictures.py.)

Roxana's are her saved cast portrait prompt, in the same house wording as her town crier set (HEAD and TAIL come
from queue_roxana_crier_pictures.py so the style matches her cast card), with a storm scene swapped in: bruised,
soaked, torn, defiant. They go in Media Library > Personas > Roxana with the role "storm", tagged "storm". NSFW is
left on "auto" like the crier set.

The ships go in Media Library > Ships > (class) with the role "wrecked", 16:9, women crew only: the broken ship
behind her on the storm screen after a heavy or savage storm.

The Pi must already run the storm update (Deploy_To_Pi.bat), or it doesn't know the roles "storm" and "wrecked".
Run from BIGBOX (the Pi trusts its Admin requests): Queue_Storm_Pictures.bat, or
    python tools/queue_storm_pictures.py [server] [roxana|ships]      (default http://192.168.1.69:8765, both)
"""
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from queue_roxana_crier_pictures import HEAD as _CRIER_HEAD, TAIL  # noqa: E402  (the house wording)

SERVER = (sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].startswith("http") else "http://192.168.1.69:8765").rstrip("/")
ONLY = next((a for a in sys.argv[1:] if a in ("roxana", "ships")), "")

HEAD = _CRIER_HEAD.replace(" acting as the port's town crier", " after a storm at sea") + ", bruised and battered"

SCENES = [
    "clinging to the splintered mainmast rail in a lightning night, her corset seam torn, coat slipping off one shoulder, "
    "a bruised collarbone and a split lip, her black logbook held high above the sea water, defiant",
    "slumped on a sea chest in the wrecked captain's cabin, soaked linen clinging to her, one forearm bandaged, a cracked "
    "brass chronometer in her lap, a worn, sly smile",
    "at the broken ship's helm in driving rain, hair loose and streaming, one sleeve torn away, rope-burned wrists, "
    "shouting into the gale",
    "sitting on a cargo hatch bandaging her ankle, skirt torn high on the thigh, a bruised knee, looking up through her "
    "lashes with a rueful smile, rain dripping from her topi",
    "knee-deep in the flooded hold by lantern light, the lantern held high, counting the loss in her black log, soaked "
    "through, a smear of tar on her cheek",
    "leaning against a smashed gun carriage, smoke and rain around her, one shoulder scraped raw, a rueful half-smile",
]

# One broken ship per class (config ship keys); women crew only.
SHIPS = [
    ("junk", "a Chinese junk, dismasted, its battened sails in tatters, listing hard to one side"),
    ("lorcha", "a lorcha, mainmast snapped, rigging trailing in the water, her deck awash"),
    ("barque", "a three-masted barque, foremast gone and the other two stripped of canvas, hull stove in at the bow"),
    ("clipper", "a tea clipper, her tall masts broken and trailing, sails shredded, heeled over on her side"),
    ("indiaman", "a large East Indiaman, mizzen gone, gunports burst and shipping water, listing badly"),
    ("gunboat", "a paddle gunboat, one paddle wheel smashed and the funnel toppled, deck guns torn from their mountings"),
    ("countryship", "a country ship, hatches stove in and bales of cargo floating in the sea around her, her masts leaning"),
    ("flagship", "a great flagship ship-of-the-line, two masts down, torn pennants and shattered gun ports, sinking by the stern"),
]
SHIP_TAIL = (", a small crew of women in oilskins clinging to the wreck, everyone in the scene is a woman, no men, "
             "grey storm sea and heavy clouds at dusk, rain and spray, romanticized cinematic historical realism, "
             "China Seas 1860, weathered maritime materials, lacquer black, oxblood, antique brass, wide 16:9 "
             "composition, no text")


def post(job):
    req = urllib.request.Request(SERVER + "/api/admin/media/generate", data=json.dumps(job).encode("utf-8"),
                                 headers={"Content-Type": "application/json", "X-SeaTrader": "admin"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            res = json.loads(r.read().decode("utf-8"))
    except Exception as e:                      # the Pi is off, or Admin asked for a password
        res = {"ok": False, "error": str(e)}
    return res


def jobs():
    out = []
    if ONLY in ("", "roxana"):
        for i, scene in enumerate(SCENES, 1):
            out.append(("roxana {}".format(i), {"kind": "persona", "subject": "narrator", "roles": ["storm"],
                        "prompt": HEAD + ", " + scene + TAIL, "aspect": "3:4", "count": 1, "nsfw": "auto",
                        "tags": "storm roxana-storm"}))
    if ONLY in ("", "ships"):
        for key, desc in SHIPS:
            out.append(("ship " + key, {"kind": "ship", "subject": key, "roles": ["wrecked"],
                        "prompt": desc[0].upper() + desc[1:] + SHIP_TAIL, "aspect": "16:9", "count": 1, "nsfw": "no",
                        "tags": "storm wrecked"}))
    return out


def main():
    todo = jobs()
    ok = 0
    for name, job in todo:
        res = post(job)
        print("{:14} {}".format(name, res.get("msg") if res.get("ok") else "FAILED: " + str(res.get("error"))))
        ok += bool(res.get("ok"))
    print()
    print("{} of {} jobs queued. Watch them in Admin > Media Library (jobs).".format(ok, len(todo)))
    return 0 if ok == len(todo) else 1


if __name__ == "__main__":
    sys.exit(main())
