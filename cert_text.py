"""Wording for the Voyage Certificate (certificate.py, web/certificate.js; 21 Nov 2026). Merged into
strings.EN / strings.FAMILY at import, so every line can be edited in Admin > Language & Text. Group "cert".

The certificate is the wallpaper a Captain is handed when the books close: home port behind, home Mayor on the
left, the cast member who defined the voyage on the right. They read one short line as the seal lands. The lines are
the banks below: cert.say.<who>.<good|bad>.<n>, written in the house voice (house_voice.HOUSE_STYLE), each
speaker in their own voice, with a clean version in FAMILY. No numbers in any of them, so each is recorded once
and replays for free. Every Port Authority officer shares the "officer" bank and reads it in their own voice.
"""

EN = {
    # ---- on the certificate itself ---------------------------------------------------------------
    "cert.title": "Certificate of the Voyage",
    "cert.place": "{ord} of {n} Houses",
    "cert.ord_one": "{n}st",
    "cert.ord_two": "{n}nd",
    "cert.ord_few": "{n}rd",
    "cert.ord_other": "{n}th",
    "cert.career_best": "Best of {n} {len} voyages",
    "cert.career_place": "{ord} best of {n} {len} voyages",
    "cert.career_first": "A first {len} voyage",
    "cert.len": "{years}-year",                 # a game length with no wording of its own below
    "cert.len_5": "five-year",
    "cert.len_10": "ten-year",
    "cert.len_20": "twenty-year",
    "cert.len_50": "fifty-year",
    "cert.bad": "Survived the China Seas",
    "cert.captain": "Captain {name}",
    "cert.house": "of the House of {firm}",
    "cert.worth": "Final net worth",
    "cert.span": "{first} to {last} · a {len} voyage out of {port}",
    "cert.span_short": "{first} to {last} · out of {port}",
    "cert.best_sale": "Best sale",
    "cert.best_sale_value": "{profit} profit",
    "cert.best_sale_sub": "{qty} {good}, sold in {port}",
    "cert.best_sale_none": "None in profit",
    "cert.best_sale_none_sub": "The sea kept the margins",
    "cert.battles": "Battles won",
    "cert.battles_value": "{won} of {n}",
    "cert.battles_sub": "{sunk} enemy ships sunk",
    "cert.battles_none": "None fought",
    "cert.battles_none_sub": "A quiet sea all voyage",
    "cert.signed": "Her Worship the Mayor",
    "cert.mayor": "Mayor of {port}",
    "cert.closed": "The books are closed",
    # ---- the certificate screen ------------------------------------------------------------------
    "cert.save": "Save as wallpaper",
    "cert.change": "Change the pictures",
    "cert.continue": "Continue to the Ledger",
    "cert.close": "Close",
    "cert.again": "Hear the line again",
    "cert.hold": "On an iPad, press and hold the picture and choose Save to Photos.",
    "cert.working": "Sealing your certificate…",
    "cert.failed": "The certificate could not be drawn. The Ledger of the Voyage has every figure.",
    "cert.saved": "Saved. Set it as your wallpaper from your pictures.",
    "cert.file": "{brand} - Captain {name} - {date}",
    "end.certificate": "Open your Certificate of the Voyage",

    # ---- Powder O'Rourke (bosun): bawdy and loud ---------------------------------------------------
    "cert.say.bosun.good.0": "Well fought, Captain! You kept my guns hot the whole voyage, and I do love a captain who never lets a girl cool down.",
    "cert.say.bosun.good.1": "Look at that, {name}: every pirate on this sea knows your broadside now. I taught you everything except when to stop, and thank God for that.",
    "cert.say.bosun.good.2": "Hang that on your wall, Captain. Powder and glory, and you handled both like someone who reads the instructions afterwards.",
    "cert.say.bosun.good.3": "A fine voyage! My ramrods are worn smooth and my girls are grinning. Whatever you did out there, Captain, do it again.",
    "cert.say.bosun.bad.0": "Still afloat, Captain, and that counts. I've seen prettier finishes, but never one that tried so hard to go down swinging.",
    "cert.say.bosun.bad.1": "Never mind the figures, {name}. You've still got your ship, your nerve and me, and two of those are loaded.",

    # ---- Admiral Li Yue (pirate): cold and slow, speaks of herself by name -------------------------
    "cert.say.pirate.good.0": "Li Yue signs nothing, Captain. But she looked at your certificate for a long time, and Li Yue does not look twice at anything she cannot have.",
    "cert.say.pirate.good.1": "You crossed her sea and kept your cargo. Li Yue finds that rude, and rather attractive.",
    "cert.say.pirate.good.2": "A worthy voyage. Li Yue has sunk better captains for less. She let you finish because she wanted to see how you would end.",
    "cert.say.pirate.good.3": "Hang it where her spies can see it, Captain. Li Yue likes to know exactly where her favourite prize is kept.",
    "cert.say.pirate.bad.0": "Li Yue took what she wanted and left you your life. Think of it as her way of saying she would like to see you again.",
    "cert.say.pirate.bad.1": "You are still breathing, Captain. Li Yue is not careless. She is saving you.",

    # ---- Madam Shek Yu-lan (agent): silky and amused -----------------------------------------------
    "cert.say.agent.good.0": "Congratulations, Captain. My girls gave you a great deal of trouble and you handled every one of them. I am told the feeling was mutual.",
    "cert.say.agent.good.1": "Such a pretty certificate. I shall tell the tea house you came through us again and again and never once paid for it.",
    "cert.say.agent.good.2": "You sank more of my junks than is polite, {name}. Come to the Praya and apologise properly. Bring the certificate. Leave the guns.",
    "cert.say.agent.good.3": "A fortune made in my waters, Captain. I do admire someone who takes their time and still finishes first.",
    "cert.say.agent.bad.0": "Poor Captain. My girls were rough with you. I could say I am sorry, but they did enjoy themselves so.",
    "cert.say.agent.bad.1": "You finished with very little, {name}. On the Praya we would say you were well looked after.",

    # ---- Madam Wu Lian (lender): velvet-warm, speaks of herself as Madam Wu ------------------------
    "cert.say.lender.good.0": "Madam Wu remembers when you came to her with nothing but a junk and a hopeful face. Look at you now. She always did like watching you grow.",
    "cert.say.lender.good.1": "A handsome fortune, Captain. Madam Wu's interest in you was never only monthly.",
    "cert.say.lender.good.2": "Paid in full and hung on the wall. Madam Wu will miss having you in her debt. You were so prompt when you were frightened.",
    "cert.say.lender.good.3": "Madam Wu has read every figure on this certificate twice, darling. Some of them made her reach for her fan.",
    "cert.say.lender.bad.0": "Madam Wu's books say you owe her, and her heart says you tried. Sadly, darling, only one of them charges interest.",
    "cert.say.lender.bad.1": "Never mind, Captain. Come back with a junk and a hopeful face. Madam Wu enjoyed you so much the first time.",

    # ---- the Port Authority officers (shared bank; each reads it in their own voice) -----------------
    "cert.say.officer.good.0": "The Port Authority congratulates you, Captain. We have been through your holds so often I feel we have been properly introduced.",
    "cert.say.officer.good.1": "A fine certificate. I stamped a great deal of your paper this voyage, Captain, and I must say you declare beautifully when you put your mind to it.",
    "cert.say.officer.good.2": "You paid this port more than any other, Captain. I have told the girls at the desk to smile when they search you.",
    "cert.say.officer.good.3": "Everything in order at last. Do come back, Captain. My desk is so dull when nobody is trying to slip something past me.",
    "cert.say.officer.bad.0": "The Port Authority thanks you for your generous contributions, Captain. You gave and gave. I only wish you had kept a little for yourself.",
    "cert.say.officer.bad.1": "I took rather a lot from you, Captain. If it helps, I thought of you every time I counted it.",

    # ---- Mrs. Evelyn Marlowe, the Registrar (taxlady): conspiratorial ------------------------------
    "cert.say.taxlady.good.0": "Between us, Captain, I wrote your name at the top of my register before the ink on this was dry. I do like a captain on top of my book.",
    "cert.say.taxlady.good.1": "That sale of yours is the talk of the harbour. I may have whispered where to go, {name}, but you are the one who went all the way.",
    "cert.say.taxlady.good.2": "Lean in, Captain. Nobody in my register has ever made a killing like yours, and I have been keeping it a very long time.",
    "cert.say.taxlady.good.3": "A certificate and a fortune. You did listen to my little tips after all. I shall have to think of something else to whisper.",
    "cert.say.taxlady.bad.0": "It is all in my register, Captain, the good months and the others. Don't worry. I only show the others to people I like.",
    "cert.say.taxlady.bad.1": "Not your voyage, {name}. Come and see me before the next one. I shall tell you something worth knowing, and close the door first.",

    # ---- Madame Anahit Sarkissian (gamemaster): regal ringmistress ---------------------------------
    "cert.say.gamemaster.good.0": "The table rises for you, Captain. I have dealt for kings, and none of them held their nerve as long as you did.",
    "cert.say.gamemaster.good.1": "A splendid game, {name}. I rang the bell for you so often my wrist has quite a reputation.",
    "cert.say.gamemaster.good.2": "Take your certificate, Captain. The house always wins, they say, and tonight the house is yours. Do be gentle with it.",
    "cert.say.gamemaster.good.3": "The Queen of the Hour declares the voyage well played. Now come here and let me see who I have been dealing to all this time.",
    "cert.say.gamemaster.bad.0": "The cards were unkind, Captain, and I dealt every one of them. I should say sorry. I shall say: again?",
    "cert.say.gamemaster.bad.1": "You lost beautifully, {name}. Sit down. The table loves a captain who does not know when to stop.",
}

