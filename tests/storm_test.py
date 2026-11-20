"""Storms and damage (owner's decisions, 20 Nov 2026; project doc "SeaTrader Storms and Damage").

Run from the project folder:  python -m pytest tests/storm_test.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import config  # noqa: E402
import engine  # noqa: E402
import storm  # noqa: E402
from engine import Game, GOODS, PORTS, SHIPS  # noqa: E402


def setup(**rules):
    cfg = config.defaults()
    cfg["rules"]["weather"]["storm_chance"] = [1, 1, 1, 1]      # every voyage is caught (chance x risk x difficulty, capped at 1)
    cfg["rules"]["weather"].update({"risk_min": 1.0, "risk_max": 1.0, "offcourse": 0.0, "forecast_accuracy": 1.0})
    cfg["rules"]["pirates"].update({"chance": 0.0})
    cfg["rules"]["liyuen"]["chance"] = 0.0
    cfg["rules"]["battle"]["match"] = False
    cfg["rules"]["fleet"]["upkeep_enabled"] = False
    cfg["rules"]["bank"]["mug_chance"] = 0.0
    cfg["rules"]["customs"]["enabled"] = False
    for path, value in rules.items():
        group, key = path.split("__")
        cfg["rules"][group][key] = value
    cfg, errors = config.validate(cfg)
    assert not errors, errors
    engine.configure(cfg)


def new_game(seed=1, cash=50000, cargo=None):
    g = Game(seed=seed)
    g.join("Ann", "")
    g.act("p1", {"type": "start"}, present=g.s["order"])
    p = g.s["players"]["p1"]
    p["cargo"] = dict(cargo or {})
    p["basis"] = {k: GOODS[k]["base"] for k in p["cargo"]}
    p["cash"] = cash
    return g, p


def teardown_function(_fn):
    engine.configure(config.defaults())


def sail(g, p, dest):
    g.act("p1", {"type": "sail", "dest": dest, "orders": "run"}, present=["p1"])
    g.resolve("all_ready", {"p1"})


def sea(g, level):
    for k in g.s["weather"]:                          # the forecast holds (accuracy 1.0), so this is the sea
        g.s["weather"][k] = level


def no_yard_ports(p):
    return [k for k in PORTS if not engine.port_has(p, k, "shipyard")]


def test_bands_follow_the_score():
    setup()
    r = storm.rules()
    assert storm.band_of(r["heavy_at"] - 1) == "rough"
    assert storm.band_of(r["heavy_at"]) == "heavy"
    assert storm.band_of(r["savage_at"] - 1) == "heavy"
    assert storm.band_of(r["savage_at"]) == "savage"


def test_severity_grows_with_the_inputs():
    setup()
    g, p = new_game(cargo={"tea": 50})
    own = storm._dice(g, p)
    lo, _ = storm.severity(g, p, 1, 1.0, own)
    hi, _ = storm.severity(g, p, 3, 1.0, storm._dice(g, p))
    assert hi > lo
    sh = p["ships"][0]
    full = storm.severity(g, p, 2, 1.0, storm._dice(g, p))[0]
    sh["hull"] = SHIPS[sh["type"]]["hull"] // 3
    weak = storm.severity(g, p, 2, 1.0, storm._dice(g, p))[0]
    assert weak > full                              # a battered fleet is weaker


def test_rough_storm_scuffs_the_hull_only():
    setup(storm__base=[0, 20, 20, 20], storm__dice_min=1.0, storm__dice_max=1.0)
    g, p = new_game(cargo={"tea": 40})
    sea(g, 2)
    sail(g, p, "singapore" if "singapore" in PORTS else [k for k in PORTS if k != p["port"]][0])
    st = p.get("storm")
    assert st and st["band"] == "rough" and not st["card"]
    assert p["cargo"].get("tea") == 40 and not st["cargo"]
    assert st["guns_lost"] == 0 and st["landing"]["diverted"] is False


def test_heavy_storm_takes_hull_cargo_guns_and_lands_at_a_yard():
    setup(storm__base=[0, 50, 50, 50], storm__dice_min=1.0, storm__dice_max=1.0, storm__heavy_guns=1.0)
    g, p = new_game(cargo={"tea": 30, "silk": 10})
    p["ships"][0]["guns"] = 3
    sea(g, 2)
    dest = [k for k in PORTS if k != p["port"]][0]
    held = dict(p["cargo"])
    ship = p["ships"][0]
    full = SHIPS[ship["type"]]["hull"]
    sail(g, p, dest)
    st = p["storm"]
    assert st["band"] == "heavy" and st["card"]
    assert sum(p["cargo"].values()) < sum(held.values())
    assert st["hull_lost"] > 0 and ship["hull"] < full
    assert st["guns_lost"] == 3 and ship["guns"] == 0
    assert st["landing"]["diverted"] and st["landing"]["yard"]
    assert p["port"] == st["landing"]["port"]
    assert p["port"] not in (st["origin"], dest)
    # the cut screen's report reaches the client
    assert g.view("p1")["me"]["storm"]["band"] == "heavy"


def test_savage_storm_lands_where_there_is_no_yard():
    setup(storm__base=[0, 120, 120, 120], storm__dice_min=1.0, storm__dice_max=1.0)
    for seed in range(1, 7):
        g, p = new_game(seed=seed, cargo={"tea": 100})
        sea(g, 3)
        dest = [k for k in PORTS if k != p["port"]][0]
        sail(g, p, dest)
        st = p.get("storm")
        if not p["ships"]:
            continue
        assert st["band"] == "savage"
        assert st["landing"]["diverted"]
        yards = [x for x in storm.rank_ports(g, p, st["origin"], dest, p["cargo"])[0] if x["yard"]]
        if len(yards) < st["landing"]["of"]:
            assert not st["landing"]["yard"]          # the worst-ranked of the candidates, and it has no yard


def test_savage_hurts_more_than_heavy():
    def run(base):
        setup(storm__base=[0, base, base, base], storm__dice_min=1.0, storm__dice_max=1.0)
        g, p = new_game(seed=3, cargo={"tea": 40})
        p["ships"][0]["guns"] = 3
        sea(g, 2)
        sail(g, p, [k for k in PORTS if k != p["port"]][0])
        return p.get("storm")
    heavy, savage = run(50), run(130)
    assert heavy["band"] == "heavy" and savage["band"] == "savage"
    assert savage["hull_lost"] >= heavy["hull_lost"]
    assert savage["cargo_cost"] >= heavy["cargo_cost"]


def test_books_and_events_keep_their_shape():
    setup(storm__base=[0, 50, 50, 50], storm__dice_min=1.0, storm__dice_max=1.0)
    g, p = new_game(cargo={"tea": 100})
    sea(g, 2)
    sail(g, p, [k for k in PORTS if k != p["port"]][0])
    kinds = [e["kind"] for e in g.events] if hasattr(g, "events") else []
    log = " ".join(p["log"])
    assert "storm" in log.lower()
    assert p["storm"]["cargo_cost"] >= 0


def test_a_port_without_a_yard_only_patches_to_half():
    setup()
    g, p = new_game()
    bare = no_yard_ports(p)
    assert bare, "the default map has ports with no shipyard"
    p["port"] = bare[0]
    ship = p["ships"][0]
    full = SHIPS[ship["type"]]["hull"]
    ship["hull"] = max(1, full // 5)
    g.act("p1", {"type": "repair", "index": "all"}, present=["p1"])
    assert ship["hull"] == int(full * storm.rules()["patch_max"])
    try:
        g.act("p1", {"type": "repair", "index": "all"}, present=["p1"])
        raise AssertionError("a second patch should be refused")
    except engine.GameError as e:
        assert "shipyard" in str(e).lower()
    me = g.view("p1")["me"]
    assert me["ships"][0]["needs_yard"] and me["ships"][0]["repair"] == 0


def test_a_yard_mends_her_whole():
    setup()
    g, p = new_game()
    yard = [k for k in PORTS if engine.port_has(p, k, "shipyard")][0]
    p["port"] = yard
    ship = p["ships"][0]
    ship["hull"] = 1
    g.act("p1", {"type": "repair", "index": "all"}, present=["p1"])
    assert ship["hull"] == SHIPS[ship["type"]]["hull"]


def test_patch_rule_can_be_switched_off():
    setup(storm__patch_max=1.0)
    g, p = new_game()
    p["port"] = no_yard_ports(p)[0]
    ship = p["ships"][0]
    ship["hull"] = 1
    g.act("p1", {"type": "repair", "index": "all"}, present=["p1"])
    assert ship["hull"] == SHIPS[ship["type"]]["hull"]


def test_ack_clears_the_report():
    setup(storm__base=[0, 50, 50, 50], storm__dice_min=1.0, storm__dice_max=1.0)
    g, p = new_game(cargo={"tea": 50})
    sea(g, 2)
    sail(g, p, [k for k in PORTS if k != p["port"]][0])
    assert p.get("storm")
    g.act("p1", {"type": "storm_ack"}, present=["p1"])
    assert not p.get("storm") and g.view("p1")["me"]["storm"] is None


def test_off_means_the_flat_damage_again():
    setup(storm__enabled=False)
    g, p = new_game(cargo={"tea": 50})
    sea(g, 2)
    sail(g, p, [k for k in PORTS if k != p["port"]][0])
    assert not p.get("storm") and p["cargo"].get("tea") == 50


def test_every_wording_line_exists():
    import strings
    en = strings.EN
    for name, n in storm.LINES.items():
        for i in range(n):
            assert "storm.{}.{}".format(name, i) in en, (name, i)
    family = strings.FAMILY
    for k in storm.LINES:
        pass
    assert "storm.btn" in en and "l.storm_cargo" in en and "e.repair_yard" in en
