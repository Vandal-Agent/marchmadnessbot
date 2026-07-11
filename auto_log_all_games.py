from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.odds_api import fetch_live_games
from app.config import settings
from app.prediction_logger import ensure_predictions_file, log_prediction
from bot import evaluate_event


def within_days(commence_time: str, days: int) -> bool:
    now_utc = datetime.now(timezone.utc)
    end_utc = now_utc + timedelta(days=days)
    dt = datetime.fromisoformat(commence_time.replace("Z", "+00:00"))
    return now_utc <= dt <= end_utc


def is_valid_baseline_pick(result: dict) -> bool:
    pick = result.get("safest_data")
    if not pick:
        return False

    # Only moneyline
    if pick.get("market_type") != "moneyline":
        return False

    # Only favorites (negative odds)
    price = pick.get("price")
    if price is None or float(price) >= 0:
        return False

    return True


def log_baseline_pick(result: dict):
    pick = result["safest_data"]

    log_prediction(
        source_command="/baseline",
        request_text="/baseline",
        game_id=result.get("event_id", ""),
        commence_time=result.get("commence_time", ""),
        sport_key=result.get("sport_key", ""),
        home_team=result.get("home_team", ""),
        away_team=result.get("away_team", ""),
        market_type=pick.get("market_type", ""),
        pick_name=pick.get("pick_name", ""),
        pick_side=pick.get("pick_side", ""),
        line=pick.get("line"),
        odds_american=pick.get("price"),
        probability=pick.get("prob"),
        ev_per_dollar=pick.get("ev"),
        is_best_ev=False,
        is_second_ev=False,
        is_safest=True,
    )


def main():
    ensure_predictions_file()

    events = fetch_live_games()

    games_seen = 0
    picks_logged = 0

    for event in events:
        commence_time = event.get("commence_time")
        if not commence_time:
            continue

        if not within_days(commence_time, 2):
            continue

        result = evaluate_event(event)
        if not result:
            continue

        games_seen += 1

        if is_valid_baseline_pick(result):
            log_baseline_pick(result)
            picks_logged += 1

    print(f"Evaluated {games_seen} games.")
    print(f"Logged {picks_logged} baseline picks.")


if __name__ == "__main__":
    main()
