"""Queue the Voyage Certificate's custom pictures on the live game (the Pi). See the project doc
"SeaTrader Voyage Certificate" (21 Nov 2026).

The certificate is a 1920 x 1080 wallpaper: the Captain's home port behind, the home Mayor fading in from the
left, the woman who defined the voyage fading in from the right, and the words down the middle. Three sets:

  backdrops   one wide scene of each port, bright at the edges and calm and dark in the middle where the words go.
              Scenery only, so always clean.                       Ports > (port), role "night"
  mayors      each port's Mayor in the LEFT third of a wide frame, turned toward the centre, the rest of the
              frame dark and empty.                                Ports > (port), role "mayor"
  personas    the same, mirrored: she stands in the RIGHT third. Powder, Admiral Li Yue, Madam Shek, Madam Wu,
              Mrs. Marlowe, Madame Anahit and every Port Authority officer.
                                                                   Personas > (her name), role "wallpaper"

Each woman is made as one NSFW + one clean picture (default looks: nude and clean). The clean one is filed NOT NSFW
with the extra tag "clean", so it is the only one a family-friendly screen sees. Everything is 16:9 (1360 x 768).
Default = 10 backdrops + 10 Mayors x 2 + 16 women x 2 = 62 pictures. Nothing is replaced or deleted.

Every picture is tagged "certificate, wallpaper, master-shot" plus its side (cert-backdrop, cert-left, cert-right).
The "wallpaper, master-shot" tags are what keep these wide, half-empty pictures out of portraits, speaker pictures
and every other screen (web/media.js sceneOf). So the tool looks at the live game's media.js before it queues:
  * no scene rule there at all   -> nothing is queued; run Deploy_To_Pi.bat first (or --force).
  * the rule, but no "certificate" scene yet (the certificate itself is not built) -> Madam Wu and Mrs. Marlowe
    are HELD BACK, because the Accounting Ledger would use their certificate pictures as its faded page
    backdrops. Run the .bat again once the certificate is on the Pi, or add --all to queue them now.

Usage (run on BIGBOX; the Pi trusts its Admin requests):
    python tools/queue_certificate_pictures.py --dry                      (print every prompt, queue nothing)
    python tools/queue_certificate_pictures.py --ports hongkong           (one port: its backdrop, Mayor and officer)
    python tools/queue_certificate_pictures.py                            (the lot)
    python tools/queue_certificate_pictures.py --sets personas --who bosun,pirate --tiers topless,clean --count 2
Options:
    --sets     backdrops,mayors,personas (default all three)
    --ports    port keys, comma-separated: only those ports' backdrop, Mayor and Port Authority officer
               (the six women who belong to no port are left out unless --who names them)
    --who      persona keys, comma-separated: exactly these women in the personas set (bosun, pirate, agent,
               lender, taxlady, gamemaster, officer_<port>)
    --tiers    looks, comma-separated (default nude,clean). Personas: sultry, boudoir, topless, nude, clean.
               Mayors: topless, nude, clean (other looks are skipped for them).
    --count    pictures per look (1-8, default 1)
    --all      queue Madam Wu and Mrs. Marlowe even before the certificate is on the Pi
    --force    skip the media.js check altogether
    --server   default http://192.168.1.69:8765 (http://127.0.0.1:8765 for the dev server)
    --dry      print the prompts only
"""
import argparse
import json
import os
import re
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
import persona_prompts_v2 as pp  # noqa: E402

_argv, sys.argv = sys.argv, sys.argv[:1]          # queue_mayor_pictures reads argv[1] as the server at import
from queue_mayor_pictures import PROMPTS as MAYORS  # noqa: E402  (each port's Mayor, as the Media Library writes her)
sys.argv = _argv

ASPECT = "16:9"
BASE_TAGS = "certificate, wallpaper, master-shot"
ADULT = pp.ADULT                                  # "unmistakably adult": every picture of a woman must carry it

