"""Actual account reports. Paper grading and recommendation parsers are unchanged."""
from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

import requests

from football_v2.kalshi_account import AccountClient, AccountError, balance_values, decimal_value, quantity
from football_v2.matching import NFL_ALIASES, event_date_from_ticker, team_similarity

PACIFIC = ZoneInfo('America/Los_Angeles')


def parsed_time(value: str) -> datetime | None:
    try:
        result = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return result if result.tzinfo else None
    except (ValueError, TypeError):
        return None


def pacific(value: str | datetime) -> str:
    value = value if isinstance(value, datetime) else parsed_time(value)
    return value.astimezone(PACIFIC).strftime('%m/%d/%Y %I:%M %p %Z') if value else 'time unavailable'


def canonical(team: str, sport: str) -> str:
    if sport == 'nfl':
        first = team.lower().split()[0] if team.split() else ''
        if first in NFL_ALIASES:
            return NFL_ALIASES[first]
    return team


@dataclass(frozen=True)
class PositionView:
    ticker: str
    sport: str
    kind: str
    label: str
    matchup: str
    teams: tuple[str, str]
    target: str
    line: Decimal | None
    qty: Decimal
    date: str


def describe(market: dict, qty: Decimal) -> PositionView:
    ticker = str(market.get('ticker', ''))
    series = ticker.split('-')[0]
    supported = {'KXNFLGAME':('nfl','moneyline'), 'KXNFLSPREAD':('nfl','spread'),
        'KXNFLTOTAL':('nfl','total'), 'KXNCAAFGAME':('ncaaf','moneyline'),
        'KXNCAAFSPREAD':('ncaaf','spread'), 'KXNCAAFTOTAL':('ncaaf','total')}
    sport, kind = supported.get(series, ('','unsupported'))
    title = str(market.get('title', ''))
    subtitle = str(market.get('yes_sub_title') or market.get('subtitle') or title or ticker)
    matchup = str(market.get('_event_title') or title)
    teams = re.split(r'\s+(?:vs\.?|at)\s+', matchup.split(':')[0], maxsplit=1, flags=re.I)
    pair = (teams[0].strip(), teams[1].strip()) if len(teams) == 2 else ('','')
    text = subtitle + ' ' + title
    target, line = subtitle, None
    if re.search(r'\b(?:half|quarter|overtime|team total)\b', text, re.I):
        kind = 'unsupported'
    if kind == 'spread':
        match = re.search(r'(.+?)\s+wins?\s+by\s+(?:over|more than)\s+(\d+(?:\.\d+)?)', subtitle, re.I)
        if match:
            target, line = match[1].strip(), decimal_value(match[2])
        else:
            kind = 'unsupported'
    elif kind == 'total':
        match = re.search(r'^Over\s+(\d+(?:\.\d+)?)\s+points?\b', subtitle, re.I)
        if match:
            target, line = '', decimal_value(match[1])
        else:
            kind = 'unsupported'
    return PositionView(ticker, sport, kind, ('YES' if qty > 0 else 'NO') + ': ' + subtitle,
        matchup, pair, target, line, qty, event_date_from_ticker(str(market.get('event_ticker') or ticker)))


def team_score(left: str, right: str, sport: str) -> float:
    return team_similarity(canonical(left,sport),canonical(right,sport))


def match_score_game(view: PositionView, games: list[dict]) -> dict | None:
    if not all(view.teams) or not view.date or not view.sport:
        return None
    candidates = []
    for row in games:
        if row.get('sport_key') not in (None, {'nfl':'americanfootball_nfl','ncaaf':'americanfootball_ncaaf'}[view.sport]):
            continue
        start = parsed_time(row.get('commence_time',''))
        if not start or start.astimezone(PACIFIC).date().isoformat() != view.date:
            continue
        home, away = str(row.get('home_team','')), str(row.get('away_team',''))
        a,b = view.teams
        scores = [min(team_score(a,home,view.sport),team_score(b,away,view.sport)),
                  min(team_score(a,away,view.sport),team_score(b,home,view.sport))]
        if max(scores) >= .76 and abs(scores[0]-scores[1]) >= .05:
            candidates.append((max(scores),row))
    candidates.sort(key=lambda x:x[0],reverse=True)
    if not candidates or (len(candidates)>1 and candidates[0][0]-candidates[1][0]<.05):
        return None
    return candidates[0][1]


def score_pair(game: dict) -> tuple[int,int] | None:
    try:
        scores={x['name']:int(x['score']) for x in game.get('scores') or []}
        result=scores[game['home_team']],scores[game['away_team']]
        return result if min(result)>=0 else None
    except (ValueError,TypeError,KeyError):
        return None


