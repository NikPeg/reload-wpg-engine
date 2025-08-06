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
            select(Player)
            .options(selectinload(Player.game))
            .where(Player.telegram_id == user_id)
        )
        player = result.scalar_one_or_none()
        break

    if not player:
        await message.answer(
            "⚙️ *Панель администратора*\n\n"
            "❌ Вы не зарегистрированы в игре.\n"
            "Используйте /register для регистрации.\n\n"
            "*Доступные команды:*\n"
            "📋 /pending - заявки на регистрацию\n"
            "📊 /game_stats - статистика игры\n"
            "✅ /approve <user_id> - одобрить регистрацию\n"
            "❌ /reject <user_id> - отклонить регистрацию\n"
            "📝 /posts - непроверенные посты\n"
            "⚖️ /verdict <post_id> <result> - вынести вердикт",
            parse_mode="Markdown"
        )
        return

    await message.answer(
        f"⚙️ *Панель администратора*\n\n"
        f"*Игра:* {player.game.name}\n"
        f"*Сеттинг:* {player.game.setting}\n"
        f"*Статус:* {player.game.status}\n\n"
        f"*Доступные команды:*\n"
        f"📋 /pending - заявки на регистрацию\n"
        f"📊 /game_stats - статистика игры\n"
        f"✅ /approve <user_id> - одобрить регистрацию\n"
        f"❌ /reject <user_id> - отклонить регистрацию\n"
        f"📝 /posts - непроверенные посты\n"
        f"⚖️ /verdict <post_id> <result> - вынести вердикт",
        parse_mode="Markdown"
    )


async def pending_command(message: Message) -> None:
    """Handle /pending command - show pending registrations"""
    user_id = message.from_user.id

    async for db in get_db():
        game_engine = GameEngine(db)
        
        # Check if user is admin
        if not await is_admin(user_id, game_engine.db):
            await message.answer("❌ У вас нет прав администратора.")
            return

        # Get admin info with eager loading
        result = await game_engine.db.execute(
            select(Player)
            .options(selectinload(Player.game))
            .where(Player.telegram_id == user_id)
        )
        admin = result.scalar_one_or_none()

        # Get pending players with eager loading
        result = await game_engine.db.execute(
            select(Player)
            .options(selectinload(Player.country))
            .where(Player.game_id == admin.game_id)
            .where(Player.role == PlayerRole.PLAYER)
            .where(Player.country_id.is_not(None))
        )
        pending_players = result.scalars().all()
        break

    if not pending_players:
        await message.answer("📋 Нет заявок на рассмотрение.")
        return

    pending_text = "📋 *Заявки на регистрацию:*\n\n"

    for player in pending_players:
        country = player.country
        aspects = country.get_aspects_values_only()

        pending_text += f"👤 *Игрок:* {player.display_name}\n"
        pending_text += f"*Telegram ID:* `{player.telegram_id}`\n"
        pending_text += f"*Username:* @{player.username or 'не указан'}\n\n"

        pending_text += f"🏛️ *Страна:* {country.name}\n"
        pending_text += f"*Столица:* {country.capital}\n"
        pending_text += f"*Население:* {country.population:,}\n"
        pending_text += f"*Описание:* {country.description[:100]}...\n\n"

        pending_text += "*Аспекты:*\n"
        aspect_names = {
            "economy": "💰 Экономика",
            "military": "⚔️ Военное дело",
            "foreign_policy": "🤝 Внешняя политика",
            "territory": "🗺️ Территория",
            "technology": "🔬 Технологичность",
            "religion_culture": "🏛️ Религия и культура",
            "governance_law": "⚖️ Управление и право",
            "construction_infrastructure": "🏗️ Строительство",
            "social_relations": "👥 Общественные отношения",
            "intelligence": "🕵️ Разведка",
        }

        for aspect, value in aspects.items():
            name = aspect_names.get(aspect, aspect)
            pending_text += f"  {name}: {value}/10\n"

        pending_text += f"\n✅ Одобрить: `/approve {player.telegram_id}`\n"
        pending_text += f"❌ Отклонить: `/reject {player.telegram_id}`\n\n"
        pending_text += "─" * 30 + "\n\n"

    # Split message if too long
    if len(pending_text) > 4000:
        parts = pending_text.split("─" * 30)
        current_message = "📋 *Заявки на регистрацию:*\n\n"

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
        await message.answer(pending_text, parse_mode="Markdown")


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
        result = await game_engine.db.execute(
            select(Player).where(Player.telegram_id == user_id)
        )
        admin = result.scalar_one_or_none()

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
            parse_mode="Markdown"
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
                parse_mode="Markdown"
            )
        except Exception:
            await message.answer(
                "⚠️ Не удалось уведомить игрока (возможно, он не начинал диалог с ботом)."
            )


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
        result = await game_engine.db.execute(
            select(Player).where(Player.telegram_id == user_id)
        )
        admin = result.scalar_one_or_none()

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
            select(Player)
            .options(selectinload(Player.country))
            .where(Player.telegram_id == target_user_id)
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
            f"❌ *Регистрация отклонена*\n\n"
            f"Заявка игрока *{player_name}* ({country_name}) отклонена и удалена.",
            parse_mode="Markdown"
        )

        # Notify player
        try:
            bot = message.bot
            await bot.send_message(
                target_user_id,
                "❌ *Регистрация отклонена*\n\n"
                "К сожалению, ваша заявка на участие в игре была отклонена администратором.\n"
                "Вы можете попробовать зарегистрироваться снова с помощью команды /register.",
                parse_mode="Markdown"
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
        result = await game_engine.db.execute(
            select(Player).where(Player.telegram_id == user_id)
        )
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
            parse_mode="Markdown"
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
        result = await game_engine.db.execute(
            select(Player).where(Player.telegram_id == user_id)
        )
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


def register_admin_handlers(dp: Dispatcher) -> None:
    """Register admin handlers"""
    dp.message.register(admin_command, Command("admin"))
    dp.message.register(pending_command, Command("pending"))
    dp.message.register(approve_command, Command("approve"))
    dp.message.register(reject_command, Command("reject"))
    dp.message.register(game_stats_command, Command("game_stats"))
    dp.message.register(posts_command, Command("posts"))
