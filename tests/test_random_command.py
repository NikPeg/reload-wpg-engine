#!/usr/bin/env python3
"""
Test script for /random command
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from aiogram.types import Message, User
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from wpg_engine.adapters.telegram.handlers.admin import random_command
from wpg_engine.core.engine import GameEngine
from wpg_engine.models import PlayerRole
from wpg_engine.models.base import Base


@pytest.fixture
async def test_db():
    """Create test database"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_random_command_returns_percentage(test_db: AsyncSession):
    """Test that /random command returns a percentage between 0 and 100"""
    game_engine = GameEngine(test_db)

    # Create a test game
    game = await game_engine.create_game(
        name="Test Game",
        description="Test game for random command",
        setting="Тестовый мир",
    )

    # Create admin player
    admin_player = await game_engine.create_player(
        game_id=game.id,
        telegram_id=123456789,
        username="admin_user",
        display_name="Admin User",
        role=PlayerRole.ADMIN,
    )

    # Create mock message
    class MockMessage:
        def __init__(self):
            self.from_user = User(
                id=admin_player.telegram_id,
                is_bot=False,
                first_name="Admin",
                username="admin_user",
            )
            self.chat = type("Chat", (), {"id": admin_player.telegram_id})()
            self.text = "/random"
            self._answer_text = None

        async def answer(self, text: str, **kwargs):
            self._answer_text = text

    # Mock is_admin to return True for our test admin
    with patch("wpg_engine.adapters.telegram.handlers.admin.is_admin") as mock_is_admin:
        mock_is_admin.return_value = True

        # Test multiple calls to ensure random percentage generation
        results = []
        for _ in range(10):
            mock_message = MockMessage()
            await random_command(mock_message)

            # Verify the response
            assert mock_message._answer_text is not None
            assert mock_message._answer_text.startswith("🎲 ")
            assert mock_message._answer_text.endswith("%")

            # Extract percentage value
            percentage_str = mock_message._answer_text.replace("🎲 ", "").replace("%", "")
            percentage = int(percentage_str)

            # Verify percentage is in valid range
            assert 0 <= percentage <= 100
            results.append(percentage)

        # Verify that we got some variation (not all same values)
        # This is a probabilistic test, but with 10 values, we should have at least 2 different values
        assert len(set(results)) >= 2 or len(results) == 1, (
            "Random command should produce varied results"
        )

        print(f"✅ Random command test passed! Generated values: {results}")


@pytest.mark.asyncio
async def test_random_command_non_admin_denied(test_db: AsyncSession):
    """Test that non-admin users cannot use /random command"""
    game_engine = GameEngine(test_db)

    # Create a test game
    game = await game_engine.create_game(
        name="Test Game",
        description="Test game for random command",
        setting="Тестовый мир",
    )

    # Create regular player (not admin)
    player = await game_engine.create_player(
        game_id=game.id,
        telegram_id=987654321,
        username="regular_user",
        display_name="Regular User",
        role=PlayerRole.PLAYER,
    )

    # Create mock message
    class MockMessage:
        def __init__(self):
            self.from_user = User(
                id=player.telegram_id,
                is_bot=False,
                first_name="User",
                username="regular_user",
            )
            self.chat = type("Chat", (), {"id": player.telegram_id})()
            self.text = "/random"
            self._answer_text = None

        async def answer(self, text: str, **kwargs):
            self._answer_text = text

    # Mock is_admin to return False for regular user
    with patch("wpg_engine.adapters.telegram.handlers.admin.is_admin") as mock_is_admin:
        mock_is_admin.return_value = False

        mock_message = MockMessage()
        await random_command(mock_message)

        # Verify that access is denied
        assert mock_message._answer_text is not None
        assert "❌" in mock_message._answer_text
        assert "прав администратора" in mock_message._answer_text

        print("✅ Non-admin access denied test passed!")


if __name__ == "__main__":
    asyncio.run(test_random_command_returns_percentage())
    asyncio.run(test_random_command_non_admin_denied())


