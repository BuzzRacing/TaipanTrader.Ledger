"""Crimson Ledger: the wording for the Game 4 review changes (20 Nov 2026).

Three kinds of enemy at sea (raiders, a small lucky band, Admiral Li Yue's war fleet), sparing a band for a
price they know, escorts that limp home crippled, ships laid up at home, wages carried by empty hold, and
the Mayor saying when she has work for the house.

EN is the house voice (house_voice.HOUSE_STYLE: sexy, funny, innuendo, never explicit, each woman in her
own voice). FAMILY is the clean wording for family-friendly screens. Lines with amounts are Captain's Log
lines, shown and never read aloud (voice.LOG_RANK leaves them under the floor); the spoken lines carry no
amounts, so each is recorded once and replayed for free.
"""

EN = {
    # Small words
    "w.raider_junks": "raider junks",
    "w.band_junks": "junks of a lucky little band",
    "w.lay_up": "Laying a ship up",

    # The three kinds of enemy, for the battle screen's header
    "battle.fleet.raiders": "Raiders: fast, lightly gunned, after your hold",
    "battle.fleet.band": "A small band: weak, and they talk if you spare them",
    "battle.fleet.war": "The war fleet: tough, costly, and the booty is huge",

    # Powder sights them (spoken; no amounts)
    "battle.say.sighting_raiders.0": "Raiders, Captain! Quick little things, and every one of them has her eye on our hold.",
    "battle.say.sighting_raiders.1": "Fast junks, light guns, wandering hands. Raiders. They want the cargo, not a fight.",
    "battle.say.sighting_raiders.2": "Raiders off the bow! They'll grab what they can and run. Shall we make them work for it?",
    "battle.say.sighting_raiders.3": "Raiders, Captain. All speed and no stamina. We can outrun this lot without breaking a sweat.",
    "battle.say.sighting_band.0": "Oh, look at them. A little band of nobodies, Captain, punching well above their weight.",
    "battle.say.sighting_band.1": "A handful of ragged junks, Captain. Brave, I'll give them that. Brave and very, very lonely.",
    "battle.say.sighting_band.2": "A small band, Captain. Give them one good broadside and they'll be begging to tell us their secrets.",
    "battle.say.sighting_band.3": "That's not a fleet, Captain, that's a flirtation. Shall we let them down gently?",
    "battle.say.sighting_war.0": "War junks, Captain. Li Yue's own, big and mean and built to hurt. And their holds are fat with silver.",
    "battle.say.sighting_war.1": "The war fleet! This one's going to cost us, Captain. But oh, what they're carrying.",
    "battle.say.sighting_war.2": "Li Yue's heavies, Captain. Thick hulls, long guns, and booty enough to make a girl weak at the knees.",
    "battle.say.sighting_war.3": "The war fleet, Captain. They hit hard and they don't stop. Pay them, run, or brace yourself.",

    # Sparing a band
    "battle.btn.spare": "Spare them",
    "battle.btn.spare_sub": "Let them go; they'll tell you a price",
    "battle.ack.spare": "Mercy, Captain. How very generous of you.",
    "battle.cap.spared": "Spared. They whisper: {goods} sells dear in {where}.",
    "battle.say.spared.0": "They've struck their colours, Captain, and now they're singing. Every secret they've got.",
    "battle.say.spared.1": "Let them go, Captain? Soft-hearted. They're so grateful they told us where the money is.",
    "battle.say.spared.2": "Mercy suits you, Captain. And look, they've paid for it with a very juicy bit of gossip.",
    "battle.say.spared.3": "Off they scuttle. Whispered a price in my ear on the way past, the darlings.",
    "battle.res.spared": "Spared them",
    "battle.res.reason_spared": "You let the little band go, and they told you what they know.",
    "l.spared": "You spared the last {n} of a little band. They were very grateful, Captain. Very.",
    "l.band_tip": "Their parting gift: {goods} is fetching {price} in {where}.",
    "n.fight_spared": "{name} of {firm} beat {n} {enemy} off {port}, then let them go. Mercy, beauties! Who knew?",
    "e.no_spare": "There's no one here to spare, Captain. Only a small band, after the first broadside.",

    # Crippled escorts
    "battle.cap.crippled": "{name} is crippled and out of the fight",
    "battle.say.crippled.0": "She's not sinking, Captain! Barely afloat, guns gone, but she's limping home.",
    "battle.say.crippled.1": "They've wrecked her, but she's still floating. Pull her back, she's done her bit.",
    "battle.say.crippled.2": "Crippled, Captain, not sunk. A bit battered, but nothing a good shipwright can't put right.",
    "battle.say.crippled.3": "She's out of the fight, Captain, stripped of every gun and still afloat. Tough old girl.",
    "l.crippled": "The {ship} '{name}' limped out of the fight crippled: hull 1, every gun gone. She'll need a shipyard, Captain.",

    # Laying ships up at home
    "m.laid_up": "{name} is laid up in {home}. Feet up, sails down, on quarter wages.",
    "m.recalled": "{name} is back with the fleet. Rested, refreshed and raring to go, Captain.",
    "e.last_ship_lay": "You can't lay up your only ship, Captain. Who would carry you?",
    "e.last_trader_lay": "Keep at least one merchantman at sea, Captain. Somebody has to do the carrying.",
    "fleet.lay_up": "Lay up",
    "fleet.lay_up_tip": "Leave her in {home} on {wage} a month (a quarter of her wage). Call her back any month you're home.",
    "fleet.recall": "Call back",
    "fleet.laid_up_title": "Laid up in {home}",
    "fleet.laid_up_info": "These ships rest in the home harbour on a quarter of their wages. They don't sail, carry or fight, but still count against each class's limit.",
    "fleet.laid_up_row": "{wage} a month (full wage {full})",
    "fleet.laid_up_away": "Call them back when you're home in {home}.",
    "fleet.wage": "Wages {wage}/month",
    "fleet.crippled": "Crippled",
    "fleet.crippled_tip": "Hull 1, every gun gone. Mending her costs about a third of a new one.",

    # Wages carried by empty hold
    "l.idle_wages": "{idle} of this month's {wages} in wages carried empty hold ({pct}% empty). Lovely ships, Captain, but they're paid to carry.",
    "port.todo.idle": "Last month {idle} of your wages carried empty hold ({pct}% empty). Fill it, or lay some ships up at home.",
    "port.acct.idle": "Wages carried by empty hold: {last} last month, {year} this year, {game} this game.",

    # The Mayor's work
    "l.contract_offer": "The Mayor of {home} has {n} new commission{s} for you, Captain. She says she's been waiting.",
    "port.todo.contract": "The Mayor has {n} commission{s} on offer for you.",
}

