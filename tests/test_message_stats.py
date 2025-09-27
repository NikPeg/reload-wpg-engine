"""
Tests for message statistics functionality
"""

import pytest
from datetime import datetime, timedelta, timezone
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
        description="Test game for message statistics",
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
async def countries_and_players(game_engine: GameEngine, test_game):
    """Create countries and players for testing"""
    # Create countries
    country1 = await game_engine.create_country(
        game_id=test_game.id,
        name="Солярия",
        description="Солнечная империя",
        capital="Солнечный Город",
        population=5000000,
    )

    country2 = await game_engine.create_country(
        game_id=test_game.id,
        name="Вирджиния",
        description="Северная республика",
        capital="Ричмонд",
        population=3000000,
    )

    country3 = await game_engine.create_country(
        game_id=test_game.id,
        name="Абобистан",
        description="Восточное царство",
        capital="Абобград",
        population=2000000,
    )

    # Create players
    player1 = await game_engine.create_player(
        game_id=test_game.id,
        telegram_id=222222222,
        username="player1",
        display_name="Player 1",
        role=PlayerRole.PLAYER,
    )

    player2 = await game_engine.create_player(
        game_id=test_game.id,
        telegram_id=333333333,
        username="player2",
        display_name="Player 2",
        role=PlayerRole.PLAYER,
    )

    player3 = await game_engine.create_player(
        game_id=test_game.id,
        telegram_id=444444444,
        username="player3",
        display_name="Player 3",
        role=PlayerRole.PLAYER,
    )

    # Assign countries to players
    await game_engine.assign_player_to_country(player1.id, country1.id)
    await game_engine.assign_player_to_country(player2.id, country2.id)
    await game_engine.assign_player_to_country(player3.id, country3.id)

    return {
        "countries": [country1, country2, country3],
        "players": [player1, player2, player3],
    }


class TestMessageStatistics:
    """Test message statistics functionality"""

    async def test_get_countries_message_stats_empty(
        self, game_engine: GameEngine, test_game, countries_and_players
    ):
        """Test getting message statistics when no messages exist"""
        stats = await game_engine.get_countries_message_stats(test_game.id)

        assert len(stats) == 3  # All countries should be included
        for stat in stats:
            assert stat["message_count"] == 0
            assert stat["country_name"] in ["Солярия", "Вирджиния", "Абобистан"]

    async def test_get_countries_message_stats_with_messages(
        self, game_engine: GameEngine, test_game, countries_and_players
    ):
        """Test getting message statistics with actual messages"""
        players = countries_and_players["players"]

        # Create messages from different players (only player messages, not admin replies)
        # Player 1 (Солярия) - 5 messages
        for i in range(5):
            await game_engine.create_message(
                player_id=players[0].id,
                game_id=test_game.id,
                content=f"Message {i + 1} from Солярия",
                is_admin_reply=False,
            )

        # Player 2 (Вирджиния) - 3 messages
        for i in range(3):
            await game_engine.create_message(
                player_id=players[1].id,
                game_id=test_game.id,
                content=f"Message {i + 1} from Вирджиния",
                is_admin_reply=False,
            )

        # Player 3 (Абобистан) - 1 message
        await game_engine.create_message(
            player_id=players[2].id,
            game_id=test_game.id,
            content="Message from Абобистан",
            is_admin_reply=False,
        )

        # Add some admin replies (should not be counted)
        await game_engine.create_message(
            player_id=players[0].id,
            game_id=test_game.id,
            content="Admin reply to Солярия",
            is_admin_reply=True,
        )

        stats = await game_engine.get_countries_message_stats(test_game.id)

        # Should be sorted by message count descending, then by country name
        assert len(stats) == 3
        assert stats[0]["country_name"] == "Солярия"
        assert stats[0]["message_count"] == 5
        assert stats[1]["country_name"] == "Вирджиния"
        assert stats[1]["message_count"] == 3
        assert stats[2]["country_name"] == "Абобистан"
        assert stats[2]["message_count"] == 1

    async def test_get_countries_message_stats_old_messages(
        self, game_engine: GameEngine, test_game, countries_and_players
    ):
        """Test that old messages (older than a week) are not counted"""
        players = countries_and_players["players"]

        # Create a message from 8 days ago (should not be counted)
        old_message = await game_engine.create_message(
            player_id=players[0].id,
            game_id=test_game.id,
            content="Old message from Солярия",
            is_admin_reply=False,
        )

        # Manually update the created_at to be 8 days ago
        from sqlalchemy import text

        eight_days_ago = datetime.now(timezone.utc) - timedelta(days=8)
        await game_engine.db.execute(
            text("UPDATE messages SET created_at = :created_at WHERE id = :message_id"),
            {"created_at": eight_days_ago, "message_id": old_message.id},
        )
        await game_engine.db.commit()

        # Create a recent message (should be counted)
        await game_engine.create_message(
            player_id=players[1].id,
            game_id=test_game.id,
            content="Recent message from Вирджиния",
            is_admin_reply=False,
        )

        stats = await game_engine.get_countries_message_stats(test_game.id)

        # Only the recent message should be counted
        solaria_stats = next(s for s in stats if s["country_name"] == "Солярия")
        virginia_stats = next(s for s in stats if s["country_name"] == "Вирджиния")

        assert solaria_stats["message_count"] == 0  # Old message not counted
        assert virginia_stats["message_count"] == 1  # Recent message counted

    async def test_get_countries_message_stats_nonexistent_game(
        self, game_engine: GameEngine
    ):
        """Test getting statistics for non-existent game"""
        stats = await game_engine.get_countries_message_stats(99999)
        assert stats == []
