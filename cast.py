"""SeaTrader cast: the characters who read the game aloud.

Each character has a profile card (portrait, Inworld voice, invented history
and a few numbers for fun) and speaks the lines assigned to them under
Admin > Cast & Voices. The defaults below are only a starting point; every
field can be changed on the Admin page, and characters can be added or removed.

LINE_DEFAULTS says who reads each line of game wording (the keys in
strings.py). A line not listed falls back to PREFIX_DEFAULTS by its group:
captain's log and confirmations go to the narrator, news to the crier.
An empty speaker ("") keeps a line silent.
"""
import copy
import re

import strings

STAT_KEYS = ["cunning", "nerve", "charm", "greed"]
STAT_LABELS = {"cunning": "Cunning", "nerve": "Nerve", "charm": "Charm", "greed": "Greed"}
BRAND_LINKS = ["", "lender", "pirate", "bank"]   # name follows Brand > Characters and places
MODELS = [
    ["inworld-tts-2-flash", "TTS-2 Flash (fast, lower cost)"],
    ["inworld-tts-2", "TTS-2 (most expressive; follows each character's delivery note)"],
    ["inworld-tts-1.5-max", "TTS-1.5 Max"],
    ["inworld-tts-1.5-mini", "TTS-1.5 Mini"],
]
# Groups of wording that can be read aloud. Everything else (buttons, labels) never is.
SPOKEN_GROUPS = {"l": "Captain's log", "n": "News", "m": "Confirmations", "e": "Rule messages"}
# Pieces of other lines rather than lines of their own.
FRAGMENTS = re.compile(r"^l\.(sea|how_)")
PREFIX_DEFAULTS = {"l": "narrator", "n": "crier", "m": "narrator", "e": "narrator"}

_ADULT = "unmistakably adult"
_STYLE = ("romanticized cinematic historical realism, China Seas 1860, humid salt haze, natural skin, "
          "weathered maritime materials, lacquer black, oxblood silk, antique brass, imperial jade, "
          "private-release adult erotic glamour, nudity including exposed breasts, buttocks or genitals and "
          "period-plausible consensual kink styling permitted when it suits the character and scene, clear agency, "
          "no explicit sex act or coercion, knees-up 3:4 portrait, hands visible, original face and garment design, no text")

