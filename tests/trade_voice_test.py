"""Checks the comprador's buy and sell banks (trade_text.py): every line is matched back to its own key,
read by the comprador with no amounts, never repeats until the bank is heard, and family screens get
clean lines. Run from the game folder: python tests/trade_voice_test.py"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import cast          # noqa: E402
import config        # noqa: E402
import strings       # noqa: E402
import trade_text    # noqa: E402
import voice         # noqa: E402

NAMES = re.compile(r"\{(\w+)\}")
AMOUNTS = {"qty", "cost", "gain"}


def test_banks_are_big_and_unique():
    for prefix, least in (("m.bought", 20), ("m.sold", 20), ("m.sold_loss", 8), ("m.sold_store", 8)):
        n = len([k for k in trade_text.KEYS if k.rsplit(".", 1)[0] == prefix])
        assert n >= least, (prefix, n)
    for table in (strings.EN, strings.FAMILY, cast.SAY, cast.SAY_FAMILY):
        vals = [table[k] for k in trade_text.KEYS]
        assert len(set(vals)) == len(vals), "duplicate line"
    for k in trade_text.KEYS:
        assert strings.FAMILY[k] != strings.EN[k], k
        assert cast.LINE_DEFAULTS[k] == "comprador", k
        for spoken in (cast.SAY[k], cast.SAY_FAMILY[k]):
            assert not set(NAMES.findall(spoken)) & AMOUNTS, (k, spoken)
            assert set(NAMES.findall(spoken)) <= set(NAMES.findall(strings.EN[k])), k


def test_voice_matches_each_line_and_drops_amounts():
    for rating in ("historical", "family"):
        cfg = config.defaults()
        cfg["content"]["rating"] = rating
        text = strings.resolve(cfg)
        plan = voice.Planner()
        plan.configure(cfg, text)
        for k in trade_text.KEYS + ["m.bought", "m.sold", "m.sold_store", "m.bought_lot"]:
            shown = text[k].format(qty=27, good="Tea", cost="$2,700", gain="$2,700")
            got, fields = plan.matcher.match(shown)
            assert got == k, (rating, k, got)
            if k in trade_text.EN:
                said = plan.spoken(got, fields, shown)
                assert "27" not in said and "Tea" in said, (rating, k, said)
                assert cast.speaker_for(cfg, k) == "comprador", k


def _game():
    import engine
    g = engine.Game.__new__(engine.Game)
    return engine, g


def test_draw_never_repeats_within_a_bank():
    engine, g = _game()
    p = {"name": "Anthony", "firm": "Test House"}
    n = len(g._bank("m.bought"))
    seen = [g._trade_say(p, "m.bought") for _ in range(n)]
    assert len(set(seen)) == n, seen
    nxt = g._trade_say(p, "m.bought")
    assert nxt != seen[-1]
    # the loss bank falls back to the sale bank, then to the plain line
    assert g._trade_say(p, "m.sold_loss", "m.sold").startswith("m.sold_loss.")
    assert g._trade_say(p, "m.nothing_here", "m.sold").startswith("m.sold.")
    assert g._trade_say(p, "m.nothing_here") == "m.nothing_here"


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("OK: trade voice checks passed")


if __name__ == "__main__":
    main()
