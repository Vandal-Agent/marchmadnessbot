"""Pacific midnight observations in a database separate from paper tracking."""
from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

from football_v2.kalshi_account import balance_values
from football_v2.kalshi_reports import PACIFIC, pacific

HISTORY_PATH = Path(__file__).resolve().parent.parent / 'data' / 'kalshi_account.sqlite'


def cutoff_for(observed_at: datetime) -> datetime:
    if observed_at.tzinfo is None:
        raise ValueError('An aware timestamp is required')
    return datetime.combine(observed_at.astimezone(PACIFIC).date(), time(), PACIFIC).astimezone(timezone.utc)


def record_snapshot(path: Path, balance: dict, observed_at: datetime, cutoff: datetime) -> bool:
    if cutoff != cutoff_for(cutoff) or not 0 <= (observed_at-cutoff).total_seconds() <= 300:
        raise ValueError('Outside the five-minute Pacific midnight observation window')
    cash, positions = balance_values(balance)
    day = (cutoff.astimezone(PACIFIC).date()-timedelta(days=1)).isoformat()
    path.parent.mkdir(parents=True,exist_ok=True)
    with closing(sqlite3.connect(path,timeout=15)) as db, db:
        db.execute('''CREATE TABLE IF NOT EXISTS snapshots (
            day TEXT PRIMARY KEY, cutoff TEXT NOT NULL, observed_at TEXT NOT NULL,
            cash REAL NOT NULL, positions REAL NOT NULL, total REAL NOT NULL)''')
        result=db.execute('INSERT OR IGNORE INTO snapshots VALUES (?,?,?,?,?,?)',
            (day,cutoff.isoformat(),observed_at.isoformat(),cash,positions,cash+positions))
        return result.rowcount==1


def build_history(path: Path = HISTORY_PATH) -> str:
    if not path.exists():
        return 'No daily snapshots saved yet. History starts after the Pacific midnight timer is activated.'
    with closing(sqlite3.connect(path,timeout=15)) as db:
        rows=db.execute('SELECT day,observed_at,cash,positions,total FROM snapshots ORDER BY day DESC LIMIT 15').fetchall()
    if not rows:
        return 'No daily snapshots saved yet.'
    lines=['KALSHI DAILY BALANCES — PACIFIC','']
    for i,(day,observed,cash,positions,total) in enumerate(rows[:14]):
        previous=rows[i+1] if i+1<len(rows) else None
        change='baseline / prior day missing'
        if previous and datetime.fromisoformat(day).date()-datetime.fromisoformat(previous[0]).date()==timedelta(days=1):
            difference=total-previous[4]
            change=f'{"+" if difference>=0 else "-"}${abs(difference):.2f}'
        lines.extend([f'{day}: ${total:.2f} ({change})',
            f'Cash ${cash:.2f}; positions ${positions:.2f}',f'Observed: {pacific(observed)}',''])
    lines.append('Changes are account value changes, not trading profit. Deposits/withdrawals are not adjusted. '
                 'Midnight observations approximate the preceding day close. Missing days are not backfilled.')
    return '\n'.join(lines)
