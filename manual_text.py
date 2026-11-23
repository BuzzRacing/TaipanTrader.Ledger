"""The Captain's Manual's wording (/Manual, 21 Nov 2026).

A leather-bound book with one chapter per major part of the game. Each chapter has a key persona who
presents it (cast keys from cast.py). Page text is plain and exact; the persona lines (the "open" bank, later
the good / bad / warn / nudge banks the practice benches fire) are in the house voice (house_voice.py,
HOUSE_STYLE): sexy, funny, full of innuendo, never explicit, each woman in her own voice. Every spoken line has
a clean family version in FAMILY that keeps the wit and drops the innuendo.

No placeholders in any line, and no amount in a spoken line. Phase 1 (the shell) ships the "open" bank for every
chapter and the full page text for the cover and the three first chapters (Money, Port Authority, The Market).
Anthony's decisions (21 Nov 2026): about 25 reactive lines per lead persona (written with each chapter's
practice bench), a voice on/off switch the player owns, no links from the game (the URL is handed to players).
"""

# id, key persona (cast.py key), difficulty of the practice bench (for the tab), whether the chapter is written
CHAPTERS = [
    {"id": "cover",     "who": "narrator",   "level": "",       "ready": True},
    {"id": "money",     "who": "lender",     "level": "easy",   "ready": True},
    {"id": "authority", "who": "customs",    "level": "medium", "ready": True},
    {"id": "market",    "who": "comprador",  "level": "hard",   "ready": True},
    {"id": "storms",    "who": "crier",      "level": "",       "ready": False},
    {"id": "battles",   "who": "bosun",      "level": "",       "ready": False},
    {"id": "fleet",     "who": "shipwright", "level": "",       "ready": False},
    {"id": "tips",      "who": "taxlady",    "level": "",       "ready": False},
    {"id": "late",      "who": "mayor",      "level": "",       "ready": False},
    {"id": "tally",     "who": "bookmaker",  "level": "",       "ready": False},
]
HOW_STEPS = {"cover": 4, "money": 4, "authority": 4, "market": 4}      # numbered "How it works" lines written
MOMENTS = ("open",)                                                    # line banks written so far (the benches add more)
BANK_SIZE = 3                                                          # lines each bank ships with; the live bank can grow

