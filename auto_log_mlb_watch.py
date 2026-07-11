from bot import MLB_SPORT_KEY, evaluate_mlb_event, within_days, dedupe_exact_events, select_unique_team_results, log_pick
from app.odds_api import fetch_live_games


def main():
    events = dedupe_exact_events(fetch_live_games(MLB_SPORT_KEY, "h2h"))

    results = []
    for e in events:
        commence_time = e.get("commence_time")
        if not commence_time or not within_days(commence_time, 3):
            continue

        r = evaluate_mlb_event(e)
        if r:
            results.append(r)

    results.sort(key=lambda x: (x["ev"], x["prob"]), reverse=True)
    results = select_unique_team_results(results, limit=8)

    for r in results:
        log_pick(r, "/mlbwatch", "auto_mlbwatch")


if __name__ == "__main__":
    main()
