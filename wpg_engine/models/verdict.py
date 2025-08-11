"""
Verdict model for admin decisions
"""

from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from wpg_engine.models.base import Base


class Verdict(Base):
    """Verdict model for admin decisions on posts"""

    __tablename__ = "verdicts"

    result: Mapped[str] = mapped_column(Text, nullable=False)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Foreign keys
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"), nullable=False)
    admin_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)

    # Relationships
    post: Mapped["Post"] = relationship("Post", back_populates="verdicts")
    admin: Mapped["Player"] = relationship("Player", back_populates="verdicts")

    def __repr__(self) -> str:
        return f"<Verdict(id={self.id}, post_id={self.post_id}, admin_id={self.admin_id})>"