CHARACTERS = {
    "narrator": {
        "name": "Roxana Cama", "title": "First Mate & Queen of the Black Log", "brand_link": "",
        "age": 41, "origin": "Bombay", "home_port": "calcutta", "color": "#2f6b5a", "portrait": "",
        "voice_id": "Deborah", "speaking_rate": 1.0,
        "delivery": "low, poised and intimate, a seasoned pirate officer making every entry sound like a verdict",
        "catchphrase": "The black log remembers, Captain. Pray I write kindly of you.",
        "bio": "Daughter of a Parsi shipping dynasty, Roxana learned navigation aboard her aunt's opium clippers "
               "and double-entry bookkeeping from her mother. She has kept the black logs of three pirate queens, "
               "outlived two, and can make a captain blush or confess with the same level stare.",
        "quirk": "Winds her brass pocket chronometer whenever bad news is coming, which the crew has learned to dread.",
        "vice": "Fine Darjeeling, dangerous women, and wagers made during storms.",
        "secret": "She owns a quiet one-eighth share in a rival corsair's clipper and has never told you.",
        "stats": {"cunning": 7, "nerve": 6, "charm": 6, "greed": 3},
        "portrait_prompt": "An {adult} Parsi woman (age 41), a commanding pirate first mate on the quarterdeck of a "
                           "trading schooner in Hong Kong harbour at dusk, fitted lacquer-black frock coat open over "
                           "an ivory angrakha-cut corset, oxblood sash, black Parsi topi, black logbook under one arm "
                           "and brass chronometer in her hand, sensual calculating gaze, {style}",
    },
    "bosun": {
        "name": "Peggy “Powder” O'Rourke", "title": "Bosun, Master Gunner & Powder Queen", "brand_link": "",
        "age": 34, "origin": "Cork", "home_port": "singapore", "color": "#b3261e", "portrait": "",
        "voice_id": "Ashley", "speaking_rate": 1.08,
        "delivery": "loud, filthy-mouthed and delighted, a fearless pirate queen shouting over cannon fire and wind",
        "catchphrase": "Run out the bloody guns—and mind the fingers you still fancy keeping!",
        "bio": "Peggy shipped out of Cork, out-swore the boatswain and out-shot the gunner before breakfast. She "
               "now rules the gun deck like a powder-streaked pirate queen, equal parts battlefield terror and "
               "dockside temptation. She has sunk more rival junks than anyone on the China coast will admit.",
        "quirk": "Names every cannon after a saint and apologises to them before each broadside.",
        "vice": "Rum, cards, bare-knuckle fights and lovers with catastrophically poor judgment.",
        "secret": "She can't swim a stroke.",
        "stats": {"cunning": 5, "nerve": 10, "charm": 7, "greed": 4},
        "portrait_prompt": "An {adult} Irish woman (age 34), voluptuous pirate bosun and master gunner standing by a "
                           "smoking brass cannon, fitted tobacco-leather waistcoat over a deeply unlaced linen shirt, "
                           "oxblood sash, red hair whipping loose, powder smudges on bare arms and cleavage, coil of "
                           "slow match in one hand, fierce laughing grin, {style}",
    },
    "lender": {
        "name": "Madam Wu Lian", "title": "Moneylender & Silver Queen of Hong Kong", "brand_link": "lender",
        "age": 63, "origin": "Canton", "home_port": "hongkong", "color": "#b08a2e", "portrait": "",
        "voice_id": "Olivia", "speaking_rate": 0.92,
        "delivery": "unhurried and velvet-warm with steel underneath, every word a seduction, a courtesy and a warning",
        "catchphrase": "Madam Wu is patient, darling. Her interest is not.",
        "bio": "Wu Lian lent her first silver dollar at fourteen and has never lost one since. Half the hongs on "
               "the Praya owe her money and the other half owe her favours. Captains call her a pirate queen because "
               "she can take a fleet with one signature; she merely smiles and adjusts the interest.",
        "quirk": "Speaks of herself as Madam Wu, as if dictating the borrower's final ledger entry.",
        "vice": "Collects Song celadon, silk garters and beautiful collateral.",
        "secret": "She quietly funds the orphanage in Wan Chai and would ruin anyone who said so.",
        "stats": {"cunning": 10, "nerve": 6, "charm": 8, "greed": 9},
        "portrait_prompt": "An {adult} Cantonese woman (age 63), the silver-haired pirate queen of Hong Kong finance, "
                           "seated behind a rosewood desk in a lamplit counting house, historically grounded dark "
                           "Qing-era silk jacket with a plunging crossed neckline and imperial-jade fastenings, abacus, "
                           "silver dollars and ledgers before her, faint seductive smile and merciless eyes, {style}",
    },
    "pirate": {
        "name": "Admiral Li Yue", "title": "Pirate Queen of the South China Sea", "brand_link": "pirate",
        "age": 48, "origin": "the Pearl River delta", "home_port": "", "color": "#9a3340", "portrait": "",
        "voice_id": "Deborah", "speaking_rate": 0.9,
        "delivery": "low, slow and coldly sensual, a pirate queen who never needs to raise her voice",
        "catchphrase": "Li Yue does not chase, darling. She waits.",
        "bio": "Nobody agrees on Admiral Li Yue's face, and the few who saw it up close have learned discretion. "
               "Her war junks hold the sea lanes from Hainan to the Pescadores, and every trader on the coast pays "
               "tribute or pays in ships. She keeps her word exactly, which frightens people more than if she broke it.",
        "quirk": "Sends a single white peony before every attack.",
        "vice": "Pride. She has burned a fleet over an unreturned courtesy.",
        "secret": "She was a customs clerk once and still reads every Imperial Maritime Customs report in bed.",
        "stats": {"cunning": 9, "nerve": 9, "charm": 6, "greed": 8},
        "portrait_prompt": "An {adult} Cantonese woman (age 48), formidable Qing-era pirate queen on the stern deck "
                           "of a great war junk at night, dark quilted silk robe falling open over sculpted leather "
                           "armour and a daring bare décolletage, oxblood sash, elaborate pinned hair, a single white "
                           "peony on the rail, lantern light from below, coldly sensual and utterly calm, {style}",
    },
    "agent": {
        "name": "Madam Shek Yu-lan", "title": "The Pirate Queen's Agent on the Praya", "brand_link": "",
        "age": 37, "origin": "Macau", "home_port": "hongkong", "color": "#7a3b7d", "portrait": "",
        "voice_id": "Olivia", "speaking_rate": 1.0,
        "delivery": "silky, wickedly amused and intimate, polite as a contract and twice as binding",
        "catchphrase": "Protection is cheaper than regret—and much more pleasurable.",
        "bio": "Madam Shek runs a respectable tea house on the Praya where the tea is excellent and the receipts "
               "are written in a cipher. Captains who pay her leave with a red silk token; captains who don't "
               "leave with a story she will enjoy hearing later.",
        "quirk": "Weighs every coin on a tiny ivory balance, even from people she likes.",
        "vice": "Mahjong, played for stakes she never mentions.",
        "secret": "She keeps a second ledger, and Admiral Li Yue does not know it exists.",
        "stats": {"cunning": 9, "nerve": 7, "charm": 10, "greed": 6},
        "portrait_prompt": "An {adult} Macanese-Chinese woman (age 37), a pirate queen's dangerously glamorous agent, "
                           "seated in a lacquered tea house on the Hong Kong waterfront, fitted oxblood Qing-era silk "
                           "jacket with sheer sleeves and a deep neckline, small ivory coin balance before her, red "
                           "silk protection token between two fingers, commanding pose and knowing half-smile, {style}",
    },
    "banker": {
        "name": "Moira Haig", "title": "Chief Cashier & Queen of the Vault", "brand_link": "",
        "age": 52, "origin": "Edinburgh", "home_port": "hongkong", "color": "#2d4a8a", "portrait": "",
        "voice_id": "Sarah", "speaking_rate": 0.98,
        "delivery": "dry, precise and imperious, a seductive Scottish banker counting every word and every weakness",
        "catchphrase": "The bank thanks you for your custom. I thank you for your caution.",
        "bio": "Moira Haig came out from Edinburgh to audit the bank for six months and seized the chief cashier's "
               "chair within six weeks. She trusts iron safes, written receipts and women ruthless enough to balance "
               "their own books. Dockside captains call her the corsair of compound interest, never to her face.",
        "quirk": "Counts change twice, out loud, while holding the customer's gaze.",
        "vice": "Islay malt at six, forbidden novels at seven, and immaculate leather gloves at all hours.",
        "secret": "She writes scandalous pirate romances under a gentleman's pen name; London society devours them.",
        "stats": {"cunning": 6, "nerve": 4, "charm": 3, "greed": 5},
        "portrait_prompt": "An {adult} Scottish woman (age 52), statuesque chief cashier and financial pirate queen "
                           "behind a brass teller's grille in a Hong Kong bank, severe lacquer-black fitted frock coat "
                           "over a burgundy silk corset, steel spectacles, pinned auburn hair, leather gloves, silver "
                           "dollars and ledger, cool appraising gaze charged with restrained erotic authority, {style}",
    },
    "comprador": {
        "name": "Lau Siu-wah", "title": "Comprador & Queen of the Godowns", "brand_link": "",
        "age": 45, "origin": "Shunde", "home_port": "hongkong", "color": "#2f7d5b", "portrait": "",
        "voice_id": "Deborah", "speaking_rate": 1.04,
        "delivery": "brisk, flirtatious and razor-shrewd, a merchant pirate queen closing a deal with dry humour",
        "catchphrase": "Every price is fair, darling—if you know exactly when to sell.",
        "bio": "Widowed at thirty, Lau took over her husband's comprador house and doubled it within three "
               "years. She speaks five languages, reads seven price lists at once, and knows what silk will "
               "fetch in Shanghai before the Shanghai merchants do.",
        "quirk": "Taps her abacus beads while you talk, already working out what you'll offer.",
        "vice": "Cannot resist a bargain, a dare or a silk blouse cut scandalously well.",
        "secret": "Her 'late husband' handed her the business on purpose and lives happily in Macau as a painter.",
        "stats": {"cunning": 9, "nerve": 6, "charm": 7, "greed": 7},
        "portrait_prompt": "An {adult} Cantonese woman (age 45), voluptuous comprador and merchant pirate queen in a "
                           "busy godown of tea chests and silk bales, fitted storm-blue Qing-era jacket with jade "
                           "fastenings, neckline loosened in the humid heat, trousers, jade bangle, abacus under one "
                           "arm and writing brush in hand, confident sensual appraising look, {style}",
    },
    "shipwright": {
        "name": "Tang Wai-lin", "title": "Master Shipwright & Queen of the Keel", "brand_link": "",
        "age": 56, "origin": "Whampoa", "home_port": "hongkong", "color": "#7a4a22", "portrait": "",
        "voice_id": "Ashley", "speaking_rate": 1.0,
        "delivery": "gruff, warm and teasing, a powerful craftswoman who loves timber more than most people",
        "catchphrase": "A ship is only as good as the woman who caulks her.",
        "bio": "Tang Wai-lin has built junks, lorchas and two British clippers, and says the clippers were the easy "
               "ones. She can tell a hull's age by knocking on it and its owner's character by how it was repaired. "
               "Captains wait months for her yard and pay double when the Queen of the Keel names her price.",
        "quirk": "Talks tenderly to the ships and indecently to their owners.",
        "vice": "Boat races, strong forearms and always backing the vessel she built.",
        "secret": "She carves a small kingfisher inside the keel of every ship she builds, for luck.",
        "stats": {"cunning": 5, "nerve": 7, "charm": 4, "greed": 5},
        "portrait_prompt": "An {adult} Cantonese woman (age 56), muscular master shipwright and dockyard pirate queen "
                           "beside a half-built junk hull, linen shirt open low and sleeves rolled, fitted leather "
                           "waist cincher, adze on one shoulder, sawdust on sun-warmed skin, silver-streaked hair tied "
                           "back, weathered hands on teak, proud gruff smile, {style}",
    },
    "customs": {
        "name": "Inspector Arabella Vane", "title": "Customs Inspector & Revenue Queen", "brand_link": "",
        "age": 39, "origin": "Bath", "home_port": "shanghai", "color": "#4f5d6b", "portrait": "",
        "voice_id": "Ashley", "speaking_rate": 0.97,
        "delivery": "crisp, imperious and spectacularly foul-mouthed, reading the law like a boarding order",
        "catchphrase": "Your manifest is shite, Captain. Open the bloody hold.",
        "bio": "Arabella Vane joined the Imperial Maritime Customs because she believed rules were weapons and "
               "stayed because nobody wielded them better. She has seized more contraband than any officer on the "
               "coast; smugglers call her Shanghai's blue-coated pirate queen, though never within pistol range.",
        "quirk": "Quotes regulation numbers from memory, including the amendments, then adds profanity of her own.",
        "vice": "Immaculate uniforms, filthy language and smugglers bold enough to make inspection interesting.",
        "secret": "She lets one charming smuggler escape each New Year, then spends twelve months pretending it was clerical error.",
        "stats": {"cunning": 7, "nerve": 8, "charm": 2, "greed": 1},
        "portrait_prompt": "An {adult} English woman (age 39), fierce customs inspector and blue-coated revenue queen "
                           "on a crowded Shanghai wharf, fitted storm-blue uniform coat with brass buttons worn over "
                           "a black silk corset and daring neckline, pith helmet under one arm, manifest clipboard and "
                           "boarding pistol, crates opened behind her, stern sensual glare, {style}",
    },
    "crier": {
        "name": "Tilly Marsh", "title": "Gazette Crier & Queen of Rumours", "brand_link": "",
        "age": 29, "origin": "Liverpool", "home_port": "hongkong", "color": "#c58a1b", "portrait": "",
        "voice_id": "Sarah", "speaking_rate": 1.06,
        "delivery": "bright, shameless and theatrical, a flirtatious pirate crier scandalising a busy harbour",
        "catchphrase": "Hear ye, beauties! Fortunes made, reputations ruined—all before breakfast!",
        "bio": "Tilly sold newspapers on the Liverpool docks, stowed away on a tea clipper, and talked the "
               "Harbour Gazette into hiring her the day she landed. She hears every rumour on the waterfront "
               "first and prints the true ones, mostly.",
        "quirk": "Rings a little brass handbell before every headline, even indoors.",
        "vice": "Gossip, applause and climbing rigging in clothes wholly unsuited to the task.",
        "secret": "Half her best scoops come from Madam Shek, in exchange for the other half.",
        "stats": {"cunning": 6, "nerve": 7, "charm": 9, "greed": 4},
        "portrait_prompt": "An {adult} English woman (age 29), dazzling pirate news crier on the Hong Kong waterfront, "
                           "holding a fresh broadsheet and brass handbell, short fitted tobacco-leather jacket over an "
                           "ivory corset and dramatically split oxblood skirt, ink on her fingers, auburn hair escaping "
                           "beneath a small cocked hat, one boot on a bollard, mid-call with a wicked grin, {style}",
    },
}
for _c in CHARACTERS.values():
    _c["portrait_prompt"] = _c["portrait_prompt"].format(adult=_ADULT, style=_STYLE)

