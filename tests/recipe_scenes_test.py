"""The tax-desk and weather recipes (24 Nov 2026): recipe_scenes.py paints what the .bat files painted."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import recipe_scenes  # noqa: E402
import recipes  # noqa: E402
import theme_guard  # noqa: E402


def settings():
    return json.loads((ROOT / "config" / "settings.json").read_text(encoding="utf-8"))


class RecipeScenesTest(unittest.TestCase):
    def test_every_officer_gets_four_desk_tells_as_a_pair(self):
        cfg = settings()
        prompts, labels, notes = recipe_scenes.all_prompts(cfg)
        officers = recipe_scenes.officers(cfg)
        self.assertEqual(len(officers), 10)
        for cid in officers:
            self.assertEqual(sorted(k for k in prompts[cid]), sorted(recipe_scenes.TAX_ENTRY_ROLES), cid)
            for key, e in prompts[cid].items():
                self.assertTrue(e["nsfw"] and e["clean"] and e["nsfw"] != e["clean"], (cid, key))
                self.assertEqual(e["aspect"], "3:4")
                self.assertEqual(e["need"], e["tags"])                       # the mood is the tag the desk looks for
                self.assertIn(e["role"], ("sly", "idle"))
                self.assertEqual(theme_guard.leaks(e["nsfw"] + " " + e["clean"]), [], (cid, key))
        self.assertEqual(prompts["officer_hongkong"]["tax_entry_sly"]["role"], "sly")
        self.assertEqual(prompts["officer_hongkong"]["tax_entry_hungry"]["role"], "idle")
        self.assertEqual(notes, [])

    def test_the_desk_tell_is_the_prompt_the_bat_made(self):
        import queue_persona_pairs as pairs
        cfg = settings()
        base = cfg["characters"]["officer_hongkong"]["portrait_prompt"]
        e = recipe_scenes.all_prompts(cfg)[0]["officer_hongkong"]["tax_entry_hungry"]
        want = pairs.pp.build("officer_hongkong", "nude", pairs.MOODS["hungry"], saved=base)
        self.assertEqual(e["nsfw"], want[:6000])

    def test_the_weather_set_is_twelve_looks_with_one_prompt_per_pose(self):
        prompts, labels, _notes = recipe_scenes.all_prompts(settings())
        wet = prompts["crier"]
        self.assertEqual(sorted(wet), sorted(recipe_scenes.WEATHER_ROLES))
        self.assertEqual(len(wet), 12)
        for kind in recipe_scenes.WEATHERS:
            nude, top, clean = (wet["weather_{}_{}".format(look, kind)] for look in recipe_scenes.LOOKS)
            self.assertEqual((len(nude["variants"]["nsfw"]), len(top["variants"]["nsfw"]), len(clean["variants"]["clean"])), (4, 5, 5))
            self.assertEqual(nude["not"], ["topless"])                       # nude is "weather-<kind>" without topless
            self.assertEqual(top["need"], ["weather-" + kind, "topless"])
            self.assertEqual((nude["clean"], top["clean"], clean["nsfw"]), ("", "", ""))
            self.assertEqual({e["role"] for e in (nude, top, clean)}, {"weather"})
            for e in (nude, top, clean):
                for text in e["variants"]["nsfw"] + e["variants"]["clean"]:
                    self.assertEqual(theme_guard.leaks(text), [], e["label"])
        self.assertEqual(len(labels), 12 + 4)

    def test_the_weather_prompts_match_the_two_weather_bats(self):
        import queue_weather_pictures as q
        import queue_weather_topless as t
        wet = recipe_scenes.all_prompts(settings())[0]["crier"]
        nude = [j for kind, ver, j in q.jobs() if kind == "calm" and ver == "nsfw"]
        self.assertEqual(wet["weather_nude_calm"]["variants"]["nsfw"], [j["prompt"] for j in nude])
        top = [j for kind, ver, j in t.jobs() if kind == "typhoon" and ver == "topless"]
        self.assertEqual(wet["weather_topless_typhoon"]["variants"]["nsfw"], [j["prompt"] for j in top])

    def test_starter_recipes_use_the_recipes_own_roles(self):
        by = {r["id"]: r for r in recipes.STARTERS}
        self.assertEqual(by["tax_desk_faces"]["roles"], recipe_scenes.TAX_ENTRY_ROLES)
        self.assertEqual(by["weather_topless_looks"]["nsfw"], 5)
        self.assertEqual(by["weather_clean_looks"]["clean"], 5)
        for rid in ("tax_desk_faces", "weather_nude_looks", "weather_topless_looks", "weather_clean_looks"):
            self.assertEqual(recipes.clean_one(by[rid])["roles"], by[rid]["roles"], rid)   # the roles survive saving

    def test_the_server_command_line_is_left_alone(self):
        saved = sys.argv
        sys.argv = ["server.py", "--port", "8765", "--only", "x"]
        try:
            recipe_scenes.all_prompts(settings())
        finally:
            after, sys.argv = sys.argv, saved
        self.assertEqual(after, ["server.py", "--port", "8765", "--only", "x"])


if __name__ == "__main__":
    unittest.main()
