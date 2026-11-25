"""Wording for the Legends (legend.py). Merged into strings.EN / strings.FAMILY at import, so every line can be
edited in Admin > Language & Text (group "legend"; the log, news, confirmations and rule messages keep their
usual l. / n. / m. / e. groups). The Legends' own lines come from legend_tales.py.

House voice (house_voice.py) for anything said aloud. Planned 20 Nov 2026: project doc "SeaTrader Legends Library"."""
import legend_tales

EN = {
    # ---- the story screen ---------------------------------------------------------------------------------
    "legend.eyebrow": "A Legend",
    "legend.epic.eyebrow": "A Legend of the China Seas",
    "legend.chapter": "Chapter {n} of {of}",
    "legend.choose": "What do you do, Captain?",
    "legend.hint": "Tap to go on",
    "legend.told_by": "Told by {name}",
    "legend.btn_reckon": "The reckoning",
    "legend.btn_done": "Back to the deck",
    "legend.btn_done_more": "Ring the bell",
    # ---- the reckoning card -------------------------------------------------------------------------------
    "legend.reck.eyebrow": "A Legend · {title}",
    "legend.reck.lead": "No time has passed. The bell finishes its swing.",
    "legend.reck.more": "This Legend is not finished with you.",
    "legend.reck.over": "This Legend is told.",
    "legend.reck.gain": "What it brought you",
    "legend.reck.cost": "What it cost you",
    "legend.reck.none": "Nothing you can count. Yet.",
    "legend.reck.net": "On the ledger",
    "legend.tile.chapter": "Chapter",
    "legend.tile.silver": "Silver",
    "legend.tile.cargo": "Cargo",
    "legend.tile.standing": "Standing",
    "legend.fx.silver_up": "Silver gained: {amount}",
    "legend.fx.silver_down": "Silver paid: {amount}",
    "legend.fx.debt": "Put on Madam Wu's books: {amount}",
    "legend.fx.cargo_up": "Loaded: {qty} {good}",
    "legend.fx.cargo_down": "Lost from the hold: {goods}",
    "legend.fx.cargo_none": "Nothing in the hold to lose",
    "legend.fx.hull": "Hull lost across the fleet: {amount}",
    "legend.fx.standing_up": "Standing in {port}: +{n}",
    "legend.fx.standing_down": "Standing in {port}: −{n}",
    # ---- Captain's log, news, confirmations, rule messages ----------------------------------------------------
    "l.legend": "A Legend: {title}. {chapter}.",
    "l.legend_end": "The Legend of {title} is told.",
    "m.legend_choice": "So be it.",
    "m.legend_done": "The bell finishes its swing.",
    "e.legend_none": "There is no Legend to answer, Captain.",
    "e.legend_choice": "That is not one of the roads, Captain.",
    "e.legend_first": "The story is not finished, Captain. Hear it out.",
    "n.legend_palace_sold": "A collector of curiosities aged three hundred years in a single night. Nagasaki is "
                            "asking who sold her the box.",
    "n.legend_jonah_threw": "A storm that broke in a minute, and a lady who was not on the passenger list when the "
                            "ship came home. {firm} has no comment, and the crew has several.",
    "n.legend_bond_seized": "A Singapore merchant woman lost her only ship to a bond held by {firm}. The waterfront "
                            "says the paper was legal, and that is the whole of what it says.",
    # ---- The last two shares (honour.py, 21 Nov 2026; project doc "SeaTrader Last Two Shares") -----------------
    # A share earned from Li Yue's Flag or from a Legend tells a quick story of its own on the Legend's stage
    # (web/legend.js): page one is the share and one spoken line, page two a small result panel beside a key
    # picture. Kept here, beside the Legends' wording, so they are edited in the same Admin group.
    "legend.share.eyebrow": "A port share",
    "legend.share.flag.title": "Li Yue's Flag",
    "legend.share.flag.sub": "{pirate}'s war fleet, sunk",
    "legend.share.legend.title": "The Legend's Share",
    "legend.share.deed.big": "One Port Share",
    "legend.share.deed.count": "Share {earned} of {cap}",
    "legend.share.deed.safe": "Never to be seized",
    "legend.share.btn_next": "How you earned it",
    "legend.share.btn_done": "Back to the deck",
    "legend.share.result.eyebrow": "A port share earned",
    "legend.share.result.lead.flag": "Her colours are yours, and a share with them.",
    "legend.share.result.lead.legend": "You chose well. The sea keeps good books.",
    "legend.share.result.how.flag": "The fleets you sank",
    "legend.share.result.how.legend": "What you chose",
    "legend.share.flag.row": "{n} war junks sunk off {port}",
    "legend.share.flag.row_sea": "{n} war junks sunk",
    "legend.share.legend.row": "Chapter {n} · {chapter}",
    "legend.share.tile.earned": "Shares earned",
    "legend.share.tile.free": "Still to place",
    "legend.share.result.place": "Place it on Port > Services in any port.",
    "legend.share.result.safe": "The moneylender can never seize this share.",
    "legend.share.picture.flag": "The war fleet, going down",
    # One spoken line on page one, from the bank of whoever hands the share over: Admiral Li Yue for her flag,
    # the Legend's storyteller for a Legend's share ("any" when a storyteller has no bank). House voice
    # (house_voice.HOUSE_STYLE): the fact plain, a wink riding on it, never explicit. No amounts.
    "legend.share.say.flag.0": "You have sunk my fleet too often to call it luck. Take my flag, Captain, and the port "
                               "share that rides with it. Hang it over your bed. I want to be the last thing you see at night.",
    "legend.share.say.flag.1": "My flag, Captain, and a port share with it. I have never been boarded before. "
                               "Do be gentle with the silk.",
    "legend.share.say.flag.2": "Take the flag. Take the port share it buys you. Li Yue pays her debts, darling, "
                               "and she always comes back for what she has lent.",
    "legend.share.say.flag.3": "A port share and my colours, Captain. You wore me down. Few have the stamina.",
    "legend.share.say.teller_temple.0": "You were good when you thought nobody was looking, Captain. The sea was looking. "
                                        "So was I. She has written a port share in your name.",
    "legend.share.say.teller_temple.1": "A port share, Captain, from the sea's own ledger. I read this page long ago. "
                                        "I did so enjoy watching you earn it.",
    "legend.share.say.teller_tavern.0": "A port share, Captain, signed by the sea herself! You did the decent thing "
                                        "when it cost you. I've known sailors who couldn't manage that with the lamp out.",
    "legend.share.say.teller_tavern.1": "The sea is paying you a port share, darling. Turns out behaving yourself is "
                                        "worth something. Don't tell my regulars. It would ruin them.",
    "legend.share.say.teller_drowned.0": "The bell has stopped again, Captain, and this time I come bearing gifts. "
                                         "A port share, from the sea, for choosing well. She doesn't give herself "
                                         "to just anyone. Neither do I.",
    "legend.share.say.teller_drowned.1": "You chose well, darling, and the sea has put a port share in your name. "
                                         "I kept it for you against my heart. Mind your fingers. It is still cold.",
    "legend.share.say.any.0": "You chose well, Captain. The sea has put a port share in your name, and she does not "
                              "open her books for just anyone.",
    "l.honour_flag": "Li Yue's flag is yours, and {n} port share{s} with it ({earned} of {cap}). Place it on "
                     "Port > Services in any port. Still to place: {free}.",
    "l.honour_legend": "A Legend has paid you {n} port share{s} ({earned} of {cap}). Place it on Port > Services "
                       "in any port. Still to place: {free}.",
    "l.honour_kept": "The moneylender's clerks could not touch {n} share{s}: {ports}. An honour is not hers to take.",
    "n.honour_flag": "{name} of {firm} has taken {pirate}'s own flag. The whole coast is talking.",
    "m.honour_done": "Back to the deck, Captain.",
    "e.honour_none": "There is no share story to close, Captain.",
}

