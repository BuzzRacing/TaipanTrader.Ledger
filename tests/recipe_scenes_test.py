"""The Media Library exposes dressed customs and weather prompts only."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config
import imagegen
import recipe_scenes
import tax_results
import cast


class RecipeScenesTest(unittest.TestCase):
    def test_customs_and_weather(self):
        prompts, labels, notes = recipe_scenes.all_prompts(config.DEFAULTS)
        self.assertFalse(notes)
        officers = recipe_scenes.officers(config.DEFAULTS)
        self.assertTrue(set(officers) & cast.MEN)
        self.assertTrue(set(officers) - cast.MEN)
        for cid in officers:
            self.assertEqual(set(prompts[cid]), set(recipe_scenes.TAX_ENTRY_ROLES))
        self.assertEqual(set(prompts["crier"]), set(recipe_scenes.WEATHER_ROLES))
        self.assertEqual(set(labels), set(recipe_scenes.TAX_ENTRY_ROLES + recipe_scenes.WEATHER_ROLES))
        for entry in prompts["crier"].values():
            self.assertEqual(len(entry["variants"]), 5)
            self.assertTrue(all("English man" in prompt for prompt in entry["variants"]))
        for subjects in (prompts, tax_results.all_prompts(config.DEFAULTS["characters"])):
            for entries in subjects.values():
                for entry in entries.values():
                    self.assertNotIn("nsfw", entry)
                    self.assertFalse(any(imagegen.adult_prompt(prompt)
                                         for prompt in [entry["clean"], *entry.get("variants", [])]))


if __name__ == "__main__":
    unittest.main()
