"""Wording for the Robbery Story (robbery.py, web/robbery.js, 22 Nov 2026).

The story is ONE screen: Magpie (the Thieves, cast key "thieves") over the port where it happened, her line (the
existing l.robbed / l.wh_robbed, already hers in house_voice.py), a caption, and what was taken. Captions are
narration: never spoken, so they need no voice clips. A caption with innuendo has a clean twin in FAMILY.
Caption banks are chosen from a seed by the screen (rob.cap.street.N, rob.cap.house.N), so add or remove lines
freely; {port} is the port's name.
"""

EN = {
    # --- the screen ---------------------------------------------------------------------------------------
    "rob.eyebrow.street": "Robbed ashore · {port}",
    "rob.eyebrow.house": "The godown · {port}",
    "rob.title.street": "Mugged.",
    "rob.title.house": "Broken into.",
    "rob.who": "Magpie",
    "rob.btn": "Back to the game",
    # --- what was taken ----------------------------------------------------------------------------------
    "rob.tile.silver": "Silver taken",
    "rob.silver_purse": "Silver, from your purse",
    "rob.tile.left": "Silver left in hand",
    "rob.tile.stock": "Stock taken",
    "rob.tile.units": "Units carried off",
    "rob.tile.value": "Worth, at cost",
    "rob.tile.share": "Of the stock",
    "rob.taken": "What was taken",
    "rob.tip.street": "Silver in the bank cannot be lifted from a pocket.",
    "rob.feather": "She left a peacock feather where it was.",
    # --- the captions: street ----------------------------------------------------------------------------
    "rob.cap.street.0": "A warm bump in the crush of the market, a murmured apology, a flash of teal silk. When you looked down, the weight at your hip was gone, and a peacock feather lay in its place.",
    "rob.cap.street.1": "You never felt a thing. That is the art of it. Somewhere behind you a woman is laughing softly, and counting.",
    "rob.cap.street.2": "The wharf was crowded, the lamps were low, and the Pickpocket Queen was in a mood to be generous. To herself.",
    "rob.cap.street.3": "She took the silver and left the feather. By the standards of the waterfront, it was a very polite robbery.",
    "rob.cap.street.4": "A friendly hand on your arm, a gentle tug at your coat, and a smile that promised nothing. Your purse went home with someone else.",
    # --- the captions: warehouse -------------------------------------------------------------------------
    "rob.cap.house.0": "The lock on the godown door was neat, quiet and, by morning, entirely open. A peacock feather sat on the empty crates.",
    "rob.cap.house.1": "Someone went through your warehouse in {port} with a lamp, a great deal of patience and very light fingers.",
    "rob.cap.house.2": "The watchman swears he heard nothing. He is, however, wearing a very fine new hat.",
    "rob.cap.house.3": "The night was long, the thieves were thorough, and your storehouse in {port} is a good deal roomier than it was.",
    # --- the answer to "Back to the game" ----------------------------------------------------------------
    "m.robbery_ack": "Back to business, Captain.",
}

# Clean twins for Family-friendly play (the written lines have no rude words, but these two lean on a wink).
FAMILY = {
    "rob.cap.street.2": "The wharf was crowded, the lamps were low, and the Pickpocket Queen was feeling thrifty.",
    "rob.cap.street.4": "A friendly hand on your arm, a gentle tug at your coat, and a smile that promised nothing. Your purse went home with someone else.",
}
