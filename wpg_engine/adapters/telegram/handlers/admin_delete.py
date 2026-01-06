"""
Admin delete commands
"""

import logging

from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from wpg_engine.adapters.telegram.utils import escape_html
from wpg_engine.core.admin_utils import get_admin_player, is_admin
from wpg_engine.core.engine import GameEngine
from wpg_engine.models import Country, Player, PlayerRole, get_db

from .admin_utils import (
    AdminStates,
    extract_country_from_reply,
    find_target_country_by_name,
)

logger = logging.getLogger(__name__)


async def delete_country_command(message: Message, state: FSMContext) -> None:
    """Handle /delete_country command"""
    user_id = message.from_user.id
    args = message.text.split(" ", 1)  # /delete_country [country_name]

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

        # Get all countries in the same game (both linked and orphaned)
        result = await game_engine.db.execute(
            select(Country).where(Country.game_id == admin.game_id)
        )
        all_countries = result.scalars().all()

        if not all_countries:
            await message.answer("❌ В игре нет стран для удаления.")
            return

        # Build list of available countries
        available_countries = [country.name for country in all_countries]

        # Check if this is a reply to a message with country information
        target_country = None
        target_country_name = None

        # Try to extract country from reply message
        reply_result = await extract_country_from_reply(message, all_countries)
        if reply_result:
            target_country, target_country_name = reply_result

        # If no country found from reply, check if country name was provided in command
        if not target_country and len(args) > 1:
            target_country_name = args[1].strip()
            target_country = await find_target_country_by_name(
                all_countries, target_country_name
            )

            if not target_country:
                countries_list = "\n".join(
                    [f"• {country}" for country in sorted(available_countries)]
                )
                await message.answer(
                    f"❌ Страна '{escape_html(target_country_name)}' не найдена.\n\n"
                    f"Доступные страны:\n{countries_list}\n\n"
                    f"Используйте: <code>/delete_country название_страны</code>",
                    parse_mode="HTML",
                )
                return

        if not target_country:
            countries_list = "\n".join(
                [f"• {country}" for country in sorted(available_countries)]
            )
            await message.answer(
                f"❌ Укажите название страны для удаления.\n\n"
                f"Доступные страны:\n{countries_list}\n\n"
                f"Используйте: <code>/delete_country название_страны</code>",
                parse_mode="HTML",
            )
            return

        # Find player linked to this country (if exists)
        result = await game_engine.db.execute(
            select(Player).where(Player.country_id == target_country.id).limit(1)
        )
        linked_player = result.scalar_one_or_none()

        # Store data for confirmation
        state_data = {
            "target_country_id": target_country.id,
            "target_country_name": target_country.name,
        }

        if linked_player:
            state_data["target_player_id"] = linked_player.id
            state_data["target_telegram_id"] = linked_player.telegram_id

        await state.update_data(**state_data)

        # Build confirmation message based on whether country has a player
        if linked_player:
            player_info = f"👤 <b>Игрок:</b> {escape_html(linked_player.display_name or linked_player.username or 'Неизвестно')}\n"
            consequences = (
                "• Страна будет удалена навсегда\n"
                "• Игрок потеряет свою страну\n"
                "• Все данные страны будут потеряны\n"
            )
        else:
            player_info = "👤 <b>Игрок:</b> <i>Отсутствует (orphaned country)</i>\n"
            consequences = (
                "• Страна будет удалена навсегда\n• Все данные страны будут потеряны\n"
            )

        # Show different message if country was auto-detected from reply
        reply_note = ""
        if message.reply_to_message:
            reply_note = "<i>(автоматически определено из сообщения)</i>\n\n"

        await message.answer(
            f"⚠️ <b>ВНИМАНИЕ! ОПАСНАЯ ОПЕРАЦИЯ!</b>\n\n"
            f"Вы собираетесь <b>ПОЛНОСТЬЮ УДАЛИТЬ</b> страну:\n\n"
            f"🏛️ <b>{escape_html(target_country.name)}</b>\n"
            f"{player_info}"
            f"{reply_note}"
            f"<b>ЭТО ДЕЙСТВИЕ НЕОБРАТИМО!</b>\n"
            f"{consequences}\n"
            f"Вы <b>ДЕЙСТВИТЕЛЬНО</b> хотите удалить эту страну?\n\n"
            f"Напишите <b>УДАЛИТЬ</b> (заглавными буквами), чтобы продолжить, или любое другое сообщение для отмены.",
            parse_mode="HTML",
        )

        await state.set_state(AdminStates.waiting_for_delete_country_confirmation)


