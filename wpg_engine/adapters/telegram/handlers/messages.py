"""
Message handlers for player-admin communication
"""

import asyncio
import logging

from aiogram import Dispatcher
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from telegramify_markdown import markdownify

from wpg_engine.adapters.telegram.utils import escape_html, escape_markdown
from wpg_engine.core.admin_utils import is_admin
from wpg_engine.core.engine import GameEngine
from wpg_engine.core.message_classifier import MessageClassifier
from wpg_engine.core.rag_system import RAGSystem
from wpg_engine.models import Player, PlayerRole, get_db

logger = logging.getLogger(__name__)


async def _send_long_message(
    bot, chat_id: int, text: str, reply_to_message_id: int
) -> None:
    """Send long message, splitting if necessary due to Telegram limits"""
    MAX_MESSAGE_LENGTH = 4096

    if len(text) <= MAX_MESSAGE_LENGTH:
        # Message fits in one part, try formatted version first
        try:
            formatted_text = markdownify(text)
            await bot.send_message(
                chat_id,
                formatted_text,
                reply_to_message_id=reply_to_message_id,
                parse_mode="MarkdownV2",
            )
        except Exception as e:
            logger.warning(f"⚠️ Не удалось отправить форматированный RAG контекст: {e}")
            # Fallback: escape dangerous characters and send as HTML
            safe_text = (
                text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&#x27;")
            )
            await bot.send_message(
                chat_id,
                safe_text,
                reply_to_message_id=reply_to_message_id,
                parse_mode="HTML",
            )
    else:
        # Message is too long, split it
        parts = _split_long_text(text, MAX_MESSAGE_LENGTH)

        for i, part in enumerate(parts):
            try:
                formatted_part = markdownify(part)
                await bot.send_message(
                    chat_id,
                    formatted_part,
                    reply_to_message_id=reply_to_message_id if i == 0 else None,
                    parse_mode="MarkdownV2",
                )
            except Exception as e:
                logger.warning(
                    f"⚠️ Не удалось отправить форматированную часть {i + 1} RAG контекста: {e}"
                )
                # Fallback: escape dangerous characters and send as HTML
                safe_part = (
                    part.replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                    .replace('"', "&quot;")
                    .replace("'", "&#x27;")
                )
                await bot.send_message(
                    chat_id,
                    safe_part,
                    reply_to_message_id=reply_to_message_id if i == 0 else None,
                    parse_mode="HTML",
                )


def _split_long_text(text: str, max_length: int) -> list[str]:
    """Split long text into parts, trying to preserve formatting"""
    if len(text) <= max_length:
        return [text]

    parts = []
    current_part = ""

    # Split by paragraphs first (double newlines)
    paragraphs = text.split("\n\n")

    for paragraph in paragraphs:
        # If adding this paragraph would exceed limit
        if len(current_part) + len(paragraph) + 2 > max_length:
            if current_part:
                parts.append(current_part.strip())
                current_part = ""

            # If single paragraph is too long, split by sentences
            if len(paragraph) > max_length:
                sentences = paragraph.split(". ")
                for sentence in sentences:
                    if len(current_part) + len(sentence) + 2 > max_length:
                        if current_part:
                            parts.append(current_part.strip())
                            current_part = ""

                    if current_part:
                        current_part += ". " + sentence
                    else:
                        current_part = sentence
            else:
                current_part = paragraph
        else:
            if current_part:
                current_part += "\n\n" + paragraph
            else:
                current_part = paragraph

    if current_part:
        parts.append(current_part.strip())

    return parts


