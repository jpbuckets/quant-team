# Research Q&A Feature Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `/research` page where users submit freeform questions and get a full round-table analysis from all 4 trading agents with auto-enriched market data.

**Architecture:** New `ResearchSession` class handles ticker extraction (Claude Haiku) and sequential agent analysis with research-specific task prompts. A new API router exposes the endpoint with progress tracking, and a new template renders the results in the existing terminal-green UI style.

**Tech Stack:** Python/FastAPI, Anthropic Claude API (Haiku for extraction, Sonnet for agents), Jinja2/Alpine.js/Tailwind for frontend.

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `quant_team/research.py` | ResearchSession: ticker extraction + agent round-table |
| Create | `quant_team/api/routers/research.py` | API endpoint + progress tracking |
| Create | `quant_team/templates/research.html` | Research page UI |
| Modify | `quant_team/api/schemas.py` | Add ResearchRequest model |
| Modify | `quant_team/api/app.py:261-272` | Register research router + add page route |
| Modify | `quant_team/templates/base.html:121-128` | Add "research" nav link |

---

### Task 1: Add ResearchRequest schema

**Files:**
- Modify: `quant_team/api/schemas.py:120-122`

- [ ] **Step 1: Add the request model**

Add after `GenerateRequest` at end of file:

```python
class ResearchRequest(BaseModel):
    question: str
    team_id: str = "quant"
```

- [ ] **Step 2: Verify syntax**

Run: `python -c "from quant_team.api.schemas import ResearchRequest; print(ResearchRequest(question='test'))"`
Expected: `question='test' team_id='quant'`

- [ ] **Step 3: Commit**

```bash
git add quant_team/api/schemas.py
git commit -m "feat: add ResearchRequest schema for Q&A feature"
```

---

### Task 2: Create ResearchSession core

**Files:**
- Create: `quant_team/research.py`

- [ ] **Step 1: Create the research module**

