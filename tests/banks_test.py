"""Checks the Dialogue Banks catalogue (banks.py): banks are found from the numbered lines, each belongs to the
right persona or story and surface, the audit flags the right things, Language & Text overrides show, and the
catalogue never changes the wording.
Run from the game folder: python tests/banks_test.py"""
import copy
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import banks         # noqa: E402
import config        # noqa: E402
import manual_text   # noqa: E402
import strings       # noqa: E402

CFG = config.DEFAULTS


def by_id(view):
    return {b["id"]: b for b in view["banks"]}


def test_numbered_banks_are_contiguous():
    view = banks.view(CFG)
    assert view["ok"] and len(view["banks"]) > 300
    for b in view["banks"]:
        if b["numbered"]:
            assert [x["n"] for x in b["lines"]] == list(range(b["size"])), b["id"]
        else:
            assert b["size"] == 1 and b["kind"] == "spoken", b["id"]


def test_every_bank_has_an_owner_and_surface():
    view = banks.view(CFG)
    owners = {o["id"] for o in view["owners"]}
    for b in view["banks"]:
        assert b["owner"] in owners and b["owner_name"], b["id"]
        assert b["surface"] in dict(banks.SURFACES), b["id"]
    assert view["summary"]["lines"] == sum(o["lines"] for o in view["owners"])
    assert view["summary"]["banks"] == sum(o["banks"] for o in view["owners"])


def test_surfaces_and_speakers():
    b = by_id(banks.view(CFG))
    assert b["m.borrowed.easy"]["owner"] == "lender" and b["m.borrowed.easy"]["surface"] == "game"
    assert b["gm.month_open"]["owner"] == "gamemaster" and b["gm.month_open"]["surface"] == "table"
    for key, who in manual_text.SPEAKER.items():
        if key.endswith(".open.0"):
            bank = b[key.rsplit(".", 1)[0]]
            assert bank["owner"] == who and bank["surface"] == "manual" and bank["kind"] == "spoken", key
    assert b["man.money.how"]["kind"] == "written"
    speech = [x for x in b.values() if x["id"].startswith("dash.whisper.") and x["id"].endswith(".speech")]
    assert speech and all(x["owner"] == banks.DASH_ANY and x["surface"] == "dashboard" for x in speech)


def test_officers_and_wardens_group_together():
    view = banks.view(CFG)
    ids = {o["id"] for o in view["owners"]}
    assert "officers" in ids and "wardens" in ids
    assert all(b["owner"] == "officers" for b in view["banks"] if "officer_" in b["id"] and b["id"].startswith("l.customs_welcome."))


def test_audit_flags():
    spicy = {"a.0": "Hello {name}", "a.1": "Hello {name}", "a.2": "Pay {amount}", "a.3": "x" * 300, "a.4": ""}
    clean = {"a.0": "Hi {name}", "a.2": "Pay now", "a.3": "y", "a.4": ""}
    seen = set()
    rows = {k: banks._line(k, i, spicy, clean, True, seen) for i, k in enumerate(spicy)}
    assert rows["a.0"]["flags"] == []
    assert rows["a.1"]["flags"] == ["no_clean", "dup"]
    assert rows["a.2"]["flags"] == ["fields"]
    assert "long" in rows["a.3"]["flags"]
    assert "empty" in rows["a.4"]["flags"]
    assert not banks._line("a.0", 0, {"a.0": "Same"}, {"a.0": "Same"}, True, set())["flags"]
    assert banks._line("a.0", 0, {"a.0": "Same"}, {"a.0": "Same"}, True, set())["same"]


def test_language_overrides_show():
    key = "m.borrowed.easy.0"
    lang = {"strings": {key: "Edited spicy"}, "family": {key: "Edited clean"}}
    line = by_id(banks.view(CFG, lang))["m.borrowed.easy"]["lines"][0]
    assert line["spicy"] == "Edited spicy" and line["clean"] == "Edited clean" and line["twin"]


def test_view_is_read_only_and_json():
    before = (copy.deepcopy(strings.EN), copy.deepcopy(strings.FAMILY))
    view = banks.view(CFG)
    assert json.loads(json.dumps(view))["ok"]
    assert (strings.EN, strings.FAMILY) == before


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("OK: dialogue bank checks passed")


if __name__ == "__main__":
    main()
