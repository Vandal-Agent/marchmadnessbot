from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

from football_v2.matching import target_side_index
from football_v2.models import FootballResult


@dataclass(frozen=True)
class GradeSummary:
    pending: int
    matched: int
    graded: int


def grade_pending_recommendations(
    db: sqlite3.Connection,
    results: list[FootballResult],
) -> GradeSummary:
    by_game_id = {result.game_id: result for result in results if result.completed}
    rows = db.execute("""
      SELECT id,game_id,market_type,selection,line,entry_price
      FROM paper_recommendations WHERE status = 'pending'
      """).fetchall()
    matched = graded = 0
    graded_at = datetime.now(timezone.utc).isoformat()
    with db:
        for recommendation_id, game_id, market_type, selection, line, entry_price in rows:
            result = by_game_id.get(game_id)
            if result is None:
                continue
            matched += 1
            side = target_side_index(selection, result.home_team, result.away_team)
            if side is None:
                continue
            selected_score, opponent_score = (
                (result.home_score, result.away_score)
                if side == 0 else (result.away_score, result.home_score)
            )
            if market_type == "moneyline":
                won = selected_score > opponent_score
            elif market_type == "spread" and line is not None:
                won = selected_score - opponent_score > float(line)
            else:
                continue
            outcome = "win" if won else "loss"
            profit_loss = (1.0 - float(entry_price)) if won else -float(entry_price)
            db.execute("""
              UPDATE paper_recommendations
              SET status='graded',result=?,profit_loss=?,graded_at=?,home_score=?,away_score=?
              WHERE id=? AND status='pending'
              """, (
                outcome, profit_loss, graded_at, result.home_score, result.away_score,
                recommendation_id,
              ))
            graded += 1
    return GradeSummary(len(rows), matched, graded)
