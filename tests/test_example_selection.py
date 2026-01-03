"""
Test example selection functionality
"""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

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
async def example_country(db_session, game):
    """Create a test example country"""
    country = Country(
        name="Example Country",
        description="A test example country",
        capital="Example Capital",
        population=5000000,
        game_id=game.id,
        economy=7,
        military=6,
        foreign_policy=5,
        territory=8,
        technology=6,
        religion_culture=5,
        governance_law=6,
        construction_infrastructure=7,
        social_relations=5,
        intelligence=4,
    )
    db_session.add(country)
    await db_session.commit()
    await db_session.refresh(country)
    return country


@pytest.fixture
async def example(db_session, game, admin_player, example_country):
    """Create a test example"""
    example = Example(
        country_id=example_country.id,
        game_id=game.id,
        created_by_id=admin_player.id,
    )
    db_session.add(example)
    await db_session.commit()
    await db_session.refresh(example)
    return example


@pytest.mark.asyncio
async def test_new_player_selects_example(db_session, game, example, example_country):
    """Test that a new player can select an example country"""
    # Create a new player with the example country
    new_player = Player(
        telegram_id=99999,
        username="newplayer",
        display_name="New Player",
        game_id=game.id,
        country_id=example_country.id,
        role=PlayerRole.PLAYER,
    )

    db_session.add(new_player)
    await db_session.commit()

    # Delete the example (simulating the selection process)
    await db_session.delete(example)
    await db_session.commit()

    # Verify player has the country
    result = await db_session.execute(
        select(Player)
        .options(selectinload(Player.country))
        .where(Player.telegram_id == 99999)
    )
    player = result.scalar_one_or_none()

    assert player is not None
    assert player.country_id == example_country.id
    assert player.country.name == "Example Country"

    # Verify example is deleted
    result = await db_session.execute(
        select(Example).where(Example.id == example.id)
    )
    deleted_example = result.scalar_one_or_none()
    assert deleted_example is None


@pytest.mark.asyncio
async def test_existing_player_changes_to_example(
    db_session, game, example, example_country
):
    """Test that an existing player can change to an example country"""
    # Create an existing country for the player
    old_country = Country(
        name="Old Country",
        description="Player's old country",
        game_id=game.id,
    )
    db_session.add(old_country)
    await db_session.commit()

    # Create existing player
    existing_player = Player(
        telegram_id=88888,
        username="existingplayer",
        display_name="Existing Player",
        game_id=game.id,
        country_id=old_country.id,
        role=PlayerRole.PLAYER,
    )
    db_session.add(existing_player)
    await db_session.commit()

    # Simulate changing to example country
    existing_player.country_id = example_country.id
    await db_session.commit()

    # Delete the example
    await db_session.delete(example)
    await db_session.commit()

    # Verify player has the new country
    result = await db_session.execute(
        select(Player)
        .options(selectinload(Player.country))
        .where(Player.telegram_id == 88888)
    )
    player = result.scalar_one_or_none()

    assert player is not None
    assert player.country_id == example_country.id
    assert player.country.name == "Example Country"

    # Verify old country still exists (not deleted)
    result = await db_session.execute(
        select(Country).where(Country.id == old_country.id)
    )
    old_country_check = result.scalar_one_or_none()
    assert old_country_check is not None

    # Verify example is deleted
    result = await db_session.execute(
        select(Example).where(Example.id == example.id)
    )
    deleted_example = result.scalar_one_or_none()
    assert deleted_example is None


@pytest.mark.asyncio
async def test_example_not_available_after_selection(
    db_session, game, example, example_country, admin_player
):
    """Test that an example is no longer available after someone selects it"""
    # First player selects the example
    player1 = Player(
        telegram_id=77777,
        username="player1",
        display_name="Player 1",
        game_id=game.id,
        country_id=example_country.id,
        role=PlayerRole.PLAYER,
    )
    db_session.add(player1)
    await db_session.commit()

    # Delete the example
    await db_session.delete(example)
    await db_session.commit()

    # Try to get the example (should not exist)
    result = await db_session.execute(
        select(Example).where(Example.id == example.id)
    )
    deleted_example = result.scalar_one_or_none()

    assert deleted_example is None

    # Verify the country is still available (just not as an example)
    result = await db_session.execute(
        select(Country).where(Country.id == example_country.id)
    )
    country = result.scalar_one_or_none()

    assert country is not None
    assert country.name == "Example Country"


@pytest.mark.asyncio
async def test_multiple_examples_selection(db_session, game, admin_player):
    """Test that multiple players can select different example countries"""
    # Create multiple example countries
    country1 = Country(
        name="Country 1",
        description="First example",
        game_id=game.id,
    )
    country2 = Country(
        name="Country 2",
        description="Second example",
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

    # Player 1 selects country 1
    player1 = Player(
        telegram_id=66666,
        username="player1",
        display_name="Player 1",
        game_id=game.id,
        country_id=country1.id,
        role=PlayerRole.PLAYER,
    )
    db_session.add(player1)
    await db_session.commit()

    await db_session.delete(example1)
    await db_session.commit()

    # Player 2 selects country 2
    player2 = Player(
        telegram_id=55555,
        username="player2",
        display_name="Player 2",
        game_id=game.id,
        country_id=country2.id,
        role=PlayerRole.PLAYER,
    )
    db_session.add(player2)
    await db_session.commit()

    await db_session.delete(example2)
    await db_session.commit()

    # Verify both players have their countries
    result = await db_session.execute(
        select(Player)
        .options(selectinload(Player.country))
        .where(Player.telegram_id.in_([66666, 55555]))
        .order_by(Player.telegram_id)
    )
    players = result.scalars().all()

    assert len(players) == 2
    assert players[0].country.name == "Country 2"  # 55555
    assert players[1].country.name == "Country 1"  # 66666

    # Verify both examples are deleted
    result = await db_session.execute(
        select(Example).where(Example.game_id == game.id)
    )
    examples = result.scalars().all()
    assert len(examples) == 0


@pytest.mark.asyncio
async def test_country_remains_after_example_deletion(
    db_session, game, example, example_country
):
    """Test that deleting an example doesn't delete the country"""
    example_id = example.id
    country_id = example_country.id

    # Delete the example
    await db_session.delete(example)
    await db_session.commit()

    # Verify example is deleted
    result = await db_session.execute(
        select(Example).where(Example.id == example_id)
    )
    deleted_example = result.scalar_one_or_none()
    assert deleted_example is None

    # Verify country still exists
    result = await db_session.execute(
        select(Country).where(Country.id == country_id)
    )
    country = result.scalar_one_or_none()
    assert country is not None
    assert country.name == "Example Country"

