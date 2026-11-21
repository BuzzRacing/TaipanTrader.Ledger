"""Review a port's personas and fill their picture gaps (21 Nov 2026). See the project doc "SeaTrader Image Batches".

Reads the LIVE Media Library, counts the pictures every woman of one port has, prints the review, and queues
only what is missing to reach the target (default 1 clean + 5 NSFW). Run it again any time: pictures already
filed and jobs still waiting on the farm are counted, so a second run only fills what is still short.

Who is "of the port":
  * the cast whose home port it is (Admin > Cast & Voices), filed under Media Library > Personas > (her name)
  * the port's own women (Media Library > Ports > (port)): keeper, shipmaster, mayor, taxlady

Two ways to count, asked on screen unless --by is given:
  --by persona   1 clean + 5 NSFW for each woman, any picture role
  --by role      1 clean + 5 NSFW for each woman AND each picture role (portrait, speaking, idle, happy, angry, sly)

What is counted: enabled pictures whose file exists. NSFW = filed NSFW; clean = not filed NSFW. Videos are not
counted. A picture with several roles counts for each of them; one with no roles counts for all of them.

Prompts: a cast member's come from her OWN cast prompt (the live game's, else this folder's cast.py), exactly as
tools/queue_persona_pairs.py builds its pairs. A port woman's come from her own pictures already in the library.
New pictures are tagged "gap-fill" (clean ones "gap-fill, clean") so a batch is easy to find and undo.

Run on BIGBOX (the Pi trusts its Admin requests): Queue_Port_Persona_Fill.bat hongkong, or
    python tools/queue_port_persona_fill.py --port hongkong            review, then asks before queuing anything
    python tools/queue_port_persona_fill.py --port hongkong --review   review only (also saved as a text file)
    python tools/queue_port_persona_fill.py --port hongkong --by role --dry       print every prompt, queue nothing
    python tools/queue_port_persona_fill.py --port manila --clean 2 --nsfw 8 --by persona --yes
Options:
    --port        port key (hongkong, manila, ...). --list-ports shows them
    --clean N     clean pictures wanted (default 1)        --nsfw N    NSFW pictures wanted (default 5)
    --by          persona or role (asked on screen when left out)
    --who a,b     only these cast keys / port roles        --skip a,b  leave these out
    --add a,b     extra cast keys to treat as this port's (e.g. bosun)
    --port-roles  the port's own women to include (default keeper,shipmaster,mayor,taxlady; "none" for none)
    --only        nsfw or clean                            --max N     stop after N pictures this run
    --review      print and save the review, queue nothing --dry       print the prompts, queue nothing
    --yes         do not ask before queuing                --server    default http://192.168.1.69:8765
"""
import argparse
import datetime
import json
import os
import re
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import queue_persona_pairs as pairs      # noqa: E402  (the house pair rule: MOODS, NUDE, CLEAN_STYLE, DECENT)

ROLES = ("portrait", "speaking", "idle", "happy", "angry", "sly")
PORT_ROLES = ("keeper", "shipmaster", "mayor", "taxlady")
TAG = "gap-fill"
# A fresh pose for each extra picture of the same woman in the same role, so five are not five copies.
TAKES = ["", "seen from a slightly different angle, turned three-quarters to the camera",
         "a closer framing, head and shoulders filling more of the picture, a different tilt of the head",
         "a different pose, leaning on one arm, glancing back at the viewer over her shoulder",
         "a different moment, seated, the lantern light coming from the other side",
         "a different pose, standing with one hand on her hip, seen from a little lower",
         "a different moment, her hair a little looser, the scene behind her at another hour of the day",
         "a different pose, both hands busy with the tools of her trade, looking up at the viewer"]
BARE = re.compile(r"\b(nude|naked|nudity|topless|undressed|nipples|breasts|vagina|ass|bottom|bare (skin|hips|belly|body|d.colletage)|"
                  r"shown openly|exposing|unashamed)\b", re.I)
STYLE_MARKS = (", sensual private-release", ", romanticized")


