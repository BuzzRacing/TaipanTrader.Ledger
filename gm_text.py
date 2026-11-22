"""The Game Master's wording (Madame Anahit Sarkissian, cast key "gamemaster", 21 Nov 2026).

She is the voice of the Table (the Harbor View, /table): she opens the month, says whose turn it is, poses the
decision a Captain faces and hands out action items. Decision 2 (Anthony, 21 Nov 2026): she speaks aloud on
the Table only. Player screens show her prompts as text, so she never talks over a Captain's own personas.

House voice (house_voice.py, HOUSE_STYLE): every line carries a wink, innuendo and never explicit, the game
fact stays plain, her trade words are dice, wagers, odds, the house, the pot, the gavel and the bell.
Every line has a family-friendly version that keeps the wit and drops the innuendo.
{name} is the Captain, {port} a port, {firm} a House. No spoken line carries an amount.
"""

EN = {
    # Opening the table
    "gm.welcome": "Welcome to the table, darlings. I'm Anahit, and for the next few hours, you're all mine.",
    "gm.month_open.0": "Bell's rung, darlings. A fresh month, a fresh hold, and everyone hoping to get lucky.",
    "gm.month_open.1": "New month at the table. Do keep your orders sealed. A little mystery never hurt anyone.",
    "gm.month_open.2": "The table is open, Captains. Come, wager something you can't quite afford to lose.",
    # Whose turn it is
    "gm.your_turn.0": "Captain {name}, the table is yours. Do try to make it interesting.",
    "gm.your_turn.1": "{name}, sweetheart, everyone is watching your hands. No pressure. Well, a little.",
    "gm.your_turn.2": "Your move, Captain {name}. Take your time. I do admire a captain who deliberates.",
    # Waiting on a seat
    "gm.waiting.0": "Still nothing from Captain {name}. Don't keep the table waiting, darling. It's rude, and not the fun kind.",
    "gm.waiting.1": "We're all waiting on {name}. Good things come to those who wait, but this is a touch much.",
    "gm.waiting.2": "Seal your orders, Captain {name}. I do so hate being left hanging.",
    "gm.all_sealed.0": "Every order sealed. Lovely. Now let's see who's been naughty on the water.",
    "gm.all_sealed.1": "All orders in. Hold your breath, darlings. The month is about to be unwrapped.",
    # The questions she puts to a Captain
    "gm.ask_sail": "Captain {name}, where will you sail? Choose with care. Ports remember who left them waiting.",
    "gm.ask_pay": "The Mayor is watching, Captain {name}. Pay what you owe, or slip out and hope she's looking elsewhere?",
    "gm.ask_loan": "The Moneylender is asking, Captain {name}. Borrow now and blush later?",
    "gm.ask_battle": "Pirates off the bow, Captain {name}! Fight, flee, or flirt with fortune?",
    "gm.ask_jail": "In irons, Captain {name}. Do you plead your case, or pay your way out of the cell?",
    # Action items
    "gm.act_repair": "A ship wants mending, Captain {name}. See to her before she starts to sulk.",
    "gm.act_shares": "Shares in {port} are on the table, Captain {name}. Own a little of her, if you dare.",
    "gm.act_cargo": "Your hold is half empty, Captain {name}. Such a waste of good room.",
    # Big moments
    "gm.storm": "Storm warning, darlings. Brace yourselves, and whatever else you're holding.",
    "gm.winner": "Captain {name} takes the pot. Do say a few words, then take a bow.",
    "gm.finale": "And that's the game, darlings. Count your silver. The house always remembers.",
    "gm.departure": "Orders sealed, Captain. Bound for {port}. Let's see whether fortune opens her arms or sharpens her teeth.",
    "gm.arrival": "Here we are, darling. {port}. Mind your manners; the welcome comes with a ledger.",
    "gm.return": "Back to the table, Captain. The harbour has had her turn. Now show me yours.",
    "gm.customs_clear": "Papers settled, darling. You may put your innocent face away until the next harbour.",
    "gm.customs_caught": "Caught, Captain. She inspected your figures rather more closely than you hoped.",
    "gm.customs_buyout": "She bought the cargo, darling. You named your price, and she took you at your word.",
    "gm.reckoning": "The excitement is over, Captain. Let's see what it left us with.",
}

FAMILY = {
    "gm.welcome": "Welcome to the table, everyone. I'm Anahit, and I'll be keeping the game moving.",
    "gm.month_open.0": "Bell's rung, Captains. A fresh month, a fresh hold, and everyone hoping for luck.",
    "gm.month_open.1": "New month at the table. Do keep your orders sealed. A little mystery keeps things fun.",
    "gm.month_open.2": "The table is open, Captains. Come, make your wagers.",
    "gm.your_turn.0": "Captain {name}, the table is yours. Do try to make it interesting.",
    "gm.your_turn.1": "{name}, everyone is watching. No pressure. Well, a little.",
    "gm.your_turn.2": "Your move, Captain {name}. Take your time and choose well.",
    "gm.waiting.0": "Still nothing from Captain {name}. Don't keep the table waiting, please.",
    "gm.waiting.1": "We're all waiting on {name}. Good things come to those who wait, but this is a long one.",
    "gm.waiting.2": "Seal your orders, Captain {name}. The table is waiting on you.",
    "gm.all_sealed.0": "Every order sealed. Lovely. Now let's see how the month turns out.",
    "gm.all_sealed.1": "All orders in. Hold your breath, Captains. The month is about to unfold.",
    "gm.ask_sail": "Captain {name}, where will you sail? Choose with care. Ports remember who they've seen.",
    "gm.ask_pay": "The Mayor is watching, Captain {name}. Pay what you owe, or try to slip out unseen?",
    "gm.ask_loan": "The Moneylender is asking, Captain {name}. Borrow now and repay later?",
    "gm.ask_battle": "Pirates off the bow, Captain {name}! Fight, flee, or trust to fortune?",
    "gm.ask_jail": "You're in the cell, Captain {name}. Do you plead your case, or pay your way out?",
    "gm.act_repair": "A ship needs mending, Captain {name}. See to her before the next voyage.",
    "gm.act_shares": "Shares in {port} are on the table, Captain {name}. Will you own a piece of her?",
    "gm.act_cargo": "Your hold is half empty, Captain {name}. There's good room going spare.",
    "gm.storm": "Storm warning, Captains. Brace yourselves.",
    "gm.winner": "Captain {name} takes the pot. Do say a few words, then take a bow.",
    "gm.finale": "And that's the game, Captains. Count your silver. The house always remembers.",
    "gm.departure": "Orders sealed, Captain. Bound for {port}. Let's see what fortune has in store.",
    "gm.arrival": "Here we are, Captain. {port}. A new harbour, a new page in the ledger.",
    "gm.return": "Back to the table, Captain. Your next decision awaits.",
    "gm.customs_clear": "Papers settled, Captain. Your port business can continue.",
    "gm.customs_caught": "Caught, Captain. The declaration did not survive inspection.",
    "gm.customs_buyout": "She bought the cargo, Captain. You named your price, and she accepted it.",
    "gm.reckoning": "The encounter is over, Captain. Let's see what it left us with.",
}
