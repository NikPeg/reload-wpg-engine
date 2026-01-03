"""
Test examples functionality
"""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from wpg_engine.models import Country, Example, Game, Player, PlayerRole


@pytest.fixture
async def game(db_session):
    """Create a test game"""
    game = Game(
        name="Test Game",
        description="Test Description",
        setting="Test Setting",
        max_players=10,
        years_per_day=1,
        max_points=30,
        max_population=10_000_000,
    )
    db_session.add(game)
    await db_session.commit()
    await db_session.refresh(game)
    return game


@pytest.fixture
async def admin_player(db_session, game):
    """Create a test admin player"""
    player = Player(
        telegram_id=12345,
        username="testadmin",
        display_name="Test Admin",
        game_id=game.id,
        role=PlayerRole.ADMIN,
    )
    db_session.add(player)
    await db_session.commit()
    await db_session.refresh(player)
    return player


@pytest.fixture
async def country(db_session, game):
    """Create a test country"""
    country = Country(
        name="Test Country",
        description="Test description",
        capital="Test Capital",
        population=1000000,
        game_id=game.id,
    )
    db_session.add(country)
    await db_session.commit()
    await db_session.refresh(country)
    return country


@pytest.mark.asyncio
async def test_create_example(db_session, game, admin_player, country):
    """Test creating an example country"""
    # Create example
    example = Example(
        country_id=country.id,
        game_id=game.id,
        created_by_id=admin_player.id,
    )

    db_session.add(example)
    await db_session.commit()
    await db_session.refresh(example)

    assert example.id is not None
    assert example.country_id == country.id
    assert example.game_id == game.id
    assert example.created_by_id == admin_player.id


@pytest.mark.asyncio
async def test_get_examples_for_game(db_session, game, admin_player):
    """Test retrieving examples for a game"""
    # Create multiple countries
    country1 = Country(
        name="Country 1",
        description="Description 1",
        game_id=game.id,
    )
    country2 = Country(
        name="Country 2",
        description="Description 2",
        game_id=game.id,
    )

    db_session.add(country1)
    db_session.add(country2)
    await db_session.commit()

    # Create examples
    example1 = Example(
        country_id=country1.id,
        game_id=game.id,
        created_by_id=admin_player.id,
    )
    example2 = Example(
        country_id=country2.id,
        game_id=game.id,
        created_by_id=admin_player.id,
    )

    db_session.add(example1)
    db_session.add(example2)
    await db_session.commit()

    # Get all examples for game
    result = await db_session.execute(
        select(Example).where(Example.game_id == game.id).order_by(Example.id)
    )
    examples = result.scalars().all()

    assert len(examples) == 2
    assert examples[0].country_id == country1.id
    assert examples[1].country_id == country2.id


@pytest.mark.asyncio
async def test_example_cascade_delete_with_game(
    db_session, game, admin_player, country
):
    """Test that examples are deleted when game is deleted"""
    # Create example
    example = Example(
        country_id=country.id,
        game_id=game.id,
        created_by_id=admin_player.id,
    )

    db_session.add(example)
    await db_session.commit()
    example_id = example.id

    # Delete game
    await db_session.delete(game)
    await db_session.commit()

    # Check that example is also deleted
    result = await db_session.execute(select(Example).where(Example.id == example_id))
    deleted_example = result.scalar_one_or_none()

    assert deleted_example is None


@pytest.mark.asyncio
async def test_example_unique_country(db_session, game, admin_player, country):
    """Test that a country can only be an example once"""
    # Create first example
    example1 = Example(
        country_id=country.id,
        game_id=game.id,
        created_by_id=admin_player.id,
    )

    db_session.add(example1)
    await db_session.commit()

    # Try to create second example with same country
    example2 = Example(
        country_id=country.id,
        game_id=game.id,
        created_by_id=admin_player.id,
    )

    db_session.add(example2)

    # Should raise an error due to unique constraint
    with pytest.raises(IntegrityError):
        await db_session.commit()
