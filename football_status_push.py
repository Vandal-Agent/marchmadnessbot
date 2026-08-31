from __future__ import annotations

from football_v2.config import settings
from football_v2.notifications import send_telegram_message
from football_v2.telegram_support import build_status


def main() -> None:
    send_telegram_message(build_status(settings.database_path))
    print("Football V2 status sent.")


if __name__ == "__main__":
    main()
