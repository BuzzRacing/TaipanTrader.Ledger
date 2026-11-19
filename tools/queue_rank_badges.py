"""Queue new Crimson Ledger rank badges on the live game (the Pi): 3 per rank, 30 in all.

Each rank gets its own emblem, and they grow grander up the ladder: tarnished iron for the Debtor up to
gold, imperial jade and twin dragons for the Hong Master. All share the house style: a round medallion
filling the square, oxblood enamel, lacquer black, antique brass, imperial jade, no lettering (the rank
name is printed beside the badge by the game).

They are filed into Media Library > Rank Badges > (rank) with the "badge" role and the tag "badge-v2".
The game shows the STARRED badge for each rank, so star your favourite of the three for each rank.
Generated badges are shown cut to a circle (web/media.js), so the square's corners never show.

Run from BIGBOX (the Pi trusts its Admin requests): Queue_Rank_Badges.bat, or
    python tools/queue_rank_badges.py [server] [count]     (defaults http://192.168.1.69:8765 and 3)
    python tools/queue_rank_badges.py http://192.168.1.69:8765 1 taipan hong_master   (only these ranks)
"""
import json
import sys
import urllib.request

ARGS = sys.argv[1:]
SERVER = (ARGS[0] if ARGS else "http://192.168.1.69:8765").rstrip("/")
COUNT = int(ARGS[1]) if len(ARGS) > 1 and ARGS[1].isdigit() else 3
ONLY = set(ARGS[2:])

STYLE = ("A single ornate circular medallion badge of rank, perfectly round, centred, seen straight on, filling the "
         "whole square frame edge to edge, rendered as a luxurious hand-made jewelled object, Crimson Ledger "
         "house style: deep oxblood enamel, lacquer black, antique brass and gold, imperial jade, ivory, "
         "China Seas 1860 trading-house heraldry with Qing and Victorian maritime motifs, chased and engraved "
         "metalwork, raised relief, bevelled rims, rich specular highlights and soft warm rim light, subtle wear "
         "and patina, photoreal macro product shot, dramatic studio lighting, plain dark background behind the "
         "medallion, no text, no letters, no numerals, no words, no people, no faces, no ribbons hanging outside the circle")

RANKS = [
    ("debtor", "the lowest rank, a humble tarnished and dented iron disc, rust bloom on the rim, a broken chain link "
               "and an empty upturned coin purse in dull relief, cracked dark red enamel, sombre and poor"),
    ("clerk", "a modest plain bronze disc, a crossed quill pen and brass inkpot over an open ledger in relief, thin "
              "oxblood enamel ring, simple rope-twist border"),
    ("trader", "a bronze medallion with a polished brass rim, a small Chinese junk under one full sail over a single "
               "silver trade dollar, oxblood enamel sea, rope border"),
    ("merchant", "a silver and brass medallion, a merchant brig under sail above a balanced pair of brass scales, "
                 "oxblood enamel ground, engraved compass points around the rim"),
    ("senior_merchant", "a heavier silver and gold medallion, a brass compass rose with two crossed warehouse keys, "
                        "a band of oxblood enamel set with four small jade studs, engraved wave pattern rim"),
    ("merchant_prince", "a gilded medallion with a small jewelled coronet above a tea clipper in full sail, jade "
                        "enamel sea, oxblood enamel sky, a ring of tiny seed pearls, ornate filigree rim"),
    ("taipan", "a rich gold medallion, a coiled Chinese dragon wrapped around a closed crimson ledger book, glossy "
               "oxblood enamel field, jade eyes, a sunburst of fine gold rays, an outer ring of gold coins"),
    ("tai_pan_china_seas", "a grand gold and jade medallion, a sinuous dragon over an engraved sea chart of the China "
                           "coast, inner ring of imperial jade, small rubies at the compass points, pearl border, "
                           "radiating gold rays"),
    ("merchant_lord", "a magnificent gold medallion, a crimson enamel crown set with rubies above crossed admiralty "
                      "anchors, a laurel wreath of gold leaves around the rim, a jade cabochon at the centre, "
                      "deep oxblood and black lacquer ground"),
    ("hong_master", "the highest rank, a breathtaking heavy gold medallion, twin facing dragons clutching a flaming "
                    "pearl over a great disc of carved imperial jade, oxblood and black lacquer enamel, a halo of "
                    "gold sunburst rays, a double ring of pearls and rubies, the grandest of all"),
]


def main():
    ok = n = 0
    for rank, emblem in RANKS:
        if ONLY and rank not in ONLY:
            continue
        n += 1
        job = {"kind": "rank", "subject": rank, "roles": ["badge"], "prompt": STYLE + ", " + emblem,
               "aspect": "1:1", "count": COUNT, "nsfw": "no", "tags": "badge-v2 crimson-ledger"}
        req = urllib.request.Request(SERVER + "/api/admin/media/generate", data=json.dumps(job).encode("utf-8"),
                                     headers={"Content-Type": "application/json", "X-SeaTrader": "admin"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                res = json.loads(r.read().decode("utf-8"))
        except Exception as e:                      # the Pi is off, or Admin asked for a password
            res = {"ok": False, "error": str(e)}
        print("{:20} x{}  {}".format(rank, COUNT, res.get("msg") if res.get("ok") else "FAILED: " + str(res.get("error"))))
        ok += bool(res.get("ok"))
    print()
    print("{} of {} ranks queued. Watch them in Admin > Media Library (jobs),".format(ok, n))
    print("then star your favourite badge for each rank under Media Library > Rank Badges.")
    return 0 if ok == n else 1


if __name__ == "__main__":
    sys.exit(main())
