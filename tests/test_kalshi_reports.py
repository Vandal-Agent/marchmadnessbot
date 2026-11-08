import unittest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import Mock

from football_v2.kalshi_reports import describe, compare_score, match_score_game, build_scores_report, pacific

NOW = datetime(2026,11,8,22,0,tzinfo=timezone.utc)

def market(kind='SPREAD', label='SEA Seahawks win by over 9.5 points'):
    return {'ticker':f'KXNFL{kind}-26NOV08ARISEA-SEA10',
        'event_ticker':f'KXNFL{kind}-26NOV08ARISEA',
        'yes_sub_title':label, 'title':'Arizona vs Seattle', '_event_title':'ARI Cardinals vs SEA Seahawks'}

def game(**extra):
    return {'home_team':'Seattle Seahawks','away_team':'Arizona Cardinals',
        'commence_time':'2026-11-08T21:25:00Z','completed':False,
        'scores':[{'name':'Seattle Seahawks','score':'17'},{'name':'Arizona Cardinals','score':'10'}],
        'last_update':'2026-11-08T21:59:30Z',**extra}

class ReportTests(unittest.TestCase):
    def test_no_spread_and_fractional_quantity(self):
        view=describe(market(), Decimal('-5.57'))
        self.assertIn('NO', view.label)
        self.assertIn('Covering by 2.5',compare_score(view,game(),NOW))
        self.assertIn('Not covering',compare_score(describe(market(),Decimal('5.57')),game(),NOW))

    def test_integer_strike_no_is_complement_not_push(self):
        row=market(label='Seattle Seahawks win by over 7 points')
        self.assertIn('Not covering',compare_score(describe(row,Decimal('1')),game(),NOW))
        self.assertIn('Covering',compare_score(describe(row,Decimal('-1')),game(),NOW))

    def test_total_and_no_total_at_equality(self):
        row=market('TOTAL','Over 27 points')
        self.assertIn('Need 1 more',compare_score(describe(row,Decimal('1.88')),game(),NOW))
        self.assertIn('Currently within total',compare_score(describe(row,Decimal('-1')),game(),NOW))

    def test_moneyline_and_missing_score(self):
        view=describe(market('GAME','SEA Seahawks'),Decimal('-2.86'))
        self.assertIn('Behind by 7',compare_score(view,game(),NOW))
        self.assertIn('Score unavailable',compare_score(view,game(scores=None),NOW))

    def test_stale_score_not_current_covering(self):
        view=describe(market(),Decimal('-1'))
        self.assertIn('stale',compare_score(view,game(last_update='2026-11-08T21:00:00Z'),NOW))
        self.assertNotIn('Covering',compare_score(view,game(last_update='2026-11-08T21:00:00Z'),NOW))

    def test_scope_and_unsupported_prop_never_evaluated(self):
        row=market(); row['title']='Arizona vs Seattle: 1st Half Spread'
        self.assertEqual(describe(row,Decimal('1')).kind,'unsupported')
        row['ticker']='KXNFLTEAMTOTAL-26NOV08ARISEA-X'
        self.assertEqual(describe(row,Decimal('1')).kind,'unsupported')

    def test_matching_requires_both_teams_sport_date_and_unique_result(self):
        view=describe(market(),Decimal('1'))
        self.assertEqual(match_score_game(view,[game()]),game())
        self.assertIsNone(match_score_game(view,[game(),game()]))
        self.assertIsNone(match_score_game(view,[game(away_team='Atlanta Falcons')]))
        self.assertIsNone(match_score_game(view,[game(commence_time='2026-11-10T21:00:00Z')]))

    def test_pacific_date_and_dst(self):
        self.assertIn('11/08',pacific('2026-11-09T01:00:00Z'))
        self.assertIn('PST',pacific('2026-11-09T01:00:00Z'))
        self.assertIn('PDT',pacific('2026-07-09T01:00:00Z'))

    def test_report_orders_live_first_and_preserves_unknown(self):
        client=Mock()
        client.positions.return_value=[{'ticker':'UNKNOWN','position_fp':'1'},
            {'ticker':market()['ticker'],'position_fp':'-5.57'}]
        client.market.side_effect=[Exception('secret'),market()]
        client.event.return_value={'title':'ARI Cardinals vs SEA Seahawks'}
        report=build_scores_report(client=client, score_fetcher=lambda sport:[game()], now=NOW)
        self.assertLess(report.index('Live'),report.index('UNKNOWN'))
        self.assertIn('5.57',report)
        self.assertNotIn('secret',report)

    def test_event_failure_preserves_market_description_and_match(self):
        client=Mock()
        client.positions.return_value=[{'ticker':market()['ticker'],'position_fp':'-5.57'}]
        client.market.return_value=market()
        client.event.side_effect=RuntimeError('secret')
        report=build_scores_report(client=client,score_fetcher=lambda sport:[game()],now=NOW)
        self.assertIn('SEA Seahawks win by over 9.5 points',report)
        self.assertIn('Covering by 2.5',report)
        self.assertNotIn('secret',report)

if __name__ == '__main__': unittest.main()
