"""
Test registration with example selection using FSM
"""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, User

from wpg_engine.adapters.telegram.handlers.registration import (
    IsExampleSelection,
    process_example_selection,
)
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
async def test_is_example_selection_filter():
    """Test the IsExampleSelection filter"""
    filter_instance = IsExampleSelection()

    # Create mock message
    reply_msg = MagicMock(spec=Message)
    reply_msg.text = "Example country\n[EXAMPLE:123]"

    message = MagicMock(spec=Message)
    message.reply_to_message = reply_msg
    message.text = "выбрать"

    # Create mock state
    state = MagicMock(spec=FSMContext)
    state.get_state = AsyncMock(
        return_value="RegistrationStates:waiting_for_country_name"
    )

    # Should return True
    result = await filter_instance(message, state)
    assert result is True

    # Test with wrong text
    message.text = "some other text"
    result = await filter_instance(message, state)
    assert result is False

    # Test without reply
    message.reply_to_message = None
    message.text = "выбрать"
    result = await filter_instance(message, state)
    assert result is False

    # Test outside registration state
    message.reply_to_message = reply_msg
    state.get_state = AsyncMock(return_value=None)
    result = await filter_instance(message, state)
    assert result is False


@pytest.mark.asyncio
async def test_process_example_selection_success(
    db_session, game, example, example_country
):
    """Test successful example selection during registration"""
    # Create mock message
    user = User(
        id=99999,
        is_bot=False,
        first_name="Test",
        username="testuser",
    )

    reply_msg = MagicMock(spec=Message)
    reply_msg.text = f"Example country\n[EXAMPLE:{example.id}]"

    message = MagicMock(spec=Message)
    message.from_user = user
    message.reply_to_message = reply_msg
    message.text = "выбрать"
    message.answer = AsyncMock()
    message.bot = MagicMock()
    message.bot.send_message = AsyncMock()

    # Create mock state
    state = MagicMock(spec=FSMContext)
    state.get_state = AsyncMock(
        return_value="RegistrationStates:waiting_for_country_name"
    )
    state.get_data = AsyncMock(
        return_value={
            "user_id": 99999,
            "game_id": game.id,
        }
    )
    state.clear = AsyncMock()

    # Mock get_db to use our test session
    @asynccontextmanager
    async def mock_get_db():
        yield db_session

    with patch(
        "wpg_engine.adapters.telegram.handlers.registration.get_db", mock_get_db
    ):
        with patch("wpg_engine.config.settings.settings") as mock_settings:
            mock_settings.telegram.is_admin_chat.return_value = False

            # Call the handler
            await process_example_selection(message, state)

    # Verify message was sent to user
    assert message.answer.called
    call_args = message.answer.call_args[0][0]
    assert "Поздравляем" in call_args
    assert "Example Country" in call_args

    # Verify state was cleared
    assert state.clear.called

    # Verify player was created with the country from example
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    result = await db_session.execute(
        select(Player)
        .options(selectinload(Player.country))
        .where(Player.telegram_id == 99999)
    )
    player = result.scalar_one_or_none()

    assert player is not None
    assert player.country_id == example_country.id
    assert player.country.name == "Example Country"

    # Verify example was deleted
    result = await db_session.execute(select(Example).where(Example.id == example.id))
    deleted_example = result.scalar_one_or_none()
    assert deleted_example is None


@pytest.mark.asyncio
async def test_process_example_selection_not_reply():
    """Test that handler does nothing if message is not a reply"""
    message = MagicMock(spec=Message)
    message.reply_to_message = None
    message.text = "выбрать"

    state = MagicMock(spec=FSMContext)

    # Should return immediately
    await process_example_selection(message, state)

    # State should not be cleared
    assert not state.clear.called


