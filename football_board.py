from __future__ import annotations

import argparse
from datetime import datetime, timezone

from football_v2.config import settings
from football_v2.kalshi import KalshiClient
from football_v2.matching import match_game
from football_v2.notifications import format_new_recommendations, send_telegram_message
from football_v2.sportsbook import SportsbookClient
from football_v2.storage import connect, save_run
from football_v2.value import compare_contract


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only Kalshi football value scanner")
    parser.add_argument("--sport", choices=("all","nfl","ncaaf"), default="all")
    parser.add_argument("--minimum-edge", type=float, default=settings.minimum_net_edge)
    parser.add_argument("--cost-buffer", type=float, default=settings.cost_buffer)
    parser.add_argument("--minimum-lead-minutes", type=int, default=settings.minimum_lead_minutes)
    parser.add_argument("--notify", action="store_true")
    parser.add_argument("--no-save", action="store_true")
    args = parser.parse_args(); sports = ("nfl","ncaaf") if args.sport == "all" else (args.sport,)
    observed = datetime.now(timezone.utc).isoformat()
    contracts, games = KalshiClient().fetch_contracts(sports), SportsbookClient().fetch_games(sports)
    values=[]; unmatched=unusable=0
    for contract in contracts:
        game, score = match_game(contract, games)
        if game is None: unmatched += 1; continue
        value = compare_contract(
            contract,game,score,args.minimum_edge,args.cost_buffer,args.minimum_lead_minutes
        )
        if value is None: unusable += 1; continue
        values.append(value)
    new_recommendations = []
    if not args.no_save:
        new_recommendations = save_run(connect(settings.database_path),observed,contracts,games,values)
    if args.notify and new_recommendations:
        send_telegram_message(format_new_recommendations(new_recommendations))
    qualifying=sorted((v for v in values if v.qualifies),key=lambda v:v.net_edge,reverse=True)
    print("FOOTBALL V2 PAPER SCAN")
    print(f"Sports: {', '.join(sports)}\nKalshi contracts: {len(contracts)}\nSportsbook games: {len(games)}")
    print(f"Comparable contracts: {len(values)}\nRejected unmatched/ambiguous: {unmatched}")
    print(f"Rejected without comparable prices: {unusable}\nPaper opportunities: {len(qualifying)}")
    for v in qualifying[:20]:
        line="" if v.line is None else f" | wins by > {v.line:g}"
        print(f"\n{v.sport.upper()} | {v.matchup}\n{v.selection}{line}\nKalshi ask {v.kalshi_yes_ask:.1%} | "
              f"consensus {v.fair_probability:.1%} | net edge {v.net_edge:.1%} | books {v.sportsbook_samples}")


if __name__ == "__main__": main()
