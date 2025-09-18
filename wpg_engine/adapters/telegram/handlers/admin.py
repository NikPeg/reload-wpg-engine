"""
Admin handlers
"""

from aiogram import Dispatcher
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy import select, text
from sqlalchemy.orm import selectinload
from telegramify_markdown import markdownify

from wpg_engine.adapters.telegram.utils import escape_html, escape_markdown
from wpg_engine.core.admin_utils import is_admin
from wpg_engine.core.engine import GameEngine
from wpg_engine.core.rag_system import RAGSystem
from wpg_engine.models import Player, PlayerRole, get_db


class AdminStates(StatesGroup):
    """Admin states"""

    waiting_for_restart_confirmation = State()
    waiting_for_event_message = State()
    waiting_for_gen_action = State()


# Removed admin_command - functionality merged into /start command

# Removed pending_command - registrations are now sent directly to admin


async def game_stats_command(message: Message) -> None:
    """Handle /game_stats command"""
    user_id = message.from_user.id

    async for db in get_db():
        game_engine = GameEngine(db)

        # Check if user is admin
        if not await is_admin(user_id, game_engine.db):
            await message.answer("❌ У вас нет прав администратора.")
            return

        # Get admin info - take the first admin player
        result = await game_engine.db.execute(
            select(Player)
            .where(Player.telegram_id == user_id)
            .where(Player.role == PlayerRole.ADMIN)
            .limit(1)
        )
        admin = result.scalar_one_or_none()

        stats = await game_engine.get_game_statistics(admin.game_id)

        await message.answer(
            f"📊 *Статистика игры*\n\n"
            f"*Название:* {escape_markdown(stats['game_name'])}\n"
            f"*Статус:* {escape_markdown(stats['status'])}\n"
            f"*Стран:* {stats['countries_count']}\n"
            f"*Игроков:* {stats['players_count']}\n"
            f"*Постов:* {stats['posts_count']}\n"
            f"*Создана:* {stats['created_at'].strftime('%d.%m.%Y %H:%M')}\n"
            f"*Обновлена:* {stats['updated_at'].strftime('%d.%m.%Y %H:%M')}",
            parse_mode="Markdown",
        )


async def restart_game_command(message: Message, state: FSMContext) -> None:
    """Handle /restart_game command"""
    user_id = message.from_user.id
    args = message.text.split(" ", 1)

    async for db in get_db():
        game_engine = GameEngine(db)

        # Check if user is admin
        if not await is_admin(user_id, game_engine.db):
            # Check if user is admin from .env
            from wpg_engine.config.settings import settings

            if not settings.telegram.admin_id or user_id != settings.telegram.admin_id:
                await message.answer("❌ У вас нет прав администратора.")
                return

        if len(args) < 2:
            await message.answer(
                "❌ Неверный формат команды.\n\n"
                "Используйте: <code>/restart_game Название игры | Сеттинг | Лет за сутки | Макс очков | Макс население</code>\n\n"
                "Пример: <code>/restart_game Древний мир | Античность | 10 | 30 | 10000000</code>\n"
                "• Макс очков - максимальная сумма очков для аспектов страны (по умолчанию 30)\n"
                "• Макс население - максимальное население страны (по умолчанию 10,000,000)",
                parse_mode="HTML",
            )
            return

        try:
            # Parse arguments
            parts = [part.strip() for part in args[1].split("|")]
            if len(parts) < 3 or len(parts) > 5:
                raise ValueError("Неверное количество параметров")

            game_name, setting, years_per_day_str = parts[:3]
            max_points_str = parts[3] if len(parts) >= 4 else "30"
            max_population_str = parts[4] if len(parts) == 5 else "10000000"

            years_per_day = int(years_per_day_str)
            max_points = int(max_points_str)
            max_population = int(max_population_str)

            if not game_name or not setting:
                raise ValueError("Название игры и сеттинг не могут быть пустыми")

            if years_per_day < 1 or years_per_day > 365:
                raise ValueError("Количество лет за сутки должно быть от 1 до 365")

            if max_points < 10 or max_points > 100:
                raise ValueError(
                    "Максимальное количество очков должно быть от 10 до 100"
                )

            if max_population < 1000 or max_population > 1_000_000_000:
                raise ValueError(
                    "Максимальное население должно быть от 1,000 до 1 млрд"
                )

        except ValueError as e:
            await message.answer(
                f"❌ Ошибка в параметрах: {e}\n\n"
                "Используйте: <code>/restart_game Название игры | Сеттинг | Лет за сутки | Макс очков | Макс население</code>\n\n"
                "Пример: <code>/restart_game Древний мир | Античность | 10 | 30 | 10000000</code>",
                parse_mode="HTML",
            )
            return

        # Store data for confirmation
        await state.update_data(
            user_id=user_id,
            game_name=game_name,
            setting=setting,
            years_per_day=years_per_day,
            max_points=max_points,
            max_population=max_population,
        )

        await message.answer(
            f"⚠️ *ВНИМАНИЕ! ОПАСНАЯ ОПЕРАЦИЯ!*\n\n"
            f"Вы собираетесь *ПОЛНОСТЬЮ ОЧИСТИТЬ* всю базу данных и создать новую игру:\n\n"
            f"*Название:* {escape_markdown(game_name)}\n"
            f"*Сеттинг:* {escape_markdown(setting)}\n"
            f"*Лет за сутки:* {years_per_day}\n"
            f"*Макс очков:* {max_points}\n"
            f"*Макс население:* {max_population:,}\n\n"
            f"*ВСЕ ДАННЫЕ БУДУТ ПОТЕРЯНЫ НАВСЕГДА:*\n"
            f"• Все игры\n"
            f"• Все игроки\n"
            f"• Все страны\n"
            f"• Все сообщения\n"
            f"• Все посты\n\n"
            f"Это действие *НЕОБРАТИМО*!\n\n"
            f"Вы *ДЕЙСТВИТЕЛЬНО* хотите перезапустить игру?\n\n"
            f"Напишите *ПОДТВЕРЖДАЮ* (заглавными буквами), чтобы продолжить, или любое другое сообщение для отмены.",
            parse_mode="Markdown",
        )
        await state.set_state(AdminStates.waiting_for_restart_confirmation)
        break


