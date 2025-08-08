"""
Game model
"""

from enum import Enum

from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from wpg_engine.models.base import Base


class GameStatus(str, Enum):
    """Game status enumeration"""

    CREATED = "created"
    ACTIVE = "active"
    PAUSED = "paused"
    FINISHED = "finished"


class Game(Base):
    """Game model"""

    __tablename__ = "games"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[GameStatus] = mapped_column(String(20), default=GameStatus.CREATED)
    setting: Mapped[str] = mapped_column(String(255), default="Современность")
    settings: Mapped[dict] = mapped_column(JSON, default=dict)

    # Game configuration
    max_players: Mapped[int] = mapped_column(default=10)
    years_per_day: Mapped[int] = mapped_column(default=1)  # Сколько игровых лет проходит за один реальный день
    max_points: Mapped[int] = mapped_column(default=30)  # Максимальная сумма очков для аспектов страны
    max_population: Mapped[int] = mapped_column(default=10_000_000)  # Максимальное население страны

    # Relationships
    countries: Mapped[list["Country"]] = relationship("Country", back_populates="game", cascade="all, delete-orphan")
    players: Mapped[list["Player"]] = relationship("Player", back_populates="game", cascade="all, delete-orphan")
    posts: Mapped[list["Post"]] = relationship("Post", back_populates="game", cascade="all, delete-orphan")
    messages: Mapped[list["Message"]] = relationship("Message", back_populates="game", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Game(id={self.id}, name='{self.name}', status='{self.status}')>"
