"""Queue the late-game pictures (19 Nov 2026) on the live game (the Pi): 39 pictures in all.

  Media Library > Home Port Services
    estate_0    Great House: empty plot      2
    estate_1    Great House: Townhouse       3
    estate_2    Great House: Mansion         3
    estate_3    Great House: Palace          3
    shares      Port Shares                  3
    mayor_work  The Mayor's commissions      3
  Media Library > Ships > Flagship
    card 3 · sailing 2 · battle 2            7
  Media Library > Scenes > Sea battle: the flagship
    one for each of the ten battle moments,  15
    two for the five busiest

Service pictures are wide (16:9) because they sit behind the title of a Services card. Every person
in every picture is a woman (the Pirate Queen sandbox). Pictures can be queued before the late-game
update is deployed; they are filed under their slots and show up there once it is.

Run from BIGBOX (the Pi trusts its Admin requests): Queue_Late_Game_Pictures.bat, or
    python tools/queue_late_game_pictures.py [server] [only]
      server  default http://192.168.1.69:8765 (use http://127.0.0.1:8765 for the dev server)
      only    queue just one group: estate, shares, mayor, flagship or battle
"""
import json
import sys
import urllib.request

SERVER = (sys.argv[1] if len(sys.argv) > 1 else "http://192.168.1.69:8765").rstrip("/")
ONLY = sys.argv[2].lower() if len(sys.argv) > 2 else ""

ERA = ("romanticized cinematic historical realism, China Seas 1860, humid salt haze, weathered maritime materials, "
       "lacquer black, oxblood silk, antique brass, imperial jade")
PLACE = ", " + ERA + ", every person in the scene is a woman, no men, wide establishing shot, no text, no watermark"
PEOPLE = (", every person in the scene is a woman, no men, " + ERA + ", natural skin, private-release adult erotic "
          "glamour, nudity including exposed breasts, buttocks or genitals and period-plausible consensual kink "
          "styling permitted when it suits the character and scene, clear agency, no explicit sex act or coercion, "
          "hands visible, original faces and garment design, no text")
SHIP = ("a magnificent private flagship of a great 1860 China Seas trading house: a huge three-masted ship of the line "
        "turned merchant flagship, black-lacquered hull with an oxblood stripe and gilded gallery windows at the stern, "
        "crimson silk pennants, a carved golden figurehead of a crowned sea queen, a double row of bronze cannon ports")
SHIP_TAIL = ", " + ERA + ", her crew are all women, no men, no text, no watermark"

JOBS = [
    # ---- the great house (Services cards at home) ------------------------------------------------------
    ("estate", "service", "estate_0", ["background"], "16:9", 2,
     "an empty walled hillside plot above a treaty-port harbour at golden hour, surveyor's stakes and red silk "
     "boundary ribbons, a stone gate with a brass plaque waiting for a name, the bay full of junks and clippers "
     "below, a lady surveyor in a wide straw hat unrolling plans on a trestle table" + PLACE),
    ("estate", "service", "estate_1", ["background"], "16:9", 3,
     "an elegant two-storey colonial-Chinese townhouse of grey brick and teak, green-shuttered verandas hung with "
     "red lanterns, a small walled garden with a plum tree, a uniformed housekeeper on the steps welcoming her "
     "mistress home, the harbour glimpsed at the end of the street, warm evening light" + PLACE),
    ("estate", "service", "estate_2", ["background"], "16:9", 3,
     "a grand hillside mansion of a merchant house, white stucco colonnades and sweeping curved Chinese roofs of "
     "green glazed tile, a moon gate, terraced gardens with koi ponds and lanterns, carriages arriving for an "
     "evening reception, ladies in silk on the terrace, the whole harbour spread below at dusk" + PLACE),
    ("estate", "service", "estate_3", ["background"], "16:9", 3,
     "a breathtaking palace of a merchant princess on the peak above the harbour, tiers of golden roofs and "
     "vermilion pillars, marble stairs lined with stone lions, fountains and a hundred red lanterns, fireworks over "
     "the bay at night, a glittering party of ladies in silk and jewels on the great terrace" + PLACE),

    # ---- port shares (Services card in every port) -------------------------------------------------------
    ("shares", "service", "shares", ["background"], "16:9", 3,
     "the harbour board's share office, a panelled room of teak and brass, tall windows on the busy quay, a great "
     "slate board chalked with port names and share prices, a lady clerk in spectacles writing share certificates "
     "with red wax seals, a lady broker in silk holding up a bundle of certificates, ledgers and a brass ticker "
     "of silver dollars" + PEOPLE),

    # ---- the Mayor's commissions (Services card) -------------------------------------------------------
    ("mayor", "service", "mayor_work", ["background"], "16:9", 3,
     "a treaty-port lady mayor at her great lacquered desk in the town hall, handing a sealed commission with a red "
     "ribbon across the desk, a sea chart pinned with cargo tags and a calendar of the year beside her, an open "
     "strongbox of silver dollars, tall windows on the harbour, confident and inviting, chain of office on her "
     "silk gown" + PEOPLE),

    # ---- the flagship (Ships > Flagship) -----------------------------------------------------------------
    ("flagship", "ship", "flagship", ["card"], "3:2", 3,
     SHIP + ", moored in a treaty-port harbour at golden hour, the whole ship shown side-on, sails furled, "
           "smaller junks dwarfed around her" + SHIP_TAIL),
    ("flagship", "ship", "flagship", ["sailing"], "16:9", 2,
     SHIP + ", under full sail across open blue sea, crimson sails bellied by a strong wind, spray at the bow, "
           "seen three-quarters from the bow" + SHIP_TAIL),
    ("flagship", "ship", "flagship", ["battle"], "16:9", 2,
     SHIP + ", in battle, her whole broadside firing in sheets of flame and white gunsmoke, pirate junks reeling "
           "and splintered around her, dusk sky lit orange" + SHIP_TAIL),
]

