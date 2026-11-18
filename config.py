"""SeaTrader settings.

Every number, name, colour and table the game uses lives here as DEFAULTS.
The Admin page (/admin) edits a copy saved in config/settings.json; anything
missing from that file falls back to the default, so new settings added in a
later version appear on their own.

SECTIONS describes each setting (label, type, limits, help) so the Admin page
can draw itself and the server can check what it is given.
"""
import copy
import hashlib
import json
import os
import re
import secrets
import time

import cast

ROOT = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = os.path.join(ROOT, "config")
SETTINGS_FILE = os.path.join(CONFIG_DIR, "settings.json")
PRESET_DIR = os.path.join(CONFIG_DIR, "presets")
BACKUP_DIR = os.path.join(CONFIG_DIR, "backups")
LANG_DIR = os.path.join(CONFIG_DIR, "lang")
ADMIN_FILE = os.path.join(CONFIG_DIR, "admin.json")
UPLOAD_DIR = os.path.join(ROOT, "web", "uploads")
KEEP_BACKUPS = 30

# Chart window (degrees). Ports must sit inside it to appear on the map.
LON_MIN, LON_MAX, LAT_MIN, LAT_MAX = 85.0, 135.0, -10.0, 35.0

DEFAULTS = {
    "brand": {
        "title_a": "Crimson", "title_b": "Ledger",
        "tagline": "Trading the China seas, 1860",
        "currency": "$",
        "lender": "Madam Wu Lian",
        "pirate": "Admiral Li Yue",
        "bank": "Merchants' Bank of Hong Kong",
        "winner": "Taipan",
    },
    "theme": {
        "colors": {
            "paper": "#f6eedb", "card": "#fbf6e9", "ink": "#2a2118", "muted": "#75664f",
            "rule": "#d9c9a3", "teak": "#45291a", "teak-2": "#5d3a24", "on-dark": "#f6e7c4",
            "highlight": "#e8b84a", "vermilion": "#b3261e", "jade": "#2f6b5a", "gold": "#b08a2e",
            "btn": "#efe2c2", "btn-border": "#c9b383", "tabs": "#ead9b1", "input": "#fffdf6",
            "sea": "#cfdcd3", "land": "#e9dcb8",
            "board-bg": "#1f1410", "board-panel": "#2c1d15", "board-ink": "#f1e4c3",
            "deck-night": "#15100c", "deck-lacquer": "#2a1b14", "deck-oxblood": "#7b2428", "deck-brass": "#c9a34e",
            "deck-jade": "#2f6b5a", "deck-ivory": "#f1e3c5", "deck-storm": "#385467", "deck-leather": "#6b452d",
        },
        "player_colors": ["#b3261e", "#2d4a8a", "#2f7d5b", "#c58a1b",
                          "#7a3b7d", "#1f7f8c", "#7a4a22", "#4f5d6b"],
        "font_title": '"Uncial Antiqua", "Palatino Linotype", Palatino, Georgia, serif',
        "font_serif": '"MedievalSharp", "Palatino Linotype", Palatino, "Book Antiqua", Georgia, serif',
        "font_sans": '"Alegreya", "Palatino Linotype", Palatino, Georgia, serif',
        "font_special": '"Almendra SC", "Palatino Linotype", Palatino, Georgia, serif',
        "web_fonts": "Uncial Antiqua | MedievalSharp | Alegreya:ital,wght@0,400;0,700;1,400;1,700 | Almendra SC",
        "font_size": 16,
        "radius": 8,
        "ambient_seconds": 40,
        "ambient_dim": 55,
        "custom_css": "",
    },
    "graphics": {
        "logo": "/uploads/historical-logo.svg",
        "favicon": "/uploads/historical-favicon.svg",
        "masthead_bg": "/uploads/historical-masthead.webp",
        "page_bg": "/uploads/historical-page.webp",
        "board_bg": "/uploads/historical-board.webp",
        "chart_bg": "/uploads/historical-chart-v3.svg",
        "goods": {
            "opium": "/uploads/historical-cargo-opium.webp",
            "silk": "/uploads/historical-cargo-silk.webp",
            "porcelain": "/uploads/historical-cargo-porcelain.webp",
            "arms": "/uploads/historical-cargo-arms.webp",
            "spices": "/uploads/historical-cargo-spices.webp",
            "tea": "/uploads/historical-cargo-tea.webp",
            "rice": "/uploads/historical-cargo-rice.webp",
            "general": "/uploads/historical-cargo-general.webp",
        },
        "ports": {
            "hongkong": "/uploads/historical-port-hongkong.webp",
            "shanghai": "/uploads/historical-port-shanghai.webp",
            "nagasaki": "/uploads/historical-port-nagasaki.webp",
            "manila": "/uploads/historical-port-manila.webp",
            "saigon": "/uploads/historical-port-saigon.webp",
            "bangkok": "/uploads/historical-port-bangkok.webp",
            "singapore": "/uploads/historical-port-singapore.webp",
            "batavia": "/uploads/historical-port-batavia.webp",
            "calcutta": "/uploads/historical-port-calcutta.webp",
        },
        "ships": {
            "junk": "/uploads/historical-ship-junk.webp",
            "lorcha": "/uploads/historical-ship-lorcha.webp",
            "barque": "/uploads/historical-ship-barque.webp",
            "clipper": "/uploads/historical-ship-clipper.webp",
            "indiaman": "/uploads/historical-ship-indiaman.webp",
        },
    },
    "language": {"active": "en"},
    "content": {"rating": "historical"},
    "difficulty": {
        "level": "normal",
        "presets": {
            "easy":   {"name": "Calm waters", "pirates": 0.6, "storms": 0.6, "interest": 0.75,
                       "start_cash": 1.5, "seizure": 0.6, "customs_view": "exact", "battle_view": "exact"},
            "normal": {"name": "Trade winds", "pirates": 1.0, "storms": 1.0, "interest": 1.0,
                       "start_cash": 1.0, "seizure": 1.0, "customs_view": "bar", "battle_view": "bar"},
            "hard":   {"name": "Typhoon season", "pirates": 1.4, "storms": 1.3, "interest": 1.25,
                       "start_cash": 0.7, "seizure": 1.5, "customs_view": "tell", "battle_view": "tell"},
        },
    },
    "ranks": [
        {"worth": -1000000000, "title": "Debtor"},
        {"worth": 0, "title": "Clerk"},
        {"worth": 10000, "title": "Trader"},
        {"worth": 50000, "title": "Merchant"},
        {"worth": 200000, "title": "Senior Merchant"},
        {"worth": 500000, "title": "Merchant Prince"},
        {"worth": 1000000, "title": "Taipan"},
    ],
    "rules": {
        "game": {"start_year": 1860, "home": "hongkong", "max_players": 8,
                 "lengths": [1, 2, 3, 5, 10], "default_years": 5, "grace_seconds": 25},
        "start": {"cash": 3500, "debt": 5000, "ship": "junk", "guns": 2, "rep": 50, "home_rep": 60,
                  "where": "random"},
        "captains": {"typed": False},
        "market": {"spread_base": 0.04, "spread_swing": 0.03, "impact": 0.25, "floor": 0.25,
                   "ceiling": 4.5, "reversion": 0.3, "vol_mult": 1.0, "start_spread": 0.15,
                   "rep_per_value": 5000, "rep_trade_cap": 2.0, "worth_cargo": 0.9},
        "bank": {"bank_rate": 0.005, "loan_rate": 0.03, "loan_base": 5000, "loan_per_rep": 100,
                 "loan_asset_share": 0.5, "debt_warn_mult": 2.5, "debt_rep_penalty": 1,
                 "debt_grace_months": 3, "debt_call_every": 3, "wu_advice": True, "wu_easy_share": 0.25,
                 "mug_threshold": 20000, "mug_chance": 0.06, "mug_rep": 0.6,
                 "mug_min": 0.07, "mug_max": 0.15,
                 "whrob_chance": 0.02, "whrob_rep": 0.6, "whrob_min": 0.10, "whrob_max": 0.30},
        "fleet": {"max_fleet": 5, "gun_price": 600, "gun_resale": 0.333, "ship_resale": 0.5,
                  "warehouse_cap": 10000, "depot_open_cost": 10000, "depot_cap": 1000,
                  "depot_expand_cost": 100000, "depot_expand_cap": 1000, "repair_base": 6, "repair_price_div": 4000,
                  "repair_noyard": 1.3, "repair_rep_discount": 0.2, "ship_rep": 2},
        "events": {"shock_chance": 0.35, "shock_mults": [0.4, 0.5, 2.0, 2.5, 3.0],
                   "shock_min_turns": 2, "shock_max_turns": 3, "ban_chance": 0.15,
                   "ban_min_turns": 3, "ban_max_turns": 5, "ban_price_mult": 1.5,
                   "windfall_chance": 0.12, "windfall_pair_chance": 0.1,
                   "crash_min": 0.02, "crash_max": 0.12, "boom_min": 2.5, "boom_max": 10.0,
                   "windfall_min_turns": 1, "windfall_max_turns": 2},
        "contraband": {"seize_chance": 0.03, "seize_banned": 0.55, "seize_rep_relief": 0.003,
                       "fine_per_unit": 300, "rep_penalty": 15},
        "weather": {"forecast_accuracy": 0.8, "storm_chance": [0.0, 0.04, 0.20, 0.60],
                    "storm_dmg_min": 5, "storm_dmg_max": 20, "typhoon_dmg_min": 20,
                    "typhoon_dmg_max": 60, "fast_dmg_mult": 0.8, "offcourse": 0.15,
                    "risk_div": 350, "risk_min": 0.6, "risk_max": 1.8},
        "pirates": {"chance": 0.18, "fleet_min": 2, "fleet_base": 4, "fleet_per_hold": 40,
                    "fleet_max": 40, "hit": 0.30, "dmg_min": 4, "dmg_max": 14, "hp": 2,
                    "gun_hit": 0.4, "rounds": 6, "run_base": 0.35, "run_fast": 0.2,
                    "run_round": 0.05, "booty_min": 150, "booty_max": 500, "booty_growth": 24,
                    "plunder_min": 0.25, "plunder_max": 0.5},
        "liyuen": {"chance": 0.06, "fleet_base": 6, "fleet_per_hold": 25, "fleet_max": 60,
                   "hit": 0.40, "dmg_min": 8, "dmg_max": 20, "protect_months": 8,
                   "protect_save": 0.5, "cost_share": 0.02, "cost_min": 500, "renew_at": 2,
                   "tribute": True, "tribute_mult": 1.5},
        "wreck": {"cash_loss": 0.5, "debt": 1500, "ship": "junk", "hull": 100, "guns": 2},
        # The sea battle played on screen (engine.Game, "sea battles"). A captain at a screen chooses
        # each round; the month waits at sea until every fight is over.
        "battle": {"interactive": True, "parley": True, "parley_per_junk": 60, "parley_cargo": 0.05,
                   "retreat_min": 0.15, "retreat_max": 0.30, "retreat_floor": 5,
                   "round_secs": 10, "first_extra": 10, "voice_grace": 0,
                   "gun_loss": 0.25, "gun_loss_two": 0.25},
        # The mayor's harbour dues, paid on leaving port (engine.Game.dues).
        "dues": {"anchorage": 10, "tonnage": 5, "repair_share": 0.05, "yard_share": 0.03,
                 "bank_share": 0.01, "loan_share": 0.01, "warehouse": 2, "rep_discount": 0.2, "debt_relief": 0.25,
                 "slip_caught": 0.35, "slip_mult": 2.0, "slip_rep": 10},
        # The Mayor's Parlour: a purse of silver for standing in that port (engine.Game.gift_quote).
        # Standing gained = cap x (1 - e^(-gift / appetite)) x headroom, once per visit. Appetite is
        # appetite x the port's harbour dues level; headroom is 1 up to soft_from, falling to 0 at 100.
        "gift": {"enabled": True, "cap": 15, "appetite": 1500, "soft_from": 50, "min_gift": 100,
                 "max_x": 5, "step": 50, "gracious_at": 3, "warm_at": 7, "delighted_at": 11,
                 "greet_cold_below": 40, "greet_warm_from": 70},
        # The Registrar (Mrs. Evelyn Marlowe, cast key "taxlady"), found only in a captain's own home port:
        # she meets the house when it comes home and gives one fresh price from her register
        # (engine.Game.registrar_here, _registrar_tip).
        "registrar": {"enabled": True, "stale_months": 2, "held_first": True},
        # The Port Authority: each port's tax officer takes a cut of the cargo's declared value on
        # arrival, or buys it at that value, or catches the lie (engine.Game, "port authority").
        # Each port's base rate, officer and mood are in the Ports table.
        "customs": {"enabled": True, "home_free": True, "bond": True, "drift": 0.005, "range": 0.0125, "min_rate": 0.0, "max_rate": 0.5,
                    "buy_base": 0.003, "buy_k": 0.3, "buy_exp": 1.8, "buy_cap": 0.9,
                    "audit_base": 0.006, "audit_k": 0.12, "audit_cap": 0.9,
                    "appetite_power": 1.0, "greed_weight": 0.08, "cunning_weight": 0.08, "rep_audit": 0.8, "rep_buy": 0.6,
                    "mood_swing": 0.15, "fine_mult": 2.0, "caught_rep": 6,
                    "strongbox": 9000, "strongbox_swing": 0.4, "buyback_premium": 0.25,
                    "bribe_share": 0.3, "bribe_min": 50, "bribe_cut": 0.5, "bribe_honest": 0.25,
                    "bribe_refused_mult": 1.5, "bribe_rep": 8, "over_rep": 5, "max_declare": 1.5,
                    "tell_curious": 0.08, "tell_hungry": 0.25, "seeded": []},
    },
    # base = typical price; vol = monthly volatility; depth = units that move the price ~25%.
    "goods": {
        "opium":     {"name": "Opium", "family_name": "Fireworks", "base": 4200, "vol": 0.16, "depth": 60, "contraband": True, "ban_odds": 0.0},
        # Gold is legal, but a port's ban sometimes covers bullion too (ban_odds).
        "gold":      {"name": "Gold", "family_name": "", "base": 2400, "vol": 0.05, "depth": 90, "contraband": False, "ban_odds": 0.5},
        "silk":      {"name": "Silk", "family_name": "", "base": 520, "vol": 0.10, "depth": 160, "contraband": False, "ban_odds": 0.0},
        "porcelain": {"name": "Porcelain", "family_name": "", "base": 230, "vol": 0.08, "depth": 250, "contraband": False, "ban_odds": 0.0},
        "arms":      {"name": "Arms", "family_name": "Ironware", "base": 160, "vol": 0.10, "depth": 250, "contraband": False, "ban_odds": 0.0},
        "spices":    {"name": "Spices", "family_name": "", "base": 95, "vol": 0.09, "depth": 450, "contraband": False, "ban_odds": 0.0},
        "tea":       {"name": "Tea", "family_name": "", "base": 70, "vol": 0.08, "depth": 500, "contraband": False, "ban_odds": 0.0},
        "rice":      {"name": "Rice", "family_name": "", "base": 14, "vol": 0.07, "depth": 1200, "contraband": False, "ban_odds": 0.0},
        "general":   {"name": "General Cargo", "family_name": "", "base": 9, "vol": 0.07, "depth": 1200, "contraband": False, "ban_odds": 0.0},
    },
    "regions": {
        "north":  {"name": "Yellow Sea & Japan", "typhoon": 0.02, "squalls": 0.20, "label_lon": 126, "label_lat": 29,
                   "seasons": [{"months": [6, 7, 8, 9, 10], "typhoon": 0.18, "squalls": 0.30}]},
        "china":  {"name": "South China Sea", "typhoon": 0.02, "squalls": 0.20, "label_lon": 115.5, "label_lat": 17,
                   "seasons": [{"months": [6, 7, 8, 9, 10], "typhoon": 0.18, "squalls": 0.30}]},
        "south":  {"name": "Straits & Java Sea", "typhoon": 0.01, "squalls": 0.25, "label_lon": 108.2, "label_lat": 3.6,
                   "seasons": [{"months": [11, 12, 1, 2, 3], "typhoon": 0.01, "squalls": 0.40}]},
        "bengal": {"name": "Bay of Bengal", "typhoon": 0.02, "squalls": 0.20, "label_lon": 91, "label_lat": 14.5,
                   "seasons": [{"months": [4, 5, 10, 11], "typhoon": 0.15, "squalls": 0.30}]},
    },
    # mods = local price multipliers (below 1 = made here, above 1 = in demand).
    "ports": {
        "hongkong":  {"name": "Hong Kong", "lon": 114.2, "lat": 22.3, "region": "china", "bank": True, "warehouse": True, "shipyard": True, "no_ban": False, "label_left": True, "dues": 1.0, "tax_rate": 0.02, "officer": "officer_hongkong", "mood": 0.15,
                      "mods": {"arms": 0.8, "tea": 0.9, "general": 0.85, "gold": 1.05}},
        "shanghai":  {"name": "Shanghai", "lon": 121.5, "lat": 31.2, "region": "north", "bank": True, "warehouse": True, "shipyard": True, "no_ban": False, "label_left": True, "dues": 1.2, "tax_rate": 0.03, "officer": "officer_shanghai", "mood": 0.15,
                      "mods": {"silk": 0.6, "tea": 0.6, "opium": 1.35, "arms": 1.3, "spices": 1.3, "gold": 1.15}},
        "nagasaki":  {"name": "Nagasaki", "lon": 129.9, "lat": 32.75, "region": "north", "bank": False, "warehouse": False, "shipyard": False, "no_ban": False, "label_left": True, "dues": 1.4, "tax_rate": 0.025, "officer": "officer_nagasaki", "mood": 0.1,
                      "mods": {"porcelain": 0.6, "silk": 0.85, "arms": 1.5, "spices": 1.4, "rice": 1.3, "opium": 1.2, "gold": 0.55}},
        "manila":    {"name": "Manila", "lon": 121.0, "lat": 14.6, "region": "china", "bank": False, "warehouse": False, "shipyard": False, "no_ban": False, "label_left": False, "dues": 0.8, "tax_rate": 0.015, "officer": "officer_manila", "mood": 0.15,
                      "mods": {"general": 0.75, "rice": 0.9, "spices": 0.9, "silk": 1.3, "porcelain": 1.3, "tea": 1.2, "gold": 0.85}},
        "foochow":   {"name": "Foochow", "lon": 119.3, "lat": 26.1, "region": "china", "bank": False, "warehouse": False, "shipyard": False, "no_ban": False, "label_left": True, "dues": 1.0, "tax_rate": 0.025, "officer": "officer_foochow", "mood": 0.15,
                      "mods": {"tea": 0.5, "porcelain": 0.85, "opium": 1.3, "arms": 1.25, "spices": 1.2, "rice": 1.15, "general": 1.1}},
        "saigon":    {"name": "Saigon", "lon": 106.7, "lat": 10.8, "region": "china", "bank": False, "warehouse": False, "shipyard": False, "no_ban": False, "label_left": False, "dues": 0.9, "tax_rate": 0.02, "officer": "officer_saigon", "mood": 0.5,
                      "mods": {"rice": 0.55, "spices": 0.85, "arms": 1.3, "porcelain": 1.25, "general": 1.2}},
        "bangkok":   {"name": "Bangkok", "lon": 100.5, "lat": 13.75, "region": "south", "bank": False, "warehouse": False, "shipyard": False, "no_ban": False, "label_left": True, "dues": 0.7, "tax_rate": 0.03, "officer": "officer_bangkok", "mood": 0.12,
                      "mods": {"rice": 0.6, "spices": 0.8, "silk": 1.25, "arms": 1.2, "tea": 1.2, "gold": 1.2}},
        "singapore": {"name": "Singapore", "lon": 103.8, "lat": 1.35, "region": "south", "bank": True, "warehouse": True, "shipyard": True, "no_ban": False, "label_left": True, "dues": 0.6, "tax_rate": 0.01, "officer": "officer_singapore", "mood": 0.1,
                      "mods": {"arms": 0.85, "general": 0.8, "opium": 0.85, "tea": 1.4, "silk": 1.35, "porcelain": 1.3}},
        "batavia":   {"name": "Batavia", "lon": 106.8, "lat": -6.2, "region": "south", "bank": False, "warehouse": False, "shipyard": False, "no_ban": False, "label_left": False, "dues": 1.1, "tax_rate": 0.035, "officer": "officer_batavia", "mood": 0.1,
                      "mods": {"spices": 0.5, "rice": 1.2, "tea": 1.3, "silk": 1.4, "arms": 1.25, "porcelain": 1.35, "general": 1.3}},
        "calcutta":  {"name": "Calcutta", "lon": 88.4, "lat": 22.6, "region": "bengal", "bank": True, "warehouse": True, "shipyard": True, "no_ban": True, "label_left": False, "dues": 1.3, "tax_rate": 0.045, "officer": "officer_calcutta", "mood": 0.2,
                      "mods": {"opium": 0.55, "tea": 0.8, "general": 0.9, "rice": 0.9, "silk": 1.3, "spices": 1.3, "porcelain": 1.5, "gold": 1.35}},
    },
    # hold = cargo units; hull = damage it can take; slots = guns it can mount.
    "ships": {
        "junk":     {"name": "Junk", "hold": 60, "hull": 100, "slots": 4, "price": 3000, "fast": False},
        "lorcha":   {"name": "Lorcha", "hold": 120, "hull": 140, "slots": 8, "price": 9000, "fast": False},
        "barque":   {"name": "Barque", "hold": 250, "hull": 200, "slots": 12, "price": 22000, "fast": False},
        "clipper":  {"name": "Clipper", "hold": 180, "hull": 160, "slots": 10, "price": 35000, "fast": True},
        "indiaman": {"name": "East Indiaman", "hold": 500, "hull": 320, "slots": 24, "price": 80000, "fast": False},
    },
    "ship_names": ["Morning Cloud", "Jade Heron", "Lucky Star", "Sea Witch", "Golden Carp", "Lady Hughes",
                   "Red Rover", "Water Dragon", "Flying Cloud", "Pearl of Canton", "Falcon", "Nemesis",
                   "Lotus Wind", "Black Joke", "Sylph", "Cowasjee", "Ariel", "Taeping", "Fiery Cross",
                   "Mandarin", "Eastern Queen", "Kestrel", "Tiger Tail", "Silver Moon", "Antelope"],
    # How much history to keep (Admin > Captain's Report). See journal.py.
    "journal": {"keep_games": 50, "server_days": 30},
    # Who reads the game aloud, and how (Admin > Cast & Voices). See cast.py.
    "characters": copy.deepcopy(cast.CHARACTERS),
    "voice": copy.deepcopy(cast.VOICE_DEFAULTS),
}

