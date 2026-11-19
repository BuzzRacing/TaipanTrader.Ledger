"""Queue 10 battle-scene pictures of Admiral Li Yue (cast key "pirate") on the live game (the Pi).

Each is her saved cast portrait prompt with the setting swapped for a different sea-battle moment and a
mood that suits it: 3 speaking, 3 happy, 2 angry, 2 sly. They are filed into Media Library > Personas >
Li Yue with that mood role (so the Sea Battle's right-hand seat can use them) and tagged "battle-scene".

Run from BIGBOX (the Pi trusts its Admin requests): Queue_Li_Yue_Battle_Pictures.bat, or
    python tools/queue_li_yue_battle_pictures.py [server]      (default http://192.168.1.69:8765)
"""
import json
import sys
import urllib.request

SERVER = (sys.argv[1] if len(sys.argv) > 1 else "http://192.168.1.69:8765").rstrip("/")

HEAD = ("An unmistakably adult Cantonese woman (age 48), formidable Qing-era pirate queen Admiral Li Yue, "
        "dark quilted silk robe falling open over sculpted leather armour and a daring bare décolletage, "
        "oxblood sash, elaborate pinned hair")
TAIL = (", every sailor and warrior in the scene is a woman, no men, romanticized cinematic historical realism, "
        "China Seas 1860, humid salt haze, natural skin, weathered maritime materials, lacquer black, oxblood silk, "
        "antique brass, imperial jade, private-release adult erotic glamour, nudity including exposed breasts, "
        "buttocks or genitals and period-plausible consensual kink styling permitted when it suits the character "
        "and scene, clear agency, no explicit sex act or coercion, knees-up 3:4 portrait, hands visible, "
        "original face and garment design, no text")

SCENES = [
    ("speaking", "standing at the bow of her black-lacquer war junk at dusk, one arm thrust forward giving the order "
                 "to fire, a row of bronze cannon flashing and belching gunsmoke behind her, blood-red sails overhead, "
                 "caught mid-command, lips parted"),
    ("happy", "on the stern deck at sunset watching a merchant ship burn and sink on the horizon, flames reflected in "
              "her eyes, a cold triumphant smile, one hand resting on the rail beside a single white peony"),
    ("angry", "drenched in a howling rainstorm mid-battle, a splintered rail and a cannonball hole torn through the "
              "blood-red sail behind her, sword gripped tight, narrowed eyes and set jaw, plainly furious"),
    ("sly", "in thick dawn fog on the poop deck, lowering a long brass spyglass after sighting a merchant fleet, a sly "
            "knowing half-smile, the faint shapes of her war junks waiting in the mist"),
    ("speaking", "leading a boarding action, one boot on the grappling-lashed gunwale between two ships, a curved dao "
                 "sword raised high as she commands her women warriors across, gunsmoke and torn rigging all around, "
                 "shouting the order"),
    ("happy", "on a captured merchant deck amid split chests of silver dollars, opium balls and bolts of silk, one foot "
              "up on a treasure chest, a broad delighted victorious smile, her women crew hauling plunder behind her"),
    ("angry", "with her own war junk on fire behind her, smoke and drifting embers, soot on her cheek, sword drawn, "
              "a sharp warning gesture, furious at the loss"),
    ("sly", "in her lantern-lit stern cabin bent over a lacquered sea chart, sliding carved jade junk markers into a "
            "trap while cannon flashes light the window behind her, a sly conspiratorial smile, one finger to her lips"),
    ("speaking", "on the smoky gun deck among her women gunners ramming powder into bronze cannon, lantern light and "
                 "drifting smoke, pointing at the enemy through the gunport, caught mid-shout"),
    ("happy", "under a full moon on a calm sea after the battle, floating wreckage and broken spars around her junk, "
              "holding a single white peony, a cold, satisfied, gloating smile, utterly calm"),
]


def main():
    ok = 0
    for i, (mood, scene) in enumerate(SCENES, 1):
        job = {"kind": "persona", "subject": "pirate", "roles": [mood], "prompt": HEAD + ", " + scene + TAIL,
               "aspect": "3:4", "count": 1, "nsfw": "auto", "tags": "battle-scene li-yue-battle"}
        req = urllib.request.Request(SERVER + "/api/admin/media/generate", data=json.dumps(job).encode("utf-8"),
                                     headers={"Content-Type": "application/json", "X-SeaTrader": "admin"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                res = json.loads(r.read().decode("utf-8"))
        except Exception as e:                      # the Pi is off, or Admin asked for a password
            res = {"ok": False, "error": str(e)}
        print("{:2}. {:8}  {}".format(i, mood, res.get("msg") if res.get("ok") else "FAILED: " + str(res.get("error"))))
        ok += bool(res.get("ok"))
    print()
    print("{} of {} jobs queued. Watch them in Admin > Media Library (jobs).".format(ok, len(SCENES)))
    return 0 if ok == len(SCENES) else 1


if __name__ == "__main__":
    sys.exit(main())
