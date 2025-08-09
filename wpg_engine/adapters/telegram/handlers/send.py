"""
Send message handlers for inter-country communication
"""

from aiogram import Dispatcher
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from wpg_engine.adapters.telegram.utils import escape_html
from wpg_engine.core.engine import GameEngine
from wpg_engine.models import Player, get_db


class SendStates(StatesGroup):
    """Send message states"""

    waiting_for_message = State()


async def send_command(message: Message, state: FSMContext) -> None:
    """Handle /send command - select target country"""
    user_id = message.from_user.id
    args = message.text.split(" ", 1)  # /send [country_name]

    async for db in get_db():
        game_engine = GameEngine(db)

        # Get sender player
        result = await game_engine.db.execute(
            select(Player)
            .options(selectinload(Player.country), selectinload(Player.game))
            .where(Player.telegram_id == user_id)
        )
        sender = result.scalar_one_or_none()
        break

    if not sender:
        await message.answer("❌ Вы не зарегистрированы в игре. Используйте /register для регистрации.")
        return

    if not sender.country:
        await message.answer("❌ Вам не назначена страна. Обратитесь к администратору.")
        return

    # Get all countries in the same game
    async for db in get_db():
        game_engine = GameEngine(db)

        result = await game_engine.db.execute(
            select(Player)
            .options(selectinload(Player.country))
            .where(Player.game_id == sender.game_id)
            .where(Player.country_id.isnot(None))
        )
        all_players = result.scalars().all()
        break

    # Get available countries (excluding own country)
    available_countries = []
    for player in all_players:
        if player.country and player.country.id != sender.country_id:
            available_countries.append(player.country.name)

    if not available_countries:
        await message.answer("❌ В игре нет других стран для отправки сообщений.")
        return

    # Check if country name was provided
    if len(args) > 1:
        target_country_name = args[1].strip()

        # Find target country (case-insensitive search by name and synonyms)
        target_player = None
        for player in all_players:
            if player.country:
                # Check official name
                if player.country.name.lower() == target_country_name.lower():
                    target_player = player
                    break

                # Check synonyms
                if player.country.synonyms:
                    for synonym in player.country.synonyms:
                        if synonym.lower() == target_country_name.lower():
                            target_player = player
                            break
                    if target_player:
                        break

        if not target_player:
            countries_list = "\n".join([f"• {country}" for country in sorted(available_countries)])
            await message.answer(
                f"❌ Страна '{escape_html(target_country_name)}' не найдена.\n\n"
                f"Доступные страны для отправки сообщений:\n{countries_list}\n\n"
                f"Используйте: <code>/send название_страны</code>",
                parse_mode="HTML",
            )
            return

        # Check if trying to send to own country
        if target_player.country_id == sender.country_id:
            await message.answer("❌ Нельзя отправлять сообщения самому себе.")
            return

        # Store target country and ask for message
        await state.update_data(target_player_id=target_player.id, target_country_name=target_player.country.name)
        await message.answer(
            f"📨 <b>Отправка сообщения в страну {escape_html(target_player.country.name)}</b>\n\n"
            f"Введите ваше сообщение:",
            parse_mode="HTML",
        )
        await state.set_state(SendStates.waiting_for_message)
    else:
        # Show available countries
        countries_list = "\n".join([f"• {country}" for country in sorted(available_countries)])
        await message.answer(
            f"📨 <b>Отправка сообщения другой стране</b>\n\n"
            f"Доступные страны для отправки сообщений:\n{countries_list}\n\n"
            f"Используйте: <code>/send название_страны</code>\n\n"
            f"Пример: <code>/send Административная Республика</code>",
            parse_mode="HTML",
        )


async def process_message_content(message: Message, state: FSMContext) -> None:
    """Process message content and send to target country"""
    message_content = message.text.strip()

    # Validate message content
    if len(message_content) < 3:
        await message.answer("❌ Сообщение слишком короткое (минимум 3 символа). Попробуйте еще раз:")
        return

    if len(message_content) > 1000:
        await message.answer("❌ Сообщение слишком длинное (максимум 1000 символов). Попробуйте еще раз:")
        return

    # Get stored data
    data = await state.get_data()
    target_player_id = data.get("target_player_id")
    target_country_name = data.get("target_country_name")

    if not target_player_id:
        await message.answer("❌ Ошибка: не найдена информация о получателе. Начните заново с /send")
        await state.clear()
        return

    user_id = message.from_user.id

    async for db in get_db():
        game_engine = GameEngine(db)

        # Get sender player
        result = await game_engine.db.execute(
            select(Player)
            .options(selectinload(Player.country), selectinload(Player.game))
            .where(Player.telegram_id == user_id)
        )
        sender = result.scalar_one_or_none()

        # Get target player
        result = await game_engine.db.execute(
            select(Player).options(selectinload(Player.country)).where(Player.id == target_player_id)
        )
        target_player = result.scalar_one_or_none()
        break

    if not sender or not target_player:
        await message.answer("❌ Ошибка: не найдена информация об отправителе или получателе.")
        await state.clear()
        return

    # Send message to target player
    try:
        bot = message.bot

        # Format message for recipient
        recipient_message = (
            f"📨 <b>Вам пришло послание из страны {escape_html(sender.country.name)}</b>\n\n"
            f"<b>Сообщение:</b>\n{escape_html(message_content)}\n\n"
            f"<i>Для ответа используйте:</i> <code>/send {escape_html(sender.country.name)}</code>"
        )

        await bot.send_message(
            target_player.telegram_id,
            recipient_message,
            parse_mode="HTML",
        )

        # Confirm to sender
        await message.answer(
            f"✅ <b>Сообщение отправлено!</b>\n\n"
            f"<b>Получатель:</b> {escape_html(target_country_name)}\n"
            f"<b>Ваше сообщение:</b>\n{escape_html(message_content)}",
            parse_mode="HTML",
        )

        # Save message to database for history
        async for db in get_db():
            game_engine = GameEngine(db)

            # Create a record of the inter-country message
            await game_engine.create_message(
                player_id=sender.id,
                game_id=sender.game_id,
                content=f"[ОТПРАВЛЕНО В {target_country_name.upper()}] {message_content}",
                telegram_message_id=message.message_id,
                is_admin_reply=False,
            )
            break

    except Exception as e:
        print(f"Failed to send inter-country message: {e}")
        await message.answer(
            f"❌ Не удалось доставить сообщение в страну {escape_html(target_country_name)}. "
            f"Возможно, игрок не начинал диалог с ботом."
        )

    # Clear state
    await state.clear()


def register_send_handlers(dp: Dispatcher) -> None:
    """Register send handlers"""
    dp.message.register(send_command, Command("send"))
    dp.message.register(process_message_content, SendStates.waiting_for_message)
