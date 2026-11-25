"""The theme check for Crimson Ledger picture prompts (24 Nov 2026).

Crimson Ledger is 1860 and at sea. Atomic Ledger (2027, heist) was forked from it and its wording, tools and
starter prompts sometimes find their way back. leaks() lists any modern, heist or aviation word in a prompt, so a
picture tool can refuse to queue it. Mirror of Atomic Ledger's tools/theme_guard.py with the word list turned round.

Words that are fine in 1860 stay allowed: ship, harbor, quay, hull, deck, captain, convoy, lamp, lantern, typhoon.
Add a word to BANNED when a picture comes back with something modern in it.
Checked by tests/theme_guard_test.py.
"""
import re

BANNED = [
    # the sibling game's identity
    "atomic", "atomic ledger", "heist", "covert", "covert freight", "off the books",
    # the modern year and style words
    "2027", "2020s", "21st century", "21st-century", "contemporary", "modern", "futuristic", "cyberpunk",
    "neon", "fluorescent", "holographic", "high-tech", "hi-tech",
    # aircraft, airports and vehicles
    "aircraft", "airplane", "aeroplane", "jet", "jets", "cargo jet", "airport", "airfield", "runway", "hangar",
    "helicopter", "drone", "drones", "turboprop", "cockpit", "tarmac", "truck", "semitruck",
    "cars", "limousine", "motorbike", "motorcycle", "forklift", "container ship", "shipping container",
    # devices and technology
    "smartphone", "phone", "iphone", "laptop", "computer", "tv", "television",
    "cctv", "security camera", "keycard", "key card", "badge reader", "barcode", "qr code", "gps", "radar",
    "satellite", "wifi", "wi-fi", "internet", "email", "digital", "electronic", "electric", "headset", "earpiece",
    "walkie-talkie", "radio", "microphone", "sunglasses", "wristwatch", "zip tie",
    # the heist and element-trading cast of things
    "assay", "isotope", "isotopes", "uranium", "helium", "cryogenic", "collider", "laboratory", "laboratories",
    "cleanroom", "cleanrooms", "vault", "sealed case", "sample case", "briefcase", "boardroom", "brokerage",
    "freight broker", "operator", "facility", "facilities", "hub", "hubs", "countermeasures", "intercept",
    "racing emerald", "three-piece suit", "cufflinks", "blazer", "hoodie",
    "jeans", "sneakers", "t-shirt", "tank top", "bikini", "lingerie",
    # modern weapons
    "handgun", "rifle", "assault rifle", "machine gun", "grenade", "taser", "bulletproof", "kevlar",
]
_RE = re.compile(r"(?<![a-z0-9])(" + "|".join(sorted((re.escape(w) for w in BANNED), key=len, reverse=True)) +
                 r")(?![a-z0-9])", re.I)


def leaks(prompt):
    """The modern words in this prompt, in the order they first appear ([] when it is clean)."""
    seen = []
    for m in _RE.finditer(str(prompt or "")):
        w = m.group(1).lower()
        if w not in seen:
            seen.append(w)
    return seen


def report(named_prompts):
    """Print every leaking prompt in [(label, prompt)]. Returns how many leak."""
    bad = 0
    for label, prompt in named_prompts:
        found = leaks(prompt)
        if found:
            bad += 1
            print("THEME CHECK: {} carries modern wording: {}".format(label, ", ".join(found)))
    return bad
