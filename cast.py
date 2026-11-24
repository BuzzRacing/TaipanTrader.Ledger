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

import house_voice
import jail_cast
import jail_text
import legend_cast
import legend_text
import strings
import trade_text

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
        "portrait_prompt": "An {adult} Cantonese woman (age 45), heavy-set, full-figured and voluptuous comprador and merchant pirate queen in a "
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
        "portrait_prompt": "An {adult} English woman (age 39), tall and powerfully muscular, strawberry-blonde hair in a tight braid, fierce customs inspector and blue-coated revenue queen "
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
               "every ship off personally. She speaks when a captain tries to leave without paying, "
               "and when a captain's purse truly pleases her.",
        "quirk": "Turns the chain of office on her desk one link at a time while she decides what you owe.",
        "vice": "Good port wine, better gossip, and the sound of a dodger's purse being emptied on her desk.",
        "secret": "The harbour watch is three old men and a lantern. Her reputation does the rest.",
        "stats": {"cunning": 8, "nerve": 7, "charm": 6, "greed": 7},
        "portrait_prompt": "An {adult} woman (age 47), the Mayor of a treaty port behind a teak harbour-office desk, "
                           "ledger and iron strongbox before her, gold chain of office over a fitted pirate frock coat "
                           "and corset, harbour lanterns through the window behind, cool appraising smile, {style}",
    },
    "taxlady": {
        "name": "Mrs. Evelyn Marlowe", "title": "Registrar of the Merchant Houses", "brand_link": "",
        "age": 36, "origin": "Portsmouth, England", "home_port": "hongkong", "color": "#3f6e6a", "portrait": "",
        "voice_id": "Olivia", "speaking_rate": 0.96,
        "delivery": "warm, teasing and conspiratorial; a widow who knows everyone's business and enjoys letting you in on a little of it",
        "catchphrase": "Welcome home, Captain. It's all written down.",
        "bio": "Evelyn kept her husband's harbour register long before the typhoon took him. Captain Henry Marlowe "
               "was Hong Kong's Harbour Master; nobody else could read his book, so they let his widow keep it. Now "
               "she keeps the register of every merchant house on the China Seas, and wherever a house calls home, "
               "she is waiting on the wharf when it comes back: with its papers stamped, and one price from another "
               "port that nobody else has heard yet.",
        "quirk": "Pushes her spectacles up into her hair just before she says something she shouldn't.",
        "vice": "Gossip, good brandy, and being the first to know.",
        "secret": "The register has a second, private column: what every captain owes, and to whom.",
        "stats": {"cunning": 8, "nerve": 6, "charm": 9, "greed": 4},
        "portrait_prompt": "An {adult} English woman (age 36), the widowed Registrar of the Port of Hong Kong at a "
                           "harbour-office desk on a foggy wharf, dark hair pinned up with spectacles pushed up into it, "
                           "black coat over an oxblood corset, open ledger and a jade-topped pencil, conspiratorial "
                           "half-smile as if about to share a secret, {style}",
    },
    # The Accounting Ledger (20 Nov 2026): the House's own bookkeeper, on its rail button and its pages.
    "bookkeeper": {
        "name": "Mademoiselle Céleste Vautrin", "title": "Bookkeeper of the House & Mistress of the Crimson Ledger",
        "brand_link": "",
        "age": 38, "origin": "Pondicherry", "home_port": "hongkong", "color": "#8e1f2c", "portrait": "",
        "voice_id": "Olivia", "speaking_rate": 0.9,
        "delivery": "slow, husky and teasing, a French bookkeeper purring figures as if each one were a confession",
        "catchphrase": "Every column balances in the end, Captain. I simply take my time getting there.",
        "bio": "Céleste learned her double entry in a Pondicherry counting house and her bad habits in the cabins of "
               "the captains who hired her. She has kept the private books of four trading houses, ruined one, and "
               "married none. Now she keeps yours, in a crimson-bound ledger nobody else is allowed to touch, "
               "in a lamplit room above the wharf where every captain eventually comes to settle up.",
        "quirk": "Licks the tip of her quill before she writes a loss, and smiles while she does it.",
        "vice": "Red ink, French brandy, silk stockings and captains who read their own accounts aloud to her.",
        "secret": "She keeps a second ledger of what every captain in the harbour is really worth, and charges dearly for a peek.",
        "stats": {"cunning": 8, "nerve": 6, "charm": 9, "greed": 5},
        "portrait_prompt": "An {adult} French-Indian woman (age 38), the trading house's private bookkeeper in a "
                           "lamplit counting room above the Hong Kong wharf, reclining in a leather chair behind a teak "
                           "desk stacked with ledgers, a great crimson-bound ledger open across her lap, quill in her "
                           "ink-stained fingers, gold wire spectacles low on her nose, black silk blouse unbuttoned to "
                           "the waist and slipping off one shoulder over an oxblood lace corset, sheer black stockings "
                           "and one knee drawn up, dark hair falling loose from its pins, candle glow on brass scales "
                           "and silver dollars, a smouldering heavy-lidded gaze over her spectacles as if she has found "
                           "something deliciously wrong in your accounts, {style}",
    },
    # The Thieves (21 Nov 2026): the face of the Accounting Ledger's "Thieves" tile (robbed ashore and from store).
    # She reads the mugging and warehouse-robbery lines (LINE_DEFAULTS below). Voice is provisional: cast her in
    # Admin > Identity > Voice Library (casting lives on the Pi).
    "thieves": {
        "name": "Kamala \u201cMagpie\u201d Pillai", "title": "Pickpocket Queen of the Waterfront & Keeper of Other People's Purses",
        "brand_link": "",
        "age": 31, "origin": "Madras", "home_port": "singapore", "color": "#1f8a8a", "portrait": "",
        "voice_id": "Saanvi", "speaking_rate": 1.08,
        "delivery": "quick, merry and unhurried, a woman who is already holding your purse and is delighted to see you",
        "catchphrase": "Mind your pockets, darling. Well, mine now.",
        "bio": "Kamala learned the trade in the Madras bazaar at seven. By twenty she could lift a wedding ring in a "
               "handshake. She now runs the waterfront crowd from Singapore to Hong Kong, and she returns hats, "
               "because a gentleman should always go home decent.",
        "quirk": "Leaves a single peacock feather where your purse used to be.",
        "vice": "Silk stockings, sweet chai, and watching a captain pat his empty pocket.",
        "secret": "She has never kept a purse from a sailor with a family aboard. She leaves them the price of a meal and tells nobody.",
        "stats": {"cunning": 9, "nerve": 8, "charm": 9, "greed": 6},
        "portrait_prompt": "An {adult} Tamil woman (age 31), the pickpocket queen of a crowded Singapore quay market, "
                           "long dark braid with jasmine and a small brass nose-stud, one hand lifting a purse from a "
                           "captain's coat while the other holds a peacock feather and a teacup, a mischievous grin, {style}",
    },
    # The Table's Game Master (21 Nov 2026): she opens the month on the Harbor View, says whose turn it is and
    # puts each decision and action item to the Captain. Speaks aloud on the Table only (gm_text.py).
    # Voice is a provisional shared one: cast her in Admin > Identity > Voice Library (casting lives on the Pi).
    "gamemaster": {
        "name": "Madame Anahit Sarkissian", "title": "Mistress of the Table & Queen of the Hour", "brand_link": "",
        "age": 44, "origin": "Calcutta (the Armenian quarter)", "home_port": "calcutta", "color": "#c8922e", "portrait": "",
        "voice_id": "Sarah", "speaking_rate": 1.04,
        "delivery": "grand, brisk and theatrical, a ringmistress with a queen's poise who makes every question sound like a royal summons and every deadline like a dare",
        "catchphrase": "The table is yours, Captain. Do try to make it interesting.",
        "bio": "Daughter of an Armenian silk-and-silver house from New Julfa, raised in Calcutta's Armenian quarter "
               "among dice, ledgers and auction bells. She ran the floor of three gaming halls and one very illegal "
               "auction house before the pirate queens hired her to run the Table. Every month she opens it, puts "
               "the questions and keeps the captains honest, or at least entertained.",
        "quirk": "Rings her brass bell exactly once before any question that matters, and twice if she already knows the answer.",
        "vice": "Armenian brandy, loaded dice she swears she does not own, and captains who cannot resist a side bet.",
        "secret": "She knows every House's orders before the table does, and has never once let it show.",
        "stats": {"cunning": 8, "nerve": 7, "charm": 9, "greed": 4},
        "portrait_prompt": "An {adult} Armenian woman (age 44), the regal ringmistress-croupier of a Calcutta "
                           "merchant-palace gaming hall, standing at the head of a gilded table, crimson velvet "
                           "ringmaster's tailcoat with gold braid and ermine lapels open over a gold-embroidered black "
                           "corset, white opera gloves, a ruby collar necklace, dark hair swept up beneath a small gold "
                           "diadem, a jewelled bell and an ivory gavel before her, chandelier glow on gold leaf, a "
                           "queen's knowing smile as if she is about to pose you a question you will not want "
                           "to answer, {style}",
    },
}
# The Port Authority officers, one for each taxed port (Admin > Ports > Port Authority officer).
# Each captain's home port is kept by the Registrar, Mrs. Evelyn Marlowe (key "taxlady", above);
# Hong Kong's desk for visiting houses is kept by Senhora Isabel Rebelo (officer_hongkong).
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
        prompt="An {adult} English woman (age 44), soft, plump and voluptuous, honey-blonde curls coming loose, the languid widowed Port Authority officer of Singapore lounging in a "
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
        prompt="An {adult} English woman (age 46), heavyset and statuesque with an imposing bosom, platinum-blonde hair piled high, the ruthless Port Authority officer of Calcutta at a mahogany "
               "desk in the Strand Road customs house, plunging midnight-purple silk evening gown and ruby choker, "
               "long gloves, a strongbox lid half open beside her and a peacock-feather fan, punkah fan swaying "
               "overhead, a sweet venomous smile, {style}"),
    # Hong Kong's desk for visiting houses (a captain whose home is Hong Kong meets the Registrar instead).
    "officer_hongkong": dict(
        name="Senhora Isabel Rebelo", title="Collector of Victoria Harbour", age=33, origin="Macau",
        home_port="hongkong", color="#8a3b4a", voice_id="Rocio", speaking_rate=0.95,
        delivery="low and honeyed, Portuguese-accented English; flirtatious and close, with a blade under every compliment",
        catchphrase="I know every hiding place on a ship, Captain. I built half of them.",
        bio="Isabel grew up on her father's lorchas, running opium and silver past the Macau forts. When the Rebelos "
            "were finally caught, the British offered his clever daughter a choice: a cell, or a desk on the Hong Kong "
            "wharves. She chose the desk, and every smuggler on the coast has regretted it since.",
        quirk="Leans across the desk to read your manifest upside down while she smiles at you.",
        vice="Port wine from home, fast boats, and captains who think they're cleverer than her.",
        secret="Her father still runs boats out of Macau, and his cargo crosses her wharf untaxed.",
        stats={"cunning": 9, "nerve": 8, "charm": 8, "greed": 6},
        prompt="An {adult} Portuguese woman (age 33), the Port Authority officer of Hong Kong on a crowded Victoria "
               "Harbour wharf, a wine-red silk jacket open over a black lace corset, a gold crucifix and a dagger at her "
               "hip, leaning over a customs desk with a manifest upside down before her, lorchas and junks behind her, "
               "a slow dangerous smile, {style}"),
}
# The wardens (jail.py, 19 Nov 2026): one per port, keyed warden_<port> (jail_cast.py).
_OFFICERS.update(jail_cast.WARDENS)
# The Legends (legend.py, 20 Nov 2026): the three storytellers and each Legend's own characters (legend_cast.py).
_OFFICERS.update(legend_cast.TELLERS)
# RETIRED (23 Nov 2026): the thirty extra port women (mayor_<port>, keeper_<port>, shipmaster_<port>) were a
# second Mayor, Market keeper and Ship master on top of the shared Mayor, Lau Siu-wah and Tang Wai-lin, who
# already speak for every port. They are no longer in the cast; config.validate drops them from a saved cast.
_PORT_KEYS = ("hongkong", "shanghai", "nagasaki", "manila", "foochow", "saigon", "bangkok", "singapore",
              "batavia", "calcutta")
