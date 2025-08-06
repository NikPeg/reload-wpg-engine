"""
Game model
"""

from enum import Enum
from typing import List, Optional
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
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[GameStatus] = mapped_column(String(20), default=GameStatus.CREATED)
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # Game configuration
    max_players: Mapped[int] = mapped_column(default=10)
    turn_duration_hours: Mapped[int] = mapped_column(default=24)
    
    # Relationships
    countries: Mapped[List["Country"]] = relationship(
        "Country", 
        back_populates="game",
        cascade="all, delete-orphan"
    )
    players: Mapped[List["Player"]] = relationship(
        "Player", 
        back_populates="game",
        cascade="all, delete-orphan"
    )
    posts: Mapped[List["Post"]] = relationship(
        "Post", 
        back_populates="game",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<Game(id={self.id}, name='{self.name}', status='{self.status}')>"