FAMILY = {
    "w.band_junks": "junks of a lucky little band",
    "battle.fleet.raiders": "Raiders: fast, lightly gunned, after your cargo",
    "battle.say.sighting_raiders.0": "Raiders, Captain! Quick little ships, and every one of them is after our cargo.",
    "battle.say.sighting_raiders.1": "Fast junks, light guns. Raiders. They want the cargo, not a fight.",
    "battle.say.sighting_raiders.2": "Raiders off the bow! They'll grab what they can and run. Shall we make them work for it?",
    "battle.say.sighting_raiders.3": "Raiders, Captain. All speed and no stamina. We can outrun this lot.",
    "battle.say.sighting_band.0": "A little band of nobodies, Captain, punching well above their weight.",
    "battle.say.sighting_band.1": "A handful of ragged junks, Captain. Brave, I'll give them that.",
    "battle.say.sighting_band.2": "A small band, Captain. One good broadside and they'll be glad to tell us what they know.",
    "battle.say.sighting_band.3": "That's hardly a fleet, Captain. Shall we teach them a lesson?",
    "battle.say.sighting_war.0": "War junks, Captain. Li Yue's own, big and built to hurt. And their holds are full of silver.",
    "battle.say.sighting_war.1": "The war fleet! This one's going to cost us, Captain. But think what they're carrying.",
    "battle.say.sighting_war.2": "Li Yue's heavies, Captain. Thick hulls, long guns, and a fortune in booty.",
    "battle.ack.spare": "Mercy, Captain. That's generous of you.",
    "battle.say.spared.0": "They've struck their colours, Captain, and now they're telling us everything they know.",
    "battle.say.spared.1": "We let them go, Captain, and they were so grateful they told us where the money is.",
    "battle.say.spared.2": "Mercy suits you, Captain. And they've paid for it with a useful bit of news.",
    "battle.say.spared.3": "Off they go. They told us a price on the way past.",
    "l.spared": "You spared the last {n} of a little band. They were very grateful, Captain.",
    "n.fight_spared": "{name} of {firm} beat {n} {enemy} off {port}, then let them go.",
    "battle.say.crippled.1": "They've wrecked her, but she's still floating. Pull her back, she's done her part.",
    "battle.say.crippled.2": "Crippled, Captain, not sunk. Nothing a good shipwright can't put right.",
    "battle.say.crippled.3": "She's out of the fight, Captain, every gun gone, but still afloat.",
    "m.laid_up": "{name} is laid up in {home}, on quarter wages.",
    "m.recalled": "{name} is back with the fleet, Captain.",
    "l.idle_wages": "{idle} of this month's {wages} in wages carried empty hold ({pct}% empty).",
    "l.contract_offer": "The Mayor of {home} has {n} new commission{s} for you, Captain.",
}
