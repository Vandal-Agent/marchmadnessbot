import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
import sys
from types import ModuleType

if "requests" not in sys.modules:
    requests_stub = ModuleType("requests")
    requests_stub.Session = object
    sys.modules["requests"] = requests_stub
if "dotenv" not in sys.modules:
    dotenv_stub = ModuleType("dotenv")
    dotenv_stub.load_dotenv = lambda *_args, **_kwargs: None
    sys.modules["dotenv"] = dotenv_stub

from football_v2.grading import count_due_recommendations, grade_pending_recommendations
from football_v2.models import FootballResult, KalshiContract, SportsbookGame, ValueComparison
from football_v2.sportsbook import parse_result
from football_v2.storage import connect, save_run


class GradingTests(unittest.TestCase):
    def test_parse_completed_score(self):
        result = parse_result({
            "id": "G", "completed": True, "commence_time": "2026-09-01T00:00:00Z",
            "home_team": "Washington Huskies", "away_team": "Washington State Cougars",
            "scores": [
                {"name": "Washington Huskies", "score": "28"},
                {"name": "Washington State Cougars", "score": "31"},
            ],
        }, "ncaaf")
        self.assertIsNotNone(result)
        self.assertEqual(result.home_score, 28)
        self.assertEqual(result.away_score, 31)

    def test_moneyline_and_spread_are_graded_per_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            db = connect(Path(directory) / "football.sqlite")
            contract = KalshiContract(
                "T", "E", "S", "ncaaf", "moneyline", "", "", "", "",
                None, None, None, None, None, 0, 0, "", {},
            )
            game = SportsbookGame("G", "ncaaf", "2026-09-01T00:00:00Z",
                                  "Washington Huskies", "Washington State Cougars", (), {})
            moneyline = ValueComparison(
                "2026-08-31T00:00:00Z", "ncaaf", "moneyline", "ML", "G",
                "2026-09-01T00:00:00Z", "Washington State at Washington", "Washington St.",
                None, 0.25, 0.35, 5, 0.10, 0.02, 0.08, True, 0.95,
            )
            spread = ValueComparison(
                "2026-08-31T00:00:01Z", "ncaaf", "spread", "SP", "G",
                "2026-09-01T00:00:00Z", "Washington State at Washington", "Washington St.",
                6.5, 0.40, 0.50, 5, 0.10, 0.02, 0.08, True, 0.95,
            )
            save_run(db, "2026-08-31T00:00:00Z", [contract], [game], [moneyline, spread])
            result = FootballResult(
                "G", "ncaaf", "2026-09-01T00:00:00Z", "Washington Huskies",
                "Washington State Cougars", 28, 31, True, {},
            )
            summary = grade_pending_recommendations(db, [result])
            self.assertEqual(summary.graded, 2)
            rows = db.execute(
                "SELECT kalshi_ticker,result,ROUND(profit_loss,2),home_score,away_score "
                "FROM paper_recommendations ORDER BY kalshi_ticker"
            ).fetchall()
            self.assertEqual(rows, [
                ("ML", "win", 0.75, 28, 31),
                ("SP", "loss", -0.40, 28, 31),
            ])
            db.close()

    def test_future_recommendation_does_not_trigger_score_request(self):
        with tempfile.TemporaryDirectory() as directory:
            db = connect(Path(directory) / "football.sqlite")
            contract = KalshiContract(
                "T", "E", "S", "nfl", "moneyline", "", "", "", "",
                None, None, None, None, None, 0, 0, "", {},
            )
            game = SportsbookGame("G", "nfl", "2026-09-10T00:00:00Z", "Home", "Away", (), {})
            value = ValueComparison(
                "2026-08-31T00:00:00Z", "nfl", "moneyline", "T", "G",
                "2026-09-10T00:00:00Z", "Away at Home", "Home", None,
                0.40, 0.50, 5, 0.10, 0.02, 0.08, True, 0.95,
            )
            save_run(db, "2026-08-31T00:00:00Z", [contract], [game], [value])
            now = datetime(2026, 9, 1, tzinfo=timezone.utc)
            self.assertEqual(count_due_recommendations(db, now), 0)
            later = datetime(2026, 9, 11, tzinfo=timezone.utc)
            self.assertEqual(count_due_recommendations(db, later), 1)
            db.close()


if __name__ == "__main__":
    unittest.main()
