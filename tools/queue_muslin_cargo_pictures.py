"""Queue a clean product-shot set of every cargo on a plain muslin backdrop, on the live game (the Pi).

Each cargo is photographed alone, centred and sharp, on a softly draped unbleached muslin cloth under even
studio light, so you can see exactly what the item is. No people, no text, square (1:1) like the market icons.
They are filed into Media Library > Cargo > <cargo> with the "icon" role, tagged "muslin product-shot",
and marked family-safe (not NSFW). They join the pictures already there; pick favourites / set primary in the
Media Library.

Run from BIGBOX (the Pi trusts its Admin requests): Queue_Muslin_Cargo_Pictures.bat, or
    python tools/queue_muslin_cargo_pictures.py [server] [count] [only]
      server  default http://192.168.1.69:8765 (use http://127.0.0.1:8765 for the dev server)
      count   pictures per cargo, 1-8 (default 3)
      only    queue just one cargo key: opium, gold, silk, porcelain, arms, spices, tea, rice or general
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

# key -> what the item looks like (matches config.py goods)
CARGO = [
    ("opium", "a chest of Indian opium for the 1860 China trade: an open dark mango-wood chest with its lid up, packed "
              "with round dark brown opium cakes wrapped in dried poppy petals, two cakes set out in front"),
    ("gold", "gold bullion for the 1860 China trade: a small stack of gleaming gold ingots and Chinese boat-shaped "
             "gold sycee, beside a small open leather pouch spilling gold coins"),
    ("silk", "Chinese silk for the 1860 export trade: several neatly folded and rolled bolts of lustrous silk in "
             "crimson, imperial yellow, jade green and ivory, one bolt partly unrolled to show its sheen and woven "
             "pattern"),
    ("porcelain", "blue-and-white Chinese export porcelain for the 1860 trade: a lidded ginger jar, a tall vase and a "
                  "stack of plates and bowls with hand-painted cobalt blue designs"),
    ("arms", "trade arms of 1860: a pair of muzzle-loading percussion rifles laid on top of an open unmarked wooden crate "
             "with a powder flask, a small keg of gunpowder and a few lead shot"),
    ("spices", "spices for the 1860 East Indies trade: open hessian sacks and small wooden bowls heaped with black "
               "pepper, cinnamon bark quills, whole nutmegs with red mace, cloves and star anise"),
    ("tea", "China tea for the 1860 export trade: a painted wooden tea chest with its lid off, lined with lead foil "
            "and full of dark twisted loose-leaf tea, a small scoop and a scattering of leaves in front"),
    ("rice", "rice for the 1860 China trade: a tightly bound woven straw rice sack and an open hessian sack overflowing "
             "with white grains of rice, a wooden measuring scoop in front"),
    ("general", "general cargo for an 1860 merchant ship: a tidy group of a small wooden barrel, a rope-bound wooden "
                "crate, a coil of hemp rope and a bundle wrapped in oilcloth and twine"),
]


def main():
    ok = total = 0
    for key, item in CARGO:
        if ONLY and key != ONLY:
            continue
        job = {"kind": "cargo", "subject": key, "roles": ["icon"], "prompt": HEAD + item + TAIL, "aspect": "1:1",
               "count": COUNT, "nsfw": "no", "tags": "muslin product-shot"}
        req = urllib.request.Request(SERVER + "/api/admin/media/generate", data=json.dumps(job).encode("utf-8"),
                                     headers={"Content-Type": "application/json", "X-SeaTrader": "admin"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                res = json.loads(r.read().decode("utf-8"))
        except Exception as e:                      # the Pi is off, or Admin asked for a password
            res = {"ok": False, "error": str(e)}
        print("cargo / {:10} x{}  {}".format(key, COUNT, res.get("msg") if res.get("ok") else
                                              "FAILED: " + str(res.get("error"))))
        total += COUNT
        ok += COUNT if res.get("ok") else 0
    if not total:
        print("No cargo called '{}'. Use one of: {}".format(ONLY, ", ".join(k for k, _ in CARGO)))
        return 1
    print()
    print("{} of {} pictures queued. Watch them in Admin > Media Library (jobs).".format(ok, total))
    return 0 if ok == total else 1


if __name__ == "__main__":
    sys.exit(main())