EN = {
    # ---- the book itself ----
    "man.title": "The Captain's Manual",
    "man.subtitle": "How to win, and make heaps of money",
    "man.back": "Back to the game",
    "man.voice_on": "Voices on",
    "man.voice_off": "Voices off",
    "man.voice_hint": "Turn the personas' voices on or off for this book. Off by default.",
    "man.voice_turn_on": "Turn voices on above to hear her.",
    "man.voice_unavailable": "Spoken lines are not switched on at this table, so you will read them instead.",
    "man.another": "Another line",
    "man.hear": "Hear it",
    "man.level.easy": "Easy",
    "man.level.medium": "Medium",
    "man.level.hard": "Hard",
    "man.soon": "Being written",
    "man.how": "How it works",
    "man.win": "How to win",
    "man.watch": "Watch out",
    "man.bench": "Practice bench",
    "man.bench_soon": "The practice bench for this chapter opens in the next build. You will move the same sliders and buttons as on the Captain's screen and see what changes.",
    "man.chapter_soon": "This chapter is still being written. Its persona is here already; the lessons follow.",
    "man.e_seat": "Take your seat in the game first, Captain. The Manual is for captains at the table: open the game on this device, join, then come back to this page.",
    "man.e_gate": "The Manual could not open just now. Try again in a moment.",
    "man.forbid.title": "Cargoes a port does not trade",
    "man.forbid.note": "Some ports do not trade some cargoes at all. Nobody there will ever mention it: the cargo is simply not on the market, and it is never a tip, a headline or a line on the tax desk. Cargo you already carry stays in your hold until you reach a port that trades it.",

    # ---- tabs, titles, kickers ----
    "man.cover.tab": "Start here", "man.cover.title": "How to win in one page", "man.cover.kicker": "From the First Mate",
    "man.money.tab": "Money", "man.money.title": "The bank, the loan and the collectors", "man.money.kicker": "From the Moneylender",
    "man.authority.tab": "Port Authority", "man.authority.title": "The declaration desk", "man.authority.kicker": "From Customs",
    "man.market.tab": "The Market", "man.market.title": "Buy low, sell high, without moving the price", "man.market.kicker": "From the Comprador",
    "man.storms.tab": "Storms", "man.storms.title": "The forecast and the sea", "man.storms.kicker": "From the Gazette",
    "man.battles.tab": "Sea battles", "man.battles.title": "Fight, run, pay or retreat", "man.battles.kicker": "From the Bosun",
    "man.fleet.tab": "Fleet", "man.fleet.title": "Ships, guns and wages", "man.fleet.kicker": "From the Shipwright",
    "man.tips.tab": "Tips and booms", "man.tips.title": "Reading a market before it moves", "man.tips.kicker": "From the Registrar",
    "man.late.tab": "Late game", "man.late.title": "Shares, the great house and rank", "man.late.kicker": "From Her Worship",
    "man.tally.tab": "The Tally", "man.tally.title": "Reading your own record", "man.tally.kicker": "From the Bookmaker",

    # ---- the cover: how to win in one page ----
    "man.cover.how.0": "Each turn is one month. Arrive, and read Port business first: it lists what is worth doing here.",
    "man.cover.how.1": "Trade on the Market tab. Drag a bar right to buy and left to sell, and read the price it shows before you press the button.",
    "man.cover.how.2": "Sort the money: the bank, the loan and the harbour bill. Debt costs more every month it sits.",
    "man.cover.how.3": "Set sail. Check the forecast and your hull, and give standing orders for a fight, because the clock will play them if you don't.",
    "man.cover.win": "Money is made at the Market and lost at the desk and on the water. Net worth counts your cargo at what dealers would really pay for all of it today, not at the posted price.",
    "man.cover.watch": "Holds that outgrow the dealers' silver, debt left to compound, and empty holds that still draw wages.",

    # ---- money: the bank, the loan and the collectors ----
    "man.money.how.0": "The moneylender lends at your home port and charges interest every month, compounding (3% a month as shipped). Unpaid dues and wages go onto the same debt.",
    "man.money.how.1": "The collectors watch a line built from your ships and your home standing. Silver and the bank do not count towards it, so every dollar you repay brings the debt closer to the line.",
    "man.money.how.2": "Over the line, you get a grace period, then a call every few months, and each call costs standing at home. The debt clock under the Debt plaque shows when they call and how much to repay to stop it.",
    "man.money.how.3": "Silver ashore can be robbed. Bank the rest keeps it safe, pays about 1% a month, and the bank can pay pirates when silver in the hold cannot.",
    "man.money.win": "Borrow only what you will turn into cargo this month, repay at home whenever you pass with silver to spare, and keep idle silver in the bank.",
    "man.money.watch": "Interest compounds on an unpaid loan, wages are paid on empty holds, and a house with no silver cannot pay its way out of a fight or a cell.",

    # ---- the Port Authority desk ----
    "man.authority.how.0": "On arrival in a taxed port you declare the value of your cargo, and the tax is a share of what you declare. Your home port and free ports take none.",
    "man.authority.how.1": "Declare less and you save tax, but the Port Authority may buy your cargo at your own declared price. The desk shows what that would cost you in silver as you slide.",
    "man.authority.how.2": "A buyout hands over the cargo at your price. Getting it back costs the larger of her price plus a quarter, or what the cargo is worth in that market.",
    "man.authority.how.3": "Port shares cut the tax in their port, and a Patron pays least. Rates differ a lot from port to port, so read the rate before you choose.",
    "man.authority.win": "Declare honestly on a big hold, and keep the gamble for small ones, where a loss is small and the saving is real.",
    "man.authority.watch": "A low declaration on a full hold can lose far more than the tax it saves. One game lost fifteen million of cargo that way to save a little over a hundred thousand each time.",

    # ---- the Market ----
    "man.market.how.0": "Every buy moves the price up and every sell moves it down, and the bigger the trade against the cargo's depth, the bigger the move. A fleet-sized buy can cost close to double the posted price.",
    "man.market.how.1": "The bar and button show the average price per unit and how many times the posted price that is: amber past 1.5, red past 2.5. Read it before you press.",
    "man.market.how.2": "Each port's dealers have only so much silver a month for each cargo. Past it they pay a third of the price on what is left. Buying has no such limit, which is how a hold gets bought dear and sold cheap.",
    "man.market.how.3": "Selling into a boom uses it up, so a full hold ends it. Under each cargo, Best known shows where it should fetch more, and how old that news is.",
    "man.market.win": "Split a big hold across ports and cargoes, watch the red dealers-have-silver-left tag, and leave a market a little hungry.",
    "man.market.watch": "Buying a whole fortune of one cargo, selling it all in one port in one visit, and arriving after a boom has already ended.",

    # ---- tab and bench titles for the practice benches (written with each chapter) ----
    "man.money.bench_title": "Borrow, repay and bank",
    "man.authority.bench_title": "Declare at the desk",
    "man.market.bench_title": "Two ports, one hold",

    # ---- persona lines: the "open" bank (house voice) ----
    "man.cover.open.0": "Welcome aboard, Captain. I keep the log, you keep the silver, and this book keeps the two of us on speaking terms.",
    "man.cover.open.1": "Page one: ships go out, silver comes home. Anything else is foreplay, and foreplay costs wages.",
    "man.cover.open.2": "Read slowly, Captain. I've seen what happens to captains who rush the first chapter. Messy. Expensive.",
    "man.money.open.0": "Come in, Captain, and shut the door. Borrowing is such a private pleasure, and repaying is such a public one.",
    "man.money.open.1": "I lend to captains I like, darling. Do give me reason to keep liking you.",
    "man.money.open.2": "Interest is only affection, compounded. Let me show you how fast it grows.",
    "man.authority.open.0": "Declarations, Captain. I like them honest and I like them early. Surprises I save for the cells.",
    "man.authority.open.1": "Everyone lies a little at my desk. The clever ones know exactly how little they can afford.",
    "man.authority.open.2": "Come closer, Captain. Let's go over what you're hiding, and what it will cost you to hide it.",
    "man.market.open.0": "A good price, Captain, is like a good evening. It looks lovely until you ask too much of it.",
    "man.market.open.1": "Buy a little, sell a little, and always leave the dealers wanting more. Wanting is half the trade.",
    "man.market.open.2": "Slide that bar slowly, darling. The market feels every inch you take.",
    "man.storms.open.0": "Read the glass before you read the gossip, Captain. The sea is never as discreet as I am.",
    "man.storms.open.1": "Fair winds are a rumour, Captain. A typhoon is a fact. I report both.",
    "man.storms.open.2": "Everyone's talking about the weather. Do keep your ship out of the conversation.",
    "man.battles.open.0": "Guns up, Captain. I like a ship that knows what to do when it's looked at that way.",
    "man.battles.open.1": "Fight, run, pay or retreat. Four ways to get through a bad afternoon, and I've enjoyed every one.",
    "man.battles.open.2": "Ten seconds a round, Captain. Take your time, but not too much of it.",
    "man.fleet.open.0": "Every hull is a promise, Captain. Keep her well fitted and she'll keep you well off.",
    "man.fleet.open.1": "A big ship eats wages whether she's full or not. I've known a few like that.",
    "man.fleet.open.2": "Come below, Captain. I'll show you how a good keel feels.",
    "man.tips.open.0": "A tip is a secret with a price tag, Captain. I do so love putting a price on secrets.",
    "man.tips.open.1": "When a boom is whispered in a doorway, ask yourself who has already sold.",
    "man.tips.open.2": "I keep the register, darling. I know who bought low, and who's about to be very sorry.",
    "man.late.open.0": "Rank is a lovely thing, Captain. So is what a grateful port will do for a patron.",
    "man.late.open.1": "Shares, a great house, a flagship. A captain with taste always has something left to spend.",
    "man.late.open.2": "Come to my parlour once you've done well, Captain. I'm so much more generous to the successful.",
    "man.tally.open.0": "Odds, Captain. Everything is odds. Let me show you how yours have been looking.",
    "man.tally.open.1": "I keep the tally, and the tally never flatters. Brave of you to look.",
    "man.tally.open.2": "Come, see how the house is doing. I always say a number is only embarrassing once.",
}

