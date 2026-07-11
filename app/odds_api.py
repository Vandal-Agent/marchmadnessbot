from __future__ import annotations

from typing import Any, Optional

import requests

from app.config import settings

BASE_URL = "https://api.the-odds-api.com/v4/sports"


def _resolve_sport_key(sport_key: Optional[str] = None) -> str:
    return sport_key or settings.sport_key


def fetch_live_games(
    sport_key: Optional[str] = None,
    markets: str = "h2h,spreads",
) -> list[dict[str, Any]]:
    if not settings.odds_api_key:
        raise ValueError("Missing ODDS_API_KEY in .env")

    resolved_sport_key = _resolve_sport_key(sport_key)

    url = f"{BASE_URL}/{resolved_sport_key}/odds"
    params = {
        "apiKey": settings.odds_api_key,
        "regions": settings.odds_region,
        "markets": markets,
        "oddsFormat": "american",
        "dateFormat": "iso",
    }

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def fetch_scores(
    days_from: int = 3,
    sport_key: Optional[str] = None,
) -> list[dict[str, Any]]:
    if not settings.odds_api_key:
        raise ValueError("Missing ODDS_API_KEY in .env")

    resolved_sport_key = _resolve_sport_key(sport_key)

    url = f"{BASE_URL}/{resolved_sport_key}/scores"
    params = {
        "apiKey": settings.odds_api_key,
        "daysFrom": days_from,
        "dateFormat": "iso",
    }

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def choose_bookmaker(event: dict[str, Any], priority: tuple[str, ...]) -> dict[str, Any] | None:
    bookmakers = event.get("bookmakers", [])
    if not bookmakers:
        return None

    keyed = {b.get("key"): b for b in bookmakers}
    for key in priority:
        if key in keyed:
            return keyed[key]

    return bookmakers[0]


def extract_markets(bookmaker: dict[str, Any], home_team: str, away_team: str) -> dict[str, Any]:
    out = {
        "bookmaker": bookmaker.get("title", ""),
        "home_moneyline": None,
        "away_moneyline": None,
        "home_spread": None,
        "away_spread": None,
        "home_spread_price": None,
        "away_spread_price": None,
    }

    for market in bookmaker.get("markets", []):
        key = market.get("key")

        for outcome in market.get("outcomes", []):
            name = outcome.get("name")

            if key == "h2h":
                if name == home_team:
                    out["home_moneyline"] = outcome.get("price")
                elif name == away_team:
                    out["away_moneyline"] = outcome.get("price")

            elif key == "spreads":
                if name == home_team:
                    out["home_spread"] = outcome.get("point")
                    out["home_spread_price"] = outcome.get("price")
                elif name == away_team:
                    out["away_spread"] = outcome.get("point")
                    out["away_spread_price"] = outcome.get("price")

    return out
