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
    # ---- the certificate on screen 4 (23 Nov 2026) --------------------------------------------------------
    "promo.cert.game": "Crimson Ledger",
    "promo.cert.kind": "Certificate of Commission",
    "promo.cert.note": "A word from the Mayor",
    "promo.cert.key": "With the Key to the Mayor's Bedchamber. Knock twice, Captain.",
    "promo.cert.ring": "Mayor of {port} · Commissioned · ",
    # ---- Cargo Tiers: the dealers close out the old stock (25 Nov 2026) -----------------------------------------
    # Narration, never spoken. l.tier_buyout / l.tier_step are the Captain's Log lines (shown, not read aloud).
    "promo.tier.title": "The market turns",
    "promo.tier.open.0": "A boy with a sealed note finds you on the wharf. The old dealers of {port} have closed their books on you, Captain, and the Mayor would like to explain why.",
    "promo.tier.open.1": "The Mayor of {port} has sent for the captain of {firm}. Something about the dealers, and something about a better class of cargo.",
    "promo.tier.open.2": "The cheap and cheerful goods have been wheeled out of the back door. The Mayor of {port} wants a word before the new stock comes in the front.",
    "promo.tier.open.3": "Word on the quay is that the small dealers cannot afford you any more, Captain {name}. The Mayor of {port} says it kindly.",
    "promo.tier.open.4": "Candles lit, ledgers open, and a very polite clerk waiting with a cheque. The Mayor of {port} has news about your cargo.",
    "promo.tier.open.5": "You have outgrown the old stalls, Captain. The Mayor of {port} is waiting to tell you who has been sent in to replace them.",
    "promo.tier.cap.0": "And there is the matter of the cargo. The old dealers of {port} have closed out your stock at the full price, and finer goods are coming in.",
    "promo.tier.cap.1": "A new rank brings a new class of trade. The common dealers have paid you off, and the luxury houses have opened their doors.",
    "promo.tier.cap.2": "The small dealers bow out, cheque in hand, and the great houses of the China Seas come in. This is what a commission buys, Captain.",
    "promo.tier.cap.3": "Out with the cheap and cheerful, in with the very best. The old stock is paid for, and the new stock is waiting.",
    "promo.tier.cap.4": "One more thing before the seal cools: your old cargo has been bought out at the market price, and the luxury trade is open to you.",
    "promo.tier.cap.5": "The market has changed its mind about you, Captain {name}. The old dealers have settled up, and finer things are for sale.",
    "promo.tier.kind": "Notice from the Dealers",
    "promo.tier.order": "By order of the {mayor}, and with the dealers' compliments",
    "promo.tier.cite": "The old dealers have closed out their stock and paid you in full. Nothing was lost in the swap.",
    "promo.tier.closed": "Closed out by the dealers",
    "promo.tier.opened": "Now on the market",
    "promo.tier.paid": "Paid to you",
    "promo.tier.none": "Nothing of yours was left on the old shelves.",
    "promo.tier.dropped": "Commissions for the old cargo were cancelled, with no fee and no blame.",
    "promo.tier.accept": "Understood, Captain",
    "promo.tier.sold_line": "{qty} {good} at {port}: {gain}",
    "l.tier_buyout": "The old dealers in {port} closed out your {closed} and handed you {total} for the lot. The cheap and cheerful stay behind, Captain. {opened} are on the market now, and they are not shy about the price.",
    "l.tier_step": "Nothing of yours was left on the old dealers' shelves, Captain. {closed} have left the market and {opened} are in. A better class of goods for a better class of house.",
    "st.line.tier_buyout": "Cargo closed out by the dealers",
    "l.tier_off": "The luxury dealers have packed up and left the market, Captain. They bought your {cargo} first, and paid {total} for the lot. Such fine things deserve a proper send-off.",
}

# Nothing here needs a cleaner version: the captions are narration and already family-friendly.
FAMILY = {
    "promo.cert.key": "With the Key to the Port of {port}",
    "l.tier_buyout": "The old dealers in {port} closed out your {closed} and paid you {total} for the lot. {opened} are on the market now.",
    "l.tier_step": "{closed} have left the market and {opened} are in.",
    "l.tier_off": "The luxury dealers have left the market. They bought your {cargo} first, and paid {total} for the lot.",
}

BANKS = ("promo.summons", "promo.rank", "promo.tier.open", "promo.tier.cap")
