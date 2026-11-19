"""The House is its id (Options, 19 Nov 2026): renaming a House changes its name everywhere, past log
lines, news and records included, and never changes a roll of the dice. Also this screen's own
Family-friendly choice (cargo by family names on one screen only).

Run from the project folder:  python tests/house_test.py
"""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import captains  # noqa: E402
import config  # noqa: E402
import engine  # noqa: E402
import media  # noqa: E402
import stats  # noqa: E402
from engine import Game, GameError  # noqa: E402

TMP = tempfile.mkdtemp(prefix="house-test-")


def fresh():
    captains.DIR = os.path.join(TMP, "captains")
    captains.FILE = os.path.join(captains.DIR, "captains.json")
    if os.path.isdir(captains.DIR):
        shutil.rmtree(captains.DIR)
    captains.reset_cache()
    media.LIB_FILE = os.path.join(TMP, "media.json")
    media.MEDIA_DIR = os.path.join(TMP, "media")
    media.WEB = TMP
    if os.path.exists(media.LIB_FILE):
        os.remove(media.LIB_FILE)
    media._cache.update(mtime=None, lib=None)
    base = config.defaults()
    base["rules"]["start"]["where"] = "home"
    engine.configure(base)


def table():
    game = Game(seed=7)
    a = game.pid_for_token(game.join("Ann", "Bonny Traders"))
    b = game.pid_for_token(game.join("Mary", "Read & Daughters"))
    game.act(a, {"type": "start"})
    return game, game.s["players"][a], game.s["players"][b]


def test_rename_changes_past_text_and_only_that_house():
    fresh()
    game, a, b = table()
    a["log"].append("Bonny Traders sold tea in Canton.")
    b["log"].append("You passed Bonny Traders off Macau. Read & Daughters held course.")
    game.s["news"].insert(0, "Jan 1860: Bonny Traders made a fortune; Bonny Traders Ltd did not.")
    events = []
    game.on_event = events.append
    msg = game.act(a["id"], {"type": "house", "name": "Bonny Trading"})
    assert "Bonny Trading" in msg
    assert a["firm"] == "Bonny Trading" and b["firm"] == "Read & Daughters"
    assert a["log"][-1] == "Bonny Trading sold tea in Canton."
    assert b["log"][-1].startswith("You passed Bonny Trading off Macau. Read & Daughters"), b["log"][-1]
    assert game.s["news"][0] == "Jan 1860: Bonny Trading made a fortune; Bonny Trading Ltd did not."
    v = game.view(a["id"])
    assert v["me"]["firm"] == "Bonny Trading"
    assert [q["firm"] for q in v["players"]] == ["Bonny Trading", "Read & Daughters"]
    ev = [e for e in events if e.get("type") == "house"]
    assert ev and ev[0]["firm"] == "Bonny Trading" and ev[0]["old"] == "Bonny Traders" and ev[0]["cat"] == "players"
    print("ok test_rename_changes_past_text_and_only_that_house")


def test_rename_refusals():
    fresh()
    game, a, b = table()
    for bad in ("", "   "):
        try:
            game.act(a["id"], {"type": "house", "name": bad})
            raise AssertionError("an empty name was taken")
        except GameError:
            pass
    try:
        game.act(a["id"], {"type": "house", "name": "read & daughters"})
        raise AssertionError("another house's name was taken")
    except GameError:
        pass
    assert a["firm"] == "Bonny Traders"
    assert "already" in game.act(a["id"], {"type": "house", "name": "Bonny Traders"})
    long = game.act(a["id"], {"type": "house", "name": "X" * 60})
    assert a["firm"] == "X" * 28, long
    print("ok test_rename_refusals")


def test_dice_seeds_keep_the_first_name():
    fresh()
    game, a, _b = table()
    first = engine.seed_firm(a)
    game.act(a["id"], {"type": "house", "name": "Spelt Right & Co."})
    game.act(a["id"], {"type": "house", "name": "Spelt Right Again"})
    assert engine.seed_firm(a) == first == "Bonny Traders" and a["firm"] == "Spelt Right Again"
    # A renamed house rolls the Registrar's tip exactly as before.
    g1, a1, _ = table()
    g2, a2, _ = table()
    g2.s["game_id"] = g1.s["game_id"]
    g2.act(a2["id"], {"type": "house", "name": "Renamed"})
    for g, p in ((g1, a1), (g2, a2)):
        p["port"] = p["home"]
        p["cargo"] = {"tea": 10}
        p["known"] = {}
    t1, t2 = g1._registrar_tip(a1), g2._registrar_tip(a2)
    assert (t1 or {}).get("port") == (t2 or {}).get("port") and (t1 or {}).get("good") == (t2 or {}).get("good"), (t1, t2)
    print("ok test_dice_seeds_keep_the_first_name")


