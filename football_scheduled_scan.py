from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent


def run_scheduled_scan(
    runner: Callable[..., Any] = subprocess.run,
    top_ten_builder: Callable[[Path], str] | None = None,
    sender: Callable[[str], None] | None = None,
    database_path: Path | None = None,
) -> None:
    result = runner(
        [
            sys.executable,
            str(BASE_DIR / "football_board.py"),
            "--sport",
            "all",
            "--notify",
        ],
        cwd=BASE_DIR,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "Football value scan failed; the top ten was not sent."
        )

    if top_ten_builder is None:
        from football_v2.telegram_support import build_top_ten

        top_ten_builder = build_top_ten

    if sender is None:
        from football_v2.notifications import send_telegram_message

        sender = send_telegram_message

    if database_path is None:
        from football_v2.config import settings

        database_path = settings.database_path

    sender(top_ten_builder(database_path))
    print("Fresh Football V2 top ten sent.")


def main() -> None:
    run_scheduled_scan()


if __name__ == "__main__":
    main()
