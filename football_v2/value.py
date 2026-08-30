from __future__ import annotations

from datetime import datetime, timedelta, timezone
from statistics import median

from football_v2.matching import target_side_index
from football_v2.models import KalshiContract, SportsbookGame, ValueComparison


def american_implied_probability(price: float) -> float:
    return (-price) / ((-price) + 100.0) if price < 0 else 100.0 / (price + 100.0)


def consensus_probability(contract: KalshiContract, game: SportsbookGame) -> tuple[float | None, int]:
    probabilities: list[float] = []
    for market in game.markets:
        if market.market_type != contract.market_type or len(market.outcomes) != 2:
            continue
        index = target_side_index(
            contract.target_team,
            market.outcomes[0].name,
            market.outcomes[1].name,
        )
        if index is None:
            continue
        target, other = market.outcomes[index], market.outcomes[1 - index]
        if contract.market_type == "spread":
            if contract.line is None or target.point is None or abs(target.point + contract.line) > 0.01:
                continue
        target_p = american_implied_probability(target.price)
        other_p = american_implied_probability(other.price)
        if target_p + other_p > 0:
            probabilities.append(target_p / (target_p + other_p))
    return (median(probabilities), len(probabilities)) if probabilities else (None, 0)


def compare_contract(contract: KalshiContract, game: SportsbookGame, match_score: float,
                     minimum_net_edge: float, cost_buffer: float,
                     minimum_lead_minutes: int = 30) -> ValueComparison | None:
    if contract.yes_ask is None or not 0 < contract.yes_ask < 1:
        return None
    now = datetime.now(timezone.utc)
    try:
        commence_time = datetime.fromisoformat(game.commence_time.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None
    if commence_time.tzinfo is None:
        commence_time = commence_time.replace(tzinfo=timezone.utc)
    if commence_time <= now + timedelta(minutes=minimum_lead_minutes):
        return None
    fair, samples = consensus_probability(contract, game)
    if fair is None:
        return None
    edge, observed = fair - contract.yes_ask, now.isoformat()
    return ValueComparison(observed, contract.sport, contract.market_type, contract.ticker, game.event_id,
        game.commence_time,
        f"{game.away_team} at {game.home_team}", contract.target_team, contract.line, contract.yes_ask,
        fair, samples, edge, cost_buffer, edge-cost_buffer,
        samples >= 2 and edge-cost_buffer >= minimum_net_edge, match_score)
