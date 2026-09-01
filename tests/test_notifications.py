import sys
import unittest
from types import ModuleType

if "telegram" not in sys.modules:
    telegram_stub = ModuleType("telegram")
    telegram_stub.Bot = object
    sys.modules["telegram"] = telegram_stub
if "dotenv" not in sys.modules:
    dotenv_stub = ModuleType("dotenv")
    dotenv_stub.load_dotenv = lambda *_args, **_kwargs: None
    sys.modules["dotenv"] = dotenv_stub

from football_v2.models import ValueComparison
from football_v2.notifications import format_new_recommendations


class NotificationTests(unittest.TestCase):
    def test_recommendation_alert_contains_decision_fields(self):
        value = ValueComparison(
            "2026-08-31T12:00:00Z", "ncaaf", "moneyline", "T", "G",
            "2026-09-01T00:00:00Z", "Away at Home", "Home", None,
            0.40, 0.48, 5, 0.08, 0.02, 0.06, True, 0.95,
        )
        message = format_new_recommendations([value])
        self.assertIn("Kalshi YES ask: 40.0%", message)
        self.assertIn("Sportsbook consensus: 48.0%", message)
        self.assertIn("Estimated net edge: 6.0%", message)
        self.assertIn("Contract: BUY YES", message)
        self.assertIn("No trade was placed", message)

    def test_no_recommendation_is_labeled_clearly(self):
        value = ValueComparison(
            "2026-08-31T12:00:00Z", "ncaaf", "moneyline", "T::NO", "G",
            "2026-09-01T00:00:00Z", "Away at Home", "Home", None,
            0.40, 0.52, 5, 0.12, 0.02, 0.10, True, 0.95,
            contract_side="no",
        )
        message = format_new_recommendations([value])
        self.assertIn("Contract: BUY NO", message)
        self.assertIn("Kalshi NO ask: 40.0%", message)


if __name__ == "__main__":
    unittest.main()
