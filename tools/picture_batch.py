"""Shared plumbing for the Crimson Ledger picture tools (ported from Atomic Ledger, 24 Nov 2026): find the game, check the prompts, queue
the pictures in the Media Library, wait for them, and put the new ones in the game.

Nothing uses it yet: a tool opts in by building a list of jobs and calling run(). The older tools/queue_*.py only queue
and walk away; this one also waits for the pictures, files the new ones in a Graphics slot and switches off the ones
they replace. A job is a dict:
    label   what to print for it
    body    the Media Library request (kind, subject, roles, prompt, aspect, count, nsfw, tags)
    old     ids of the library pictures this one replaces (switched off afterwards, never deleted)
    slot    ("ships", key) to put the new picture in that Graphics slot and star it, or None
"""
import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import theme_guard  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS = os.path.join(ROOT, "config", "settings.json")
SERVERS = ("http://192.168.1.69:8765", "http://127.0.0.1:8765")
HEADERS = {"Content-Type": "application/json", "X-SeaTrader": "admin"}
LIVE = ("waiting", "running", "cancelling")
POLL_SECONDS = 5
STALL_SECONDS = 20 * 60          # nothing painted for this long: stop waiting (the jobs stay queued)


def call(server, path, body=None, timeout=30):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(server + "/api/admin/" + path, data=data, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def find_server(wanted=""):
    for server in ([wanted.rstrip("/")] if wanted else SERVERS):
        try:
            if call(server, "all", timeout=20).get("ok"):
                return server
        except Exception as e:
            print("No game server at {} ({})".format(server, e))
    return ""


def load(wanted, dry):
    """(server, settings, library items). With --dry and no game running, the settings on this PC and no library."""
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass
    server = find_server(wanted)
    if server:
        print("Game server:", server)
        return server, call(server, "all", timeout=30)["config"], call(server, "media/library", timeout=60).get("items") or []
    if dry:
        print("No game server; using this PC's config\\settings.json instead.")
        with open(SETTINGS, encoding="utf-8") as f:
            return "", json.load(f), []
    print("The game server is not running. Start Crimson Ledger (or switch the Pi on) and run this again.")
    return "", None, []


def wait_for(server, jobs):
    """Watch the Media Library queue until every job in {job id: label} has finished. Returns {job id: job row}."""
    done, last, told_paused = {}, time.time(), False
    while len(done) < len(jobs):
        time.sleep(POLL_SECONDS)
        try:
            res = call(server, "media/jobs", timeout=30)
        except Exception as e:
            print("  (the game server did not answer: {})".format(e))
            res = {}
        rows = {j["id"]: j for j in res.get("jobs") or []}
        for jid, label in jobs.items():
            row = rows.get(jid)
            if jid in done or (row and row.get("status") in LIVE):
                continue
            if row is None and res:
                row = {"status": "lost", "items": [], "error": "the job is no longer in the queue"}
            if row is None:
                continue
            done[jid] = row
            last = time.time()
            print("{:3}/{} {:46} {}".format(len(done), len(jobs), label[:46], "painted" if row.get("items")
                                             else "FAILED: " + str(row.get("error") or row.get("status"))))
        paused = (((res.get("queue") or {}).get("lanes") or {}).get("picture") or {}).get("paused")
        if paused and not told_paused:
            told_paused = True
            print("  The picture queue is paused. Press Resume in Admin > Media Library and this carries on.")
        if paused:
            last = time.time()
        elif time.time() - last > STALL_SECONDS:
            print("Nothing has been painted for {} minutes; not waiting any longer.".format(STALL_SECONDS // 60))
            print("Is the image computer on and running ComfyUI? The jobs stay queued in Admin > Media Library.")
            break
    return done


def run(server, jobs, keep_old=False, dry=False, what="picture", resume="Run it again to pick up the rest."):
    """Check, queue, wait, file. Returns the exit code for the bat."""
    if not jobs:
        print("Nothing to paint.")
        return 0
    if theme_guard.report((j["label"], j["body"]["prompt"]) for j in jobs):
        print("Nothing was queued. Fix the wording above (or the cast member's portrait prompt) and run this again.")
        return 1
    print("{} {}(s) to paint. Theme check passed: no modern wording.".format(len(jobs), what))
    if dry:
        for j in jobs:
            print("\n== {} [{}]\n{}".format(j["label"], j["body"].get("tags", ""), j["body"]["prompt"]))
        return 0

    queued = {}                                        # job id -> job
    for j in jobs:
        try:
            res = call(server, "media/generate", j["body"])
        except Exception as e:
            res = {"ok": False, "error": str(e)}
        if res.get("ok"):
            queued[res["job"]] = j
        else:
            print("{:46} NOT QUEUED: {}".format(j["label"][:46], res.get("error")))
    if not queued:
        return 1
    print("Queued {}. Painting (watch them in Admin > Media Library)...".format(len(queued)))
    started = time.time()
    finished = wait_for(server, {jid: j["label"] for jid, j in queued.items()})

    lib = call(server, "media/library", timeout=60).get("items") or []
    url_of = {i["id"]: i["url"] for i in lib}
    painted = []                                       # (job, [new item ids])
    for jid, row in finished.items():
        ids = [x for x in row.get("items") or [] if x in url_of]
        if ids:
            painted.append((queued[jid], ids))
    if not painted:
        print("\nNothing was painted. Is the image computer on and running ComfyUI?")
        return 1

    # Graphics slots (the fleet cards): choose the new picture and Save & apply, as it is right now so Admin
    # changes made while the pictures were painting are kept.
    slotted = [(j, ids) for j, ids in painted if j.get("slot")]
    if slotted:
        cfg = call(server, "all", timeout=30)["config"]
        gr = cfg.setdefault("graphics", {})
        for j, ids in slotted:
            group, key = j["slot"]
            gr.setdefault(group, {})[key] = url_of[ids[-1]]
        res = call(server, "save", {"config": cfg, "langs": {}}, timeout=60)
        if not res.get("ok"):
            print("\nSAVE FAILED: {} {}".format(res.get("error"), res.get("errors") or ""))
            print("The new pictures are in the Media Library; choose them under Admin > Graphics.")
            return 1
        for j, ids in slotted:
            call(server, "media/update", {"ids": [ids[-1]], "changes": {"primary": True, "enabled": True}})

    retired = 0
    if not keep_old:
        new = {x for _j, ids in painted for x in ids}
        old = sorted({x for j, _ids in painted for x in j.get("old") or []} - new)
        if old:
            retired = call(server, "media/update", {"ids": old, "changes": {"enabled": False}}).get("changed", 0)

    print()
    print("{} of {} {}s painted in {:.0f} min and put in the game.".format(
        len(painted), len(jobs), what, (time.time() - started) / 60))
    if retired:
        print("{} older picture(s) switched off (still in Admin > Media Library; nothing was deleted).".format(retired))
    if len(painted) < len(jobs):
        print("Not everything was painted. " + resume)
        return 1
    return 0