async def handle_text_message(message: Message, state: FSMContext) -> None:
    """Handle all text messages that are not commands"""
    user_id = message.from_user.id
    content = message.text.strip()

    # Check if user is in any FSM state - if so, skip this handler
    # to let FSM handlers process the message
    current_state = await state.get_state()
    if current_state is not None:
        return

    # Check if this is a reply to an example country selection
    if message.reply_to_message and message.reply_to_message.text:
        import re

        example_match = re.search(r"\[EXAMPLE:(\d+)\]", message.reply_to_message.text)
        if example_match and content.lower() in ["выбрать", "выбираю"]:
            async with get_db() as db:
                game_engine = GameEngine(db)
                await handle_example_selection(
                    message, int(example_match.group(1)), game_engine
                )
            return

    # Skip if message is too short or too long
    if len(content) < 3:
        await message.answer("❌ Сообщение слишком короткое (минимум 3 символа).")
        return

    if len(content) > 2000:
        await message.answer("❌ Сообщение слишком длинное (максимум 2000 символов).")
        return

    async with get_db() as db:
        game_engine = GameEngine(db)

        # Optimized: Load player without relations first
        result = await game_engine.db.execute(
            select(Player).where(Player.telegram_id == user_id)
        )
        player = result.scalar_one_or_none()

        if not player:
            await message.answer(
                "❌ Вы не зарегистрированы в игре. Используйте /start для начала работы с ботом."
            )
            return

        # Load relations only when needed
        await game_engine.db.refresh(player, ["country", "game"])

        # Check if this is an admin replying to a message or sending a message with ID
        if await is_admin(user_id, game_engine.db, message.chat.id):
            # If admin is sending a message in admin chat (not a reply), skip it
            # This is just admins talking to each other in the chat
            from wpg_engine.config.settings import settings

            if settings.telegram.is_admin_chat() and not message.reply_to_message:
                # Skip messages from admins in admin chat that are not replies
                # This prevents processing of regular admin-to-admin conversations
                return

            # Check if this is a reply to a message (for registration decisions)
            if message.reply_to_message:
                await handle_admin_reply(message, player, game_engine)
                return
            # Check if message contains message ID for direct reply
            import re

            if re.search(
                r"(?:ID сообщения|msg|message):\s*\d+|^\d+\s+", content, re.IGNORECASE
            ):
                await handle_admin_reply(message, player, game_engine)
                return

        # Regular player message - send to admin
        await handle_player_message(message, player, game_engine)


async def _process_ai_analysis_background(
    bot,
    target_chat_id: int,
    content: str,
    country_name: str,
    sent_message_id: int,
    player_id: int,
    game_id: int,
) -> None:
    """
    Background task to process AI analysis (classification + RAG).
    This runs independently and doesn't block the user's response.
    """
    try:
        # Step 1: Classify message type using LLM
        logger.info("🤖 Starting background AI classification...")
        classifier = MessageClassifier()
        message_type = await classifier.classify_message(content, country_name)
        logger.info(f"✅ Classification complete: {message_type}")

        # Map message types to emojis and descriptions
        type_info = {
            "вопрос": {"emoji": "❓", "desc": "Вопрос"},
            "приказ": {"emoji": "⚡", "desc": "Приказ"},
            "проект": {"emoji": "🏗️", "desc": "Проект"},
            "иное": {"emoji": "💭", "desc": "Иное"},
        }

        type_emoji = type_info.get(message_type, type_info["иное"])["emoji"]
        type_desc = type_info.get(message_type, type_info["иное"])["desc"]

        # Step 2: Send message type classification to admin
        type_message = (
            f"{type_emoji} <b>Тип сообщения: {type_desc}</b>\n"
            f"<i>Автоматически определено ИИ</i>"
        )

        await bot.send_message(target_chat_id, type_message, parse_mode="HTML")
        logger.info("✅ Message type sent to admin")

        # Step 3: Generate and send RAG context as reply to the original message
        # Open new DB session for background task
        async with get_db() as db:
            rag_system = RAGSystem(db)
            logger.info("🤖 Starting background RAG analysis...")
            rag_context = await rag_system.generate_admin_context(
                content, country_name, game_id, player_id
            )
            logger.info(
                f"✅ RAG analysis complete, length: {len(rag_context) if rag_context else 0}"
            )

            # Send RAG context as reply to admin's message if available
            if rag_context:
                await _send_long_message(
                    bot, target_chat_id, rag_context, sent_message_id
                )
                logger.info("✅ RAG context sent to admin")

    except Exception as e:
        logger.error(f"❌ Error in background AI processing: {type(e).__name__}: {e}")
        logger.exception("Full traceback:")
        # Don't notify user about background errors - they already got their confirmation


