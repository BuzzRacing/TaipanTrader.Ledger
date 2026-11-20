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
        "logo": "/assets/branding/crimson-ledger-logo-v01.png",
        "favicon": "/assets/branding/crimson-ledger-icon-v01.png",
        "masthead_bg": "/uploads/historical-masthead.webp",
        "admin_masthead_bg": "/assets/branding/crimson-ledger-command-center-v01.webp",
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
                       "start_cash": 1.5, "seizure": 0.6, "jail": 0.5, "customs_view": "exact", "battle_view": "exact"},
            "normal": {"name": "Trade winds", "pirates": 1.0, "storms": 1.0, "interest": 1.0,
                       "start_cash": 1.0, "seizure": 1.0, "jail": 1.0, "customs_view": "bar", "battle_view": "bar"},
            "hard":   {"name": "Typhoon season", "pirates": 1.4, "storms": 1.3, "interest": 1.25,
                       "start_cash": 0.7, "seizure": 1.5, "jail": 1.5, "customs_view": "tell", "battle_view": "tell"},
        },
    },
    "ranks": [
        {"id": "debtor", "worth": -1000000000, "title": "Debtor"},
        {"id": "clerk", "worth": 0, "title": "Clerk"},
        {"id": "trader", "worth": 10000, "title": "Trader"},
        {"id": "merchant", "worth": 50000, "title": "Merchant"},
        {"id": "senior_merchant", "worth": 200000, "title": "Senior Merchant"},
        {"id": "merchant_prince", "worth": 500000, "title": "Merchant Prince"},
        {"id": "taipan", "worth": 1000000, "title": "Taipan"},
        # Ranks above Taipan (19 Nov 2026). "scales": the worth is for a game of rules.game.rank_years
        # years and grows or shrinks with the game's length (a 5-year game halves it).
        {"id": "tai_pan_china_seas", "worth": 25000000, "title": "Tai-Pan of the China Seas", "scales": True},
        {"id": "merchant_lord", "worth": 50000000, "title": "Merchant Lord", "scales": True},
        {"id": "hong_master", "worth": 100000000, "title": "Hong Master", "scales": True},
    ],
    "rules": {
        "game": {"start_year": 1860, "home": "hongkong", "max_players": 8,
                 "lengths": [5, 10, 20, 50], "default_years": 10, "grace_seconds": 25,
                 "rank_years": 10, "late_ranks_v1": False},
        "start": {"cash": 3500, "debt": 5000, "ship": "junk", "guns": 2, "rep": 50, "home_rep": 60,
                  "where": "random"},
        "captains": {"typed": False},
        "market": {"spread_base": 0.04, "spread_swing": 0.03, "impact": 0.25, "floor": 0.25,
                   "ceiling": 4.5, "reversion": 0.3, "vol_mult": 1.0, "start_spread": 0.15,
                   "rep_per_value": 5000, "rep_trade_cap": 2.0, "worth_cargo": 0.9,
                   "own_fade": 0.7, "avg_amber": 1.5, "avg_red": 2.5, "depth_v2": False,
                   # The dealers' purse (Game 3 review, 19 Nov 2026): each port's dealers have only so much
                   # silver a month for each cargo: purse_depths x the cargo's depth x its normal price there
                   # x the port's own purse size (Ports table). Silver asked past it is paid at purse_over.
                   "purse_enabled": True, "purse_depths": 0.75, "purse_over": 0.35,
                   "review3_v1": False,
                   # Wild cargoes (Game 4 review, 20 Nov 2026): Maijiuana (porcelain) swings wildly. Each month a
                   # port may start a run: its price climbs or falls runs_drift_min..max a month for runs_min..max
                   # months, on top of a bigger monthly swing (wild_vol), a weaker pull back (wild_reversion) and a
                   # much wider floor and ceiling (wild_floor..wild_ceiling x usual). No signal: no News, no arrow.
                   "wild_goods": ["porcelain"], "wild_vol": 0.35, "wild_reversion": 0.08,
                   "wild_floor": 0.15, "wild_ceiling": 6.0,
                   "runs_chance": 0.15, "runs_min": 2, "runs_max": 4, "runs_drift_min": 0.15, "runs_drift_max": 0.35,
                   "review4_v1": False},
        "bank": {"bank_rate": 0.01, "loan_rate": 0.03, "loan_base": 5000, "loan_per_rep": 100,
                 "loan_asset_share": 0.5, "debt_warn_mult": 2.5, "debt_rep_penalty": 1,
                 "debt_grace_months": 3, "debt_call_every": 3,
                 "debt_cap_mult": 3.0, "bankrupt_enabled": True, "bankrupt_months": 12, "bankrupt_warn": 3,
                 "bankrupt_stake": 2000, "bankrupt_rep": 10, "wu_advice": True, "wu_easy_share": 0.25,
                 "mug_threshold": 20000, "mug_chance": 0.06, "mug_rep": 0.6,
                 "mug_min": 0.07, "mug_max": 0.15,
                 "whrob_chance": 0.02, "whrob_rep": 0.6, "whrob_min": 0.10, "whrob_max": 0.30},
        # max_fleet counts merchantmen (ships with role "trader"). Escorts (guns, no hold) and cargo ships
        # (hold, no guns) have their own limits, and open once the house has escort_unlock merchantmen.
        "fleet": {"max_fleet": 5, "max_escorts": 5, "max_cargo": 5, "escort_unlock": 5, "cargo_unlock": 5,
                  "flagship_unlock": 0, "flagship_deter": 0.4,
                  "keep_trader": True, "seeded_ships": [], "gun_price": 600, "gun_resale": 0.333, "ship_resale": 0.5,
                  "cannon_cost": 7.5, "cannon_power": 2, "cannon_slots": 2,
                  # Weapons take cargo space (19 Nov 2026): units of a ship's hold each gun / cannon takes.
                  "gun_hold": 5, "cannon_hold": 10,
                  "warehouse_cap": 10000, "depot_open_cost": 10000, "depot_cap": 1000,
                  "depot_expand_cost": 100000, "depot_expand_cap": 1000, "repair_base": 6, "repair_price_div": 4000,
                  "repair_noyard": 1.3, "repair_rep_discount": 0.2, "ship_rep": 2,
                  # Crew wages and upkeep (Game 3 review, 19 Nov 2026), paid every month: upkeep_rate of each
                  # ship's price plus upkeep_gun for each gun or cannon, times (1 + upkeep_rank for each rank
                  # the house holds above upkeep_rank_from): a famous house's crews expect famous pay.
                  "upkeep_enabled": True, "upkeep_rate": 0.02, "upkeep_gun": 15,
                  "upkeep_rank": 0.25, "upkeep_rank_from": "merchant",
                  # Game 4 review (20 Nov 2026): the flagship's wage is flat, like a big merchantman's (times the
                  # rank multiplier as every ship), not 2% of her price. A ship laid up at home pays
                  # laid_up_wage of her wage. The Captain's Log notes wages carried by empty hold from idle_note_min.
                  "flagship_wage": 6000, "laid_up_wage": 0.25, "idle_note_min": 1000, "idle_note_share": 0.25,
                  # An escort that would sink limps home crippled cripple_chance of the time (hull 1, every gun
                  # and cannon gone); mending her costs cripple_repair of a new one.
                  "cripple_chance": 0.5, "cripple_repair": 0.333},
        "events": {"shock_chance": 0.35, "shock_mults": [0.4, 0.5, 2.0, 2.5, 3.0],
                   "shock_min_turns": 2, "shock_max_turns": 3, "ban_chance": 0.15,
                   "ban_min_turns": 3, "ban_max_turns": 5, "ban_price_mult": 1.5,
                   "windfall_chance": 0.12, "windfall_pair_chance": 0.1,
                   "crash_min": 0.02, "crash_max": 0.12, "boom_min": 2.5, "boom_max": 10.0,
                   "windfall_min_turns": 1, "windfall_max_turns": 2,
                   # Game 3 review (19 Nov 2026): when a shortage, a boom and a hot-tip boom (or a ban) meet on
                   # one cargo in one port, only the strongest counts (stack_booms False), and a boom's price
                   # never runs past its own size. Selling into a boom or a shortage uses it up: a sale of
                   # boom_eat_depths x the cargo's depth ends it, a smaller one shrinks it in proportion.
                   "stack_booms": False, "boom_eat_depths": 3.0},
        "contraband": {"seize_chance": 0.03, "seize_banned": 0.55, "seize_rep_relief": 0.003,
                       "fine_per_unit": 300, "rep_penalty": 15},
        "weather": {"forecast_accuracy": 0.8, "storm_chance": [0.0, 0.04, 0.20, 0.60],
                    "storm_dmg_min": 5, "storm_dmg_max": 20, "typhoon_dmg_min": 20,
                    "typhoon_dmg_max": 60, "fast_dmg_mult": 0.8, "offcourse": 0.15,
                    "risk_div": 350, "risk_min": 0.6, "risk_max": 1.8},
        # Storms and damage (storm.py, 20 Nov 2026; project doc "SeaTrader Storms and Damage"). A storm that
        # catches the fleet gets a severity score (sea, dice, distance, hold load, hull condition, guns,
        # difficulty) that falls in a band: Rough (scuffed), Heavy or Savage. Heavy and Savage take a share of
        # every ship's hull, of the hold and of the guns, and send the fleet to another port: Heavy to the
        # middle-ranked of the nearest ports that have a shipyard, Savage to the worst-ranked one (no yard).
        # While it is on it replaces the flat damage and the 15% typhoon detour above.
        "storm": {"enabled": True, "base": [0, 20, 32, 62], "dice_min": 0.6, "dice_max": 1.4,
                  "risk_w": 0.5, "load_w": 0.25, "hull_w": 0.5, "arms_w": 0.15,
                  "big_hull": 300, "big_mult": 0.85, "heavy_at": 45, "savage_at": 75, "cap": 130,
                  "rough_hull_min": 0.05, "rough_hull_max": 0.15,
                  "heavy_hull_min": 0.20, "heavy_hull_max": 0.40, "heavy_cargo_min": 0.10,
                  "heavy_cargo_max": 0.25, "heavy_guns": 0.33,
                  "savage_hull_min": 0.45, "savage_hull_max": 0.75, "savage_cargo_min": 0.25,
                  "savage_cargo_max": 0.55, "savage_guns": 0.67,
                  "divert_heavy": 1.0, "divert_savage": 1.0, "candidates": 4,
                  "w_price": 0.5, "w_yard": 0.35, "w_standing": 0.15, "ban_penalty": 0.25,
                  "patch_max": 0.5},
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
        # The crew hides a share before it is taken (owner's decision, 19 Nov 2026): whenever customs
        # seize contraband, the Port Authority buys cargo out, pirates plunder the hold, or the
        # moneylender closes the books, the crew always gets a random min..max share of it out of
        # sight first. Small, dear goods (dear_goods) hide dear_mult times as well.
        # The jail (jail.py, 19 Nov 2026). Chances and the crew's drinking are multiplied by the difficulty's "jail".
        "jail": {"enabled": True, "arrest_months": 1, "max_months": 6, "arrest_standing": 1,
                 "hostile_below": 20, "hostile_chance": 0.05, "contraband_chance": 0.25, "contraband_low_rep": 20,
                 "contraband_low_mult": 1.5, "slip_chance": 0.20, "slip_repeat": 0.15, "slip_repeat_months": 24,
                 "slip_jail_max": 0.65, "collectors_chance": 0.20, "bankrupt_months": 3,
                 "plea": True, "big_share": 0.05, "big_min": 1000, "plea1_min": 0.40, "plea1_max": 0.60,
                 "plea3_min": 0.10, "plea3_max": 0.25, "drink_min": 0.03, "drink_max": 0.10,
                 "spoil_min": 0.05, "spoil_max": 0.15, "perishables": ["rice", "tea", "spices"], "release_floor": 10},
        "hide": {"enabled": True, "min": 0.10, "max": 0.30, "dear_mult": 1.5, "dear_goods": ["gold", "opium"],
                 "customs": True, "desk": True, "pirates": True, "bankrupt": True},
        # The sea battle played on screen (engine.Game, "sea battles"). A captain at a screen chooses
        # each round; the month waits at sea until every fight is over.
        "battle": {"interactive": True, "parley": True, "parley_per_junk": 60, "parley_cargo": 0.05,
                   # Game 4 review (20 Nov 2026): a fair price to pass, parley_cargo..parley_cargo_max of the
                   # hold's value (drawn for each fight), so paying in cargo is always there when silver is short.
                   "parley_cargo_max": 0.10,
                   # Three kinds of enemy (Game 4 review): Admiral Li Yue's heavy war fleet (her own chance),
                   # and the ordinary pirates come either as raiders or, band_share of the time, a small lucky band.
                   # Raiders: fast, few guns (raider_guns x their fire), go for the hold, easy to outrun (+raider_run).
                   # A band: band_strength x the usual hull and guns, at most band_ships_max junks, band_booty x
                   # the booty; spare them (after the first round) and they pass on a price they know.
                   "fleet_types": True, "band_share": 0.3, "raider_guns": 0.6, "raider_run": 0.25,
                   "band_strength": 0.45, "band_ships_max": 4, "band_booty": 0.5, "lord_booty": 2.0,
                   "retreat_min": 0.15, "retreat_max": 0.30, "retreat_floor": 5,
                   "round_secs": 10, "first_extra": 10, "voice_grace": 0,
                   "gun_loss": 0.25, "gun_loss_two": 0.25,
                   # Hits that miss the guns may land in the hold: one kind of goods (gold as likely as rice)
                   # loses cargo_hit_min to cargo_hit_max of its units over the side, at least one.
                   "cargo_hit": 0.2, "cargo_hit_min": 0.1, "cargo_hit_max": 0.3,
                   # Spiteful crews: rolled at the sighting; they aim for the hold spite_hold times as often,
                   # and a hold hit goes for the dearest good aboard spite_aim of the time.
                   "spite": True, "spite_chance": 0.3, "spite_chance_lord": 0.5, "spite_aim": 0.75, "spite_hold": 2.0,
                   # Paying to pass when silver and bank fall short: Madam Wu covers the rest for this fee.
                   "wu_fee": 0.10,
                   # The enemy answers the bosun at the key moments (Admiral Li Yue for her war junks,
                   # Madam Shek Yu-lan for the pirate junks), from her own lines, battle.foe.*.
                   "foe_voice": True,
                   # Matched fights (engine.Game._muster): the enemy is sized from the house's own fleet.
                   # Their hull = our firepower x match_rounds; their guns = our hull x match / match_rounds.
                   # match (1 = an even fight) = base + cargo x temptation + fame x fame share
                   #   - standing x (standing in the port ahead - 50) / 50 + noise, held between min and max.
                   "match": True, "match_rounds_min": 2.5, "match_rounds_max": 4.5, "match_base": 0.55,
                   "match_cargo": 0.3, "match_fame": 0.2, "match_standing": 0.1, "match_spread": 0.1,
                   "match_min": 0.3, "match_max": 1.5, "match_lord": 0.15, "match_escort_share": 0.5, "match_cargo_ref": 100000,
                   "match_ships_min": 2, "match_ships_max": 24, "match_lord_ships_max": 30, "match_size_swing": 0.3,
                   "match_v2": False,
                   "match_hp_min": 4, "match_hp_max": 12, "match_flag": 2.0,
                   # How keen they are to attack at all: allure = base + cargo x temptation + fame x fame share.
                   "allure_base": 0.6, "allure_cargo": 0.6, "allure_fame": 0.3, "match_booty": 0.8,
                   # Rich houses draw the big fleets (Game 3 review, 19 Nov 2026). worth share = net worth /
                   # (net worth + worth_ref). It adds match_worth to the match (their guns), match_worth_rounds
                   # to the rounds their hull lasts, allure_worth to their keenness to attack, and lord_worth
                   # times it to the chance of meeting the pirate queen.
                   "worth_ref": 5000000, "match_worth": 0.3, "match_worth_rounds": 1.0,
                   "allure_worth": 0.4, "lord_worth": 1.0,
                   # Fame at sea: gained by winning, fades each month; fame_ref of it counts as full fame.
                   "fame_win": 1.0, "fame_broke_off": 0.5, "fame_decay": 0.1, "fame_ref": 10,
                   # Formation: escorts in the van, merchantmen in the line, cargo ships in the rear.
                   "focus": 0.3, "van_weight": 4, "line_weight": 3, "rear_weight": 3, "rear_cover": 0.85,
                   "cargo_spill": 1.0,
                   # They misjudge the hold (engine.Game._lowball): chance x (1 + dense x the share of the cargo's
                   # value in lowball_goods) x (1 - fame x fame share). They then price the cargo at lowball_min to
                   # lowball_max of its worth. Refused, they see the hold and ask the full price once before fighting.
                   "lowball": True, "lowball_chance": 0.15, "lowball_dense": 1.0, "lowball_fame": 0.7,
                   "lowball_min": 0.1, "lowball_max": 0.3, "lowball_goods": ["gold", "opium"],
                   # Prize cargo from a won fight (engine.Game._battle_prize): a tier by weight, then that many
                   # kinds of goods. Scraps are a few units each; the others are a value in silver per enemy
                   # junk (grown like booty) shared among the goods. Only what fits in the hold is taken.
                   "prize": True, "prize_lord_step": 1,
                   "prize_tiers": {
                       "scraps": {"weight": 40, "goods_min": 1, "goods_max": 1, "units_min": 1, "units_max": 6},
                       "modest": {"weight": 35, "goods_min": 2, "goods_max": 3, "value_min": 150, "value_max": 400},
                       "rich":   {"weight": 18, "goods_min": 3, "goods_max": 5, "value_min": 400, "value_max": 1000},
                       "haul":   {"weight": 7, "goods_min": 5, "goods_max": 8, "value_min": 1000, "value_max": 2500}}},
        # The mayor's harbour dues, paid on leaving port (engine.Game.dues).
        "dues": {"anchorage": 10, "tonnage": 5, "repair_share": 0.05, "yard_share": 0.03,
                 "bank_share": 0.01, "loan_share": 0.01, "warehouse": 2, "rep_discount": 0.2, "debt_relief": 0.25,
                 # Slipping out at night (owner's decisions, 19 Nov 2026; engine.Game.slip_odds / _depart).
                 # Caught: slip_base + slip_per_ship a ship (at most slip_ship_max), then the standing band
                 # there moves it by slip_<band>, kept between slip_min and slip_max.
                 "slip_base": 0.25, "slip_per_ship": 0.03, "slip_ship_max": 0.60,
                 "slip_hostile": 0.10, "slip_cool": 0.05, "slip_neutral": 0.0, "slip_warm": -0.05, "slip_favoured": -0.10,
                 "slip_min": 0.10, "slip_max": 0.70,
                 # The fine: the larger of slip_mult x the bill, or net worth x a roll between the band's
                 # slip_floor_<band>_lo and _hi (half the desk's floors), set by the band after the fall.
                 "slip_mult": 2.0,
                 "slip_floor_hostile_lo": 0.02, "slip_floor_hostile_hi": 0.05,
                 "slip_floor_cool_lo": 0.01, "slip_floor_cool_hi": 0.025,
                 "slip_floor_neutral_lo": 0.005, "slip_floor_neutral_hi": 0.0125,
                 "slip_floor_warm_lo": 0.0025, "slip_floor_warm_hi": 0.0075,
                 "slip_floor_favoured_lo": 0.001, "slip_floor_favoured_hi": 0.005,
                 # Standing: slip_rep x the band's penalty roll, and the same region hears its share.
                 "slip_rep": 10, "slip_travel": True,
                 # The Mayor's share of profit made selling cargo in her port this visit (engine.Game.profit_share).
                 "profit_enabled": True, "profit_rate_min": 0.015, "profit_rate_max": 0.035, "profit_free": 10000,
                 "profit_margin_floor": 0.25, "profit_margin_full": 1.0, "profit_margin_top": 2.0,
                 "profit_top_mult": 1.5, "profit_rep_cut": 0.5},
        # The Mayor's Parlour: a purse of silver for standing in that port (engine.Game.gift_quote).
        # Standing gained = cap x (1 - e^(-gift / appetite)) x headroom, once per visit. Appetite is
        # appetite x the port's harbour dues level; headroom is 1 up to soft_from, falling to 0 at 100.
        "gift": {"enabled": True, "cap": 15, "appetite": 1500, "soft_from": 50, "min_gift": 100,
                 "max_x": 5, "step": 50, "gracious_at": 3, "warm_at": 7, "delighted_at": 11,
                 "greet_cold_below": 40, "greet_warm_from": 70},
        # The Registrar (Mrs. Evelyn Marlowe, cast key "taxlady"), found only in a captain's own home port:
        # she meets the house when it comes home and gives one fresh price from her register
        # (engine.Game.registrar_here, _registrar_tip).
        # Hot tips (engine _hot_tip): a boom the giver knows is coming, in a cargo cheap where it is told,
        # booked into the market so it really lands. The Registrar gives one on hot_home_chance of
        # homecomings (otherwise her price tip); any other port's officer on hot_away_chance of arrivals.
        # Never two at once per house: none while a tip is still to come or still running.
        # Late game (19 Nov 2026): port shares and the great house at home. Shares: a pool per port
        # shared by every house; each share held cuts the Port Authority tax there by share_cut; the
        # biggest holder is Patron of the port. They count in net worth at what was paid.
        # The great house: three stages bought in turn at the home port; each raises home standing
        # once (house_rep_N) and cuts the chance of being robbed ashore at home (house_rob_N).
        "estates": {"shares_enabled": True, "shares_per_port": 10, "share_cut": 0.10,
                    "share_price_per_pct": 100000, "share_price_min": 150000, "share_price_max": 400000,
                    "share_sell_back": True,
                    # Captain's share allowance (19 Nov 2026): shares are earned, not bought. One free share
                    # for each rank climbed above Clerk (shares_per_rank) and later from special awards; at
                    # most shares_per_house in all, placed in any port. shares_buy brings back the silver sale.
                    "shares_per_house": 10, "shares_per_rank": 1, "shares_buy": False,
                    "house_enabled": True,
                    "house_cost_1": 500000, "house_cost_2": 2000000, "house_cost_3": 6000000,
                    "house_rep_1": 5, "house_rep_2": 8, "house_rep_3": 12,
                    "house_rob_1": 0.3, "house_rob_2": 0.6, "house_rob_3": 0.9,
                    # Selling back (19 Nov 2026): the top stage of the great house can be sold at home for
                    # house_sell_back of what was paid for it. Its standing and robbery cut go with it.
                    "house_sell": True, "house_sell_back": 0.5,
                    # Prices that grow with the house (Game 3 review, 19 Nov 2026): shares, the great house and
                    # the Mayor's fees are multiplied by the square root of (net worth / wealth_ref), at least
                    # 1 and at most wealth_max. Each December the great house costs house_upkeep of what was
                    # paid for it, and each port where the house is Patron costs patron_upkeep of its shares.
                    "wealth_scale": True, "wealth_ref": 1000000, "wealth_max": 10.0,
                    "house_upkeep": 0.06, "patron_upkeep": 0.05},
        # The Mayor's commissions (late game, 19 Nov 2026): the home Mayor offers one yearly goal and one
        # short contract at a time. Kinds: deliveries, supply runs to a port short of a cargo, and
        # standing goals. Paid in silver and home standing; a missed one is only a missed chance.
        "contracts": {"enabled": True, "short_min": 3, "short_max": 5, "supply_months": 3, "offer_months": 3,
                      "hold_share_short": 0.35, "hold_share_year": 1.0, "min_qty": 10,
                      "fee_share": 0.25, "fee_share_year": 0.35, "supply_mult": 1.5, "shortage_at": 1.35,
                      "standing_short": 10, "standing_year": 25, "standing_fee": 0.0015,
                      "rep_short": 3, "rep_year": 8, "fee_wealth": True},
        # Under the Counter (counter.py, 20 Nov 2026): the port's tax lady sells a tip. Her price is a share
        # of the tip's worth, from fee_min at the lowest rank to fee_max at the top.
        "counter": {"enabled": True, "fee_min": 0.10, "fee_max": 0.30, "fee_floor": 25, "min_worth": 150,
                    "risk_loss": 0.4},
        "registrar": {"enabled": True, "stale_months": 2, "held_first": True,
                      "hot_enabled": True, "hot_home_chance": 0.25, "hot_away_chance": 0.1,
                      "hot_every": 3, "hot_lead": 1, "hot_months": 2, "hot_hold": True,
                      "hot_months_min": 1, "hot_months_max": 3, "hot_after_max": 1.5,
                      "hot_min": 3.0, "hot_max": 6.0},
        # The Port Authority: each port's tax officer takes a cut of the cargo's declared value on
        # arrival, or buys it at that value, or catches the lie (engine.Game, "port authority").
        # Each port's base rate, officer and mood are in the Ports table.
        "customs": {"enabled": True, "home_free": True, "spot_home": 0.05, "spot_shares": 0.05, "bond": True, "drift": 0.005, "range": 0.0125, "min_rate": 0.0, "max_rate": 0.5,
                    "buy_base": 0.003, "buy_k": 0.3, "buy_exp": 1.8, "buy_cap": 0.9,
                    "audit_base": 0.006, "audit_k": 0.12, "audit_cap": 0.9,
                    "appetite_power": 1.0, "greed_weight": 0.08, "cunning_weight": 0.08, "rep_audit": 0.8, "rep_buy": 0.6,
                    "mood_swing": 0.15, "fine_mult": 2.0, "caught_rep": 6,
                    "strongbox": 9000, "strongbox_swing": 0.4, "buyback_premium": 0.25,
                    "bribe_share": 0.3, "bribe_min": 50, "bribe_cut": 0.5, "bribe_honest": 0.25,
                    "bribe_refused_mult": 1.5, "bribe_rep": 8, "over_rep": 5, "max_declare": 1.5,
                    "pay_less_lo": 0.7, "pay_less_hi": 0.95, "pay_more_share": 1.1,
                    "tell_curious": 0.08, "tell_hungry": 0.25, "seeded": [],
                    "greet_aloud_min": 2, "greet_aloud_max": 4},
        # Reputation swings (owner's decisions, 19 Nov 2026; project doc "SeaTrader Reputation Swings").
        # Standing in each port falls in five bands of 20 (Hostile 0-19, Cool 20-39, Neutral 40-59,
        # Warm 60-79, Favoured 80-100). Every penalty or reward below is multiplied by a fresh roll from
        # the band the house is in there: <band>_pen_lo..hi for losses, <band>_rew_lo..hi for gains.
        "standing": {"enabled": True,
                     "hostile_pen_lo": 2.0, "hostile_pen_hi": 6.0, "hostile_rew_lo": 0.2, "hostile_rew_hi": 0.6,
                     "cool_pen_lo": 1.3, "cool_pen_hi": 3.0, "cool_rew_lo": 0.5, "cool_rew_hi": 1.0,
                     "neutral_pen_lo": 0.7, "neutral_pen_hi": 1.5, "neutral_rew_lo": 0.7, "neutral_rew_hi": 1.4,
                     "warm_pen_lo": 0.5, "warm_pen_hi": 1.0, "warm_rew_lo": 1.0, "warm_rew_hi": 1.8,
                     "favoured_pen_lo": 0.2, "favoured_pen_hi": 0.8, "favoured_rew_lo": 1.2, "favoured_rew_hi": 2.5,
                     # Caught lying at the Port Authority desk (decision 1): base + lie x the share of the
                     # hold's value hidden, varied by caught_vary either way (its own roll, not the band's).
                     "caught_base": 12, "caught_lie": 25, "caught_vary": 0.3,
                     # Word travels (decision 3): other ports in the same region lose this share of the hit.
                     "region_share": 0.333,
                     # The fine (decision 2), set by the band the house lands in after the fall: the larger
                     # of fine_hidden x the hidden value x the band's penalty roll, or net worth x a roll
                     # between the band's floor_lo and floor_hi.
                     "fine_hidden": 0.5,
                     "hostile_floor_lo": 0.04, "hostile_floor_hi": 0.10, "cool_floor_lo": 0.02, "cool_floor_hi": 0.05,
                     "neutral_floor_lo": 0.01, "neutral_floor_hi": 0.025, "warm_floor_lo": 0.005, "warm_floor_hi": 0.015,
                     "favoured_floor_lo": 0.0025, "favoured_floor_hi": 0.01,
                     # Trading (decision 5): only good business earns standing (a sale at a profit, a cargo
                     # sold where it is short, bought where it is in glut), at most trade_cap a visit.
                     "trade_cap": 4, "short_at": 1.3, "glut_at": 0.75,
                     # Drift (decision 6, changed to 0.5 after the 10-year simulations): points a month every
                     # port moves back toward 50. At 2 standing sat in Neutral nine months in ten.
                     "drift": 0.5,
                     # Losses (decision 7), each times the band's penalty roll.
                     "seized": 20, "dues_short": 3, "collect_home": 3, "collect_away": 1,
                     "bankrupt_home": 30, "bankrupt_away": 10, "beaten": 3, "dump": 2, "dump_below": 0.6,
                     "contract_missed": 2,
                     # Gains (decision 8), each times the band's reward roll. Pay More is declaring
                     # pay_more_at or more of the true worth; each honest desk in a row after the first adds
                     # honest_run, up to honest_run_max.
                     "pay_correct": 1, "pay_more": 3, "pay_more_at": 1.1, "honest_run": 0.5, "honest_run_max": 2,
                     "pirates_beaten": 3, "debt_cleared": 3, "debt_cleared_min": 1000,
                     # Hostile and Cool ports (decision 9).
                     "hostile_audit": 2.0, "cool_audit": 1.4, "hostile_margin": 0.04, "cool_margin": 0.02,
                     "hostile_yard": 0.25, "cool_yard": 0.10, "hostile_match": 0.15, "cool_match": 0.07,
                     # Warm and Favoured ports (decision 10).
                     "warm_tax_cut": 0.15, "favoured_tax_cut": 0.30, "favoured_match": 0.15, "favoured_avoid": 0.25,
                     "lot_chance": 0.3, "lot_depth": 0.15, "lot_discount": 0.15, "lot_discount_max": 0.5},
    },
    # base = typical price; vol = monthly volatility; depth = units that move the price ~25%.
    "goods": {
        "opium":     {"name": "Opium", "family_name": "Fireworks", "base": 4200, "vol": 0.16, "depth": 600, "contraband": True, "ban_odds": 0.0},
        # Gold is legal, but a port's ban sometimes covers bullion too (ban_odds).
        "gold":      {"name": "Gold", "family_name": "", "base": 2400, "vol": 0.05, "depth": 900, "contraband": False, "ban_odds": 0.5},
        "silk":      {"name": "Silk", "family_name": "", "base": 520, "vol": 0.10, "depth": 1200, "contraband": False, "ban_odds": 0.0},
        "porcelain": {"name": "Porcelain", "family_name": "", "base": 230, "vol": 0.08, "depth": 1500, "contraband": False, "ban_odds": 0.0},
        "arms":      {"name": "Arms", "family_name": "Ironware", "base": 160, "vol": 0.10, "depth": 1500, "contraband": False, "ban_odds": 0.0},
        "spices":    {"name": "Spices", "family_name": "", "base": 95, "vol": 0.09, "depth": 1800, "contraband": False, "ban_odds": 0.0},
        "tea":       {"name": "Tea", "family_name": "", "base": 70, "vol": 0.08, "depth": 2000, "contraband": False, "ban_odds": 0.0},
        "rice":      {"name": "Rice", "family_name": "", "base": 14, "vol": 0.07, "depth": 3000, "contraband": False, "ban_odds": 0.0},
        "general":   {"name": "General Cargo", "family_name": "", "base": 9, "vol": 0.07, "depth": 3000, "contraband": False, "ban_odds": 0.0},
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
        "hongkong":  {"name": "Hong Kong", "lon": 114.2, "lat": 22.3, "region": "china", "bank": True, "warehouse": True, "shipyard": True, "no_ban": False, "label_left": True, "dues": 1.0, "tax_rate": 0.02, "officer": "officer_hongkong", "mood": 0.15, "purse": 1.4,
                      "mods": {"arms": 0.8, "tea": 0.9, "general": 0.85, "gold": 1.05}},
        "shanghai":  {"name": "Shanghai", "lon": 121.5, "lat": 31.2, "region": "north", "bank": True, "warehouse": True, "shipyard": True, "no_ban": False, "label_left": True, "dues": 1.2, "tax_rate": 0.03, "officer": "officer_shanghai", "mood": 0.15, "purse": 1.3,
                      "mods": {"silk": 0.6, "tea": 0.6, "opium": 1.35, "arms": 1.3, "spices": 1.3, "gold": 1.15}},
        "nagasaki":  {"name": "Nagasaki", "lon": 129.9, "lat": 32.75, "region": "north", "bank": False, "warehouse": False, "shipyard": False, "no_ban": False, "label_left": True, "dues": 1.4, "tax_rate": 0.025, "officer": "officer_nagasaki", "mood": 0.1, "purse": 0.8,
                      "mods": {"porcelain": 0.6, "silk": 0.85, "arms": 1.5, "spices": 1.4, "rice": 1.3, "opium": 1.2, "gold": 0.55}},
        "manila":    {"name": "Manila", "lon": 121.0, "lat": 14.6, "region": "china", "bank": False, "warehouse": False, "shipyard": False, "no_ban": False, "label_left": False, "dues": 0.8, "tax_rate": 0.015, "officer": "officer_manila", "mood": 0.15, "purse": 0.9,
                      "mods": {"general": 0.75, "rice": 0.9, "spices": 0.9, "silk": 1.3, "porcelain": 1.3, "tea": 1.2, "gold": 0.85}},
        "foochow":   {"name": "Foochow", "lon": 119.3, "lat": 26.1, "region": "china", "bank": False, "warehouse": False, "shipyard": False, "no_ban": False, "label_left": True, "dues": 1.0, "tax_rate": 0.025, "officer": "officer_foochow", "mood": 0.15, "purse": 0.9,
                      "mods": {"tea": 0.5, "porcelain": 0.85, "opium": 1.3, "arms": 1.25, "spices": 1.2, "rice": 1.15, "general": 1.1}},
        "saigon":    {"name": "Saigon", "lon": 106.7, "lat": 10.8, "region": "china", "bank": False, "warehouse": False, "shipyard": False, "no_ban": False, "label_left": False, "dues": 0.9, "tax_rate": 0.02, "officer": "officer_saigon", "mood": 0.5, "purse": 0.8,
                      "mods": {"rice": 0.55, "spices": 0.85, "arms": 1.3, "porcelain": 1.25, "general": 1.2}},
        "bangkok":   {"name": "Bangkok", "lon": 100.5, "lat": 13.75, "region": "south", "bank": False, "warehouse": False, "shipyard": False, "no_ban": False, "label_left": True, "dues": 0.7, "tax_rate": 0.03, "officer": "officer_bangkok", "mood": 0.12, "purse": 0.9,
                      "mods": {"rice": 0.6, "spices": 0.8, "silk": 1.25, "arms": 1.2, "tea": 1.2, "gold": 1.2}},
        "singapore": {"name": "Singapore", "lon": 103.8, "lat": 1.35, "region": "south", "bank": True, "warehouse": True, "shipyard": True, "no_ban": False, "label_left": True, "dues": 0.6, "tax_rate": 0.01, "officer": "officer_singapore", "mood": 0.1, "purse": 1.2,
                      "mods": {"arms": 0.85, "general": 0.8, "opium": 0.85, "tea": 1.4, "silk": 1.35, "porcelain": 1.3}},
        "batavia":   {"name": "Batavia", "lon": 106.8, "lat": -6.2, "region": "south", "bank": False, "warehouse": False, "shipyard": False, "no_ban": False, "label_left": False, "dues": 1.1, "tax_rate": 0.035, "officer": "officer_batavia", "mood": 0.1, "purse": 1.0,
                      "mods": {"spices": 0.5, "rice": 1.2, "tea": 1.3, "silk": 1.4, "arms": 1.25, "porcelain": 1.35, "general": 1.3}},
        "calcutta":  {"name": "Calcutta", "lon": 88.4, "lat": 22.6, "region": "bengal", "bank": True, "warehouse": True, "shipyard": True, "no_ban": True, "label_left": False, "dues": 1.3, "tax_rate": 0.045, "officer": "officer_calcutta", "mood": 0.2, "purse": 1.2,
                      "mods": {"opium": 0.55, "tea": 0.8, "general": 0.9, "rice": 0.9, "silk": 1.3, "spices": 1.3, "porcelain": 1.5, "gold": 1.35}},
    },
    # hold = cargo units; hull = damage it can take; slots = guns it can mount (a cannon takes
    # rules.fleet.cannon_slots of them); cannons = whether her deck can carry cannons at all.
    "ships": {
        "junk":     {"name": "Junk", "hold": 60, "hull": 100, "slots": 4, "price": 3000, "fast": False, "cannons": False},
        "lorcha":   {"name": "Lorcha", "hold": 120, "hull": 140, "slots": 8, "price": 9000, "fast": False, "cannons": False},
        "barque":   {"name": "Barque", "hold": 250, "hull": 200, "slots": 12, "price": 22000, "fast": False, "cannons": True},
        "clipper":  {"name": "Clipper", "hold": 180, "hull": 160, "slots": 10, "price": 35000, "fast": True, "cannons": False},
        "indiaman": {"name": "East Indiaman", "hold": 500, "hull": 320, "slots": 24, "price": 80000, "fast": False, "cannons": True},
        # Escort: a hired war steamer like the paddle gunboats that convoyed the China coast in the 1850s
        # and 60s. Guns only, no hold; sails in the van and takes the enemy's fire.
        "gunboat":  {"name": "Paddle Gunboat", "hold": 0, "hull": 500, "slots": 12, "price": 65000, "fast": False, "cannons": True,
                     "role": "escort"},
        # Cargo ship: a big teak-built Indian "country ship" of the India-China trade. Hold only, no guns;
        # sails in the rear behind the escorts. Every hit on her sends cargo to the bottom.
        "countryship": {"name": "Country Ship", "hold": 750, "hull": 200, "slots": 0, "price": 120000, "fast": False,
                        "cannons": False, "role": "cargo"},
        # The flagship (late game, 19 Nov 2026): one per house, outside the class limits. A big hold
        # and heavy guns; pirates think twice (rules.fleet.flagship_deter); she always sinks last.
        "flagship": {"name": "Flagship", "hold": 1500, "hull": 900, "slots": 48, "price": 2500000, "fast": False,
                     "cannons": True, "role": "flagship"},
    },
    "ship_names": ["Morning Cloud", "Jade Heron", "Lucky Star", "Sea Witch", "Golden Carp", "Lady Hughes",
                   "Red Rover", "Water Dragon", "Flying Cloud", "Pearl of Canton", "Falcon", "Nemesis",
                   "Lotus Wind", "Black Joke", "Sylph", "Cowasjee", "Ariel", "Taeping", "Fiery Cross",
                   "Mandarin", "Eastern Queen", "Kestrel", "Tiger Tail", "Silver Moon", "Antelope"],
    # Escorts (guns only) and cargo ships (hold only) each have their own list; ship_names above is
    # the Merchantmen's. An empty or used-up list falls back to the Merchantmen's names.
    "escort_names": ["Iron Maiden", "Hellcat", "Valkyrie", "Fury", "Vixen", "Medusa", "Gorgon", "Banshee",
                     "Firebrand", "Lady Vengeance", "Scarlet Fang", "Widow's Wrath", "Steel Siren", "Harpy",
                     "Thunder Queen", "Brimstone Belle", "Tempest", "Red Fury", "Cutthroat Kate", "Bloody Mary"],
    "cargo_names": ["Golden Hoard", "Silk Purse", "Treasure Chest", "Rich Widow", "Dowager Empress", "Laden Lady",
                    "Cornucopia", "Bountiful", "Ample Grace", "Spice Queen", "Tea Duchess", "Bengal Matron",
                    "Bombay Belle", "Coromandel Countess", "Golden Fleece", "Deep Pockets", "Fat Purse",
                    "Heavy Heart", "Plenty", "Big Bertha"],
    # NSFW name lists (19 Nov 2026): used instead of the three lists above while the content rating is
    # not family-friendly. Each ship also keeps a clean name, shown whenever family-friendly is on
    # (for the whole table, or one screen from Captain's Options).
    "nsfw_ship_names": ["Saucy Wench", "Loose Lips", "Naughty Nell", "Bawdy Bess", "Wet Dream", "Busty Mermaid",
                        "Hussy's Hold", "Lusty Lotus", "Strumpet", "Brazen Hussy", "Moist Maiden", "Bare Bodice",
                        "Easy Virtue", "Wandering Hands", "Siren's Cleavage", "Jade's Bosom", "Spread Sails",
                        "Tight Rigging", "Ample Bosom", "Rogering Rose", "Night Caller", "Madam's Garter",
                        "Velvet Thighs", "Peekaboo Petticoat", "Booty Call"],
    "nsfw_escort_names": ["Sea Slut", "Ball Buster", "Nut Cracker", "Spanking Sally", "Whip Mistress",
                          "Leather Lass", "Dominatrix", "Bad Bitch", "Cock Blocker", "Stiff Broadside",
                          "Long Gun Lil", "Grabby Gretchen", "Thrusting Thalia", "Hard Ram", "Mean Mistress",
                          "Cat o' Nine Tails", "Hot Shot Hattie", "Pounding Polly", "Rough Rider",
                          "Bitch of Batavia"],
    "nsfw_cargo_names": ["Big Booty", "Wide Load", "Junk in the Trunk", "Ample Bottom", "Bottomless Betty",
                         "Loose Hold", "Stuffed Stockings", "Full Bodice", "Heavy Bosom", "Bounteous Booty",
                         "Overstuffed Corset", "Hot Bottom", "Ripe Melons", "Lady Cushions", "Back Door Betty",
                         "Packed Petticoats", "Plump Rump", "Thick Thighs", "Generous Hold", "Bustle Bertha"],
    # How much history to keep (Admin > Captain's Report). See journal.py.
    "journal": {"keep_games": 50, "server_days": 30},
    # Who reads the game aloud, and how (Admin > Cast & Voices). See cast.py.
    "characters": copy.deepcopy(cast.CHARACTERS),
    "voice": copy.deepcopy(cast.VOICE_DEFAULTS),
}

