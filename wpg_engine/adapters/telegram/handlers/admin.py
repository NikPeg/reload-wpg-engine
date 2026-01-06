"""
Admin handlers
"""

import logging
import re

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
from wpg_engine.core.admin_utils import get_admin_player, is_admin
from wpg_engine.core.engine import GameEngine
from wpg_engine.core.rag_system import RAGSystem
from wpg_engine.models import Country, Example, Player, PlayerRole, get_db

logger = logging.getLogger(__name__)


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
    message: Message, all_countries_or_players: list[Country] | list[Player]
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

    import re

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


class AdminStates(StatesGroup):
    """Admin states"""

    waiting_for_restart_confirmation = State()
    waiting_for_event_message = State()
    waiting_for_gen_action = State()
    waiting_for_delete_country_confirmation = State()
    waiting_for_final_message = State()
    waiting_for_delete_user_confirmation = State()
    waiting_for_example_message = State()


# Removed admin_command - functionality merged into /start command

# Removed pending_command - registrations are now sent directly to admin


async def game_stats_command(message: Message) -> None:
    """Handle /game_stats command"""
    user_id = message.from_user.id

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


async def active_command(message: Message) -> None:
    """Handle /active command - show message statistics by countries for the last week"""
    user_id = message.from_user.id

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

        # Get message statistics by countries
        stats = await game_engine.get_countries_message_stats(admin.game_id)

        if not stats:
            await message.answer(
                "📊 В игре пока нет стран или сообщений за последнюю неделю."
            )
            return

        # Format statistics message
        stats_text = "📊 **Активность стран за последнюю неделю**\n\n"

        total_messages = sum(stat["message_count"] for stat in stats)

        for i, stat in enumerate(stats, 1):
            country_name = stat["country_name"]
            message_count = stat["message_count"]

            # Add emoji based on position
            if i == 1 and message_count > 0:
                emoji = "🥇"
            elif i == 2 and message_count > 0:
                emoji = "🥈"
            elif i == 3 and message_count > 0:
                emoji = "🥉"
            elif message_count > 0:
                emoji = "📝"
            else:
                emoji = "💤"

            stats_text += f"{emoji} **{escape_markdown(country_name)}**: {message_count} сообщений\n"

        stats_text += f"\n**Всего сообщений:** {total_messages}"

        await message.answer(stats_text, parse_mode="Markdown")


async def restart_game_command(message: Message, state: FSMContext) -> None:
    """Handle /restart_game command"""
    user_id = message.from_user.id
    args = message.text.split(" ", 1)

    async with get_db() as db:
        game_engine = GameEngine(db)

        # Check if user is admin
        if not await is_admin(user_id, game_engine.db, message.chat.id):
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

    async with get_db() as db:
        game_engine = GameEngine(db)

        # ПОЛНАЯ ОЧИСТКА БАЗЫ ДАННЫХ
        await message.answer("🔄 Очищаю базу данных...")

        # Удаляем все данные из всех таблиц
        await game_engine.db.execute(text("DELETE FROM verdicts"))
        await game_engine.db.execute(text("DELETE FROM posts"))
        await game_engine.db.execute(text("DELETE FROM messages"))
        await game_engine.db.execute(text("DELETE FROM examples"))
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

        # Create admin player WITHOUT a country
        username = message.from_user.username
        display_name = message.from_user.full_name or f"Admin_{user_id}"

        await game_engine.create_player(
            game_id=game.id,
            telegram_id=user_id,
            username=username,
            display_name=display_name,
            role=PlayerRole.ADMIN,
        )

        await message.answer(
            f"✅ <b>Игра успешно перезапущена!</b>\n\n"
            f"<b>Название:</b> {escape_html(game_name)}\n"
            f"<b>Сеттинг:</b> {escape_html(setting)}\n"
            f"<b>Лет за сутки:</b> {years_per_day}\n"
            f"<b>Макс очков для стран:</b> {max_points}\n"
            f"<b>Макс население стран:</b> {max_population:,}\n"
            f"<b>ID игры:</b> {game.id}\n\n"
            f"Вы назначены администратором игры.\n\n"
            f"<i>💡 Администратору не требуется страна. "
            f"Если вы хотите создать страну для себя, используйте /register</i>\n\n"
            f"Теперь игроки могут регистрироваться в игре командой /register",
            parse_mode="HTML",
        )

    await state.clear()


async def update_game_command(message: Message) -> None:
    """Handle /update_game command - update game settings"""
    user_id = message.from_user.id
    args = message.text.split(" ", 1)

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


