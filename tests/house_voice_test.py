"""Checks the house voice (house_voice.py): every rewritten line keeps its {names}, is read by the voice
in the new style, and the family-friendly wording still gives the old, clean line and its old clip.
Run from the game folder: python tests/house_voice_test.py"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import cast          # noqa: E402
import config        # noqa: E402
import house_voice   # noqa: E402
import strings       # noqa: E402
import voice         # noqa: E402

NAMES = re.compile(r"\{(\w+)\}")
AMOUNTS = {"amount", "cost", "cash", "qty", "fine", "total", "price", "tax", "paid", "lost", "gain", "value",
           "months", "rate", "debt", "stake", "worth", "declared", "suggest"}


def names(t):
    return sorted(set(NAMES.findall(t)))


def test_lines_keep_their_names():
    assert len(house_voice.LINES) > 500
    for key, line in house_voice.LINES.items():
        assert key in strings.EN, key
        assert strings.EN[key] == line, key
        assert names(line) == names(house_voice.ORIGINAL[key]), key


def test_old_wording_is_the_family_wording():
    for key, old in house_voice.ORIGINAL.items():
        assert key in strings.FAMILY, key
        if strings.FAMILY[key] != old:            # a line that already had family wording keeps it
            continue
        assert strings.FAMILY[key] != strings.EN[key], key


def test_spoken_versions_follow_the_new_lines():
    for key in house_voice.LINES:
        if key in cast.SAY:
            if key.startswith("m.gift."):
                assert cast.SAY[key] in strings.EN[key], key
            else:
                assert key in house_voice.SPOKEN and cast.SAY[key] == house_voice.SPOKEN[key], key
    for key, spoken in house_voice.SPOKEN.items():
        assert not (set(names(spoken)) & AMOUNTS), (key, spoken)
        assert set(names(spoken)) <= set(names(strings.EN[key])), key


def _planner(rating):
    cfg = config.defaults()
    cfg["content"]["rating"] = rating
    text = strings.resolve(cfg)
    plan = voice.Planner()
    plan.configure(cfg, text)
    return plan, text


def test_voice_reads_the_new_style_and_family_the_old():
    for rating in ("historical", "family"):
        plan, text = _planner(rating)
        for key in ("m.bought", "l.robbed", "l.sank_all", "m.gift.warm.3", "l.customs_welcome.4", "m.ship_joined"):
            fields = {n: "Rice" for n in names(text[key])}
            shown = re.sub(r"\{(\w+)\}", lambda m: "27" if m.group(1) in AMOUNTS else fields[m.group(1)], text[key])
            k, _f = plan.matcher.match(shown)
            assert k == key, (rating, key, k)
            said = plan.spoken(k, _f, shown)
            new_style = key in house_voice.LINES and text[key] == house_voice.LINES[key]
            assert new_style == (rating != "family") or key not in house_voice.ORIGINAL, (rating, key)
            if key in cast.SAY or (rating == "family" and key in cast.SAY_FAMILY):
                assert "27" not in said, (rating, key, said)


def test_delivery_carries_the_house_style():
    ch = {"voice_id": "x", "delivery": "low and slow"}
    on = voice._params("Hello", ch, {"model_id": "inworld-tts-2", "temperature": 1.0})
    assert on["delivery"].startswith("low and slow; ") and house_voice.DELIVERY in on["delivery"]
    flash = voice._params("Hello", ch, {"model_id": "inworld-tts-2-flash", "temperature": 1.0})
    assert flash["delivery"] == ""                 # Flash ignores notes, so its clips are unchanged


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("OK: house voice checks passed")


if __name__ == "__main__":
    main()