LINE_DEFAULTS = {}
for _who, _keys in {
    "narrator": ["l.arrive", "l.anchor", "l.collectors", "l.robbed", "l.sailed", "l.offcourse", "l.anchored",
                 "l.ship_lost", "l.cargo_lost", "l.wrecked", "m.sail", "m.stay", "m.unsail", "m.forced", "m.years"],
    "bosun": ["l.typhoon", "l.storm", "l.driven_off", "l.attack", "l.attack_noguns", "l.sank_all", "l.outran",
              "l.long_fight", "l.plundered", "l.damage"],
    "lender": ["m.borrowed", "m.repaid", "e.no_more_loans", "e.nothing_to_repay"],
    "pirate": ["l.lord_found"],
    "agent": ["l.protect_lapsed", "m.protected", "e.protect_content", "e.protect_cost"],
    "banker": ["m.deposited", "m.withdrew", "e.no_deposit", "e.account_empty"],
    "comprador": ["m.bought", "m.sold", "m.stored", "m.loaded", "e.no_room", "e.cost", "e.only_have",
                  "e.unknown_cargo", "e.nothing_to_store", "e.nothing_to_load", "e.home_only"],
    "shipwright": ["m.ship_joined", "m.ship_sold", "m.gun_mounted", "m.repaired", "e.unknown_ship", "e.no_shipyard",
                   "e.fleet_limit", "e.ship_cost", "e.no_such_ship", "e.last_ship", "e.unload_first",
                   "e.no_more_guns", "e.gun_cost", "e.nothing_to_repair"],
    "customs": ["l.seized", "n.ban", "n.ban_lifted", "n.caught"],
    "crier": ["n.opening", "n.start_one", "n.start_many", "n.game_over", "n.scarce", "n.glut", "n.wrecked",
              "m.begin", "m.new_game"],
}.items():
    for _k in _keys:
        LINE_DEFAULTS[_k] = _who

