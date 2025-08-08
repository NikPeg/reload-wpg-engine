"""
Admin handlers
"""

from aiogram import Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from wpg_engine.core.admin_utils import is_admin
from wpg_engine.core.engine import GameEngine
from wpg_engine.models import Player, PlayerRole, get_db


async def admin_command(message: Message) -> None:
    """Handle /admin command - admin panel"""
    user_id = message.from_user.id

    async for db in get_db():
        game_engine = GameEngine(db)

        # Check if user is admin
        if not await is_admin(user_id, game_engine.db):
            await message.answer("❌ У вас нет прав администратора.")
            return

        # Get player info for game details with eager loading
        result = await game_engine.db.execute(
            select(Player).options(selectinload(Player.game)).where(Player.telegram_id == user_id)
        )
        player = result.scalar_one_or_none()
        break

    if not player:
        await message.answer(
            "⚙️ *Панель администратора*\n\n"
            "❌ Вы не зарегистрированы в игре.\n"
            "Используйте /register для регистрации.",
            parse_mode="Markdown",
        )
        return

    await message.answer(
        f"⚙️ *Панель администратора*\n\n"
        f"*Игра:* {player.game.name}\n"
        f"*Сеттинг:* {player.game.setting}\n"
        f"*Статус:* {player.game.status}",
        parse_mode="Markdown",
    )


# Removed pending_command - registrations are now sent directly to admin


async def approve_command(message: Message) -> None:
    """Handle /approve command"""
    user_id = message.from_user.id
    args = message.text.split()[1:]

    async for db in get_db():
        game_engine = GameEngine(db)

        # Check if user is admin
        if not await is_admin(user_id, game_engine.db):
            await message.answer("❌ У вас нет прав администратора.")
            return

        # Get admin info
        result = await game_engine.db.execute(select(Player).where(Player.telegram_id == user_id))
        result.scalar_one_or_none()

    if not args:
        await message.answer("❌ Укажите Telegram ID игрока: `/approve 123456789`")
        return

    try:
        target_user_id = int(args[0])
    except ValueError:
        await message.answer("❌ Некорректный Telegram ID.")
        return

        # Find player with eager loading
        result = await game_engine.db.execute(
            select(Player)
            .options(selectinload(Player.country), selectinload(Player.game))
            .where(Player.telegram_id == target_user_id)
        )
        player = result.scalar_one_or_none()

        if not player:
            await message.answer("❌ Игрок не найден.")
            return

        await message.answer(
            f"✅ *Регистрация одобрена!*\n\n"
            f"Игрок *{player.display_name}* теперь может участвовать в игре "
            f"за страну *{player.country.name}*.",
            parse_mode="Markdown",
        )

        # Notify player (if bot has access to send messages)
        try:
            bot = message.bot
            await bot.send_message(
                target_user_id,
                f"🎉 *Поздравляем!*\n\n"
                f"Ваша регистрация в игре *{player.game.name}* одобрена!\n"
                f"Вы управляете страной *{player.country.name}*.\n\n"
                f"Используйте /start для просмотра доступных команд.",
                parse_mode="Markdown",
            )
        except Exception:
            await message.answer("⚠️ Не удалось уведомить игрока (возможно, он не начинал диалог с ботом).")


async def reject_command(message: Message) -> None:
    """Handle /reject command"""
    user_id = message.from_user.id
    args = message.text.split()[1:]

    async for db in get_db():
        game_engine = GameEngine(db)

        # Check if user is admin
        if not await is_admin(user_id, game_engine.db):
            await message.answer("❌ У вас нет прав администратора.")
            return

        # Get admin info
        result = await game_engine.db.execute(select(Player).where(Player.telegram_id == user_id))
        result.scalar_one_or_none()

    if not args:
        await message.answer("❌ Укажите Telegram ID игрока: `/reject 123456789`")
        return

    try:
        target_user_id = int(args[0])
    except ValueError:
        await message.answer("❌ Некорректный Telegram ID.")
        return

        # Find and delete player with eager loading
        result = await game_engine.db.execute(
            select(Player).options(selectinload(Player.country)).where(Player.telegram_id == target_user_id)
        )
        player = result.scalar_one_or_none()

        if not player:
            await message.answer("❌ Игрок не найден.")
            return

        player_name = player.display_name
        country_name = player.country.name if player.country else "без страны"

        # Delete player and country
        if player.country:
            await game_engine.db.delete(player.country)
        await game_engine.db.delete(player)
        await game_engine.db.commit()

        await message.answer(
            f"❌ *Регистрация отклонена*\n\n" f"Заявка игрока *{player_name}* ({country_name}) отклонена и удалена.",
            parse_mode="Markdown",
        )

        # Notify player
        try:
            bot = message.bot
            await bot.send_message(
                target_user_id,
                "❌ *Регистрация отклонена*\n\n"
                "К сожалению, ваша заявка на участие в игре была отклонена администратором.\n"
                "Вы можете попробовать зарегистрироваться снова с помощью команды /register.",
                parse_mode="Markdown",
            )
        except Exception:
            pass


