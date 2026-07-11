from app.odds_api import fetch_scores

for days in [3, 7, 14, 30, 60, 90]:
    try:
        games = fetch_scores(days_from=days, sport_key="baseball_mlb")
        completed = [g for g in games if g.get("completed")]
        print(f"days_from={days}: total={len(games)} completed={len(completed)}")
    except Exception as e:
        print(f"days_from={days}: ERROR {e}")
