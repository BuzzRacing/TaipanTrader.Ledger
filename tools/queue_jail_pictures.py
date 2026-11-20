"""Queue the jail pictures (19 Nov 2026) on the live game (the Pi): 20 pictures, one job each.

  Media Library > Personas > (warden)   one photo of each port's warden: roles "portrait" and "speaking"
                                         (warden_<port>, prompts from jail_cast.py, the same as her cast card)
  Media Library > Ports > (port)         one jail cell for each port: role "jail_cell" (16:9, behind her on
                                         the jail screen)

Every person in every picture is a woman (the Pirate Queen sandbox). The Pi must already run the jail
update (Deploy_To_Pi.bat) or it drops the "jail_cell" role and doesn't know the wardens yet.

Run from BIGBOX (the Pi trusts its Admin requests): Queue_Jail_Pictures.bat, or
    python tools/queue_jail_pictures.py [server] [only]
      server  default http://192.168.1.69:8765 (use http://127.0.0.1:8765 for the dev server)
      only    queue just one group: wardens or cells
"""
import json
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import cast  # noqa: E402  (the wardens' own prompts, with {adult} and {style} filled in)

SERVER = (sys.argv[1] if len(sys.argv) > 1 else "http://192.168.1.69:8765").rstrip("/")
ONLY = sys.argv[2].lower() if len(sys.argv) > 2 else ""

ERA = ("romanticized cinematic historical realism, China Seas 1860, humid salt haze, weathered maritime materials, "
       "lacquer black, oxblood silk, antique brass, imperial jade")
CELL_TAIL = (", the inside of a gaol cell seen from within, empty of people, room in the left half of the frame for "
             "a figure to stand in front, " + ERA + ", moody low-key lighting, wide shot, no text, no watermark")

CELLS = {
    "hongkong": "Victoria Gaol in Hong Kong: whitewashed granite walls, a heavy iron-strapped door with a grille, a "
                "plank bunk with a grey blanket, a high barred window on the harbour with junk masts beyond, a tin "
                "cup and a Bible on a shelf, cold blue morning light",
    "shanghai": "the Mixed Court cells in Shanghai: a long stone corridor of iron-barred cages, straw on the flagstones, "
                "a gas lamp hissing, Chinese and English notices pasted on the wall, a bamboo cangue leaning in a corner",
    "nagasaki": "the Sakuramachi gaol in Nagasaki: a cell of dark wooden lattice bars on a raised tatami floor, a "
                "folded futon, a paper lantern outside the bars, a brush-written register on a low desk, quiet dusk",
    "manila": "the Bilibid in Manila: a thick-walled Spanish colonial stone cell with an arched barred window, a "
              "crucifix on the wall, a candle in an iron sconce, a rosary on a wooden stool, tropical heat haze",
    "foochow": "the yamen cells on the Min River at Foochow: a cell of thick wooden bars, straw mats, tea-chest labels "
               "pasted on the wall, a smoky oil lantern, a low clay teapot and cup by the bars, river fog at the window",
    "saigon": "the Maison Centrale in Saigon: a new French colonial cell of yellow lime-washed brick, a slatted shutter "
              "throwing bars of hot light, an iron cot, a scatter of playing cards on the floor, a rusted French padlock",
    "bangkok": "the King's prison in Bangkok: a teak-barred cell opening on a gilded courtyard, a woven mat, a lotus "
               "bud on a brass tray, temple roofs and spires beyond, warm golden river light",
    "singapore": "the Pearl's Hill lock-up in Singapore: a colonial cell of teak bars under a ceiling fan, a rattan "
                 "cot, a pith helmet on a peg outside, palms through the barred window, slatted tropical light",
    "batavia": "the vaulted brick cellars beneath the Batavia Stadhuis: a low arched cell behind an iron grille, damp "
               "walls, a printed list of rules nailed to the door, a lantern, a pail of water, green canal light",
    "calcutta": "the Presidency Jail in Calcutta: a high-ceilinged cell with a punkah fan, an iron bedstead made up "
                "with a neat blanket, an embroidery hoop left on a chair outside the bars, a barred window on a "
                "dusty courtyard, warm lamplight",
}


def jobs():
    out = []
    for cid, ch in cast.CHARACTERS.items():
        if cid.startswith("warden_"):
            out.append(("wardens", {"kind": "persona", "subject": cid, "roles": ["portrait", "speaking"],
                                    "prompt": ch["portrait_prompt"], "aspect": "3:4", "count": 1, "nsfw": "auto",
                                    "tags": "jail warden"}))
    for port, scene in CELLS.items():
        out.append(("cells", {"kind": "port", "subject": port, "roles": ["jail_cell"], "prompt": scene + CELL_TAIL,
                              "aspect": "16:9", "count": 1, "nsfw": "auto", "tags": "jail cell"}))
    return out


def main():
    ok = total = 0
    for group, job in jobs():
        if ONLY and group != ONLY:
            continue
        total += 1
        req = urllib.request.Request(SERVER + "/api/admin/media/generate", data=json.dumps(job).encode("utf-8"),
                                     headers={"Content-Type": "application/json", "X-SeaTrader": "admin"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                res = json.loads(r.read().decode("utf-8"))
        except Exception as e:                      # the Pi is off, or Admin asked for a password
            res = {"ok": False, "error": str(e)}
        print("{:8} {:20} {}".format(job["kind"], job["subject"], res.get("msg") if res.get("ok") else "FAILED: " + str(res.get("error"))))
        ok += bool(res.get("ok"))
    print()
    print("{} of {} jobs queued. Watch them in Admin > Media Library (jobs).".format(ok, total))
    return 0 if ok == total and total else 1


if __name__ == "__main__":
    sys.exit(main())
