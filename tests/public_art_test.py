"""Public captain artwork stays clean even when the table is adult."""
import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import captains


class PublicArtTest(unittest.TestCase):
    def test_public_catalog_forces_clean_without_mutating_table(self):
        cfg = {'content': {'rating': 'historical'}}
        before = copy.deepcopy(cfg)
        saved = {'captains': {'c1': {'cid':'c1','name':'Anne','title':'Captain','guest':False,
                 'retired':False,'games':[], 'houses':[{'hid':'h1','name':'House','color':'#123456',
                 'motto':'','home_port':'','retired':False}]}}}

        def pick(kind, subject, config, *args, **kwargs):
            self.assertEqual(config['content']['rating'], 'family')
            return '/clean-' + subject

        with patch.object(captains, 'load', return_value=saved), patch.object(captains, '_pick', side_effect=pick):
            result = captains.public_list(cfg)
        self.assertEqual(result[0]['portrait'], '/clean-c1')
        self.assertEqual(result[0]['houses'][0]['image'], '/clean-h1')
        self.assertEqual(cfg, before)
        self.assertNotIn('pin', result[0])


if __name__ == '__main__':
    unittest.main()
