"""Taipan Trader's own look (Admin > Look & Style): jade and porcelain blue instead of Crimson Ledger's
oxblood and brass. Lays the theme over config/settings.json and leaves every other setting alone.
Run from the game folder: python tools/taipan_theme.py"""
import json
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

with open(PATH, encoding="utf-8") as f:
    cfg = json.load(f)
th = cfg.setdefault("theme", {})
th.setdefault("colors", {}).update(COLORS)
th.update(FONTS)
tmp = PATH + ".tmp"
with open(tmp, "w", encoding="utf-8") as f:
    json.dump(cfg, f, indent=1, ensure_ascii=False)
os.replace(tmp, PATH)
print("Taipan Trader theme applied to", PATH)
