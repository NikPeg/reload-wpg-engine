"""
Test admin copy functionality for send messages
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, User

from wpg_engine.adapters.telegram.handlers.send import process_message_content
from wpg_engine.core.engine import GameEngine
from wpg_engine.models import PlayerRole


@pytest.mark.asyncio
async def test_admin_receives_message_copy(db_session):
    """Test that admin receives a copy of inter-country messages"""
    # Create game
    game_engine = GameEngine(db_session)
    game = await game_engine.create_game(
        name="Test Game",
        description="Test game for admin copy",
        setting="Test Setting",
        max_players=10,
        years_per_day=1,
        max_points=30,
        max_population=10000000,
    )

    # Create admin player
    admin_player = await game_engine.create_player(
        game_id=game.id,
        telegram_id=12345,
        username="admin",
        display_name="Admin",
        role=PlayerRole.ADMIN,
    )

    # Create admin country
    admin_country = await game_engine.create_country(
        game_id=game.id,
        name="Admin Country",
        description="Admin country",
        capital="Admin Capital",
        population=1000000,
        aspects={
            "economy": 5,
            "military": 5,
            "foreign_policy": 5,
            "territory": 5,
            "technology": 5,
            "religion_culture": 5,
            "governance_law": 5,
            "construction_infrastructure": 5,
            "social_relations": 5,
            "intelligence": 5,
        },
    )

    # Assign admin to country
    await game_engine.assign_player_to_country(admin_player.id, admin_country.id)

    # Create sender player and country
    sender_player = await game_engine.create_player(
        game_id=game.id,
        telegram_id=67890,
        username="sender",
        display_name="Sender",
        role=PlayerRole.PLAYER,
    )

    sender_country = await game_engine.create_country(
        game_id=game.id,
        name="Sender Country",
        description="Sender country",
        capital="Sender Capital",
        population=2000000,
        aspects={
            "economy": 4,
            "military": 4,
            "foreign_policy": 4,
            "territory": 4,
            "technology": 4,
            "religion_culture": 4,
            "governance_law": 4,
            "construction_infrastructure": 4,
            "social_relations": 4,
            "intelligence": 4,
        },
    )

    await game_engine.assign_player_to_country(sender_player.id, sender_country.id)

    # Create target player and country
    target_player = await game_engine.create_player(
        game_id=game.id,
        telegram_id=11111,
        username="target",
        display_name="Target",
        role=PlayerRole.PLAYER,
    )

    target_country = await game_engine.create_country(
        game_id=game.id,
        name="Target Country",
        description="Target country",
        capital="Target Capital",
        population=3000000,
        aspects={
            "economy": 6,
            "military": 6,
            "foreign_policy": 6,
            "territory": 6,
            "technology": 6,
            "religion_culture": 6,
            "governance_law": 6,
            "construction_infrastructure": 6,
            "social_relations": 6,
            "intelligence": 6,
        },
    )

    await game_engine.assign_player_to_country(target_player.id, target_country.id)

    # Mock message and bot
    mock_user = User(id=67890, is_bot=False, first_name="Sender")
    mock_message = MagicMock(spec=Message)
    mock_message.from_user = mock_user
    mock_message.text = "Тестовое сообщение для проверки копии администратору"
    mock_message.message_id = 123
    mock_message.answer = AsyncMock()

    # Mock bot
    mock_bot = AsyncMock()
    mock_message.bot = mock_bot

    # Mock FSM context
    mock_state = AsyncMock(spec=FSMContext)
    mock_state.get_data.return_value = {
        "target_player_id": target_player.id,
        "target_country_name": target_country.name,
    }
    mock_state.clear = AsyncMock()

    # Mock get_db to return our test database session
    async def mock_get_db():
        yield db_session

    # Call the function with mocked database
    with patch("wpg_engine.adapters.telegram.handlers.send.get_db", mock_get_db):
        await process_message_content(mock_message, mock_state)

    # Verify that bot.send_message was called 3 times:
    # 1. To target player
    # 2. To admin (copy)
    # 3. Confirmation to sender (via message.answer)
    assert mock_bot.send_message.call_count == 2  # Target + Admin

    # Check calls to bot.send_message
    calls = mock_bot.send_message.call_args_list

    # First call should be to target player
    target_call = calls[0]
    assert target_call[0][0] == target_player.telegram_id
    assert "Вам пришло послание из страны Sender Country" in target_call[0][1]
    assert "Тестовое сообщение для проверки копии администратору" in target_call[0][1]

    # Second call should be to admin
    admin_call = calls[1]
    assert admin_call[0][0] == admin_player.telegram_id
    assert "Копия сообщения между странами" in admin_call[0][1]
    assert "<b>От:</b> Sender Country" in admin_call[0][1]
    assert "<b>Кому:</b> Target Country" in admin_call[0][1]
    assert "Тестовое сообщение для проверки копии администратору" in admin_call[0][1]

    # Verify confirmation was sent to sender
    mock_message.answer.assert_called_once()
    confirmation_call = mock_message.answer.call_args
    assert "Сообщение отправлено!" in confirmation_call[0][0]
    assert "Target Country" in confirmation_call[0][0]

    # Verify state was cleared
    mock_state.clear.assert_called_once()


@pytest.mark.asyncio
async def test_admin_not_receiving_own_messages(db_session):
    """Test that admin doesn't receive copy when they are sender or recipient"""
    # Create game
    game_engine = GameEngine(db_session)
    game = await game_engine.create_game(
        name="Test Game",
        description="Test game for admin copy",
        setting="Test Setting",
        max_players=10,
        years_per_day=1,
        max_points=30,
        max_population=10000000,
    )

    # Create admin player
    admin_player = await game_engine.create_player(
        game_id=game.id,
        telegram_id=12345,
        username="admin",
        display_name="Admin",
        role=PlayerRole.ADMIN,
    )

    # Create admin country
    admin_country = await game_engine.create_country(
        game_id=game.id,
        name="Admin Country",
        description="Admin country",
        capital="Admin Capital",
        population=1000000,
        aspects={
            "economy": 5,
            "military": 5,
            "foreign_policy": 5,
            "territory": 5,
            "technology": 5,
            "religion_culture": 5,
            "governance_law": 5,
            "construction_infrastructure": 5,
            "social_relations": 5,
            "intelligence": 5,
        },
    )

    await game_engine.assign_player_to_country(admin_player.id, admin_country.id)

    # Create target player and country
    target_player = await game_engine.create_player(
        game_id=game.id,
        telegram_id=11111,
        username="target",
        display_name="Target",
        role=PlayerRole.PLAYER,
    )

    target_country = await game_engine.create_country(
        game_id=game.id,
        name="Target Country",
        description="Target country",
        capital="Target Capital",
        population=3000000,
        aspects={
            "economy": 6,
            "military": 6,
            "foreign_policy": 6,
            "territory": 6,
            "technology": 6,
            "religion_culture": 6,
            "governance_law": 6,
            "construction_infrastructure": 6,
            "social_relations": 6,
            "intelligence": 6,
        },
    )

    await game_engine.assign_player_to_country(target_player.id, target_country.id)

    # Mock message from admin
    mock_user = User(id=12345, is_bot=False, first_name="Admin")  # Admin's telegram_id
    mock_message = MagicMock(spec=Message)
    mock_message.from_user = mock_user
    mock_message.text = "Сообщение от администратора"
    mock_message.message_id = 123
    mock_message.answer = AsyncMock()

    # Mock bot
    mock_bot = AsyncMock()
    mock_message.bot = mock_bot

    # Mock FSM context
    mock_state = AsyncMock(spec=FSMContext)
    mock_state.get_data.return_value = {
        "target_player_id": target_player.id,
        "target_country_name": target_country.name,
    }
    mock_state.clear = AsyncMock()

    # Mock get_db to return our test database session
    async def mock_get_db():
        yield db_session

    # Call the function with mocked database
    with patch("wpg_engine.adapters.telegram.handlers.send.get_db", mock_get_db):
        await process_message_content(mock_message, mock_state)

    # Verify that bot.send_message was called only once (to target player)
    # Admin should not receive a copy since they are the sender
    assert mock_bot.send_message.call_count == 1

    # Check the call
    calls = mock_bot.send_message.call_args_list
    target_call = calls[0]
    assert target_call[0][0] == target_player.telegram_id
    assert "Вам пришло послание из страны Admin Country" in target_call[0][1]
