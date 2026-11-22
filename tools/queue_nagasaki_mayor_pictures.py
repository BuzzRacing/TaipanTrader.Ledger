"""Queue five dramatic NSFW PROFILE pictures of the Mayor of Nagasaki (22 Nov 2026) on the live game (the Pi).

She is the same woman as her Media Library mayor (an unmistakably adult Dutch-Japanese woman, age 40, honey-brown
hair, jade comb), caught in five different dramatic activities as waist-up profile portraits, alone in frame,
glamour styling, never explicit. Nothing promotional: these are her ordinary "mayor" profile role, not the Promotion Story.
Wording follows the 21 Nov rule: the nude and topless looks say "completely naked" / "completely topless" plainly.

  1  the duel        dawn duel on the Dejima quay, cutlass mid-lunge                 completely topless
  2  the typhoon     on the harbour-office roof in a typhoon, lantern in hand        completely naked, chain only
  3  the raid        smashing open seized contraband tea chests with a boarding axe  completely topless
  4  the dive        rising from the night harbour with the strongbox key            completely naked
  5  the bonfire     burning the town's ledger of debts in an iron brazier           completely naked, gloves and chain

Filed under Media Library > Ports > Nagasaki, role "mayor" (her profile picture), NSFW "yes", tags "mayor-set profile nagasaki-action action-N".

Run from BIGBOX (the Pi trusts its Admin requests): Queue_Nagasaki_Mayor_Pictures.bat, or
    python tools/queue_nagasaki_mayor_pictures.py [--server URL] [--count N] [--only 1,3] [--aspect 3:4] [--dry]
      --count N   pictures per activity (default 1, up to 8)
      --only      just those activities, e.g. --only 2,5
      --dry       print the prompts, queue nothing
"""
import argparse
import json
import sys
import urllib.request

WHO = ("An unmistakably adult Dutch-Japanese Eurasian woman (age 40) with hazel eyes and a slim, curvy figure, "
       "honey-brown hair with a jade comb, a former pirate queen who is now the lady mayor of Nagasaki in 1860, "
       "she is the only person in the picture")

TAIL = {
    "topless": ", romanticized 1860 China Seas glamour photograph, completely topless, bold magazine-centerfold "
               "styling, tasteful and playful, natural skin with a soft sheen, confident direct gaze, "
               "dramatic atmosphere, waist-up profile portrait with her face and the action both clearly in frame, {aspect}",
    "nude": ", romanticized 1860 China Seas glamour photograph, completely naked, bold vintage-centerfold styling, "
            "tasteful and playful, artful composition, natural skin with a soft sheen, confident direct gaze, "
            "dramatic atmosphere, waist-up profile portrait with her face and the action both clearly in frame, {aspect}",
}

# (name, tier, what she is doing and wearing, the light)
SCENES = [
    ("the duel", "topless",
     "completely topless in black riding breeches and tall boots, her hair coming loose, caught mid-lunge with a "
     "cutlass flashing in one hand and the other arm thrown back for balance, fighting a duel on the Dejima quay "
     "at dawn, a fierce delighted grin, the scabbard and her gold mayor's chain swinging",
     "pale dawn mist over the water, low gold sun behind her, sparks of light on the blade"),
    ("the typhoon", "nude",
     "completely naked except for her gold mayor's chain of office, standing on the harbour-office roof in a "
     "typhoon with one hand raised holding a storm lantern close to her face against the wind, a long red silk sash streaming from her "
     "arm and wrapping across her hips, hair whipping, ships tossing in the harbour far below, defiant and exultant",
     "sheet lightning and rain, rim-lighting on wet skin, dark green-black sky"),
    ("the raid", "topless",
     "completely topless in an open black lacquer coat torn off one shoulder, a boarding axe swung overhead in "
     "mid-strike at a seized tea chest bursting open and spilling silver dollars and ivory-wrapped tea bricks "
     "across the customs-house floor, her boots planted on the wreckage, wild triumphant laughter",
     "shafts of golden dust-filled light through high shutters, flying splinters frozen in the air"),
    ("the dive", "nude",
     "completely naked and rising out of the night harbour waist-deep in black water, streaming wet, hair slicked "
     "back, one arm lifting a dripping brass strongbox key high overhead like a trophy, the other sweeping water "
     "from her face, a triumphant smile at the camera, ripples and the wooden piles of the quay behind her",
     "lantern light from the quay above, warm gold on wet skin, cold blue moonlit water"),
    ("the bonfire", "nude",
     "completely naked except for long black gloves and her gold mayor's chain, standing before a great iron brazier "
     "at midnight, tearing the town's ledger of debts apart and feeding the pages to the flames, burning paper and "
     "embers spiralling up around her, a slow wicked smile, one knee forward, ash on her shoulders",
     "firelight from below, deep orange glow on skin, black shadows, drifting sparks"),
]


def prompt(i, aspect):
    name, tier, doing, light = SCENES[i]
    return "{}, {}, {}{}".format(WHO, doing, light, TAIL[tier].format(aspect=aspect))[:6000]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", default="http://192.168.1.69:8765")
    ap.add_argument("--count", type=int, default=1)
    ap.add_argument("--only", default="")
    ap.add_argument("--aspect", default="3:4")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    server = a.server.rstrip("/")
    count = max(1, min(8, a.count))
    picks = [int(x) for x in a.only.split(",") if x.strip().isdigit() and 1 <= int(x) <= len(SCENES)] or \
        list(range(1, len(SCENES) + 1))
    ok = total = 0
    for n in picks:
        total += 1
        job = {"kind": "port", "subject": "nagasaki", "roles": ["mayor"], "prompt": prompt(n - 1, a.aspect),
               "aspect": a.aspect, "count": count, "nsfw": "yes",
               "tags": "mayor-set profile nagasaki-action action-{}".format(n)}
        label = "{} {}".format(n, SCENES[n - 1][0])
        if a.dry:
            print("{:16} NSFW x{}\n    {}\n".format(label, count, job["prompt"]))
            ok += 1
            continue
        req = urllib.request.Request(server + "/api/admin/media/generate", data=json.dumps(job).encode("utf-8"),
                                     headers={"Content-Type": "application/json", "X-SeaTrader": "admin"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                res = json.loads(r.read().decode("utf-8"))
        except Exception as e:                      # the Pi is off, or Admin asked for a password
            res = {"ok": False, "error": str(e)}
        print("{:16} {}".format(label, res.get("msg") if res.get("ok") else "FAILED: " + str(res.get("error"))))
        ok += bool(res.get("ok"))
    print()
    print("{} of {} {}. Watch them in Admin > Media Library (jobs), tag nagasaki-action.".format(
        ok, total, "prompts printed" if a.dry else "jobs queued"))
    return 0 if ok == total and total else 1


if __name__ == "__main__":
    sys.exit(main())
