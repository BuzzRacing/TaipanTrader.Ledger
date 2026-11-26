"""Taipan Trader's own settings, laid over config/settings.json (Deploy_To_Pi.bat runs it on the Pi too):
its look (jade and porcelain blue instead of Crimson Ledger's oxblood and brass, Admin > Look & Style) and the
clean names for ship classes and new ships. Every other setting is left alone.
Run from the game folder: python tools/taipan_theme.py"""
import json
import sys
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "config", "settings.json")

COLORS = {
    # Celadon paper, indigo ink: a treaty-port ledger printed on sea-damp paper.
    "paper": "#ecf0e4", "card": "#f6f8f0", "ink": "#1b2a33", "muted": "#5a6b68", "rule": "#b7c8bb",
    # Bars and headers: deep porcelain indigo rather than teak.
    "teak": "#173447", "teak-2": "#245069", "on-dark": "#e8f1ea",
    # Junk-sail ochre for highlights; cinnabar seal red kept only for warnings.
    "highlight": "#d9a441", "vermilion": "#b5462a", "jade": "#2e7d6b", "gold": "#c08a2e",
    "btn": "#dce7de", "btn-border": "#98b2a5", "tabs": "#cfdfd5", "input": "#fbfcf7",
    "sea": "#b4d2d4", "land": "#e4dcc2",
    # Harbor board: the South China Sea at night.
    "board-bg": "#0e1b23", "board-panel": "#16303d", "board-ink": "#e2ede6",
    # The player's deck.
    "deck-night": "#0b161d", "deck-lacquer": "#12283a", "deck-oxblood": "#1f5f7a", "deck-brass": "#d6a84e",
    "deck-jade": "#3f9a7f", "deck-ivory": "#eef1e2", "deck-storm": "#4f7488", "deck-leather": "#6e5a3e",
}
FONTS = {
    # IM Fell English: type cut in the 1600s and still the look of colonial printing in the 1860s.
    "font_title": "\"IM Fell English SC\", \"Palatino Linotype\", Palatino, Georgia, serif",
    # Caslon: the typeface of British trade papers, shipping lists and the Hong Kong press of the period.
    "font_serif": "\"Libre Caslon Text\", \"Palatino Linotype\", Palatino, \"Book Antiqua\", Georgia, serif",
    "font_special": "\"IM Fell English SC\", \"Palatino Linotype\", Palatino, Georgia, serif",
    "web_fonts": "IM Fell English SC | Libre Caslon Text:ital,wght@0,400;0,700;1,400",
    # Taipan Trader has no NSFW, so the Captain's Options desk hides its Family Friendly switch and flip picture.
    "custom_css": "/* Taipan Trader: no NSFW switch on the Captain's Options desk. */\n.op-fam { display: none !important; }",
}
# Ship classes by their plain names (Crimson Ledger's were Velvet Cutlass, Crimson Mistress and so on).
CLASS_NAMES = {"junk": "Junk", "lorcha": "Lorcha", "barque": "Barque", "clipper": "Tea Clipper",
               "indiaman": "East Indiaman"}
# Names for new ships that read as innuendo, vice or swearing, swapped for plain ones.
NAME_SWAPS = {
    "Opium Moon": "Harvest Moon", "Red Lantern": "Paper Lantern", "Jasmine Smoke": "Jasmine Breeze",
    "The Jewelry Box": "The Lacquer Box", "Crimson Purse": "Golden Purse", "Silver Tongue": "Silver Wake",
    "Black Widow": "Black Swan",
    "Bloody Mary": "Mary Rose", "Cutthroat Kate": "Cutlass Kate", "Vixen": "Kestrel", "Hellcat": "Sea Hawk",
    "Brimstone Belle": "Thunder Belle", "Steel Siren": "Steel Heron",
    "Rich Widow": "Rich Harvest", "Deep Pockets": "Deep Hold", "Fat Purse": "Full Purse",
}

with open(PATH, encoding="utf-8") as f:
    cfg = json.load(f)
th = cfg.setdefault("theme", {})
th.setdefault("colors", {}).update(COLORS)
th.update(FONTS)
for key, name in CLASS_NAMES.items():
    if isinstance((cfg.get("ships") or {}).get(key), dict):
        cfg["ships"][key]["name"] = name
sys.path.insert(0, ROOT)
import config  # noqa: E402  (the shipped name lists, for a table the saved settings leave at its default)
for table in ("ship_names", "escort_names", "cargo_names"):
    names = cfg.get(table) if isinstance(cfg.get(table), list) else list(config.DEFAULTS.get(table) or [])
    cfg[table] = [NAME_SWAPS.get(n, n) for n in names]
for table in ("nsfw_ship_names", "nsfw_escort_names", "nsfw_cargo_names"):
    cfg[table] = []
# Cast cards saved with Crimson Ledger's wording: changed only while they still say exactly that.
CARD_FIXES = {
    ("bookkeeper", "title"): ("Bookkeeper of the House & Mistress of the Crimson Ledger",
                              "Bookkeeper of the House & Keeper of the House Ledger"),
    ("thieves", "catchphrase"): ("Mind your pockets, darling. Well, mine now.", "Mind your pockets, Captain. Well, mine now."),
}
for (cid, field), (old, new) in CARD_FIXES.items():
    card = (cfg.get("characters") or {}).get(cid)
    if isinstance(card, dict) and card.get(field) == old:
        card[field] = new
tmp = PATH + ".tmp"
with open(tmp, "w", encoding="utf-8") as f:
    json.dump(cfg, f, indent=1, ensure_ascii=False)
os.replace(tmp, PATH)
print("Taipan Trader settings applied to", PATH)