RETIRED = tuple(_p + "_" + _k for _p in ("mayor", "keeper", "shipmaster") for _k in _PORT_KEYS)
for _cid, _o in _OFFICERS.items():
    _o["brand_link"], _o["portrait"] = "", ""
    _o["portrait_prompt"] = _o.pop("prompt")
    CHARACTERS[_cid] = _o
# Voices Inworld does not have (Elizabeth, Julia, Priya) are replaced by the Easy-pass casting voices, so every
# default persona has a voice that exists. Only the defaults: a voice set in Voice Library is never touched.
for _cid, _v in {"officer_singapore": "Wendy", "officer_manila": "Marta", "officer_bangkok": "Liwa",
                 "warden_singapore": "Tala", "warden_manila": "Rocio", "warden_bangkok": "Minji",
                 "warden_calcutta": "Winifred", "teller_tavern": "Dalisay", "teller_drowned": "Rosalind"}.items():
    if _cid in CHARACTERS:
        CHARACTERS[_cid]["voice_id"] = _v
# Added after games were already saved: config.validate adds these to a saved cast once.
SEEDED = list(_OFFICERS) + ["bookkeeper", "gamemaster", "thieves"]
for _c in CHARACTERS.values():
    _c["portrait_prompt"] = _c["portrait_prompt"].format(adult=_ADULT, style=_STYLE)

