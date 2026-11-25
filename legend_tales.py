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
    "right":  {node: (choice key, ...)}: the RIGHT answer at each question in this chapter (see below),
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

THE RIGHT CHOICE (owner's decision, 21 Nov 2026; project doc "SeaTrader Last Two Shares"): every chapter marks
one right answer at each of its questions. A Captain who answers rules.legend.share_right chapters of one
Legend rightly (2 of 3) earns a port share, once a game (honour.py). The right answer is the generous or
honourable one, and it should cost the Captain the bigger prize. It is never shown or hinted on the screen,
so do not write a button label or a line that gives it away. EVERY NEW LEGEND NEEDS ITS "right" MAP: check()
complains about a question without one.

WRITING: every spoken line follows the house voice (house_voice.HOUSE_STYLE): the fact plain, a wink riding on
it, innuendo and never explicit. No amounts in a spoken line: figures belong on the Reckoning card. A third
item in a beat is its family-friendly wording.

LENGTH (owner's decision, 21 Nov 2026: the first telling ran about half too long). Keep a Legend quick: a
chapter's opening is 2 or 3 lines, an answer's outcome 1 or 2, so a whole chapter is 3 to 6 lines from the bell
stopping to the Reckoning card. One line carries the fact and its wink together. tests/legend_test.py holds
every road to that budget.
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
             "right": {"open": ("free",)},                     # let her go, and take nothing for it
             "nodes": {
                 "open": {
                     "beats": [
                         (T, "Hold still, Captain. The bell has stopped, so it's my turn to "
                             "talk. Your crew has netted a sea turtle the size of a captain's "
                             "table."),
                         (T, "The comb carvers pay a fortune for a shell like hers, and she "
                             "knows it. I do love watching a captain handle something "
                             "delicate.",
                             "The comb carvers pay a fortune for a shell like hers, and she "
                             "knows it. I do love watching a captain make up her mind."),
                     ],
                     "choices": [("free", "Cut her free", "free"),
                                 ("sell", "Sell her to the comb carvers", "sell"),
                                 ("keep", "Keep her aboard for luck", "keep")]},
                 "free": {
                     "beats": [
                         (T, "You cut the net yourself. She slid into the dark without a "
                             "thank-you, which is how you know she's a lady."),
                     ],
                     "fx": [("flag", "freed")], "end": True},
                 "sell": {
                     "beats": [
                         (T, "The carvers paid in silver and didn't haggle. That should have "
                             "worried you. Somewhere below, your name was written down."),
                     ],
                     "fx": [("silver", 0.6), ("standing", "here", 1), ("flag", "sold")], "end": True},
                 "keep": {
                     "beats": [
                         (T, "You gave her a tub on deck. She watches the water every night, "
                             "Captain, like a girl waiting at a window."),
                     ],
                     "fx": [("flag", "kept")], "end": True},
             }},
            # ---- Chapter 2 ---------------------------------------------------------------------------
            {"id": "palace", "title": "The Lady on the Anchor Chain", "where": None, "scene": "deep",
             "start": [("sold", "sold"), ("kept", "kept"), (None, "freed")],
             # go home when asked; pay what is owed; hand her back and name no price
             "right": {"freed": ("home",), "sold": ("pay",), "kept": ("give",)},
             "nodes": {
                 # She was set free: an invitation.
                 "freed": {
                     "beats": [
                         (T, "Dead calm, Captain, and a woman is coming up your anchor chain, "
                             "wearing more pearls than modesty.",
                             "Dead calm, Captain, and a woman is coming up your anchor chain, "
                             "wearing more pearls than a jeweller's window."),
                         (O, "I am Otohime, daughter of the Dragon King. You freed my "
                             "handmaid from a net. In my father's house that is practically a "
                             "proposal. Come below.",
                             "I am Otohime, daughter of the Dragon King. You freed my "
                             "handmaid from a net. In my father's house that is a debt of "
                             "honour. Come below."),
                         (T, "You went, of course. Nobody says no to pearls. On the third "
                             "night she asked what you wanted. Careful, darling."),
                     ],
                     "choices": [("stay", "Stay one more night", "stay"),
                                 ("home", "Ask to be taken home", "home"),
                                 ("trade", "Ask to open an account with the sea", "trade")]},
                 "stay": {
                     "beats": [
                         (O, "One more night? Captain, I thought you'd never ask. Take these "
                             "pearls. A woman should pay for what she enjoys.",
                             "One more night? The cooks have been hoping. Take these pearls. "
                             "A good guest should never leave empty-handed."),
                     ],
                     "fx": [("silver", 1.0), ("flag", "fond")], "goto": "box"},
                 "home": {
                     "beats": [
                         (O, "Home. How refreshingly dull. Most captains have to be thrown "
                             "out."),
                     ],
                     "fx": [("standing", "home", 3), ("flag", "polite")], "goto": "box"},
                 "trade": {
                     "beats": [
                         (O, "An account with the sea. You would flirt with a typhoon if it "
                             "carried cargo. Very well. A hold of sea-silk now, and my "
                             "interest later.",
                             "An account with the sea. You would bargain with a typhoon if it "
                             "carried cargo. Very well. A hold of sea-silk now, and my "
                             "interest later."),
                     ],
                     "fx": [("cargo", "silk", 0.9), ("flag", "debtor")], "goto": "box"},
                 # She was sold: a bill.
                 "sold": {
                     "beats": [
                         (T, "Dead calm, Captain, and a woman is coming up your anchor chain "
                             "dripping pearls and fury. Lovely shoulders. Dreadful mood.",
                             "Dead calm, Captain, and a woman is coming up your anchor chain "
                             "dripping pearls and fury. Lovely manners. Dreadful mood."),
                         (O, "I am Otohime, daughter of the Dragon King. You sold my "
                             "handmaid, and she is a hair ornament now. I will take silver, "
                             "service or satisfaction.",
                             "I am Otohime, daughter of the Dragon King. You sold my "
                             "handmaid, and she is a hair ornament now. I will take silver, "
                             "service or a quarrel."),
                     ],
                     "choices": [("pay", "Pay the blood-price", "pay"),
                                 ("serve", "Offer to serve her instead", "serve"),
                                 ("refuse", "Refuse. A turtle is a turtle.", "refuse")]},
                 "pay": {
                     "beats": [
                         (O, "Silver, and no argument. Perhaps there is a conscience under "
                             "all that brass."),
                     ],
                     "fx": [("silver", -1.0), ("flag", "paid")], "goto": "box"},
                 "serve": {
                     "beats": [
                         (O, "Service. How promising. Carry this box for me, and do not peek, "
                             "however prettily it begs."),
                         (T, "She smiled like a moneylender and was gone. The box hums at "
                             "night, darling. I'd sleep on deck."),
                     ],
                     "fx": [("flag", "box"), ("flag", "cursed")], "end": True},
                 "refuse": {
                     "beats": [
                         (O, "A turtle is a turtle, and a ship is only timber. Let me show "
                             "you how the sea feels about timber."),
                         (T, "The sea took its price out of your hull and your hold. No box "
                             "for you, Captain. Just a grudge."),
                     ],
                     "fx": [("hull", 0.25), ("lose_cargo", 0.20), ("flag", "enemy")], "end": True},
                 # She was kept aboard: a reunion.
                 "kept": {
                     "beats": [
                         (T, "Dead calm, and your turtle is at the rail like a wife at the "
                             "dock. A woman is coming up the anchor chain in pearls and very "
                             "little patience.",
                             "Dead calm, and your turtle is at the rail like a wife at the "
                             "dock. A woman is coming up the anchor chain in pearls and no "
                             "patience at all."),
                         (O, "There you are, you wicked girl. I am Otohime, daughter of the "
                             "Dragon King. You kept my handmaid fed and unsold, Captain. What "
                             "shall I do with you?"),
                     ],
                     "choices": [("give", "Hand her back with your compliments", "give"),
                                 ("ransom", "Name a price for her keep", "ransom")]},
                 "give": {
                     "beats": [
                         (O, "No bill? No bargaining? I hardly know where to look. Take a "
                             "handful of pearls, Captain."),
                     ],
                     "fx": [("silver", 0.5), ("flag", "polite")], "goto": "box"},
                 "ransom": {
                     "beats": [
                         (O, "You are charging me board for my own maid. I ought to drown "
                             "you. Instead I am impressed. Here. Pearls."),
                     ],
                     "fx": [("silver", 0.9), ("flag", "greedy")], "goto": "box"},
                 # The box (every road but two leads here).
                 "box": {
                     "beats": [
                         (O, "One thing more. This box is yours, and you are never to open "
                             "it. I know how you people are with lids."),
                         (T, "And up you came, and the bell finished its swing. The box hums "
                             "a little at night. I'm sure that's nothing."),
                     ],
                     "fx": [("flag", "box")], "end": True},
             }},
            # ---- Chapter 3 ---------------------------------------------------------------------------
            {"id": "box", "title": "The Box", "where": None, "scene": "port",
             "start": [("box", "box"), (None, "grudge")],
             "right": {"box": ("keep",), "grudge": ("offer",)},   # never open it; make the offering
             "nodes": {
                 "box": {
                     "beats": [
                         (T, "Stop the bell, Captain. Your box has been singing, and a "
                             "collector in {port} has offered a sum that made your bookkeeper "
                             "sit down."),
                         (T, "Otohime said never. Ladies say a great many things."),
                     ],
                     "choices": [("keep", "Keep it shut", "keep"),
                                 ("sell", "Sell it unopened to the collector", "sell"),
                                 ("open", "Open it", "open")]},
                 "keep": {
                     "beats": [
                         (O, "You kept my lid on. Do you know how rare that is, Captain? The "
                             "sea pays interest on trust. Hold out both hands."),
                         (T, "She took the box back. It was her heart in there, or her "
                             "laundry. She was blushing."),
                     ],
                     "fx": [("silver", 1.6), ("standing", "home", 4), ("standing", "nagasaki", 4)], "end": True},
                 "sell": {
                     "beats": [
                         (T, "You sold it. The collector opened it that night, and by morning "
                             "she was three hundred years old and absolutely livid."),
                     ],
                     "fx": [("silver", 1.2), ("standing", "nagasaki", -8), ("standing", "here", -3),
                            ("news", "n.legend_palace_sold")], "end": True},
                 "open": {
                     "beats": [
                         (T, "You lifted the lid. Of course you did."),
                     ],
                     "roll": [(35, "open_bad"), (30, "open_good"), (35, "open_empty")],
                     "roll_if": {"cursed": [(60, "open_bad"), (15, "open_good"), (25, "open_empty")],
                                 "greedy": [(60, "open_bad"), (15, "open_good"), (25, "open_empty")],
                                 "polite": [(20, "open_bad"), (45, "open_good"), (35, "open_empty")],
                                 "fond": [(20, "open_bad"), (45, "open_good"), (35, "open_empty")]}},
                 "open_bad": {
                     "beats": [
                         (T, "Out came your three days below, with a few hundred years of "
                             "interest. Your newest hull is now your oldest."),
                         (O, "I did say never. I even made the face."),
                     ],
                     "fx": [("hull", 0.35)], "end": True},
                 "open_good": {
                     "beats": [
                         (O, "I knew you would peek, Captain. I packed for it: one pearl, the "
                             "size of a plum. Take it."),
                     ],
                     "fx": [("silver", 2.0)], "end": True},
                 "open_empty": {
                     "beats": [
                         (O, "Empty, Captain, but for my note. It says: made you look. I "
                             "signed it with a kiss.",
                             "Empty, Captain, but for my note. It says: made you look. I "
                             "signed it with a flourish."),
                     ],
                     "fx": [("standing", "home", 1)], "end": True},
                 # No box: she is owed.
                 "grudge": {
                     "beats": [
                         (T, "The bell has stopped, Captain, and this one is a bill. The sea "
                             "holds a grudge, and a shrine keeper in {port} says a fat "
                             "offering might settle it. Might."),
                     ],
                     "choices": [("offer", "Make the offering", "offer"),
                                 ("sail", "Sail on. A grudge is a grudge.", "sail")]},
                 "offer": {
                     "beats": [
                         (O, "Accepted. Late, graceless and in the wrong currency. Do not "
                             "sell any more of my staff."),
                     ],
                     "fx": [("silver", -0.6), ("standing", "here", 2)], "end": True},
                 "sail": {
                     "beats": [
                         (T, "You sailed. Brave, or stubborn."),
                     ],
                     "roll": [(50, "sail_bad"), (50, "sail_ok")]},
                 "sail_bad": {
                     "beats": [
                         (T, "She waited for deep water. Then the sea reached up, quite "
                             "politely, and helped itself to your hold."),
                     ],
                     "fx": [("lose_cargo", 0.30), ("hull", 0.15)], "end": True},
                 "sail_ok": {
                     "beats": [
                         (T, "Nothing happened. Nothing kept happening. She does know how to "
                             "make a captain wait."),
                     ],
                     "end": True},
             }},
        ],
    },
}


# The second set (25 Nov 2026; legend_tales_more.py): five more Legends, merged in here.
import legend_tales_more as _more  # noqa: E402
TALES.update(_more.MORE)


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
            right = ch.get("right") or {}
            for name, keys in right.items():
                asked = [c[0] for c in (nodes.get(name) or {}).get("choices") or ()]
                if not keys or any(k not in asked for k in keys):
                    bad.append("{}.{}: the right answer at {} is not one of its choices".format(tid, ch["id"], name))
                if asked and len(keys) >= len(asked):
                    bad.append("{}.{}: every answer at {} is marked right".format(tid, ch["id"], name))
            for name, node in nodes.items():
                if node.get("choices") and name not in right:
                    bad.append("{}.{}.{}: a question with no right answer marked".format(tid, ch["id"], name))
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
