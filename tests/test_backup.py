import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from football_backup import backup_database


class BackupTests(unittest.TestCase):
    def test_backup_is_verified_and_retention_is_enforced(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "football.sqlite"
            backups = root / "backups"

            db = sqlite3.connect(source)
            db.execute("CREATE TABLE picks(id INTEGER PRIMARY KEY, name TEXT)")
            db.execute("INSERT INTO picks(name) VALUES ('example')")
            db.commit()
            db.close()

            for day in (1, 2, 3):
                backup_database(
                    source,
                    backups,
                    keep=2,
                    now=datetime(2026, 9, day, tzinfo=timezone.utc),
                )

            saved = sorted(backups.glob("football_v2-*.sqlite"))
            self.assertEqual(
                [path.name for path in saved],
                [
                    "football_v2-20260902T000000Z.sqlite",
                    "football_v2-20260903T000000Z.sqlite",
                ],
            )

            restored = sqlite3.connect(saved[-1])
            self.assertEqual(
                restored.execute("PRAGMA integrity_check").fetchone()[0],
                "ok",
            )
            self.assertEqual(
                restored.execute("SELECT name FROM picks").fetchone()[0],
                "example",
            )
            restored.close()

    def test_failed_backup_does_not_prune_existing_backups(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            backups = root / "backups"
            backups.mkdir()
            existing = backups / "football_v2-20260831T000000Z.sqlite"
            existing.write_bytes(b"existing backup")

            with self.assertRaises(FileNotFoundError):
                backup_database(
                    root / "missing.sqlite",
                    backups,
                    keep=1,
                )

            self.assertTrue(existing.exists())


if __name__ == "__main__":
    unittest.main()
