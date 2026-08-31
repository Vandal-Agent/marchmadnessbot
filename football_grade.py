from __future__ import annotations

from football_v2.config import settings
from football_v2.grading import grade_pending_recommendations
from football_v2.sportsbook import SportsbookClient
from football_v2.storage import connect


def main() -> None:
    db = connect(settings.database_path)
    pending = db.execute(
        "SELECT COUNT(*) FROM paper_recommendations WHERE status='pending'"
    ).fetchone()[0]
    if pending == 0:
        print("FOOTBALL V2 PAPER GRADING")
        print("Pending recommendations: 0")
        print("No score API request needed.")
        db.close()
        return
    results = SportsbookClient().fetch_scores(("nfl", "ncaaf"), days_from=3)
    summary = grade_pending_recommendations(db, results)
    print("FOOTBALL V2 PAPER GRADING")
    print(f"Pending recommendations: {summary.pending}")
    print(f"Completed games matched: {summary.matched}")
    print(f"Recommendations graded: {summary.graded}")
    db.close()


if __name__ == "__main__":
    main()
