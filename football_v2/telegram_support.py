from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def is_authorized_chat(chat_id: int | str | None, configured_chat_id: str) -> bool:
    return bool(configured_chat_id) and str(chat_id) == configured_chat_id


def build_status(database_path: Path) -> str:
    if not database_path.exists():
        return "FOOTBALL V2 PAPER STATUS\nNo paper database exists yet."
    db = sqlite3.connect(database_path)
    last_scan = db.execute("SELECT MAX(observed_at) FROM scan_runs").fetchone()[0]
    total = db.execute("SELECT COUNT(*) FROM paper_recommendations").fetchone()[0]
    pending = db.execute(
        "SELECT COUNT(*) FROM paper_recommendations WHERE status='pending'"
    ).fetchone()[0]
    wins = db.execute(
        "SELECT COUNT(*) FROM paper_recommendations WHERE result='win'"
    ).fetchone()[0]
    losses = db.execute(
        "SELECT COUNT(*) FROM paper_recommendations WHERE result='loss'"
    ).fetchone()[0]
    profit_loss, cost = db.execute("""
      SELECT COALESCE(SUM(profit_loss),0),COALESCE(SUM(entry_price),0)
      FROM paper_recommendations WHERE status='graded'
      """).fetchone()
    db.close()
    roi = profit_loss / cost if cost else 0.0
    return (
        "FOOTBALL V2 PAPER STATUS\n"
        f"Last scan: {last_scan or 'none'}\n"
        f"Official recommendations: {total}\n"
        f"Pending: {pending}\n"
        f"Graded: {wins + losses} ({wins} W, {losses} L)\n"
        f"Gross P/L before fees: {profit_loss:+.2f} per-contract dollars\n"
        f"Gross ROI before fees: {roi:+.1%}"
    )


def run_manual_scan(timeout: int = 240) -> str:
    result = subprocess.run(
        [sys.executable, str(BASE_DIR / "football_board.py"), "--sport", "all"],
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        return "Football scan failed. Check logs/football_v2_scan.log on the server."
    output = result.stdout.strip() or "Football scan completed with no console output."
    return output[:3900]
