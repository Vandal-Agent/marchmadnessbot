from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace

from football_scheduled_scan import run_scheduled_scan


class ScheduledScanTests(unittest.TestCase):
    def test_successful_scan_sends_fresh_top_ten(self):
        calls = []

        def runner(command, **kwargs):
            calls.append((command, kwargs))
            return SimpleNamespace(returncode=0)

        built_for = []

        def builder(database_path):
            built_for.append(database_path)
            return "fresh top ten"

        sent = []
        run_scheduled_scan(
            runner=runner,
            top_ten_builder=builder,
            sender=sent.append,
            database_path=Path("test.sqlite"),
        )

        command, kwargs = calls[0]
        self.assertIn("football_board.py", command[1])
        self.assertEqual(command[-3:], ["--sport", "all", "--notify"])
        self.assertFalse(kwargs["check"])
        self.assertEqual(len(built_for), 1)
        self.assertEqual(sent, ["fresh top ten"])

    def test_failed_scan_does_not_send_stale_top_ten(self):
        built = []
        sent = []

        with self.assertRaisesRegex(RuntimeError, "top ten was not sent"):
            run_scheduled_scan(
                runner=lambda *args, **kwargs: SimpleNamespace(
                    returncode=1
                ),
                top_ten_builder=lambda path: built.append(path),
                sender=sent.append,
            )

        self.assertEqual(built, [])
        self.assertEqual(sent, [])


if __name__ == "__main__":
    unittest.main()
