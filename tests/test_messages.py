"""
Tests for the message system
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from wpg_engine.core.engine import GameEngine
from wpg_engine.models import Player, PlayerRole


@pytest.fixture
async def game_engine(db_session: AsyncSession):
    """Create a game engine instance"""
    return GameEngine(db_session)


@pytest.fixture
async def test_game(game_engine: GameEngine):
    """Create a test game"""
    return await game_engine.create_game(
        name="Test Game",
        description="Test game for message system",
        setting="Modern",
        max_players=5,
    )


@pytest.fixture
async def admin_player(game_engine: GameEngine, test_game):
    """Create an admin player"""
    return await game_engine.create_player(
        game_id=test_game.id,
        telegram_id=111111111,
        username="admin",
        display_name="Test Admin",
        role=PlayerRole.ADMIN,
    )


@pytest.fixture
async def regular_player(game_engine: GameEngine, test_game):
    """Create a regular player"""
    player = await game_engine.create_player(
        game_id=test_game.id,
        telegram_id=222222222,
        username="player",
        display_name="Test Player",
        role=PlayerRole.PLAYER,
    )

    # Create a country for the player
    country = await game_engine.create_country(
        game_id=test_game.id,
        name="Test Kingdom",
        description="A test kingdom",
        capital="Test City",
        population=100000,
    )

    # Assign country to player
    await game_engine.assign_player_to_country(player.id, country.id)

    return player


class TestMessageSystem:
    """Test the message system functionality"""

    async def test_create_message(
        self, game_engine: GameEngine, regular_player: Player, test_game
    ):
        """Test creating a message"""
        message = await game_engine.create_message(
            player_id=regular_player.id,
            game_id=test_game.id,
            content="Test message from player",
            telegram_message_id=12345,
            is_admin_reply=False,
        )

        assert message.id is not None
        assert message.content == "Test message from player"
        assert message.player_id == regular_player.id
        assert message.game_id == test_game.id
        assert message.telegram_message_id == 12345
        assert message.is_admin_reply is False
        assert message.reply_to_id is None

    async def test_create_admin_reply(
        self, game_engine: GameEngine, regular_player: Player, test_game
    ):
        """Test creating an admin reply to a player message"""
        # Create original player message
        original_message = await game_engine.create_message(
            player_id=regular_player.id,
            game_id=test_game.id,
            content="Player question",
            is_admin_reply=False,
        )

        # Create admin reply
        admin_reply = await game_engine.create_message(
            player_id=regular_player.id,  # Still associated with the same player
            game_id=test_game.id,
            content="Admin response",
            reply_to_id=original_message.id,
            is_admin_reply=True,
        )

        assert admin_reply.reply_to_id == original_message.id
        assert admin_reply.is_admin_reply is True
        assert admin_reply.content == "Admin response"

    async def test_get_player_messages(
        self, game_engine: GameEngine, regular_player: Player, test_game
    ):
        """Test retrieving player messages"""
        import asyncio

        # Create multiple messages with small delays to ensure different timestamps
        messages = []
        for i in range(5):
            message = await game_engine.create_message(
                player_id=regular_player.id,
                game_id=test_game.id,
                content=f"Test message {i + 1}",
                is_admin_reply=False,
            )
            messages.append(message)
            await asyncio.sleep(0.01)  # Small delay to ensure different timestamps

        # Get player messages (should return in reverse chronological order)
        retrieved_messages = await game_engine.get_player_messages(
            regular_player.id, limit=10
        )

        assert len(retrieved_messages) == 5
        # Messages should be in reverse chronological order (newest first)
        assert retrieved_messages[0].content == "Test message 5"
        assert retrieved_messages[4].content == "Test message 1"

    async def test_get_player_messages_limit(
        self, game_engine: GameEngine, regular_player: Player, test_game
    ):
        """Test retrieving player messages with limit"""
        import asyncio

        # Create 15 messages with small delays to ensure different timestamps
        for i in range(15):
            await game_engine.create_message(
                player_id=regular_player.id,
                game_id=test_game.id,
                content=f"Message {i + 1}",
                is_admin_reply=False,
            )
            await asyncio.sleep(0.01)  # Small delay to ensure different timestamps

        # Get only last 10 messages
        retrieved_messages = await game_engine.get_player_messages(
            regular_player.id, limit=10
        )

        assert len(retrieved_messages) == 10
        # Should get messages 15, 14, 13, ..., 6
        assert retrieved_messages[0].content == "Message 15"
        assert retrieved_messages[9].content == "Message 6"

    async def test_get_message_by_telegram_id(
        self, game_engine: GameEngine, regular_player: Player, test_game
    ):
        """Test retrieving message by telegram message ID"""
        telegram_msg_id = 98765

        # Create message with specific telegram ID
        message = await game_engine.create_message(
            player_id=regular_player.id,
            game_id=test_game.id,
            content="Message with telegram ID",
            telegram_message_id=telegram_msg_id,
            is_admin_reply=False,
        )

        # Retrieve by telegram ID
        retrieved_message = await game_engine.get_message_by_telegram_id(
            telegram_msg_id
        )

        assert retrieved_message is not None
        assert retrieved_message.id == message.id
        assert retrieved_message.telegram_message_id == telegram_msg_id
        assert retrieved_message.content == "Message with telegram ID"

    async def test_get_message_by_nonexistent_telegram_id(
        self, game_engine: GameEngine
    ):
        """Test retrieving message by non-existent telegram ID"""
        retrieved_message = await game_engine.get_message_by_telegram_id(99999)
        assert retrieved_message is None
