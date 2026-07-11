from __future__ import annotations

from datetime import datetime, timedelta, timezone
from html import escape

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from app.config import settings
from app.odds_api import fetch_live_games, choose_bookmaker, extract_markets
from app.prediction_logger import ensure_predictions_file, log_prediction


MLB_SPORT_KEY = "baseball_mlb"

MLB_MIN_EV = 0.01
MLB_HOME_FIELD_BUMP = 0.015
MLB_HEAVY_FAVORITE_PENALTY = 0.012
MLB_CONFIDENCE_SHRINK = 0.85


def h(text):
    return escape(str(text))


def clamp_prob(p):
    return max(0.02, min(0.98, float(p)))


def american_to_implied_prob(price):
    if price is None:
        return None
    price = float(price)
    if price < 0:
        return (-price) / ((-price) + 100.0)
    return 100.0 / (price + 100.0)


def american_profit(price):
    if price is None:
        return None
    price = float(price)
    if price > 0:
        return price / 100.0
    return 100.0 / abs(price)


def strip_vig(p1, p2):
    if p1 is None or p2 is None:
        return p1, p2
    total = p1 + p2
    if total <= 0:
        return None, None
    return p1 / total, p2 / total


def expected_value(prob, price):
    if prob is None or price is None:
        return None
    profit = american_profit(price)
    return (float(prob) * profit) - (1.0 - float(prob))


def dampen_weak_ev(ev):
    if ev is None:
        return None
    if ev < 0.05:
        return ev * 0.5
    if ev < 0.15:
        return ev * 0.75
    return ev


def within_days(ts, days):
    now = datetime.now(timezone.utc)
    end = now + timedelta(days=days)
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return now <= dt <= end


def dedupe_exact_events(events):
    seen = set()
    unique = []

    for e in events:
        home = e.get("home_team", "")
        away = e.get("away_team", "")
        time = e.get("commence_time", "")
        key = (tuple(sorted([home, away])), time[:16])

        if key in seen:
            continue

        seen.add(key)
        unique.append(e)

    return unique


def select_unique_team_results(results, limit=8):
    selected = []
    used_teams = set()

    for r in results:
        home = r["home_team"]
        away = r["away_team"]

        if home in used_teams or away in used_teams:
            continue

        selected.append(r)
        used_teams.add(home)
        used_teams.add(away)

        if len(selected) >= limit:
            break

    return selected


def apply_mlb_adjustments(home_prob, away_prob, home_ml, away_ml):
    adjusted_home = float(home_prob) + MLB_HOME_FIELD_BUMP
    adjusted_away = 1.0 - adjusted_home

    if home_ml is not None and float(home_ml) <= -200:
        adjusted_home -= MLB_HEAVY_FAVORITE_PENALTY
        adjusted_away += MLB_HEAVY_FAVORITE_PENALTY

    if away_ml is not None and float(away_ml) <= -200:
        adjusted_away -= MLB_HEAVY_FAVORITE_PENALTY
        adjusted_home += MLB_HEAVY_FAVORITE_PENALTY

    adjusted_home = clamp_prob(adjusted_home)
    adjusted_away = clamp_prob(1.0 - adjusted_home)

    return adjusted_home, adjusted_away


def shrink_confidence(home_prob):
    shrunk_home = 0.5 + (float(home_prob) - 0.5) * MLB_CONFIDENCE_SHRINK
    shrunk_home = clamp_prob(shrunk_home)
    shrunk_away = clamp_prob(1.0 - shrunk_home)
    return shrunk_home, shrunk_away


