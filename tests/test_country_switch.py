"""
Test country switching during re-registration
"""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from wpg_engine.core.engine import GameEngine
from wpg_engine.models import Country, Player, PlayerRole


@pytest.mark.asyncio
async def test_player_can_switch_countries(db_session):
    """Test that a player can switch from one country to another"""
    # Create game
    game_engine = GameEngine(db_session)
    game = await game_engine.create_game(
        name="Test Game",
        description="Test game for country switching",
        max_points=30,
        max_population=10_000_000,
    )

    # Create first country
    country1 = await game_engine.create_country(
        game_id=game.id,
        name="Country One",
        description="First country",
        capital="Capital One",
        population=5_000_000,
        aspects={
            "economy": 5,
            "military": 5,
            "foreign_policy": 5,
            "territory": 5,
            "technology": 5,
            "religion_culture": 0,
            "governance_law": 0,
            "construction_infrastructure": 0,
            "social_relations": 0,
            "intelligence": 0,
        },
    )

    # Create player with first country
    telegram_id = 123456789
    player = await game_engine.create_player(
        game_id=game.id,
        telegram_id=telegram_id,
        username="test_user",
        display_name="Test User",
        country_id=country1.id,
        role=PlayerRole.PLAYER,
    )

    # Verify initial setup
    assert player.telegram_id == telegram_id
    assert player.country_id == country1.id

    # Simulate re-registration: detach player from old country
    player.country_id = None
    await db_session.commit()

    # Create second country
    country2 = await game_engine.create_country(
        game_id=game.id,
        name="Country Two",
        description="Second country",
        capital="Capital Two",
        population=8_000_000,
        aspects={
            "economy": 3,
            "military": 7,
            "foreign_policy": 4,
            "territory": 6,
            "technology": 2,
            "religion_culture": 2,
            "governance_law": 2,
            "construction_infrastructure": 2,
            "social_relations": 1,
            "intelligence": 1,
        },
    )

    # Simulate complete_registration: check if player exists and update
    result = await db_session.execute(
        select(Player).where(Player.telegram_id == telegram_id)
    )
    existing_player = result.scalar_one_or_none()

    assert existing_player is not None, "Player should exist from previous registration"

    # Update existing player with new country (this is what the fix does)
    existing_player.country_id = country2.id
    existing_player.username = "test_user_updated"
    existing_player.display_name = "Test User Updated"
    await db_session.commit()

    # Verify the update
    await db_session.refresh(existing_player)
    assert existing_player.telegram_id == telegram_id
    assert existing_player.country_id == country2.id
    assert existing_player.username == "test_user_updated"
    assert existing_player.display_name == "Test User Updated"

    # Verify only one player record exists for this telegram_id
    result = await db_session.execute(
        select(Player).where(Player.telegram_id == telegram_id)
    )
    all_players = result.scalars().all()
    assert len(all_players) == 1, "Should only have one player record"

    # Verify both countries still exist
    result = await db_session.execute(select(Country).where(Country.game_id == game.id))
    countries = result.scalars().all()
    assert len(countries) == 2, "Both countries should exist"

    # Verify country1 has no players
    result = await db_session.execute(
        select(Country)
        .options(selectinload(Country.players))
        .where(Country.id == country1.id)
    )
    country1_refreshed = result.scalar_one()
    assert len(country1_refreshed.players) == 0, "Country1 should have no players"

    # Verify country2 has the player
    result = await db_session.execute(
        select(Country)
        .options(selectinload(Country.players))
        .where(Country.id == country2.id)
    )
    country2_refreshed = result.scalar_one()
    assert len(country2_refreshed.players) == 1, "Country2 should have one player"
    assert country2_refreshed.players[0].id == player.id


@pytest.mark.asyncio
async def test_multiple_country_switches(db_session):
    """Test that a player can switch countries multiple times"""
    game_engine = GameEngine(db_session)
    game = await game_engine.create_game(
        name="Test Game",
        description="Test game for multiple switches",
        max_points=30,
    )

    telegram_id = 987654321

    # Create and switch through 3 countries
    countries = []
    for i in range(3):
        country = await game_engine.create_country(
            game_id=game.id,
            name=f"Country {i + 1}",
            description=f"Country number {i + 1}",
            capital=f"Capital {i + 1}",
            population=(i + 1) * 1_000_000,
        )
        countries.append(country)

        # Check if player exists
        result = await db_session.execute(
            select(Player).where(Player.telegram_id == telegram_id)
        )
        existing_player = result.scalar_one_or_none()

        if existing_player:
            # Update existing player
            existing_player.country_id = country.id
            await db_session.commit()
        else:
            # Create new player
            existing_player = await game_engine.create_player(
                game_id=game.id,
                telegram_id=telegram_id,
                username=f"user_iteration_{i}",
                display_name=f"User Iteration {i}",
                country_id=country.id,
                role=PlayerRole.PLAYER,
            )

    # Verify only one player exists
    result = await db_session.execute(
        select(Player).where(Player.telegram_id == telegram_id)
    )
    all_players = result.scalars().all()
    assert len(all_players) == 1, "Should only have one player record"

    # Verify player is assigned to the last country
    player = all_players[0]
    assert player.country_id == countries[-1].id

    # Verify all countries exist
    result = await db_session.execute(select(Country).where(Country.game_id == game.id))
    all_countries = result.scalars().all()
    assert len(all_countries) == 3, "All three countries should exist"


