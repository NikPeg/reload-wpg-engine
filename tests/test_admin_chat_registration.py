#!/usr/bin/env python3
"""
Test script for admin chat auto-registration
"""

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from wpg_engine.adapters.telegram.handlers.common import start_command
from wpg_engine.core.engine import GameEngine
from wpg_engine.models import Player, PlayerRole
from wpg_engine.models.base import Base


async def test_admin_chat_registration():
    """Test that admins from admin chat are automatically registered"""

    # Create test database
    engine = create_async_engine("sqlite+aiosqlite:///./test_admin_chat.db", echo=False)

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
            description="Test game for admin chat registration",
            setting="Древний мир",
            max_players=20,
            years_per_day=10,
            max_points=30,
            max_population=10_000_000,
        )

        # Start the game
        await game_engine.start_game(game.id)

        print(f"✅ Created game: {game.name} (ID: {game.id})")

        # Create first admin
        admin1 = await game_engine.create_player(
            game_id=game.id,
            telegram_id=111111111,
            username="admin1",
            display_name="First Admin",
            role=PlayerRole.ADMIN,
        )
        print(f"✅ Created first admin: {admin1.display_name}")

        # Test: Second admin from admin chat should be auto-registered
        print("\n🧪 Test: Second admin from admin chat auto-registration")

        # Mock message from second admin in admin chat
        mock_message = MagicMock()
        mock_message.from_user.id = 222222222  # Different user ID
        mock_message.from_user.username = "admin2"
        mock_message.from_user.full_name = "Second Admin"
        mock_message.chat.id = -1001234567890  # Admin chat ID
        mock_message.answer = AsyncMock()

        # Patch settings to simulate admin chat
        with patch(
            "wpg_engine.adapters.telegram.handlers.common.is_admin"
        ) as mock_is_admin:
            # Admin from admin chat
            mock_is_admin.return_value = True

            # Patch get_db to return our session
            async def mock_get_db():
                yield session

            with patch(
                "wpg_engine.adapters.telegram.handlers.common.get_db", mock_get_db
            ):
                # Call start_command
                await start_command(mock_message)

        # Check that the admin was auto-registered
        from sqlalchemy import select

        result = await session.execute(
            select(Player).where(Player.telegram_id == 222222222)
        )
        admin2 = result.scalar_one_or_none()

        # Assertions
        assert admin2 is not None, "Second admin should be registered in database"
        assert admin2.role == PlayerRole.ADMIN, "Second admin should have ADMIN role"
        assert admin2.username == "admin2", "Username should match"
        assert admin2.display_name == "Second Admin", "Display name should match"
        assert admin2.game_id == game.id, "Admin should be in the same game"
        assert admin2.country_id is None, "Admin should not have a country"

        print(
            f"✅ Second admin auto-registered: {admin2.display_name} (role: {admin2.role})"
        )

        # Verify that the admin panel message was sent
        assert mock_message.answer.called, "Admin panel message should be sent"
        sent_message = mock_message.answer.call_args[0][0]
        assert "⚙️" in sent_message, "Should show admin panel"
        assert "Панель администратора" in sent_message, "Should show admin panel title"

        print("✅ Admin panel message verified")

        # Test: All admins from admin chat get the same admin panel
        print("\n🧪 Test: All admins get the same admin panel")

        # Create mock for first admin
        mock_message1 = MagicMock()
        mock_message1.from_user.id = 111111111
        mock_message1.from_user.username = "admin1"
        mock_message1.from_user.full_name = "First Admin"
        mock_message1.chat.id = -1001234567890
        mock_message1.answer = AsyncMock()

        with patch(
            "wpg_engine.adapters.telegram.handlers.common.is_admin"
        ) as mock_is_admin:
            mock_is_admin.return_value = True

            async def mock_get_db():
                yield session

            with patch(
                "wpg_engine.adapters.telegram.handlers.common.get_db", mock_get_db
            ):
                await start_command(mock_message1)

        # Both admins should get admin panel
        sent_message1 = mock_message1.answer.call_args[0][0]
        assert "⚙️" in sent_message1, "First admin should get admin panel"
        assert "Панель администратора" in sent_message1, (
            "First admin should get admin panel title"
        )

        print("✅ Both admins receive admin panel")

        print("\n✅ All tests passed!")
        print("\n📋 Admin chat registration features:")
        print("1. ✅ First admin creates game and is registered")
        print("2. ✅ Second admin from admin chat is auto-registered")
        print("3. ✅ Both admins have ADMIN role in database")
        print("4. ✅ Both admins receive '⚙️ Панель администратора' message")
        print("5. ✅ Admins are registered without countries")
        print("6. ✅ No more '🎯 Добро пожаловать, Администратор!' message")

    # Clean up
    await engine.dispose()
    os.remove("test_admin_chat.db")
    print("\n🧹 Cleaned up test database")


if __name__ == "__main__":
    asyncio.run(test_admin_chat_registration())
