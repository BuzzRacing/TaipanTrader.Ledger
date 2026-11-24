"""Each port's Market keeper and Ship master, for cast.py (23 Nov 2026). Keyed "keeper_<port>" and
"shipmaster_<port>".

Why they exist: every port shows its own Market keeper (Market tab) and Ship master (Fleet tab) in pictures
(Media Library > Ports > (port), roles "keeper" and "shipmaster"), but they never spoke: every trade was read
by the comprador, Lau Siu-wah, and all yard work by the shipwright, Tang Wai-lin, whose own faces took the
stage. Each entry here is that port's woman as a VOICE: give her an Inworld voice in Admin > Voice Library
and, in her port, the comprador's lines (keeper) or the shipwright's lines (ship master) are read with it,
with her own picture kept on the stage (voice.Planner.port_voice; web/deck.js, web/player.js stageFace).
Until she has a voice of her own, Lau Siu-wah and Tang Wai-lin speak as before, so nothing changes until she
is cast.

Her looks below follow the pictures already made for her port where there are any (three have no set look
yet). All invented adult women, all editable in Admin > Cast & Voices."""

_PORTS = {"hongkong": "Hong Kong", "shanghai": "Shanghai", "nagasaki": "Nagasaki", "manila": "Manila",
          "foochow": "Foochow", "saigon": "Saigon", "bangkok": "Bangkok", "singapore": "Singapore",
          "batavia": "Batavia", "calcutta": "Calcutta"}

# port: (age, colour, her looks in her pictures)
_KEEPERS = {
    "hongkong": (26, "#b06a3a", "petite, slender Hakka Chinese woman with a heart-shaped face"),
    "shanghai": (44, "#a8563f", "plump, full-figured, voluptuous Ningbo Chinese woman with a round, rosy face"),
    "nagasaki": (52, "#7f5a86", "soft, full-figured, matronly Japanese woman with laughing eyes and fine smile lines"),
    "manila": (24, "#b5753a", "petite, curvy Tagalog Filipina with warm brown skin and dimples"),
    "foochow": (28, "#5a8250", "woman of the Min River tea country"),
    "saigon": (28, "#8f6a9a", "slender, graceful Vietnamese woman with a long elegant neck"),
    "bangkok": (47, "#c2922e", "heavy, round-faced, jolly Teochew-Thai woman with a generous figure"),
    "singapore": (39, "#9a4a3a", "full-figured, soft-curved Peranakan Nyonya with a coy smile"),
    "batavia": (30, "#74863a", "slender, golden-skinned Javanese woman with almond eyes"),
    "calcutta": (35, "#64559a", "plump, curvy Bengali woman with large dark eyes"),
}
_MASTERS = {
    "hongkong": (38, "#4a6f8a", "tall, powerfully muscular Black Mozambican-Portuguese woman raised in Macau, "
                                "deep brown skin, broad strong shoulders"),
    "shanghai": (35, "#3f6a94", "tall, broad-shouldered, athletic Punjabi Sikh woman with a strong jaw and kohl-dark eyes"),
    "nagasaki": (33, "#4f5f86", "lean, wiry, hard-muscled Japanese woman with a thin scar on one cheek"),
    "manila": (41, "#3a7a80", "muscular, sun-browned Tausug Moro woman, a famed corsair, with fierce dark eyes"),
    "foochow": (32, "#3f7a6a", "weathered, capable woman of the Foochow junk yards"),
    "saigon": (36, "#4a5a90", "tall, powerfully built Senegalese woman with very dark skin and high cheekbones"),
    "bangkok": (31, "#3a8a7a", "athletic, hard-bodied Malay woman with sun-browned skin"),
    "singapore": (34, "#3f6f7f", "strong, sea-browned woman of the Singapore yards"),
    "batavia": (37, "#527a94", "big-boned, muscular, sun-reddened Dutch woman with forearms like a stevedore's"),
    "calcutta": (40, "#4a4f8a", "tall, powerful Siddi (Afro-Indian) woman with very dark skin and broad shoulders"),
}


# Inworld voice per Market keeper and Ship master (23 Nov 2026): every one speaks with a voice of her own. All are
# voices the cast already uses; none repeats her port's Mayor, officer or warden. Re-cast in Admin > Voice Library.
_VOICES = {
    "keeper": {"hongkong": "Hina", "shanghai": "Xinyi", "foochow": "Jing", "nagasaki": "Asuka", "manila": "Yoona",
               "saigon": "Xinyi", "bangkok": "Jing", "singapore": "Xinyi", "batavia": "Hina", "calcutta": "Priya"},
    "shipmaster": {"hongkong": "Olivia", "shanghai": "Priya", "foochow": "Maisie", "nagasaki": "Minji",
                   "manila": "Deborah", "saigon": "Victoria", "bangkok": "Wendy", "singapore": "Deborah",
                   "batavia": "Johanna", "calcutta": "Sarah"},
}


def _woman(port, role, age, color, looks):
    name = _PORTS[port]
    keeper = role == "keeper"
    return dict(
        name=("The Market Keeper of {}" if keeper else "The Ship Master of {}").format(name),
        title=("Market Keeper of {} & Queen of the Stalls" if keeper else "Ship Master of {} & Queen of the Slips").format(name),
        age=age, origin=name, home_port=port, color=color,
        voice_id=_VOICES[role][port],
        speaking_rate=1.02 if keeper else 1.0,
        delivery=("quick, warm and teasing, a stallholder who weighs the customer as closely as the goods" if keeper
                  else "low, blunt and sure, a yard boss who has launched more hulls than you have sailed"),
        catchphrase=("Everything on my stall has a price, Captain. Go on, ask me." if keeper
                     else "She'll take whatever you put in her, Captain. I built her that way."),
        bio=("She runs the stalls of {} and knows what every cargo fetched yesterday, and who was fool enough to "
             "pay it." if keeper else
             "She rules the slips of {}: every hull that leaves her yard is sound, and every captain who haggles "
             "with her leaves lighter.").format(name),
        quirk="Tests every coin on her teeth." if keeper else "Raps a hull twice with her knuckles before she names a price.",
        vice="A full purse and a captain in a hurry." if keeper else "Good teak, strong rum and a clean launch.",
        secret="She keeps a second set of scales." if keeper else "She has never lost a ship she built, and means to keep it so.",
        stats={"cunning": 7, "nerve": 6, "charm": 8, "greed": 7} if keeper else {"cunning": 6, "nerve": 9, "charm": 6, "greed": 6},
        prompt=("An {{adult}} woman (age {age}), a {looks}, " + (
            "who runs a trading stall in the {name} market in 1860, leaning on her counter among bales and tea chests, "
            "looking straight into the camera with a knowing, bargaining smile" if keeper else
            "the ship master who rules the {name} yards in 1860, standing on the slip before a hull on the stocks, "
            "arms folded, looking straight into the camera with a level, appraising stare") + ", {{style}}").format(
            age=age, looks=looks, name=name))


WOMEN = {}
for _port, _row in _KEEPERS.items():
    WOMEN["keeper_" + _port] = _woman(_port, "keeper", *_row)
for _port, _row in _MASTERS.items():
    WOMEN["shipmaster_" + _port] = _woman(_port, "shipmaster", *_row)