async def process_delete_country_confirmation(
    message: Message, state: FSMContext
) -> None:
    """Process confirmation for country deletion"""
    confirmation = message.text.strip()

    if confirmation != "УДАЛИТЬ":
        await message.answer("❌ Удаление страны отменено.")
        await state.clear()
        return

    # Get stored data
    data = await state.get_data()
    target_country_id = data["target_country_id"]
    target_country_name = data["target_country_name"]
    target_player_id = data.get(
        "target_player_id"
    )  # May be None for orphaned countries

    user_id = message.from_user.id

    async with get_db() as db:
        game_engine = GameEngine(db)

        # Check if user is still admin
        if not await is_admin(user_id, game_engine.db, message.chat.id):
            await message.answer("❌ У вас нет прав администратора.")
            await state.clear()
            return

        # Get admin player
        admin = await get_admin_player(user_id, game_engine.db)

        if not admin:
            await message.answer("❌ Администратор не найден в игре.")
            await state.clear()
            return

        # Verify the country still exists
        country = await game_engine.get_country(target_country_id)
        if not country:
            await message.answer("❌ Страна уже была удалена или не существует.")
            await state.clear()
            return

        # If country has a player, ask for final message
        if target_player_id:
            await state.update_data(admin_id=admin.id)
            await message.answer(
                f"💬 <b>Последнее слово</b>\n\n"
                f"Перед удалением страны <b>{escape_html(target_country_name)}</b> вы можете отправить игроку последнее сообщение.\n\n"
                f"Введите текст сообщения или напишите <code>skip</code>, чтобы пропустить:",
                parse_mode="HTML",
            )
            await state.set_state(AdminStates.waiting_for_final_message)
        else:
            # Orphaned country - delete immediately without asking for message
            await message.answer(
                f"🔄 Удаляю страну <b>{escape_html(target_country_name)}</b> (без игрока)...",
                parse_mode="HTML",
            )

            # Delete the country
            success = await game_engine.delete_country(target_country_id)

            if success:
                await message.answer(
                    f"✅ <b>Страна успешно удалена!</b>\n\n"
                    f"🏛️ {escape_html(target_country_name)}\n\n"
                    f"<i>Orphaned country была удалена из базы данных.</i>",
                    parse_mode="HTML",
                )
            else:
                await message.answer(
                    "❌ Не удалось удалить страну. Возможно, она уже была удалена."
                )

            await state.clear()


