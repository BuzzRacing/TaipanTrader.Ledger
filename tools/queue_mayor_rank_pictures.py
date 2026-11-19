"""Queue every port's lady mayor congratulating a captain on the three ranks above Taipan (19 Nov 2026), on
the live game (the Pi): 10 ports x 3 ranks = 30 pictures, one job each, filed into Media Library > Ports >
(port) with the rank's own Mayor role, which comes first on that rank's promotion certificate:
  mayor_tai_pan_china_seas   Tai-Pan of the China Seas   crimson-and-gold audience hall, a jade seal
  mayor_merchant_lord        Merchant Lord               lantern-lit hall, midnight-blue and gold, a gold chain
  mayor_hong_master          Hong Master                 the town-hall terrace at night, cloth-of-gold, fireworks
Each prompt is that port's own congratulations prompt from queue_mayor_pictures.py (so each woman keeps her
own look), with the setting moved to the rank's grander one and the rank's certificate colours added.

Deploy_To_Pi.bat first: until the Pi runs the late-game update it doesn't know these three roles and drops
them, so the pictures would land in the port without a role.
Run from BIGBOX (the Pi trusts its Admin requests): Queue_Mayor_Rank_Pictures.bat, or
    python tools/queue_mayor_rank_pictures.py [server] [rank]
      server  default http://192.168.1.69:8765 (http://127.0.0.1:8765 for the dev server)
      rank    just one: tai_pan_china_seas, merchant_lord or hong_master
"""
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from queue_mayor_pictures import PROMPTS          # noqa: E402  (each port's mayor, as the Media Library writes her)

SERVER = (sys.argv[1] if len(sys.argv) > 1 else "http://192.168.1.69:8765").rstrip("/")
ONLY = sys.argv[2] if len(sys.argv) > 2 else ""

OLD_SETTING = ", standing in her harbour-office parlour and congratulating the viewer on a hard-won promotion: "
STYLE_AT = ", sensual private-release"

RANKS = {
    "tai_pan_china_seas": (
        ", standing in the crimson-and-gold audience hall of her town hall and proclaiming the viewer "
        "Tai-Pan of the China Seas, a rank far above any Taipan: ",
        ", crimson lacquer pillars and heavy antique gold embroidery on her robe, a carved jade seal of office "
        "resting in one open palm, the harbour beyond the tall windows crowded with the viewer's own ships at dusk"),
    "merchant_lord": (
        ", standing in a grand lantern-lit reception hall and greeting the viewer as a Merchant Lord, "
        "a lord of the China Seas trade: ",
        ", midnight-blue silk with lavish gold brocade on her gown, a heavy ceremonial gold chain draped over one "
        "outstretched hand as a gift, tall carved windows on a fleet riding at anchor under the evening stars"),
    "hong_master": (
        ", standing on the great terrace of her town hall at night with the whole harbour lit for the occasion, "
        "honouring the viewer as Hong Master, the highest rank in all the China Seas: ",
        ", black velvet and cloth-of-gold, a jewelled civic chain blazing on her bare décolletage, a gilded "
        "commission on a lacquer table, hundreds of red lanterns and golden fireworks bursting over the bay"),
}


PARLOUR_FROM, PARLOUR_TO = ", a sealed ivory letter of commission", ", her head,"


def rank_prompt(congrats, rank):
    setting, decor = RANKS[rank]
    out = congrats.replace(OLD_SETTING, setting, 1)
    # Her parlour's props (teak desk, strongbox, candle glow) don't belong in the grander settings.
    i, j = out.find(PARLOUR_FROM), out.find(PARLOUR_TO)
    if 0 < i < j:
        out = out[:i] + out[j:]
    at = out.find(STYLE_AT)
    return out[:at] + decor + out[at:] if at > 0 else out + decor


def main():
    ok = total = 0
    for rank in RANKS:
        if ONLY and rank != ONLY:
            continue
        for port, roles in PROMPTS.items():
            total += 1
            role = "mayor_" + rank
            job = {"kind": "port", "subject": port, "roles": [role], "prompt": rank_prompt(roles["mayor_congrats"], rank),
                   "aspect": "3:4", "count": 1, "nsfw": "auto", "tags": "mayor-set rank-portrait " + rank}
            req = urllib.request.Request(SERVER + "/api/admin/media/generate", data=json.dumps(job).encode("utf-8"),
                                         headers={"Content-Type": "application/json", "X-SeaTrader": "admin"})
            try:
                with urllib.request.urlopen(req, timeout=20) as r:
                    res = json.loads(r.read().decode("utf-8"))
            except Exception as e:                      # the Pi is off, or Admin asked for a password
                res = {"ok": False, "error": str(e)}
            print("{:10} {:26} {}".format(port, role, res.get("msg") if res.get("ok") else "FAILED: " + str(res.get("error"))))
            ok += bool(res.get("ok"))
    print()
    print("{} of {} jobs queued. Watch them in Admin > Media Library (jobs).".format(ok, total))
    return 0 if ok == total and total else 1


if __name__ == "__main__":
    sys.exit(main())
