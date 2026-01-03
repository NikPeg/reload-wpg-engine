"""
Test reregistration functionality
"""

import pytest
from sqlalchemy import select

from wpg_engine.core.engine import GameEngine
from wpg_engine.models import Country, Player, PlayerRole


class TestReregistration:
    """Test reregistration functionality"""

    @pytest.mark.asyncio
    async def test_reregistration_keeps_old_country(self, db_session):
        """Test that old country is kept in database when player re-registers"""
        game_engine = GameEngine(db_session)

        # Create a game
        game = await game_engine.create_game(
            name="Test Game",
            description="A test game",
            setting="Test Setting",
        )

        # Create first country
        country1 = await game_engine.create_country(
            game_id=game.id,
            name="Old Country",
            description="Player's first country",
            capital="Old Capital",
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

        # Create a player and assign to first country
        player = await game_engine.create_player(
            game_id=game.id,
            telegram_id=12345,
            username="testuser",
            display_name="Test User",
            role=PlayerRole.PLAYER,
            country_id=country1.id,
        )

        # Verify initial state
        result = await db_session.execute(
            select(Country).where(Country.id == country1.id)
        )
        old_country = result.scalar_one_or_none()
        assert old_country is not None
        assert old_country.name == "Old Country"

        result = await db_session.execute(select(Player).where(Player.id == player.id))
        existing_player = result.scalar_one_or_none()
        assert existing_player is not None
        assert existing_player.country_id == country1.id

        # Simulate re-registration: unlink player from old country
        existing_player.country_id = None
        await db_session.commit()

        # Create new country for the same player
        country2 = await game_engine.create_country(
            game_id=game.id,
            name="New Country",
            description="Player's second country",
            capital="New Capital",
            population=2000000,
            aspects={
                "economy": 7,
                "military": 5,
                "foreign_policy": 6,
                "territory": 5,
                "technology": 8,
                "religion_culture": 5,
                "governance_law": 7,
                "construction_infrastructure": 6,
                "social_relations": 5,
                "intelligence": 4,
            },
        )

        # Assign player to new country
        await game_engine.assign_player_to_country(player.id, country2.id)

        # Verify final state
        # Old country should still exist
        result = await db_session.execute(
            select(Country).where(Country.id == country1.id)
        )
        old_country_after = result.scalar_one_or_none()
        assert old_country_after is not None
        assert old_country_after.name == "Old Country"

        # New country should exist
        result = await db_session.execute(
            select(Country).where(Country.id == country2.id)
        )
        new_country = result.scalar_one_or_none()
        assert new_country is not None
        assert new_country.name == "New Country"

        # Player should be linked to new country
        result = await db_session.execute(select(Player).where(Player.id == player.id))
        player_after = result.scalar_one_or_none()
        assert player_after is not None
        assert player_after.country_id == country2.id

        # Old country should have no players
        result = await db_session.execute(
            select(Country).where(Country.id == country1.id)
        )
        old_country_final = result.scalar_one_or_none()
        assert old_country_final is not None

        # Check that no players are assigned to old country
        result = await db_session.execute(
            select(Player).where(Player.country_id == country1.id)
        )
        players_in_old_country = result.scalars().all()
        assert len(players_in_old_country) == 0

    @pytest.mark.asyncio
    async def test_admin_can_delete_orphaned_country(self, db_session):
        """Test that admin can delete orphaned country (without player)"""
        game_engine = GameEngine(db_session)

        # Create a game
        game = await game_engine.create_game(
            name="Test Game",
            description="A test game",
            setting="Test Setting",
        )

        # Create an orphaned country (no player assigned)
        orphaned_country = await game_engine.create_country(
            game_id=game.id,
            name="Orphaned Country",
            description="Country without a player",
            capital="Orphan Capital",
            population=500000,
        )

        # Verify country exists
        result = await db_session.execute(
            select(Country).where(Country.id == orphaned_country.id)
        )
        country_before = result.scalar_one_or_none()
        assert country_before is not None
        assert country_before.name == "Orphaned Country"

        # Admin deletes the orphaned country
        success = await game_engine.delete_country(orphaned_country.id)
        assert success is True

        # Verify country is deleted
        result = await db_session.execute(
            select(Country).where(Country.id == orphaned_country.id)
        )
        country_after = result.scalar_one_or_none()
        assert country_after is None
