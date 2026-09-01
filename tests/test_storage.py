import sqlite3
import tempfile
import unittest
from pathlib import Path

from football_v2.models import KalshiContract, SportsbookGame, ValueComparison
from football_v2.storage import connect, save_run


class StorageTests(unittest.TestCase):
    def test_compact_storage_and_first_signals_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            db = connect(Path(directory) / "football.sqlite")
            contract = KalshiContract(
                "T", "E", "S", "ncaaf", "moneyline", "Team wins", "Team", "Opponent", "",
                0.39, 0.40, 0.60, 0.61, None, 10, 20, "", {"large": "raw payload"},
            )
            game = SportsbookGame(
                "G", "ncaaf", "", "Team", "Opponent", (), {"large": "raw payload"}
            )
            qualifying = ValueComparison(
                "2026-08-30T16:00:01Z", "ncaaf", "moneyline", "T", "G",
                "2026-09-01T16:00:00Z", "Opponent at Team", "Team", None,
                0.40, 0.48, 5, 0.08, 0.02, 0.06, True, 0.95,
            )
            rejected = ValueComparison(
                "2026-08-30T16:00:01Z", "ncaaf", "moneyline", "T2", "G2",
                "2026-09-01T16:00:00Z", "Other at Opponent", "Opponent", None,
                0.60, 0.55, 5, -0.05, 0.02, -0.07, False, 0.95,
            )

            first_new = save_run(
                db,
                "2026-08-30T16:00:00Z",
                [contract],
                [game],
                [qualifying, rejected],
                tracked_watchlist=[qualifying, rejected],
            )
            later_signal = ValueComparison(
                "2026-08-30T17:00:01Z", "ncaaf", "moneyline", "T", "G",
                "2026-09-01T16:00:00Z", "Opponent at Team", "Team", None,
                0.44, 0.51, 6, 0.07, 0.02, 0.05, True, 0.96,
            )
            second_new = save_run(
                db,
                "2026-08-30T17:00:00Z",
                [contract],
                [game],
                [later_signal],
                tracked_watchlist=[later_signal],
            )

            self.assertEqual(
                db.execute("SELECT COUNT(*) FROM scan_runs").fetchone()[0],
                2,
            )
            self.assertEqual(
                db.execute("SELECT COUNT(*) FROM value_comparisons").fetchone()[0],
                3,
            )
            self.assertEqual(
                db.execute("SELECT COUNT(*) FROM paper_recommendations").fetchone()[0],
                1,
            )
            self.assertEqual(
                db.execute("SELECT entry_price FROM paper_recommendations").fetchone()[0],
                0.40,
            )
            self.assertEqual(
                db.execute("SELECT COUNT(*) FROM paper_watchlist").fetchone()[0],
                2,
            )
            self.assertEqual(
                db.execute(
                    "SELECT first_seen_rank,entry_price FROM paper_watchlist "
                    "WHERE kalshi_ticker='T'"
                ).fetchone(),
                (1, 0.40),
            )
            self.assertEqual(
                [value.kalshi_ticker for value in first_new],
                ["T"],
            )
            self.assertEqual(second_new, [])
            self.assertEqual(
                db.execute("SELECT COUNT(*) FROM kalshi_snapshots").fetchone()[0],
                0,
            )
            self.assertEqual(
                db.execute("SELECT COUNT(*) FROM sportsbook_snapshots").fetchone()[0],
                0,
            )
            db.close()

    def test_old_databases_migrate_to_version_six(self):
        for old_version in (1, 2, 3, 4, 5):
            with self.subTest(old_version=old_version), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "football.sqlite"
                old = sqlite3.connect(path)
                old.execute("CREATE TABLE schema_meta(version INTEGER NOT NULL)")
                old.execute(
                    "INSERT INTO schema_meta VALUES(?)",
                    (old_version,),
                )
                old.commit()
                old.close()

                db = connect(path)
                self.assertEqual(
                    db.execute("SELECT version FROM schema_meta").fetchone()[0],
                    6,
                )
                recommendation_columns = {
                    row[1]
                    for row in db.execute(
                        "PRAGMA table_info(paper_recommendations)"
                    )
                }
                watchlist_columns = {
                    row[1]
                    for row in db.execute(
                        "PRAGMA table_info(paper_watchlist)"
                    )
                }
                for column in (
                    "commence_time",
                    "home_score",
                    "away_score",
                    "contract_side",
                ):
                    self.assertIn(column, recommendation_columns)
                for column in (
                    "first_seen_rank",
                    "qualifies_at_entry",
                    "home_score",
                    "away_score",
                    "contract_side",
                ):
                    self.assertIn(column, watchlist_columns)
                db.close()


if __name__ == "__main__":
    unittest.main()
