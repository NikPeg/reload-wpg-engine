"""
Player handlers
"""

import logging

from aiogram import Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from wpg_engine.adapters.telegram.utils import escape_html
from wpg_engine.core.engine import GameEngine
from wpg_engine.models import Example, Game, Player, get_db

logger = logging.getLogger(__name__)

# Removed PostStates - no longer needed

# Telegram message limit
TELEGRAM_MAX_MESSAGE_LENGTH = 4096


async def send_long_message(
    message: Message, text: str, parse_mode: str = "HTML"
) -> None:
    """
    Send a long message, splitting it intelligently if it exceeds Telegram's limit.

    Tries to split by section markers to keep related content together.
    Section markers are lines starting with emoji + <b> tag (aspect headers).

    Args:
        message: The message to reply to
        text: The text to send (can be longer than 4096 characters)
        parse_mode: Parse mode for Telegram (default: HTML)
    """
    if len(text) <= TELEGRAM_MAX_MESSAGE_LENGTH:
        # Message fits in one piece, send as is
        await message.answer(text, parse_mode=parse_mode)
        return

    # Split text into logical sections (header + content blocks)
    sections = []
    current_section = ""

    lines = text.split("\n")
    for line in lines:
        # If adding this line would exceed the limit, save current section and start new
        potential_length = len(current_section) + len(line) + 1  # +1 for newline

        if potential_length > TELEGRAM_MAX_MESSAGE_LENGTH - 100:  # Leave some margin
            # If current section is empty, we need to force-split this single line
            if not current_section.strip():
                # Force split this line into chunks
                while len(line) > TELEGRAM_MAX_MESSAGE_LENGTH - 100:
                    chunk = line[: TELEGRAM_MAX_MESSAGE_LENGTH - 100]
                    sections.append(chunk)
                    line = line[TELEGRAM_MAX_MESSAGE_LENGTH - 100 :]
                current_section = line + "\n" if line else ""
            else:
                # Save current section and start new one with this line
                sections.append(current_section.rstrip())
                current_section = line + "\n"
        else:
            current_section += line + "\n"

    # Add remaining section
    if current_section.strip():
        sections.append(current_section.rstrip())

    # Send all sections
    for section in sections:
        if section.strip():  # Only send non-empty sections
            await message.answer(section, parse_mode=parse_mode)


def truncate_text(text: str, max_length: int = 300) -> str:
    """
    Truncate text to max_length characters, adding ... if truncated

    NOTE: This function is kept for backward compatibility but should not be used
    for country descriptions. Use full text and rely on send_long_message() instead.
    """
    if not text:
        return text
    if len(text) <= max_length:
        return text
    return text[:max_length].rstrip() + "..."


async def stats_command(message: Message) -> None:
    """Handle /stats command - show player's country info"""
    user_id = message.from_user.id

    async with get_db() as db:
        game_engine = GameEngine(db)

        # Get player
        result = await game_engine.db.execute(
            select(Player)
            .options(selectinload(Player.country), selectinload(Player.game))
            .where(Player.telegram_id == user_id)
        )
        player = result.scalar_one_or_none()

    if not player:
        await message.answer("❌ Вы не зарегистрированы в игре. Используйте /register")
        return

    if not player.country:
        await message.answer("❌ Вам не назначена страна. Обратитесь к администратору.")
        return

    country = player.country
    aspects = country.get_aspects()

    # Format aspects with emojis
    aspect_emojis = {
        "economy": "💰",
        "military": "⚔️",
        "foreign_policy": "🤝",
        "territory": "🗺️",
        "technology": "🔬",
        "religion_culture": "🏛️",
        "governance_law": "⚖️",
        "construction_infrastructure": "🏗️",
        "social_relations": "👥",
        "intelligence": "🕵️",
    }

    aspect_names = {
        "economy": "Экономика",
        "military": "Военное дело",
        "foreign_policy": "Внешняя политика",
        "territory": "Территория",
        "technology": "Технологичность",
        "religion_culture": "Религия и культура",
        "governance_law": "Управление и право",
        "construction_infrastructure": "Строительство",
        "social_relations": "Общественные отношения",
        "intelligence": "Разведка",
    }

    aspects_text = ""
    for aspect, data in aspects.items():
        emoji = aspect_emojis.get(aspect, "📊")
        name = aspect_names.get(aspect, aspect)
        value = data["value"]
        description = data["description"] or "Нет описания"

        # Add rating bar
        rating_bar = "█" * value + "░" * (10 - value)

        aspects_text += f"{emoji} <b>{name}</b>: {value}/10\n"
        aspects_text += f"   {rating_bar}\n"
        # Don't truncate aspect descriptions - send full text
        aspects_text += f"   <i>{escape_html(description)}</i>\n\n"

    # Build country info message
    country_info = "🏛️ <b>Информация о вашей стране</b>\n\n"
    country_info += f"<b>Название:</b> {escape_html(country.name)}\n"

    # Show synonyms if they exist
    if country.synonyms:
        synonyms_text = ", ".join([escape_html(syn) for syn in country.synonyms])
        country_info += f"<b>Синонимы:</b> {synonyms_text}\n"

    country_info += f"<b>Столица:</b> {escape_html(country.capital or 'Не указана')}\n"
    country_info += f"<b>Население:</b> {country.population:,} чел.\n\n"
    # Don't truncate country description - send full text
    country_info += f"<b>Описание:</b>\n<i>{escape_html(country.description)}</i>\n\n"
    country_info += f"<b>Аспекты развития:</b>\n\n{aspects_text}"
    country_info += f"<b>Игра:</b> {escape_html(player.game.name)}\n"
    country_info += f"<b>Сеттинг:</b> {escape_html(player.game.setting)}\n"
    country_info += f"<b>Темп:</b> {player.game.years_per_day} лет/день"

    # Use smart message sending that handles long texts
    await send_long_message(message, country_info, parse_mode="HTML")


