"""Queue the sea battle's right-hand seat pictures on the live game (the Pi): 22 mood pictures,
11 for Admiral Li Yue (cast key "pirate") and 11 for Madam Shek Yu-lan ("agent"):
3 speaking, 3 happy (gloating), 3 angry (cursing), 2 sly. Each is her own cast portrait prompt with the
Media Library's mood clause put in before the style tail, as the 17 Nov mood set was made.

Run from BIGBOX (the Pi trusts its Admin requests): Queue_Battle_Seat_Pictures.bat, or
    python tools/queue_battle_seat_pictures.py [server]      (default http://192.168.1.69:8765)
The pictures are made on the AI farm and filed into Media Library > Personas as they finish.
"""
import json
import sys
import urllib.request

SERVER = (sys.argv[1] if len(sys.argv) > 1 else "http://192.168.1.69:8765").rstrip("/")
BASE = {
    "pirate": "An unmistakably adult Cantonese woman (age 48), formidable Qing-era pirate queen on the stern deck of a great war junk at night, dark quilted silk robe falling open over sculpted leather armour and a daring bare décolletage, oxblood sash, elaborate pinned hair, a single white peony on the rail, lantern light from below, coldly sensual and utterly calm, romanticized cinematic historical realism, China Seas 1860, humid salt haze, natural skin, weathered maritime materials, lacquer black, oxblood silk, antique brass, imperial jade, private-release adult erotic glamour, nudity including exposed breasts, buttocks or genitals and period-plausible consensual kink styling permitted when it suits the character and scene, clear agency, no explicit sex act or coercion, knees-up 3:4 portrait, hands visible, original face and garment design, no text",
    "agent": "An unmistakably adult Macanese-Chinese woman (age 37), a pirate queen's dangerously glamorous agent, seated in a lacquered tea house on the Hong Kong waterfront, fitted oxblood Qing-era silk jacket with sheer sleeves and a deep neckline, small ivory coin balance before her, red silk protection token between two fingers, commanding pose and knowing half-smile, romanticized cinematic historical realism, China Seas 1860, humid salt haze, natural skin, weathered maritime materials, lacquer black, oxblood silk, antique brass, imperial jade, private-release adult erotic glamour, nudity including exposed breasts, buttocks or genitals and period-plausible consensual kink styling permitted when it suits the character and scene, clear agency, no explicit sex act or coercion, knees-up 3:4 portrait, hands visible, original face and garment design, no text"
}
MOODS = {
    "speaking": "caught mid-sentence, lips parted, one hand raised as she makes her point",
    "happy": "a broad, triumphant, delighted smile, eyes bright, good news written all over her face",
    "angry": "narrowed eyes, jaw set, a sharp warning gesture, plainly furious at bad news",
    "sly": "a sly conspiratorial half-smile and a knowing wink, leaning in close as if sharing a secret, one finger raised to her lips"
}
COUNTS = {"speaking": 3, "happy": 3, "angry": 3, "sly": 2}


def prompt(who, mood):
    base = BASE[who]
    at = base.find(", romanticized")
    return base[:at] + ", " + MOODS[mood] + base[at:] if at > 0 else base + ", " + MOODS[mood]


def main():
    ok = 0
    for who in ("pirate", "agent"):
        for mood, n in COUNTS.items():
            job = {"kind": "persona", "subject": who, "roles": [mood], "prompt": prompt(who, mood), "aspect": "3:4",
                   "count": n, "nsfw": "auto", "tags": "mood-set battle-seat"}
            req = urllib.request.Request(SERVER + "/api/admin/media/generate", data=json.dumps(job).encode("utf-8"),
                                         headers={"Content-Type": "application/json", "X-SeaTrader": "admin"})
            try:
                with urllib.request.urlopen(req, timeout=20) as r:
                    res = json.loads(r.read().decode("utf-8"))
            except Exception as e:                      # the Pi is off, or Admin asked for a password
                res = {"ok": False, "error": str(e)}
            print("{:7} {:9} x{}  {}".format(who, mood, n, res.get("msg") if res.get("ok") else "FAILED: " + str(res.get("error"))))
            ok += bool(res.get("ok"))
    print()
    print("{} of 8 jobs queued. Watch them in Admin > Media Library (jobs).".format(ok))
    return 0 if ok == 8 else 1


if __name__ == "__main__":
    sys.exit(main())
