"""
Admin event commands
"""

from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from wpg_engine.adapters.telegram.utils import escape_html
from wpg_engine.core.admin_utils import get_admin_player, is_admin
from wpg_engine.core.engine import GameEngine
from wpg_engine.models import Player, PlayerRole, get_db

from .admin_utils import (
    AdminStates,
    extract_country_from_reply,
    find_target_player_by_country_name,
    send_message_to_players,
)


async def event_command(message: Message, state: FSMContext) -> None:
    """Handle /event command - send event message to players"""
    user_id = message.from_user.id
    args = message.text.split(" ", 1)  # /event [country_name]

    async with get_db() as db:
        game_engine = GameEngine(db)

        # Check if user is admin
        if not await is_admin(user_id, game_engine.db, message.chat.id):
            await message.answer("❌ У вас нет прав администратора.")
            return

        # Get admin player (works for both admin chat and admin user)
        admin = await get_admin_player(user_id, game_engine.db)

        if not admin:
            await message.answer(
                "❌ В игре нет зарегистрированных администраторов. Создайте игру с помощью /restart_game"
            )
            return

        # Get all countries in the same game
        result = await game_engine.db.execute(
            select(Player)
            .options(selectinload(Player.country))
            .where(Player.game_id == admin.game_id)
            .where(Player.country_id.isnot(None))
            .where(Player.role == PlayerRole.PLAYER)
        )
        all_players = result.scalars().all()

    # Get available countries
    available_countries = []
    for player in all_players:
        if player.country:
            available_countries.append(player.country.name)

    if not available_countries:
        await message.answer("❌ В игре нет стран для отправки сообщений.")
        return

    # Check if this is a reply to a message with country information
    target_player = None
    target_country_name = None

    # Try to extract country from reply message
    reply_result = await extract_country_from_reply(message, all_players)
    if reply_result:
        target_player, target_country_name = reply_result

    # If no country found from reply, check if country name was provided in command
    if not target_player and len(args) > 1:
        target_country_name = args[1].strip()
        target_player = await find_target_player_by_country_name(
            all_players, target_country_name
        )

        if not target_player:
            countries_list = "\n".join(
                [f"• {country}" for country in sorted(available_countries)]
            )
            await message.answer(
                f"❌ Страна '{escape_html(target_country_name)}' не найдена.\n\n"
                f"Доступные страны:\n{countries_list}\n\n"
                f"Используйте: <code>/event название_страны</code> или <code>/event</code> для всех",
                parse_mode="HTML",
            )
            return

    if target_player:
        # Store target country and ask for message
        await state.update_data(
            target_player_id=target_player.id,
            target_country_name=target_player.country.name,
        )

        # Show different message if country was auto-detected from reply
        if message.reply_to_message:
            await message.answer(
                f"📢 <b>Отправка события в страну {escape_html(target_player.country.name)}</b>\n"
                f"<i>(автоматически определено из сообщения)</i>\n\n"
                f"Введите текст события или напишите <code>cancel</code> для отмены:",
                parse_mode="HTML",
            )
        else:
            await message.answer(
                f"📢 <b>Отправка события в страну {escape_html(target_player.country.name)}</b>\n\n"
                f"Введите текст события или напишите <code>cancel</code> для отмены:",
                parse_mode="HTML",
            )
        await state.set_state(AdminStates.waiting_for_event_message)
    else:
        # Send to all countries
        await state.update_data(target_player_id=None, target_country_name="все страны")
        await message.answer(
            "📢 <b>Отправка события всем странам</b>\n\n"
            "Введите текст события или напишите <code>cancel</code> для отмены:",
            parse_mode="HTML",
        )
        await state.set_state(AdminStates.waiting_for_event_message)


async def process_event_message(message: Message, state: FSMContext) -> None:
    """Process event message content and send to target(s)"""
    message_content = message.text.strip()

    # Check for cancel command
    if message_content.lower() == "cancel":
        await message.answer("❌ Отправка события отменена.")
        await state.clear()
        return

    # Validate message content
    if len(message_content) < 3:
        await message.answer(
            "❌ Сообщение слишком короткое (минимум 3 символа). Попробуйте еще раз или напишите <code>cancel</code> для отмены:",
            parse_mode="HTML",
        )
        return

    if len(message_content) > 4096:
        await message.answer(
            "❌ Сообщение слишком длинное (максимум 4096 символов). Попробуйте еще раз или напишите <code>cancel</code> для отмены:",
            parse_mode="HTML",
        )
        return

    # Get stored data
    data = await state.get_data()
    target_player_id = data.get("target_player_id")
    target_country_name = data.get("target_country_name")

    user_id = message.from_user.id

    async with get_db() as db:
        game_engine = GameEngine(db)

        # Get admin player (works for both admin chat and admin user)
        admin = await get_admin_player(user_id, game_engine.db)

        if not admin:
            await message.answer("❌ Ошибка: администратор не найден в игре.")
            await state.clear()
            return

        bot = message.bot
        sent_count = 0
        failed_count = 0

        if target_player_id:
            # Send to specific country
            result = await game_engine.db.execute(
                select(Player)
                .options(selectinload(Player.country))
                .where(Player.id == target_player_id)
            )
            target_player = result.scalar_one_or_none()

            if target_player:
                sent_count, failed_count = await send_message_to_players(
                    bot, game_engine, [target_player], message_content, admin.game_id
                )
        else:
            # Send to all countries
            result = await game_engine.db.execute(
                select(Player)
                .where(Player.game_id == admin.game_id)
                .where(Player.role == PlayerRole.PLAYER)
            )
            players = result.scalars().all()

            sent_count, failed_count = await send_message_to_players(
                bot, game_engine, players, message_content, admin.game_id
            )

        # Send confirmation to admin
        if target_player_id:
            if failed_count == 0:
                await message.answer(
                    f"✅ Событие отправлено в страну {escape_html(target_country_name)}!"
                )
            else:
                await message.answer(
                    f"❌ Не удалось отправить событие в страну {escape_html(target_country_name)}."
                )
        else:
            if failed_count == 0:
                await message.answer(
                    f"✅ Событие отправлено всем странам ({sent_count} получателей)!"
                )
            else:
                await message.answer(
                    f"⚠️ Событие отправлено {sent_count} странам. "
                    f"Не удалось отправить {failed_count} странам."
                )

    # Clear state
    await state.clear()
