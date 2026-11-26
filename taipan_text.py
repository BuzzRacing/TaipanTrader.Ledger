"""Taipan Trader wording: laid over everything else by strings.resolve, last.

Taipan Trader's cast is a mix of men and women, so lines about "the officer" or "the warden" (a different person
in every port) no longer say "she", and lines by or about the men say "he". A few family lines that still leaned
on innuendo are made plain here too. Edit a line here, or in Admin > Language & Text, which wins over this file.
"""

OVERRIDES = {
    # The bosun, Patrick "Powder" O'Rourke.
    "battle.tell.bargain.2": "Powder winks at you and plants himself between them and the hatches.",
    "battle.tell.calm.1": "Powder is humming as he sights along a barrel.",
    "battle.tell.calm.2": "\"Easy work,\" says Powder, wiping soot from his cheek.",
    "battle.tell.grim.0": "Powder has gone quiet. He is tying a rag round his head with both hands.",
    "battle.tell.grim.2": "Powder shakes his head and looks at the horizon behind you.",
    "battle.tell.worried.0": "Powder counts their sails twice and chews his lip.",

    # The Port Authority desk: each port's officer, man or woman.
    "customs.bribe": "Slip the officer a sweetener ({cost})",
    "customs.bribe_note": "Halves the officer's appetite for checking. An honest officer refuses it, checks harder "
                          "and your standing suffers.",
    "customs.bribe_refused": "The officer refused your sweetener and checked harder.",
    "customs.bribe_taken": "The officer pocketed your sweetener of {cost}.",
    "customs.hid_tip": "Your crew slipped these below decks before the count: kept aboard, untaxed",
    "customs.hot_head": "A hot tip",
    "customs.low_warn": "At this price the officer may simply buy it: {price} for cargo worth {value}.",
    "customs.low_warn_odds": "If the officer buys at your price, you hand over {value} of {good} for {price}. The low "
                             "price saves {saved} in tax; the chance of a buy: {odds}%.",
    "customs.low_warn_silver": "If the officer buys at your price, you hand over {value} of {good} for {price}. The "
                               "low price saves {saved} in tax.",
    "customs.odds_buy": "Buys it",
    "customs.odds_hidden": "Read the officer's face, Captain.",
    "customs.odds_title": "The odds",
    "customs.out.empty": "Taxed (the strongbox was empty)",
    "customs.pay_sub.correct": "Pay the officer's figure. Tax {tax}. No buying, no search.",
    "customs.pay_sub.less": "Pay under the officer's figure. Tax under {tax}.",
    "customs.pay_sub.more": "Pay {over}% over the officer's figure. Tax {tax}. No buying, no search, and your standing "
                            "rises.",
    "customs.pay_warn.less": "If the officer buys at your price, you hand over your cargo for less than it's worth.",
    "customs.pay_warn.nothing": "If the officer buys at your price, you hand over your cargo for nothing.",
    "customs.rate_base": "the usual rate",
    "customs.share": "{pct}% of the officer's figure",
    "customs.she_paid": "Paid to you",
    "customs.tell_bored.0": "The officer barely looks up from the ledger. Honest captains are a bore.",
    "customs.tell_bored.1": "A stretch, and a pen run down your manifest without much interest.",
    "customs.tell_bored.2": "A yawn stifled behind the hand. The officer's eyes drift to the next ship.",
    "customs.tell_curious.0": "The officer taps a pen on the desk and looks at you a little longer.",
    "customs.tell_curious.1": "The officer leans across the desk. \"Is that all you are carrying, Captain?\"",
    "customs.tell_curious.2": "One eyebrow rises. A page is turned back, slowly.",
    "customs.tell_hungry.0": "The officer is eyeing your {good} very closely.",
    "customs.tell_hungry.1": "The ledger closes, very slowly, with a smile. That smile is never good news.",
    "customs.tell_hungry.2": "\"Open the hold, Captain,\" says the officer. \"I want to see everything.\"",
    "customs.tell_over.0": "A warm smile. Generous captains are the officer's favourite kind.",
    "customs.tell_over.1": "A hand rests on your manifest. \"Such an honest captain.\"",
    "customs.tip_head": "From the register",
    "customs.verdict": "The ruling",
    "e.customs_nothing_back": "The officer bought nothing of that from you.",
    "gm.customs_buyout": "The officer bought the cargo, Captain. You named your price, and it was accepted.",

    # The men among the officers.
    "l.customs_welcome.officer_bangkok.10": "Welcome to Bangkok, Captain. The river is high, the temples are lovely "
                                            "in the evening light, and the King's tolls are kept by a man who would "
                                            "very much like to be your friend. Please, declare your cargo truthfully.",
    "l.customs_welcome.officer_calcutta.9": "Three fortunes I married, Captain, each larger than the last. You'd be "
                                            "surprised how many captains remind me of my fathers-in-law.",
    "l.customs_welcome.officer_calcutta.13": "Two of my fathers-in-law were captains, Captain, and both of them "
                                             "under-declared. Neither of them is with us any more. Now, what are you "
                                             "carrying?",
    "l.customs_welcome.officer_singapore.4": "Do be quick, Captain. My lime cordial is getting warm.",
    "l.customs_welcome.officer_singapore.7": "My predecessor used to read every manifest twice. He died of it, I'm "
                                             "told. I read them once, if they're short.",
    "l.customs_welcome.officer_singapore.1": "Papers, Captain. Put them on the corner that isn't holding down the fan.",
    "l.customs_welcome.officer_singapore.8": "Take the chair in the shade. The chair in the sun is for forms I never intend to read.",
    "l.customs_welcome.officer_singapore.11": "The ice in my lime cordial has lasted longer than the last captain's story. Let's keep yours to the cargo.",
    "l.customs_welcome.officer_manila.3": "Welcome to Manila. I've had the chocolate brought out. Now let me see what you've brought.",
    "l.customs_welcome.officer_manila.14": "My warehouses have room for silk and porcelain, Captain. Name a fair value and pay your tax. Name a bargain and I may buy.",
    "l.customs_welcome.officer_saigon.7": "The admiral told me this desk would be quiet. The admiral had never worked at this desk. Your papers, please.",
    "l.customs_welcome.officer_saigon.8": "I had the whole second act of an opera in my head until you knocked. Your declaration had better be worth the interruption.",
    "l.customs_welcome.officer_nagasaki.2": "I've turned the manifest so you can read it. I didn't need to turn it for myself.",
    "l.customs_welcome.officer_shanghai.2": "Manifest left. Cargo tally right. My clerks are fast, Captain. Try to keep up.",
    "l.customs_welcome.officer_bangkok.2": "Please set your papers beside the jasmine, Captain. We'll see to the King's tolls before the tide turns.",
    "l.customs_welcome.officer_foochow.4": "Let the leaves settle, Captain. Then start with what you loaded last.",
    "l.customs_welcome.officer_hongkong.2": "Leave the manifest upside down, Captain. I learned to read one across a much wobblier desk.",
    "l.customs_welcome.officer_calcutta.11": "Let us be quick, Captain. I've set aside a clean page for your declaration. Whether I need a second page is entirely up to you.",
    # Batavia's tollmistress checks columns with a brass ruler now, not a crop.
    "l.customs_welcome.officer_batavia.3": "Tap. That is the ruler. Declare.",
    "l.customs_welcome.officer_batavia.6": "The ruler is for columns, Captain. Mostly. Please declare your cargo.",
    "l.customs_welcome.officer_batavia.10": "Good morning, Captain, and welcome to the Batavia Roads. You will declare "
                                            "each line of cargo, you will write the value clearly, and you will sign "
                                            "at the bottom. I will then check each column, one tap of the ruler at a "
                                            "time.",
    "l.customs_welcome.officer_batavia.14": "Each tap of this ruler is one column checked, Captain. Most captains hear "
                                            "twelve taps and leave. A few hear thirteen, and stay rather longer than "
                                            "they planned. Let us aim for twelve, shall we?",

    # The wardens: each port's own, man or woman.
    "jail.free.1": "The warden holds the door a moment longer than needed. Then you are let go. Don't come back, "
                   "Captain.",
    "jail.irons.0": "The irons go on, cold and heavy. The warden of {port} walks you in personally, and takes their "
                    "time about it.",
    "jail.month.3": "The warden brings your supper in person and waits at the bars to see you finish it.",
    "l.jail_standing": "Your name in {port} is mud. The warden's guards were waiting on the wharf: {months} "
                       "month{s} in the {port} gaol, Captain.",
    "l.plea_offer": "The warden of {port} makes you an offer on your fine of {fine}: pay it all, or pay less and sit "
                    "in the gaol a while.",

    # Family lines that still leaned on innuendo.
    "storm.hull.1": "Planks sprung, seams weeping. She's a leaky ship and I'm a soggy first mate. Find us a yard, "
                    "Captain.",
    "storm.hull.2": "Our timbers are bruised from stem to stern. She needs a careful hand and a good yard.",
    "legend.palace.palace.kept.1": "There you are, you clever thing. I am Otohime, daughter of the Dragon King. You "
                                   "kept my handmaid fed and unsold, Captain. What shall I do with you?",

    # "Darling" becomes "Captain": every character addresses the players as captains.
    "battle.foe.agent.reprice.2": "Lying to a woman with a ledger. That will cost you, Captain.",
    "battle.foe.agent.victory.2": "You should have paid, Captain. It would have been so much cheaper.",
    "battle.foe.pirate.paid.2": "Sail on, Captain. You are under my peony now.",
    "battle.foe.pirate.retreat.0": "Throw it all overboard, Captain. I will have my divers fetch it.",
    "battle.foe.pirate.sighting.0": "Li Yue does not chase, Captain. She waits. And here you are.",
    "battle.foe.pirate.spite.0": "If the cargo will not be mine, Captain, it will be the sea's.",
    "battle.foe.pirate.victory.0": "Into the boats, Captain. My sea keeps what it takes, and your crew can row home.",
    "legend.ledger.page.open.0": "A fishwife wrapped your mullet in a page torn from a ledger, Captain. Fine hand, red "
                                 "ink, and a column of names that owe more than they can bear.",
    "legend.palace.palace.freed.2": "You went, of course. Nobody says no to pearls. On the third night she asked what "
                                    "you wanted. Careful, Captain.",
    "legend.palace.palace.serve.1": "She smiled like a moneylender and was gone. The box hums at night, Captain. I'd "
                                    "sleep on deck.",
    "legend.share.say.flag.2": "Take the flag. Take the port share it buys you. Li Yue pays her debts, Captain, and "
                               "she always comes back for what she has lent.",
    "legend.share.say.teller_drowned.1": "You chose well, Captain, and the sea has put a port share in your name. I "
                                         "kept it safe for you. Mind your fingers. It is still cold.",
    "legend.share.say.teller_tavern.1": "The sea is paying you a port share, Captain. Turns out behaving yourself is "
                                        "worth something. Don't tell my regulars. It would ruin them.",
    "st.host.happy": "Your numbers are climbing, Captain. I adore a rising house.",
}


def apply_say(say):
    """Drops voice-only versions of overridden lines from cast.SAY, so the voice reads what the screen shows."""
    for k in OVERRIDES:
        say.pop(k, None)
