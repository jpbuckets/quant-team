"""Research Q&A — run agent round-table analysis on freeform questions."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

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
                    "You extract ticker symbols from questions about markets, economics, "
                    "and investing. Include stocks, ETFs, index symbols, AND commodity "
                    "futures (Yahoo Finance format: GC=F for gold, SI=F for silver, "
                    "CL=F for crude oil, NG=F for natural gas, ZC=F for corn, ZW=F for "
                    "wheat, ZS=F for soybeans, HG=F for copper, PL=F for platinum). "
                    "Return ONLY a JSON array of uppercase ticker symbols. Always include "
                    "both the futures contract AND relevant ETFs/stocks. Examples:\n"
                    '- "What does the corn farming report mean?" -> ["ZC=F", "CORN", "DBA", "ADM", "DE"]\n'
                    '- "What is happening with silver?" -> ["SI=F", "SLV", "SIVR", "AG", "PAAS"]\n'
                    '- "How will Fed rate cuts affect banks?" -> ["XLF", "KRE", "JPM", "BAC", "GS"]\n'
                    '- "What about gold prices?" -> ["GC=F", "GLD", "IAU", "NEM", "GOLD"]\n'
                    '- "Oil market outlook" -> ["CL=F", "USO", "XLE", "XOP", "CVX"]\n'
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

        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        if market_context_parts:
            market_context = f"# Market Data (fetched live at {now})\n\n"
            market_context += "\n".join(market_context_parts)
            market_context += f"\n\n## RESEARCH QUESTION\n{question}"
        else:
            market_context = (
                f"Data as of: {now}\n\n"
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
                    f"your perspective as {agent.title}. Provide detailed, actionable insights.\n\n"
                    f"IMPORTANT: The Market Data section above contains LIVE prices fetched "
                    f"moments ago. Use these exact prices and figures in your analysis — do NOT "
                    f"rely on older prices from your training data. Cite specific current prices, "
                    f"percentage changes, and levels from the provided data.\n\n"
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
                    f"IMPORTANT: The Market Data section above contains LIVE prices fetched "
                    f"moments ago. Reference these exact current prices in your synthesis — "
                    f"do NOT use older prices from your training data.\n\n"
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
