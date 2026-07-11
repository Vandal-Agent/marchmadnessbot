from __future__ import annotations

import requests
from pathlib import Path

from app.config import settings


LOG_FILE = Path("logs/eval.log")


def get_last_report() -> str:
    if not LOG_FILE.exists():
        return "No evaluation data yet."

    lines = LOG_FILE.read_text(encoding="utf-8").strip().split("\n")

    if not lines:
        return "No evaluation data yet."

    # grab last ~20 lines for context
    return "\n".join(lines[-20:])


def send_telegram_message(text: str):
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        print("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")
        return

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"

    payload = {
        "chat_id": settings.telegram_chat_id,
        "text": text,
        "parse_mode": "Markdown",
    }

    response = requests.post(url, json=payload, timeout=30)

    if response.status_code != 200:
        print("Failed to send message:", response.text)
    else:
        print("Message sent.")


def main():
    report = get_last_report()

    message = f"*Daily Betting Report*\n\n```\n{report}\n```"

    send_telegram_message(message)


if __name__ == "__main__":
    main()