# Family-friendly wording for every spoken line: the wit stays, the innuendo goes.
FAMILY = {
    "man.cover.open.0": "Welcome aboard, Captain. I keep the log, you keep the silver, and this book keeps the two of us out of trouble.",
    "man.cover.open.1": "Page one: ships go out, silver comes home. Anything else is dawdling, and dawdling costs wages.",
    "man.cover.open.2": "Read slowly, Captain. I've seen what happens to captains who rush the first chapter. Messy and expensive.",
    "man.money.open.0": "Come in, Captain, and sit down. Borrowing is easy, and repaying is the part everyone remembers.",
    "man.money.open.1": "I lend to captains I like. Do give me reason to keep liking you.",
    "man.money.open.2": "Interest is only patience, compounded. Let me show you how fast it grows.",
    "man.authority.open.0": "Declarations, Captain. I like them honest and I like them early. Surprises are for birthdays.",
    "man.authority.open.1": "Everyone is tempted at my desk. The clever ones know exactly what it could cost.",
    "man.authority.open.2": "Come closer, Captain. Let's go over what you're declaring, and what it will cost you to be careless.",
    "man.market.open.0": "A good price, Captain, is like a good harvest. It looks lovely until you try to take too much of it.",
    "man.market.open.1": "Buy a little, sell a little, and always leave the dealers wanting more. Wanting is half the trade.",
    "man.market.open.2": "Slide that bar slowly, Captain. The market feels every inch you take.",
    "man.storms.open.0": "Read the glass before you read the gossip, Captain. The sea is never as polite as I am.",
    "man.storms.open.1": "Fair winds are a rumour, Captain. A typhoon is a fact. I report both.",
    "man.storms.open.2": "Everyone's talking about the weather. Do keep your ship out of the conversation.",
    "man.battles.open.0": "Guns up, Captain. I like a crew that knows what to do when trouble shows up.",
    "man.battles.open.1": "Fight, run, pay or retreat. Four ways to get through a bad afternoon, and I've tried every one.",
    "man.battles.open.2": "Ten seconds a round, Captain. Take your time, but not too much of it.",
    "man.fleet.open.0": "Every hull is a promise, Captain. Keep her well fitted and she'll keep you well off.",
    "man.fleet.open.1": "A big ship eats wages whether she's full or not. Mind you fill her.",
    "man.fleet.open.2": "Come below, Captain. I'll show you what a good keel looks like.",
    "man.tips.open.0": "A tip is a secret with a price tag, Captain. I do like putting a price on a secret.",
    "man.tips.open.1": "When a boom is whispered in a doorway, ask yourself who has already sold.",
    "man.tips.open.2": "I keep the register, Captain. I know who bought low, and who's about to be sorry.",
    "man.late.open.0": "Rank is a fine thing, Captain. So is what a grateful port will do for a patron.",
    "man.late.open.1": "Shares, a great house, a flagship. A captain with taste always has something left to spend.",
    "man.late.open.2": "Come to my parlour once you've done well, Captain. I'm much more generous to the successful.",
    "man.tally.open.0": "Odds, Captain. Everything is odds. Let me show you how yours have been looking.",
    "man.tally.open.1": "I keep the tally, and the tally never flatters. Brave of you to look.",
    "man.tally.open.2": "Come, see how the house is doing. I always say a number is only embarrassing once.",
}