# The three classes of ship (Ships > Class): merchantmen carry cargo and guns, escorts guns only,
# cargo ships cargo only. SEEDED_SHIPS join saved settings once (see validate).
SHIP_ROLES = ("trader", "escort", "cargo", "flagship")
# Market depths shipped before 19 Nov 2026 (see the depth_v2 upgrade in normalise).
OLD_DEPTHS = {"opium": 60, "gold": 90, "silk": 160, "porcelain": 250, "arms": 250, "spices": 450, "tea": 500,
              "rice": 1200, "general": 1200}

SEEDED_SHIPS = ("gunboat", "countryship", "flagship")
# Game 3 review (19 Nov 2026): the swingiest cargoes are calmed once to at most these monthly swings.
CALM_VOLS = {"porcelain": 0.2, "tea": 0.3, "silk": 0.2}

# Paths whose whole value is replaced on save (rows can be deleted), not merged.
WHOLE = ("goods", "ports", "ships", "regions", "ranks", "ship_names", "escort_names", "cargo_names",
         "nsfw_ship_names", "nsfw_escort_names", "nsfw_cargo_names", "difficulty.presets",
         "theme.player_colors", "rules.game.lengths", "rules.events.shock_mults",
         "rules.weather.storm_chance", "rules.storm.base", "graphics.goods", "graphics.ports", "graphics.ships",
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
             F("brand.title_a", "Title, first part", "text", "First word of the game's name, shown as the logo on every screen.", max=24),
             F("brand.title_b", "Title, second part", "text", "Second word of the game's name. Both parts make the logo, in the gilded Ceremony Title lettering.", max=24),
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
                      C("jail", "Jail", "num", "Multiplies every chance of being locked up and how much the crew "
                        "drinks while the captain is inside.", min=0, max=5, step=0.05, default=1.0),
                      C("customs_view", "Port Authority odds shown", "select",
                        "What a captain sees while declaring cargo: the exact chances, a coloured bar without numbers, "
                        "or only the officer's face and manner.", default="bar",
                        options=[["exact", "Exact percentages"], ["bar", "Bar and her tell"], ["tell", "Her tell only"]]),
                      C("battle_view", "Sea battle odds shown", "select",
                        "What a captain sees on the battle buttons: the exact chances, a coloured bar without numbers, "
                        "or only the bosun's manner.", default="bar",
                        options=[["exact", "Exact chances"], ["bar", "Bar and her manner"], ["tell", "Her manner only"]])]},
         {"path": "ranks", "title": "Player ranks", "kind": "list",
          "help": "Captains receive their highest qualifying promotion at Home Port. Keep each badge ID the same when renaming its title.",
          "columns": [C("worth", "Net worth from", "int", min=-10**12, max=10**12),
                      C("title", "Title", "text", max=30),
                      C("id", "Badge ID", "text", "Leave blank to create an ID from the title.", max=48),
                      C("scales", "Grows with game length", "bool",
                        "On: the worth is for a game of the 'Ranks are set for' length (Game Setup) and is scaled to "
                        "each game's length, so a 5-year game halves it. Off: the same worth in every game.")]},
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
             F("rules.game.rank_years", "Ranks are set for a game of (years)", "int",
               "The top ranks marked 'Grows with game length' (Ratings > Player ranks) are worth their listed "
               "amount in a game this long, and scale with each game's length.", min=1, max=50),
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
         {"title": "Jail", "fields": [
             F("rules.jail.enabled", "Captains can be jailed", "bool", "Locked up for 1 or 3 months: the fleet waits at "
               "anchor, the House is marked as sailed every month, the crew drinks the silver aboard and perishable "
               "cargo spoils. No early way out. Every chance is multiplied by the difficulty level's Jail setting."),
             F("rules.jail.arrest_months", "Months for an arrest", "int", min=1, max=12),
             F("rules.jail.max_months", "Sentences add up to at most (months)", "int", min=1, max=36),
             F("rules.jail.arrest_standing", "Arrested on arrival at or below this standing", "num", min=0, max=100, step=1),
             F("rules.jail.hostile_below", "A Hostile port is below this standing", "num", min=0, max=100, step=1),
             _pct("rules.jail.hostile_chance", "Chance of arrest on arriving in a Hostile port"),
             _pct("rules.jail.contraband_chance", "Chance of jail when contraband is seized"),
             F("rules.jail.contraband_low_rep", "Below this standing...", "num", min=0, max=100, step=1),
             F("rules.jail.contraband_low_mult", "...that chance is multiplied by", "num", min=0, max=10, step=0.1),
             _pct("rules.jail.slip_chance", "Chance the Mayor locks up a captain caught slipping out (first time)"),
             _pct("rules.jail.slip_repeat", "...plus this for each earlier catch in that port",
                  "Catches in the same port within the months below. The Mayor remembers your face."),
             F("rules.jail.slip_repeat_months", "...counting catches within (months)", "int", min=1, max=600),
             _pct("rules.jail.slip_jail_max", "...but never more than"),
             _pct("rules.jail.collectors_chance", "Chance of debtors' prison when the collectors call past the debt cap"),
             F("rules.jail.bankrupt_months", "Months of debtors' prison on bankruptcy", "int", min=0, max=36),
             F("rules.jail.plea", "Big fines may be swapped for time (the plea)", "bool"),
             _pct("rules.jail.big_share", "A fine is big above this share of net worth", "Or when it is more than "
                  "silver plus bank."),
             F("rules.jail.big_min", "...and at least", "int", min=0, max=10**9),
             _pct("rules.jail.plea1_min", "1 month: still pay, least"),
             _pct("rules.jail.plea1_max", "1 month: still pay, most"),
             _pct("rules.jail.plea3_min", "3 months: still pay, least"),
             _pct("rules.jail.plea3_max", "3 months: still pay, most"),
             _pct("rules.jail.drink_min", "Each month inside the crew drinks, least", "A share of the silver aboard. "
                  "Banked silver is safe."),
             _pct("rules.jail.drink_max", "Each month inside the crew drinks, most"),
             _pct("rules.jail.spoil_min", "Perishable cargo spoils each month, least"),
             _pct("rules.jail.spoil_max", "Perishable cargo spoils each month, most"),
             F("rules.jail.perishables", "Perishable cargo", "lines", "Cargo keys, one per line.", max=20),
             F("rules.jail.release_floor", "Standing in the jail port on release, at least", "num", min=0, max=100, step=1)]},
         {"title": "Crew hides a share (before it is taken)", "fields": [
             F("rules.hide.enabled", "The crew hides a share", "bool", "Whenever cargo or silver is about to be "
               "taken, the crew always gets a random share of it out of sight first. It stays aboard."),
             _pct("rules.hide.min", "Share hidden, least"),
             _pct("rules.hide.max", "Share hidden, most"),
             F("rules.hide.dear_goods", "Goods small and dear enough to hide better", "lines",
               "Cargo keys, one per line (gold, opium).", max=20),
             F("rules.hide.dear_mult", "They hide this many times as well", "num", "1.5 turns 10-30% into "
               "15-45%. Never more than all of it.", min=1, max=10, step=0.1),
             F("rules.hide.customs", "From customs seizing contraband", "bool"),
             F("rules.hide.desk", "From the Port Authority buying cargo out", "bool"),
             F("rules.hide.pirates", "From pirates plundering the hold", "bool"),
             F("rules.hide.bankrupt", "From the moneylender at bankruptcy (silver and cargo aboard)", "bool")]},
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
             _pct("rules.market.own_fade", "Share of a trade's own price move gone by next month",
                  "A big buy or sale moves the port's price; this much of that move fades the month after "
                  "and the rest the month after that. The usual pull back works on top.", 0, 1),
             F("rules.market.floor", "Lowest price (x usual)", "num", min=0.01, max=1, step=0.01),
             F("rules.market.ceiling", "Highest price (x usual)", "num", min=1, max=50, step=0.1),
             _pct("rules.market.start_spread", "Random spread of opening prices", "", 0, 0.9),
             F("rules.market.rep_per_value", "Trade value that earns 1 standing", "int", min=1, max=10**9),
             F("rules.market.rep_trade_cap", "Most standing from one trade", "num", min=0, max=100, step=0.5),
             _pct("rules.market.worth_cargo", "Cargo's share counted in net worth", "", 0, 2),
             F("rules.market.avg_amber", "Trade bar turns amber at (x posted)", "num",
               "The average price per unit of a buy, against the posted price. Sales use the same line upside down.",
               min=1, max=20, step=0.1),
             F("rules.market.avg_red", "Trade bar turns red at (x posted)", "num", min=1, max=50, step=0.1)]},
         {"title": "Wild cargoes (Maijiuana)", "fields": [
             F("rules.market.wild_goods", "Wild cargoes", "lines",
               "Cargo keys, one per line. Maijiuana is porcelain under its NSFW name. Their prices run in trends "
               "and swing far wider than the rest. No News and no arrow give a run away.", max=20),
             _pct("rules.market.wild_vol", "Wild cargo: monthly swing", "", 0, 2),
             _pct("rules.market.wild_reversion", "Wild cargo: monthly pull back to the usual price", "", 0, 1),
             F("rules.market.wild_floor", "Wild cargo: lowest price (x usual)", "num", min=0.01, max=1, step=0.01),
             F("rules.market.wild_ceiling", "Wild cargo: highest price (x usual)", "num", min=1, max=50, step=0.1),
             _pct("rules.market.runs_chance", "Chance a port starts a run each month",
                  "For each wild cargo in each port with no run going."),
             F("rules.market.runs_min", "A run lasts at least (months)", "int", min=1, max=24),
             F("rules.market.runs_max", "A run lasts at most (months)", "int", min=1, max=24),
             _pct("rules.market.runs_drift_min", "A run moves the price each month, least", "", 0, 2),
             _pct("rules.market.runs_drift_max", "A run moves the price each month, most", "", 0, 2)]},
         {"title": "The dealers' purse", "fields": [
             F("rules.market.purse_enabled", "Dealers have only so much silver a month", "bool",
               "Each port's dealers can pay only so much for each cargo each month, so a huge hold has to be sold across "
               "several ports. Shared by every house; full again each month. Each port's size is in the Ports table."),
             F("rules.market.purse_depths", "Purse for each cargo (x its depth at its usual price)", "num",
               "0.75 with opium's depth of 600 at $8,000 is $3.6 million a month at a normal port. A boom drains it faster.",
               min=0.01, max=100, step=0.05),
             _pct("rules.market.purse_over", "Paid for silver asked past the purse",
                  "What the dealers pay, as a share of their price, for a sale that runs past their purse.")]},
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
             F("rules.bank.debt_rep_penalty", "Standing lost each time they call (Standing swings off)", "num", min=0, max=100, step=0.5),
             F("rules.bank.debt_cap_mult", "Debt cap: interest stops at (x the collectors' line)", "num",
               "Once the debt reaches this many times the collectors' line, no more interest is added (the debt "
               "is never reduced). 0 = no cap.", min=0, max=1000, step=0.5),
             F("rules.bank.bankrupt_enabled", "Bankruptcy", "bool",
               "On: a house worth less than nothing for the months below loses everything (ships, cargo, "
               "warehouses, depots, port shares, the great house), its debt is cleared, and it starts again at home "
               "with a sound junk (the shipwreck ship) and a stake. Ranks are kept."),
             F("rules.bank.bankrupt_months", "Bankruptcy after (months in a row worth less than nothing)", "int",
               min=1, max=600),
             F("rules.bank.bankrupt_warn", "Warn each month in the last (months)", "int",
               "Also warned in the first month under water.", min=0, max=600),
             F("rules.bank.bankrupt_stake", "Stake after bankruptcy (silver)", "int", min=0, max=10**9),
             F("rules.bank.bankrupt_rep", "Home standing lost on bankruptcy (Standing swings off)", "num", min=0, max=100, step=0.5),
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
             F("rules.fleet.max_fleet", "Most merchantmen in a fleet", "int",
               "Ships of the Merchantman class (Ships). Escorts and cargo ships have their own limits below.", min=1, max=20),
             F("rules.fleet.max_escorts", "Most escorts (guns only)", "int", min=0, max=20),
             F("rules.fleet.max_cargo", "Most cargo ships (hold only)", "int", min=0, max=20),
             F("rules.fleet.escort_unlock", "Merchantmen needed before a shipyard sells escorts", "int",
               "Counted when buying. Escorts already bought stay if merchantmen are lost.", min=0, max=20),
             F("rules.fleet.cargo_unlock", "Merchantmen needed before a shipyard sells cargo ships", "int", min=0, max=20),
             F("rules.fleet.flagship_unlock", "Merchantmen needed before a shipyard sells the flagship", "int",
               "The flagship is any ship type of class Flagship (Ships). A house may own one, outside the limits above; "
               "if she is sunk, a new one can be bought at full price.", min=0, max=20),
             _pct("rules.fleet.flagship_deter", "Flagship: fewer pirate attacks while she sails",
                  "40% means pirates (and the pirate queen's war junks) find the fleet 40% less often."),
             F("rules.fleet.keep_trader", "The last merchantman cannot be sold", "bool",
               "A fleet of only escorts or cargo ships cannot trade properly; keep one merchantman as the flagship."),
             F("rules.fleet.gun_price", "Price of a gun", "int", min=0, max=10**7),
             _pct("rules.fleet.gun_resale", "Gun's share of value when a ship is sold",
                  "Cannons sell back at the same share of their price."),
             F("rules.fleet.cannon_cost", "Price of a cannon, in guns", "num",
               "7.5 means a cannon costs seven and a half times the price of a gun.", min=0, max=1000, step=0.5),
             F("rules.fleet.cannon_power", "A cannon's firepower, in guns", "int",
               "Each cannon fires this many shots a round.", min=1, max=100),
             F("rules.fleet.cannon_slots", "Gun mounts a cannon takes", "int",
               "Only ships marked for cannons (Ships) can carry them.", min=1, max=20),
             F("rules.fleet.gun_hold", "Cargo space a gun takes (units)", "int",
               "Each gun mounted takes this much of her hold. 0 = guns take no cargo space.", min=0, max=10000),
             F("rules.fleet.cannon_hold", "Cargo space a cannon takes (units)", "int",
               "Each cannon mounted takes this much of her hold. A ship's hold never drops below 0.", min=0, max=10000),
             _pct("rules.fleet.ship_resale", "Ship resale value (sound hull)"),
             F("rules.fleet.warehouse_cap", "Warehouse space (units)", "int", min=0, max=10**8),
             F("rules.fleet.depot_open_cost", "Away warehouse: price to open", "int", min=0, max=10**9),
             F("rules.fleet.depot_cap", "Away warehouse: space when opened (units)", "int", min=0, max=10**8),
             F("rules.fleet.depot_expand_cost", "Away warehouse: price to enlarge", "int", min=0, max=10**9),
             F("rules.fleet.depot_expand_cap", "Away warehouse: space added each time (units)", "int", min=1, max=10**8),
             F("rules.fleet.ship_rep", "Standing gained by buying a ship", "num", min=0, max=100, step=0.5)]},
         {"title": "Crew wages and upkeep", "fields": [
             F("rules.fleet.upkeep_enabled", "Ships cost wages and upkeep every month", "bool",
               "Taken from silver aboard, then the bank; whatever is left goes on the debt. Shown in the accounts."),
             _pct("rules.fleet.upkeep_rate", "Each month, this share of each ship's price", "", 0, 1),
             F("rules.fleet.upkeep_gun", "Each month, for each gun or cannon", "num", min=0, max=100000, step=1),
             F("rules.fleet.upkeep_rank", "Wages rise by this much for each rank above the one below", "num",
               "A famous house's crews expect famous pay. 0.25 is a quarter more for each rank.", min=0, max=10, step=0.05),
             F("rules.fleet.upkeep_rank_from", "Wages start rising above this rank", "text", max=30),
             F("rules.fleet.flagship_wage", "The flagship's monthly wage (flat, before the rank rise)", "int",
               "Like a big merchantman's, not a share of her price.", min=0, max=10**8),
             _pct("rules.fleet.laid_up_wage", "A ship laid up at home pays this share of her wage"),
             F("rules.fleet.idle_note_min", "Note wages carried by empty hold from (silver a month)", "int",
               "The Captain's Log and the Port to-do list say how much of the month's wages carried empty space.",
               min=0, max=10**9),
             _pct("rules.fleet.idle_note_share", "... when at least this share of the hold is empty")]},
         {"title": "Crippled escorts", "fields": [
             _pct("rules.fleet.cripple_chance", "An escort that would sink limps home crippled instead",
                  "Hull 1, every gun and cannon gone. She sits out the rest of the fight."),
             _pct("rules.fleet.cripple_repair", "Mending a crippled escort costs this share of a new one")]},
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
             _pct("rules.dues.slip_base", "Slipping out at night: chance the harbour watch catches you, base",
                  "Plus the share below for every ship in the fleet; then the standing band moves it."),
             _pct("rules.dues.slip_per_ship", "...plus this for each ship"),
             _pct("rules.dues.slip_ship_max", "...the fleet part at most"),
             _pct("rules.dues.slip_hostile", "...Hostile port: add (a minus takes away)", "", -1, 1),
             _pct("rules.dues.slip_cool", "...Cool port: add (a minus takes away)", "", -1, 1),
             _pct("rules.dues.slip_neutral", "...Neutral port: add (a minus takes away)", "", -1, 1),
             _pct("rules.dues.slip_warm", "...Warm port: add (a minus takes away)", "", -1, 1),
             _pct("rules.dues.slip_favoured", "...Favoured port: add (a minus takes away)", "", -1, 1),
             _pct("rules.dues.slip_min", "Chance of being caught, never less than"),
             _pct("rules.dues.slip_max", "Chance of being caught, never more than"),
             F("rules.dues.slip_mult", "Caught slipping out: fine at least the bill this many times", "num", min=1, max=20, step=0.5,
               help="Or a share of net worth set by the band after the fall, whichever is larger."),
             _pct("rules.dues.slip_floor_hostile_lo", "...or net worth share, Hostile, least"),
             _pct("rules.dues.slip_floor_hostile_hi", "...or net worth share, Hostile, most"),
             _pct("rules.dues.slip_floor_cool_lo", "...or net worth share, Cool, least"),
             _pct("rules.dues.slip_floor_cool_hi", "...or net worth share, Cool, most"),
             _pct("rules.dues.slip_floor_neutral_lo", "...or net worth share, Neutral, least"),
             _pct("rules.dues.slip_floor_neutral_hi", "...or net worth share, Neutral, most"),
             _pct("rules.dues.slip_floor_warm_lo", "...or net worth share, Warm, least"),
             _pct("rules.dues.slip_floor_warm_hi", "...or net worth share, Warm, most"),
             _pct("rules.dues.slip_floor_favoured_lo", "...or net worth share, Favoured, least"),
             _pct("rules.dues.slip_floor_favoured_hi", "...or net worth share, Favoured, most"),
             F("rules.dues.slip_rep", "Caught slipping out: standing lost in that port (times the band's roll)", "num", min=0, max=100, step=1),
             F("rules.dues.slip_travel", "Caught slipping out: word travels to the same region", "bool")]},
         {"title": "Harbour dues: the Mayor's share of profit", "fields": [
             F("rules.dues.profit_enabled", "The Mayor takes a share of profit made in her port", "bool",
               "Only profit from cargo sold in that port this visit. A loss on one cargo offsets a gain on another."),
             _pct("rules.dues.profit_rate_min", "Share of profit: lowest monthly rate",
                  "Each port draws a new rate every month between these two, then multiplies it by its harbour dues level."),
             _pct("rules.dues.profit_rate_max", "Share of profit: highest monthly rate"),
             F("rules.dues.profit_free", "Profit never charged each visit", "num",
               "Small loads (a few rice or tea sales) stay under this and pay nothing.", min=0, max=10**9, step=500),
             _pct("rules.dues.profit_margin_floor", "Margins at or below this pay nothing",
                  "Margin is a cargo's profit divided by what it cost. Low-margin trade is left alone.", 0, 10),
             _pct("rules.dues.profit_margin_full", "Margin that pays the full monthly rate",
                  "Between the floor and this the rate rises in a straight line.", 0, 10),
             _pct("rules.dues.profit_margin_top", "Margin that pays the most", "", 0, 50),
             F("rules.dues.profit_top_mult", "At that margin, pay this many times the monthly rate", "num",
               "Captured cargo cost nothing, so it counts at this margin.", min=1, max=10, step=0.05),
             _pct("rules.dues.profit_rep_cut", "Standing 100 cuts the share by (the same extra at standing 0)",
                  "Standing 50 pays the share as it stands. Each share held in the port also cuts it, as it cuts the "
                  "Port Authority tax (Port shares > cut per share); all 10 shares there and nothing is due.")]},
         {"title": "Port shares (late game)", "fields": [
             F("rules.estates.shares_enabled", "Houses can hold shares in a port", "bool",
               "Placed on the Port tab's Services in any port. Each share lowers that house's Port Authority tax there."),
             F("rules.estates.shares_per_house", "Most shares one captain can hold, all ports together", "int",
               "Placed in one port or spread around. 10 lets a captain hold every share in one port.", min=0, max=100),
             F("rules.estates.shares_per_rank", "Free shares earned for each promotion above Clerk", "int",
               "Trader to Hong Master is 8 promotions. Two more are planned as special awards.", min=0, max=10),
             F("rules.estates.shares_buy", "Shares can also be bought with silver", "bool",
               "Off: shares only come from promotions and awards, which stops a rich house buying out a port. "
               "On: a captain may buy more at the price below, still within the limit above."),
             F("rules.estates.shares_per_port", "Shares in each port", "int",
               "One pool per port, shared by every house. The biggest holder is named Patron of the port.", min=1, max=100),
             _pct("rules.estates.share_cut", "Tax cut for each share held",
                  "10% with 10 shares a port means a house holding them all pays no tax there."),
             F("rules.estates.share_price_per_pct", "Share price for each 1% of the port's base tax rate", "int",
               "A port with a 2.5% base rate and 100,000 here prices a share at 250,000.", min=0, max=10**9),
             F("rules.estates.share_price_min", "Cheapest share", "int", min=0, max=10**9),
             F("rules.estates.share_price_max", "Dearest share", "int", min=0, max=10**9),
             F("rules.estates.share_sell_back", "Shares can be taken back (a bought one for what was paid; an earned one to place again)", "bool")]},
         {"title": "The great house at home (late game)", "fields": [
             F("rules.estates.house_enabled", "Houses can build a great house at home", "bool",
               "Three stages, bought in turn at the home port: Townhouse, Mansion, Palace. Counted in net worth at what was paid."),
             F("rules.estates.house_cost_1", "Townhouse: price", "int", min=0, max=10**10),
             F("rules.estates.house_cost_2", "Mansion: price", "int", min=0, max=10**10),
             F("rules.estates.house_cost_3", "Palace: price", "int", min=0, max=10**10),
             F("rules.estates.house_rep_1", "Townhouse: home standing gained", "num", min=0, max=100, step=1),
             F("rules.estates.house_rep_2", "Mansion: home standing gained", "num", min=0, max=100, step=1),
             F("rules.estates.house_rep_3", "Palace: home standing gained", "num", min=0, max=100, step=1),
             _pct("rules.estates.house_rob_1", "Townhouse: cut in the chance of being robbed ashore at home"),
             _pct("rules.estates.house_rob_2", "Mansion: cut in the chance of being robbed ashore at home"),
             _pct("rules.estates.house_rob_3", "Palace: cut in the chance of being robbed ashore at home"),
             F("rules.estates.house_sell", "Houses can sell the great house back, a stage at a time", "bool",
               "At home. The top stage goes, with the standing it gave and its cut in robbery; December's upkeep falls with it."),
             _pct("rules.estates.house_sell_back", "Selling a stage back pays this share of what was paid for it", "", 0, 1)]},
         {"title": "Prices and upkeep that grow with the house (late game)", "fields": [
             F("rules.estates.wealth_scale", "Shares, the great house and the Mayor's fees grow with net worth", "bool",
               "They are multiplied by the square root of (net worth / the figure below), at least 1."),
             F("rules.estates.wealth_ref", "Net worth at which prices start to grow", "int",
               "At 1,000,000: a house worth 4 million pays double, 25 million five times.", min=1, max=10**12),
             F("rules.estates.wealth_max", "Prices grow at most this many times", "num", min=1, max=1000, step=0.5),
             _pct("rules.estates.house_upkeep", "Each December: the great house costs this share of what was paid", "", 0, 1),
             _pct("rules.estates.patron_upkeep", "Each December: each patronage costs this share of the shares held there", "", 0, 1),
             F("rules.contracts.fee_wealth", "The Mayor's delivery and supply fees grow with net worth too", "bool")]},
         {"title": "The Mayor's commissions (late game)", "fields": [
             F("rules.contracts.enabled", "The home Mayor offers yearly goals and contracts", "bool",
               "One yearly goal and one short contract at a time, taken at home on the Port tab's Services. "
               "Deliveries, supply runs to a port short of a cargo, and standing goals. A missed one costs nothing."),
             F("rules.contracts.short_min", "Short contract: fewest months to finish", "int", min=1, max=24),
             F("rules.contracts.short_max", "Short contract: most months to finish", "int", min=1, max=24),
             F("rules.contracts.supply_months", "Supply run: months to finish", "int", min=1, max=24),
             F("rules.contracts.offer_months", "An offer not taken is replaced after (months)", "int", min=1, max=24),
             _pct("rules.contracts.hold_share_short", "Short delivery: cargo asked for, as a share of the fleet's hold", hi=5.0),
             _pct("rules.contracts.hold_share_year", "Yearly delivery: cargo asked for, as a share of the fleet's hold", hi=10.0),
             F("rules.contracts.min_qty", "Smallest delivery (units)", "int", min=1, max=10**6),
             _pct("rules.contracts.fee_share", "Short delivery fee, as a share of the cargo's normal value", hi=5.0),
             _pct("rules.contracts.fee_share_year", "Yearly delivery fee, as a share of the cargo's normal value", hi=5.0),
             F("rules.contracts.supply_mult", "Supply run: fee x", "num", min=1, max=10, step=0.1),
             F("rules.contracts.shortage_at", "A port is short of a cargo at (x its normal price)", "num", min=1, max=10, step=0.05),
             F("rules.contracts.standing_short", "Short standing goal: points to gain", "int", min=1, max=100),
             F("rules.contracts.standing_year", "Yearly standing goal: points to gain", "int", min=1, max=100),
             _pct("rules.contracts.standing_fee", "Standing goal fee per point, as a share of the house's net worth", hi=0.1),
             F("rules.contracts.rep_short", "Short contract done: home standing gained", "num", min=0, max=100, step=1),
             F("rules.contracts.rep_year", "Yearly goal done: home standing gained", "num", min=0, max=100, step=1)]},
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
             _pct("rules.customs.spot_home", "Spot check at home: chance a house is stopped anyway",
                  "Now and then a house coming home with cargo is stopped and declares at the port's full rate, "
                  "for that one landing only. Lies, buyouts and audits work as in any port. 0: never.", 0, 1),
             _pct("rules.customs.spot_shares", "Spot check where shares make a port free",
                  "The same, in a port where the house's shares cut its tax to nothing: the shares are set aside "
                  "for that landing and it declares at the full rate. 0: never.", 0, 1),
             F("rules.customs.bond", "Cargo may be kept sealed in bond", "bool",
               "At the desk a captain may leave a cargo sealed aboard: no tax and no risk on it, but none of it "
               "can be sold in that port until the house has sailed."),
             _pct("rules.customs.drift", "Most the rate moves in a month", "", 0, 0.5),
             _pct("rules.customs.range", "Most the rate strays from the port's base rate", "", 0, 0.5),
             _pct("rules.customs.min_rate", "Lowest rate anywhere", "", 0, 1),
             _pct("rules.customs.max_rate", "Highest rate anywhere", "", 0, 1),
             _pct("rules.customs.max_declare", "Highest declaration allowed (share of true worth)",
                  "Above 100% is over-declaring: she never buys, you pay more tax, and your standing rises.", 1, 5),
             _pct("rules.customs.pay_less_lo", "Pay Less: declares at least (share of true worth)",
                  "The desk's four buttons. Pay Less draws a share of each cargo's worth between these two, "
                  "hidden until her ruling.", 0, 1),
             _pct("rules.customs.pay_less_hi", "Pay Less: declares at most (share of true worth)", "", 0, 1),
             _pct("rules.customs.pay_more_share", "Pay More: declares (share of true worth)",
                  "Pay Correct and Pay More are never bought out or searched. Pay More also earns standing.", 1, 5),
             F("rules.customs.greet_aloud_min", "Her greeting is read aloud every (landings), at least", "int",
               "Her greeting is always written on her desk; this only sets how often it is spoken. After she reads "
               "it, the next landings are quiet. 1 and 1: every landing. The Registrar's price tip is always read.",
               min=1, max=20),
             F("rules.customs.greet_aloud_max", "... and at most every (landings)", "int", min=1, max=20)]},
         {"title": "Under the Counter (the tax lady's paid tips)", "fields": [
             F("rules.counter.enabled", "The Under the Counter tab is open", "bool",
               "A tab on the left rail with the port's tax lady. She sells two tips (a full hold: what to buy here "
               "and where to sell it; what you're carrying: where to sell the hold), paid before she talks."),
             _pct("rules.counter.fee_min", "Her price at the lowest rank (share of the tip's worth)",
                  "Her price is this share of what the tip is worth to the house, rising evenly with rank."),
             _pct("rules.counter.fee_max", "Her price at the top rank (share of the tip's worth)"),
             F("rules.counter.fee_floor", "She never charges less than", "int", min=0, max=1000000),
             F("rules.counter.min_worth", "A tip worth less than this she gives away (no sale)", "int",
               "Below this she says nothing pays and charges nothing.", min=0, max=1000000),
             _pct("rules.counter.risk_loss", "Share of the profit a pirate fight is reckoned to cost",
                  "Her figure of a tip's worth takes this share of the profit off, times the chance of a fight on "
                  "the way, so a dangerous run must pay more to come top.")]},
         {"title": "The Registrar (Mrs. Marlowe, at each captain's home port)", "fields": [
             F("rules.registrar.enabled", "The Registrar meets each house in its home port with a price tip", "bool",
               "On: a house coming home is met by the Registrar (cast key taxlady) instead of the port's officer, "
               "and told this month's price of one cargo in one other port, written into its Price Book and read "
               "aloud. Off: the home port's own officer waves it in, with no tip."),
             F("rules.registrar.stale_months", "She tips a port not seen for at least (months)", "int",
               "She picks a port whose price the house hasn't seen for this long, or never. If every price is "
               "fresher than that, she gives the oldest one.", min=0, max=60),
             F("rules.registrar.held_first", "She favours a cargo the house is carrying", "bool",
               "Off: any cargo. (Her ordinary price tip only.)"),
             F("rules.registrar.hot_enabled", "Hot tips: she foretells a boom", "bool",
               "On: now and then she (at home) or a port's officer (anywhere else) names a cargo that is cheap "
               "there and is about to boom in another port. The boom is real: it lands when they say. Off: price tips only."),
             _pct("rules.registrar.hot_home_chance", "Chance of a hot tip when a house comes home",
                  "The Registrar gives a hot tip on this share of homecomings; otherwise her ordinary price tip."),
             _pct("rules.registrar.hot_away_chance", "Chance of a hot tip in any other port",
                  "That port's own officer gives a hot tip on this share of arrivals; otherwise no tip."),
             F("rules.registrar.hot_every", "A hot tip at most every (months)", "int",
               "Per house, from anyone. Never two at once either: while a tip is still to come or still "
               "running, nobody gives the house another.", min=1, max=60),
             F("rules.registrar.hot_lead", "The boom lands after (months)", "int",
               "1: the month after she tells you, so a house that buys and sails at once arrives in it.",
               min=1, max=6),
             F("rules.registrar.hot_months_min", "The boom lasts at least (months)", "int",
               "How long a hot-tip boom runs is picked at random between this and the longest, and kept "
               "secret: the tip says when it lands, never how long it lasts.", min=1, max=12),
             F("rules.registrar.hot_months_max", "The boom lasts at most (months)", "int", min=1, max=12),
             F("rules.registrar.hot_hold", "A hot-tip boom holds its price the whole time", "bool",
               "On: while a foretold boom runs, the month's price swing can lift it but never drop it below "
               "the level that was foretold. Off: it swings like any other price."),
             F("rules.registrar.hot_after_max", "When it ends, the price falls to (up to, times normal)", "num",
               "The month a hot-tip boom runs out its price drops straight back to between normal and this, "
               "so a house that arrives late has missed it.", min=1, max=10, step=0.1),
             F("rules.registrar.hot_min", "Boom: lowest price (times normal)", "num", min=1, max=100, step=0.5),
             F("rules.registrar.hot_max", "Boom: highest price (times normal)", "num", min=1, max=100, step=0.5)]},
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
             F("rules.customs.fine_mult", "Caught: fine as a multiple of the tax dodged (Standing swings off)", "num", min=0, max=50, step=0.5),
             F("rules.customs.caught_rep", "Caught: standing lost in that port (Standing swings off)", "num", min=0, max=100, step=1),
             F("rules.customs.over_rep", "Over-declaring to the limit: standing gained (Standing swings off)", "num", min=0, max=100, step=0.5),
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
         {"title": "Standing: the five bands and their luck", "fields": [
             F("rules.standing.enabled", "Standing swings (bands, big falls, drift)", "bool",
               "Standing falls in five bands of 20. Every standing loss or gain below is multiplied by a fresh roll from the band the house is in, and the fine for a caught lie is set by the band it falls into. Off: standing works as before."),
             F("rules.standing.hostile_pen_lo", "Hostile (0-19): losses times, least", "num",  min=0, max=20, step=0.05),
             F("rules.standing.hostile_pen_hi", "Hostile (0-19): losses times, most", "num",  min=0, max=20, step=0.05),
             F("rules.standing.hostile_rew_lo", "Hostile (0-19): gains times, least", "num",  min=0, max=20, step=0.05),
             F("rules.standing.hostile_rew_hi", "Hostile (0-19): gains times, most", "num",  min=0, max=20, step=0.05),
             F("rules.standing.cool_pen_lo", "Cool (20-39): losses times, least", "num",  min=0, max=20, step=0.05),
             F("rules.standing.cool_pen_hi", "Cool (20-39): losses times, most", "num",  min=0, max=20, step=0.05),
             F("rules.standing.cool_rew_lo", "Cool (20-39): gains times, least", "num",  min=0, max=20, step=0.05),
             F("rules.standing.cool_rew_hi", "Cool (20-39): gains times, most", "num",  min=0, max=20, step=0.05),
             F("rules.standing.neutral_pen_lo", "Neutral (40-59): losses times, least", "num",  min=0, max=20, step=0.05),
             F("rules.standing.neutral_pen_hi", "Neutral (40-59): losses times, most", "num",  min=0, max=20, step=0.05),
             F("rules.standing.neutral_rew_lo", "Neutral (40-59): gains times, least", "num",  min=0, max=20, step=0.05),
             F("rules.standing.neutral_rew_hi", "Neutral (40-59): gains times, most", "num",  min=0, max=20, step=0.05),
             F("rules.standing.warm_pen_lo", "Warm (60-79): losses times, least", "num",  min=0, max=20, step=0.05),
             F("rules.standing.warm_pen_hi", "Warm (60-79): losses times, most", "num",  min=0, max=20, step=0.05),
             F("rules.standing.warm_rew_lo", "Warm (60-79): gains times, least", "num",  min=0, max=20, step=0.05),
             F("rules.standing.warm_rew_hi", "Warm (60-79): gains times, most", "num",  min=0, max=20, step=0.05),
             F("rules.standing.favoured_pen_lo", "Favoured (80-100): losses times, least", "num",  min=0, max=20, step=0.05),
             F("rules.standing.favoured_pen_hi", "Favoured (80-100): losses times, most", "num",  min=0, max=20, step=0.05),
             F("rules.standing.favoured_rew_lo", "Favoured (80-100): gains times, least", "num",  min=0, max=20, step=0.05),
             F("rules.standing.favoured_rew_hi", "Favoured (80-100): gains times, most", "num",  min=0, max=20, step=0.05)]},
         {"title": "Standing: caught at the desk", "fields": [
             F("rules.standing.caught_base", "Caught: standing lost, base", "num", "Plus the share below for how much of the hold's value was hidden. This hit is not band-rolled.", min=0, max=100, step=0.5),
             F("rules.standing.caught_lie", "Caught: more standing lost for hiding all of it", "num",  min=0, max=100, step=0.5),
             _pct("rules.standing.caught_vary", "Caught: the fall varies by up to", "Either way.", 0, 1),
             _pct("rules.standing.region_share", "Word travels: share of a fall felt in the same region", "When caught at the desk or when contraband is seized. Ports in other regions never hear.", 0, 1),
             F("rules.standing.fine_hidden", "Fine: share of the hidden value, times the band's loss roll", "num",  min=0, max=20, step=0.05),
             _pct("rules.standing.hostile_floor_lo", "Hostile (0-19): fine at least this share of net worth, least", "", 0, 1),
             _pct("rules.standing.hostile_floor_hi", "Hostile (0-19): fine at least this share of net worth, most", "", 0, 1),
             _pct("rules.standing.cool_floor_lo", "Cool (20-39): fine at least this share of net worth, least", "", 0, 1),
             _pct("rules.standing.cool_floor_hi", "Cool (20-39): fine at least this share of net worth, most", "", 0, 1),
             _pct("rules.standing.neutral_floor_lo", "Neutral (40-59): fine at least this share of net worth, least", "", 0, 1),
             _pct("rules.standing.neutral_floor_hi", "Neutral (40-59): fine at least this share of net worth, most", "", 0, 1),
             _pct("rules.standing.warm_floor_lo", "Warm (60-79): fine at least this share of net worth, least", "", 0, 1),
             _pct("rules.standing.warm_floor_hi", "Warm (60-79): fine at least this share of net worth, most", "", 0, 1),
             _pct("rules.standing.favoured_floor_lo", "Favoured (80-100): fine at least this share of net worth, least", "", 0, 1),
             _pct("rules.standing.favoured_floor_hi", "Favoured (80-100): fine at least this share of net worth, most", "", 0, 1)]},
         {"title": "Standing: gains and losses", "fields": [
             F("rules.standing.trade_cap", "Good business: most standing from trading in one visit", "num", "A sale at a profit, a cargo sold where it is short or bought where it is in glut. Before the band roll.", min=0, max=100, step=0.5),
             F("rules.standing.short_at", "Short: price at least this times its usual price there", "num",  min=1, max=10, step=0.05),
             F("rules.standing.glut_at", "Glut: price at most this times its usual price there", "num",  min=0, max=1, step=0.05),
             F("rules.standing.drift", "Drift: points a month every port moves back toward 50", "num",  min=0, max=50, step=0.5),
             F("rules.standing.pay_correct", "Honest declaration: standing gained", "num",  min=0, max=100, step=0.5),
             F("rules.standing.pay_more", "Pay More: standing gained", "num",  min=0, max=100, step=0.5),
             F("rules.standing.pay_more_at", "Pay More: declared at least this times the true worth", "num",  min=1, max=2, step=0.01),
             F("rules.standing.honest_run", "Each honest desk in a row after the first adds", "num",  min=0, max=100, step=0.5),
             F("rules.standing.honest_run_max", "The honest run adds at most", "num",  min=0, max=100, step=0.5),
             F("rules.standing.pirates_beaten", "Pirates beaten on the way to a port: standing gained there", "num",  min=0, max=100, step=0.5),
             F("rules.standing.debt_cleared", "Debt cleared: home standing gained", "num",  min=0, max=100, step=0.5),
             F("rules.standing.debt_cleared_min", "Debt cleared: only for a debt of at least", "int", min=0, max=10**9),
             F("rules.standing.seized", "Contraband seized: standing lost", "num",  min=0, max=100, step=0.5),
             F("rules.standing.dues_short", "Harbour dues paid short: standing lost", "num",  min=0, max=100, step=0.5),
             F("rules.standing.collect_home", "Collectors call: home standing lost", "num",  min=0, max=100, step=0.5),
             F("rules.standing.collect_away", "Collectors call: standing lost everywhere else", "num",  min=0, max=100, step=0.5),
             F("rules.standing.bankrupt_home", "Bankruptcy: home standing lost", "num",  min=0, max=100, step=0.5),
             F("rules.standing.bankrupt_away", "Bankruptcy: standing lost everywhere else", "num",  min=0, max=100, step=0.5),
             F("rules.standing.beaten", "Beaten or retreating on the way to a port: standing lost there", "num",  min=0, max=100, step=0.5),
             F("rules.standing.dump", "Dumping a lot far below market: standing lost", "num",  min=0, max=100, step=0.5),
             F("rules.standing.dump_below", "Dumping: paid under this times the cargo's usual price there", "num",  min=0, max=1, step=0.05),
             F("rules.standing.contract_missed", "Missing a Mayor's commission: home standing lost", "num",  min=0, max=100, step=0.5)]},
         {"title": "Standing: what each band does", "fields": [
             F("rules.standing.hostile_audit", "Hostile: Port Authority audits times", "num",  min=1, max=10, step=0.05),
             F("rules.standing.cool_audit", "Cool: Port Authority audits times", "num",  min=1, max=10, step=0.05),
             _pct("rules.standing.hostile_margin", "Hostile: dealer's margin widened by", "", 0, 0.5),
             _pct("rules.standing.cool_margin", "Cool: dealer's margin widened by", "", 0, 0.5),
             _pct("rules.standing.hostile_yard", "Hostile: ships and repairs cost more by", "", 0, 5),
             _pct("rules.standing.cool_yard", "Cool: ships and repairs cost more by", "", 0, 5),
             F("rules.standing.hostile_match", "Hostile: pirates leaving this port are tougher by", "num", "Added to the fight's match (1 = an even fight).", min=0, max=3, step=0.01),
             F("rules.standing.cool_match", "Cool: pirates leaving this port are tougher by", "num",  min=0, max=3, step=0.01),
             _pct("rules.standing.warm_tax_cut", "Warm: Port Authority tax cut by", "", 0, 1),
             _pct("rules.standing.favoured_tax_cut", "Favoured: Port Authority tax cut by", "", 0, 1),
             F("rules.standing.favoured_match", "Favoured: pirates leaving this port are weaker by", "num",  min=0, max=3, step=0.01),
             _pct("rules.standing.favoured_avoid", "Favoured: chance friends' warning avoids a fight leaving this port", "", 0, 1),
             _pct("rules.standing.lot_chance", "Favoured: chance a dealer offers a private lot on arrival", "", 0, 1),
             _pct("rules.standing.lot_depth", "Private lot: size, as a share of the cargo's market depth, times the gain roll", "", 0, 5),
             _pct("rules.standing.lot_discount", "Private lot: below market by, times the gain roll", "", 0, 1),
             _pct("rules.standing.lot_discount_max", "Private lot: never more than this below market", "", 0, 1)]},
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
                        min=0, max=1, default=0.15),
                      C("purse", "Dealers' purse size", "num", "How much silver this port's dealers have each month for "
                        "each cargo, against the usual (Economy > Markets sets the usual). 1 is normal; a great port is "
                        "bigger, a small one smaller. Selling past it pays far less.", min=0.05, max=20, step=0.05, default=1.0)]},
     ],
     "matrix": {"path": "ports", "sub": "mods", "cols_from": "goods", "title": "Local prices",
                "help": "Each cell multiplies the cargo's usual price in that port. Below 1 it is made there and cheap; "
                        "above 1 it is in demand. Blank means 1.", "min": 0.05, "max": 20}},
    {"id": "ships", "title": "Ships", "intro": "What the shipyards sell. A ship type removed during a game is replaced by the shipwreck ship.",
     "tables": [
         {"path": "ships", "title": "Ship types", "kind": "dict", "id_label": "Key",
          "columns": [C("name", "Name", "text", max=30),
                      C("hold", "Hold (units)", "int", "0 for an escort.", min=0, max=10**6),
                      C("hull", "Hull points", "int", min=1, max=10**5),
                      C("slots", "Gun mounts", "int", min=0, max=500),
                      C("price", "Price", "int", min=0, max=10**9),
                      C("fast", "Fast", "bool", "Runs from pirates better and suffers less in storms."),
                      C("cannons", "Cannons", "bool", "Her deck can carry cannons as well as guns. Each cannon takes "
                        "the gun mounts set under Rules > Fleet.", default=False),
                      C("role", "Class", "select", "Merchantman: cargo and guns (the first line of the fleet). "
                        "Escort: guns only, sails in the van and takes the fire. Cargo ship: hold only, sails in "
                        "the rear. The limits for each class are under Rules > Fleet.", default="trader",
                        options=[["trader", "Merchantman"], ["escort", "Escort"], ["cargo", "Cargo ship"],
                                 ["flagship", "Flagship (one per house, outside the limits)"]])]},
     ],
     "groups": [
         {"title": "Ship names", "fields": [
             F("ship_names", "Merchantman names", "lines", "Names given to new Merchantmen. One per line.", max=40),
             F("escort_names", "Escort names", "lines", "Names given to new Escorts. One per line.", max=40),
             F("cargo_names", "Cargo ship names", "lines", "Names given to new Cargo ships. One per line.", max=40)]},
         {"title": "NSFW ship names", "fields": [
             F("nsfw_ship_names", "NSFW Merchantman names", "lines", "Used instead of the clean Merchantman names "
               "while Family-friendly is off. Every ship also gets a clean name, shown whenever Family-friendly is on "
               "(for the table, or one screen). One per line.", max=40),
             F("nsfw_escort_names", "NSFW Escort names", "lines", "Used instead of the clean Escort names while "
               "Family-friendly is off. One per line.", max=40),
             F("nsfw_cargo_names", "NSFW Cargo ship names", "lines", "Used instead of the clean Cargo ship names "
               "while Family-friendly is off. One per line.", max=40)]},
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
         {"title": "Storms: how bad (the cut screen)", "fields": [
             F("rules.storm.enabled", "Storms hurt by severity", "bool", "On: a storm gets a severity score and a band "
               "(Rough, Heavy, Savage) and takes hull, cargo and guns, and Heavy and Savage storms send the fleet to "
               "another port and show the storm screen. Off: the flat damage and the typhoon detour above."),
             F("rules.storm.base", "Severity by sea: calm, fair, squalls, typhoon", "numlist",
               "Four numbers. The starting score of a storm in each kind of sea.", min=0, max=500, count=4),
             F("rules.storm.dice_min", "Storm dice: least", "num", "The score is multiplied by a roll between the two.",
               min=0, max=5, step=0.05),
             F("rules.storm.dice_max", "Storm dice: most", "num", min=0, max=5, step=0.05),
             F("rules.storm.risk_w", "Distance counts for", "num", "0 ignores the length of the run; 1 is the full "
               "risk multiplier above.", min=0, max=3, step=0.05),
             F("rules.storm.load_w", "A full hold adds", "num", "Score x (1 + this x how full the hold is).",
               min=0, max=3, step=0.05),
             F("rules.storm.hull_w", "A battered fleet adds", "num", "Score x (1 + this x how much hull is already lost).",
               min=0, max=3, step=0.05),
             F("rules.storm.arms_w", "Heavy guns add", "num", "Score x (1 + this x how many of the gun slots are armed).",
               min=0, max=3, step=0.05),
             F("rules.storm.big_hull", "Ships with at least this much hull ride it better", "int", min=0, max=100000),
             F("rules.storm.big_mult", "...and take this share of the damage", "num", min=0, max=5, step=0.05),
             F("rules.storm.heavy_at", "Heavy from this score", "num", min=0, max=1000, step=1),
             F("rules.storm.savage_at", "Savage from this score", "num", min=0, max=1000, step=1),
             F("rules.storm.cap", "Score where a storm is at its worst", "num", "Scores above this count as this.",
               min=1, max=1000, step=1)]},
         {"title": "Storms: what each band takes", "fields": [
             _pct("rules.storm.rough_hull_min", "Rough: hull lost, least", "A share of each ship's full hull."),
             _pct("rules.storm.rough_hull_max", "Rough: hull lost, most"),
             _pct("rules.storm.heavy_hull_min", "Heavy: hull lost, least"),
             _pct("rules.storm.heavy_hull_max", "Heavy: hull lost, most"),
             _pct("rules.storm.heavy_cargo_min", "Heavy: cargo overboard, least", "A share of each cargo in the hold."),
             _pct("rules.storm.heavy_cargo_max", "Heavy: cargo overboard, most"),
             _pct("rules.storm.heavy_guns", "Heavy: share of guns and cannons washed away", "Each gun is lost this often."),
             _pct("rules.storm.savage_hull_min", "Savage: hull lost, least"),
             _pct("rules.storm.savage_hull_max", "Savage: hull lost, most"),
             _pct("rules.storm.savage_cargo_min", "Savage: cargo overboard, least"),
             _pct("rules.storm.savage_cargo_max", "Savage: cargo overboard, most"),
             _pct("rules.storm.savage_guns", "Savage: share of guns and cannons washed away")]},
         {"title": "Storms: where the fleet lands", "fields": [
             _pct("rules.storm.divert_heavy", "Heavy: chance of being sent to another port"),
             _pct("rules.storm.divert_savage", "Savage: chance of being sent to another port"),
             F("rules.storm.candidates", "Ports a storm can throw you onto", "int", "The nearest to your track, "
               "leaving out where you sailed from and where you were going.", min=1, max=20),
             F("rules.storm.w_price", "Port score: what the hold fetches there", "num", "Compared with the best port for "
               "the cargo left. The worst score is the worst port for your hold.", min=0, max=10, step=0.05),
             F("rules.storm.w_yard", "Port score: has a shipyard", "num", min=0, max=10, step=0.05),
             F("rules.storm.w_standing", "Port score: standing there", "num", min=0, max=10, step=0.05),
             F("rules.storm.ban_penalty", "Port score: each banned cargo aboard costs", "num", min=0, max=10, step=0.05),
             _pct("rules.storm.patch_max", "A port with no shipyard can mend a ship up to", "A share of her full hull. "
                  "100% turns the rule off; full repair then works in every port as before.")]},
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
             F("rules.battle.foe_voice", "The enemy answers the bosun", "bool",
               "On: Admiral Li Yue (her war junks) or Madam Shek Yu-lan (the pirate junks) stands on the right and "
               "answers at the key moments: the sighting, the price, a ship sunk on either side, and the ending. "
               "Their lines are under Sea battle in Language & Text (battle.foe.*)."),
             _pct("rules.battle.gun_loss", "Enemy hits that smash guns instead of the hull",
                  "Each hit on a ship that still has guns: this share dismounts guns (no hull damage); the rest hole the hull."),
             _pct("rules.battle.gun_loss_two", "Gun hits that smash two guns, not one"),
             _pct("rules.battle.cargo_hit", "Enemy hits that burst the hold instead of the hull",
                  "Of the hits that miss the guns: this share lands in the hold. One kind of goods aboard, every "
                  "kind as likely as the next (gold included), loses part of its units over the side."),
             _pct("rules.battle.cargo_hit_min", "Hold hit: share of that good lost, least"),
             F("rules.battle.spite", "Spiteful crews aim for the dearest cargo", "bool",
               "On: some enemy crews would rather sink a rich cargo than let it sail. Rolled at the sighting; "
               "Powder and the enemy say so. They hit the hold more often and mostly the dearest good aboard."),
             _pct("rules.battle.spite_chance", "Pirate crews that are spiteful"),
             _pct("rules.battle.spite_chance_lord", "Li Yue's war junk crews that are spiteful"),
             _pct("rules.battle.spite_aim", "Spiteful hold hits that find the dearest good",
                  "The rest land on any good aboard, as usual."),
             F("rules.battle.spite_hold", "Spiteful crews hit the hold this many times as often", "float",
               "Multiplies the hold-hit share above (2 = twice as often).", min=1, max=5),
             _pct("rules.battle.cargo_hit_max", "Hold hit: share of that good lost, most"),
             F("rules.battle.parley", "Pirates name a price to let the fleet pass", "bool",
               "Before the first shot. The pirate queen's fleet never does."),
             F("rules.battle.parley_per_junk", "Their price: silver per junk", "int", min=0, max=10**7),
             _pct("rules.battle.parley_cargo", "Their price: share of the cargo's usual value, least"),
             _pct("rules.battle.parley_cargo_max", "Their price: share of the cargo's usual value, most",
                  "Drawn for each fight. If silver and the bank fall short, they take the rest in cargo."),
             F("rules.battle.fleet_types", "Three kinds of enemy (raiders, a small band, the war fleet)", "bool",
               "Raiders are fast, lightly gunned and go for the hold; a small band is weak and can be spared for a "
               "price tip; Admiral Li Yue's war fleet is tough and pays big booty."),
             _pct("rules.battle.band_share", "Ordinary pirates who come as a small band"),
             F("rules.battle.raider_guns", "Raiders' guns (x usual)", "num", min=0, max=5, step=0.05),
             _pct("rules.battle.raider_run", "Outrunning raiders: extra chance"),
             F("rules.battle.band_strength", "A band's hull and guns (x usual)", "num", min=0.05, max=5, step=0.05),
             F("rules.battle.band_ships_max", "A band: most junks", "int", min=1, max=60),
             F("rules.battle.band_booty", "A band's booty (x usual)", "num", min=0, max=10, step=0.05),
             F("rules.battle.lord_booty", "The war fleet's booty (x usual)", "num", min=0, max=10, step=0.05),
             _pct("rules.battle.retreat_min", "Retreat: cargo thrown overboard, least"),
             _pct("rules.battle.retreat_max", "Retreat: cargo thrown overboard, most"),
             F("rules.battle.retreat_floor", "Retreat: hull left on the last ship", "int",
               "A retreat never sinks the last ship; she limps in with this much hull.", min=1, max=1000),
             F("rules.battle.prize", "A won fight takes the enemy's cargo", "bool",
               "Whatever the sunk junks had stolen from someone else: mostly scraps, now and then a hold full. "
               "Only what fits in the hold is taken."),
             F("rules.battle.prize_lord_step", "Pirate queen's fleet: prize tiers richer by", "int",
               "Her war junks carry better plunder: the tier drawn moves up this many steps.", min=0, max=3),
             F("rules.battle.prize_tiers.scraps.weight", "Prize, Scraps: how often (weight)", "int", min=0, max=1000),
             F("rules.battle.prize_tiers.scraps.goods_min", "Prize, Scraps: kinds of goods, least", "int", min=1, max=9),
             F("rules.battle.prize_tiers.scraps.goods_max", "Prize, Scraps: kinds of goods, most", "int", min=1, max=9),
             F("rules.battle.prize_tiers.scraps.units_min", "Prize, Scraps: units of each, least", "int", min=1, max=10000),
             F("rules.battle.prize_tiers.scraps.units_max", "Prize, Scraps: units of each, most", "int", min=1, max=10000),
             F("rules.battle.prize_tiers.modest.weight", "Prize, Modest: how often (weight)", "int", min=0, max=1000),
             F("rules.battle.prize_tiers.modest.goods_min", "Prize, Modest: kinds of goods, least", "int", min=1, max=9),
             F("rules.battle.prize_tiers.modest.goods_max", "Prize, Modest: kinds of goods, most", "int", min=1, max=9),
             F("rules.battle.prize_tiers.modest.value_min", "Prize, Modest: silver per enemy junk, least", "int", min=0, max=10**6),
             F("rules.battle.prize_tiers.modest.value_max", "Prize, Modest: silver per enemy junk, most", "int", min=0, max=10**6),
             F("rules.battle.prize_tiers.rich.weight", "Prize, Rich: how often (weight)", "int", min=0, max=1000),
             F("rules.battle.prize_tiers.rich.goods_min", "Prize, Rich: kinds of goods, least", "int", min=1, max=9),
             F("rules.battle.prize_tiers.rich.goods_max", "Prize, Rich: kinds of goods, most", "int", min=1, max=9),
             F("rules.battle.prize_tiers.rich.value_min", "Prize, Rich: silver per enemy junk, least", "int", min=0, max=10**6),
             F("rules.battle.prize_tiers.rich.value_max", "Prize, Rich: silver per enemy junk, most", "int", min=0, max=10**6),
             F("rules.battle.prize_tiers.haul.weight", "Prize, A great haul: how often (weight)", "int", min=0, max=1000),
             F("rules.battle.prize_tiers.haul.goods_min", "Prize, A great haul: kinds of goods, least", "int", min=1, max=9),
             F("rules.battle.prize_tiers.haul.goods_max", "Prize, A great haul: kinds of goods, most", "int", min=1, max=9),
             F("rules.battle.prize_tiers.haul.value_min", "Prize, A great haul: silver per enemy junk, least", "int", min=0, max=10**6),
             F("rules.battle.prize_tiers.haul.value_max", "Prize, A great haul: silver per enemy junk, most", "int", min=0, max=10**6)]},
         {"title": "Matched fights and the fleet's formation", "fields": [
             F("rules.battle.match", "Pirates match the fleet they attack", "bool",
               "On: the enemy is sized from your own fleet (fewer, tougher junks with real broadsides), so every fight "
               "is close enough to be worth thinking about. Off: the old way, more junks the bigger your hold."),
             F("rules.battle.match_rounds_min", "Rounds of our fire to sink them all, least", "num", min=1, max=20, step=0.5),
             F("rules.battle.match_rounds_max", "Rounds of our fire to sink them all, most", "num", min=1, max=20, step=0.5),
             F("rules.battle.match_base", "How close the fight is: base", "num",
               "1 is an even fight (they sink us as fast as we sink them). 0.5 means we should win and take about a "
               "quarter of our hull in damage.", min=0, max=3, step=0.05),
             F("rules.battle.match_cargo", "Plus this much for a rich hold (at the most)", "num", min=0, max=3, step=0.05),
             F("rules.battle.match_cargo_ref", "Cargo value that counts as half-rich", "int",
               "At usual prices. A hold worth this much adds half the amount above.", min=1, max=10**9),
             F("rules.battle.match_fame", "Plus this much for a famous fleet (at the most)", "num", min=0, max=3, step=0.05),
             F("rules.battle.match_standing", "Less this much for standing 100 in the port ahead", "num",
               "Standing 0 adds the same. Friends ashore send word of who is lying in wait.", min=0, max=3, step=0.05),
             F("rules.battle.match_spread", "Chance swing (spread)", "num", min=0, max=2, step=0.01),
             F("rules.battle.match_min", "Closeness, least", "num", min=0, max=5, step=0.05),
             F("rules.battle.match_max", "Closeness, most", "num", min=0, max=5, step=0.05),
             F("rules.battle.match_lord", "The pirate queen's fleet: closer by", "num", min=0, max=3, step=0.05),
             _pct("rules.battle.match_escort_share", "Escorts' hull counted when they size their guns",
                  "Their broadsides are sized from the hull they mean to take. Escorts count only this share, so each escort "
                  "soaks up fire meant for the merchantmen and the cargo ships."),
             F("rules.battle.match_ships_min", "Enemy junks, least", "int", min=1, max=100),
             F("rules.battle.match_ships_max", "Enemy junks, most (pirates)", "int", min=1, max=100),
             F("rules.battle.match_lord_ships_max", "Enemy junks, most (the pirate queen)", "int", min=1, max=100),
             _pct("rules.battle.match_size_swing", "Enemy fleet size swings by up to",
                  "Each fight's number of junks moves up or down by up to this share, so fights vary.", 0, 1),
             _pct("rules.battle.wu_fee", "Madam Wu's fee for covering a price to pass",
                  "When silver aboard and the bank can't pay the pirates, she pays the rest and adds it to the debt with this fee.", 0, 2),
             F("rules.battle.match_hp_min", "Shots to sink a junk: least (before the cap above)", "num", min=1, max=1000, step=1),
             F("rules.battle.match_hp_max", "Shots to sink a junk: most (before the cap above)", "num", min=1, max=1000, step=1),
             F("rules.battle.match_flag", "Their flagship is this many times tougher", "num", min=1, max=10, step=0.1),
             F("rules.battle.match_booty", "Booty from a matched fight (x the usual per-junk booty)", "num", min=0, max=10, step=0.05),
             F("rules.battle.allure_base", "How keen they are to attack: base", "num",
               "Multiplies the pirate attack chance. An empty hold and no fame gives this.", min=0, max=5, step=0.05),
             F("rules.battle.allure_cargo", "Keener by this much for a rich hold (at the most)", "num", min=0, max=5, step=0.05),
             F("rules.battle.allure_fame", "Keener by this much for a famous fleet (at the most)", "num", min=0, max=5, step=0.05),
             F("rules.battle.worth_ref", "Rich house: net worth that counts as half way rich", "int",
               "How rich a house looks to the pirates: net worth / (net worth + this).", min=1, max=10**12),
             F("rules.battle.allure_worth", "Keener by this much for a rich house (at the most)", "num", min=0, max=5, step=0.05),
             F("rules.battle.match_worth", "A rich house meets this much more fire (at the most)", "num",
               "Added to the match, so their guns grow with the house.", min=0, max=5, step=0.05),
             F("rules.battle.match_worth_rounds", "A rich house's enemies last this many more rounds (at the most)", "num",
               min=0, max=10, step=0.25),
             F("rules.battle.lord_worth", "The pirate queen finds a rich house this much more often (at the most)", "num",
               "1 doubles her chance for the richest houses.", min=0, max=10, step=0.1),
             F("rules.battle.fame_win", "Fame gained by winning a fight", "num", min=0, max=100, step=0.25),
             F("rules.battle.fame_broke_off", "Fame gained when they break off", "num", min=0, max=100, step=0.25),
             _pct("rules.battle.fame_decay", "Fame that fades each month"),
             F("rules.battle.fame_ref", "Fame that counts as fully famous", "num", min=0.5, max=1000, step=0.5),
             _pct("rules.battle.focus", "Enemy broadsides laid on the weakest ship in front",
                  "The rest are spread over the fleet by the weights below."),
             F("rules.battle.van_weight", "Escorts (van): share of the spread fire", "num", min=0, max=100, step=0.5),
             F("rules.battle.line_weight", "Merchantmen (line): share of the spread fire", "num", min=0, max=100, step=0.5),
             F("rules.battle.rear_weight", "Cargo ships (rear): share of the spread fire, unscreened", "num", min=0, max=100, step=0.5),
             _pct("rules.battle.rear_cover", "Fire a full screen keeps off the rear",
                  "Screened by one escort (or two merchantmen) per cargo ship. As the van is sunk the rear is hit more."),
             F("rules.battle.cargo_spill", "Cargo lost when a cargo ship is hit", "num",
               "1 means a hit that takes 10% of her hull sends 10% of her share of the hold to the bottom.", min=0, max=10, step=0.1)]},
         {"title": "They misjudge the hold (a bargain to pass)", "fields": [
             F("rules.battle.lowball", "Pirates sometimes misjudge what you carry", "bool",
               "Now and then they take a rich fleet for a poor coaster and name a price on a fraction of the cargo. "
               "Turn it down and they see the hold: they ask the full price once more before the first shot. "
               "How plainly the screen says it is a bargain follows the difficulty's sea battle odds."),
             _pct("rules.battle.lowball_chance", "Chance they misjudge the hold (base)"),
             F("rules.battle.lowball_dense", "More likely by this much when the hold is all gold or opium", "num",
               "1 means a hold of nothing but those goods doubles the chance.", min=0, max=10, step=0.1),
             F("rules.battle.lowball_goods", "Goods small and dear enough to fool them", "lines",
               "Cargo keys, one per line (gold, opium).", max=20),
             _pct("rules.battle.lowball_fame", "A famous fleet fools them this much less",
                  "At full fame. Famous houses are known to be rich."),
             _pct("rules.battle.lowball_min", "They think the cargo is worth, least"),
             _pct("rules.battle.lowball_max", "They think the cargo is worth, most")]},
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
             F("rules.contraband.rep_penalty", "Standing lost when caught (Standing swings off)", "num", min=0, max=100, step=1)]},
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
             F("rules.events.windfall_max_turns", "Lasts at most (months)", "int", min=1, max=12),
             F("rules.events.stack_booms", "Booms stack", "bool",
               "Off: when a shortage, a boom, a hot-tip boom or a ban meet on one cargo in one port, only the strongest "
               "counts, and a boom never runs past its own size. On: they multiply (the old way, which made 34x prices)."),
             F("rules.events.boom_eat_depths", "Selling this many depths ends a boom", "num",
               "Selling into a boom or a shortage uses it up: this many times the cargo's depth ends it, a smaller sale "
               "shrinks it in proportion. 0 turns it off.", min=0, max=100, step=0.25)]},
     ]},
]

