"""The Table must not leak a private seat or replay another game's journal."""
import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config
import engine
import harbor_view
import journal


class HarborViewTests(unittest.TestCase):
    def setUp(self):
        engine.configure(config.defaults())
        self.game = engine.Game(seed=3)
        self.game.join("Anthony", "")
        self.game.admin("start", {})

    def test_solo_gets_scene_without_mutating_game(self):
        seat = self.game.view("p1", ["p1"])
        before = copy.deepcopy(self.game.s)
        feed = harbor_view.view(self.game, ["p1"], seat)
        self.assertEqual(feed["focus"]["id"], "p1")
        self.assertIsNone(feed["state"]["me"])
        self.assertNotIn("token", feed["focus"])
        self.assertEqual(self.game.s, before)

    def test_multiplayer_never_gets_a_live_private_scene(self):
        self.game.s["phase"] = "lobby"
        self.game.join("Victoria", "")
        seat = self.game.view("p1", ["p1"])
        for phase in ("port", "ended"):
            self.game.s["phase"] = phase
            feed = harbor_view.view(self.game, ["p1"], seat)
            self.assertNotIn("focus", feed)
            self.assertNotIn("voice", feed)
            self.assertIsNone(feed["state"]["me"])
        self.game.s["phase"] = "port"
        feed = harbor_view.view(self.game)
        self.assertEqual(feed["events"], [])
        self.assertTrue(all("prices" not in row for row in feed["ports"].values()))

    def test_journal_is_scoped_to_game_and_filters_internal_records(self):
        rows = [{"n": 1, "pid": "p1", "type": "buy", "cat": "market", "result": "Bought tea.", "a": {"good": "tea", "qty": 20}},
                {"n": 2, "pid": "p1", "type": "buy", "cat": "rejected", "msg": "Refused"},
                {"n": 3, "pid": "p1", "type": "storm", "cat": "dice", "msg": "Hidden roll"}]
        with patch.object(journal, "_cur", {"gid": "another-game"}), patch.object(journal, "_recent", rows):
            self.assertEqual(harbor_view.story_events(self.game, "open"), [])
        with patch.object(journal, "_cur", {"gid": self.game.s["game_id"]}), patch.object(journal, "_recent", rows):
            events = harbor_view.story_events(self.game, "open")
            self.assertEqual([e["n"] for e in events], [1])
            self.assertEqual(events[0]["qty"], 20)
            self.assertEqual(harbor_view.story_events(self.game, "public"), [])


if __name__ == "__main__":
    unittest.main()
