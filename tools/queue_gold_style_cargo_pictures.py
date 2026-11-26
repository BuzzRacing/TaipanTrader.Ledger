"""Queue the whole cargo catalog in the "gold" muslin product-shot style, with the product LARGE in the frame.

Same look as the muslin gold picture (Queue_Muslin_Cargo_Pictures.bat): one item alone on softly draped
unbleached cream muslin, studio light, no people, no text, square. The difference is the framing: the camera is
close and the product fills about four fifths of the picture, with only a narrow margin of muslin round it, so
the icon reads at market size.

All 15 cargoes (the original nine and the six Cargo Tiers luxuries) plus the two family-friendly stand-ins
(Fireworks for Opium, Ironware for Arms). Filed to Media Library > Cargo:
    the 15 cargoes        role "icon",   tags "muslin product-shot large"
    the 2 stand-ins       role "family", tags "muslin product-shot large family"
They join the pictures already there; pick favourites / set primary in the Media Library. Nothing is deleted.

Every prompt goes through tools/theme_guard.py first; nothing is queued if a modern word slips in.

Run from BIGBOX (the Pi trusts its Admin requests): Queue_Gold_Style_Cargo_Pictures.bat, or
    python tools/queue_gold_style_cargo_pictures.py [server] [count] [only] [--dry]
      server  default http://192.168.1.69:8765 (use http://127.0.0.1:8765 for the dev server)
      count   pictures per cargo, 1-8 (default 3)
      only    just one cargo: opium, gold, silk, porcelain, arms, spices, tea, rice, general, camphor, sandalwood,
              ginseng, jade, pearls, ambergris (opium and arms also queue their family stand-in)
              or "family" for just the two stand-ins, or "luxuries" for just the six new ones
      --dry   print the prompts and queue nothing
Deploy the Cargo Tiers data to the Pi first (Deploy_To_Pi.bat), or the Pi will not know the six luxuries.
"""
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import theme_guard  # noqa: E402

ARGS = [a for a in sys.argv[1:] if a != "--dry"]
DRY = "--dry" in sys.argv[1:]
SERVER = (ARGS[0] if len(ARGS) > 0 else "http://192.168.1.69:8765").rstrip("/")
try:
    COUNT = max(1, min(8, int(ARGS[1]))) if len(ARGS) > 1 else 3
except ValueError:
    COUNT = 3
ONLY = ARGS[2].lower() if len(ARGS) > 2 else ""

HEAD = ("Museum-quality studio product photograph, a tight close-up still life of ")
TAIL = (", the items packed closely together as one compact group, centred on a seamless backdrop of plain natural "
        "unbleached cream muslin cloth with gentle soft folds, shot from close in with the camera near so the product "
        "is LARGE in the frame and fills about 80 percent of the picture, only a narrow margin of muslin visible "
        "around it, nothing cut off at the edges, soft even diffused studio lighting, a soft natural contact shadow, "
        "crisp sharp focus across every detail of the item, true colours, authentic 1860 China trade period object, "
        "nothing else in the picture, no people, no hands, no text, no labels, no watermark, square composition")