```python
"""Research Q&A — run agent round-table analysis on freeform questions."""

from __future__ import annotations

import asyncio
import json
import logging

import anthropic

from .agents.base import Agent, Message
from .teams.registry import TeamConfig
from .market.router import MarketDataRouter
from .market.indicators import compute_all

logger = logging.getLogger("quant_team")


async def extract_tickers(question: str) -> list[str]:
    """Use Claude Haiku to extract relevant ticker symbols from a freeform question."""
    client = anthropic.AsyncAnthropic()
    try:
        response = await asyncio.wait_for(
            client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=256,
                system=(
                    "You extract stock tickers, ETFs, and index symbols from questions about "
                    "markets, economics, and investing. Return ONLY a JSON array of uppercase "
                    "ticker symbols. If no specific tickers are relevant, return related ETFs "
                    "or sector funds. Examples:\n"
                    '- "What does the corn farming report mean?" -> ["CORN", "DBA", "ADM", "DE", "MOS"]\n'
                    '- "How will Fed rate cuts affect banks?" -> ["XLF", "KRE", "JPM", "BAC", "GS"]\n'
                    '- "Is AI still a good investment?" -> ["NVDA", "MSFT", "GOOGL", "AMD", "SMH"]\n'
                    "Return only the JSON array, nothing else."
                ),
                messages=[{"role": "user", "content": question}],
            ),
            timeout=30.0,
        )
        text = response.content[0].text.strip()
        tickers = json.loads(text)
        if isinstance(tickers, list):
            return [t.upper() for t in tickers if isinstance(t, str)]
    except Exception as e:
        logger.warning(f"Ticker extraction failed: {e}")
    return []


class ResearchSession:
    """Orchestrates a research Q&A session — analysis only, no trade execution."""

    def __init__(self, config: TeamConfig):
        self.config = config
        self.market = MarketDataRouter(config)
        self.agents: list[Agent] = [
            Agent(
                name=spec.name,
                title=spec.title,
                system_prompt=spec.system_prompt,
                model=spec.model,
            )
            for spec in config.agents
        ]

    async def run(
        self,
        question: str,
        on_progress: callable | None = None,
    ) -> dict:
        """Run a full round-table research session on the user's question."""
        _progress = on_progress or (lambda *a: None)
        total_steps = len(self.agents) + 2  # ticker extraction + market data + each agent

        # Step 1: Extract tickers
        _progress("Extracting relevant tickers", 1, total_steps)
        tickers = await extract_tickers(question)
        logger.info(f"Research: extracted tickers {tickers} from question")

        # Step 2: Fetch market data for extracted tickers
        _progress("Fetching market data", 2, total_steps)
        market_context_parts = []

        if tickers:
            try:
                market_context_parts.append(self.market.get_market_summary(tickers))
            except Exception as e:
                logger.warning(f"Market summary failed: {e}")

            for ticker in tickers[:6]:
                try:
                    df = self.market.fetch_ohlcv(ticker, "3mo", "1d")
                    indicators = compute_all(df)
                    market_context_parts.append(f"\n## {ticker} Technical Analysis\n{indicators}")
                except Exception:
                    pass

        if market_context_parts:
            market_context = "\n".join(market_context_parts)
            market_context += f"\n\n## RESEARCH QUESTION\n{question}"
        else:
            market_context = (
                "No specific market data available for this question. "
                "Answer based on your expertise and general market knowledge.\n\n"
                f"## RESEARCH QUESTION\n{question}"
            )

        # Step 3: Run agent round-table
        discussion: list[Message] = []
        analyses: dict[str, str] = {}
        analyst_agents = self.agents[:-1] if len(self.agents) > 1 else []
        decision_agent = self.agents[-1] if self.agents else None

        for i, agent in enumerate(analyst_agents):
            if i > 0:
                await asyncio.sleep(60)  # Rate limit spacing
            _progress(f"{agent.name} ({agent.title}) analyzing", 3 + i, total_steps)
            response = await agent.analyze(
                market_context=market_context,
                discussion=discussion,
                task=(
                    f"A user has asked your team a research question. Analyze it from "
                    f"your perspective as {agent.title}. Provide detailed, actionable insights. "
                    f"Reference specific data points where available.\n\n"
                    f"Question: {question}"
                ),
            )
            discussion.append(Message(role=f"{agent.name} ({agent.title})", content=response))
            analyses[agent.name.lower()] = response

        # Decision-maker synthesizes
        if decision_agent:
            if analyst_agents:
                await asyncio.sleep(60)
            _progress(f"{decision_agent.name} synthesizing", total_steps, total_steps)
            response = await decision_agent.analyze(
                market_context=market_context,
                discussion=discussion,
                task=(
                    f"Your team has analyzed this research question. Synthesize their insights "
                    f"into a comprehensive response. Structure your analysis with these sections:\n\n"
                    f"**KEY FINDINGS** — What the data and your team's analysis reveals\n"
                    f"**OPPORTUNITIES** — Specific investment opportunities identified\n"
                    f"**RISKS** — Key risks and concerns to watch\n"
                    f"**ACTIONABLE IDEAS** — Concrete next steps or trades to consider\n\n"
                    f"Do NOT output JSON trade blocks. This is a research session, not a trading session.\n\n"
                    f"Question: {question}"
                ),
            )
            analyses[decision_agent.name.lower()] = response

        return {
            "question": question,
            "tickers_analyzed": tickers,
            "macro": analyses.get("macro", ""),
            "quant": analyses.get("quant", ""),
            "risk": analyses.get("risk", ""),
            "cio": analyses.get("cio", ""),
        }
```

- [ ] **Step 2: Verify import works**

Run: `python -c "from quant_team.research import ResearchSession, extract_tickers; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add quant_team/research.py
git commit -m "feat: add ResearchSession for Q&A round-table analysis"
```

---

### Task 3: Create research API router

**Files:**
- Create: `quant_team/api/routers/research.py`

- [ ] **Step 1: Create the router**

