"""Crimson Ledger: banks of buy and sell lines for the comprador (Lau Siu-wah), so a busy trader doesn't
hear the same receipt every time (owner's request, 20 Nov 2026: "too repetitive, I make a lot of trades").

Each trade draws the next line from a shuffled deck per house (engine _draw), so no line repeats until the
whole bank has been heard. Banks:
    m.bought.N       a purchase
    m.sold.N         a sale at a profit (or about even)
    m.sold_loss.N    a sale for less than the cargo cost
    m.sold_store.N   selling hold and warehouse together ("Sell all")
The plain m.bought / m.sold / m.sold_store lines stay as the fallback if a bank is blanked in Admin.

Every screen line keeps the receipt first ("Bought {qty} {good} for {cost}.") and then the wink, in the
house voice (house_voice.HOUSE_STYLE). The voice says SAY instead: the same wink with no amounts, and the
opening varied too, so each line is recorded once per cargo and replayed for free. FAMILY / SAY_FAMILY
are the clean versions for family-friendly screens.
"""

BUY = "Bought {qty} {good} for {cost}. "
SELL = "Sold {qty} {good} for {gain}. "
STORE = "Sold {qty} {good} from the hold and warehouse for {gain}. "

# (wink on screen, spoken version, family wink, family spoken)
_BOUGHT = [
    ("Nice and weighty, darling. I like a full hold.", "{good} bought. Nice and weighty, darling. I like a full hold.",
     "Good choice, Captain.", "{good} bought. Good choice, Captain."),
    ("I do love a captain who knows what she wants.", "{good}, all yours. I do love a captain who knows what she wants.",
     "A captain who knows what she wants. Refreshing.", "{good}, all yours. A captain who knows what she wants."),
    ("Load it slowly, darling. Savour it.", "Bought {good}. Load it slowly, darling. Savour it.",
     "Load it carefully, Captain.", "Bought {good}. Load it carefully, Captain."),
    ("Don't tell anyone who sold it to you, Captain.", "{good} is yours. Don't tell anyone who sold it to you, Captain.",
     "Keep my name out of it, Captain.", "{good} is yours. Keep my name out of it, Captain."),
    ("Your hold looks better full. So do you.", "There's your {good}. Your hold looks better full. So do you.",
     "Your hold looks better full.", "There's your {good}. Your hold looks better full."),
    ("Signed, sealed and stowed, darling.", "{good}, signed, sealed and stowed, darling.",
     "Signed, sealed and stowed.", "{good}, signed, sealed and stowed."),
    ("Mm. You buy like you mean it, Captain.", "{good} it is. Mm. You buy like you mean it, Captain.",
     "You buy like you mean it, Captain.", "{good} it is. You buy like you mean it, Captain."),
    ("There. Now you're carrying something worth stealing.", "Bought {good}. Now you're carrying something worth stealing.",
     "Now you're carrying something worth guarding.", "Bought {good}. Now you're carrying something worth guarding."),
    ("A firm grip on the market, Captain. I noticed.", "{good} bought. A firm grip on the market, Captain. I noticed.",
     "A firm grip on the market, Captain.", "{good} bought. A firm grip on the market, Captain."),
    ("Handle it gently, darling. It's been in good hands.", "Your {good}, Captain. Handle it gently, darling. It's been in good hands.",
     "Handle it with care, Captain.", "Your {good}, Captain. Handle it with care."),
    ("My shelves are lighter, your hold is heavier. Everybody's satisfied.", "{good} bought. My shelves are lighter, your hold is heavier. Everybody's satisfied.",
     "My shelves are lighter and your hold is heavier.", "{good} bought. My shelves are lighter and your hold is heavier."),
    ("Don't keep it waiting too long, Captain. Good things spoil.", "Bought {good}. Don't keep it waiting too long, Captain. Good things spoil.",
     "Don't sit on it too long, Captain.", "Bought {good}. Don't sit on it too long, Captain."),
    ("You've filled a gap in my ledger, darling. Come back and fill another.", "{good}, sold to you. You've filled a gap in my ledger, darling. Come back and fill another.",
     "You've filled a gap in my ledger, Captain.", "{good}, sold to you. You've filled a gap in my ledger."),
    ("Spend like that and I'll have to put the kettle on.", "That's the {good}. Spend like that and I'll have to put the kettle on.",
     "Spend like that and I'll put the kettle on.", "That's the {good}. Spend like that and I'll put the kettle on."),
    ("Stow it deep, Captain. The best things are kept low and out of sight.", "Bought {good}. Stow it deep, Captain. The best things are kept low and out of sight.",
     "Stow it deep, Captain, out of sight.", "Bought {good}. Stow it deep, Captain, out of sight."),
    ("I'll write it in my little book. You have a page all to yourself.", "{good} bought. I'll write it in my little book. You have a page all to yourself.",
     "I'll write it in my book, Captain.", "{good} bought. I'll write it in my book, Captain."),
    ("There's more where that came from, darling. There always is with me.", "{good}, yours. There's more where that came from, darling. There always is with me.",
     "There's more where that came from.", "{good}, yours. There's more where that came from."),
    ("Bought and paid for, Captain. Not many things on this wharf are.", "Your {good}, bought and paid for, Captain. Not many things on this wharf are.",
     "Bought and paid for, Captain.", "Your {good}, bought and paid for, Captain."),
    ("Take it before I change my mind. I won't, but let me pretend.", "{good} bought. Take it before I change my mind. I won't, but let me pretend.",
     "Take it before I change my mind.", "{good} bought. Take it before I change my mind."),
    ("A sweet bargain, Captain. Sweet for one of us, anyway.", "{good}, done. A sweet bargain, Captain. Sweet for one of us, anyway.",
     "A fair bargain, Captain. Mostly fair.", "{good}, done. A fair bargain, Captain. Mostly fair."),
    ("Your purser will weep, darling. I'm smiling.", "Bought {good}. Your purser will weep, darling. I'm smiling.",
     "Your purser will weep, Captain.", "Bought {good}. Your purser will weep, Captain."),
    ("Tie it down tight, darling. The sea likes to grab.", "{good} going aboard. Tie it down tight, darling. The sea likes to grab.",
     "Tie it down tight, Captain.", "{good} going aboard. Tie it down tight, Captain."),
    ("I can tell you've done this before, Captain.", "{good} bought. I can tell you've done this before, Captain.",
     "You've done this before, Captain.", "{good} bought. You've done this before, Captain."),
    ("A pleasure doing business, darling. And I do mean pleasure.", "There's your {good}. A pleasure doing business, darling. And I do mean pleasure.",
     "A pleasure doing business, Captain.", "There's your {good}. A pleasure doing business, Captain."),
    ("Easy, Captain. Leave a little for the other girls.", "{good} bought. Easy, Captain. Leave a little for the other girls.",
     "Leave a little for the others, Captain.", "{good} bought. Leave a little for the others, Captain."),
]

