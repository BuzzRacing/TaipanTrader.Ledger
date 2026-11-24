"""Queue the Port Authority's wide 16:9 TAX-RESULT pictures on the live game (tax_results.py, 23 Nov 2026).

For every tax lady (the ten port officers and Mrs. Marlowe) and each result:
    good   she is delighted: tax paid, or she bought your cargo     role tax_good
    bad    she is furious: she caught a lie                         role tax_bad
two jobs are queued: one NSFW (her nude look) and one clean (her clean look, not NSFW), 16:9, filed under
Personas > (her name), tagged "tax-result" (clean ones "tax-result, clean"). Default: 11 women x 2 results x 2 = 44.
The result screen at her desk shows only these; no other screen ever does.

It also saves the Recipe "Tax lady result pictures: 1 clean + 1 NSFW each" in Admin > Media Library > Recipes
(once), so the same pictures can be topped up from there after you disable or delete one.

Deploy first (Deploy_To_Pi.bat): the live game must know the two new roles, or this stops without queuing.

Usage (run on BIGBOX; the Pi trusts its Admin requests):
    python tools/queue_tax_result_pictures.py
    python tools/queue_tax_result_pictures.py --who officer_saigon          (one woman: 4 pictures)
    python tools/queue_tax_result_pictures.py --dry                         (print every prompt, queue nothing)
Options:
    --who        cast keys or prefixes ending in _, comma-separated (default: every tax lady)
    --result     good or bad (default both)
    --only       nsfw or clean (default both)
    --nsfw-tier  her NSFW look: nude (default), topless, boudoir or sultry
    --count      pictures per version (default 1)
    --server     default http://192.168.1.69:8765
    --dry        print the prompts only
"""
import argparse
import json
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import tax_results  # noqa: E402

HEAD = {"Content-Type": "application/json", "X-SeaTrader": "admin"}


def get(server, what):
    req = urllib.request.Request(server + "/api/admin/" + what, headers={"X-SeaTrader": "admin"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def post(server, what, body):
    req = urllib.request.Request(server + "/api/admin/" + what, data=json.dumps(body).encode("utf-8"), headers=HEAD)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:                  # the Pi is off, or Admin asked for a password
        return {"ok": False, "error": str(e)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--who", default="")
    ap.add_argument("--result", choices=["good", "bad"], default="")
    ap.add_argument("--only", choices=["nsfw", "clean"], default="")
    ap.add_argument("--nsfw-tier", choices=["nude", "topless", "boudoir", "sultry"], default="nude")
    ap.add_argument("--count", type=int, default=1)
    ap.add_argument("--server", default="http://192.168.1.69:8765")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    server = a.server.rstrip("/")
    everyone = tax_results.who()
    keys = [w.strip() for w in a.who.split(",") if w.strip()]
    who = [c for c in everyone if not keys or any(c == k or (k.endswith("_") and c.startswith(k)) for k in keys)]
    if not who:
        print("Nobody matches {}. The tax ladies: {}".format(a.who, ", ".join(everyone)))
        return 1
    roles = [r for r in tax_results.ROLES if not a.result or r == "tax_" + a.result]

    # Her identity as edited in Cast & Voices, and what the live game knows.
    saved, names, lib = {}, {}, None
    try:
        chars = get(server, "all")["config"]["characters"]
        saved = {k: v.get("portrait_prompt") or "" for k, v in chars.items()}
        names = {k: v.get("name", k) for k, v in chars.items()}
        print("Cast prompts from the live game at", server)
    except Exception as e:
        print("Could not read the live game's cast ({}); using this folder's prompts".format(e))
    if not a.dry:
        try:
            lib = get(server, "media/library")
        except Exception as e:
            print("The live game did not answer ({}). Nothing queued.".format(e))
            return 1
        known = {r[0] for r in lib.get("kinds", {}).get("persona", {}).get("roles", [])}
        if not set(tax_results.ROLES) <= known:
            print("The live game does not know the tax-result roles yet. Run Deploy_To_Pi.bat, then run this again.")
            print("Nothing queued.")
            return 1

    ok = total = 0
    for cid in who:
        for role in roles:
            for kind in ("nsfw", "clean"):
                if a.only and kind != a.only:
                    continue
                total += 1
                prompt = tax_results.build(cid, role, a.nsfw_tier if kind == "nsfw" else "clean", saved.get(cid) or None)
                if a.dry:
                    print("\n== {} ({}) {} {}\n{}".format(cid, names.get(cid, ""), role, kind.upper(), prompt))
                    ok += 1
                    continue
                job = {"kind": "persona", "subject": cid, "roles": [role], "prompt": prompt[:6000],
                       "aspect": tax_results.ASPECT, "count": max(1, min(8, a.count)),
                       "nsfw": "yes" if kind == "nsfw" else "no",
                       "tags": tax_results.TAG if kind == "nsfw" else tax_results.TAG + ", clean"}
                res = post(server, "media/generate", job)
                print("{:20} {:28} {:9} {:5} {}".format(cid, names.get(cid, "")[:28], role, kind,
                                                        res.get("msg") if res.get("ok") else "FAILED: " + str(res.get("error"))))
                ok += bool(res.get("ok"))
    print()
    print("{} of {} jobs {}.".format(ok, total, "shown" if a.dry else "queued. Watch them in Admin > Media Library (jobs)"))

    if not a.dry and lib is not None:
        have = lib.get("recipes") or []
        if any(r.get("id") == tax_results.RECIPE["id"] for r in have):
            print('The Recipe "{}" is already saved.'.format(tax_results.RECIPE["name"]))
        else:
            res = post(server, "media/recipes", {"recipes": have + [tax_results.recipe()]})
            print('Recipe "{}" {}'.format(tax_results.RECIPE["name"],
                                          "saved in Admin > Media Library > Recipes." if res.get("ok")
                                          else "could NOT be saved: " + str(res.get("error"))))
    return 0 if ok == total and total else 1


if __name__ == "__main__":
    sys.exit(main())