PORTS = {
    "hongkong": ("Hong Kong", "Victoria Harbour seen from the water at dusk, the Praya's lamplit godowns along the "
                 "shore, junks and lorchas riding at anchor, the Peak rising into violet haze"),
    "shanghai": ("Shanghai", "the Bund seen from the Huangpu at first light, a long line of stone trading houses and "
                 "the customs house, river junks and tea clippers crowding the roads, banners stirring"),
    "foochow": ("Foochow", "the Pagoda Anchorage on the Min River in morning mist, tea clippers loading from "
                "sampans, the white pagoda on its island, steep green tea hills fading into cloud"),
    "nagasaki": ("Nagasaki", "Nagasaki bay at twilight, the fan-shaped island of Dejima with its Dutch warehouses, "
                 "paper lanterns along the waterfront, dark wooded hills and drifting mist"),
    "manila": ("Manila", "Manila Bay at sunset from beyond the stone walls of Intramuros, church domes and bell "
               "towers against a burning sky, galleons and outrigger bancas at anchor"),
    "saigon": ("Saigon", "the Saigon river quay in heavy golden evening light, shuttered colonial houses and tall "
               "palms along the bank, sampans and a steam packet moored in the brown water"),
    "bangkok": ("Bangkok", "the Chao Phraya at golden hour, gilded temple spires and a tall prang catching the sun, "
                "royal barges and floating houses along the banks"),
    "singapore": ("Singapore", "the Singapore roads at sunset seen from the sea, Boat Quay's curve of shophouses, "
                  "bumboats and tongkangs, the green hill and its flagstaff above the town"),
    "batavia": ("Batavia", "the old harbour of Batavia at dawn, whitewashed Dutch warehouses along the Kali Besar "
                "canal, a drawbridge, tall pinisi schooners with furled sails at the quay"),
    "calcutta": ("Calcutta", "the Hooghly at Calcutta in hazy evening light, the ghats and pillared houses of Strand "
                 "Road, East Indiamen at their moorings, the ramparts of the fort low in the distance"),
}
BACKDROP_TAIL = (", a deserted waterfront with every ship riding quietly at anchor, wide panoramic composition with the "
                 "town and the tallest ships kept to the far left and far right edges, the whole middle of the picture "
                 "a calm dark expanse of still water and deepening sky, lantern light in antique brass against "
                 "lacquer-black and oxblood shadow, romanticized cinematic historical realism, China Seas 1860, "
                 "humid salt haze, rich depth and atmosphere, 16:9")

# Where she stands. The empty two thirds is where the certificate's words and the other woman go.
FRAME = {
    "left": ("Wide 16:9 composition: the woman is placed in the left third of the frame and turned toward the "
             "centre, the right two thirds of the frame open and uncluttered, falling away into deep shadow and "
             "dark empty space. "),
    "right": ("Wide 16:9 composition: the woman is placed in the right third of the frame and turned toward the "
              "centre, the left two thirds of the frame open and uncluttered, falling away into deep shadow and "
              "dark empty space. "),
}

# ---- Mayors: each port's own Mayor, from her Media Library prompt, so her face, hair and dress stay hers.
OLD_SETTING = ", standing in her harbour-office parlour and congratulating the viewer on a hard-won promotion: "
LOOK = re.compile(r"direct eye contact, (.*?), worn open at the throat")
STYLE_AT = ", sensual private-release"
OLD_OPEN = "Waist-up portrait of a breathtakingly beautiful,"
NEW_OPEN = "Wide cinematic picture of a breathtakingly beautiful, " + ADULT + ","
MAYOR_SCENE = ("standing at the great window of her harbour office at dusk, seen from the knees up, with the whole port "
               "of {port} and its fleet glittering far below, a sealed certificate of the voyage with a red wax seal "
               "held in one hand, ")
# The NSFW looks name no costume: her own dress varies too much from port to port to describe it coming off.
MAYOR_LOOKS = {
    "topless": "her dress fallen open and gathered at her hips, completely topless, her gold mayor's chain of office lying across her skin, one hand at her hip, a proud knowing smile and direct eye contact",
    "nude": "completely naked, wearing only her gold mayor's chain of office and her jewellery, her dress laid over "
            "the chair behind her, standing tall in a tasteful vintage glamour pose with one hand at her hip, "
            "a proud knowing smile and direct eye contact",
    "clean": "a dignified high-necked formal gown in the colours of her usual dress with her shoulders and chest "
             "fully covered and her gold mayor's chain of office worn over it, a proud warm smile and direct eye contact",
}
MAYOR_TIERS = tuple(MAYOR_LOOKS)