def call(server, path, body=None, timeout=60):
    req = urllib.request.Request(server + path, data=json.dumps(body).encode("utf-8") if body is not None else None,
                                 headers={"Content-Type": "application/json", "X-SeaTrader": "admin"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


# ---------------------------------------------------------------- who lives here

def load_cast(server):
    """{key: {name, home_port, prompt}} from the live game, topped up from this folder's cast.py."""
    out, ports = {}, {}
    try:
        cfg = call(server, "/api/admin/all", timeout=20)["config"]
        for k, v in (cfg.get("characters") or {}).items():
            out[k] = {"name": v.get("name", k), "home_port": v.get("home_port") or "",
                      "prompt": v.get("portrait_prompt") or ""}
        p = cfg.get("ports") or {}
        ports = ({k: (v.get("name") or k) for k, v in p.items()} if isinstance(p, dict)
                 else {(x.get("id") or x.get("key")): (x.get("name") or x.get("id")) for x in p if isinstance(x, dict)})
    except Exception as e:
        print("Could not read the live game's cast ({}); using this folder's cast.py".format(e))
    try:
        sys.path.insert(0, ROOT)
        import cast
        for k, v in cast.CHARACTERS.items():
            if k not in out:
                out[k] = {"name": v.get("name", k), "home_port": v.get("home_port") or "",
                          "prompt": v.get("portrait_prompt") or ""}
    except Exception as e:
        if not out:
            print("Could not read cast.py either ({}).".format(e))
    return out, ports


def warden_clean_prompts():
    """The wardens' dressed prompts (their cast prompts are nude), from queue_jail_clean_pictures.py."""
    argv, sys.argv = sys.argv, sys.argv[:1]
    try:
        import queue_jail_clean_pictures as j
        return {k: (j.ADULT + d[3:] if d.startswith("An ") else j.ADULT + d) for k, d in j.PROMPTS.items()}
    except Exception:
        return {}
    finally:
        sys.argv = argv


# ---------------------------------------------------------------- prompts

def split(prompt):
    """(what she looks like, the style tail)."""
    for mark in STYLE_MARKS:
        at = prompt.find(mark)
        if at > 0:
            return prompt[:at], prompt[at + 2:]
    return prompt, ""


def dressed(desc):
    """A description made decent: undressed wording swapped, and any clause that is plainly bare dropped."""
    for pat, rep in pairs.DECENT:
        desc = re.sub(pat, rep, desc)
    desc = re.sub(r",? ?(opened and unbuttoned |falling open, |slipping off her shoulders, )?exposing her [^,]*", "", desc)
    keep = [c for c in desc.split(", ") if not BARE.search(c)]
    return re.sub(r"\s+,", ",", re.sub(r"  +", " ", ", ".join(keep))).strip(" ,")


def build(base, role, kind, take, clean_base=""):
    """One prompt for a cast member: her cast prompt + the role's mood (none for a plain portrait) + a pose."""
    mood = "" if role in ("portrait", "") else pairs.MOODS.get(role, role)
    extra = ", ".join(x for x in (mood, TAKES[take % len(TAKES)]) if x)
    desc, tail = split(base)
    if kind == "nsfw":
        body = ", ".join(x for x in (desc, extra, "" if "nude" in desc.lower() else pairs.NUDE) if x)
        return (body + (", " + tail if tail else ""))[:6000]
    body = split(clean_base)[0] if clean_base else dressed(desc)
    return ", ".join(x for x in (body, extra, pairs.CLEAN_STYLE) if x)[:6000]


def build_port(sources, kind, take):
    """One prompt for a port woman, from her own pictures: same kind first, else the other kind converted."""
    same = [s for s in sources if bool(s.get("nsfw")) == (kind == "nsfw")]
    src = (same or sources)[take % len(same or sources)]
    desc, tail = split(src["prompt"])
    extra = TAKES[take % len(TAKES)] if (take or not same) else TAKES[1]
    if kind == "nsfw":
        bare = "" if same else pairs.NUDE
        return (", ".join(x for x in (desc, extra, bare) if x) + (", " + tail if tail else ""))[:6000]
    body = desc if same else dressed(desc)
    return ", ".join(x for x in (body, extra, pairs.CLEAN_STYLE) if x)[:6000]


# ---------------------------------------------------------------- counting

def is_nsfw(v):
    return v is True or str(v).lower() in ("yes", "true", "1")


def tally(lib, kind, subject, roles):
    """{role: [clean, nsfw]} and [clean, nsfw] in all, counting filed pictures and jobs still on the farm."""
    per = {r: [0, 0] for r in roles}
    total, waiting = [0, 0], 0
    for i in lib.get("items", []):
        if i.get("kind") != kind or i.get("subject") != subject or i.get("type") == "video":
            continue
        if i.get("enabled") is False or i.get("missing"):
            continue
        n = 1 if i.get("nsfw") else 0
        mine = [r for r in roles if r in (i.get("roles") or [])] if i.get("roles") else list(roles)
        if kind == "port" and not mine:
            continue
        total[n] += 1
        for r in mine:
            per[r][n] += 1
    for j in lib.get("jobs", []):
        if j.get("status") not in ("waiting", "running") or j.get("type") == "video":
            continue
        if j.get("kind") != kind or j.get("subject") != subject:
            continue
        left = max(0, int(j.get("count") or 1) - int(j.get("done") or 0) - int(j.get("failed") or 0))
        mine = [r for r in roles if r in (j.get("roles") or [])]
        if not left or (kind == "port" and not mine):
            continue
        n = 1 if is_nsfw(j.get("nsfw")) else 0
        total[n] += left
        waiting += left
        for r in mine:
            per[r][n] += left
    return per, total, waiting


def shortfall(per, total, by, want, roles):
    """[(role, kind, how many)] still needed. By persona, new pictures go to her thinnest roles."""
    need = []
    if by == "role":
        for r in roles:
            for n, kind in ((0, "clean"), (1, "nsfw")):
                if want[n] - per[r][n] > 0:
                    need.append((r, kind, want[n] - per[r][n]))
        return need
    for n, kind in ((0, "clean"), (1, "nsfw")):
        have = {r: per[r][n] for r in roles}
        for _ in range(max(0, want[n] - total[n])):
            r = min(roles, key=lambda x: (have[x], roles.index(x)))
            have[r] += 1
            need.append((r, kind, 1))
    return need


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description="Review a port's personas and fill their picture gaps.")
    ap.add_argument("--port", default="")
    ap.add_argument("--clean", type=int, default=1)
    ap.add_argument("--nsfw", type=int, default=5)
    ap.add_argument("--by", choices=["persona", "role"], default="")
    ap.add_argument("--who", default="")
    ap.add_argument("--skip", default="")
    ap.add_argument("--add", default="")
    ap.add_argument("--port-roles", default=",".join(PORT_ROLES))
    ap.add_argument("--only", choices=["nsfw", "clean"], default="")
    ap.add_argument("--max", type=int, default=0)
    ap.add_argument("--review", action="store_true")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--list-ports", action="store_true")
    ap.add_argument("--server", default="http://192.168.1.69:8765")
    a = ap.parse_args()
    server = a.server.rstrip("/")
    csv = lambda s: [x.strip() for x in s.split(",") if x.strip()]          # noqa: E731

    try:
        lib = call(server, "/api/admin/media/library")
    except Exception as e:                          # the Pi is off, or Admin asked for a password
        print("Could not read the Media Library at {}: {}".format(server, e))
        return 1
    cast, ports = load_cast(server)
    homes = sorted({c["home_port"] for c in cast.values() if c["home_port"]} | set(ports))
    if a.list_ports or not a.port:
        print("Ports: " + ", ".join(homes))
        print("Run again with --port <one of them>.")
        return 0 if a.list_ports else 1
    port = a.port.lower().replace(" ", "")
    if port not in homes:
        print("No port called '{}'. Ports: {}".format(a.port, ", ".join(homes)))
        return 1
    port_name = ports.get(port) or port.title()
    want = (max(0, a.clean), max(0, a.nsfw))
    who, skip = csv(a.who), csv(a.skip)
    wanted = lambda key: (not who or key in who) and key not in skip          # noqa: E731

    # Everyone to look at: (label, kind, subject, roles, name)
    people = []
    for key in sorted(k for k, c in cast.items() if c["home_port"] == port or k in csv(a.add)):
        if wanted(key):
            people.append((key, "persona", key, ROLES, cast[key]["name"]))
    port_roles = [] if a.port_roles.lower() == "none" else csv(a.port_roles)
    for role in port_roles:
        if wanted(role):
            people.append((port + " " + role, "port", port, (role,), "{}'s {}".format(port_name, role)))
    if not people:
        print("Nobody to review for", port_name)
        return 1

    rows, plans = [], {"persona": [], "role": []}
    for label, kind, subject, roles, name in people:
        per, total, waiting = tally(lib, kind, subject, roles)
        rows.append((label, name, kind, roles, per, total, waiting))
        for by in plans:
            for role, pic, n in shortfall(per, total, "role" if kind == "port" else by, want, roles):
                if not a.only or a.only == pic:
                    plans[by].append((label, kind, subject, role, pic, n, per[role][0 if pic == "clean" else 1]))
    count = {by: sum(p[5] for p in plans[by]) for by in plans}

    # ---- the review
    out = []
    say = out.append
    say("Crimson Ledger: {} personas, picture review   ({}, live library at {})".format(
        port_name, datetime.datetime.now().strftime("%d %b %Y %H:%M"), server))
    say("Target: {} clean + {} NSFW.   Each cell is clean/NSFW.   * = short of the target".format(*want))
    say("")
    head = "{:19}{:31}".format("Key", "Who") + "".join("{:>10}".format(r) for r in ROLES) + "{:>10}".format("ALL")
    say(head)
    say("-" * len(head))
    cell = lambda c, n: "{:>10}".format("{}/{}{}".format(c, n, "*" if c < want[0] or n < want[1] else " "))  # noqa: E731
    for label, name, kind, roles, per, total, waiting in rows:
        if kind == "persona":
            line = "{:19}{:31}".format(label[:18], name[:30]) + "".join(cell(*per[r]) for r in ROLES) + cell(*total)
        else:
            line = "{:19}{:31}".format(label[:18], name[:30]) + " " * 10 * len(ROLES) + cell(*total)
        say(line + ("   ({} on the farm)".format(waiting) if waiting else ""))
    say("")
    say("To reach the target:")
    say("  1. For each woman (any picture role):     {:4} pictures".format(count["persona"]))
    say("  2. For each woman AND each picture role:  {:4} pictures".format(count["role"]))
    print("\n".join(out))
    try:
        folder = os.path.join(ROOT, "cache", "reviews")
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, "port_personas_{}.txt".format(port))
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(out) + "\n")
        print("\nReview saved to", path)
    except OSError:
        pass
    if a.review:
        return 0

    # ---- which count, and go?
    by = a.by
    if not by:
        if not count["persona"] and not count["role"]:
            print("\nNothing is short. Nothing to queue.")
            return 0
        if a.yes or a.dry:
            by = "persona"
        else:
            pick = input("\nQueue which? 1 = each woman ({}), 2 = each woman and role ({}), Enter = nothing: ".format(
                count["persona"], count["role"])).strip()
            by = {"1": "persona", "2": "role"}.get(pick, "")
            if not by:
                print("Nothing queued.")
                return 0
    plan = plans[by]
    if a.max and count[by] > a.max:
        print("Stopping at {} of {} pictures this run (--max). Run it again for the rest.".format(a.max, count[by]))
    if not plan:
        print("\nNothing is short. Nothing to queue.")
        return 0
    if a.by and not (a.yes or a.dry):
        if input("\nQueue {} pictures on the farm? (Y/N): ".format(min(count[by], a.max or count[by]))).strip().lower() \
                not in ("y", "yes"):
            print("Nothing queued.")
            return 0

    clean_wardens = warden_clean_prompts()
    ok = total = 0
    for label, kind, subject, role, pic, n, have in plan:
        if kind == "port":
            sources = [i for i in lib.get("items", []) if i.get("kind") == "port" and i.get("subject") == subject
                       and role in (i.get("roles") or []) and len(i.get("prompt") or "") > 20
                       and i.get("type") != "video" and i.get("enabled") is not False]
            plain = [i for i in sources if i.get("roles") == [role]]
            sources = plain or sources
            if not sources:
                print("{:19} {:9} {:5} has no picture to copy a prompt from; skipped".format(label, role, pic))
                continue
        else:
            base = (cast[subject]["prompt"] or "").replace("{adult}", "unmistakably adult").replace(", {style}", "")
            if len(base) < 20:
                print("{:19} has no cast prompt; skipped".format(label))
                continue
        for k in range(n):
            if a.max and total >= a.max:
                break
            total += 1
            take = have + k
            prompt = (build_port(sources, pic, take) if kind == "port"
                      else build(base, role, pic, take, clean_wardens.get(subject, "")))
            job = {"kind": kind, "subject": subject, "roles": [role], "prompt": prompt, "aspect": "3:4", "count": 1,
                   "nsfw": "yes" if pic == "nsfw" else "no", "tags": TAG if pic == "nsfw" else TAG + ", clean"}
            if a.dry:
                print("\n== {} / {} / {}\n{}".format(label, role, pic.upper(), prompt))
                ok += 1
                continue
            try:
                res = call(server, "/api/admin/media/generate", job, timeout=20)
            except Exception as e:
                res = {"ok": False, "error": str(e)}
            print("{:19} {:9} {:5} {}".format(label, role, pic,
                                             res.get("msg") if res.get("ok") else "FAILED: " + str(res.get("error"))))
            ok += bool(res.get("ok"))
    print()
    print("{} of {} pictures {}.".format(ok, total, "shown" if a.dry else "queued. Watch them in Admin > Media Library (jobs)"))
    return 0 if ok == total else 1


if __name__ == "__main__":
    sys.exit(main())