# Family-friendly wording: the same thought, said straight.
FAMILY = {
    "cert.say.bosun.good.0": "Well fought, Captain! You kept my guns busy the whole voyage.",
    "cert.say.bosun.good.1": "Every pirate on this sea knows your broadside now, {name}. Well done.",
    "cert.say.bosun.good.2": "Hang that on your wall, Captain. Powder and glory, and you earned both.",
    "cert.say.bosun.good.3": "A fine voyage! The gun crews are grinning. Do it again, Captain.",
    "cert.say.bosun.bad.0": "Still afloat, Captain, and that counts. You went down swinging.",
    "cert.say.bosun.bad.1": "Never mind the figures, {name}. You still have your ship and your nerve.",
    "cert.say.pirate.good.0": "Li Yue signs nothing, Captain. But she read your certificate with respect.",
    "cert.say.pirate.good.1": "You crossed her sea and kept your cargo. Li Yue is impressed.",
    "cert.say.pirate.good.2": "A worthy voyage. Li Yue let you finish because you earned it.",
    "cert.say.pirate.good.3": "Hang it where everyone can see it, Captain. Li Yue will remember your name.",
    "cert.say.pirate.bad.0": "Li Yue took her share and left you your ship. Sail again, Captain.",
    "cert.say.pirate.bad.1": "You are still sailing, Captain. Li Yue respects a survivor.",
    "cert.say.agent.good.0": "Congratulations, Captain. My crews gave you a great deal of trouble and you beat every one.",
    "cert.say.agent.good.1": "Such a pretty certificate. I shall tell the tea house you came through us every time.",
    "cert.say.agent.good.2": "You sank more of my junks than is polite, {name}. Come to the Praya for tea.",
    "cert.say.agent.good.3": "A fortune made in my waters, Captain. Well sailed.",
    "cert.say.agent.bad.0": "Poor Captain. My crews were hard on you. Better luck next voyage.",
    "cert.say.agent.bad.1": "You finished with very little, {name}. The sea was not kind.",
    "cert.say.lender.good.0": "Madam Wu remembers when you had nothing but a junk. Look at you now.",
    "cert.say.lender.good.1": "A handsome fortune, Captain. Madam Wu is proud to have backed you.",
    "cert.say.lender.good.2": "Paid in full and hung on the wall. Madam Wu will miss your custom.",
    "cert.say.lender.good.3": "Madam Wu has read every figure on this certificate twice. Well done.",
    "cert.say.lender.bad.0": "Madam Wu's books say you owe her, but she knows you tried.",
    "cert.say.lender.bad.1": "Never mind, Captain. Come back and start again. Madam Wu will be here.",
    "cert.say.officer.good.0": "The Port Authority congratulates you, Captain. We know your ships well by now.",
    "cert.say.officer.good.1": "A fine certificate. I stamped a great deal of your paper this voyage, Captain.",
    "cert.say.officer.good.2": "You paid this port more than any other, Captain. You are always welcome at my desk.",
    "cert.say.officer.good.3": "Everything in order at last. Do come back, Captain.",
    "cert.say.officer.bad.0": "The Port Authority thanks you for your contributions, Captain. Better luck next voyage.",
    "cert.say.officer.bad.1": "I took rather a lot from you, Captain. The rules are the rules.",
    "cert.say.taxlady.good.0": "Between us, Captain, I wrote your name at the top of my register.",
    "cert.say.taxlady.good.1": "That sale of yours is the talk of the harbour, {name}. Well done.",
    "cert.say.taxlady.good.2": "Nobody in my register has made a sale like yours, Captain.",
    "cert.say.taxlady.good.3": "A certificate and a fortune. You did listen to my tips after all.",
    "cert.say.taxlady.bad.0": "It is all in my register, Captain, the good months and the others.",
    "cert.say.taxlady.bad.1": "Not your voyage, {name}. Come and see me before the next one.",
    "cert.say.gamemaster.good.0": "The table rises for you, Captain. A voyage well played.",
    "cert.say.gamemaster.good.1": "A splendid game, {name}. I rang the bell for you many times.",
    "cert.say.gamemaster.good.2": "Take your certificate, Captain. Tonight the house is yours.",
    "cert.say.gamemaster.good.3": "The Queen of the Hour declares the voyage well played.",
    "cert.say.gamemaster.bad.0": "The cards were unkind, Captain. Shall we play again?",
    "cert.say.gamemaster.bad.1": "You lost with style, {name}. Sit down and play again.",
}

# Who has a bank of her own. A Port Authority officer (cast key "officer_<port>") reads the "officer" bank.
SPEAKERS = ("bosun", "pirate", "agent", "lender", "officer", "taxlady", "gamemaster")
SAY_KEYS = [k for k in EN if k.startswith("cert.say.")]


def bank(who, mood):
    """The line keys for one speaker and mood ("good" or "bad"), in order."""
    who = "officer" if str(who).startswith("officer_") else who
    prefix = "cert.say.{}.{}.".format(who, "bad" if mood == "bad" else "good")
    return sorted((k for k in SAY_KEYS if k.startswith(prefix)), key=lambda k: int(k.rsplit(".", 1)[1]))