# Every line a persona can speak: key -> cast key. (Used by the server to find the voice; the Admin Cast &
# Voices page still decides what each persona sounds like.)
SPEAKER = {}
for _c in CHAPTERS:
    for _m in MOMENTS:
        for _i in range(BANK_SIZE):
            SPEAKER["man.{}.{}.{}".format(_c["id"], _m, _i)] = _c["who"]


def bank_keys(chapter_id, moment, live=None):
    """The keys of one chapter's line bank that have wording right now: every contiguous `man.<chapter>.<moment>.N`,
    skipping retired (blank) lines, so a line added in Admin > Language & Text > Dialogue Banks is used."""
    if live is None:
        import banks
        import strings
        banks.apply()
        live = strings.EN
    keys, i = [], 0
    while True:
        k = "man.{}.{}.{}".format(chapter_id, moment, i)
        if k not in live:
            break
        if live[k]:
            keys.append(k)
        i += 1
    return keys


def chapters(live=None):
    """What the page needs to lay out the book: the chapters in order, each with its persona and the keys
    of its line banks (the page reads the wording itself from /api/info)."""
    out = []
    for c in CHAPTERS:
        out.append({
            "id": c["id"], "who": c["who"], "level": c["level"], "ready": c["ready"],
            "how": HOW_STEPS.get(c["id"], 0),
            "bank": {m: bank_keys(c["id"], m, live) for m in MOMENTS},
        })
    return out
