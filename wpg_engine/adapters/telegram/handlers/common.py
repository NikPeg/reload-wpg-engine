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
        )
        player = result.scalar_one_or_none()
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
                f"📝 /post - отправить пост с действием\n"
                f"⚙️ /admin - панель администратора\n"
                f"📋 /pending - заявки на регистрацию\n"
                f"📊 /game_stats - статистика игры",
                parse_mode="HTML"
            )
        else:
            # Use HTML parsing to avoid markdown issues
            from html import escape
            display_name = escape(player.display_name)
            country_name = escape(player.country.name if player.country else 'страну не назначена')
            game_name = escape(player.game.name)
            
            await message.answer(
                f"🎮 Добро пожаловать, <b>{display_name}</b>!\n\n"
                f"Вы играете за <b>{country_name}</b> "
                f"в игре <b>{game_name}</b>.\n\n"
                f"<b>Доступные команды:</b>\n"
                f"👤 /stats - информация о вашей стране\n"
                f"📝 /post - отправить пост с действием\n"
                f"🌍 /world - информация о других странах",
                parse_mode="HTML"
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
            parse_mode="HTML"
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
        )
        player = result.scalar_one_or_none()
        break

    if not player:
        await message.answer(
            "<b>Справка по командам:</b>\n\n"
            "/start - начать работу с ботом\n"
            "/register - зарегистрироваться в игре\n"
            "/help - показать эту справку",
            parse_mode="HTML"
        )
    elif player.role == PlayerRole.ADMIN:
        await message.answer(
            "<b>Справка по командам (Администратор):</b>\n\n"
            "<b>Общие команды:</b>\n"
            "/start - главное меню\n"
            "/stats - информация о вашей стране\n"
            "/post - отправить пост с действием\n"
            "/help - показать эту справку\n\n"
            "<b>Команды администратора:</b>\n"
            "/admin - панель администратора\n"
            "/pending - заявки на регистрацию\n"
            "/game_stats - статистика игры\n"
            "/approve &lt;user_id&gt; - одобрить регистрацию\n"
            "/reject &lt;user_id&gt; - отклонить регистрацию",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "<b>Справка по командам (Игрок):</b>\n\n"
            "/start - главное меню\n"
            "/stats - информация о вашей стране\n"
            "/post - отправить пост с действием\n"
            "/world - информация о других странах\n"
            "/help - показать эту справку",
            parse_mode="HTML"
        )


def register_common_handlers(dp: Dispatcher) -> None:
    """Register common handlers"""
    dp.message.register(start_command, Command("start"))
    dp.message.register(help_command, Command("help"))
