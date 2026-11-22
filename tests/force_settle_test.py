"""A host "force" resolves the month inside Game.act. A declaration nobody made is then filed at
month's end (_settle_customs); that used to leave Game._hold as None under the running act, which
raised a TypeError (about half of the journalled bot games in Game 5).

Run from the project folder:  python -m pytest tests/force_settle_test.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import config  # noqa: E402
import customs_test as ct  # noqa: E402
import engine  # noqa: E402


def test_force_with_an_open_declaration_does_not_crash_and_keeps_the_events():
    base = ct.no_spot(config.defaults())
    base["rules"]["start"]["where"] = "home"
    engine.configure(base)
    for seed in range(40):
        g, p = ct.arrive(seed, "calcutta")
        cu = p.get("customs")
        if not p["ships"] or not cu or cu["status"] != "declare":
            continue
        events = []
        g.on_event = events.append
        g.act("p1", {"type": "force"}, present=["p1"])          # used to raise TypeError
        kinds = [e["type"] for e in events]
        assert g._hold is None                                   # nothing left queued after the act
        assert "force" in kinds, kinds                           # the outer act's own event still goes out
        assert "customs_auto" in kinds, kinds                    # and so does the honest filing
        return
    raise AssertionError("no seed reached an open declaration")