@pytest.mark.asyncio
async def test_process_example_selection_wrong_text():
    """Test that handler does nothing if text is not 'выбрать' or 'выбираю'"""
    reply_msg = MagicMock(spec=Message)
    reply_msg.text = "Example country\n[EXAMPLE:123]"

    message = MagicMock(spec=Message)
    message.reply_to_message = reply_msg
    message.text = "some country name"

    state = MagicMock(spec=FSMContext)
    state.get_state = AsyncMock(
        return_value="RegistrationStates:waiting_for_country_name"
    )

    # Should return immediately without processing
    await process_example_selection(message, state)

    # State should not be cleared
    assert not state.clear.called


@pytest.mark.asyncio
async def test_process_example_selection_example_not_found(db_session, game):
    """Test handling when example is not found (already taken)"""
    user = User(
        id=99999,
        is_bot=False,
        first_name="Test",
        username="testuser",
    )

    reply_msg = MagicMock(spec=Message)
    reply_msg.text = "Example country\n[EXAMPLE:99999]"  # Non-existent example

    message = MagicMock(spec=Message)
    message.from_user = user
    message.reply_to_message = reply_msg
    message.text = "выбрать"
    message.answer = AsyncMock()

    state = MagicMock(spec=FSMContext)
    state.get_state = AsyncMock(
        return_value="RegistrationStates:waiting_for_country_name"
    )
    state.get_data = AsyncMock(
        return_value={
            "user_id": 99999,
            "game_id": game.id,
        }
    )

    @asynccontextmanager
    async def mock_get_db():
        yield db_session

    with patch(
        "wpg_engine.adapters.telegram.handlers.registration.get_db", mock_get_db
    ):
        await process_example_selection(message, state)

    # Verify error message was sent
    assert message.answer.called
    call_args = message.answer.call_args[0][0]
    assert "не найден" in call_args or "уже был выбран" in call_args


@pytest.mark.asyncio
async def test_selection_works_from_any_registration_state(
    db_session, game, admin_player
):
    """Test that example selection works from any registration state"""
    states_to_test = [
        "RegistrationStates:waiting_for_country_name",
        "RegistrationStates:waiting_for_capital",
        "RegistrationStates:waiting_for_population",
        "RegistrationStates:waiting_for_economy",
    ]

    for i, test_state in enumerate(states_to_test):
        # Create a unique country and example for each test
        test_country = Country(
            name=f"Test Country {i}",
            description=f"Test country for state {test_state}",
            capital=f"Capital {i}",
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
        db_session.add(test_country)
        await db_session.commit()
        await db_session.refresh(test_country)

        new_example = Example(
            country_id=test_country.id,
            game_id=game.id,
            created_by_id=admin_player.id,
        )
        db_session.add(new_example)
        await db_session.commit()
        await db_session.refresh(new_example)

        user = User(
            id=88888 + i,  # Unique user ID for each iteration
            is_bot=False,
            first_name="Test",
            username="testuser",
        )

        reply_msg = MagicMock(spec=Message)
        reply_msg.text = f"Example country\n[EXAMPLE:{new_example.id}]"

        message = MagicMock(spec=Message)
        message.from_user = user
        message.reply_to_message = reply_msg
        message.text = "выбираю"
        message.answer = AsyncMock()
        message.bot = MagicMock()
        message.bot.send_message = AsyncMock()

        state = MagicMock(spec=FSMContext)
        state.get_state = AsyncMock(return_value=test_state)
        state.get_data = AsyncMock(
            return_value={
                "user_id": 88888 + i,
                "game_id": game.id,
            }
        )
        state.clear = AsyncMock()

        @asynccontextmanager
        async def mock_get_db():
            yield db_session

        with patch(
            "wpg_engine.adapters.telegram.handlers.registration.get_db", mock_get_db
        ):
            with patch("wpg_engine.config.settings.settings") as mock_settings:
                mock_settings.telegram.is_admin_chat.return_value = False

                await process_example_selection(message, state)

        # Verify state was cleared
        assert state.clear.called, f"State was not cleared for {test_state}"
