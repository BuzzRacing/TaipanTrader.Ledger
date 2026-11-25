"""Queue 4 more battle-scene pictures of Admiral Li Yue (cast key "pirate") on the live game (the Pi).

She is the enemy's voice for the war junks in the Sea Battle (the right-hand seat). Each picture is her own
look with the setting swapped for a sea-battle moment she has not been shown in yet (the first ten are from
queue_li_yue_battle_pictures.py), filed into Media Library > Personas > Li Yue with that mood role and tagged
"battle-scene li-yue-battle-3":
  3 NSFW   speaking, happy, angry
  1 clean  sly, fully clothed, tagged "battle-scene li-yue-battle-3, clean" (family-friendly screens)

Run from BIGBOX (the Pi trusts its Admin requests): Queue_Li_Yue_Battle_Third_Set.bat, or
    python tools/queue_li_yue_battle_third_set.py [server] [--dry]      (default http://192.168.1.69:8765)
"""
import json
import sys
import urllib.request

ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
DRY = "--dry" in sys.argv[1:]
SERVER = (ARGS[0] if ARGS else "http://192.168.1.69:8765").rstrip("/")

HEAD = ("An unmistakably adult Cantonese woman (age 48), formidable Qing-era pirate queen Admiral Li Yue, "
        "elaborate pinned hair, oxblood sash, a single white peony pinned at her collar")
NUDE = ("completely naked except for a dark quilted silk robe slipping from her shoulders and falling open, her "
        "breasts and body shown openly, the oxblood sash tied low on her naked hips")
TAIL = (", every sailor and warrior in the scene is a woman, no men, romanticized cinematic historical realism, "
        "China Seas 1860, humid salt haze, natural skin, weathered maritime materials, lacquer black, oxblood silk, "
        "antique brass, imperial jade, private-release adult erotic glamour, nudity including exposed breasts, "
        "buttocks or genitals and period-plausible consensual kink styling permitted when it suits the character "
        "and scene, clear agency, no explicit sex act or coercion, knees-up 3:4 portrait, hands visible, "
        "original face and garment design, no text")
CLEAN = (", wearing a dark quilted silk robe fastened to a high collar over sculpted leather armour, fully and "
         "modestly clothed, no nudity, no cleavage, every sailor in the scene is a woman, no men, romanticized "
         "cinematic historical realism, China Seas 1860, humid salt haze, natural skin, weathered maritime "
         "materials, lacquer black, oxblood silk, antique brass, imperial jade, waist-up 3:4 portrait, hands "
         "visible, original face and garment design, no text")

SCENES = [
    ("speaking", "on the high quarterdeck of her black-lacquer flagship at night, a signal lantern raised in one "
                 "hand, calling the war junks into line of battle, a long column of blood-red sails and gun flashes "
                 "stretching behind her, caught mid-command, lips parted"),
    ("happy", "on the stern as a merchant fleet strikes its colours in the dawn light, bronze cannon smoking behind "
              "her, her women gunners cheering, a slow, cold, victorious smile, one hand resting on the rail"),
    ("angry", "at the mainmast of her flagship as a shot snaps the mizzen and burning canvas drops across the deck, "
              "sparks and smoke swirling, her women scrambling with buckets, sword drawn, jaw set, furious"),
]
CLEAN_SCENE = ("sly", "standing between two rows of run-out bronze cannon on the gun deck, tapping a closed ivory fan "
                      "against a gun barrel, a sly knowing half-smile as hidden war junks slide out of a sea mist "
                      "behind her to close the trap, one finger to her lips")


def queue(job):
    req = urllib.request.Request(SERVER + "/api/admin/media/generate", data=json.dumps(job).encode("utf-8"),
                                 headers={"Content-Type": "application/json", "X-SeaTrader": "admin"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:                          # the Pi is off, or Admin asked for a password
        return {"ok": False, "error": str(e)}


def main():
    jobs = [(mood, "nsfw", {"kind": "persona", "subject": "pirate", "roles": [mood],
                             "prompt": HEAD + ", " + scene + ", " + NUDE + TAIL, "aspect": "3:4", "count": 1,
                             "nsfw": "yes", "tags": "battle-scene li-yue-battle-3"}) for mood, scene in SCENES]
    mood, scene = CLEAN_SCENE
    jobs.append((mood, "clean", {"kind": "persona", "subject": "pirate", "roles": [mood],
                                 "prompt": HEAD + ", " + scene + CLEAN, "aspect": "3:4", "count": 1,
                                 "nsfw": "no", "tags": "battle-scene li-yue-battle-3, clean"}))
    ok = 0
    for i, (mood, kind, job) in enumerate(jobs, 1):
        if DRY:
            print("\n== {}. {} {}\n{}".format(i, mood, kind.upper(), job["prompt"]))
            ok += 1
            continue
        res = queue(job)
        print("{}. {:8} {:5}  {}".format(i, mood, kind, res.get("msg") if res.get("ok") else "FAILED: " + str(res.get("error"))))
        ok += bool(res.get("ok"))
    print()
    print("{} of {} jobs {}.".format(ok, len(jobs), "shown" if DRY else "queued. Watch them in Admin > Media Library (jobs)"))
    return 0 if ok == len(jobs) else 1


if __name__ == "__main__":
    sys.exit(main())
