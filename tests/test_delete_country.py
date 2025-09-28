"""
Test delete country functionality
"""

import pytest
from sqlalchemy import select

from wpg_engine.core.engine import GameEngine
from wpg_engine.models import Country, Player, PlayerRole


class TestDeleteCountry:
    """Test delete country functionality"""

    @pytest.mark.asyncio
    async def test_delete_country_success(self, db_session):
        """Test successful country deletion"""
        game_engine = GameEngine(db_session)

        # Create a game first
        game = await game_engine.create_game(
            name="Test Game",
            description="A test game",
            setting="Test Setting",
        )

        # Create a country
        country = await game_engine.create_country(
            game_id=game.id,
            name="Test Country",
            description="A test country",
            capital="Test Capital",
            population=1000000,
            aspects={
                "economy": 5,
                "military": 6,
                "foreign_policy": 4,
                "territory": 7,
                "technology": 5,
                "religion_culture": 6,
                "governance_law": 5,
                "construction_infrastructure": 4,
                "social_relations": 6,
                "intelligence": 3,
            },
        )

        # Create a player and assign to country
        player = await game_engine.create_player(
            game_id=game.id,
            telegram_id=12345,
            username="testuser",
            display_name="Test User",
            role=PlayerRole.PLAYER,
        )
        await game_engine.assign_player_to_country(player.id, country.id)

        # Verify country and player exist and are linked
        result = await db_session.execute(
            select(Country).where(Country.id == country.id)
        )
        existing_country = result.scalar_one_or_none()
        assert existing_country is not None

        result = await db_session.execute(select(Player).where(Player.id == player.id))
        existing_player = result.scalar_one_or_none()
        assert existing_player is not None
        assert existing_player.country_id == country.id

        # Delete the country
        success = await game_engine.delete_country(country.id)
        assert success is True

        # Verify country is deleted
        result = await db_session.execute(
            select(Country).where(Country.id == country.id)
        )
        deleted_country = result.scalar_one_or_none()
        assert deleted_country is None

        # Verify player is unassigned from country
        result = await db_session.execute(select(Player).where(Player.id == player.id))
        unassigned_player = result.scalar_one_or_none()
        assert unassigned_player is not None
        assert unassigned_player.country_id is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_country(self, db_session):
        """Test deleting a non-existent country"""
        game_engine = GameEngine(db_session)

        # Try to delete a country that doesn't exist
        success = await game_engine.delete_country(99999)
        assert success is False

    @pytest.mark.asyncio
    async def test_delete_country_with_multiple_players(self, db_session):
        """Test deleting a country with multiple players assigned"""
        game_engine = GameEngine(db_session)

        # Create a game first
        game = await game_engine.create_game(
            name="Multi-Player Test Game",
            description="A test game with multiple players",
            setting="Test Setting",
        )

        # Create a country
        country = await game_engine.create_country(
            game_id=game.id,
            name="Multi-Player Country",
            description="A country with multiple players",
            capital="Multi Capital",
            population=2000000,
        )

        # Create multiple players and assign to country
        player1 = await game_engine.create_player(
            game_id=game.id,
            telegram_id=11111,
            username="player1",
            display_name="Player One",
            role=PlayerRole.PLAYER,
        )
        player2 = await game_engine.create_player(
            game_id=game.id,
            telegram_id=22222,
            username="player2",
            display_name="Player Two",
            role=PlayerRole.PLAYER,
        )

        await game_engine.assign_player_to_country(player1.id, country.id)
        await game_engine.assign_player_to_country(player2.id, country.id)

        # Verify both players are assigned
        result = await db_session.execute(select(Player).where(Player.id == player1.id))
        p1 = result.scalar_one_or_none()
        assert p1.country_id == country.id

        result = await db_session.execute(select(Player).where(Player.id == player2.id))
        p2 = result.scalar_one_or_none()
        assert p2.country_id == country.id

        # Delete the country
        success = await game_engine.delete_country(country.id)
        assert success is True

        # Verify both players are unassigned
        result = await db_session.execute(select(Player).where(Player.id == player1.id))
        p1_after = result.scalar_one_or_none()
        assert p1_after.country_id is None

        result = await db_session.execute(select(Player).where(Player.id == player2.id))
        p2_after = result.scalar_one_or_none()
        assert p2_after.country_id is None