# Persona prompts v2 (21 Nov 2026): persona_prompts_v2.py is the source of every default portrait prompt, and of
# her costume ladder (sultry / boudoir / topless / nude / clean), her light and her motion line. The old defaults
# above stay as the fallback if that module is ever missing. PORTRAIT_TIER is the look the Admin shows by default.
PORTRAIT_TIER = "topless"
try:
    import persona_prompts_v2 as _pp
except ImportError:      # pragma: no cover - the old defaults keep the game running
    _pp = None
if _pp:
    for _cid, _c in CHARACTERS.items():
        if _cid in _pp.LOOKS:
            _c["portrait_prompt"] = _pp.build(_cid, PORTRAIT_TIER)


def tier_prompt(cid, tier, mood=None, saved=None):
    """Her prompt at one look (sultry, boudoir, topless, nude, clean) from persona_prompts_v2, else her default.
    saved is her portrait prompt as edited on her Cast & Voices card (cfg["characters"][cid]["portrait_prompt"]):
    her identity is taken from it, so an edit on the card reaches every look. The costume wording stays in code."""
    if _pp and cid in _pp.LOOKS:
        return _pp.build(cid, tier, mood, saved=saved)
    return CHARACTERS.get(cid, {}).get("portrait_prompt", "")

LINE_DEFAULTS = {}
for _who, _keys in {
    "narrator": ["l.arrive", "l.anchor", "l.collectors", "l.collectors_warn", "l.sailed", "l.anchored",
                 "l.ship_lost", "l.cargo_lost", "l.wrecked", "m.unsail", "m.forced"],
    # Silent (owner's decision, 17 Nov 2026): giving orders can turn the month at once, so "Orders given:
    # sail for ..." was heard after the voyage had already begun, over the sea battle or the captain's log.
    # The words still show on screen. Admin > Cast & Voices can hand them back to a reader.
    # Storms (20 Nov 2026): the storm screen replaces the voiced storm report, so these stay on screen only.
    "": ["m.sail", "m.stay", "m.slip", "l.typhoon", "l.storm", "l.offcourse", "l.storm_cargo", "l.storm_guns",
         "l.storm_land", "l.storm_land_bad", "l.storm_land_far", "m.storm_ack",
         # The Registrar's log line is the receipt; she says the tip itself at the desk.
         "l.registrar_logged", "l.registrar_hot_logged", "l.officer_hot_logged"] + [
         # The Mayor's Parlour (decision 3): small thanks are text only; the log line is the receipt.
         "m.gift.cool", "m.gift.gracious", "l.gift"]
        + ["m.gift.{}.{}".format(t, i) for t in ("cool", "gracious") for i in range(10)],
    "bosun": ["l.driven_off", "l.attack", "l.attack_noguns", "l.sank_all", "l.outran",
              "l.long_fight", "l.plundered", "l.damage", "l.attack_met", "l.retreated", "l.parley_paid",
              # The crew hides a share (19 Nov 2026): the bosun tells you what they saved.
              "l.hid_pirates", "l.hid_customs", "l.hid_desk", "l.hid_bankrupt"],
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
                   "e.fleet_limit", "e.class_limit.escort", "e.class_limit.cargo", "e.class_locked.escort",
                   "e.class_locked.cargo", "e.last_trader", "e.ship_cost", "e.no_such_ship", "e.last_ship", "e.unload_first",
                   "e.no_more_guns", "e.gun_cost", "e.nothing_to_repair"],
    "customs": ["l.seized", "n.ban", "n.ban_lifted", "n.caught"],
    # The Mayor and the Tax collector speak only when they catch a captain (owner's decision).
    # The Mayor's Parlour: she thanks a Warm or Delighted gift aloud (decision 3).
    "mayor": ["l.slip_caught", "m.gift.warm", "m.gift.delighted", "l.band_hostile", "l.band_favoured"]
             + ["m.gift.{}.{}".format(t, i) for t in ("warm", "delighted") for i in range(10)]
             # Her congratulations on a promotion (18 Nov 2026).
             + [k for k in strings.EN if k.startswith("m.promote.") or k.startswith("m.promote_top.")],
    # The Port Authority: every line is read by the officer of the port the house is in
    # (voice.Planner, OFFICER_KEYS); "taxlady" is her stand-in when a line has no port.
    "taxlady": ["l.customs_welcome", "l.customs_free", "l.customs_home", "l.customs_empty", "l.customs_paid", "l.customs_bought",
                "l.customs_caught", "m.customs_clean", "m.customs_over", "m.customs_bought", "m.customs_caught",
                "m.customs_bribe_refused", "m.customs_buyback", "e.customs_first", "e.customs_bribe_cost",
                "e.customs_nothing_back",
                # Hers too (23 Nov 2026): these fell to the First Mate, who read them over the officer's face.
                "l.customs_spot_home", "l.customs_spot_shares", "m.customs_nothing", "m.customs_done"] + [k for k in strings.EN if k.startswith(("l.customs_welcome.", "m.customs_clean."))]
               # A hot tip from a port's own officer (engine _hot_tip), read by the officer of that port.
               + [k for k in strings.EN if k.startswith("l.officer_hot.")]
               # Under the Counter (counter.py): her paid tips, read by the officer of the port the house is in.
               + [k for k in strings.EN if k.startswith("l.counter_")] + ["e.counter_cost", "e.counter_off"],
    # The Thieves (21 Nov 2026): Magpie reads the mugging and the warehouse robbery herself.
    "thieves": ["l.robbed", "l.wh_robbed"],
    "crier": ["n.opening", "n.start_one", "n.start_many", "n.game_over", "n.scarce", "n.glut", "n.wrecked",
              "m.begin", "m.new_game"],
}.items():
    for _k in _keys:
        LINE_DEFAULTS[_k] = _who