async def handle_player_message(
    message: Message, player: Player, game_engine: GameEngine
) -> None:
    """Handle message from player - save and forward to admin"""
    content = message.text.strip()

    # IMMEDIATELY confirm to player (this is the key - user gets instant response)
    await message.answer("✅ Сообщение отправлено администратору!")

    # Import settings to check if admin_id is a chat
    import random

    from wpg_engine.config.settings import settings

    # Determine target based on admin_id configuration
    admin = None
    target_chat_id = None

    if settings.telegram.is_admin_chat():
        # If admin_id is a chat (negative), send to that chat
        target_chat_id = settings.telegram.admin_id
    else:
        # Find admin(s) to send message to
        result = await game_engine.db.execute(
            select(Player)
            .where(Player.game_id == player.game_id)
            .where(Player.role == PlayerRole.ADMIN)
        )
        admins = result.scalars().all()

        if admins:
            # If multiple admins, choose one randomly
            admin = random.choice(admins)
            target_chat_id = admin.telegram_id

    if target_chat_id:
        try:
            country_name = player.country.name if player.country else "без страны"
            bot = message.bot

            # Step 1: Send original message to admin IMMEDIATELY (no AI yet)
            admin_message = (
                f"💬 <b>Новое сообщение от игрока</b>\n\n"
                f"<b>От:</b> {escape_html(player.display_name)} (ID: {player.telegram_id})\n"
                f"<b>Страна:</b> {escape_html(country_name)}\n\n"
                f"<b>Сообщение:</b>\n{escape_html(content)}"
            )

            sent_message = await bot.send_message(
                target_chat_id, admin_message, parse_mode="HTML"
            )

            # Step 2: Save message to database IMMEDIATELY
            await game_engine.create_message(
                player_id=player.id,
                game_id=player.game_id,
                content=content,
                telegram_message_id=message.message_id,
                admin_telegram_message_id=sent_message.message_id,
                is_admin_reply=False,
            )

            # Step 3: Launch AI processing in BACKGROUND (doesn't block)
            # Only process AI if player has a country
            if player.country:
                logger.info("🚀 Launching background AI analysis task...")
                asyncio.create_task(
                    _process_ai_analysis_background(
                        bot,
                        target_chat_id,
                        content,
                        country_name,
                        sent_message.message_id,
                        player.id,
                        player.game_id,
                    )
                )
                logger.info("✅ Background task launched, returning control to user")

        except Exception as e:
            logger.error(
                f"❌ Не удалось отправить сообщение администратору: {type(e).__name__}: {e}"
            )
            logger.exception("Full traceback:")
            # Note: User already got confirmation, so we don't send error message
            # We just log it for admin monitoring
    else:
        # Only if admin not found, tell the user
        await message.answer("⚠️ Администратор не найден в игре.")


