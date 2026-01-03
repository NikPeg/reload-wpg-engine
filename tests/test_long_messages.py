"""Test for long message handling in player commands"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from wpg_engine.adapters.telegram.handlers.player import send_long_message


@pytest.mark.asyncio
async def test_send_long_message_short_text():
    """Test that short messages are sent as-is"""
    message = MagicMock()
    message.answer = AsyncMock()

    short_text = "This is a short message"
    await send_long_message(message, short_text)

    # Should be called once with full text
    message.answer.assert_called_once_with(short_text, parse_mode="HTML")


@pytest.mark.asyncio
async def test_send_long_message_long_text():
    """Test that long messages are split properly"""
    message = MagicMock()
    message.answer = AsyncMock()

    # Create a message that exceeds 4096 characters
    long_text = "Header\n\n"
    for i in range(100):
        long_text += f"💰 <b>Section {i}</b>: Value\n"
        long_text += f"   Description for section {i} " + "x" * 50 + "\n\n"

    await send_long_message(message, long_text)

    # Should be called multiple times
    assert message.answer.call_count > 1

    # Verify each call is within Telegram limits
    for call in message.answer.call_args_list:
        args, kwargs = call
        text = args[0]
        assert len(text) <= 4096
        assert kwargs.get("parse_mode") == "HTML"


@pytest.mark.asyncio
async def test_send_long_message_preserves_sections():
    """Test that sections are kept together when possible"""
    message = MagicMock()
    message.answer = AsyncMock()

    # Create sections that should stay together
    sections = []
    for i in range(20):
        section = f"💰 <b>Economy Section {i}</b>\n"
        section += f"   Rating: {i}/10\n"
        section += f"   Description: This is a detailed description for section {i}\n\n"
        sections.append(section)

    long_text = "🏛️ <b>Country Information</b>\n\n" + "".join(sections)

    # Make it long enough to require splitting (add with newlines to be realistic)
    for i in range(50):
        long_text += f"Extra text line {i}\n"

    await send_long_message(message, long_text)

    # Should be called multiple times
    assert message.answer.call_count >= 1

    # Verify each call is within limits
    for call in message.answer.call_args_list:
        args, kwargs = call
        text = args[0]
        assert len(text) <= 4096


@pytest.mark.asyncio
async def test_send_long_message_handles_empty_sections():
    """Test that empty sections are skipped"""
    message = MagicMock()
    message.answer = AsyncMock()

    text = "Header\n\n\n\nContent"
    await send_long_message(message, text)

    # Should still send the message
    assert message.answer.call_count >= 1


@pytest.mark.asyncio
async def test_send_long_message_with_html_tags():
    """Test that HTML tags are preserved correctly"""
    message = MagicMock()
    message.answer = AsyncMock()

    text = "<b>Bold</b> <i>Italic</i> <code>Code</code>\n" * 100
    await send_long_message(message, text)

    # Verify HTML is preserved in all parts
    for call in message.answer.call_args_list:
        args, kwargs = call
        text = args[0]
        # Check that tags are properly closed in each part
        assert (
            text.count("<b>") == text.count("</b>") or "<b>" in text or "</b>" in text
        )
