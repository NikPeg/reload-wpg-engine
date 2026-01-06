"""
Admin simple commands (without FSM)
"""

from aiogram.types import Message

from wpg_engine.adapters.telegram.utils import escape_html, escape_markdown
from wpg_engine.core.admin_utils import get_admin_player, is_admin
from wpg_engine.core.engine import GameEngine
from wpg_engine.models import get_db


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
