from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ModelTotals:
    market_fair_total: Optional[float]
    model_total: Optional[float]
    blended_total: Optional[float]


def compute_model_total(
    pace_home: Optional[float],
    ortg_home: Optional[float],
    drtg_home: Optional[float],
    pace_away: Optional[float],
    ortg_away: Optional[float],
    drtg_away: Optional[float],
) -> Optional[float]:
    if None in (pace_home, ortg_home, drtg_home, pace_away, ortg_away, drtg_away):
        return None

    expected_pace = (pace_home + pace_away) / 2
    ppp_home = (ortg_home + (100 - drtg_away)) / 200
    ppp_away = (ortg_away + (100 - drtg_home)) / 200
    expected_ppp = (ppp_home + ppp_away) / 2
    return expected_pace * expected_ppp


def blend_totals(
    market_fair_total: Optional[float],
    model_total: Optional[float],
    market_weight: float,
    model_weight: float,
) -> Optional[float]:
    if market_fair_total is None:
        return None
    if model_total is None:
        return market_fair_total
    return (market_weight * market_fair_total) + (model_weight * model_total)
