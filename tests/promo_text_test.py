"""Checks the Promotion Story's wording (promo_text.py): the caption banks reach strings.EN, every line uses only
the names the story fills in, and the story's own keys sit in the "promo" group of Language & Text.
Run from the game folder: python tests/promo_text_test.py"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import promo_text   # noqa: E402
import strings      # noqa: E402

NAMES = re.compile(r"\{(\w+)\}")
FILLED = {"port", "name", "firm", "rank"}          # what promotion.js passes to the caption banks


def test_banks_reach_the_game_wording():
    for bank in promo_text.BANKS:
        keys = sorted(k for k in strings.EN if k.startswith(bank + "."))
        assert len(keys) >= 6, (bank, len(keys))
    for key, line in promo_text.EN.items():
        assert strings.EN[key] == line, key


def test_lines_only_use_names_the_story_fills_in():
    for key, line in promo_text.EN.items():
        assert set(NAMES.findall(line)) <= FILLED, (key, line)


def test_story_keys_sit_in_their_own_group():
    groups = {g[0] for g in strings.GROUPS}
    assert "promo" in groups
    assert all(k.split(".")[0] == "promo" for k in promo_text.EN)


def test_the_mayors_own_congratulations_are_untouched():
    # the captions are narration; her spoken words stay m.promote.N / m.promote_top.N
    assert not any(k.startswith("m.promote") for k in promo_text.EN)
    assert sum(1 for k in strings.EN if k.startswith("m.promote.")) >= 30


if __name__ == "__main__":
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("ok  ", name)
            except AssertionError as e:
                failed += 1
                print("FAIL", name, e)
    print("passed" if not failed else f"{failed} failed")
    sys.exit(1 if failed else 0)