```python
"""Research Q&A API — ask the trading team questions without executing trades."""

from __future__ import annotations

import asyncio
import logging
import uuid

from fastapi import APIRouter, HTTPException, BackgroundTasks

from ...teams.registry import TeamRegistry
from ...research import ResearchSession
from ..schemas import ResearchRequest

logger = logging.getLogger("quant_team")

router = APIRouter(prefix="/api/research", tags=["research"])

_sessions: dict[str, dict] = {}


def _update_progress(session_id: str, step: str, step_num: int, total_steps: int) -> None:
    if session_id in _sessions:
        _sessions[session_id]["progress"] = {
            "step": step,
            "step_num": step_num,
            "total_steps": total_steps,
        }
    logger.info(f"Research progress [{step_num}/{total_steps}]: {step}")


async def _run_research(session_id: str, question: str, team_id: str) -> None:
    _sessions[session_id] = {
        "generating": True,
        "error": None,
        "result": None,
        "progress": {"step": "Starting...", "step_num": 0, "total_steps": 6},
    }
    try:
        registry = TeamRegistry()
        config = registry.get(team_id)
        session = ResearchSession(config=config)
        result = await session.run(
            question=question,
            on_progress=lambda s, n, t: _update_progress(session_id, s, n, t),
        )
        _sessions[session_id]["result"] = result
        _sessions[session_id]["progress"] = {
            "step": "Complete",
            "step_num": _sessions[session_id]["progress"]["total_steps"],
            "total_steps": _sessions[session_id]["progress"]["total_steps"],
        }
        logger.info("Research session completed successfully")
    except asyncio.TimeoutError:
        _sessions[session_id]["error"] = "Research timed out after 5 minutes"
    except Exception as e:
        _sessions[session_id]["error"] = str(e)
        logger.error(f"Research session failed: {e}", exc_info=True)
    finally:
        _sessions[session_id]["generating"] = False


@router.post("/ask")
async def ask_question(body: ResearchRequest, background_tasks: BackgroundTasks):
    if any(s["generating"] for s in _sessions.values()):
        raise HTTPException(status_code=409, detail="Research session already in progress")
    session_id = str(uuid.uuid4())
    background_tasks.add_task(_run_research, session_id, body.question, body.team_id)
    return {"status": "started", "session_id": session_id}


@router.get("/status")
def research_status():
    if not _sessions:
        return {
            "generating": False,
            "error": None,
            "result": None,
            "progress": {"step": "", "step_num": 0, "total_steps": 6},
        }
    latest_id = list(_sessions.keys())[-1]
    s = _sessions[latest_id]
    return {
        "generating": s["generating"],
        "error": s["error"],
        "result": s["result"],
        "progress": s["progress"],
        "session_id": latest_id,
    }
```

- [ ] **Step 2: Verify import**

Run: `python -c "from quant_team.api.routers.research import router; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add quant_team/api/routers/research.py
git commit -m "feat: add research API router with ask endpoint and progress tracking"
```

---

### Task 4: Register router and add page route

**Files:**
- Modify: `quant_team/api/app.py:261-272` (router registration)
- Modify: `quant_team/api/app.py:345-349` (add page route after `/analysis`)

- [ ] **Step 1: Add router import and registration**

After line 266 (`from .routers.sessions import router as sessions_router`), add:
```python
from .routers.research import router as research_router
```

After line 272 (`app.include_router(teams.router, ...)`), add:
```python
app.include_router(research_router)
```

- [ ] **Step 2: Add the /research page route**

After the `/analysis` route (line 349), add:

```python
@app.get("/research")
async def research_page(request: Request):
    if not _auth_required(request):
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse(request, "research.html")
```

- [ ] **Step 3: Verify server starts**