# The family-friendly wording of the share story's spoken lines: the wit stays, the innuendo goes.
FAMILY = {
    "legend.share.say.flag.0": "You have sunk my fleet too often to call it luck. Take my flag, Captain, and the port "
                               "share that rides with it. Hang it in your cabin, and remember who gave it up.",
    "legend.share.say.flag.1": "My flag, Captain, and a port share with it. Nobody has ever taken it before. "
                               "Do be careful with the silk.",
    "legend.share.say.flag.3": "A port share and my colours, Captain. You wore my fleet down. Few have the patience.",
    "legend.share.say.teller_tavern.0": "A port share, Captain, signed by the sea herself! You did the decent thing "
                                        "when it cost you. I've known sailors who couldn't manage that on a dare.",
    "legend.share.say.teller_drowned.0": "The bell has stopped again, Captain, and this time I come bearing gifts. "
                                         "A port share, from the sea, for choosing well. She doesn't open her "
                                         "books for just anyone.",
    "legend.share.say.teller_drowned.1": "You chose well, darling, and the sea has put a port share in your name. "
                                         "I kept it safe for you. Mind your fingers. It is still cold.",
}

_en, _fam, SPOKEN = legend_tales.text_keys()
EN.update(_en)
FAMILY.update(_fam)

# Lines never read aloud by the Captain's Log (the story screen tells the Legend itself).
SILENT = ["l.legend", "l.legend_end", "m.legend_choice", "m.legend_done",
          # the share story (honour.py) tells its own news too
          "l.honour_flag", "l.honour_legend", "m.honour_done"]
