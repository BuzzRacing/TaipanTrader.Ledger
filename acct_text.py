"""The Accounting Ledger's wording (20 Nov 2026): the House's own books, kept by the bookkeeper,
Mademoiselle Céleste Vautrin (cast key "bookkeeper"). It replaced the Port screen's Accounts view.

acct.*          the Ledger's pages (Admin > Language & Text > Accounting Ledger)
l.acct_up.N     her greeting when the last voyage made money      (she reads it; happy pictures)
l.acct_down.N   ... when it lost money                             (angry pictures)
l.acct_even.N   ... before the first voyage, or when it came out even (sly pictures)
l.acct_debt.N   ... when the moneylender's collectors are due      (sly pictures)

Every spoken line follows the house voice (house_voice.HOUSE_STYLE): sexy, funny, full of innuendo,
never explicit, in her own voice. FAMILY holds a clean version of each. No spoken line has an amount
in it, so each is recorded once and replayed for free.
"""

EN = {
    # The rail button and the book's frame.
    "tab.acct": "Ledger",
    "acct.open_hint": "The Accounting Ledger: profit and loss, bank, debts, the fleet's accounts and every due",
    "acct.title": "The Accounting Ledger",
    "acct.keeper": "{name}, keeper of the House's books",
    "acct.close": "Close the ledger",
    "acct.prev": "Turn back", "acct.next": "Turn the page",
    "acct.spread.purse": "The Purse", "acct.spread.house": "The Counting House", "acct.spread.dues": "Dues & Duties",
    "acct.folio": "Folio {n} of {of}",
    "acct.locked": "Orders are given: the books are closed until you land. Take your orders back to move silver.",
    "acct.date": "Written up in {port}, {date}",

    # Spread 1, left: the balance.
    "acct.bs.title": "What the House owns, and what it owes",
    "acct.bs.worth": "Net worth",
    "acct.bs.cash": "Silver aboard", "acct.bs.bank": "In the bank",
    "acct.bs.cargo": "Cargo aboard", "acct.bs.cargo_sub": "at what the dealers of {port} would pay today",
    "acct.bs.fleet": "The fleet", "acct.bs.fleet_sub": "{n} ship(s), at what a yard would pay",
    "acct.bs.other": "Stores, holdings and laid-up ships", "acct.bs.other_sub": "warehouse stock, shares, the great house, ships at rest",
    "acct.bs.debt": "Owed to {lender}", "acct.bs.debt_sub": "{rate}% a month, compounding",
    "acct.bs.owns": "The House owns", "acct.bs.owes": "The House owes",
    "acct.chart.title": "Worth, month by month",
    "acct.chart.loading": "Fetching the old pages from the archive…",
    "acct.chart.none": "The first page fills in after your first month at sea.",
    "acct.chart.cash": "Silver", "acct.chart.bank": "Bank", "acct.chart.cargo": "Cargo", "acct.chart.fleet": "Fleet",
    "acct.chart.debt": "Debt", "acct.chart.worth": "Net worth",
    "acct.chart.hint": "Run a finger along the chart to read any month.",

    # Spread 1, right: profit and loss.
    "acct.pl.title": "Profit and loss",
    "acct.pl.flow": "Where the silver came from, and where it went",
    "acct.pl.net": "Net", "acct.pl.grp_other": "Everything else",
    "acct.pl.hint": "Tap a bar to see its lines.",

    # Spread 2, left: bank and moneylender.
    "acct.money.title": "Silver, the bank and the moneylender",
    "acct.money.cash": "Silver aboard", "acct.money.bank": "In the bank", "acct.money.debt": "Owed",
    "acct.money.room": "{lender} would lend you",
    "acct.proj.title": "What it comes to next month",
    "acct.proj.hint": "Move a slider: these figures follow it before anything is written down.",
    "acct.proj.bank_int": "The bank pays you", "acct.proj.loan_int": "Interest added to the debt",
    "acct.proj.net_int": "Interest, all told",
    "acct.proj.debt_next": "Owed next month", "acct.proj.never": "nothing owed",
    "acct.proj.line": "The collectors' line", "acct.proj.over": "{amount} over it", "acct.proj.under": "{amount} to spare",
    "acct.proj.ashore": "Silver aboard ashore", "acct.proj.safe": "too little to tempt a thief",
    "acct.proj.risk": "worth robbing ({lo}–{hi}% if they strike)",
    "acct.away.bank": "The bank counter is in {home} and in ports with a bank. Your balance earns {rate}% a month wherever you are.",
    "acct.away.loan": "{lender} lends and is repaid only in {home}.",

    # Spread 2, right: the fleet's accounts.
    "acct.fleet.title": "The fleet's accounts",
    "acct.fleet.ship": "Ship", "acct.fleet.value": "Worth", "acct.fleet.wage": "A month", "acct.fleet.repair": "Repairs",
    "acct.fleet.total": "Wages and upkeep, a month",
    "acct.fleet.laid": "Laid up at {home}",
    "acct.fleet.laid_note": "Laid-up ships cost {pct}% of their wages. Recall them at {home}.",
    "acct.fleet.saving": "saves {amount} a month",
    "acct.fleet.sell": "Sell {value}", "acct.fleet.repair_btn": "Repair {cost}", "acct.fleet.repair_all": "Repair all {cost}",
    "acct.fleet.layup": "Lay up", "acct.fleet.recall": "Recall",
    "acct.fleet.no_yard": "Ships are sold and repaired at a shipyard.",
    "acct.fleet.home_only": "Ships are laid up and recalled at {home}.",
    "acct.fleet.chart": "Where the month's wages go",
    "acct.prot.title": "{pirate}'s protection",
    "acct.prot.left": "{n} months left", "acct.prot.left_1": "1 month left", "acct.prot.none": "Not protected",
    "acct.prot.pay": "Pay {cost}", "acct.prot.home": "Paid to her agent in {home}.",

    # Spread 3, left: housing and the Mayor's bill.
    "acct.house.title": "Housing: warehouses and the great house",
    "acct.house.wh": "{port} warehouse", "acct.house.used": "{used} of {cap} in store",
    "acct.house.goods": "Stock", "acct.house.none": "The House rents no warehouse yet.",
    "acct.house.rent": "Warehouse rent", "acct.house.estate": "Upkeep of the great house and patronages",
    "acct.house.estate_now": "The great house: stage {n}",
    "acct.house.range": "{range}",
    "acct.bill.title": "The Mayor's bill, if you sail from {port} now",
    "acct.bill.total": "Payable on sailing", "acct.bill.none": "Nothing to pay: the harbour is yours.",
    "acct.bill.after": "Silver left after paying",

    # Spread 3, right: who got the silver, and the taxman.
    "acct.takers.title": "Who got your silver",
    "acct.takers.none": "Nobody has had a coin of yours yet. Give it time.",
    "acct.who.mayor": "The Mayors", "acct.who.mayor_sub": "harbour dues and gifts",
    "acct.who.officer": "The Port Authority", "acct.who.officer_sub": "cargo tax, fines and seizures",
    "acct.who.lender": "{lender}", "acct.who.lender_sub": "interest on the debt",
    "acct.who.banker": "The bank", "acct.who.banker_sub": "interest paid to you",
    "acct.who.shipwright": "The shipyards", "acct.who.shipwright_sub": "ships, guns and repairs",
    "acct.who.agent": "{pirate}'s agent", "acct.who.agent_sub": "protection",
    "acct.who.pirates": "Pirates", "acct.who.pirates_sub": "plunder and the price to pass",
    "acct.who.thieves": "Thieves", "acct.who.thieves_sub": "robbed ashore and from store",
    "acct.who.warehouse": "Warehouse keepers", "acct.who.warehouse_sub": "rent",
    "acct.tax.title": "Dues and the Port Authority, port by port",
    "acct.tax.port": "Port", "acct.tax.visits": "Visits", "acct.tax.tax": "Tax", "acct.tax.fine": "Fines",
    "acct.tax.none": "No Port Authority desk has had your silver yet.",
    "acct.tax.dues": "Harbour dues paid this game: {paid} over {count} sailings",
    "acct.tax.slipped": "{n} slipped out at night, dodging {saved}",
    "acct.wages": "Crew wages and upkeep this game: {amount}",
    "acct.game_only": "From the whole game's journal, as the Tally Book reads it.",

    # Her greetings, one a visit, chosen by how the last voyage went. Read aloud by the bookkeeper.
    "l.acct_up.0": "Oh, Captain. Come in and close the door. Your profits are showing, and I do so like a captain who comes home heavy.",
    "l.acct_up.1": "Black ink from top to bottom, Captain. I had to loosen my collar just adding it up.",
    "l.acct_up.2": "A handsome profit. Sit on the edge of my desk and let me show you every column, slowly.",
    "l.acct_up.3": "You've been a very good captain this voyage. My quill hasn't had this much fun in months.",
    "l.acct_up.4": "Look at these figures, Captain. Firm, generous, and growing. Exactly how I like them.",
    "l.acct_up.5": "Profit, darling. Pour us both a brandy. Tonight, the books and I are in a very good mood.",
    "l.acct_down.0": "Red ink again, Captain. You know what red ink does to me. Sit down. We're going to have a long, firm talk.",
    "l.acct_down.1": "A loss. Tsk. Spread the ledger open, Captain, and let's see exactly where you were careless.",
    "l.acct_down.2": "You came home lighter than you left, Captain. I can always tell. Shall I show you where it all slipped away?",
    "l.acct_down.3": "Every coin you lost is written down here in my prettiest hand. I'm not angry, Captain. I'm keeping score.",
    "l.acct_down.4": "Down again. Never mind, Captain. Some captains need a firm hand on the purse strings. I happen to have two.",
    "l.acct_down.5": "My quill is out and dripping red, Captain. Next voyage, bring me something I can enjoy.",
    "l.acct_even.0": "A fresh page, Captain. Clean, crisp, untouched. Let's see how long you can keep it that way.",
    "l.acct_even.1": "Nothing much to report, Captain. Even books are terribly dull. Do something to excite them.",
    "l.acct_even.2": "Every column balances, Captain. A pity. I so enjoy it when something doesn't add up.",
    "l.acct_even.3": "Pull up a chair, Captain. I've kept your books warm. Now go and give me something worth writing down.",
    "l.acct_debt.0": "The collectors are on their way, Captain. They're far less patient with you than I am, and far less fun.",
    "l.acct_debt.1": "{lender} has been asking after you, Captain. Pay her something, before she comes to ask in person.",
    "l.acct_debt.2": "You owe more than is good for you, Captain. I'd be tempted to tie your purse strings myself.",
    "l.acct_debt.3": "Debt is like a jealous lover, Captain. Ignore her long enough and she turns up at the door with friends.",
}

