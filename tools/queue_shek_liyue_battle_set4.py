"""Queue 60 new sea-battle pictures of Madam Shek Yu-lan (cast key "agent") and Admiral Li Yue (cast key "pirate")
on the live game (the Pi).

Each woman gets 10 NEW battle scenes (none repeat their earlier sets), and every scene is made 3 times:
  1 clean   fully clothed, tagged "battle-scene <tag>, clean" (family-friendly screens)
  2 NSFW    two sultry looks of the same scene (A: robe slipping off a shoulder, plunging neckline;
            B: rain/sea-soaked silk clinging, a high slit, torn battle damage). Suggestive and glamorous,
            nothing explicit. Sent with nsfw "yes" so they file under the adult pictures.
That is 10 x 3 x 2 = 60 jobs. Filed under Media Library > Personas > Madam Shek / Admiral Li Yue with the scene's
mood role (speaking, happy, angry, sly), tagged "battle-scene shek-battle-4" / "battle-scene li-yue-battle-4".

Run from BIGBOX (the Pi trusts its Admin requests): Queue_Shek_LiYue_Battle_Fourth_Set.bat, or
    python tools/queue_shek_liyue_battle_set4.py [server] [--dry] [--only shek|liyue] [--only-kind clean|nsfw]
(default server http://192.168.1.69:8765)
"""
import json
import sys
import urllib.request

ARGV = sys.argv[1:]
DRY = "--dry" in ARGV


def _opt(name):
    if name in ARGV:
        i = ARGV.index(name)
        return ARGV[i + 1].lower() if i + 1 < len(ARGV) else ""
    return ""


ONLY = _opt("--only")                    # shek | liyue | "" (both)
ONLY_KIND = _opt("--only-kind")          # clean | nsfw | "" (both)
_skip = {ARGV[ARGV.index(o) + 1] for o in ("--only", "--only-kind") if o in ARGV and ARGV.index(o) + 1 < len(ARGV)}
ARGS = [a for a in ARGV if not a.startswith("--") and a not in _skip]
SERVER = (ARGS[0] if ARGS else "http://192.168.1.69:8765").rstrip("/")

# --- the shared look of the shot -------------------------------------------------------------------------------
COMMON = ("every sailor and warrior in the scene is a woman, no men, romanticized cinematic historical realism, "
          "China Seas 1860, humid salt haze, natural skin, weathered maritime materials, lacquer black, oxblood "
          "silk, antique brass, imperial jade, hands visible, original face and garment design, no text")
TAIL_CLEAN = ", fully and modestly clothed, no nudity, no cleavage, " + COMMON + ", waist-up 3:4 portrait"
TAIL_NSFW = (", sultry adult glamour pin-up styling, confident and teasing, tasteful and suggestive, "
             "no nudity, nothing explicit, " + COMMON + ", knees-up 3:4 portrait")