Run: `cd /Users/justinprappas/trading && timeout 5 python -c "from quant_team.api.app import app; print('App loaded OK')" 2>&1 || true`
Expected: `App loaded OK` (may show warnings about scheduler, that's fine)

- [ ] **Step 4: Commit**

```bash
git add quant_team/api/app.py
git commit -m "feat: register research router and add /research page route"
```

---

### Task 5: Add research nav link

**Files:**
- Modify: `quant_team/templates/base.html:121-128`

- [ ] **Step 1: Add nav link**

After the `analysis` nav link (line 124) and before the `market_data` nav link (line 125), add:

```html
                <a href="/research" class="nav-link flex items-center px-4 py-2 text-xs transition-colors border-l-2 border-transparent {% block nav_research %}{% endblock %}">
                    <span class="text-term-dim mr-2.5">&gt;</span>
                    <span>research</span>
                </a>
```

- [ ] **Step 2: Commit**

```bash
git add quant_team/templates/base.html
git commit -m "feat: add research link to sidebar navigation"
```

---

### Task 6: Create research page template

**Files:**
- Create: `quant_team/templates/research.html`

- [ ] **Step 1: Create the template**

```html
{% extends "base.html" %}
{% block title %}RESEARCH{% endblock %}
{% block nav_research %}nav-active{% endblock %}

{% block content %}
<div x-data="researchApp()" x-init="init()">
    <div class="mb-6">
        <h2 class="text-sm text-term-green text-glow uppercase tracking-widest">// Research</h2>
        <p class="text-[0.6rem] text-term-dim mt-1">ask the trading team anything — get multi-agent analysis</p>
    </div>

    <!-- Question Input -->
    <div class="bg-term-panel border border-term-border term-glow p-4 mb-4">
        <label class="text-xs text-term-amber text-glow-amber uppercase tracking-wider block mb-2">Your Question</label>
        <textarea x-model="question" rows="3" placeholder="e.g. What does the USDA corn farming report mean for investments? How will Fed rate cuts affect the market?"
                  class="w-full bg-term-bg border border-term-border text-xs text-term-text px-3 py-2 focus:border-term-green focus:outline-none placeholder-term-dim resize-none"
                  :disabled="generating"
                  @keydown.meta.enter="askQuestion()"
                  @keydown.ctrl.enter="askQuestion()"></textarea>
        <div class="flex items-center justify-between mt-3">
            <span class="text-[0.55rem] text-term-dim">cmd+enter to submit</span>
            <button @click="askQuestion()" :disabled="generating || !question.trim()"
                    class="px-4 py-1.5 border border-term-green text-term-green text-xs hover:bg-term-greenMuted disabled:border-term-dim disabled:text-term-dim transition-colors">
                <span x-show="!generating">[ ASK TEAM ]</span>
                <span x-show="generating" x-text="'[' + progressStep + '/' + progressTotal + '] ' + progressLabel"></span>
            </button>
        </div>
    </div>

    <!-- Progress Bar -->
    <div x-show="generating" class="mb-4 bg-term-panel border border-term-border p-4">
        <div class="flex items-center justify-between mb-2">
            <span class="text-xs text-term-green text-glow uppercase tracking-wider" x-text="progressLabel"></span>
            <span class="text-xs text-term-dim" x-text="progressStep + ' / ' + progressTotal"></span>
        </div>
        <div class="w-full h-1.5 bg-term-border overflow-hidden">
            <div class="h-full bg-term-green transition-all duration-500 ease-out"
                 :style="'width: ' + (progressTotal > 0 ? (progressStep / progressTotal * 100) : 0) + '%'"></div>
        </div>
        <div class="flex justify-between mt-2 text-[0.55rem] text-term-dim">
            <span :class="progressStep >= 1 ? 'text-term-green' : ''">TICKERS</span>
            <span :class="progressStep >= 2 ? 'text-term-green' : ''">DATA</span>
            <span :class="progressStep >= 3 ? 'text-term-amber' : ''">MACRO</span>
            <span :class="progressStep >= 4 ? 'text-term-cyan' : ''">QUANT</span>
            <span :class="progressStep >= 5 ? 'text-term-red' : ''">RISK</span>
            <span :class="progressStep >= 6 ? 'text-term-green' : ''">CIO</span>
        </div>
    </div>

    <!-- Error -->
    <div x-show="error" class="mb-4 px-4 py-3 border border-term-red bg-term-red/10 text-term-red text-xs">
        <span class="uppercase tracking-wider font-bold">Error:</span> <span x-text="error"></span>
        <button @click="error = null" class="ml-2 text-term-dim hover:text-term-text">[dismiss]</button>
    </div>

    <!-- Results -->
    <div x-show="result" class="space-y-3">
        <!-- Detected Tickers -->
        <div x-show="result && result.tickers_analyzed && result.tickers_analyzed.length > 0" class="flex items-center gap-2 flex-wrap mb-2">
            <span class="text-[0.55rem] text-term-dim uppercase tracking-wider">Tickers analyzed:</span>
            <template x-for="ticker in (result?.tickers_analyzed || [])" :key="ticker">
                <span class="px-2 py-0.5 text-[0.6rem] border border-term-green/30 text-term-green bg-term-greenMuted/20" x-text="ticker"></span>
            </template>
        </div>
        <div x-show="result && (!result.tickers_analyzed || result.tickers_analyzed.length === 0)" class="mb-2">
            <span class="text-[0.55rem] text-term-dim">No specific tickers detected — agents analyzed from general knowledge</span>
        </div>

        <!-- Macro -->
        <div class="bg-term-panel border border-term-border term-glow" x-show="result && result.macro">
            <div class="px-4 py-2 border-b border-term-border flex items-center gap-2">
                <span class="w-2 h-2 bg-term-amber"></span>
                <span class="text-xs text-term-amber text-glow-amber uppercase tracking-wider">MACRO // Senior Macro Strategist</span>
            </div>
            <div class="p-4 text-xs text-term-text whitespace-pre-wrap max-h-80 overflow-y-auto leading-relaxed" x-text="result.macro"></div>
        </div>

        <!-- Quant -->
        <div class="bg-term-panel border border-term-border term-glow" x-show="result && result.quant">
            <div class="px-4 py-2 border-b border-term-border flex items-center gap-2">
                <span class="w-2 h-2 bg-term-cyan"></span>
                <span class="text-xs text-term-cyan text-glow-cyan uppercase tracking-wider">QUANT // Lead Quantitative Analyst</span>
            </div>
            <div class="p-4 text-xs text-term-text whitespace-pre-wrap max-h-80 overflow-y-auto leading-relaxed" x-text="result.quant"></div>
        </div>

        <!-- Risk -->
        <div class="bg-term-panel border border-term-border term-glow" x-show="result && result.risk">
            <div class="px-4 py-2 border-b border-term-border flex items-center gap-2">
                <span class="w-2 h-2 bg-term-red"></span>
                <span class="text-xs text-term-red text-glow-red uppercase tracking-wider">RISK // Chief Risk Officer</span>
            </div>
            <div class="p-4 text-xs text-term-text whitespace-pre-wrap max-h-80 overflow-y-auto leading-relaxed" x-text="result.risk"></div>
        </div>

        <!-- CIO -->
        <div class="bg-term-panel border border-term-green/30 term-glow" x-show="result && result.cio">
            <div class="px-4 py-2 border-b border-term-green/30 flex items-center gap-2">
                <span class="w-2 h-2 bg-term-green"></span>
                <span class="text-xs text-term-green text-glow uppercase tracking-wider">CIO // Research Summary</span>
            </div>
            <div class="p-4 text-xs text-term-text whitespace-pre-wrap max-h-96 overflow-y-auto leading-relaxed" x-text="result.cio"></div>
        </div>
    </div>

    <!-- Empty State -->
    <div x-show="!result && !generating" class="bg-term-panel border border-term-border term-glow p-12 text-center">
        <div class="text-term-dim text-xs">ask a question to start a research session</div>
        <div class="text-term-dim text-[0.6rem] mt-1">the full trading team will analyze your question</div>
    </div>
</div>
{% endblock %}

{% block scripts %}
<script>
function researchApp() {
    return {
        question: '',
        generating: false,
        error: null,
        result: null,
        progressLabel: 'Starting...',
        progressStep: 0,
        progressTotal: 6,

        init() {},

        async askQuestion() {
            if (!this.question.trim() || this.generating) return;

            this.generating = true;
            this.error = null;
            this.result = null;
            this.progressStep = 0;
            this.progressLabel = 'Starting...';

            try {
                const res = await fetch('/api/research/ask', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ question: this.question }),
                });

                if (!res.ok) {
                    const err = await res.json();
                    this.error = err.detail || 'Failed to start research session';
                    this.generating = false;
                    return;
                }

                // Poll for progress and result
                const poll = setInterval(async () => {
                    try {
                        const statusRes = await fetch('/api/research/status');
                        const status = await statusRes.json();

                        if (status.progress) {
                            this.progressLabel = status.progress.step || 'Working...';
                            this.progressStep = status.progress.step_num || 0;
                            this.progressTotal = status.progress.total_steps || 6;
                        }

                        if (status.error) {
                            clearInterval(poll);
                            this.generating = false;
                            this.error = status.error;
                            return;
                        }

                        if (!status.generating && status.result) {
                            clearInterval(poll);
                            this.generating = false;
                            this.result = status.result;
                        }
                    } catch (e) {
                        console.error('Poll error:', e);
                    }
                }, 3000);

                // Timeout after 10 minutes
                setTimeout(() => {
                    clearInterval(poll);
                    if (this.generating) {
                        this.generating = false;
                        this.error = 'Research session timed out';
                    }
                }, 600000);
            } catch (e) {
                console.error(e);
                this.error = e.message;
                this.generating = false;
            }
        },
    };
}
</script>
{% endblock %}
```

- [ ] **Step 2: Commit**

```bash
git add quant_team/templates/research.html
git commit -m "feat: add research page template with question input and agent panels"
```

---

### Task 7: End-to-end verification

- [ ] **Step 1: Verify all imports resolve**

Run: `cd /Users/justinprappas/trading && python -c "from quant_team.api.app import app; print('All imports OK')"`
Expected: `All imports OK`

- [ ] **Step 2: Verify API routes are registered**

Run: `cd /Users/justinprappas/trading && python -c "from quant_team.api.app import app; routes = [r.path for r in app.routes]; print('/api/research/ask' in routes, '/api/research/status' in routes, '/research' in routes)"`
Expected: `True True True`

- [ ] **Step 3: Commit all remaining changes**

If any files weren't committed in prior tasks, commit them now.

```bash
git add -A
git commit -m "feat: complete research Q&A feature — full round-table analysis on freeform questions"
```
