"""Recorded Table scenes survive fast acknowledgement without altering game outcomes."""
import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import engine
import harbor_view
import journal
from tools.preview_table import journey_sample

class TableStoryTests(unittest.TestCase):
    def test_fast_voyage_keeps_arrival_and_cleared_customs(self):
        game, rows = journey_sample()
        self.assertEqual([r['type'] for r in rows], ['sailed','arrived','customs_open','customs_declare'])
        self.assertIsNone(game.s['players']['p1'].get('customs'))
        self.assertEqual(rows[2]['report']['status'], 'declare')
        self.assertEqual(rows[3]['report']['status'], 'verdict')
        self.assertTrue(rows[1]['welcome'])
        self.assertEqual(rows[0]['focus']['port'], 'hongkong')
        self.assertEqual(rows[1]['focus']['port'], 'singapore')
        original = copy.deepcopy(rows)
        game.s['players']['p1']['cash'] = 0
        game.s['players']['p1']['ships'][0]['hull'] = 0
        self.assertEqual(rows, original)

    def test_spectator_receives_preserved_report_but_no_auth_fields(self):
        game, rows = journey_sample()
        report = rows[-1]['report']
        raw = {'n':1,'pid':'p1','turn':1,'type':'customs_declare','cat':'finance',
               'port':'singapore','table_report':report,'table_focus':rows[-1]['focus']}
        with patch.object(journal,'_cur',{'gid':game.s['game_id']}), patch.object(journal,'_recent',[raw]):
            events = harbor_view.story_events(game,'open')
            self.assertEqual(events[0]['report']['result'],report['result'])
            self.assertNotIn('token', events[0]['focus'])
            self.assertEqual(harbor_view.story_events(game,'public'),[])

    def test_observation_does_not_change_voyage_outcome(self):
        game, _ = journey_sample()
        before = copy.deepcopy(game.s)
        games = [engine.Game(state=copy.deepcopy(before), seed=99) for _ in range(2)]
        recorded = []
        games[1].on_event = lambda e: recorded.append(copy.deepcopy(e))
        for current in games:
            current.act('p1',{'type':'sail','dest':'hongkong','orders':'run'},present=['p1'])
            current.maybe_advance({'p1'})
            current.fight_out({'p1'})
        self.assertEqual(games[0].s,games[1].s)
        self.assertTrue(any(e['type']=='arrived' for e in recorded))

if __name__ == '__main__':
    unittest.main()