def test_captain_house_rename_and_records():
    fresh()
    c = captains.save_captain({"name": "Anne Bonny", "pin": "4321",
                               "houses": [{"name": "Bonny & Co.", "color": "#aa2233"}, {"name": "Second House"}]})
    hid = c["houses"][0]["hid"]
    captains.link_game(c["cid"], "g1", "p1", c["houses"][0])
    captains.link_game(c["cid"], "g2", "p3", c["houses"][0])
    before, after = captains.update_house(c["cid"], hid, "Bonny & Sons", "#112233")
    assert before["name"] == "Bonny & Co." and after["name"] == "Bonny & Sons" and after["color"] == "#112233"
    saved = captains.get(c["cid"])
    assert all(g["house"] == "Bonny & Sons" for g in saved["games"])
    assert captains.firm_names("g1") == {"p1": "Bonny & Sons"} and captains.firm_names("g2") == {"p3": "Bonny & Sons"}
    try:
        captains.update_house(c["cid"], hid, "second house")
        raise AssertionError("two Houses of one Captain got the same name")
    except captains.CaptainError:
        pass
    v1 = captains.names_version()
    captains.update_house(c["cid"], hid, "Bonny & Daughters")
    assert captains.names_version() != v1
    # The seat finds its House by id, else by this game's link, else by name.
    assert captains.house_for_seat({"id": "p1", "captain": c["cid"], "firm": "whatever"}, "g1") == hid
    assert captains.house_for_seat({"id": "p9", "captain": c["cid"], "firm": "Second House"}, "gx") == c["houses"][1]["hid"]
    assert captains.house_for_seat({"id": "p9", "firm": "Bonny & Daughters"}, "g1") == ""
    print("ok test_captain_house_rename_and_records")


def test_records_show_the_name_now():
    events = [{"type": "seat_new", "pid": "p1", "name": "Ann", "firm": "Old Name"},
              {"type": "seat_new", "pid": "p2", "name": "Mary", "firm": "Other"},
              {"cat": "snapshot", "firms": [{"id": "p1", "name": "Ann", "firm": "Old Name"}]},
              {"type": "house", "cat": "players", "pid": "p2", "firm": "Other Renamed", "old": "Other"}]
    ps = {p["id"]: p["firm"] for p in stats._players(events, {})}
    assert ps == {"p1": "Old Name", "p2": "Other Renamed"}, ps
    stats.HOUSE_NAMES = lambda gid: {"p1": "New Name"} if gid == "g1" else {}
    try:
        ps = {p["id"]: p["firm"] for p in stats._players(events, {}, "g1")}
        assert ps == {"p1": "New Name", "p2": "Other Renamed"}, ps
        ps = {p["id"]: p["firm"] for p in stats._players(events, {}, "g2")}
        assert ps["p1"] == "Old Name"
    finally:
        stats.HOUSE_NAMES = None
    print("ok test_records_show_the_name_now")


def test_server_sync_and_family_screen():
    fresh()
    import server  # noqa: E402
    server.SAVE_FILE = os.path.join(TMP, "game.json")
    server.SAVES = TMP
    c = captains.save_captain({"name": "Anne Bonny", "pin": "4321", "houses": [{"name": "Bonny & Co."}]})
    h = c["houses"][0]
    game = Game(seed=3)
    token = game.join("Anne Bonny", h["name"], captain=c["cid"])
    pid = game.pid_for_token(token)
    game.s["players"][pid]["hid"] = h["hid"]
    game.s["players"][pid]["log"].append("Bonny & Co. came into port.")
    hub = server.Hub(game, "http://x")
    with hub.cond:
        assert hub.sync_houses() is False                 # nothing to change
    captains.update_house(c["cid"], h["hid"], "Bonny & Sons")
    with hub.cond:
        assert hub.sync_houses() is True
    p = game.s["players"][pid]
    assert p["firm"] == "Bonny & Sons" and p["log"][-1] == "Bonny & Sons came into port."
    # A seat linked by name only gets its House id written on it.
    p.pop("hid")
    with hub.cond:
        hub.sync_houses()
    assert p["hid"] == h["hid"]

    # This screen's Family-friendly: family cargo names in words, ids untouched.
    cfg = engine.CFG
    goods = {k: g for k, g in cfg["goods"].items() if g.get("family_name") and g["family_name"] != g["name"]}
    assert goods, "no cargo has a family name"
    key, g = next(iter(goods.items()))
    view = {"me": {"cargo": {key: 5}, "log": ["Sold 5 {} in Canton.".format(g["name"]),
                                              "the {} trade is hot".format(g["name"].lower())],
                   "good": key, "label": g["name"]}}
    out = server.family_view(view)
    assert out["me"]["cargo"] == {key: 5} and out["me"]["good"] == key
    assert out["me"]["log"][0] == "Sold 5 {} in Canton.".format(g["family_name"]), out["me"]["log"]
    assert out["me"]["log"][1] == "the {} trade is hot".format(g["family_name"].lower())
    assert out["me"]["label"] == g["family_name"]
    fcfg, data = server.family_screen(cfg, {"goods": engine.GOODS, "text": dict(engine.TEXT),
                                                 "tokens": dict(engine.TOKENS), "rating": cfg["content"]["rating"]})
    assert fcfg["content"]["rating"] == "family" and cfg["content"]["rating"] != "family"
    assert data["goods"][key]["name"] == g["family_name"] and engine.GOODS[key]["name"] == g["name"]
    assert data["screen_family"] and data["rating"] == "family"
    print("ok test_server_sync_and_family_screen")


if __name__ == "__main__":
    try:
        test_rename_changes_past_text_and_only_that_house()
        test_rename_refusals()
        test_dice_seeds_keep_the_first_name()
        test_captain_house_rename_and_records()
        test_records_show_the_name_now()
        test_server_sync_and_family_screen()
        print("OK: House id checks passed (6 tests)")
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
