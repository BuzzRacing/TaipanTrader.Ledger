"""The second set of Legends (25 Nov 2026; project doc "SeaTrader Legends Second Set"), merged into
legend_tales.TALES. Same format and the same rules as legend_tales.py (read its header): the right answer at
every question is the generous one and it costs the Captain the bigger prize; never shown or hinted; each
chapter is 3 to 6 lines from the bell stopping to the Reckoning card; no amounts or digits in a spoken line; a
third item in a beat is its family-friendly wording.

Chosen with Anthony as moral dilemmas, each from an old story made nautical:
  jonah   The Passenger Who Brought the Storm   (the Book of Jonah)         sacrifice one to save the many
  bond    The Bond                              (The Merchant of Venice)    the law against mercy
  hunger  The Hungry Port                       (Les Miserables, Stone Soup) profit against relief
  robe    The Mermaid's Robe                    (the selkie, the swan maiden) freedom against benefit
  ledger  The Crimson Ledger                    (the Ring of Gyges)         power against decency
Chapters 1 and 2 of every Legend ask a question with a right answer, so two right answers earn the share.
"""

T = "teller"
P = "legend_passenger"
B = "legend_debtor"
N = "legend_robe"
C = "legend_clerk"
M = "mayor"                       # the shared Mayor speaks for Saigon: no new face needed

