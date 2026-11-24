"""The ten Mayors (one per port), for cast.py (23 Nov 2026). Keyed "mayor_<port>".

Why they exist: every port has its own Mayor in pictures (Media Library > Ports > (port), roles "mayor",
"mayor_congrats", "mayor_<rank>"), but all ten spoke with the one voice of the cast member "mayor". Each
entry here is that port's Mayor as a VOICE: give her an Inworld voice in Admin > Voice Library and every
Mayor's line in her port is read with it (voice.Planner.mayor_voice). Until she has a voice of her own she
speaks with the shared Mayor's, so nothing changes until she is cast.

The screens still show the speaker as the Mayor ("mayor"), with that port's pictures, as before. Her looks
below follow the pictures already made for her port (tools/queue_mayor_pictures.py). All invented adult
women, all editable in Admin > Cast & Voices."""

# port: (port name, age, origin, colour, who she is in her pictures, how she speaks)
_WHO = {
    "hongkong": ("Hong Kong", 58, "Canton and Hong Kong", "#b8862b",
                 "heavyset, full-figured, deeply glamorous Cantonese matriarch with a soft double chin and shrewd eyes",
                 "slow, rich and amused, a Cantonese matriarch who has never once been hurried"),
    "shanghai": ("Shanghai", 45, "Gothenburg, Sweden", "#5f86a8",
                 "statuesque, curvaceous Swedish woman with ice-blue eyes",
                 "cool, level and precise, a Swedish lilt with frost on it"),
    "foochow": ("Foochow", 42, "Dundee, Scotland", "#4e7a52",
                "full-figured, freckled Scottish woman from the tea trade",
                "warm, quick and dry, a Scots tea-trader who drives a hard bargain with a smile"),
    "nagasaki": ("Nagasaki", 40, "Dejima, Nagasaki", "#7a4e86",
                 "striking Dutch-Japanese Eurasian woman with hazel eyes and a slim, curvy figure",
                 "soft, exact and courteous, every word placed like a stone in a garden"),
    "manila": ("Manila", 62, "Intramuros, Manila", "#a8452f",
               "heavyset, imposing Spanish-Filipina mestiza grand dame with a commanding bosom and a wicked smile",
               "grand, rolling and theatrical, a Manila grand dame holding court"),
    "saigon": ("Saigon", 50, "Marseille, France", "#8a5a7a",
               "plump, voluptuous French woman with a sensual mouth and knowing eyes",
               "low, unhurried and French, as if every sentence were a confidence"),
    "bangkok": ("Bangkok", 55, "Bangkok, Siam", "#c79a2e",
                "wiry, sharp-featured Siamese noblewoman with fine lines and steel in her eyes",
                "quiet, formal and very sure, a court lady who never repeats herself"),
    "singapore": ("Singapore", 49, "Madras and Singapore", "#9a3f2a",
                  "heavyset, voluptuous Tamil woman with dark skin, a gold nose ring and commanding eyes",
                  "deep, warm and commanding, Indian English with a laugh held just behind it"),
    "batavia": ("Batavia", 60, "Batavia, Java", "#6a7f3a",
                "plump, comfortable Indo (Dutch-Javanese) matriarch with a sly smile",
                "comfortable, sly and motherly, Dutch vowels and a long memory"),
    "calcutta": ("Calcutta", 64, "Calcutta, Bengal", "#5a4a8a",
                 "heavyset, imposing Bengali zamindar's widow with a heavy-lidded, appraising stare",
                 "slow, heavy-lidded and regal, a widow who weighs each word before she spends it"),
}


# Inworld voice per Mayor (23 Nov 2026): every Mayor speaks with a voice of her own. All are voices the cast
# already uses; none repeats the port's officer or warden. Re-cast any of them in Admin > Voice Library.
_VOICES = {"hongkong": "Jing", "shanghai": "Lore", "foochow": "Beatrice", "nagasaki": "Hina", "manila": "Rocio",
           "saigon": "Marta", "bangkok": "Asuka", "singapore": "Priya", "batavia": "Tamara", "calcutta": "Saanvi"}


def _mayor(port, name, age, origin, color, looks, delivery):
    return dict(
        name="The Mayor of {}".format(name), title="Mayor of {} & Keeper of the Harbour Watch".format(name),
        age=age, origin=origin, home_port=port, color=color,
        voice_id=_VOICES[port],
        speaking_rate=0.94, delivery=delivery,
        catchphrase="My harbour, Captain. Pay what you owe it and it will be very good to you.",
        bio="A pirate queen once, and now the lady Mayor of {}. She keeps the harbour watch, takes the "
            "harbour's dues and remembers every house that has paid them, and every house that has not.".format(name),
        quirk="Turns the chain of office once around her finger before she names a sum.",
        vice="A full strongbox, a captain who pays without being asked, and being called Your Worship.",
        secret="She still knows where her old flagship is laid up, and who would crew her.",
        stats={"cunning": 8, "nerve": 8, "charm": 8, "greed": 7},
        prompt="An {{adult}} woman (age {age}), a {looks}, a former pirate queen who is now the lady mayor of {name} "
               "in 1860, seated at a heavy teak desk in her harbour office, a fitted pirate frock coat over a "
               "high-necked blouse, the gold chain of office across her chest, looking straight into the camera "
               "with a sly, appraising half-smile, {{style}}".format(age=age, looks=looks, name=name))


MAYORS = {"mayor_" + port: _mayor(port, *row) for port, row in _WHO.items()}