# ---- Scenes > Sea battle: the flagship: one per moment (the busiest moments get two) ------------------------
MOMENTS = [
    ("sighting", 2, "from her quarterdeck, the lady captain lowers a brass spyglass as a line of pirate junks with "
                    "blood-red sails appears on the horizon, the gun crews running to their stations"),
    ("broadside", 2, "her whole broadside erupting in flame and white smoke, the lady gunners bent over the bronze "
                     "cannon, the pirate junks across the water taking the shot"),
    ("enemy_hit", 2, "a pirate junk breaking apart under her guns, masts falling and red sails burning, seen from "
                     "the flagship's rail"),
    ("we_are_hit", 2, "the flagship struck by pirate shot, splinters flying from her gilded rail, smoke on her deck, "
                      "her lady officers bracing and shouting orders"),
    ("ship_lost", 1, "from the flagship's stern, a smaller merchant ship of her fleet sinking in flames, the lady "
                     "captain watching grim and furious"),
    ("boarding", 1, "pirate women with cutlasses swarming over the flagship's rail from a grappled junk, her lady "
                    "crew meeting them with pistols and swords amid gunsmoke"),
    ("got_away", 1, "the flagship under full crimson sail outrunning the pirate junks into a squall at dusk, the "
                    "pirates falling far astern"),
    ("retreat", 1, "the flagship breaking off the fight, her crew heaving cargo crates over the side to lighten her, "
                   "pirate junks still firing behind"),
    ("victory", 2, "the flagship victorious at sunset amid smoking pirate wreckage, her lady crew cheering on the "
                   "yards, the house flag flying high"),
    ("defeat", 1, "the burning flagship going down last of all her fleet at night, her lady captain standing defiant "
                  "on the quarterdeck as the sea rises"),
]
for moment, n, scene in MOMENTS:
    JOBS.append(("battle", "scene", "seafight_flagship", [moment], "16:9", n,
                 SHIP + ", " + scene + SHIP_TAIL + ", dramatic cinematic sea battle"))


def main():
    ok = total = 0
    for group, kind, subject, roles, aspect, count, prompt in JOBS:
        if ONLY and group != ONLY:
            continue
        job = {"kind": kind, "subject": subject, "roles": roles, "prompt": prompt, "aspect": aspect,
               "count": count, "nsfw": "auto", "tags": "late-game " + group}
        req = urllib.request.Request(SERVER + "/api/admin/media/generate", data=json.dumps(job).encode("utf-8"),
                                     headers={"Content-Type": "application/json", "X-SeaTrader": "admin"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                res = json.loads(r.read().decode("utf-8"))
        except Exception as e:                      # the Pi is off, or Admin asked for a password
            res = {"ok": False, "error": str(e)}
        label = "{} / {} / {}".format(kind, subject, ",".join(roles))
        print("{:46} x{}  {}".format(label, count, res.get("msg") if res.get("ok") else "FAILED: " + str(res.get("error"))))
        total += count
        ok += count if res.get("ok") else 0
    print()
    print("{} of {} pictures queued. Watch them in Admin > Media Library (jobs).".format(ok, total))
    return 0 if ok == total and total else 1


if __name__ == "__main__":
    sys.exit(main())
