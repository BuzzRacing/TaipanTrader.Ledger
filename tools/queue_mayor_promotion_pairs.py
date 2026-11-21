"""Queue the Promotion Story's mayor pictures (20 Nov 2026) on the live game (the Pi): for each of the ten port
mayors, FOUR NSFW pictures that lead the viewer along one soap-opera scene and get more undressed at every step,
plus ONE clean twin for family-friendly screens. 10 mayors x 5 = 50 pictures, one job each, filed into
Media Library > Ports > (port) with the role "mayor_congrats" (the Mayor picture the Promotion Story rotates through).

  step 1  the gasp       she reads out the promotion and her gown slips: one shoulder and the tops of her breasts bare
  step 2  the confession her gown falls open to the waist, back and shoulders bare, one arm held across her breasts
  step 3  the swoon      topless, gown pooled at her hips, only her chain of office and a hand covering her
  step 4  the surrender  fully nude on the unrolled commission, only her chain and jewellery, strategically draped
  clean   the same scene, fully and modestly clothed, hand on heart, tearful and delighted

Each prompt starts from that port's own congratulations prompt in queue_mayor_pictures.py, so every woman keeps her
own age, face, hair and costume. The nude steps are glamour nudes: sultry, never explicit (the house voice).
Filed NSFW "yes" with tags "mayor-set promotion-story soap-drama promo-step-N"; the clean one NSFW "no" with the extra
tag "clean", so family-friendly screens only ever receive the clean one.

Run from BIGBOX (the Pi trusts its Admin requests): Queue_Mayor_Promotion_Pairs.bat, or
    python tools/queue_mayor_promotion_pairs.py [--server URL] [--only nsfw|clean] [--port manila] [--dry]
      --dry    print the prompts, queue nothing
"""
import argparse
import json
import os
import re
import sys
import urllib.request

_argv, sys.argv = sys.argv, sys.argv[:1]          # queue_mayor_pictures reads argv[1] as the server at import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from queue_mayor_pictures import PROMPTS          # noqa: E402  (each port's mayor, as the Media Library writes her)
sys.argv = _argv

OLD_SETTING = ", standing in her harbour-office parlour and congratulating the viewer on a hard-won promotion: "
LOOK = re.compile(r"direct eye contact, (.*?), worn open at the throat")
STYLE_AT = ", sensual private-release"

SCENE = ("in her private harbour-office parlour late at night with a storm breaking over the harbour, the sealed "
         "commission of promotion in her hand, ")
SOAP = (", melodramatic prestige-soap-opera tableau, heightened romantic emotion, rain-lashed window, guttering "
        "candles and sheet lightning, her head and her body down to her hips inside the frame with room around them")

# What she does and how much she has on, from the gasp to the surrender.
STEPS = [
    ("the gasp",
     "having just read the viewer's promotion aloud she gasps with scandalous delight, one hand flying to her chest, "
     "{garb} slipping dangerously low so one shoulder and the tops of her breasts are bare, a lace come undone, "
     "flushed cheeks, heavy-lidded eyes locked on the camera, a candle guttering in the draught"),
    ("the confession",
     "she turns from the rain-lashed window and confesses in a breathless whisper how long she has waited for this "
     "promotion, glancing back over her bare shoulder at the camera, {garb} fallen open to her waist so her back and "
     "both shoulders are bare, one forearm held across her bare breasts in mock modesty, her hair coming down, tears "
     "of triumph shining on her lashes, a sheer silk chemise sliding off her arm"),
    ("the swoon",
     "she swoons theatrically back against the heavy teak desk as lightning flashes, the commission and a scatter of "
     "letters fallen to the floor, {garb} pooled around her hips, topless, her gold mayor's chain of office and one "
     "hand just covering her breasts, back arched, head thrown back with parted lips and then burning eyes on the "
     "camera, a spilled glass of Madeira, lightning rim-lighting her bare skin"),
    ("the surrender",
     "in the last scene of the episode she has let everything fall, completely nude, reclining across the teak desk "
     "on the unrolled commission and a drift of red silk, wearing only her gold mayor's chain of office and her "
     "jewellery, one knee raised and the silk and her arm placed to keep it a tasteful glamour nude, a wicked "
     "triumphant smile, unbroken eye contact as if inviting the viewer to claim his reward, scattered rose petals"),
]