# Short spoken versions of lines with amounts in them. The screen still shows the
# full wording; the voice says this instead, so a line sounds the same however
# much it was for and is paid for only once. Names in {braces} come from the
# line on screen (ports, goods, ships, people) and are kept to small, fixed sets.
# A spoken version is only used while the on-screen line is the stock English
# (or stock family) wording; reword a line and it is read in full unless the
# Admin page gives it a spoken version of its own (cfg voice.say).
SAY = {
    "e.full": "This game is full.",
    "e.years": "Choose one of the game lengths shown.",
    "e.no_room": "There is not enough room in the hold.",
    "e.cost": "You cannot afford that.",
    "e.only_have": "You do not have that much {good} aboard.",
    "e.fleet_limit": "Your fleet is already as large as it can be.",
    "e.ship_cost": "You cannot afford a {ship}.",
    "e.gun_cost": "You cannot afford a gun.",
    "e.protect_content": "{pirate} is content for now.",
    "e.protect_cost": "{pirate} asks more than you can pay.",
    "m.years": "Game length set.",
    "m.bought": "Bought {good}.",
    "m.sold": "Sold {good}.",
    "m.deposited": "Silver deposited.",
    "m.withdrew": "Silver withdrawn.",
    "m.borrowed": "The loan is yours. Mind the interest.",
    "m.repaid": "Loan repaid.",
    "m.stored": "{good} stored in the warehouse.",
    "m.loaded": "{good} loaded aboard.",
    "m.ship_sold": "Sold the '{name}'.",
    "m.repaired": "Repairs done.",
    "m.protected": "Tribute paid to {pirate}. Her fleets will leave you be.",
    "l.arrive": "You arrive in {home} with one {ship}, a little silver and a debt to {lender}.",
    "l.robbed": "You were beaten and robbed in the street. Silver is safer in the bank.",
    "l.driven_off": "Pirate junks closed in, but {pirate}'s fleet drove them off.",
    "l.seized": "Customs officers searched the fleet, seized your {contraband} and fined you.",
    "l.attack": "You were attacked. Your orders were to {orders}.",
    "l.attack_noguns": "You were attacked. With no guns aboard, you could only run.",
    "l.sank_all": "You sank every one of them and took their booty.",
    "l.outran": "You outran them under fire.",
    "l.long_fight": "After a long fight you sank several of them and the rest broke off.",
    "l.plundered": "They ran you down, boarded and plundered your cargo.",
    "l.damage": "Your surviving ships took damage.",
    "l.wrecked": "Your last ship went down. A passing clipper pulled you from the sea and landed you in {home}. "
                 "Cargo and silver were lost. {lender} has advanced you a battered {ship}, adding to your debt.",
    "n.start_many": "The trading houses open for business.",
    "n.game_over": "The game is over. {name} of {firm} is {winner}.",
}
# The same, for lines whose family-friendly wording differs.
SAY_FAMILY = {
    "l.robbed": "A pickpocket made off with your silver in the market. Silver is safer in the bank.",
    "l.sank_all": "You drove them all off and won salvage.",
    "l.long_fight": "After a long chase you drove some of them off and the rest gave up.",
    "l.plundered": "They caught you and carried off cargo.",
    "l.seized": "Customs officers searched the fleet, took your {contraband} and fined you.",
}


