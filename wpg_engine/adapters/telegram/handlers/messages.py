"""
Message handlers for player-admin communication
"""

from aiogram import Dispatcher
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from wpg_engine.adapters.telegram.utils import escape_html, escape_markdown
from wpg_engine.core.admin_utils import is_admin
from wpg_engine.core.engine import GameEngine
from wpg_engine.models import Player, PlayerRole, get_db


async def handle_text_message(message: Message) -> None:
    """Handle all text messages that are not commands"""
    user_id = message.from_user.id
    content = message.text.strip()

    # Skip if message is too short or too long
    if len(content) < 3:
        await message.answer("❌ Сообщение слишком короткое (минимум 3 символа).")
        return

    if len(content) > 2000:
        await message.answer("❌ Сообщение слишком длинное (максимум 2000 символов).")
        return

    async for db in get_db():
        game_engine = GameEngine(db)

        # Get player
        result = await game_engine.db.execute(
            select(Player)
            .options(selectinload(Player.country), selectinload(Player.game))
            .where(Player.telegram_id == user_id)
        )
        player = result.scalar_one_or_none()

        if not player:
            await message.answer("❌ Вы не зарегистрированы в игре. Используйте /start для начала работы с ботом.")
            return

        # Check if this is an admin replying to a message or sending a message with ID
        if await is_admin(user_id, game_engine.db):
            # Check if this is a reply to a message (for registration decisions)
            if message.reply_to_message:
                await handle_admin_reply(message, player, game_engine)
                return
            # Check if message contains message ID for direct reply
            import re

            if re.search(r"(?:ID сообщения|msg|message):\s*\d+|^\d+\s+", content, re.IGNORECASE):
                await handle_admin_reply(message, player, game_engine)
                return

        # Regular player message - send to admin
        await handle_player_message(message, player, game_engine)
        break


async def handle_player_message(message: Message, player: Player, game_engine: GameEngine) -> None:
    """Handle message from player - save and forward to admin"""
    content = message.text.strip()

    # Confirm to player
    await message.answer("✅ Сообщение отправлено администратору!")

    # Find admin to send message to
    result = await game_engine.db.execute(
        select(Player).where(Player.game_id == player.game_id).where(Player.role == PlayerRole.ADMIN)
    )
    admin = result.scalar_one_or_none()

    if admin and admin.telegram_id:
        try:
            # Format message for admin (no ID needed)
            country_name = player.country.name if player.country else "без страны"
            admin_message = (
                f"💬 <b>Новое сообщение от игрока</b>\n\n"
                f"<b>От:</b> {escape_html(player.display_name)} (ID: {player.telegram_id})\n"
                f"<b>Страна:</b> {escape_html(country_name)}\n\n"
                f"<b>Сообщение:</b>\n{escape_html(content)}"
            )

            # Send to admin first
            bot = message.bot
            sent_message = await bot.send_message(admin.telegram_id, admin_message, parse_mode="HTML")

            # Now save message to database with admin's telegram message ID
            await game_engine.create_message(
                player_id=player.id,
                game_id=player.game_id,
                content=content,
                telegram_message_id=message.message_id,
                admin_telegram_message_id=sent_message.message_id,
                is_admin_reply=False,
            )

        except Exception as e:
            print(f"Failed to send message to admin: {e}")
            await message.answer("⚠️ Не удалось отправить сообщение администратору. Попробуйте позже.")
    else:
        await message.answer("⚠️ Администратор не найден в игре.")


async def handle_admin_reply(message: Message, admin: Player, game_engine: GameEngine) -> None:
    """Handle admin reply to player message, registration, or country editing"""
    content = message.text.strip()

    # Check if this is a registration approval/rejection (when replying to registration message)
    if message.reply_to_message and (content.lower() == "одобрить" or content.lower().startswith("отклонить")):
        decision = "одобрить" if content.lower() == "одобрить" else "отклонить"
        await handle_registration_decision(message, admin, game_engine, decision)
        return

    # Check if this is a country editing reply (when replying to country info message)
    if message.reply_to_message and message.reply_to_message.text:
        replied_text = message.reply_to_message.text
        import re

        # Look for country editing marker
        country_match = re.search(r"\[EDIT_COUNTRY:(\d+)\]", replied_text)
        if country_match:
            country_id = int(country_match.group(1))
            await handle_country_edit(message, admin, game_engine, country_id, content)
            return

    # If admin is replying to a message, find the original player message in database
    if not message.reply_to_message:
        await message.answer("❌ Ответьте на сообщение от игрока для отправки ответа.")
        return

    # Find the original player message by the admin message ID that was replied to
    original_message = await game_engine.get_message_by_admin_telegram_id(message.reply_to_message.message_id)

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
                success_messages.append(f"✅ Название изменено на: {escape_html(new_name)}")
            else:
                error_messages.append("❌ Название не может быть пустым")
            continue

        elif line.lower().startswith("описание "):
            new_description = line[9:].strip()
            await game_engine.update_country_basic_info(country_id, description=new_description)
            success_messages.append("✅ Описание страны обновлено")
            continue

        elif line.lower().startswith("столица "):
            new_capital = line[8:].strip()
            await game_engine.update_country_basic_info(country_id, capital=new_capital)
            success_messages.append(f"✅ Столица изменена на: {escape_html(new_capital)}")
            continue

        elif line.lower().startswith("население "):
            try:
                new_population = int(line[10:].strip().replace(",", "").replace(" ", ""))
                await game_engine.update_country_basic_info(country_id, population=new_population)
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
                new_synonyms = [s.strip() for s in synonyms_text.split(",") if s.strip()]
                if new_synonyms:
                    # Check for conflicts with existing countries and their synonyms
                    conflict_found = False
                    from wpg_engine.models import Country

                    result = await game_engine.db.execute(
                        select(Country).where(Country.game_id == country.game_id).where(Country.id != country_id)
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
                        await game_engine.update_country_synonyms(country_id, new_synonyms)
                        escaped_synonyms = [escape_html(syn) for syn in new_synonyms]
                        success_messages.append(f"✅ Синонимы обновлены: {', '.join(escaped_synonyms)}")
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
            result = await game_engine.update_country_aspect_description(country_id, found_aspect, new_description)
            if result:
                success_messages.append(f"✅ Описание аспекта '{key}' обновлено")
            else:
                error_messages.append(f"❌ Не удалось обновить описание аспекта '{key}'")
        else:
            # Try to parse as value update
            try:
                new_value = int(remaining.strip())
                if 1 <= new_value <= 10:
                    result = await game_engine.update_country_aspect_value(country_id, found_aspect, new_value)
                    if result:
                        success_messages.append(f"✅ {key.capitalize()}: {new_value}/10")
                    else:
                        error_messages.append(f"❌ Не удалось обновить {key}")
                else:
                    error_messages.append(f"❌ Значение {key} должно быть от 1 до 10")
            except ValueError:
                error_messages.append(f"❌ Некорректное значение для {key}: {remaining}")

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


async def handle_registration_decision(message: Message, admin: Player, game_engine: GameEngine, decision: str) -> None:
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
                rejection_reason = message_text[10:].strip()  # Remove "отклонить " prefix

            # Reject registration - delete player and country
            country_name = player.country.name if player.country else "без страны"
            player_name = player.display_name

            # Delete player and country
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
                rejection_message += f"\n\n<b>Причина отклонения:</b>\n{escape_html(rejection_reason)}"

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
                admin_message += f"\n\n<b>Указанная причина:</b>\n{escape_html(rejection_reason)}"

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