# (cargo key, group, what the item looks like). group: "base" the original nine, "luxury" the Cargo Tiers six,
# "family" the family-friendly stand-ins (filed with the "family" role).
CARGO = [
    ("opium", "base", "a chest of Indian opium for the 1860 China trade: an open dark mango-wood chest with its lid up, "
                      "packed with round dark brown opium cakes wrapped in dried poppy petals, two cakes set out in "
                      "front"),
    ("gold", "base", "gold bullion for the 1860 China trade: a stack of gleaming gold ingots and Chinese boat-shaped "
                     "gold sycee, beside an open leather pouch spilling gold coins"),
    ("silk", "base", "Chinese silk for the 1860 export trade: several neatly folded and rolled bolts of lustrous silk "
                     "in crimson, imperial yellow, jade green and ivory, one bolt partly unrolled to show its sheen "
                     "and woven pattern"),
    ("porcelain", "base", "blue-and-white Chinese export porcelain for the 1860 trade: a lidded ginger jar, a tall "
                          "vase and a stack of plates and bowls with hand-painted cobalt blue designs"),
    ("arms", "base", "trade arms of 1860: a pair of muzzle-loading percussion muskets laid on top of an open unmarked "
                     "wooden crate with a powder flask, a small keg of gunpowder and a few lead shot"),
    ("spices", "base", "spices for the 1860 East Indies trade: open hessian sacks and small wooden bowls heaped with "
                       "black pepper, cinnamon bark quills, whole nutmegs with red mace, cloves and star anise"),
    ("tea", "base", "China tea for the 1860 export trade: a painted wooden tea chest with its lid off, lined with "
                    "lead foil and full of dark twisted loose-leaf tea, a small scoop and a scattering of leaves in "
                    "front"),
    ("rice", "base", "rice for the 1860 China trade: a tightly bound woven straw rice sack and an open hessian sack "
                     "overflowing with white grains of rice, a wooden measuring scoop in front"),
    ("general", "base", "general cargo for an 1860 merchant ship: a tidy group of a small wooden barrel, a rope-bound "
                        "wooden crate, a coil of hemp rope and a bundle wrapped in oilcloth and twine"),
    ("camphor", "luxury", "camphor for the 1860 China Seas trade: an open camphorwood chest lined with sheet lead, "
                          "packed with translucent white crystalline slabs of refined camphor, a few raw chunks of "
                          "camphor gum and pale wood shavings heaped in front"),
    ("sandalwood", "luxury", "sandalwood for the 1860 China Seas trade: a stack of golden-brown sandalwood billets "
                             "bound with hemp rope, one billet split open to show its pale yellow heartwood, a small "
                             "heap of fragrant shavings and chips in front"),
    ("ginseng", "luxury", "ginseng for the 1860 China trade: an open shallow wooden box lined with rice paper holding "
                          "dried pale gnarled ginseng roots, several shaped like little figures, one small bundle "
                          "tied with red string laid in front"),
    ("jade", "luxury", "jade for the 1860 China trade: a rough river-worn boulder of green jade with one polished "
                       "window cut into it, beside a few carved pieces in translucent apple-green and white jade: a "
                       "round pendant disc, a bracelet ring and a small lidded cup, on a small wooden tray"),
    ("pearls", "luxury", "natural pearls for the 1860 China Seas trade: an open lacquered wooden casket lined with "
                         "ivory silk, holding long strands of lustrous cream pearls, a few loose pearls in a small "
                         "shallow brass dish, and a single open pearl oyster shell in front"),
    ("ambergris", "luxury", "ambergris for the 1860 China Seas trade: one large irregular lump of mottled grey and "
                            "black waxy ambergris cut open to show its marbled layers, a few smaller pieces in a "
                            "small shallow brass dish, a loose square of sailcloth beside them"),
    ("opium", "family", "Chinese fireworks for the 1860 export trade: an open red-lacquered wooden chest packed with "
                        "bundles of red paper firecrackers on braided fuses, a few tall bamboo-stick sky rockets and "
                        "round paper shells with gold paper trim, one long string of red firecrackers draped over "
                        "the front of the chest"),
    ("arms", "family", "ironware for the 1860 China trade: a neat group of black cast-iron cooking pots and a deep "
                       "iron wok, a heavy iron kettle, a bundle of wrought-iron nails and bar iron tied with twine, "
                       "beside an open wooden crate packed with straw"),
]


def wanted(key, group):
    if not ONLY:
        return True
    if ONLY == "family":
        return group == "family"
    if ONLY == "luxuries":
        return group == "luxury"
    return key == ONLY


def main():
    jobs = []
    for key, group, item in CARGO:
        if not wanted(key, group):
            continue
        family = group == "family"
        label = key + (" (family)" if family else "")
        jobs.append((label, {"kind": "cargo", "subject": key, "roles": ["family" if family else "icon"],
                             "prompt": HEAD + item + TAIL, "aspect": "1:1", "count": COUNT, "nsfw": "no",
                             "tags": "muslin product-shot large" + (" family" if family else "")}))
    if not jobs:
        print("No cargo called '{}'. Use one of: {}, family, luxuries".format(
            ONLY, ", ".join(dict.fromkeys(k for k, _g, _i in CARGO))))
        return 1
    if theme_guard.report((label, j["prompt"]) for label, j in jobs):
        print("Nothing was queued. Fix the wording above and run this again.")
        return 1
    print("Theme check passed: no modern wording in {} prompt(s).".format(len(jobs)))
    if DRY:
        for label, job in jobs:
            print("\n== cargo / {} x{} [{}]\n{}".format(label, COUNT, job["tags"], job["prompt"]))
        return 0

    ok = total = 0
    for label, job in jobs:
        req = urllib.request.Request(SERVER + "/api/admin/media/generate", data=json.dumps(job).encode("utf-8"),
                                     headers={"Content-Type": "application/json", "X-SeaTrader": "admin"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                res = json.loads(r.read().decode("utf-8"))
        except Exception as e:                      # the Pi is off, or Admin asked for a password
            res = {"ok": False, "error": str(e)}
        print("cargo / {:18} x{}  {}".format(label, COUNT, res.get("msg") if res.get("ok") else
                                            "FAILED: " + str(res.get("error"))))
        total += COUNT
        ok += COUNT if res.get("ok") else 0
    print()
    print("{} of {} pictures queued. Watch them in Admin > Media Library (jobs).".format(ok, total))
    if ok < total:
        print("If it says a cargo is unknown, run Deploy_To_Pi.bat first so the Pi has the six new cargoes.")
    return 0 if ok == total else 1


if __name__ == "__main__":
    sys.exit(main())
