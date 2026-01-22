from abc import ABC, abstractmethod
from typing import Any, Dict, List


class OddsProvider(ABC):
    @abstractmethod
    async def fetch_odds(self) -> List[Dict[str, Any]]:
        """Return raw odds data for the configured sport."""
