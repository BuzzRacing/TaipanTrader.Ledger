"""Queue the weather-girl pictures for the Newspaper's weather glass (21 Nov 2026).

Tilly Marsh (cast key "crier", the Gazette Crier) reports the forecast from the end of a Hong Kong quay, live and
plainly at the mercy of it: wilting in a dead calm, breezy and bright in fair weather, soaked in the squalls,
hanging on to a mooring post in a typhoon. Her picture sits behind each sea's column on Port > Newspaper.

For each of the four kinds of weather this queues NSFW + clean pairs (project doc "SeaTrader Image Batches"):
    NSFW    nude, filed NSFW,         tags "weather, weather-<kind>"
    clean   dressed, filed NOT NSFW,  tags "weather, weather-<kind>, clean"
All of them are filed under Media Library > Personas > Tilly Marsh in the "weather" role. Pictures in that role
(or tagged weather) are shown behind the forecast and nowhere else, so a drenched Tilly never turns up as the
Town Crier's portrait. Four seas can show the same weather in one month, so each kind gets several poses.

Run from BIGBOX (the Pi trusts its Admin requests): Queue_Weather_Pictures.bat, or
    python tools/queue_weather_pictures.py [server] [options]        (default server http://192.168.1.69:8765)
Options:
    --nsfw N     nude poses per kind of weather, 0 to 4 (default 4)
    --clean N    clean poses per kind of weather, 0 to 4 (default 2)
    --from N     start at pose N of the four (default 1). The first batch made clean poses 1 and 2, so
                 "--only clean --from 3" adds clean poses 3 and 4 without making the first two again
    --kinds a,b  only these kinds: calm, fair, squalls, typhoon (default all four)
    --only nsfw|clean
    --dry        print the prompts, queue nothing
    --force      queue even if the server does not have the weather glass yet (not advised: see below)

DEPLOY FIRST. The "weather" role and the one-slot rule arrive with the weather glass (web/weather-glass.js). A
server without them would file these pictures with no role at all, and they would turn up everywhere Tilly does.
The tool checks the server and stops if it is not ready.
"""
import json
import sys
import urllib.request

ARGV = sys.argv[1:]
ARGS, OPT, i = [], {}, 0
while i < len(ARGV):
    a = ARGV[i]
    if a in ("--nsfw", "--clean", "--kinds", "--only", "--from") and i + 1 < len(ARGV):
        OPT[a[2:]] = ARGV[i + 1]
        i += 2
        continue
    if a.startswith("--"):
        OPT[a[2:]] = True
    else:
        ARGS.append(a)
    i += 1
SERVER = (ARGS[0] if ARGS else "http://192.168.1.69:8765").rstrip("/")
DRY, FORCE = bool(OPT.get("dry")), bool(OPT.get("force"))
WHO = "crier"
KINDS = ("calm", "fair", "squalls", "typhoon")


def _n(key, default):
    try:
        return max(0, min(4, int(OPT.get(key, default))))
    except (TypeError, ValueError):
        return default


# Who she is, the same in every picture. Framed for the column: she stands in the middle, the weather either side.
HEAD = ("An unmistakably adult English woman (age 29), Tilly Marsh, the Harbour Gazette's crier, reporting the "
        "weather from the end of a stone quay in Hong Kong harbour, auburn hair, a brass handbell on a "
        "lanyard, ink on her fingers, standing in the centre of the frame with her face in the middle of the "
        "picture, the sea and sky filling both sides")

# Each kind of weather: (the sky and sea behind her, [four poses, each plainly at the mercy of it]).
SCENES = {
    "calm": ("a dead calm, the harbour flat as glass under a white heat haze, junks with slack sails hanging "
             "limp, not a breath of wind, soft pale light",
             ["wilting in the heat, fanning herself with a limp broadsheet, a sheen of sweat on her skin, "
              "eyes half closed, a slow lazy smile",
              "slumped against a bollard with her hat pushed back, holding up one wetted finger to find a "
              "wind that is not there, a comic pout",
              "sitting on the quay's edge trailing one bare foot in the still water, the handbell silent in "
              "her lap, yawning behind her hand",
              "pressing a cold ginger-beer bottle to her neck, hair stuck to her temples, looking straight "
              "at the viewer as if the heat is their fault"]),
    "fair": ("fair weather, bright sun on a sparkling blue harbour, junks under full sail, white clouds "
             "running, a steady fresh breeze",
             ["laughing, one hand holding her cocked hat on as the breeze lifts her hair, the handbell "
              "swung high in the other",
              "arms flung wide to the wind with her face turned up to the sun, hair streaming sideways, "
              "eyes bright with delight",
              "chasing a broadsheet the breeze has snatched from her fingers, caught mid-stride and "
              "mid-laugh, glancing back at the viewer",
              "leaning back against a bollard with the breeze in her hair, pointing out to the good "
              "sailing weather, a wide wicked grin"]),
    "squalls": ("squalls, rain driving sideways in grey sheets, a dark sky torn by gusts, steep grey "
                "chop slapping the quay, lanterns swinging",
                ["soaked to the skin with her hair plastered across her face, gripping an umbrella "
                 "blown inside out, shouting the forecast into the wind",
                 "hanging on to her hat with both hands as a gust hits, shoulders hunched against the "
                 "rain, eyes screwed up, laughing at the state of herself",
                 "one arm hooked round a lamp-post, the broadsheet turned to pulp in her fist, rain "
                 "streaming off her nose, giving the viewer a look of pure outrage",
                 "braced with her boots wide apart as spray bursts over the quay behind her, wiping "
                 "wet hair from her eyes with the back of her wrist, still grinning"]),
    "typhoon": ("a typhoon at its height, a black-green sky, rain flying flat, huge seas bursting over "
                "the quay, roof tiles and torn sailcloth in the air, a junk dragging her anchors behind",
                ["clinging to a mooring post with one arm and leaning hard into the wind at a wild "
                 "angle, her hat long gone, hair whipping straight out behind her, bellowing the "
                 "warning with fierce joy",
                 "both arms wrapped round the mooring post as a wave explodes over the quay behind "
                 "her, drenched and wide-eyed, mouth open in a great shout",
                 "on one knee gripping an iron ring in the quay, the handbell torn sideways on its "
                 "lanyard, squinting into flying spray with her teeth bared in a grin",
                 "bent almost double into the wind with a rope lashed round her waist to the bollard, "
                 "one hand shielding her eyes, plainly thrilled and terrified at once"]),
}

