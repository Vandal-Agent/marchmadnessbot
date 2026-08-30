from __future__ import annotations

import re
from typing import Any, Iterable

import requests

from football_v2.config import settings
from football_v2.models import KalshiContract

BASE_URL = "https://external-api.kalshi.com/trade-api/v2"
SERIES = {
    "nfl": {"moneyline": "KXNFLGAME", "spread": "KXNFLSPREAD"},
    "ncaaf": {"moneyline": "KXNCAAFGAME", "spread": "KXNCAAFSPREAD"},
}


def _number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _price(market: dict[str, Any], stem: str) -> float | None:
    dollars = _number(market.get(f"{stem}_dollars"))
    if dollars is not None:
        return dollars
    cents = _number(market.get(stem))
    return None if cents is None else cents / 100.0


def _matchup(title: str) -> tuple[str, str]:
    cleaned = re.sub(r"\s*:\s*(spread|moneyline).*?$", "", title, flags=re.I).strip()
    parts = re.split(r"\s+(?:vs\.?|at)\s+", cleaned, maxsplit=1, flags=re.I)
    return (parts[0].strip(), parts[1].strip()) if len(parts) == 2 else ("", "")


def _spread_details(market: dict[str, Any]) -> tuple[str, float | None]:
    text = " | ".join(str(market.get(k, "")) for k in ("yes_sub_title", "subtitle", "title"))
    match = re.search(r"(.+?)\s+wins?\s+by\s+(?:more than|over)\s+(-?\d+(?:\.\d+)?)", text, re.I)
    if match:
        return match.group(1).split("|")[-1].strip(), abs(float(match.group(2)))
    line = _number(market.get("functional_strike"))
    if line is None:
        line = _number(market.get("floor_strike"))
    return str(market.get("yes_sub_title", "")).strip(), None if line is None else abs(line)


class KalshiClient:
    def __init__(self, timeout: int = settings.request_timeout) -> None:
        self.timeout = timeout
        self.session = requests.Session()

    def fetch_open_markets(self, series_ticker: str, max_pages: int = 10) -> list[dict[str, Any]]:
        cursor = ""
        rows: list[dict[str, Any]] = []
        for _ in range(max_pages):
            params = {"series_ticker": series_ticker, "status": "open", "limit": 1000, "mve_filter": "exclude"}
            if cursor:
                params["cursor"] = cursor
            response = self.session.get(f"{BASE_URL}/markets", params=params, timeout=self.timeout)
            response.raise_for_status()
            payload = response.json()
            rows.extend(payload.get("markets", []))
            cursor = payload.get("cursor", "")
            if not cursor:
                break
        return rows

    def fetch_open_events(self, series_ticker: str, max_pages: int = 10) -> dict[str, dict[str, Any]]:
        cursor = ""
        events: dict[str, dict[str, Any]] = {}
        for _ in range(max_pages):
            params = {"series_ticker": series_ticker, "status": "open", "limit": 200}
            if cursor:
                params["cursor"] = cursor
            response = self.session.get(f"{BASE_URL}/events", params=params, timeout=self.timeout)
            response.raise_for_status()
            payload = response.json()
            for event in payload.get("events", []):
                ticker = str(event.get("event_ticker", ""))
                if ticker:
                    events[ticker] = event
            cursor = payload.get("cursor", "")
            if not cursor:
                break
        return events

    def fetch_contracts(self, sports: Iterable[str]) -> list[KalshiContract]:
        contracts: list[KalshiContract] = []
        for sport in sports:
            for market_type, series_ticker in SERIES[sport].items():
                events = self.fetch_open_events(series_ticker)
                for market in self.fetch_open_markets(series_ticker):
                    market = dict(market)
                    parent = events.get(str(market.get("event_ticker", "")), {})
                    market["_event_title"] = str(parent.get("title", ""))
                    market["_event_sub_title"] = str(parent.get("sub_title", ""))
                    contract = parse_contract(market, sport, market_type, series_ticker)
                    if contract:
                        contracts.append(contract)
        return contracts


def parse_contract(market: dict[str, Any], sport: str, market_type: str, series_ticker: str) -> KalshiContract | None:
    ticker = str(market.get("ticker", "")).strip()
    title = str(market.get("title", "")).strip()
    if not ticker:
        return None
    event_title = str(market.get("_event_title", "")).strip()
    first_team, second_team = _matchup(event_title or title)
    if market_type == "spread":
        target_team, line = _spread_details(market)
    else:
        target_team, line = str(market.get("yes_sub_title", "")).strip(), None
    if not target_team and first_team and second_team:
        target_team = str(market.get("subtitle", "")).strip()
    opponent = ""
    if first_team and second_team:
        opponent = second_team if target_team.lower() in first_team.lower() else first_team
    return KalshiContract(
        ticker=ticker, event_ticker=str(market.get("event_ticker", "")), series_ticker=series_ticker,
        sport=sport, market_type=market_type, title=title, target_team=target_team,
        opponent_team=opponent, close_time=str(market.get("close_time", "")),
        yes_bid=_price(market, "yes_bid"), yes_ask=_price(market, "yes_ask"),
        no_bid=_price(market, "no_bid"), no_ask=_price(market, "no_ask"), line=line,
        volume=_number(market.get("volume_fp")) or _number(market.get("volume")) or 0.0,
        liquidity=_number(market.get("liquidity_dollars")) or _number(market.get("liquidity")) or 0.0,
        rules_primary=str(market.get("rules_primary", "")), raw=market,
    )