@pytest.mark.asyncio
async def test_integrity_error_does_not_occur_on_reregistration(db_session):
    """Test that IntegrityError does not occur when player re-registers"""
    game_engine = GameEngine(db_session)
    game = await game_engine.create_game(
        name="Test Game",
        description="Test game",
        max_points=30,
    )

    telegram_id = 897853482  # Same ID from the error message

    # First registration
    country1 = await game_engine.create_country(
        game_id=game.id,
        name="First Country",
        description="First country",
        capital="First Capital",
        population=5_000_000,
    )

    player = await game_engine.create_player(
        game_id=game.id,
        telegram_id=telegram_id,
        username="Peganov_ns",
        display_name="Никита Пеганов",
        country_id=country1.id,
        role=PlayerRole.PLAYER,
    )

    assert player.telegram_id == telegram_id
    assert player.country_id == country1.id

    # Simulate re-registration flow
    # 1. Detach from old country (done in process_reregistration_confirmation)
    player.country_id = None
    await db_session.commit()

    # 2. Create new country
    country2 = await game_engine.create_country(
        game_id=game.id,
        name="Second Country",
        description="Second country",
        capital="Second Capital",
        population=3_000_000,
    )

    # 3. Try to "register" again - this should NOT raise IntegrityError
    # Check if player exists (this is what the fix does)
    result = await db_session.execute(
        select(Player).where(Player.telegram_id == telegram_id)
    )
    existing_player = result.scalar_one_or_none()

    if existing_player:
        # Update - this is the fixed behavior
        existing_player.country_id = country2.id
        await db_session.commit()
    else:
        # This would have caused the IntegrityError before the fix
        await game_engine.create_player(
            game_id=game.id,
            telegram_id=telegram_id,
            username="Peganov_ns",
            display_name="Никита Пеганов",
            country_id=country2.id,
            role=PlayerRole.PLAYER,
        )

    # Verify the update worked
    await db_session.refresh(player)
    assert player.country_id == country2.id

    # Verify only one player record exists
    result = await db_session.execute(
        select(Player).where(Player.telegram_id == telegram_id)
    )
    all_players = result.scalars().all()
    assert len(all_players) == 1


@pytest.mark.asyncio
async def test_old_country_remains_in_database_after_switch(db_session):
    """Test that old country remains in database after player switches"""
    game_engine = GameEngine(db_session)
    game = await game_engine.create_game(
        name="Test Game",
        description="Test game",
        max_points=30,
    )

    telegram_id = 111222333

    # Create first country and player
    country1 = await game_engine.create_country(
        game_id=game.id,
        name="Old Country",
        description="This country will be abandoned",
        capital="Old Capital",
        population=2_000_000,
    )

    player = await game_engine.create_player(
        game_id=game.id,
        telegram_id=telegram_id,
        username="test_player",
        display_name="Test Player",
        country_id=country1.id,
        role=PlayerRole.PLAYER,
    )

    country1_id = country1.id

    # Switch to new country
    player.country_id = None
    await db_session.commit()

    country2 = await game_engine.create_country(
        game_id=game.id,
        name="New Country",
        description="This is the new country",
        capital="New Capital",
        population=4_000_000,
    )

    player.country_id = country2.id
    await db_session.commit()

    # Verify old country still exists in database
    result = await db_session.execute(select(Country).where(Country.id == country1_id))
    old_country = result.scalar_one_or_none()
    assert old_country is not None, "Old country should still exist in database"
    assert old_country.name == "Old Country"

    # Verify old country has no players
    result = await db_session.execute(
        select(Country)
        .options(selectinload(Country.players))
        .where(Country.id == country1_id)
    )
    old_country_refreshed = result.scalar_one()
    assert len(old_country_refreshed.players) == 0, "Old country should have no players"

    # Verify player is now linked to new country
    await db_session.refresh(player)
    assert player.country_id == country2.id


@pytest.mark.asyncio
async def test_player_info_updates_on_reregistration(db_session):
    """Test that player username and display_name update on re-registration"""
    game_engine = GameEngine(db_session)
    game = await game_engine.create_game(
        name="Test Game",
        description="Test game",
        max_points=30,
    )

    telegram_id = 444555666

    # Initial registration
    country1 = await game_engine.create_country(
        game_id=game.id,
        name="Country 1",
        description="First country",
    )

    player = await game_engine.create_player(
        game_id=game.id,
        telegram_id=telegram_id,
        username="old_username",
        display_name="Old Display Name",
        country_id=country1.id,
        role=PlayerRole.PLAYER,
    )

    # Simulate user changed their Telegram username/display name
    player.country_id = None
    await db_session.commit()

    country2 = await game_engine.create_country(
        game_id=game.id,
        name="Country 2",
        description="Second country",
    )

    # Update player info (simulating what happens in complete_registration)
    result = await db_session.execute(
        select(Player).where(Player.telegram_id == telegram_id)
    )
    existing_player = result.scalar_one_or_none()

    assert existing_player is not None
    existing_player.country_id = country2.id
    existing_player.username = "new_username"
    existing_player.display_name = "New Display Name"
    await db_session.commit()

    # Verify updates
    await db_session.refresh(player)
    assert player.username == "new_username"
    assert player.display_name == "New Display Name"
    assert player.country_id == country2.id
