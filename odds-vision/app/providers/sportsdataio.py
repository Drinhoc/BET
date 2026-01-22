import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from ..settings import get_settings

logger = logging.getLogger(__name__)


class SportsDataIOProvider:
    def __init__(self) -> None:
        settings = get_settings()
        self.api_key = settings.sportsdataio_api_key
        self.base_url = settings.sportsdataio_base
        self.subscription_header = settings.sportsdataio_subscription_header

    async def fetch_injuries(self, report_date: str) -> List[Dict[str, Any]]:
        if not self.api_key:
            logger.warning("SPORTSDATAIO_API_KEY is not configured")
            return []

        url = f"{self.base_url}/scores/json/Injuries/{report_date}"
        headers = {self.subscription_header: self.api_key}
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()

        injuries: List[Dict[str, Any]] = []
        for entry in data:
            injuries.append(
                {
                    "game_id": _safe_value(entry.get("GameID")),
                    "team": _safe_value(
                        entry.get("Team")
                        or entry.get("TeamName")
                        or entry.get("TeamFullName")
                    ),
                    "player": _safe_value(
                        entry.get("Name")
                        or entry.get("PlayerName")
                        or entry.get("Player")
                    ),
                    "status": _safe_value(entry.get("Status") or entry.get("InjuryStatus")),
                    "updated_at": _safe_value(entry.get("Updated")),
                }
            )

        logger.info("Fetched %s injuries from SportsDataIO", len(injuries))
        return injuries

    async def fetch_team_stats(self, report_date: str) -> List[Dict[str, Any]]:
        if not self.api_key:
            logger.warning("SPORTSDATAIO_API_KEY is not configured")
            return []

        season = _season_from_date(report_date)
        url = f"{self.base_url}/stats/json/TeamSeasonStats/{season}"
        headers = {self.subscription_header: self.api_key}
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()

        stats: List[Dict[str, Any]] = []
        for entry in data:
            pace = _extract_numeric(
                entry.get("Pace")
                or entry.get("PossessionsPerGame")
                or entry.get("Possessions")
            )
            ortg = _extract_numeric(entry.get("OffensiveRating") or entry.get("OffRtg"))
            drtg = _extract_numeric(entry.get("DefensiveRating") or entry.get("DefRtg"))
            stats.append(
                {
                    "team": _safe_value(entry.get("Name") or entry.get("Team")),
                    "pace": pace,
                    "ortg": ortg,
                    "drtg": drtg,
                    "updated_at": _safe_value(entry.get("LastUpdated")),
                }
            )

        logger.info("Fetched %s team stats from SportsDataIO", len(stats))
        return stats


def _season_from_date(report_date: str) -> str:
    date = datetime.fromisoformat(report_date)
    year = date.year
    if date.month >= 10:
        return str(year + 1)
    return str(year)


def _safe_value(value: Optional[Any]) -> Optional[str]:
    if value is None:
        return None
    return str(value)


def _extract_numeric(value: Optional[Any]) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
