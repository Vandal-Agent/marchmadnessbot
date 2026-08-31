from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

from football_v2.storage import connect

BASE_DIR = Path(__file__).resolve().parent.parent


def is_authorized_chat(
    chat_id: int | str | None,
    configured_chat_id: str,
) -> bool:
    return (
        bool(configured_chat_id)
        and str(chat_id) == configured_chat_id
    )


def latest_value_board(
    db: sqlite3.Connection,
    last_scan: str | None,
    limit: int = 5,
) -> list[tuple]:
    if not last_scan:
        return []

    rows = db.execute(
        """
        SELECT
            sport,
            market_type,
            matchup,
            selection,
            line,
            kalshi_yes_ask,
            fair_probability,
            sportsbook_samples,
            net_edge,
            qualifies
        FROM value_comparisons
        WHERE observed_at >= ?
          AND sportsbook_samples >= 2
        ORDER BY
            net_edge DESC,
            sportsbook_samples DESC,
            fair_probability DESC
        """,
        (last_scan,),
    ).fetchall()

    board = []
    seen_games = set()

    for row in rows:
        sport, _, matchup = row[:3]
        game_key = (sport, matchup)

        if game_key in seen_games:
            continue

        seen_games.add(game_key)
        board.append(row)

        if len(board) >= limit:
            break

    return board


def format_value_board(rows: list[tuple]) -> list[str]:
    lines = [
        "",
        "TOP 5 CURRENT FOOTBALL VALUE BOARD",
        "From the latest saved scan. No extra API request used.",
        "Ranked by estimated net value, not simply chance of winning.",
    ]

    if not rows:
        lines.append(
            "No valid saved comparisons are currently available."
        )
        return lines

    for rank, row in enumerate(rows, start=1):
        (
            sport,
            market_type,
            matchup,
            selection,
            line,
            kalshi_yes_ask,
            fair_probability,
            sportsbook_samples,
            net_edge,
            qualifies,
        ) = row

        verdict = (
            "OFFICIAL PAPER RECOMMENDATION"
            if qualifies
            else "WATCHLIST ONLY - NOT RECOMMENDED"
        )
        market = (
            "Moneyline"
            if market_type == "moneyline" or line is None
            else f"Wins by over {line:g}"
        )

        lines.extend(
            [
                "",
                f"{rank}. {verdict}",
                f"{sport.upper()} | {matchup}",
                f"Selection: {selection} | {market}",
                (
                    f"Kalshi YES ask: {kalshi_yes_ask:.1%} | "
                    f"Sportsbook consensus: {fair_probability:.1%}"
                ),
                (
                    f"Estimated net edge: {net_edge:+.1%} | "
                    f"Sportsbooks used: {sportsbook_samples}"
                ),
            ]
        )

    return lines


def _paper_record(
    db: sqlite3.Connection,
    table: str,
) -> tuple[int, int, int, int, float, float]:
    total = db.execute(
        f"SELECT COUNT(*) FROM {table}"
    ).fetchone()[0]
    pending = db.execute(
        f"SELECT COUNT(*) FROM {table} WHERE status='pending'"
    ).fetchone()[0]
    wins = db.execute(
        f"SELECT COUNT(*) FROM {table} WHERE result='win'"
    ).fetchone()[0]
    losses = db.execute(
        f"SELECT COUNT(*) FROM {table} WHERE result='loss'"
    ).fetchone()[0]
    profit_loss, cost = db.execute(
        f"""
        SELECT
            COALESCE(SUM(profit_loss), 0),
            COALESCE(SUM(entry_price), 0)
        FROM {table}
        WHERE status='graded'
        """
    ).fetchone()
    return total, pending, wins, losses, profit_loss, cost


def build_status(database_path: Path) -> str:
    if not database_path.exists():
        return (
            "FOOTBALL V2 PAPER STATUS\n"
            "No paper database exists yet."
        )

    db = connect(database_path)

    try:
        last_scan = db.execute(
            "SELECT MAX(observed_at) FROM scan_runs"
        ).fetchone()[0]
        official = _paper_record(
            db,
            "paper_recommendations",
        )
        watchlist = _paper_record(
            db,
            "paper_watchlist",
        )
        value_board = latest_value_board(db, last_scan)
    finally:
        db.close()

    (
        official_total,
        official_pending,
        official_wins,
        official_losses,
        official_profit_loss,
        official_cost,
    ) = official
    (
        watchlist_total,
        watchlist_pending,
        watchlist_wins,
        watchlist_losses,
        watchlist_profit_loss,
        watchlist_cost,
    ) = watchlist

    official_roi = (
        official_profit_loss / official_cost
        if official_cost
        else 0.0
    )
    watchlist_roi = (
        watchlist_profit_loss / watchlist_cost
        if watchlist_cost
        else 0.0
    )

    lines = [
        "FOOTBALL V2 PAPER STATUS",
        f"Last scan: {last_scan or 'none'}",
        "",
        "OFFICIAL RECOMMENDATIONS",
        f"Entries: {official_total}",
        f"Pending: {official_pending}",
        (
            f"Graded: {official_wins + official_losses} "
            f"({official_wins} W, {official_losses} L)"
        ),
        (
            "Gross P/L before fees: "
            f"{official_profit_loss:+.2f} per-contract dollars"
        ),
        f"Gross ROI before fees: {official_roi:+.1%}",
        "",
        "TRACKED TOP-TEN PAPER CANDIDATES",
        "Observational only. Not recommendations.",
        f"Entries: {watchlist_total}",
        f"Pending: {watchlist_pending}",
        (
            f"Graded: {watchlist_wins + watchlist_losses} "
            f"({watchlist_wins} W, {watchlist_losses} L)"
        ),
        (
            "Gross P/L before fees: "
            f"{watchlist_profit_loss:+.2f} per-contract dollars"
        ),
        f"Gross ROI before fees: {watchlist_roi:+.1%}",
    ]
    lines.extend(format_value_board(value_board))

    return "\n".join(lines)[:3900]


def run_manual_scan(timeout: int = 240) -> str:
    result = subprocess.run(
        [
            sys.executable,
            str(BASE_DIR / "football_board.py"),
            "--sport",
            "all",
        ],
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )

    if result.returncode != 0:
        return (
            "Football scan failed. "
            "Check logs/football_v2_scan.log on the server."
        )

    output = (
        result.stdout.strip()
        or "Football scan completed with no console output."
    )
    return output[:3900]
