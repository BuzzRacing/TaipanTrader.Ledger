"""Checks that screens take turns to speak and never talk over each other.

    python tests/voicefloor_test.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import voicefloor  # noqa: E402

FAILS = []


def check(cond, what):
    if not cond:
        FAILS.append(what)
        print("FAIL:", what)


def fresh():
    f = voicefloor.Floor()
    f.own = {"127.0.0.1", "::1", "localhost", "192.168.1.213"}
    return f


def test_one_at_a_time():
    f = fresh()
    check(f.ask("127.0.0.1", "player", "take", now=0)["granted"], "first screen gets the turn")
    check(not f.ask("127.0.0.1", "board", "take", now=0.1)["granted"], "second screen on the same computer waits")
    check(f.ask("127.0.0.1", "player", "take", now=0.2)["granted"], "the speaker keeps its turn for its next line")
    f.ask("127.0.0.1", "player", "free", now=1)
    check(f.ask("127.0.0.1", "board", "take", now=1.1)["granted"], "the waiting screen speaks once the turn is free")


def test_same_computer_by_any_address():
    f = fresh()
    f.ask("127.0.0.1", "player", "take", now=0)
    check(not f.ask("::1", "board", "take", now=0)["granted"], "localhost over IPv6 is the same computer")
    check(not f.ask("192.168.1.213", "x", "take", now=0)["granted"], "the server's LAN address is the same computer")
    check(not f.ask("::ffff:127.0.0.1", "y", "take", now=0)["granted"], "IPv4-mapped localhost is the same computer")


def test_other_devices_have_their_own_turn():
    f = fresh()
    f.ask("127.0.0.1", "player", "take", now=0)
    check(f.ask("192.168.1.50", "ipad", "take", now=0)["granted"], "an iPad has its own speakers and its own turn")


def test_first_come_first_served():
    f = fresh()
    f.ask("127.0.0.1", "a", "take", now=0)
    f.ask("127.0.0.1", "b", "take", now=0.1)
    f.ask("127.0.0.1", "c", "take", now=0.2)
    f.ask("127.0.0.1", "a", "free", now=1)
    check(not f.ask("127.0.0.1", "c", "take", now=1.05)["granted"], "a later screen cannot jump the line")
    check(f.ask("127.0.0.1", "b", "take", now=1.1)["granted"], "the screen that asked first goes next")


def test_dead_screen_loses_the_turn():
    f = fresh()
    f.ask("127.0.0.1", "gone", "take", now=0)
    f.ask("127.0.0.1", "gone", "renew", now=2)
    check(not f.ask("127.0.0.1", "board", "take", now=6)["granted"], "a renewed turn is still held")
    check(f.ask("127.0.0.1", "board", "take", now=2 + voicefloor.LEASE + 0.1)["granted"],
          "a screen that stopped renewing loses the turn")


def test_stale_waiter_leaves_the_line():
    f = fresh()
    f.ask("127.0.0.1", "a", "take", now=0)
    f.ask("127.0.0.1", "closed", "take", now=0.1)     # asked once, then the window closed
    f.ask("127.0.0.1", "b", "take", now=0.2)
    for t in (1, 2, 3, 4):
        f.ask("127.0.0.1", "b", "take", now=t)
        f.ask("127.0.0.1", "a", "renew", now=t)
    f.ask("127.0.0.1", "a", "free", now=4.5)
    check(f.ask("127.0.0.1", "b", "take", now=4.6)["granted"], "a closed window does not block the line")


def test_headline_read_once_per_device():
    f = fresh()
    check(f.ask("127.0.0.1", "board", "take", clip="news1", now=0)["granted"], "board reads the headline")
    f.ask("127.0.0.1", "board", "free", now=3)
    r = f.ask("127.0.0.1", "player", "take", clip="news1", now=3.1)
    check(r["skip"] and not r["granted"], "the player window skips the headline the board just read")
    check(f.ask("127.0.0.1", "player", "take", clip="news2", now=3.2)["granted"], "a new headline is read")
    check(f.ask("192.168.1.50", "ipad", "take", clip="news1", now=3.3)["granted"], "another device still hears it")


def test_no_id_never_blocks():
    f = fresh()
    f.ask("127.0.0.1", "a", "take", now=0)
    check(f.ask("127.0.0.1", "", "take", now=0)["granted"], "a request without a screen id is let through")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("voicefloor: {} failure(s)".format(len(FAILS)) if FAILS else "voicefloor: all good")
    sys.exit(1 if FAILS else 0)
