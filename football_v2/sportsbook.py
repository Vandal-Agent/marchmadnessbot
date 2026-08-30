from __future__ import annotations

from typing import Any, Iterable

import requests

from football_v2.config import settings
from football_v2.models import SportsbookGame, SportsbookMarket, SportsbookOutcome

BASE_URL = "https://api.the-odds-api.com/v4/sports"
SPORT_KEYS = {"nfl": "americanfootball_nfl", "ncaaf": "americanfootball_ncaaf"}


class SportsbookClient:
    def __init__(self, api_key: str = settings.odds_api_key, timeout: int = settings.request_timeout) -> None:
        self.api_key, self.timeout, self.session = api_key, timeout, requests.Session()

    def fetch_games(self, sports: Iterable[str]) -> list[SportsbookGame]:
        if not self.api_key:
            raise ValueError("Missing ODDS_API_KEY in /home/vandal/.env")
        games: list[SportsbookGame] = []
        for sport in sports:
            response = self.session.get(
                f"{BASE_URL}/{SPORT_KEYS[sport]}/odds",
                params={"apiKey": self.api_key, "regions": settings.odds_region,
                        "markets": "h2h,spreads", "oddsFormat": "american", "dateFormat": "iso"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            games.extend(parse_game(row, sport) for row in response.json())
        return games


def parse_game(row: dict[str, Any], sport: str) -> SportsbookGame:
    markets: list[SportsbookMarket] = []
    for bookmaker in row.get("bookmakers", []):
        for market in bookmaker.get("markets", []):
            if market.get("key") not in {"h2h", "spreads"}:
                continue
            outcomes = tuple(
                SportsbookOutcome(str(o.get("name", "")), float(o["price"]),
                                   None if o.get("point") is None else float(o["point"]))
                for o in market.get("outcomes", []) if o.get("name") and o.get("price") is not None
            )
            if len(outcomes) == 2:
                markets.append(SportsbookMarket(str(bookmaker.get("key", "")),
                    str(bookmaker.get("title", "")), "moneyline" if market.get("key") == "h2h" else "spread", outcomes))
    return SportsbookGame(str(row.get("id", "")), sport, str(row.get("commence_time", "")),
                          str(row.get("home_team", "")), str(row.get("away_team", "")), tuple(markets), row)