async def process_restart_confirmation(message: Message, state: FSMContext) -> None:
    """Process confirmation for game restart"""
    confirmation = message.text.strip()

    if confirmation != "ПОДТВЕРЖДАЮ":
        await message.answer("❌ Перезапуск игры отменен.")
        await state.clear()
        return

    # Get stored data
    data = await state.get_data()
    user_id = data["user_id"]
    game_name = data["game_name"]
    setting = data["setting"]
    years_per_day = data["years_per_day"]
    max_points = data["max_points"]
    max_population = data["max_population"]

    async for db in get_db():
        game_engine = GameEngine(db)

        # ПОЛНАЯ ОЧИСТКА БАЗЫ ДАННЫХ
        await message.answer("🔄 Очищаю базу данных...")

        # Удаляем все данные из всех таблиц
        await game_engine.db.execute(text("DELETE FROM verdicts"))
        await game_engine.db.execute(text("DELETE FROM posts"))
        await game_engine.db.execute(text("DELETE FROM messages"))
        await game_engine.db.execute(text("DELETE FROM players"))
        await game_engine.db.execute(text("DELETE FROM countries"))
        await game_engine.db.execute(text("DELETE FROM games"))
        await game_engine.db.commit()

        await message.answer("✅ База данных очищена. Создаю новую игру...")

        # Create new game
        game = await game_engine.create_game(
            name=game_name,
            description=f"Игра в сеттинге '{setting}'",
            setting=setting,
            max_players=20,
            years_per_day=years_per_day,
            max_points=max_points,
            max_population=max_population,
        )

        # Create admin player
        username = message.from_user.username
        display_name = message.from_user.full_name or f"Admin_{user_id}"

        admin_player = await game_engine.create_player(
            game_id=game.id,
            telegram_id=user_id,
            username=username,
            display_name=display_name,
            role=PlayerRole.ADMIN,
        )

        # Create admin country
        admin_country = await game_engine.create_country(
            game_id=game.id,
            name="Административная Республика",
            description="Страна администратора игры",
            capital="Центральный Город",
            population=1000000,
            aspects={
                "economy": 8,
                "military": 7,
                "foreign_policy": 9,
                "territory": 6,
                "technology": 8,
                "religion_culture": 7,
                "governance_law": 10,
                "construction_infrastructure": 7,
                "social_relations": 8,
                "intelligence": 9,
            },
        )

        # Assign country to admin
        await game_engine.assign_player_to_country(admin_player.id, admin_country.id)

        await message.answer(
            f"✅ <b>Игра успешно перезапущена!</b>\n\n"
            f"<b>Название:</b> {escape_html(game_name)}\n"
            f"<b>Сеттинг:</b> {escape_html(setting)}\n"
            f"<b>Лет за сутки:</b> {years_per_day}\n"
            f"<b>Макс очков для стран:</b> {max_points}\n"
            f"<b>Макс население стран:</b> {max_population:,}\n"
            f"<b>ID игры:</b> {game.id}\n\n"
            f"Вы назначены администратором игры и получили страну '{escape_html(admin_country.name)}'.\n\n"
            f"Теперь игроки могут регистрироваться в игре командой /register",
            parse_mode="HTML",
        )
        break

    await state.clear()


