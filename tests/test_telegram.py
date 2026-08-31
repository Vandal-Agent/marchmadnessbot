import sqlite3
import tempfile
import unittest
from pathlib import Path

from football_v2.storage import connect
from football_v2.telegram_support import build_status, is_authorized_chat


class TelegramSupportTests(unittest.TestCase):
    def test_chat_authorization_is_exact(self):
        self.assertTrue(is_authorized_chat(12345, "12345"))
        self.assertFalse(is_authorized_chat(12346, "12345"))
        self.assertFalse(is_authorized_chat(12345, ""))
        self.assertFalse(is_authorized_chat(None, "12345"))

    def test_status_reports_paper_record(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "football.sqlite"
            db = connect(path)
            db.execute("INSERT INTO scan_runs VALUES(?,?,?,?,?)", ("2026-08-31T12:00:00Z", 10, 2, 3, 0))
            db.commit()
            db.close()
            status = build_status(path)
            self.assertIn("Last scan: 2026-08-31T12:00:00Z", status)
            self.assertIn("Official recommendations: 0", status)
            self.assertIn("Gross ROI before fees: +0.0%", status)


if __name__ == "__main__":
    unittest.main()
