import logging
from typing import Any, Dict, List

import httpx

from ..settings import get_settings
from .base import OddsProvider

logger = logging.getLogger(__name__)


class OddsAPIProvider(OddsProvider):
    def __init__(self) -> None:
        settings = get_settings()
        self.api_key = settings.odds_api_key
        self.base_url = settings.odds_api_base_url
        self.sport_key = settings.odds_api_sport_key
        self.regions = settings.odds_api_regions
        self.markets = settings.odds_api_markets
        self.odds_format = settings.odds_api_odds_format
        self.date_format = settings.odds_api_date_format

    async def fetch_odds(self) -> List[Dict[str, Any]]:
        if not self.api_key:
            raise ValueError("ODDS_API_KEY is not configured")

        url = f"{self.base_url}/v4/sports/{self.sport_key}/odds"
        params = {
            "apiKey": self.api_key,
            "regions": self.regions,
            "markets": self.markets,
            "oddsFormat": self.odds_format,
            "dateFormat": self.date_format,
        }

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        logger.info("Fetched %s events from odds API", len(data))
        return data
