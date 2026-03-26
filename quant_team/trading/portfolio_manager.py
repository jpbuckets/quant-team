"""Database-backed portfolio manager for the autonomous trading desk."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from ..database.models import (
    PortfolioState, PortfolioPosition, PortfolioSnapshot,
    TradeRecord, Recommendation,
)
from ..market.router import MarketDataRouter


class PortfolioManager:
    """Manages the fictional $10,000 portfolio backed by SQLite."""

    def __init__(self, db: Session, market: MarketDataRouter):
        self.db = db
        self.market = market

    def get_state(self, team_id: str = "quant") -> PortfolioState:
        state = self.db.query(PortfolioState).filter_by(team_id=team_id).first()
        if state is None:
            state = PortfolioState(
                cash=10000.0, initial_capital=10000.0,
                peak_value=10000.0, total_realized_pnl=0.0,
                team_id=team_id,
            )
            self.db.add(state)
            self.db.commit()
        return state

    def get_open_positions(self, team_id: str = "quant") -> list[PortfolioPosition]:
        return (
            self.db.query(PortfolioPosition)
            .filter(PortfolioPosition.status == "open", PortfolioPosition.team_id == team_id)
            .all()
        )

    def execute_recommendation(self, rec: Recommendation) -> PortfolioPosition | None:
        """Execute a trade recommendation — open a position."""
        state = self.get_state()

        # Get current price
        try:
            quote = self.market.fetch_quote(rec.ticker)
            current_price = quote["price"]
        except Exception:
            return None

        # Calculate cost
        if rec.position_type == "shares":
            quantity = rec.quantity or 1
            cost = current_price * quantity
        else:
            contracts = rec.quantity or 1
            try:
                chain = self.market.fetch_options_chain(rec.ticker)
                option_price = self._find_option_price(
                    chain, rec.strike, rec.expiry, rec.position_type
                )
                if option_price:
                    current_price = option_price
                    cost = option_price * 100 * contracts
                else:
                    option_price = current_price * 0.03
                    current_price = option_price
                    cost = option_price * 100 * contracts
            except Exception:
                option_price = current_price * 0.03
                current_price = option_price
                cost = option_price * 100 * contracts

        if cost > state.cash or cost <= 0:
            return None

        # Deduct cash
        state.cash -= cost
        state.updated_at = datetime.utcnow()

        # Create position
        position = PortfolioPosition(
            recommendation_id=rec.id,
            ticker=rec.ticker,
            position_type=rec.position_type,
            entry_price=current_price,
            quantity=rec.quantity or 1,
            strike=rec.strike,
            strike2=rec.strike2,
            expiry=rec.expiry,
            stop_loss=rec.stop_loss if rec.position_type == "shares" else None,
            take_profit=rec.take_profit if rec.position_type == "shares" else None,
            status="open",
        )
        self.db.add(position)

        # Record trade
        trade = TradeRecord(
            recommendation_id=rec.id,
            ticker=rec.ticker,
            action="BUY",
            position_type=rec.position_type,
            price=current_price,
            quantity=rec.quantity or 1,
            notional=cost,
            reasoning=rec.reasoning,
        )
        self.db.add(trade)

        # Update recommendation
        rec.entry_price = current_price

        self.db.commit()

        trade.position_id = position.id
        self.db.commit()

        return position

    def sell_by_ticker(self, ticker: str, reasoning: str = "") -> TradeRecord | None:
        """Find and close an open position for the given ticker."""
        pos = (
            self.db.query(PortfolioPosition)
            .filter(
                PortfolioPosition.ticker == ticker,
                PortfolioPosition.status == "open",
            )
            .first()
        )
        if pos is None:
            return None
        return self.close_position(pos.id, reasoning)

    def close_position(self, position_id: int, reasoning: str = "Position closed") -> TradeRecord | None:
        """Close an open position at current market price."""
        pos = self.db.query(PortfolioPosition).get(position_id)
        if pos is None or pos.status != "open":
            return None

        state = self.get_state()

        try:
            if pos.position_type == "shares":
                quote = self.market.fetch_quote(pos.ticker)
                current_price = quote["price"]
                notional = current_price * pos.quantity
                pnl = (current_price - pos.entry_price) * pos.quantity
            else:
                chain = self.market.fetch_options_chain(pos.ticker)
                option_price = self._find_option_price(
                    chain, pos.strike, pos.expiry, pos.position_type
                )
                if option_price:
                    current_price = option_price
                else:
                    current_price = pos.entry_price
                notional = current_price * 100 * pos.quantity
                pnl = (current_price - pos.entry_price) * 100 * pos.quantity
        except Exception:
            current_price = pos.entry_price
            notional = current_price * (100 if pos.position_type != "shares" else 1) * pos.quantity
            pnl = 0.0

        # Update cash
        state.cash += notional
        state.total_realized_pnl += pnl
        state.updated_at = datetime.utcnow()

        # Close position
        pos.status = "closed"
        pos.exit_price = current_price
        pos.realized_pnl = pnl
        pos.closed_at = datetime.utcnow()

        # Update recommendation if linked
        if pos.recommendation_id:
            rec = self.db.query(Recommendation).get(pos.recommendation_id)
            if rec:
                rec.exit_price = current_price
                rec.outcome_pnl = pnl
                entry_cost = pos.entry_price * (100 if pos.position_type != "shares" else 1) * pos.quantity
                rec.outcome_pct = (pnl / entry_cost * 100) if entry_cost > 0 else 0
                rec.closed_at = datetime.utcnow()

        # Record trade
        trade = TradeRecord(
            position_id=position_id,
            recommendation_id=pos.recommendation_id,
            ticker=pos.ticker,
            action="SELL",
            position_type=pos.position_type,
            price=current_price,
            quantity=pos.quantity,
            notional=notional,
            pnl=pnl,
            reasoning=reasoning,
        )
        self.db.add(trade)
        self.db.commit()

        return trade

    def check_stops(self, team_id: str = "quant") -> list[TradeRecord]:
        """Check stop-loss and take-profit on open positions."""
        closed = []
        for pos in self.get_open_positions(team_id=team_id):
            if pos.position_type != "shares":
                continue

            try:
                quote = self.market.fetch_quote(pos.ticker)
                price = quote["price"]
            except Exception:
                continue

            if pos.stop_loss and price <= pos.stop_loss:
                trade = self.close_position(pos.id, "Stop-loss triggered")
                if trade:
                    closed.append(trade)
            elif pos.take_profit and price >= pos.take_profit:
                trade = self.close_position(pos.id, "Take-profit triggered")
                if trade:
                    closed.append(trade)

        return closed

    def get_current_value(self, team_id: str = "quant") -> dict:
        """Calculate current portfolio value with live prices."""
        state = self.get_state(team_id=team_id)
        positions = self.get_open_positions(team_id=team_id)

        total_invested = 0.0
        total_unrealized = 0.0
        position_details = []

        for pos in positions:
            try:
                if pos.position_type == "shares":
                    quote = self.market.fetch_quote(pos.ticker)
                    current_price = quote["price"]
                    market_value = current_price * pos.quantity
                    cost_basis = pos.entry_price * pos.quantity
                    unrealized = market_value - cost_basis
                else:
                    chain = self.market.fetch_options_chain(pos.ticker)
                    option_price = self._find_option_price(
                        chain, pos.strike, pos.expiry, pos.position_type
                    )
                    current_price = option_price if option_price else pos.entry_price
                    market_value = current_price * 100 * pos.quantity
                    cost_basis = pos.entry_price * 100 * pos.quantity
                    unrealized = market_value - cost_basis

                total_invested += market_value
                total_unrealized += unrealized
                pnl_pct = (unrealized / cost_basis * 100) if cost_basis > 0 else 0
                position_details.append({
                    "id": pos.id, "ticker": pos.ticker, "position_type": pos.position_type,
                    "quantity": pos.quantity, "entry_price": pos.entry_price,
                    "current_price": current_price, "market_value": market_value,
                    "cost_basis": cost_basis, "unrealized_pnl": unrealized, "pnl_pct": pnl_pct,
                    "strike": pos.strike, "expiry": str(pos.expiry) if pos.expiry else None,
                    "stop_loss": pos.stop_loss, "take_profit": pos.take_profit,
                    "opened_at": pos.opened_at.isoformat() if pos.opened_at else None,
                })
            except Exception:
                cost_basis = pos.entry_price * (100 if pos.position_type != "shares" else 1) * pos.quantity
                total_invested += cost_basis
                position_details.append({
                    "id": pos.id, "ticker": pos.ticker, "position_type": pos.position_type,
                    "quantity": pos.quantity, "entry_price": pos.entry_price,
                    "current_price": pos.entry_price, "market_value": cost_basis,
                    "cost_basis": cost_basis, "unrealized_pnl": 0, "pnl_pct": 0,
                    "strike": pos.strike, "expiry": str(pos.expiry) if pos.expiry else None,
                    "stop_loss": pos.stop_loss, "take_profit": pos.take_profit,
                    "opened_at": pos.opened_at.isoformat() if pos.opened_at else None,
                })

        total_value = state.cash + total_invested
        total_return_pct = (total_value / state.initial_capital - 1) * 100

        if total_value > state.peak_value:
            state.peak_value = total_value
            self.db.commit()

        drawdown = (state.peak_value - total_value) / state.peak_value * 100 if state.peak_value > 0 else 0

        return {
            "total_value": total_value, "cash": state.cash, "invested": total_invested,
            "unrealized_pnl": total_unrealized, "realized_pnl": state.total_realized_pnl,
            "total_return_pct": total_return_pct, "drawdown_pct": drawdown,
            "initial_capital": state.initial_capital, "positions": position_details,
        }

    def get_portfolio_summary_for_agents(self) -> str:
        """Text summary for agent consumption."""
        data = self.get_current_value()
        lines = [
            "# Portfolio State",
            f"- **Total Value**: ${data['total_value']:,.2f}",
            f"- **Cash**: ${data['cash']:,.2f} ({data['cash']/data['total_value']*100:.1f}%)" if data['total_value'] > 0 else f"- **Cash**: ${data['cash']:,.2f}",
            f"- **Return**: {data['total_return_pct']:+.2f}%",
            f"- **Drawdown**: {data['drawdown_pct']:.2f}%",
            f"- **Realized P&L**: ${data['realized_pnl']:,.2f}",
            f"- **Unrealized P&L**: ${data['unrealized_pnl']:,.2f}",
            "",
        ]

        if data["positions"]:
            lines.append("## Open Positions")
            for p in data["positions"]:
                if p["position_type"] == "shares":
                    lines.append(
                        f"- **{p['ticker']}** (shares): {p['quantity']:.0f} @ ${p['entry_price']:,.2f} "
                        f"→ ${p['current_price']:,.2f} | P&L: ${p['unrealized_pnl']:,.2f} ({p['pnl_pct']:+.1f}%)"
                    )
                else:
                    lines.append(
                        f"- **{p['ticker']}** ({p['position_type']}): {p['quantity']:.0f}x "
                        f"${p.get('strike', 'N/A')} strike exp {p.get('expiry', 'N/A')} | "
                        f"P&L: ${p['unrealized_pnl']:,.2f} ({p['pnl_pct']:+.1f}%)"
                    )
        else:
            lines.append("## No open positions")

        return "\n".join(lines)

    def take_snapshot(self, team_id: str = "quant") -> PortfolioSnapshot:
        data = self.get_current_value(team_id=team_id)
        snapshot = PortfolioSnapshot(
            total_value=data["total_value"], cash=data["cash"],
            invested=data["invested"], unrealized_pnl=data["unrealized_pnl"],
            realized_pnl=data["realized_pnl"], total_return_pct=data["total_return_pct"],
            team_id=team_id,
        )
        self.db.add(snapshot)
        self.db.commit()
        return snapshot

    def reset(self, team_id: str = "quant") -> None:
        for pos in self.get_open_positions(team_id=team_id):
            pos.status = "closed"
            pos.closed_at = datetime.utcnow()
        state = self.get_state(team_id=team_id)
        state.cash = 10000.0
        state.initial_capital = 10000.0
        state.peak_value = 10000.0
        state.total_realized_pnl = 0.0
        state.updated_at = datetime.utcnow()
        self.db.commit()

    def _find_option_price(self, chain_data: dict, strike, expiry, position_type: str) -> float | None:
        if not strike or not chain_data.get("chains"):
            return None
        expiry_str = str(expiry) if expiry else None
        is_call = "call" in position_type
        for exp, chain in chain_data["chains"].items():
            if expiry_str and exp != expiry_str:
                continue
            options = chain["calls"] if is_call else chain["puts"]
            for opt in options:
                if abs(opt["strike"] - strike) < 0.01:
                    mid = (opt["bid"] + opt["ask"]) / 2 if opt["bid"] and opt["ask"] else opt["lastPrice"]
                    return mid if mid > 0 else opt["lastPrice"]
        return None