class VerdictGenerator:
    """Class for generating verdicts based on admin reference"""

    EMOTIONAL_MARKERS = [
        "катастрофический",
        "ужасный",
        "трагический",
        "провальный",
        "неудачный",
        "разрушительный",
        "критический",
        "плачевный",
        "блестящий",
        "триумфальный",
        "успешный",
        "отличный",
        "превосходный",
        "великолепный",
        "исключительный",
        "неожиданный",
        "непредвиденный",
        "драматический",
        "эпический",
        "загадочный",
        "парадоксальный",
        "сомнительный",
        "спорный",
        "нейтральный",
        "смешанный",
    ]

    def __init__(self, rag_system: RAGSystem):
        self.rag_system = rag_system

    async def generate_verdict(
        self,
        admin_reference: str,
        country_id: int,
        game_id: int,
        game_setting: str,
        admin_prompt: str | None = None,
        emotional_marker: str | None = None,
    ) -> str:
        """
        Generate verdict based on admin reference

        Args:
            admin_reference: Admin reference text (справка для администратора)
            country_id: Country ID for context
            game_id: Game ID
            game_setting: Game setting
            admin_prompt: Optional admin prompt to consider
            emotional_marker: Optional emotional marker (e.g., "ужасно", "прекрасно")

        Returns:
            Generated verdict text
        """
        # Build prompt based on mode
        if emotional_marker:
            # Random mode - use emotional marker
            prompt = f"""Ты администратор многопользовательской стратегической игры в сеттинге "{game_setting}".

СПРАВКА ДЛЯ АДМИНИСТРАТОРА:
{admin_reference}

Напиши вердикт для игрока, учитывая справку и учитывая {emotional_marker} результат действия игрока.

Вердикт должен быть:
- Соответствующим сеттингу игры
- Учитывающим информацию из справки
- Отражающим {emotional_marker} результат действия

Отвечай на русском языке."""
        elif admin_prompt:
            # Custom prompt mode
            prompt = f"""Ты администратор многопользовательской стратегической игры в сеттинге "{game_setting}".

СПРАВКА ДЛЯ АДМИНИСТРАТОРА:
{admin_reference}

Администратор просит: {admin_prompt}

Напиши вердикт для игрока, учитывая справку и запрос администратора.

Вердикт должен быть:
- Кратким (2-4 предложения)
- Соответствующим сеттингу игры
- Учитывающим информацию из справки
- Учитывающим запрос администратора: {admin_prompt}

Отвечай на русском языке."""
        else:
            # Default mode - just use reference
            prompt = f"""Ты администратор многопользовательской стратегической игры в сеттинге "{game_setting}".

СПРАВКА ДЛЯ АДМИНИСТРАТОРА:
{admin_reference}

Напиши вердикт для игрока, учитывая справку.

Вердикт должен быть:
- Кратким (2-4 предложения)
- Соответствующим сеттингу игры
- Учитывающим информацию из справки

Отвечай на русском языке."""

        try:
            logger.info("🎲 Начало генерации вердикта")
            verdict = await self.rag_system.client.call_api(
                prompt=prompt,
                max_tokens=1000,
                temperature=0.3,
                max_retries=2,
                timeout_seconds=60.0,
            )
            logger.info(
                f"✅ Вердикт успешно сгенерирован (длина: {len(verdict)} символов)"
            )
            return verdict
        except Exception as e:
            logger.error(f"❌ Ошибка при генерации вердикта: {type(e).__name__}: {e}")
            logger.exception("Full traceback:")
            return "Не удалось сгенерировать вердикт. Попробуйте еще раз."

    def get_random_emotional_marker(self) -> str:
        """Get random emotional marker"""
        import random

        return random.choice(self.EMOTIONAL_MARKERS)


