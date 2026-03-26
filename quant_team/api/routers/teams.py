"""Team management API endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...database.connection import get_db
from ...market.router import MarketDataRouter
from ...teams.registry import TeamRegistry
from ...trading.portfolio_manager import PortfolioManager

logger = logging.getLogger("quant_team")
router = APIRouter()


class ExecutionModeRequest(BaseModel):
    mode: str  # "paper" or future: "alpaca", "solana"


@router.get("")
def list_teams():
    """List all configured teams."""
    registry = TeamRegistry()
    teams = registry.all()
    return [
        {
            "team_id": t.team_id,
            "name": t.name,
            "asset_class": t.asset_class,
            "execution_backend": t.execution_backend,
            "watchlist": t.watchlist,
        }
        for t in teams
    ]


@router.get("/summary")
def teams_summary():
    """Cross-team aggregate portfolio summary across all configured teams."""
    registry = TeamRegistry()
    all_teams = registry.all()
    db = get_db()
    try:
        team_summaries = []
        aggregate_total_value = 0.0
        aggregate_cash = 0.0
        aggregate_unrealized_pnl = 0.0
        aggregate_realized_pnl = 0.0
        aggregate_initial_capital = 0.0

        for t in all_teams:
            try:
                market = MarketDataRouter(t)
                pm = PortfolioManager(db, market)
                data = pm.get_current_value(team_id=t.team_id)

                total_value = data.get("total_value", 0.0)
                cash = data.get("cash", 0.0)
                unrealized_pnl = data.get("unrealized_pnl", 0.0)
                realized_pnl = data.get("realized_pnl", 0.0)
                initial_capital = data.get("initial_capital", 10000.0)
                position_count = len(data.get("positions", []))

                aggregate_total_value += total_value
                aggregate_cash += cash
                aggregate_unrealized_pnl += unrealized_pnl
                aggregate_realized_pnl += realized_pnl
                aggregate_initial_capital += initial_capital

                team_summaries.append({
                    "team_id": t.team_id,
                    "name": t.name,
                    "asset_class": t.asset_class,
                    "execution_backend": t.execution_backend,
                    "total_value": total_value,
                    "unrealized_pnl": unrealized_pnl,
                    "position_count": position_count,
                })
            except Exception as e:
                logger.error(f"Failed to get value for team {t.team_id}: {e}")
                team_summaries.append({
                    "team_id": t.team_id,
                    "name": t.name,
                    "asset_class": t.asset_class,
                    "execution_backend": t.execution_backend,
                    "total_value": 0.0,
                    "unrealized_pnl": 0.0,
                    "position_count": 0,
                })

        total_return_pct = (
            (aggregate_total_value / aggregate_initial_capital - 1) * 100
            if aggregate_initial_capital > 0
            else 0.0
        )

        return {
            "aggregate": {
                "total_value": aggregate_total_value,
                "cash": aggregate_cash,
                "unrealized_pnl": aggregate_unrealized_pnl,
                "realized_pnl": aggregate_realized_pnl,
                "total_return_pct": total_return_pct,
            },
            "teams": team_summaries,
        }
    finally:
        db.close()


@router.get("/{team_id}")
def get_team(team_id: str):
    """Get full detail for a single team including execution_backend and risk limits."""
    registry = TeamRegistry()
    try:
        config = registry.get(team_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Team not found: {team_id}")
    return {
        "team_id": config.team_id,
        "name": config.name,
        "asset_class": config.asset_class,
        "execution_backend": config.execution_backend,
        "watchlist": config.watchlist,
        "risk_limits": {
            "max_position_pct": config.risk_limits.max_position_pct,
            "max_exposure_pct": config.risk_limits.max_exposure_pct,
            "max_drawdown_pct": config.risk_limits.max_drawdown_pct,
            "max_options_pct": config.risk_limits.max_options_pct,
        },
    }


@router.patch("/{team_id}/execution-mode")
def update_execution_mode(team_id: str, body: ExecutionModeRequest):
    """Toggle execution mode for a team (paper/live). Takes effect on next session."""
    valid_modes = ["paper"]  # Expand when live executors added
    if body.mode not in valid_modes:
        raise HTTPException(400, f"Invalid mode: {body.mode}. Valid: {valid_modes}")
    registry = TeamRegistry()
    try:
        config = registry.get(team_id)
    except KeyError:
        raise HTTPException(404, f"Team not found: {team_id}")
    config.execution_backend = body.mode
    logger.info(f"Team {team_id} execution mode changed to: {body.mode}")
    return {"team_id": team_id, "execution_backend": body.mode}
