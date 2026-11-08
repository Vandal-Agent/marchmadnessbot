import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from football_v2.kalshi_history import record_snapshot, build_history, cutoff_for


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'account.sqlite'

    def test_midnight_labels_previous_pacific_day_and_keeps_observation(self):
        observed = datetime(2026,11,9,8,0,12,tzinfo=timezone.utc)
        cutoff = cutoff_for(observed)
        self.assertTrue(record_snapshot(self.path, {'balance':4204,'portfolio_value':1050}, observed, cutoff))
        with closing(sqlite3.connect(self.path)) as db:
            day, actual = db.execute('SELECT day,observed_at FROM snapshots').fetchone()
        self.assertEqual(day, '2026-11-08')
        self.assertEqual(actual, observed.isoformat())
        report = build_history(self.path)
        self.assertIn('52.54', report)
        self.assertIn('PST', report)

    def test_late_sample_refused_and_duplicate_does_not_overwrite(self):
        observed = datetime(2026,11,9,8,0,tzinfo=timezone.utc)
        cutoff = cutoff_for(observed)
        self.assertTrue(record_snapshot(self.path, {'balance':100,'portfolio_value':0}, observed, cutoff))
        self.assertFalse(record_snapshot(self.path, {'balance':200,'portfolio_value':0}, observed, cutoff))
        with self.assertRaises(ValueError):
            record_snapshot(self.path, {'balance':200,'portfolio_value':0}, observed.replace(hour=9), cutoff)
        self.assertIn('$1.00',build_history(self.path))

    def test_dst_midnights_have_correct_utc_offsets(self):
        self.assertEqual(cutoff_for(datetime(2026,7,1,7,0,tzinfo=timezone.utc)).hour,7)
        self.assertEqual(cutoff_for(datetime(2026,11,9,8,0,tzinfo=timezone.utc)).hour,8)

    def test_gap_is_not_reported_as_daily_change(self):
        for day, cash in [(9,100),(11,300),(12,400)]:
            observed = datetime(2026,11,day,8,0,tzinfo=timezone.utc)
            record_snapshot(self.path, {'balance':cash,'portfolio_value':0},observed,cutoff_for(observed))
        report=build_history(self.path)
        self.assertIn('prior day missing',report)
        self.assertIn('+$1.00',report)
        self.assertIn('not trading profit',report)

    def test_missing_history_does_not_create_database(self):
        self.assertIn('No daily snapshots',build_history(self.path))
        self.assertFalse(self.path.exists())