def compare_score(view: PositionView, game: dict, now: datetime) -> str:
    scores=score_pair(game)
    if scores is None:
        return 'Score unavailable'
    if not game.get('completed'):
        updated=parsed_time(game.get('last_update',''))
        if updated is None or not -60 <= (now-updated).total_seconds() <= 180:
            return 'Score stale or update time unavailable; position comparison withheld'
    if view.kind == 'unsupported':
        return 'Contract comparison unavailable'
    home,away=scores
    if view.kind == 'total':
        total=home+away
        yes=Decimal(total)>view.line
        if game.get('completed'):
            return 'Final score meets your condition; settlement pending' if yes == (view.qty>0) else 'Final score does not meet your condition; settlement pending'
        if view.qty>0:
            needed=int(view.line)+1-total
            return f'{total} combined; '+(f'Need {needed} more points' if needed>0 else 'Total exceeded')
        return f'{total} combined; '+('Currently within total' if not yes else 'Total exceeded; NO condition not met')
    similarities=[team_score(view.target,str(game.get(k,'')),view.sport) for k in ('home_team','away_team')]
    index=0 if similarities[0]>similarities[1] else 1
    if similarities[index]<.76 or abs(similarities[0]-similarities[1])<.05:
        return 'Target team ambiguous; comparison unavailable'
    difference=Decimal(scores[index]-scores[1-index])
    threshold=view.line if view.kind=='spread' else Decimal(0)
    yes=difference>threshold
    if game.get('completed'):
        return 'Final score meets your condition; settlement pending' if yes==(view.qty>0) else 'Final score does not meet your condition; settlement pending'
    if view.kind=='moneyline':
        lead=difference if view.qty>0 else -difference
        return f'Leading by {lead:g}' if lead>0 else f'Behind by {-lead:g}' if lead<0 else 'Tied'
    margin=difference-threshold
    if view.qty<0:
        margin=-margin
    covering=yes==(view.qty>0)
    if margin==0:
        return 'Covering (NO includes equality)' if covering else 'Not covering (YES requires strictly over the line)'
    return f'Covering by {margin:g} points' if covering else f'Not covering; {abs(margin):g} points short of line'


_score_cache = {}
_score_lock = threading.Lock()


def fetch_score_games(sport: str) -> list[dict]:
    from football_v2.config import settings
    if not settings.odds_api_key:
        raise AccountError('Scores unavailable: missing Odds API configuration')
    with _score_lock:
        cached=_score_cache.get(sport)
        if cached and time.monotonic()-cached[0]<60:
            return cached[1]
        sport_key={'nfl':'americanfootball_nfl','ncaaf':'americanfootball_ncaaf'}[sport]
        try:
            response=requests.get(f'https://api.the-odds-api.com/v4/sports/{sport_key}/scores',
                params={'apiKey':settings.odds_api_key,'daysFrom':3,'dateFormat':'iso'},timeout=20,
                allow_redirects=False)
            if response.status_code!=200:
                raise AccountError('Scores unavailable from Odds API')
            rows=response.json()
            if not isinstance(rows,list) or not all(isinstance(r,dict) for r in rows):
                raise AccountError('Scores unavailable: invalid response')
            _score_cache[sport]=(time.monotonic(),rows)
            return rows
        except AccountError:
            raise
        except Exception:
            raise AccountError('Scores unavailable from Odds API') from None


def views(client: AccountClient):
    events={}
    for row in client.positions():
        qty=quantity(row)
        ticker=str(row.get('ticker',''))
        try:
            market=dict(client.market(ticker))
        except Exception:
            market={'ticker':ticker,'title':ticker,'yes_sub_title':'Market description unavailable'}
        event_ticker=market.get('event_ticker','')
        if event_ticker not in events:
            try:
                events[event_ticker]=client.event(event_ticker) if event_ticker else {}
            except Exception:
                events[event_ticker]={}
        market['_event_title']=events[event_ticker].get('title','')
        yield row,market,describe(market,qty)


def build_account_report(*, client=None, now=None) -> str:
    client=client or AccountClient.from_env()
    now=now or datetime.now(timezone.utc)
    cash,value=balance_values(client.get_balance())
    lines=['KALSHI ACCOUNT','Observed: '+pacific(now),f'Cash: ${cash:.2f}',f'Positions value (API): ${value:.2f}',
        f'Total account value: ${cash+value:.2f}','']
    count=0
    for row,market,view in views(client):
        count+=1
        lines.extend([view.matchup,view.label,f'{abs(view.qty):g} contracts; maximum binary payout ${abs(view.qty):.2f}',''])
    if not count:
        lines.append('No open positions.')
    lines.append('Position value is an estimate. Payout includes stake; it is not profit.')
    return '\n'.join(lines)


def build_scores_report(*, client=None, score_fetcher=None, now=None) -> str:
    client=client or AccountClient.from_env()
    score_fetcher=score_fetcher or fetch_score_games
    now=now or datetime.now(timezone.utc)
    positions=list(views(client))
    games={}
    for sport in sorted({v.sport for _,_,v in positions if v.sport}):
        try:
            games[sport]=score_fetcher(sport)
        except Exception:
            games[sport]=[]
    reports=[]
    for _,market,view in positions:
        game=match_score_game(view,games.get(view.sport,[]))
        lines=[view.matchup,view.label,f'{abs(view.qty):g} contracts']
        if game is None:
            rank=3
            lines.append('Score unavailable: no unambiguous matching game/feed coverage.')
        else:
            start=parsed_time(game.get('commence_time',''))
            pair=score_pair(game)
            if game.get('completed'):
                rank,status=2,'Final'
            elif start and start>now:
                rank,status=1,'Upcoming: '+pacific(start)
            else:
                rank,status=0,'Live' if pair else 'Started / score unavailable'
            lines.append(status)
            if pair:
                lines.append(f"{game['away_team']} {pair[1]} - {game['home_team']} {pair[0]}")
                lines.append(compare_score(view,game,now))
                lines.append('Score updated: '+pacific(game.get('last_update','')))
        reports.append((rank,view.ticker,'\n'.join(lines)))
    header='KALSHI POSITIONS & SCORES\n'+pacific(now)+'\n'
    footer='\nScores may be delayed. Live comparisons are not settled results. Quarter/clock unavailable from this feed.'
    return header+'\n\n'.join(r[2] for r in sorted(reports)) + ('\nNo open positions.' if not positions else '')+footer
