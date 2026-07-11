from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv

# Load central env
load_dotenv("/home/vandal/.env")


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str = os.getenv("MARCHMADNESS_TELEGRAM_BOT_TOKEN", "").strip()
    telegram_chat_id: str = os.getenv("MARCHMADNESS_TELEGRAM_CHAT_ID", "").strip()
    odds_api_key: str = os.getenv("ODDS_API_KEY", "").strip()
    odds_region: str = os.getenv("ODDS_REGION", "us").strip()
    bookmaker_priority: tuple[str, ...] = tuple(
        x.strip() for x in os.getenv(
            "BOOKMAKER_PRIORITY",
            "draftkings,fanduel,betmgm,espnbet"
        ).split(",") if x.strip()
    )
    sport_key: str = "basketball_ncaab"


settings = Settings()
