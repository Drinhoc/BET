# Odds Vision MVP

MVP de Fair Odds / Value Finder para NBA pré-jogo (totals). Usa The Odds API como proxy de mercado e SportsDataIO para contexto pré-jogo (injuries + stats), com persistência SQLite e UI simples em Jinja2.

## Funcionalidades

- Coleta odds de NBA totals (incluindo alternates quando disponíveis).
- Armazena linhas por bookmaker (raw) e calcula fair odds removendo vig.
- Relatório diário com múltiplas linhas por jogo, market fair total, model total e blended total.
- Injuries e stats (pace, offensive/defensive rating) via SportsDataIO.
- Inserção manual de odds alvo (Stake/Betano) e cálculo de EV.
- Ledger de apostas com status (open/won/lost/void) e P&L.

## Estrutura

```
odds-vision/
  app/
    main.py
    settings.py
    db.py
    models.py
    providers/
      base.py
      odds_api.py
      sportsdataio.py
    engines/
      fair_odds.py
      model_total.py
      ev_calc.py
    services/
      report_service.py
      bets_service.py
    templates/
      index.html
      report.html
      bets.html
  requirements.txt
  .env.example
```

## Como rodar localmente

1) Criar virtualenv e instalar dependências:

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2) Configurar variáveis de ambiente:

```
cp .env.example .env
# editar ODDS_API_KEY e SPORTSDATAIO_API_KEY
```

3) Subir servidor:

```
cd odds-vision
uvicorn app.main:app --reload
```

4) Acessar:

- `http://localhost:8000/` para gerar relatório do dia.
- `http://localhost:8000/bets` para o ledger.

## Observações

- Banco SQLite é criado automaticamente em `odds_vision.db`.
- O relatório filtra jogos pela data local do usuário (timezone configurável).
- A coleta usa `markets=totals,alternate_totals` e ignora linhas incompletas.
- SportsDataIO endpoints usados:
  - Injuries: `/scores/json/Injuries/{YYYY-MM-DD}`.
  - TeamSeasonStats: `/stats/json/TeamSeasonStats/{season}` (season derivada do report_date).
- Campos usados para stats: `Pace` (ou `PossessionsPerGame`/`Possessions`), `OffensiveRating`, `DefensiveRating`.

## Cálculos (MVP)

- **Fair odds por linha**: remove vig por book e agrega por linha via mediana.
- **Market fair total**: linha cuja probabilidade fair do OVER está mais próxima de 50% (se só houver 1 linha, usa ela).
- **Model total**:
  - expected_pace = média(pace_timeA, pace_timeB)
  - expected_points_per_possession = média( (ortg_A + (100 - drtg_B))/200 , (ortg_B + (100 - drtg_A))/200 )
  - model_total = expected_pace * expected_points_per_possession
- **Blended total**: `blend_market_weight * market_fair_total + blend_model_weight * model_total` (se não houver model_total, usa só market_fair_total).