# Paths whose whole value is replaced on save (rows can be deleted), not merged.
WHOLE = ("goods", "ports", "ships", "regions", "ranks", "ship_names", "difficulty.presets",
         "theme.player_colors", "rules.game.lengths", "rules.events.shock_mults",
         "rules.weather.storm_chance", "graphics.goods", "graphics.ports", "graphics.ships",
         "characters", "voice.lines", "voice.say")


def F(path, label, kind, help="", **kw):
    d = {"path": path, "label": label, "type": kind, "help": help}
    d.update(kw)
    return d


def C(key, label, kind, help="", **kw):
    d = {"key": key, "label": label, "type": kind, "help": help}
    d.update(kw)
    return d


def _pct(path, label, help="", lo=0.0, hi=1.0):
    return F(path, label, "pct", help, min=lo, max=hi)


_COLOR_LABELS = [
    ("paper", "Page background"), ("card", "Cards and panels"), ("ink", "Text"), ("muted", "Secondary text"),
    ("rule", "Lines and borders"), ("teak", "Header (dark wood)"), ("teak-2", "Header tiles"),
    ("on-dark", "Text on the header"), ("highlight", "Title highlight"), ("vermilion", "Main buttons and warnings"),
    ("jade", "Good news and links"), ("gold", "Trim and tags"), ("btn", "Ordinary buttons"),
    ("btn-border", "Button and input borders"), ("tabs", "Tab bar"), ("input", "Input fields"),
    ("sea", "Chart: sea"), ("land", "Chart: land"), ("board-bg", "Harbor board: background"),
    ("board-panel", "Harbor board: panels"), ("board-ink", "Harbor board: text"),
]
# The player screen ("the deck") uses the Art Bible palette rather than the parchment colours above.
_DECK_LABELS = [
    ("deck-night", "Night ink: deepest background"), ("deck-lacquer", "Lacquer brown: buttons and tiles"),
    ("deck-oxblood", "Oxblood silk: main buttons and warnings"), ("deck-brass", "Antique brass: trim, headings, active tab"),
    ("deck-jade", "Imperial jade: good news and gains"), ("deck-ivory", "Ivory linen: text"),
    ("deck-storm", "Storm blue: sea and weather"), ("deck-leather", "Tobacco leather: warm accents"),
]