def say_default(text, key):
    """The stock spoken version for a key, or "" when the line is read as shown."""
    tpl = text.get(key)
    if key in SAY and tpl == strings.EN.get(key):
        return SAY[key]
    if key in strings.FAMILY and tpl == strings.FAMILY[key]:
        return SAY_FAMILY.get(key, "")
    return ""


def spoken_template(cfg, text, key):
    """What the voice says for a key: the Admin's spoken version, the stock one, or the line itself."""
    say = cfg["voice"].get("say") or {}
    if key in say:
        return say[key] or text.get(key, "")
    return say_default(text, key) or text.get(key, "")


VOICE_DEFAULTS = {
    "enabled": True,
    "model_id": "inworld-tts-2-flash",
    "temperature": 1.0,
    "read_log": True,
    "read_news_board": True,
    "read_news_players": False,
    "read_confirmations": True,
    "read_errors": True,
    "custom_news": "crier",
    "lines": {},
    "say": {},    # key -> spoken version ("" = read the line exactly as shown)
}

ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,23}$")
COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
VOICE_RE = re.compile(r"^[A-Za-z0-9_.:\-/]{1,120}$")


def spoken_keys(text):
    """Wording keys that can be read aloud, in order."""
    return [k for k in text if k.split(".")[0] in SPOKEN_GROUPS and not FRAGMENTS.match(k)]


