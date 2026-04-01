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

REPORT_WRITER_PROMPT = """\
You are a senior investment research editor at a top-tier financial publication.
Your job is to take raw analyst notes from a 4-person research team and rewrite
them into a polished, cohesive investment newsletter that a portfolio manager
can act on immediately.

## Output Structure (use ## markdown headings for each section)

## EXECUTIVE BRIEFING
2-3 paragraph narrative overview. No bullets here — just clear, authoritative
prose that captures the full picture in 60 seconds of reading.

## MARKET LANDSCAPE
Current market context and macro conditions woven into a readable narrative.
Reference specific prices, levels, and percentage changes from the analyst notes.

## QUANTITATIVE PICTURE
Key technical and quantitative signals. Use a mix of brief narrative and
selective bullets for key levels and metrics. Bold the most important figures.

## OPPORTUNITIES
Specific actionable investment ideas with reasoning. Use a mix of short prose
and structured bullet points. Each opportunity should have a clear thesis.

## RISK FACTORS
Key risks organized by severity. Brief, punchy prose. Be direct about what
could go wrong.

## BOTTOM LINE
1-2 paragraph synthesis with the single most important takeaway and recommended
positioning. This is what the reader remembers.

## Style Guidelines
- Write in clear, authoritative financial prose — not academic, not casual
- Use proper paragraphs (3-5 sentences each), not walls of bullet points
- Cite specific prices, levels, and percentages from the analyst notes
- Eliminate redundancy — if multiple analysts flagged the same point, mention
  it once with proper attribution
- Use markdown: **bold** for emphasis, - for bullet lists, ## for sections
- Target 800-1200 words total
- Never invent data not present in the analyst notes
- Do not use tables or numbered lists
"""


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
        total_steps = len(self.agents) + 3  # ticker extraction + market data + each agent + report writer

        # Step 1: Extract tickers
        _progress("Extracting relevant tickers", 1, total_steps)
        tickers = await extract_tickers(question)
        logger.info(f"Research: extracted tickers {tickers} from question")

        # Step 2: Fetch market data for extracted tickers
        _progress("Fetching market data", 2, total_steps)
        market_context_parts = []
        live_quotes: list[str] = []

        if tickers:
            # Fetch live quotes first — these go into a prominent header
            for ticker in tickers:
                try:
                    q = self.market.fetch_quote(ticker)
                    live_quotes.append(
                        f"  {ticker}: ${q['price']:,.2f} ({q['change_pct']:+.2f}%)"
                    )
                except Exception:
                    pass

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
            # Build a prominent live price header that cannot be missed
            price_block = "\n".join(live_quotes) if live_quotes else ""
            market_context = (
                "╔══════════════════════════════════════════════════╗\n"
                f"║  LIVE MARKET DATA — fetched {now}  ║\n"
                "╚══════════════════════════════════════════════════╝\n"
                f"\nCURRENT PRICES (use ONLY these prices in your analysis):\n"
                f"{price_block}\n\n"
                "These are real-time prices. Do NOT use any other prices.\n"
                "If you cite a price, it MUST match the data above.\n\n"
            )
            market_context += "\n".join(market_context_parts)
            market_context += f"\n\n## RESEARCH QUESTION\n{question}"
        else:
            market_context = (
                f"Data as of: {now}\n\n"
                "No specific market data available for this question. "
                "Answer based on your expertise and general market knowledge.\n\n"
                f"## RESEARCH QUESTION\n{question}"
            )

        # Build a price reminder that gets embedded in every agent task prompt
        # This is the strongest defense against training data prices
        if live_quotes:
            price_reminder = (
                f"\n\nCRITICAL — Today is {now}. Current live prices:\n"
                + "\n".join(live_quotes)
                + "\nYour analysis MUST use these exact prices. Any price you cite "
                "must match the data above. Do NOT use prices from your training data "
                "— they are months out of date."
            )
        else:
            price_reminder = f"\n\nToday is {now}."

        # Step 3: Run agent round-table
        discussion: list[Message] = []
        analyses: dict[str, str] = {}
        analyst_agents = self.agents[:-1] if len(self.agents) > 1 else []
        decision_agent = self.agents[-1] if self.agents else None

        for i, agent in enumerate(analyst_agents):
            if i > 0:
                await asyncio.sleep(60)  # Rate limit spacing
            _progress(f"{agent.name} ({agent.title}) analyzing", 3 + i, total_steps)
            # Disable memory for research sessions — prevents stale data anchoring
            agent.memory.clear()
            response = await agent.analyze(
                market_context=market_context,
                discussion=discussion,
                task=(
                    f"A user has asked your team a research question. Analyze it from "
                    f"your perspective as {agent.title}. Provide detailed, actionable insights."
                    f"{price_reminder}\n\n"
                    f"Question: {question}"
                ),
            )
            discussion.append(Message(role=f"{agent.name} ({agent.title})", content=response))
            analyses[agent.name.lower()] = response

        # Decision-maker synthesizes
        if decision_agent:
            if analyst_agents:
                await asyncio.sleep(60)
            _progress(f"{decision_agent.name} synthesizing", total_steps - 1, total_steps)
            decision_agent.memory.clear()
            response = await decision_agent.analyze(
                market_context=market_context,
                discussion=discussion,
                task=(
                    f"Your team has analyzed this research question. Synthesize their insights "
                    f"into a comprehensive response. Structure your analysis with these sections:\n\n"
                    f"**KEY FINDINGS** — What the data and your team's analysis reveals\n"
                    f"**OPPORTUNITIES** — Specific investment opportunities identified\n"
                    f"**RISKS** — Key risks and concerns to watch\n"
                    f"**ACTIONABLE IDEAS** — Concrete next steps or trades to consider"
                    f"{price_reminder}\n\n"
                    f"Do NOT output JSON trade blocks. This is a research session, not a trading session.\n\n"
                    f"Question: {question}"
                ),
            )
            analyses[decision_agent.name.lower()] = response

        # Step 4: Report Writer — rewrite into polished newsletter
        newsletter = ""
        try:
            await asyncio.sleep(60)
            _progress("Report Writer composing newsletter", total_steps, total_steps)
            report_writer = Agent(
                name="ReportWriter",
                title="Investment Report Writer",
                system_prompt=REPORT_WRITER_PROMPT,
                model="claude-sonnet-4-20250514",
            )
            writer_prompt = (
                f"Rewrite the following analyst notes into a polished investment newsletter.\n\n"
                f"**Research Question:** {question}\n"
                f"**Tickers Analyzed:** {', '.join(tickers)}\n\n"
                f"--- MACRO ANALYST ---\n{analyses.get('macro', 'N/A')}\n\n"
                f"--- QUANT ANALYST ---\n{analyses.get('quant', 'N/A')}\n\n"
                f"--- RISK OFFICER ---\n{analyses.get('risk', 'N/A')}\n\n"
                f"--- CIO SYNTHESIS ---\n{analyses.get('cio', 'N/A')}"
            )
            newsletter = await report_writer.respond(writer_prompt)
            logger.info("Report Writer completed newsletter")
        except Exception as e:
            logger.error(f"Report Writer failed: {e}", exc_info=True)

        result = {
            "question": question,
            "tickers_analyzed": tickers,
            "macro": analyses.get("macro", ""),
            "quant": analyses.get("quant", ""),
            "risk": analyses.get("risk", ""),
            "cio": analyses.get("cio", ""),
        }
        if newsletter:
            result["newsletter"] = newsletter
        return result