SECTIONS = [
    {"id": "brand", "title": "Brand", "intro": "The game's name and the names of its characters. "
     "These names are also dropped into the game's wording wherever {lender}, {pirate}, {bank} and {winner} appear.",
     "groups": [
         {"title": "Name", "fields": [
             F("brand.title_a", "Title, first part", "text", "Shown in plain lettering.", max=24),
             F("brand.title_b", "Title, second part", "text", "Shown in the highlight colour, in italics.", max=24),
             F("brand.tagline", "Tagline", "text", "Under the title on the join and lobby screens.", max=80),
             F("brand.currency", "Currency symbol", "text", "Put before every amount of money.", max=4)]},
         {"title": "Characters and places", "fields": [
             F("brand.lender", "Moneylender", "text", max=40),
             F("brand.pirate", "Pirate queen", "text", "Sells protection and hunts those who do not pay.", max=40),
             F("brand.bank", "Bank", "text", max=60),
             F("brand.winner", "Winner's title", "text", "What the richest house is called at the end.", max=30)]},
     ]},
    {"id": "theme", "title": "Look & Style", "intro": "Colours, lettering and shape for the player screens and the harbor board. "
     "Saved changes reach every open screen at once.",
     "groups": [
         {"title": "Colours", "cols": 3, "fields": [F("theme.colors." + k, label, "color") for k, label in _COLOR_LABELS]},
         {"title": "Player screen (the deck)", "cols": 3, "fields":
             [F("theme.colors." + k, label, "color") for k, label in _DECK_LABELS] + [
             F("theme.ambient_seconds", "Background change (seconds)", "int", "How long each background picture "
               "stays before it slowly fades to the next. Pictures come from the Media Library: scenes in the "
               "background role, then the port's night pictures.", min=10, max=600),
             F("theme.ambient_dim", "Background darkness (%)", "int", "How much the background is darkened "
               "behind the panels. Higher is easier to read.", min=0, max=90)]},
         {"title": "Player flag colours", "fields": [
             F("theme.player_colors", "Eight house colours", "colorlist", "Given to players in the order they join.", count=8)]},
         {"title": "Lettering and shape", "fields": [
             F("theme.font_title", "Game title font", "text", "The game's name on the title screens, harbor board "
               "and admin bar. A CSS font list: the first font that is available is used.", max=200),
             F("theme.font_serif", "Name header font", "text", "Section headings, port, ship and house names.", max=200),
             F("theme.font_sans", "General text font", "text", "Body text, tables, buttons and forms.", max=200),
             F("theme.font_special", "Special text font", "text", "Taglines, ranks, the captain's log heading "
               "and the harbor board headline.", max=200),
             F("theme.web_fonts", "Web fonts to download", "text", "Google Fonts families, separated by |. The game "
               "downloads them once into web/fonts and serves them to every screen, so devices need no internet "
               "or installed fonts. Leave empty to use only installed fonts.", max=400),
             F("theme.font_size", "Base text size (px)", "int", min=12, max=24),
             F("theme.radius", "Corner roundness (px)", "int", min=0, max=24)]},
         {"title": "Custom CSS", "fields": [
             F("theme.custom_css", "Extra style rules", "code", "Added after everything else, so it wins. "
               "For changes the settings above do not cover.", max=20000)]},
     ]},
    {"id": "ratings", "title": "Ratings & Difficulty", "intro": "Three kinds of rating: who the game is suitable for, "
     "how hard it is, and the titles players earn.",
     "groups": [
         {"title": "Content rating", "fields": [
             F("content.rating", "Rating", "select", "Historical is the private adult release and permits nudity, "
               "exposed parts, erotic posing and consensual kink direction in the Art Bible. Family-friendly swaps "
               "cargo names, uses softer wording and locks the Art Bible prompt studio to fully dressed, non-erotic art. "
               "It does not replace artwork already uploaded under Graphics.",
               options=[["historical", "Historical (private adult)"], ["family", "Family-friendly (sharing)"]])]},
         {"title": "Difficulty", "fields": [
             F("difficulty.level", "Current level", "select", "Applies to the game in progress as well as new ones.",
               options_from="difficulty.presets")]},
     ],
     "tables": [
         {"path": "difficulty.presets", "title": "Difficulty levels", "kind": "dict", "id_label": "Key",
          "help": "Each number multiplies the normal value: 1 leaves it alone, 0.5 halves it, 2 doubles it.",
          "columns": [C("name", "Name", "text", max=30),
                      C("pirates", "Pirate attacks", "num", min=0, max=5, step=0.05),
                      C("storms", "Storms", "num", min=0, max=5, step=0.05),
                      C("interest", "Loan interest", "num", min=0, max=5, step=0.05),
                      C("start_cash", "Starting silver", "num", min=0, max=20, step=0.05),
                      C("seizure", "Customs seizures", "num", "Also multiplies the Port Authority's chance of catching a lie.",
                        min=0, max=5, step=0.05),
                      C("customs_view", "Port Authority odds shown", "select",
                        "What a captain sees while declaring cargo: the exact chances, a coloured bar without numbers, "
                        "or only the officer's face and manner.", default="bar",
                        options=[["exact", "Exact percentages"], ["bar", "Bar and her tell"], ["tell", "Her tell only"]]),
                      C("battle_view", "Sea battle odds shown", "select",
                        "What a captain sees on the battle buttons: the exact chances, a coloured bar without numbers, "
                        "or only the bosun's manner.", default="bar",
                        options=[["exact", "Exact chances"], ["bar", "Bar and her manner"], ["tell", "Her manner only"]])]},
         {"path": "ranks", "title": "Player ranks", "kind": "list",
          "help": "A player holds the highest rank whose net worth they have reached.",
          "columns": [C("worth", "Net worth from", "int", min=-10**12, max=10**12),
                      C("title", "Title", "text", max=30)]},
     ]},
    {"id": "game", "title": "Game Setup", "intro": "How a game starts and how long it runs.",
     "groups": [
         {"title": "Game", "fields": [
             F("rules.game.start_year", "Starting year", "int", min=1, max=3000),
             F("rules.game.home", "Home port", "select", "Everyone's home port when starts are not random, and the "
               "port whose prices value cargo for net worth. With random starts each player's home port is the "
               "port they start in.", options_from="ports"),
             F("rules.start.where", "Where players start", "select", "Random gives each player a different port, "
               "drawn afresh every game (ports are shared only when there are more players than ports). The port "
               "a player starts in is their home port: their bank, lender, warehouse and protection are there.",
               options=[["random", "A random port each, different every game"], ["home", "Everyone in the home port"]]),
             F("rules.captains.typed", "Players may join without a saved Captain", "bool", "Off: everyone picks a "
               "Captain from Admin > Captains (and types the PIN), or one of the two guest Captains. On: the join "
               "screen also offers the old typed name and firm, with no career kept."),
             F("rules.game.max_players", "Most players", "int", min=1, max=8),
             F("rules.game.lengths", "Game lengths offered (years)", "numlist", "The host picks one in the lobby.", min=1, max=50, integer=True),
             F("rules.game.default_years", "Length chosen by default", "int", min=1, max=50),
             F("rules.game.grace_seconds", "Seconds a dropped device still counts as present", "int", min=5, max=600)]},
         {"title": "Each player starts with", "fields": [
             F("rules.start.cash", "Silver", "int", min=0, max=10**9),
             F("rules.start.debt", "Debt", "int", min=0, max=10**9),
             F("rules.start.ship", "Ship", "select", options_from="ships"),
             F("rules.start.guns", "Guns", "int", min=0, max=99),
             F("rules.start.rep", "Standing in each port (0-100)", "int", min=0, max=100),
             F("rules.start.home_rep", "Standing in the home port", "int", min=0, max=100)]},
         {"title": "Shipwreck (losing the whole fleet)", "fields": [
             _pct("rules.wreck.cash_loss", "Share of silver lost"),
             F("rules.wreck.debt", "Debt added for the replacement ship", "int", min=0, max=10**9),
             F("rules.wreck.ship", "Replacement ship", "select", options_from="ships"),
             F("rules.wreck.hull", "Its hull points", "int", "Never more than a sound ship of that kind.", min=1, max=10000),
             F("rules.wreck.guns", "Its guns", "int", "Never more than that ship has room for.", min=0, max=1000)]},
         {"title": "Records (see Captain's Report)", "fields": [
             F("journal.keep_games", "Game journals to keep", "int", "Every game has a journal of everything that "
               "happened in it. When there are more than this many, the oldest are deleted, except the game in "
               "progress and any marked Keep. 0 keeps them all.", min=0, max=10000),
             F("journal.server_days", "Days of server log to keep", "int", "The technical log (start-ups, errors, "
               "voice requests) is one file per day. 0 keeps them all.", min=0, max=3650)]},
     ]},
    {"id": "economy", "title": "Economy", "intro": "Markets, money and the price of running a fleet.",
     "groups": [
         {"title": "Markets", "fields": [
             _pct("rules.market.spread_base", "Dealer's margin at standing 50", "", 0, 0.5),
             _pct("rules.market.spread_swing", "Margin gained or lost by standing 100 or 0", "", 0, 0.5),
             _pct("rules.market.impact", "Price move from trading one 'depth' of a cargo", "Depth is set per cargo.", 0, 2),
             F("rules.market.vol_mult", "Price swing multiplier", "num", "Scales every cargo's monthly volatility.", min=0, max=5, step=0.05),
             _pct("rules.market.reversion", "Monthly pull back to the usual price"),
             F("rules.market.floor", "Lowest price (x usual)", "num", min=0.01, max=1, step=0.01),
             F("rules.market.ceiling", "Highest price (x usual)", "num", min=1, max=50, step=0.1),
             _pct("rules.market.start_spread", "Random spread of opening prices", "", 0, 0.9),
             F("rules.market.rep_per_value", "Trade value that earns 1 standing", "int", min=1, max=10**9),
             F("rules.market.rep_trade_cap", "Most standing from one trade", "num", min=0, max=100, step=0.5),
             _pct("rules.market.worth_cargo", "Cargo's share counted in net worth", "", 0, 2)]},
         {"title": "Bank and moneylender", "fields": [
             _pct("rules.bank.bank_rate", "Bank interest per month", "", 0, 1),
             _pct("rules.bank.loan_rate", "Loan interest per month", "Compounding. Multiplied by the difficulty level.", 0, 1),
             F("rules.bank.loan_base", "Loan limit: base", "int", min=0, max=10**9),
             F("rules.bank.loan_per_rep", "Loan limit: per point of home standing", "int", min=0, max=10**7),
             _pct("rules.bank.loan_asset_share", "Loan limit: share of silver, bank and ships", "", 0, 5),
             F("rules.bank.debt_warn_mult", "Collectors call when debt passes (x limit)", "num",
               "The limit here is the loan limit without silver or bank: base, home standing and the share of "
               "ship value. Repaying always brings the debt closer to this line.", min=1, max=100, step=0.1),
             F("rules.bank.debt_grace_months", "Grace period before the first call (months)", "int",
               "Months in a row over the line before the collectors first call.", min=0, max=120),
             F("rules.bank.debt_call_every", "Then they call every (months)", "int", min=1, max=120),
             F("rules.bank.debt_rep_penalty", "Standing lost each time they call", "num", min=0, max=100, step=0.5),
             F("rules.bank.wu_advice", "The moneylender gives advice when you borrow or repay", "bool",
               "On: after the receipt she adds a word that follows how close the debt is to the collectors' line. "
               "Off: the receipt only. Her lines are in Language & Text (Confirmations, m.borrowed.* and m.repaid.*)."),
             _pct("rules.bank.wu_easy_share", "She starts to caution you at (share of the collectors' line)",
                  "Below this the moneylender just encourages you; from here to the line she cautions; over it she warns.",
                  0, 1)]},
         {"title": "Street robbery", "fields": [
             F("rules.bank.mug_threshold", "Silver on hand that tempts thieves", "int", min=0, max=10**9),
             _pct("rules.bank.mug_chance", "Chance per month"),
             _pct("rules.bank.mug_rep", "Standing 100 cuts the chance by (standing 0 adds the same)",
                  "Standing in the port where the house is ashore at month end. At standing 50 the chance is as set above.", 0, 1),
             _pct("rules.bank.mug_min", "Least taken"),
             _pct("rules.bank.mug_max", "Most taken")]},
         {"title": "Warehouse robbery", "fields": [
             _pct("rules.bank.whrob_chance", "Chance per warehouse per month",
                  "Rolled for every warehouse with cargo in it (home and rented), wherever the house is. 0 turns it off."),
             _pct("rules.bank.whrob_rep", "Standing 100 cuts the chance by (standing 0 adds the same)",
                  "Standing in the warehouse's own port. At standing 50 the chance is as set above.", 0, 1),
             _pct("rules.bank.whrob_min", "Least share of the stock taken"),
             _pct("rules.bank.whrob_max", "Most share of the stock taken")]},
         {"title": "Fleet and warehouse", "fields": [
             F("rules.fleet.max_fleet", "Most ships in a fleet", "int", min=1, max=20),
             F("rules.fleet.gun_price", "Price of a gun", "int", min=0, max=10**7),
             _pct("rules.fleet.gun_resale", "Gun's share of value when a ship is sold"),
             _pct("rules.fleet.ship_resale", "Ship resale value (sound hull)"),
             F("rules.fleet.warehouse_cap", "Warehouse space (units)", "int", min=0, max=10**8),
             F("rules.fleet.depot_open_cost", "Away warehouse: price to open", "int", min=0, max=10**9),
             F("rules.fleet.depot_cap", "Away warehouse: space when opened (units)", "int", min=0, max=10**8),
             F("rules.fleet.depot_expand_cost", "Away warehouse: price to enlarge", "int", min=0, max=10**9),
             F("rules.fleet.depot_expand_cap", "Away warehouse: space added each time (units)", "int", min=1, max=10**8),
             F("rules.fleet.ship_rep", "Standing gained by buying a ship", "num", min=0, max=100, step=0.5)]},
         {"title": "Repairs", "fields": [
             F("rules.fleet.repair_base", "Cost per hull point: base", "num", min=0, max=10000, step=0.5),
             F("rules.fleet.repair_price_div", "Plus ship price divided by", "int", min=1, max=10**7),
             F("rules.fleet.repair_noyard", "Multiplier in ports without a shipyard", "num", min=0.1, max=10, step=0.05),
             _pct("rules.fleet.repair_rep_discount", "Discount at standing 100")]},
         {"title": "Harbour dues (the mayor's bill on leaving port)", "fields": [
             F("rules.dues.anchorage", "Anchorage per ship", "num", min=0, max=10**6, step=1),
             F("rules.dues.tonnage", "Tonnage dues per 100 units of hold", "num", min=0, max=10**6, step=0.5),
             _pct("rules.dues.repair_share", "Shipyard levy: share of repairs paid this visit"),
             _pct("rules.dues.yard_share", "Shipwright and chandler: share of ships and guns bought this visit"),
             _pct("rules.dues.bank_share", "Counting-house fee: share of money deposited or withdrawn this visit"),
             _pct("rules.dues.loan_share", "Moneylender's stamp: share of money borrowed or repaid this visit"),
             F("rules.dues.warehouse", "Wharfage per 100 units stored or loaded this visit", "num", min=0, max=10**6, step=0.5),
             _pct("rules.dues.rep_discount", "Discount at standing 100 (the same surcharge at standing 0)",
                  "Standing 50 pays the full bill; the change is in proportion either side of it."),
             _pct("rules.dues.debt_relief", "Debtor's relief: most taken off for a house in debt",
                  "In proportion to the debt against the collectors' line: half way to the line gets half of this, at or past the line gets all of it. 0 turns it off."),
             _pct("rules.dues.slip_caught", "Slipping out at night: chance the harbour watch catches you"),
             F("rules.dues.slip_mult", "Caught slipping out: pay the bill this many times", "num", min=1, max=20, step=0.5),
             F("rules.dues.slip_rep", "Caught slipping out: standing lost in that port", "num", min=0, max=100, step=1)]},
         {"title": "The Mayor's Parlour (a gift for standing)", "fields": [
             F("rules.gift.enabled", "Players can call on the Mayor with a gift", "bool",
               "Off: the Call on the Mayor row is hidden on the Port tab."),
             F("rules.gift.cap", "Most standing one gift can buy", "num",
               "A gift of any size never earns more than this. Standing gained = this x (1 - e^(-gift / appetite)) x headroom.",
               min=0, max=100, step=0.5),
             F("rules.gift.appetite", "The Mayor's appetite (x the port's harbour dues level)", "int",
               "A gift of one appetite earns about 63% of the most; two, about 86%; five, about 99%. "
               "Shanghai's harbour dues level 1.2 makes 1,500 into 1,800.", min=1, max=10**8),
             F("rules.gift.soft_from", "She gets harder to impress above standing", "num",
               "Up to this standing a gift earns in full; above it, less and less, down to nothing at 100.",
               min=0, max=99, step=1),
             F("rules.gift.min_gift", "Smallest gift", "int", min=1, max=10**8),
             F("rules.gift.max_x", "Largest gift (x her appetite, never more than the silver on hand)", "num", min=1, max=100, step=0.5),
             F("rules.gift.step", "Slider step", "int", min=1, max=10**6),
             F("rules.gift.gracious_at", "Gracious thanks from (standing gained)", "num",
               "Below this she is Cool. Cool and Gracious thanks are text only.", min=0, max=100, step=0.5),
             F("rules.gift.warm_at", "Warm thanks from (standing gained)", "num",
               "Warm and Delighted thanks are read aloud by the Mayor.", min=0, max=100, step=0.5),
             F("rules.gift.delighted_at", "Delighted thanks from (standing gained)", "num", min=0, max=100, step=0.5),
             F("rules.gift.greet_cold_below", "She greets you coldly below standing", "num",
               "Her greeting in the Parlour has three moods, ten lines each: cold, neutral and warm.",
               min=0, max=100, step=1),
             F("rules.gift.greet_warm_from", "She greets you warmly from standing", "num", min=0, max=100, step=1)]},
         {"title": "Port Authority: the rate (each port's base rate and officer are in Ports)", "fields": [
             F("rules.customs.enabled", "Declare cargo on arrival", "bool",
               "Off: ships come and go without seeing the Port Authority."),
             F("rules.customs.home_free", "A house pays no cargo tax in its own home port", "bool",
               "Each player's home port (where they started) waves them in free, whatever its rate for others."),
             F("rules.customs.bond", "Cargo may be kept sealed in bond", "bool",
               "At the desk a captain may leave a cargo sealed aboard: no tax and no risk on it, but none of it "
               "can be sold in that port until the house has sailed."),
             _pct("rules.customs.drift", "Most the rate moves in a month", "", 0, 0.5),
             _pct("rules.customs.range", "Most the rate strays from the port's base rate", "", 0, 0.5),
             _pct("rules.customs.min_rate", "Lowest rate anywhere", "", 0, 1),
             _pct("rules.customs.max_rate", "Highest rate anywhere", "", 0, 1),
             _pct("rules.customs.max_declare", "Highest declaration allowed (share of true worth)",
                  "Above 100% is over-declaring: she never buys, you pay more tax, and your standing rises.", 1, 5)]},
         {"title": "The Registrar (Mrs. Marlowe, at each captain's home port)", "fields": [
             F("rules.registrar.enabled", "The Registrar meets each house in its home port with a price tip", "bool",
               "On: a house coming home is met by the Registrar (cast key taxlady) instead of the port's officer, "
               "and told this month's price of one cargo in one other port, written into its Price Book and read "
               "aloud. Off: the home port's own officer waves it in, with no tip."),
             F("rules.registrar.stale_months", "She tips a port not seen for at least (months)", "int",
               "She picks a port whose price the house hasn't seen for this long, or never. If every price is "
               "fresher than that, she gives the oldest one.", min=0, max=60),
             F("rules.registrar.held_first", "She favours a cargo the house is carrying", "bool",
               "Off: any cargo.")]},
         {"title": "Port Authority: her odds", "fields": [
             _pct("rules.customs.buy_base", "Chance she buys an honest line", "Times her greed, her mood, your standing and how much the port wants that cargo."),
             _pct("rules.customs.buy_k", "Buyout chance added by a 100% lie", "", 0, 5),
             F("rules.customs.buy_exp", "Buyout curve", "num", "1 rises evenly with the lie; above 1 small lies are "
               "safe and big ones are not.", min=0.2, max=5, step=0.05),
             _pct("rules.customs.buy_cap", "Most chance of a buyout"),
             _pct("rules.customs.audit_base", "Chance she checks any under-declared line"),
             _pct("rules.customs.audit_k", "Audit chance added by a 100% lie", "Times her cunning, your standing, her mood "
                  "and the difficulty level's customs setting.", 0, 5),
             _pct("rules.customs.audit_cap", "Most chance of an audit"),
             F("rules.customs.appetite_power", "How much the port's own demand matters", "num",
               "Her buyout chance is multiplied by the port's local price for that cargo raised to this power. 0 ignores it.",
               min=0, max=5, step=0.1),
             _pct("rules.customs.greed_weight", "Each point of greed above 5: more buyouts", "", 0, 1),
             _pct("rules.customs.cunning_weight", "Each point of cunning above 5: more audits", "", 0, 1),
             _pct("rules.customs.rep_audit", "Standing 100 cuts audits by (standing 0 adds the same)", "", 0, 1),
             _pct("rules.customs.rep_buy", "Standing 100 cuts buyouts by (standing 0 adds the same)", "", 0, 1),
             _pct("rules.customs.mood_swing", "Her mood swing, for ports that do not set their own", "", 0, 1),
             _pct("rules.customs.tell_curious", "Her tell: curious above this risk", "", 0, 1),
             _pct("rules.customs.tell_hungry", "Her tell: hungry above this risk", "", 0, 1)]},
         {"title": "Port Authority: outcomes and second chances", "fields": [
             F("rules.customs.fine_mult", "Caught: fine as a multiple of the tax dodged", "num", min=0, max=50, step=0.5),
             F("rules.customs.caught_rep", "Caught: standing lost in that port", "num", min=0, max=100, step=1),
             F("rules.customs.over_rep", "Over-declaring to the limit: standing gained", "num", min=0, max=100, step=0.5),
             F("rules.customs.strongbox", "Her strongbox: silver she can spend on buyouts", "int",
               "Once it is empty she cannot buy any more, so a big lie may only be partly bought.", min=0, max=10**9),
             _pct("rules.customs.strongbox_swing", "Strongbox varies by up to", "", 0, 1),
             _pct("rules.customs.buyback_premium", "Buying it back costs her price plus", "", 0, 10),
             _pct("rules.customs.bribe_share", "Sweetener: share of the tax declared", "", 0, 10),
             F("rules.customs.bribe_min", "Sweetener: least it costs", "int", min=0, max=10**7),
             _pct("rules.customs.bribe_cut", "Sweetener taken: audit chance cut by"),
             _pct("rules.customs.bribe_honest", "Chance she is honest and refuses it",
                  "Less for greedy officers, more for upright ones."),
             F("rules.customs.bribe_refused_mult", "Sweetener refused: audit chance multiplied by", "num", min=1, max=10, step=0.05),
             F("rules.customs.bribe_rep", "Sweetener refused: standing lost", "num", min=0, max=100, step=1)]},
     ]},
    {"id": "goods", "title": "Cargo", "intro": "What can be traded. Removing a cargo during a game discards any that players hold.",
     "tables": [
         {"path": "goods", "title": "Cargoes", "kind": "dict", "id_label": "Key",
          "columns": [C("name", "Name", "text", max=30),
                      C("family_name", "Family-friendly name", "text", "Used when the content rating is family-friendly. Blank keeps the name.", max=30),
                      C("base", "Usual price", "num", min=0.5, max=10**7, step=1),
                      C("vol", "Monthly swing", "pct", min=0, max=1),
                      C("depth", "Depth (units)", "int", "Units traded that move the local price by the 'price move' setting.", min=1, max=10**7),
                      C("contraband", "Contraband", "bool", "Subject to bans, searches and seizure."),
                      C("ban_odds", "Sometimes contraband", "pct",
                        "For cargo that is normally legal: the chance a port's ban also covers it. While it does, it sells "
                        "for more there and can be searched and seized. Ignored when Contraband is ticked.",
                        min=0, max=1, default=0.0)]},
     ]},
    {"id": "ports", "title": "Ports", "intro": "Where the game is played. The chart covers longitude 85 to 135 and latitude -10 to 35.",
     "tables": [
         {"path": "ports", "title": "Ports", "kind": "dict", "id_label": "Key",
          "columns": [C("name", "Name", "text", max=30),
                      C("lon", "Longitude", "num", min=LON_MIN, max=LON_MAX, step=0.1),
                      C("lat", "Latitude", "num", min=LAT_MIN, max=LAT_MAX, step=0.1),
                      C("region", "Sea", "select", options_from="regions"),
                      C("shipyard", "Shipyard", "bool"),
                      C("bank", "Bank", "bool", "The bank's counter in this port. It is the one account: deposit anywhere, "
                        "withdraw anywhere there is a counter. A house's own home port always has it.", default=False),
                      C("warehouse", "Warehouse", "bool", "Houses may open a warehouse of their own here (Fleet and warehouse "
                        "sets the price). Each port's store holds only what was left in that port. Home always has one, free.",
                        default=False),
                      C("no_ban", "Never bans contraband", "bool"),
                      C("label_left", "Name left of dot", "bool", "Which side of the dot the name sits on the chart."),
                      C("dues", "Harbour dues level", "num", "Multiplies the Mayor's whole bill when leaving this port. 1 is normal, 0.5 half, 2 double.",
                        min=0, max=20, step=0.05, default=1.0),
                      C("tax_rate", "Port Authority base rate", "pct", "Taken on the declared value of cargo on arrival. "
                        "0 makes a free port: no declaration at all. The rate drifts around this each month.",
                        min=0, max=1, default=0.05),
                      C("officer", "Port Authority officer", "select", "The cast member at the desk (Cast & Voices). "
                        "Her greed and cunning shape the odds; her pictures are this port's Tax lady pictures.",
                        options_from="characters", default="taxlady"),
                      C("mood", "Officer's mood swing", "pct", "How far her odds can move from one visit to the next.",
                        min=0, max=1, default=0.15)]},
     ],
     "matrix": {"path": "ports", "sub": "mods", "cols_from": "goods", "title": "Local prices",
                "help": "Each cell multiplies the cargo's usual price in that port. Below 1 it is made there and cheap; "
                        "above 1 it is in demand. Blank means 1.", "min": 0.05, "max": 20}},
    {"id": "ships", "title": "Ships", "intro": "What the shipyards sell. A ship type removed during a game is replaced by the shipwreck ship.",
     "tables": [
         {"path": "ships", "title": "Ship types", "kind": "dict", "id_label": "Key",
          "columns": [C("name", "Name", "text", max=30),
                      C("hold", "Hold (units)", "int", min=1, max=10**6),
                      C("hull", "Hull points", "int", min=1, max=10**5),
                      C("slots", "Gun mounts", "int", min=0, max=500),
                      C("price", "Price", "int", min=0, max=10**9),
                      C("fast", "Fast", "bool", "Runs from pirates better and suffers less in storms.")]},
     ],
     "groups": [
         {"title": "Ship names", "fields": [
             F("ship_names", "Names given to new ships", "lines", "One per line.", max=40)]},
     ]},
    {"id": "weather", "title": "Weather & Seas", "intro": "Storm odds for each sea and what storms do.",
     "tables": [
         {"path": "regions", "title": "Seas", "kind": "dict", "id_label": "Key",
          "help": "Seasons are a list like [{\"months\": [6,7,8,9,10], \"typhoon\": 0.18, \"squalls\": 0.3}]. "
                  "Months are 1 to 12; odds are 0 to 1 and replace the usual odds in those months.",
          "columns": [C("name", "Name", "text", max=40),
                      C("typhoon", "Typhoon chance", "pct", min=0, max=1),
                      C("squalls", "Squall chance", "pct", min=0, max=1),
                      C("label_lon", "Label longitude", "num", min=LON_MIN, max=LON_MAX, step=0.1),
                      C("label_lat", "Label latitude", "num", min=LAT_MIN, max=LAT_MAX, step=0.1),
                      C("seasons", "Seasons", "json")]},
     ],
     "groups": [
         {"title": "Forecast and storms", "fields": [
             _pct("rules.weather.forecast_accuracy", "How often the forecast is right"),
             F("rules.weather.storm_chance", "Chance of being caught: calm, fair, squalls, typhoon", "numlist",
               "Four numbers from 0 to 1. Multiplied by distance and the difficulty level.", min=0, max=1, count=4),
             F("rules.weather.storm_dmg_min", "Storm damage per ship: least", "int", min=0, max=10000),
             F("rules.weather.storm_dmg_max", "Storm damage per ship: most", "int", min=0, max=10000),
             F("rules.weather.typhoon_dmg_min", "Typhoon damage per ship: least", "int", min=0, max=10000),
             F("rules.weather.typhoon_dmg_max", "Typhoon damage per ship: most", "int", min=0, max=10000),
             F("rules.weather.fast_dmg_mult", "Damage multiplier for fast ships", "num", min=0, max=5, step=0.05),
             _pct("rules.weather.offcourse", "Chance a typhoon blows you to another port")]},
         {"title": "Distance", "fields": [
             F("rules.weather.risk_div", "Chart distance that counts as normal risk", "int", "Shorter runs are safer, longer ones riskier.", min=10, max=5000),
             F("rules.weather.risk_min", "Least risk multiplier", "num", min=0, max=10, step=0.05),
             F("rules.weather.risk_max", "Greatest risk multiplier", "num", min=0, max=10, step=0.05)]},
     ]},
    {"id": "danger", "title": "Pirates & Customs", "intro": "Everything that can go wrong at sea and at the dock.",
     "groups": [
         {"title": "Pirates", "fields": [
             _pct("rules.pirates.chance", "Chance of attack per voyage", "Multiplied by distance and the difficulty level."),
             F("rules.pirates.fleet_min", "Fewest junks", "int", min=1, max=500),
             F("rules.pirates.fleet_base", "Most junks for a small fleet", "int", min=1, max=500),
             F("rules.pirates.fleet_per_hold", "One more junk per this much hold", "int", min=1, max=10**6),
             F("rules.pirates.fleet_max", "Most junks ever", "int", min=1, max=1000),
             _pct("rules.pirates.hit", "Each junk's chance to hit per round"),
             F("rules.pirates.dmg_min", "Damage per hit: least", "int", min=0, max=10000),
             F("rules.pirates.dmg_max", "Damage per hit: most", "int", min=0, max=10000),
             F("rules.pirates.booty_min", "Booty per junk sunk: least", "int", min=0, max=10**7),
             F("rules.pirates.booty_max", "Booty per junk sunk: most", "int", min=0, max=10**7),
             F("rules.pirates.booty_growth", "Months for booty to double", "int", min=1, max=10000),
             _pct("rules.pirates.plunder_min", "Cargo plundered if caught running: least"),
             _pct("rules.pirates.plunder_max", "Cargo plundered if caught running: most")]},
         {"title": "Battles", "fields": [
             F("rules.pirates.rounds", "Rounds before the enemy breaks off", "int", min=1, max=50),
             _pct("rules.pirates.gun_hit", "Each gun's chance to hit per round"),
             F("rules.pirates.hp", "Hits to sink a junk", "int", min=1, max=100),
             _pct("rules.pirates.run_base", "Chance to outrun per round"),
             _pct("rules.pirates.run_fast", "Bonus if every ship is fast"),
             _pct("rules.pirates.run_round", "Bonus added each round")]},
         {"title": "Sea battle on screen", "fields": [
             F("rules.battle.interactive", "Captains fight their battles on screen", "bool",
               "On: a house that is attacked while its captain is at a screen fights round by round, and nobody lands "
               "until every fight is over. Off: every fight is settled at once from standing orders, as before."),
             F("rules.battle.round_secs", "Seconds to choose each round", "int",
               "When the time runs out the round is played on the captain's standing orders.", min=5, max=600),
             F("rules.battle.first_extra", "Extra seconds on the first round", "int", min=0, max=600),
             F("rules.battle.voice_grace", "Seconds allowed for the bosun's line", "int",
               "Added to every round so the clock does not run while she is speaking.", min=0, max=60),
             _pct("rules.battle.gun_loss", "Enemy hits that smash guns instead of the hull",
                  "Each hit on a ship that still has guns: this share dismounts guns (no hull damage); the rest hole the hull."),
             _pct("rules.battle.gun_loss_two", "Gun hits that smash two guns, not one"),
             F("rules.battle.parley", "Pirates name a price to let the fleet pass", "bool",
               "Before the first shot. The pirate queen's fleet never does."),
             F("rules.battle.parley_per_junk", "Their price: silver per junk", "int", min=0, max=10**7),
             _pct("rules.battle.parley_cargo", "Their price: share of the cargo's usual value"),
             _pct("rules.battle.retreat_min", "Retreat: cargo thrown overboard, least"),
             _pct("rules.battle.retreat_max", "Retreat: cargo thrown overboard, most"),
             F("rules.battle.retreat_floor", "Retreat: hull left on the last ship", "int",
               "A retreat never sinks the last ship; she limps in with this much hull.", min=1, max=1000)]},
         {"title": "The pirate queen", "fields": [
             _pct("rules.liyuen.chance", "Chance her fleet finds an unprotected player"),
             F("rules.liyuen.fleet_base", "War junks: base", "int", min=1, max=1000),
             F("rules.liyuen.fleet_per_hold", "One more per this much hold", "int", min=1, max=10**6),
             F("rules.liyuen.fleet_max", "Most war junks", "int", min=1, max=1000),
             _pct("rules.liyuen.hit", "Each war junk's chance to hit"),
             F("rules.liyuen.dmg_min", "Damage per hit: least", "int", min=0, max=10000),
             F("rules.liyuen.dmg_max", "Damage per hit: most", "int", min=0, max=10000),
             F("rules.liyuen.protect_months", "Months of protection bought", "int", min=1, max=120),
             _pct("rules.liyuen.protect_save", "Chance her fleet drives off other pirates"),
             _pct("rules.liyuen.cost_share", "Tribute as a share of net worth"),
             F("rules.liyuen.cost_min", "Least tribute", "int", min=0, max=10**9),
             F("rules.liyuen.tribute", "She names her price at sea before the first shot", "bool",
               "An unprotected house she finds may pay tribute there and then, and is protected as if it had paid "
               "at home. She attacks only if the captain refuses or cannot pay. A house with nobody at a screen "
               "pays if it has the silver."),
             F("rules.liyuen.tribute_mult", "Her price at sea: times the tribute at home", "num", min=1, max=100),
             F("rules.liyuen.renew_at", "Can renew with this many months left", "int", min=0, max=120)]},
         {"title": "Contraband and customs", "fields": [
             _pct("rules.contraband.seize_chance", "Chance of seizure in an ordinary port", "Multiplied by the difficulty level."),
             _pct("rules.contraband.seize_banned", "Chance of seizure where it is banned"),
             _pct("rules.contraband.seize_rep_relief", "Reduction per point of standing", "", 0, 0.1),
             F("rules.contraband.fine_per_unit", "Fine per unit seized", "int", min=0, max=10**7),
             F("rules.contraband.rep_penalty", "Standing lost when caught", "num", min=0, max=100, step=1)]},
         {"title": "Market news and bans", "fields": [
             _pct("rules.events.shock_chance", "Chance of a glut or shortage each month"),
             F("rules.events.shock_mults", "Possible price multipliers", "numlist", "One is picked at random.", min=0.05, max=20),
             F("rules.events.shock_min_turns", "Lasts at least (months)", "int", min=1, max=60),
             F("rules.events.shock_max_turns", "Lasts at most (months)", "int", min=1, max=60),
             _pct("rules.events.ban_chance", "Chance a port bans contraband each month"),
             F("rules.events.ban_min_turns", "Ban lasts at least (months)", "int", min=1, max=60),
             F("rules.events.ban_max_turns", "Ban lasts at most (months)", "int", min=1, max=60),
             F("rules.events.ban_price_mult", "Contraband price multiplier under a ban", "num", min=0.1, max=20, step=0.05)]},
         {"title": "Crashes and booms (lottery prices)", "fields": [
             _pct("rules.events.windfall_chance", "Chance of a crash or a boom each month",
                  "One cargo in one port goes far outside its usual price range. Crash or boom is a coin toss."),
             _pct("rules.events.windfall_pair_chance", "Chance a crash and a boom land together",
                  "When one happens, the chance the opposite one also happens that month, in another port."),
             F("rules.events.crash_min", "Crash: lowest price (times normal)", "num", "0.02 = 2% of the normal price.", min=0.001, max=1, step=0.005),
             F("rules.events.crash_max", "Crash: highest price (times normal)", "num", min=0.001, max=1, step=0.005),
             F("rules.events.boom_min", "Boom: lowest price (times normal)", "num", min=1, max=100, step=0.5),
             F("rules.events.boom_max", "Boom: highest price (times normal)", "num", min=1, max=100, step=0.5),
             F("rules.events.windfall_min_turns", "Lasts at least (months)", "int", min=1, max=12),
             F("rules.events.windfall_max_turns", "Lasts at most (months)", "int", min=1, max=12)]},
     ]},
]

