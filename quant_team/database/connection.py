"""Database connection and session management."""

from __future__ import annotations

import os
import logging
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, Session

from .models import Base, PortfolioState

logger = logging.getLogger("quant_team")

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
    """Add team_id column to existing SQLite tables if missing. Safe and idempotent."""
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


def get_engine():
    """Get or create the database engine. Uses DATABASE_URL if set, else SQLite."""
    global _engine
    if _engine is None:
        database_url = os.environ.get("DATABASE_URL")
        if database_url:
            # Railway uses postgres:// but SQLAlchemy 2.0 requires postgresql://
            if database_url.startswith("postgres://"):
                database_url = database_url.replace("postgres://", "postgresql://", 1)
            _engine = create_engine(database_url, pool_pre_ping=True, pool_size=5)
            logger.info("Using PostgreSQL database")
        else:
            db_path = "data/dashboard.db"
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            _engine = create_engine(f"sqlite:///{db_path}", echo=False)
            logger.info("Using SQLite database")
    return _engine


def get_session_factory() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        engine = get_engine()
        _SessionLocal = sessionmaker(bind=engine)
    return _SessionLocal


def get_db() -> Session:
    """Get a database session."""
    factory = get_session_factory()
    return factory()


def init_db() -> None:
    """Create all tables, run migrations, and seed defaults."""
    engine = get_engine()

    # SQLite-specific setup
    if engine.dialect.name == "sqlite":
        with engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL"))
            conn.commit()

    Base.metadata.create_all(engine)

    # SQLite migration for existing databases (PostgreSQL gets clean schema)
    if engine.dialect.name == "sqlite":
        _maybe_add_team_id(engine)

    # Initialize default portfolio state for 'quant' team
    session = get_db()
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