async def process_final_message(message: Message, state: FSMContext) -> None:
    """Process final message and delete country"""
    final_message_text = message.text.strip()

    # Get stored data
    data = await state.get_data()
    target_country_id = data["target_country_id"]
    target_country_name = data["target_country_name"]
    admin_id = data["admin_id"]

    # These may not exist for orphaned countries
    target_player_id = data.get("target_player_id")
    target_telegram_id = data.get("target_telegram_id")

    user_id = message.from_user.id

    async with get_db() as db:
        game_engine = GameEngine(db)

        # Check if user is still admin
        if not await is_admin(user_id, game_engine.db, message.chat.id):
            await message.answer("❌ У вас нет прав администратора.")
            await state.clear()
            return

        # Get admin info by ID (stored earlier)
        result = await game_engine.db.execute(
            select(Player).where(Player.id == admin_id)
        )
        admin = result.scalar_one_or_none()

        if not admin:
            await message.answer("❌ Ошибка: администратор не найден.")
            await state.clear()
            return

        # Verify the country still exists
        country = await game_engine.get_country(target_country_id)
        if not country:
            await message.answer("❌ Страна уже была удалена или не существует.")
            await state.clear()
            return

        # Send final message to player if provided and player exists
        if (
            target_player_id
            and target_telegram_id
            and final_message_text.lower() != "skip"
            and len(final_message_text) >= 3
        ):
            if len(final_message_text) > 4096:
                await message.answer(
                    "❌ Сообщение слишком длинное (максимум 4096 символов). Попробуйте еще раз или напишите <code>skip</code> для пропуска:",
                    parse_mode="HTML",
                )
                return

            try:
                bot = message.bot
                final_message = (
                    f"📢 <b>Сообщение от администратора</b>\n\n"
                    f"{escape_html(final_message_text)}\n\n"
                    f"<i>Ваша страна {escape_html(target_country_name)} была удалена из игры.</i>"
                )

                await bot.send_message(
                    target_telegram_id,
                    final_message,
                    parse_mode="HTML",
                )

                # Save the admin message to database for RAG context
                await game_engine.create_message(
                    player_id=target_player_id,
                    game_id=admin.game_id,
                    content=final_message_text,
                    is_admin_reply=True,
                )

                await message.answer("✅ Последнее сообщение отправлено игроку.")
            except Exception as e:
                logger.error(
                    f"❌ Не удалось отправить финальное сообщение игроку {data['target_telegram_id']}: {type(e).__name__}: {e}"
                )
                await message.answer(
                    "⚠️ Не удалось отправить сообщение игроку, но удаление продолжается..."
                )

        # Delete the country
        success = await game_engine.delete_country(target_country_id)

        if success:
            # Check if there was a player assigned to this country
            player_message = ""
            if data.get("target_telegram_id"):
                player_message = (
                    "👤 <b>Игрок:</b> освобожден от страны\n\n"
                    "Игрок может теперь зарегистрировать новую страну командой /register"
                )
            else:
                player_message = "👤 <b>Игрок:</b> страна не была привязана к игроку"

            await message.answer(
                f"✅ <b>Страна успешно удалена!</b>\n\n"
                f"🏛️ <b>Удаленная страна:</b> {escape_html(target_country_name)}\n"
                f"{player_message}",
                parse_mode="HTML",
            )
        else:
            await message.answer(
                "❌ Не удалось удалить страну. Возможно, она уже была удалена."
            )

    await state.clear()


async def delete_user_command(message: Message, state: FSMContext) -> None:
    """Handle /delete_user command - delete player and all related data"""
    user_id = message.from_user.id

    async with get_db() as db:
        game_engine = GameEngine(db)

        # Check if user is admin
        if not await is_admin(user_id, game_engine.db, message.chat.id):
            await message.answer("❌ У вас нет прав администратора.")
            return

        # Parse username from command
        command_text = message.text.strip()
        parts = command_text.split(maxsplit=1)

        if len(parts) < 2:
            await message.answer(
                "❌ <b>Неверный формат команды!</b>\n\n"
                "<b>Использование:</b>\n"
                "/delete_user @username\n"
                "/delete_user username\n\n"
                "<b>Примеры:</b>\n"
                "/delete_user @john_doe\n"
                "/delete_user john_doe",
                parse_mode="HTML",
            )
            return

        # Extract username (remove @ if present)
        username = parts[1].strip().lstrip("@")

        if not username:
            await message.answer("❌ Необходимо указать имя пользователя.")
            return

        # Find player by username
        result = await game_engine.db.execute(
            select(Player)
            .options(selectinload(Player.country), selectinload(Player.game))
            .where(Player.username == username)
            .limit(1)
        )
        target_player = result.scalar_one_or_none()

        if not target_player:
            await message.answer(
                f"❌ Пользователь с именем <code>@{escape_html(username)}</code> не найден в базе данных.",
                parse_mode="HTML",
            )
            return

        # Check if trying to delete admin
        if target_player.role == PlayerRole.ADMIN:
            await message.answer(
                f"❌ Нельзя удалить администратора!\n\n"
                f"<b>Пользователь:</b> @{escape_html(username)}\n"
                f"<b>Роль:</b> {escape_html(target_player.role)}",
                parse_mode="HTML",
            )
            return

        # Prepare info message
        info_parts = [
            "⚠️ <b>УДАЛЕНИЕ ПОЛЬЗОВАТЕЛЯ</b>\n",
            f"<b>Пользователь:</b> @{escape_html(username)}",
        ]

        if target_player.display_name:
            info_parts.append(f"<b>Имя:</b> {escape_html(target_player.display_name)}")

        if target_player.telegram_id:
            info_parts.append(f"<b>Telegram ID:</b> {target_player.telegram_id}")

        if target_player.country:
            info_parts.append(
                f"<b>Страна:</b> {escape_html(target_player.country.name)}"
            )

        if target_player.game:
            info_parts.append(f"<b>Игра:</b> {escape_html(target_player.game.name)}")

        info_parts.append(
            "\n<b>⚠️ ВНИМАНИЕ!</b> Будут удалены:\n"
            "• Игрок и его данные\n"
            "• Все сообщения игрока\n"
            "• Все посты игрoka\n"
            "• Все вердикты, если игрок был админом\n"
            "• Привязка к стране (страна останется без игрока)\n"
        )

        info_parts.append(
            "\n<b>Для подтверждения напишите:</b> <code>УДАЛИТЬ</code>\n"
            "<b>Для отмены напишите:</b> <code>ОТМЕНА</code>"
        )

        await message.answer("\n".join(info_parts), parse_mode="HTML")

        # Store data for confirmation
        await state.update_data(
            target_player_id=target_player.id,
            target_username=username,
            admin_id=user_id,
        )
        await state.set_state(AdminStates.waiting_for_delete_user_confirmation)


