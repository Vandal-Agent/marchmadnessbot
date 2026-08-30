from __future__ import annotations

import re
from datetime import datetime
from difflib import SequenceMatcher

from football_v2.models import KalshiContract, SportsbookGame

NFL_ALIASES = {
    "ari":"arizona cardinals","atl":"atlanta falcons","bal":"baltimore ravens","buf":"buffalo bills",
    "car":"carolina panthers","chi":"chicago bears","cin":"cincinnati bengals","cle":"cleveland browns",
    "dal":"dallas cowboys","den":"denver broncos","det":"detroit lions","gb":"green bay packers",
    "hou":"houston texans","ind":"indianapolis colts","jax":"jacksonville jaguars","kc":"kansas city chiefs",
    "lv":"las vegas raiders","lac":"los angeles chargers","lar":"los angeles rams","mia":"miami dolphins",
    "min":"minnesota vikings","ne":"new england patriots","no":"new orleans saints","nyg":"new york giants",
    "nyj":"new york jets","phi":"philadelphia eagles","pit":"pittsburgh steelers","sea":"seattle seahawks",
    "sf":"san francisco 49ers","tb":"tampa bay buccaneers","ten":"tennessee titans","was":"washington commanders",
}

TOKEN_ALIASES = {
    "st": "state",
}

IGNORED_TOKENS = {"university", "college", "football", "the"}
MINIMUM_TEAM_SCORE = 0.76
MINIMUM_SIDE_MARGIN = 0.05


def normalize_team(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", " ", value.lower().replace("&", " and ")).strip()
    if text in NFL_ALIASES:
        return NFL_ALIASES[text]
    tokens = (TOKEN_ALIASES.get(token, token) for token in text.split())
    return " ".join(token for token in tokens if token not in IGNORED_TOKENS)


def team_similarity(left: str, right: str) -> float:
    a, b = normalize_team(left), normalize_team(right)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    aa, bb = set(a.split()), set(b.split())
    if aa <= bb or bb <= aa:
        return 0.78 if min(len(aa), len(bb)) == 1 else 0.92
    return max(2 * len(aa & bb) / (len(aa) + len(bb)), SequenceMatcher(None, a, b).ratio())


def target_side_index(target_team: str, left_team: str, right_team: str) -> int | None:
    scores = (team_similarity(target_team, left_team), team_similarity(target_team, right_team))
    best_index = 0 if scores[0] >= scores[1] else 1
    if scores[best_index] < MINIMUM_TEAM_SCORE:
        return None
    if scores[best_index] - scores[1 - best_index] < MINIMUM_SIDE_MARGIN:
        return None
    return best_index


def game_match_score(contract: KalshiContract, game: SportsbookGame) -> float:
    event_date = event_date_from_ticker(contract.event_ticker)
    game_date = game.commence_time[:10]
    if event_date and game_date:
        try:
            day_gap = abs((datetime.fromisoformat(game_date) - datetime.fromisoformat(event_date)).days)
        except ValueError:
            return 0.0
        if day_gap > 1:
            return 0.0

    if not contract.opponent_team:
        return 0.0

    side_index = target_side_index(contract.target_team, game.home_team, game.away_team)
    if side_index is None:
        return 0.0

    game_teams = (game.home_team, game.away_team)
    target_score = team_similarity(contract.target_team, game_teams[side_index])
    opponent_score = team_similarity(contract.opponent_team, game_teams[1 - side_index])
    if opponent_score < MINIMUM_TEAM_SCORE:
        return 0.0
    return 0.55 * target_score + 0.45 * opponent_score


def event_date_from_ticker(event_ticker: str) -> str:
    match = re.search(r"-(\d{2})([A-Z]{3})(\d{2})", event_ticker.upper())
    if not match:
        return ""
    year, month_text, day = match.groups()
    try:
        month = datetime.strptime(month_text, "%b").month
    except ValueError:
        return ""
    return f"20{year}-{month:02d}-{int(day):02d}"


def match_game(contract: KalshiContract, games: list[SportsbookGame], minimum_score: float = 0.76,
               ambiguity_margin: float = 0.05) -> tuple[SportsbookGame | None, float]:
    candidates = sorted(((game_match_score(contract, g), g) for g in games if g.sport == contract.sport),
                        key=lambda x: x[0], reverse=True)
    if not candidates or candidates[0][0] < minimum_score:
        return None, candidates[0][0] if candidates else 0.0
    if len(candidates) > 1 and candidates[0][0] - candidates[1][0] < ambiguity_margin:
        return None, candidates[0][0]
    return candidates[0][1], candidates[0][0]
