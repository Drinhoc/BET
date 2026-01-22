# Odds Vision MVP

MVP de Fair Odds / Value Finder para NBA pré-jogo (totals). Usa The Odds API como proxy de mercado, com persistência SQLite e UI simples em Jinja2.

## Funcionalidades

- Coleta odds de NBA totals (incluindo alternates quando disponíveis).
- Armazena linhas por bookmaker (raw) e calcula fair odds removendo vig.
- Relatório diário com múltiplas linhas por jogo.
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
    engines/
      fair_odds.py
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
# editar ODDS_API_KEY
```

3) Subir servidor:

```
uvicorn odds-vision.app.main:app --reload
```

4) Acessar:

- `http://localhost:8000/` para gerar relatório do dia.
- `http://localhost:8000/bets` para o ledger.

## Observações

- Banco SQLite é criado automaticamente em `odds_vision.db`.
- O relatório filtra jogos pela data local do usuário (timezone configurável).
- A coleta usa `markets=totals,alternate_totals` e ignora linhas incompletas.
