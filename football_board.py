from __future__ import annotations

import argparse
from datetime import datetime, timezone

from football_v2.config import settings
from football_v2.kalshi import KalshiClient
from football_v2.matching import match_game
from football_v2.notifications import (
    format_new_recommendations,
    send_telegram_message,
)
from football_v2.sportsbook import SportsbookClient
from football_v2.storage import connect, save_run
from football_v2.value import compare_contract


def rank_value_board(values: list, limit: int = 5) -> list:
    """Return the strongest valid comparison from each distinct game."""
    ranked = sorted(
        (value for value in values if value.sportsbook_samples >= 2),
        key=lambda value: (
            value.net_edge,
            value.sportsbook_samples,
            value.fair_probability,
        ),
        reverse=True,
    )

    board = []
    seen_games = set()

    for value in ranked:
        game_key = (value.sport, value.matchup)

        if game_key in seen_games:
            continue

        seen_games.add(game_key)
        board.append(value)

        if len(board) >= limit:
            break

    return board


def print_value_board(values: list) -> None:
    board = rank_value_board(values)

    print()
    print("TOP 5 FOOTBALL VALUE BOARD")
    print("Ranked by estimated net value, not simply chance of winning.")
    print("WATCHLIST entries are manual-review choices, not recommendations.")

    if not board:
        print("No valid value comparisons are currently available.")
        return

    for rank, value in enumerate(board, start=1):
        verdict = (
            "OFFICIAL PAPER RECOMMENDATION"
            if value.qualifies
            else "WATCHLIST ONLY - NOT RECOMMENDED"
        )
        market = (
            "Moneyline"
            if value.line is None
            else f"Wins by over {value.line:g}"
        )

        print()
        print(f"{rank}. {verdict}")
        print(f"{value.sport.upper()} | {value.matchup}")
        print(f"Selection: {value.selection} | {market}")
        print(f"Kalshi YES ask: {value.kalshi_yes_ask:.1%}")
        print(f"Sportsbook consensus: {value.fair_probability:.1%}")
        print(f"Estimated net edge: {value.net_edge:+.1%}")
        print(f"Sportsbooks used: {value.sportsbook_samples}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read-only Kalshi football value scanner"
    )
    parser.add_argument(
        "--sport",
        choices=("all", "nfl", "ncaaf"),
        default="all",
    )
    parser.add_argument(
        "--minimum-edge",
        type=float,
        default=settings.minimum_net_edge,
    )
    parser.add_argument(
        "--cost-buffer",
        type=float,
        default=settings.cost_buffer,
    )
    parser.add_argument(
        "--minimum-lead-minutes",
        type=int,
        default=settings.minimum_lead_minutes,
    )
    parser.add_argument("--notify", action="store_true")
    parser.add_argument("--no-save", action="store_true")
    args = parser.parse_args()

    sports = (
        ("nfl", "ncaaf")
        if args.sport == "all"
        else (args.sport,)
    )
    observed = datetime.now(timezone.utc).isoformat()

    contracts = KalshiClient().fetch_contracts(sports)
    games = SportsbookClient().fetch_games(sports)

    values = []
    unmatched = 0
    unusable = 0

    for contract in contracts:
        game, score = match_game(contract, games)

        if game is None:
            unmatched += 1
            continue

        value = compare_contract(
            contract,
            game,
            score,
            args.minimum_edge,
            args.cost_buffer,
            args.minimum_lead_minutes,
        )

        if value is None:
            unusable += 1
            continue

        values.append(value)

    new_recommendations = []

    if not args.no_save:
        new_recommendations = save_run(
            connect(settings.database_path),
            observed,
            contracts,
            games,
            values,
        )

    if args.notify and new_recommendations:
        send_telegram_message(
            format_new_recommendations(new_recommendations)
        )

    qualifying = [
        value for value in values
        if value.qualifies
    ]

    print("FOOTBALL V2 PAPER SCAN")
    print(f"Sports: {', '.join(sports)}")
    print(f"Kalshi contracts: {len(contracts)}")
    print(f"Sportsbook games: {len(games)}")
    print(f"Comparable contracts: {len(values)}")
    print(f"Rejected unmatched/ambiguous: {unmatched}")
    print(f"Rejected without comparable prices: {unusable}")
    print(f"Official paper opportunities: {len(qualifying)}")

    print_value_board(values)


if __name__ == "__main__":
    main()