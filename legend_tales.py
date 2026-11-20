"""The Legend and Folklore Library: the Legends themselves, as data (legend.py plays them).

Owner's decisions (20 Nov 2026; project doc "SeaTrader Legends Library"): each story is a LEGEND; it takes over
the screen when it triggers and costs no game time; four to six a game, all big; each in 2 to 4 CHAPTERS, with
the choice in one chapter deciding what comes back months later; stakes scaled to wealth; told by one of three
storytellers, with the Legend's own characters answering on the right.

HOW A LEGEND IS WRITTEN
  TALES[id] = {
    "title":   shown on the screen and in the log,
    "teller":  the storyteller who tells it (legend_cast.STORYTELLERS) unless Admin says otherwise,
    "cast":    its own characters (legend_cast.py keys), for the pictures,
    "start":   {"port": key} it begins on arriving there, or {} for any landfall,
    "chapters": [chapter, ...] in order }
  chapter = {
    "id", "title",
    "where":  a port key, or None for any landfall,
    "scene":  "port" (the port by night), "sea" (open water) or "deep" (under the sea): the picture behind,
    "start":  [(flag, node), ..., (None, node)]: the first whose flag the Captain carries is where it opens,
    "nodes":  {name: node} }
  node = {
    "beats":   [(who, text) or (who, text, family_text), ...]   who is T (the storyteller) or a cast key,
    "fx":      [effect, ...] applied as the node is reached (see legend.py EFFECTS),
    "choices": [(key, button label, node), ...]   the story waits for the Captain, OR
    "goto":    node                                it runs straight on, OR
    "roll":    [(weight, node), ...] with optional "roll_if": {flag: [(weight, node), ...]}   the dice decide, OR
    "end":     True                                the chapter is over (the next one is scheduled, if any) }

EFFECTS (all sized from the house's STAKE: a share of its net worth, rules.legend.stake_share)
  ("silver", x)            x stakes of silver gained (or lost: silver aboard, then the bank, then Madam Wu's books)
  ("cargo", good, x)       x stakes' worth of a cargo, as much as the hold has room for (the rest in silver)
  ("lose_cargo", share)    that share of every cargo in the hold is gone
  ("hull", share)          every ship loses that share of her full hull (never sunk by a Legend)
  ("standing", where, n)   n points of standing: where is "here", "home" or a port key
  ("flag", name)           remembered for the later chapters
  ("news", key)            a headline for the next month's news

WRITING: every spoken line follows the house voice (house_voice.HOUSE_STYLE): the fact plain, a wink riding on
it, innuendo and never explicit. No amounts in a spoken line: figures belong on the Reckoning card. A third
item in a beat is its family-friendly wording.
"""

T = "teller"
O = "legend_otohime"

