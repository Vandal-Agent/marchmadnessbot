from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
PREDICTIONS_FILE = DATA_DIR / "predictions.csv"

FIELDNAMES = [
    "logged_at_utc",
    "source_command",
    "request_text",
    "game_id",
    "commence_time",
    "sport_key",
    "home_team",
    "away_team",
    "market_type",
    "pick_name",
    "pick_side",
    "line",
    "odds_american",
    "probability",
    "ev_per_dollar",
    "is_best_ev",
    "is_second_ev",
    "is_safest",
]


def ensure_predictions_file() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if not PREDICTIONS_FILE.exists():
        with PREDICTIONS_FILE.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(FIELDNAMES)


def _clean(value) -> str:
    if value is None:
        return ""
    return str(value)


def _same_pick(row: dict, game_id: str, market_type: str, pick_side: str, line, odds_american) -> bool:
    return (
        row.get("game_id", "") == _clean(game_id)
        and row.get("market_type", "") == _clean(market_type)
        and row.get("pick_side", "") == _clean(pick_side)
        and row.get("line", "") == _clean(line)
        and row.get("odds_american", "") == _clean(odds_american)
    )


def prediction_already_logged(
    *,
    game_id: str,
    market_type: str,
    pick_side: str,
    line,
    odds_american,
) -> bool:
    ensure_predictions_file()

    with PREDICTIONS_FILE.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if _same_pick(row, game_id, market_type, pick_side, line, odds_american):
                return True

    return False


def log_prediction(
    *,
    source_command: str,
    request_text: str,
    game_id: str,
    commence_time: str,
    sport_key: str,
    home_team: str,
    away_team: str,
    market_type: str,
    pick_name: str,
    pick_side: str,
    line,
    odds_american,
    probability,
    ev_per_dollar,
    is_best_ev: bool = False,
    is_second_ev: bool = False,
    is_safest: bool = False,
) -> bool:
    ensure_predictions_file()

    if prediction_already_logged(
        game_id=game_id,
        market_type=market_type,
        pick_side=pick_side,
        line=line,
        odds_american=odds_american,
    ):
        return False

    with PREDICTIONS_FILE.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.now(timezone.utc).isoformat(),
            source_command,
            request_text,
            _clean(game_id),
            _clean(commence_time),
            _clean(sport_key),
            _clean(home_team),
            _clean(away_team),
            _clean(market_type),
            _clean(pick_name),
            _clean(pick_side),
            _clean(line),
            _clean(odds_american),
            _clean(probability),
            _clean(ev_per_dollar),
            str(bool(is_best_ev)),
            str(bool(is_second_ev)),
            str(bool(is_safest)),
        ])

    return True
