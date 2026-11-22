"""Queue NSFW + clean PAIRS of persona pictures in one go (19 Nov 2026), so the image farm can crank
through a whole group while you tinker. See the project doc "SeaTrader Image Batches".

For every persona in the group, two jobs are queued from that persona's OWN cast prompt (the live
game's, so a face stays close to her profile picture):
  NSFW   her prompt + the mood + openly nude              filed NSFW,     tags "<tag>"
  clean  her prompt dressed modestly + the mood + clean   filed NOT NSFW, tags "<tag>, clean"
Family-friendly screens only ever get the clean one. A tag works as a mood anywhere the game looks
for one (the Port Authority's bored / curious / hungry tells, happy / angry rulings...).

Usage (run on BIGBOX; the Pi trusts its Admin requests):
    python tools/queue_persona_pairs.py --who officer_ --mood hungry
    python tools/queue_persona_pairs.py --who warden_,officer_hongkong --mood happy --count 2
    python tools/queue_persona_pairs.py --who officer_ --mood "laughing at a joke" --tag laughing --only clean
    python tools/queue_persona_pairs.py --who officer_ --mood hungry --dry      (print the prompts, queue nothing)
Options:
    --who      cast keys or key prefixes, comma-separated (officer_ = every Port Authority officer)
    --mood     a mood below, or your own words for her expression
    --tag      the tag filed on the pictures (default: the mood's name, or "mood")
    --roles    persona roles, comma-separated (default: the mood if it is a persona role, else "idle")
    --count    pictures per version (default 1)
    --only     nsfw or clean (default both)
    --server   default http://192.168.1.69:8765 (http://127.0.0.1:8765 for the dev server)
    --dry      print the prompts only
"""
import argparse
import json
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
try:
    import persona_prompts_v2 as pp
except ImportError:
    pp = None

# Expressions. The first five match the Media Library's own persona moods (media-admin.js PERSONA_MOODS);
# bored / curious / hungry are the Port Authority's tells.
MOODS = {
    "speaking": "caught mid-sentence, lips parted, one hand raised as she makes her point",
    "happy": "a broad, triumphant, delighted smile, eyes bright, good news written all over her face",
    "angry": "narrowed eyes, jaw set, a sharp warning gesture, plainly furious at bad news",
    "sly": "a sly conspiratorial half-smile and a knowing wink, leaning in close as if sharing a secret, one finger raised to her lips",
    "idle": "a relaxed, unguarded moment, looking off to one side, lost in thought",
    "bored": "utterly bored, chin propped on one hand, heavy-lidded eyes drifting away from the papers, stifling a yawn",
    "curious": "suddenly interested, one eyebrow arched, head tilted, studying the viewer closely over the papers",
    "hungry": "leaning in over her desk with a hungry, predatory look, eyes lit with greed and fixed on the viewer, "
              "lips parted in a wolfish smile, as if she has just spotted a big lie in the manifest and can already "
              "taste the cargo",
}
# The bookkeeper's own looks (Queue_Bookkeeper_Pairs.bat).
MOODS.update({
    "portrait": "a slow, sultry come-hither look over her spectacles, quill resting against her lower lip",
    "ledger_happy": "a delighted, wicked smile, leaning back with the crimson ledger hugged to her chest, "
                    "as if your profits have thoroughly excited her",
    "ledger_angry": "a cool, smouldering glare over her spectacles, red quill poised to strike out a loss, lips pursed",
    "ledger_sly": "a slow sly smile and one raised eyebrow, a finger tracing down a column of figures, "
                  "as if she has found a secret in your books she means to keep",
})
PERSONA_ROLES = ("portrait", "speaking", "idle", "happy", "angry", "sly")

NUDE = ("completely nude, her clothes fallen away, bare breasts and body shown openly, only her jewellery and the "
        "props of her trade left on her")
CLEAN_STYLE = ("fully and modestly clothed, high neckline, no nudity, no cleavage, romanticized cinematic historical "
               "realism, China Seas 1860, humid salt haze, natural skin, weathered maritime materials, lacquer black, "
               "oxblood silk, antique brass, imperial jade, waist-up 3:4 portrait, hands visible, original face and "
               "garment design, no text")
# Undressed wording in the profile prompts, made decent for the clean version.
DECENT = [
    (r"worn loose off both shoulders with the obi half undone", "neatly worn and tied"),
    (r"off-shoulder ", ""), (r"slipping from one shoulder", "worn neatly"), (r"draped over one bare shoulder", "draped neatly"),
    (r"half-laced ", ""), (r"loosened ", ""), (r"with a thigh-high slit unbuttoned at the collar", "buttoned to the collar"),
    (r"open over a black lace corset", "buttoned over a black lace blouse"),
    (r"open over a black silk corset, high collar undone", "with the high collar buttoned"),
    (r"with a laced leather corset over it", ""), (r"plunging ", "high-necked "), (r"with a deep neckline", ""),
    (r"\bundone\b", "fastened"), (r"across her skin", "across the room"), (r"bedroom gaze", "gaze"),
    (r"sensual private-release erotic glamour,? ?", ""),
    # The bookkeeper (Accounting Ledger, 20 Nov 2026).
    (r"black silk blouse unbuttoned to the waist and slipping off one shoulder over an oxblood lace corset",
     "black silk blouse buttoned to the collar under an oxblood waistcoat"),
    (r"sheer black stockings and one knee drawn up, ", ""), (r"reclining in", "seated in"),
    (r"a smouldering heavy-lidded gaze", "a knowing gaze"), (r" deliciously", ""),
]


