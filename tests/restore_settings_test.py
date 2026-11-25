"""tools/restore_pi_settings.py (24 Nov 2026): lists backups, refuses a bad one, restores a good one and keeps what was there."""
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import restore_pi_settings as r  # noqa: E402


class RestoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "backups").mkdir()
        self.old = (r.CFG, r.BACKUPS, r.CURRENT)
        r.CFG, r.BACKUPS, r.CURRENT = str(self.tmp), str(self.tmp / "backups"), str(self.tmp / "settings.json")
        shutil.copy(ROOT / "config" / "settings.json", r.CURRENT)
        shutil.copy(ROOT / "config" / "settings.json", self.tmp / "backups" / "good.json")
        (self.tmp / "backups" / "broken.json").write_text("{not json", encoding="utf-8")

    def tearDown(self):
        r.CFG, r.BACKUPS, r.CURRENT = self.old
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_the_live_settings_are_recognised_as_crimson(self):
        i = r.inspect(r.CURRENT)
        self.assertTrue(i["ok"], i["why"])
        self.assertTrue(i["crimson"])
        self.assertEqual((i["ports"], i["year"]), (10, 1860))

    def test_a_broken_backup_is_refused_and_nothing_changes(self):
        before = Path(r.CURRENT).read_bytes()
        self.assertEqual(r.main(["--restore", "broken.json"]), 1)
        self.assertEqual(Path(r.CURRENT).read_bytes(), before)
        self.assertEqual(r.main(["--restore", "missing.json"]), 1)

    def test_a_good_backup_is_restored_and_the_old_settings_kept(self):
        d = json.loads(Path(r.CURRENT).read_text(encoding="utf-8"))
        d["rules"]["game"]["start_year"] = 1861            # a change made after the backup
        Path(r.CURRENT).write_text(json.dumps(d), encoding="utf-8")
        self.assertEqual(r.main(["--restore", "good.json"]), 0)
        self.assertEqual(json.loads(Path(r.CURRENT).read_text(encoding="utf-8"))["rules"]["game"]["start_year"], 1860)
        kept = [p for p in os.listdir(r.BACKUPS) if p.startswith("settings_before_restore_")]
        self.assertEqual(len(kept), 1)
        self.assertEqual(json.loads((Path(r.BACKUPS) / kept[0]).read_text(encoding="utf-8"))["rules"]["game"]["start_year"], 1861)

    def test_list_suggests_a_good_crimson_backup(self):
        import io
        from contextlib import redirect_stdout
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(r.main(["--list"]), 0)
        text = out.getvalue()
        self.assertIn("SUGGEST: good.json", text)
        self.assertIn("REJECTED", text)


if __name__ == "__main__":
    unittest.main()
