"""Cargo Tiers, phase 1 (24 Nov 2026): the data is in place and the switch changes nothing yet.
Six real China Seas luxuries sit in the cargo table (config.py), each with the tier it joins at; saved
settings gain them once; the engine keeps them out of play until the per-captain tables are built
(engine.TIERS_READY). Run: python tests/tiers_data_test.py
"""
import copy
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import config  # noqa: E402
import engine  # noqa: E402

NINE = ["opium", "gold", "silk", "porcelain", "arms", "spices", "tea", "rice", "general"]
LUXURIES = {"camphor": 1, "sandalwood": 1, "ginseng": 1, "jade": 2, "pearls": 2, "ambergris": 2}
LEAVES = {"general": 1, "rice": 1, "tea": 1, "spices": 2, "arms": 2, "porcelain": 2}
FORBID = {"calcutta": "camphor", "shanghai": "sandalwood", "manila": "ginseng", "bangkok": "jade",
          "batavia": "jade", "foochow": "pearls", "saigon": "ambergris", "nagasaki": "ambergris"}


def old_settings():
    """Settings as saved before Cargo Tiers: no luxuries, no tier fields, no tiers rule."""
    raw = copy.deepcopy(config.defaults())
    for key in LUXURIES:
        raw["goods"].pop(key)
    for g in raw["goods"].values():
        g.pop("enters", None)
        g.pop("leaves", None)
    for port_key, port in raw["ports"].items():
        port["forbidden"] = [g for g in port["forbidden"] if g not in LUXURIES]
    raw["rules"].pop("tiers")
    raw["rules"]["market"]["wild_goods"] = ["porcelain"]
    return raw


def test_the_six_luxuries_are_in_the_defaults():
    cfg = config.defaults()
    assert list(cfg["goods"])[:9] == NINE, "the original nine keep their order"
    for key, tier in LUXURIES.items():
        g = cfg["goods"][key]
        assert g["enters"] == tier and g["leaves"] == 0 and not g["contraband"], key
        assert g["base"] > cfg["goods"]["opium"]["base"], "{} is priced above opium".format(key)
    prices = [cfg["goods"][k]["base"] for k in LUXURIES]
    assert prices == sorted(prices), "the second batch is dearer than the first, and each is dearer than the last"
    for key in NINE:
        assert cfg["goods"][key]["enters"] == 0 and cfg["goods"][key]["leaves"] == LEAVES.get(key, 0), key


def test_steps_and_switch():
    t = config.defaults()["rules"]["tiers"]
    assert t["enabled"] is False and t["steps"] == ["merchant", "merchant_prince"]
    ids = [r["id"] for r in config.defaults()["ranks"]]
    assert all(s in ids for s in t["steps"])


def test_defaults_validate_clean():
    cfg, errors = config.validate(config.defaults())
    assert not errors, errors


def test_the_forbidden_map_for_the_luxuries():
    cfg = config.defaults()
    for port, good in FORBID.items():
        assert good in cfg["ports"][port]["forbidden"], (port, good)
    assert cfg["ports"]["hongkong"]["forbidden"] == [] and cfg["ports"]["singapore"]["forbidden"] == ["rice", "gold"]
    for key in LUXURIES:
        n = sum(1 for p in cfg["ports"].values() if key in p["forbidden"])
        assert 1 <= n <= 2, (key, n)
        assert len(cfg["ports"]) - n >= 8


def test_ambergris_is_a_wild_cargo():
    assert "ambergris" in config.defaults()["rules"]["market"]["wild_goods"]


def test_the_switch_decides_whether_the_luxuries_are_in_play():
    """TIERS_READY is True since phase 5 (25 Nov 2026), so rules.tiers.enabled alone decides."""
    assert engine.TIERS_READY
    for enabled in (False, True):
        cfg = config.defaults()
        cfg["rules"]["tiers"]["enabled"] = enabled
        engine.configure(cfg)
        if enabled:
            assert list(engine.GOODS) == NINE + list(LUXURIES), list(engine.GOODS)
            assert engine.FORBIDDEN.get("calcutta") and "camphor" in engine.FORBIDDEN["calcutta"]
        else:
            assert list(engine.GOODS) == NINE, list(engine.GOODS)
            assert not any(g in LUXURIES for ports in engine.FORBIDDEN.values() for g in ports)
        assert engine.FORBIDDEN.get("shanghai") >= {"porcelain", "rice"}, engine.FORBIDDEN
    engine.configure(config.defaults())


def test_a_game_plays_as_before():
    engine.configure(config.defaults())
    g = engine.Game(seed=7)
    assert set(g.s["prices"]["hongkong"]) == set(NINE)
    for port in engine.PORTS:
        assert not set(g.s["prices"][port]) & set(LUXURIES), port


def test_saved_settings_gain_the_luxuries_once():
    cfg, errors = config.validate(old_settings())
    assert not errors, errors
    for key, tier in LUXURIES.items():
        assert key in cfg["goods"] and cfg["goods"][key]["enters"] == tier, key
    for key in NINE:
        assert cfg["goods"][key]["leaves"] == LEAVES.get(key, 0), key       # tier fields come from the shipped table
    for port, good in FORBID.items():
        assert good in cfg["ports"][port]["forbidden"], (port, good)
    assert "ambergris" in cfg["rules"]["market"]["wild_goods"]
    assert cfg["rules"]["tiers"]["seeded_v1"] is True and cfg["rules"]["tiers"]["enabled"] is False
    assert cfg["rules"]["tiers"]["steps"] == ["merchant", "merchant_prince"]


