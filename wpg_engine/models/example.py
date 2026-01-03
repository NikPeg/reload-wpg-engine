"""
Example message model
"""

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from wpg_engine.models.base import Base


class Example(Base):
    """Example message for players"""

    __tablename__ = "examples"

    # Text of the example
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Game this example belongs to
    game_id: Mapped[int] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"), nullable=False
    )

    # Admin who created this example
    created_by_id: Mapped[int] = mapped_column(
        ForeignKey("players.id", ondelete="CASCADE"), nullable=False
    )

    # Relationships
    game: Mapped["Game"] = relationship("Game", back_populates="examples")
    created_by: Mapped["Player"] = relationship("Player", foreign_keys=[created_by_id])

    def __repr__(self) -> str:
        return f"<Example(id={self.id}, game_id={self.game_id}, content='{self.content[:50]}...')>"

