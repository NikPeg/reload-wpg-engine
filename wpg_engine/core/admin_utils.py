"""
Admin utilities for role management
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wpg_engine.config.settings import settings
from wpg_engine.models import Player, PlayerRole


async def determine_player_role(telegram_id: int, game_id: int, db: AsyncSession) -> PlayerRole:
    """
    Determine player role based on:
    1. Admin IDs from environment variables
    2. Auto-assign admin to first player in game
    """

    # Check if user is in admin list from .env
    if telegram_id in settings.telegram.admin_ids:
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


async def is_admin(telegram_id: int, db: AsyncSession) -> bool:
    """Check if user is admin"""
    result = await db.execute(select(Player).where(Player.telegram_id == telegram_id))
    player = result.scalar_one_or_none()

    return player is not None and player.role == PlayerRole.ADMIN