def clean_style(erotic_tail):
    """The clean twin's style tail: the era and light of the NSFW tail, none of its erotic words."""
    tail = erotic_tail.split("sensual private-release erotic glamour, ", 1)[-1].lstrip(", ")
    return ("fully and modestly clothed, high neckline, no nudity, no cleavage, " + tail).rstrip(", ")


def pieces(port):
    congrats = PROMPTS[port]["mayor_congrats"]
    who = congrats.split(OLD_SETTING, 1)[0]                       # her age, face, build and who she is
    look = LOOK.search(congrats).group(1)                          # her hair and her costume
    hair, _, garb = look.partition(", a ")
    garb = ("a " + garb) if garb else look
    at = congrats.find(STYLE_AT)
    tail = congrats[at:] if at > 0 else ", romanticized cinematic historical realism, China Seas 1860, no text"
    return who, hair, garb, tail


def nsfw_prompt(port, step):
    who, hair, garb, tail = pieces(port)
    _, doing = STEPS[step]
    return "{}, {}{}{}, {}{}{}".format(who, SCENE, "her hair " + hair if step < 3 else "her " + hair, "",
                                       doing.format(garb="her " + garb), SOAP, tail)[:6000]


def clean_prompt(port):
    who, hair, garb, tail = pieces(port)
    return ("{}, {}overjoyed and tearful at the viewer's promotion, one hand pressed to her heart in soap-opera "
            "delight and the other holding the sealed commission, her {}, a dignified high-necked formal gown in the "
            "colours of her usual dress with her shoulders and chest fully covered and her gold mayor's chain of "
            "office worn over it, a radiant proud smile and direct eye contact{}, {}").format(
        who, SCENE, hair, SOAP, clean_style(tail))[:6000]


def jobs(only="", port_only=""):
    out = []
    for port in PROMPTS:
        if port_only and port != port_only:
            continue
        if only != "clean":
            for i, (name, _) in enumerate(STEPS):
                out.append((port, "step {} {}".format(i + 1, name), {
                    "kind": "port", "subject": port, "roles": ["mayor_congrats"], "prompt": nsfw_prompt(port, i),
                    "aspect": "3:4", "count": 1, "nsfw": "yes",
                    "tags": "mayor-set promotion-story soap-drama promo-step-{}".format(i + 1)}))
        if only != "nsfw":
            out.append((port, "clean", {
                "kind": "port", "subject": port, "roles": ["mayor_congrats"], "prompt": clean_prompt(port),
                "aspect": "3:4", "count": 1, "nsfw": "no", "tags": "mayor-set promotion-story soap-drama, clean"}))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", default="http://192.168.1.69:8765")
    ap.add_argument("--only", choices=["nsfw", "clean"], default="")
    ap.add_argument("--port", default="")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    server = a.server.rstrip("/")
    ok = total = 0
    for port, label, job in jobs(a.only, a.port):
        total += 1
        if a.dry:
            print("{:10} {:18} {}\n    {}\n".format(port, label, "NSFW" if job["nsfw"] == "yes" else "clean", job["prompt"]))
            ok += 1
            continue
        req = urllib.request.Request(server + "/api/admin/media/generate", data=json.dumps(job).encode("utf-8"),
                                     headers={"Content-Type": "application/json", "X-SeaTrader": "admin"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                res = json.loads(r.read().decode("utf-8"))
        except Exception as e:                      # the Pi is off, or Admin asked for a password
            res = {"ok": False, "error": str(e)}
        print("{:10} {:18} {}".format(port, label, res.get("msg") if res.get("ok") else "FAILED: " + str(res.get("error"))))
        ok += bool(res.get("ok"))
    print()
    print("{} of {} {}. Watch them in Admin > Media Library (jobs).".format(
        ok, total, "prompts printed" if a.dry else "jobs queued"))
    return 0 if ok == total and total else 1


if __name__ == "__main__":
    sys.exit(main())
