"""No modern, heist or aviation wording in any saved Crimson Ledger picture prompt (24 Nov 2026)."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import theme_guard  # noqa: E402

FILES = ("config/settings.json", "config/artbible_examples.json")


def prompts(node, path=""):
    """Every text under a key with 'prompt' in its path, with where it was found."""
    if isinstance(node, dict):
        for k, v in node.items():
            yield from prompts(v, path + "/" + k)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from prompts(v, "{}/{}".format(path, i))
    elif isinstance(node, str) and "prompt" in path.lower():
        yield path, node


class ThemeGuardTest(unittest.TestCase):
    def test_the_guard_catches_the_modern_world_and_allows_1860(self):
        self.assertEqual(theme_guard.leaks("a cargo jet on the runway, 2027, a heist"), ["cargo jet", "runway", "2027", "heist"])
        self.assertEqual(theme_guard.leaks("an operator at the facility with a smartphone"), ["operator", "facility", "smartphone"])
        # 1860 things and words that merely contain a banned one
        self.assertEqual(theme_guard.leaks("a clipper at the quay, a lantern, a flintlock pistol, the captain on deck, he led them"), [])
        self.assertEqual(theme_guard.leaks("a hubbub, a carpet, a vanity, a jetty and a telephoto lens"), [])
        self.assertEqual(theme_guard.report([("ok", "a junk under sail"), ("bad", "a drone at the airport")]), 1)

    def test_every_saved_prompt_is_in_period(self):
        seen = 0
        for name in FILES:
            f = ROOT / name
            if not f.exists():
                continue
            for where, text in prompts(json.loads(f.read_text(encoding="utf-8")), name):
                seen += 1
                self.assertEqual(theme_guard.leaks(text), [], where)
        self.assertGreater(seen, 0)


if __name__ == "__main__":
    unittest.main()