TALES = {
    # =====================================================================================================
    # THE PALACE BENEATH THE WAVES (Urashima Taro, off Nagasaki). Told by the drowned bride: a legend about
    # lost time, told by the woman who stops the clock.
    # =====================================================================================================
    "palace": {
        "title": "The Palace Beneath the Waves",
        "teller": "teller_drowned",
        "cast": [O],
        "start": {"port": "nagasaki"},
        "chapters": [
            # ---- Chapter 1 ---------------------------------------------------------------------------
            {"id": "turtle", "title": "The Turtle in the Net", "where": "nagasaki", "scene": "port",
             "start": [(None, "open")],
             "nodes": {
                 "open": {
                     "beats": [
                         (T, "Hold still, Captain. The bell has stopped mid-swing, which means it's my turn to talk. "
                             "Don't look so alarmed. I only bite sailors I'm fond of.",
                             "Hold still, Captain. The bell has stopped mid-swing, which means it's my turn to talk. "
                             "Don't look so alarmed. I only haunt sailors I'm fond of."),
                         (T, "Off the Nagasaki roads your crew hauled up a net, and in it a sea turtle the size of a "
                             "captain's table. Old as sin, with a shell like lacquer and gold."),
                         (T, "The comb carvers of Nagasaki pay a fortune for a shell like hers. Your crew knows it. "
                             "She knows it too. Look at her looking at you."),
                         (T, "So. One knife, one turtle, one decision. I do love watching a captain handle "
                             "something delicate.",
                             "So. One knife, one turtle, one decision. I do love watching a captain make up her mind."),
                     ],
                     "choices": [("free", "Cut her free", "free"),
                                 ("sell", "Sell her to the comb carvers", "sell"),
                                 ("keep", "Keep her aboard for luck", "keep")]},
                 "free": {
                     "beats": [
                         (T, "You cut the net yourself. She slid into the dark without a thank-you, which is how "
                             "you know she's a lady."),
                         (T, "Your crew sulked for a week. The sea keeps better books than they do, darling, and "
                             "she has just opened an account in your name."),
                     ],
                     "fx": [("flag", "freed")], "end": True},
                 "sell": {
                     "beats": [
                         (T, "The carvers paid in silver and didn't haggle, which should have worried you. I'd have "
                             "haggled. I'd have enjoyed it."),
                         (T, "You sailed in richer. Somewhere below, a door opened and a name was written down. "
                             "Yours has such pretty letters."),
                     ],
                     "fx": [("silver", 0.6), ("standing", "here", 1), ("flag", "sold")], "end": True},
                 "keep": {
                     "beats": [
                         (T, "You gave her a tub on deck and a name the crew won't repeat in front of the Mayor. "
                             "She eats better than your gunners."),
                         (T, "She watches the water every night, Captain, like a girl waiting at a window. "
                             "Somebody is coming for her."),
                     ],
                     "fx": [("flag", "kept")], "end": True},
             }},
            # ---- Chapter 2 ---------------------------------------------------------------------------
            {"id": "palace", "title": "The Lady on the Anchor Chain", "where": None, "scene": "deep",
             "start": [("sold", "sold"), ("kept", "kept"), (None, "freed")],
             "nodes": {
                 # She was set free: an invitation.
                 "freed": {
                     "beats": [
                         (T, "Hush. Feel that? Dead calm, the bell stopped, every hand aboard frozen with her "
                             "mouth open. Most unattractive. That's my cue, and hers."),
                         (T, "A woman came up your anchor chain, hand over hand, dry as a ledger and wearing "
                             "more pearls than modesty.",
                             "A woman came up your anchor chain, hand over hand, dry as a ledger and wearing "
                             "more pearls than a jeweller's window."),
                         (O, "Captain. You untied one of my handmaids from a net. In my father's house that is "
                             "practically a proposal.",
                             "Captain. You untied one of my handmaids from a net. In my father's house that is "
                             "a debt of honour."),
                         (O, "I am Otohime, daughter of the Dragon King. Come below for three days. I promise to "
                             "return you in the condition I found you. More or less."),
                         (T, "You went, of course. Nobody says no to pearls. Three days of feasting in halls of "
                             "coral, and she never once let your cup stand empty."),
                         (T, "On the third night she asked what you wanted. Careful, darling. Down there they "
                             "grant things."),
                     ],
                     "choices": [("stay", "Stay one more night", "stay"),
                                 ("home", "Ask to be taken home", "home"),
                                 ("trade", "Ask to open an account with the sea", "trade")]},
                 "stay": {
                     "beats": [
                         (O, "One more night? Captain, I thought you'd never ask. I was beginning to doubt my "
                             "own hospitality.",
                             "One more night? Captain, I thought you'd never ask. The cooks have been hoping."),
                         (T, "It was a long night. I shan't say more. I was only watching through the porthole.",
                             "It was a long feast. Forty courses. I counted them through the porthole."),
                         (O, "Take these pearls. A woman should pay for what she enjoys.",
                             "Take these pearls. A good guest should never leave empty-handed."),
                     ],
                     "fx": [("silver", 1.0), ("flag", "fond")], "goto": "box"},
                 "home": {
                     "beats": [
                         (O, "Home. How refreshingly dull. Most captains have to be thrown out."),
                         (O, "A guest who knows when to leave is rarer than black pearls. I shall remember you "
                             "fondly, which is more dangerous than it sounds."),
                     ],
                     "fx": [("standing", "home", 3), ("flag", "polite")], "goto": "box"},
                 "trade": {
                     "beats": [
                         (O, "An account. With the sea. You would flirt with a typhoon if it carried cargo.",
                             "An account. With the sea. You would bargain with a typhoon if it carried cargo."),
                         (O, "Very well. My father's weavers will fill your hold with sea-silk. Sell it dear. I "
                             "take my interest later, and I never forget a figure."),
                     ],
                     "fx": [("cargo", "silk", 0.9), ("flag", "debtor")], "goto": "box"},
                 # She was sold: a bill.
                 "sold": {
                     "beats": [
                         (T, "Dead calm, Captain. The bell has stopped. I'd offer you a drink, but you'll want "
                             "both hands."),
                         (T, "A woman came up your anchor chain dripping pearls and fury. Lovely shoulders. "
                             "Dreadful mood.",
                             "A woman came up your anchor chain dripping pearls and fury. Lovely manners. "
                             "Dreadful mood."),
                         (O, "You sold my handmaid to the comb carvers. She is a hair ornament now. I have seen "
                             "it. It doesn't even suit the girl wearing it."),
                         (O, "I am Otohime, daughter of the Dragon King, and you owe my house a life. I will take "
                             "silver, service or satisfaction. Choose quickly. I am not patient above water.",
                             "I am Otohime, daughter of the Dragon King, and you owe my house a life. I will take "
                             "silver, service or a quarrel. Choose quickly. I am not patient above water."),
                     ],
                     "choices": [("pay", "Pay the blood-price", "pay"),
                                 ("serve", "Offer to serve her instead", "serve"),
                                 ("refuse", "Refuse. A turtle is a turtle.", "refuse")]},
                 "pay": {
                     "beats": [
                         (T, "You paid. It hurt. I watched your face, and it was the most honest thing you've "
                             "done all year."),
                         (O, "Silver, and no argument. Perhaps there is a conscience under all that brass. Let "
                             "us test it."),
                     ],
                     "fx": [("silver", -1.0), ("flag", "paid")], "goto": "box"},
                 "serve": {
                     "beats": [
                         (O, "Service. How promising. You will carry something for me, and you will not peek, "
                             "however prettily it begs."),
                         (T, "She pressed a lacquer box into your hands and smiled like a moneylender. You've "
                             "known a few. You know that smile."),
                         (T, "Then she was gone, and the bell finished its swing. The box hums at night. I'd "
                             "sleep on deck, darling."),
                     ],
                     "fx": [("flag", "box"), ("flag", "cursed")], "end": True},
                 "refuse": {
                     "beats": [
                         (O, "A turtle is a turtle. And a ship is only timber. Let me show you how the sea feels "
                             "about timber."),
                         (T, "She went over the side without a splash, and the calm ended all at once. The sea "
                             "took its price out of your hull and your hold, and left the receipt in splinters."),
                         (T, "No box for you, Captain. Just a grudge. Those keep even better."),
                     ],
                     "fx": [("hull", 0.25), ("lose_cargo", 0.20), ("flag", "enemy")], "end": True},
                 # She was kept aboard: a reunion.
                 "kept": {
                     "beats": [
                         (T, "Dead calm. The bell has stopped. And your turtle, Captain, is standing at the rail "
                             "on her hind flippers like a wife at the dock."),
                         (T, "A woman came up the anchor chain in pearls and very little patience.",
                             "A woman came up the anchor chain in pearls and no patience at all."),
                         (O, "There you are, you wicked girl. Weeks I have searched. And living in a washtub, "
                             "with sailors."),
                         (O, "I am Otohime, daughter of the Dragon King. You have kept my handmaid fed and "
                             "unsold, Captain, which is better manners than most. What shall I do with you?"),
                     ],
                     "choices": [("give", "Hand her back with your compliments", "give"),
                                 ("ransom", "Name a price for her keep", "ransom")]},
                 "give": {
                     "beats": [
                         (O, "No bill? No bargaining? I hardly know where to look. Come below, Captain. Let me "
                             "feed you properly for once."),
                         (T, "Three days in halls of coral. She is a generous hostess. I counted the courses "
                             "through the porthole and lost my place twice."),
                         (O, "Pearls, for your trouble. Don't be shy. Take a handful."),
                     ],
                     "fx": [("silver", 0.5), ("flag", "polite")], "goto": "box"},
                 "ransom": {
                     "beats": [
                         (O, "You are charging me board for my own maid. I ought to drown you. Instead I find "
                             "I am impressed."),
                         (O, "Here. Pearls. Count them twice. I certainly shall."),
                     ],
                     "fx": [("silver", 0.9), ("flag", "greedy")], "goto": "box"},
                 # The box (every road but two leads here).
                 "box": {
                     "beats": [
                         (O, "One thing more. This box is yours. It is lacquer, it is beautiful, and you are "
                             "never to open it. I do mean never, Captain. I know how you people are with lids."),
                         (T, "And up you came. Three days below, and above, the bell finished its swing as "
                             "though you had only blinked. I keep the hours while you're away. It's my one talent."),
                         (T, "The box sits in your cabin now. It hums a little at night. I'm sure that's nothing."),
                     ],
                     "fx": [("flag", "box")], "end": True},
             }},
            # ---- Chapter 3 ---------------------------------------------------------------------------
            {"id": "box", "title": "The Box", "where": None, "scene": "port",
             "start": [("box", "box"), (None, "grudge")],
             "nodes": {
                 "box": {
                     "beats": [
                         (T, "Stop the bell, Captain. We need to talk about your box. It has been singing. The "
                             "cook has resigned twice."),
                         (T, "Word got about. A collector of curiosities in {port} has offered you a sum that "
                             "made your bookkeeper sit down. Your crew, meanwhile, has a wager on what's inside."),
                         (T, "Otohime said never. Ladies say a great many things. I only mention that I have "
                             "seen what's in there, and I'm not telling."),
                     ],
                     "choices": [("keep", "Keep it shut", "keep"),
                                 ("sell", "Sell it unopened to the collector", "sell"),
                                 ("open", "Open it", "open")]},
                 "keep": {
                     "beats": [
                         (T, "You put it back on the shelf. The crew called you dull. I'd call you the first "
                             "captain in a thousand years to do as a lady asked."),
                         (O, "You kept my lid on. Do you know how rare that is, Captain? I had a wager with my "
                             "father. He is furious."),
                         (O, "The sea pays interest on trust. Hold out your hands. Both of them. You will "
                             "need both."),
                         (T, "And the box? She took it back. It was her heart in there, or her laundry. She "
                             "wouldn't say, and she was blushing."),
                     ],
                     "fx": [("silver", 1.6), ("standing", "home", 4), ("standing", "nagasaki", 4)], "end": True},
                 "sell": {
                     "beats": [
                         (T, "You sold it. Very sensible. The collector paid in gold and carried it home like "
                             "a bride."),
                         (T, "She opened it that night. By morning she was three hundred years old and "
                             "absolutely livid. People talk, darling. They are talking in Nagasaki."),
                     ],
                     "fx": [("silver", 1.2), ("standing", "nagasaki", -8), ("standing", "here", -3),
                            ("news", "n.legend_palace_sold")], "end": True},
                 "open": {
                     "beats": [
                         (T, "You lifted the lid. Of course you did. I'd have been disappointed otherwise."),
                     ],
                     "roll": [(35, "open_bad"), (30, "open_good"), (35, "open_empty")],
                     "roll_if": {"cursed": [(60, "open_bad"), (15, "open_good"), (25, "open_empty")],
                                 "greedy": [(60, "open_bad"), (15, "open_good"), (25, "open_empty")],
                                 "polite": [(20, "open_bad"), (45, "open_good"), (35, "open_empty")],
                                 "fond": [(20, "open_bad"), (45, "open_good"), (35, "open_empty")]}},
                 "open_bad": {
                     "beats": [
                         (T, "Out it came, Captain: three days. The three days you spent below, with a few "
                             "hundred years of interest."),
                         (T, "It missed you, mercifully, and settled on your ships. Timbers greyed. Rope rotted. "
                             "Your newest hull is now your oldest."),
                         (O, "I did say never. I said it twice. I even made the face."),
                     ],
                     "fx": [("hull", 0.35)], "end": True},
                 "open_good": {
                     "beats": [
                         (T, "Inside, on a bed of sea-silk: one pearl the size of a plum, and a note in a very "
                             "elegant hand."),
                         (O, "I knew you would peek. I should be cross. Instead I find I packed for it. Don't "
                             "make that face. Take the pearl."),
                     ],
                     "fx": [("silver", 2.0)], "end": True},
                 "open_empty": {
                     "beats": [
                         (T, "Empty. Lacquer, a smell of salt, and one slip of paper."),
                         (O, "It says: made you look. I signed it with a kiss, Captain, and that is worth more "
                             "than you will admit.",
                             "It says: made you look. I signed it with a flourish, Captain, and that is worth "
                             "more than you will admit."),
                     ],
                     "fx": [("standing", "home", 1)], "end": True},
                 # No box: she is owed.
                 "grudge": {
                     "beats": [
                         (T, "The bell has stopped, Captain. This one is a bill. The sea has been keeping it "
                             "since the day you told a princess a turtle was only a turtle."),
                         (T, "Every net you pass fouls your rudder. Every pilot crosses herself. A shrine keeper "
                             "in {port} says a fat offering might settle the account. Might."),
                     ],
                     "choices": [("offer", "Make the offering", "offer"),
                                 ("sail", "Sail on. A grudge is a grudge.", "sail")]},
                 "offer": {
                     "beats": [
                         (T, "You paid the shrine and felt a fool. That night the water under your keel went "
                             "smooth as a made bed.",
                             "You paid the shrine and felt a fool. That night the water under your keel went "
                             "smooth as glass."),
                         (O, "Accepted. Late, graceless and in the wrong currency. But accepted. Do not sell any "
                             "more of my staff."),
                     ],
                     "fx": [("silver", -0.6), ("standing", "here", 2)], "end": True},
                 "sail": {
                     "beats": [
                         (T, "You sailed. Brave. Or stubborn. On you they look much the same."),
                     ],
                     "roll": [(50, "sail_bad"), (50, "sail_ok")]},
                 "sail_bad": {
                     "beats": [
                         (T, "She waited for deep water. Then the sea reached up, quite politely, and helped "
                             "itself to your hold."),
                     ],
                     "fx": [("lose_cargo", 0.30), ("hull", 0.15)], "end": True},
                 "sail_ok": {
                     "beats": [
                         (T, "Nothing happened. Nothing kept happening. That's the worst of her, darling: she "
                             "knows how to make a captain wait."),
                     ],
                     "end": True},
             }},
        ],
    },
}


