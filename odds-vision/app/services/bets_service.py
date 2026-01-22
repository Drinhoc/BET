from datetime import datetime
from typing import Dict, List

from ..db import get_connection
from ..models import BetCreate, BetSettle


def create_bet(bet: BetCreate) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO bets
            (placed_at, sport, league, game_id, market, side, line, odds_taken, stake, book, status, settled_at, profit, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                bet.placed_at.isoformat(),
                bet.sport,
                bet.league,
                bet.game_id,
                bet.market,
                bet.side,
                bet.line,
                bet.odds_taken,
                bet.stake,
                bet.book,
                "open",
                None,
                0.0,
                bet.notes,
            ),
        )
        return cursor.lastrowid


def settle_bet(bet_id: int, payload: BetSettle) -> None:
    profit = 0.0
    if payload.status == "won":
        profit = _calc_profit_won(bet_id)
    elif payload.status == "lost":
        profit = _calc_profit_lost(bet_id)

    with get_connection() as conn:
        conn.execute(
            """
            UPDATE bets
            SET status = ?, settled_at = ?, profit = ?
            WHERE id = ?
            """,
            (payload.status, payload.settled_at.isoformat(), profit, bet_id),
        )


def list_bets() -> List[Dict[str, str]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM bets ORDER BY placed_at DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def summarize_bets() -> Dict[str, float]:
    with get_connection() as conn:
        rows = conn.execute("SELECT stake, profit FROM bets").fetchall()
    total_stake = sum(row["stake"] for row in rows)
    total_profit = sum(row["profit"] for row in rows)
    roi = (total_profit / total_stake) if total_stake else 0.0
    return {"total_stake": total_stake, "total_profit": total_profit, "roi": roi}


def _calc_profit_won(bet_id: int) -> float:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT stake, odds_taken FROM bets WHERE id = ?", (bet_id,)
        ).fetchone()
    if not row:
        return 0.0
    return row["stake"] * (row["odds_taken"] - 1)


def _calc_profit_lost(bet_id: int) -> float:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT stake FROM bets WHERE id = ?", (bet_id,)
        ).fetchone()
    if not row:
        return 0.0
    return -row["stake"]