async def handle_admin_reply(
    message: Message, admin: Player, game_engine: GameEngine
) -> None:
    """Handle admin reply to player message, registration, country editing, or event sending"""
    content = message.text.strip()

    # Check if this is a registration approval/rejection (when replying to registration message)
    if message.reply_to_message and (
        content.lower() == "одобрить" or content.lower().startswith("отклонить")
    ):
        decision = "одобрить" if content.lower() == "одобрить" else "отклонить"
        await handle_registration_decision(message, admin, game_engine, decision)
        return

    # Check if this is a reply to a country info message (for editing or event sending)
    if message.reply_to_message and message.reply_to_message.text:
        replied_text = message.reply_to_message.text
        import re

        # Look for country editing marker
        country_match = re.search(r"\[EDIT_COUNTRY:(\d+)\]", replied_text)
        if country_match:
            country_id = int(country_match.group(1))

            # Check if this looks like an editing command or an event message
            if is_country_editing_command(content):
                await handle_country_edit(
                    message, admin, game_engine, country_id, content
                )
                return
            else:
                # This is an event message for the country
                await handle_country_event(
                    message, admin, game_engine, country_id, content
                )
                return

    # If admin is replying to a message, find the original player message in database
    if not message.reply_to_message:
        await message.answer("❌ Ответьте на сообщение от игрока для отправки ответа.")
        return

    # Find the original player message by the admin message ID that was replied to
    original_message = await game_engine.get_message_by_admin_telegram_id(
        message.reply_to_message.message_id
    )

    if not original_message:
        await message.answer("❌ Не удалось найти исходное сообщение игрока.")
        return

    # Save admin reply
    await game_engine.create_message(
        player_id=original_message.player_id,
        game_id=original_message.game_id,
        content=content,
        reply_to_id=original_message.id,
        is_admin_reply=True,
    )

    # Send reply to original player as a reply to their original message
    try:
        bot = message.bot

        # Send the admin's response as a reply to the original player's message
        await bot.send_message(
            original_message.player.telegram_id,
            escape_html(content),
            reply_to_message_id=original_message.telegram_message_id,
            parse_mode="HTML",
        )

        await message.answer("✅ Ответ отправлен игроку!")

    except Exception as e:
        await message.answer(f"❌ Не удалось отправить ответ игроку: {e}")


def is_country_editing_command(content: str) -> bool:
    """Check if the message content looks like a country editing command"""
    content_lower = content.lower().strip()

    # List of editing command keywords
    editing_keywords = [
        "название ",
        "описание ",
        "столица ",
        "население ",
        "синонимы ",
        "экономика ",
        "военное ",
        "военное дело ",
        "армия ",
        "внешняя ",
        "внешняя политика ",
        "дипломатия ",
        "территория ",
        "технологии ",
        "технологичность ",
        "наука ",
        "религия ",
        "культура ",
        "религия и культура ",
        "управление ",
        "право ",
        "управление и право ",
        "строительство ",
        "инфраструктура ",
        "общество ",
        "общественные отношения ",
        "социальные ",
        "разведка ",
        "шпионаж ",
    ]

    # Check if content starts with any editing keyword
    for keyword in editing_keywords:
        if content_lower.startswith(keyword):
            return True

    # Check for aspect value patterns (like "экономика 8")
    import re

    if re.match(r"^[а-яё\s]+\s+\d+$", content_lower):
        return True

    # Check for aspect description patterns (like "экономика описание новое описание")
    if re.search(r"^[а-яё\s]+\s+описание\s+", content_lower):
        return True

    return False


async def handle_country_event(
    message: Message,
    admin: Player,
    game_engine: GameEngine,
    country_id: int,
    content: str,
) -> None:
    """Handle sending event to a specific country"""

    # Validate message content
    if len(content) < 3:
        await message.answer("❌ Сообщение слишком короткое (минимум 3 символа).")
        return

    if len(content) > 2000:
        await message.answer("❌ Сообщение слишком длинное (максимум 2000 символов).")
        return

    # Get the country
    country = await game_engine.get_country(country_id)
    if not country:
        await message.answer("❌ Страна не найдена.")
        return

    # Find the player who owns this country
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    result = await game_engine.db.execute(
        select(Player)
        .options(selectinload(Player.country))
        .where(Player.game_id == admin.game_id)
        .where(Player.country_id == country_id)
        .where(Player.role == PlayerRole.PLAYER)
    )
    target_player = result.scalar_one_or_none()

    if not target_player:
        await message.answer(
            f"❌ Не найден игрок для страны {escape_html(country.name)}."
        )
        return

    # Send event to the player
    try:
        bot = message.bot
        await bot.send_message(
            target_player.telegram_id,
            escape_html(content),
            parse_mode="HTML",
        )

        # Save the admin message to database for RAG context
        await game_engine.create_message(
            player_id=target_player.id,
            game_id=admin.game_id,
            content=content,
            is_admin_reply=True,
        )

        # Confirm to admin
        await message.answer(
            f"✅ <b>Событие отправлено в страну {escape_html(country.name)}</b>\n"
            f"<i>(автоматически определено из ответа на описание страны)</i>",
            parse_mode="HTML",
        )

    except Exception as e:
        logger.error(
            f"❌ Не удалось отправить событие игроку {target_player.telegram_id}: {type(e).__name__}: {e}"
        )
        logger.exception("Full traceback:")
        await message.answer(
            f"❌ Не удалось отправить событие в страну {escape_html(country.name)}."
        )


