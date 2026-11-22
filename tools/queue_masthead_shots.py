"""Queue RECLINING wide pictures for the Dashboard masthead (persona_prompts_v2.build_master + a lying-back pose).

Each picture is the woman in her own scene (build_master), stretched out lengthways across the frame, low and wide, with the
left third left dark and quiet so the big Crimson Ledger title can sit over it. Filed under Personas > (her name), role
"wallpaper", tagged "masthead, reclining, <look>". The Dashboard (web/dashboard.js, renderLounge) shows any of these in the masthead.
Nothing is replaced or deleted.

Usage (run on BIGBOX; the Pi trusts its Admin requests):
    python tools/queue_masthead_shots.py
    python tools/queue_masthead_shots.py --who gamemaster --tiers clean,topless --count 3
    python tools/queue_masthead_shots.py --dry
Options: --who (keys), --tiers (sultry,boudoir,topless,nude,clean), --count per look (1-8), --mood, --aspect, --server, --dry
"""
import argparse
import json
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import persona_prompts_v2 as pp  # noqa: E402

DEFAULT_WHO = "gamemaster,bookkeeper"
# Added after her look and scene, before the style tail.
RECLINE = ("reclining at full length on a chaise longue, propped on one elbow, legs stretched out and crossed at the ankle, "
           "the whole of her body running left to right across a very wide low frame, relaxed and knowing, she fills the right two thirds "
           "of the picture while the left third is dark empty shadow and rigging, wide cinematic banner composition")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--who", default=DEFAULT_WHO)
    ap.add_argument("--tiers", default="clean,topless")
    ap.add_argument("--count", type=int, default=2)
    ap.add_argument("--mood", default="")
    ap.add_argument("--aspect", default="16:9")
    ap.add_argument("--server", default="http://192.168.1.69:8765")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    server = a.server.rstrip("/")
    who = [w.strip() for w in a.who.split(",") if w.strip()]
    tiers = [t.strip() for t in a.tiers.split(",") if t.strip()]
    bad = [w for w in who if w not in pp.MASTER] + [t for t in tiers if t not in pp.ALL_TIERS]
    if bad:
        print("Unknown:", ", ".join(bad), "| personas:", ", ".join(pp.MASTER), "| tiers:", ", ".join(pp.ALL_TIERS))
        return 1
    ok = total = 0
    for cid in who:
        for tier in tiers:
            total += 1
            base = pp.build_master(cid, tier, a.mood or None)
            tail = pp.MASTER_TAIL[tier]
            body = base[:-len(tail)] if base.endswith(tail) else base
            prompt = body + ", " + RECLINE + tail
            job = {"kind": "persona", "subject": cid, "roles": ["wallpaper"], "prompt": prompt[:6000], "aspect": a.aspect,
                   "count": max(1, min(8, a.count)), "nsfw": "no" if tier == "clean" else "yes",
                   "tags": "masthead, reclining, wallpaper, " + tier + (", clean" if tier == "clean" else "")}
            if a.dry:
                print("\n== {} {}\n{}".format(cid, tier.upper(), prompt))
                ok += 1
                continue
            req = urllib.request.Request(server + "/api/admin/media/generate", data=json.dumps(job).encode("utf-8"),
                                         headers={"Content-Type": "application/json", "X-SeaTrader": "admin"})
            try:
                with urllib.request.urlopen(req, timeout=20) as r:
                    res = json.loads(r.read().decode("utf-8"))
            except Exception as e:                  # the Pi is off, or Admin asked for a password
                res = {"ok": False, "error": str(e)}
            print("{:20} {:8} {}".format(cid, tier, res.get("msg") if res.get("ok") else "FAILED: " + str(res.get("error"))))
            ok += bool(res.get("ok"))
    print("\n{} of {} jobs {}.".format(ok, total, "shown" if a.dry else "queued. Watch them in Admin > Media Library (jobs), tag masthead"))
    return 0 if ok == total and total else 1


if __name__ == "__main__":
    sys.exit(main())
