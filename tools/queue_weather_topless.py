"""Queue the second weather batch of Tilly Marsh pictures (21 Nov 2026).

Per kind of weather (calm, fair, squalls, typhoon):
    5 TOPLESS  filed NSFW,         tags "weather, weather-<kind>, topless"       (poses 1 to 5)
    1 clean    filed NOT NSFW,     tags "weather, weather-<kind>, clean"         (pose 5, never made before)
= 24 pictures. Same scenes, same Tilly, same "weather" role and one-slot rule as queue_weather_pictures.py,
which this file borrows from (keep the two side by side in tools/). Pose 5 is new for every weather, so nothing
already in the Media Library is repeated.

    python tools/queue_weather_topless.py [server] [options]      (default server http://192.168.1.69:8765)
    --topless N   topless poses per kind, 0 to 5 (default 5)
    --clean N     clean pictures per kind, 0 or 1 (default 1)
    --kinds a,b   only these kinds: calm, fair, squalls, typhoon
    --only topless|clean
    --dry         print the prompts, queue nothing
    --force       queue even if the server has no weather glass yet (not advised)
"""
import json
import sys

import queue_weather_pictures as q   # its HEAD, SCENES, CLEAN_WEAR, CLEAN_TAIL, fetch(), ready() and option parsing

OPT = q.OPT

# A fifth pose for every weather, in the same spirit as the first four.
POSE5 = {
    "calm": "lying back along the warm stone of the quay with the handbell balanced on her stomach, one knee "
            "up, watching a motionless gull and blowing a strand of damp hair off her lip",
    "fair": "twirling on the spot at the quay's edge with her arms out and the handbell flying on its lanyard, "
            "head thrown back, laughing at the sky",
    "squalls": "sheltering under a dripping rope-coil with the broadsheet held over her head, peeking out at the "
               "viewer with a rueful grin as the rain hammers down",
    "typhoon": "flat against the lee of a stone bollard with the wind pinning her hair and the wave-spray "
               "behind her, shouting into the gale with one fist in the air, gloriously defiant",
}

TOPLESS_WEAR = {
    "calm": "completely topless in the heat, her blouse shed in a heap on the quay, breasts shown openly, wearing only "
            "her oxblood skirt and a small cocked hat",
    "fair": "completely topless, the breeze has carried her blouse off down the quay, breasts shown openly, wearing "
            "only her oxblood skirt that snaps in the wind and a small cocked hat",
    "squalls": "completely topless and streaming wet, her soaked blouse torn off by the squall, breasts shown openly, "
               "rain running down her skin, wearing only her wet oxblood skirt and boots",
    "typhoon": "completely topless and streaming wet, the typhoon has ripped her blouse and coat away, breasts shown openly, wearing only her sodden oxblood skirt, boots and the handbell's lanyard",
}
TOPLESS_TAIL = (", she is the only person in the picture, romanticized 1860 China Seas glamour photograph, "
                "completely topless, vintage-centerfold styling, tasteful and playful, artful composition, natural skin, "
                "dramatic weather and atmosphere, knees-up 3:4 portrait")


def _n(key, top, default):
    try:
        return max(0, min(top, int(OPT.get(key, default))))
    except (TypeError, ValueError):
        return default


def jobs():
    kinds = [k.strip() for k in str(OPT.get("kinds") or ",".join(q.KINDS)).split(",") if k.strip() in q.KINDS]
    only = OPT.get("only") if OPT.get("only") in ("topless", "clean") else ""
    out = []
    for kind in kinds:
        sky, poses = q.SCENES[kind]
        poses = list(poses) + [POSE5[kind]]
        for ver, picks in (("topless", poses[:_n("topless", 5, 5)]),
                           ("clean", poses[4:5] if _n("clean", 1, 1) else [])):
            if only and ver != only:
                continue
            for pose in picks:
                wear, tail = (TOPLESS_WEAR[kind], TOPLESS_TAIL) if ver == "topless" else (q.CLEAN_WEAR[kind], q.CLEAN_TAIL)
                tags = "weather, weather-" + kind + (", clean" if ver == "clean" else ", topless")
                out.append((kind, ver, {"kind": "persona", "subject": q.WHO, "roles": ["weather"],
                                        "prompt": ", ".join((q.HEAD, sky, pose, wear)) + tail, "aspect": "3:4",
                                        "count": 1, "nsfw": "no" if ver == "clean" else "yes", "tags": tags}))
    return out


def main():
    todo = jobs()
    if not todo:
        print("Nothing to queue with those options.")
        return 1
    if not q.DRY and not q.FORCE and not q.ready():
        print("The game at {} does not have the weather glass yet (or cannot be reached).".format(q.SERVER))
        print("Run Deploy_To_Pi.bat first, then run this again. Nothing was queued.")
        return 1
    ok = 0
    for i, (kind, ver, job) in enumerate(todo, 1):
        if q.DRY:
            print("\n== {:2}. {} {} [{}]\n{}".format(i, kind, ver.upper(), job["tags"], job["prompt"]))
            ok += 1
            continue
        try:
            res = json.loads(q.fetch("/api/admin/media/generate", job))
        except Exception as e:
            res = {"ok": False, "error": str(e)}
        print("{:2}. {:8} {:7}  {}".format(i, kind, ver, res.get("msg") if res.get("ok") else "FAILED: " + str(res.get("error"))))
        ok += bool(res.get("ok"))
    print()
    print("{} of {} jobs {}.".format(ok, len(todo), "shown" if q.DRY else
                                     "queued. Watch them in Admin > Media Library (jobs); filter the gallery by the tag weather"))
    return 0 if ok == len(todo) else 1


if __name__ == "__main__":
    sys.exit(main())
