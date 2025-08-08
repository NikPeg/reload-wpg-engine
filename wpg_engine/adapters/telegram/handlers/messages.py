"""
Message handlers for player-admin communication
"""

from aiogram import Dispatcher
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.orm import selectinload

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
        break

    if not player:
        await message.answer("❌ Вы не зарегистрированы в игре. Используйте /start для начала работы с ботом.")
        return

    # Check if this is an admin replying to a message
    if await is_admin(user_id, game_engine.db) and message.reply_to_message:
        await handle_admin_reply(message, player, game_engine)
        return

    # Regular player message - send to admin
    await handle_player_message(message, player, game_engine)


async def handle_player_message(message: Message, player: Player, game_engine: GameEngine) -> None:
    """Handle message from player - save and forward to admin"""
    content = message.text.strip()

    # Save message to database
    saved_message = await game_engine.create_message(
        player_id=player.id,
        game_id=player.game_id,
        content=content,
        telegram_message_id=message.message_id,
        is_admin_reply=False,
    )

    # Confirm to player
    await message.answer("✅ Сообщение отправлено администратору!")

    # Find admin to send message to
    result = await game_engine.db.execute(
        select(Player).where(Player.game_id == player.game_id).where(Player.role == PlayerRole.ADMIN)
    )
    admin = result.scalar_one_or_none()

    if admin and admin.telegram_id:
        try:
            # Format message for admin
            country_name = player.country.name if player.country else "без страны"
            admin_message = (
                f"💬 <b>Новое сообщение от игрока</b>\n\n"
                f"<b>От:</b> {player.display_name} (ID: {player.telegram_id})\n"
                f"<b>Страна:</b> {country_name}\n"
                f"<b>Игра:</b> {player.game.name}\n\n"
                f"<b>Сообщение:</b>\n{content}"
            )

            # Send to admin
            bot = message.bot
            sent_message = await bot.send_message(admin.telegram_id, admin_message, parse_mode="HTML")

            # Update saved message with admin's telegram message ID for reply functionality
            saved_message.telegram_message_id = sent_message.message_id
            await game_engine.db.commit()

        except Exception as e:
            print(f"Failed to send message to admin: {e}")
            await message.answer("⚠️ Сообщение сохранено, но не удалось отправить администратору. Попробуйте позже.")
    else:
        await message.answer("⚠️ Сообщение сохранено, но администратор не найден в игре.")


async def handle_admin_reply(message: Message, admin: Player, game_engine: GameEngine) -> None:
    """Handle admin reply to player message or registration"""
    if not message.reply_to_message:
        return

    content = message.text.strip().lower()

    # Check if this is a registration approval/rejection
    if content in ["одобрить", "отклонить"]:
        await handle_registration_decision(message, admin, game_engine, content)
        return

    # Find original message by telegram message ID
    original_message = await game_engine.get_message_by_telegram_id(message.reply_to_message.message_id)

    if not original_message:
        await message.answer("❌ Не удалось найти исходное сообщение.")
        return

    content = message.text.strip()

    # Save admin reply
    await game_engine.create_message(
        player_id=original_message.player_id,
        game_id=original_message.game_id,
        content=content,
        reply_to_id=original_message.id,
        is_admin_reply=True,
    )

    # Send reply to original player
    try:
        bot = message.bot
        reply_text = (
            f"📩 <b>Ответ администратора</b>\n\n"
            f"<b>На ваше сообщение:</b>\n<i>{original_message.content[:100]}{'...' if len(original_message.content) > 100 else ''}</i>\n\n"
            f"<b>Ответ:</b>\n{content}"
        )

        await bot.send_message(original_message.player.telegram_id, reply_text, parse_mode="HTML")

        await message.answer("✅ Ответ отправлен игроку!")

    except Exception as e:
        await message.answer(f"❌ Не удалось отправить ответ игроку: {e}")


async def handle_registration_decision(message: Message, admin: Player, game_engine: GameEngine, decision: str) -> None:
    """Handle admin decision on registration"""
    # Extract player telegram ID from the replied message
    replied_text = message.reply_to_message.text

    # Find telegram ID in the message
    import re

    telegram_id_match = re.search(r"Telegram ID:</b> <code>(\d+)</code>", replied_text)
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
                f"Вы управляете страной <b>{player.country.name}</b>.\n\n"
                f"Используйте /start для просмотра доступных команд.",
                parse_mode="HTML",
            )

            await message.answer(
                f"✅ <b>Регистрация одобрена!</b>\n\n"
                f"Игрок <b>{player.display_name}</b> теперь может участвовать в игре "
                f"за страну <b>{player.country.name}</b>.",
                parse_mode="HTML",
            )

        elif decision == "отклонить":
            # Reject registration - delete player and country
            country_name = player.country.name if player.country else "без страны"
            player_name = player.display_name

            # Delete player and country
            if player.country:
                await game_engine.db.delete(player.country)
            await game_engine.db.delete(player)
            await game_engine.db.commit()

            await bot.send_message(
                player_telegram_id,
                "❌ <b>Регистрация отклонена</b>\n\n"
                "К сожалению, ваша заявка на участие в игре была отклонена администратором.\n"
                "Вы можете попробовать зарегистрироваться снова с помощью команды /register.",
                parse_mode="HTML",
            )

            await message.answer(
                f"❌ <b>Регистрация отклонена</b>\n\n"
                f"Заявка игрока <b>{player_name}</b> ({country_name}) отклонена и удалена.",
                parse_mode="HTML",
            )

    except Exception as e:
        await message.answer(f"❌ Не удалось уведомить игрока: {e}")


def register_message_handlers(dp: Dispatcher) -> None:
    """Register message handlers"""
    # Handle all text messages that are not commands
    dp.message.register(handle_text_message, lambda message: message.text and not message.text.startswith("/"))
