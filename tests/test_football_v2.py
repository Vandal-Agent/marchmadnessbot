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
from football_v2.matching import event_date_from_ticker, match_game, normalize_team, team_similarity
from football_v2.models import KalshiContract,SportsbookGame,SportsbookMarket,SportsbookOutcome
from football_v2.value import american_implied_probability,compare_contract,consensus_probability


class FootballV2Tests(unittest.TestCase):
    def test_american_probability(self):
        self.assertEqual(round(american_implied_probability(-150),4),0.6)
        self.assertEqual(round(american_implied_probability(200),4),0.3333)

    def test_nfl_abbreviation_matching(self):
        self.assertEqual(team_similarity("SEA","Seattle Seahawks"),1.0)

    def test_college_state_abbreviation_selects_correct_team(self):
        self.assertEqual(normalize_team("Washington St."), "washington state")
        self.assertGreater(
            team_similarity("Washington St.", "Washington State Cougars"),
            team_similarity("Washington St.", "Washington Huskies"),
        )

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

    def test_washington_state_uses_underdog_probability(self):
        c=KalshiContract("T","E","KXNCAAFGAME","ncaaf","moneyline","Washington St. vs Washington",
          "Washington St.","Washington","",.05,.08,.92,.95,None,100,100,"",{})
        g=SportsbookGame("G","ncaaf","2026-09-06T00:00:00Z","Washington Huskies","Washington State Cougars",(
          SportsbookMarket("b1","Book 1","moneyline",(
            SportsbookOutcome("Washington State Cougars",900),
            SportsbookOutcome("Washington Huskies",-1400),
          )),
          SportsbookMarket("b2","Book 2","moneyline",(
            SportsbookOutcome("Washington State Cougars",850),
            SportsbookOutcome("Washington Huskies",-1300),
          )),
        ),{})
        probability,samples=consensus_probability(c,g)
        self.assertEqual(samples,2)
        self.assertIsNotNone(probability)
        self.assertLess(probability,0.15)

    def test_started_game_cannot_be_recommended(self):
        c=KalshiContract("T","E","KXNFLGAME","nfl","moneyline","SEA vs NE","SEA","NE","",.40,.42,.58,.60,None,100,100,"",{})
        g=SportsbookGame("G","nfl","2000-01-01T00:00:00Z","New England Patriots","Seattle Seahawks",(
          SportsbookMarket("b1","Book 1","moneyline",(
            SportsbookOutcome("Seattle Seahawks",100),
            SportsbookOutcome("New England Patriots",-120),
          )),
          SportsbookMarket("b2","Book 2","moneyline",(
            SportsbookOutcome("Seattle Seahawks",100),
            SportsbookOutcome("New England Patriots",-120),
          )),
        ),{})
        self.assertIsNone(compare_contract(c,g,1.0,0.05,0.02,30))

    def test_compare_contract_selects_better_no_side(self):
        c = KalshiContract(
            "T", "E", "KXNFLGAME", "nfl", "moneyline",
            "SEA vs NE", "SEA", "NE", "",
            .59, .60, .38, .40, None, 100, 100, "", {},
        )
        g = SportsbookGame(
            "G", "nfl", "2099-09-01T00:00:00Z",
            "New England Patriots", "Seattle Seahawks",
            (
                SportsbookMarket(
                    "b1", "Book 1", "moneyline",
                    (
                        SportsbookOutcome("Seattle Seahawks", -110),
                        SportsbookOutcome("New England Patriots", -110),
                    ),
                ),
                SportsbookMarket(
                    "b2", "Book 2", "moneyline",
                    (
                        SportsbookOutcome("Seattle Seahawks", -110),
                        SportsbookOutcome("New England Patriots", -110),
                    ),
                ),
            ),
            {},
        )

        value = compare_contract(c, g, 1.0, 0.05, 0.02, 30)

        self.assertIsNotNone(value)
        self.assertEqual(value.contract_side, "no")
        self.assertEqual(value.kalshi_ticker, "T::NO")
        self.assertAlmostEqual(value.fair_probability, 0.50)
        self.assertAlmostEqual(value.kalshi_yes_ask, 0.40)


if __name__ == "__main__":
    unittest.main()