def speaker_for(cfg, key):
    """Character id for a wording key (empty = silent)."""
    lines, chars = cfg["voice"]["lines"], cfg["characters"]
    who = lines[key] if key in lines else LINE_DEFAULTS.get(key, PREFIX_DEFAULTS.get(key.split(".")[0], ""))
    if who == "" or who in chars:
        return who
    # Assigned to a character who was removed: hand the line to the group's usual reader.
    fallback = PREFIX_DEFAULTS.get(key.split(".")[0], "")
    return fallback if fallback in chars else ""


def display_name(cfg, cid):
    c = cfg["characters"].get(cid) or {}
    link = c.get("brand_link") or ""
    if link and cfg["brand"].get(link):
        return cfg["brand"][link]
    return c.get("name") or cid


def public_cast(cfg):
    """What the player screens need to show who is speaking."""
    return {cid: {"name": display_name(cfg, cid), "title": c["title"], "portrait": c["portrait"], "color": c["color"]}
            for cid, c in cfg["characters"].items()}


def _text(v, n):
    return " ".join(str(v if v is not None else "").split())[:n]


def _num(v, lo, hi, default, integer=False):
    try:
        v = float(v)
        if v != v:
            raise ValueError
    except (TypeError, ValueError):
        return default
    v = min(hi, max(lo, v))
    return int(round(v)) if integer else round(v, 3)


