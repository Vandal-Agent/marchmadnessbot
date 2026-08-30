from __future__ import annotations

import re
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


def normalize_team(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", " ", value.lower().replace("&", " and ")).strip()
    return NFL_ALIASES.get(text, " ".join(t for t in text.split() if t not in {"university","college","football","the"}))


def team_similarity(left: str, right: str) -> float:
    a, b = normalize_team(left), normalize_team(right)
    if not a or not b: return 0.0
    if a == b: return 1.0
    aa, bb = set(a.split()), set(b.split())
    if aa <= bb or bb <= aa: return 0.78 if min(len(aa), len(bb)) == 1 else 0.92
    return max(2 * len(aa & bb) / (len(aa) + len(bb)), SequenceMatcher(None, a, b).ratio())


def game_match_score(contract: KalshiContract, game: SportsbookGame) -> float:
    home = team_similarity(contract.target_team, game.home_team)
    away = team_similarity(contract.target_team, game.away_team)
    target = max(home, away)
    if not contract.opponent_team: return target
    opponent = team_similarity(contract.opponent_team, game.away_team if home >= away else game.home_team)
    return 0.65 * target + 0.35 * opponent


def match_game(contract: KalshiContract, games: list[SportsbookGame], minimum_score: float = 0.76,
               ambiguity_margin: float = 0.05) -> tuple[SportsbookGame | None, float]:
    candidates = sorted(((game_match_score(contract, g), g) for g in games if g.sport == contract.sport),
                        key=lambda x: x[0], reverse=True)
    if not candidates or candidates[0][0] < minimum_score: return None, candidates[0][0] if candidates else 0.0
    if len(candidates) > 1 and candidates[0][0] - candidates[1][0] < ambiguity_margin: return None, candidates[0][0]
    return candidates[0][1], candidates[0][0]