GRAPHIC_SLOTS = [
    ["logo", "Logo", "Replaces the lettered title on the join screen, lobby and harbor board. A wide transparent PNG works best."],
    ["favicon", "Browser tab icon", "A small square image."],
    ["masthead_bg", "Title banner background", "Behind the title on the join and lobby screens."],
    ["page_bg", "Player screen background", "Behind the cards on every player screen. Subtle textures work best."],
    ["board_bg", "Harbor board background", "Behind the big-screen board."],
    ["chart_bg", "Chart artwork", "Replaces the drawn coastlines. Must cover longitude 85-135, latitude -10 to 35 at 5:3 (for example 2000 x 1200)."],
]
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".ico")
ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,23}$")
COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
# Pictures may live in web/uploads (older art), web/media/<kind>/<subject>/ (the media library) or web/assets.
URL_RE = re.compile(r"^(/uploads/[A-Za-z0-9._-]+|/(media|assets)/(?!_trash/)(?!.*\.\.)[A-Za-z0-9._/-]+|https?://[^\s\"'()<>]+)$")


def defaults():
    return copy.deepcopy(DEFAULTS)


def get_path(d, path):
    for part in path.split("."):
        d = d[part]
    return d


def set_path(d, path, value):
    parts = path.split(".")
    for part in parts[:-1]:
        d = d.setdefault(part, {})
    d[parts[-1]] = value


