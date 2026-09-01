from __future__ import annotations

import argparse
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATABASE = BASE_DIR / "data" / "football_v2.sqlite"
DEFAULT_BACKUP_DIR = Path(
    "/home/vandal/backups/marchmadnessbot/football-v2-databases"
)
BACKUP_PREFIX = "football_v2-"


def _backup_name(now: datetime) -> str:
    observed = now.astimezone(timezone.utc)
    return f"{BACKUP_PREFIX}{observed:%Y%m%dT%H%M%SZ}.sqlite"


def _verified_backup(source: Path, temporary: Path) -> None:
    source_db = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    backup_db = sqlite3.connect(temporary)
    try:
        source_db.backup(backup_db)
        result = backup_db.execute("PRAGMA integrity_check").fetchone()
        if result is None or result[0] != "ok":
            detail = "no result" if result is None else str(result[0])
            raise RuntimeError(f"Backup integrity check failed: {detail}")
    finally:
        backup_db.close()
        source_db.close()


def _prune_backups(directory: Path, keep: int) -> list[Path]:
    backups = sorted(
        directory.glob(f"{BACKUP_PREFIX}*.sqlite"),
        key=lambda path: path.name,
        reverse=True,
    )
    removed = backups[keep:]
    for path in removed:
        path.unlink()
    return removed


def backup_database(
    source: Path,
    backup_directory: Path,
    keep: int = 14,
    now: datetime | None = None,
) -> tuple[Path, list[Path]]:
    source = source.resolve()
    backup_directory = backup_directory.resolve()

    if keep < 1:
        raise ValueError("keep must be at least 1")
    if not source.is_file():
        raise FileNotFoundError(f"Database does not exist: {source}")

    backup_directory.mkdir(parents=True, exist_ok=True)
    destination = backup_directory / _backup_name(
        now or datetime.now(timezone.utc)
    )
    temporary = backup_directory / (
        f".{destination.name}.{uuid4().hex}.tmp"
    )

    try:
        _verified_backup(source, temporary)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)

    removed = _prune_backups(backup_directory, keep)
    return destination, removed


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create and verify a live Football V2 SQLite backup"
    )
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument(
        "--backup-directory",
        type=Path,
        default=DEFAULT_BACKUP_DIR,
    )
    parser.add_argument("--keep", type=int, default=14)
    args = parser.parse_args()

    destination, removed = backup_database(
        args.database,
        args.backup_directory,
        args.keep,
    )
    print("FOOTBALL V2 DATABASE BACKUP")
    print(f"Backup: {destination}")
    print("Integrity: ok")
    print(f"Size: {destination.stat().st_size} bytes")
    print(f"Expired backups removed: {len(removed)}")


if __name__ == "__main__":
    main()
