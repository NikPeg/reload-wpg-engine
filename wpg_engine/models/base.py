"""
Base database model and database setup
"""

import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime

from sqlalchemy import DateTime, event, func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.pool import NullPool

from wpg_engine.config.settings import settings


# Register datetime adapter for SQLite (Python 3.12+ requirement)
def adapt_datetime_iso(val):
    """Adapt datetime.datetime to timezone-naive ISO 8601 date."""
    return val.isoformat()


sqlite3.register_adapter(datetime, adapt_datetime_iso)


class Base(DeclarativeBase):
    """Base model for all database entities"""

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# Database engine with proper async configuration
# Use NullPool to avoid connection pool issues with SQLite
# Each request gets a fresh connection that's properly closed
engine = create_async_engine(
    settings.database.url.replace("sqlite://", "sqlite+aiosqlite://"),
    echo=settings.database.echo,
    poolclass=NullPool,  # No connection pooling - fresh connection each time
    connect_args={
        "check_same_thread": False,  # Allow sharing connection across threads
        "timeout": 60,  # Increased timeout for busy database operations
    },
)


# Enable WAL mode and optimize SQLite for concurrent access
@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """Set SQLite pragmas for better concurrent performance"""
    cursor = dbapi_conn.cursor()
    # Enable WAL mode for better concurrent access
    cursor.execute("PRAGMA journal_mode=WAL")
    # Reduce synchronous commits for better performance (still safe with WAL)
    cursor.execute("PRAGMA synchronous=NORMAL")
    # Increase cache size to 64MB
    cursor.execute("PRAGMA cache_size=-64000")
    # Enable foreign keys
    cursor.execute("PRAGMA foreign_keys=ON")
    # Set busy timeout to 60 seconds
    cursor.execute("PRAGMA busy_timeout=60000")
    cursor.close()


AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,  # Manual flush control for better performance
)


@asynccontextmanager
async def get_db():
    """
    Get database session as async context manager.

    Usage:
        async with get_db() as db:
            # Use db here
            await db.execute(...)
            await db.commit()
    """
    session = AsyncSessionLocal()
    try:
        yield session
        # Auto-commit if there were no exceptions
        if session.in_transaction():
            await session.commit()
    except Exception:
        # Rollback on any exception
        if session.in_transaction():
            await session.rollback()
        raise
    finally:
        await session.close()


async def init_db() -> None:
    """Initialize database tables"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
