import tempfile
import unittest
from pathlib import Path

from football_v2.storage import connect
from football_v2.telegram_support import (
    build_status,
    is_authorized_chat,
)


def insert_comparison(
    db,
    *,
    observed_at: str,
    ticker: str,
    matchup: str,
    net_edge: float,
    sportsbook_samples: int = 2,
) -> None:
    db.execute(
        """
        INSERT INTO value_comparisons(
            observed_at,
            sport,
            market_type,
            kalshi_ticker,
            game_id,
            commence_time,
            matchup,
            selection,
            line,
            kalshi_yes_ask,
            fair_probability,
            sportsbook_samples,
            edge_before_costs,
            cost_buffer,
            net_edge,
            qualifies,
            match_score
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            observed_at,
            "ncaaf",
            "moneyline",
            ticker,
            ticker,
            "2026-09-05T19:00:00Z",
            matchup,
            f"{matchup} Selection",
            None,
            0.40,
            0.50,
            sportsbook_samples,
            net_edge + 0.02,
            0.02,
            net_edge,
            int(net_edge >= 0.05),
            0.99,
        ),
    )


class TelegramSupportTests(unittest.TestCase):
    def test_chat_authorization_is_exact(self):
        self.assertTrue(
            is_authorized_chat(12345, "12345")
        )
        self.assertFalse(
            is_authorized_chat(12346, "12345")
        )
        self.assertFalse(
            is_authorized_chat(12345, "")
        )
        self.assertFalse(
            is_authorized_chat(None, "12345")
        )

    def test_status_reports_paper_record(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "football.sqlite"
            db = connect(path)
            db.execute(
                "INSERT INTO scan_runs VALUES(?,?,?,?,?)",
                (
                    "2026-08-31T12:00:00Z",
                    10,
                    2,
                    3,
                    0,
                ),
            )
            db.commit()
            db.close()

            status = build_status(path)

            self.assertIn(
                "Last scan: 2026-08-31T12:00:00Z",
                status,
            )
            self.assertIn(
                "Official recommendations: 0",
                status,
            )
            self.assertIn(
                "Gross ROI before fees: +0.0%",
                status,
            )

    def test_status_includes_five_distinct_latest_values(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "football.sqlite"
            db = connect(path)
            db.execute(
                "INSERT INTO scan_runs VALUES(?,?,?,?,?)",
                (
                    "2026-08-31T12:00:00Z",
                    100,
                    20,
                    8,
                    0,
                ),
            )

            comparisons = [
                ("A1", "Game A", 0.040, 2),
                ("A2", "Game A", 0.039, 5),
                ("B1", "Game B", 0.030, 2),
                ("C1", "Game C", 0.020, 2),
                ("D1", "Game D", 0.010, 2),
                ("E1", "Game E", 0.000, 2),
                ("F1", "Game F", -0.010, 2),
                ("G1", "One-book Game", 0.200, 1),
            ]

            for index, (
                ticker,
                matchup,
                edge,
                samples,
            ) in enumerate(comparisons, start=1):
                insert_comparison(
                    db,
                    observed_at=(
                        "2026-08-31T12:00:"
                        f"{index:02d}Z"
                    ),
                    ticker=ticker,
                    matchup=matchup,
                    net_edge=edge,
                    sportsbook_samples=samples,
                )

            db.commit()
            db.close()

            status = build_status(path)

            self.assertIn(
                "TOP 5 CURRENT FOOTBALL VALUE BOARD",
                status,
            )
            self.assertIn(
                "No extra API request used.",
                status,
            )

            for matchup in (
                "Game A",
                "Game B",
                "Game C",
                "Game D",
                "Game E",
            ):
                self.assertIn(matchup, status)

            self.assertEqual(status.count("NCAAF | Game A"), 1)
            self.assertNotIn("NCAAF | Game F", status)
            self.assertNotIn("One-book Game", status)


if __name__ == "__main__":
    unittest.main()
