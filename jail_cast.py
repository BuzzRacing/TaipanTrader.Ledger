"""The ten wardens (one per port, jail.py), for cast.py. All invented adult women, all editable in
Admin > Cast & Voices. Each is keyed "warden_<port>"; her one photo is filed in the Media Library under
Personas > (her name), and her port's cell under Ports > (port) with the "jail_cell" role
(tools/queue_jail_pictures.py)."""

WARDENS = {
    "warden_hongkong": dict(
        name="Mrs. Agatha Crane", title="Matron of Victoria Gaol", age=52, origin="Portsmouth and Hong Kong",
        home_port="hongkong", color="#5a3a2a", voice_id="Deborah", speaking_rate=0.92,
        delivery="dry, unhurried English matron; never raises her voice and never needs to",
        catchphrase="Supper is at six, Captain. Whether you get any is up to you.",
        bio="A naval widow who took the matron's keys of Victoria Gaol when nobody else would. She runs the cleanest "
            "cells in the East and counts every prisoner twice, morning and night.",
        quirk="Jingles her key ring once before she speaks.",
        vice="Strong tea, a tidy register, and captains who think they are above the law.",
        secret="She keeps a second key to every cell sewn into her stays.",
        stats={"cunning": 7, "nerve": 9, "charm": 5, "greed": 4},
        prompt="An {adult} English woman (age 52), tall, broad-shouldered and handsome, iron-grey hair in a severe "
               "bun, the matron of Victoria Gaol in Hong Kong in 1860, standing at an iron cell door with a great ring "
               "of brass keys at her waist, a black wool gown with a crisp white collar unbuttoned at the throat and a "
               "leather belt cinched tight, lamplight on whitewashed stone, a dry, knowing half-smile, {style}"),
    "warden_singapore": dict(
        name="Miss Rosalind Pell", title="Keeper of the Pearl's Hill Lock-up", age=36, origin="Penang",
        home_port="singapore", color="#4f7a5a", voice_id="Elizabeth", speaking_rate=0.96,
        delivery="bright, brisk and teasing, a colonial officer's daughter who enjoys her work far too much",
        catchphrase="Do make yourself at home, Captain. You'll be here a while.",
        bio="Born in the Penang garrison and raised among soldiers, Rosalind took the Pearl's Hill lock-up as a lark "
            "and stayed for the power. She knows every smuggler on the Straits by name.",
        quirk="Twirls her keys on one finger while she reads the charge.",
        vice="Gin slings, gossip and brand-new prisoners.",
        secret="She lets the pretty ones out a day early.",
        stats={"cunning": 6, "nerve": 7, "charm": 9, "greed": 5},
        prompt="An {adult} English woman (age 36), slim and curvy with sun-browned skin and chestnut curls pinned up "
               "loosely, the keeper of the Pearl's Hill lock-up in Singapore in 1860, leaning against barred teak "
               "doors with keys twirled on one finger, a white linen officer's tunic open over a lace chemise, a "
               "pith helmet hung on a peg, slatted tropical light, a bright teasing smile, {style}"),
    "warden_manila": dict(
        name="Doña Remedios Salcedo", title="Alcaide of the Bilibid", age=48, origin="Manila",
        home_port="manila", color="#7a2a2f", voice_id="Julia", speaking_rate=0.95,
        delivery="velvet Spanish-accented English; pious on the surface, merciless underneath",
        catchphrase="Pray, Captain. It passes the time.",
        bio="The widow of a colonel, Remedios keeps the Bilibid with a rosary in one hand and the keys in the other. "
            "She hears every prisoner's confession and forgets none of them.",
        quirk="Counts her rosary beads while you plead.",
        vice="Church silver, black lace, and the confessions of proud captains.",
        secret="The confessions are sold to the Aduana.",
        stats={"cunning": 8, "nerve": 8, "charm": 7, "greed": 7},
        prompt="An {adult} Spanish-Filipina mestiza woman (age 48), full-figured and statuesque, black hair under a "
               "black lace mantilla, the alcaide of the Bilibid prison in Manila in 1860, standing in a stone archway "
               "of the gaol with a rosary and a ring of iron keys in her hands, a black silk gown with a deep square "
               "neckline and a crimson sash, candlelight and shadow, a serene, merciless gaze, {style}"),
    "warden_saigon": dict(
        name="Madame Odile Marchetti", title="Gardienne of the Saigon Maison Centrale", age=41, origin="Corsica",
        home_port="saigon", color="#4b3d6e", voice_id="Olivia", speaking_rate=1.0,
        delivery="smoky Corsican-French, amused and bored; she has seen every kind of prisoner",
        catchphrase="Every captain says he is innocent. Every one.",
        bio="A Corsican who came out with the colonial garrison, Odile runs the new Maison Centrale with a cigarette "
            "and a pistol. She plays cards with her prisoners and always wins.",
        quirk="Deals a hand of cards on the cell bars while she talks.",
        vice="Black tobacco, card games and winning.",
        secret="She has never once lost at cards, and never once played honestly.",
        stats={"cunning": 8, "nerve": 9, "charm": 7, "greed": 6},
        prompt="An {adult} Corsican-French woman (age 41), lean and curvy with olive skin and cropped black hair, the "
               "gardienne of the Maison Centrale in Saigon in 1860, seated on a stool before a cell with a hand of "
               "playing cards fanned against the bars, a thin cigarette, an open military coat over a black corset, "
               "a pistol on her hip, shuttered tropical light, an amused, bored, dangerous look, {style}"),
    "warden_nagasaki": dict(
        name="Kuroda Hisa", title="Warden of the Sakuramachi Gaol", age=44, origin="Nagasaki",
        home_port="nagasaki", color="#2f3e57", voice_id="Sarah", speaking_rate=0.88,
        delivery="quiet, formal and utterly calm; she speaks as if reading the sentence aloud",
        catchphrase="The days are long here, Captain. Count them.",
        bio="Hisa keeps the Sakuramachi gaol as her father did, by the old rules. Foreigners or not, every prisoner "
            "sweeps their cell at dawn and bows when she passes.",
        quirk="Writes each prisoner's name with a brush, and crosses it out on release.",
        vice="Silence, order, and the moment a proud man bows.",
        secret="She learned Dutch from a prisoner and reads every letter that leaves her gaol.",
        stats={"cunning": 9, "nerve": 8, "charm": 5, "greed": 3},
        prompt="An {adult} Japanese woman (age 44), slender and composed, black hair in a tight samurai-wife's knot, "
               "the warden of the Sakuramachi gaol in Nagasaki in 1860, kneeling on a tatami platform before a wooden "
               "lattice cell with a brush and a register, a dark indigo kimono loosened at the shoulders, a ring of "
               "iron keys beside her, paper lantern glow, a perfectly calm, unreadable stare, {style}"),
    "warden_foochow": dict(
        name="Madam Chen Yue-hua", title="Keeper of the Min River Yamen Cells", age=50, origin="Foochow",
        home_port="foochow", color="#355e3b", voice_id="Ashley", speaking_rate=0.94,
        delivery="soft and patient, a yamen keeper who bargains in whispers",
        catchphrase="Even a cell has a price, Captain. Just not one you can pay.",
        bio="Yue-hua has kept the yamen cells on the Min River for twenty years and buried three magistrates. "
            "Tea merchants, smugglers and princes have all slept on her straw.",
        quirk="Brings you a cup of tea and drinks it herself.",
        vice="Old jade, slow tea and other people's secrets.",
        secret="She was a pirate's wife before she was a keeper.",
        stats={"cunning": 8, "nerve": 7, "charm": 7, "greed": 6},
        prompt="An {adult} Chinese woman (age 50), plump and handsome with silver-streaked hair pinned with jade, the "
               "keeper of the yamen cells on the Min River at Foochow in 1860, standing before a wooden-barred cell "
               "with a lantern and a cup of tea, a dark green silk jacket open at the collar over an embroidered "
               "bodice, a ring of keys on a red cord, smoky lantern light, a patient, knowing smile, {style}"),
    "warden_shanghai": dict(
        name="Madam Tang Xiu-ying", title="Gaoler of the Mixed Court", age=39, origin="Suzhou",
        home_port="shanghai", color="#7d2418", voice_id="Ashley", speaking_rate=1.04,
        delivery="crisp, cold and commanding; she gives orders, never conversation",
        catchphrase="On your feet, Captain. You are in my house now.",
        bio="Xiu-ying keeps the cells of the Mixed Court, where foreign captains and Chinese thieves sleep side by "
            "side. She answers to nobody on the Bund, and the Bund knows it.",
        quirk="Taps a bamboo rod against her boot as she walks the cells.",
        vice="Power, silence and the Bund's best dumplings, eaten in front of the prisoners.",
        secret="Half the captains in her cells were put there on her word alone.",
        stats={"cunning": 8, "nerve": 10, "charm": 6, "greed": 6},
        prompt="An {adult} Chinese woman (age 39), tall and athletic with a sharp jaw and black hair in a long braid, "
               "the gaoler of the Mixed Court cells in Shanghai in 1860, striding down a stone corridor of iron-barred "
               "cells with a bamboo rod and a ring of keys, a fitted oxblood jacket with the high collar undone over a "
               "black silk bodice, riding boots, cold gaslight, a cold, commanding stare, {style}"),
    "warden_bangkok": dict(
        name="Khun Ying Prapai", title="Keeper of the King's Prison", age=46, origin="Bangkok",
        home_port="bangkok", color="#9a6a17", voice_id="Priya", speaking_rate=0.9,
        delivery="gracious and gentle, with perfect court manners; never unkind, never merciful",
        catchphrase="The King is patient, Captain. So am I.",
        bio="A lady of the court given the keys of the King's prison as an honour, Prapai keeps her prisoners fed, "
            "washed and locked up exactly as long as the sentence says, not one hour less.",
        quirk="Offers a lotus bud to every new prisoner.",
        vice="Lotus, gold leaf and perfect order.",
        secret="She once kept a prince for a year past his sentence because he was rude.",
        stats={"cunning": 7, "nerve": 7, "charm": 9, "greed": 4},
        prompt="An {adult} Thai court lady (age 46), graceful and full-figured with short court-style hair, the "
               "keeper of the King's prison in Bangkok in 1860, standing at a teak-barred cell in a gilded courtyard, "
               "a gold-threaded silk sabai over one bare shoulder, heavy gold armlets, a lotus bud in one hand and a "
               "ring of keys in the other, warm river light, a gracious, immovable smile, {style}"),
    "warden_batavia": dict(
        name="Mevrouw Hendrika Visser", title="Cipiersvrouw of the Stadhuis Cells", age=45, origin="Amsterdam",
        home_port="batavia", color="#c06a1a", voice_id="Wendy", speaking_rate=0.95,
        delivery="clipped Dutch precision with a dry, wicked humour",
        catchphrase="Rules, Captain. I have a great many of them.",
        bio="Hendrika keeps the cells under the Batavia Stadhuis exactly as the Company kept them for two hundred "
            "years. She posts the rules on every door, and adds one for every prisoner who breaks one.",
        quirk="Reads the rules aloud, in full, to every new arrival.",
        vice="Genever, starch, and captains who argue.",
        secret="She wrote most of the rules herself.",
        stats={"cunning": 8, "nerve": 8, "charm": 5, "greed": 5},
        prompt="An {adult} Dutch woman (age 45), tall and robust with pale blonde hair pinned tight under a white cap, "
               "the keeper of the cells beneath the Stadhuis of Batavia in 1860, standing in a vaulted brick cellar "
               "before an iron grille with a lantern and a printed list of rules, a black gown with a starched white "
               "collar unbuttoned over a laced bodice, a heavy ring of keys at her belt, a stern, wickedly amused "
               "look, {style}"),
    "warden_calcutta": dict(
        name="Mrs. Lavinia Hartley", title="Superintendent of the Presidency Jail", age=49, origin="Bristol and Calcutta",
        home_port="calcutta", color="#4a2848", voice_id="Elizabeth", speaking_rate=0.93,
        delivery="sweet, motherly and quietly terrifying; she calls every prisoner 'dear'",
        catchphrase="There, there, dear. It's only a few months.",
        bio="Lavinia came out to marry a magistrate and ended up running his jail. She is the kindest superintendent "
            "the Presidency Jail has ever had, and nobody has ever escaped it.",
        quirk="Tucks prisoners in with a blanket, then locks the door twice.",
        vice="Sugared almonds, embroidery and a full register.",
        secret="Her husband the magistrate hasn't sentenced anyone in years. She does it for him.",
        stats={"cunning": 9, "nerve": 8, "charm": 8, "greed": 5},
        prompt="An {adult} English woman (age 49), heavyset and comfortable with rosy cheeks and auburn hair going grey "
               "in soft curls, the superintendent of the Presidency Jail in Calcutta in 1860, standing at a barred cell "
               "door with a folded blanket over one arm and a great ring of keys in her hand, a plum silk gown with a "
               "low lace neckline and a cameo brooch, punkah fan and lamplight, a sweet, motherly, quietly terrifying "
               "smile, {style}"),
}
