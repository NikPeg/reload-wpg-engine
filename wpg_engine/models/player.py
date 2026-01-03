"""
Player model
"""

from enum import Enum
from typing import Optional

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
    telegram_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, unique=True
    )
    vk_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # Player info
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[PlayerRole] = mapped_column(String(20), default=PlayerRole.PLAYER)

    # Foreign keys
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), nullable=False)
    country_id: Mapped[int | None] = mapped_column(
        ForeignKey("countries.id"), nullable=True, unique=True
    )

    # Relationships
    game: Mapped["Game"] = relationship("Game", back_populates="players")
    country: Mapped[Optional["Country"]] = relationship(
        "Country", back_populates="players"
    )
    posts: Mapped[list["Post"]] = relationship("Post", back_populates="author")
    verdicts: Mapped[list["Verdict"]] = relationship("Verdict", back_populates="admin")
    messages: Mapped[list["Message"]] = relationship("Message", back_populates="player")

    def __repr__(self) -> str:
        return f"<Player(id={self.id}, username='{self.username}', role='{self.role}')>"
