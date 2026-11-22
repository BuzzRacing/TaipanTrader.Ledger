"""Crimson Ledger: adds five opium-only and five marijuana-only buy lines (NSFW wording; family screens keep a clean line).

Run by Add_Opium_Buy_Lines.bat. Changes two files, each with a one-time backup in cache\\opium_buy_backup\\:

  trade_text.py   new banks m.bought.opium.0-4 and m.bought.marijuana.0-4 (screen, spoken, family, spoken-family,
                  like the other banks), BULK_MIN (a purchase of this many units or more uses them) and
                  PRODUCT_BUY (cargo key -> bank). Marijuana's family wording is one clean line ("Hemp").
  engine.py       _trade_say takes the cargo and quantity; _act_buy passes them. A bulk purchase of a cargo
                  that has its own bank draws from it (its own shuffled deck, so no repeat until all five
                  are heard); anything else draws from m.bought exactly as before.

Safe to run again: it says "already applied" and changes nothing. If a file has changed in a way the patch
does not recognise, it stops before writing anything.

    python tools/add_opium_buy_lines.py [opium|marijuana]     apply (both when none is named)
    python tools/add_opium_buy_lines.py --check    say what it would do, write nothing
"""
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKUP = os.path.join(ROOT, "cache", "opium_buy_backup")

# (screen wink, spoken version, family wink, family spoken). The receipt ("Bought {qty} {good} for {cost}.")
# is put in front of the screen wink by trade_text, like every other bank. Family wink = a clean line the
# comprador already uses, so clean screens hear nothing new.
BASE = '''
# A purchase of this many units or more uses the cargo's own bank (PRODUCT_BUY), if it has one.
BULK_MIN = 50
PRODUCT_BUY = {}

'''

OPIUM = '''# Opium, bought in bulk: NSFW wording only. Family screens get a clean line they already know.
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
PRODUCT_BUY["opium"] = "m.bought.opium"

'''

MARIJUANA = '''# Marijuana, bought in bulk: NSFW wording only. Family screens (where it is Hemp) all get the one clean line.
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

'''

LOOP = '''# loop: {cargo}
for _i, (_wink, _say, _fwink, _fsay) in enumerate(_BOUGHT_{up}):
    _k = "m.bought.{cargo}.{{}}".format(_i)
    EN[_k] = BUY + _wink
    FAMILY[_k] = BUY + _fwink
    SAY[_k] = _say
    SAY_FAMILY[_k] = _fsay

'''
BANKS = {"opium": OPIUM, "marijuana": MARIJUANA}
ANCHOR_OLD = "EN, FAMILY, SAY, SAY_FAMILY = {}, {}, {}, {}\n"
KEYS_OLD = "KEYS = list(EN)\n"

SAY_OLD = '''    def _trade_say(self, p, prefix, fallback=None):
        """The comprador's line for a trade (trade_text.py): the next of the bank prefix.N for this house,
        else the fallback's bank, else the plain line, so a busy trader seldom hears the same receipt."""
'''
SAY_NEW = '''    def _trade_say(self, p, prefix, fallback=None, good=None, qty=0):
        """The comprador's line for a trade (trade_text.py): the next of the bank prefix.N for this house,
        else the fallback's bank, else the plain line, so a busy trader seldom hears the same receipt.
        A bulk purchase (trade_text.BULK_MIN or more) of a cargo with its own bank (trade_text.PRODUCT_BUY)
        draws from that bank first."""
        own = trade_text.PRODUCT_BUY.get(good) if prefix == "m.bought" and qty >= trade_text.BULK_MIN else None
        if own and self._bank(own):
            return self._draw(p, own)
'''
BUY_OLD = '        return tx(self._trade_say(p, "m.bought"), qty=q, good=GOODS[g]["name"], cost=money(cost))'
BUY_NEW = '        return tx(self._trade_say(p, "m.bought", good=g, qty=q), qty=q, good=GOODS[g]["name"], cost=money(cost))'


def read(path):
    with open(path, "rb") as f:
        raw = f.read()
    crlf = b"\r\n" in raw
    return raw.decode("utf-8").replace("\r\n", "\n"), crlf


def write(path, text, crlf):
    if crlf:
        text = text.replace("\n", "\r\n")
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(text.encode("utf-8"))
    os.replace(tmp, path)


def once(text, old, label):
    n = text.count(old)
    if n != 1:
        raise SystemExit("STOPPED: expected to find {} exactly once, found {}. Nothing was changed.".format(label, n))


def main():
    check = "--check" in sys.argv[1:]
    only = [a for a in sys.argv[1:] if not a.startswith("--")]    # e.g. "marijuana"; none = both
    tt, eng = os.path.join(ROOT, "trade_text.py"), os.path.join(ROOT, "engine.py")
    for p in (tt, eng):
        if not os.path.exists(p):
            raise SystemExit("STOPPED: {} not found. Nothing was changed.".format(p))
    t_text, t_crlf = read(tt)
    e_text, e_crlf = read(eng)
    old_loop = ''',
                              ("m.bought.opium", BUY, _BOUGHT_OPIUM)):'''
    if old_loop in t_text:      # the first version of this patch: fold its opium bank into the new layout
        t_text = t_text.replace(old_loop, "):")
        t_text = t_text.replace('PRODUCT_BUY = {"opium": "m.bought.opium"}', 'PRODUCT_BUY = {}\nPRODUCT_BUY["opium"] = "m.bought.opium"')
        folded = True
    else:
        folded = False
    which = [c for c in ("opium", "marijuana") if (not only or c in only or "_BOUGHT_" + c.upper() in t_text)]
    base = "BULK_MIN" in t_text
    todo_bank = [c for c in which if "_BOUGHT_" + c.upper() not in t_text]
    todo_loop = [c for c in which if "# loop: " + c not in t_text]
    t_done = base and not todo_bank and not todo_loop
    e_done = "trade_text.PRODUCT_BUY" in e_text
    if t_done and e_done:
        print("Already applied. Nothing to do.")
        return
    if not t_done:
        once(t_text, ANCHOR_OLD, "the banks' start line in trade_text.py")
        once(t_text, KEYS_OLD, "the KEYS line in trade_text.py")
        if not base:
            t_text = t_text.replace(ANCHOR_OLD, BASE.lstrip("\n") + ANCHOR_OLD)
        for c in todo_bank:
            t_text = t_text.replace(ANCHOR_OLD, BANKS[c] + ANCHOR_OLD)
        for c in todo_loop:
            t_text = t_text.replace(KEYS_OLD, LOOP.format(cargo=c, up=c.upper()) + KEYS_OLD)
    if not e_done:
        once(e_text, SAY_OLD, "_trade_say in engine.py")
        once(e_text, BUY_OLD, "the buy receipt in engine.py")
        e_text = e_text.replace(SAY_OLD, SAY_NEW).replace(BUY_OLD, BUY_NEW)
    if check:
        print("Check only: the patch fits. Would change:{}{}".format(
            "" if t_done else " trade_text.py", "" if e_done else " engine.py"))
        return
    os.makedirs(BACKUP, exist_ok=True)
    for path, text, crlf, done in ((tt, t_text, t_crlf, t_done), (eng, e_text, e_crlf, e_done)):
        if done:
            continue
        keep = os.path.join(BACKUP, os.path.basename(path))
        if not os.path.exists(keep):
            shutil.copy2(path, keep)
        write(path, text, crlf)
        print("Updated " + os.path.basename(path))
    print("Done. Backups are in cache\\opium_buy_backup. Restart the server (or run Deploy_To_Pi.bat) to use the lines.")


if __name__ == "__main__":
    main()
