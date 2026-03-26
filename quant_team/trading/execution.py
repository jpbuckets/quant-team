"""Paper trade execution framework — BaseExecutor ABC and PaperExecutor implementation."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.orm import Session

from ..database.models import (
    PortfolioPosition, PortfolioState, Recommendation, TradeRecord,
)
from ..market.router import MarketDataRouter

logger = logging.getLogger("quant_team")


@dataclass
class ExecutionResult:
    """Result of a paper trade execution attempt."""

    success: bool
    trade_record: TradeRecord | None = None
    position: PortfolioPosition | None = None
    reason: str = ""
    simulated_price: float = 0.0


class BaseExecutor(ABC):
    """Abstract base for trade execution backends (paper, Alpaca, Solana, etc.)."""

    @abstractmethod
    def execute_buy(
        self,
        rec: Recommendation,
        market: MarketDataRouter,
        db: Session,
        team_id: str,
    ) -> ExecutionResult:
        """Execute a BUY recommendation. Returns ExecutionResult with success/failure detail."""

    @abstractmethod
    def execute_sell(
        self,
        rec: Recommendation,
        market: MarketDataRouter,
        db: Session,
        team_id: str,
    ) -> ExecutionResult:
        """Execute a SELL recommendation. Returns ExecutionResult with success/failure detail."""


class PaperExecutor(BaseExecutor):
    """Simulates trade execution without sending real orders."""

    def execute_buy(
        self,
        rec: Recommendation,
        market: MarketDataRouter,
        db: Session,
        team_id: str,
    ) -> ExecutionResult:
        """Simulate a BUY: fetch price, check cash, deduct, open position, log trade."""
        # Fetch simulated fill price
        try:
            quote = market.fetch_quote(rec.ticker)
            current_price = float(quote["price"])
        except Exception:
            return ExecutionResult(success=False, reason="Price fetch failed")

        quantity = rec.quantity or 1.0

        # Calculate cost — options use 0.03 * underlying * 100 * contracts fallback
        if rec.position_type == "shares":
            cost = current_price * quantity
        else:
            # Options: try options chain; fall back to 3% of underlying per contract
            option_price = current_price * 0.03
            current_price = option_price
            cost = option_price * 100 * quantity

        # Check portfolio cash
        state = self._get_state(db, team_id)
        if cost > state.cash or cost <= 0:
            return ExecutionResult(success=False, reason="Insufficient cash")

        # Deduct cash
        state.cash -= cost
        state.updated_at = datetime.utcnow()

        # Open position
        position = PortfolioPosition(
            team_id=team_id,
            recommendation_id=rec.id,
            ticker=rec.ticker,
            position_type=rec.position_type,
            entry_price=current_price,
            quantity=quantity,
            status="open",
        )
        db.add(position)

        # Write trade record
        reasoning = "[PAPER] " + (rec.reasoning or "")
        trade = TradeRecord(
            team_id=team_id,
            recommendation_id=rec.id,
            ticker=rec.ticker,
            action="BUY",
            position_type=rec.position_type,
            price=current_price,
            quantity=quantity,
            notional=cost,
            reasoning=reasoning,
        )
        db.add(trade)

        # Update recommendation entry price
        rec.entry_price = current_price

        db.commit()

        # Link trade to position after IDs are assigned
        trade.position_id = position.id
        db.commit()

        logger.info(f"[PAPER] BUY {quantity} {rec.ticker} @ ${current_price:.2f}")

        return ExecutionResult(
            success=True,
            trade_record=trade,
            position=position,
            simulated_price=current_price,
        )

    def execute_sell(
        self,
        rec: Recommendation,
        market: MarketDataRouter,
        db: Session,
        team_id: str,
    ) -> ExecutionResult:
        """Simulate a SELL: find open position, fetch price, close position, return proceeds."""
        # Find open position for ticker
        pos = (
            db.query(PortfolioPosition)
            .filter(
                PortfolioPosition.team_id == team_id,
                PortfolioPosition.ticker == rec.ticker,
                PortfolioPosition.status == "open",
            )
            .first()
        )
        if pos is None:
            return ExecutionResult(
                success=False,
                reason=f"No open position found for {rec.ticker}",
            )

        # Fetch simulated fill price
        try:
            quote = market.fetch_quote(rec.ticker)
            current_price = float(quote["price"])
        except Exception:
            current_price = pos.entry_price

        # Calculate proceeds and PnL
        if pos.position_type == "shares":
            notional = current_price * pos.quantity
            pnl = (current_price - pos.entry_price) * pos.quantity
        else:
            # Options: use entry_price fallback if chain unavailable
            notional = current_price * 100 * pos.quantity
            pnl = (current_price - pos.entry_price) * 100 * pos.quantity

        # Update portfolio cash
        state = self._get_state(db, team_id)
        state.cash += notional
        state.total_realized_pnl += pnl
        state.updated_at = datetime.utcnow()

        # Close position
        pos.status = "closed"
        pos.exit_price = current_price
        pos.realized_pnl = pnl
        pos.closed_at = datetime.utcnow()

        # Write trade record
        reasoning = "[PAPER] " + (rec.reasoning or "")
        trade = TradeRecord(
            team_id=team_id,
            position_id=pos.id,
            recommendation_id=rec.id,
            ticker=rec.ticker,
            action="SELL",
            position_type=pos.position_type,
            price=current_price,
            quantity=pos.quantity,
            notional=notional,
            pnl=pnl,
            reasoning=reasoning,
        )
        db.add(trade)
        db.commit()

        logger.info(f"[PAPER] SELL {pos.quantity} {rec.ticker} @ ${current_price:.2f} | PnL: ${pnl:.2f}")

        return ExecutionResult(
            success=True,
            trade_record=trade,
            position=pos,
            simulated_price=current_price,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_state(self, db: Session, team_id: str) -> PortfolioState:
        """Fetch or create PortfolioState for the team."""
        state = db.query(PortfolioState).filter_by(team_id=team_id).first()
        if state is None:
            state = PortfolioState(
                cash=10000.0, initial_capital=10000.0,
                peak_value=10000.0, total_realized_pnl=0.0,
                team_id=team_id,
            )
            db.add(state)
            db.commit()
        return state