async def generate_game_event(
    rag_system: RAGSystem,
    game_id: int,
    country_name: str | None = None,
    game_setting: str = "Современность",
    admin_prompt: str | None = None,
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

    # Add randomness to event generation (only if no admin prompt)
    import random

    if admin_prompt:
        # If admin provided prompt, don't use random tone
        selected_tone = None
    else:
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
        if admin_prompt:
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

Администратор просит: {admin_prompt}

Создай короткое игровое событие (2-4 предложения) для этой страны, учитывая:
1. Сеттинг игры
2. Характеристики страны (сильные и слабые стороны)
3. Текущее состояние аспектов
4. Запрос администратора: {admin_prompt}

Событие должно быть:
- Интересным и вовлекающим
- Соответствующим сеттингу
- Учитывающим особенности страны
- Требующим решения от игрока
- Соответствующим запросу администратора

Отвечай на русском языке. НЕ добавляй "Варианты действий:" или подобные фразы в конце."""
        else:
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

        if admin_prompt:
            prompt = f"""Ты мастер многопользовательской стратегической игры в сеттинге "{game_setting}".

Основные страны в игре:{countries_info}

Администратор просит: {admin_prompt}

Создай короткое глобальное игровое событие (2-4 предложения), которое затронет все страны мира, учитывая:
1. Сеттинг игры
2. Разнообразие стран и их характеристики
3. Необходимость взаимодействия между странами
4. Запрос администратора: {admin_prompt}

Событие должно быть:
- Глобальным по масштабу
- Интересным и вовлекающим
- Соответствующим сеттингу
- Требующим координации между странами
- Соответствующим запросу администратора

Отвечай на русском языке. НЕ добавляй "Варианты действий:" или подобные фразы в конце."""
        else:
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
        tone_info = (
            f" (тон: {selected_tone})"
            if selected_tone
            else (f" (промпт: {admin_prompt})" if admin_prompt else "")
        )
        logger.info(f"🎲 Начало генерации события{tone_info}")
        event_text = await rag_system.client.call_api(
            prompt=prompt,
            max_tokens=1000,
            temperature=0.3,
            max_retries=2,
            timeout_seconds=60.0,
        )
        logger.info(
            f"✅ Событие успешно сгенерировано (длина: {len(event_text)} символов)"
        )
        return event_text, selected_tone or "с промптом"
    except Exception as e:
        logger.error(f"❌ Ошибка при генерации события: {type(e).__name__}: {e}")
        logger.exception("Full traceback:")
        return (
            "Не удалось сгенерировать событие. Попробуйте еще раз.",
            selected_tone or "с промптом",
        )


async def _handle_gen_verdict(
    message: Message,
    state: FSMContext,
    game_engine: GameEngine,
    admin: Player,
    admin_ref_match: re.Match,
    replied_text: str,
    args: list[str],
) -> None:
    """Handle verdict generation from admin reference"""
    country_id = int(admin_ref_match.group(1))

    # Get country
    country = await game_engine.get_country(country_id)
    if not country:
        await message.answer("❌ Страна не найдена.")
        return

    # Get player for this country
    result = await game_engine.db.execute(
        select(Player)
        .options(selectinload(Player.country))
        .where(Player.country_id == country_id)
        .where(Player.role == PlayerRole.PLAYER)
        .limit(1)
    )
    target_player = result.scalar_one_or_none()

    if not target_player:
        await message.answer(
            f"❌ Не найден игрок для страны {escape_html(country.name)}."
        )
        return

    # Determine mode and parameters
    admin_prompt = None
    emotional_marker = None
    mode_description = ""

    if len(args) > 1:
        prompt_text = args[1].strip().lower()
        if prompt_text in ["random", "рандом"]:
            # Random mode
            generator = VerdictGenerator(RAGSystem(game_engine.db))
            emotional_marker = generator.get_random_emotional_marker()
            mode_description = f"случайный маркер: {emotional_marker}"
        else:
            # Custom prompt mode
            admin_prompt = args[1].strip()
            mode_description = f"промпт: {admin_prompt}"
    else:
        # Default mode - just use reference
        mode_description = "стандартный режим"

    # Initialize RAG system and generator
    rag_system = RAGSystem(game_engine.db)
    generator = VerdictGenerator(rag_system)

    # Get admin reference (remove the country identifier at the end)
    admin_reference = re.sub(
        r"\n\n<code>\[ADMIN_REFERENCE:\d+\]</code>$", "", replied_text
    )
    admin_reference = re.sub(r"\n\n\[ADMIN_REFERENCE:\d+\]$", "", admin_reference)

    # Generate verdict
    await message.answer(f"🎲 Генерирую вердикт ({mode_description})...")

    verdict_text = await generator.generate_verdict(
        admin_reference=admin_reference,
        country_id=country_id,
        game_id=admin.game_id,
        game_setting=admin.game.setting,
        admin_prompt=admin_prompt,
        emotional_marker=emotional_marker,
    )

    # Create inline keyboard
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📤 Отправить", callback_data="gen_verdict_send"
                ),
                InlineKeyboardButton(
                    text="🔄 Заново", callback_data="gen_verdict_regenerate"
                ),
                InlineKeyboardButton(
                    text="❌ Отменить", callback_data="gen_verdict_cancel"
                ),
            ]
        ]
    )

    # Send verdict with buttons
    verdict_header = "🎲 **Сгенерированный вердикт**\n\n"
    verdict_header += f"**Для страны:** {escape_markdown(country.name)}\n"
    if mode_description:
        verdict_header += f"**Режим:** {escape_markdown(mode_description)}\n"
    verdict_header += "\n"

    # Format the full message with markdownify
    full_message = f"{verdict_header}{verdict_text}"

    try:
        formatted_message = markdownify(full_message)
        verdict_message = await message.answer(
            formatted_message, parse_mode="MarkdownV2", reply_markup=keyboard
        )
    except Exception as e:
        logger.warning(
            f"⚠️ Не удалось отправить форматированное сообщение вердикта: {e}"
        )
        # Fallback to HTML
        verdict_message = await message.answer(
            f"{verdict_header}{escape_html(verdict_text)}",
            parse_mode="HTML",
            reply_markup=keyboard,
        )

    # Store data for callback handlers
    await state.update_data(
        target_country_name=country.name,
        target_player_id=target_player.id,
        target_country_id=country_id,
        verdict_text=verdict_text,
        game_id=admin.game_id,
        game_setting=admin.game.setting,
        admin_reference=admin_reference,
        admin_prompt=admin_prompt,
        emotional_marker=emotional_marker,
        verdict_message_id=verdict_message.message_id,
    )

    await state.set_state(AdminStates.waiting_for_gen_action)


async def _handle_gen_country_event(
    message: Message,
    state: FSMContext,
    game_engine: GameEngine,
    admin: Player,
    country_edit_match: re.Match,
    admin_prompt: str | None,
) -> None:
    """Handle event generation for specific country"""
    country_id = int(country_edit_match.group(1))

    # Get country
    country = await game_engine.get_country(country_id)
    if not country:
        await message.answer("❌ Страна не найдена.")
        return

    # Get player for this country
    result = await game_engine.db.execute(
        select(Player)
        .options(selectinload(Player.country))
        .where(Player.country_id == country_id)
        .where(Player.role == PlayerRole.PLAYER)
        .limit(1)
    )
    target_player = result.scalar_one_or_none()

    if not target_player:
        await message.answer(
            f"❌ Не найден игрок для страны {escape_html(country.name)}."
        )
        return

    # Initialize RAG system
    rag_system = RAGSystem(game_engine.db)

    # Generate event
    mode_description = (
        f"промпт: {admin_prompt}" if admin_prompt else "стандартный режим"
    )
    await message.answer(f"🎲 Генерирую событие для страны ({mode_description})...")

    event_text, selected_tone = await generate_game_event(
        rag_system, admin.game_id, country.name, admin.game.setting, admin_prompt
    )

    # Create inline keyboard
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📤 Отправить", callback_data="gen_send"),
                InlineKeyboardButton(text="🔄 Заново", callback_data="gen_regenerate"),
                InlineKeyboardButton(text="❌ Отменить", callback_data="gen_cancel"),
            ]
        ]
    )

    # Send event with buttons
    event_header = "🎲 **Сгенерированное событие**\n"
    event_header += f"**Для страны:** {escape_markdown(country.name)}\n"
    if admin_prompt:
        event_header += f"**Промпт:** {escape_markdown(admin_prompt)}\n"
    event_header += "\n"

    # Format the full message with markdownify
    full_message = f"{event_header}{event_text}"

    try:
        formatted_message = markdownify(full_message)
        event_message = await message.answer(
            formatted_message, parse_mode="MarkdownV2", reply_markup=keyboard
        )
    except Exception as e:
        logger.warning(f"⚠️ Не удалось отправить форматированное сообщение события: {e}")
        # Fallback to HTML
        event_message = await message.answer(
            f"{event_header}{escape_html(event_text)}",
            parse_mode="HTML",
            reply_markup=keyboard,
        )

    # Store data for callback handlers
    await state.update_data(
        target_country_name=country.name,
        target_player_id=target_player.id,
        event_text=event_text,
        game_id=admin.game_id,
        game_setting=admin.game.setting,
        event_message_id=event_message.message_id,
        admin_prompt=admin_prompt,
    )

    await state.set_state(AdminStates.waiting_for_gen_action)


async def _handle_gen_global_event(
    message: Message,
    state: FSMContext,
    game_engine: GameEngine,
    admin: Player,
    admin_prompt: str | None,
) -> None:
    """Handle global event generation"""
    # Initialize RAG system
    rag_system = RAGSystem(game_engine.db)

    # Generate event
    mode_description = (
        f"промпт: {admin_prompt}" if admin_prompt else "стандартный режим"
    )
    await message.answer(f"🎲 Генерирую глобальное событие ({mode_description})...")

    event_text, selected_tone = await generate_game_event(
        rag_system, admin.game_id, None, admin.game.setting, admin_prompt
    )

    # Create inline keyboard
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📤 Отправить", callback_data="gen_send"),
                InlineKeyboardButton(text="🔄 Заново", callback_data="gen_regenerate"),
                InlineKeyboardButton(text="❌ Отменить", callback_data="gen_cancel"),
            ]
        ]
    )

    # Send event with buttons
    event_header = "🎲 **Сгенерированное событие**\n"
    event_header += "**Глобальное событие для всех стран**\n"
    if admin_prompt:
        event_header += f"**Промпт:** {escape_markdown(admin_prompt)}\n"
    event_header += "\n"

    # Format the full message with markdownify
    full_message = f"{event_header}{event_text}"

    try:
        formatted_message = markdownify(full_message)
        event_message = await message.answer(
            formatted_message, parse_mode="MarkdownV2", reply_markup=keyboard
        )
    except Exception as e:
        logger.warning(f"⚠️ Не удалось отправить форматированное сообщение события: {e}")
        # Fallback to HTML
        event_message = await message.answer(
            f"{event_header}{escape_html(event_text)}",
            parse_mode="HTML",
            reply_markup=keyboard,
        )

    # Store data for callback handlers
    await state.update_data(
        target_country_name=None,
        target_player_id=None,
        event_text=event_text,
        game_id=admin.game_id,
        game_setting=admin.game.setting,
        event_message_id=event_message.message_id,
        admin_prompt=admin_prompt,
    )

    await state.set_state(AdminStates.waiting_for_gen_action)


async def gen_command(message: Message, state: FSMContext) -> None:
    """Handle /gen command - generate verdict or event"""
    user_id = message.from_user.id
    args = message.text.split(" ", 1)  # /gen [prompt|random|рандом]

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

        # Parse arguments
        admin_prompt = None
        if len(args) > 1:
            prompt_text = args[1].strip().lower()
            if prompt_text not in ["random", "рандом"]:
                admin_prompt = args[1].strip()

        # Check if this is a reply to a message
        if message.reply_to_message and message.reply_to_message.text:
            replied_text = message.reply_to_message.text

            # Check for admin reference (verdict generation)
            admin_ref_match = re.search(r"\[ADMIN_REFERENCE:(\d+)\]", replied_text)
            if admin_ref_match:
                # Generate verdict based on admin reference
                await _handle_gen_verdict(
                    message,
                    state,
                    game_engine,
                    admin,
                    admin_ref_match,
                    replied_text,
                    args,
                )
                return

            # Check for country edit marker (event generation for country)
            country_edit_match = re.search(r"\[EDIT_COUNTRY:(\d+)\]", replied_text)
            if country_edit_match:
                # Generate event for specific country
                await _handle_gen_country_event(
                    message, state, game_engine, admin, country_edit_match, admin_prompt
                )
                return

        # No reply or no markers found - generate global event
        await _handle_gen_global_event(message, state, game_engine, admin, admin_prompt)


async def process_gen_callback(
    callback_query: CallbackQuery, state: FSMContext
) -> None:
    """Process callback from gen command buttons"""
    user_id = callback_query.from_user.id

    async with get_db() as db:
        game_engine = GameEngine(db)

        # Check if user is admin
        if not await is_admin(user_id, game_engine.db, callback_query.message.chat.id):
            await callback_query.answer("❌ У вас нет прав администратора.")
            return

        # Get admin player (works for both admin chat and admin user)
        admin = await get_admin_player(user_id, game_engine.db)

        if not admin:
            await callback_query.answer("❌ Администратор не найден в игре.")
            return

        # Check if this is an admin chat callback (no state required)
        if callback_query.data.startswith(
            "gen_verdict_resend:"
        ) or callback_query.data.startswith("gen_verdict_undo:"):
            # Handle admin chat callbacks (no state)
            parts = callback_query.data.split(":")
            action = parts[0]
            player_id = int(parts[1])

            result = await game_engine.db.execute(
                select(Player)
                .options(selectinload(Player.country))
                .where(Player.id == player_id)
            )
            target_player = result.scalar_one_or_none()

            if not target_player:
                await callback_query.answer("❌ Игрок не найден.")
                return

            # Extract verdict from current message
            message_text = (
                callback_query.message.text or callback_query.message.caption or ""
            )
            # Try to extract verdict text (between "Вердикт:" and end)
            verdict_match = re.search(
                r"<b>Вердикт:</b>\n(.*?)(?:\n\n|$)", message_text, re.DOTALL
            )
            if verdict_match:
                verdict_text = verdict_match.group(1).strip()
                # Remove HTML tags
                verdict_text = re.sub(r"<[^>]+>", "", verdict_text)
            else:
                # Fallback: try to extract from message text (everything after "Вердикт:")
                if "Вердикт:" in message_text:
                    verdict_text = message_text.split("Вердикт:")[-1].strip()
                    verdict_text = re.sub(r"<[^>]+>", "", verdict_text)
                else:
                    await callback_query.answer("❌ Не удалось найти текст вердикта.")
                    return

            if action == "gen_verdict_resend":
                await callback_query.answer("📤 Отправляю вердикт заново...")
                try:
                    # Send verdict to player again
                    await callback_query.bot.send_message(
                        target_player.telegram_id,
                        escape_html(verdict_text),
                        parse_mode="HTML",
                    )

                    # Save the admin message to database
                    await game_engine.create_message(
                        player_id=target_player.id,
                        game_id=admin.game_id,
                        content=verdict_text,
                        is_admin_reply=True,
                    )

                    await callback_query.message.edit_text(
                        f"✅ <b>Вердикт отправлен игроку заново</b>\n\n"
                        f"<b>Игрок:</b> {escape_html(target_player.display_name)}\n"
                        f"<b>Страна:</b> {escape_html(target_player.country.name if target_player.country else 'без страны')}\n\n"
                        f"<b>Вердикт:</b>\n{escape_html(verdict_text)}",
                        parse_mode="HTML",
                    )
                except Exception as e:
                    await callback_query.answer(f"❌ Не удалось отправить вердикт: {e}")

            elif action == "gen_verdict_undo":
                await callback_query.answer("❌ Отмена вердикта...")
                # Note: We can't actually "undo" a sent message, but we can notify
                await callback_query.message.edit_text(
                    f"❌ <b>Вердикт отменен</b>\n\n"
                    f"<b>Игрок:</b> {escape_html(target_player.display_name)}\n"
                    f"<b>Страна:</b> {escape_html(target_player.country.name if target_player.country else 'без страны')}\n\n"
                    f"<i>Примечание: Сообщение уже было отправлено игроку. Это уведомление для администраторов.</i>",
                    parse_mode="HTML",
                )
            return

        # Get state data (for verdict/event callbacks that require state)
        data = await state.get_data()

        if not data:
            await callback_query.answer("❌ Данные сессии утеряны. Начните заново.")
            return

        # Check if this is a verdict callback (new functionality) or event callback (old)
        is_verdict = "verdict_text" in data or callback_query.data.startswith(
            "gen_verdict"
        )

        if is_verdict:
            # Handle verdict callbacks
            if callback_query.data == "gen_verdict_cancel":
                await callback_query.message.edit_text(
                    "❌ Генерация вердикта отменена.", parse_mode="HTML"
                )
                await state.clear()
                await callback_query.answer()

            elif callback_query.data == "gen_verdict_regenerate":
                await callback_query.answer("🔄 Генерирую новый вердикт...")

                # Initialize RAG system and generator
                rag_system = RAGSystem(game_engine.db)
                generator = VerdictGenerator(rag_system)

                # Generate new verdict
                new_verdict_text = await generator.generate_verdict(
                    admin_reference=data["admin_reference"],
                    country_id=data["target_country_id"],
                    game_id=data["game_id"],
                    game_setting=data["game_setting"],
                    admin_prompt=data.get("admin_prompt"),
                    emotional_marker=data.get("emotional_marker"),
                )

                # Create keyboard
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="📤 Отправить", callback_data="gen_verdict_send"
                            ),
                            InlineKeyboardButton(
                                text="🔄 Заново", callback_data="gen_verdict_regenerate"
                            ),
                            InlineKeyboardButton(
                                text="❌ Отменить", callback_data="gen_verdict_cancel"
                            ),
                        ]
                    ]
                )

                # Update message
                verdict_header = "🎲 **Сгенерированный вердикт**\n\n"
                verdict_header += f"**Для страны:** {escape_markdown(data['target_country_name'])}\n\n"

                full_message = f"{verdict_header}{new_verdict_text}"

                try:
                    formatted_message = markdownify(full_message)
                    await callback_query.message.edit_text(
                        formatted_message,
                        parse_mode="MarkdownV2",
                        reply_markup=keyboard,
                    )
                except Exception as e:
                    logger.warning(
                        f"⚠️ Не удалось отредактировать форматированное сообщение вердикта: {e}"
                    )
                    await callback_query.message.edit_text(
                        f"{verdict_header}{escape_html(new_verdict_text)}",
                        parse_mode="HTML",
                        reply_markup=keyboard,
                    )

                # Update stored data
                await state.update_data(verdict_text=new_verdict_text)

            elif callback_query.data == "gen_verdict_send":
                await callback_query.answer("📤 Отправляю вердикт...")

                # Send verdict to player
                bot = callback_query.bot
                result = await game_engine.db.execute(
                    select(Player)
                    .options(selectinload(Player.country))
                    .where(Player.id == data["target_player_id"])
                )
                target_player = result.scalar_one_or_none()

                if target_player:
                    try:
                        # Send verdict to player
                        await bot.send_message(
                            target_player.telegram_id,
                            escape_html(data["verdict_text"]),
                            parse_mode="HTML",
                        )

                        # Save the admin message to database
                        await game_engine.create_message(
                            player_id=target_player.id,
                            game_id=data["game_id"],
                            content=data["verdict_text"],
                            is_admin_reply=True,
                        )

                        # Send to admin chat with buttons
                        from wpg_engine.config.settings import settings

                        admin_chat_id = None
                        if settings.telegram.is_admin_chat():
                            admin_chat_id = settings.telegram.admin_id
                        else:
                            # Find admins
                            result = await game_engine.db.execute(
                                select(Player)
                                .where(Player.game_id == data["game_id"])
                                .where(Player.role == PlayerRole.ADMIN)
                            )
                            admins = result.scalars().all()
                            if admins:
                                import random

                                admin_player = random.choice(admins)
                                admin_chat_id = admin_player.telegram_id

                        if admin_chat_id:
                            # Create keyboard for admin chat
                            admin_keyboard = InlineKeyboardMarkup(
                                inline_keyboard=[
                                    [
                                        InlineKeyboardButton(
                                            text="📤 Отправить заново",
                                            callback_data=f"gen_verdict_resend:{target_player.id}",
                                        ),
                                        InlineKeyboardButton(
                                            text="❌ Отменить",
                                            callback_data=f"gen_verdict_undo:{target_player.id}",
                                        ),
                                    ]
                                ]
                            )

                            admin_message_text = (
                                f"✅ <b>Вердикт отправлен игроку</b>\n\n"
                                f"<b>Игрок:</b> {escape_html(target_player.display_name)}\n"
                                f"<b>Страна:</b> {escape_html(data['target_country_name'])}\n\n"
                                f"<b>Вердикт:</b>\n{escape_html(data['verdict_text'])}"
                            )

                            await bot.send_message(
                                admin_chat_id,
                                admin_message_text,
                                parse_mode="HTML",
                                reply_markup=admin_keyboard,
                            )

                        # Update message with result
                        status_text = f"✅ **Вердикт отправлен игроку {data['target_country_name']}!**"
                        verdict_header = "🎲 **Сгенерированный вердикт**\n\n"
                        verdict_header += f"**Для страны:** {escape_markdown(data['target_country_name'])}\n\n"
                        full_message = f"{verdict_header}{data['verdict_text']}\n\n---\n{status_text}"

                        try:
                            formatted_message = markdownify(full_message)
                            await callback_query.message.edit_text(
                                formatted_message, parse_mode="MarkdownV2"
                            )
                        except Exception as e:
                            logger.warning(
                                f"⚠️ Не удалось отредактировать форматированное сообщение результата: {e}"
                            )
                            await callback_query.message.edit_text(
                                f"{verdict_header}{escape_html(data['verdict_text'])}\n\n---\n{escape_html(status_text)}",
                                parse_mode="HTML",
                            )

                    except Exception as e:
                        logger.error(
                            f"❌ Не удалось отправить вердикт игроку: {type(e).__name__}: {e}"
                        )
                        await callback_query.answer(
                            f"❌ Не удалось отправить вердикт игроку: {e}"
                        )
                        return

                await state.clear()

        # Old event callbacks (keep for backward compatibility)
        elif callback_query.data == "gen_cancel":
            await callback_query.message.edit_text(
                "❌ Генерация события отменена.", parse_mode="HTML"
            )
            await state.clear()
            await callback_query.answer()

        elif callback_query.data == "gen_regenerate":
            await callback_query.answer("🔄 Генерирую новое событие...")

            # Step 1: Delete the old event message
            try:
                await callback_query.bot.delete_message(
                    chat_id=callback_query.message.chat.id,
                    message_id=data["event_message_id"],
                )
            except Exception as e:
                logger.warning(f"⚠️ Не удалось удалить старое сообщение события: {e}")

            # Step 2: Edit the existing tone message to show "generating..." immediately
            try:
                await callback_query.bot.edit_message_text(
                    chat_id=callback_query.message.chat.id,
                    message_id=data["tone_message_id"],
                    text="🎲 Генерирую новое событие...",
                )
            except Exception as e:
                logger.warning(f"⚠️ Не удалось отредактировать сообщение тона: {e}")
                # Fallback: send new message if editing fails
                tone_message = await callback_query.message.answer(
                    "🎲 Генерирую новое событие..."
                )
                # Update tone message ID in state
                await state.update_data(tone_message_id=tone_message.message_id)

            # Step 3: Initialize RAG system and regenerate (this takes time)
            rag_system = RAGSystem(game_engine.db)

            new_event_text, selected_tone = await generate_game_event(
                rag_system,
                data["game_id"],
                data["target_country_name"],
                data["game_setting"],
            )

            # Step 4: Update the tone message with the actual tone
            try:
                await callback_query.bot.edit_message_text(
                    chat_id=callback_query.message.chat.id,
                    message_id=data["tone_message_id"],
                    text=f"🎲 Генерирую {selected_tone} событие...",
                )
            except Exception as e:
                logger.warning(
                    f"⚠️ Не удалось отредактировать сообщение тона с актуальным тоном: {e}"
                )

            # Step 5: Send new event message
            # Create keyboard
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

            # Create event message
            event_header = "🎲 **Сгенерированное событие**\n"
            if data["target_country_name"]:
                event_header += f"**Для страны:** {data['target_country_name']}\n\n"
            else:
                event_header += "**Глобальное событие для всех стран**\n\n"

            # Format and send the new event message
            full_message = f"{event_header}{new_event_text}"

            try:
                formatted_message = markdownify(full_message)
                new_event_message = await callback_query.message.answer(
                    formatted_message, parse_mode="MarkdownV2", reply_markup=keyboard
                )
            except Exception as e:
                logger.warning(
                    f"⚠️ Не удалось отправить форматированное сообщение события: {e}"
                )
                # Fallback to HTML
                new_event_message = await callback_query.message.answer(
                    f"{event_header}{escape_html(new_event_text)}",
                    parse_mode="HTML",
                    reply_markup=keyboard,
                )

            # Update stored data with new event text and message ID
            await state.update_data(
                event_text=new_event_text, event_message_id=new_event_message.message_id
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
                    sent_count, failed_count = await send_message_to_players(
                        bot,
                        game_engine,
                        [target_player],
                        data["event_text"],
                        data["game_id"],
                        use_markdown=True,
                    )
            else:
                # Send to all countries
                result = await game_engine.db.execute(
                    select(Player)
                    .where(Player.game_id == data["game_id"])
                    .where(Player.role == PlayerRole.PLAYER)
                )
                players = result.scalars().all()

                sent_count, failed_count = await send_message_to_players(
                    bot,
                    game_engine,
                    players,
                    data["event_text"],
                    data["game_id"],
                    use_markdown=True,
                )

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
                logger.warning(
                    f"⚠️ Не удалось отредактировать форматированное сообщение результата: {e}"
                )
                # Fallback to HTML
                await callback_query.message.edit_text(
                    f"{event_header}{escape_html(data['event_text'])}\n\n---\n{escape_html(status_text)}",
                    parse_mode="HTML",
                )

            await state.clear()


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


async def add_example_command(message: Message, state: FSMContext) -> None:
    """Handle /add_example command - mark a country as example for new players"""
    user_id = message.from_user.id
    args = message.text.split(maxsplit=1)

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

        # Check if country name is provided
        if len(args) < 2:
            await message.answer(
                "❌ Укажите название страны.\n\n"
                "Формат: <code>/add_example Название страны</code>\n\n"
                "Пример: <code>/add_example Римская Империя</code>",
                parse_mode="HTML",
            )
            return

        country_name = args[1].strip()

        # Find country by name or synonym
        country = await game_engine.find_country_by_name_or_synonym(
            admin.game_id, country_name
        )

        if not country:
            await message.answer(
                f"❌ Страна '{escape_html(country_name)}' не найдена.\n\n"
                f"Используйте /world для просмотра всех стран.",
                parse_mode="HTML",
            )
            return

        # Check if country is already an example
        result = await game_engine.db.execute(
            select(Example).where(Example.country_id == country.id)
        )
        existing_example = result.scalar_one_or_none()

        if existing_example:
            await message.answer(
                f"ℹ️ Страна <b>{escape_html(country.name)}</b> уже является примером.",
                parse_mode="HTML",
            )
            return

        # Create new example
        example = Example(
            country_id=country.id,
            game_id=admin.game_id,
            created_by_id=admin.id,
        )

        game_engine.db.add(example)
        await game_engine.db.commit()
        await game_engine.db.refresh(example)

        await message.answer(
            f"✅ <b>Страна добавлена в примеры!</b>\n\n"
            f"<b>Страна:</b> {escape_html(country.name)}\n\n"
            f"Новые игроки смогут увидеть эту страну как пример при регистрации, используя команду /examples",
            parse_mode="HTML",
        )


async def random_command(message: Message) -> None:
    """Handle /random command - return random percentage from 0 to 100"""
    user_id = message.from_user.id

    async with get_db() as db:
        game_engine = GameEngine(db)

        # Check if user is admin
        if not await is_admin(user_id, game_engine.db, message.chat.id):
            await message.answer("❌ У вас нет прав администратора.")
            return

        # Generate random percentage from 0 to 100 (inclusive)
        import random

        percentage = random.randint(0, 100)

        await message.answer(f"🎲 {percentage}%")


async def process_example_message(message: Message, state: FSMContext) -> None:
    """Process example message from admin - NO LONGER USED"""
    # This function is no longer needed but kept for backward compatibility
    await state.clear()
    await message.answer(
        "⚠️ Эта функция больше не используется. Используйте /add_example с названием страны.",
        parse_mode="HTML",
    )


def register_admin_handlers(dp: Dispatcher) -> None:
    """Register admin handlers"""
    dp.message.register(game_stats_command, Command("game_stats"))
    dp.message.register(active_command, Command("active"))
    dp.message.register(restart_game_command, Command("restart_game"))
    dp.message.register(update_game_command, Command("update_game"))
    dp.message.register(event_command, Command("event"))
    dp.message.register(gen_command, Command("gen"))
    dp.message.register(delete_country_command, Command("delete_country"))
    dp.message.register(delete_user_command, Command("delete_user"))
    dp.message.register(add_example_command, Command("add_example"))
    dp.message.register(random_command, Command("random"))
    dp.message.register(
        process_restart_confirmation, AdminStates.waiting_for_restart_confirmation
    )
    dp.message.register(process_event_message, AdminStates.waiting_for_event_message)
    dp.message.register(
        process_delete_country_confirmation,
        AdminStates.waiting_for_delete_country_confirmation,
    )
    dp.message.register(process_final_message, AdminStates.waiting_for_final_message)
    dp.message.register(
        process_delete_user_confirmation,
        AdminStates.waiting_for_delete_user_confirmation,
    )
    dp.message.register(
        process_example_message, AdminStates.waiting_for_example_message
    )
    dp.callback_query.register(process_gen_callback, AdminStates.waiting_for_gen_action)
    # Register callback handlers for admin chat buttons (no state required)
    dp.callback_query.register(
        process_gen_callback,
        lambda c: c.data
        and (
            c.data.startswith("gen_verdict_resend:")
            or c.data.startswith("gen_verdict_undo:")
        ),
    )
