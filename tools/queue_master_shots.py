"""Queue wide 16:9 WALLPAPER "master shots" of the personas on the live game (persona_prompts_v2.build_master).

Each picture is the woman alone in a dramatic scene of her own world (vault hall, flagship stern, gun deck...),
low heroic camera, filed under Personas > (her name), role "wallpaper", tagged "master-shot, wallpaper, <look>", NSFW.
Default: Bookkeeper, Batavia officer, Powder and Mrs. Marlowe x topless, nude and clean = 12 pictures (clean is not NSFW).
`--who all` does all 24 (48 pictures at two looks). Nothing is replaced or deleted.

Usage (run on BIGBOX; the Pi trusts its Admin requests):
    python tools/queue_master_shots.py
    python tools/queue_master_shots.py --who all --tiers nude
    python tools/queue_master_shots.py --who pirate,lender --tiers topless --count 2 --mood dare --dry
Options: --who (keys or "all"), --tiers (sultry,boudoir,topless,nude,clean), --count per look (1-8), --mood, --roles, --aspect, --server, --dry
"""
import argparse
import json
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import persona_prompts_v2 as pp  # noqa: E402

DEFAULT_WHO = "bookkeeper,officer_batavia,bosun,taxlady"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--who", default=DEFAULT_WHO)
    ap.add_argument("--tiers", default="topless,nude,clean")
    ap.add_argument("--count", type=int, default=1)
    ap.add_argument("--mood", default="")
    ap.add_argument("--roles", default="wallpaper")
    ap.add_argument("--aspect", default="16:9")
    ap.add_argument("--server", default="http://192.168.1.69:8765")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    server = a.server.rstrip("/")
    who = list(pp.MASTER) if a.who.strip().lower() == "all" else [w.strip() for w in a.who.split(",") if w.strip()]
    tiers = [t.strip() for t in a.tiers.split(",") if t.strip()]
    roles = [r for r in a.roles.split(",") if r]
    bad = [w for w in who if w not in pp.MASTER] + [t for t in tiers if t not in pp.ALL_TIERS]
    if bad:
        print("Unknown:", ", ".join(bad), "| personas:", ", ".join(pp.MASTER), "| tiers:", ", ".join(pp.ALL_TIERS))
        return 1
    ok = total = 0
    for cid in who:
        for tier in tiers:
            total += 1
            prompt = pp.build_master(cid, tier, a.mood or None)
            job = {"kind": "persona", "subject": cid, "roles": roles, "prompt": prompt[:6000], "aspect": a.aspect,
                   "count": max(1, min(8, a.count)), "nsfw": "no" if tier == "clean" else "yes",
                   "tags": "master-shot, wallpaper, " + tier + (", clean" if tier == "clean" else "")}
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
    print("\n{} of {} jobs {}.".format(ok, total, "shown" if a.dry else "queued. Watch them in Admin > Media Library (jobs), tag master-shot"))
    return 0 if ok == total and total else 1


if __name__ == "__main__":
    sys.exit(main())
