"""
Telegram utilities for safe message formatting
"""

from html import escape


def escape_html(text: str) -> str:
    """
    Escape HTML special characters to prevent Telegram parsing errors.

    This function should be used for all user-generated content that will be
    displayed in Telegram messages to prevent "can't parse entities" errors.

    Args:
        text: The text to escape

    Returns:
        The escaped text safe for HTML parsing in Telegram
    """
    if not text:
        return ""
    return escape(str(text))


def escape_markdown(text: str) -> str:
    """
    Escape Markdown special characters to prevent Telegram parsing errors.

    This function should be used for all user-generated content that will be
    displayed in Telegram messages with Markdown parsing.

    Args:
        text: The text to escape

    Returns:
        The escaped text safe for Markdown parsing in Telegram
    """
    if not text:
        return ""

    # Escape only the most critical Markdown special characters for Telegram
    # Telegram uses a simplified Markdown parser, so we only need to escape these
    special_chars = ["*", "_", "`", "[", "]"]
    text = str(text)

    for char in special_chars:
        text = text.replace(char, f"\\{char}")

    return text
