"""
Tests for refactored admin functions
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from wpg_engine.adapters.telegram.handlers.admin_utils import (
    extract_country_from_reply,
    find_target_country_by_name,
    find_target_player_by_country_name,
    send_message_to_players,
)


@pytest.mark.asyncio
async def test_find_target_country_by_name():
    """Test finding country by name and synonyms"""
    # Create mock countries
    country1 = MagicMock()
    country1.name = "Российская Империя"
    country1.synonyms = ["Россия", "РИ"]

    country2 = MagicMock()
    country2.name = "Британская Империя"
    country2.synonyms = ["Британия", "Англия"]

    # Create mock players
    player1 = MagicMock()
    player1.country = country1

    player2 = MagicMock()
    player2.country = country2

    players = [player1, player2]

    # Test finding by official name using the player-specific function
    result = await find_target_player_by_country_name(players, "Российская Империя")
    assert result == player1

    # Test finding by synonym (case insensitive)
    result = await find_target_player_by_country_name(players, "россия")
    assert result == player1

    result = await find_target_player_by_country_name(players, "АНГЛИЯ")
    assert result == player2

    # Test not found
    result = await find_target_player_by_country_name(players, "Несуществующая страна")
    assert result is None

    # Also test the Country-only version
    countries = [country1, country2]

    result = await find_target_country_by_name(countries, "Российская Империя")
    assert result == country1

    result = await find_target_country_by_name(countries, "россия")
    assert result == country1

    result = await find_target_country_by_name(countries, "Несуществующая страна")
    assert result is None


@pytest.mark.asyncio
async def test_extract_country_from_reply():
    """Test extracting country from reply message"""
    # Create mock country
    country = MagicMock()
    country.id = 123
    country.name = "Тестовая Страна"
    country.synonyms = ["Тест"]

    # Create mock player
    player = MagicMock()
    player.country = country

    players = [player]

    # Test with hidden marker
    reply_message = MagicMock()
    reply_message.text = "Some text [EDIT_COUNTRY:123] more text"

    message = MagicMock()
    message.reply_to_message = reply_message

    result = await extract_country_from_reply(message, players)
    assert result == (player, "Тестовая Страна")

    # Test with country name in HTML format
    reply_message.text = "🏛️ <b>Тестовая Страна</b> some other text"
    result = await extract_country_from_reply(message, players)
    assert result == (player, "Тестовая Страна")

    # Test with no reply message
    message.reply_to_message = None
    result = await extract_country_from_reply(message, players)
    assert result is None


@pytest.mark.asyncio
async def test_send_message_to_players():
    """Test sending messages to players"""
    # Create mock bot
    bot = AsyncMock()

    # Create mock game engine
    game_engine = AsyncMock()

    # Create mock players
    player1 = MagicMock()
    player1.id = 1
    player1.telegram_id = 100

    player2 = MagicMock()
    player2.id = 2
    player2.telegram_id = 200

    players = [player1, player2]

    # Test successful sending
    sent_count, failed_count = await send_message_to_players(
        bot, game_engine, players, "Test message", 1, use_markdown=False
    )

    assert sent_count == 2
    assert failed_count == 0

    # Verify bot.send_message was called for each player
    assert bot.send_message.call_count == 2

    # Verify game_engine.create_message was called for each player
    assert game_engine.create_message.call_count == 2


@pytest.mark.asyncio
async def test_send_message_to_players_with_markdown():
    """Test sending messages with markdown formatting"""
    # Create mock bot
    bot = AsyncMock()

    # Create mock game engine
    game_engine = AsyncMock()

    # Create mock player
    player = MagicMock()
    player.id = 1
    player.telegram_id = 100

    players = [player]

    # Test with markdown enabled
    sent_count, failed_count = await send_message_to_players(
        bot, game_engine, players, "**Test message**", 1, use_markdown=True
    )

    assert sent_count == 1
    assert failed_count == 0

    # Verify bot.send_message was called
    assert bot.send_message.call_count == 1


@pytest.mark.asyncio
async def test_send_message_to_players_with_failure():
    """Test handling failures when sending messages"""
    # Create mock bot that fails
    bot = AsyncMock()
    bot.send_message.side_effect = Exception("Network error")

    # Create mock game engine
    game_engine = AsyncMock()

    # Create mock player
    player = MagicMock()
    player.id = 1
    player.telegram_id = 100

    players = [player]

    # Test with failure
    sent_count, failed_count = await send_message_to_players(
        bot, game_engine, players, "Test message", 1, use_markdown=False
    )

    assert sent_count == 0
    assert failed_count == 1

    # Verify bot.send_message was called but failed
    assert bot.send_message.call_count == 1

    # Verify game_engine.create_message was not called due to failure
    assert game_engine.create_message.call_count == 0