# The jail (jail.py): every line is read by the warden of the port the house is in (voice.Planner,
# WARDEN_KEYS); Hong Kong's warden is the stand-in when a line has no port.
for _k in jail_text.WARDEN_KEYS:
    LINE_DEFAULTS[_k] = "warden_hongkong"
LINE_DEFAULTS["n.jail"] = "crier"
# The Legends (legend.py): the story screen tells a Legend itself, so its log lines and receipts stay on
# screen only; its headlines are the crier's.
for _k in legend_text.SILENT:
    LINE_DEFAULTS[_k] = ""
LINE_DEFAULTS["n.legend_palace_sold"] = "crier"
# The Accounting Ledger (acct_text.py): the bookkeeper reads her own greetings.
for _k in strings.EN:
    if _k.startswith("l.acct_"):
        LINE_DEFAULTS[_k] = "bookkeeper"
# The Game Master (gm_text.py, 21 Nov 2026): her prompts are read on the Table only.
for _k in strings.EN:
    if _k.startswith("gm."):
        LINE_DEFAULTS[_k] = "gamemaster"
# "Game length set to N years" is said on the Set the terms screen, so Madame Anahit says it, not the First Mate.
LINE_DEFAULTS["m.years"] = "gamemaster"
# The comprador's buy and sell banks (trade_text.py): all hers.
for _k in trade_text.KEYS:
    LINE_DEFAULTS[_k] = "comprador"
