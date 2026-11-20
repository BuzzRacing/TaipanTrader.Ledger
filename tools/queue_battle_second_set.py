"""Queue a second picture for every sea-battle moment that has only one (19 Nov 2026), so each of the ten
moments has two pictures to rotate through for pirate junks, war junks and the flagship.

It reads the live game's Media Library (Scenes > "Sea battle: pirate junks" / "war junks" / "the flagship"),
counts the enabled pictures for each moment (sighting, broadside, enemy_hit, we_are_hit, boarding, victory,
defeat, retreat, got_away, ship_lost) and, for each moment short of two, queues more from that moment's own
prompt with a fresh camera angle, the same roles and tags, and the same NSFW setting. Nothing is replaced.

Run from BIGBOX (the Pi trusts its Admin requests): Queue_Battle_Second_Set.bat, or
    python tools/queue_battle_second_set.py [server] [--dry] [--want 2]   (default http://192.168.1.69:8765)
"""
import json
import sys
import urllib.request

ARGS = sys.argv[1:]
DRY = "--dry" in ARGS
WANT = int(ARGS[ARGS.index("--want") + 1]) if "--want" in ARGS else 2
POS = [a for i, a in enumerate(ARGS) if not a.startswith("--") and (i == 0 or ARGS[i - 1] != "--want")]
SERVER = (POS[0] if POS else "http://192.168.1.69:8765").rstrip("/")

SUBJECTS = ("seafight_pirates", "seafight_lord", "seafight_flagship")
MOMENTS = ("sighting", "broadside", "enemy_hit", "we_are_hit", "boarding", "victory", "defeat", "retreat",
           "got_away", "ship_lost")
ANGLES = ["seen from a different angle, a wider view of the same moment",
          "seen from a different angle, closer in on the action of the same moment",
          "seen from a different angle, low across the water, the same moment a few seconds later"]


def call(path, body=None):
    req = urllib.request.Request(SERVER + path, data=json.dumps(body).encode("utf-8") if body is not None else None,
                                 headers={"Content-Type": "application/json", "X-SeaTrader": "admin"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def add_angle(prompt, angle):
    """Put the camera note just before the style tail, so the look stays the same."""
    for mark in (", romanticized", ", dramatic cinematic"):
        at = prompt.find(mark)
        if at > 0:
            return prompt[:at] + ", " + angle + prompt[at:]
    return prompt + ", " + angle


def main():
    try:
        lib = call("/api/admin/media/library")
    except Exception as e:                          # the Pi is off, or Admin asked for a password
        print("Could not read the Media Library at {}: {}".format(SERVER, e))
        return 1
    items = [i for i in lib.get("items", []) if i.get("kind") == "scene" and i.get("subject") in SUBJECTS
             and i.get("enabled", True) and not i.get("missing")]
    ok = total = 0
    for subject in SUBJECTS:
        for moment in MOMENTS:
            have = [i for i in items if i["subject"] == subject and moment in (i.get("roles") or []) + (i.get("tags") or [])]
            need = WANT - len(have)
            if need <= 0:
                continue
            if not have or not have[0].get("prompt"):
                print("{:18} {:10} has no picture to copy the prompt from; skipped".format(subject, moment))
                continue
            src = have[0]
            for n in range(need):
                total += 1
                job = {"kind": "scene", "subject": subject, "roles": src.get("roles") or [moment],
                       "prompt": add_angle(src["prompt"], ANGLES[(len(have) + n - 1) % len(ANGLES)])[:6000],
                       "aspect": "16:9", "count": 1, "nsfw": "yes" if src.get("nsfw") else "no",
                       "tags": " ".join(t for t in (src.get("tags") or []) if t not in MOMENTS)}
                if DRY:
                    print("\n== {} / {} (has {})\n{}".format(subject, moment, len(have), job["prompt"]))
                    ok += 1
                    continue
                try:
                    res = call("/api/admin/media/generate", job)
                except Exception as e:
                    res = {"ok": False, "error": str(e)}
                print("{:18} {:10} has {}  {}".format(subject, moment, len(have),
                                                     res.get("msg") if res.get("ok") else "FAILED: " + str(res.get("error"))))
                ok += bool(res.get("ok"))
    print()
    if not total:
        print("Every sea-battle moment already has {} or more pictures.".format(WANT))
        return 0
    print("{} of {} pictures {}.".format(ok, total, "shown" if DRY else "queued. Watch them in Admin > Media Library (jobs)"))
    return 0 if ok == total else 1


if __name__ == "__main__":
    sys.exit(main())
