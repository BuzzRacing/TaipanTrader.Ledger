"""persona_pairs.py (24 Nov 2026): the shared NSFW/clean twin builder gives exactly what the queue tool always made."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import persona_pairs  # noqa: E402
import queue_persona_pairs as tool  # noqa: E402


# Known, unchanged since before the port: these two profile prompts say "naked breasts exposed" (bosun) and
# "bare decolletage" (pirate) in words DECENT has no rule for, so their clean twins still carry it.
KNOWN_UNDRESSED = {"bosun", "pirate"}


def cast():
    chars = json.loads((ROOT / "config" / "settings.json").read_text(encoding="utf-8"))["characters"]
    return {k: v["portrait_prompt"] for k, v in chars.items() if len(v.get("portrait_prompt") or "") > 20}


class PersonaPairsTest(unittest.TestCase):
    def test_the_tool_uses_the_shared_module(self):
        self.assertIs(tool.nsfw_prompt, persona_pairs.nsfw_prompt)
        self.assertIs(tool.clean_prompt, persona_pairs.clean_prompt)

    def test_nsfw_and_clean_shapes(self):
        for cid, base in cast().items():
            nsfw, clean = persona_pairs.nsfw_prompt(base, "sly"), persona_pairs.clean_prompt(base, "sly")
            self.assertIn(persona_pairs.NUDE, nsfw, cid)
            self.assertIn("sly", nsfw, cid)
            self.assertTrue(clean.endswith(persona_pairs.CLEAN_STYLE), cid)
            if cid not in KNOWN_UNDRESSED:
                self.assertNotIn("naked", clean, cid)
            self.assertNotEqual(nsfw, clean)

    def test_the_style_tail_is_kept_on_the_nude_and_dropped_on_the_clean(self):
        base = "a harbour clerk, black silk, plunging neckline, romanticized cinematic historical realism, no text"
        self.assertTrue(persona_pairs.nsfw_prompt(base, "m").endswith("romanticized cinematic historical realism, no text"))
        self.assertNotIn("plunging", persona_pairs.clean_prompt(base, "m"))
        self.assertIn("high-necked", persona_pairs.clean_prompt(base, "m"))
        self.assertEqual(persona_pairs.split("no tail here"), ("no tail here", ""))

    def test_pair_returns_both(self):
        p = persona_pairs.pair("a clerk, romanticized x", "happy")
        self.assertEqual(set(p), {"nsfw", "clean"})

    def test_cast_falls_back_to_the_local_settings(self):
        got, names = tool.cast_prompts("http://127.0.0.1:1")      # nothing listens there
        self.assertEqual(got, {k: v.get("portrait_prompt") or "" for k, v in json.loads(
            (ROOT / "config" / "settings.json").read_text(encoding="utf-8"))["characters"].items()})
        self.assertTrue(names)


if __name__ == "__main__":
    unittest.main()