# Removed post_command and process_post_content functions
# Posts are now handled through direct messages


async def world_command(message: Message) -> None:
    """Handle /world command - show info about countries"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    chat_type = message.chat.type

    # Parse command arguments
    command_text = message.text or ""
    parts = command_text.split(maxsplit=1)
    country_name = parts[1].strip() if len(parts) > 1 else None

    logger.info(
        f"🌍 Команда /world вызвана пользователем {user_id} в чате {chat_id} (тип: {chat_type})"
        + (f" с параметром '{country_name}'" if country_name else " без параметров")
    )

    # Aspect emojis and names
    aspect_emojis = {
        "economy": "💰",
        "military": "⚔️",
        "foreign_policy": "🤝",
        "territory": "🗺️",
        "technology": "🔬",
        "religion_culture": "🏛️",
        "governance_law": "⚖️",
        "construction_infrastructure": "🏗️",
        "social_relations": "👥",
        "intelligence": "🕵️",
    }

    aspect_names = {
        "economy": "Экономика",
        "military": "Военное дело",
        "foreign_policy": "Внешняя политика",
        "territory": "Территория",
        "technology": "Технологичность",
        "religion_culture": "Религия и культура",
        "governance_law": "Управление и право",
        "construction_infrastructure": "Строительство",
        "social_relations": "Общественные отношения",
        "intelligence": "Разведка",
    }

    async with get_db() as db:
        game_engine = GameEngine(db)

        # Get player
        result = await game_engine.db.execute(
            select(Player)
            .options(selectinload(Player.country))
            .where(Player.telegram_id == user_id)
        )
        player = result.scalar_one_or_none()

        if not player:
            logger.warning(f"⚠️ Пользователь {user_id} не зарегистрирован в игре")
            await message.answer(
                "❌ Вы не зарегистрированы в игре. Используйте /register"
            )
            return

        # Check if user is admin
        from wpg_engine.core.admin_utils import is_admin

        user_is_admin = await is_admin(user_id, game_engine.db, message.chat.id)

        # Get all countries in the game
        game = await game_engine.get_game(player.game_id)
        if not game:
            logger.error(
                f"❌ Игра {player.game_id} не найдена для пользователя {user_id}"
            )
            await message.answer("❌ Игра не найдена.")
            return

        if country_name:
            # Show info about specific country
            logger.info(f"🔍 Поиск страны '{country_name}' в игре {player.game_id}")
            country = await game_engine.find_country_by_name_or_synonym(
                player.game_id, country_name
            )

            if not country:
                logger.warning(
                    f"⚠️ Страна '{country_name}' не найдена в игре {player.game_id}"
                )
                await message.answer(
                    f"❌ Страна '{escape_html(country_name)}' не найдена.\n\n"
                    f"Используйте /world без параметров для просмотра всех стран.",
                    parse_mode="HTML",
                )
                return

            logger.info(f"✅ Страна '{country.name}' найдена, показываем информацию")

            # Check if country is NPC (example or without active player)
            # Check if country is an example
            result = await db.execute(
                select(Example).where(Example.country_id == country.id)
            )
            is_example = result.scalar_one_or_none() is not None

            # Check if country has an active player
            result = await db.execute(
                select(Player).where(Player.country_id == country.id)
            )
            has_player = result.scalar_one_or_none() is not None

            is_npc = is_example or not has_player

            country_info = ""
            if is_npc:
                country_info += "🤖 <b>NPC</b>\n\n"

            country_info += f"🏛️ <b>{escape_html(country.name)}</b>\n"

            country_info += (
                f"<b>Столица:</b> {escape_html(country.capital or 'Неизвестна')}\n"
            )

            if country.population:
                country_info += f"<b>Население:</b> {country.population:,} чел.\n"

            # Show description for all players when requesting specific country (full text, no truncation)
            if country.description:
                country_info += (
                    f"<b>Описание:</b> <i>{escape_html(country.description)}</i>\n"
                )

            country_info += "\n"

            # When requesting specific country, show detailed info (like admin but without intelligence for regular players)
            aspects = country.get_aspects()
            country_info += "<b>Аспекты развития:</b>\n\n"

            for aspect, data in aspects.items():
                # Hide intelligence from regular players
                if aspect == "intelligence" and not user_is_admin:
                    continue

                emoji = aspect_emojis.get(aspect, "📊")
                name = aspect_names.get(aspect, aspect)
                value = data["value"]
                description = data["description"] or "Нет описания"

                # Add rating bar
                rating_bar = "█" * value + "░" * (10 - value)

                country_info += f"{emoji} <b>{name}</b>: {value}/10\n"
                country_info += f"   {rating_bar}\n"
                # Don't truncate aspect descriptions - send full text
                country_info += f"   <i>{escape_html(description)}</i>\n\n"

            # Add hidden marker for admin editing (invisible to user) only for admins
            if user_is_admin:
                country_info += f"\n<code>[EDIT_COUNTRY:{country.id}]</code>"

            # Send country info using smart message sending
            await send_long_message(message, country_info, parse_mode="HTML")
            logger.info(
                f"✅ Информация о стране '{country.name}' отправлена пользователю {user_id}"
            )
        else:
            # Show info about all countries (original behavior)
            logger.info(f"📋 Показываем список всех стран в игре {player.game_id}")
            await message.answer(
                "🌍 <b>Информация о странах мира</b>", parse_mode="HTML"
            )

            countries_count = 0
            # Send info about each country in separate messages
            for country in game.countries:
                if not user_is_admin and country.id == player.country_id:
                    continue  # Skip own country for regular players, but show for admins

                countries_count += 1

                # Check if country is NPC (example or without active player)
                # Check if country is an example
                result = await db.execute(
                    select(Example).where(Example.country_id == country.id)
                )
                is_example = result.scalar_one_or_none() is not None

                # Check if country has an active player
                result = await db.execute(
                    select(Player).where(Player.country_id == country.id)
                )
                has_player = result.scalar_one_or_none() is not None

                is_npc = is_example or not has_player

                country_info = ""
                if is_npc:
                    country_info += "🤖 <b>NPC</b>\n\n"

                country_info += f"🏛️ <b>{escape_html(country.name)}</b>\n"

                # Show synonyms if they exist
                if country.synonyms:
                    synonyms_text = ", ".join(
                        [escape_html(syn) for syn in country.synonyms]
                    )
                    country_info += f"<b>Синонимы:</b> {synonyms_text}\n"

                country_info += (
                    f"<b>Столица:</b> {escape_html(country.capital or 'Неизвестна')}\n"
                )

                if country.population:
                    country_info += f"<b>Население:</b> {country.population:,} чел.\n"

                if country.description and user_is_admin:
                    # Don't truncate country description for admins - send full text
                    country_info += (
                        f"<b>Описание:</b> <i>{escape_html(country.description)}</i>\n"
                    )

                country_info += "\n"

                if user_is_admin:
                    # Admin sees all aspects with descriptions
                    aspects = country.get_aspects()
                    country_info += "<b>Все аспекты развития:</b>\n\n"

                    for aspect, data in aspects.items():
                        emoji = aspect_emojis.get(aspect, "📊")
                        name = aspect_names.get(aspect, aspect)
                        value = data["value"]
                        description = data["description"] or "Нет описания"

                        # Add rating bar
                        rating_bar = "█" * value + "░" * (10 - value)

                        country_info += f"{emoji} <b>{name}</b>: {value}/10\n"
                        country_info += f"   {rating_bar}\n"
                        # Don't truncate aspect descriptions - send full text
                        country_info += f"   <i>{escape_html(description)}</i>\n\n"

                    # Add hidden marker for admin editing (invisible to user)
                    country_info += f"\n<code>[EDIT_COUNTRY:{country.id}]</code>"
                else:
                    # Regular players see only public aspects (values only)
                    public_aspects = country.get_public_aspects()

                    if public_aspects:
                        country_info += "<b>Известная информация:</b>\n"

                        for aspect, data in public_aspects.items():
                            emoji = aspect_emojis.get(aspect, "📊")
                            name = aspect_names.get(aspect, aspect)
                            value = data["value"]

                            # Hide intelligence from regular players
                            if aspect == "intelligence" and not user_is_admin:
                                continue

                            country_info += f"  {emoji} {name}: {value}/10\n"
                    else:
                        country_info += "<i>Публичная информация недоступна</i>\n"

                # Send country info using smart message sending
                await send_long_message(message, country_info, parse_mode="HTML")

            logger.info(
                f"✅ Информация о {countries_count} странах отправлена пользователю {user_id}"
            )


async def examples_command(message: Message) -> None:
    """Handle /examples command - show example countries for new players"""
    user_id = message.from_user.id

    async with get_db() as db:
        game_engine = GameEngine(db)

        # Get player to check if registered and get game_id
        result = await game_engine.db.execute(
            select(Player)
            .options(selectinload(Player.game))
            .where(Player.telegram_id == user_id)
        )
        player = result.scalar_one_or_none()

        if not player:
            # For unregistered users, show examples from first available game
            result = await game_engine.db.execute(select(Game).limit(1))
            game = result.scalar_one_or_none()
            if not game:
                await message.answer("❌ В данный момент нет активных игр.")
                return
            game_id = game.id
        else:
            game_id = player.game_id

        # Get all examples for the game
        result = await game_engine.db.execute(
            select(Example)
            .options(selectinload(Example.country))
            .where(Example.game_id == game_id)
            .order_by(Example.created_at.desc())
        )
        examples = result.scalars().all()

    if not examples:
        await message.answer(
            "📝 <b>Примеры стран</b>\n\n"
            "Пока нет примеров стран для вашей игры.\n"
            "Администратор может добавить примеры с помощью команды /add_example",
            parse_mode="HTML",
        )
        return

    # Send initial message
    await message.answer(
        "📝 <b>Примеры стран для выбора</b>\n\n"
        "Вы можете выбрать одну из этих стран для игры.\n"
        "Просто ответьте на сообщение о стране словом <b>выбрать</b> или <b>выбираю</b>.",
        parse_mode="HTML",
    )

    # Aspect emojis and names for displaying
    aspect_emojis = {
        "economy": "💰",
        "military": "⚔️",
        "foreign_policy": "🤝",
        "territory": "🗺️",
        "technology": "🔬",
        "religion_culture": "🏛️",
        "governance_law": "⚖️",
        "construction_infrastructure": "🏗️",
        "social_relations": "👥",
        "intelligence": "🕵️",
    }

    aspect_names = {
        "economy": "Экономика",
        "military": "Военное дело",
        "foreign_policy": "Внешняя политика",
        "territory": "Территория",
        "technology": "Технологичность",
        "religion_culture": "Религия и культура",
        "governance_law": "Управление и право",
        "construction_infrastructure": "Строительство",
        "social_relations": "Общественные отношения",
        "intelligence": "Разведка",
    }

    # Send each example country as a separate message
    for example in examples:
        country = example.country
        country_text = f"🏛️ <b>{escape_html(country.name)}</b>\n\n"

        if country.capital:
            country_text += f"<b>Столица:</b> {escape_html(country.capital)}\n"
        if country.population:
            country_text += f"<b>Население:</b> {country.population:,} чел.\n"

        if country.description:
            country_text += (
                # Don't truncate country description - send full text
                f"\n<b>Описание:</b>\n<i>{escape_html(country.description)}</i>\n"
            )

        country_text += "\n<b>Аспекты развития:</b>\n\n"

        # Show all aspects with descriptions
        aspects = country.get_aspects()
        for aspect, data in aspects.items():
            emoji = aspect_emojis.get(aspect, "📊")
            name = aspect_names.get(aspect, aspect)
            value = data["value"]
            description = data["description"] or "Нет описания"

            # Add rating bar
            rating_bar = "█" * value + "░" * (10 - value)

            country_text += f"{emoji} <b>{name}</b>: {value}/10\n"
            country_text += f"   {rating_bar}\n"
            # Don't truncate aspect descriptions - send full text
            country_text += f"   <i>{escape_html(description)}</i>\n\n"

        country_text += (
            "\n💡 <b>Чтобы играть за эту страну, ответьте на это сообщение</b> "
            "и напишите <b>выбрать</b> или <b>выбираю</b>.\n\n"
            f"<code>[EXAMPLE:{example.id}]</code>"
        )

        # Use smart message sending for examples too
        await send_long_message(message, country_text, parse_mode="HTML")


def register_player_handlers(dp: Dispatcher) -> None:
    """Register player handlers"""
    dp.message.register(stats_command, Command("stats"))
    # Command with ignore_mention=True allows it to work in group chats without bot mention
    dp.message.register(world_command, Command("world", ignore_mention=True))
    dp.message.register(examples_command, Command("examples"))
