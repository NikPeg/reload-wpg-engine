"""
Admin utilities for role management
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from wpg_engine.config.settings import settings
from wpg_engine.models import Player, PlayerRole


def is_admin_chat(chat_id: int | None = None) -> bool:
    """
    Check if chat is admin chat based on environment variables.

    Args:
        chat_id: Chat ID (if message is from a chat/group)

    Returns:
        True if chat is admin chat
    """
    if not settings.telegram.admin_id or chat_id is None:
        return False

    # If admin_id is negative (chat), check if message is from that chat
    if settings.telegram.is_admin_chat():
        return chat_id == settings.telegram.admin_id

    return False


async def determine_player_role(
    telegram_id: int, game_id: int, db: AsyncSession, chat_id: int | None = None
) -> PlayerRole:
    """
    Determine player role based on:
    1. Check if message is from admin chat (TG_ADMIN_ID)
    2. Auto-assign admin to first player in game

    Args:
        telegram_id: User's Telegram ID
        game_id: Game ID
        db: Database session
        chat_id: Chat ID (if message is from a chat/group)
    """

    # Check if message is from admin chat
    if is_admin_chat(chat_id):
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
    Check if user is admin by checking:
    1. Admin chat (if message is from admin chat)
    2. Database role

    Args:
        telegram_id: User's Telegram ID
        db: Database session
        chat_id: Chat ID (if message is from a chat/group)

    Returns:
        True if user is admin (from admin chat or has ADMIN role in database)
    """
    # Check if message is from admin chat
    if is_admin_chat(chat_id):
        return True

    # Check database role
    result = await db.execute(
        select(Player).where(Player.telegram_id == telegram_id).limit(1)
    )
    player = result.scalar_one_or_none()

    return player is not None and player.role == PlayerRole.ADMIN


async def get_admin_player(telegram_id: int, db: AsyncSession) -> Player | None:
    """
    Get admin player for admin operations.

    Args:
        telegram_id: User's Telegram ID
        db: Database session

    Returns:
        Player object with ADMIN role (with preloaded game and country) or None
    """
    result = await db.execute(
        select(Player)
        .options(selectinload(Player.game), selectinload(Player.country))
        .where(Player.telegram_id == telegram_id)
        .where(Player.role == PlayerRole.ADMIN)
        .limit(1)
    )
    return result.scalar_one_or_none()
