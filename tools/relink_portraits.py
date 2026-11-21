"""Relink cast portraits on this machine's Crimson Ledger.

Puts back each character's portrait link in config/settings.json when it is
blank, using the portrait files already in web/uploads. Characters that
already have a portrait are left alone. The settings it replaces are kept in
config/backups first. Nothing else in the settings changes.

Run from the game folder:  python3 tools/relink_portraits.py
Add --check to only report, without changing anything.
"""
import glob
import json
import os
import shutil
import sys
import time

# The portraits linked on the main PC (D:\SeaTrader\config\settings.json, 20 Nov 2026).
KNOWN = {
    "narrator": "portrait-narrator-74bb5d1b.webp",
    "bosun": "portrait-bosun-3bb0c4a1.webp",
    "lender": "portrait-lender-7c0ef57d.webp",
    "pirate": "portrait-pirate-de5e688f.webp",
    "agent": "portrait-agent-0ac6fcf0.webp",
    "banker": "portrait-banker-1ba0a27f.webp",
    "comprador": "portrait-comprador-923b711d.webp",
    "shipwright": "portrait-shipwright-bc277b87.webp",
    "customs": "portrait-customs-422516f6.webp",
    "crier": "portrait-crier-4195e5dd.webp",
    "bookmaker": "portrait-bookmaker-2ed8ebda.webp",
    "mayor": "portrait-mayor-29f09073.webp",
    "taxlady": "portrait-taxlady-6bbeb4a0.webp",
    "officer_singapore": "portrait-officer_singapore-d326ddeb.webp",
    "officer_manila": "portrait-officer_manila-b8a53d03.webp",
    "officer_saigon": "portrait-officer_saigon-0f2061f3.webp",
    "officer_nagasaki": "portrait-officer_nagasaki-d4993606.webp",
    "officer_foochow": "portrait-officer_foochow-2991db6f.webp",
    "officer_shanghai": "portrait-officer_shanghai-45bcf0d6.webp",
    "officer_bangkok": "portrait-officer_bangkok-8302134d.webp",
    "officer_batavia": "portrait-officer_batavia-cb0e29a4.webp",
    "officer_calcutta": "portrait-officer_calcutta-f77f45aa.webp",
    "officer_hongkong": "portrait-officer_hongkong-5f81cb49.webp",
}

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS = os.path.join(ROOT, "config", "settings.json")
BACKUPS = os.path.join(ROOT, "config", "backups")
UPLOADS = os.path.join(ROOT, "web", "uploads")


def find_file(cid):
    """The portrait file for a character: the known one if present, else the newest of hers."""
    known = KNOWN.get(cid)
    if known and os.path.isfile(os.path.join(UPLOADS, known)):
        return known
    mine = [p for ext in ("webp", "png", "jpg", "jpeg")
            for p in glob.glob(os.path.join(UPLOADS, "portrait-%s-*.%s" % (cid, ext)))]
    if not mine:
        return None
    return os.path.basename(max(mine, key=os.path.getmtime))


def main():
    check_only = "--check" in sys.argv
    with open(SETTINGS, encoding="utf-8") as f:
        cfg = json.load(f)
    chars = cfg.get("characters") or {}

    fixed, kept, no_file, broken = [], [], [], []
    for cid, c in chars.items():
        link = c.get("portrait") or ""
        if link:
            if os.path.isfile(os.path.join(ROOT, "web", link.lstrip("/"))):
                kept.append(cid)
                continue
            broken.append("%s (was %s)" % (cid, link))
        name = find_file(cid)
        if not name:
            no_file.append(cid)
            continue
        c["portrait"] = "/uploads/" + name
        fixed.append("%s -> /uploads/%s" % (cid, name))

    print("Characters:            %d" % len(chars))
    print("Already linked, kept:  %d" % len(kept))
    print("Relinked:              %d" % len(fixed))
    for line in fixed:
        print("   " + line)
    if broken:
        print("Links that pointed at a missing file (relinked above if a file was found):")
        for line in broken:
            print("   " + line)
    if no_file:
        print("No portrait file on this machine for: " + ", ".join(no_file))

    if check_only or not fixed:
        print("NO_CHANGE" if not fixed else "CHECK_ONLY")
        return

    os.makedirs(BACKUPS, exist_ok=True)
    backup = os.path.join(BACKUPS, time.strftime("settings-%Y%m%d-%H%M%S-before-portrait-relink.json"))
    shutil.copy2(SETTINGS, backup)
    tmp = SETTINGS + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=1)
    os.replace(tmp, SETTINGS)
    print("Backup: " + backup)
    print("RELINKED")


if __name__ == "__main__":
    main()