_SOLD = [
    ("Letting go so gracefully, Captain. Not everyone can.", "{good} sold. Letting go so gracefully, Captain. Not everyone can.",
     "You know when to let go, Captain.", "{good} sold. You know when to let go, Captain."),
    ("Silver in your hand and a smile on my face. Fair trade.", "Sold the {good}. Silver in your hand and a smile on my face. Fair trade.",
     "Silver in your hand. Fair trade.", "Sold the {good}. Silver in your hand. Fair trade."),
    ("You drive a hard bargain, darling. I don't mind a little pressure.", "{good} sold. You drive a hard bargain, darling. I don't mind a little pressure.",
     "You drive a hard bargain, Captain.", "{good} sold. You drive a hard bargain, Captain."),
    ("Profit looks good on you, Captain.", "Your {good}, sold. Profit looks good on you, Captain.",
     "Profit suits you, Captain.", "Your {good}, sold. Profit suits you, Captain."),
    ("Lighter hold, heavier purse. The best way round.", "{good} gone. Lighter hold, heavier purse. The best way round.",
     "Lighter hold, heavier purse.", "{good} gone. Lighter hold, heavier purse."),
    ("Count it twice, darling. I always do.", "Sold the {good}. Count it twice, darling. I always do.",
     "Count it twice, Captain.", "Sold the {good}. Count it twice, Captain."),
    ("I'll take that off you, Captain. Again and again, if you like.", "{good} sold. I'll take that off you, Captain. Again and again, if you like.",
     "I'll take more any time, Captain.", "{good} sold. I'll take more any time, Captain."),
    ("Now that's what I call a clean finish.", "{good}, sold. Now that's what I call a clean finish.",
     "A clean finish, Captain.", "{good}, sold. A clean finish, Captain."),
    ("Very nice, Captain. You made me pay for that one.", "Sold your {good}. Very nice, Captain. You made me pay for that one.",
     "You made me pay for that one, Captain.", "Sold your {good}. You made me pay for that one, Captain."),
    ("Emptied out and well paid. Every captain's dream.", "{good} sold. Emptied out and well paid. Every captain's dream.",
     "Unloaded and well paid.", "{good} sold. Unloaded and well paid."),
    ("My ledger groans, Captain. Yours sings.", "{good}, done. My ledger groans, Captain. Yours sings.",
     "My ledger groans. Yours sings.", "{good}, done. My ledger groans. Yours sings."),
    ("Bought low, sold to me. Clever and cruel.", "Sold the {good}. Bought low, sold to me. Clever and cruel.",
     "Bought low, sold to me. Clever.", "Sold the {good}. Bought low, sold to me. Clever."),
    ("Don't let it go to your head, darling. Let it go to the bank.", "{good} sold. Don't let it go to your head, darling. Let it go to the bank.",
     "Don't let it go to your head. Let it go to the bank.", "{good} sold. Don't let it go to your head. Let it go to the bank."),
    ("Lovely doing business with you, darling. Do come round again.", "{good}, sold. Lovely doing business with you, darling. Do come round again.",
     "Do come round again, Captain.", "{good}, sold. Do come round again, Captain."),
    ("I'll pass it on with a little mark-up. We all have our pleasures.", "Your {good} is mine now. I'll pass it on with a little mark-up. We all have our pleasures.",
     "I'll pass it on with a little mark-up.", "Your {good} is mine now. I'll pass it on with a little mark-up."),
    ("There's your silver, still warm from my strongbox.", "{good} sold. There's your silver, still warm from my strongbox.",
     "There's your silver, Captain.", "{good} sold. There's your silver, Captain."),
    ("You brought it all this way just for me? I'm touched.", "Sold the {good}. You brought it all this way just for me? I'm touched.",
     "You brought it all this way for me? Kind.", "Sold the {good}. You brought it all this way for me? Kind."),
    ("Hear that, darling? Money changing hands. My favourite music.", "{good} sold. Hear that, darling? Money changing hands. My favourite music.",
     "Money changing hands. My favourite sound.", "{good} sold. Money changing hands. My favourite sound."),
    ("I'm almost sorry to see you so pleased with yourself. Almost.", "{good}, sold. I'm almost sorry to see you so pleased with yourself. Almost.",
     "You look pleased with yourself, Captain.", "{good}, sold. You look pleased with yourself, Captain."),
    ("Done. Now go and buy yourself something pretty.", "Sold your {good}. Now go and buy yourself something pretty.",
     "Now go and buy yourself something nice.", "Sold your {good}. Now go and buy yourself something nice."),
    ("Sharp work, Captain. I'll be sore for a week.", "{good} sold. Sharp work, Captain. I'll be sore for a week.",
     "Sharp work, Captain.", "{good} sold. Sharp work, Captain."),
    ("Off your hands and into mine. They're very capable hands.", "{good}, sold. Off your hands and into mine. They're very capable hands.",
     "Off your hands and into mine.", "{good}, sold. Off your hands and into mine."),
    ("You timed that beautifully, darling. Timing is everything.", "Sold the {good}. You timed that beautifully, darling. Timing is everything.",
     "You timed that well, Captain.", "Sold the {good}. You timed that well, Captain."),
    ("Paid in full. Don't spend it all in one port, sweetheart.", "{good} sold. Paid in full. Don't spend it all in one port, sweetheart.",
     "Don't spend it all in one port.", "{good} sold. Don't spend it all in one port."),
]

