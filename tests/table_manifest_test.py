"""Departure manifests are event-time records, exported only to the solo Table."""
import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import engine
import harbor_view
import journal
from tools.preview_table import journey_sample


class TableManifestTests(unittest.TestCase):
    def test_manifest_survives_cargo_and_fleet_changes(self):
        game, rows = journey_sample()
        passage = rows[0]['passage']
        manifest = passage['manifest']
        self.assertEqual(manifest['cargo']['tea'],20)
        self.assertEqual(manifest['used'],20)
        self.assertGreaterEqual(manifest['capacity'],20)
        self.assertEqual(manifest['ships'],1)
        self.assertEqual(passage['orders'],'run')
        before=copy.deepcopy(passage)
        game.s['players']['p1']['cargo']['tea']=0
        game.s['players']['p1']['ships'][0]['hull']=1
        game.s['players']['p1']['protect']=99
        game.s['weather']={key:3 for key in game.s['weather']}
        self.assertEqual(passage,before)

    def test_feed_preserves_conditions_and_does_not_alias_journal(self):
        game,rows=journey_sample()
        source=rows[0]['passage']
        event={'n':1,'pid':'p1','turn':1,'type':'sailed','cat':'voyage','sea':source['sea'],
               'orders':source['orders'],'protect':source['protect'],'table_manifest':copy.deepcopy(source['manifest']),
               'table_weather':copy.deepcopy(source['weather'])}
        with patch.object(journal,'_cur',{'gid':game.s['game_id']}),patch.object(journal,'_recent',[event]):
            output=harbor_view.story_events(game,'open')
            self.assertEqual(output[0]['passage'],source)
            output[0]['passage']['manifest']['cargo']['tea']=999
            self.assertEqual(event['table_manifest']['cargo']['tea'],20)
            self.assertEqual(harbor_view.story_events(game,'public'),[])
            game.s['order'].append('p2')
            self.assertNotIn('passage',harbor_view.story_events(game,'open')[0])


if __name__=='__main__':unittest.main()
