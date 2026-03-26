"""Agent session API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ...database.connection import get_db
from ...database.models import AgentSession

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.get("")
def list_sessions(limit: int = 20, team_id: str | None = None):
    db = get_db()
    try:
        query = db.query(AgentSession).order_by(AgentSession.timestamp.desc())
        if team_id is not None:
            query = query.filter(AgentSession.team_id == team_id)
        sessions = query.limit(limit).all()
        return [
            {
                "id": s.id,
                "timestamp": s.timestamp.isoformat() if s.timestamp else "",
                "tickers_analyzed": s.tickers_analyzed,
                "recommendations_count": s.recommendations_count,
            }
            for s in sessions
        ]
    finally:
        db.close()


@router.get("/latest")
def get_latest_session(team_id: str | None = None):
    db = get_db()
    try:
        query = db.query(AgentSession).order_by(AgentSession.timestamp.desc())
        if team_id is not None:
            query = query.filter(AgentSession.team_id == team_id)
        session = query.first()
        if session is None:
            raise HTTPException(status_code=404, detail="No sessions found")
        return {
            "id": session.id,
            "timestamp": session.timestamp.isoformat() if session.timestamp else "",
            "tickers_analyzed": session.tickers_analyzed,
            "macro_analysis": session.macro_analysis,
            "quant_analysis": session.quant_analysis,
            "risk_analysis": session.risk_analysis,
            "cio_decision": session.cio_decision,
            "recommendations_count": session.recommendations_count,
        }
    finally:
        db.close()


@router.get("/{session_id}")
def get_session(session_id: int):
    db = get_db()
    try:
        session = db.query(AgentSession).get(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        return {
            "id": session.id,
            "timestamp": session.timestamp.isoformat() if session.timestamp else "",
            "tickers_analyzed": session.tickers_analyzed,
            "market_context_summary": session.market_context_summary,
            "macro_analysis": session.macro_analysis,
            "quant_analysis": session.quant_analysis,
            "risk_analysis": session.risk_analysis,
            "cio_decision": session.cio_decision,
            "recommendations_count": session.recommendations_count,
        }
    finally:
        db.close()
