"""
Test RAG system context functionality with admin messages
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from wpg_engine.core.engine import GameEngine
from wpg_engine.core.rag_system import RAGSystem
from wpg_engine.models import Base, PlayerRole


@pytest.fixture
async def db_session():
    """Create test database session"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session


@pytest.fixture
async def test_game_data(db_session):
    """Create test game, country, players"""
    game_engine = GameEngine(db_session)

    # Create test game
    game = await game_engine.create_game(
        name="Test Game", description="Test game for RAG context"
    )

    # Create test country
    country = await game_engine.create_country(
        game_id=game.id,
        name="TestCountry",
        description="Test country",
        aspects={"economy": 5, "military": 7, "foreign_policy": 6},
    )

    # Create test player
    player = await game_engine.create_player(
        game_id=game.id,
        telegram_id=12345,
        display_name="Test Player",
        role=PlayerRole.PLAYER,
        country_id=country.id,
    )

    # Create admin player
    admin = await game_engine.create_player(
        game_id=game.id,
        telegram_id=67890,
        display_name="Test Admin",
        role=PlayerRole.ADMIN,
    )

    return {
        "game": game,
        "country": country,
        "player": player,
        "admin": admin,
        "game_engine": game_engine,
    }


@pytest.mark.asyncio
async def test_rag_context_with_admin_message(db_session, test_game_data):
    """Test RAG system includes admin message context"""
    data = test_game_data
    game_engine = data["game_engine"]
    player = data["player"]
    game = data["game"]
    country = data["country"]

    # Create admin message
    admin_message_content = (
        "Ваша страна подверглась нападению со стороны соседей. Что будете делать?"
    )
    _ = await game_engine.create_message(
        player_id=player.id,
        game_id=game.id,
        content=admin_message_content,
        is_admin_reply=True,
    )

    # Create player response
    player_response = "Отразить нападение"
    _ = await game_engine.create_message(
        player_id=player.id,
        game_id=game.id,
        content=player_response,
        is_admin_reply=False,
    )

    # Test RAG system
    rag_system = RAGSystem(db_session)
    rag_system.api_key = "test_key"  # Mock API key

    # Test getting previous admin message
    previous_admin_msg = await rag_system._get_previous_admin_message(
        player.id, game.id
    )

    assert previous_admin_msg == admin_message_content

    # Test prompt creation includes context
    countries_data = await rag_system._get_all_countries_data(game.id)
    prompt = rag_system._create_analysis_prompt(
        player_response, country.name, countries_data, previous_admin_msg
    )

    assert "КОНТЕКСТ: Предыдущее сообщение от администратора" in prompt
    assert admin_message_content in prompt


@pytest.mark.asyncio
async def test_rag_context_without_admin_message(db_session, test_game_data):
    """Test RAG system when no admin message exists"""
    data = test_game_data
    game_engine = data["game_engine"]
    player = data["player"]
    game = data["game"]
    country = data["country"]

    # Create only player message (no admin message)
    player_response = "Хочу напасть на соседей"
    _ = await game_engine.create_message(
        player_id=player.id,
        game_id=game.id,
        content=player_response,
        is_admin_reply=False,
    )

    # Test RAG system
    rag_system = RAGSystem(db_session)
    rag_system.api_key = "test_key"  # Mock API key

    # Test getting previous admin message
    previous_admin_msg = await rag_system._get_previous_admin_message(
        player.id, game.id
    )

    assert previous_admin_msg is None

    # Test prompt creation without context
    countries_data = await rag_system._get_all_countries_data(game.id)
    prompt = rag_system._create_analysis_prompt(
        player_response, country.name, countries_data, previous_admin_msg
    )

    assert "КОНТЕКСТ: Предыдущее сообщение от администратора" not in prompt


@pytest.mark.asyncio
async def test_event_message_saving_and_retrieval(db_session, test_game_data):
    """Test that event messages are saved and retrieved correctly"""
    data = test_game_data
    game_engine = data["game_engine"]
    player = data["player"]
    game = data["game"]
    country = data["country"]

    # Simulate old admin message
    old_admin_msg = "Потому что вы слабы"
    await game_engine.create_message(
        player_id=player.id, game_id=game.id, content=old_admin_msg, is_admin_reply=True
    )

    # Simulate event message (like /event command would create)
    event_message = "На вас напало племя эльфов"
    await game_engine.create_message(
        player_id=player.id, game_id=game.id, content=event_message, is_admin_reply=True
    )

    # Player responds
    player_response = "Отразить нападение"
    await game_engine.create_message(
        player_id=player.id,
        game_id=game.id,
        content=player_response,
        is_admin_reply=False,
    )

    # Test RAG system retrieves the LATEST admin message
    rag_system = RAGSystem(db_session)
    rag_system.api_key = "test_key"

    previous_admin_msg = await rag_system._get_previous_admin_message(
        player.id, game.id
    )

    # Should get the latest event message, not the old one
    assert previous_admin_msg == event_message
    assert previous_admin_msg != old_admin_msg

    # Test prompt includes the latest context
    countries_data = await rag_system._get_all_countries_data(game.id)
    prompt = rag_system._create_analysis_prompt(
        player_response, country.name, countries_data, previous_admin_msg
    )

    assert event_message in prompt
    assert old_admin_msg not in prompt


@pytest.mark.asyncio
async def test_multiple_players_event_messages(db_session, test_game_data):
    """Test event messages for multiple players (like /event for all)"""
    data = test_game_data
    game_engine = data["game_engine"]
    game = data["game"]

    # Create second country and player
    country2 = await game_engine.create_country(
        game_id=game.id, name="SecondCountry", description="Second test country"
    )

    player2 = await game_engine.create_player(
        game_id=game.id,
        telegram_id=54321,
        display_name="Second Player",
        role=PlayerRole.PLAYER,
        country_id=country2.id,
    )

    # Send event to all players (simulating /event without country name)
    global_event = "Началась эпидемия чумы"

    # Save message for both players
    await game_engine.create_message(
        player_id=data["player"].id,
        game_id=game.id,
        content=global_event,
        is_admin_reply=True,
    )

    await game_engine.create_message(
        player_id=player2.id, game_id=game.id, content=global_event, is_admin_reply=True
    )

    # Players respond to the event
    await game_engine.create_message(
        player_id=data["player"].id,
        game_id=game.id,
        content="Закрываем границы",
        is_admin_reply=False,
    )

    await game_engine.create_message(
        player_id=player2.id,
        game_id=game.id,
        content="Ищем лекарство",
        is_admin_reply=False,
    )

    # Test RAG system for both players
    rag_system = RAGSystem(db_session)
    rag_system.api_key = "test_key"

    # Both players should have the same event in their context
    context1 = await rag_system._get_previous_admin_message(data["player"].id, game.id)
    context2 = await rag_system._get_previous_admin_message(player2.id, game.id)

    assert context1 == global_event
    assert context2 == global_event
    assert context1 == context2