MORE = {
    # =====================================================================================================
    # THE PASSENGER WHO BROUGHT THE STORM (the Book of Jonah). Told by the drowned bride, who knows what it
    # is to be thrown over the side.
    # =====================================================================================================
    "jonah": {
        "title": "The Passenger Who Brought the Storm",
        "teller": "teller_drowned",
        "cast": [P],
        "start": {},
        "chapters": [
            {"id": "fare", "title": "A Passenger Who Pays Too Well", "where": None, "scene": "port",
             "start": [(None, "open")],
             "right": {"open": ("fair",)},                       # the usual fare, and the good cabin
             "nodes": {
                 "open": {
                     "beats": [
                         (T, "The bell has stopped, Captain, and a woman is on your gangway holding a purse "
                             "she can barely lift. Pretty enough to be trouble, rich enough to be worth it."),
                         (P, "Dona Ines de Albuquerque. Passage to anywhere that is not here. I will pay "
                             "three times the fare and answer no questions. Does the cabin lock from inside?",
                             "Dona Ines de Albuquerque. Passage to anywhere that is not here. I will pay "
                             "three times the fare and answer no questions. Is the cabin quiet?"),
                     ],
                     "choices": [("take", "Take the triple fare and ask nothing", "take"),
                                 ("fair", "Carry her at the usual fare", "fair"),
                                 ("refuse", "Tell her the berths are full", "refuse")]},
                 "take": {
                     "beats": [
                         (T, "You took the purse. It clinked like a clergyman's conscience, and "
                             "you slept very well on it."),
                     ],
                     "fx": [("silver", 0.8), ("flag", "paid")], "end": True},
                 "fair": {
                     "beats": [
                         (T, "You charged the usual fare and gave her the good cabin. She looked at "
                             "you as if nobody had ever done that before."),
                     ],
                     "fx": [("silver", 0.15), ("flag", "fair")], "end": True},
                 "refuse": {
                     "beats": [
                         (T, "She stood on the quay a long while with her purse. Then she took a berth "
                             "on a rotten lorcha whose skipper smelled of wine and bad decisions."),
                     ],
                     "fx": [("flag", "refused")], "end": True},
             }},
            {"id": "storm", "title": "The Storm", "where": None, "scene": "sea",
             "start": [("refused", "left"), (None, "aboard")],
             "right": {"aboard": ("hold",), "left": ("rescue",)},
             "nodes": {
                 "aboard": {
                     "beats": [
                         (T, "Three days out, Captain, and the sky is the colour of a bruise. Your crew "
                             "has noticed the storm began the hour she came aboard."),
                         (T, "They are at your cabin door with a rope and a prayer. The sea wants a "
                             "passenger, they say, and she is the only one who paid."),
                         (P, "I have done nothing but pray and tip, Captain. Is that so very like "
                             "witchcraft?"),
                     ],
                     "choices": [("throw", "Give her to the sea", "throw"),
                                 ("boat", "Set her adrift in the longboat, with water", "boat"),
                                 ("hold", "Hold her aboard and ride it out", "hold")]},
                 "throw": {
                     "beats": [
                         (T, "The sea went flat as a pressed sheet. Your crew cheered, then looked at "
                             "their boots. I know what it is to be thrown over, Captain."),
                     ],
                     "fx": [("silver", 0.5), ("flag", "threw"), ("news", "n.legend_jonah_threw")], "end": True},
                 "boat": {
                     "beats": [
                         (T, "A longboat, a barrel of water and a lantern: murder in a clean apron. "
                             "The storm eased by half, and so did your sleep."),
                     ],
                     "fx": [("hull", 0.08), ("flag", "adrift")], "end": True},
                 "hold": {
                     "beats": [
                         (P, "Thank you. Nobody has ever stood in a doorway for me.",),
                         (T, "The storm took its time and its toll. Your crew grumbled, your passenger "
                             "prayed, and nobody drowned."),
                     ],
                     "fx": [("hull", 0.2), ("lose_cargo", 0.15), ("flag", "held")], "end": True},
                 "left": {
                     "beats": [
                         (T, "A storm, Captain, and on the reef a lorcha is breaking up. A woman clings "
                             "to the mast. You turned her away yourself."),
                         (T, "You can see the wreck from your own deck, and you can see what it costs "
                             "to turn back."),
                     ],
                     "choices": [("rescue", "Turn back and take them off", "rescue"),
                                 ("pass", "Hold your course. Not your ship, not your storm", "pass")]},
                 "rescue": {
                     "beats": [
                         (P, "You came back. You, of all people."),
                         (T, "Your hull paid and your hold paid, and you took every soul off that "
                             "lorcha. One of them still had her purse."),
                     ],
                     "fx": [("hull", 0.15), ("lose_cargo", 0.10), ("flag", "rescued")], "end": True},
                 "pass": {
                     "beats": [
                         (T, "You held your course. The lorcha broke on the reef with her cook, her "
                             "skipper and one very rich woman aboard. You kept a clean hold and an "
                             "untidy conscience."),
                     ],
                     "fx": [("standing", "here", -1), ("flag", "lost")], "end": True},
             }},
            {"id": "truth", "title": "Who She Was", "where": None, "scene": "port",
             "start": [("threw", "threw"), ("adrift", "adrift"), ("held", "held"), ("rescued", "held"),
                       (None, "lost")],
             "right": {},
             "nodes": {
                 "held": {
                     "beats": [
                         (P, "I ran from my husband's creditors with his pearls in my stays, Captain. "
                             "They would have had the pearls and the stays. You gave me a door that "
                             "locked from the right side.",
                             "I ran from my husband's creditors with his pearls in my luggage, Captain. "
                             "They would have had the pearls and the luggage. You gave me a door that "
                             "locked from the right side."),
                         (T, "She pressed the pearls into your hand and her mouth to your cheek. "
                             "Honest people are so rare they should be taxed.",
                             "She pressed the pearls into your hand and her thanks to your cheek. "
                             "Honest people are so rare they should be taxed."),
                     ],
                     "fx": [("silver", 1.8), ("standing", "home", 4)], "end": True},
                 "adrift": {
                     "beats": [
                         (P, "Fishermen found a longboat, a lantern and a very cross Portuguese lady. "
                             "You owe me a passage, Captain. I will take it in silver."),
                         (T, "You paid. It was cheaper than the alternative, which was her telling "
                             "the story at every dock from here to Goa."),
                     ],
                     "fx": [("silver", -0.5), ("standing", "here", -1)], "end": True},
                 "threw": {
                     "beats": [
                         (T, "Bell stopped, Captain. There is a woman beside me with salt in her hair, "
                             "and she would like her purse back."),
                         (P, "The sea was kinder than the crew. It was only your hand on the rope "
                             "that was cold."),
                         (T, "She took her purse out of your hold, and some of your hold with it."),
                     ],
                     "fx": [("silver", -0.5), ("lose_cargo", 0.12), ("hull", 0.10)], "end": True},
                 "lost": {
                     "beats": [
                         (T, "A shawl turned up in your net off {port}, Captain, smelling of jasmine "
                             "and very faintly of guilt."),
                         (T, "You paid a priest to say a prayer for the lorcha. It was the cheapest "
                             "sleep you ever bought."),
                     ],
                     "fx": [("silver", -0.2), ("standing", "here", 1)], "end": True},
             }},
        ],
    },

    # =====================================================================================================
    # THE BOND (the Merchant of Venice, made a Singapore shipping loan). Told by the tavern singer, who has
    # drunk with both sides of every debt on the waterfront.
    # =====================================================================================================
    "bond": {
        "title": "The Bond",
        "teller": "teller_tavern",
        "cast": [B],
        "start": {"port": "singapore"},
        "chapters": [
            {"id": "paper", "title": "The Paper in Madam Wu's Books", "where": "singapore", "scene": "port",
             "start": [(None, "open")],
             "right": {"open": ("forgive",)},
             "nodes": {
                 "open": {
                     "beats": [
                         (T, "Listen close, darling. Madam Wu sells old debts by the pound, and she has "
                             "sold you a peach: the bond on Nyonya Bee-Lian's only ship."),
                         (B, "A good paper, Captain. The Mayor will enforce it to the letter. I would "
                             "so like you to enforce it to the spirit.",
                             "A good paper, Captain. The Mayor will enforce it to the letter. I would "
                             "so like you to be kind."),
                     ],
                     "choices": [("seize", "Call the bond and take her ship", "seize"),
                                 ("extend", "Give her fair terms to pay it off", "extend"),
                                 ("forgive", "Tear it up", "forgive")]},
                 "seize": {
                     "beats": [
                         (T, "The Mayor's bailiffs took her ship at dawn. Nobody loves a bailiff, but "
                             "everyone loves the captain who hires one."),
                     ],
                     "fx": [("silver", 1.5), ("standing", "singapore", -2), ("flag", "seized"),
                            ("news", "n.legend_bond_seized")], "end": True},
                 "extend": {
                     "beats": [
                         (B, "A fair rate, and you did not even blush. I could kiss the clerk who wrote "
                             "your name on this.",
                             "A fair rate, and you did not even frown. I could thank the clerk who wrote "
                             "your name on this."),
                     ],
                     "fx": [("silver", 0.5), ("flag", "extended")], "end": True},
                 "forgive": {
                     "beats": [
                         (T, "You tore it in half in front of her, and she looked at the pieces as if "
                             "they were a proposal."),
                     ],
                     "fx": [("standing", "singapore", 2), ("flag", "forgave")], "end": True},
             }},
            {"id": "stair", "title": "The Debtors' Stair", "where": None, "scene": "port",
             "start": [("seized", "seized"), ("extended", "extended"), (None, "forgave")],
             "right": {"seized": ("bail",), "extended": ("grace",), "forgave": ("stand",)},
             "nodes": {
                 "seized": {
                     "beats": [
                         (T, "Debtors' prison, Captain, and one inmate has your name on her lips. Not "
                             "the pretty way, either."),
                         (B, "I lost my ship and my staff. I would like to keep my dignity, and the "
                             "stairs are very steep."),
                     ],
                     "choices": [("bail", "Pay her bail from your own purse", "bail"),
                                 ("leave", "Let the law finish its business", "leave")]},
                 "bail": {
                     "beats": [
                         (B, "You bought me out of my own cell. Nobody will believe it. I shall tell "
                             "everyone."),
                     ],
                     "fx": [("silver", -0.7), ("flag", "bailed")], "end": True},
                 "leave": {
                     "beats": [
                         (T, "The law finished its business. It is very thorough, and it sends no "
                             "flowers."),
                     ],
                     "fx": [("standing", "singapore", -2), ("flag", "left")], "end": True},
                 "extended": {
                     "beats": [
                         (T, "Bee-Lian missed a payment, Captain. A squall took her ship, she says. "
                             "A gambling den took it, everyone else says."),
                     ],
                     "choices": [("grace", "Give her another season", "grace"),
                                 ("collect", "Collect, and let the Mayor's men do the talking", "collect")]},
                 "grace": {
                     "beats": [
                         (B, "A season. You are either a saint or a very patient shark."),
                     ],
                     "fx": [("silver", -0.3), ("flag", "graced")], "end": True},
                 "collect": {
                     "beats": [
                         (T, "The Mayor's men were polite, which is how you know they were terrifying."),
                     ],
                     "fx": [("silver", 0.8), ("standing", "singapore", -2), ("flag", "collected")],
                     "end": True},
                 "forgave": {
                     "beats": [
                         (T, "Bee-Lian is thriving, and a rival has noticed. He is spreading the story "
                             "that her torn bond was a forgery. A court is called."),
                         (B, "I have no friends in that court but you, Captain. Come and stand where "
                             "they can see you.",
                             "I have no friends in that court but you, Captain. Come and sit where "
                             "they can see you."),
                     ],
                     "choices": [("stand", "Stand beside her in court", "stand"),
                                 ("stay", "Stay out of it", "stay")]},
                 "stand": {
                     "beats": [
                         (T, "You stood. The rival muttered something about foreigners and filth, and "
                             "the judge's face did the rest."),
                     ],
                     "fx": [("silver", -0.3), ("standing", "singapore", 2), ("flag", "stood")], "end": True},
                 "stay": {
                     "beats": [
                         (T, "You stayed home with a good book. Bee-Lian won anyway, which is exactly "
                             "what she will remember."),
                     ],
                     "fx": [("flag", "stayed")], "end": True},
             }},
            {"id": "day", "title": "The Day the Paper Came Due", "where": None, "scene": "port",
             "start": [("bailed", "bailed"), ("left", "left"), ("graced", "graced"),
                       ("collected", "collected"), ("stood", "stood"), (None, "stayed")],
             "right": {},
             "nodes": {
                 "bailed": {
                     "beats": [
                         (B, "I have a new ship, Captain, and a shelf with your name on it. Take what "
                             "is on it."),
                         (T, "A hold of tea, a handful of silver, and a friend in Singapore. Not "
                             "bad for a bail bond."),
                     ],
                     "fx": [("cargo", "tea", 1.2), ("standing", "singapore", 4)], "end": True},
                 "left": {
                     "beats": [
                         (T, "Bee-Lian came out of the Stair thin and quiet, and now she sells "
                             "information. Yours, mostly."),
                     ],
                     "fx": [("standing", "singapore", -3), ("lose_cargo", 0.08)], "end": True},
                 "graced": {
                     "beats": [
                         (B, "Paid in full, Captain, and a little over, for patience. A merchant who "
                             "waits is a rarer thing than a pearl."),
                     ],
                     "fx": [("silver", 1.3), ("standing", "singapore", 3)], "end": True},
                 "collected": {
                     "beats": [
                         (T, "She paid every last coin, and told every merchant on the waterfront how "
                             "you do business. They noticed."),
                     ],
                     "fx": [("standing", "singapore", -2), ("silver", 0.3)], "end": True},
                 "stood": {
                     "beats": [
                         (B, "I am the richest woman on this quay and you are the only one who "
                             "never asked me for anything. Take the ledger. Take the tea. Take me out "
                             "to supper.",
                             "I am the richest woman on this quay and you are the only one who "
                             "never asked me for anything. Take the ledger. Take the tea. Take a "
                             "friend to supper."),
                     ],
                     "fx": [("cargo", "tea", 1.0), ("silver", 1.2), ("standing", "singapore", 5)],
                     "end": True},
                 "stayed": {
                     "beats": [
                         (B, "I did not forget the day you tore my paper. I only forgot to send a "
                             "cake. Here is the cake."),
                     ],
                     "fx": [("silver", 0.4), ("standing", "singapore", 1)], "end": True},
             }},
        ],
    },

    # =====================================================================================================
    # THE HUNGRY PORT (Les Miserables and Stone Soup, in Saigon). Told by the temple keeper, who has fed the
    # shrine's steps through three famines and knows the price of rice in prayer. The Mayor answers.
    # =====================================================================================================
    "hunger": {
        "title": "The Hungry Port",
        "teller": "teller_temple",
        "cast": [M],
        "start": {"port": "saigon"},
        "chapters": [
            {"id": "famine", "title": "The Rice Runs Out", "where": "saigon", "scene": "port",
             "start": [(None, "open")],
             "right": {"open": ("cost", "give")},
             "nodes": {
                 "open": {
                     "beats": [
                         (T, "Sit, Captain. The paddies failed, and Saigon is thin. The dealers have "
                             "noticed you have a hold, and so has the Mayor."),
                         (M, "The dealers offer you five times the price. I offer only gratitude and a "
                             "little harbour goodwill. Both are hard to eat, and both keep."),
                     ],
                     "choices": [("sell", "Sell to the dealers at the famine price", "sell"),
                                 ("cost", "Sell to the Mayor at cost", "cost"),
                                 ("give", "Give the Mayor what she needs", "give")]},
                 "sell": {
                     "beats": [
                         (T, "The dealers paid well, in coin and in smiles. The streets were quiet that "
                             "night, in the way a held breath is quiet."),
                     ],
                     "fx": [("silver", 1.4), ("standing", "saigon", -3), ("flag", "sold")], "end": True},
                 "cost": {
                     "beats": [
                         (M, "At cost. You are either a fool or a saint, Captain, and I find the "
                             "difference is only the quality of the wine."),
                     ],
                     "fx": [("silver", 0.2), ("standing", "saigon", 4), ("flag", "fed")], "end": True},
                 "give": {
                     "beats": [
                         (M, "You gave it. Nobody gives the Mayor anything, Captain, except trouble. "
                             "I do not know where to put my hands.",
                             "You gave it. Nobody gives the Mayor anything, Captain, except trouble. "
                             "I do not know where to put the thank-you."),
                     ],
                     "fx": [("silver", -0.3), ("standing", "saigon", 7), ("flag", "fed")], "end": True},
             }},
            {"id": "hoard", "title": "The Warehouse That Was Not Empty", "where": None, "scene": "port",
             "start": [(None, "open")],
             "right": {"open": ("report",)},
             "nodes": {
                 "open": {
                     "beats": [
                         (T, "A rumour, Captain, in the way of all rumours. A rival has three "
                             "warehouses of rice she will not release until the price is silly."),
                         (M, "I have no proof, and the law protects her stock. But you have eyes, and "
                             "a lantern, and she is not going to invite me to look."),
                     ],
                     "choices": [("report", "Tell the Mayor what is behind the doors", "report"),
                                 ("buyin", "Buy a share of the hoard and wait for the price", "buyin"),
                                 ("ignore", "It is none of your business", "ignore")]},
                 "report": {
                     "beats": [
                         (M, "Three warehouses, and a very surprised merchant. Thank you, Captain. "
                             "I shall be at my finest at her trial."),
                     ],
                     "fx": [("silver", -0.4), ("standing", "saigon", 5), ("flag", "reported")], "end": True},
                 "buyin": {
                     "beats": [
                         (T, "You bought into the hoard, and the price went where hoarders pray it "
                             "will. The city noticed whose name was on the bill of sale."),
                     ],
                     "fx": [("silver", 1.6), ("standing", "saigon", -4), ("flag", "hoarded")], "end": True},
                 "ignore": {
                     "beats": [
                         (T, "You minded your own business. It is a thriving trade, though a lonely "
                             "one."),
                     ],
                     "fx": [("flag", "ignored")], "end": True},
             }},
            {"id": "noodles", "title": "The Great Noodle Disaster", "where": None, "scene": "port",
             "start": [("fed", "fed"), (None, "unfed")],
             "right": {"disaster": ("help",)},
             "nodes": {
                 "fed": {
                     "beats": [
                         (T, "Saigon throws its feast, Captain, and you are the guest of honour. The "
                             "cooks have built a cauldron of noodles as long as the harbour wall."),
                         (M, "It has been boiling for two days. I did not ask how."),
                     ],
                     "goto": "disaster"},
                 "unfed": {
                     "beats": [
                         (T, "Saigon throws its feast, Captain, and you are not on the list. The cooks "
                             "have built a cauldron of noodles as long as the harbour wall."),
                         (M, "It has been boiling for two days. I did not ask how."),
                     ],
                     "goto": "disaster"},
                 "disaster": {
                     "beats": [
                         (T, "The cauldron gave way. A river of noodles came down the quay, taking "
                             "dignitaries, drays and one very surprised bishop."),
                     ],
                     "choices": [("help", "Wade in and help clear the quay", "help"),
                                 ("leave", "Sail out before the noodles reach the ship", "leave")]},
                 "help": {
                     "beats": [
                         (M, "You are up to your knees in noodles for a stranger's feast. Come back "
                             "when you are clean, Captain. I will have a hot bath and a better "
                             "reward waiting.",
                             "You are up to your knees in noodles for a stranger's feast. Come back "
                             "when you are clean, Captain. I will have a good meal and a better "
                             "reward waiting."),
                     ],
                     "fx": [("hull", 0.02), ("silver", 0.6), ("standing", "saigon", 5)], "end": True},
                 "leave": {
                     "beats": [
                         (T, "You sailed. The noodles reached the dock a minute later, and your deck "
                             "was spared, though not your reputation."),
                     ],
                     "fx": [("standing", "saigon", -1)], "end": True},
             }},
        ],
    },

    # =====================================================================================================
    # THE MERMAID'S ROBE (the selkie wife, the swan maiden, made a robe of sea-silk). Told by the temple
    # keeper, who tends the sea goddess whose daughters these are.
    # =====================================================================================================
    "robe": {
        "title": "The Mermaid's Robe",
        "teller": "teller_temple",
        "cast": [N],
        "start": {"port": "foochow"},
        "chapters": [
            {"id": "rocks", "title": "The Robe on the Rocks", "where": "foochow", "scene": "sea",
             "start": [(None, "open")],
             "right": {"open": ("return",)},
             "nodes": {
                 "open": {
                     "beats": [
                         (T, "Light a stick of incense, Captain. Your bosun found a robe of sea-silk on "
                             "the rocks beyond the temple, folded as if someone had only just stepped "
                             "out of it."),
                         (N, "That is mine, sailor. I was only swimming. Hand it over, and do not "
                             "look at the rest of me while you decide.",
                             "That is mine, sailor. I was only swimming. Hand it over, and look "
                             "politely at the sea while you decide."),
                     ],
                     "choices": [("hide", "Keep the robe. She can sail with you", "hide"),
                                 ("ransom", "Hand it back for a price", "ransom"),
                                 ("return", "Hand it back with your apologies", "return")]},
                 "hide": {
                     "beats": [
                         (N, "Fine. I will steer your ship, since I have no choice. The stars are my "
                             "cousins, Captain, and they gossip."),
                     ],
                     "fx": [("flag", "kept")], "end": True},
                 "ransom": {
                     "beats": [
                         (N, "A price for my own skin. How very commercial of you. Here: silver, and "
                             "my opinion of you."),
                     ],
                     "fx": [("silver", 0.7), ("flag", "ransomed")], "end": True},
                 "return": {
                     "beats": [
                         (N, "Most men run. You gave it back, and then you turned away. Do you know "
                             "how rare that is? Tell the goddess I owe her a good word."),
                     ],
                     "fx": [("standing", "foochow", 3), ("flag", "freed")], "end": True},
             }},
            {"id": "wake", "title": "The Best Navigator in the China Seas", "where": None, "scene": "sea",
             "start": [("kept", "kept"), ("ransomed", "ransomed"), (None, "freed")],
             "right": {"kept": ("free",), "ransomed": ("refund",), "freed": ("carry",)},
             "nodes": {
                 "kept": {
                     "beats": [
                         (T, "A season of fair winds, Captain. Every squall slid off your bow like a "
                             "rumour."),
                         (N, "Another storm dodged. You are very lucky and I am very locked. Which of "
                             "us do you think is the happier?"),
                     ],
                     "choices": [("lock", "Keep the robe locked away", "lock"),
                                 ("free", "Give her the robe", "free")]},
                 "lock": {
                     "beats": [
                         (N, "Then I will keep steering. But I will not warm your cabin. A navigator is "
                             "not a hearth.",
                             "Then I will keep steering. But I will not smile at your jokes. A "
                             "navigator is not a friend."),
                     ],
                     "fx": [("silver", 1.2), ("flag", "locked")], "end": True},
                 "free": {
                     "beats": [
                         (N, "You are giving it back. After all this time. I do not know how to say "
                             "thank you without it sounding like an offer."),
                     ],
                     "fx": [("silver", 0.2), ("flag", "freed2")], "end": True},
                 "ransomed": {
                     "beats": [
                         (N, "You sold me my own robe at a good price, Captain. Do you know what the "
                             "sea thinks of bargain hunters?"),
                         (T, "She is not threatening you. She is only asking, and it is the asking "
                             "that frightens."),
                     ],
                     "choices": [("refund", "Refund half of it", "refund"),
                                 ("keepit", "Keep what she paid", "keepit")]},
                 "refund": {
                     "beats": [
                         (N, "Half. It is more than most would give, and less than I deserved. I will "
                             "take it."),
                     ],
                     "fx": [("silver", -0.35), ("flag", "fair")], "end": True},
                 "keepit": {
                     "beats": [
                         (N, "Keep it, then. The sea keeps accounts of its own."),
                     ],
                     "fx": [("hull", 0.08), ("flag", "greedy")], "end": True},
                 "freed": {
                     "beats": [
                         (N, "A word, Captain. My sister's net is snagged on the shoals beyond {port}. "
                             "It would cost you a detour and the good half of a morning."),
                         (T, "A drowned lantern in her hand, a plea in her voice. She is not asking "
                             "for the whole sea, only the small part."),
                     ],
                     "choices": [("carry", "Carry the message, whatever the detour", "carry"),
                                 ("forget", "Wave and sail on", "forget")]},
                 "carry": {
                     "beats": [
                         (N, "You went. Of course you went. Take this: my sister's thanks, folded in "
                             "silk."),
                     ],
                     "fx": [("silver", -0.2), ("flag", "carried")], "end": True},
                 "forget": {
                     "beats": [
                         (T, "You waved, and you sailed. A net is a net, and a sister is a sister, "
                             "and somewhere a woman is still tangled."),
                     ],
                     "fx": [("flag", "forgot")], "end": True},
             }},
            {"id": "silk", "title": "Where the Robe Went", "where": None, "scene": "port",
             "start": [("locked", "locked"), ("freed2", "freed2"), ("fair", "fair"), ("greedy", "greedy"),
                       ("carried", "carried"), (None, "forgot")],
             "right": {},
             "nodes": {
                 "locked": {
                     "beats": [
                         (N, "I found the robe in your own chest, Captain, on a night when the moon "
                             "was kind. I took it. I took a little of your hold as well. Navigators "
                             "must eat."),
                     ],
                     "fx": [("lose_cargo", 0.12), ("hull", 0.08)], "end": True},
                 "freed2": {
                     "beats": [
                         (N, "I came back, Captain. By choice. Nobody has ever come back to the man "
                             "who opened the door.",
                             "I came back, Captain. By choice. Nobody has ever come back to the "
                             "person who opened the door."),
                         (T, "A season of her company, free, and the sea itself on your side. The "
                             "goddess approves, in her fashion."),
                     ],
                     "fx": [("silver", 1.6), ("standing", "home", 4), ("standing", "foochow", 3)],
                     "end": True},
                 "fair": {
                     "beats": [
                         (N, "Square, Captain. You gave me back what you took, and I have given you "
                             "a bale of the good silk. Keep your hands to yourself."),
                     ],
                     "fx": [("cargo", "silk", 0.8)], "end": True},
                 "greedy": {
                     "beats": [
                         (N, "The sea kept your price and added its interest. You will find it in "
                             "your hull, in the mornings."),
                     ],
                     "fx": [("hull", 0.10), ("lose_cargo", 0.10)], "end": True},
                 "carried": {
                     "beats": [
                         (N, "My sister is free, and she sends her love and a hold of sea-silk. She "
                             "would send herself, but she is shy."),
                     ],
                     "fx": [("cargo", "silk", 1.1), ("standing", "home", 3)], "end": True},
                 "forgot": {
                     "beats": [
                         (N, "I untangled her myself, Captain. It took all night. I remember who "
                             "waved."),
                     ],
                     "fx": [("standing", "here", -1)], "end": True},
             }},
        ],
    },

    # =====================================================================================================
    # THE CRIMSON LEDGER (the Ring of Gyges: a power that costs nothing to use). The game's own title, told by
    # the tavern singer who started half the rumours in it.
    # =====================================================================================================
    "ledger": {
        "title": "The Crimson Ledger",
        "teller": "teller_tavern",
        "cast": [C],
        "start": {},
        "chapters": [
            {"id": "page", "title": "A Page in the Fish Market", "where": None, "scene": "port",
             "start": [(None, "open")],
             "right": {"open": ("return",)},
             "nodes": {
                 "open": {
                     "beats": [
                         (T, "A fishwife wrapped your mullet in a page torn from a ledger, darling. "
                             "Fine hand, red ink, and a column of names that owe more than they can "
                             "bear."),
                         (C, "Hoa, clerk to a dead merchant, and that page is mine, Captain. His book of who owes what and "
                             "why they would pay to keep it quiet. Most of it is scattered. I am "
                             "collecting it, one fishwife at a time."),
                     ],
                     "choices": [("use", "Read it and write to the names on it", "use"),
                                 ("sell", "Sell the page to the highest bidder", "sell"),
                                 ("return", "Give it to the clerk and ask nothing", "return")]},
                 "use": {
                     "beats": [
                         (T, "You wrote four letters, and by the end of the week four people were "
                             "sending flowers. Nobody sends flowers out of love."),
                     ],
                     "fx": [("silver", 1.2), ("standing", "here", -3), ("flag", "used")], "end": True},
                 "sell": {
                     "beats": [
                         (T, "A man in a good hat paid in advance and asked no questions, which is the "
                             "worst sort of buyer."),
                     ],
                     "fx": [("silver", 0.9), ("flag", "sold")], "end": True},
                 "return": {
                     "beats": [
                         (C, "No bargaining? No price? You must be the first sailor to hand over "
                             "something and keep your hands to yourself.",
                             "No bargaining? No price? You must be the first sailor to hand over "
                             "something and keep your word."),
                     ],
                     "fx": [("silver", 0.1), ("flag", "returned")], "end": True},
             }},
            {"id": "pages", "title": "The Pages in Three Ports", "where": None, "scene": "port",
             "start": [("used", "used"), ("sold", "sold"), (None, "returned")],
             "right": {"used": ("confess",), "sold": ("amends",), "returned": ("warn",)},
             "nodes": {
                 "used": {
                     "beats": [
                         (T, "Someone you squeezed has hired a lawyer, a thug and a poet, Captain. The "
                             "poet is the one to fear."),
                     ],
                     "choices": [("confess", "Burn the letters and make amends", "confess"),
                                 ("double", "Squeeze the lawyer too", "double")]},
                 "confess": {
                     "beats": [
                         (T, "You burned the letters and returned the silver. The poet wrote a sonnet "
                             "about you. It was not flattering, but it was warm."),
                     ],
                     "fx": [("silver", -0.6), ("flag", "c_ok")], "end": True},
                 "double": {
                     "beats": [
                         (T, "The lawyer paid, and the thug collected. Your hull still has the marks "
                             "of his boots."),
                     ],
                     "fx": [("silver", 1.0), ("hull", 0.10), ("flag", "c_bad")], "end": True},
                 "sold": {
                     "beats": [
                         (T, "The man in the good hat used your page to ruin an honest chandler. His "
                             "widow is on your gangway with a lantern and the bill of sale."),
                     ],
                     "choices": [("amends", "Buy the page back and burn it", "amends"),
                                 ("shrug", "Say business is business", "shrug")]},
                 "amends": {
                     "beats": [
                         (C, "You bought it back at his price, and burned it in front of her. That is "
                             "the only honest bonfire I have ever seen."),
                     ],
                     "fx": [("silver", -0.7), ("flag", "s_ok")], "end": True},
                 "shrug": {
                     "beats": [
                         (T, "Business is business, you said. She said nothing, which in a widow is "
                             "louder than a curse."),
                     ],
                     "fx": [("standing", "here", -2), ("flag", "s_bad")], "end": True},
                 "returned": {
                     "beats": [
                         (C, "Page seven, Captain. It lists the Mayor of {port} and every captain who "
                             "ever bribed her. Some of them are dangerous, and all of them are "
                             "unaware."),
                         (T, "She wants to warn them before their enemies read the same page."),
                     ],
                     "choices": [("warn", "Help her warn them", "warn"),
                                 ("hush", "Say nothing. It is not your business", "hush")]},
                 "warn": {
                     "beats": [
                         (C, "You carried the news yourself, and none of them knew whether to thank "
                             "you or throw you out."),
                     ],
                     "fx": [("silver", -0.4), ("standing", "here", 2), ("flag", "r_ok")], "end": True},
                 "hush": {
                     "beats": [
                         (T, "You kept quiet. It is a very fine trade, silence. It pays, mostly in "
                             "regret."),
                     ],
                     "fx": [("flag", "r_bad")], "end": True},
             }},
            {"id": "last", "title": "The Last Page", "where": None, "scene": "port",
             "start": [("c_ok", "good"), ("s_ok", "good"), ("r_ok", "good"), (None, "bad")],
             "right": {"good": ("burn",)},
             "nodes": {
                 "good": {
                     "beats": [
                         (T, "Hoa lays the last page on your chart table, Captain, and the Crimson "
                             "Ledger lies open at last, fat with every secret on the coast."),
                         (C, "It is yours. Burn it, and nobody owes anybody anything. Keep it, and "
                             "everybody owes you everything. Choose the way you have been choosing."),
                     ],
                     "choices": [("burn", "Burn the Crimson Ledger", "burn"),
                                 ("keep", "Keep the Ledger and everything in it", "keep")]},
                 "burn": {
                     "beats": [
                         (T, "It burned red, then gold, then ash, and a hundred debts went up the "
                             "chimney with it. The whole coast breathed out."),
                     ],
                     "fx": [("silver", 0.5), ("standing", "home", 4), ("standing", "here", 3)],
                     "end": True},
                 "keep": {
                     "beats": [
                         (T, "You kept it, and it kept you. Every name in it was a door, and every "
                             "door was a favour. Nobody in the Crimson Ledger can say no to you now, "
                             "and nobody will say yes without remembering."),
                     ],
                     "fx": [("silver", 2.0), ("standing", "here", -4), ("flag", "kept")], "end": True},
                 "bad": {
                     "beats": [
                         (T, "The last page never came, Captain. The Ledger went to someone with a "
                             "worse grudge than yours, and she has started with the names you "
                             "squeezed."),
                         (C, "I told you it was dangerous. I did not tell you it was personal."),
                     ],
                     "fx": [("silver", -0.5), ("hull", 0.10), ("standing", "here", -3)], "end": True},
             }},
        ],
    },
}