FAMILY = {
    "l.acct_up.0": "Oh, Captain, come in. Your profits are showing, and I do like a captain who comes home with a full purse.",
    "l.acct_up.1": "Black ink from top to bottom, Captain. It was a pleasure adding it up.",
    "l.acct_up.2": "A handsome profit. Pull up a chair and let me show you every column.",
    "l.acct_up.3": "You've been a very good captain this voyage. My quill hasn't had this much fun in months.",
    "l.acct_up.4": "Look at these figures, Captain. Healthy, generous and growing. Exactly how I like them.",
    "l.acct_up.5": "Profit, Captain. Pour us both a cup of tea. Today the books and I are in a very good mood.",
    "l.acct_down.0": "Red ink again, Captain. Sit down. We're going to have a long talk.",
    "l.acct_down.1": "A loss. Tsk. Open the ledger, Captain, and let's see exactly where things went wrong.",
    "l.acct_down.2": "You came home lighter than you left, Captain. I can always tell. Shall I show you where it went?",
    "l.acct_down.3": "Every coin you lost is written down here in my neatest hand. I'm not angry, Captain. I'm keeping score.",
    "l.acct_down.4": "Down again. Never mind, Captain. Some captains need a firm hand on the purse strings, and I have one.",
    "l.acct_down.5": "My quill is out and it's writing in red, Captain. Next voyage, bring me something better.",
    "l.acct_even.0": "A fresh page, Captain. Clean, crisp and untouched. Let's see how long you can keep it that way.",
    "l.acct_even.1": "Nothing much to report, Captain. Even books are terribly dull. Go and do something exciting.",
    "l.acct_even.2": "Every column balances, Captain. A pity. I enjoy it when something doesn't add up.",
    "l.acct_even.3": "Pull up a chair, Captain. Your books are ready. Now go and give me something worth writing down.",
    "l.acct_debt.0": "The collectors are on their way, Captain. They're far less patient with you than I am.",
    "l.acct_debt.1": "{lender} has been asking after you, Captain. Pay her something before she comes to ask in person.",
    "l.acct_debt.2": "You owe more than is good for you, Captain. I'd be tempted to hold your purse for you.",
    "l.acct_debt.3": "Debt is like a stray dog, Captain. Feed it long enough and it brings its friends to your door.",
}
