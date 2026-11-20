"""Queue a clean (not NSFW) photo of each port's warden on the live game (the Pi): 10 pictures, one job each.

These are the wardens' original prompts from before the nude rewrite (19 Nov 2026), dressed, with a clean
style line, filed as NOT NSFW and tagged "jail warden, clean". They go in Media Library > Personas > (her
name) with the roles "portrait" and "speaking", next to her nude photo. Family-friendly screens show
only these; other screens show the nude photo first (web/jail.js), and this one if she has no other.

The Pi must already run the jail update (Deploy_To_Pi.bat), or it doesn't know the wardens yet.
Run from BIGBOX (the Pi trusts its Admin requests): Queue_Jail_Clean_Pictures.bat, or
    python tools/queue_jail_clean_pictures.py [server]      (default http://192.168.1.69:8765)
"""
import json
import sys
import urllib.request

SERVER = (sys.argv[1] if len(sys.argv) > 1 else "http://192.168.1.69:8765").rstrip("/")
ADULT = "An unmistakably adult "
STYLE = (", fully and modestly clothed, no nudity, romanticized cinematic historical realism, China Seas 1860, "
         "humid salt haze, natural skin, weathered maritime materials, lacquer black, oxblood silk, antique brass, "
         "imperial jade, waist-up 3:4 portrait, hands visible, original face and garment design, no text")
PROMPTS = {
 "warden_hongkong": "An English woman (age 52), tall, broad-shouldered and handsome, iron-grey hair in a severe bun, the matron of Victoria Gaol in Hong Kong in 1860, standing at an iron cell door with a great ring of brass keys at her waist, a black wool gown with a crisp white collar buttoned at the throat and a leather belt cinched tight, lamplight on whitewashed stone, a dry, knowing half-smile",
 "warden_singapore": "An English woman (age 36), slim and curvy with sun-browned skin and chestnut curls pinned up loosely, the keeper of the Pearl's Hill lock-up in Singapore in 1860, leaning against barred teak doors with keys twirled on one finger, a buttoned white linen officer's tunic, a pith helmet hung on a peg, slatted tropical light, a bright teasing smile",
 "warden_manila": "An Spanish-Filipina mestiza woman (age 48), full-figured and statuesque, black hair under a black lace mantilla, the alcaide of the Bilibid prison in Manila in 1860, standing in a stone archway of the gaol with a rosary and a ring of iron keys in her hands, a black silk gown with a deep square neckline and a crimson sash, candlelight and shadow, a serene, merciless gaze",
 "warden_saigon": "An Corsican-French woman (age 41), lean and curvy with olive skin and cropped black hair, the gardienne of the Maison Centrale in Saigon in 1860, seated on a stool before a cell with a hand of playing cards fanned against the bars, a thin cigarette, a buttoned military coat, a pistol on her hip, shuttered tropical light, an amused, bored, dangerous look",
 "warden_nagasaki": "An Japanese woman (age 44), slender and composed, black hair in a tight samurai-wife's knot, the warden of the Sakuramachi gaol in Nagasaki in 1860, kneeling on a tatami platform before a wooden lattice cell with a brush and a register, a dark indigo kimono neatly tied, a ring of iron keys beside her, paper lantern glow, a perfectly calm, unreadable stare",
 "warden_foochow": "An Chinese woman (age 50), plump and handsome with silver-streaked hair pinned with jade, the keeper of the yamen cells on the Min River at Foochow in 1860, standing before a wooden-barred cell with a lantern and a cup of tea, a dark green silk jacket open at the collar over an embroidered bodice, a ring of keys on a red cord, smoky lantern light, a patient, knowing smile",
 "warden_shanghai": "An Chinese woman (age 39), tall and athletic with a sharp jaw and black hair in a long braid, the gaoler of the Mixed Court cells in Shanghai in 1860, striding down a stone corridor of iron-barred cells with a bamboo rod and a ring of keys, a fitted oxblood jacket with the high collar buttoned, riding boots, cold gaslight, a cold, commanding stare",
 "warden_bangkok": "An Thai court lady (age 46), graceful and full-figured with short court-style hair, the keeper of the King's prison in Bangkok in 1860, standing at a teak-barred cell in a gilded courtyard, a gold-threaded silk sabai over one bare shoulder, heavy gold armlets, a lotus bud in one hand and a ring of keys in the other, warm river light, a gracious, immovable smile",
 "warden_batavia": "An Dutch woman (age 45), tall and robust with pale blonde hair pinned tight under a white cap, the keeper of the cells beneath the Stadhuis of Batavia in 1860, standing in a vaulted brick cellar before an iron grille with a lantern and a printed list of rules, a black gown with a starched white collar buttoned to the throat, a heavy ring of keys at her belt, a stern, wickedly amused look",
 "warden_calcutta": "An English woman (age 49), heavyset and comfortable with rosy cheeks and auburn hair going grey in soft curls, the superintendent of the Presidency Jail in Calcutta in 1860, standing at a barred cell door with a folded blanket over one arm and a great ring of keys in her hand, a plum silk gown with a high lace neckline and a cameo brooch, punkah fan and lamplight, a sweet, motherly, quietly terrifying smile"
}


def main():
    ok = 0
    for cid, desc in PROMPTS.items():
        prompt = ADULT + desc[3:] + STYLE if desc.startswith("An ") else ADULT + desc + STYLE
        job = {"kind": "persona", "subject": cid, "roles": ["portrait", "speaking"], "prompt": prompt,
               "aspect": "3:4", "count": 1, "nsfw": "no", "tags": "jail warden, clean"}
        req = urllib.request.Request(SERVER + "/api/admin/media/generate", data=json.dumps(job).encode("utf-8"),
                                     headers={"Content-Type": "application/json", "X-SeaTrader": "admin"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                res = json.loads(r.read().decode("utf-8"))
        except Exception as e:                      # the Pi is off, or Admin asked for a password
            res = {"ok": False, "error": str(e)}
        print("{:20} {}".format(cid, res.get("msg") if res.get("ok") else "FAILED: " + str(res.get("error"))))
        ok += bool(res.get("ok"))
    print()
    print("{} of {} jobs queued. Watch them in Admin > Media Library (jobs).".format(ok, len(PROMPTS)))
    return 0 if ok == len(PROMPTS) else 1


if __name__ == "__main__":
    sys.exit(main())
