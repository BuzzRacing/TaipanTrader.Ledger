"""Queue 11 battle-scene pictures of Madam Shek Yu-lan (cast key "agent") on the live game (the Pi).

She is the enemy's voice for ordinary pirate junks in the Sea Battle (Admiral Li Yue speaks for her war
junks). Each picture is her own look with the setting swapped for a sea-battle moment and a mood that
suits it, filed into Media Library > Personas > Madam Shek with that mood role, so the Sea Battle's
right-hand seat can use them, and tagged "battle-scene shek-battle":
  10 NSFW   3 speaking, 2 happy, 2 angry, 3 sly (her bargain whispers use sly, raising the price angry)
   1 clean  speaking, fully clothed, tagged "battle-scene shek-battle, clean" (family-friendly screens)

Run from BIGBOX (the Pi trusts its Admin requests): Queue_Shek_Battle_Pictures.bat, or
    python tools/queue_shek_battle_pictures.py [server] [--dry]      (default http://192.168.1.69:8765)
"""
import json
import sys
import urllib.request

ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
DRY = "--dry" in sys.argv[1:]
SERVER = (ARGS[0] if ARGS else "http://192.168.1.69:8765").rstrip("/")

HEAD = ("An unmistakably adult Macanese-Chinese woman (age 37), Madam Shek Yu-lan, the pirate queen's dangerously "
        "glamorous agent, sleek black hair pinned with jade combs, a red silk protection token tied at her wrist")
NUDE = ("completely nude but for an oxblood silk jacket with sheer sleeves slipping from her shoulders and falling "
        "open, her bare breasts and body shown openly, jade earrings and a gold coin belt low on her naked hips")
TAIL = (", every sailor and warrior in the scene is a woman, no men, romanticized cinematic historical realism, "
        "China Seas 1860, humid salt haze, natural skin, weathered maritime materials, lacquer black, oxblood silk, "
        "antique brass, imperial jade, private-release adult erotic glamour, nudity including exposed breasts, "
        "buttocks or genitals and period-plausible consensual kink styling permitted when it suits the character "
        "and scene, clear agency, no explicit sex act or coercion, knees-up 3:4 portrait, hands visible, "
        "original face and garment design, no text")
CLEAN = (", wearing a fitted oxblood Qing-era silk jacket buttoned to a high collar, fully and modestly clothed, "
         "no nudity, no cleavage, every sailor in the scene is a woman, no men, romanticized cinematic historical "
         "realism, China Seas 1860, humid salt haze, natural skin, weathered maritime materials, lacquer black, "
         "oxblood silk, antique brass, imperial jade, waist-up 3:4 portrait, hands visible, original face and "
         "garment design, no text")

SCENES = [
    ("speaking", "standing at the rail of a pirate junk with patched brown sails as it closes on a merchant ship, "
                 "one arm flung out pointing at the prey, caught mid-shout calling out terms across the water"),
    ("sly", "leaning on the gunwale in thick dawn fog, weighing a coin on her tiny ivory balance, a sly knowing "
            "half-smile as if she has already guessed what is in your hold, the shapes of pirate junks in the mist"),
    ("sly", "in a small lantern-lit boat drawn alongside your ship to bargain, red silk token held up between two "
            "fingers, one finger to her lips, a conspiratorial smile, a cheap price on offer"),
    ("angry", "on the pirate deck after her price was refused, snapping her ivory balance shut, narrowed eyes and set "
              "jaw, a sharp gesture to the gunners behind her to run out the guns"),
    ("speaking", "on the smoky deck among her women gunners at the swivel guns, pointing at the enemy through the "
                 "gunsmoke, lips parted mid-command, lantern light and torn rigging"),
    ("happy", "watching a cannonball tear through a merchant's sail, laughing with delight, one hand on the rigging, "
              "smoke and splinters drifting past"),
    ("angry", "drenched in spray with a splintered rail and a smoking hole in the brown sail behind her, soot on her "
              "cheek, plainly furious that the merchant fights back"),
    ("speaking", "at the head of a boarding party on the grappling-lashed gunwale between two ships, a slim curved "
                 "dao in one hand, shouting her women across, gunsmoke and tangled rope all around"),
    ("happy", "on a captured merchant deck amid split chests of silver dollars and bolts of silk, one foot up on a "
              "chest, counting coins onto her ivory balance with a delighted victorious smile"),
    ("sly", "at the stern under a full moon as the battle ends, floating wreckage on a calm sea, slipping a red silk "
            "token into her sash, a cool satisfied half-smile, utterly unhurried"),
]
CLEAN_SCENE = ("speaking", "standing at the rail of a pirate junk with patched brown sails as it closes on a merchant "
                           "ship, one arm flung out pointing at the prey, caught mid-shout calling out terms across "
                           "the water, red silk token between two fingers")


def queue(job):
    req = urllib.request.Request(SERVER + "/api/admin/media/generate", data=json.dumps(job).encode("utf-8"),
                                 headers={"Content-Type": "application/json", "X-SeaTrader": "admin"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:                          # the Pi is off, or Admin asked for a password
        return {"ok": False, "error": str(e)}


def main():
    jobs = [(mood, "nsfw", {"kind": "persona", "subject": "agent", "roles": [mood],
                             "prompt": HEAD + ", " + scene + ", " + NUDE + TAIL, "aspect": "3:4", "count": 1,
                             "nsfw": "yes", "tags": "battle-scene shek-battle"}) for mood, scene in SCENES]
    mood, scene = CLEAN_SCENE
    jobs.append((mood, "clean", {"kind": "persona", "subject": "agent", "roles": [mood],
                                 "prompt": HEAD + ", " + scene + CLEAN, "aspect": "3:4", "count": 1,
                                 "nsfw": "no", "tags": "battle-scene shek-battle, clean"}))
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