async def update_game_command(message: Message) -> None:
    """Handle /update_game command - update game settings"""
    user_id = message.from_user.id
    args = message.text.split(" ", 1)

    async for db in get_db():
        game_engine = GameEngine(db)

        # Check if user is admin
        if not await is_admin(user_id, game_engine.db):
            await message.answer("❌ У вас нет прав администратора.")
            return

        # Get admin info - take the first admin player for this user
        result = await game_engine.db.execute(
            select(Player)
            .where(Player.telegram_id == user_id)
            .where(Player.role == PlayerRole.ADMIN)
            .limit(1)
        )
        admin = result.scalar_one_or_none()

        if not admin:
            await message.answer("❌ Вы не зарегистрированы в игре.")
            return

        if len(args) < 2:
            await message.answer(
                "❌ Неверный формат команды.\n\n"
                "Используйте: <code>/update_game параметр значение</code>\n\n"
                "Доступные параметры:\n"
                "• <code>name</code> - название игры\n"
                "• <code>setting</code> - сеттинг игры\n"
                "• <code>max_players</code> - максимальное количество игроков\n"
                "• <code>years_per_day</code> - лет за сутки (1-365)\n"
                "• <code>max_points</code> - максимальные очки для стран (10-100)\n"
                "• <code>max_population</code> - максимальное население стран (1000-1000000000)\n\n"
                "Примеры:\n"
                "• <code>/update_game name Новое название игры</code>\n"
                "• <code>/update_game max_population 5000000</code>\n"
                "• <code>/update_game setting Средневековье</code>",
                parse_mode="HTML",
            )
            return

        # Parse parameters - first word is parameter, rest is value
        parts = args[1].split(" ", 1)
        if len(parts) < 2:
            await message.answer("❌ Укажите параметр и его значение.")
            return

        param = parts[0].strip()
        value = parts[1].strip()

        updates = {}

        try:
            if param == "name":
                if len(value) < 2 or len(value) > 255:
                    raise ValueError("Название должно быть от 2 до 255 символов")
                updates["name"] = value
            elif param == "setting":
                if len(value) < 2 or len(value) > 255:
                    raise ValueError("Сеттинг должен быть от 2 до 255 символов")
                updates["setting"] = value
            elif param == "max_players":
                max_players = int(value)
                if max_players < 1 or max_players > 1000:
                    raise ValueError(
                        "Максимальное количество игроков должно быть от 1 до 1000"
                    )
                updates["max_players"] = max_players
            elif param == "years_per_day":
                years_per_day = int(value)
                if years_per_day < 1 or years_per_day > 365:
                    raise ValueError("Лет за сутки должно быть от 1 до 365")
                updates["years_per_day"] = years_per_day
            elif param == "max_points":
                max_points = int(value)
                if max_points < 10 or max_points > 100:
                    raise ValueError("Максимальные очки должны быть от 10 до 100")
                updates["max_points"] = max_points
            elif param == "max_population":
                max_population = int(value)
                if max_population < 1000 or max_population > 1_000_000_000:
                    raise ValueError(
                        "Максимальное население должно быть от 1,000 до 1 млрд"
                    )
                updates["max_population"] = max_population
            else:
                raise ValueError(f"Неизвестный параметр: {param}")

        except ValueError as e:
            await message.answer(f"❌ Ошибка в параметрах: {e}")
            return

        # Update game
        updated_game = await game_engine.update_game_settings(admin.game_id, **updates)

        if not updated_game:
            await message.answer("❌ Не удалось обновить настройки игры.")
            return

        # Show updated settings
        param_names = {
            "name": "Название",
            "setting": "Сеттинг",
            "max_players": "Макс игроков",
            "years_per_day": "Лет за сутки",
            "max_points": "Макс очков",
            "max_population": "Макс население",
        }

        changes_text = "\n".join(
            [
                (
                    f"• <b>{param_names.get(key, key)}:</b> {value:,}"
                    if isinstance(value, int)
                    else f"• <b>{param_names.get(key, key)}:</b> {value}"
                )
                for key, value in updates.items()
            ]
        )

        await message.answer(
            f"✅ <b>Настройки игры обновлены!</b>\n\n"
            f"<b>Обновленные параметры:</b>\n{changes_text}\n\n"
            f"<b>Текущие настройки игры:</b>\n"
            f"• <b>Название:</b> {escape_html(updated_game.name)}\n"
            f"• <b>Сеттинг:</b> {escape_html(updated_game.setting)}\n"
            f"• <b>Макс игроков:</b> {updated_game.max_players}\n"
            f"• <b>Лет за сутки:</b> {updated_game.years_per_day}\n"
            f"• <b>Макс очков:</b> {updated_game.max_points}\n"
            f"• <b>Макс население:</b> {updated_game.max_population:,}",
            parse_mode="HTML",
        )
        break


