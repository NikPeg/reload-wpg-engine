"""
Base database model and database setup
"""

from collections.abc import AsyncGenerator
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.pool import StaticPool

from wpg_engine.config.settings import settings


class Base(DeclarativeBase):
    """Base model for all database entities"""

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# Database engine and session factory
# Use StaticPool for SQLite to reuse connections and improve performance
engine = create_async_engine(
    settings.database.url.replace("sqlite://", "sqlite+aiosqlite://"),
    echo=settings.database.echo,
    poolclass=StaticPool,  # Reuse single connection for SQLite (thread-safe)
    connect_args={
        "check_same_thread": False,  # Allow sharing connection across threads
        "timeout": 30,  # Increase timeout for busy database
    },
)

AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
