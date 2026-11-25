"""Queue the Legends' background pictures on the live game (the Pi): the picture behind each chapter of a Legend.
Wide 16:9 scenes with nobody in them (the storyteller and the Legend's own people stand in front), filed in
Media Library > Scenes > "Legend: ..." with the role "background". Not NSFW.

The people (the three storytellers and each Legend's characters) are queued as NSFW + clean pairs by
tools/queue_persona_pairs.py; Queue_Legend_Pictures.bat runs both.

The Pi must already run the Legends update (Deploy_To_Pi.bat), or it doesn't know the scenes yet.
Run from BIGBOX (the Pi trusts its Admin requests): Queue_Legend_Pictures.bat, or
    python tools/queue_legend_pictures.py [server] [--count N] [--dry]      (default http://192.168.1.69:8765, 2 each)
"""
import json
import sys
import urllib.request

ARGS = sys.argv[1:]
SERVER = next((a for a in ARGS if a.startswith("http")), "http://192.168.1.69:8765").rstrip("/")
COUNT = int(ARGS[ARGS.index("--count") + 1]) if "--count" in ARGS else 2
DRY = "--dry" in ARGS

TAIL = (", nobody in the picture, no people, romanticized cinematic historical realism, China Seas 1860, humid salt "
        "haze, lacquer black, oxblood, antique brass, imperial jade, deep sea blue and lantern gold, moody and "
        "mysterious, room left in the middle for large lettering, wide 16:9 composition, no text")

# (scene key in media.SCENES, tag, what it shows)
SCENES = [
    ("legend", "legend",
     "The deck of a trading junk at night in a dead calm, a brass ship's bell frozen mid-swing in the foreground, "
     "fog lying on still black water, one lantern burning, an eerie blue-green glow rising from the sea"),
    ("legend_palace_turtle", "legend palace",
     "The wet deck of a trading junk at night off the Nagasaki roads, a huge ancient sea turtle with a shell like "
     "black lacquer and gold lying tangled in a fishing net, lantern light on its shell, the lights of Nagasaki "
     "harbour and its hills across the water"),
    ("legend_palace_palace", "legend palace",
     "A palace beneath the sea, great halls of red coral and black lacquer with gilded dragon carvings, pearl "
     "lanterns glowing, a long banquet table laid with gold dishes, shafts of green light falling through the water "
     "above, sea turtles gliding between the pillars"),
    ("legend_palace_box", "legend palace",
     "A ship captain's cabin by lamp light, a small black lacquer box tied with a red silk cord sitting on the chart "
     "table and glowing faintly from within, sea charts and a brass chronometer beside it, dark sea through the "
     "stern windows"),
    # ---- The second set (25 Nov 2026): three scenes for each of five Legends -------------------------------
    ("legend_jonah_fare", "legend jonah",
     "A busy Indian Ocean quay at dusk in 1860, a single empty gangway of a trading ship in the foreground, a "
     "heavy leather purse and a lace shawl left on a barrel, lantern light, crates and rope, ships' masts against "
     "an orange sky"),
    ("legend_jonah_storm", "legend jonah",
     "A trading junk's deck in a violent storm at night, enormous black waves, lightning splitting the sky, a "
     "ship's lantern swinging wildly, rain driving sideways, a closed cabin door at the stern with a thin line "
     "of warm light under it"),
    ("legend_jonah_truth", "legend jonah",
     "A harbour tavern table at dawn after a storm, a string of pearls and a rosary lying on a worn wooden table "
     "beside two cups, soft light through a shuttered window, calm masts outside"),
    ("legend_bond_paper", "legend bond",
     "A Singapore money-lender's counting house in 1860, a long lacquered desk with a rolled bond sealed in red "
     "wax, brass scales, stacks of silver dollars and an open ledger, tall windows onto the harbour and godowns"),
    ("legend_bond_stair", "legend bond",
     "A steep stone stairway down into a whitewashed colonial debtors' prison in Singapore, iron-barred doors, "
     "a single shaft of light on the steps, tropical foliage pressing at a small window"),
    ("legend_bond_day", "legend bond",
     "A Singapore waterfront at golden hour, a freshly painted trading ship with an empty quay beside it, a "
     "laid supper table with lanterns and bowls of tea, merchants' houses in the background"),
    ("legend_hunger_famine", "legend hunger",
     "A Saigon quay in a famine year in 1860, an almost empty rice market with bare wooden stalls, a few bags of "
     "rice on a barrow, a long patient queue of silent baskets, grey humid light over the river"),
    ("legend_hunger_hoard", "legend hunger",
     "Three tall shuttered river warehouses in Saigon at night, a single thread of lantern light under the "
     "doors, a heavy padlock and chain, bags of rice glimpsed through a crack, sampans moored beneath"),
    ("legend_hunger_noodles", "legend hunger",
     "A Saigon harbour quay buried in a river of long noodles, an enormous collapsed iron cauldron steaming in "
     "the background, upturned carts and paper lanterns, festive bunting torn down, comic and chaotic, warm light"),
    ("legend_robe_rocks", "legend robe",
     "A rocky Fujian shoreline below a sea goddess temple at moonrise, a gauzy robe of shimmering sea-silk folded "
     "on a flat black rock above the surf, red temple lanterns on the cliff, mist on the water"),
    ("legend_robe_wake", "legend robe",
     "The open sea at dawn behind the stern of a trading junk, a luminous path of foam running to the horizon, a "
     "brass compass and a silk-wrapped chest on the deck, fair wind filling the sails"),
    ("legend_robe_silk", "legend robe",
     "A ship captain's cabin at night with a carved sea chest open on the floor, folds of shimmering sea-silk "
     "spilling from it and glowing faintly blue-green, moonlight through the stern windows, rolled charts"),
    ("legend_ledger_page", "legend ledger",
     "A fish market at dawn in 1860, a torn page covered in fine red-inked writing wrapped around a silver fish "
     "on a wet slab, baskets, hanging lanterns and gutting knives, steam rising from the stalls"),
    ("legend_ledger_pages", "legend ledger",
     "A lamp-lit Saigon pawnshop back room, torn pages of a crimson ledger pinned across a wall with string "
     "between them like a map, a writing desk with a red pen and black coffee, dust motes in the lamp light"),
    ("legend_ledger_last", "legend ledger",
     "A captain's cabin chart table at night, a great open crimson ledger filling the table, lit by a single "
     "brass lamp, a brazier glowing beside it, shadow of rolling sea outside the stern windows"),
]


def post(job):
    req = urllib.request.Request(SERVER + "/api/admin/media/generate", data=json.dumps(job).encode("utf-8"),
                                 headers={"Content-Type": "application/json", "X-SeaTrader": "admin"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:                      # the Pi is off, or Admin asked for a password
        return {"ok": False, "error": str(e)}


def main():
    ok = 0
    for key, tags, desc in SCENES:
        job = {"kind": "scene", "subject": key, "roles": ["background"], "prompt": desc + TAIL, "aspect": "16:9",
               "count": COUNT, "nsfw": "no", "tags": tags}
        if DRY:
            print(key, "\n   ", job["prompt"], "\n")
            ok += 1
            continue
        res = post(job)
        print("{:24} {}".format(key, res.get("msg") if res.get("ok") else "FAILED: " + str(res.get("error"))))
        ok += bool(res.get("ok"))
    print()
    print("{} of {} scenes {}.".format(ok, len(SCENES), "printed" if DRY else "queued. Watch them in Admin > Media Library (jobs)"))
    return 0 if ok == len(SCENES) else 1


if __name__ == "__main__":
    sys.exit(main())
