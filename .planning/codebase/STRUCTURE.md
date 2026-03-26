# Structure

## Directory Layout

```
trading/
├── run.py                          # Application entry point
├── requirements.txt                # Python dependencies
├── .env                            # Environment variables (API keys)
├── quant_team/
│   ├── __init__.py
│   ├── orchestrator.py             # TradingDesk — central orchestrator
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base.py                 # BaseAgent — Claude API integration
│   │   ├── macro.py                # MacroAgent — macro environment analysis
│   │   ├── quant.py                # QuantAgent — quantitative analysis
│   │   ├── risk.py                 # RiskAgent — risk assessment
│   │   └── cio.py                  # CIOAgent — investment decisions (JSON output)
│   ├── api/
│   │   ├── __init__.py
│   │   ├── app.py                  # FastAPI application, HTML routes, scheduler
│   │   ├── auth.py                 # Authentication (cookie-based, HMAC)
│   │   ├── schemas.py              # Pydantic request/response models
│   │   └── routers/
│   │       ├── portfolio.py        # Portfolio API endpoints
│   │       ├── sessions.py         # Analysis session endpoints
│   │       ├── recommendations.py  # Trade recommendation endpoints
│   │       └── market.py           # Market data endpoints
│   ├── database/
│   │   ├── __init__.py
│   │   ├── connection.py           # SQLite connection setup
│   │   └── models.py              # Database models/schemas
│   ├── market/
│   │   ├── __init__.py
│   │   ├── stock_data.py           # Market data fetching (yfinance)
│   │   └── indicators.py           # Technical indicator calculations
│   ├── trading/
│   │   ├── __init__.py
│   │   ├── portfolio_manager.py    # Trade execution and position management
│   │   ├── risk.py                 # RiskChecker — trade validation
│   │   └── pdt.py                  # PDTChecker — pattern day trader rules
│   ├── strategy/
│   │   ├── __init__.py
│   │   └── ips.py                  # Investment Policy Statement generation
│   ├── templates/                  # Jinja2 HTML templates
│   └── static/                     # CSS, JavaScript assets
└── .venv/                          # Python virtual environment
```

## Key Locations

| What | Where |
|------|-------|
| Entry point | `run.py` |
| Core orchestration | `quant_team/orchestrator.py` |
| AI agents | `quant_team/agents/` |
| API routes | `quant_team/api/app.py` + `quant_team/api/routers/` |
| Authentication | `quant_team/api/auth.py` |
| Database | `quant_team/database/` |
| Market data | `quant_team/market/` |
| Trade execution | `quant_team/trading/` |
| Strategy/IPS | `quant_team/strategy/` |
| Frontend | `quant_team/templates/` + `quant_team/static/` |

## Naming Conventions

- **Modules:** snake_case (`stock_data.py`, `portfolio_manager.py`)
- **Classes:** PascalCase (`TradingDesk`, `BaseAgent`, `RiskChecker`)
- **Functions:** snake_case (`run_analysis`, `fetch_market_data`)
- **Package:** `quant_team` — top-level package for all application code

---
*Mapped: 2026-03-25*
