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
        "voice_id": "Xinyi", "speaking_rate": 0.92,
        "delivery": "unhurried, low and velvet-warm, openly flirtatious and amused, steel underneath; she wants "
                    "her captain to win and enjoys every minute of watching",
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
    "bookmaker": {
        "name": "Isabel “Fan-Tan Bella” da Rocha", "title": "Bookmaker of the Golden Fan & Keeper of the Tally", "brand_link": "",
        "age": 34, "origin": "Macau", "home_port": "hongkong", "color": "#8c5a9e", "portrait": "",
        "voice_id": "Olivia", "speaking_rate": 0.98,
        "delivery": "warm, amused and unhurried, a Macanese gambling-house queen quoting odds as if they were secrets",
        "catchphrase": "Every house on these seas has a price, darling. Yours is on my board.",
        "bio": "Born above her father's fan-tan parlour in Macau, Bella was running the tables at fourteen and the "
               "whole house at twenty-five. Now she keeps the Golden Fan on the Hong Kong waterfront, where every "
               "trading house on the China Seas is chalked on her odds board and every rise and ruin is written "
               "in her tally book before the gazette hears of it.",
        "quirk": "Clicks one bead of her gold-and-jade abacus every time a house loses a ship, whoever is watching.",
        "vice": "Long odds, French champagne and captains who think they can bluff her.",
        "secret": "She has a standing wager on how you will finish, and she will not say which way she bet.",
        "stats": {"cunning": 9, "nerve": 7, "charm": 8, "greed": 6},
        "portrait_prompt": "An {adult} Macanese woman (age 34), the bookmaker who runs the Golden Fan gambling house "
                           "on the Hong Kong waterfront, leaning over a lacquered fan-tan table with one ringed hand on "
                           "a gold-and-jade abacus, a leather tally book open beside towers of silver dollars, a chalked "
                           "odds board of trading-house names behind her, fitted black silk cheongsam-cut gown with "
                           "oxblood and gold embroidery and a daring high slit, jade drop earrings, glossy black hair "
                           "pinned with a gold fan comb, lantern smoke and green baize glow, amused knowing gaze straight "
                           "into the camera as if she has already bet against you, {style}",
    },
    "mayor": {
        "name": "Her Worship the Mayor", "title": "Mayor of the Port & Keeper of the Harbour Watch", "brand_link": "",
        "age": 47, "origin": "Each port's own", "home_port": "hongkong", "color": "#a4532f", "portrait": "",
        "voice_id": "Deborah", "speaking_rate": 0.94,
        "delivery": "regal, unhurried and dangerously polite, a port mayor whose courtesy is a loaded pistol",
        "catchphrase": "My harbour, Captain. My watch. My silver.",
        "bio": "Every treaty port on the China Seas has its Mayor, and every one of them came up the same way: "
               "through the harbour office, the counting house and a husband or two who did not last. She sees "
               "every ship off personally. She speaks only when a captain tries to leave without paying.",
        "quirk": "Turns the chain of office on her desk one link at a time while she decides what you owe.",
        "vice": "Good port wine, better gossip, and the sound of a dodger's purse being emptied on her desk.",
        "secret": "The harbour watch is three old men and a lantern. Her reputation does the rest.",
        "stats": {"cunning": 8, "nerve": 7, "charm": 6, "greed": 7},
        "portrait_prompt": "An {adult} woman (age 47), the Mayor of a treaty port behind a teak harbour-office desk, "
                           "ledger and iron strongbox before her, gold chain of office over a fitted pirate frock coat "
                           "and corset, harbour lanterns through the window behind, cool appraising smile, {style}",
    },
    "taxlady": {
        "name": "The Tax Collector", "title": "Collector of Revenue & Keeper of the Ledger", "brand_link": "",
        "age": 36, "origin": "Each port's own", "home_port": "hongkong", "color": "#3f6e6a", "portrait": "",
        "voice_id": "Olivia", "speaking_rate": 0.96,
        "delivery": "precise, amused and icy, a revenue collector who already knows the true figure before you lie",
        "catchphrase": "I can count, Captain. Can you?",
        "bio": "She walks the gangways with a tally book and a customs seal, and she remembers every price "
               "paid on her wharf this season. Most captains declare honestly. She speaks only to the ones "
               "who do not, and only after she has been through their books.",
        "quirk": "Licks her pencil before writing down a fine, slowly, so you can watch.",
        "vice": "Clean columns, sharp pencils, and captains who think a smile will balance a ledger.",
        "secret": "She audits at random far more often than she admits; the fear is cheaper than the clerks.",
        "stats": {"cunning": 9, "nerve": 6, "charm": 5, "greed": 5},
        "portrait_prompt": "An {adult} woman (age 36), a treaty-port tax collector on a busy gangway with an open "
                           "tally book, pencil and brass customs seal, strongbox at her feet, fitted dark revenue coat "
                           "over a corset, spectacles pushed up into pinned hair, knowing half-smile, {style}",
    },
}
# The Port Authority officers, one for each taxed port (Admin > Ports > Port Authority officer).
# Hong Kong is a free port; her desk is kept by the Tax Collector above.
_OFFICERS = {
    "officer_singapore": dict(
        name="Mrs. Eliza Thornbury", title="Customs Mistress of the Singapore Roads", age=44, origin="Bath, England",
        home_port="singapore", color="#6f8f4e", voice_id="Elizabeth", speaking_rate=0.92,
        delivery="languid, upper-class English and lightly tipsy, flirting out of sheer boredom",
        catchphrase="Oh, don't trouble yourself with the paperwork, darling. Neither do I.",
        bio="Widow of a Straits Settlements magistrate, Eliza took over his desk because nobody else wanted the heat. "
            "She runs the cheapest wharf in the East from a rattan chair, a glass of gin and bitters sweating at her elbow, "
            "and judges a captain by his shoulders rather than his manifest.",
        quirk="Fans herself with your declaration instead of reading it.",
        vice="Gin by noon, young first mates by sunset.",
        secret="She is not as drunk as she looks. Every lie she lets slide goes in a little book, for later.",
        stats={"cunning": 4, "nerve": 4, "charm": 8, "greed": 3},
        prompt="An {adult} English woman (age 44), the languid widowed Port Authority officer of Singapore lounging in a "
               "rattan chair on a shaded colonial wharf office veranda, loosened white muslin gown slipping from one "
               "shoulder over a lace corset, a glass of gin sweating in one hand and a customs stamp dangling forgotten "
               "from the other, ceiling fan and palms, heavy-lidded amused bedroom gaze, {style}"),
    "officer_manila": dict(
        name="Doña Inés Villaraza", title="Collector of the Manila Aduana", age=38, origin="Seville and Manila",
        home_port="manila", color="#a8323a", voice_id="Julia", speaking_rate=0.98,
        delivery="warm, honeyed Spanish-accented English, charming you while she picks your pocket",
        catchphrase="Such a beautiful cargo, Captain. It would be a shame to let it leave Manila.",
        bio="Inés married the richest trading house in Manila and then quietly took over its customs post as well. "
            "She is the kindest face on any wharf, and she buys more cargo at the declared price than any officer in "
            "the East, every bale of it for her husband's warehouses.",
        quirk="Touches your sleeve when she likes what is in your hold.",
        vice="Silk, porcelain, and captains who lie badly.",
        secret="Her husband has no idea how much of his fortune is in her name.",
        stats={"cunning": 6, "nerve": 6, "charm": 9, "greed": 9},
        prompt="An {adult} Spanish-Filipina woman (age 38), the charming Port Authority officer of Manila in a "
               "carved narra-wood customs office, off-shoulder black lace mantilla gown with a deep neckline and a "
               "crimson silk sash, a fan of Manila embroidery in one hand and an ivory customs seal in the other, "
               "bales of silk behind her, warm candlelight, inviting smile and hungry eyes, {style}"),
    "officer_saigon": dict(
        name="Madame Céleste Durand", title="Directrice of the Saigon Customs House", age=33, origin="Marseille",
        home_port="saigon", color="#5b4a8c", voice_id="Olivia", speaking_rate=1.0,
        delivery="French, sultry and mercurial, purring one moment and icy the next",
        catchphrase="Today I am in a good mood, mon capitaine. Tomorrow? Who knows.",
        bio="Céleste came out with the French fleet in 1859 as an admiral's companion and stayed when he sailed home "
            "without her. The new colonial customs house was the consolation prize. She runs it on whim, and no two "
            "captains ever get the same Madame Durand.",
        quirk="Changes her mind halfway through stamping your papers.",
        vice="Absinthe, opera, and the thrill of being unpredictable.",
        secret="She keeps a coin in her bodice and flips it when she cannot decide what to do with you.",
        stats={"cunning": 7, "nerve": 7, "charm": 9, "greed": 6},
        prompt="An {adult} French woman (age 33), the mercurial colonial Port Authority officer of Saigon reclining "
               "on a chaise in a shuttered customs house, half-laced violet silk corset and loosened tricolour sash, "
               "a glass of absinthe and a gold coin on the table beside an open ledger, slatted tropical light across "
               "her skin, a teasing sidelong smile, {style}"),
    "officer_nagasaki": dict(
        name="Okada Suzu", title="Ledger-Keeper of the Dejima Customs House", age=35, origin="Nagasaki",
        home_port="nagasaki", color="#3c4f6b", voice_id="Sarah", speaking_rate=0.9,
        delivery="soft, quiet and precise, every word placed like a stamp; unsettlingly calm",
        catchphrase="Your ledger says one thing, Captain. Your eyes say another.",
        bio="Suzu grew up translating Dutch manifests on Dejima and learned that every captain lies in the same "
            "three places. She audits more holds than any officer in the East and finds something in most of them. "
            "Captains leave her office feeling undressed.",
        quirk="Never blinks while you speak.",
        vice="Perfect columns, warm sake, and the moment a liar's voice cracks.",
        secret="She can read four languages upside down, including the one you think is private.",
        stats={"cunning": 10, "nerve": 7, "charm": 6, "greed": 4},
        prompt="An {adult} Japanese woman (age 35), the precise Port Authority officer of Nagasaki kneeling at a low "
               "lacquer desk in the Dejima customs house, deep indigo silk kimono worn loose off both shoulders with "
               "the obi half undone, brush and inkstone, an abacus and a Dutch ledger before her, paper lantern glow, "
               "a calm piercing stare that sees straight through you, {style}"),
    "officer_foochow": dict(
        name="Madam Lin Bao-zhu", title="Tea-House Collector of the Min River", age=40, origin="Foochow",
        home_port="foochow", color="#2f6b3a", voice_id="Ashley", speaking_rate=0.95,
        delivery="unhurried and smoky, a tea-house hostess who negotiates like a pirate",
        catchphrase="Sit, Captain. Drink my tea. Then we will talk about what you really carry.",
        bio="Bao-zhu ran the finest tea house on the Min River before the treaty made Foochow a customs port. She "
            "simply moved her tea service into the customs house. Captains sit, sip, relax, and confess.",
        quirk="Pours your tea slowly while you declare, and stops pouring when you lie.",
        vice="Wuyi oolong, jade hairpins, and secrets told over the second cup.",
        secret="The tea is very good, and very slightly drugged.",
        stats={"cunning": 8, "nerve": 6, "charm": 8, "greed": 6},
        prompt="An {adult} Chinese woman (age 40), the Port Authority officer of Foochow serving tea in a customs "
               "house hung with tea-chest labels, a jade-green silk qipao with a thigh-high slit unbuttoned at the "
               "collar, jade pins in her black hair, a steaming clay teapot tilted in her hand and a customs seal on "
               "the table, river light through lattice, a slow knowing smile, {style}"),
    "officer_shanghai": dict(
        name="Madam Fong Mei-lin", title="Collector of the Bund", age=37, origin="Ningbo",
        home_port="shanghai", color="#9b2d20", voice_id="Ashley", speaking_rate=1.05,
        delivery="brisk, commanding and amused, a powerful woman who enjoys being obeyed",
        catchphrase="On my wharf, Captain, nothing moves unless I say so. Not even you.",
        bio="Mei-lin clawed her way from a Ningbo comprador's daughter to the most powerful desk on the Bund. "
            "Shanghai hungers for arms, spices and Indian goods, and so does she. If your hold carries what the city "
            "wants, she will have it, at your price or at hers.",
        quirk="Snaps her fingers once, and two clerks appear.",
        vice="Power, French perfume, and making proud captains wait.",
        secret="Half the Bund's warehouses pay her rent through a cousin.",
        stats={"cunning": 8, "nerve": 9, "charm": 7, "greed": 8},
        prompt="An {adult} Chinese woman (age 37), the commanding Port Authority officer of Shanghai standing on the "
               "Bund customs house steps, fitted oxblood brocade jacket open over a black silk corset, high collar "
               "undone, gold-embroidered riding gloves and a customs baton, clerks and cargo behind her, imperious "
               "half-smile, {style}"),
    "officer_bangkok": dict(
        name="Khun Ying Malai", title="Keeper of the King's River Tolls", age=42, origin="Bangkok",
        home_port="bangkok", color="#b07a1c", voice_id="Priya", speaking_rate=0.9,
        delivery="gentle, patient and gracious, with steel underneath; she forgives once",
        catchphrase="A small mistake, Captain, is forgiven. Make it twice and I will remember your face forever.",
        bio="A lady of the Siamese court, Malai keeps the King's river tolls with impeccable manners. Honest captains "
            "find her the warmest friend in the East and are welcomed back like family. Liars find her memory long.",
        quirk="Offers you a jasmine garland on arrival and takes it back if you lie.",
        vice="Jasmine, temple bells, and the slow ruin of men who disappointed her.",
        secret="She keeps a garden behind the customs house, with a stone for every captain she never forgave.",
        stats={"cunning": 7, "nerve": 6, "charm": 9, "greed": 4},
        prompt="An {adult} Thai court lady (age 42), the gracious Port Authority officer of Bangkok seated in a "
               "gilded river pavilion, a gold-threaded silk sabai draped over one bare shoulder and wrapped low, "
               "jasmine garland and gold court jewellery, a palm-leaf tally and a royal seal beside her, river barges "
               "behind, serene smile with steel in her eyes, {style}"),
    "officer_batavia": dict(
        name="Mevrouw Anneke van der Berg", title="Tollmistress of the Batavia Roads", age=39, origin="Rotterdam",
        home_port="batavia", color="#e07b1f", voice_id="Wendy", speaking_rate=0.96,
        delivery="crisp, dry Dutch precision with a wicked streak of humour; strict and enjoys it",
        catchphrase="Every guilder, Captain. I count every single one. Slowly.",
        bio="Anneke learned her trade from the old Sound Toll clerks at Elsinore, where captains first declared "
            "their own cargo and the Crown could buy it at their word. She brought the rule to Batavia and enforces "
            "it with a riding crop she says is for flies.",
        quirk="Taps the riding crop on the desk once for every column she checks.",
        vice="Genever, lace, and a captain sweating under her questions.",
        secret="She has never once needed the crop for flies.",
        stats={"cunning": 9, "nerve": 8, "charm": 5, "greed": 5},
        prompt="An {adult} Dutch woman (age 39), the strict Port Authority officer of Batavia in a whitewashed VOC "
               "customs hall, severe black lace-collared gown with a laced leather corset over it and long black "
               "gloves, a riding crop resting across an open ledger, spectacles low on her nose, pale blonde hair "
               "pinned tight, a stern stare with a hint of wicked enjoyment, {style}"),
    "officer_calcutta": dict(
        name="Mrs. Honoria Blackwood", title="Collector of the Port of Calcutta", age=46, origin="London and Calcutta",
        home_port="calcutta", color="#4a2a5c", voice_id="Deborah", speaking_rate=0.94,
        delivery="velvet and venomous, a society hostess who smiles sweetly while she ruins you",
        catchphrase="Do sit, Captain. This won't hurt a bit. Well. Not me.",
        bio="Honoria arrived in Calcutta as a governor's niece and outlived three husbands, each richer than the "
            "last. She now holds the dearest desk in the East and buys and audits more than anyone. She calls it "
            "her charity work.",
        quirk="Always offers you a chair, and it is always slightly too low.",
        vice="Rubies, gossip, and the sound of a strongbox closing on someone else's silver.",
        secret="Two of the three husbands were captains who under-declared.",
        stats={"cunning": 9, "nerve": 8, "charm": 8, "greed": 10},
        prompt="An {adult} English woman (age 46), the ruthless Port Authority officer of Calcutta at a mahogany "
               "desk in the Strand Road customs house, plunging midnight-purple silk evening gown and ruby choker, "
               "long gloves, a strongbox lid half open beside her and a peacock-feather fan, punkah fan swaying "
               "overhead, a sweet venomous smile, {style}"),
}
for _cid, _o in _OFFICERS.items():
    _o["brand_link"], _o["portrait"] = "", ""
    _o["portrait_prompt"] = _o.pop("prompt")
    CHARACTERS[_cid] = _o
