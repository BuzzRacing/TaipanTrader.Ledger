"""Queue 10 town crier pictures of Roxana Cama (cast key "narrator") on the live game (the Pi).

Each is her saved cast portrait prompt with the setting swapped for a different town crier moment and a
mood that suits it: 4 speaking, 2 happy, 2 angry, 2 sly. They are filed into Media Library > Personas >
Roxana with that mood role and tagged "town-crier".

Run from BIGBOX (the Pi trusts its Admin requests): Queue_Roxana_Crier_Pictures.bat, or
    python tools/queue_roxana_crier_pictures.py [server]      (default http://192.168.1.69:8765)
"""
import json
import sys
import urllib.request

SERVER = (sys.argv[1] if len(sys.argv) > 1 else "http://192.168.1.69:8765").rstrip("/")

HEAD = ("An unmistakably adult Parsi woman (age 41), commanding pirate first mate Roxana Cama acting as the port's "
        "town crier, fitted lacquer-black frock coat open over an ivory angrakha-cut corset, oxblood sash, black Parsi "
        "topi, sensual calculating gaze")
TAIL = (", everyone in the scene is a woman, no men, romanticized cinematic historical realism, "
        "China Seas 1860, humid salt haze, natural skin, weathered maritime materials, lacquer black, oxblood silk, "
        "antique brass, imperial jade, private-release adult erotic glamour, nudity including exposed breasts, "
        "buttocks or genitals and period-plausible consensual kink styling permitted when it suits the character "
        "and scene, clear agency, no explicit sex act or coercion, knees-up 3:4 portrait, hands visible, "
        "original face and garment design, no text")

SCENES = [
    ("speaking", "standing on an upturned tea crate on a crowded Hong Kong waterfront at morning, ringing a large brass "
                 "handbell high in one hand, an unrolled news sheet in the other, caught mid-proclamation, lips parted"),
    ("speaking", "on the stone steps of a colonial customs house, reading aloud from her black logbook to a gathered "
                 "crowd of dockside women, one hand raised for silence, lantern light at dusk"),
    ("speaking", "in a rain-slicked night market under red paper lanterns, calling out the news through a brass "
                 "speaking trumpet, a sheaf of printed bulletins tucked under her arm"),
    ("speaking", "beside the harbour notice board nailing up a printed bulletin of market prices, turning over her "
                 "shoulder to announce it to the crowd, hammer still in hand, mid-sentence"),
    ("happy", "on a dockside barrel ringing her handbell with a broad delighted smile, waving a news sheet announcing a "
              "great price boom, a cheering crowd of merchant women and tea porters around her"),
    ("happy", "at a busy wharf in bright morning sun reading out the arrival of a rich treasure fleet, a warm triumphant "
              "smile, gulls and tall clipper masts behind her"),
    ("angry", "in a grey storm on the harbour wall, coat whipping in the wind, reading out a warning of pirates and a "
              "port seizure, one hand thrust out in warning, stern furious glare, waves breaking behind"),
    ("angry", "on the customs house steps tearing a crumpled news sheet in half after announcing a market crash, "
              "jaw set, eyes blazing, brass chronometer hanging from her wrist"),
    ("sly", "leaning in a lantern-lit tavern doorway, handbell lowered, whispering a juicy rumour to the viewer with a "
            "conspiratorial half-smile, one finger raised to her lips"),
    ("sly", "winding her brass pocket chronometer on the empty quay at dawn, a folded scandal sheet peeking from her "
            "coat, a knowing sly smile as if she already knows tomorrow's news"),
]


def main():
    ok = 0
    for i, (mood, scene) in enumerate(SCENES, 1):
        job = {"kind": "persona", "subject": "narrator", "roles": [mood], "prompt": HEAD + ", " + scene + TAIL,
               "aspect": "3:4", "count": 1, "nsfw": "auto", "tags": "town-crier roxana-crier"}
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
