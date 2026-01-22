import statistics
from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple


@dataclass(frozen=True)
class FairLine:
    total_line: float
    fair_over_odds: float
    fair_under_odds: float
    books_used: int


def _vig_free_odds(odd_over: float, odd_under: float) -> Tuple[float, float]:
    p_over = 1 / odd_over
    p_under = 1 / odd_under
    total = p_over + p_under
    p_over_fair = p_over / total
    p_under_fair = p_under / total
    return 1 / p_over_fair, 1 / p_under_fair


def compute_fair_lines(
    prices: Dict[float, Dict[str, Tuple[float, float]]]
) -> List[FairLine]:
    fair_lines: List[FairLine] = []
    for total_line, book_prices in prices.items():
        fair_over_odds_list: List[float] = []
        fair_under_odds_list: List[float] = []
        for odd_over, odd_under in book_prices.values():
            fair_over, fair_under = _vig_free_odds(odd_over, odd_under)
            fair_over_odds_list.append(fair_over)
            fair_under_odds_list.append(fair_under)

        if not fair_over_odds_list:
            continue

        fair_lines.append(
            FairLine(
                total_line=total_line,
                fair_over_odds=statistics.median(fair_over_odds_list),
                fair_under_odds=statistics.median(fair_under_odds_list),
                books_used=len(book_prices),
            )
        )

    return fair_lines


def build_price_map(
    entries: Iterable[Tuple[str, float, str, float]]
) -> Dict[float, Dict[str, Tuple[float, float]]]:
    price_map: Dict[float, Dict[str, Tuple[float, float]]] = {}
    for bookmaker, total_line, side, odds in entries:
        line_map = price_map.setdefault(total_line, {})
        book_entry = line_map.setdefault(bookmaker, [None, None])
        if side.lower() == "over":
            book_entry[0] = odds
        else:
            book_entry[1] = odds

    clean_map: Dict[float, Dict[str, Tuple[float, float]]] = {}
    for total_line, book_prices in price_map.items():
        for bookmaker, (over_odds, under_odds) in book_prices.items():
            if over_odds is None or under_odds is None:
                continue
            clean_map.setdefault(total_line, {})[bookmaker] = (over_odds, under_odds)

    return clean_map
