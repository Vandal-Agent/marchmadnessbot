import unittest
import sys
from types import ModuleType

# Keep pure parser/math tests independent of optional runtime packages.
if "requests" not in sys.modules:
    requests_stub = ModuleType("requests")
    requests_stub.Session = object
    sys.modules["requests"] = requests_stub
if "dotenv" not in sys.modules:
    dotenv_stub = ModuleType("dotenv")
    dotenv_stub.load_dotenv = lambda *_args, **_kwargs: None
    sys.modules["dotenv"] = dotenv_stub

from football_v2.kalshi import parse_contract
from football_v2.matching import event_date_from_ticker, match_game, team_similarity
from football_v2.models import KalshiContract,SportsbookGame,SportsbookMarket,SportsbookOutcome
from football_v2.value import american_implied_probability,consensus_probability


class FootballV2Tests(unittest.TestCase):
    def test_american_probability(self):
        self.assertEqual(round(american_implied_probability(-150),4),0.6)
        self.assertEqual(round(american_implied_probability(200),4),0.3333)

    def test_nfl_abbreviation_matching(self):
        self.assertEqual(team_similarity("SEA","Seattle Seahawks"),1.0)

    def test_parse_prices(self):
        c=parse_contract({"ticker":"T","event_ticker":"E","title":"NE Patriots vs SEA Seahawks",
          "yes_sub_title":"SEA","yes_bid_dollars":"0.5100","yes_ask":54},"nfl","moneyline","KXNFLGAME")
        self.assertIsNotNone(c)
        self.assertEqual(c.yes_bid,0.51)
        self.assertEqual(c.yes_ask,0.54)

    def test_parent_event_supplies_opponent(self):
        market={"ticker":"T","event_ticker":"KXNCAAFGAME-26SEP12CHARMISS",
          "title":"Charlotte wins","yes_sub_title":"Charlotte","_event_title":"Charlotte vs Ole Miss"}
        c=parse_contract(market,"ncaaf","moneyline","KXNCAAFGAME")
        self.assertEqual(c.target_team,"Charlotte")
        self.assertEqual(c.opponent_team,"Ole Miss")

    def test_event_date_and_opponent_prevent_wrong_game(self):
        market={"ticker":"T","event_ticker":"KXNCAAFGAME-26SEP12CHARMISS",
          "title":"Charlotte wins","yes_sub_title":"Charlotte","_event_title":"Charlotte vs Ole Miss"}
        c=parse_contract(market,"ncaaf","moneyline","KXNCAAFGAME")
        wrong=SportsbookGame("W","ncaaf","2026-09-05T19:30:00Z","Charlotte 49ers","Citadel Bulldogs",(),{})
        right=SportsbookGame("R","ncaaf","2026-09-12T19:30:00Z","Ole Miss Rebels","Charlotte 49ers",(),{})
        game,score=match_game(c,[wrong,right])
        self.assertEqual(event_date_from_ticker(c.event_ticker),"2026-09-12")
        self.assertIsNotNone(game)
        self.assertEqual(game.event_id,"R")
        self.assertGreater(score,0.76)

    def test_consensus_removes_vig(self):
        c=KalshiContract("T","E","KXNFLGAME","nfl","moneyline","SEA vs NE","SEA","NE","",.49,.51,.48,.50,None,100,100,"",{})
        g=SportsbookGame("G","nfl","","New England Patriots","Seattle Seahawks",(
          SportsbookMarket("b1","Book 1","moneyline",(SportsbookOutcome("Seattle Seahawks",-110),SportsbookOutcome("New England Patriots",-110))),
          SportsbookMarket("b2","Book 2","moneyline",(SportsbookOutcome("Seattle Seahawks",-120),SportsbookOutcome("New England Patriots",100))),),{})
        probability,samples=consensus_probability(c,g)
        self.assertEqual(samples,2)
        self.assertIsNotNone(probability)
        self.assertTrue(0.50<probability<0.53)


if __name__ == "__main__":
    unittest.main()
