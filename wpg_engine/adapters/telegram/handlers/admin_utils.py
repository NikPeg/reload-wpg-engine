"""
Admin handlers utilities
"""

import re

from aiogram.fsm.state import State, StatesGroup
from telegramify_markdown import markdownify

from wpg_engine.adapters.telegram.utils import escape_html
from wpg_engine.core.engine import GameEngine
from wpg_engine.models import Country, Player


class AdminStates(StatesGroup):
    """Admin states"""

    waiting_for_restart_confirmation = State()
    waiting_for_event_message = State()
    waiting_for_gen_action = State()
    waiting_for_delete_country_confirmation = State()
    waiting_for_final_message = State()
    waiting_for_delete_user_confirmation = State()
    waiting_for_example_message = State()


async def find_target_country_by_name(
    all_countries: list[Country], country_name: str
) -> Country | None:
    """Find target country by name or synonyms (case-insensitive)"""
    for country in all_countries:
        # Check official name
        if country.name.lower() == country_name.lower():
            return country

        # Check synonyms
        if country.synonyms:
            for synonym in country.synonyms:
                if synonym.lower() == country_name.lower():
                    return country
    return None


async def find_target_player_by_country_name(
    all_players: list[Player], country_name: str
) -> Player | None:
    """Find target player by their country name or synonyms (case-insensitive)"""
    for player in all_players:
        if not player.country:
            continue

        # Check official name
        if player.country.name.lower() == country_name.lower():
            return player

        # Check synonyms
        if player.country.synonyms:
            for synonym in player.country.synonyms:
                if synonym.lower() == country_name.lower():
                    return player
    return None


async def extract_country_from_reply(
    message, all_countries_or_players: list[Country] | list[Player]
) -> tuple[Country | Player, str] | None:
    """Extract country information from reply message

    Args:
        message: Message to extract from
        all_countries_or_players: List of Country or Player objects to search in

    Returns:
        Tuple of (target_country_or_player, country_name) or None if not found
    """
    if not message.reply_to_message or not message.reply_to_message.text:
        return None

    replied_text = message.reply_to_message.text

    # Determine if we're working with Players or Countries
    is_player_list = len(all_countries_or_players) > 0 and hasattr(
        all_countries_or_players[0], "country"
    )

    # Look for the hidden marker [EDIT_COUNTRY:id]
    country_id_match = re.search(r"\[EDIT_COUNTRY:(\d+)\]", replied_text)
    if country_id_match:
        country_id = int(country_id_match.group(1))

        # Find the country/player with this ID
        if is_player_list:
            for player in all_countries_or_players:
                if player.country and player.country.id == country_id:
                    return player, player.country.name
        else:
            for country in all_countries_or_players:
                if country.id == country_id:
                    return country, country.name

    # If no hidden marker found, try to extract country name from the message
    # Look for country name in the format "🏛️ **Country Name**"
    country_name_match = re.search(r"🏛️\s*<b>([^<]+)</b>", replied_text)
    if country_name_match:
        extracted_country_name = country_name_match.group(1).strip()

        # Find target country by name and synonyms
        if is_player_list:
            target_player = await find_target_player_by_country_name(
                all_countries_or_players, extracted_country_name
            )
            if target_player:
                return target_player, target_player.country.name
        else:
            target_country = await find_target_country_by_name(
                all_countries_or_players, extracted_country_name
            )
            if target_country:
                return target_country, target_country.name

    return None


async def send_message_to_players(
    bot,
    game_engine: GameEngine,
    players: list[Player],
    message_content: str,
    game_id: int,
    use_markdown: bool = False,
) -> tuple[int, int]:
    """Send message to multiple players

    Returns:
        Tuple of (sent_count, failed_count)
    """
    import logging

    logger = logging.getLogger(__name__)

    sent_count = 0
    failed_count = 0

    for player in players:
        try:
            if use_markdown:
                # Try to format with markdownify first
                try:
                    formatted_message = markdownify(message_content)
                    await bot.send_message(
                        player.telegram_id,
                        formatted_message,
                        parse_mode="MarkdownV2",
                    )
                except Exception as format_error:
                    logger.warning(
                        f"⚠️ Не удалось отправить форматированное сообщение игроку {player.telegram_id}: {format_error}"
                    )
                    # Fallback to HTML
                    await bot.send_message(
                        player.telegram_id,
                        escape_html(message_content),
                        parse_mode="HTML",
                    )
            else:
                await bot.send_message(
                    player.telegram_id,
                    escape_html(message_content),
                    parse_mode="HTML",
                )
            sent_count += 1

            # Save the admin message to database for RAG context
            await game_engine.create_message(
                player_id=player.id,
                game_id=game_id,
                content=message_content,
                is_admin_reply=True,
            )
        except Exception as e:
            logger.error(
                f"❌ Не удалось отправить сообщение игроку {player.telegram_id}: {type(e).__name__}: {e}"
            )
            failed_count += 1

    return sent_count, failed_count
