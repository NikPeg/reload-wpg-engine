"""
Message model for player-admin communication
"""

from typing import Optional

from sqlalchemy import BigInteger, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from wpg_engine.models.base import Base


class Message(Base):
    """Message model for player-admin communication"""

    __tablename__ = "messages"

    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Telegram message ID for reply functionality (original player message)
    telegram_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # Admin's telegram message ID (when message is forwarded to admin)
    admin_telegram_message_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )

    # Foreign keys
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), nullable=False)

    # Optional reply to another message
    reply_to_id: Mapped[int | None] = mapped_column(
        ForeignKey("messages.id"), nullable=True
    )

    # Is this message from admin (reply) or from player
    is_admin_reply: Mapped[bool] = mapped_column(default=False)

    # Relationships
    player: Mapped["Player"] = relationship("Player", back_populates="messages")
    game: Mapped["Game"] = relationship("Game", back_populates="messages")

    # Self-referential relationship for replies
    reply_to: Mapped[Optional["Message"]] = relationship(
        "Message", remote_side="Message.id", back_populates="replies"
    )
    replies: Mapped[list["Message"]] = relationship(
        "Message", back_populates="reply_to"
    )

    def __repr__(self) -> str:
        return (
            f"<Message(id={self.id}, player_id={self.player_id}, "
            f"is_admin_reply={self.is_admin_reply})>"
        )
