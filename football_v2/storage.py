from __future__ import annotations

import sqlite3
from pathlib import Path

from football_v2.models import KalshiContract, SportsbookGame, ValueComparison

SCHEMA_VERSION = 6


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
      status TEXT NOT NULL DEFAULT 'pending',result TEXT,profit_loss REAL,graded_at TEXT,
      home_score INTEGER,away_score INTEGER);
    CREATE TABLE IF NOT EXISTS paper_watchlist(id INTEGER PRIMARY KEY,first_seen_at TEXT NOT NULL,
      first_seen_rank INTEGER NOT NULL,sport TEXT NOT NULL,market_type TEXT NOT NULL,
      kalshi_ticker TEXT NOT NULL UNIQUE,game_id TEXT NOT NULL,commence_time TEXT NOT NULL,
      matchup TEXT NOT NULL,selection TEXT NOT NULL,line REAL,entry_price REAL NOT NULL,
      fair_probability REAL NOT NULL,sportsbook_samples INTEGER NOT NULL,edge_before_costs REAL NOT NULL,
      cost_buffer REAL NOT NULL,net_edge REAL NOT NULL,qualifies_at_entry INTEGER NOT NULL,
      match_score REAL NOT NULL,status TEXT NOT NULL DEFAULT 'pending',result TEXT,
      profit_loss REAL,graded_at TEXT,home_score INTEGER,away_score INTEGER);
    """)
    for table in ("value_comparisons", "paper_recommendations"):
        columns = {
            row[1]
            for row in db.execute(f"PRAGMA table_info({table})")
        }
        if "commence_time" not in columns:
            db.execute(
                f"ALTER TABLE {table} "
                "ADD COLUMN commence_time TEXT NOT NULL DEFAULT ''"
            )
    for table in ("paper_recommendations", "paper_watchlist"):
        columns = {
            row[1]
            for row in db.execute(f"PRAGMA table_info({table})")
        }
        for column in ("home_score", "away_score"):
            if column not in columns:
                db.execute(
                    f"ALTER TABLE {table} ADD COLUMN {column} INTEGER"
                )
    for table in (
        "value_comparisons",
        "paper_recommendations",
        "paper_watchlist",
    ):
        columns = {
            row[1]
            for row in db.execute(f"PRAGMA table_info({table})")
        }
        if "contract_side" not in columns:
            db.execute(
                f"ALTER TABLE {table} ADD COLUMN "
                "contract_side TEXT NOT NULL DEFAULT 'yes'"
            )
    row = db.execute(
        "SELECT version FROM schema_meta LIMIT 1"
    ).fetchone()
    if row is None:
        db.execute(
            "INSERT INTO schema_meta VALUES (?)",
            (SCHEMA_VERSION,),
        )
    elif row[0] in (1, 2, 3, 4, 5):
        db.execute(
            "UPDATE schema_meta SET version = ?",
            (SCHEMA_VERSION,),
        )
    elif row[0] != SCHEMA_VERSION:
        raise RuntimeError(f"Unsupported schema {row[0]}")
    db.commit()
    return db


def save_run(
    db: sqlite3.Connection,
    observed_at: str,
    contracts: list[KalshiContract],
    games: list[SportsbookGame],
    values: list[ValueComparison],
    tracked_watchlist: list[ValueComparison] | None = None,
) -> list[ValueComparison]:
    qualifying = [value for value in values if value.qualifies]
    new_recommendations: list[ValueComparison] = []
    watchlist = tracked_watchlist or []

    with db:
        db.execute(
            "INSERT OR IGNORE INTO scan_runs VALUES(?,?,?,?,?)",
            (
                observed_at,
                len(contracts),
                len(games),
                len(values),
                len(qualifying),
            ),
        )
        db.executemany(
            """
            INSERT OR IGNORE INTO value_comparisons(
              observed_at,sport,market_type,kalshi_ticker,game_id,commence_time,matchup,selection,line,
              kalshi_yes_ask,fair_probability,sportsbook_samples,edge_before_costs,cost_buffer,net_edge,
              qualifies,match_score,contract_side
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            [
                (
                    value.observed_at,
                    value.sport,
                    value.market_type,
                    value.kalshi_ticker,
                    value.game_id,
                    value.commence_time,
                    value.matchup,
                    value.selection,
                    value.line,
                    value.kalshi_yes_ask,
                    value.fair_probability,
                    value.sportsbook_samples,
                    value.edge_before_costs,
                    value.cost_buffer,
                    value.net_edge,
                    int(value.qualifies),
                    value.match_score,
                    value.contract_side,
                )
                for value in values
            ],
        )
        for rank, value in enumerate(watchlist, start=1):
            db.execute(
                """
                INSERT OR IGNORE INTO paper_watchlist(
                  first_seen_at,first_seen_rank,sport,market_type,kalshi_ticker,game_id,commence_time,
                  matchup,selection,line,entry_price,fair_probability,sportsbook_samples,
                  edge_before_costs,cost_buffer,net_edge,qualifies_at_entry,match_score,contract_side
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    value.observed_at,
                    rank,
                    value.sport,
                    value.market_type,
                    value.kalshi_ticker,
                    value.game_id,
                    value.commence_time,
                    value.matchup,
                    value.selection,
                    value.line,
                    value.kalshi_yes_ask,
                    value.fair_probability,
                    value.sportsbook_samples,
                    value.edge_before_costs,
                    value.cost_buffer,
                    value.net_edge,
                    int(value.qualifies),
                    value.match_score,
                    value.contract_side,
                ),
            )
        for value in qualifying:
            cursor = db.execute(
                """
                INSERT OR IGNORE INTO paper_recommendations(
                  first_seen_at,sport,market_type,kalshi_ticker,game_id,commence_time,matchup,selection,line,
                  entry_price,fair_probability,sportsbook_samples,edge_before_costs,cost_buffer,net_edge,match_score,
                  contract_side
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    value.observed_at,
                    value.sport,
                    value.market_type,
                    value.kalshi_ticker,
                    value.game_id,
                    value.commence_time,
                    value.matchup,
                    value.selection,
                    value.line,
                    value.kalshi_yes_ask,
                    value.fair_probability,
                    value.sportsbook_samples,
                    value.edge_before_costs,
                    value.cost_buffer,
                    value.net_edge,
                    value.match_score,
                    value.contract_side,
                ),
            )
            if cursor.rowcount == 1:
                new_recommendations.append(value)

    return new_recommendations
