from __future__ import annotations

from datetime import datetime, timezone

from football_v2.config import settings
from football_v2.grading import (
    count_due_recommendations,
    count_due_watchlist,
    grade_pending_recommendations,
    grade_pending_watchlist,
)
from football_v2.sportsbook import SportsbookClient
from football_v2.storage import connect


def main() -> None:
    db = connect(settings.database_path)
    pending_recommendations = db.execute(
        """
        SELECT COUNT(*) FROM paper_recommendations
        WHERE status='pending'
        """
    ).fetchone()[0]
    pending_watchlist = db.execute(
        """
        SELECT COUNT(*) FROM paper_watchlist
        WHERE status='pending'
        """
    ).fetchone()[0]

    now = datetime.now(timezone.utc)
    due_recommendations = count_due_recommendations(db, now)
    due_watchlist = count_due_watchlist(db, now)

    print("FOOTBALL V2 PAPER GRADING")
    print(f"Pending recommendations: {pending_recommendations}")
    print(f"Pending top-ten candidates: {pending_watchlist}")
    print(
        "Recommendations due for grading: "
        f"{due_recommendations}"
    )
    print(
        "Top-ten candidates due for grading: "
        f"{due_watchlist}"
    )

    if due_recommendations + due_watchlist == 0:
        print("No score API request needed.")
        db.close()
        return

    results = SportsbookClient().fetch_scores(
        ("nfl", "ncaaf"),
        days_from=3,
    )
    recommendation_summary = grade_pending_recommendations(
        db,
        results,
    )
    watchlist_summary = grade_pending_watchlist(
        db,
        results,
    )

    print(
        "Completed recommendation games matched: "
        f"{recommendation_summary.matched}"
    )
    print(
        "Recommendations graded: "
        f"{recommendation_summary.graded}"
    )
    print(
        "Completed top-ten games matched: "
        f"{watchlist_summary.matched}"
    )
    print(
        "Top-ten candidates graded: "
        f"{watchlist_summary.graded}"
    )
    db.close()


if __name__ == "__main__":
    main()
