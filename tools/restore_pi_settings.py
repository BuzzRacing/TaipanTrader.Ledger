"""Lists the saved copies of config/settings.json and puts one back (ported from Atomic Ledger, 24 Nov 2026).  Run ON the Pi (or on the PC) from the game folder.

  python3 tools/restore_pi_settings.py --list              every backup, newest first: does the game accept it, and is it
                                                           the Crimson setup (10 ports, 1860)?
  python3 tools/restore_pi_settings.py --restore FILE      copy that backup (a name in config/backups) over settings.json.
The current settings are saved first as config/backups/settings_before_restore_<time>.json, and a backup the game would
reject is refused.  Stop the game before restoring (the batch file does)."""
import datetime
import glob
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
CFG = os.path.join(ROOT, "config")
BACKUPS = os.path.join(CFG, "backups")
CURRENT = os.path.join(CFG, "settings.json")
PORTS = {"hongkong", "shanghai", "nagasaki", "manila", "saigon", "bangkok", "singapore", "batavia", "calcutta", "foochow"}


def inspect(path):
    import config
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError) as e:
        return {"ok": False, "why": "unreadable ({})".format(e)}
    try:
        _c, errors = config.validate(json.loads(json.dumps(d)))
    except Exception as e:
        errors = ["check failed: {}".format(e)]
    ports, goods = d.get("ports") or {}, d.get("goods") or {}
    chars = d.get("characters") or {}
    ships = d.get("ships") or {}
    return {
        "ok": not errors, "why": "; ".join(errors[:2]),
        "crimson": set(ports) == PORTS, "ports": len(ports), "goods": len(goods), "chars": len(chars),
        "first_port": next(iter(ports.values()), {}).get("name", "-"), "ships": len(ships),
        "year": ((d.get("rules") or {}).get("game") or {}).get("start_year"),
        "portraits": sum(1 for c in chars.values() if c.get("portrait")),
        "size": os.path.getsize(path),
    }


def score(i):
    return (i["ok"], i.get("crimson", False))


def files():
    out = [(CURRENT, "settings.json (CURRENT)")]
    for p in glob.glob(os.path.join(BACKUPS, "*.json")):
        out.append((p, os.path.basename(p)))
    return sorted(out, key=lambda t: os.path.getmtime(t[0]), reverse=True)


def main(argv):
    if "--restore" in argv:
        name = argv[argv.index("--restore") + 1]
        src = os.path.join(BACKUPS, os.path.basename(name))
        if not os.path.isfile(src):
            print("No such backup: " + name)
            return 1
        i = inspect(src)
        if not i["ok"]:
            print("Not restored: the game would reject that file ({}).".format(i["why"]))
            return 1
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        keep = os.path.join(BACKUPS, "settings_before_restore_{}.json".format(stamp))
        shutil.copy2(CURRENT, keep)
        tmp = CURRENT + ".tmp"
        shutil.copy2(src, tmp)
        os.replace(tmp, CURRENT)
        print("Restored {} ({} ports, {} cargoes, {} cast cards).".format(name, i["ports"], i["goods"], i["chars"]))
        print("The settings that were there are kept as " + os.path.basename(keep))
        print("RESTORE_OK")
        return 0
    best = None
    print("{:<48} {:<17} {:>3} {:>4} {:>4}  {}".format("file", "saved", "port", "good", "cast", "notes"))
    for path, label in files():
        i = inspect(path)
        when = datetime.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%d %b %H:%M:%S")
        notes = []
        if not i["ok"]:
            notes.append("REJECTED: " + i["why"])
        else:
            notes.append("CRIMSON" if i["crimson"] else "not the Crimson setup")
            if i["crimson"]:
                notes.append("portraits set: %d" % i["portraits"])
        print("{:<48} {:<17} {:>4} {:>4} {:>4}  {}".format(label[:48], when, i.get("ports", "-"), i.get("goods", "-"),
                                                          i.get("chars", "-"), " ".join(notes)))
        if i["ok"] and i["crimson"] and path != CURRENT and best is None:
            best = os.path.basename(path)
    print("SUGGEST: " + (best or "none"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
