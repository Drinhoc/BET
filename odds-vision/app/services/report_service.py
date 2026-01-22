import logging
from datetime import datetime
from typing import Any, Dict, List

import pytz

from ..db import get_connection
from ..engines.fair_odds import build_price_map, compute_fair_lines
from ..providers.odds_api import OddsAPIProvider
from ..settings import get_settings

logger = logging.getLogger(__name__)


def _parse_commence_time(commence_time: str) -> datetime:
    return datetime.fromisoformat(commence_time.replace("Z", "+00:00"))


def _filter_games_by_date(events: List[Dict[str, Any]], report_date: str) -> List[Dict[str, Any]]:
    settings = get_settings()
    tz = pytz.timezone(settings.timezone)
    filtered = []
    for event in events:
        commence_time = _parse_commence_time(event["commence_time"]).astimezone(tz)
        if commence_time.date().isoformat() == report_date:
            filtered.append(event)
    logger.info("Filtered to %s events for %s", len(filtered), report_date)
    return filtered


def _flatten_prices(event: Dict[str, Any]) -> List[Dict[str, Any]]:
    prices: List[Dict[str, Any]] = []
    for bookmaker in event.get("bookmakers", []):
        book_key = bookmaker.get("key")
        for market in bookmaker.get("markets", []):
            market_key = market.get("key")
            for outcome in market.get("outcomes", []):
                total_line = outcome.get("point")
                side = outcome.get("name")
                odds = outcome.get("price")
                if total_line is None or odds is None:
                    continue
                prices.append(
                    {
                        "bookmaker": book_key,
                        "market_key": market_key,
                        "total_line": float(total_line),
                        "side": side,
                        "odds": float(odds),
                    }
                )
    return prices


def generate_report(report_date: str) -> None:
    provider = OddsAPIProvider()
    settings = get_settings()
    tz = pytz.timezone(settings.timezone)
    fetched_at = datetime.now(tz).isoformat()

    events = _filter_games_by_date(
        events=_get_odds_sync(provider),
        report_date=report_date,
    )

    with get_connection() as conn:
        conn.execute("DELETE FROM reports WHERE report_date = ?", (report_date,))
        conn.execute("DELETE FROM games WHERE report_date = ?", (report_date,))
        conn.execute("DELETE FROM prices_raw WHERE report_date = ?", (report_date,))
        conn.execute("DELETE FROM fair_prices WHERE report_date = ?", (report_date,))
        conn.execute("DELETE FROM target_quotes WHERE report_date = ?", (report_date,))

        conn.execute(
            "INSERT INTO reports (report_date, created_at) VALUES (?, ?)",
            (report_date, fetched_at),
        )

        for event in events:
            conn.execute(
                """
                INSERT INTO games (report_date, game_id, commence_time, home_team, away_team)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    report_date,
                    event["id"],
                    event["commence_time"],
                    event["home_team"],
                    event["away_team"],
                ),
            )

            flattened = _flatten_prices(event)
            for price in flattened:
                conn.execute(
                    """
                    INSERT INTO prices_raw
                    (report_date, game_id, bookmaker, market_key, total_line, side, odds, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        report_date,
                        event["id"],
                        price["bookmaker"],
                        price["market_key"],
                        price["total_line"],
                        price["side"],
                        price["odds"],
                        fetched_at,
                    ),
                )

            price_rows = conn.execute(
                """
                SELECT bookmaker, total_line, side, odds
                FROM prices_raw
                WHERE report_date = ? AND game_id = ?
                """,
                (report_date, event["id"]),
            ).fetchall()

            entries = [
                (row["bookmaker"], row["total_line"], row["side"], row["odds"])
                for row in price_rows
            ]

            price_map = build_price_map(entries)
            fair_lines = compute_fair_lines(price_map)

            for line in fair_lines:
                conn.execute(
                    """
                    INSERT INTO fair_prices
                    (report_date, game_id, total_line, fair_over_odds, fair_under_odds, books_used, method, computed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        report_date,
                        event["id"],
                        line.total_line,
                        line.fair_over_odds,
                        line.fair_under_odds,
                        line.books_used,
                        "median_vig_free",
                        fetched_at,
                    ),
                )


async def _get_odds_async(provider: OddsAPIProvider) -> List[Dict[str, Any]]:
    return await provider.fetch_odds()


def _get_odds_sync(provider: OddsAPIProvider) -> List[Dict[str, Any]]:
    import asyncio

    return asyncio.run(_get_odds_async(provider))