def _merge(base, over, path=""):
    """Lay saved settings over the defaults."""
    if path in WHOLE:
        return copy.deepcopy(over)
    if isinstance(base, dict) and isinstance(over, dict):
        out = {}
        for k, v in base.items():
            sub = (path + "." + k) if path else k
            out[k] = _merge(v, over[k], sub) if k in over else copy.deepcopy(v)
        return out
    return copy.deepcopy(over)


# ------------------------------------------------------------- checking --
def _coerce(spec, value, where, errors):
    kind, label = spec["type"], spec.get("label", where)

    def bad(msg):
        errors.append("{}: {}".format(where + " / " + label if where else label, msg))

    def number(v, integer=False):
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            try:
                v = float(str(v).strip())
            except (TypeError, ValueError):
                bad("must be a number")
                return None
        if v != v or v in (float("inf"), float("-inf")):
            bad("must be a number")
            return None
        lo, hi = spec.get("min"), spec.get("max")
        if lo is not None and v < lo:
            bad("must be at least {}".format(lo))
            return None
        if hi is not None and v > hi:
            bad("must be at most {}".format(hi))
            return None
        return int(round(v)) if integer else float(v)

    if kind in ("int",):
        return number(value, True)
    if kind in ("num", "pct"):
        return number(value)
    if kind == "bool":
        return bool(value)
    if kind in ("text", "code"):
        s = str(value if value is not None else "")
        if kind == "text":
            s = " ".join(s.split())
        return s[:spec.get("max", 200)]
    if kind == "color":
        if not isinstance(value, str) or not COLOR_RE.match(value):
            bad("must be a colour like #b3261e")
            return None
        return value.lower()
    if kind == "colorlist":
        if not isinstance(value, list) or len(value) != spec.get("count", 8) or \
                not all(isinstance(c, str) and COLOR_RE.match(c) for c in value):
            bad("needs {} colours".format(spec.get("count", 8)))
            return None
        return [c.lower() for c in value]
    if kind == "numlist":
        if not isinstance(value, list) or not value:
            bad("needs at least one number")
            return None
        out = []
        for v in value:
            n = number(v, spec.get("integer", False))
            if n is None:
                return None
            out.append(n)
        if spec.get("count") and len(out) != spec["count"]:
            bad("needs exactly {} numbers".format(spec["count"]))
            return None
        return out
    if kind == "lines":
        if not isinstance(value, list):
            bad("must be a list")
            return None
        out = [" ".join(str(v).split())[:spec.get("max", 60)] for v in value]
        out = [v for v in out if v]
        if not out:
            bad("needs at least one line")
            return None
        return out
    if kind == "select":
        return str(value)        # checked against its options in validate()
    if kind == "json":
        return value
    return value