GRAPHIC_SLOTS = [
    ["logo", "Logo", "Transparent wide logo used on the join screen, lobby, opening, harbor board and admin header. Include the game name in the artwork."],
    ["favicon", "Browser tab icon", "A small square image."],
    ["masthead_bg", "Title banner background", "Behind the title on the join and lobby screens."],
    ["admin_masthead_bg", "Command Center banner", "Behind the title in the admin header. Use a wide panorama with quiet, dark space on the left; the center strip is shown. Managed in Media Library > Brand > Command Center banner."],
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


def promotion_styles():
    with open(os.path.join(ROOT, "web", "assets", "promotion-styles.json"), encoding="utf-8") as f:
        styles = json.load(f)
    if not isinstance(styles, dict) or not styles:
        raise ValueError("web/assets/promotion-styles.json: certificate styles must be a non-empty object")
    for rank, style in styles.items():
        if not ID_RE.fullmatch(rank) or not isinstance(style, dict) or \
                not all(COLOR_RE.fullmatch(str(style.get(k, ""))) for k in ("tone", "deep", "metal", "paper", "ink")) or \
                not isinstance(style.get("audience"), str):
            raise ValueError("web/assets/promotion-styles.json: invalid certificate style for {}".format(rank))
    return styles


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

    # Deeper markets (19 Nov 2026): settings saved before then still carry the old, thin depths, sized
    # for a junk. Any cargo still at its old shipped depth moves to the new one, once; depths set by hand stay.
    mk = cfg["rules"]["market"]
    if not mk.get("depth_v2"):
        for key, old_depth in OLD_DEPTHS.items():
            if key in cfg["goods"] and int(cfg["goods"][key].get("depth", 0)) == old_depth:
                cfg["goods"][key]["depth"] = DEFAULTS["goods"][key]["depth"]
        mk["depth_v2"] = True

    # Game 3 review (19 Nov 2026), once: the swingiest cargoes (porcelain, tea, silk) are calmed to at most
    # CALM_VOLS, and hot tips saved in the file come half as often. Values already lower stay as they are,
    # and anything changed by hand afterwards sticks.
    if not mk.get("review3_v1"):
        for key, top in CALM_VOLS.items():
            if key in cfg["goods"] and float(cfg["goods"][key].get("vol", 0)) > top:
                cfg["goods"][key]["vol"] = top
        saved = ((raw.get("rules") or {}).get("registrar") or {}) if isinstance(raw.get("rules"), dict) else {}
        reg = cfg["rules"]["registrar"]
        for key in ("hot_home_chance", "hot_away_chance"):
            if key in saved:                       # a saved chance is halved; a missing one is already the new default
                reg[key] = round(float(reg[key]) * 0.5, 4)
        mk["review3_v1"] = True

    # Game 4 review (20 Nov 2026), once: bank interest moves from the old 0.5% a month to 1% (a rate set by
    # hand to anything else stays). Maijiuana's swing is set by the wild-cargo rules from now on.
    if not mk.get("review4_v1"):
        bk = cfg["rules"]["bank"]
        if abs(float(bk.get("bank_rate", 0)) - 0.005) < 1e-9:
            bk["bank_rate"] = DEFAULTS["rules"]["bank"]["bank_rate"]
        mk["review4_v1"] = True

    # Bigger pirate fleets (19 Nov 2026): saved settings still at the old shipped caps (12 junks, the
    # pirate queen 16) move to the new ones, once; caps set by hand stay.
    bt = cfg["rules"]["battle"]
    if not bt.get("match_v2"):
        if int(bt.get("match_ships_max", 0)) == 12:
            bt["match_ships_max"] = DEFAULTS["rules"]["battle"]["match_ships_max"]
        if int(bt.get("match_lord_ships_max", 0)) == 16:
            bt["match_lord_ships_max"] = DEFAULTS["rules"]["battle"]["match_lord_ships_max"]
        bt["match_v2"] = True

    # Ranks above Taipan (19 Nov 2026): saved rank tables gain the three new top ranks once; deleting
    # one afterwards sticks.
    gm = cfg["rules"]["game"]
    if not gm.get("late_ranks_v1"):
        have = {r["id"] for r in cfg["ranks"]}
        for rank in DEFAULTS["ranks"]:
            if rank.get("scales") and rank["id"] not in have:
                cfg["ranks"].append(copy.deepcopy(rank))
        cfg["ranks"].sort(key=lambda r: r["worth"])
        gm["late_ranks_v1"] = True

    # Ship types added in a later version (the escort and the cargo ship) join a saved Ships table
    # once; deleting one afterwards sticks.
    fl = cfg["rules"]["fleet"]
    seeded_ships = set(fl.get("seeded_ships") or [])
    for key in SEEDED_SHIPS:
        if key not in seeded_ships and key not in cfg["ships"]:
            cfg["ships"][key] = copy.deepcopy(DEFAULTS["ships"][key])
        seeded_ships.add(key)
    fl["seeded_ships"] = sorted(seeded_ships)
    # Each class keeps to its job: an escort carries no cargo, a cargo ship mounts no guns.
    for key, sh in cfg["ships"].items():
        if sh.get("role") not in SHIP_ROLES:
            sh["role"] = "trader"
        if sh["role"] == "escort":
            sh["hold"] = 0
        elif sh["role"] == "cargo":
            sh["slots"], sh["cannons"] = 0, False
    if not any(sh["role"] == "trader" for sh in cfg["ships"].values()):
        errors.append("Ships: at least one ship type must be a Merchantman")

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
        elif ships[k].get("role", "trader") != "trader":
            errors.append("{}: '{}' must be a Merchantman (escorts and cargo ships can't sail alone)".format(where, k))
    if cfg["rules"]["start"]["ship"] in ships:
        cfg["rules"]["start"]["guns"] = min(cfg["rules"]["start"]["guns"], ships[cfg["rules"]["start"]["ship"]]["slots"])
    g["lengths"] = sorted(set(g["lengths"]))
    if g["default_years"] not in g["lengths"]:
        g["default_years"] = min(g["lengths"], key=lambda y: abs(y - g["default_years"]))
    if cfg["difficulty"]["level"] not in cfg["difficulty"]["presets"]:
        errors.append("Ratings: difficulty level '{}' does not exist".format(cfg["difficulty"]["level"]))
    if cfg["content"]["rating"] not in ("historical", "family"):
        errors.append("Ratings: unknown content rating")
    rank_ids = set()
    for rank in cfg["ranks"]:
        key = rank["id"] or re.sub(r"[^a-z0-9]+", "_", rank["title"].lower()).strip("_")
        if not ID_RE.fullmatch(key) or key in rank_ids:
            errors.append("Player ranks / {}: use a unique badge ID starting with a lowercase letter".format(rank["title"]))
        rank["id"] = key
        rank_ids.add(key)
    cfg["ranks"].sort(key=lambda r: r["worth"])
    for lo, hi, label in (("storm_dmg_min", "storm_dmg_max", "Storm damage"),
                          ("typhoon_dmg_min", "typhoon_dmg_max", "Typhoon damage")):
        if cfg["rules"]["weather"][lo] > cfg["rules"]["weather"][hi]:
            errors.append("Weather: {} 'least' is above 'most'".format(label))
    st = cfg["rules"].get("storm") or {}
    for lo, hi, label in (("dice_min", "dice_max", "Storm dice"), ("rough_hull_min", "rough_hull_max", "Rough storm hull"),
                          ("heavy_hull_min", "heavy_hull_max", "Heavy storm hull"),
                          ("heavy_cargo_min", "heavy_cargo_max", "Heavy storm cargo"),
                          ("savage_hull_min", "savage_hull_max", "Savage storm hull"),
                          ("savage_cargo_min", "savage_cargo_max", "Savage storm cargo")):
        if lo in st and hi in st and st[lo] > st[hi]:
            errors.append("Weather: {} 'least' is above 'most'".format(label))
    if "heavy_at" in st and "savage_at" in st and st["heavy_at"] > st["savage_at"]:
        errors.append("Weather: a storm is Heavy from a lower score than Savage")
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