# What she wears. The weather does the rest: the clean looks are dressed for it, the nude ones have lost the lot to it.
CLEAN_WEAR = {
    "calm": "wearing a small cocked hat, a high-collared ivory blouse with the sleeves rolled and an oxblood skirt, her tobacco-leather "
            "jacket folded over one arm",
    "fair": "wearing a small cocked hat, her short tobacco-leather jacket buttoned over a high-collared ivory blouse and an oxblood skirt "
            "that snaps in the breeze",
    "squalls": "wearing a long oilskin coat buttoned to the throat over her blouse and oxblood skirt, everything "
               "streaming wet",
    "typhoon": "wearing a long oilskin coat buttoned to the throat and a sou'wester strap under her chin, everything "
               "streaming wet and flattened by the wind",
}
NUDE_WEAR = {
    "calm": "completely nude in the heat, her clothes shed in a heap on the quay beside her, bare breasts and body "
            "shown openly, only her cocked hat and a garter left on",
    "fair": "completely nude, the breeze has carried her clothes off down the quay, bare breasts and body shown "
            "openly, only her cocked hat, a garter and the handbell left to her",
    "squalls": "completely nude and streaming wet, the squall has stripped her to her boots, bare breasts and body "
               "shown openly, rain running down her skin",
    "typhoon": "completely nude and streaming wet, the typhoon has torn every stitch off her, bare breasts and body "
               "shown openly, only her boots and the handbell's lanyard left",
}
# The style tails follow persona_prompts_v2.py (state what is wanted; nothing the renderer could take as a request).
NUDE_TAIL = (", she is the only person in the picture, romanticized 1860 China Seas glamour photograph, bold "
             "vintage-centerfold nude styling, tasteful and playful, artful composition, natural skin, dramatic "
             "weather and atmosphere, knees-up 3:4 portrait")
CLEAN_TAIL = (", she is the only person in the picture, romanticized 1860 China Seas photograph, fully dressed "
              "styling, high neckline, natural skin, dramatic weather and atmosphere, knees-up 3:4 portrait")


def fetch(path, data=None):
    req = urllib.request.Request(SERVER + path, data=json.dumps(data).encode("utf-8") if data is not None else None,
                                 headers={"Content-Type": "application/json", "X-SeaTrader": "admin"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", "replace")


def ready():
    """True when the server has the weather glass (so it knows the "weather" role and keeps these to one slot)."""
    try:
        return "WeatherGlass" in fetch("/weather-glass.js")
    except Exception:
        return False


def jobs():
    kinds = [k.strip() for k in str(OPT.get("kinds") or ",".join(KINDS)).split(",") if k.strip() in KINDS]
    only = OPT.get("only") if OPT.get("only") in ("nsfw", "clean") else ""
    try:
        start = max(1, min(4, int(OPT.get("from", 1)))) - 1
    except (TypeError, ValueError):
        start = 0
    out = []
    for kind in kinds:
        sky, poses = SCENES[kind]
        for ver, n in (("nsfw", _n("nsfw", 4)), ("clean", _n("clean", 2))):
            if only and ver != only:
                continue
            for pose in poses[start:start + n]:
                wear, tail = (NUDE_WEAR[kind], NUDE_TAIL) if ver == "nsfw" else (CLEAN_WEAR[kind], CLEAN_TAIL)
                tags = "weather, weather-" + kind + ("" if ver == "nsfw" else ", clean")
                out.append((kind, ver, {"kind": "persona", "subject": WHO, "roles": ["weather"],
                                        "prompt": ", ".join((HEAD, sky, pose, wear)) + tail, "aspect": "3:4",
                                        "count": 1, "nsfw": "yes" if ver == "nsfw" else "no", "tags": tags}))
    return out


def main():
    todo = jobs()
    if not todo:
        print("Nothing to queue with those options.")
        return 1
    if not DRY and not FORCE and not ready():
        print("The game at {} does not have the weather glass yet (or cannot be reached).".format(SERVER))
        print("Run Deploy_To_Pi.bat first, then run this again. Nothing was queued.")
        return 1
    ok = 0
    for i, (kind, ver, job) in enumerate(todo, 1):
        if DRY:
            print("\n== {:2}. {} {} [{}]\n{}".format(i, kind, ver.upper(), job["tags"], job["prompt"]))
            ok += 1
            continue
        try:
            res = json.loads(fetch("/api/admin/media/generate", job))
        except Exception as e:                      # the Pi is off, or Admin asked for a password
            res = {"ok": False, "error": str(e)}
        print("{:2}. {:8} {:5}  {}".format(i, kind, ver, res.get("msg") if res.get("ok") else "FAILED: " + str(res.get("error"))))
        ok += bool(res.get("ok"))
    print()
    print("{} of {} jobs {}.".format(ok, len(todo), "shown" if DRY else
                                     "queued. Watch them in Admin > Media Library (jobs); filter the gallery by the tag weather"))
    return 0 if ok == len(todo) else 1


if __name__ == "__main__":
    sys.exit(main())