WARDEN_KEYS = frozenset(jail_text.WARDEN_KEYS)
# The Mayor's lines: in a port whose own Mayor (mayor_<port>) has a voice, they are read with hers.
MAYOR_KEYS = frozenset(_k for _k, _w in LINE_DEFAULTS.items() if _w == "mayor")
# Cast members who are a different woman in every port: while a line is still theirs by default, it is read in
# the voice of that port's own woman (cast key <prefix><port>) once she has one (voice.Planner.port_voice).
PORT_VOICES = {}      # emptied 23 Nov 2026: the thirty port women are retired (see RETIRED); one Mayor, comprador, shipwright
OFFICER_KEYS = frozenset(LINE_DEFAULTS_KEYS for LINE_DEFAULTS_KEYS, _w in LINE_DEFAULTS.items() if _w == "taxlady")
# The Registrar's own lines (Mrs. Marlowe, at each captain's home port). Set after OFFICER_KEYS so they
# are always hers, never handed to the officer of the port she is standing in.
for _k in ["l.registrar_home.{}".format(i) for i in range(15)] + ["l.registrar_tip.{}".format(i) for i in range(10)] \
        + ["l.registrar_hot.{}".format(i) for i in range(10)]:
    LINE_DEFAULTS[_k] = "taxlady"

