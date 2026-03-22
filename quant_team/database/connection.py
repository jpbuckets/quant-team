"""Database connection and session management."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from .models import Base, PortfolioState

_engine = None
_SessionLocal = None


def get_engine(db_path: str = "data/dashboard.db"):
    global _engine
    if _engine is None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(f"sqlite:///{db_path}", echo=False)
    return _engine


def get_session_factory(db_path: str = "data/dashboard.db") -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        engine = get_engine(db_path)
        _SessionLocal = sessionmaker(bind=engine)
    return _SessionLocal


def get_db(db_path: str = "data/dashboard.db") -> Session:
    """Get a database session."""
    factory = get_session_factory(db_path)
    return factory()


def init_db(db_path: str = "data/dashboard.db") -> None:
    """Create all tables and initialize portfolio state."""
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)

    session = get_db(db_path)
    try:
        state = session.query(PortfolioState).get(1)
        if state is None:
            state = PortfolioState(
                id=1,
                cash=10000.0,
                initial_capital=10000.0,
                peak_value=10000.0,
                total_realized_pnl=0.0,
            )
            session.add(state)
            session.commit()
    finally:
        session.close()