def _seasons(value, where, errors):
    out = []
    if not isinstance(value, list):
        errors.append(where + ": seasons must be a list")
        return out
    for s in value:
        try:
            months = sorted({int(m) for m in s["months"] if 1 <= int(m) <= 12})
            ty, sq = float(s["typhoon"]), float(s["squalls"])
            if not months or not (0 <= ty <= 1) or not (0 <= sq <= 1) or ty + sq > 1:
                raise ValueError
            out.append({"months": months, "typhoon": ty, "squalls": sq})
        except (KeyError, TypeError, ValueError):
            errors.append(where + ": each season needs months (1-12), typhoon and squalls (0 to 1)")
    return out


def validate(raw):
    """Returns (clean settings, list of problems). Problems mean nothing was changed."""
    errors = []
    if not isinstance(raw, dict):
        return defaults(), ["Settings must be an object."]
    try:
        cfg = _merge(DEFAULTS, raw)
    except (TypeError, KeyError, AttributeError):
        return defaults(), ["Settings are not in the expected shape."]

    for sec in SECTIONS:
        for tb in sec.get("tables", []):
            rows = get_path(cfg, tb["path"])
            title = tb["title"]
            if tb["kind"] == "dict":
                if not isinstance(rows, dict) or not rows:
                    errors.append("{}: needs at least one row".format(title))
                    set_path(cfg, tb["path"], copy.deepcopy(get_path(DEFAULTS, tb["path"])))
                    continue
                clean = {}
                for key, row in rows.items():
                    if not isinstance(key, str) or not ID_RE.match(key):
                        errors.append("{}: key '{}' must be lower-case letters, digits or _ and start with a letter".format(title, key))
                        continue
                    row = row if isinstance(row, dict) else {}
                    new = {k: v for k, v in row.items() if k in ("mods",)}
                    for col in tb["columns"]:
                        if col["key"] not in row and "default" in col:
                            # a column added later: settings saved before it get the shipped value, or the default
                            shipped = get_path(DEFAULTS, tb["path"]).get(key, {})
                            new[col["key"]] = _coerce(col, shipped.get(col["key"], col["default"]), "{} / {}".format(title, key), errors)
                            continue
                        if col["key"] not in row:
                            errors.append("{} / {}: '{}' is missing".format(title, key, col["label"]))
                            continue
                        new[col["key"]] = _coerce(col, row[col["key"]], "{} / {}".format(title, key), errors)
                    clean[key] = new
                set_path(cfg, tb["path"], clean)
            else:
                clean = []
                for i, row in enumerate(rows if isinstance(rows, list) else []):
                    row = row if isinstance(row, dict) else {}
                    new = {}
                    for col in tb["columns"]:
                        new[col["key"]] = _coerce(col, row.get(col["key"]), "{} / row {}".format(title, i + 1), errors)
                    clean.append(new)
                if not clean:
                    errors.append("{}: needs at least one row".format(title))
                set_path(cfg, tb["path"], clean)
        for grp in sec.get("groups", []):
            for f in grp["fields"]:
                try:
                    cur = get_path(cfg, f["path"])
                except (KeyError, TypeError):
                    errors.append("{}: missing".format(f["label"]))
                    continue
                set_path(cfg, f["path"], _coerce(f, cur, sec["title"], errors))
    if errors:
        return cfg, errors

    goods, ports, ships, regions = cfg["goods"], cfg["ports"], cfg["ships"], cfg["regions"]
    for key, r in regions.items():
        r["seasons"] = _seasons(r.get("seasons", []), "Seas / " + key, errors)
        if r["typhoon"] + r["squalls"] > 1:
            errors.append("Seas / {}: typhoon and squall chances add up to more than 100%".format(key))
    if len(ports) < 2:
        errors.append("Ports: the game needs at least two ports")
    for key, p in ports.items():
        if p["region"] not in regions:
            errors.append("Ports / {}: sea '{}' does not exist".format(key, p["region"]))
        mods = {}
        for g, v in (p.get("mods") or {}).items():
            if g not in goods:
                continue
            try:
                v = float(v)
            except (TypeError, ValueError):
                errors.append("Local prices / {} / {}: must be a number".format(key, g))
                continue
            if not 0.05 <= v <= 20:
                errors.append("Local prices / {} / {}: must be between 0.05 and 20".format(key, g))
            elif abs(v - 1.0) > 1e-9:
                mods[g] = v
        p["mods"] = mods
    g = cfg["rules"]["game"]
    if cfg["rules"]["start"].get("where") not in ("random", "home"):
        errors.append("Game Setup: 'Where players start' must be random or home")
    if g["home"] not in ports:
        errors.append("Game Setup: the home port '{}' does not exist".format(g["home"]))
    for where, k in (("Game Setup / starting ship", cfg["rules"]["start"]["ship"]),
                     ("Game Setup / replacement ship", cfg["rules"]["wreck"]["ship"])):
        if k not in ships:
            errors.append("{}: ship '{}' does not exist".format(where, k))
    if cfg["rules"]["start"]["ship"] in ships:
        cfg["rules"]["start"]["guns"] = min(cfg["rules"]["start"]["guns"], ships[cfg["rules"]["start"]["ship"]]["slots"])
    g["lengths"] = sorted(set(g["lengths"]))
    if g["default_years"] not in g["lengths"]:
        g["default_years"] = min(g["lengths"], key=lambda y: abs(y - g["default_years"]))
    if cfg["difficulty"]["level"] not in cfg["difficulty"]["presets"]:
        errors.append("Ratings: difficulty level '{}' does not exist".format(cfg["difficulty"]["level"]))
    if cfg["content"]["rating"] not in ("historical", "family"):
        errors.append("Ratings: unknown content rating")
    cfg["ranks"].sort(key=lambda r: r["worth"])
    for lo, hi, label in (("storm_dmg_min", "storm_dmg_max", "Storm damage"),
                          ("typhoon_dmg_min", "typhoon_dmg_max", "Typhoon damage")):
        if cfg["rules"]["weather"][lo] > cfg["rules"]["weather"][hi]:
            errors.append("Weather: {} 'least' is above 'most'".format(label))
    for grp, lo, hi, label in (("pirates", "dmg_min", "dmg_max", "Pirate damage"),
                               ("pirates", "booty_min", "booty_max", "Booty"),
                               ("pirates", "plunder_min", "plunder_max", "Plunder"),
                               ("liyuen", "dmg_min", "dmg_max", "Pirate queen damage"),
                               ("battle", "retreat_min", "retreat_max", "Retreat cargo"),
                               ("bank", "mug_min", "mug_max", "Robbery"),
                               ("bank", "whrob_min", "whrob_max", "Warehouse robbery"),
                               ("events", "shock_min_turns", "shock_max_turns", "Shortage length"),
                               ("events", "ban_min_turns", "ban_max_turns", "Ban length"),
                               ("events", "crash_min", "crash_max", "Crash price"),
                               ("events", "boom_min", "boom_max", "Boom price"),
                               ("events", "windfall_min_turns", "windfall_max_turns", "Crash or boom length"),
                               ("weather", "risk_min", "risk_max", "Risk multiplier")):
        if cfg["rules"][grp][lo] > cfg["rules"][grp][hi]:
            errors.append("{}: 'least' is above 'most'".format(label))
    if cfg["rules"]["market"]["spread_base"] - cfg["rules"]["market"]["spread_swing"] < 0:
        errors.append("Economy: the dealer's margin would fall below zero at standing 100")

    gr = cfg["graphics"]
    for slot, _label, _help in GRAPHIC_SLOTS:
        v = gr.get(slot) or ""
        gr[slot] = v if isinstance(v, str) and URL_RE.match(v) else ""
    for group, table in (("goods", goods), ("ports", ports), ("ships", ships)):
        src = gr.get(group) if isinstance(gr.get(group), dict) else {}
        gr[group] = {k: v for k, v in src.items() if k in table and isinstance(v, str) and URL_RE.match(v)}
    # Cast members added in a later version join a saved cast once (deleting one afterwards sticks).
    seeded = set(cfg["rules"]["customs"].get("seeded") or [])
    for cid in cast.SEEDED:
        if cid not in seeded and cid not in cfg["characters"]:
            cfg["characters"][cid] = copy.deepcopy(cast.CHARACTERS[cid])
        seeded.add(cid)
    cfg["rules"]["customs"]["seeded"] = sorted(seeded)
    for key, p in ports.items():
        if p.get("officer") not in cfg["characters"]:
            p["officer"] = "taxlady" if "taxlady" in cfg["characters"] else next(iter(cfg["characters"]), "")
    lang = str(cfg["language"].get("active") or "en")
    cfg["language"] = {"active": lang if re.match(r"^[a-z]{2,3}(-[a-z0-9]{2,8})?$", lang) else "en"}
    cast.clean(cfg, URL_RE, errors)
    return cfg, errors


