from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

from football_v2.matching import target_side_index
from football_v2.models import FootballResult

_GRADED_TABLES = {
    "paper_recommendations",
    "paper_watchlist",
}


@dataclass(frozen=True)
class GradeSummary:
    pending: int
    matched: int
    graded: int


def _validate_table(table: str) -> None:
    if table not in _GRADED_TABLES:
        raise ValueError(f"Unsupported grading table: {table}")


def _count_due(
    db: sqlite3.Connection,
    table: str,
    now: datetime | None = None,
) -> int:
    _validate_table(table)
    observed = (now or datetime.now(timezone.utc)).isoformat()
    return db.execute(
        f"""
        SELECT COUNT(*) FROM {table}
        WHERE status='pending'
          AND datetime(commence_time) <= datetime(?, '-4 hours')
        """,
        (observed,),
    ).fetchone()[0]


def count_due_recommendations(
    db: sqlite3.Connection,
    now: datetime | None = None,
) -> int:
    return _count_due(db, "paper_recommendations", now)


def count_due_watchlist(
    db: sqlite3.Connection,
    now: datetime | None = None,
) -> int:
    return _count_due(db, "paper_watchlist", now)


def _grade_pending(
    db: sqlite3.Connection,
    table: str,
    results: list[FootballResult],
) -> GradeSummary:
    _validate_table(table)
    by_game_id = {
        result.game_id: result
        for result in results
        if result.completed
    }
    rows = db.execute(
        f"""
        SELECT id,game_id,market_type,selection,line,entry_price
        FROM {table} WHERE status='pending'
        """
    ).fetchall()
    matched = 0
    graded = 0
    graded_at = datetime.now(timezone.utc).isoformat()

    with db:
        for (
            entry_id,
            game_id,
            market_type,
            selection,
            line,
            entry_price,
        ) in rows:
            result = by_game_id.get(game_id)
            if result is None:
                continue

            matched += 1
            side = target_side_index(
                selection,
                result.home_team,
                result.away_team,
            )
            if side is None:
                continue

            selected_score, opponent_score = (
                (result.home_score, result.away_score)
                if side == 0
                else (result.away_score, result.home_score)
            )

            if market_type == "moneyline":
                won = selected_score > opponent_score
            elif market_type == "spread" and line is not None:
                won = (
                    selected_score - opponent_score
                    > float(line)
                )
            else:
                continue

            outcome = "win" if won else "loss"
            profit_loss = (
                1.0 - float(entry_price)
                if won
                else -float(entry_price)
            )
            db.execute(
                f"""
                UPDATE {table}
                SET status='graded',result=?,profit_loss=?,
                    graded_at=?,home_score=?,away_score=?
                WHERE id=? AND status='pending'
                """,
                (
                    outcome,
                    profit_loss,
                    graded_at,
                    result.home_score,
                    result.away_score,
                    entry_id,
                ),
            )
            graded += 1

    return GradeSummary(len(rows), matched, graded)


def grade_pending_recommendations(
    db: sqlite3.Connection,
    results: list[FootballResult],
) -> GradeSummary:
    return _grade_pending(
        db,
        "paper_recommendations",
        results,
    )


def grade_pending_watchlist(
    db: sqlite3.Connection,
    results: list[FootballResult],
) -> GradeSummary:
    return _grade_pending(
        db,
        "paper_watchlist",
        results,
    )