def clean(cfg, url_re, errors):
    """Checks and tidies cfg['characters'] and cfg['voice'] in place."""
    raw = cfg.get("characters")
    if not isinstance(raw, dict) or not raw:
        errors.append("Cast & Voices: needs at least one character")
        cfg["characters"] = copy.deepcopy(CHARACTERS)
        raw = cfg["characters"]
    ports = cfg.get("ports") or {}
    out = {}
    for cid, c in raw.items():
        if not isinstance(cid, str) or not ID_RE.match(cid):
            errors.append("Cast & Voices: key '{}' must be lower-case letters, digits or _ and start with a letter".format(cid))
            continue
        c = c if isinstance(c, dict) else {}
        base = CHARACTERS.get(cid, {})
        d = {
            "name": _text(c.get("name"), 60),
            "title": _text(c.get("title"), 80),
            "brand_link": c.get("brand_link") if c.get("brand_link") in BRAND_LINKS else "",
            "age": _num(c.get("age"), 18, 150, 30, True),
            "origin": _text(c.get("origin"), 60),
            "home_port": c.get("home_port") if c.get("home_port") in ports else "",
            "color": c.get("color").lower() if isinstance(c.get("color"), str) and COLOR_RE.match(c.get("color")) else "#75664f",
            "portrait": c.get("portrait") if isinstance(c.get("portrait"), str) and url_re.match(c.get("portrait")) else "",
            "voice_id": str(c.get("voice_id") or "").strip(),
            "speaking_rate": _num(c.get("speaking_rate"), 0.5, 1.5, 1.0),
            "delivery": _text(c.get("delivery"), 200),
            "catchphrase": _text(c.get("catchphrase"), 200),
            "bio": str(c.get("bio") or "").strip()[:1200],
            "quirk": _text(c.get("quirk"), 300),
            "vice": _text(c.get("vice"), 300),
            "secret": _text(c.get("secret"), 300),
            "stats": {},
            "portrait_prompt": str(c.get("portrait_prompt") or base.get("portrait_prompt") or "").strip()[:2000],
        }
        if not d["name"] and not d["brand_link"]:
            errors.append("Cast & Voices / {}: give the character a name".format(cid))
        if d["voice_id"] and not VOICE_RE.match(d["voice_id"]):
            errors.append("Cast & Voices / {}: the voice ID has characters Inworld does not use".format(d["name"] or cid))
        stats = c.get("stats") if isinstance(c.get("stats"), dict) else {}
        for k in STAT_KEYS:
            d["stats"][k] = _num(stats.get(k), 0, 10, 5, True)
        out[cid] = d
    if not out:
        errors.append("Cast & Voices: needs at least one character")
        out = copy.deepcopy(CHARACTERS)
    cfg["characters"] = out

    v = cfg.get("voice") if isinstance(cfg.get("voice"), dict) else {}
    nv = {}
    for k, default in VOICE_DEFAULTS.items():
        if isinstance(default, bool):
            nv[k] = bool(v.get(k, default))
    nv["model_id"] = v.get("model_id") if v.get("model_id") in [m[0] for m in MODELS] else VOICE_DEFAULTS["model_id"]
    nv["temperature"] = _num(v.get("temperature", 1.0), 0.0, 2.0, 1.0)
    nv["custom_news"] = v.get("custom_news") if v.get("custom_news") in out or v.get("custom_news") == "" else (
        "crier" if "crier" in out else "")
    lines = {}
    for key, who in (v.get("lines") or {}).items():
        if not isinstance(key, str) or key.split(".")[0] not in SPOKEN_GROUPS:
            continue
        if who == "" or who in out:
            lines[key] = who
    nv["lines"] = lines
    say = {}
    for key, txt in (v.get("say") or {}).items():
        if isinstance(key, str) and key.split(".")[0] in SPOKEN_GROUPS and isinstance(txt, str):
            say[key] = _text(txt, 400)
    nv["say"] = say
    cfg["voice"] = nv