def cast_prompts(server):
    """Every cast member's portrait prompt: the live game's own, else this folder's cast.py."""
    try:
        req = urllib.request.Request(server + "/api/admin/all", headers={"X-SeaTrader": "admin"})
        with urllib.request.urlopen(req, timeout=20) as r:
            chars = json.loads(r.read().decode("utf-8"))["config"]["characters"]
        print("Prompts from the live game at", server)
        prompts = {k: v.get("portrait_prompt") or "" for k, v in chars.items()}
        names = {k: v.get("name", k) for k, v in chars.items()}
        # Someone new in this folder's cast.py (the bookkeeper, say) that the live game has not seeded yet.
        sys.path.insert(0, ROOT)
        import cast
        for k, v in cast.CHARACTERS.items():
            if k not in prompts:
                prompts[k], names[k] = v["portrait_prompt"], v["name"]
        return prompts, names
    except Exception as e:
        print("Could not read the live game's cast ({}); using this folder's cast.py".format(e))
        sys.path.insert(0, ROOT)
        import cast
        return ({k: v["portrait_prompt"] for k, v in cast.CHARACTERS.items()},
                {k: v["name"] for k, v in cast.CHARACTERS.items()})


def split(prompt):
    """(her description, the style tail). The style tail starts at ', romanticized'."""
    at = prompt.find(", romanticized")
    return (prompt[:at], prompt[at + 2:]) if at > 0 else (prompt, "")


def nsfw_prompt(base, mood):
    desc, tail = split(base)
    return "{}, {}, {}{}".format(desc, mood, NUDE, ", " + tail if tail else "")


def clean_prompt(base, mood):
    desc, _tail = split(base)
    for pat, rep in DECENT:
        desc = re.sub(pat, rep, desc)
    desc = re.sub(r"\s+,", ",", re.sub(r"  +", " ", desc))
    return "{}, {}, {}".format(desc, mood, CLEAN_STYLE)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--who", required=True)
    ap.add_argument("--mood", required=True)
    ap.add_argument("--tag", default="")
    ap.add_argument("--roles", default="")
    ap.add_argument("--count", type=int, default=1)
    ap.add_argument("--only", choices=["nsfw", "clean"], default="")
    ap.add_argument("--server", default="http://192.168.1.69:8765")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    server = a.server.rstrip("/")
    mood = MOODS.get(a.mood, a.mood)
    tag = a.tag or (a.mood if a.mood in MOODS else "mood")
    roles = [r for r in a.roles.split(",") if r] or ([a.mood] if a.mood in PERSONA_ROLES else ["idle"])
    prompts, names = cast_prompts(server)
    keys = [w.strip() for w in a.who.split(",") if w.strip()]
    who = [cid for cid in sorted(prompts) if any(cid == k or (k.endswith("_") and cid.startswith(k)) for k in keys)]
    if not who:
        print("Nobody in the cast matches", a.who)
        return 1
    ok = total = 0
    for cid in who:
        base = prompts[cid]
        if len(base) < 20:
            print("{:20} has no portrait prompt; skipped".format(cid))
            continue
        for kind in ("nsfw", "clean"):
            if a.only and kind != a.only:
                continue
            total += 1
            prompt = nsfw_prompt(base, mood) if kind == "nsfw" else clean_prompt(base, mood)
            if pp and cid in pp.LOOKS:      # v2 (21 Nov 2026): her own nude and clean looks, no regex swapping
                prompt = pp.build(cid, "nude" if kind == "nsfw" else "clean", mood)
            job = {"kind": "persona", "subject": cid, "roles": roles, "prompt": prompt[:6000], "aspect": "3:4",
                   "count": max(1, min(8, a.count)), "nsfw": "yes" if kind == "nsfw" else "no",
                   "tags": tag if kind == "nsfw" else tag + ", clean"}
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
            print("{:20} {:30} {:5} {}".format(cid, names.get(cid, "")[:30], kind,
                                               res.get("msg") if res.get("ok") else "FAILED: " + str(res.get("error"))))
            ok += bool(res.get("ok"))
    print()
    print("{} of {} jobs {}.".format(ok, total, "shown" if a.dry else "queued. Watch them in Admin > Media Library (jobs)"))
    return 0 if ok == total and total else 1


if __name__ == "__main__":
    sys.exit(main())
