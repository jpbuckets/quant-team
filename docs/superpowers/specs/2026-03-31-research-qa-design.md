# Research Q&A Feature

## Overview

Allow users to submit freeform questions to the trading team agents and receive a full round-table analysis. The agents auto-detect relevant tickers, fetch live market data, and provide multi-perspective analysis without executing any trades.

## Requirements

- User submits a freeform question (e.g., "What does the USDA corn farming report mean for investments?")
- System extracts relevant tickers via a lightweight Claude Haiku call
- Market data (quotes, technicals) fetched for extracted tickers
- All 4 agents (Macro, Quant, Risk, CIO) analyze sequentially in round-table format
- CIO produces structured analysis (not executable trade JSON)
- Results displayed on a new `/research` page with 4 agent panels
- No database persistence — results are ephemeral
- No trade execution — analysis only

## Architecture

### New Files

#### `quant_team/research.py` — ResearchSession

Orchestrates the research Q&A flow.

**`extract_tickers(question: str) -> list[str]`**
- Single Claude Haiku call with a focused extraction prompt
- Returns JSON array of ticker symbols relevant to the question
- Fallback: returns empty list on failure (agents still answer without market data)

**`run(team_id: str, question: str, on_progress: callable | None) -> dict`**
- Loads team config from TeamRegistry
- Calls `extract_tickers()` to identify relevant tickers
- If tickers found: fetches market summary + technical indicators via MarketDataRouter
- Builds market_context string combining market data + the user's question
- Runs agents sequentially: Macro → Quant → Risk → CIO
  - Each agent calls `analyze(market_context, discussion, task)`
  - 60s delay between agent calls (rate limiting)
  - Discussion accumulates: each agent sees prior agents' responses
- Research-specific task prompts per agent:
  - Analysts: "Analyze the following research question from your perspective: {question}"
  - CIO: "Synthesize the team's analysis. Structure your response with: Key Findings, Opportunities, Risks, and Actionable Ideas. Do NOT output trade JSON."
- Returns `{"macro": str, "quant": str, "risk": str, "cio": str, "tickers_analyzed": list[str]}`

#### `quant_team/api/routers/research.py` — Research Router

**`POST /api/research/ask`**
- Request body: `{"question": str, "team_id": str}` (team_id defaults to "quant")
- Guards against concurrent research sessions (same pattern as trading sessions)
- Runs ResearchSession as background task
- Progress reported via existing SSE mechanism (`_progress` global)
- Response: the 4-agent analysis dict

**`GET /api/research/status`**
- Returns current progress state for the frontend to poll/SSE

#### `quant_team/templates/research.html` — Research Page

New page at `/research` route.

**Layout:**
- Text area input for the question
- Submit button (disabled while running)
- Progress indicator showing current agent being consulted
- Detected tickers displayed as badges/chips
- 4 collapsible panels for agent responses (same visual style as `/analysis` page)
- Panels: Macro Analysis, Quant Analysis, Risk Analysis, CIO Summary

### Modified Files

#### `quant_team/api/app.py`
- Register research router: `app.include_router(research_router)`
- Add `/research` HTML route that renders `research.html`

#### `quant_team/templates/base.html`
- Add "Research" nav link between existing nav items

### Reused Components (No Changes)

- `Agent.analyze()` — same multi-turn analysis method
- `MarketDataRouter` — fetch quotes and indicators
- `indicators.py` — compute technicals for extracted tickers
- `TeamRegistry` — load team config (agents, risk limits)
- SSE progress pattern — real-time status updates
- Existing CSS/styling — terminal green theme, panel layouts

## Data Flow

```
User Question
  |
  v
extract_tickers() [Claude Haiku]
  |
  v
["CORN", "DBA", "ADM", "DE", "MOS"]
  |
  v
MarketDataRouter.get_market_summary(tickers)
MarketDataRouter.get_indicators(tickers)
  |
  v
market_context = market_data + "\n\nRESEARCH QUESTION: {question}"
  |
  v
Macro.analyze(market_context, [], task)  --> macro_analysis
  | (60s delay)
  v
Quant.analyze(market_context, [macro], task)  --> quant_analysis
  | (60s delay)
  v
Risk.analyze(market_context, [macro, quant], task)  --> risk_analysis
  | (60s delay)
  v
CIO.analyze(market_context, [macro, quant, risk], task)  --> cio_summary
  |
  v
Return {macro, quant, risk, cio, tickers_analyzed}
```

## Error Handling

- Ticker extraction failure: proceed with empty ticker list, agents answer from knowledge only
- Market data fetch failure: skip failed tickers, include whatever data is available
- Agent API failure: report error in progress, return partial results (whatever agents completed)
- Concurrent request: return 409 Conflict (same as trading session pattern)

## UI Behavior

- Submit disables the form and shows progress ("Extracting tickers...", "Consulting Macro Strategist...", etc.)
- Each agent panel appears as its response completes (progressive rendering)
- Detected tickers shown as chips above the results
- If no tickers detected, show a note: "No specific tickers detected — agents will analyze from general knowledge"
- Error states shown inline with retry option

## Out of Scope

- No database persistence (ephemeral results)
- No trade execution from research sessions
- No follow-up questions / conversation memory
- No file upload (e.g., PDF reports)
- No custom agent selection (always full round-table)
