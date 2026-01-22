import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import httpx
import pytz

from ..db import get_connection
from ..engines.fair_odds import FairLine, build_price_map, compute_fair_lines
from ..engines.model_total import blend_totals, compute_model_total
from ..providers.odds_api import OddsAPIProvider
from ..providers.sportsdataio import SportsDataIOProvider
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


def _select_market_fair_total(fair_lines: List[FairLine]) -> Optional[float]:
    if not fair_lines:
        return None
    if len(fair_lines) == 1:
        return fair_lines[0].total_line

    best_line = None
    best_delta = None
    for line in fair_lines:
        p_over = 1 / line.fair_over_odds
        delta = abs(p_over - 0.5)
        if best_delta is None or delta < best_delta:
            best_delta = delta
            best_line = line.total_line

    return best_line


def _team_key(team_name: str) -> str:
    return team_name.strip().lower()


def _map_team_stats(stats: List[Dict[str, Any]]) -> Dict[str, Dict[str, Optional[float]]]:
    mapped: Dict[str, Dict[str, Optional[float]]] = {}
    for entry in stats:
        team = entry.get("team")
        if not team:
            continue
        mapped[_team_key(team)] = {
            "pace": entry.get("pace"),
            "ortg": entry.get("ortg"),
            "drtg": entry.get("drtg"),
        }
    return mapped


def _group_injuries(injuries: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for entry in injuries:
        team = entry.get("team")
        if not team:
            continue
        grouped.setdefault(_team_key(team), []).append(entry)
    return grouped


def _compute_game_model(
    market_fair_total: Optional[float],
    home_stats: Dict[str, Optional[float]],
    away_stats: Dict[str, Optional[float]],
    market_weight: float,
    model_weight: float,
) -> Tuple[Optional[float], Optional[float]]:
    model_total = compute_model_total(
        pace_home=home_stats.get("pace"),
        ortg_home=home_stats.get("ortg"),
        drtg_home=home_stats.get("drtg"),
        pace_away=away_stats.get("pace"),
        ortg_away=away_stats.get("ortg"),
        drtg_away=away_stats.get("drtg"),
    )
    blended_total = blend_totals(
        market_fair_total=market_fair_total,
        model_total=model_total,
        market_weight=market_weight,
        model_weight=model_weight,
    )
    return model_total, blended_total


async def generate_report(report_date: str) -> None:
    provider = OddsAPIProvider()
    sports_provider = SportsDataIOProvider()
    settings = get_settings()
    tz = pytz.timezone(settings.timezone)
    fetched_at = datetime.now(tz).isoformat()

    events = _filter_games_by_date(
        events=await provider.fetch_odds(),
        report_date=report_date,
    )

    injuries: List[Dict[str, Any]] = []
    team_stats: List[Dict[str, Any]] = []
    try:
        injuries, team_stats = await asyncio.gather(
            sports_provider.fetch_injuries(report_date),
            sports_provider.fetch_team_stats(report_date),
        )
    except httpx.HTTPError as exc:
        logger.warning("SportsDataIO fetch failed: %s", exc)
    except Exception:
        logger.exception("Unexpected SportsDataIO error")

    with get_connection() as conn:
        conn.execute("DELETE FROM reports WHERE report_date = ?", (report_date,))
        conn.execute("DELETE FROM games WHERE report_date = ?", (report_date,))
        conn.execute("DELETE FROM prices_raw WHERE report_date = ?", (report_date,))
        conn.execute("DELETE FROM fair_prices WHERE report_date = ?", (report_date,))
        conn.execute("DELETE FROM injuries WHERE report_date = ?", (report_date,))
        conn.execute("DELETE FROM team_stats_daily WHERE report_date = ?", (report_date,))
        conn.execute("DELETE FROM game_models WHERE report_date = ?", (report_date,))

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

        for entry in injuries:
            conn.execute(
                """
                INSERT INTO injuries
                (report_date, game_id, team, player, status, updated_at, source)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report_date,
                    entry.get("game_id"),
                    entry.get("team") or "Unknown",
                    entry.get("player") or "Unknown",
                    entry.get("status") or "Unknown",
                    entry.get("updated_at") or fetched_at,
                    "sportsdataio",
                ),
            )

        for entry in team_stats:
            conn.execute(
                """
                INSERT INTO team_stats_daily
                (report_date, team, pace, ortg, drtg, updated_at, source)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report_date,
                    entry.get("team") or "Unknown",
                    entry.get("pace"),
                    entry.get("ortg"),
                    entry.get("drtg"),
                    entry.get("updated_at") or fetched_at,
                    "sportsdataio",
                ),
            )

        team_stats_map = _map_team_stats(team_stats)
        for event in events:
            fair_rows = conn.execute(
                """
                SELECT total_line, fair_over_odds, fair_under_odds, books_used
                FROM fair_prices
                WHERE report_date = ? AND game_id = ?
                """,
                (report_date, event["id"]),
            ).fetchall()
            fair_lines = [
                FairLine(
                    total_line=row["total_line"],
                    fair_over_odds=row["fair_over_odds"],
                    fair_under_odds=row["fair_under_odds"],
                    books_used=row["books_used"],
                )
                for row in fair_rows
            ]

            market_fair_total = _select_market_fair_total(fair_lines)
            home_stats = team_stats_map.get(_team_key(event["home_team"]), {})
            away_stats = team_stats_map.get(_team_key(event["away_team"]), {})
            model_total, blended_total = _compute_game_model(
                market_fair_total,
                home_stats,
                away_stats,
                settings.blend_market_weight,
                settings.blend_model_weight,
            )

            conn.execute(
                """
                INSERT INTO game_models
                (report_date, game_id, market_fair_total, model_total, blended_total, computed_at, method)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report_date,
                    event["id"],
                    market_fair_total,
                    model_total,
                    blended_total,
                    fetched_at,
                    "market_median_line + pace_ratings_simple",
                ),
            )