# Short spoken versions of lines with amounts in them. The screen still shows the
# full wording; the voice says this instead, so a line sounds the same however
# much it was for and is paid for only once. Names in {braces} come from the
# line on screen (ports, goods, ships, people) and are kept to small, fixed sets.
# A spoken version is only used while the on-screen line is the stock English
# (or stock family) wording; reword a line and it is read in full unless the
# Admin page gives it a spoken version of its own (cfg voice.say).
SAY = {
    # Under the Counter: her price, said without the figures (shown on screen).
    "e.counter_cost": "My price is more than you're carrying, Captain. I don't do favours on credit. Not that kind, anyway.",
    "l.slip_caught": "Slipping out of {port} in the dark, Captain? My watch never sleeps. You will pay double, and {port} will remember your name.",
    "l.slip_away": "You slipped out of {port} at night. The harbour watch never saw you, and the Mayor's dues went unpaid.",
    "m.gift.warm": "Now that is how a captain calls on a lady. My clerks will be told your house is a friend of the city.",
    "m.gift.delighted": "Captain! Sit, sit, you will take a glass with me. Anyone who troubles your house in my harbour answers to me.",
    "l.customs_welcome": "{line} Declare your cargo, Captain. Truly, or not. I do so enjoy finding out.",
    # Her full-length greetings (strings.py l.customs_welcome.20-29), said without the month's rate.
    "l.customs_welcome.20": "{line} Declare your cargo, Captain. Truly, or not. I do so enjoy finding out.",
    "l.customs_welcome.21": "{line} Write your figures honestly, Captain, or write them bravely. I'll know which.",
    "l.customs_welcome.22": "Good day, Captain. {line} Declare low and I may buy at your price; declare false and I will find out. Choose well.",
    "l.customs_welcome.23": "{line} I have seen every trick on this coast, Captain: the false bottom, the second ledger, the sad story about the storm. Just give me the numbers.",
    "l.customs_welcome.24": "There you are. {line} Declare it all, declare it true, and you'll be ashore by supper.",
    "l.customs_welcome.25": "{line} A little lie may slip past me, Captain. A large one never has. Shall we begin?",
    "l.customs_welcome.26": "Come in, Captain. {line} The ink is free, and the truth costs you nothing at all. Lies cost a great deal more.",
    "l.customs_welcome.27": "{line} And before you ask, no, my rate does not come down because you smile at me. Lying costs you double. Declare, Captain.",
    "l.customs_welcome.28": "Ah, Captain, at last. I've had nothing but rice junks and honest men all morning. {line} Do try to make this interesting.",
    "l.customs_welcome.29": "{line} You know the rule of this desk, Captain: you name your cargo's worth, and if your price is too modest, I buy at it. Name it wisely.",
    # The Registrar's price tips, said without the price (the price stays on screen and in the Price Book).
    "l.registrar_tip.0": "A little something from my register, Captain: {goods} is fetching a pretty price in {where} this month. You didn't hear it from me.",
    "l.registrar_tip.1": "Lean in. A captain off the {where} run let slip what {goods} went for there this month. It's on your desk. Do with it what you will.",
    "l.registrar_tip.2": "My book has this month's price for {goods} in {where}, Captain. My book is never wrong.",
    "l.registrar_tip.3": "Between us, Captain: {goods}, in {where}. Fresh this month. The figure's on your papers. Now forget where you heard it.",
    "l.registrar_tip.4": "The {where} manifests came in this morning. {goods}. I thought of you at once, Captain.",
    "l.registrar_tip.5": "Spectacles up, Captain, I'm about to say something I shouldn't: what {goods} is selling for in {where} this month. It's written on your papers.",
    "l.registrar_tip.6": "You'll want to know this, Captain. {goods} in {where}, as of this month. The price is on your desk. Don't tell the other houses.",
    "l.registrar_tip.7": "A gift from the register, Captain, and it's worth more than brandy: this month's price for {goods} in {where}.",
    "l.registrar_tip.8": "Everyone's talking about {where}, Captain, but only I know the figure for {goods}. I've written it down for you.",
    "l.registrar_tip.9": "I keep a second column for my favourite captains, Captain. In it: {goods}, {where}, this month. The figure's on your papers.",
    # The spot-check greetings, said without the month's rate (23 Nov 2026; house_voice.SPOKEN has the new wording).
    "l.customs_spot_home": "{line} Welcome home, Captain, but not so fast. Spot check today: even our own houses are looked over now and then. {port}'s full rate on whatever you declare.",
    "l.customs_spot_shares": "{line} Your shares in {port} buy you a great deal of goodwill, Captain, but not today. Spot check: the full rate on whatever you declare.",
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
    # A soft opening word first, so the clip ramps in instead of starting on a hard "B" or "S".
    "m.bought": "Approved. Bought {good}.",
    "m.sold": "Approved. Sold {good}.",
    "m.sold_store": "Approved. Sold {good} from the hold and warehouse.",
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
    "l.hid_pirates": "Before they came over the rail, the crew stowed some of the cargo where no pirate would look.",
    "l.hid_customs": "The crew had some of it under the ballast before the officers came aboard. They never found it.",
    "l.hid_desk": "While she counted, the crew slipped some of it below decks. Untaxed, and still ours.",
    "l.hid_bankrupt": "Before the clerks came aboard, the crew squirrelled a little away. It is yours still.",
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

# The Mayor's banked thanks (strings.py m.gift.<tier>.N) are said without the receipt: just her words.
SAY.update({k: v.split("+{gain}. ", 1)[1] for k, v in strings.EN.items()
            if k.startswith(("m.gift.warm.", "m.gift.delighted.")) and "+{gain}. " in v})
# The wardens say their lines without the numbers (jail_text.py).
SAY.update(jail_text.SAY)
# The comprador's banked receipts, without the amounts (trade_text.py).
SAY.update(trade_text.SAY)
# The same, for lines whose family-friendly wording differs.
SAY_FAMILY = {
    "e.counter_cost": "My price is more than you're carrying, Captain. I don't do favours on credit.",
    "l.jail_drink": "Your crew has been spending your silver ashore while you sit here, Captain.",
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

# The house voice (house_voice.py): spoken versions of the rewritten lines. The spoken versions they
# replace go with the old wording, now the family wording, so family-friendly voices keep their clips.
SAY_FAMILY.update(trade_text.SAY_FAMILY)
house_voice.apply_say(SAY, SAY_FAMILY)
for _k, _v in house_voice.family_gift_say(strings.FAMILY).items():
    SAY_FAMILY.setdefault(_k, _v)


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
    "read_routine_log": False,   # sailed / anchored / dues (paid or short) / customs paid: shown, not read
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
VOICE_RE = re.compile(r"^[\w.:\-/]{1,120}$")     # \w lets in accented Inworld ids such as "Hélène"


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


# Casting (23 Nov 2026): Admin > Brand picks which cast member plays the moneylender and the pirate queen
# (brand.lender_cast, brand.pirate_cast). The game still asks for the role ("lender", "pirate"); whoever is
# cast answers with her own name, title, portrait, pictures and voice.
ROLES = ("lender", "pirate")


def played_by(cfg, cid):
    """The cast member who plays a role just now (the role's own character unless Brand cast someone else)."""
    if cid in ROLES:
        who = (cfg.get("brand") or {}).get(cid + "_cast") or cid
        if who in (cfg.get("characters") or {}):
            return who
    return cid


def _own_role(cfg, link):
    """True while a Brand role is still played by its own character, so its Brand name applies."""
    return link not in ROLES or ((cfg.get("brand") or {}).get(link + "_cast") or link) == link


def actor_name(cfg, cid):
    """A cast member's own name, whatever role she is playing."""
    c = cfg["characters"].get(cid) or {}
    link = c.get("brand_link") or ""
    if c.get("name"):
        return c["name"]
    return cfg["brand"].get(link) or cid if link else cid


def display_name(cfg, cid):
    who = played_by(cfg, cid)
    if who != cid:
        return actor_name(cfg, who)
    c = cfg["characters"].get(cid) or {}
    link = c.get("brand_link") or ""
    if link and cfg["brand"].get(link) and _own_role(cfg, link):
        return cfg["brand"][link]
    return c.get("name") or cid


def apply_casting(cfg):
    """Tidies brand.<role>_cast and, when someone else is cast, makes the Brand name hers, so the wording's
    {lender} and {pirate} follow the choice. Called by config.validate after the cast is cleaned."""
    brand, chars = cfg["brand"], cfg["characters"]
    for role in ROLES:
        who = brand.get(role + "_cast")
        if not isinstance(who, str) or who not in chars:
            who = role if role in chars else ""
        brand[role + "_cast"] = who
    for role in ROLES:
        who = brand[role + "_cast"]
        if who and who != role:
            brand[role] = (chars[who].get("name") or brand.get(role) or who)[:60]
        elif who and chars[who].get("name") and any(
                k != role and c.get("name") == brand.get(role) for k, c in chars.items()):
            brand[role] = chars[who]["name"][:60]      # handed back: the stand-in's name goes, her own returns


def public_cast(cfg):
    """What the player screens need to show who is speaking. A Brand role shows whoever is cast in it."""
    out = {}
    for cid in cfg["characters"]:
        c = cfg["characters"][played_by(cfg, cid)]
        out[cid] = {"name": display_name(cfg, cid), "title": c["title"], "portrait": c["portrait"], "color": c["color"]}
    return out


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


def _saved_prompt(saved, default):
    """A saved portrait prompt, unless it is an untouched old default (it still carries the old shared style tail):
    then she gets the v2 prompt. A prompt edited in Admin has no such tail and is kept as written."""
    saved = str(saved or "").strip()
    if saved and not (_pp and _STYLE in saved):
        return saved
    return str(default or "").strip()


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
            "portrait_prompt": _saved_prompt(c.get("portrait_prompt"), base.get("portrait_prompt"))[:2000],
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
