from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from football_v2.models import KalshiContract, SportsbookGame, ValueComparison

SCHEMA_VERSION = 1


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path); db.execute("PRAGMA journal_mode=WAL")
    db.executescript("""
    CREATE TABLE IF NOT EXISTS schema_meta(version INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS kalshi_snapshots(id INTEGER PRIMARY KEY,observed_at TEXT NOT NULL,ticker TEXT NOT NULL,
      sport TEXT NOT NULL,market_type TEXT NOT NULL,yes_bid REAL,yes_ask REAL,no_bid REAL,no_ask REAL,
      volume REAL NOT NULL,liquidity REAL NOT NULL,raw_json TEXT NOT NULL,UNIQUE(observed_at,ticker));
    CREATE TABLE IF NOT EXISTS sportsbook_snapshots(id INTEGER PRIMARY KEY,observed_at TEXT NOT NULL,
      event_id TEXT NOT NULL,sport TEXT NOT NULL,raw_json TEXT NOT NULL,UNIQUE(observed_at,event_id));
    CREATE TABLE IF NOT EXISTS value_comparisons(id INTEGER PRIMARY KEY,observed_at TEXT NOT NULL,sport TEXT NOT NULL,
      market_type TEXT NOT NULL,kalshi_ticker TEXT NOT NULL,game_id TEXT NOT NULL,matchup TEXT NOT NULL,
      selection TEXT NOT NULL,line REAL,kalshi_yes_ask REAL NOT NULL,fair_probability REAL NOT NULL,
      sportsbook_samples INTEGER NOT NULL,edge_before_costs REAL NOT NULL,cost_buffer REAL NOT NULL,
      net_edge REAL NOT NULL,qualifies INTEGER NOT NULL,match_score REAL NOT NULL,UNIQUE(observed_at,kalshi_ticker));
    """)
    row = db.execute("SELECT version FROM schema_meta LIMIT 1").fetchone()
    if row is None: db.execute("INSERT INTO schema_meta VALUES (?)", (SCHEMA_VERSION,))
    elif row[0] != SCHEMA_VERSION: raise RuntimeError(f"Unsupported schema {row[0]}")
    db.commit(); return db


def save_run(db: sqlite3.Connection, observed_at: str, contracts: list[KalshiContract],
             games: list[SportsbookGame], values: list[ValueComparison]) -> None:
    with db:
        db.executemany("INSERT OR IGNORE INTO kalshi_snapshots VALUES(NULL,?,?,?,?,?,?,?,?,?,?,?)",
          [(observed_at,c.ticker,c.sport,c.market_type,c.yes_bid,c.yes_ask,c.no_bid,c.no_ask,c.volume,c.liquidity,
            json.dumps(c.raw,sort_keys=True)) for c in contracts])
        db.executemany("INSERT OR IGNORE INTO sportsbook_snapshots VALUES(NULL,?,?,?,?)",
          [(observed_at,g.event_id,g.sport,json.dumps(g.raw,sort_keys=True)) for g in games])
        db.executemany("INSERT OR IGNORE INTO value_comparisons VALUES(NULL,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
          [(v.observed_at,v.sport,v.market_type,v.kalshi_ticker,v.game_id,v.matchup,v.selection,v.line,
            v.kalshi_yes_ask,v.fair_probability,v.sportsbook_samples,v.edge_before_costs,v.cost_buffer,
            v.net_edge,int(v.qualifies),v.match_score) for v in values])
