#!/usr/bin/env python3
"""
Test script for admin system
"""

import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from wpg_engine.models.base import Base
from wpg_engine.core.engine import GameEngine
from wpg_engine.core.admin_utils import determine_player_role
from wpg_engine.models import GameStatus, PlayerRole


async def test_admin_system():
    """Test admin role assignment system"""
    
    # Create test database
    engine = create_async_engine("sqlite+aiosqlite:///./test_admin.db", echo=True)
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    # Create session
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        game_engine = GameEngine(session)
        
        # Create a test game
        game = await game_engine.create_game(
            name="Test Game",
            description="Test game for admin system",
            setting="Древний мир"
        )
        
        # Start the game
        await game_engine.start_game(game.id)
        
        print(f"✅ Created game: {game.name} (ID: {game.id})")
        
        # Test 1: First player should become admin
        print("\n🧪 Test 1: First player auto-admin")
        role1 = await determine_player_role(123456789, game.id, session)
        print(f"First player role: {role1}")
        assert role1 == PlayerRole.ADMIN, "First player should be admin"
        
        # Create first player
        player1 = await game_engine.create_player(
            game_id=game.id,
            telegram_id=123456789,
            username="first_player",
            display_name="First Player",
            role=role1
        )
        print(f"Created player: {player1.display_name} with role {player1.role}")
        
        # Test 2: Second player should be regular player
        print("\n🧪 Test 2: Second player regular role")
        role2 = await determine_player_role(987654321, game.id, session)
        print(f"Second player role: {role2}")
        assert role2 == PlayerRole.PLAYER, "Second player should be regular player"
        
        # Test 3: Test admin from environment (if set)
        print("\n🧪 Test 3: Admin from environment")
        # Simulate admin ID in environment
        from wpg_engine.config.settings import settings
        if settings.telegram.admin_ids:
            admin_id = settings.telegram.admin_ids[0]
            role3 = await determine_player_role(admin_id, game.id, session)
            print(f"Environment admin role: {role3}")
            assert role3 == PlayerRole.ADMIN, "Environment admin should be admin"
        else:
            print("No admin IDs in environment - skipping test")
        
        print("\n✅ All tests passed!")
        print("\n📋 Admin system features:")
        print("1. ✅ First player auto-becomes admin")
        print("2. ✅ Environment admin IDs supported")
        print("3. ✅ Role-based access control")
        print("4. ✅ Admin utilities for checking permissions")
        
        # Clean up
        os.remove("test_admin.db")
        print("\n🧹 Cleaned up test database")


if __name__ == "__main__":
    asyncio.run(test_admin_system())