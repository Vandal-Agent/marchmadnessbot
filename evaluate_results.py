#!/usr/bin/env python3
"""
evaluate_results.py

Builds a graded betting ledger from:
- data/predictions.csv
- data/results.csv

Outputs:
- data/graded_bets.csv

Prints summary performance tables by:
- source_command
- market_type
- favorite_or_underdog
- odds_band
- ev_bucket

Also prints combo summary tables by:
- source_command + market_type
- source_command + favorite_or_underdog
- market_type + favorite_or_underdog
- source_command + market_type + favorite_or_underdog
- odds_band + favorite_or_underdog
- ev_bucket + market_type

Design goals:
- Re-runnable over all saved predictions
- Defensive against small column-name differences
- Keep logic simple and transparent
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
PREDICTIONS_CSV = DATA_DIR / "predictions.csv"
RESULTS_CSV = DATA_DIR / "results.csv"
GRADED_CSV = DATA_DIR / "graded_bets.csv"


# -----------------------------
# Helpers
# -----------------------------

def safe_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def safe_lower(value: Any) -> str:
    return safe_str(value).lower()


def parse_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    s = safe_str(value)
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def parse_int(value: Any) -> Optional[int]:
    f = parse_float(value)
    if f is None:
        return None
    try:
        return int(round(f))
    except (TypeError, ValueError):
        return None


def american_profit_per_dollar(odds_american: Any) -> Optional[float]:
    """
    Returns profit (not payout) on a $1 stake if the bet wins.
    Example:
      +150 -> 1.50
      -200 -> 0.50
    """
    odds = parse_int(odds_american)
    if odds is None or odds == 0:
        return None

    if odds > 0:
        return odds / 100.0
    return 100.0 / abs(odds)


def profit_loss_from_result(odds_american: Any, result: str) -> Optional[float]:
    """
    Profit/loss for a $1 stake.
    win  -> profit
    loss -> -1.0
    push -> 0.0
    """
    result = safe_lower(result)
    if result == "push":
        return 0.0
    if result == "loss":
        return -1.0
    if result == "win":
        return american_profit_per_dollar(odds_american)
    return None


def load_csv_rows(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return list(reader)


def find_first_key(row: Dict[str, Any], candidates: List[str]) -> Optional[str]:
    row_keys_lower = {k.lower(): k for k in row.keys()}
    for candidate in candidates:
        if candidate.lower() in row_keys_lower:
            return row_keys_lower[candidate.lower()]
    return None


def get_value(row: Dict[str, Any], candidates: List[str], default: Any = "") -> Any:
    key = find_first_key(row, candidates)
    if key is None:
        return default
    return row.get(key, default)


def normalize_team_name(name: Any) -> str:
    s = safe_lower(name)
    s = s.replace("&", "and")
    s = s.replace(".", "")
    s = s.replace(",", "")
    s = s.replace("'", "")
    s = " ".join(s.split())
    return s


def build_game_key_from_names(team_a: Any, team_b: Any) -> str:
    a = normalize_team_name(team_a)
    b = normalize_team_name(team_b)
    if not a or not b:
        return ""
    return "|".join(sorted([a, b]))


def bucket_ev(ev: Any) -> str:
    value = parse_float(ev)
    if value is None:
        return "unknown"

    if value < 0:
        return "<0"
    if value < 0.05:
        return "0.00 to 0.04"
    if value < 0.10:
        return "0.05 to 0.09"
    if value < 0.20:
        return "0.10 to 0.19"
    if value < 0.35:
        return "0.20 to 0.34"
    return "0.35+"


def bucket_odds(odds_american: Any) -> str:
    odds = parse_int(odds_american)
    if odds is None:
        return "unknown"

    if odds <= -300:
        return "-300 or worse"
    if odds <= -200:
        return "-299 to -200"
    if odds <= -150:
        return "-199 to -150"
    if odds <= -110:
        return "-149 to -110"
    if odds < 100:
        return "-109 to +99"
    if odds <= 150:
        return "+100 to +150"
    if odds <= 250:
        return "+151 to +250"
    return "+251+"


def infer_market_type(pred_row: Dict[str, Any]) -> str:
    market = safe_lower(get_value(pred_row, ["market", "market_type"]))
    if market:
        if "spread" in market:
            return "spreads"
        if "h2h" in market or "moneyline" in market or market == "ml":
            return "moneyline"
        return market

    line = parse_float(get_value(pred_row, ["line", "spread_line", "point_spread"], default=""))
    if line is not None:
        return "spreads"

    return "moneyline"


def infer_pick_side(pred_row: Dict[str, Any]) -> str:
    return safe_str(get_value(pred_row, ["pick", "pick_side", "selection", "team"]))


def infer_source_command(pred_row: Dict[str, Any]) -> str:
    return safe_str(get_value(pred_row, ["source", "source_command", "command", "tag"], default="unknown"))


def infer_game_id(pred_row: Dict[str, Any]) -> str:
    return safe_str(get_value(pred_row, ["event_id", "game_id", "id", "event"]))


def infer_date_logged(pred_row: Dict[str, Any]) -> str:
    return safe_str(get_value(pred_row, ["timestamp", "date_logged", "logged_at", "created_at"]))


# -----------------------------
# Results indexing
# -----------------------------

def build_results_indexes(results_rows: List[Dict[str, Any]]) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """
    Returns:
      by_game_id
      by_team_pair
    """
    by_game_id: Dict[str, Dict[str, Any]] = {}
    by_team_pair: Dict[str, Dict[str, Any]] = {}

    for row in results_rows:
        game_id = safe_str(get_value(row, ["event_id", "game_id", "id", "event"]))
        home_team = safe_str(get_value(row, ["home_team", "home"]))
        away_team = safe_str(get_value(row, ["away_team", "away"]))

        if game_id:
            by_game_id[game_id] = row

        key = build_game_key_from_names(home_team, away_team)
        if key:
            by_team_pair[key] = row

    return by_game_id, by_team_pair


def find_matching_result(
    pred_row: Dict[str, Any],
    results_by_id: Dict[str, Dict[str, Any]],
    results_by_pair: Dict[str, Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    game_id = infer_game_id(pred_row)
    if game_id and game_id in results_by_id:
        return results_by_id[game_id]

    home_team = safe_str(get_value(pred_row, ["home_team", "home"]))
    away_team = safe_str(get_value(pred_row, ["away_team", "away"]))
    key = build_game_key_from_names(home_team, away_team)
    if key and key in results_by_pair:
        return results_by_pair[key]

    return None


# -----------------------------
# Grading logic
# -----------------------------

def get_result_scores(result_row: Dict[str, Any]) -> Tuple[Optional[int], Optional[int]]:
    home_score = parse_int(get_value(result_row, ["home_score", "scores_home", "score_home"]))
    away_score = parse_int(get_value(result_row, ["away_score", "scores_away", "score_away"]))
    return home_score, away_score


def get_result_teams(result_row: Dict[str, Any]) -> Tuple[str, str]:
    home_team = safe_str(get_value(result_row, ["home_team", "home"]))
    away_team = safe_str(get_value(result_row, ["away_team", "away"]))
    return home_team, away_team


def determine_favorite_underdog(pred_row: Dict[str, Any], market_type: str) -> str:
    """
    Uses price/line heuristics.
    For moneyline:
      negative American odds -> favorite
      positive American odds -> underdog
    For spreads:
      negative line -> favorite
      positive line -> underdog
      0 -> pickem
    """
    if market_type == "moneyline":
        odds = parse_int(get_value(pred_row, ["price", "odds_american", "odds"]))
        if odds is None:
            return "unknown"
        return "favorite" if odds < 0 else "underdog"

    if market_type == "spreads":
        line = parse_float(get_value(pred_row, ["line", "spread_line", "point_spread"]))
        if line is None:
            return "unknown"
        if line < 0:
            return "favorite"
        if line > 0:
            return "underdog"
        return "pickem"

    return "unknown"


def grade_moneyline(pred_row: Dict[str, Any], result_row: Dict[str, Any]) -> str:
    pick_side = normalize_team_name(infer_pick_side(pred_row))
    home_team, away_team = get_result_teams(result_row)
    home_score, away_score = get_result_scores(result_row)

    if not pick_side or home_score is None or away_score is None:
        return "ungraded"

    winner = None
    if home_score > away_score:
        winner = normalize_team_name(home_team)
    elif away_score > home_score:
        winner = normalize_team_name(away_team)
    else:
        return "push"

    return "win" if pick_side == winner else "loss"


def grade_spread(pred_row: Dict[str, Any], result_row: Dict[str, Any]) -> str:
    pick_side = normalize_team_name(infer_pick_side(pred_row))
    line = parse_float(get_value(pred_row, ["line", "spread_line", "point_spread"]))
    home_team, away_team = get_result_teams(result_row)
    home_score, away_score = get_result_scores(result_row)

    if not pick_side or line is None or home_score is None or away_score is None:
        return "ungraded"

    home_norm = normalize_team_name(home_team)
    away_norm = normalize_team_name(away_team)

    if pick_side == home_norm:
        adjusted_margin = (home_score + line) - away_score
    elif pick_side == away_norm:
        adjusted_margin = (away_score + line) - home_score
    else:
        return "ungraded"

    if adjusted_margin > 0:
        return "win"
    if adjusted_margin < 0:
        return "loss"
    return "push"


def grade_prediction(pred_row: Dict[str, Any], result_row: Dict[str, Any]) -> str:
    market_type = infer_market_type(pred_row)
    if market_type == "moneyline":
        return grade_moneyline(pred_row, result_row)
    if market_type == "spreads":
        return grade_spread(pred_row, result_row)
    return "ungraded"


# -----------------------------
# Ledger row builder
# -----------------------------

def build_graded_row(pred_row: Dict[str, Any], result_row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    market_type = infer_market_type(pred_row)
    pick_side = infer_pick_side(pred_row)
    source_command = infer_source_command(pred_row)
    odds_american = get_value(pred_row, ["price", "odds_american", "odds"])
    ev_per_dollar = get_value(pred_row, ["ev", "ev_per_dollar", "expected_value"], default="")
    game_id = infer_game_id(pred_row)
    date_logged = infer_date_logged(pred_row)
    line = get_value(pred_row, ["line", "spread_line", "point_spread"], default="")

    result = grade_prediction(pred_row, result_row)
    if result == "ungraded":
        return None

    profit_loss = profit_loss_from_result(odds_american, result)
    favorite_or_underdog = determine_favorite_underdog(pred_row, market_type)
    odds_band = bucket_odds(odds_american)
    ev_bucket = bucket_ev(ev_per_dollar)

    home_team = safe_str(get_value(pred_row, ["home_team", "home"]))
    away_team = safe_str(get_value(pred_row, ["away_team", "away"]))
    commence_time = safe_str(get_value(pred_row, ["commence_time", "game_time", "start_time"]))

    result_home_team = safe_str(get_value(result_row, ["home_team", "home"]))
    result_away_team = safe_str(get_value(result_row, ["away_team", "away"]))
    result_home_score = get_value(result_row, ["home_score", "scores_home", "score_home"], default="")
    result_away_score = get_value(result_row, ["away_score", "scores_away", "score_away"], default="")

    graded_row = {
        "date_logged": date_logged,
        "commence_time": commence_time,
        "game_id": game_id,
        "home_team": home_team or result_home_team,
        "away_team": away_team or result_away_team,
        "source_command": source_command,
        "market_type": market_type,
        "pick_side": pick_side,
        "line": line,
        "odds_american": safe_str(odds_american),
        "ev_per_dollar": safe_str(ev_per_dollar),
        "result": result,
        "profit_loss": "" if profit_loss is None else f"{profit_loss:.4f}",
        "favorite_or_underdog": favorite_or_underdog,
        "odds_band": odds_band,
        "ev_bucket": ev_bucket,
        "result_home_score": safe_str(result_home_score),
        "result_away_score": safe_str(result_away_score),
    }
    return graded_row


# -----------------------------
# Summary reporting
# -----------------------------

def summarize_rows(rows: List[Dict[str, Any]], group_field: str) -> List[Dict[str, Any]]:
    grouped: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        "bets": 0,
        "wins": 0,
        "losses": 0,
        "pushes": 0,
        "profit_loss": 0.0,
    })

    for row in rows:
        key = safe_str(row.get(group_field, "unknown")) or "unknown"
        result = safe_lower(row.get("result", ""))
        pl = parse_float(row.get("profit_loss")) or 0.0

        grouped[key]["bets"] += 1
        grouped[key]["profit_loss"] += pl

        if result == "win":
            grouped[key]["wins"] += 1
        elif result == "loss":
            grouped[key]["losses"] += 1
        elif result == "push":
            grouped[key]["pushes"] += 1

    summary = []
    for key, stats in grouped.items():
        bets = stats["bets"]
        roi = stats["profit_loss"] / bets if bets else 0.0
        win_rate_base = stats["wins"] + stats["losses"]
        win_rate = (stats["wins"] / win_rate_base) if win_rate_base else 0.0

        summary.append({
            "group": key,
            "bets": bets,
            "wins": stats["wins"],
            "losses": stats["losses"],
            "pushes": stats["pushes"],
            "win_rate": win_rate,
            "profit_loss": stats["profit_loss"],
            "roi": roi,
        })

    summary.sort(key=lambda x: (x["roi"], x["profit_loss"]), reverse=True)
    return summary


def add_combo_fields(rows: List[Dict[str, Any]]) -> None:
    for row in rows:
        source = safe_str(row.get("source_command", "unknown")) or "unknown"
        market = safe_str(row.get("market_type", "unknown")) or "unknown"
        fave_dog = safe_str(row.get("favorite_or_underdog", "unknown")) or "unknown"
        odds_band = safe_str(row.get("odds_band", "unknown")) or "unknown"
        ev_bucket = safe_str(row.get("ev_bucket", "unknown")) or "unknown"

        row["combo_source_market"] = f"{source} | {market}"
        row["combo_source_fave_dog"] = f"{source} | {fave_dog}"
        row["combo_market_fave_dog"] = f"{market} | {fave_dog}"
        row["combo_source_market_fave_dog"] = f"{source} | {market} | {fave_dog}"
        row["combo_oddsband_fave_dog"] = f"{odds_band} | {fave_dog}"
        row["combo_evbucket_market"] = f"{ev_bucket} | {market}"


def print_summary_table(
    title: str,
    rows: List[Dict[str, Any]],
    group_field: str,
    min_bets: int = 1,
) -> None:
    summary = summarize_rows(rows, group_field)
    summary = [item for item in summary if item["bets"] >= min_bets]

    print()
    print("=" * 100)
    print(title)
    print("=" * 100)

    if not summary:
        print(f"No graded rows with at least {min_bets} bets.")
        return

    header = f"{'Group':<42} {'Bets':>5} {'W':>4} {'L':>4} {'P':>4} {'Win%':>8} {'P/L':>10} {'ROI':>9}"
    print(header)
    print("-" * len(header))

    for item in summary:
        print(
            f"{item['group'][:42]:<42} "
            f"{item['bets']:>5} "
            f"{item['wins']:>4} "
            f"{item['losses']:>4} "
            f"{item['pushes']:>4} "
            f"{item['win_rate'] * 100:>7.1f}% "
            f"{item['profit_loss']:>10.2f} "
            f"{item['roi']:>8.3f}"
        )


# -----------------------------
# Main
# -----------------------------

def main() -> None:
    predictions = load_csv_rows(PREDICTIONS_CSV)
    results = load_csv_rows(RESULTS_CSV)

    results_by_id, results_by_pair = build_results_indexes(results)

    graded_rows: List[Dict[str, Any]] = []
    matched_predictions = 0
    unmatched_predictions = 0
    ungraded_predictions = 0

    for pred in predictions:
        result_row = find_matching_result(pred, results_by_id, results_by_pair)
        if result_row is None:
            unmatched_predictions += 1
            continue

        matched_predictions += 1
        graded = build_graded_row(pred, result_row)
        if graded is None:
            ungraded_predictions += 1
            continue

        graded_rows.append(graded)

    add_combo_fields(graded_rows)

    GRADED_CSV.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "date_logged",
        "commence_time",
        "game_id",
        "home_team",
        "away_team",
        "source_command",
        "market_type",
        "pick_side",
        "line",
        "odds_american",
        "ev_per_dollar",
        "result",
        "profit_loss",
        "favorite_or_underdog",
        "odds_band",
        "ev_bucket",
        "combo_source_market",
        "combo_source_fave_dog",
        "combo_market_fave_dog",
        "combo_source_market_fave_dog",
        "combo_oddsband_fave_dog",
        "combo_evbucket_market",
        "result_home_score",
        "result_away_score",
    ]

    with GRADED_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(graded_rows)

    print()
    print("Finished grading predictions")
    print(f"Predictions loaded:      {len(predictions)}")
    print(f"Results loaded:          {len(results)}")
    print(f"Matched predictions:     {matched_predictions}")
    print(f"Unmatched predictions:   {unmatched_predictions}")
    print(f"Ungraded after match:    {ungraded_predictions}")
    print(f"Graded rows written:     {len(graded_rows)}")
    print(f"Output file:             {GRADED_CSV}")

    # Single-field summaries
    print_summary_table("Summary by Source Command", graded_rows, "source_command")
    print_summary_table("Summary by Market Type", graded_rows, "market_type")
    print_summary_table("Summary by Favorite or Underdog", graded_rows, "favorite_or_underdog")
    print_summary_table("Summary by Odds Band", graded_rows, "odds_band")
    print_summary_table("Summary by EV Bucket", graded_rows, "ev_bucket")

    # Combo summaries
    print_summary_table(
        "Combo Summary: Source Command + Market Type",
        graded_rows,
        "combo_source_market",
        min_bets=1,
    )
    print_summary_table(
        "Combo Summary: Source Command + Favorite or Underdog",
        graded_rows,
        "combo_source_fave_dog",
        min_bets=1,
    )
    print_summary_table(
        "Combo Summary: Market Type + Favorite or Underdog",
        graded_rows,
        "combo_market_fave_dog",
        min_bets=1,
    )
    print_summary_table(
        "Combo Summary: Source Command + Market Type + Favorite or Underdog",
        graded_rows,
        "combo_source_market_fave_dog",
        min_bets=1,
    )
    print_summary_table(
        "Combo Summary: Odds Band + Favorite or Underdog",
        graded_rows,
        "combo_oddsband_fave_dog",
        min_bets=1,
    )
    print_summary_table(
        "Combo Summary: EV Bucket + Market Type",
        graded_rows,
        "combo_evbucket_market",
        min_bets=1,
    )

    # More useful filtered combo views
    print_summary_table(
        "Combo Summary: Source + Market + Favorite/Underdog (min 3 bets)",
        graded_rows,
        "combo_source_market_fave_dog",
        min_bets=3,
    )
    print_summary_table(
        "Combo Summary: Odds Band + Favorite/Underdog (min 3 bets)",
        graded_rows,
        "combo_oddsband_fave_dog",
        min_bets=3,
    )
    print_summary_table(
        "Combo Summary: EV Bucket + Market Type (min 3 bets)",
        graded_rows,
        "combo_evbucket_market",
        min_bets=3,
    )


if __name__ == "__main__":
    main()
