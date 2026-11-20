"""Queue the Family Friendly flip pictures (20 Nov 2026): four personas, each in two SQUARE states.

  SAFE    buttoned up, demure, refined and composed.   Filed NOT NSFW, tags "square nsfw-or-safe, safe, clean"
  UNSAFE  caught in a state of undress, but NOT exposed  Filed NSFW,     tags "square nsfw-or-safe, unsafe"
          (flustered, coat and blouse hanging open, modesty kept by her arms, a ledger, cloth and props).

Captain's Options > Table settings > Family Friendly shows one square picture. Each time Options is opened it picks
one persona that has BOTH a safe and an unsafe picture carrying the "nsfw-or-safe" tag, and tapping the picture
flips it between the two (Safe = Family Friendly on, Unsafe = off). Which picture is which comes from the NSFW flag,
so the unsafe ones must be filed NSFW (this tool does that), and anything you tag "nsfw-or-safe" by hand in the
Media Library joins the rotation.

Each prompt starts from the persona's OWN cast prompt (the live game's, else this folder's cast.py), exactly like
queue_persona_pairs.py, so her face stays close to her profile picture.

Usage (run on BIGBOX; the Pi trusts its Admin requests):
    python tools/queue_family_flip_pictures.py                      the four default personas, one picture per state
    python tools/queue_family_flip_pictures.py --count 2            two pictures per state (more variety on screen)
    python tools/queue_family_flip_pictures.py --who bookkeeper     just one persona (cast keys, comma-separated)
    python tools/queue_family_flip_pictures.py --only unsafe        only one state
    python tools/queue_family_flip_pictures.py --dry                print the prompts, queue nothing
Options: --who, --count (1-8 per state), --only safe|unsafe, --server (default http://192.168.1.69:8765), --dry
"""
import argparse
import json
import os
import re
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import queue_persona_pairs as qpp        # the cast-prompt helpers (read only)

# Mrs. Evelyn Marlowe (the Registrar), Her Worship the Mayor, Mademoiselle Celeste Vautrin (the bookkeeper),
# Moira Haig (the chief cashier). Change the list, or pass --who, for any other cast key.
DEFAULT_WHO = ["taxlady", "mayor", "bookkeeper", "banker"]
TAG_BOTH = "square nsfw-or-safe"
ROLES = ["idle"]

FRAME = ("square 1:1 composition, centred waist-up portrait facing the viewer, in her own office, "
         "same lamplit setting and lighting")

SAFE_STATE = ("perfectly buttoned up and proper, high collar fastened to the throat, hair neatly pinned, "
              "hands folded or resting on her ledger, upright composed posture, a demure refined closed-lip smile, "
              "immaculate Victorian respectability, completely covered from neck to wrist")
SAFE_STYLE = qpp.CLEAN_STYLE.replace("waist-up 3:4 portrait", "square waist-up portrait")

UNSAFE_STATE = ("caught in a state of undress, interrupted mid-dressing and flustered: her coat and blouse hanging open, "
                "stays loosened, chemise slipping off her shoulders, one arm and her ledger pulled across her chest, "
                "a flush of embarrassment, wide startled eyes and a caught-red-handed half-smile, "
                "modesty kept by her arms, cloth and props, underthings visible but nothing exposed, "
                "no bare breasts, no nipples, no nudity")
UNSAFE_STYLE = ("romanticized cinematic historical realism, China Seas 1860, humid salt haze, natural skin, "
                "weathered maritime materials, lacquer black, oxblood silk, antique brass, imperial jade, "
                "tasteful boudoir comedy, hands visible, original face and garment design, no text")

# The cast prompts are written glamorous; for the buttoned-up picture, make the wardrobe plainly proper.
PROPER = [
    (r"\b(?:an|a) (?:oxblood |burgundy silk |black silk |black lace )?corset", "a silk waistcoat"),
    (r"(?:oxblood |burgundy silk |black silk |black lace )?corset", "silk waistcoat"),
    (r" charged with restrained erotic authority", ""),
    (r"dark hair falling loose from its pins", "dark hair neatly pinned"),
]


def safe_prompt(base):
    desc, _tail = qpp.split(base)
    for pat, rep in qpp.DECENT + PROPER:
        desc = re.sub(pat, rep, desc)
    desc = re.sub(r"\s+,", ",", re.sub(r"  +", " ", desc))
    return "{}, {}, {}, {}".format(desc, SAFE_STATE, FRAME, SAFE_STYLE)


def unsafe_prompt(base):
    desc, _tail = qpp.split(base)
    for pat, rep in PROPER[2:3]:
        desc = re.sub(pat, rep, desc)
    return "{}, {}, {}, {}".format(desc, UNSAFE_STATE, FRAME, UNSAFE_STYLE)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--who", default=",".join(DEFAULT_WHO))
    ap.add_argument("--count", type=int, default=1)
    ap.add_argument("--only", choices=["safe", "unsafe"], default="")
    ap.add_argument("--server", default="http://192.168.1.69:8765")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    server = a.server.rstrip("/")
    prompts, names = qpp.cast_prompts(server)
    who = [w.strip() for w in a.who.split(",") if w.strip()]
    ok = total = 0
    for cid in who:
        base = prompts.get(cid, "")
        if len(base) < 20:
            print("{:12} has no portrait prompt (or is not in the cast); skipped".format(cid))
            continue
        for kind in ("safe", "unsafe"):
            if a.only and kind != a.only:
                continue
            total += 1
            prompt = safe_prompt(base) if kind == "safe" else unsafe_prompt(base)
            job = {"kind": "persona", "subject": cid, "roles": ROLES, "prompt": prompt[:6000], "aspect": "1:1",
                   "count": max(1, min(8, a.count)), "nsfw": "no" if kind == "safe" else "yes",
                   "tags": TAG_BOTH + (", safe, clean" if kind == "safe" else ", unsafe")}
            if a.dry:
                print("\n== {} ({}) {}\n{}".format(cid, names.get(cid, ""), kind.upper(), prompt))
                ok += 1
                continue
            req = urllib.request.Request(server + "/api/admin/media/generate", data=json.dumps(job).encode("utf-8"),
                                         headers={"Content-Type": "application/json", "X-SeaTrader": "admin"})
            try:
                with urllib.request.urlopen(req, timeout=20) as r:
                    res = json.loads(r.read().decode("utf-8"))
            except Exception as e:                  # the Pi is off, or Admin asked for a password
                res = {"ok": False, "error": str(e)}
            print("{:12} {:32} {:7} {}".format(cid, names.get(cid, "")[:32], kind.upper(),
                                               res.get("msg") if res.get("ok") else "FAILED: " + str(res.get("error"))))
            ok += bool(res.get("ok"))
    print()
    print("{} of {} jobs {}.".format(ok, total, "shown" if a.dry else "queued. Watch them in Admin > Media Library (jobs)"))
    return 0 if ok == total and total else 1


if __name__ == "__main__":
    sys.exit(main())