async def event_command(message: Message, state: FSMContext) -> None:
    """Handle /event command - send event message to players"""
    user_id = message.from_user.id
    args = message.text.split(" ", 1)  # /event [country_name]

    async for db in get_db():
        game_engine = GameEngine(db)

        # Check if user is admin
        if not await is_admin(user_id, game_engine.db):
            await message.answer("❌ У вас нет прав администратора.")
            return

        # Get admin info - take the first admin player
        result = await game_engine.db.execute(
            select(Player)
            .options(selectinload(Player.country), selectinload(Player.game))
            .where(Player.telegram_id == user_id)
            .where(Player.role == PlayerRole.ADMIN)
            .limit(1)
        )
        admin = result.scalar_one_or_none()

        if not admin:
            await message.answer("❌ Вы не зарегистрированы в игре.")
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
        break

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

    if message.reply_to_message and message.reply_to_message.text:
        # Try to extract country ID from the replied message
        import re

        replied_text = message.reply_to_message.text

        # Look for the hidden marker [EDIT_COUNTRY:id]
        country_id_match = re.search(r"\[EDIT_COUNTRY:(\d+)\]", replied_text)
        if country_id_match:
            country_id = int(country_id_match.group(1))

            # Find the player with this country
            for player in all_players:
                if player.country and player.country.id == country_id:
                    target_player = player
                    target_country_name = player.country.name
                    break

        # If no hidden marker found, try to extract country name from the message
        if not target_player:
            # Look for country name in the format "🏛️ **Country Name**"
            country_name_match = re.search(r"🏛️\s*<b>([^<]+)</b>", replied_text)
            if country_name_match:
                extracted_country_name = country_name_match.group(1).strip()

                # Find target country by name
                for player in all_players:
                    if player.country:
                        # Check official name
                        if (
                            player.country.name.lower()
                            == extracted_country_name.lower()
                        ):
                            target_player = player
                            target_country_name = player.country.name
                            break

                        # Check synonyms
                        if player.country.synonyms:
                            for synonym in player.country.synonyms:
                                if synonym.lower() == extracted_country_name.lower():
                                    target_player = player
                                    target_country_name = player.country.name
                                    break
                            if target_player:
                                break

    # If no country found from reply, check if country name was provided in command
    if not target_player and len(args) > 1:
        target_country_name = args[1].strip()

        # Find target country (case-insensitive search by name and synonyms)
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

    if len(message_content) > 2000:
        await message.answer(
            "❌ Сообщение слишком длинное (максимум 2000 символов). Попробуйте еще раз или напишите <code>cancel</code> для отмены:",
            parse_mode="HTML",
        )
        return

    # Get stored data
    data = await state.get_data()
    target_player_id = data.get("target_player_id")
    target_country_name = data.get("target_country_name")

    user_id = message.from_user.id

    async for db in get_db():
        game_engine = GameEngine(db)

        # Get admin player
        result = await game_engine.db.execute(
            select(Player)
            .options(selectinload(Player.country), selectinload(Player.game))
            .where(Player.telegram_id == user_id)
            .where(Player.role == PlayerRole.ADMIN)
            .limit(1)
        )
        admin = result.scalar_one_or_none()

        if not admin:
            await message.answer("❌ Ошибка: вы не являетесь администратором.")
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
                try:
                    await bot.send_message(
                        target_player.telegram_id,
                        escape_html(message_content),
                        parse_mode="HTML",
                    )
                    sent_count = 1

                    # Save the admin message to database for RAG context
                    await game_engine.create_message(
                        player_id=target_player.id,
                        game_id=admin.game_id,
                        content=message_content,
                        is_admin_reply=True,
                    )
                except Exception as e:
                    print(
                        f"Failed to send event message to player {target_player.telegram_id}: {e}"
                    )
                    failed_count = 1
        else:
            # Send to all countries
            result = await game_engine.db.execute(
                select(Player)
                .where(Player.game_id == admin.game_id)
                .where(Player.role == PlayerRole.PLAYER)
            )
            players = result.scalars().all()

            for player in players:
                try:
                    await bot.send_message(
                        player.telegram_id,
                        escape_html(message_content),
                        parse_mode="HTML",
                    )
                    sent_count += 1

                    # Save the admin message to database for RAG context
                    await game_engine.create_message(
                        player_id=player.id,
                        game_id=admin.game_id,
                        content=message_content,
                        is_admin_reply=True,
                    )
                except Exception as e:
                    print(
                        f"Failed to send event message to player {player.telegram_id}: {e}"
                    )
                    failed_count += 1

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
        break

    # Clear state
    await state.clear()


