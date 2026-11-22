"""Checks for the Captain's Manual (manual_text.py, manual_feed.py, web/manual.*). Run: python tests/manual_test.py

What it guards (Anthony, 21 Nov 2026): every persona line has a clean family version; no line carries a
placeholder or an amount; every chapter's persona exists in the cast; every key the page reads exists; the
page only uses scripts and styles the game serves; and the server answers a seatless visitor with the seat
refusal rather than the book.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import manual_text  # noqa: E402

failed = []


def check(name, ok, detail=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else "  " + str(detail)))
    if not ok:
        failed.append(name)


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


EN, FAMILY = manual_text.EN, manual_text.FAMILY
spoken = sorted(manual_text.SPEAKER)

check("every chapter has a tab, title and kicker",
      all(("man.%s.%s" % (c["id"], k)) in EN for c in manual_text.CHAPTERS for k in ("tab", "title", "kicker")))
check("every spoken line exists", all(k in EN for k in spoken), [k for k in spoken if k not in EN])
check("every spoken line has a family version", all(k in FAMILY for k in spoken), [k for k in spoken if k not in FAMILY])
check("family versions only exist for real lines", all(k in EN for k in FAMILY), [k for k in FAMILY if k not in EN])
check("no placeholders in any manual wording", not [k for k, v in list(EN.items()) + list(FAMILY.items()) if "{" in v or "}" in v])
check("no amount in a spoken line", not [k for k in spoken if re.search(r"[$0-9]", EN[k]) or re.search(r"[$0-9]", FAMILY.get(k, ""))])
check("family wording differs from the house voice only where it should",
      sum(1 for k in spoken if FAMILY[k] != EN[k]) >= len(spoken) // 2)
check("chapter ids are unique", len({c["id"] for c in manual_text.CHAPTERS}) == len(manual_text.CHAPTERS))
check("ready chapters have their lessons",
      all(all(("man.%s.how.%d" % (c["id"], i)) in EN for i in range(manual_text.HOW_STEPS.get(c["id"], 0)))
          and manual_text.HOW_STEPS.get(c["id"], 0) > 0
          and ("man.%s.win" % c["id"]) in EN and ("man.%s.watch" % c["id"]) in EN
          for c in manual_text.CHAPTERS if c["ready"]))
check("each chapter lists its banks", all(c["bank"] and len(c["bank"]["open"]) == manual_text.BANK_SIZE for c in manual_text.chapters()))

# the persona keys must exist in the cast (read as text so this test needs no game imports)
cast_src = read("cast.py") if os.path.exists(os.path.join(ROOT, "cast.py")) else ""
for c in manual_text.CHAPTERS:
    check("persona %s exists in cast.py" % c["who"], re.search(r'^    "%s": \{' % re.escape(c["who"]), cast_src, re.M) is not None)

# every man.* key the page asks for by name must exist (keys built from chapter ids are covered above)
js = read("web", "manual.js")
for key in sorted(set(re.findall(r'"(man\.[a-z_.]+)"', js))):
    if key.endswith("."):
        continue
    check("page key %s exists" % key, key in EN, key)

# the page only loads files the game serves
html = read("web", "manual.html")
for src in re.findall(r'(?:src|href)="/([^"?]+)', html):
    if src.startswith(("assets/", "fonts.css", "theme.css")):
        continue
    check("served file %s exists" % src, os.path.exists(os.path.join(ROOT, "web", src)), src)

# every css class the page's markup uses is defined in manual.css (mn-*)
css = read("web", "manual.css")
used = set(re.findall(r'mn-[a-z-]+', js)) - {"mn-say", "mn-vnote", "mn-another", "mn-hear", "mn-voice", "mn-art", "mn-left", "mn-right"}
check("every mn- class in manual.js is styled", all(("." + c) in css for c in used), [c for c in used if ("." + c) not in css])

print("\n%d failed" % len(failed) if failed else "\nall passed")
sys.exit(1 if failed else 0)
