from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class KalshiContract:
    ticker: str
    event_ticker: str
    series_ticker: str
    sport: str
    market_type: str
    title: str
    target_team: str
    opponent_team: str
    close_time: str
    yes_bid: float | None
    yes_ask: float | None
    no_bid: float | None
    no_ask: float | None
    line: float | None
    volume: float
    liquidity: float
    rules_primary: str
    raw: dict[str, Any] = field(repr=False)


@dataclass(frozen=True)
class SportsbookOutcome:
    name: str
    price: float
    point: float | None = None


@dataclass(frozen=True)
class SportsbookMarket:
    bookmaker_key: str
    bookmaker_title: str
    market_type: str
    outcomes: tuple[SportsbookOutcome, ...]


@dataclass(frozen=True)
class SportsbookGame:
    event_id: str
    sport: str
    commence_time: str
    home_team: str
    away_team: str
    markets: tuple[SportsbookMarket, ...]
    raw: dict[str, Any] = field(repr=False)


@dataclass(frozen=True)
class FootballResult:
    game_id: str
    sport: str
    commence_time: str
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    completed: bool
    raw: dict[str, Any] = field(repr=False)


@dataclass(frozen=True)
class ValueComparison:
    observed_at: str
    sport: str
    market_type: str
    kalshi_ticker: str
    game_id: str
    commence_time: str
    matchup: str
    selection: str
    line: float | None
    kalshi_yes_ask: float
    fair_probability: float
    sportsbook_samples: int
    edge_before_costs: float
    cost_buffer: float
    net_edge: float
    qualifies: bool
    match_score: float
