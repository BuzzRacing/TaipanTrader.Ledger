"""Crimson Ledger: the wording for the Game 5 fixes (21 Nov 2026): a house that is stuck for good.

No silver, nothing aboard or stored, no loan and no ship to sell: the moneylender closes the books early
(rules.bank.stuck_*), and a broke house that still has a way out is told what it is.

EN is the house voice (house_voice.HOUSE_STYLE: a wink, never explicit). FAMILY is the clean wording.
These are Captain's Log lines, shown and not read aloud.
"""

EN = {
    "l.stuck_warn": "Not a coin to your name, Captain, an empty hold, and {lender} will not lend you another farthing. You are stuck fast, darling. {months} more month{s} of it and she wipes the slate and sets you up again. Gently, I promise.",
    "l.stuck_bankrupt": "Stuck fast with nothing left to sell, borrow or sail, Captain. {lender} takes pity on you this once: the books are closed, and there is no cell door for you.",
    "l.broke_away": "Empty pockets and a long way from home, Captain. Sail home, call back a laid-up ship and sell her, or trade your ship down at a yard for silver. A little ingenuity goes a long way, darling.",
    "l.broke_home": "Empty pockets, Captain. Call back a laid-up ship and sell her, sell a spare, or trade your ship down at the yard for silver. Plenty of ways to get your hands on a little something.",
}

FAMILY = {
    "l.stuck_warn": "You have no silver, nothing in your hold, and {lender} will not lend you any more. You are stuck. If it lasts {months} more month{s}, she will clear the books and set you up again.",
    "l.stuck_bankrupt": "You had nothing left to sell, borrow or sail. {lender} has closed the books, and there is no gaol this time.",
    "l.broke_away": "Your purse is empty and you are far from home. Sail home, call back a laid-up ship and sell her, or trade your ship down at a yard for silver.",
    "l.broke_home": "Your purse is empty. Call back a laid-up ship and sell her, sell a spare, or trade your ship down at the yard for silver.",
}
