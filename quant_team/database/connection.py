"""Database connection and session management."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, Session

from .models import Base, PortfolioState

_engine = None
_SessionLocal = None

_TEAM_ID_TABLES = [
    "recommendations",
    "portfolio_positions",
    "portfolio_snapshots",
    "trade_records",
    "agent_sessions",
    "portfolio_state",
]


def _maybe_add_team_id(engine) -> None:
    """Add team_id column to existing tables if missing. Safe and idempotent."""
    inspector = inspect(engine)
    for table_name in _TEAM_ID_TABLES:
        try:
            columns = [c["name"] for c in inspector.get_columns(table_name)]
        except Exception:
            continue  # table doesn't exist yet, create_all will handle it
        if "team_id" not in columns:
            with engine.connect() as conn:
                conn.execute(text(
                    f"ALTER TABLE {table_name} ADD COLUMN team_id TEXT NOT NULL DEFAULT 'quant'"
                ))
                conn.commit()


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
    """Create all tables, enable WAL mode, and run migrations."""
    engine = get_engine(db_path)

    # Enable WAL mode for concurrent access
    with engine.connect() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL"))
        conn.commit()

    Base.metadata.create_all(engine)

    # Migrate existing tables (adds team_id if missing)
    _maybe_add_team_id(engine)

    # Initialize default portfolio state for 'quant' team
    session = get_db(db_path)
    try:
        state = session.query(PortfolioState).filter_by(team_id="quant").first()
        if state is None:
            state = PortfolioState(
                cash=10000.0,
                initial_capital=10000.0,
                peak_value=10000.0,
                total_realized_pnl=0.0,
                team_id="quant",
            )
            session.add(state)
            session.commit()
    finally:
        session.close()
