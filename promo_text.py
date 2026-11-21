"""Wording for the Promotion Story (web/promotion.js, 20 Nov 2026). Merged into strings.EN / strings.FAMILY at
import, so every line can be edited in Admin > Language & Text (group "promo"). The captions are narration and
are never spoken; the Mayor's own congratulations stay m.promote.N / m.promote_top.N (strings.py), read by
her voice. The ceremony's older keys (fleet.promotion_*) are reused where they still fit.

Words in {braces}: {port} {name} {firm} {rank}."""

EN = {
    # ---- screen 1: the Mayor sends for you -------------------------------------------------------------
    "promo.title.summons": "Summoned",
    "promo.summons.0": "A boy with a sealed note finds you on the wharf. The Mayor of {port} would like a word, Captain. Now, if it is not too much trouble.",
    "promo.summons.1": "The bell at the Mayor's Parlour rings once, and every clerk in {port} looks up at you. Something is about to be signed.",
    "promo.summons.2": "Word has run along the quay faster than any clipper. The Mayor of {port} has sent for the captain of {firm}.",
    "promo.summons.3": "You are shown into the Parlour past a row of clerks who all, suddenly, find their ledgers fascinating.",
    "promo.summons.4": "The Mayor of {port} is standing when you come in. She never stands. Something waits on the table, under a cloth, with a ribbon.",
    "promo.summons.5": "The best chair in {port} has been dusted and the good tea has been brought out. This is not a visit about taxes.",
    "promo.summons.6": "Your name has been passed from desk to desk all week, Captain {name}. Today it reaches the top of the pile.",
    "promo.summons.7": "Candles lit, ink warmed, wax melting on a brass spoon. The Mayor of {port} has been waiting for you.",
    # ---- screen 2: the commission is stamped ---------------------------------------------------------
    "promo.rank.0": "The wax is pressed, the ribbon is tied and the register is signed. {name} of {firm} is commissioned {rank}.",
    "promo.rank.1": "The Mayor's pen scratches once across the page, and the China Seas have a new {rank}.",
    "promo.rank.2": "Ink, wax and a very fine seal. It is done, it is written, and it says {rank}.",
    "promo.rank.3": "The commission is stamped in front of the whole Parlour. Captain {name}, {rank} of {port}, and not a day too soon.",
    "promo.rank.4": "She turns the register to face you. {rank}, it says, and your name sits beside it in her own hand.",
    "promo.rank.5": "A new rank, a new seal, and a brand new reason for every rival in {port} to sulk. You are {rank}, Captain.",
    "promo.rank.6": "The seal glints in the lamplight as the wax cools. {firm} has a new {rank}, and {port} has a new story to tell.",
    "promo.rank.7": "Rise, Captain {name}. The register says {rank}, and the register does not make mistakes.",
    # ---- screen 3 and the card ------------------------------------------------------------------------
    "promo.title.words": "The Mayor's congratulations",
    "promo.story.next": "Tap to go on",
    "promo.cost.citation": "The citation",
    "promo.cost.road": "The road ahead",
    "promo.tile.ports": "Ports visited",
    "promo.tile.won": "Battles won",
}

# Nothing here needs a cleaner version: the captions are narration and already family-friendly.
FAMILY = {}

BANKS = ("promo.summons", "promo.rank")
