"""Queue family-friendly pictures for the cargoes that change name when the game is family-friendly, on the
live game (the Pi): Opium shows as Fireworks and Arms as Ironware (Admin > Cargo > Family-friendly name).

They match the muslin product-shot set (Queue_Muslin_Cargo_Pictures.bat): the item alone on plain muslin,
square, no people, no text. Each is filed into Media Library > Cargo > <cargo> with the "family" role, tagged
"muslin product-shot family", and marked family-safe. A "family" picture shows only while the game (or one
screen) is family-friendly, in place of that cargo's own pictures; with NSFW on it stays hidden.

Run from BIGBOX (the Pi trusts its Admin requests): Queue_Family_Cargo_Pictures.bat, or
    python tools/queue_family_cargo_pictures.py [server] [count] [only]
      server  default http://192.168.1.69:8765 (use http://127.0.0.1:8765 for the dev server)
      count   pictures per cargo, 1-8 (default 3)
      only    queue just one cargo key: opium or arms
"""
import json
import sys
import urllib.request

SERVER = (sys.argv[1] if len(sys.argv) > 1 else "http://192.168.1.69:8765").rstrip("/")
try:
    COUNT = max(1, min(8, int(sys.argv[2]))) if len(sys.argv) > 2 else 3
except ValueError:
    COUNT = 3
ONLY = sys.argv[3].lower() if len(sys.argv) > 3 else ""

HEAD = ("Museum-quality studio product photograph, a single isolated still life of ")
TAIL = (", placed alone in the centre of the frame on a seamless backdrop of plain natural unbleached cream muslin "
        "cloth, softly draped with gentle folds, the muslin fills the whole background and floor, soft even diffused "
        "studio lighting, a soft natural contact shadow, crisp sharp focus on every detail of the item, true colours, "
        "the whole item fully in frame with space around it, authentic 1860 China trade period object, "
        "nothing else in the picture, no people, no hands, no text, no labels, no watermark, square composition")

# cargo key -> its family-friendly stand-in (what the picture shows)
CARGO = [
    ("opium", "Chinese fireworks for the 1860 export trade: an open red-lacquered wooden chest packed with bundles "
              "of red paper firecrackers on braided fuses, a few tall bamboo-stick sky rockets and round paper "
              "shells with gold paper trim, one long string of red firecrackers draped over the front of the chest"),
    ("arms", "ironware for the 1860 China trade: a neat group of black cast-iron cooking pots and a deep iron wok, "
             "a heavy iron kettle, a bundle of wrought-iron nails and bar iron tied with twine, beside an open "
             "wooden crate packed with straw"),
]


def main():
    ok = total = 0
    for key, item in CARGO:
        if ONLY and key != ONLY:
            continue
        job = {"kind": "cargo", "subject": key, "roles": ["family"], "prompt": HEAD + item + TAIL, "aspect": "1:1",
               "count": COUNT, "nsfw": "no", "tags": "muslin product-shot family"}
        req = urllib.request.Request(SERVER + "/api/admin/media/generate", data=json.dumps(job).encode("utf-8"),
                                     headers={"Content-Type": "application/json", "X-SeaTrader": "admin"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                res = json.loads(r.read().decode("utf-8"))
        except Exception as e:                      # the Pi is off, or Admin asked for a password
            res = {"ok": False, "error": str(e)}
        print("cargo / {:6} (family) x{}  {}".format(key, COUNT, res.get("msg") if res.get("ok") else
                                                     "FAILED: " + str(res.get("error"))))
        total += COUNT
        ok += COUNT if res.get("ok") else 0
    if not total:
        print("No cargo called '{}'. Use one of: {}".format(ONLY, ", ".join(k for k, _ in CARGO)))
        return 1
    print()
    print("{} of {} pictures queued. Watch them in Admin > Media Library (jobs).".format(ok, total))
    print("They need the new media.py on the Pi: run Deploy_To_Pi.bat first if you haven't.")
    return 0 if ok == total else 1


if __name__ == "__main__":
    sys.exit(main())