async def process_delete_user_confirmation(message: Message, state: FSMContext) -> None:
    """Process user deletion confirmation"""
    user_id = message.from_user.id
    confirmation = message.text.strip().upper()

    async with get_db() as db:
        game_engine = GameEngine(db)

        # Check if user is still admin
        if not await is_admin(user_id, game_engine.db, message.chat.id):
            await message.answer("❌ У вас нет прав администратора.")
            await state.clear()
            return

        if confirmation == "ОТМЕНА":
            await message.answer("✅ Удаление отменено.")
            await state.clear()
            return

        if confirmation != "УДАЛИТЬ":
            await message.answer(
                "❌ Неверное подтверждение. Напишите <code>УДАЛИТЬ</code> для подтверждения или <code>ОТМЕНА</code> для отмены.",
                parse_mode="HTML",
            )
            return

        # Get stored data
        data = await state.get_data()
        target_player_id = data.get("target_player_id")
        target_username = data.get("target_username")

        if not target_player_id:
            await message.answer("❌ Ошибка: данные игрока не найдены.")
            await state.clear()
            return

        # Get player with all related data
        result = await game_engine.db.execute(
            select(Player)
            .options(
                selectinload(Player.country),
                selectinload(Player.game),
                selectinload(Player.messages),
                selectinload(Player.posts),
                selectinload(Player.verdicts),
            )
            .where(Player.id == target_player_id)
        )
        target_player = result.scalar_one_or_none()

        if not target_player:
            await message.answer("❌ Игрок не найден или уже был удален.")
            await state.clear()
            return

        # Count related data
        messages_count = len(target_player.messages)
        posts_count = len(target_player.posts)
        verdicts_count = len(target_player.verdicts)

        try:
            # Delete the player (cascade will delete related data)
            await game_engine.db.delete(target_player)
            await game_engine.db.commit()

            await message.answer(
                f"✅ <b>Пользователь успешно удален!</b>\n\n"
                f"<b>Пользователь:</b> @{escape_html(target_username)}\n"
                f"<b>Удалено данных:</b>\n"
                f"• Сообщений: {messages_count}\n"
                f"• Постов: {posts_count}\n"
                f"• Вердиктов: {verdicts_count}",
                parse_mode="HTML",
            )
        except Exception as e:
            await game_engine.db.rollback()
            await message.answer(
                f"❌ Ошибка при удалении пользователя: {escape_html(str(e))}",
                parse_mode="HTML",
            )

    await state.clear()