_SOLD_LOSS = [
    ("Less than you paid, darling. We all have our off nights.", "{good} sold, at a loss. We all have our off nights, darling.",
     "Less than you paid, Captain. It happens.", "{good} sold, at a loss. It happens, Captain."),
    ("Under cost, darling. I won't tell if you don't.", "{good} sold under cost. I won't tell if you don't, darling.",
     "Under cost, Captain. Our secret.", "{good} sold under cost. Our secret, Captain."),
    ("Ouch. That went out cheaper than it came in.", "{good} sold. Ouch. That went out cheaper than it came in.",
     "That went out cheaper than it came in.", "{good} sold. That went out cheaper than it came in."),
    ("Sometimes you just have to let it go, Captain. Even at a loss.", "{good} gone, for less than it cost. Sometimes you just have to let it go, Captain.",
     "Sometimes you have to let it go, Captain.", "{good} gone, for less than it cost. Sometimes you have to let it go."),
    ("A little poorer, a little wiser. Mostly poorer, darling.", "Sold the {good} at a loss. A little poorer, a little wiser. Mostly poorer, darling.",
     "A little poorer, a little wiser.", "Sold the {good} at a loss. A little poorer, a little wiser."),
    ("Short of what you paid. Better luck in the next port, sweetheart.", "{good} sold, short of what you paid. Better luck in the next port, sweetheart.",
     "Short of what you paid. Better luck next port.", "{good} sold, short of what you paid. Better luck next port."),
    ("I'll take it off your hands, darling. Somebody had to.", "{good} sold at a loss. I'll take it off your hands, darling. Somebody had to.",
     "I'll take it off your hands, Captain.", "{good} sold at a loss. I'll take it off your hands, Captain."),
    ("Not your finest hour, Captain. You'll make it up to yourself.", "{good} sold for less than you paid. Not your finest hour, Captain.",
     "Not your finest hour, Captain.", "{good} sold for less than you paid. Not your finest hour, Captain."),
    ("Down on the deal, darling. Chin up. The rest of you looks fine.", "{good} sold, down on the deal. Chin up, darling. The rest of you looks fine.",
     "Down on the deal. Chin up, Captain.", "{good} sold, down on the deal. Chin up, Captain."),
    ("Bought dear, sold cheap. I've had worse nights, and I'm sure you have too.", "{good} sold. Bought dear, sold cheap. I've had worse nights, and I'm sure you have too.",
     "Bought dear, sold cheap. It happens to us all.", "{good} sold. Bought dear, sold cheap. It happens to us all."),
]

