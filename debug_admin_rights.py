#!/usr/bin/env python3
"""
Debug script to check admin rights
"""

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from wpg_engine.models.base import Base
from wpg_engine.core.engine import GameEngine
from wpg_engine.core.admin_utils import determine_player_role, is_admin
from wpg_engine.models import Player, Game, GameStatus
from wpg_engine.config.settings import settings


async def debug_admin_rights():
    """Debug admin rights for specific user"""
    
    user_telegram_id = 241248104  # Your Telegram ID
    
    print(f"🔍 Debugging admin rights for Telegram ID: {user_telegram_id}")
    print(f"📋 Admin IDs from settings: {settings.telegram.admin_ids}")
    
    # Check if user is in admin list
    if user_telegram_id in settings.telegram.admin_ids:
        print("✅ User is in admin list from environment")
    else:
        print("❌ User is NOT in admin list from environment")
    
    # Connect to database (convert sqlite URL to async)
    db_url = settings.database.url
    if db_url.startswith("sqlite:///"):
        db_url = db_url.replace("sqlite:///", "sqlite+aiosqlite:///")
    engine = create_async_engine(db_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        game_engine = GameEngine(session)
        
        # Check if user exists in database
        result = await session.execute(
            select(Player).where(Player.telegram_id == user_telegram_id)
        )
        player = result.scalar_one_or_none()
        
        if player:
            print(f"✅ Player found in database:")
            print(f"   - ID: {player.id}")
            print(f"   - Username: {player.username}")
            print(f"   - Display Name: {player.display_name}")
            print(f"   - Role: {player.role}")
            print(f"   - Game ID: {player.game_id}")
            
            # Check admin status
            admin_status = await is_admin(user_telegram_id, session)
            print(f"   - Is Admin: {admin_status}")
            
            if player.game:
                print(f"   - Game: {player.game.name}")
                print(f"   - Game Status: {player.game.status}")
        else:
            print("❌ Player NOT found in database")
            print("   You need to register first with /register command")
            
            # Check what role would be assigned
            result = await session.execute(select(Game).where(Game.status == GameStatus.ACTIVE))
            active_game = result.scalar_one_or_none()
            
            if active_game:
                role = await determine_player_role(user_telegram_id, active_game.id, session)
                print(f"   - Role that would be assigned: {role}")
            else:
                print("   - No active game found")
        
        # Show all players in database
        result = await session.execute(select(Player))
        all_players = result.scalars().all()
        
        print(f"\n📊 All players in database ({len(all_players)}):")
        for p in all_players:
            print(f"   - {p.display_name} (ID: {p.telegram_id}, Role: {p.role})")


if __name__ == "__main__":
    asyncio.run(debug_admin_rights())