async def game_stats_command(message: Message) -> None:
    """Handle /game_stats command"""
    user_id = message.from_user.id

    async for db in get_db():
        game_engine = GameEngine(db)

        # Check if user is admin
        if not await is_admin(user_id, game_engine.db):
            await message.answer("❌ У вас нет прав администратора.")
            return

        # Get admin info
        result = await game_engine.db.execute(select(Player).where(Player.telegram_id == user_id))
        admin = result.scalar_one_or_none()

        stats = await game_engine.get_game_statistics(admin.game_id)

        await message.answer(
            f"📊 *Статистика игры*\n\n"
            f"*Название:* {stats['game_name']}\n"
            f"*Статус:* {stats['status']}\n"
            f"*Стран:* {stats['countries_count']}\n"
            f"*Игроков:* {stats['players_count']}\n"
            f"*Постов:* {stats['posts_count']}\n"
            f"*Создана:* {stats['created_at'].strftime('%d.%m.%Y %H:%M')}\n"
            f"*Обновлена:* {stats['updated_at'].strftime('%d.%m.%Y %H:%M')}",
            parse_mode="Markdown",
        )


async def posts_command(message: Message) -> None:
    """Handle /posts command - show posts without verdicts"""
    user_id = message.from_user.id

    async for db in get_db():
        game_engine = GameEngine(db)

        # Check if user is admin
        if not await is_admin(user_id, game_engine.db):
            await message.answer("❌ У вас нет прав администратора.")
            return

        # Get admin info
        result = await game_engine.db.execute(select(Player).where(Player.telegram_id == user_id))
        admin = result.scalar_one_or_none()

        # Get posts without verdicts
        posts = await game_engine.get_game_posts(admin.game_id)
        posts_without_verdicts = [post for post in posts if not post.verdicts]

        if not posts_without_verdicts:
            await message.answer("📝 Нет постов, ожидающих вердикта.")
            return

        posts_text = "📝 *Посты без вердиктов:*\n\n"

        for post in posts_without_verdicts:
            posts_text += f"*Пост #{post.id}*\n"
            posts_text += f"*Автор:* {post.author.country.name if post.author.country else post.author.display_name}\n"
            posts_text += f"*Дата:* {post.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            posts_text += f"*Содержание:*\n{post.content}\n\n"
            posts_text += f"⚖️ Вердикт: `/verdict {post.id} <результат>`\n\n"
            posts_text += "─" * 30 + "\n\n"

        # Split if too long
        if len(posts_text) > 4000:
            parts = posts_text.split("─" * 30)
            current_message = "📝 *Посты без вердиктов:*\n\n"

            for part in parts:
                if part.strip():
                    if len(current_message + part) > 4000:
                        await message.answer(current_message, parse_mode="Markdown")
                        current_message = part
                    else:
                        current_message += part

            if current_message.strip():
                await message.answer(current_message, parse_mode="Markdown")
        else:
            await message.answer(posts_text, parse_mode="Markdown")


async def create_game_command(message: Message) -> None:
    """Handle /create_game command"""
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
                "Используйте: <code>/create_game Название игры | Сеттинг | Лет за сутки | Макс очков</code>\n\n"
                "Пример: <code>/create_game Древний мир | Античность | 10 | 30</code>\n"
                "Макс очков - максимальная сумма очков для аспектов страны (по умолчанию 30)",
                parse_mode="HTML",
            )
            return

        try:
            # Parse arguments
            parts = [part.strip() for part in args[1].split("|")]
            if len(parts) < 3 or len(parts) > 4:
                raise ValueError("Неверное количество параметров")

            game_name, setting, years_per_day_str = parts[:3]
            max_points_str = parts[3] if len(parts) == 4 else "30"

            years_per_day = int(years_per_day_str)
            max_points = int(max_points_str)

            if not game_name or not setting:
                raise ValueError("Название игры и сеттинг не могут быть пустыми")

            if years_per_day < 1 or years_per_day > 365:
                raise ValueError("Количество лет за сутки должно быть от 1 до 365")

            if max_points < 10 or max_points > 100:
                raise ValueError("Максимальное количество очков должно быть от 10 до 100")

        except ValueError as e:
            await message.answer(
                f"❌ Ошибка в параметрах: {e}\n\n"
                "Используйте: <code>/create_game Название игры | Сеттинг | Лет за сутки | Макс очков</code>\n\n"
                "Пример: <code>/create_game Древний мир | Античность | 10 | 30</code>",
                parse_mode="HTML",
            )
            return

        # Create game
        game = await game_engine.create_game(
            name=game_name,
            description=f"Игра в сеттинге '{setting}'",
            setting=setting,
            max_players=20,
            years_per_day=years_per_day,
            max_points=max_points,
        )

        # Create admin player
        username = message.from_user.username
        display_name = message.from_user.full_name or f"Admin_{user_id}"

        admin_player = await game_engine.create_player(
            game_id=game.id, telegram_id=user_id, username=username, display_name=display_name, role=PlayerRole.ADMIN
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
            f"✅ <b>Игра успешно создана!</b>\n\n"
            f"<b>Название:</b> {game_name}\n"
            f"<b>Сеттинг:</b> {setting}\n"
            f"<b>Лет за сутки:</b> {years_per_day}\n"
            f"<b>Макс очков для стран:</b> {max_points}\n"
            f"<b>ID игры:</b> {game.id}\n\n"
            f"Вы назначены администратором игры и получили страну '{admin_country.name}'.\n\n"
            f"Теперь игроки могут регистрироваться в игре командой /register",
            parse_mode="HTML",
        )
        break


def register_admin_handlers(dp: Dispatcher) -> None:
    """Register admin handlers"""
    dp.message.register(admin_command, Command("admin"))
    dp.message.register(approve_command, Command("approve"))
    dp.message.register(reject_command, Command("reject"))
    dp.message.register(game_stats_command, Command("game_stats"))
    dp.message.register(posts_command, Command("posts"))
    dp.message.register(create_game_command, Command("create_game"))