_SOLD_STORE = [
    ("Both of them emptied for me, Captain. You're spoiling me.", "All the {good}, sold from hold and warehouse. You're spoiling me, Captain.",
     "Emptied both, Captain. Very thorough.", "All the {good}, sold from hold and warehouse. Very thorough, Captain."),
    ("Every last crate, darling. You don't do things by halves.", "Every last crate of {good}, sold. You don't do things by halves, darling.",
     "Every last crate. No half measures.", "Every last crate of {good}, sold. No half measures."),
    ("Ship and storehouse both. That's what I call a clear-out.", "{good} sold, ship and storehouse both. That's what I call a clear-out.",
     "Ship and storehouse both. A proper clear-out.", "{good} sold, ship and storehouse both. A proper clear-out."),
    ("Nothing held back. I admire that in a captain.", "All your {good}, sold. Nothing held back. I admire that in a captain.",
     "Nothing held back, Captain.", "All your {good}, sold. Nothing held back, Captain."),
    ("The whole lot in one go. Greedy, Captain. I approve.", "The whole lot of {good}, in one go. Greedy, Captain. I approve.",
     "The whole lot in one go. Bold, Captain.", "The whole lot of {good}, in one go. Bold, Captain."),
    ("Bare from top to bottom, darling. You'll have to fill them up again.", "{good} sold out of hold and warehouse. Bare from top to bottom, darling. You'll have to fill them up again.",
     "Bare from top to bottom. Time to fill up again.", "{good} sold out of hold and warehouse. Time to fill up again."),
    ("The whole lot, Captain. My dock hands will need a lie down.", "Every bit of the {good}, sold. My dock hands will need a lie down, Captain.",
     "My dock hands will need a rest after that.", "Every bit of the {good}, sold. My dock hands will need a rest."),
    ("Cleaned out top to bottom. Very satisfying, darling.", "{good}, cleaned out top to bottom. Very satisfying, darling.",
     "Cleaned out top to bottom.", "{good}, cleaned out top to bottom."),
    ("You saved it all up just for me? Sweet.", "All the {good} at once. You saved it all up just for me? Sweet.",
     "You saved it all up for me? Kind.", "All the {good} at once. You saved it all up for me? Kind."),
    ("Warehouse swept, hold empty, purse full. Perfect, darling.", "{good} sold. Warehouse swept, hold empty, purse full. Perfect, darling.",
     "Warehouse swept, hold empty, purse full.", "{good} sold. Warehouse swept, hold empty, purse full."),
]