# ---------------------------------------------------------------- files --
def _read(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
    os.replace(tmp, path)


def load():
    """Saved settings laid over the defaults. Never fails: bad files fall back to defaults."""
    if os.path.isfile(SETTINGS_FILE):
        try:
            cfg, errors = validate(_read(SETTINGS_FILE))
            if not errors:
                return cfg
            print("config/settings.json has problems, using defaults: " + "; ".join(errors[:3]))
        except (ValueError, OSError) as e:
            print("Could not read config/settings.json ({}), using defaults.".format(e))
    return defaults()


def save(cfg):
    """Keeps a dated copy of the previous settings, then writes the new ones."""
    if os.path.isfile(SETTINGS_FILE):
        os.makedirs(BACKUP_DIR, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        dst = os.path.join(BACKUP_DIR, "settings-{}.json".format(stamp))
        n = 1
        while os.path.exists(dst):
            n += 1
            dst = os.path.join(BACKUP_DIR, "settings-{}-{}.json".format(stamp, n))
        with open(SETTINGS_FILE, "rb") as src, open(dst, "wb") as out:
            out.write(src.read())
        old = sorted(f for f in os.listdir(BACKUP_DIR) if f.endswith(".json"))
        for f in old[:-KEEP_BACKUPS]:
            os.remove(os.path.join(BACKUP_DIR, f))
    _write(SETTINGS_FILE, cfg)


def _safe_name(name):
    name = re.sub(r"[^A-Za-z0-9 _-]", "", str(name or "")).strip()[:40]
    return name


def list_dir(folder):
    if not os.path.isdir(folder):
        return []
    out = []
    for f in sorted(os.listdir(folder)):
        if f.endswith(".json"):
            out.append({"name": f[:-5], "time": int(os.path.getmtime(os.path.join(folder, f)))})
    return out


def preset_path(name):
    name = _safe_name(name)
    return os.path.join(PRESET_DIR, name + ".json") if name else None


def read_named(folder, name):
    name = re.sub(r"[^A-Za-z0-9 _-]", "", str(name or ""))
    path = os.path.join(folder, name + ".json")
    if not name or not os.path.isfile(path):
        return None
    return _read(path)


# ------------------------------------------------------------- language --
def lang_path(code):
    return os.path.join(LANG_DIR, code + ".json") if re.match(r"^[a-z]{2,3}(-[a-z0-9]{2,8})?$", str(code)) else None


def load_lang(code):
    """{"name": ..., "strings": {key: text}, "family": {key: text}} for one language."""
    out = {"name": "English" if code == "en" else code, "strings": {}, "family": {}}
    path = lang_path(code)
    if path and os.path.isfile(path):
        try:
            data = _read(path)
            out["name"] = str(data.get("name") or out["name"])[:40]
            for part in ("strings", "family"):
                src = data.get(part)
                if isinstance(src, dict):
                    out[part] = {str(k): str(v) for k, v in src.items() if isinstance(v, str) and v.strip()}
        except (ValueError, OSError, AttributeError):
            pass
    return out


def save_lang(code, data):
    path = lang_path(code)
    if not path:
        raise ValueError("Language codes look like 'en', 'de' or 'pt-br'.")
    clean = {"name": " ".join(str(data.get("name") or code).split())[:40], "strings": {}, "family": {}}
    for part in ("strings", "family"):
        src = data.get(part)
        if isinstance(src, dict):
            clean[part] = {str(k)[:60]: str(v)[:600] for k, v in src.items() if isinstance(v, str) and v.strip()}
    _write(path, clean)


def list_langs():
    out = {"en": "English"}
    if os.path.isdir(LANG_DIR):
        for f in sorted(os.listdir(LANG_DIR)):
            if f.endswith(".json") and lang_path(f[:-5]):
                out[f[:-5]] = load_lang(f[:-5])["name"]
    return out


# ---------------------------------------------------------------- theme --
def _css_url(v):
    return 'url("{}")'.format(v) if v and URL_RE.match(v) else None


def _font(v):
    return str(v or "serif").replace(";", "").replace("}", "").replace("{", "").replace("<", "")


def font_vars(th):
    return ["  --title: {};".format(_font(th["font_title"])),
            "  --serif: {};".format(_font(th["font_serif"])),
            "  --sans: {};".format(_font(th["font_sans"])),
            "  --special: {};".format(_font(th["font_special"]))]


def fonts_css(cfg, local=""):
    """/fonts.css: the downloaded @font-face rules plus the four lettering roles.
    Loaded by the player screen, the harbor board and the admin page."""
    return (local or "") + ":root {\n" + "\n".join(font_vars(cfg["theme"])) + "\n}\n"


def theme_css(cfg):
    th, gr = cfg["theme"], cfg["graphics"]
    lines = [":root {"]
    for k, v in th["colors"].items():
        lines.append("  --{}: {};".format(k, v))
    lines.extend(font_vars(th))
    lines.append("  --base-size: {}px;".format(th["font_size"]))
    lines.append("  --radius: {}px;".format(th["radius"]))
    lines.append("  --amb-seconds: {};".format(int(th.get("ambient_seconds", 40))))
    lines.append("  --amb-dim: {};".format(round(int(th.get("ambient_dim", 55)) / 100, 2)))
    lines.append("}")
    for sel, slot in ((".masthead", "masthead_bg"), ("body.player", "page_bg"), ("body.board", "board_bg")):
        u = _css_url(gr.get(slot))
        if u:
            lines.append("{} {{ background-image: {}; background-size: cover; background-position: center; "
                         "background-attachment: {}; }}".format(sel, u, "scroll" if slot == "masthead_bg" else "fixed"))
    lines.append(th.get("custom_css") or "")
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------- password --
def _hash(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 120000).hex()


def has_password():
    return os.path.isfile(ADMIN_FILE)


def set_password(password):
    if not password:
        if os.path.isfile(ADMIN_FILE):
            os.remove(ADMIN_FILE)
        return
    salt = secrets.token_hex(16)
    _write(ADMIN_FILE, {"salt": salt, "hash": _hash(password, salt)})


def check_password(password):
    try:
        data = _read(ADMIN_FILE)
        return secrets.compare_digest(_hash(str(password or ""), data["salt"]), data["hash"])
    except (OSError, ValueError, KeyError):
        return False
