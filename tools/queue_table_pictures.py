"""Queue the Table's pictures on the live game (the Pi): painted top-down ships and the player-mat fabric.

Ships: one set per ship class (junk, lorcha, barque, clipper, indiaman, gunboat, countryship, flagship), painted as
seen from straight above, one ship alone on a plain white backdrop so the Table can lift it off the chart. Filed to
Media Library > Ships > (class) with the role "topdown", tagged "topdown table". 1:1. No people visible.

Fabric: the luxurious period cloth under each player mat (deep crimson silk-brocade, gold-thread damask, leather and
velvet). Filed to Media Library > Scenes > "Table: the period fabric under the player mat" (role "background"), 16:9,
tagged "table cloth". The Table picks one at random for each mat.

The Pi must already run the Table update (Deploy_To_Pi.bat), or it does not know the "topdown" role and the
"table_cloth" scene yet. Run from BIGBOX (the Pi trusts its Admin requests): Queue_Table_Pictures.bat, or
    python tools/queue_table_pictures.py [server] [ships|fabric] [count]
      server  default http://192.168.1.69:8765 (use http://127.0.0.1:8765 for the dev server)
      count   pictures per ship class (1-8, default 3) or fabrics (1-8, default 4)
"""
import json
import sys
import urllib.request

args = sys.argv[1:]
SERVER = (args[0] if args and args[0].startswith("http") else "http://192.168.1.69:8765").rstrip("/")
ONLY = next((a for a in args if a in ("ships", "fabric")), "")
NUM = next((int(a) for a in args if a.isdigit()), 0)

SHIP_HEAD = "A painted top-down view of "
SHIP_TAIL = (", seen from directly above (a bird's-eye plan view, bow pointing straight up), the whole ship fully in frame "
             "and centred with space round it, hand-painted gouache and ink in the style of an 1860 Chinese export "
             "painting, warm cream and cinnamon sails, dark teak deck, antique brass fittings, a small crimson pennant, "
             "the ship alone on a perfectly plain flat pure white background with no sea, no water, no wake, no shadow "
             "on the background, no people visible, no text, no watermark, square composition")

# config ship keys; same classes as the storm set.
SHIPS = [
    ("junk", "a Chinese junk, full battened sails spread"),
    ("lorcha", "a lorcha, a Portuguese hull with Chinese junk sails"),
    ("barque", "a three-masted barque under full sail"),
    ("clipper", "a slender tea clipper under towering sail"),
    ("indiaman", "a large East Indiaman merchant ship under full sail, gun ports along her sides"),
    ("gunboat", "a paddle gunboat with two side paddle wheels and a tall funnel, deck guns visible"),
    ("countryship", "a broad country ship, a heavy trading vessel with a deep hold and square sails"),
    ("flagship", "a great flagship ship-of-the-line with three gun decks, three masts and a tall poop deck"),
]

FABRIC = [
    "deep crimson silk brocade with a woven gold-thread damask pattern of coiled dragons and peonies",
    "oxblood red velvet table cloth with a gold bullion fringe and fine gold embroidery along the edge",
    "dark lacquer-red Chinese silk with an embroidered border of gold clouds and waves, thick tassels",
    "burnished crimson leather inlaid with brass studs and a gold-tooled border, worn and luxurious",
]
FABRIC_TAIL = (", a luxurious 1860 China trade-house table covering filling the whole frame edge to edge, seen from "
               "directly above in warm lamplight, rich folds and soft sheen, sumptuous and period-correct, nothing "
               "on it, no objects, no people, no text, no watermark, wide 16:9 composition")


def post(job):
    req = urllib.request.Request(SERVER + "/api/admin/media/generate", data=json.dumps(job).encode("utf-8"),
                                 headers={"Content-Type": "application/json", "X-SeaTrader": "admin"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:                      # the Pi is off, or Admin asked for a password
        return {"ok": False, "error": str(e)}


def main():
    ok = total = 0
    if ONLY in ("", "ships"):
        n = max(1, min(8, NUM)) if NUM else 3
        for key, ship in SHIPS:
            job = {"kind": "ship", "subject": key, "roles": ["topdown"], "prompt": SHIP_HEAD + ship + SHIP_TAIL,
                   "aspect": "1:1", "count": n, "nsfw": "no", "tags": "topdown table"}
            res = post(job)
            print("ship / {:12} x{}  {}".format(key, n, res.get("msg") if res.get("ok") else "FAILED: " + str(res.get("error"))))
            total += n
            ok += n if res.get("ok") else 0
    if ONLY in ("", "fabric"):
        n = max(1, min(8, NUM)) if NUM else 1
        for i, fab in enumerate(FABRIC):
            job = {"kind": "scene", "subject": "table_cloth", "roles": ["background"], "prompt": "A close view of " + fab + FABRIC_TAIL,
                   "aspect": "16:9", "count": n, "nsfw": "no", "tags": "table cloth"}
            res = post(job)
            print("scene / table_cloth {}  x{}  {}".format(i + 1, n, res.get("msg") if res.get("ok") else "FAILED: " + str(res.get("error"))))
            total += n
            ok += n if res.get("ok") else 0
    print()
    print("{} of {} pictures queued. Watch them in Admin > Media Library (jobs).".format(ok, total))
    return 0 if ok == total else 1


if __name__ == "__main__":
    sys.exit(main())