async def handle_country_edit(
    message: Message,
    admin: Player,
    game_engine: GameEngine,
    country_id: int,
    content: str,
) -> None:
    """Handle country editing by admin"""

    # Get the country
    country = await game_engine.get_country(country_id)
    if not country:
        await message.answer("❌ Страна не найдена.")
        return

    # Parse the editing command
    # Format examples:
    # "экономика 8" - set economy value to 8
    # "экономика описание Новое описание экономики" - set economy description
    # "название Новое название страны" - set country name
    # "описание Новое описание страны" - set country description
    # "столица Новая столица" - set capital
    # "население 5000000" - set population

    # Aspect mappings
    aspect_mappings = {
        "экономика": "economy",
        "военное": "military",
        "военное дело": "military",
        "армия": "military",
        "внешняя": "foreign_policy",
        "внешняя политика": "foreign_policy",
        "дипломатия": "foreign_policy",
        "территория": "territory",
        "технологии": "technology",
        "технологичность": "technology",
        "наука": "technology",
        "религия": "religion_culture",
        "культура": "religion_culture",
        "религия и культура": "religion_culture",
        "управление": "governance_law",
        "право": "governance_law",
        "управление и право": "governance_law",
        "строительство": "construction_infrastructure",
        "инфраструктура": "construction_infrastructure",
        "общество": "social_relations",
        "общественные отношения": "social_relations",
        "социальные": "social_relations",
        "разведка": "intelligence",
        "шпионаж": "intelligence",
    }

    # Try to parse different formats
    lines = content.strip().split("\n")
    success_messages = []
    error_messages = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Check for basic country info updates
        if line.lower().startswith("название "):
            new_name = line[9:].strip()
            if new_name:
                await game_engine.update_country_basic_info(country_id, name=new_name)
                success_messages.append(
                    f"✅ Название изменено на: {escape_html(new_name)}"
                )
            else:
                error_messages.append("❌ Название не может быть пустым")
            continue

        elif line.lower().startswith("описание "):
            new_description = line[9:].strip()
            await game_engine.update_country_basic_info(
                country_id, description=new_description
            )
            success_messages.append("✅ Описание страны обновлено")
            continue

        elif line.lower().startswith("столица "):
            new_capital = line[8:].strip()
            await game_engine.update_country_basic_info(country_id, capital=new_capital)
            success_messages.append(
                f"✅ Столица изменена на: {escape_html(new_capital)}"
            )
            continue

        elif line.lower().startswith("население "):
            try:
                new_population = int(
                    line[10:].strip().replace(",", "").replace(" ", "")
                )
                await game_engine.update_country_basic_info(
                    country_id, population=new_population
                )
                success_messages.append(f"✅ Население изменено на: {new_population:,}")
            except ValueError:
                error_messages.append("❌ Некорректное значение населения")
            continue

        elif line.lower().startswith("синонимы "):
            synonyms_text = line[9:].strip()
            if synonyms_text.lower() == "очистить":
                # Clear all synonyms
                await game_engine.update_country_synonyms(country_id, [])
                success_messages.append("✅ Синонимы очищены")
            else:
                # Parse synonyms (comma-separated)
                new_synonyms = [
                    s.strip() for s in synonyms_text.split(",") if s.strip()
                ]
                if new_synonyms:
                    # Check for conflicts with existing countries and their synonyms
                    conflict_found = False
                    from wpg_engine.models import Country

                    result = await game_engine.db.execute(
                        select(Country)
                        .where(Country.game_id == country.game_id)
                        .where(Country.id != country_id)
                    )
                    other_countries = result.scalars().all()

                    for synonym in new_synonyms:
                        for other_country in other_countries:
                            # Check against official names
                            if other_country.name.lower() == synonym.lower():
                                error_messages.append(
                                    f"❌ Синоним '{synonym}' конфликтует с названием страны '{other_country.name}'"
                                )
                                conflict_found = True
                                break

                            # Check against other synonyms
                            if other_country.synonyms:
                                for other_synonym in other_country.synonyms:
                                    if other_synonym.lower() == synonym.lower():
                                        error_messages.append(
                                            f"❌ Синоним '{synonym}' уже используется страной '{other_country.name}'"
                                        )
                                        conflict_found = True
                                        break
                            if conflict_found:
                                break
                        if conflict_found:
                            break

                    if not conflict_found:
                        await game_engine.update_country_synonyms(
                            country_id, new_synonyms
                        )
                        escaped_synonyms = [escape_html(syn) for syn in new_synonyms]
                        success_messages.append(
                            f"✅ Синонимы обновлены: {', '.join(escaped_synonyms)}"
                        )
                else:
                    error_messages.append("❌ Не указаны синонимы")
            continue

        # Parse aspect updates
        found_aspect = None
        for key, aspect in aspect_mappings.items():
            if line.lower().startswith(key.lower() + " "):
                found_aspect = aspect
                remaining = line[len(key) :].strip()
                break

        if not found_aspect:
            error_messages.append(f"❌ Неизвестный аспект: {line}")
            continue

        # Check if it's a description update
        if remaining.lower().startswith("описание "):
            new_description = remaining[9:].strip()
            result = await game_engine.update_country_aspect_description(
                country_id, found_aspect, new_description
            )
            if result:
                success_messages.append(f"✅ Описание аспекта '{key}' обновлено")
            else:
                error_messages.append(
                    f"❌ Не удалось обновить описание аспекта '{key}'"
                )
        else:
            # Try to parse as value update
            try:
                new_value = int(remaining.strip())
                if 1 <= new_value <= 10:
                    result = await game_engine.update_country_aspect_value(
                        country_id, found_aspect, new_value
                    )
                    if result:
                        success_messages.append(
                            f"✅ {key.capitalize()}: {new_value}/10"
                        )
                    else:
                        error_messages.append(f"❌ Не удалось обновить {key}")
                else:
                    error_messages.append(f"❌ Значение {key} должно быть от 1 до 10")
            except ValueError:
                error_messages.append(
                    f"❌ Некорректное значение для {key}: {remaining}"
                )

    # Send response
    response = f"🏛️ *Редактирование страны {escape_markdown(country.name)}*\n\n"

    if success_messages:
        response += "*Успешно обновлено:*\n" + "\n".join(success_messages) + "\n\n"

    if error_messages:
        response += "*Ошибки:*\n" + "\n".join(error_messages) + "\n\n"

    if not success_messages and not error_messages:
        response += "❌ Не удалось распознать команды редактирования.\n\n"

    response += "*Доступные команды:*\n"
    response += "• `название Новое название`\n"
    response += "• `описание Новое описание`\n"
    response += "• `столица Новая столица`\n"
    response += "• `население 1000000`\n"
    response += "• `синонимы ХФ, Хуан` - установить синонимы\n"
    response += "• `синонимы очистить` - удалить все синонимы\n"
    response += "• `экономика 8` - изменить значение\n"
    response += "• `экономика описание Новое описание` - изменить описание\n"
    response += "• Аналогично для других аспектов: военное, внешняя, территория, технологии, религия, управление, строительство, общество, разведка"

    await message.answer(response, parse_mode="Markdown")


