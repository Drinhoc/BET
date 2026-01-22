import logging
from datetime import datetime
from typing import Dict, List

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from .db import get_connection, init_db
from .engines.ev_calc import calculate_ev
from .models import BetCreate, BetSettle, TargetQuoteCreate
from .services.bets_service import create_bet, list_bets, settle_bet, summarize_bets
from .services.report_service import generate_report
from .settings import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Odds Vision")


templates = Jinja2Templates(directory="odds-vision/app/templates")


@app.on_event("startup")
async def startup() -> None:
    init_db()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "index.html", {"request": request, "app_name": get_settings().app_name}
    )


@app.post("/generate-report")
async def generate_report_route(report_date: str = Form(...)) -> RedirectResponse:
    generate_report(report_date)
    return RedirectResponse(url=f"/report/{report_date}", status_code=303)


@app.get("/report/{report_date}", response_class=HTMLResponse)
async def report_view(request: Request, report_date: str) -> HTMLResponse:
    with get_connection() as conn:
        games = conn.execute(
            """
            SELECT * FROM games
            WHERE report_date = ?
            ORDER BY commence_time ASC
            """,
            (report_date,),
        ).fetchall()

        fair_prices = conn.execute(
            """
            SELECT * FROM fair_prices
            WHERE report_date = ?
            ORDER BY total_line ASC
            """,
            (report_date,),
        ).fetchall()

        target_quotes = conn.execute(
            """
            SELECT * FROM target_quotes
            WHERE report_date = ?
            ORDER BY created_at DESC
            """,
            (report_date,),
        ).fetchall()

    fair_map: Dict[str, List[Dict[str, str]]] = {}
    for row in fair_prices:
        fair_map.setdefault(row["game_id"], []).append(dict(row))

    target_map: Dict[str, List[Dict[str, str]]] = {}
    for row in target_quotes:
        target_map.setdefault(row["game_id"], []).append(dict(row))

    ev_map: Dict[str, Dict[float, Dict[str, float]]] = {}
    for game_id, quotes in target_map.items():
        for quote in quotes:
            for line in fair_map.get(game_id, []):
                if line["total_line"] == quote["total_line"]:
                    ev = calculate_ev(
                        line["fair_over_odds"],
                        line["fair_under_odds"],
                        quote["over_odds"],
                        quote["under_odds"],
                    )
                    ev_map.setdefault(game_id, {}).setdefault(
                        quote["total_line"],
                        {"ev_over": ev.ev_over, "ev_under": ev.ev_under},
                    )

    return templates.TemplateResponse(
        "report.html",
        {
            "request": request,
            "report_date": report_date,
            "games": games,
            "fair_map": fair_map,
            "target_map": target_map,
            "ev_map": ev_map,
            "ev_threshold": get_settings().ev_threshold,
        },
    )


@app.post("/target-quote")
async def target_quote_submit(
    report_date: str = Form(...),
    game_id: str = Form(...),
    book_target: str = Form(...),
    total_line: float = Form(...),
    over_odds: float = Form(...),
    under_odds: float = Form(...),
) -> RedirectResponse:
    payload = TargetQuoteCreate(
        report_date=report_date,
        game_id=game_id,
        book_target=book_target,
        total_line=total_line,
        over_odds=over_odds,
        under_odds=under_odds,
    )
    created_at = datetime.utcnow().isoformat()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO target_quotes
            (report_date, game_id, book_target, total_line, over_odds, under_odds, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.report_date,
                payload.game_id,
                payload.book_target,
                payload.total_line,
                payload.over_odds,
                payload.under_odds,
                created_at,
            ),
        )
    return RedirectResponse(url=f"/report/{report_date}", status_code=303)


@app.get("/bets", response_class=HTMLResponse)
async def bets_view(request: Request) -> HTMLResponse:
    bets = list_bets()
    summary = summarize_bets()
    return templates.TemplateResponse(
        "bets.html",
        {"request": request, "bets": bets, "summary": summary},
    )


@app.post("/bets")
async def create_bet_route(
    placed_at: str = Form(...),
    sport: str = Form(...),
    league: str = Form(...),
    game_id: str = Form(...),
    market: str = Form(...),
    side: str = Form(...),
    line: float = Form(...),
    odds_taken: float = Form(...),
    stake: float = Form(...),
    book: str = Form(...),
    notes: str = Form("")
) -> RedirectResponse:
    payload = BetCreate(
        placed_at=datetime.fromisoformat(placed_at),
        sport=sport,
        league=league,
        game_id=game_id,
        market=market,
        side=side,
        line=line,
        odds_taken=odds_taken,
        stake=stake,
        book=book,
        notes=notes or None,
    )
    create_bet(payload)
    return RedirectResponse(url="/bets", status_code=303)


@app.post("/bets/{bet_id}/settle")
async def settle_bet_route(
    bet_id: int,
    status: str = Form(...),
    settled_at: str = Form(...),
) -> RedirectResponse:
    payload = BetSettle(status=status, settled_at=datetime.fromisoformat(settled_at))
    settle_bet(bet_id, payload)
    return RedirectResponse(url="/bets", status_code=303)
