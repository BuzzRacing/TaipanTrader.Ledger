"""Queue very wide SWIMSUIT-EDITION banners for the Dashboard masthead (several scene options).

Each picture is one persona reclining on her side along the shoreline in the exact middle of a 16:5 frame (the widest the farm makes),
camera at sand level so her whole figure is a thin horizontal band, with the scene carrying on to the left and right of her.
The Dashboard crops the strip to that band. Filed under Personas > (her name), role "wallpaper", tagged
"masthead-banner, swimsuit, <scene>". Nothing is replaced or deleted. Original women only; the look is the game's own.

Usage (run on BIGBOX; the Pi trusts its Admin requests):
    python tools/queue_masthead_banners.py                        # every scene, both women, 1 picture each
    python tools/queue_masthead_banners.py --scenes cove,lagoon --count 3
    python tools/queue_masthead_banners.py --who gamemaster --dry
Options: --who, --scenes (name,name or all), --count per scene (1-8), --aspect, --server, --rating (yes = NSFW flag, no = family), --dry
"""
import argparse
import json
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import persona_prompts_v2 as pp  # noqa: E402

DEFAULT_WHO = "gamemaster,bookkeeper"

# What each woman wears and keeps on (her face and hair stay hers).
SWIM = {
    "gamemaster": "dark hair loose and wet over one shoulder, a small gold diadem, a ruby collar necklace, a crimson silk two-piece swimsuit trimmed in gold braid",
    "bookkeeper": "dark hair loose and wind-tossed, gold wire spectacles pushed up into her hair, an oxblood two-piece swimsuit with brass buckles",
}
GENERIC_SWIM = "hair loose and wet, a sleek two-piece swimsuit in the colours of her own look"

# name: (what is to the left and right of her, light)
SCENES = {
    "cove": ("a sandy Hong Kong cove in 1860, red-sailed junks and a tall black clipper anchored on the water to both sides of her, green hills and a pier in the haze",
             "golden hour, warm low sun, long soft shadows, gleaming wet sand"),
    "lagoon": ("a turquoise tropical lagoon, palms leaning in from both edges, a wooden pier to one side and a sampan with a paper lantern to the other",
               "bright noon sparkle on shallow water, white sand, crisp blue sky"),
    "sandbar": ("a long pale sandbar with surf rolling in, rocky headlands and a lighthouse on one side, a distant fleet of junk sails on the other",
                "sunrise, pink and gold sky, mist on the water, dew-bright sand"),
    "moonlit": ("a moonlit beach, strings of red paper lanterns and beached junks to both sides, a glowing harbour far behind",
                "silver moonlight and lantern glow, deep blue night, warm skin highlights"),
    "storm": ("a wild beach under a rolling storm sky, heavy surf and a wrecked mast on the sand to one side, a ship riding out the swell on the other",
              "dramatic breaking light through storm clouds, wet glistening sand, spray in the air"),
}
COMPOSE = ("an ultra-wide panoramic banner, shot at sand level with an extreme low camera, she reclines on her side along the shoreline "
           "dead centre of the frame, propped on one elbow, her whole figure forming a thin horizontal band across the middle of the picture, "
           "open sky and sea above her and nothing tall behind her, the scene carrying on symmetrically to the left and right")
TAIL = (", romanticized 1860 China Seas swimsuit-edition editorial photograph, glossy skin with sea spray and grains of sand, confident direct gaze, "
        "rich depth and atmosphere, ultra-wide panoramic banner")


def build(cid, scene):
    look = pp.LOOKS[cid]
    who = ",".join(look["who"].format(adult=pp.ADULT).split(",")[:2])      # "An adult ... woman (age N), Name"
    left_right, light = SCENES[scene]
    return "An " + who + ", " + SWIM.get(cid, GENERIC_SWIM) + ", " + COMPOSE + ", " + left_right + ", " + light + TAIL


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--who", default=DEFAULT_WHO)
    ap.add_argument("--scenes", default="all")
    ap.add_argument("--count", type=int, default=1)
    ap.add_argument("--aspect", default="16:5")
    ap.add_argument("--rating", default="yes", choices=("yes", "no"))
    ap.add_argument("--server", default="http://192.168.1.69:8765")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    server = a.server.rstrip("/")
    who = [w.strip() for w in a.who.split(",") if w.strip()]
    scenes = list(SCENES) if a.scenes.strip().lower() == "all" else [s.strip() for s in a.scenes.split(",") if s.strip()]
    bad = [w for w in who if w not in pp.LOOKS] + [s for s in scenes if s not in SCENES]
    if bad:
        print("Unknown:", ", ".join(bad), "| scenes:", ", ".join(SCENES))
        return 1
    ok = total = 0
    for cid in who:
        for scene in scenes:
            total += 1
            prompt = build(cid, scene)
            job = {"kind": "persona", "subject": cid, "roles": ["wallpaper"], "prompt": prompt[:6000], "aspect": a.aspect,
                   "count": max(1, min(8, a.count)), "nsfw": a.rating,
                   "tags": "masthead-banner, swimsuit, " + scene}
            if a.dry:
                print("\n== {} / {}\n{}".format(cid, scene, prompt))
                ok += 1
                continue
            req = urllib.request.Request(server + "/api/admin/media/generate", data=json.dumps(job).encode("utf-8"),
                                         headers={"Content-Type": "application/json", "X-SeaTrader": "admin"})
            try:
                with urllib.request.urlopen(req, timeout=20) as r:
                    res = json.loads(r.read().decode("utf-8"))
            except Exception as e:                  # the Pi is off, or Admin asked for a password
                res = {"ok": False, "error": str(e)}
            print("{:12} {:9} {}".format(cid, scene, res.get("msg") if res.get("ok") else "FAILED: " + str(res.get("error"))))
            ok += bool(res.get("ok"))
    print("\n{} of {} jobs {}.".format(ok, total, "shown" if a.dry else "queued. Watch them in Admin > Media Library (jobs), tag masthead-banner"))
    return 0 if ok == total and total else 1


if __name__ == "__main__":
    sys.exit(main())
