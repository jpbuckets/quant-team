"""Research Q&A API — ask the trading team questions without executing trades."""

from __future__ import annotations

import asyncio
import logging
import uuid

from fastapi import APIRouter, HTTPException, BackgroundTasks

from ...teams.registry import TeamRegistry
from ...research import ResearchSession
from ..schemas import ResearchRequest

logger = logging.getLogger("quant_team")

router = APIRouter(prefix="/api/research", tags=["research"])

_sessions: dict[str, dict] = {}


def _update_progress(session_id: str, step: str, step_num: int, total_steps: int) -> None:
    if session_id in _sessions:
        _sessions[session_id]["progress"] = {
            "step": step,
            "step_num": step_num,
            "total_steps": total_steps,
        }
    logger.info(f"Research progress [{step_num}/{total_steps}]: {step}")


async def _run_research(session_id: str, question: str, team_id: str) -> None:
    _sessions[session_id] = {
        "generating": True,
        "error": None,
        "result": None,
        "progress": {"step": "Starting...", "step_num": 0, "total_steps": 6},
    }
    try:
        registry = TeamRegistry()
        config = registry.get(team_id)
        session = ResearchSession(config=config)
        result = await session.run(
            question=question,
            on_progress=lambda s, n, t: _update_progress(session_id, s, n, t),
        )
        _sessions[session_id]["result"] = result
        _sessions[session_id]["progress"] = {
            "step": "Complete",
            "step_num": _sessions[session_id]["progress"]["total_steps"],
            "total_steps": _sessions[session_id]["progress"]["total_steps"],
        }
        logger.info("Research session completed successfully")
    except asyncio.TimeoutError:
        _sessions[session_id]["error"] = "Research timed out after 5 minutes"
    except Exception as e:
        _sessions[session_id]["error"] = str(e)
        logger.error(f"Research session failed: {e}", exc_info=True)
    finally:
        _sessions[session_id]["generating"] = False


@router.post("/ask")
async def ask_question(body: ResearchRequest, background_tasks: BackgroundTasks):
    if any(s["generating"] for s in _sessions.values()):
        raise HTTPException(status_code=409, detail="Research session already in progress")
    session_id = str(uuid.uuid4())
    background_tasks.add_task(_run_research, session_id, body.question, body.team_id)
    return {"status": "started", "session_id": session_id}


@router.get("/status")
def research_status():
    if not _sessions:
        return {
            "generating": False,
            "error": None,
            "result": None,
            "progress": {"step": "", "step_num": 0, "total_steps": 6},
        }
    latest_id = list(_sessions.keys())[-1]
    s = _sessions[latest_id]
    return {
        "generating": s["generating"],
        "error": s["error"],
        "result": s["result"],
        "progress": s["progress"],
        "session_id": latest_id,
    }