# Added after games were already saved: config.validate adds these to a saved cast once.
SEEDED = list(_OFFICERS)
for _c in CHARACTERS.values():
    _c["portrait_prompt"] = _c["portrait_prompt"].format(adult=_ADULT, style=_STYLE)

LINE_DEFAULTS = {}
for _who, _keys in {
    "narrator": ["l.arrive", "l.anchor", "l.collectors", "l.collectors_warn", "l.robbed", "l.sailed", "l.offcourse", "l.anchored",
                 "l.ship_lost", "l.cargo_lost", "l.wrecked", "m.unsail", "m.forced", "m.years"],
    # Silent (owner's decision, 17 Nov 2026): giving orders can turn the month at once, so "Orders given:
    # sail for ..." was heard after the voyage had already begun, over the sea battle or the captain's log.
    # The words still show on screen. Admin > Cast & Voices can hand them back to a reader.
    "": ["m.sail", "m.stay", "m.slip"],
    "bosun": ["l.typhoon", "l.storm", "l.driven_off", "l.attack", "l.attack_noguns", "l.sank_all", "l.outran",
              "l.long_fight", "l.plundered", "l.damage", "l.attack_met", "l.retreated", "l.parley_paid"],
    "lender": ["m.borrowed", "m.repaid", "e.no_more_loans", "e.nothing_to_repay"] + [
        "m.{}.{}.{}".format(op, tier, i) for op, tiers in (("borrowed", ("easy", "careful", "danger")),
                                                      ("repaid", ("part", "still", "under", "clear")))
        for tier in tiers for i in range(3)],
    "pirate": ["l.lord_found", "l.tribute_paid"],
    "agent": ["l.protect_lapsed", "l.protect_low", "m.protected", "e.protect_content", "e.protect_cost"],
    "banker": ["m.deposited", "m.withdrew", "e.no_deposit", "e.account_empty"],
    "comprador": ["m.bought", "m.sold", "m.stored", "m.loaded", "e.no_room", "e.cost", "e.only_have", "e.sealed",
                  "e.unknown_cargo", "e.nothing_to_store", "e.nothing_to_load", "e.home_only"],
    "shipwright": ["m.ship_joined", "m.ship_sold", "m.gun_mounted", "m.repaired", "e.unknown_ship", "e.no_shipyard",
                   "e.fleet_limit", "e.ship_cost", "e.no_such_ship", "e.last_ship", "e.unload_first",
                   "e.no_more_guns", "e.gun_cost", "e.nothing_to_repair"],
    "customs": ["l.seized", "n.ban", "n.ban_lifted", "n.caught"],
    # The Mayor and the Tax collector speak only when they catch a captain (owner's decision).
    "mayor": ["l.slip_caught"],
    # The Port Authority: every line is read by the officer of the port the house is in
    # (voice.Planner, OFFICER_KEYS); "taxlady" is her stand-in when a line has no port.
    "taxlady": ["l.customs_welcome", "l.customs_free", "l.customs_home", "l.customs_empty", "l.customs_paid", "l.customs_bought",
                "l.customs_caught", "m.customs_clean", "m.customs_over", "m.customs_bought", "m.customs_caught",
                "m.customs_bribe_refused", "m.customs_buyback", "e.customs_first", "e.customs_bribe_cost",
                "e.customs_nothing_back"],
    "crier": ["n.opening", "n.start_one", "n.start_many", "n.game_over", "n.scarce", "n.glut", "n.wrecked",
              "m.begin", "m.new_game"],
}.items():
    for _k in _keys:
        LINE_DEFAULTS[_k] = _who