async def generate_game_event(
    rag_system: RAGSystem,
    game_id: int,
    country_name: str | None = None,
    game_setting: str = "Современность",
) -> tuple[str, str]:
    """Generate a game event using RAG system

    Returns:
        tuple: (event_text, selected_tone)
    """

    # Get all countries data for context
    countries_data = await rag_system._get_all_countries_data(game_id)

    if not countries_data:
        return (
            "Не удалось получить информацию о странах для генерации события.",
            "нейтральное",
        )

    # Add randomness to event generation
    import random

    event_tones = [
        "хорошее",
        "нейтральное",
        "плохое",
        "ужасающее",
        "прекрасное",
        "неожиданное",
        "драматическое",
        "загадочное",
        "радостное",
        "тревожное",
        "удивительное",
        "катастрофическое",
        "благоприятное",
        "странное",
        "героическое",
        "мистическое",
        "абсурдное",
    ]

    selected_tone = random.choice(event_tones)

    # Create prompt for event generation
    if country_name:
        # Find specific country
        target_country = None
        for country in countries_data:
            if country["name"].lower() == country_name.lower():
                target_country = country
                break
            # Check synonyms
            if country["synonyms"]:
                for synonym in country["synonyms"]:
                    if synonym.lower() == country_name.lower():
                        target_country = country
                        break
                if target_country:
                    break

        if not target_country:
            return f"Страна '{country_name}' не найдена.", "нейтральное"

        # Generate event for specific country
        prompt = f"""Ты мастер многопользовательской стратегической игры в сеттинге "{game_setting}".

Информация о стране "{target_country["name"]}":
Столица: {target_country["capital"]}
Население: {target_country["population"]:,}
Аспекты (1-10):
- Экономика: {target_country["aspects"]["economy"]}{f" - {target_country['descriptions']['economy']}" if target_country["descriptions"]["economy"] else ""}
- Военное дело: {target_country["aspects"]["military"]}{f" - {target_country['descriptions']['military']}" if target_country["descriptions"]["military"] else ""}
- Внешняя политика: {target_country["aspects"]["foreign_policy"]}{f" - {target_country['descriptions']['foreign_policy']}" if target_country["descriptions"]["foreign_policy"] else ""}
- Территория: {target_country["aspects"]["territory"]}{f" - {target_country['descriptions']['territory']}" if target_country["descriptions"]["territory"] else ""}
- Технологии: {target_country["aspects"]["technology"]}{f" - {target_country['descriptions']['technology']}" if target_country["descriptions"]["technology"] else ""}
- Религия и культура: {target_country["aspects"]["religion_culture"]}{f" - {target_country['descriptions']['religion_culture']}" if target_country["descriptions"]["religion_culture"] else ""}
- Управление и право: {target_country["aspects"]["governance_law"]}{f" - {target_country['descriptions']['governance_law']}" if target_country["descriptions"]["governance_law"] else ""}
- Строительство и инфраструктура: {target_country["aspects"]["construction_infrastructure"]}{f" - {target_country['descriptions']['construction_infrastructure']}" if target_country["descriptions"]["construction_infrastructure"] else ""}
- Общественные отношения: {target_country["aspects"]["social_relations"]}{f" - {target_country['descriptions']['social_relations']}" if target_country["descriptions"]["social_relations"] else ""}
- Разведка: {target_country["aspects"]["intelligence"]}{f" - {target_country['descriptions']['intelligence']}" if target_country["descriptions"]["intelligence"] else ""}

Создай {selected_tone} короткое игровое событие (2-4 предложения) для этой страны, учитывая:
1. Сеттинг игры
2. Характеристики страны (сильные и слабые стороны)
3. Текущее состояние аспектов
4. Событие должно быть именно {selected_tone} по характеру

Событие должно быть:
- Интересным и вовлекающим
- Соответствующим сеттингу
- Учитывающим особенности страны
- Требующим решения от игрока
- {selected_tone.capitalize()} по тону и последствиям

Отвечай на русском языке. НЕ добавляй "Варианты действий:" или подобные фразы в конце."""
    else:
        # Generate global event for all countries
        countries_info = ""
        for country in countries_data[:5]:  # Limit to first 5 countries for brevity
            countries_info += f"""
{country["name"]} (население: {country["population"]:,})
- Экономика: {country["aspects"]["economy"]}, Военное дело: {country["aspects"]["military"]}
- Технологии: {country["aspects"]["technology"]}, Внешняя политика: {country["aspects"]["foreign_policy"]}"""

        prompt = f"""Ты мастер многопользовательской стратегической игры в сеттинге "{game_setting}".

Основные страны в игре:{countries_info}

Создай {selected_tone} короткое глобальное игровое событие (2-4 предложения), которое затронет все страны мира, учитывая:
1. Сеттинг игры
2. Разнообразие стран и их характеристики
3. Необходимость взаимодействия между странами
4. Событие должно быть именно {selected_tone} по характеру

Событие должно быть:
- Глобальным по масштабу
- Интересным и вовлекающим
- Соответствующим сеттингу
- Требующим координации между странами
- {selected_tone.capitalize()} по тону и последствиям

Отвечай на русском языке. НЕ добавляй "Варианты действий:" или подобные фразы в конце."""

    try:
        event_text = await rag_system._call_openrouter_api(prompt)
        return event_text, selected_tone
    except Exception as e:
        print(f"Error generating event: {e}")
        return "Не удалось сгенерировать событие. Попробуйте еще раз.", selected_tone


