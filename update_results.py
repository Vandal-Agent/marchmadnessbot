from __future__ import annotations

import csv
from pathlib import Path

from app.config import settings
from app.odds_api import fetch_scores


DATA_DIR = Path("data")
RESULTS_FILE = DATA_DIR / "results.csv"

SPORT_KEYS = [
    settings.sport_key,      # NCAA / current configured sport
    "baseball_mlb",          # MLB
]


def ensure_results_file() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if not RESULTS_FILE.exists():
        with RESULTS_FILE.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "game_id",
                "commence_time",
                "home_team",
                "away_team",
                "home_score",
                "away_score",
                "winner",
                "status",
            ])


def load_existing_game_ids() -> set[str]:
    if not RESULTS_FILE.exists():
        return set()

    with RESULTS_FILE.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return {row["game_id"] for row in reader if row.get("game_id")}


def extract_scores(event: dict):
    scores = event.get("scores") or []

    if len(scores) < 2:
        return None, None

    home_team = event.get("home_team")
    away_team = event.get("away_team")

    home_score = None
    away_score = None

    for score_item in scores:
        name = score_item.get("name")
        score = score_item.get("score")

        if name == home_team:
            home_score = score
        elif name == away_team:
            away_score = score

    try:
        home_score = int(home_score) if home_score is not None else None
        away_score = int(away_score) if away_score is not None else None
    except Exception:
        return None, None

    return home_score, away_score


def determine_winner(home_team, away_team, home_score, away_score):
    if home_score is None or away_score is None:
        return ""

    if home_score > away_score:
        return home_team
    if away_score > home_score:
        return away_team
    return "tie"


def collect_completed_games_for_sport(sport_key: str, existing_ids: set[str]) -> list[list]:
    events = fetch_scores(days_from=3, sport_key=sport_key)
    rows_to_add = []

    for event in events:
        game_id = event.get("id")
        if not game_id or game_id in existing_ids:
            continue

        if not event.get("completed"):
            continue

        home_team = event.get("home_team", "")
        away_team = event.get("away_team", "")
        commence_time = event.get("commence_time", "")
        home_score, away_score = extract_scores(event)
        winner = determine_winner(home_team, away_team, home_score, away_score)

        rows_to_add.append([
            game_id,
            commence_time,
            home_team,
            away_team,
            home_score if home_score is not None else "",
            away_score if away_score is not None else "",
            winner,
            "final",
        ])

        existing_ids.add(game_id)

    return rows_to_add


def main() -> None:
    ensure_results_file()

    existing_ids = load_existing_game_ids()
    all_rows_to_add = []

    for sport_key in SPORT_KEYS:
        try:
            rows = collect_completed_games_for_sport(sport_key, existing_ids)
            all_rows_to_add.extend(rows)
            print(f"{sport_key}: added {len(rows)} completed games.")
        except Exception as e:
            print(f"{sport_key}: error fetching scores: {e}")

    if all_rows_to_add:
        with RESULTS_FILE.open("a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerows(all_rows_to_add)

    print(f"Total added {len(all_rows_to_add)} completed games.")


if __name__ == "__main__":
    main()
