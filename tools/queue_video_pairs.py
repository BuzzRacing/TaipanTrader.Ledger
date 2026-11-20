"""Queue clean + NSFW PAIRS of 10-second looping clips, made from personas' own pictures (20 Nov 2026).
See the project doc "SeaTrader Video Gallery".

For every persona in the group, the newest NSFW picture and the newest clean picture (tagged "clean",
or simply not NSFW) are sent to the live game, which asks the farm (Wan 2.2 on BIGBOX) for a clip from
each: the same movement and the same seeds for both, so the two can be compared like with like in
Admin > Media Library > Compare. The NSFW clip is filed NSFW; the clean clip is not, and is tagged "clean".
The movement describes motion only; her look and clothes come from each picture.

Usage (run on BIGBOX; the Pi trusts its Admin requests):
    python tools/queue_video_pairs.py --who warden_hongkong --motion keys
    python tools/queue_video_pairs.py --who warden_ --motion keys_slow --count 1
    python tools/queue_video_pairs.py --who warden_hongkong --motion "She laughs and tosses her hair" --tag laughing
    python tools/queue_video_pairs.py --who warden_hongkong --dry      (show the pictures and movement, queue nothing)
Options:
    --who      cast keys or key prefixes, comma-separated (warden_ = every jail warden)
    --motion   a movement below, or your own words
    --tag      extra tags, comma-separated (default "jail warden, motion-<movement>")
    --count    takes per version, 1-4 (default 2)
    --only     nsfw or clean (default both; one alone is queued as a single clip)
    --server   default http://192.168.1.69:8765 (http://127.0.0.1:8765 for the dev server)
    --dry      print what would be queued
"""
import argparse
import json
import sys
import urllib.request

# The same movements as the Make video panel (web/media-admin.js MOTIONS).
MOTIONS = {
    "keys": "She walks slowly toward the camera with a confident sway, idly spinning a ring of heavy iron keys around "
            "one finger, the keys glinting and swinging, a knowing smile, then eases back to where she began, steady "
            "camera, smooth natural motion",
    "keys_slow": "She stands in place, slowly swinging a ring of heavy iron keys from one hand and shifting her weight "
                 "from hip to hip, a knowing smile, steady camera, smooth natural motion",
    "idle": "She breathes slowly with small natural movements, blinks, a faint smile, hair stirring in a light breeze, "
            "steady camera",
    "speaking": "She talks to the camera with expressive hand gestures and a playful smile, steady camera, smooth "
                "natural motion",
    "look": "She turns her head toward the camera, holds its gaze and smiles slowly, steady camera",
}


def call(server, path, body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(server + path, data=data, method="GET" if body is None else "POST",
                                 headers={"Content-Type": "application/json", "X-SeaTrader": "admin"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def is_clean(it):
    return not it.get("nsfw") or "clean" in (it.get("tags") or [])


def newest(items):
    return sorted(items, key=lambda i: (("portrait" in (i.get("roles") or [])), str(i.get("added") or "")))[-1] if items else None


def pick(items, cid):
    """(nsfw picture, clean picture) of a persona: enabled, on disk, newest first, portraits preferred."""
    mine = [i for i in items if i.get("kind") == "persona" and i.get("subject") == cid and i.get("type") == "image"
            and i.get("enabled", True) and not i.get("missing")]
    return newest([i for i in mine if not is_clean(i)]), newest([i for i in mine if is_clean(i)])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--who", required=True)
    ap.add_argument("--motion", default="keys")
    ap.add_argument("--tag", default="")
    ap.add_argument("--count", type=int, default=2)
    ap.add_argument("--only", choices=("nsfw", "clean"), default="")
    ap.add_argument("--server", default="http://192.168.1.69:8765")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    server = a.server.rstrip("/")
    motion = MOTIONS.get(a.motion, a.motion)
    if len(motion) < 10:
        sys.exit("Describe the movement in more words, or use one of: " + ", ".join(MOTIONS))
    name = a.motion if a.motion in MOTIONS else "own"
    tags = a.tag or "jail warden, motion-{}".format(name.replace("_", "-"))
    count = max(1, min(4, a.count))
    try:
        lib = call(server, "/api/admin/media/library")
    except Exception as e:
        sys.exit("Could not read the Media Library at {} ({}). Is the game running there?".format(server, e))
    items = lib.get("items") or []
    keys = sorted({i.get("subject") for i in items if i.get("kind") == "persona" and i.get("subject")})
    want = []
    for w in [x.strip() for x in a.who.split(",") if x.strip()]:
        want += [k for k in keys if (k.startswith(w) if w.endswith("_") else k == w) and k not in want]
    if not want:
        sys.exit("No persona pictures found for --who {}.".format(a.who))
    print("Movement:", motion)
    print("Tags:", tags, "| takes per version:", count)
    queued = 0
    for cid in want:
        n_pic, c_pic = pick(items, cid)
        if a.only == "nsfw":
            c_pic = None
        if a.only == "clean":
            n_pic = None
        print("\n{}:\n  NSFW  from {}\n  clean from {}".format(cid, n_pic["url"] if n_pic else "(none)",
                                                             c_pic["url"] if c_pic else "(none)"))
        if not n_pic and not c_pic:
            continue
        if n_pic and c_pic:
            body = {"nsfw_id": n_pic["id"], "clean_id": c_pic["id"]}
        else:
            body = {"id": (n_pic or c_pic)["id"]}
        body.update(motion=motion, count=count, tags=tags)
        if a.dry:
            continue
        try:
            res = call(server, "/api/admin/media/video", body)
        except Exception as e:
            print("  not queued:", e)
            continue
        print("  " + (res.get("msg") if res.get("ok") else "not queued: " + str(res.get("error"))))
        if res.get("ok"):
            queued += count * (2 if "nsfw_id" in body else 1)
    print("\n{} clip(s) queued. Watch them in Admin > Media Library (jobs); each takes a while on the farm.".format(
        queued) if not a.dry else "\n(dry run: nothing queued)")


if __name__ == "__main__":
    main()
