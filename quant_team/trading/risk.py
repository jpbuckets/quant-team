"""Risk management rules and checks for stock/options trading."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RiskLimits:
    max_position_pct: float = 25.0           # Max single stock position as % of portfolio
    max_options_position_pct: float = 15.0   # Max single options position as % of portfolio
    max_exposure_pct: float = 90.0           # Max total exposure (rest in cash)
    max_sector_concentration_pct: float = 30.0  # Max in any one sector
    max_daily_drawdown_pct: float = 2.0      # Halt trading if daily DD exceeds this
    max_total_drawdown_pct: float = 15.0     # Close 50% positions if exceeded
    max_stop_loss_pct: float = 8.0           # Max stop loss distance for stocks
    max_options_loss_pct: float = 5.0        # Max loss per options trade as % of portfolio
    min_cash_pct: float = 10.0               # Minimum cash reserve
    max_correlated_pct: float = 40.0         # Max in highly correlated assets


class RiskChecker:
    """Validates trades against risk limits."""

    def __init__(self, limits: RiskLimits | None = None):
        self.limits = limits or RiskLimits()

    def check_trade(
        self,
        portfolio_value: float,
        cash: float,
        size_pct: float,
        stop_loss_pct: float,
        current_exposure_pct: float,
        current_drawdown_pct: float,
        is_options: bool = False,
    ) -> tuple[bool, list[str]]:
        """Check if a proposed trade passes risk limits. Returns (approved, reasons)."""
        issues = []
        max_pct = self.limits.max_options_position_pct if is_options else self.limits.max_position_pct

        # Position size check
        if size_pct > max_pct:
            issues.append(
                f"Position size {size_pct:.1f}% exceeds max "
                f"{'options ' if is_options else ''}{max_pct:.1f}%"
            )

        # Exposure check
        new_exposure = current_exposure_pct + size_pct
        if new_exposure > self.limits.max_exposure_pct:
            issues.append(
                f"Total exposure would be {new_exposure:.1f}%, exceeds max {self.limits.max_exposure_pct:.1f}%"
            )

        # Cash reserve check
        trade_amount = portfolio_value * (size_pct / 100)
        remaining_cash_pct = ((cash - trade_amount) / portfolio_value) * 100 if portfolio_value > 0 else 0
        if remaining_cash_pct < self.limits.min_cash_pct:
            issues.append(
                f"Remaining cash would be {remaining_cash_pct:.1f}%, below min {self.limits.min_cash_pct:.1f}%"
            )

        # Stop loss check (only for stocks)
        if not is_options and stop_loss_pct > self.limits.max_stop_loss_pct:
            issues.append(
                f"Stop loss {stop_loss_pct:.1f}% exceeds max {self.limits.max_stop_loss_pct:.1f}%"
            )

        # Drawdown checks
        if current_drawdown_pct > self.limits.max_daily_drawdown_pct:
            issues.append(
                f"Current drawdown {current_drawdown_pct:.2f}% exceeds daily limit "
                f"{self.limits.max_daily_drawdown_pct:.1f}% — trading halted"
            )

        if current_drawdown_pct > self.limits.max_total_drawdown_pct:
            issues.append(
                f"CRITICAL: Drawdown {current_drawdown_pct:.2f}% exceeds total limit "
                f"{self.limits.max_total_drawdown_pct:.1f}% — must reduce positions"
            )

        return len(issues) == 0, issues

    def get_limits_summary(self) -> str:
        """Text summary of risk limits for agents."""
        return (
            "# Active Risk Limits\n"
            f"- Max single stock position: {self.limits.max_position_pct}% of portfolio\n"
            f"- Max single options position: {self.limits.max_options_position_pct}% of portfolio\n"
            f"- Max total exposure: {self.limits.max_exposure_pct}%\n"
            f"- Max sector concentration: {self.limits.max_sector_concentration_pct}%\n"
            f"- Min cash reserve: {self.limits.min_cash_pct}%\n"
            f"- Max stop loss (stocks): {self.limits.max_stop_loss_pct}% from entry\n"
            f"- Max options loss per trade: {self.limits.max_options_loss_pct}% of portfolio\n"
            f"- Daily drawdown halt: {self.limits.max_daily_drawdown_pct}%\n"
            f"- Total drawdown limit: {self.limits.max_total_drawdown_pct}%\n"
            f"- Max correlated exposure: {self.limits.max_correlated_pct}%\n"
            f"- NO shorting stocks | NO futures | NO naked short options"
        )
