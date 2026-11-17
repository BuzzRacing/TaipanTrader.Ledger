"""Captains: saved profiles with a PIN, Houses, pictures in the Media Library and a career record.

Run from the project folder:  python tests/captains_test.py
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
from engine import Game, GameError  # noqa: E402

TMP = tempfile.mkdtemp(prefix="captains-test-")


def fresh():
    """Point the Captains file (and the Media Library) at a scratch folder."""
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


def anne(pin="4321", houses=None):
    return captains.save_captain({"name": "Anne Bonny", "title": "the Red", "pin": pin,
                                  "houses": houses or [{"name": "Bonny & Co.", "color": "#aa2233"},
                                                       {"name": "Red Flag Trading", "color": "#222222"}]})


def test_two_guests_are_always_there():
    fresh()
    caps = captains.public_list({})
    guests = [c for c in caps if c["guest"]]
    assert len(guests) == 2
    assert all("pin" not in c for c in caps)                 # the join screen never sees a PIN
    c, h = captains.verify(guests[0]["cid"], "", None, "1.2.3.4")   # guests need no PIN
    assert h["name"]
    try:
        captains.delete_captain(guests[0]["cid"])
        assert False, "guests can't be deleted"
    except captains.CaptainError:
        pass


def test_pin_rules():
    fresh()
    a = anne()
    for bad in ("12", "12ab", "123456789"):
        try:
            captains.save_captain(dict(a, pin=bad))
            assert False, bad
        except captains.CaptainError:
            pass
    try:
        captains.save_captain({"name": "Mary Read", "pin": "4321", "houses": [{"name": "Read"}]})
        assert False, "duplicate PIN"
    except captains.CaptainError:
        pass
    try:
        captains.save_captain({"name": "anne bonny", "pin": "1111", "houses": [{"name": "X"}]})
        assert False, "duplicate name"
    except captains.CaptainError:
        pass
    # Changing the PIN keeps the id (and so the history).
    b = captains.save_captain(dict(a, pin="9999"))
    assert b["cid"] == a["cid"] and b["pin"] == "9999"


def test_wrong_pin_and_lockout():
    fresh()
    a = anne()
    try:
        captains.verify(a["cid"], "0000", None, "10.0.0.9")
        assert False
    except captains.CaptainError:
        pass
    c, h = captains.verify(a["cid"], "4321", a["houses"][1]["hid"], "10.0.0.9")
    assert h["name"] == "Red Flag Trading"
    for _ in range(5):
        try:
            captains.verify(a["cid"], "1", None, "10.0.0.8")
        except captains.CaptainError:
            pass
    try:
        captains.verify(a["cid"], "4321", None, "10.0.0.8")
        assert False, "locked out for a minute"
    except captains.CaptainError as e:
        assert "Too many" in str(e)


def test_join_as_captain_and_seat_is_protected():
    fresh()
    a = anne()
    game = Game(seed=3)
    c, h = captains.verify(a["cid"], "4321", None, "x")
    token = game.join(c["name"], h["name"], captain=c["cid"])
    pid = game.pid_for_token(token)
    p = game.s["players"][pid]
    assert p["captain"] == a["cid"] and p["firm"] == "Bonny & Co."
    # Someone typing the same name can't take the seat; the Captain can.
    try:
        game.join("Anne Bonny", "x")
        assert False
    except GameError:
        pass
    assert game.join("Anne Bonny", "", captain=a["cid"]) == token
    captains.link_game(a["cid"], game.s["game_id"], pid, h)
    captains.link_game(a["cid"], game.s["game_id"], pid, h)     # once per game
    got = captains.get(a["cid"])
    assert len(got["games"]) == 1 and captains.links(got) == {game.s["game_id"]: pid}


def test_time_at_the_screen():
    fresh()
    a = anne()
    captains.link_game(a["cid"], "g1", "p1", a["houses"][0])
    captains.tick([(a["cid"], "g1")], 30)
    captains.tick([(a["cid"], "g1")], 15)
    captains.flush(force=True)
    assert captains.get(a["cid"])["games"][0]["seconds"] == 45


def test_houses_and_pictures_live_in_the_media_library():
    fresh()
    a = anne()
    hid = a["houses"][0]["hid"]
    assert "Bonny & Co." in captains.prompt_for(a, a["houses"][0])
    caps, houses = captains.media_subjects()
    assert [hid, "Bonny & Co. (Anne Bonny)"] in houses
    assert "house" in media.KINDS and "captain" in media.KINDS
    png = b"\x89PNG\r\n\x1a\n" + b"\0" * 64
    one = media.add_bytes(png, ".png", "house", hid, ["crest"], source="generated")
    two = media.add_bytes(png, ".png", "house", hid, ["crest"], source="generated")
    assert captains._pick("house", hid, {}, family=False) == one["url"]        # the first becomes the chosen one
    media.update([two["id"]], {"primary": True})                                # star another in the library
    assert captains._pick("house", hid, {}, family=False) == two["url"]
    assert two["url"] in captains.urls_in_use({})
    view = [c for c in captains.public_list({}) if c["cid"] == a["cid"]][0]
    assert view["houses"][0]["image"] == two["url"]


def test_retired_hidden_from_join():
    fresh()
    a = anne()
    captains.save_captain(dict(a, retired=True))
    assert a["cid"] not in [c["cid"] for c in captains.public_list({})]
    try:
        captains.verify(a["cid"], "4321", None, "y")
        assert False
    except captains.CaptainError:
        pass


if __name__ == "__main__":
    try:
        for name, fn in sorted(globals().items()):
            if name.startswith("test_") and callable(fn):
                fn()
                print("ok", name)
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
