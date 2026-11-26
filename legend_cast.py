"""The Legends' own people (legend.py, 20 Nov 2026; project doc "SeaTrader Legends Library"), for cast.py.

THE THREE STORYTELLERS (owner's decision: "all three"). A Legend is told by one of them, standing on the
left of the story screen as Powder does in a sea battle:

  teller_temple   Mother Chen Sui-lan, keeper of the lantern at the sea goddess's temple. Serene, knowing,
                  teases you about the ending she has already read.
  teller_tavern   Josefina "La Golondrina" Reyes, a tavern singer who has sailed with everyone. Bawdy and
                  funny, and swears she was there for all of it.
  teller_drowned  Morwenna Teague, the drowned bride, whom only the Captain can see. She appears when the
                  bell stops, which is why the month waits.

Each Legend names the one who tells it; Admin > Legends can hand them all to one teller or pick at random.

THE LEGENDS' CHARACTERS answer on the right of the screen, as the enemy does in a battle. Keyed legend_<name>.

All invented adult women, all editable in Admin > Cast & Voices. Pictures are filed in the Media Library under
Personas > (her name) and queued as NSFW + clean pairs with Queue_Storyteller_Pairs.bat."""

TELLERS = {
    "teller_temple": dict(
        name="Mother Chen Sui-lan", title="Keeper of the Lantern, Temple of the Sea Goddess", age=47, origin="Meizhou",
        home_port="foochow", color="#b3262e", voice_id="Xinyi", speaking_rate=0.88,
        delivery="serene, low and unhurried, a temple storyteller who has read the last page and finds your "
                 "hopes adorable",
        catchphrase="Sit, Captain. The ending is already written. I only enjoy watching you reach it.",
        bio="Sui-lan has kept the red lantern at the sea goddess's temple since she was a girl, and every sailor on "
            "the coast has knelt in front of her at least once, usually to ask for something he did not deserve. She "
            "tells the old stories to anyone who lights incense, and she has never been known to tell one the same "
            "way twice, or to tell one wrong.",
        quirk="Trims the lantern wick with her fingers before the part of the story you will not like.",
        vice="Good incense, plum wine after the last prayer, and captains who think they are the hero.",
        secret="She was a pirate's navigator for six years, and half her stories are confessions.",
        stats={"cunning": 9, "nerve": 7, "charm": 8, "greed": 2},
        prompt='An {adult} Chinese woman (age 47), Mother Chen Sui-lan, graceful and full-figured with a calm beautiful face, long black hair pinned up with red lacquer pins, the keeper of the lantern at a sea goddess temple on the Fujian coast kneeling beside a great glowing red paper lantern, incense smoke curling around her, gilded carvings of waves and dragons behind, an open scroll across her lap, a serene knowing smile as if she has already read the ending, crimson and gold silk temple robe worn closed with a high collar, red lantern glow and incense haze on gold, warm and devotional, {style}'),
    "teller_tavern": dict(
        name="Josefina \"La Golondrina\" Reyes", title="Singer at the Sign of the Swallow", age=34, origin="Manila",
        home_port="manila", color="#c7802b", voice_id="Julia", speaking_rate=1.02,
        delivery="warm, bawdy and quick, a tavern singer telling it over the rim of a glass and laughing at her "
                 "own best lines",
        catchphrase="I was there, Captain. I was always there. Buy me a drink and I'll tell you who was under the table.",
        bio="Josefina has sung in every waterfront tavern from Calcutta to Nagasaki and sailed, by her own count, "
            "with every captain worth the trouble. They call her the Swallow because she always comes back, and "
            "because of a story she tells about a bishop. She knows which legends are true, having started several.",
        quirk="Taps the rhythm of the story on her glass, and stops dead when it turns dangerous.",
        vice="Rum, applause, other people's secrets and the last word.",
        secret="She cannot swim, and has never once told a story about herself that was true.",
        stats={"cunning": 7, "nerve": 8, "charm": 10, "greed": 6},
        prompt='An {adult} Spanish-Filipina woman (age 34), Josefina "La Golondrina" Reyes, vivid with warm brown skin, a mass of dark curls and gold hoop earrings, a tavern singer on a small stage in a smoky waterfront tavern, seated on the edge of a table with a guitar across her knee and a glass of rum raised, head thrown back in a wicked laugh, scarlet off-shoulder blouse with a modest neckline and a tiered skirt, warm lantern light, smoky amber haze, sailors\' silhouettes behind, {style}'),
    "teller_drowned": dict(
        name="Morwenna Teague", title="The Drowned Bride", age=29, origin="Cornwall, and the Paracels",
        home_port="hongkong", color="#3f7f8c", voice_id="Elizabeth", speaking_rate=0.86,
        delivery="soft, close and amused, a drowned woman murmuring in the Captain's ear while the world stands "
                 "still; cold water and warm mischief",
        catchphrase="The bell has stopped, Captain. That means you're mine for a little while.",
        bio="Morwenna went over the side of the brig Tamar off the Paracels in her wedding dress, the night before "
            "the wedding, and has not decided whether she jumped. She has kept the hours for drowning sailors ever "
            "since. Only one living captain can see her, and she appears when the ship's bell stops mid-swing: "
            "while she talks, no time passes at all. She finds this very convenient.",
        quirk="Wrings sea water out of her hair onto your charts while she talks.",
        vice="Warm hands, lit lamps, and captains who do not look away.",
        secret="She can leave whenever she likes. She stays because nobody else has ever listened.",
        stats={"cunning": 8, "nerve": 9, "charm": 9, "greed": 1},
        prompt="An {adult} Cornish woman (age 29), Morwenna Teague, the Drowned Bride, pale and beautiful with sea-green eyes and long dark wet hair strung with tiny shells and a strand of pearls, risen from the sea on the moonlit deck of a trading junk, a ship's bell frozen mid-swing beside her, a soft sad smile, ivory wedding gown with a high lace collar and long sleeves, sea water dripping from the hem, a faint blue-green glow, moonlight, fog and still black water, {style}"),
    # ---- The Palace Beneath the Waves -------------------------------------------------------------------
    "legend_otohime": dict(
        name="Princess Otohime", title="Daughter of the Dragon King", age=30, origin="The Palace Beneath the Waves",
        home_port="nagasaki", color="#2c6e8f", voice_id="Asuka", speaking_rate=0.92,
        delivery="regal, silky and entertained, a sea princess who has never been refused and is curious what it "
                 "would feel like",
        catchphrase="I promise to return you in the condition I found you, Captain. More or less.",
        bio="The Dragon King's daughter keeps a palace of coral under the Nagasaki roads, a household of turtles and "
            "a ledger of every kindness and every insult the sea has ever been done. She pays both back with "
            "interest. She gives her guests a lacquer box when they leave, and tells them never to open it.",
        quirk="Counts her pearls with one finger while she decides what to do with you.",
        vice="Guests, wagers with her father, and mortals who do as they are told.",
        secret="Nobody has ever kept the lid on. She has started to hope.",
        stats={"cunning": 9, "nerve": 9, "charm": 10, "greed": 4},
        prompt='An {adult} Japanese woman (age 30), Princess Otohime, tall and exquisite with ink-black hair falling to her hips and pinned with coral and gold, the daughter of the Dragon King in an undersea palace of coral and lacquer, a small black lacquer box tied with a red cord in both hands, a great sea turtle at her side, an amused regal dangerous smile, high-collared sea-blue and silver court robe trailing in the water, ropes of pearls, shafts of green light falling through the water, pearl shimmer, deep teal, {style}'),
    # ---- The second set (25 Nov 2026) -------------------------------------------------------------------
    "legend_passenger": dict(
        name="Dona Ines de Albuquerque", title="The Passenger Who Pays Too Well", age=36, origin="Goa",
        home_port="calcutta", color="#8a2f4a", voice_id="Sarah", speaking_rate=0.95,
        delivery="low, polished and a little hunted, a Goan lady who has learned to be charming at doors she is "
                 "afraid of",
        catchphrase="Passage to anywhere that is not here, Captain. I will pay for the silence.",
        bio="Dona Ines married a Portuguese shipping agent in Goa and buried him within the year, with debts she "
            "had never seen. She ran with his pearls and her prayer book, and has been paying for a quiet cabin "
            "ever since. She tips like a duchess and prays like a sinner, and the sea has a way of noticing both.",
        quirk="Tells her rosary over the bedcovers, and counts the locks on any door she passes.",
        vice="Port wine, good locks and captains who do not ask where she is from.",
        secret="She never stole the pearls. He gave them to her, the night before the creditors came.",
        stats={"cunning": 7, "nerve": 6, "charm": 9, "greed": 4},
        prompt="An {adult} Goan-Portuguese woman (age 36), elegant and full-figured with olive skin and dark hair "
               "half-pinned under a black lace mantilla, a widow travelling in secret in 1860, in a lamp-lit ship's "
               "cabin with a heavy purse and a rosary on the table, wearing a deep wine-red travelling dress "
               "buttoned to the throat with a string of pearls and a lace shawl around her "
               "shoulders, a hand on the cabin lock and a hunted, glancing, beautiful look, {style}"),
    "legend_debtor": dict(
        name="Nyonya Tan Bee-Lian", title="Owner of the Only Ship She Has", age=44, origin="Singapore",
        home_port="singapore", color="#2f8a5b", voice_id="Ashley", speaking_rate=0.98,
        delivery="warm, quick and a little theatrical, a Peranakan trader who negotiates the way other women "
                 "haggle: with eye contact and a plan",
        catchphrase="I have one ship, Captain, and several admirers. Let us see which of them is the cheaper.",
        bio="Bee-Lian runs freight from Singapore to Malacca on a single sound ship and a great many promises. She "
            "signed the ship over as security to a lender who sold the paper to a lender who sold it to Madam Wu, "
            "and now it sits on the desk of a foreign captain who has never met her. She dresses to be underestimated.",
        quirk="Fans herself with her own bills of lading.",
        vice="Fine tea, fine cloth, a good gamble and friends with long memories.",
        secret="The squall that sank her second ship was a gambling table. She has not told anyone, including "
               "her bookkeeper.",
        stats={"cunning": 9, "nerve": 7, "charm": 8, "greed": 6},
        prompt="An {adult} Peranakan Chinese woman (age 44), poised and full-figured with sleek dark hair in a "
               "chignon pinned with gold, a Singapore shipping merchant in 1860 standing at a harbour counting "
               "house desk with a stack of bills of lading and a lacquered fan, wearing a fitted embroidered "
               "kebaya of emerald silk fastened with gold brooches over a sarong, jade bangles, harbour lanterns "
               "and godowns through the window, a bright appraising smile that gives nothing away, {style}"),
    "legend_robe": dict(
        name="Lady Nami of the Foam", title="The Dancer on the Water", age=28, origin="Ryukyu, and below",
        home_port="foochow", color="#58a6b8", voice_id="Sarah", speaking_rate=0.90,
        delivery="light, amused and faintly sung, a sea woman who finds mortal bargaining adorable and a little "
                 "sad",
        catchphrase="Give it back, sailor. I was only swimming.",
        bio="Nami is one of the sea goddess's many daughters, who come ashore on moonlit rocks to dance in robes "
            "of sea-silk. A robe taken is a bride caught, and every coast has a story about a man who hid one. "
            "She finds this flattering the first time and tiresome the thousandth.",
        quirk="Wrings her hair out and the water makes a faint song.",
        vice="Moonlight, salt air, mortals who turn their backs and her sisters' gossip.",
        secret="She could always have made the sea take the robe back. She wanted to see what you would do.",
        stats={"cunning": 8, "nerve": 8, "charm": 10, "greed": 2},
        prompt="An {adult} Ryukyuan woman (age 28), lithe and luminous with long wet black hair and pearl-white "
               "skin dusted with sea-glitter, a sea goddess's daughter standing on a rock in moonlit surf, "
               "wrapped in a flowing high-collared robe of shimmering sea-silk, shells in her hair, sea spray "
               "around her, green-blue light on the water, a playful, patient, dangerous smile, "
               "{style}"),
    "legend_clerk": dict(
        name="Le Thi Hoa", title="Last Clerk of the Crimson Ledger", age=33, origin="Saigon",
        home_port="saigon", color="#a4232f", voice_id="Olivia", speaking_rate=0.93,
        delivery="dry, precise and quietly wry, a clerk who has read everyone's secrets and kept every one of "
                 "them, until now",
        catchphrase="Everyone owes somebody, Captain. I only know who.",
        bio="Hoa kept the books of a Saigon merchant who died owing the whole coast, and who left behind a ledger "
            "of everything the coast owed him in turn: money, favours, silences. She has been recovering its torn "
            "pages ever since, one fishwife and one pawnshop at a time, trying to decide whether the whole thing "
            "should be burned.",
        quirk="Dips her pen without looking and never blots it.",
        vice="Red ink, black coffee and the moment a liar realises she has the page.",
        secret="She has read her own name on page nine, and has not told anyone what it says.",
        stats={"cunning": 10, "nerve": 6, "charm": 7, "greed": 3},
        prompt="An {adult} Vietnamese woman (age 33), slender and sharp-eyed with a long black braid over one "
               "shoulder, a merchant's clerk in a lamp-lit counting room in Saigon in 1860, seated at a "
               "slanted writing desk with a fat crimson ledger and a red pen, wearing a fitted indigo ao dai "
               "buttoned at the collar, spectacles pushed up into her hair, torn ledger "
               "pages pinned along the wall behind her, a dry, knowing look over the book, {style}"),
}

STORYTELLERS = ("teller_temple", "teller_tavern", "teller_drowned")
