from __future__ import annotations

from datetime import datetime, timezone

from football_v2.config import settings
from football_v2.grading import count_due_recommendations, grade_pending_recommendations
from football_v2.sportsbook import SportsbookClient
from football_v2.storage import connect


def main() -> None:
    db = connect(settings.database_path)
    pending = db.execute(
        "SELECT COUNT(*) FROM paper_recommendations WHERE status='pending'"
    ).fetchone()[0]
    due = count_due_recommendations(db, datetime.now(timezone.utc))
    if due == 0:
        print("FOOTBALL V2 PAPER GRADING")
        print(f"Pending recommendations: {pending}")
        print("Recommendations due for grading: 0")
        print("No score API request needed.")
        db.close()
        return
    results = SportsbookClient().fetch_scores(("nfl", "ncaaf"), days_from=3)
    summary = grade_pending_recommendations(db, results)
    print("FOOTBALL V2 PAPER GRADING")
    print(f"Pending recommendations: {summary.pending}")
    print(f"Recommendations due for grading: {due}")
    print(f"Completed games matched: {summary.matched}")
    print(f"Recommendations graded: {summary.graded}")
    db.close()


if __name__ == "__main__":
    main()
