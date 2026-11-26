"""Queue clean product-shot pictures of the six new Cargo Tiers luxuries on the Taipan Trader server (taipantrader.ledger).

Same recipe as tools/queue_muslin_cargo_pictures.py: each luxury is photographed alone, centred and sharp, on
softly draped unbleached muslin under even studio light. No people, no text, square (1:1) like the market icons.
They are filed into Media Library > Cargo > <cargo> with the "icon" role, tagged "muslin product-shot", and
marked family-safe (not NSFW). None of the six is contraband, so there is no "family" set to make.

Batch A (Merchant):        camphor, sandalwood, ginseng
Batch B (Merchant Prince): jade, pearls, ambergris

Every prompt goes through tools/theme_guard.py first; nothing is queued if a modern word slips in.

Run from BIGBOX (the Pi trusts its Admin requests): Queue_Luxury_Cargo_Pictures.bat, or
    python tools/queue_luxury_cargo_pictures.py [server] [count] [only] [--dry]
      server  default http://taipantrader.ledger (use http://127.0.0.1:8775 for the dev server)
      count   pictures per cargo, 1-8 (default 3)
      only    queue just one cargo key: camphor, sandalwood, ginseng, jade, pearls or ambergris
      --dry   print the prompts and queue nothing
Run Deploy_To_Pi.bat first, or the Pi will not know these six cargoes.
"""
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import theme_guard  # noqa: E402

ARGS = [a for a in sys.argv[1:] if a != "--dry"]
DRY = "--dry" in sys.argv[1:]
SERVER = (ARGS[0] if len(ARGS) > 0 else "http://taipantrader.ledger").rstrip("/")
try:
    COUNT = max(1, min(8, int(ARGS[1]))) if len(ARGS) > 1 else 3
except ValueError:
    COUNT = 3
ONLY = ARGS[2].lower() if len(ARGS) > 2 else ""

HEAD = ("Museum-quality studio product photograph, a single isolated still life of ")
TAIL = (", placed alone in the centre of the frame on a seamless backdrop of plain natural unbleached cream muslin "
        "cloth, softly draped with gentle folds, the muslin fills the whole background and floor, soft even diffused "
        "studio lighting, a soft natural contact shadow, crisp sharp focus on every detail of the item, true colours, "
        "the whole item fully in frame with space around it, authentic 1860 China trade period object, "
        "nothing else in the picture, no people, no hands, no text, no labels, no watermark, square composition")

# key -> what the item looks like (matches the six luxuries in config.py)
CARGO = [
    ("camphor", "camphor for the 1860 China Seas trade: an open camphorwood chest lined with sheet lead, packed with "
                "translucent white crystalline slabs of refined camphor, a few raw chunks of camphor gum and pale "
                "wood shavings heaped in front"),
    ("sandalwood", "sandalwood for the 1860 China Seas trade: a stack of golden-brown sandalwood billets bound with "
                   "hemp rope, one billet split open to show its pale yellow heartwood, a small heap of fragrant "
                   "shavings and chips in front"),
    ("ginseng", "ginseng for the 1860 China trade: an open shallow wooden box lined with rice paper holding dried "
                "pale gnarled ginseng roots, several shaped like little figures, one small bundle tied with red "
                "string laid in front"),
    ("jade", "jade for the 1860 China trade: a rough river-worn boulder of green jade with one polished window cut "
             "into it, beside a few carved pieces in translucent apple-green and white jade: a round pendant disc, a "
             "bracelet ring and a small lidded cup, on a small wooden tray"),
    ("pearls", "natural pearls for the 1860 China Seas trade: an open lacquered wooden casket lined with ivory silk, "
               "holding long strands of lustrous cream pearls, a few loose pearls in a small shallow brass dish, and "
               "a single open pearl oyster shell in front"),
    ("ambergris", "ambergris for the 1860 China Seas trade: one large irregular lump of mottled grey and black waxy "
                  "ambergris cut open to show its marbled layers, a few smaller pieces in a small shallow brass "
                  "dish, a loose square of sailcloth beside them"),
]


def main():
    jobs = [(key, {"kind": "cargo", "subject": key, "roles": ["icon"], "prompt": HEAD + item + TAIL, "aspect": "1:1",
                   "count": COUNT, "nsfw": "no", "tags": "muslin product-shot"})
            for key, item in CARGO if not ONLY or key == ONLY]
    if not jobs:
        print("No cargo called '{}'. Use one of: {}".format(ONLY, ", ".join(k for k, _ in CARGO)))
        return 1
    if theme_guard.report((k, j["prompt"]) for k, j in jobs):
        print("Nothing was queued. Fix the wording above and run this again.")
        return 1
    print("Theme check passed: no modern wording in {} prompt(s).".format(len(jobs)))
    if DRY:
        for key, job in jobs:
            print("\n== cargo / {} x{} [{}]\n{}".format(key, COUNT, job["tags"], job["prompt"]))
        return 0

    ok = total = 0
    for key, job in jobs:
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
    print()
    print("{} of {} pictures queued. Watch them in Admin > Media Library (jobs).".format(ok, total))
    if ok < total:
        print("If it says the cargo is unknown, run Deploy_To_Pi.bat first so the Pi has the six new cargoes.")
    return 0 if ok == total else 1


if __name__ == "__main__":
    sys.exit(main())
