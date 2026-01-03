"""
Example country model - countries that serve as examples for new players
"""

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from wpg_engine.models.base import Base


class Example(Base):
    """Example country for new players to see before registration"""

    __tablename__ = "examples"

    # Country that is an example
    country_id: Mapped[int] = mapped_column(
        ForeignKey("countries.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    # Game this example belongs to
    game_id: Mapped[int] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"), nullable=False
    )

    # Admin who created this example
    created_by_id: Mapped[int] = mapped_column(
        ForeignKey("players.id", ondelete="CASCADE"), nullable=False
    )

    # Relationships
    country: Mapped["Country"] = relationship("Country", back_populates="example")
    game: Mapped["Game"] = relationship("Game", back_populates="examples")
    created_by: Mapped["Player"] = relationship("Player", foreign_keys=[created_by_id])

    def __repr__(self) -> str:
        return f"<Example(id={self.id}, game_id={self.game_id}, country_id={self.country_id})>"
