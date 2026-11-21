"""Queue 12 shipyard pictures of Tang Wai-lin (cast key "shipwright") on the live game (the Pi).

She is the Master Shipwright & Queen of the Keel: the voice of the shipyard (a ship joins the fleet, a ship
is sold, guns are mounted, repairs are done). Each picture is her own look in a different moment at her
Whampoa yard with a mood that suits it, filed into Media Library > Personas > Tang Wai-lin with that mood
role, and tagged "shipyard tang-shipyard":
  10 NSFW   2 portrait, 3 speaking, 2 happy, 1 angry, 2 sly
   2 clean  1 portrait, 1 speaking, fully clothed, tagged "shipyard tang-shipyard, clean" (family-friendly screens)

Run from BIGBOX (the Pi trusts its Admin requests): Queue_Tang_Shipyard_Pictures.bat, or
    python tools/queue_tang_shipyard_pictures.py [server] [--dry]      (default http://192.168.1.69:8765)
"""
import json
import sys
import urllib.request

ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
DRY = "--dry" in sys.argv[1:]
SERVER = (ARGS[0] if ARGS else "http://192.168.1.69:8765").rstrip("/")

HEAD = ("An unmistakably adult Cantonese woman (age 56), Tang Wai-lin, muscular master shipwright and dockyard "
        "pirate queen, silver-streaked hair tied back, strong forearms and weathered hands, sawdust on "
        "sun-warmed skin")
NUDE = ("completely nude but for a fitted leather waist cincher and a linen shirt hanging wide open off her "
        "shoulders, her bare breasts and body shown openly, a leather tool belt slung low on her naked hips")
TAIL = (", every shipwright and sailor in the scene is a woman, no men, romanticized cinematic historical realism, "
        "China Seas 1860, humid salt haze, natural skin, weathered maritime materials, lacquer black, oxblood silk, "
        "antique brass, imperial jade, private-release adult erotic glamour, nudity including exposed breasts, "
        "buttocks or genitals and period-plausible consensual kink styling permitted when it suits the character "
        "and scene, clear agency, no explicit sex act or coercion, knees-up 3:4 portrait, hands visible, "
        "original face and garment design, no text")
CLEAN = (", wearing a sturdy buttoned linen work shirt with rolled sleeves, a leather shipwright's apron and "
         "loose trousers, fully and modestly clothed, no nudity, no cleavage, every shipwright in the scene is a "
         "woman, no men, romanticized cinematic historical realism, China Seas 1860, humid salt haze, natural "
         "skin, weathered maritime materials, lacquer black, oxblood silk, antique brass, imperial jade, waist-up "
         "3:4 portrait, hands visible, original face and garment design, no text")

SCENES = [
    ("portrait", "standing beside a half-built junk hull on the slipway of her Whampoa yard, adze resting on one "
                 "shoulder, golden afternoon light through the ribs of the hull, a proud gruff smile straight at "
                 "the viewer"),
    ("portrait", "leaning back against a stack of seasoned teak planks in the yard at dusk, arms folded, one "
                 "eyebrow raised, paper lanterns just lit along the slip, a warm teasing look"),
    ("speaking", "one hand flat on the fresh-tarred hull of a finished junk on launch day, the other arm sweeping "
                 "out to present her, caught mid-sentence naming her price, bunting and firecracker smoke behind"),
    ("speaking", "knocking her knuckles on the planking of an old hull hauled up for survey, head cocked to "
                 "listen, lips parted mid-verdict on what the last owner did to her"),
    ("speaking", "in the lantern-lit mould loft over a ship's plan chalked on the floor, a caulking mallet in one "
                 "hand, pointing down at the keel line and laying down the law"),
    ("happy", "watching a new junk slide down the slip into the Pearl River, head thrown back in a great laugh, "
              "one fist raised, spray and cheering women shipwrights around her"),
    ("happy", "patting the muzzle of a freshly mounted brass cannon on a junk's deck, a broad satisfied grin, "
              "rope tackle and blocks still rigged overhead"),
    ("angry", "holding up a rotten, worm-eaten plank torn from a badly repaired hull, jaw set and eyes blazing, "
              "plainly furious at whoever botched the work, the stripped hull behind her"),
    ("sly", "sitting on an upturned sampan weighing a purse of silver dollars in her palm, a sly sideways smile "
            "as if the price just went up, coils of rope and barrels of tung oil around her"),
    ("sly", "by lantern light inside the bare ribs of a hull, chisel in hand beside a small kingfisher she has "
            "just carved into the keel, one finger to her lips, a private knowing smile"),
]
CLEAN_SCENES = [
    ("portrait", "standing beside a half-built junk hull on the slipway of her Whampoa yard, adze resting on one "
                 "shoulder, golden afternoon light through the ribs of the hull, a proud gruff smile straight at "
                 "the viewer"),
    ("speaking", "one hand flat on the fresh-tarred hull of a finished junk on launch day, the other arm sweeping "
                 "out to present her, caught mid-sentence naming her price, bunting and firecracker smoke behind"),
]


def queue(job):
    req = urllib.request.Request(SERVER + "/api/admin/media/generate", data=json.dumps(job).encode("utf-8"),
                                 headers={"Content-Type": "application/json", "X-SeaTrader": "admin"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:                          # the Pi is off, or Admin asked for a password
        return {"ok": False, "error": str(e)}


def main():
    jobs = [(mood, "nsfw", {"kind": "persona", "subject": "shipwright", "roles": [mood],
                             "prompt": HEAD + ", " + scene + ", " + NUDE + TAIL, "aspect": "3:4", "count": 1,
                             "nsfw": "yes", "tags": "shipyard tang-shipyard"}) for mood, scene in SCENES]
    jobs += [(mood, "clean", {"kind": "persona", "subject": "shipwright", "roles": [mood],
                              "prompt": HEAD + ", " + scene + CLEAN, "aspect": "3:4", "count": 1,
                              "nsfw": "no", "tags": "shipyard tang-shipyard, clean"}) for mood, scene in CLEAN_SCENES]
    ok = 0
    for i, (mood, kind, job) in enumerate(jobs, 1):
        if DRY:
            print("\n== {:2}. {} {}\n{}".format(i, mood, kind.upper(), job["prompt"]))
            ok += 1
            continue
        res = queue(job)
        print("{:2}. {:8} {:5}  {}".format(i, mood, kind, res.get("msg") if res.get("ok") else "FAILED: " + str(res.get("error"))))
        ok += bool(res.get("ok"))
    print()
    print("{} of {} jobs {}.".format(ok, len(jobs), "shown" if DRY else "queued. Watch them in Admin > Media Library (jobs)"))
    return 0 if ok == len(jobs) else 1


if __name__ == "__main__":
    sys.exit(main())