def test_deleting_a_luxury_afterwards_sticks():
    cfg, errors = config.validate(old_settings())
    assert not errors, errors
    cfg["goods"].pop("jade")
    for p in cfg["ports"].values():
        p["forbidden"] = [g for g in p["forbidden"] if g != "jade"]
    again, errors = config.validate(cfg)
    assert not errors, errors
    assert "jade" not in again["goods"], "a deleted luxury must not come back"
    assert all("jade" not in p["forbidden"] for p in again["ports"].values())


def test_settings_that_already_have_the_luxuries_are_left_alone():
    cfg = config.defaults()
    cfg["goods"]["camphor"]["base"] = 6000
    cfg["rules"]["tiers"]["seeded_v1"] = False
    out, errors = config.validate(cfg)
    assert not errors, errors
    assert out["goods"]["camphor"]["base"] == 6000


def test_tier_fields_are_checked():
    cfg = config.defaults()
    cfg["goods"]["jade"]["enters"] = 3                  # only two steps
    _, errors = config.validate(cfg)
    assert any("jade" in e and "tier" in e for e in errors), errors
    cfg = config.defaults()
    cfg["goods"]["tea"]["enters"], cfg["goods"]["tea"]["leaves"] = 1, 1
    _, errors = config.validate(cfg)
    assert any("tea" in e for e in errors), errors


def test_unknown_steps_are_dropped():
    cfg = config.defaults()
    cfg["rules"]["tiers"]["steps"] = ["merchant", "no_such_rank", "merchant"]
    out, errors = config.validate(cfg)
    assert out["rules"]["tiers"]["steps"] == ["merchant"]


def test_settings_saved_before_forbidden_cargo_get_the_whole_shipped_map():
    raw = old_settings()
    for port in raw["ports"].values():
        port.pop("forbidden")                           # no list at all, as in a file saved before Forbidden Cargo
    cfg, errors = config.validate(raw)
    assert not errors, errors
    want = config.defaults()["ports"]
    for key, port in cfg["ports"].items():
        assert port["forbidden"] == want[key]["forbidden"], (key, port["forbidden"])
    assert cfg["ports"]["shanghai"]["forbidden"] == ["porcelain", "rice", "sandalwood"]


def test_the_luxuries_are_priced_for_the_pis_economy():
    """Phase 8 (25 Nov 2026), rebalanced against the Pi's real economy (tests/pi_economy.py): the luxuries cost more than
    opium, climb in price, swing and the money one price move takes (price x depth), and no luxury's market is thicker
    than a retained cargo's. Numbers come from tests/tiers_market_scan.py ceiling on the Pi's settings."""
    cfg = config.defaults()
    goods = cfg["goods"]
    order = ["camphor", "sandalwood", "ginseng", "jade", "pearls", "ambergris"]
    for series in ([goods[g]["base"] for g in order], [goods[g]["vol"] for g in order],
                   [goods[g]["base"] * goods[g]["depth"] for g in order]):
        assert series == sorted(series), series
    assert goods["camphor"]["base"] > 8522, "dearer than the Pi's opium"
    assert all(goods[g]["depth"] <= 450 for g in order)
    assert 3_000_000 <= goods["camphor"]["base"] * goods["camphor"]["depth"] <= goods["ambergris"]["base"] * goods["ambergris"]["depth"] <= 10_000_000
    assert "ambergris" in cfg["rules"]["market"]["wild_goods"], "wild in the shipped defaults (the Pi's list differs)"


def test_a_file_seeded_with_the_placeholder_rows_moves_to_the_balanced_ones_once():
    """The Pi was seeded in phase 1 with placeholder rows. The first load after this change moves a row that is still
    exactly the placeholder; a row someone edited is left alone; and it happens only once (rules.tiers.rows_v2)."""
    raw = copy.deepcopy(config.defaults())
    for key, (base, vol, depth) in config.TIER_OLD_ROWS.items():
        raw["goods"][key].update(base=base, vol=vol, depth=depth)
    raw["goods"]["jade"].update(base=12345)                  # edited by hand: stays
    raw["rules"]["tiers"].update(seeded_v1=True, rows_v2=False)
    cfg, errors = config.validate(raw)
    assert not errors, errors
    shipped = config.defaults()["goods"]
    for key in config.TIER_GOODS:
        if key == "jade":
            assert cfg["goods"][key]["base"] == 12345
        else:
            assert (cfg["goods"][key]["base"], cfg["goods"][key]["vol"], cfg["goods"][key]["depth"]) == \
                (shipped[key]["base"], shipped[key]["vol"], shipped[key]["depth"]), key
    assert cfg["rules"]["tiers"]["rows_v2"] is True
    cfg["goods"]["camphor"].update(base=5500, vol=0.08, depth=400)    # put the placeholder back by hand: not touched again
    again, errors = config.validate(cfg)
    assert again["goods"]["camphor"]["base"] == 5500


if __name__ == "__main__":
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("ok", name)
            except Exception as exc:  # noqa: BLE001
                failed += 1
                print("FAIL", name, repr(exc))
    sys.exit(1 if failed else 0)
