"""Queue 10 battle-scene pictures of Peggy "Powder" O'Rourke (cast key "bosun") on the live game (the Pi).

Each is her saved cast portrait prompt with the setting swapped for a different sea-battle moment and a
mood that suits it: 3 speaking, 3 happy, 2 angry, 2 sly. They are filed into Media Library > Personas >
Powder with that mood role and tagged "battle-scene".

Run from BIGBOX (the Pi trusts its Admin requests): Queue_Powder_Battle_Pictures.bat, or
    python tools/queue_powder_battle_pictures.py [server]      (default http://192.168.1.69:8765)
"""
import json
import sys
import urllib.request

SERVER = (sys.argv[1] if len(sys.argv) > 1 else "http://192.168.1.69:8765").rstrip("/")

HEAD = ("An unmistakably adult Irish woman (age 34), voluptuous pirate bosun and master gunner Peggy \"Powder\" "
        "O'Rourke, fitted tobacco-leather waistcoat, her naked breasts exposed, oxblood sash, red hair whipping loose, "
        "powder smudges on bare arms and cleavage")
TAIL = (", every sailor and warrior in the scene is a woman, no men, romanticized cinematic historical realism, "
        "China Seas 1860, humid salt haze, natural skin, weathered maritime materials, lacquer black, oxblood silk, "
        "antique brass, imperial jade, private-release adult erotic glamour, nudity including exposed breasts, "
        "buttocks or genitals and period-plausible consensual kink styling permitted when it suits the character "
        "and scene, clear agency, no explicit sex act or coercion, knees-up 3:4 portrait, hands visible, "
        "original face and garment design, no text")

SCENES = [
    ("speaking", "on the gun deck of a merchant ship, touching a smoking slow match to a brass cannon's touch-hole as "
                 "it fires, roaring the order down the line of guns, lips wide mid-shout, gunsmoke rolling past"),
    ("happy", "at the rail with a fist raised, cackling with delight as a ragged rust-sailed pirate junk breaks apart and "
              "sinks behind her, flames and splinters on the water, a fierce laughing grin"),
    ("angry", "knocked against a splintered gun carriage after an enemy hit, a smashed cannon beside her, smoke and "
              "flying splinters, soot on her face, bellowing curses, narrowed eyes and bared teeth, plainly furious"),
    ("sly", "crouched behind a loaded brass cannon at the gunport in grey dawn fog, one eye squinting down the barrel "
            "at a pirate junk drifting into range, a sly knowing half-smile, one finger to her lips"),
    ("speaking", "up on the ratlines in a gale with one arm hooked through the rigging, the other pointing at war "
                 "junks with blood-red sails on the horizon, red hair whipping in the wind, shouting a warning"),
    ("happy", "sitting astride a captured pirate cannon, swigging from a rum bottle, prize chests of tea and silver "
              "around her, a broad, triumphant, delighted grin"),
    ("angry", "on a burning, listing merchant deck, dragging a powder keg clear of the flames, smoke and embers all "
              "around, soot-streaked, jaw set, a sharp furious glare at the enemy"),
    ("sly", "below decks in the lantern-lit powder magazine, cradling a fused powder keg under one arm, a wicked "
            "conspiratorial smile as if about to send the enemy a present, one eyebrow raised"),
    ("speaking", "at the stern among her women gunners heaving a brass cannon into position, smoke and lantern light, "
                 "one hand on the barrel and caught mid-sentence as she gives orders, lips parted"),
    ("happy", "on a calm moonlit deck after the battle, leaning on a still-warm cannon with a rum bottle, enemy "
              "wreckage drifting on the water behind her, a satisfied, laughing grin"),
]


def main():
    ok = 0
    for i, (mood, scene) in enumerate(SCENES, 1):
        job = {"kind": "persona", "subject": "bosun", "roles": [mood], "prompt": HEAD + ", " + scene + TAIL,
               "aspect": "3:4", "count": 1, "nsfw": "auto", "tags": "battle-scene powder-battle"}
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