async def gen_command(message: Message, state: FSMContext) -> None:
    """Handle /gen command - generate game event"""
    user_id = message.from_user.id
    args = message.text.split(" ", 1)  # /gen [country_name]

    async for db in get_db():
        game_engine = GameEngine(db)

        # Check if user is admin
        if not await is_admin(user_id, game_engine.db):
            await message.answer("❌ У вас нет прав администратора.")
            return

        # Get admin info - take the first admin player
        result = await game_engine.db.execute(
            select(Player)
            .options(selectinload(Player.country), selectinload(Player.game))
            .where(Player.telegram_id == user_id)
            .where(Player.role == PlayerRole.ADMIN)
            .limit(1)
        )
        admin = result.scalar_one_or_none()

        if not admin:
            await message.answer("❌ Вы не зарегистрированы в игре.")
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
            await message.answer("❌ В игре нет стран для генерации событий.")
            return

        # Check if this is a reply to a message with country information
        target_player = None
        target_country_name = None

        if message.reply_to_message and message.reply_to_message.text:
            # Try to extract country ID from the replied message
            import re

            replied_text = message.reply_to_message.text

            # Look for the hidden marker [EDIT_COUNTRY:id]
            country_id_match = re.search(r"\[EDIT_COUNTRY:(\d+)\]", replied_text)
            if country_id_match:
                country_id = int(country_id_match.group(1))

                # Find the player with this country
                for player in all_players:
                    if player.country and player.country.id == country_id:
                        target_player = player
                        target_country_name = player.country.name
                        break

            # If no hidden marker found, try to extract country name from the message
            if not target_player:
                # Look for country name in the format "🏛️ **Country Name**"
                country_name_match = re.search(r"🏛️\s*<b>([^<]+)</b>", replied_text)
                if country_name_match:
                    extracted_country_name = country_name_match.group(1).strip()

                    # Find target country by name
                    for player in all_players:
                        if player.country:
                            # Check official name
                            if (
                                player.country.name.lower()
                                == extracted_country_name.lower()
                            ):
                                target_player = player
                                target_country_name = player.country.name
                                break

                            # Check synonyms
                            if player.country.synonyms:
                                for synonym in player.country.synonyms:
                                    if (
                                        synonym.lower()
                                        == extracted_country_name.lower()
                                    ):
                                        target_player = player
                                        target_country_name = player.country.name
                                        break
                                if target_player:
                                    break

        # If no country found from reply, check if country name was provided in command
        if not target_player and len(args) > 1:
            target_country_name = args[1].strip()

            # Find target country (case-insensitive search by name and synonyms)
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
                                target_country_name = player.country.name
                                break
                        if target_player:
                            break

            if not target_player:
                countries_list = "\n".join(
                    [f"• {country}" for country in sorted(available_countries)]
                )
                await message.answer(
                    f"❌ Страна '{escape_html(target_country_name)}' не найдена.\n\n"
                    f"Доступные страны:\n{countries_list}\n\n"
                    f"Используйте: <code>/gen название_страны</code> или <code>/gen</code> для всех",
                    parse_mode="HTML",
                )
                return

        # Initialize RAG system
        rag_system = RAGSystem(game_engine.db)

        # Generate event
        event_text, selected_tone = await generate_game_event(
            rag_system, admin.game_id, target_country_name, admin.game.setting
        )

        await message.answer(f"🎲 Генерирую {selected_tone} событие...")

        # Create inline keyboard
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="📤 Отправить", callback_data="gen_send"),
                    InlineKeyboardButton(
                        text="🔄 Заново", callback_data="gen_regenerate"
                    ),
                    InlineKeyboardButton(
                        text="❌ Отменить", callback_data="gen_cancel"
                    ),
                ]
            ]
        )

        # Store data for callback handlers
        await state.update_data(
            target_country_name=target_country_name,
            target_player_id=target_player.id if target_player else None,
            event_text=event_text,
            game_id=admin.game_id,
            game_setting=admin.game.setting,
        )

        # Send event with buttons
        event_header = "🎲 **Сгенерированное событие**\n"
        if target_country_name:
            event_header += f"**Для страны:** {target_country_name}\n"
            # Show different message if country was auto-detected from reply
            if message.reply_to_message:
                event_header += "*(автоматически определено из сообщения)*\n\n"
            else:
                event_header += "\n"
        else:
            event_header += "**Глобальное событие для всех стран**\n\n"

        # Format the full message with markdownify
        full_message = f"{event_header}{event_text}"

        try:
            formatted_message = markdownify(full_message)
            await message.answer(
                formatted_message, parse_mode="MarkdownV2", reply_markup=keyboard
            )
        except Exception as e:
            print(f"Failed to send formatted event message: {e}")
            # Fallback to HTML
            await message.answer(
                f"{event_header}{escape_html(event_text)}",
                parse_mode="HTML",
                reply_markup=keyboard,
            )

        await state.set_state(AdminStates.waiting_for_gen_action)
        break


