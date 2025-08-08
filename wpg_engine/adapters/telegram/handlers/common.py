"""
Common handlers for all users
"""

from aiogram import Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from wpg_engine.core.engine import GameEngine
from wpg_engine.models import Player, PlayerRole, get_db


async def start_command(message: Message) -> None:
    """Handle /start command"""
    user_id = message.from_user.id

    async for db in get_db():
        game_engine = GameEngine(db)

        # Check if user is already registered
        result = await game_engine.db.execute(
            select(Player)
            .options(selectinload(Player.game), selectinload(Player.country))
            .where(Player.telegram_id == user_id)
            .limit(1)
        )
        player = result.scalar_one_or_none()

        # Check if user is admin (from .env)
        from wpg_engine.config.settings import settings

        is_admin_user = settings.telegram.admin_id and user_id == settings.telegram.admin_id

        # Check if any games exist
        from wpg_engine.models import Game

        result = await game_engine.db.execute(select(Game))
        existing_games = result.scalars().all()

        break

    if player:
        if player.role == PlayerRole.ADMIN:
            # Use HTML parsing to avoid markdown issues
            from html import escape

            display_name = escape(player.display_name)
            game_name = escape(player.game.name)

            await message.answer(
                f"🎯 Добро пожаловать, <b>{display_name}</b>!\n\n"
                f"Вы администратор игры <b>{game_name}</b>.\n\n"
                f"<b>Доступные команды:</b>\n"
                f"👤 /stats - информация о вашей стране\n"
                f"⚙️ /admin - панель администратора\n"
                f"📊 /game_stats - статистика игры\n"
                f"🎮 /create_game - создать новую игру\n"
                f"🔄 /register - перерегистрироваться (создать новую страну)",
                parse_mode="HTML",
            )
        else:
            # Use HTML parsing to avoid markdown issues
            from html import escape

            display_name = escape(player.display_name)
            country_name = escape(player.country.name if player.country else "страну не назначена")
            game_name = escape(player.game.name)

            # List of example messages for random selection
            examples = [
                "Собрать всех детей в огромную город-школу",
                "Начать строительство космического лифта",
                "Объявить войну соседней стране из-за спора о границах",
                "Создать новую религию на основе поклонения технологиям",
                "Провести массовую эвакуацию населения в подземные города",
                "Запустить программу по превращению пустыни в цветущий сад",
                "Установить дипломатические отношения с инопланетной цивилизацией",
                "Ввести всеобщий базовый доход для всех граждан",
                "Построить гигантскую стену вокруг всей страны",
                "Объявить о создании первого в мире города на воде",
            ]

            import random

            random_example = random.choice(examples)

            await message.answer(
                f"🎮 Добро пожаловать, <b>{display_name}</b>!\n\n"
                f"Вы играете за <b>{country_name}</b> "
                f"в игре <b>{game_name}</b>.\n\n"
                f"<b>Доступные команды:</b>\n"
                f"👤 /stats - информация о вашей стране\n"
                f"🌍 /world - информация о других странах\n"
                f"🔄 /register - перерегистрироваться (создать новую страну)\n\n"
                f"напиши свое, задай вопрос или начни проект! Например: <code>{random_example}</code>",
                parse_mode="HTML",
            )
    elif is_admin_user:
        # Admin user but no games exist
        if not existing_games:
            await message.answer(
                "🎯 Добро пожаловать, <b>Администратор</b>!\n\n"
                "❌ В данный момент нет активных игр.\n\n"
                "Используйте команду /create_game для создания новой игры.\n"
                "Формат: <code>/create_game Название игры | Сеттинг | Лет за сутки</code>\n\n"
                "Пример: <code>/create_game Древний мир | Античность | 10</code>",
                parse_mode="HTML",
            )
        else:
            await message.answer(
                "🎯 Добро пожаловать, <b>Администратор</b>!\n\n"
                "Для участия в игре используйте команду /register для регистрации.",
                parse_mode="HTML",
            )
    else:
        await message.answer(
            "👋 Добро пожаловать в <b>WPG Engine</b>!\n\n"
            "Это бот для проведения текстовых военно-политических игр.\n\n"
            "Для участия в игре вам необходимо зарегистрироваться.\n"
            "Используйте команду /register для начала регистрации.\n\n"
            "<b>Что такое ВПИ?</b>\n"
            "Военно-политическая игра - это стратегическая ролевая игра, "
            "где игроки управляют странами, развивают их по 10 аспектам "
            "и взаимодействуют друг с другом через дипломатию, торговлю и конфликты.",
            parse_mode="HTML",
        )


async def help_command(message: Message) -> None:
    """Handle /help command"""
    user_id = message.from_user.id

    async for db in get_db():
        game_engine = GameEngine(db)

        # Check if user is registered
        result = await game_engine.db.execute(
            select(Player)
            .options(selectinload(Player.game), selectinload(Player.country))
            .where(Player.telegram_id == user_id)
            .limit(1)
        )
        player = result.scalar_one_or_none()
        break

    if not player:
        await message.answer(
            "<b>Справка по командам:</b>\n\n"
            "/start - начать работу с ботом\n"
            "/register - зарегистрироваться в игре (или перерегистрироваться)\n"
            "/help - показать эту справку",
            parse_mode="HTML",
        )
    elif player.role == PlayerRole.ADMIN:
        await message.answer(
            "<b>Справка по командам (Администратор):</b>\n\n"
            "<b>Общие команды:</b>\n"
            "/start - главное меню\n"
            "/stats - информация о вашей стране\n"
            "/register - перерегистрироваться (создать новую страну)\n"
            "/help - показать эту справку\n\n"
            "<b>Команды администратора:</b>\n"
            "/admin - панель администратора\n"
            "/game_stats - статистика игры\n"
            "/create_game - создать новую игру\n"
            "/approve &lt;user_id&gt; - одобрить регистрацию\n"
            "/reject &lt;user_id&gt; - отклонить регистрацию\n\n"
            "<b>Отправка сообщений:</b>\n"
            "Просто напишите сообщение - оно будет отправлено администратору",
            parse_mode="HTML",
        )
    else:
        await message.answer(
            "<b>Справка по командам (Игрок):</b>\n\n"
            "/start - главное меню\n"
            "/stats - информация о вашей стране\n"
            "/world - информация о других странах\n"
            "/register - перерегистрироваться (создать новую страну)\n"
            "/help - показать эту справку\n\n"
            "<b>Отправка сообщений:</b>\n"
            "Просто напишите сообщение - оно будет отправлено администратору",
            parse_mode="HTML",
        )


def register_common_handlers(dp: Dispatcher) -> None:
    """Register common handlers"""
    dp.message.register(start_command, Command("start"))
    dp.message.register(help_command, Command("help"))
