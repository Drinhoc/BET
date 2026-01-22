import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .settings import get_settings

logger = logging.getLogger(__name__)


def _database_path() -> Path:
    settings = get_settings()
    if settings.database_url.startswith("sqlite:///"):
        return Path(settings.database_url.replace("sqlite:///", "", 1))
    raise ValueError("Only sqlite database_url is supported in MVP")


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    db_path = _database_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        logger.exception("Database error")
        raise
    finally:
        conn.close()


def init_db() -> None:
    schema = """
    CREATE TABLE IF NOT EXISTS reports (
        report_date TEXT PRIMARY KEY,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS games (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        report_date TEXT NOT NULL,
        game_id TEXT NOT NULL,
        commence_time TEXT NOT NULL,
        home_team TEXT NOT NULL,
        away_team TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS prices_raw (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        report_date TEXT NOT NULL,
        game_id TEXT NOT NULL,
        bookmaker TEXT NOT NULL,
        market_key TEXT NOT NULL,
        total_line REAL NOT NULL,
        side TEXT NOT NULL,
        odds REAL NOT NULL,
        fetched_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS fair_prices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        report_date TEXT NOT NULL,
        game_id TEXT NOT NULL,
        total_line REAL NOT NULL,
        fair_over_odds REAL NOT NULL,
        fair_under_odds REAL NOT NULL,
        books_used INTEGER NOT NULL,
        method TEXT NOT NULL,
        computed_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS target_quotes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        report_date TEXT NOT NULL,
        game_id TEXT NOT NULL,
        book_target TEXT NOT NULL,
        total_line REAL NOT NULL,
        over_odds REAL NOT NULL,
        under_odds REAL NOT NULL,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS injuries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        report_date TEXT NOT NULL,
        game_id TEXT,
        team TEXT NOT NULL,
        player TEXT NOT NULL,
        status TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        source TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS team_stats_daily (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        report_date TEXT NOT NULL,
        team TEXT NOT NULL,
        pace REAL,
        ortg REAL,
        drtg REAL,
        updated_at TEXT NOT NULL,
        source TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS game_models (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        report_date TEXT NOT NULL,
        game_id TEXT NOT NULL,
        market_fair_total REAL,
        model_total REAL,
        blended_total REAL,
        computed_at TEXT NOT NULL,
        method TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS bets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        placed_at TEXT NOT NULL,
        sport TEXT NOT NULL,
        league TEXT NOT NULL,
        game_id TEXT NOT NULL,
        market TEXT NOT NULL,
        side TEXT NOT NULL,
        line REAL NOT NULL,
        odds_taken REAL NOT NULL,
        stake REAL NOT NULL,
        book TEXT NOT NULL,
        status TEXT NOT NULL,
        settled_at TEXT,
        profit REAL NOT NULL,
        notes TEXT
    );
    """

    with get_connection() as conn:
        conn.executescript(schema)
        logger.info("Database initialized")