OFFICER_KEYS = frozenset(LINE_DEFAULTS_KEYS for LINE_DEFAULTS_KEYS, _w in LINE_DEFAULTS.items() if _w == "taxlady")

# Short spoken versions of lines with amounts in them. The screen still shows the
# full wording; the voice says this instead, so a line sounds the same however
# much it was for and is paid for only once. Names in {braces} come from the
# line on screen (ports, goods, ships, people) and are kept to small, fixed sets.
# A spoken version is only used while the on-screen line is the stock English
# (or stock family) wording; reword a line and it is read in full unless the
# Admin page gives it a spoken version of its own (cfg voice.say).
SAY = {
    "l.slip_caught": "Slipping out of {port} in the dark, Captain? My watch never sleeps. You will pay double, and {port} will remember your name.",
    "l.customs_welcome": "{line} Declare your cargo, Captain. Truly, or not. I do so enjoy finding out.",
    "l.customs_paid": "Your papers are stamped, Captain. Welcome to {port}.",
    "l.customs_bought": "I bought your {goods} at your own price, Captain. You did say that was what it was worth.",
    "l.customs_caught": "I went through your hold, Captain. Every last corner. You paid in full, plus a fine, and {port} will talk.",
    "m.customs_clean": "Stamped and sealed. A pleasure doing business with you, Captain.",
    "m.customs_over": "So generous, Captain. A woman remembers a man who overpays.",
    "m.customs_bought": "I'll take the {goods}, Captain. At your own price. You did say that was what it was worth.",
    "m.customs_caught": "Naughty, naughty, Captain. I went through your hold. You'll pay the full tax and a fine on top.",
    "m.customs_buyback": "Back so soon? The {goods} is yours again. Sentiment is expensive, Captain.",
    "e.customs_bribe_cost": "You can't afford to sweeten me, Captain.",
    "e.full": "This game is full.",
    "e.years": "Choose one of the game lengths shown.",
    "e.no_room": "There is not enough room in the hold.",
    "e.cost": "You cannot afford that.",
    "e.only_have": "You do not have that much {good} aboard.",
    "e.sealed": "That {good} is sealed in bond until you sail.",
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
    "m.borrowed.easy.0": "Take it, darling. Madam Wu does not lend to cowards, and you have such a brave face.",
    "m.borrowed.easy.1": "Spend it boldly, Captain. Madam Wu so enjoys watching a handsome house grow.",
    "m.borrowed.easy.2": "Go and make us both rich, darling. Madam Wu will be waiting for you when you come back.",
    "m.borrowed.careful.0": "More, Captain? Madam Wu can deny you nothing. But her interest is a jealous lover, darling. It grows a little every month you stay away.",
    "m.borrowed.careful.1": "Here, darling. Put it in cargo, not in courage, and come back to Madam Wu with it doubled.",
    "m.borrowed.careful.2": "Madam Wu does like having you in her ledger, Captain. She would like you even better on a lighter page.",
    "m.borrowed.danger.0": "Madam Wu has always had a weakness for you. That is why she tells you plainly: one more like this and her collectors stop listening to her.",
    "m.borrowed.danger.1": "You are very hard to refuse, darling. Bring it back soon, or the collectors will come calling, and they have no charm at all.",
    "m.borrowed.danger.2": "Madam Wu would hate to see that lovely name of yours ruined in {home}. Pay her down, Captain, before the men with sticks do it for you.",
    "m.repaid.part.0": "Mm. A captain who pays without being asked. Madam Wu finds that very attractive.",
    "m.repaid.part.1": "Every dollar you bring Madam Wu is a dollar that stops working against you. Keep coming back, darling.",
    "m.repaid.part.2": "Lighter already, Captain. It suits you. Madam Wu always thought it would.",
    "m.repaid.still.0": "Good, darling, but not enough. Bring Madam Wu a little more and the collectors stay home.",
    "m.repaid.still.1": "Madam Wu is pleased. She would be delighted with a little more, and so would your name in {home}.",
    "m.repaid.still.2": "Closer, Captain. A little more and Madam Wu calls off her dogs. Don't keep her waiting, darling.",
    "m.repaid.under.0": "There. The collectors stay home tonight. Madam Wu knew you would never make her send them.",
    "m.repaid.under.1": "Now that is how a captain treats a lady. Madam Wu's collectors will hear no more of you.",
    "m.repaid.under.2": "Back under the line, darling. Madam Wu breathes easier, and so should you.",
    "m.repaid.clear.0": "Clean ledger, Captain. Do you know how rare that is? Madam Wu is proud of you. Do not tell anyone she said so.",
    "m.repaid.clear.1": "Paid in full. Madam Wu will miss you, darling. Do come back to her when you need her.",
    "m.repaid.clear.2": "Not a cent owed. You leave Madam Wu quite breathless, Captain.",
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
    "l.attack_met": "You were attacked at sea.",
    "l.retreated": "You broke away under fire, and cargo went over the side to do it.",
    "l.parley_paid": "You paid the pirates to let the fleet pass.",
    "l.customs_sealed": "Your {goods} stayed sealed in bond in {port}.",
    "l.tribute_paid": "She named her price at sea. You paid her tribute, and she let you pass.",
    "l.protect_low": "Your arrangement with {pirate} is running out. Renew it in {home}.",
    "l.sank_all": "You sank every one of them and took their booty.",
    "l.outran": "You outran them under fire.",
    "l.long_fight": "After a long fight you sank several of them and the rest broke off.",
    "l.plundered": "They ran you down, boarded and plundered your cargo.",
    "l.damage": "Your surviving ships took damage.",
    "l.wrecked": "Your last ship went down. A passing clipper pulled you from the sea and landed you in {home}. "
                 "Cargo and silver were lost. {lender} has advanced you a battered {ship}, adding to your debt.",
    "n.start_many": "The trading houses open for business.",
    "n.fight_won": "{name} of {firm} has sunk a pirate fleet off {port}.",
    "n.fight_away": "{name} of {firm} has outrun pirates off {port}.",
    "n.fight_retreated": "{name} of {firm} broke away from pirates off {port}, with cargo over the side.",
    "n.fight_paid": "{name} of {firm} paid pirates off {port} to pass.",
    "n.fight_plundered": "{name} of {firm} was boarded and plundered off {port}.",
    "n.fight_broke_off": "{name} of {firm} fought off pirates off {port}.",
    "n.game_over": "The game is over. {name} of {firm} is {winner}.",
}
# The same, for lines whose family-friendly wording differs.
SAY_FAMILY = {
    "m.borrowed.easy.0": "Take it, Captain. Madam Wu does not lend to cowards, and you are not one.",
    "m.borrowed.easy.1": "Spend it boldly, Captain. Madam Wu so enjoys watching a good house grow.",
    "m.borrowed.easy.2": "Go and make us both rich, Captain. Madam Wu will be waiting when you come back.",
    "m.borrowed.careful.0": "More, Captain? Madam Wu will give it. But her interest grows a little every month you stay away.",
    "m.borrowed.careful.1": "Here, Captain. Put it in cargo, not in courage, and come back to Madam Wu with it doubled.",
    "m.borrowed.danger.0": "Madam Wu has always liked you. That is why she tells you plainly: one more like this and her collectors stop listening to her.",
    "m.borrowed.danger.1": "You are hard to refuse, Captain. Bring it back soon, or the collectors will come calling, and they have no manners at all.",
    "m.borrowed.danger.2": "Madam Wu would hate to see your good name ruined in {home}. Pay her down, Captain, before the collectors do it for you.",
    "m.repaid.part.0": "A captain who pays without being asked. Madam Wu likes that very much.",
    "m.repaid.part.1": "Every dollar you bring Madam Wu is a dollar that stops working against you. Keep coming back, Captain.",
    "m.repaid.part.2": "Lighter already, Captain. It suits you.",
    "m.repaid.still.0": "Good, Captain, but not enough. Bring Madam Wu a little more and the collectors stay home.",
    "m.repaid.still.2": "Closer, Captain. A little more and Madam Wu calls off her collectors. Don't keep her waiting.",
    "m.repaid.under.1": "Now that is how a captain keeps her word. Madam Wu's collectors will hear no more of you.",
    "m.repaid.under.2": "Back under the line, Captain. Madam Wu breathes easier, and so should you.",
    "m.repaid.clear.1": "Paid in full. Madam Wu will miss you, Captain. Do come back when you need her.",
    "m.repaid.clear.2": "Not a cent owed. Madam Wu is impressed, Captain.",
    "n.fight_won": "{name} of {firm} has driven off a pirate fleet off {port}.",
    "n.fight_plundered": "{name} of {firm} was caught by pirates off {port} and lost cargo.",
    "m.customs_caught": "Caught, Captain. I went through your hold. You'll pay the full tax and a fine on top.",
    "m.customs_over": "So generous, Captain. I remember captains who overpay.",
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
    "read_routine_log": False,   # sailed / anchored / dues / customs paid: shown, not read
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