# ---- Personas: who can stand on the right (plan: "Who the story persona is"). Keys are cast.py / pp keys.
STORY = ["bosun", "pirate", "agent", "lender", "taxlady", "gamemaster"]
OFFICERS = ["officer_" + p for p in PORTS]
NAMES = {"bosun": "Powder O'Rourke", "pirate": "Admiral Li Yue", "agent": "Madam Shek Yu-lan", "lender": "Madam Wu",
         "taxlady": "Mrs. Marlowe", "gamemaster": "Madame Anahit"}
# The Accounting Ledger draws these two women's "wallpaper" pictures as its faded page backdrops (web/ledger.js WALLS).
LEDGER_SHARED = {"lender", "taxlady"}


def clean_style(erotic_tail):
    """A clean Mayor's style tail: the era and light of her usual tail with none of its erotic words."""
    tail = erotic_tail.split("sensual private-release erotic glamour, ", 1)[-1].lstrip(", ")
    return tail.replace(", no text", "").rstrip(", ")


def mayor_pieces(port):
    congrats = MAYORS[port]["mayor_congrats"]
    who = congrats.split(OLD_SETTING, 1)[0].replace(OLD_OPEN, NEW_OPEN)     # her age, face, build and who she is
    hair = LOOK.search(congrats).group(1).partition(", a ")[0]              # her hair (her costume follows it)
    at = congrats.find(STYLE_AT)
    tail = congrats[at:] if at > 0 else ", romanticized cinematic historical realism, China Seas 1860"
    return who, hair, tail


def mayor_prompt(port, tier):
    who, hair, tail = mayor_pieces(port)
    style = (", fully and modestly clothed, " + clean_style(tail)) if tier == "clean" else tail.replace(", no text", "")
    return (FRAME["left"] + "{}, {}her {}, {}{}".format(
        who, MAYOR_SCENE.format(port=PORTS[port][0]), hair, MAYOR_LOOKS[tier], style.rstrip(", ")))[:6000]


def persona_prompt(key, tier):
    return (FRAME["right"] + pp.build_master(key, tier))[:6000]


def backdrop_prompt(port):
    return ("A wide painted harbour view of " + PORTS[port][1] + BACKDROP_TAIL)[:6000]


def jobs(sets, ports, who, tiers, count):
    """[(label, look, job)] in the order they are queued: backdrops, then Mayors, then personas."""
    out = []
    if "backdrops" in sets:
        for p in ports:
            out.append(("backdrop " + p, "scene", {
                "kind": "port", "subject": p, "roles": ["night"], "prompt": backdrop_prompt(p), "aspect": ASPECT,
                "count": count, "nsfw": "no", "tags": BASE_TAGS + ", cert-backdrop, clean"}))
    if "mayors" in sets:
        for p in ports:
            for t in tiers:
                if t not in MAYOR_TIERS:
                    continue
                out.append(("mayor " + p, t, {
                    "kind": "port", "subject": p, "roles": ["mayor"], "prompt": mayor_prompt(p, t), "aspect": ASPECT,
                    "count": count, "nsfw": "no" if t == "clean" else "yes",
                    "tags": BASE_TAGS + ", cert-left, " + t}))
    if "personas" in sets:
        for k in who:
            for t in tiers:
                out.append((k, t, {
                    "kind": "persona", "subject": k, "roles": ["wallpaper"], "prompt": persona_prompt(k, t),
                    "aspect": ASPECT, "count": count, "nsfw": "no" if t == "clean" else "yes",
                    "tags": BASE_TAGS + ", cert-right, " + t}))
    return out


def scene_rule(server):
    """What the live game's media.js knows: "none" (no scene rule), "wallpaper" (the rule, no certificate
    scene yet), "certificate" (the certificate is on the server), or "" when the server cannot be reached."""
    try:
        with urllib.request.urlopen(server + "/media.js", timeout=10) as r:
            text = r.read().decode("utf-8", "replace")
    except Exception:
        return ""
    if "master-shot" not in text:
        return "none"
    return "certificate" if re.search(r"""["']certificate["']""", text) else "wallpaper"