WOMEN = {
    "shek": {
        "name": "Madam Shek Yu-lan", "subject": "agent", "tag": "shek-battle-4",
        "head": ("An unmistakably adult Macanese-Chinese woman (age 37), Madam Shek Yu-lan, the pirate queen's "
                 "dangerously glamorous agent, sleek black hair pinned with jade combs, a red silk protection "
                 "token tied at her wrist"),
        "clean": ", wearing a fitted oxblood Qing-era silk jacket buttoned to a high collar over dark trousers",
        "nsfw_a": (", wearing an oxblood silk jacket with sheer sleeves slipping off one shoulder over a plunging "
                   "neckline, jade earrings, a gold coin belt cinched at her waist"),
        "nsfw_b": (", wearing sea-soaked oxblood silk clinging to her curves, a high slit up one leg, the jacket "
                   "torn open at the collar by battle, jade earrings, a gold coin belt low on her hips"),
        "scenes": [
            ("sly", "at a lacquered table in the pirate junk's cabin as cannon thunder outside, stacking silver "
                    "dollars against a ledger, a sly knowing smile, an ivory balance in one hand, a tea cup steaming"),
            ("speaking", "up on the junk's rail with a brass speaking trumpet, hailing a frigate through the "
                         "sea-spray and offering terms, one hand holding her hair off her face in the wind"),
            ("angry", "snatching a smoking fuse out of a gunner's hand beside a run-out cannon, scolding her "
                      "crew in a rage as the deck shakes, sparks and gunsmoke in her hair"),
            ("happy", "swinging from a rope across the gap between two ships, laughing wildly, a curved dao in "
                      "her free hand, the merchants' faces wide-eyed below her"),
            ("sly", "kneeling at the open lid of a plundered chest of tea and silk, holding a string of pearls "
                    "up to the lantern light, glancing sideways at the viewer with a small smile"),
            ("speaking", "standing on a wave-washed deck in a storm, one hand raised, shouting orders into the "
                         "wind to a line of women hauling on the sheets, lightning behind her"),
            ("angry", "sitting captive for a heartbeat in the brig of a navy ship, wrists in rope, glaring "
                      "defiantly through iron bars, a lantern swinging above her"),
            ("happy", "dancing across a captured deck to a fiddle played by her crew, red silk token spinning in "
                      "her hand, lanterns strung in the rigging, victory night"),
            ("sly", "perched on a barrel of gunpowder with her feet crossed, a lit taper held lazily in two "
                    "fingers, a daring teasing smile as she threatens to settle the debt the hard way"),
            ("speaking", "at the bow of her junk as it breaks through a bank of gunsmoke, pointing a slim sword "
                         "at the merchant ship ahead, calling out the last offer, the sun low and red behind her"),
        ],
    },
    "liyue": {
        "name": "Admiral Li Yue", "subject": "pirate", "tag": "li-yue-battle-4",
        "head": ("An unmistakably adult Cantonese woman (age 48), formidable Qing-era pirate queen Admiral Li Yue, "
                 "elaborate pinned hair, oxblood sash, a single white peony pinned at her collar"),
        "clean": ", wearing a dark quilted silk robe fastened to a high collar over sculpted leather armour",
        "nsfw_a": (", wearing a dark quilted silk robe slipping off her shoulders over a plunging neckline, the "
                   "oxblood sash tied low at her hips, one bare shoulder gleaming"),
        "nsfw_b": (", wearing wet black silk clinging to her figure, the robe torn open by battle, a high slit "
                   "up one leg, the oxblood sash knotted low on her hips"),
        "scenes": [
            ("speaking", "at the helm of her black-lacquer flagship in a gale, one hand on the tiller, the other "
                         "pointing her fleet toward a storm-lit merchant convoy, rain streaming down her face"),
            ("sly", "seated on a carved throne chair on the quarterdeck while a line of captured captains kneels "
                    "before her, turning a white peony slowly in her fingers, a cold quiet smile"),
            ("angry", "standing over a shattered ship's bell and a gunner's broken ramrod, a cannonball having "
                      "torn through her flagship's rail, sword leveled at an unseen traitor, smoke curling"),
            ("happy", "on the prow as her war junks surge in perfect line behind her through blue morning water, "
                      "wind lifting her sleeves, a rare real smile, a peony between her fingers"),
            ("speaking", "in the crow's nest-high rigging platform, a signal flag in each hand, directing the "
                         "fleet's turn through a haze of gunsmoke, her voice carrying across the water"),
            ("sly", "at a long table in her war cabin, calmly moving jade pieces across a sea map while a "
                    "far-off cannon rumbles, a cup of tea untouched, a smile that says the trap is already shut"),
            ("angry", "descending the boarding plank onto a defeated navy ship, wading through splinters and "
                      "smoke, sword drawn, eyes blazing at the captain who dared to fire first"),
            ("happy", "on the deck at night as her women crew hoist lanterns and sing, a victory banner blowing "
                      "overhead, she raises a small cup of wine to the fleet, flushed and glowing"),
            ("speaking", "alone at the stern railing facing a huge wall of black storm cloud, one arm outstretched "
                         "as if commanding the sea itself to take her side, her robe whipping in the wind"),
            ("sly", "in a small sampan sliding between two anchored warships at dusk, one finger raised to her "
                    "lips to hush her rowers, the moon rising over fire-lit masts"),
        ],
    },
}


def queue(job):
    req = urllib.request.Request(SERVER + "/api/admin/media/generate", data=json.dumps(job).encode("utf-8"),
                                 headers={"Content-Type": "application/json", "X-SeaTrader": "admin"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:                          # the Pi is off, or Admin asked for a password
        return {"ok": False, "error": str(e)}


def build_jobs():
    jobs = []
    for key, w in WOMEN.items():
        if ONLY and ONLY != key:
            continue
        for n, (mood, scene) in enumerate(w["scenes"], 1):
            base = {"kind": "persona", "subject": w["subject"], "roles": [mood], "aspect": "3:4", "count": 1}
            if ONLY_KIND in ("", "clean"):
                jobs.append((w["name"], n, mood, "clean", dict(
                    base, prompt=w["head"] + ", " + scene + w["clean"] + TAIL_CLEAN, nsfw="no",
                    tags="battle-scene " + w["tag"] + ", clean")))
            if ONLY_KIND in ("", "nsfw"):
                for label, outfit in (("nsfw-A", w["nsfw_a"]), ("nsfw-B", w["nsfw_b"])):
                    jobs.append((w["name"], n, mood, label, dict(
                        base, prompt=w["head"] + ", " + scene + outfit + TAIL_NSFW, nsfw="yes",
                        tags="battle-scene " + w["tag"])))
    return jobs


def main():
    jobs = build_jobs()
    if not jobs:
        print("Nothing to queue (check --only shek|liyue and --only-kind clean|nsfw).")
        return 1
    ok = 0
    for i, (who, n, mood, kind, job) in enumerate(jobs, 1):
        if DRY:
            print("\n== {:2}. {} scene {} {} {}\n{}".format(i, who, n, mood, kind.upper(), job["prompt"]))
            ok += 1
            continue
        res = queue(job)
        print("{:2}. {:18} {:2} {:8} {:7} {}".format(i, who, n, mood, kind,
              res.get("msg") if res.get("ok") else "FAILED: " + str(res.get("error"))))
        ok += bool(res.get("ok"))
    print()
    print("{} of {} jobs {}.".format(ok, len(jobs), "shown" if DRY else "queued. Watch them in Admin > Media Library (jobs)"))
    return 0 if ok == len(jobs) else 1


if __name__ == "__main__":
    sys.exit(main())
