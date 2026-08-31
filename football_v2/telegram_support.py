from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

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


def build_status(database_path: Path) -> str:
    if not database_path.exists():
        return (
            "FOOTBALL V2 PAPER STATUS\n"
            "No paper database exists yet."
        )

    db = sqlite3.connect(database_path)

    try:
        last_scan = db.execute(
            "SELECT MAX(observed_at) FROM scan_runs"
        ).fetchone()[0]
        total = db.execute(
            "SELECT COUNT(*) FROM paper_recommendations"
        ).fetchone()[0]
        pending = db.execute(
            """
            SELECT COUNT(*)
            FROM paper_recommendations
            WHERE status='pending'
            """
        ).fetchone()[0]
        wins = db.execute(
            """
            SELECT COUNT(*)
            FROM paper_recommendations
            WHERE result='win'
            """
        ).fetchone()[0]
        losses = db.execute(
            """
            SELECT COUNT(*)
            FROM paper_recommendations
            WHERE result='loss'
            """
        ).fetchone()[0]
        profit_loss, cost = db.execute(
            """
            SELECT
                COALESCE(SUM(profit_loss), 0),
                COALESCE(SUM(entry_price), 0)
            FROM paper_recommendations
            WHERE status='graded'
            """
        ).fetchone()
        value_board = latest_value_board(db, last_scan)
    finally:
        db.close()

    roi = profit_loss / cost if cost else 0.0

    lines = [
        "FOOTBALL V2 PAPER STATUS",
        f"Last scan: {last_scan or 'none'}",
        f"Official recommendations: {total}",
        f"Pending: {pending}",
        f"Graded: {wins + losses} ({wins} W, {losses} L)",
        (
            "Gross P/L before fees: "
            f"{profit_loss:+.2f} per-contract dollars"
        ),
        f"Gross ROI before fees: {roi:+.1%}",
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
