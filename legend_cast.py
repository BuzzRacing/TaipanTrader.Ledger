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
        prompt="An {adult} Chinese woman (age 47), graceful and full-figured with a calm, beautiful face, long black "
               "hair pinned up with red lacquer pins, the keeper of the lantern at a sea goddess temple on the Fujian "
               "coast in 1860, kneeling beside a great glowing red paper lantern, wearing a loosened crimson and "
               "gold silk temple robe, incense smoke curling around her, gilded carvings "
               "of waves and dragons behind, an open scroll across her lap, a serene knowing smile as if she has "
               "already read the ending, {style}"),
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
        prompt="An {adult} Spanish-Filipina woman (age 34), curvy and vivid with warm brown skin, a mass of dark "
               "curls and gold hoop earrings, a tavern singer on a small stage in a smoky waterfront tavern in 1860, "
               "seated on the edge of a table with a guitar across her knee and a glass of rum in her raised hand, "
               "a plunging scarlet off-shoulder blouse and a tiered skirt, lantern light, "
               "sailors' silhouettes in the haze behind her, head thrown back in a wicked laugh, {style}"),
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
        prompt="An {adult} Cornish woman (age 29), pale and beautiful with sea-green eyes and long dark wet hair "
               "strung with tiny shells and a strand of pearls, a drowned bride risen from the sea in 1860, standing "
               "on the moonlit deck of a trading junk, wearing a soaked ivory off-shoulder wedding gown that "
               "clings to her, water streaming from the hem, a ship's bell frozen mid-swing beside "
               "her, a faint blue-green glow on her skin, fog and still black water behind, a soft teasing smile "
               "meant for one person only, {style}"),
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
        prompt="An {adult} Japanese woman (age 30), tall and exquisite with ink-black hair falling to her hips and "
               "pinned with coral and gold, the daughter of the Dragon King in an undersea palace of coral and "
               "lacquer, wearing ropes of pearls and a plunging sea-blue and silver court robe "
               "trailing in the water like a tail, a small black lacquer box tied with a red cord held in both "
               "hands, shafts of green light falling through the water above, a great sea turtle at her side, an "
               "amused, regal, dangerous smile, {style}"),
}

STORYTELLERS = ("teller_temple", "teller_tavern", "teller_drowned")
