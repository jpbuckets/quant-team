"""Execution routing — dispatches trade execution to the correct backend based on team config."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from .execution import BaseExecutor, ExecutionResult, PaperExecutor
from ..market.router import MarketDataRouter
from ..teams.registry import TeamConfig
from ..database.models import Recommendation

logger = logging.getLogger("quant_team")


class ExecutionRouter:
    """Routes trade execution to the correct backend based on team config."""

    def __init__(self, config: TeamConfig):
        self.config = config
        self._executor: BaseExecutor = self._build_executor(config.execution_backend)

    def _build_executor(self, backend: str) -> BaseExecutor:
        """Instantiate the correct executor for the given backend name."""
        if backend == "paper":
            return PaperExecutor()
        # Future: elif backend == "alpaca": return AlpacaExecutor(...)
        # Future: elif backend == "solana": return SolanaExecutor(...)
        else:
            raise ValueError(f"Unknown execution_backend: {backend!r}")

    def execute_buy(
        self,
        rec: Recommendation,
        market: MarketDataRouter,
        db: Session,
        team_id: str,
    ) -> ExecutionResult:
        """Delegate BUY execution to the current backend."""
        return self._executor.execute_buy(rec, market, db, team_id)

    def execute_sell(
        self,
        rec: Recommendation,
        market: MarketDataRouter,
        db: Session,
        team_id: str,
    ) -> ExecutionResult:
        """Delegate SELL execution to the current backend."""
        return self._executor.execute_sell(rec, market, db, team_id)

    def update_backend(self, backend: str) -> None:
        """Hot-swap executor backend without restart."""
        self._executor = self._build_executor(backend)
        self.config.execution_backend = backend
        logger.info(f"ExecutionRouter: backend changed to {backend!r} for team {self.config.team_id!r}")
