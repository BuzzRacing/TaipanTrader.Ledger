"""Crimson Ledger: adds five marijuana-only SELL lines (NSFW wording; family screens, where it is Hemp, keep one clean line).

Run by Add_Marijuana_Sell_Lines.bat, AFTER the buy lines (Add_Marijuana_Buy_Lines.bat), which put in the hook this uses.

  trade_text.py   a new bank m.sold.marijuana.0-4 (screen, spoken, family, spoken-family) and PRODUCT_SELL
                  (cargo key -> bank). Same BULK_MIN as the buy lines: a sale of that many units or more.
  engine.py       _trade_say also checks PRODUCT_SELL for a sale at a profit (or about even); _act_sell passes the
                  cargo and quantity. A sale at a loss, "Sell all" and smaller sales use the normal banks as before.

Backups go to cache\\marijuana_sell_backup\\. Safe to run again. Stops without writing anything if a file is not as expected.

    python tools/add_marijuana_sell_lines.py            apply
    python tools/add_marijuana_sell_lines.py --check    test the fit, write nothing
"""
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKUP = os.path.join(ROOT, "cache", "marijuana_sell_backup")

BANK = '''# Marijuana, sold in bulk at a profit: NSFW wording only. Family screens (where it is Hemp) get the one clean line.
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

'''
KEYS_OLD = "KEYS = list(EN)\n"

OWN_OLD = '''        own = trade_text.PRODUCT_BUY.get(good) if prefix == "m.bought" and qty >= trade_text.BULK_MIN else None
'''
OWN_NEW = '''        table = {"m.bought": trade_text.PRODUCT_BUY, "m.sold": getattr(trade_text, "PRODUCT_SELL", {})}.get(prefix)
        own = table.get(good) if table and qty >= trade_text.BULK_MIN else None
'''
SELL_OLD = '        return tx(self._trade_say(p, "m.sold_loss" if loss else "m.sold", "m.sold"), qty=q, good=GOODS[g]["name"], gain=money(gain))'
SELL_NEW = '        return tx(self._trade_say(p, "m.sold_loss" if loss else "m.sold", "m.sold", good=g, qty=q), qty=q, good=GOODS[g]["name"], gain=money(gain))'


def read(path):
    with open(path, "rb") as f:
        raw = f.read()
    return raw.decode("utf-8").replace("\r\n", "\n"), b"\r\n" in raw


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
    tt, eng = os.path.join(ROOT, "trade_text.py"), os.path.join(ROOT, "engine.py")
    t_text, t_crlf = read(tt)
    e_text, e_crlf = read(eng)
    if "BULK_MIN" not in t_text or "trade_text.PRODUCT_BUY" not in e_text:
        raise SystemExit("STOPPED: run Add_Marijuana_Buy_Lines.bat first (it puts in the hook this uses). Nothing was changed.")
    t_done, e_done = "_SOLD_MARIJUANA" in t_text, "PRODUCT_SELL" in e_text
    if t_done and e_done:
        print("Already applied. Nothing to do.")
        return
    if not t_done:
        once(t_text, KEYS_OLD, "the KEYS line in trade_text.py")
        t_text = t_text.replace(KEYS_OLD, BANK + KEYS_OLD)
    if not e_done:
        once(e_text, OWN_OLD, "the bulk check in engine.py (_trade_say)")
        once(e_text, SELL_OLD, "the sell receipt in engine.py")
        e_text = e_text.replace(OWN_OLD, OWN_NEW).replace(SELL_OLD, SELL_NEW)
    if check:
        print("Check only: the patch fits. Would change:{}{}".format("" if t_done else " trade_text.py", "" if e_done else " engine.py"))
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
    print("Done. Backups are in cache\\marijuana_sell_backup. Restart the server (or run Deploy_To_Pi.bat) to use the lines.")


if __name__ == "__main__":
    main()
