"""Orchestrates trading sessions — coordinates agent discussions and auto-executes trades."""

from __future__ import annotations

import json
import re
from datetime import datetime, date
from pathlib import Path

from sqlalchemy.orm import Session

from .agents.base import Agent, Message
from .teams.registry import TeamConfig
from .market.router import MarketDataRouter
from .market.indicators import compute_all
from .trading.risk import RiskChecker
from .trading.pdt import PDTChecker
from .trading.portfolio_manager import PortfolioManager
from .trading.execution_router import ExecutionRouter
from .database.models import Recommendation, AgentSession, PortfolioPosition


DEFAULT_WATCHLIST = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "TSLA", "META", "SPY", "QQQ"]


class TeamOrchestrator:
    """Orchestrates trading sessions for a specific team using its configuration."""

    def __init__(self, config: TeamConfig, db: Session):
        self.config = config
        self.db = db
        self.tickers = config.watchlist or DEFAULT_WATCHLIST

        # Construct agents dynamically from team config
        self.agents: list[Agent] = []
        for spec in config.agents:
            agent = Agent(
                name=spec.name,
                title=spec.title,
                system_prompt=spec.system_prompt,
                model=spec.model,
            )
            self.agents.append(agent)

        # The last agent is the decision-maker (CIO equivalent)
        self.decision_agent = self.agents[-1] if self.agents else None

        # Infrastructure
        self.market = MarketDataRouter(config)
        self.risk_checker = RiskChecker()
        self.pdt_checker = PDTChecker(db)
        self.portfolio = PortfolioManager(db, self.market)
        self.execution = ExecutionRouter(config)

    async def run_trading_session(
        self, tickers: list[str] | None = None, evolve_strategy: bool = False,
        on_progress: callable | None = None,
    ) -> list[Recommendation]:
        """Run a full trading session: analyze → discuss → decide → execute."""
        tickers = tickers or self.tickers
        _progress = on_progress or (lambda *a: None)

        # Step 1: Gather market data
        _progress("Fetching market data & indicators", 1, 6)
        market_context_parts = [self.market.get_market_summary(tickers)]

        for ticker in tickers[:6]:
            try:
                df = self.market.fetch_ohlcv(ticker, "3mo", "1d")
                indicators = compute_all(df)
                market_context_parts.append(f"\n## {ticker} Technical Analysis\n{indicators}")
            except Exception as e:
                market_context_parts.append(f"\n## {ticker}\nOHLCV unavailable: {e}")

        # Options data for top 3 tickers
        for ticker in tickers[:3]:
            try:
                options_summary = self.market.get_options_summary(ticker)
                market_context_parts.append(f"\n{options_summary}")
            except Exception:
                pass

        # Portfolio state
        portfolio_summary = self.portfolio.get_portfolio_summary_for_agents()
        market_context_parts.append(f"\n{portfolio_summary}")
        market_context_parts.append(f"\n{self.risk_checker.get_limits_summary()}")

        # PDT status
        pdt_summary = self.pdt_checker.get_summary_for_agents()
        market_context_parts.append(f"\n{pdt_summary}")

        # Load IPS if available
        ips_path = Path("data/ips.md")
        if ips_path.exists():
            ips = ips_path.read_text()
            market_context_parts.append(f"\n## Investment Policy Statement (Summary)\n{ips[:2000]}")

        market_context = "\n".join(market_context_parts)

        # Step 2: Agent round-table discussion
        discussion: list[Message] = []
        agent_analyses = {}

        pdt_status = self.pdt_checker.get_status()
        pdt_note = (
            f"PDT Status: {pdt_status['day_trades_used']}/{pdt_status['max_day_trades']} day trades used. "
            f"{pdt_status['day_trades_remaining']} remaining. Prefer swing trades (2+ day holds)."
        )

        if self.config.asset_class == "crypto":
            task_prompt = (
                f"Analyze the current crypto market conditions and our portfolio. "
                f"Watchlist: {', '.join(tickers)}. "
                f"We trade AUTONOMOUSLY — decisions execute immediately. "
                f"We can buy tokens (long only, NO shorting, NO leverage). "
                f"Our goal is to GROW the $10,000 portfolio. "
                f"Provide your assessment and any trade ideas from your perspective. "
                f"Reference specific data points from the indicators."
            )
        else:
            task_prompt = (
                f"Analyze the current US stock market conditions and our portfolio. "
                f"Watchlist: {', '.join(tickers)}. "
                f"We trade AUTONOMOUSLY — decisions execute immediately. "
                f"We can buy shares (long only, NO shorting) and trade options "
                f"(long calls, long puts, spreads — NO naked short options, NO futures). "
                f"Our goal is to GROW the $10,000 portfolio. "
                f"{pdt_note} "
                f"Provide your assessment and any trade ideas from your perspective. "
                f"Reference specific data points from the indicators."
            )

        # All agents except the last one are analysts; last one is the decision-maker
        analyst_agents = self.agents[:-1] if len(self.agents) > 1 else []
        total_steps = 6

        for i, agent in enumerate(analyst_agents):
            _progress(f"{agent.name} ({agent.title}) analyzing", 2 + i, total_steps)
            response = await agent.analyze(
                market_context=market_context,
                discussion=discussion,
                task=task_prompt,
            )
            discussion.append(Message(role=f"{agent.name} ({agent.title})", content=response))
            agent_analyses[agent.name.lower()] = response

        # Step 3: Decision-maker makes final decisions
        if self.decision_agent:
            _progress(f"{self.decision_agent.name} making final decisions", 2 + len(analyst_agents), total_steps)
            cio_response = await self.decision_agent.analyze(
                market_context=market_context,
                discussion=discussion,
                task=(
                    "You've heard from your team. Now make your FINAL TRADE DECISIONS. "
                    "These execute AUTOMATICALLY — be precise and deliberate. "
                    f"Watchlist: {', '.join(tickers)}. "
                    f"{pdt_note} "
                    "For each trade, output a JSON block with the required fields. "
                    "For SELL decisions, use the ticker of a position you currently hold. "
                    "Remember: NO shorting, NO futures, NO naked short options. "
                    "Your goal is to GROW this portfolio. "
                    "If no trades, explain why HOLD is the right call."
                ),
            )
            discussion.append(Message(role=f"{self.decision_agent.name} ({self.decision_agent.title})", content=cio_response))
            agent_analyses[self.decision_agent.name.lower()] = cio_response
        else:
            cio_response = ""

        # Step 4: Save session & execute
        _progress("Executing trades & saving session", 6, 6)
        session = AgentSession(
            team_id=self.config.team_id,
            tickers_analyzed=json.dumps(tickers),
            market_context_summary=market_context[:5000],
            macro_analysis=agent_analyses.get("macro", agent_analyses.get(self.agents[0].name.lower() if self.agents else "", "")),
            quant_analysis=agent_analyses.get("quant", agent_analyses.get(self.agents[1].name.lower() if len(self.agents) > 1 else "", "")),
            risk_analysis=agent_analyses.get("risk", agent_analyses.get(self.agents[2].name.lower() if len(self.agents) > 2 else "", "")),
            cio_decision=cio_response,
        )
        self.db.add(session)
        self.db.flush()

        # Step 5: Parse recommendations
        recommendations = self._parse_recommendations(cio_response, session.id)
        self.db.flush()

        # Step 6: AUTO-EXECUTE each recommendation
        for rec in recommendations:
            self._auto_execute(rec)

        session.recommendations_count = len(recommendations)
        self.db.commit()

        # Step 7: Evolve strategy if requested (end-of-day)
        if evolve_strategy and self.decision_agent:
            try:
                from .strategy.ips import evolve_ips
                await evolve_ips(self.decision_agent, self.db)
            except Exception:
                pass  # Don't fail the session if evolution fails

        return recommendations

    def _parse_recommendations(
        self, cio_response: str, session_id: int
    ) -> list[Recommendation]:
        """Extract JSON trade decisions from CIO/decision-maker response."""
        recommendations = []
        json_pattern = r'\{[^{}]*"action"[^{}]*\}'
        matches = re.findall(json_pattern, cio_response, re.DOTALL)

        for match in matches:
            try:
                data = json.loads(match)
            except json.JSONDecodeError:
                continue

            action = data.get("action", "").upper()
            if action not in ("BUY", "SELL", "HOLD"):
                continue

            ticker = data.get("ticker", "").upper()
            if not ticker:
                continue

            position_type = data.get("position_type", "shares").lower()

            expiry = None
            if data.get("expiry"):
                try:
                    expiry = date.fromisoformat(data["expiry"])
                except (ValueError, TypeError):
                    pass

            rec = Recommendation(
                team_id=self.config.team_id,
                session_id=session_id,
                ticker=ticker,
                action=action,
                position_type=position_type,
                quantity=data.get("quantity") or data.get("contracts"),
                strike=data.get("strike"),
                strike2=data.get("strike2"),
                expiry=expiry,
                reasoning=data.get("reasoning", ""),
                stop_loss=data.get("stop_loss"),
                stop_loss_pct=data.get("stop_loss_pct"),
                take_profit=data.get("take_profit"),
                take_profit_pct=data.get("take_profit_pct"),
                confidence=data.get("confidence"),
                timeframe=data.get("timeframe"),
                status="pending",  # Will be updated by _auto_execute
            )
            self.db.add(rec)
            recommendations.append(rec)

        return recommendations

    def _auto_execute(self, rec: Recommendation) -> None:
        """Automatically execute a recommendation: validate and open/close position."""
        if rec.action == "HOLD":
            rec.status = "executed"
            return

        if rec.action == "SELL":
            # Close existing position via execution router
            result = self.execution.execute_sell(rec, self.market, self.db, self.config.team_id)
            rec.status = "executed" if result.success else "blocked"
            if not result.success:
                rec.reasoning += f" [BLOCKED: {result.reason}]"
            return

        # BUY — validate first
        portfolio_data = self.portfolio.get_current_value()
        total_value = portfolio_data["total_value"]
        cash = portfolio_data["cash"]

        # Calculate position size as % of portfolio
        try:
            quote = self.market.fetch_quote(rec.ticker)
            price = quote["price"]
        except Exception:
            rec.status = "blocked"
            rec.reasoning += " [BLOCKED: Could not fetch price]"
            return

        is_options = rec.position_type != "shares"
        if is_options:
            quantity = rec.quantity or 1
            estimated_cost = price * 0.03 * 100 * quantity  # rough estimate
        else:
            quantity = rec.quantity or 1
            estimated_cost = price * quantity

        size_pct = (estimated_cost / total_value * 100) if total_value > 0 else 100

        # Risk check
        exposure_pct = (1 - cash / total_value) * 100 if total_value > 0 else 0
        drawdown_pct = portfolio_data["drawdown_pct"]

        approved, issues = self.risk_checker.check_trade(
            portfolio_value=total_value,
            cash=cash,
            size_pct=size_pct,
            stop_loss_pct=float(rec.stop_loss_pct or 5),
            current_exposure_pct=exposure_pct,
            current_drawdown_pct=drawdown_pct,
            is_options=is_options,
        )

        if not approved:
            rec.status = "blocked"
            rec.reasoning += f" [BLOCKED: {'; '.join(issues)}]"
            return

        # PDT check — would this create a day trade?
        if self.pdt_checker.would_be_day_trade(rec.ticker, "BUY"):
            can_dt, remaining = self.pdt_checker.can_day_trade()
            if not can_dt:
                rec.status = "blocked"
                rec.reasoning += " [BLOCKED: PDT limit reached — no day trades remaining]"
                return

        # Execute via execution router
        result = self.execution.execute_buy(rec, self.market, self.db, self.config.team_id)
        rec.status = "executed" if result.success else "blocked"
        if not result.success:
            rec.reasoning += f" [BLOCKED: {result.reason}]"


# Backward compatibility alias
TradingDesk = TeamOrchestrator