async def handle_example_selection(
    message: Message, example_id: int, game_engine: GameEngine
) -> None:
    """Handle player selection of an example country"""
    user_id = message.from_user.id

    # Get the example
    from wpg_engine.models import Example

    result = await game_engine.db.execute(
        select(Example)
        .options(selectinload(Example.country))
        .where(Example.id == example_id)
    )
    example = result.scalar_one_or_none()

    if not example:
        await message.answer(
            "❌ Эта страна уже недоступна для выбора. "
            "Используйте /examples чтобы посмотреть доступные страны."
        )
        return

    country = example.country
    game_id = example.game_id

    # Check if user is already registered
    result = await game_engine.db.execute(
        select(Player)
        .options(selectinload(Player.country))
        .where(Player.telegram_id == user_id)
    )
    existing_player = result.scalar_one_or_none()

    try:
        if existing_player:
            # Player exists - update their country
            # First, detach old country if it exists
            if existing_player.country_id:
                existing_player.country_id = None
                await game_engine.db.commit()

            # Assign new country
            existing_player.country_id = country.id
            existing_player.game_id = game_id
            await game_engine.db.commit()

            # Delete the example entry
            await game_engine.db.delete(example)
            await game_engine.db.commit()

            await message.answer(
                f"✅ <b>Отлично!</b>\n\n"
                f"Вы теперь играете за страну <b>{escape_html(country.name)}</b>!\n\n"
                f"<b>Столица:</b> {escape_html(country.capital or 'Не указана')}\n"
                f"<b>Население:</b> {country.population:,} чел.\n\n"
                f"Используйте /stats для просмотра полной информации о вашей стране.\n"
                f"Используйте /start для просмотра доступных команд.",
                parse_mode="HTML",
            )
        else:
            # Create new player
            username = message.from_user.username
            display_name = message.from_user.full_name or f"Player_{user_id}"

            await game_engine.create_player(
                game_id=game_id,
                telegram_id=user_id,
                username=username,
                display_name=display_name,
                country_id=country.id,
                role=PlayerRole.PLAYER,
            )

            # Delete the example entry
            await game_engine.db.delete(example)
            await game_engine.db.commit()

            await message.answer(
                f"🎉 <b>Поздравляем с регистрацией!</b>\n\n"
                f"Вы выбрали страну <b>{escape_html(country.name)}</b>!\n\n"
                f"<b>Столица:</b> {escape_html(country.capital or 'Не указана')}\n"
                f"<b>Население:</b> {country.population:,} чел.\n\n"
                f"Используйте /stats для просмотра полной информации о вашей стране.\n"
                f"Используйте /start для просмотра доступных команд.",
                parse_mode="HTML",
            )

        # Notify admin about the selection
        from wpg_engine.config.settings import settings

        target_chat_id = None
        if settings.telegram.is_admin_chat():
            target_chat_id = settings.telegram.admin_id
        else:
            # Find admins
            result = await game_engine.db.execute(
                select(Player)
                .where(Player.game_id == game_id)
                .where(Player.role == PlayerRole.ADMIN)
            )
            admins = result.scalars().all()
            if admins:
                import random

                admin = random.choice(admins)
                target_chat_id = admin.telegram_id

        if target_chat_id:
            try:
                bot = message.bot
                await bot.send_message(
                    target_chat_id,
                    f"ℹ️ <b>Игрок выбрал страну из примеров</b>\n\n"
                    f"<b>Игрок:</b> {escape_html(display_name or message.from_user.full_name)}\n"
                    f"<b>Username:</b> @{escape_html(message.from_user.username or 'не указан')}\n"
                    f"<b>Telegram ID:</b> <code>{user_id}</code>\n\n"
                    f"<b>Выбранная страна:</b> {escape_html(country.name)}\n"
                    f"<b>Столица:</b> {escape_html(country.capital or 'Не указана')}\n"
                    f"<b>Население:</b> {country.population:,} чел.",
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.warning(
                    f"⚠️ Не удалось уведомить админа о выборе примера: {type(e).__name__}: {e}"
                )

    except Exception as e:
        logger.error(f"❌ Ошибка при обработке выбора примера: {type(e).__name__}: {e}")
        logger.exception("Full traceback:")
        await message.answer(
            "❌ Произошла ошибка при выборе страны. Попробуйте еще раз или обратитесь к администратору."
        )


async def handle_registration_decision(
    message: Message, admin: Player, game_engine: GameEngine, decision: str
) -> None:
    """Handle admin decision on registration"""
    # Extract player telegram ID from the replied message
    replied_text = message.reply_to_message.text

    # Find telegram ID in the message
    import re

    telegram_id_match = re.search(r"Telegram ID:\s*(\d+)", replied_text)
    if not telegram_id_match:
        await message.answer("❌ Не удалось найти Telegram ID в сообщении.")
        return

    player_telegram_id = int(telegram_id_match.group(1))

    # Find the player
    result = await game_engine.db.execute(
        select(Player)
        .options(selectinload(Player.country))
        .where(Player.telegram_id == player_telegram_id)
        .where(Player.game_id == admin.game_id)
    )
    player = result.scalar_one_or_none()

    if not player:
        await message.answer("❌ Игрок не найден.")
        return

    try:
        bot = message.bot

        if decision == "одобрить":
            # Approve registration - player is already created, just notify
            await bot.send_message(
                player_telegram_id,
                f"🎉 <b>Поздравляем!</b>\n\n"
                f"Ваша регистрация в игре одобрена!\n"
                f"Вы управляете страной <b>{escape_html(player.country.name)}</b>.\n\n"
                f"Используйте /start для просмотра доступных команд.",
                parse_mode="HTML",
            )

            await message.answer(
                f"✅ <b>Регистрация одобрена!</b>\n\n"
                f"Игрок <b>{escape_html(player.display_name)}</b> теперь может участвовать в игре "
                f"за страну <b>{escape_html(player.country.name)}</b>.",
                parse_mode="HTML",
            )

        elif decision == "отклонить":
            # Extract rejection reason from the message
            rejection_reason = ""
            message_text = message.text.strip()
            if message_text.lower().startswith("отклонить "):
                rejection_reason = message_text[
                    10:
                ].strip()  # Remove "отклонить " prefix

            # Reject registration - delete player and country
            country_name = player.country.name if player.country else "без страны"
            player_name = player.display_name

            # First, delete all messages associated with this player to avoid foreign key constraint violations
            from wpg_engine.models import Message

            result = await game_engine.db.execute(
                select(Message).where(Message.player_id == player.id)
            )
            messages = result.scalars().all()
            for message in messages:
                await game_engine.db.delete(message)

            # Then delete country and player
            if player.country:
                await game_engine.db.delete(player.country)
            await game_engine.db.delete(player)
            await game_engine.db.commit()

            # Prepare rejection message for player
            rejection_message = (
                "❌ <b>Регистрация отклонена</b>\n\n"
                "К сожалению, ваша заявка на участие в игре была отклонена администратором."
            )

            if rejection_reason:
                rejection_message += (
                    f"\n\n<b>Причина отклонения:</b>\n{escape_html(rejection_reason)}"
                )

            rejection_message += "\n\nВы можете попробовать зарегистрироваться снова с помощью команды /register."

            await bot.send_message(
                player_telegram_id,
                rejection_message,
                parse_mode="HTML",
            )

            # Prepare confirmation message for admin
            admin_message = (
                f"❌ <b>Регистрация отклонена</b>\n\n"
                f"Заявка игрока <b>{escape_html(player_name)}</b> ({escape_html(country_name)}) отклонена и удалена."
            )

            if rejection_reason:
                admin_message += (
                    f"\n\n<b>Указанная причина:</b>\n{escape_html(rejection_reason)}"
                )

            await message.answer(admin_message, parse_mode="HTML")

    except Exception as e:
        await message.answer(f"❌ Не удалось уведомить игрока: {e}")


def register_message_handlers(dp: Dispatcher) -> None:
    """Register message handlers"""
    # Handle all text messages that are not commands
    dp.message.register(
        handle_text_message,
        lambda message: message.text and not message.text.startswith("/"),
    )
