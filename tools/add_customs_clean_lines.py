"""Crimson Ledger: 15 new Port Authority lines for the clean-customs receipt ("Stamped and sealed... I could get used to you").

Run by Add_Customs_Clean_Lines.bat.

  trade_text.py   a new bank m.customs_clean.0-14: 10 suggestive lines (innuendo, never explicit; each has its own
                  clean family-friendly wording) and 5 clean lines (same wording on every screen). Screen lines keep
                  the receipt first ("{tax} on {declared} declared."); the voice says the line without the amounts,
                  so each line is recorded once and replayed for free.
  engine.py       the clean-customs receipt draws from that bank (a shuffled deck per house: no line comes round
                  again until all 15 have been heard). The old m.customs_clean line stays as the fallback if the
                  bank is blanked in Language & Text.
  cast.py         the new keys are read by the Port Authority officer of the port, like m.customs_clean.

Backups go to cache\\customs_clean_backup\\. Safe to run again. Stops without writing anything if a file is not as expected.

    python tools/add_customs_clean_lines.py            apply
    python tools/add_customs_clean_lines.py --check    test the fit, write nothing
"""
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKUP = os.path.join(ROOT, "cache", "customs_clean_backup")

# Placed after KEYS = list(EN) on purpose: KEYS is the comprador's list (cast.py), and these are the officer's.
BANK = '''
# Port Authority, tax paid with nothing wrong: 15 new receipts so the officer stops saying the same one
# ("too repetitive", owner, 22 Nov 2026). The first ten are suggestive (innuendo, never explicit) and each has its own
# clean wording for family-friendly screens; the last five are clean on every screen.
_CUSTOMS_CLEAN_PREFIX = "{tax} on {declared} declared. "
_CUSTOMS_CLEAN = [
    ("Paid in full and nothing hidden. I do admire someone with nothing to conceal.",
     "Paid in full and nothing hidden. A captain with nothing to conceal, how refreshing."),
    ("Not one false figure. Pity. I had my gloves on.",
     "Not one false figure. The Port Authority is pleased."),
    ("Everything in order, Captain. Such a shame. I cleared the desk and everything.",
     "Everything in order, Captain. The Port Authority has nothing more to ask."),
    ("You declared it all and paid it on time. I do like someone who finishes what they start.",
     "You declared it all and paid it on time. I do like a captain who finishes what she starts."),
    ("Clean hold, clean conscience. I only wish I'd been allowed to look a little closer.",
     "Clean hold, clean conscience. Nothing for me to find today."),
    ("Nothing to find, nothing to fine. Come back soon, Captain. I get so bored when I can't be thorough.",
     "Nothing to find, nothing to fine. Come back soon, Captain."),
    ("Settled to the last coin. You leave me nothing to chase, and I do so enjoy a chase.",
     "Settled to the last coin. You leave me nothing to chase, Captain."),
    ("A full declaration, nothing held back. You do know how to satisfy a Port Authority, Captain.",
     "A full declaration, nothing held back. The Port Authority is satisfied, Captain."),
    ("My stamp is warm and my ink is wet, and you've been very good. Off you go, before I forget my duties.",
     "My stamp is ready and my ink is fresh, and you've been very good. Off you go, Captain."),
    ("No lies, no fines, no fun. Unless you'd like to go back and lie a little, Captain. I'd search you gladly.",
     "No lies, no fines, Captain. The Port Authority thanks you for your honesty."),
    ("Paid and recorded, Captain. The Port Authority thanks you.",) * 2,
    ("Everything declared, everything paid. A tidy ledger is a pleasure to keep.",) * 2,
    ("Your papers are in order. Fair winds and good trading, Captain.",) * 2,
    ("Receipt issued, Captain. Don't spend it all in one port.",) * 2,
    ("Duty paid in full. Mind the tide on your way out, Captain.",) * 2,
]
# loop: clean customs
for _i, (_wink, _fwink) in enumerate(_CUSTOMS_CLEAN):
    _k = "m.customs_clean.{}".format(_i)
    EN[_k] = _CUSTOMS_CLEAN_PREFIX + _wink
    FAMILY[_k] = _CUSTOMS_CLEAN_PREFIX + _fwink
    SAY[_k] = _wink
    SAY_FAMILY[_k] = _fwink

'''
KEYS_OLD = "KEYS = list(EN)\n"

ENG_OLD = '        return tx("m.customs_clean", tax=money(tax_total), declared=money(total_declared))'
ENG_NEW = '        return tx(self._trade_say(p, "m.customs_clean"), tax=money(tax_total), declared=money(total_declared))'

CAST_OLD = '"e.customs_nothing_back"] + [k for k in strings.EN if k.startswith("l.customs_welcome.")]'
CAST_NEW = '"e.customs_nothing_back"] + [k for k in strings.EN if k.startswith(("l.customs_welcome.", "m.customs_clean."))]'


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
    files = {n: os.path.join(ROOT, n) for n in ("trade_text.py", "engine.py", "cast.py")}
    text, crlf = {}, {}
    for n, path in files.items():
        text[n], crlf[n] = read(path)
    done = {"trade_text.py": "_CUSTOMS_CLEAN" in text["trade_text.py"],
            "engine.py": 'self._trade_say(p, "m.customs_clean")' in text["engine.py"],
            "cast.py": "m.customs_clean.\"" in text["cast.py"]}
    if all(done.values()):
        print("Already applied. Nothing to do.")
        return
    if not done["trade_text.py"]:
        once(text["trade_text.py"], KEYS_OLD, "the KEYS line in trade_text.py")
        text["trade_text.py"] = text["trade_text.py"].replace(KEYS_OLD, KEYS_OLD + BANK)
    if not done["engine.py"]:
        once(text["engine.py"], ENG_OLD, "the clean-customs receipt in engine.py")
        text["engine.py"] = text["engine.py"].replace(ENG_OLD, ENG_NEW)
    if not done["cast.py"]:
        once(text["cast.py"], CAST_OLD, "the Port Authority key list in cast.py")
        text["cast.py"] = text["cast.py"].replace(CAST_OLD, CAST_NEW)
    todo = [n for n in files if not done[n]]
    if check:
        print("Check only: the patch fits. Would change: " + ", ".join(todo))
        return
    os.makedirs(BACKUP, exist_ok=True)
    for n in todo:
        keep = os.path.join(BACKUP, n)
        if not os.path.exists(keep):
            shutil.copy2(files[n], keep)
        write(files[n], text[n], crlf[n])
        print("Updated " + n)
    print("Done. Backups are in cache\\customs_clean_backup. Restart the server (or run Deploy_To_Pi.bat) to use the lines.")
    print("The voice records each new line the first time it is heard, then replays it from cache\\voice.")


if __name__ == "__main__":
    main()