def main():
    ap = argparse.ArgumentParser(description="Queue the Voyage Certificate's pictures on the live game.")
    ap.add_argument("--sets", default="backdrops,mayors,personas")
    ap.add_argument("--ports", default="")
    ap.add_argument("--who", default="")
    ap.add_argument("--tiers", default="nude,clean")
    ap.add_argument("--count", type=int, default=1)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--server", default="http://192.168.1.69:8765")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    server = a.server.rstrip("/")
    split = lambda s: [x.strip().lower() for x in s.split(",") if x.strip()]  # noqa: E731
    sets, tiers = split(a.sets), split(a.tiers)
    ports = split(a.ports) or list(PORTS)
    who = split(a.who) or (STORY + OFFICERS if not a.ports else ["officer_" + p for p in ports])
    bad = ([s for s in sets if s not in ("backdrops", "mayors", "personas")] + [p for p in ports if p not in PORTS]
           + [w for w in who if w not in pp.MASTER] + [t for t in tiers if t not in pp.ALL_TIERS])
    if bad or not tiers:
        print("Unknown:", ", ".join(bad) or "(no looks given)")
        print("  sets: backdrops, mayors, personas | ports:", ", ".join(PORTS))
        print("  personas:", ", ".join(STORY + OFFICERS), "| looks:", ", ".join(pp.ALL_TIERS))
        return 1
    count = max(1, min(8, a.count))

    held = set()
    if not a.dry and not a.force:
        rule = scene_rule(server)
        if not rule:
            print("Cannot reach the game at {}. Is the Pi on? Nothing was queued.".format(server))
            return 1
        if rule == "none":
            print("The game at {} does not keep wide scene pictures out of its other screens yet, so these would turn up\n"
                  "as portraits and speaker pictures. Run Deploy_To_Pi.bat first, then run this again.\n"
                  "(--force queues them anyway.) Nothing was queued.".format(server))
            return 1
        if rule == "wallpaper" and not a.all:
            held = LEDGER_SHARED & set(who)

    ok = total = pictures = skipped = 0
    for label, look, job in jobs(sets, ports, who, tiers, count):
        if job["kind"] == "persona" and job["subject"] in held:
            continue
        if look != "scene" and ADULT not in job["prompt"]:          # never queue a woman's picture without it
            print("{:22} {:8} SKIPPED: the prompt has lost its adult anchor".format(label, look))
            skipped += 1
            continue
        total += 1
        if a.dry:
            print("== {} [{}] {} {}  tags: {}\n{}\n".format(label, look, "/".join(job["roles"]),
                                                            "NSFW" if job["nsfw"] == "yes" else "clean", job["tags"], job["prompt"]))
            ok += 1
            pictures += count
            continue
        req = urllib.request.Request(server + "/api/admin/media/generate", data=json.dumps(job).encode("utf-8"),
                                     headers={"Content-Type": "application/json", "X-SeaTrader": "admin"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                res = json.loads(r.read().decode("utf-8"))
        except Exception as e:                      # the Pi is off, or Admin asked for a password
            res = {"ok": False, "error": str(e)}
        print("{:22} {:8} {}".format(label, look, res.get("msg") if res.get("ok") else "FAILED: " + str(res.get("error"))))
        if res.get("ok"):
            ok += 1
            pictures += count
    print()
    if "mayors" in sets and not any(t in MAYOR_TIERS for t in tiers):
        print("No Mayors: they are made in the looks {} only.".format(", ".join(MAYOR_TIERS)))
    if held:
        print("HELD BACK until the certificate is on the Pi: {}. The Accounting Ledger would use their certificate\n"
              "pictures as its page backdrops. Run this again after the certificate is deployed, or add --all now."
              .format(", ".join(NAMES.get(k, k) for k in sorted(held))))
    print("{} of {} jobs {} ({} pictures){}.".format(
        ok, total, "shown" if a.dry else "queued", pictures, ", {} skipped".format(skipped) if skipped else ""))
    if not a.dry:
        print("Watch them in Admin > Media Library (jobs), tag certificate.")
    return 0 if ok == total and total and not skipped else 1


if __name__ == "__main__":
    sys.exit(main())
