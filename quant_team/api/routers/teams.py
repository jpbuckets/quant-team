"""Team management API endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...teams.registry import TeamRegistry

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
