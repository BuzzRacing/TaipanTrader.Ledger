"""The Pi's live economy (read from Admin on 25 Nov 2026) as a test fixture: tests/fixtures/pi_economy_2026-11-25.json.
apply(cfg) turns a default config into that economy: the live nine cargoes (no General Cargo; Marijuana is its own
cargo), the live market rules, rank ladder, port multipliers and forbidden map. The six luxuries stay as cfg has them,
so a test can try new rows on the real economy."""
import copy
import json
import os

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "pi_economy_2026-11-25.json")
LUXURIES = ("camphor", "sandalwood", "ginseng", "jade", "pearls", "ambergris")
# What the Pi was seeded with (phase 1 placeholders): base, vol, depth.
OLD_ROWS = {"camphor": (5500, 0.08, 400), "sandalwood": (6500, 0.08, 350), "ginseng": (8000, 0.10, 300),
            "jade": (11000, 0.10, 250), "pearls": (15000, 0.12, 200), "ambergris": (20000, 0.12, 150)}


def load():
    with open(FIXTURE, encoding="utf-8") as f:
        return json.load(f)


def apply(cfg, luxuries=None):
    snap = load()
    lux = {k: copy.deepcopy(v) for k, v in cfg["goods"].items() if k in LUXURIES}
    for k, (base, vol, depth) in (luxuries or {}).items():
        lux[k].update(base=base, vol=vol, depth=depth)
    cfg["goods"] = {k: dict(v) for k, v in snap["goods"].items()}
    cfg["goods"].update(lux)
    cfg["rules"]["market"].update(snap["market"])
    cfg["rules"]["start"].update(snap["start"])
    for rank in cfg["ranks"]:
        if rank["id"] in snap["ranks"]:
            rank["worth"] = snap["ranks"][rank["id"]]
    cfg["ranks"].sort(key=lambda r: r["worth"])
    for port, row in snap["ports"].items():
        cfg["ports"][port]["mods"] = dict(row["mods"])
        cfg["ports"][port]["forbidden"] = list(row["forbidden"])
    cfg["rules"]["tiers"]["enabled"] = True
    return cfg


def old_luxuries():
    return {k: v for k, v in OLD_ROWS.items()}
