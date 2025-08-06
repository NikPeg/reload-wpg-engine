"""
Player model
"""

from enum import Enum
from typing import List, Optional

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from wpg_engine.models.base import Base


class PlayerRole(str, Enum):
    """Player role enumeration"""

    ADMIN = "admin"
    PLAYER = "player"
    OBSERVER = "observer"


class Player(Base):
    """Player model"""

    __tablename__ = "players"

    # External service IDs
    telegram_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    vk_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    # Player info
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[PlayerRole] = mapped_column(String(20), default=PlayerRole.PLAYER)

    # Foreign keys
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), nullable=False)
    country_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("countries.id"), nullable=True
    )

    # Relationships
    game: Mapped["Game"] = relationship("Game", back_populates="players")
    country: Mapped[Optional["Country"]] = relationship(
        "Country", back_populates="players"
    )
    posts: Mapped[List["Post"]] = relationship("Post", back_populates="author")
    verdicts: Mapped[List["Verdict"]] = relationship("Verdict", back_populates="admin")

    def __repr__(self) -> str:
        return f"<Player(id={self.id}, username='{self.username}', role='{self.role}')>"