def _key(tale, ch, node, i):
    return "legend.{}.{}.{}.{}".format(tale, ch, node, i)


def text_keys():
    """(EN, FAMILY, SPOKEN): every line of every Legend as wording keys, so each can be edited in
    Admin > Language & Text. SPOKEN is the set of keys a character says aloud."""
    en, fam, spoken = {}, {}, {}
    for tid, tale in TALES.items():
        en["legend.{}.title".format(tid)] = tale["title"]
        for ch in tale["chapters"]:
            en["legend.{}.{}.title".format(tid, ch["id"])] = ch["title"]
            for name, node in ch["nodes"].items():
                for i, beat in enumerate(node.get("beats") or ()):
                    k = _key(tid, ch["id"], name, i)
                    en[k] = beat[1]
                    spoken[k] = beat[0]
                    if len(beat) > 2:
                        fam[k] = beat[2]
                for ckey, label, _to in node.get("choices") or ():
                    en["legend.{}.{}.{}.c.{}".format(tid, ch["id"], name, ckey)] = label
    return en, fam, spoken


def check():
    """Every node a Legend points to exists, every chapter can end, every flag tested is one that is set.
    Returns a list of problems (empty when all is well)."""
    bad = []
    for tid, tale in TALES.items():
        flags = set()
        for ch in tale["chapters"]:
            nodes = ch["nodes"]
            for flag, start in ch["start"]:
                if start not in nodes:
                    bad.append("{}.{}: start node {} is missing".format(tid, ch["id"], start))
                if flag and flag not in flags:
                    bad.append("{}.{}: opens on flag {} that no earlier chapter sets".format(tid, ch["id"], flag))
            if ch["start"][-1][0] is not None:
                bad.append("{}.{}: the last start must be the fallback (None)".format(tid, ch["id"]))
            for name, node in nodes.items():
                ways = [k for k in ("choices", "goto", "roll", "end") if node.get(k)]
                if len(ways) != 1:
                    bad.append("{}.{}.{}: needs exactly one of choices / goto / roll / end".format(tid, ch["id"], name))
                targets = [c[2] for c in node.get("choices") or ()] + ([node["goto"]] if node.get("goto") else [])
                targets += [t for _w, t in node.get("roll") or ()]
                for opts in (node.get("roll_if") or {}).values():
                    targets += [t for _w, t in opts]
                for t in targets:
                    if t not in nodes:
                        bad.append("{}.{}.{}: points to missing node {}".format(tid, ch["id"], name, t))
                for fx in node.get("fx") or ():
                    if fx[0] == "flag":
                        flags.add(fx[1])
                for f in (node.get("roll_if") or {}):
                    if f not in flags:
                        bad.append("{}.{}.{}: rolls on flag {} that is never set".format(tid, ch["id"], name, f))
    return bad