# Opium, bought in bulk (BULK_MIN or more): NSFW wording only. Family screens get a clean line they already know.
_BOUGHT_OPIUM = [
    ("Dark, sticky and sold by the chest. Mind where you put your fingers, darling. It clings.",
     "{good} bought. Dark, sticky and sold by the chest. Mind where you put your fingers, darling. It clings.",
     "Good choice, Captain.", "{good} bought. Good choice, Captain."),
    ("Chests and chests of poppy, packed tight and heavy. You'll be dreaming of me all the way to port.",
     "Chests and chests of {good}, packed tight and heavy. You'll be dreaming of me all the way to port.",
     "Load it carefully, Captain.", "Chests of {good}. Load it carefully, Captain."),
    ("Lamp lit, pipe warm, hold full. All that's missing is you staying the night, Captain.",
     "{good}, yours. Lamp lit, pipe warm, hold full. All that's missing is you staying the night, Captain.",
     "Signed, sealed and stowed.", "{good}, signed, sealed and stowed."),
    ("That much smoke is hard to hide, darling. Wrap it tight, stow it deep, and keep a straight face. That's the hard part.",
     "Bought {good}. That much smoke is hard to hide, darling. Wrap it tight, stow it deep, and keep a straight face. That's the hard part.",
     "Bought and paid for, Captain.", "Your {good}, bought and paid for, Captain."),
    ("Chasing the dragon by the chestful? Go gently, Captain. She bites, and I'd hate to lose you.",
     "That's the {good}. Chasing the dragon by the chestful? Go gently, Captain. She bites, and I'd hate to lose you.",
     "A firm grip on the market, Captain.", "{good} bought. A firm grip on the market, Captain."),
]

# A purchase of this many units or more uses the cargo's own bank below (PRODUCT_BUY), if it has one.
BULK_MIN = 50
PRODUCT_BUY = {}
PRODUCT_BUY["opium"] = "m.bought.opium"


# Marijuana, bought in bulk: NSFW wording only. Family screens (where it is Hemp) all get the one clean line.
_BOUGHT_MARIJUANA = [
    ("Sweet, green and stacked to the rafters. Careful, darling. The smell gets into everything, and so do I.",
     "{good} bought. Sweet, green and stacked to the rafters. Careful, darling. The smell gets into everything, and so do I.",
     "Good choice, Captain.", "{good} bought. Good choice, Captain."),
    ("Bales of it, tightly rolled. You do know how to handle a bundle, Captain.",
     "Bales of {good}, tightly rolled. You do know how to handle a bundle, Captain.",
     "Good choice, Captain.", "{good} bought. Good choice, Captain."),
    ("Light a little, darling, not the whole hold. Though I would watch you try.",
     "{good}, yours. Light a little, darling, not the whole hold. Though I would watch you try.",
     "Good choice, Captain.", "{good} bought. Good choice, Captain."),
    ("That much green and I'll be giggling till the next tide. Take it before I get ideas.",
     "That's the {good}. That much green and I'll be giggling till the next tide. Take it before I get ideas.",
     "Good choice, Captain.", "{good} bought. Good choice, Captain."),
    ("Everything goes slow and sweet with this aboard, Captain. Do keep your hands on the wheel. Mostly.",
     "Bought {good}. Everything goes slow and sweet with this aboard, Captain. Do keep your hands on the wheel. Mostly.",
     "Good choice, Captain.", "{good} bought. Good choice, Captain."),
]
PRODUCT_BUY["marijuana"] = "m.bought.marijuana"

