from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv("/home/vandal/.env")


@dataclass(frozen=True)
class FootballSettings:
    odds_api_key: str = os.getenv("ODDS_API_KEY", "").strip()
    odds_region: str = os.getenv("ODDS_REGION", "us").strip()
    database_path: Path = BASE_DIR / "data" / "football_v2.sqlite"
    minimum_net_edge: float = float(os.getenv("FOOTBALL_MIN_NET_EDGE", "0.05"))
    cost_buffer: float = float(os.getenv("KALSHI_COST_BUFFER", "0.02"))
    request_timeout: int = 30


settings = FootballSettings()
