"""
Post model for player actions
"""

from typing import Optional

from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from wpg_engine.models.base import Base


class Post(Base):
    """Post model for player actions and communications"""

    __tablename__ = "posts"

    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Foreign keys
    author_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), nullable=False)

    # Optional reply to another post
    reply_to_id: Mapped[int | None] = mapped_column(
        ForeignKey("posts.id"), nullable=True
    )

    # Relationships
    author: Mapped["Player"] = relationship("Player", back_populates="posts")
    game: Mapped["Game"] = relationship("Game", back_populates="posts")

    # Self-referential relationship for replies
    reply_to: Mapped[Optional["Post"]] = relationship(
        "Post", remote_side="Post.id", back_populates="replies"
    )
    replies: Mapped[list["Post"]] = relationship("Post", back_populates="reply_to")

    # Verdicts for this post
    verdicts: Mapped[list["Verdict"]] = relationship(
        "Verdict", back_populates="post", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<Post(id={self.id}, author_id={self.author_id}, game_id={self.game_id})>"
        )
