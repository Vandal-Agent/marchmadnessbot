from __future__ import annotations

import sqlite3
from pathlib import Path

from football_v2.models import KalshiContract, SportsbookGame, ValueComparison

SCHEMA_VERSION = 4


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.execute("PRAGMA journal_mode=WAL")
    db.executescript("""
    CREATE TABLE IF NOT EXISTS schema_meta(version INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS kalshi_snapshots(id INTEGER PRIMARY KEY,observed_at TEXT NOT NULL,ticker TEXT NOT NULL,
      sport TEXT NOT NULL,market_type TEXT NOT NULL,yes_bid REAL,yes_ask REAL,no_bid REAL,no_ask REAL,
      volume REAL NOT NULL,liquidity REAL NOT NULL,raw_json TEXT NOT NULL,UNIQUE(observed_at,ticker));
    CREATE TABLE IF NOT EXISTS sportsbook_snapshots(id INTEGER PRIMARY KEY,observed_at TEXT NOT NULL,
      event_id TEXT NOT NULL,sport TEXT NOT NULL,raw_json TEXT NOT NULL,UNIQUE(observed_at,event_id));
    CREATE TABLE IF NOT EXISTS value_comparisons(id INTEGER PRIMARY KEY,observed_at TEXT NOT NULL,sport TEXT NOT NULL,
      market_type TEXT NOT NULL,kalshi_ticker TEXT NOT NULL,game_id TEXT NOT NULL,commence_time TEXT NOT NULL,
      matchup TEXT NOT NULL,
      selection TEXT NOT NULL,line REAL,kalshi_yes_ask REAL NOT NULL,fair_probability REAL NOT NULL,
      sportsbook_samples INTEGER NOT NULL,edge_before_costs REAL NOT NULL,cost_buffer REAL NOT NULL,
      net_edge REAL NOT NULL,qualifies INTEGER NOT NULL,match_score REAL NOT NULL,UNIQUE(observed_at,kalshi_ticker));
    CREATE TABLE IF NOT EXISTS scan_runs(observed_at TEXT PRIMARY KEY,kalshi_contracts INTEGER NOT NULL,
      sportsbook_games INTEGER NOT NULL,comparable_contracts INTEGER NOT NULL,
      qualifying_recommendations INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS paper_recommendations(id INTEGER PRIMARY KEY,first_seen_at TEXT NOT NULL,
      sport TEXT NOT NULL,market_type TEXT NOT NULL,kalshi_ticker TEXT NOT NULL UNIQUE,game_id TEXT NOT NULL,
      commence_time TEXT NOT NULL,
      matchup TEXT NOT NULL,selection TEXT NOT NULL,line REAL,entry_price REAL NOT NULL,
      fair_probability REAL NOT NULL,sportsbook_samples INTEGER NOT NULL,edge_before_costs REAL NOT NULL,
      cost_buffer REAL NOT NULL,net_edge REAL NOT NULL,match_score REAL NOT NULL,
      status TEXT NOT NULL DEFAULT 'pending',result TEXT,profit_loss REAL,graded_at TEXT);
    """)
    for table in ("value_comparisons", "paper_recommendations"):
        columns = {row[1] for row in db.execute(f"PRAGMA table_info({table})")}
        if "commence_time" not in columns:
            db.execute(f"ALTER TABLE {table} ADD COLUMN commence_time TEXT NOT NULL DEFAULT ''")
    recommendation_columns = {row[1] for row in db.execute("PRAGMA table_info(paper_recommendations)")}
    for column in ("home_score", "away_score"):
        if column not in recommendation_columns:
            db.execute(f"ALTER TABLE paper_recommendations ADD COLUMN {column} INTEGER")
    row = db.execute("SELECT version FROM schema_meta LIMIT 1").fetchone()
    if row is None:
        db.execute("INSERT INTO schema_meta VALUES (?)", (SCHEMA_VERSION,))
    elif row[0] in (1, 2, 3):
        db.execute("UPDATE schema_meta SET version = ?", (SCHEMA_VERSION,))
    elif row[0] != SCHEMA_VERSION:
        raise RuntimeError(f"Unsupported schema {row[0]}")
    db.commit()
    return db


def save_run(db: sqlite3.Connection, observed_at: str, contracts: list[KalshiContract],
             games: list[SportsbookGame], values: list[ValueComparison]) -> list[ValueComparison]:
    qualifying = [value for value in values if value.qualifies]
    new_recommendations: list[ValueComparison] = []
    with db:
        db.execute(
            "INSERT OR IGNORE INTO scan_runs VALUES(?,?,?,?,?)",
            (observed_at, len(contracts), len(games), len(values), len(qualifying)),
        )
        db.executemany("""
          INSERT OR IGNORE INTO value_comparisons(
            observed_at,sport,market_type,kalshi_ticker,game_id,commence_time,matchup,selection,line,
            kalshi_yes_ask,fair_probability,sportsbook_samples,edge_before_costs,cost_buffer,net_edge,
            qualifies,match_score
          ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
          """,
          [(v.observed_at,v.sport,v.market_type,v.kalshi_ticker,v.game_id,v.commence_time,v.matchup,v.selection,v.line,
            v.kalshi_yes_ask,v.fair_probability,v.sportsbook_samples,v.edge_before_costs,v.cost_buffer,
            v.net_edge,int(v.qualifies),v.match_score) for v in values])
        for value in qualifying:
            cursor = db.execute("""
              INSERT OR IGNORE INTO paper_recommendations(
                first_seen_at,sport,market_type,kalshi_ticker,game_id,commence_time,matchup,selection,line,entry_price,
                fair_probability,sportsbook_samples,edge_before_costs,cost_buffer,net_edge,match_score
              ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
              """, (
                value.observed_at,value.sport,value.market_type,value.kalshi_ticker,value.game_id,
                value.commence_time,value.matchup,value.selection,value.line,value.kalshi_yes_ask,
                value.fair_probability,value.sportsbook_samples,value.edge_before_costs,value.cost_buffer,
                value.net_edge,value.match_score,
              ))
            if cursor.rowcount == 1:
                new_recommendations.append(value)
    return new_recommendations
