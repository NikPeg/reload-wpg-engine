"""
Admin handlers
"""

from aiogram import Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select

from wpg_engine.core.engine import GameEngine
from wpg_engine.models import Player, PlayerRole


async def admin_command(message: Message, game_engine: GameEngine) -> None:
    """Handle /admin command - admin panel"""
    user_id = message.from_user.id

    # Check if user is admin
    result = await game_engine.db.execute(
        select(Player).where(Player.telegram_id == user_id)
    )
    player = result.scalar_one_or_none()

    if not player or player.role != PlayerRole.ADMIN:
        await message.answer("❌ У вас нет прав администратора.")
        return

    await message.answer(
        f"⚙️ *Панель администратора*\n\n"
        f"*Игра:* {player.game.name}\n"
        f"*Сеттинг:* {player.game.setting}\n"
        f"*Статус:* {player.game.status.value}\n\n"
        f"*Доступные команды:*\n"
        f"📋 /pending - заявки на регистрацию\n"
        f"📊 /game_stats - статистика игры\n"
        f"✅ /approve <user_id> - одобрить регистрацию\n"
        f"❌ /reject <user_id> - отклонить регистрацию\n"
        f"📝 /posts - непроверенные посты\n"
        f"⚖️ /verdict <post_id> <result> - вынести вердикт"
    )


async def pending_command(message: Message, game_engine: GameEngine) -> None:
    """Handle /pending command - show pending registrations"""
    user_id = message.from_user.id

    # Check if user is admin
    result = await game_engine.db.execute(
        select(Player).where(Player.telegram_id == user_id)
    )
    admin = result.scalar_one_or_none()

    if not admin or admin.role != PlayerRole.ADMIN:
        await message.answer("❌ У вас нет прав администратора.")
        return

    # Get pending players (players without approved status)
    # For now, we'll consider all non-admin players as pending
    result = await game_engine.db.execute(
        select(Player)
        .where(Player.game_id == admin.game_id)
        .where(Player.role == PlayerRole.PLAYER)
        .where(Player.country_id.is_not(None))
    )
    pending_players = result.scalars().all()

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
                    await message.answer(current_message)
                    current_message = part
                else:
                    current_message += part

        if current_message.strip():
            await message.answer(current_message)
    else:
        await message.answer(pending_text)


async def approve_command(message: Message, game_engine: GameEngine) -> None:
    """Handle /approve command"""
    user_id = message.from_user.id
    args = message.text.split()[1:]

    # Check if user is admin
    result = await game_engine.db.execute(
        select(Player).where(Player.telegram_id == user_id)
    )
    admin = result.scalar_one_or_none()

    if not admin or admin.role != PlayerRole.ADMIN:
        await message.answer("❌ У вас нет прав администратора.")
        return

    if not args:
        await message.answer("❌ Укажите Telegram ID игрока: `/approve 123456789`")
        return

    try:
        target_user_id = int(args[0])
    except ValueError:
        await message.answer("❌ Некорректный Telegram ID.")
        return

    # Find player
    result = await game_engine.db.execute(
        select(Player).where(Player.telegram_id == target_user_id)
    )
    player = result.scalar_one_or_none()

    if not player:
        await message.answer("❌ Игрок не найден.")
        return

    await message.answer(
        f"✅ *Регистрация одобрена!*\n\n"
        f"Игрок *{player.display_name}* теперь может участвовать в игре "
        f"за страну *{player.country.name}*."
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
        )
    except Exception:
        await message.answer(
            "⚠️ Не удалось уведомить игрока (возможно, он не начинал диалог с ботом)."
        )


async def reject_command(message: Message, game_engine: GameEngine) -> None:
    """Handle /reject command"""
    user_id = message.from_user.id
    args = message.text.split()[1:]

    # Check if user is admin
    result = await game_engine.db.execute(
        select(Player).where(Player.telegram_id == user_id)
    )
    admin = result.scalar_one_or_none()

    if not admin or admin.role != PlayerRole.ADMIN:
        await message.answer("❌ У вас нет прав администратора.")
        return

    if not args:
        await message.answer("❌ Укажите Telegram ID игрока: `/reject 123456789`")
        return

    try:
        target_user_id = int(args[0])
    except ValueError:
        await message.answer("❌ Некорректный Telegram ID.")
        return

    # Find and delete player
    result = await game_engine.db.execute(
        select(Player).where(Player.telegram_id == target_user_id)
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
        f"Заявка игрока *{player_name}* ({country_name}) отклонена и удалена."
    )

    # Notify player
    try:
        bot = message.bot
        await bot.send_message(
            target_user_id,
            "❌ *Регистрация отклонена*\n\n"
            "К сожалению, ваша заявка на участие в игре была отклонена администратором.\n"
            "Вы можете попробовать зарегистрироваться снова с помощью команды /register.",
        )
    except Exception:
        pass


async def game_stats_command(message: Message, game_engine: GameEngine) -> None:
    """Handle /game_stats command"""
    user_id = message.from_user.id

    # Check if user is admin
    result = await game_engine.db.execute(
        select(Player).where(Player.telegram_id == user_id)
    )
    admin = result.scalar_one_or_none()

    if not admin or admin.role != PlayerRole.ADMIN:
        await message.answer("❌ У вас нет прав администратора.")
        return

    stats = await game_engine.get_game_statistics(admin.game_id)

    await message.answer(
        f"📊 *Статистика игры*\n\n"
        f"*Название:* {stats['game_name']}\n"
        f"*Статус:* {stats['status'].value}\n"
        f"*Стран:* {stats['countries_count']}\n"
        f"*Игроков:* {stats['players_count']}\n"
        f"*Постов:* {stats['posts_count']}\n"
        f"*Создана:* {stats['created_at'].strftime('%d.%m.%Y %H:%M')}\n"
        f"*Обновлена:* {stats['updated_at'].strftime('%d.%m.%Y %H:%M')}"
    )


async def posts_command(message: Message, game_engine: GameEngine) -> None:
    """Handle /posts command - show posts without verdicts"""
    user_id = message.from_user.id

    # Check if user is admin
    result = await game_engine.db.execute(
        select(Player).where(Player.telegram_id == user_id)
    )
    admin = result.scalar_one_or_none()

    if not admin or admin.role != PlayerRole.ADMIN:
        await message.answer("❌ У вас нет прав администратора.")
        return

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
                    await message.answer(current_message)
                    current_message = part
                else:
                    current_message += part

        if current_message.strip():
            await message.answer(current_message)
    else:
        await message.answer(posts_text)


def register_admin_handlers(dp: Dispatcher) -> None:
    """Register admin handlers"""
    dp.message.register(admin_command, Command("admin"))
    dp.message.register(pending_command, Command("pending"))
    dp.message.register(approve_command, Command("approve"))
    dp.message.register(reject_command, Command("reject"))
    dp.message.register(game_stats_command, Command("game_stats"))
    dp.message.register(posts_command, Command("posts"))
