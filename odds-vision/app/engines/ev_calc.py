from dataclasses import dataclass


@dataclass(frozen=True)
class EvResult:
    ev_over: float
    ev_under: float


def calculate_ev(
    fair_over_odds: float,
    fair_under_odds: float,
    target_over_odds: float,
    target_under_odds: float,
) -> EvResult:
    p_over_fair = 1 / fair_over_odds
    p_under_fair = 1 / fair_under_odds
    ev_over = (p_over_fair * target_over_odds) - 1
    ev_under = (p_under_fair * target_under_odds) - 1
    return EvResult(ev_over=ev_over, ev_under=ev_under)