def evaluate_mlb_event(event):
    home = event.get("home_team")
    away = event.get("away_team")

    if not home or not away:
        return None

    book = choose_bookmaker(event, settings.bookmaker_priority)
    if not book:
        return None

    markets = extract_markets(book, home, away)
    home_ml = markets.get("home_moneyline")
    away_ml = markets.get("away_moneyline")

    if home_ml is None and away_ml is None:
        return None

    p_home = american_to_implied_prob(home_ml)
    p_away = american_to_implied_prob(away_ml)
    p_home, p_away = strip_vig(p_home, p_away)

    if p_home is None and p_away is None:
        return None
    if p_home is None:
        p_home = 1.0 - p_away
    if p_away is None:
        p_away = 1.0 - p_home

    p_home, p_away = apply_mlb_adjustments(p_home, p_away, home_ml, away_ml)
    p_home, p_away = shrink_confidence(p_home)

    candidates = []

    if home_ml is not None and float(home_ml) < 0:
        home_ev = expected_value(p_home, home_ml)
        home_ev = dampen_weak_ev(home_ev)
        if home_ev is not None:
            candidates.append(
                {
                    "home_team": home,
                    "away_team": away,
                    "prob": p_home,
                    "price": home_ml,
                    "ev": home_ev,
                    "raw_ev": expected_value(p_home, home_ml),
                    "event_id": event.get("id"),
                    "commence_time": event.get("commence_time"),
                    "sport_key": event.get("sport_key"),
                    "pick_name": home,
                }
            )

    if away_ml is not None and float(away_ml) < 0:
        away_ev = expected_value(p_away, away_ml)
        away_ev = dampen_weak_ev(away_ev)
        if away_ev is not None:
            candidates.append(
                {
                    "home_team": home,
                    "away_team": away,
                    "prob": p_away,
                    "price": away_ml,
                    "ev": away_ev,
                    "raw_ev": expected_value(p_away, away_ml),
                    "event_id": event.get("id"),
                    "commence_time": event.get("commence_time"),
                    "sport_key": event.get("sport_key"),
                    "pick_name": away,
                }
            )

    if not candidates:
        return None

    candidates.sort(key=lambda x: (x["ev"], x["prob"]), reverse=True)
    return candidates[0]


def log_pick(result, command, text):
    log_prediction(
        source_command=command,
        request_text=text,
        game_id=result["event_id"],
        commence_time=result["commence_time"],
        sport_key=result["sport_key"],
        home_team=result["home_team"],
        away_team=result["away_team"],
        market_type="moneyline",
        pick_name=result["pick_name"],
        pick_side=result["pick_name"],
        line=None,
        odds_american=result["price"],
        probability=result["prob"],
        ev_per_dollar=result["ev"],
        is_best_ev=True,
        is_second_ev=False,
        is_safest=False,
    )


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Commands:\n"
        "/mlbtop\n"
        "/mlbwatch"
    )


async def mlbtop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        events = dedupe_exact_events(fetch_live_games(MLB_SPORT_KEY, "h2h"))

        results = []
        for e in events:
            commence_time = e.get("commence_time")
            if not commence_time or not within_days(commence_time, 3):
                continue

            r = evaluate_mlb_event(e)
            if not r:
                continue

            if r["ev"] < MLB_MIN_EV:
                continue

            results.append(r)

        if not results:
            await update.message.reply_text(
                f"No positive-EV MLB picks found. Current cutoff: EV >= {MLB_MIN_EV:.2f}"
            )
            return

        results.sort(key=lambda x: (x["ev"], x["prob"]), reverse=True)
        results = select_unique_team_results(results, limit=8)

        lines = [f"MLB Top Picks\nCutoff: EV >= {MLB_MIN_EV:.2f}"]
        for i, r in enumerate(results, 1):
            log_pick(r, "/mlbtop", "/mlbtop")
            lines.append(
                f"\n{i}. {r['away_team']} vs {r['home_team']}\n"
                f"Pick: {r['pick_name']} | Prob {r['prob']:.3f} | Price {r['price']} | EV {r['ev']:.3f}"
            )

        await update.message.reply_text("\n".join(lines))
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")


async def mlbwatch_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        events = dedupe_exact_events(fetch_live_games(MLB_SPORT_KEY, "h2h"))

        results = []
        for e in events:
            commence_time = e.get("commence_time")
            if not commence_time or not within_days(commence_time, 3):
                continue

            r = evaluate_mlb_event(e)
            if r:
                results.append(r)

        if not results:
            await update.message.reply_text("No MLB watchlist picks.")
            return

        results.sort(key=lambda x: (x["ev"], x["prob"]), reverse=True)
        results = select_unique_team_results(results, limit=8)

        lines = ["MLB Watchlist\nTop moneyline favorites ranked by EV, no cutoff"]
        for i, r in enumerate(results, 1):
            log_pick(r, "/mlbwatch", "/mlbwatch")
            lines.append(
                f"\n{i}. {r['away_team']} vs {r['home_team']}\n"
                f"Watch: {r['pick_name']} | Prob {r['prob']:.3f} | Price {r['price']} | EV {r['ev']:.3f}"
            )

        await update.message.reply_text("\n".join(lines))
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")


def main():
    if not settings.telegram_bot_token:
        raise ValueError("Missing TELEGRAM_BOT_TOKEN in .env")

    ensure_predictions_file()

    app = Application.builder().token(settings.telegram_bot_token).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("mlbtop", mlbtop_cmd))
    app.add_handler(CommandHandler("mlbwatch", mlbwatch_cmd))

    app.run_polling()


if __name__ == "__main__":
    main()
