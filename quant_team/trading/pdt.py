"""Pattern Day Trading (PDT) rule enforcement.

PDT rules for accounts under $25,000:
- A day trade = buying and selling the same security on the same calendar day
- Pattern Day Trader = 4+ day trades in any 5 rolling business days
- We must stay at 3 or fewer day trades per 5 business days
"""

from __future__ import annotations

from datetime import datetime, timedelta, date
from collections import defaultdict

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database.models import TradeRecord


class PDTChecker:
    """Tracks and enforces Pattern Day Trading rules."""

    MAX_DAY_TRADES = 3
    LOOKBACK_BUSINESS_DAYS = 5

    def __init__(self, db: Session):
        self.db = db

    def _get_business_days_ago(self, n: int) -> date:
        """Get the date N business days ago."""
        current = date.today()
        days_back = 0
        while days_back < n:
            current -= timedelta(days=1)
            if current.weekday() < 5:  # Mon-Fri
                days_back += 1
        return current

    def count_day_trades(self) -> int:
        """Count round-trip same-day trades in the last 5 business days."""
        cutoff = self._get_business_days_ago(self.LOOKBACK_BUSINESS_DAYS)

        trades = (
            self.db.query(TradeRecord)
            .filter(TradeRecord.timestamp >= datetime.combine(cutoff, datetime.min.time()))
            .order_by(TradeRecord.timestamp)
            .all()
        )

        # Group trades by (ticker, calendar date)
        daily_trades: dict[tuple[str, date], dict[str, int]] = defaultdict(
            lambda: {"BUY": 0, "SELL": 0}
        )
        for t in trades:
            trade_date = t.timestamp.date() if t.timestamp else date.today()
            key = (t.ticker, trade_date)
            daily_trades[key][t.action] += 1

        # A day trade = both BUY and SELL of the same ticker on the same day
        day_trade_count = 0
        for (ticker, trade_date), actions in daily_trades.items():
            if actions["BUY"] > 0 and actions["SELL"] > 0:
                day_trade_count += min(actions["BUY"], actions["SELL"])

        return day_trade_count

    def get_remaining_day_trades(self) -> int:
        """How many day trades are still allowed."""
        used = self.count_day_trades()
        return max(0, self.MAX_DAY_TRADES - used)

    def can_day_trade(self) -> tuple[bool, int]:
        """Returns (allowed, remaining_day_trades)."""
        remaining = self.get_remaining_day_trades()
        return remaining > 0, remaining

    def would_be_day_trade(self, ticker: str, action: str) -> bool:
        """Check if executing this trade would create a day trade.

        A day trade occurs when you buy and sell (or sell and buy)
        the same security on the same calendar day.
        """
        today = date.today()
        start_of_day = datetime.combine(today, datetime.min.time())

        # Check if we have the opposite action for this ticker today
        opposite = "SELL" if action == "BUY" else "BUY"
        existing = (
            self.db.query(TradeRecord)
            .filter(
                TradeRecord.ticker == ticker,
                TradeRecord.action == opposite,
                TradeRecord.timestamp >= start_of_day,
            )
            .count()
        )

        return existing > 0

    def get_status(self) -> dict:
        """Get full PDT status for display."""
        used = self.count_day_trades()
        remaining = max(0, self.MAX_DAY_TRADES - used)
        return {
            "day_trades_used": used,
            "day_trades_remaining": remaining,
            "max_day_trades": self.MAX_DAY_TRADES,
            "lookback_days": self.LOOKBACK_BUSINESS_DAYS,
            "pdt_restricted": remaining == 0,
        }

    def get_summary_for_agents(self) -> str:
        """Text summary for agent consumption."""
        status = self.get_status()
        return (
            "# Pattern Day Trading (PDT) Status\n"
            f"- Day trades used (5-day rolling): {status['day_trades_used']}/{status['max_day_trades']}\n"
            f"- Day trades remaining: {status['day_trades_remaining']}\n"
            f"- PDT restricted: {'YES — NO same-day round trips allowed' if status['pdt_restricted'] else 'No'}\n"
            f"- Rule: Max {status['max_day_trades']} day trades per {status['lookback_days']} business days (account < $25k)\n"
            f"- A day trade = buying AND selling the same stock on the same day\n"
            f"- **Prefer swing trades (hold 2+ days) to conserve day trades**"
        )
