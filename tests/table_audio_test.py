import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from voicefloor import Floor, LEASE


class TableAudioTests(unittest.TestCase):
    def test_table_leads_only_its_device_and_enabled_channels(self):
        f = Floor()
        f.ask("192.168.1.20", "table", "table", now=0, role="table", channels=["music", "dialogue"])
        status = f.ask("192.168.1.20", "player", "status", now=1)
        self.assertEqual(status["table_channels"], ["music", "dialogue"])
        self.assertTrue(f.ask("192.168.1.20", "player", "take", now=1)["skip"])
        self.assertTrue(f.ask("192.168.1.21", "ipad", "take", now=1)["granted"])
        f.ask("192.168.1.20", "table", "table", now=2, role="table", channels=["music"])
        self.assertTrue(f.ask("192.168.1.20", "player", "take", now=3)["granted"])

    def test_crash_and_close_restore_player_audio(self):
        for close in (True, False):
            f = Floor()
            f.ask("x", "table", "table", now=0, role="table", channels=["dialogue"])
            if close:
                f.ask("x", "table", "leave_table", now=1)
            now = 2 if close else LEASE + 1
            self.assertEqual(f.ask("x", "player", "status", now=now)["table_channels"], [])
            self.assertTrue(f.ask("x", "player", "take", now=now)["granted"])

    def test_muting_table_yields_all_channels(self):
        f = Floor()
        f.ask("x", "t", "table", now=0, role="table", channels=["dialogue", "music"])
        f.ask("x", "t", "table", now=1, role="table", channels=[])
        self.assertEqual(f.ask("x", "p", "status", now=2)["table_channels"], [])


if __name__ == "__main__":
    unittest.main()
