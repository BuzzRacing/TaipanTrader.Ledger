"""Applies the Easy-pass voice casting (20 Nov 2026) to a Crimson Ledger settings.json.

Used by Apply_Voice_Casting.bat, which pulls the Pi's config, runs this, and pushes the result back.
Only each persona's voice_id changes; everything else in settings.json is left exactly as it was.

  python tools/apply_voice_casting.py --settings S.json --library L.json [--out OUT.json] [--dry-run]

Exit codes: 0 = fine (changes written, or nothing to do), 2 = a voice is missing from the Inworld
list or a persona is missing, so NOTHING was written.
"""
import argparse
import json
import sys

# persona key -> (new Inworld voice ID, why). Accents are from Inworld's own descriptions, not from listening.
CASTING = {
    "narrator":          ("Anjali",   "Roxana is a Bombay Parsi: Indian English"),
    "lender":            ("Serene",   "Madam Wu, Canton: Singaporean English"),
    "pirate":            ("Mei",      "Admiral Li Yue: formal standard Mandarin"),
    "agent":             ("Xiaoyin",  "Madam Shek, Macau: Chinese"),
    "shipwright":        ("Shu",      "Tang Wai-lin: Singaporean English"),
    "customs":           ("Imogen",   "Inspector Vane, Bath: refined British"),
    "crier":             ("Maisie",   "Tilly Marsh, Liverpool: young British"),
    "taxlady":           ("Eleanor",  "Mrs. Marlowe, Portsmouth: British"),
    "officer_singapore": ("Wendy",    "Mrs. Thornbury, Bath: posh British"),
    "officer_manila":    ("Marta",    "Dona Ines, Seville: Castilian Spanish"),
    "officer_saigon":    ("Hélène",   "Celeste Durand, Marseille: French"),
    "officer_nagasaki":  ("Hina",     "Okada Suzu: Japanese"),
    "officer_foochow":   ("Maricel",  "Lin Bao-zhu: Filipino (Asian) English"),
    "officer_shanghai":  ("Huiling",  "Fong Mei-lin, Ningbo: Singaporean English"),
    "officer_bangkok":   ("Liwa",     "Khun Ying Malai: gentle, patient Filipino English"),
    "officer_batavia":   ("Katrien",  "Anneke van der Berg, Rotterdam: Dutch"),
    "officer_calcutta":  ("Cordelia", "Mrs. Blackwood: refined British"),
    "officer_hongkong":  ("Matilde",  "Senhora Rebelo, Macau: European Portuguese"),
    "warden_singapore":  ("Tala",     "Rosalind Pell, Penang: Filipino English (old voice Elizabeth is not on Inworld)"),
    "warden_manila":     ("Rocio",    "Dona Remedios: Castilian Spanish (old voice Julia is not on Inworld)"),
    "warden_saigon":     ("Giovanna", "Odile Marchetti, Corsica: Italian"),
    "warden_nagasaki":   ("Asuka",    "Kuroda Hisa: Japanese"),
    "warden_foochow":    ("Yoona",    "Chen Yue-hua: Korean (Asian)"),
    "warden_shanghai":   ("Xiaoyin",  "Tang Xiu-ying: Chinese (shared with Madam Shek)"),
    "warden_bangkok":    ("Minji",    "Khun Ying Prapai: Korean (old voice Priya is not on Inworld)"),
    "warden_batavia":    ("Lore",     "Hendrika Visser, Amsterdam: Dutch"),
    "warden_calcutta":   ("Winifred", "Lavinia Hartley: mature British (old voice Elizabeth is not on Inworld)"),
    "teller_tavern":     ("Dalisay",  "Josefina, Manila: Filipino English (old voice Julia is not on Inworld)"),
    "teller_drowned":    ("Rosalind", "Morwenna Teague, Cornwall: mature British (old voice Elizabeth is not on Inworld)"),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--settings", required=True)
    ap.add_argument("--library", required=True)
    ap.add_argument("--out", default="")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    with open(a.settings, encoding="utf-8") as f:
        text = f.read()
    cfg = json.loads(text)
    with open(a.library, encoding="utf-8") as f:
        lib = json.load(f).get("voices", {})
    chars = cfg.get("characters", {})

    problems, changes = [], []
    for key, (vid, why) in CASTING.items():
        c = chars.get(key)
        if c is None:
            problems.append("persona '{}' is not in this settings.json".format(key))
            continue
        v = lib.get(vid)
        if v is None:
            problems.append("voice '{}' (for {}) is not in the Inworld list".format(vid, c.get("name", key)))
            continue
        if v.get("gone_at"):
            problems.append("voice '{}' (for {}) has left Inworld".format(vid, c.get("name", key)))
            continue
        old = c.get("voice_id", "")
        if old != vid:
            changes.append((key, c.get("name", key), old, vid, why))

    print("Voice casting: {} change(s) of {} planned".format(len(changes), len(CASTING)))
    for key, name, old, new, why in changes:
        print("  {:<26} {:<12} -> {:<10} {}".format(name[:26], old or "(none)", new, why))

    if problems:
        print("\nPROBLEMS - nothing was written:")
        for p in problems:
            print("  " + p)
        return 2

    if not changes:
        print("Nothing to change: the casting is already applied.")
        return 0
    if a.dry_run or not a.out:
        print("\n(check only - nothing written)")
        return 0

    for key, _n, _o, new, _w in changes:
        chars[key]["voice_id"] = new
    out = json.dumps(cfg, indent=1, ensure_ascii=False)
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        f.write(out)
    print("\nWrote " + a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
