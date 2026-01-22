from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class TargetQuoteCreate(BaseModel):
    report_date: str
    game_id: str
    book_target: str
    total_line: float
    over_odds: float
    under_odds: float


class BetCreate(BaseModel):
    placed_at: datetime
    sport: str
    league: str
    game_id: str
    market: str
    side: str
    line: float
    odds_taken: float
    stake: float
    book: str
    notes: Optional[str] = None


class BetSettle(BaseModel):
    status: str = Field(..., pattern="^(won|lost|void)$")
    settled_at: datetime
