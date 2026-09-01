from __future__ import annotations

import asyncio

from telegram import Bot

from football_v2.config import settings
from football_v2.models import ValueComparison


def format_new_recommendations(values: list[ValueComparison]) -> str:
    lines = [f"NEW FOOTBALL V2 PAPER RECOMMENDATION{'S' if len(values) != 1 else ''}"]
    for value in values:
        proposition = (
            f"{value.selection} wins"
            if value.line is None
            else f"{value.selection} wins by over {value.line:g}"
        )
        lines.extend([
            "",
            f"{value.sport.upper()} | {value.matchup}",
            f"Contract: BUY {value.contract_side.upper()}",
            f"Proposition: {proposition}",
            (
                f"Kalshi {value.contract_side.upper()} ask: "
                f"{value.kalshi_yes_ask:.1%}"
            ),
            f"Sportsbook consensus: {value.fair_probability:.1%}",
            f"Estimated net edge: {value.net_edge:.1%}",
            f"Sportsbooks: {value.sportsbook_samples}",
            f"Kickoff: {value.commence_time}",
            "Paper tracking only. No trade was placed.",
        ])
    return "\n".join(lines)[:3900]


async def _send(text: str) -> None:
    bot = Bot(settings.telegram_bot_token)
    await bot.send_message(chat_id=settings.telegram_chat_id, text=text)


def send_telegram_message(text: str) -> None:
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        raise ValueError("Missing Football V2 Telegram configuration")
    asyncio.run(_send(text))