async def process_gen_callback(
    callback_query: CallbackQuery, state: FSMContext
) -> None:
    """Process callback from gen command buttons"""
    data = await state.get_data()

    if not data:
        await callback_query.answer("❌ Данные сессии утеряны. Начните заново.")
        return

    user_id = callback_query.from_user.id

    async for db in get_db():
        game_engine = GameEngine(db)

        # Check if user is admin
        if not await is_admin(user_id, game_engine.db):
            await callback_query.answer("❌ У вас нет прав администратора.")
            return

        # Get admin info
        result = await game_engine.db.execute(
            select(Player)
            .options(selectinload(Player.country), selectinload(Player.game))
            .where(Player.telegram_id == user_id)
            .where(Player.role == PlayerRole.ADMIN)
            .limit(1)
        )
        admin = result.scalar_one_or_none()

        if not admin:
            await callback_query.answer("❌ Вы не зарегистрированы в игре.")
            return

        if callback_query.data == "gen_cancel":
            await callback_query.message.edit_text(
                "❌ Генерация события отменена.", parse_mode="HTML"
            )
            await state.clear()
            await callback_query.answer()

        elif callback_query.data == "gen_regenerate":
            await callback_query.answer("🔄 Генерирую новое событие...")

            # Initialize RAG system and regenerate
            rag_system = RAGSystem(game_engine.db)

            new_event_text, selected_tone = await generate_game_event(
                rag_system,
                data["game_id"],
                data["target_country_name"],
                data["game_setting"],
            )

            # Send message with selected tone
            await callback_query.message.answer(
                f"🎲 Генерирую {selected_tone} событие..."
            )

            # Update stored data
            await state.update_data(event_text=new_event_text)

            # Create keyboard again
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="📤 Отправить", callback_data="gen_send"
                        ),
                        InlineKeyboardButton(
                            text="🔄 Заново", callback_data="gen_regenerate"
                        ),
                        InlineKeyboardButton(
                            text="❌ Отменить", callback_data="gen_cancel"
                        ),
                    ]
                ]
            )

            # Update message
            event_header = "🎲 **Сгенерированное событие**\n"
            if data["target_country_name"]:
                event_header += f"**Для страны:** {data['target_country_name']}\n\n"
            else:
                event_header += "**Глобальное событие для всех стран**\n\n"

            # Format the full message with markdownify
            full_message = f"{event_header}{new_event_text}"

            try:
                formatted_message = markdownify(full_message)
                await callback_query.message.edit_text(
                    formatted_message, parse_mode="MarkdownV2", reply_markup=keyboard
                )
            except Exception as e:
                print(f"Failed to edit formatted event message: {e}")
                # Fallback to HTML
                await callback_query.message.edit_text(
                    f"{event_header}{escape_html(new_event_text)}",
                    parse_mode="HTML",
                    reply_markup=keyboard,
                )

        elif callback_query.data == "gen_send":
            await callback_query.answer("📤 Отправляю событие...")

            # Send event to target(s)
            bot = callback_query.bot
            sent_count = 0
            failed_count = 0

            if data["target_player_id"]:
                # Send to specific country
                result = await game_engine.db.execute(
                    select(Player)
                    .options(selectinload(Player.country))
                    .where(Player.id == data["target_player_id"])
                )
                target_player = result.scalar_one_or_none()

                if target_player:
                    try:
                        # Format event text with markdownify
                        try:
                            formatted_event = markdownify(data["event_text"])
                            await bot.send_message(
                                target_player.telegram_id,
                                formatted_event,
                                parse_mode="MarkdownV2",
                            )
                        except Exception as format_error:
                            print(
                                f"Failed to send formatted event to player: {format_error}"
                            )
                            # Fallback to HTML
                            await bot.send_message(
                                target_player.telegram_id,
                                escape_html(data["event_text"]),
                                parse_mode="HTML",
                            )
                        sent_count = 1

                        # Save the admin message to database for RAG context
                        await game_engine.create_message(
                            player_id=target_player.id,
                            game_id=data["game_id"],
                            content=data["event_text"],
                            is_admin_reply=True,
                        )
                    except Exception as e:
                        print(
                            f"Failed to send event to player {target_player.telegram_id}: {e}"
                        )
                        failed_count = 1
            else:
                # Send to all countries
                result = await game_engine.db.execute(
                    select(Player)
                    .where(Player.game_id == data["game_id"])
                    .where(Player.role == PlayerRole.PLAYER)
                )
                players = result.scalars().all()

                for player in players:
                    try:
                        # Format event text with markdownify
                        try:
                            formatted_event = markdownify(data["event_text"])
                            await bot.send_message(
                                player.telegram_id,
                                formatted_event,
                                parse_mode="MarkdownV2",
                            )
                        except Exception as format_error:
                            print(
                                f"Failed to send formatted event to player {player.telegram_id}: {format_error}"
                            )
                            # Fallback to HTML
                            await bot.send_message(
                                player.telegram_id,
                                escape_html(data["event_text"]),
                                parse_mode="HTML",
                            )
                        sent_count += 1

                        # Save the admin message to database for RAG context
                        await game_engine.create_message(
                            player_id=player.id,
                            game_id=data["game_id"],
                            content=data["event_text"],
                            is_admin_reply=True,
                        )
                    except Exception as e:
                        print(
                            f"Failed to send event to player {player.telegram_id}: {e}"
                        )
                        failed_count += 1

            # Update message with result, keeping the original event text
            event_header = "🎲 **Сгенерированное событие**\n"
            if data["target_country_name"]:
                event_header += f"**Для страны:** {data['target_country_name']}\n\n"
            else:
                event_header += "**Глобальное событие для всех стран**\n\n"

            # Add result status
            if data["target_player_id"]:
                if failed_count == 0:
                    status_text = f"✅ **Событие отправлено в страну {data['target_country_name']}!**"
                else:
                    status_text = f"❌ **Не удалось отправить событие в страну {data['target_country_name']}.**"
            else:
                if failed_count == 0:
                    status_text = f"✅ **Событие отправлено всем странам ({sent_count} получателей)!**"
                else:
                    status_text = f"⚠️ **Событие отправлено {sent_count} странам. Не удалось отправить {failed_count} странам.**"

            # Format the full message with event text and result
            full_message = f"{event_header}{data['event_text']}\n\n---\n{status_text}"

            try:
                formatted_message = markdownify(full_message)
                await callback_query.message.edit_text(
                    formatted_message, parse_mode="MarkdownV2"
                )
            except Exception as e:
                print(f"Failed to edit formatted result message: {e}")
                # Fallback to HTML
                await callback_query.message.edit_text(
                    f"{event_header}{escape_html(data['event_text'])}\n\n---\n{escape_html(status_text)}",
                    parse_mode="HTML",
                )

            await state.clear()

        break


def register_admin_handlers(dp: Dispatcher) -> None:
    """Register admin handlers"""
    dp.message.register(game_stats_command, Command("game_stats"))
    dp.message.register(restart_game_command, Command("restart_game"))
    dp.message.register(update_game_command, Command("update_game"))
    dp.message.register(event_command, Command("event"))
    dp.message.register(gen_command, Command("gen"))
    dp.message.register(
        process_restart_confirmation, AdminStates.waiting_for_restart_confirmation
    )
    dp.message.register(process_event_message, AdminStates.waiting_for_event_message)
    dp.callback_query.register(process_gen_callback, AdminStates.waiting_for_gen_action)
