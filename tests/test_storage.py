import sqlite3
import tempfile
import unittest
from pathlib import Path

from football_v2.models import KalshiContract, SportsbookGame, ValueComparison
from football_v2.storage import connect, save_run


class StorageTests(unittest.TestCase):
    def test_compact_storage_and_first_signal_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            db = connect(Path(directory) / "football.sqlite")
            contract = KalshiContract(
                "T", "E", "S", "ncaaf", "moneyline", "Team wins", "Team", "Opponent", "",
                0.39, 0.40, 0.60, 0.61, None, 10, 20, "", {"large": "raw payload"},
            )
            game = SportsbookGame("G", "ncaaf", "", "Team", "Opponent", (), {"large": "raw payload"})
            qualifying = ValueComparison(
                "2026-08-30T16:00:01Z", "ncaaf", "moneyline", "T", "G", "Opponent at Team",
                "Team", None, 0.40, 0.48, 5, 0.08, 0.02, 0.06, True, 0.95,
            )
            rejected = ValueComparison(
                "2026-08-30T16:00:01Z", "ncaaf", "moneyline", "T2", "G", "Opponent at Team",
                "Opponent", None, 0.60, 0.55, 5, -0.05, 0.02, -0.07, False, 0.95,
            )

            save_run(db, "2026-08-30T16:00:00Z", [contract], [game], [qualifying, rejected])
            later_signal = ValueComparison(
                "2026-08-30T17:00:01Z", "ncaaf", "moneyline", "T", "G", "Opponent at Team",
                "Team", None, 0.44, 0.51, 6, 0.07, 0.02, 0.05, True, 0.96,
            )
            save_run(db, "2026-08-30T17:00:00Z", [contract], [game], [later_signal])

            self.assertEqual(db.execute("SELECT COUNT(*) FROM scan_runs").fetchone()[0], 2)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM value_comparisons").fetchone()[0], 3)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM paper_recommendations").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT entry_price FROM paper_recommendations").fetchone()[0], 0.40)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM kalshi_snapshots").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM sportsbook_snapshots").fetchone()[0], 0)
            db.close()

    def test_version_one_database_migrates_to_version_two(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "football.sqlite"
            old = sqlite3.connect(path)
            old.execute("CREATE TABLE schema_meta(version INTEGER NOT NULL)")
            old.execute("INSERT INTO schema_meta VALUES(1)")
            old.commit()
            old.close()

            db = connect(path)
            self.assertEqual(db.execute("SELECT version FROM schema_meta").fetchone()[0], 2)
            self.assertIsNotNone(db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='paper_recommendations'"
            ).fetchone())
            db.close()


if __name__ == "__main__":
    unittest.main()
