# Architecture

## Pattern

**Multi-Agent AI Trading System** — A sequential round-table orchestration pattern where Claude-powered specialist agents analyze markets and produce trade decisions.

## Layers

```
┌─────────────────────────────────────────┐
│  Web UI (Jinja2 templates + static)     │
├─────────────────────────────────────────┤
│  FastAPI REST API + HTML routes         │
│  `quant_team/api/app.py`               │
│  `quant_team/api/routers/`             │
├─────────────────────────────────────────┤
│  Orchestrator (TradingDesk)             │
│  `quant_team/orchestrator.py`           │
├─────────────────────────────────────────┤
│  AI Agents (Macro, Quant, Risk, CIO)   │
│  `quant_team/agents/`                   │
├─────────────────────────────────────────┤
│  Trading Layer                          │
│  Portfolio Manager + Risk + PDT         │
│  `quant_team/trading/`                  │
├─────────────────────────────────────────┤
│  Market Data (yfinance)                 │
│  `quant_team/market/`                   │
├─────────────────────────────────────────┤
│  Database (SQLite)                      │
│  `quant_team/database/`                 │
└─────────────────────────────────────────┘
```

## Data Flow

1. **Trigger** — User clicks "Run Analysis" in web UI, or APScheduler fires at scheduled times (9:35am, 12pm, 3:30pm ET weekdays)
2. **Orchestrator** — `TradingDesk` in `quant_team/orchestrator.py` coordinates the analysis session
3. **Market Data** — `quant_team/market/stock_data.py` fetches current market data via yfinance; `indicators.py` computes technical indicators
4. **Agent Round-Table** — Sequential agent execution:
   - **Macro Agent** (`agents/macro.py`) — Analyzes macro environment
   - **Quant Agent** (`agents/quant.py`) — Quantitative analysis
   - **Risk Agent** (`agents/risk.py`) — Risk assessment
   - **CIO Agent** (`agents/cio.py`) — Final investment decisions, outputs JSON trade recommendations
5. **Validation** — CIO's JSON decisions parsed, validated by `RiskChecker` and `PDTChecker` (`quant_team/trading/risk.py`, `pdt.py`)
6. **Execution** — `PortfolioManager` (`quant_team/trading/portfolio_manager.py`) auto-executes validated trades
7. **Storage** — Results stored in SQLite database (`quant_team/database/`)
8. **Display** — Results rendered in web UI via FastAPI endpoints

## Key Abstractions

### TradingDesk (`quant_team/orchestrator.py`)
Central orchestrator that manages the full analysis pipeline. Coordinates agent execution, parses results, triggers trade execution.

### BaseAgent (`quant_team/agents/base.py`)
Abstract base class for all AI agents. Provides Claude API integration with `max_tokens=4096`. Each agent specializes via system prompts and analysis focus.

### PortfolioManager (`quant_team/trading/portfolio_manager.py`)
Handles actual trade execution. Manages positions, validates against risk rules and PDT constraints.

## Entry Points

- **`run.py`** — Main application entry point, starts FastAPI server
- **`quant_team/api/app.py`** — FastAPI application with HTML and API routes
- **APScheduler** — Autonomous scheduled sessions (configured in app startup)

## Scheduling

- Autonomous trading sessions run on weekdays at 9:35am, 12:00pm, 3:30pm ET
- Uses APScheduler integrated with the FastAPI application
- Sessions run the full orchestrator pipeline without user interaction

---
*Mapped: 2026-03-25*
