"""
Admin utilities for role management
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wpg_engine.config.settings import settings
from wpg_engine.models import Player, PlayerRole


def is_admin_from_env(telegram_id: int, chat_id: int | None = None) -> bool:
    """
    Check if user/chat is admin based on environment variables.

    Args:
        telegram_id: User's Telegram ID
        chat_id: Chat ID (if message is from a chat/group)

    Returns:
        True if user or chat is admin
    """
    if not settings.telegram.admin_id:
        return False

    # If admin_id is negative (chat), check if message is from that chat
    if settings.telegram.is_admin_chat():
        return chat_id is not None and chat_id == settings.telegram.admin_id

    # If admin_id is positive (user), check if user matches
    if settings.telegram.is_admin_user():
        return telegram_id == settings.telegram.admin_id

    return False


async def determine_player_role(
    telegram_id: int, game_id: int, db: AsyncSession, chat_id: int | None = None
) -> PlayerRole:
    """
    Determine player role based on:
    1. Admin IDs from environment variables (user or chat)
    2. Auto-assign admin to first player in game

    Args:
        telegram_id: User's Telegram ID
        game_id: Game ID
        db: Database session
        chat_id: Chat ID (if message is from a chat/group)
    """

    # Check if user is admin from .env (supports both user and chat admin)
    if is_admin_from_env(telegram_id, chat_id):
        return PlayerRole.ADMIN

    # Check if this is the first player in the game
    result = await db.execute(select(Player).where(Player.game_id == game_id))
    existing_players = result.scalars().all()

    # If no players exist, make this user admin
    if not existing_players:
        return PlayerRole.ADMIN

    # Check if there are any admins in the game
    admins = [p for p in existing_players if p.role == PlayerRole.ADMIN]
    if not admins:
        return PlayerRole.ADMIN

    # Default role is player
    return PlayerRole.PLAYER


async def is_admin(
    telegram_id: int, db: AsyncSession, chat_id: int | None = None
) -> bool:
    """
    Check if user is admin.

    Args:
        telegram_id: User's Telegram ID
        db: Database session
        chat_id: Chat ID (if message is from a chat/group)

    Returns:
        True if user is admin (either from env or from database)
    """
    # First check environment variables (for admin user or admin chat)
    if is_admin_from_env(telegram_id, chat_id):
        return True

    # Then check database
    result = await db.execute(
        select(Player).where(Player.telegram_id == telegram_id).limit(1)
    )
    player = result.scalar_one_or_none()

    return player is not None and player.role == PlayerRole.ADMIN