EN, FAMILY, SAY, SAY_FAMILY = {}, {}, {}, {}
for _prefix, _lead, _bank in (("m.bought", BUY, _BOUGHT), ("m.sold", SELL, _SOLD),
                              ("m.sold_loss", SELL, _SOLD_LOSS), ("m.sold_store", STORE, _SOLD_STORE)):
    for _i, (_wink, _say, _fwink, _fsay) in enumerate(_bank):
        _k = "{}.{}".format(_prefix, _i)
        EN[_k] = _lead + _wink
        FAMILY[_k] = _lead + _fwink
        SAY[_k] = _say
        SAY_FAMILY[_k] = _fsay

# loop: opium
for _i, (_wink, _say, _fwink, _fsay) in enumerate(_BOUGHT_OPIUM):
    _k = "m.bought.opium.{}".format(_i)
    EN[_k] = BUY + _wink
    FAMILY[_k] = BUY + _fwink
    SAY[_k] = _say
    SAY_FAMILY[_k] = _fsay

# loop: marijuana
for _i, (_wink, _say, _fwink, _fsay) in enumerate(_BOUGHT_MARIJUANA):
    _k = "m.bought.marijuana.{}".format(_i)
    EN[_k] = BUY + _wink
    FAMILY[_k] = BUY + _fwink
    SAY[_k] = _say
    SAY_FAMILY[_k] = _fsay

# Marijuana, sold in bulk at a profit: NSFW wording only. Family screens (where it is Hemp) get the one clean line.
_SOLD_MARIJUANA = [
    ("Fresh green and a buyer already breathless for it. Sweet doing business with you, Captain.",
     "Sold your {good}. Fresh green and a buyer already breathless for it. Sweet doing business with you, Captain.",
     "A pleasure doing business, Captain.", "Sold your {good}. A pleasure doing business, Captain."),
    ("Every last bale gone up in smoke, as it were. Come back when you're stocked, darling.",
     "All that {good}, gone up in smoke, as it were. Come back when you're stocked, darling.",
     "A pleasure doing business, Captain.", "Sold your {good}. A pleasure doing business, Captain."),
    ("They'll be giggling all over the harbor tonight, and you're the cause. Take a bow, Captain.",
     "Sold your {good}. They'll be giggling all over the harbor tonight, and you're the cause. Take a bow, Captain.",
     "A pleasure doing business, Captain.", "Sold your {good}. A pleasure doing business, Captain."),
    ("That's a lot of green changing hands. Count it slowly, darling. I like to watch.",
     "That's a lot of {good} changing hands. Count it slowly, darling. I like to watch.",
     "A pleasure doing business, Captain.", "Sold your {good}. A pleasure doing business, Captain."),
    ("Light up the profit, darling. You've earned a long, slow one.",
     "Sold your {good}. Light up the profit, darling. You've earned a long, slow one.",
     "A pleasure doing business, Captain.", "Sold your {good}. A pleasure doing business, Captain."),
]
PRODUCT_SELL = {"marijuana": "m.sold.marijuana"}
# loop: sold marijuana
for _i, (_wink, _say, _fwink, _fsay) in enumerate(_SOLD_MARIJUANA):
    _k = "m.sold.marijuana.{}".format(_i)
    EN[_k] = SELL + _wink
    FAMILY[_k] = SELL + _fwink
    SAY[_k] = _say
    SAY_FAMILY[_k] = _fsay

KEYS = list(EN)

# Below this share of what the cargo cost, a sale counts as "at a loss" (a sale about even gets a sale line).
LOSS_BELOW = 0.98
