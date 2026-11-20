"""Queue the Legends' background pictures on the live game (the Pi): the picture behind each chapter of a Legend.
Wide 16:9 scenes with nobody in them (the storyteller and the Legend's own people stand in front), filed in
Media Library > Scenes > "Legend: ..." with the role "background". Not NSFW.

The people (the three storytellers and each Legend's characters) are queued as NSFW + clean pairs by
tools/queue_persona_pairs.py; Queue_Legend_Pictures.bat runs both.

The Pi must already run the Legends update (Deploy_To_Pi.bat), or it doesn't know the scenes yet.
Run from BIGBOX (the Pi trusts its Admin requests): Queue_Legend_Pictures.bat, or
    python tools/queue_legend_pictures.py [server] [--count N] [--dry]      (default http://192.168.1.69:8765, 2 each)
"""
import json
import sys
import urllib.request

ARGS = sys.argv[1:]
SERVER = next((a for a in ARGS if a.startswith("http")), "http://192.168.1.69:8765").rstrip("/")
COUNT = int(ARGS[ARGS.index("--count") + 1]) if "--count" in ARGS else 2
DRY = "--dry" in ARGS

TAIL = (", nobody in the picture, no people, romanticized cinematic historical realism, China Seas 1860, humid salt "
        "haze, lacquer black, oxblood, antique brass, imperial jade, deep sea blue and lantern gold, moody and "
        "mysterious, room left in the middle for large lettering, wide 16:9 composition, no text")

# (scene key in media.SCENES, tag, what it shows)
SCENES = [
    ("legend", "legend",
     "The deck of a trading junk at night in a dead calm, a brass ship's bell frozen mid-swing in the foreground, "
     "fog lying on still black water, one lantern burning, an eerie blue-green glow rising from the sea"),
    ("legend_palace_turtle", "legend palace",
     "The wet deck of a trading junk at night off the Nagasaki roads, a huge ancient sea turtle with a shell like "
     "black lacquer and gold lying tangled in a fishing net, lantern light on its shell, the lights of Nagasaki "
     "harbour and its hills across the water"),
    ("legend_palace_palace", "legend palace",
     "A palace beneath the sea, great halls of red coral and black lacquer with gilded dragon carvings, pearl "
     "lanterns glowing, a long banquet table laid with gold dishes, shafts of green light falling through the water "
     "above, sea turtles gliding between the pillars"),
    ("legend_palace_box", "legend palace",
     "A ship captain's cabin by lamp light, a small black lacquer box tied with a red silk cord sitting on the chart "
     "table and glowing faintly from within, sea charts and a brass chronometer beside it, dark sea through the "
     "stern windows"),
]


def post(job):
    req = urllib.request.Request(SERVER + "/api/admin/media/generate", data=json.dumps(job).encode("utf-8"),
                                 headers={"Content-Type": "application/json", "X-SeaTrader": "admin"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:                      # the Pi is off, or Admin asked for a password
        return {"ok": False, "error": str(e)}


def main():
    ok = 0
    for key, tags, desc in SCENES:
        job = {"kind": "scene", "subject": key, "roles": ["background"], "prompt": desc + TAIL, "aspect": "16:9",
               "count": COUNT, "nsfw": "no", "tags": tags}
        if DRY:
            print(key, "\n   ", job["prompt"], "\n")
            ok += 1
            continue
        res = post(job)
        print("{:24} {}".format(key, res.get("msg") if res.get("ok") else "FAILED: " + str(res.get("error"))))
        ok += bool(res.get("ok"))
    print()
    print("{} of {} scenes {}.".format(ok, len(SCENES), "printed" if DRY else "queued. Watch them in Admin > Media Library (jobs)"))
    return 0 if ok == len(SCENES) else 1


if __name__ == "__main__":
    sys.exit(main())
