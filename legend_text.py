"""Wording for the Legends (legend.py). Merged into strings.EN / strings.FAMILY at import, so every line can be
edited in Admin > Language & Text (group "legend"; the log, news, confirmations and rule messages keep their
usual l. / n. / m. / e. groups). The Legends' own lines come from legend_tales.py.

House voice (house_voice.py) for anything said aloud. Planned 20 Nov 2026: project doc "SeaTrader Legends Library"."""
import legend_tales

EN = {
    # ---- the story screen ---------------------------------------------------------------------------------
    "legend.eyebrow": "A Legend",
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
}

FAMILY = {}

_en, _fam, SPOKEN = legend_tales.text_keys()
EN.update(_en)
FAMILY.update(_fam)

# Lines never read aloud by the Captain's Log (the story screen tells the Legend itself).
SILENT = ["l.legend", "l.legend_end", "m.legend_choice", "m.legend_done"]
