"""
Common handlers for all users
"""

from aiogram import Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select

from wpg_engine.core.engine import GameEngine
from wpg_engine.models import Player, PlayerRole


async def start_command(message: Message, game_engine: GameEngine) -> None:
    """Handle /start command"""
    user_id = message.from_user.id

    # Check if user is already registered
    result = await game_engine.db.execute(
        select(Player).where(Player.telegram_id == user_id)
    )
    player = result.scalar_one_or_none()

    if player:
        if player.role == PlayerRole.ADMIN:
            await message.answer(
                f"🎯 Добро пожаловать, *{player.display_name}*!\n\n"
                f"Вы администратор игры *{player.game.name}*.\n\n"
                f"*Доступные команды:*\n"
                f"👤 /stats - информация о вашей стране\n"
                f"📝 /post - отправить пост с действием\n"
                f"⚙️ /admin - панель администратора\n"
                f"📋 /pending - заявки на регистрацию\n"
                f"📊 /game_stats - статистика игры"
            )
        else:
            await message.answer(
                f"🎮 Добро пожаловать, *{player.display_name}*!\n\n"
                f"Вы играете за *{player.country.name if player.country else 'страну не назначена'}* "
                f"в игре *{player.game.name}*.\n\n"
                f"*Доступные команды:*\n"
                f"👤 /stats - информация о вашей стране\n"
                f"📝 /post - отправить пост с действием\n"
                f"🌍 /world - информация о других странах"
            )
    else:
        await message.answer(
            "👋 Добро пожаловать в *WPG Engine*!\n\n"
            "Это бот для проведения текстовых военно-политических игр.\n\n"
            "Для участия в игре вам необходимо зарегистрироваться.\n"
            "Используйте команду /register для начала регистрации.\n\n"
            "*Что такое ВПИ?*\n"
            "Военно-политическая игра - это стратегическая ролевая игра, "
            "где игроки управляют странами, развивают их по 10 аспектам "
            "и взаимодействуют друг с другом через дипломатию, торговлю и конфликты."
        )


async def help_command(message: Message, game_engine: GameEngine) -> None:
    """Handle /help command"""
    user_id = message.from_user.id

    # Check if user is registered
    result = await game_engine.db.execute(
        select(Player).where(Player.telegram_id == user_id)
    )
    player = result.scalar_one_or_none()

    if not player:
        await message.answer(
            "*Справка по командам:*\n\n"
            "/start - начать работу с ботом\n"
            "/register - зарегистрироваться в игре\n"
            "/help - показать эту справку"
        )
    elif player.role == PlayerRole.ADMIN:
        await message.answer(
            "*Справка по командам (Администратор):*\n\n"
            "*Общие команды:*\n"
            "/start - главное меню\n"
            "/stats - информация о вашей стране\n"
            "/post - отправить пост с действием\n"
            "/help - показать эту справку\n\n"
            "*Команды администратора:*\n"
            "/admin - панель администратора\n"
            "/pending - заявки на регистрацию\n"
            "/game_stats - статистика игры\n"
            "/approve <user_id> - одобрить регистрацию\n"
            "/reject <user_id> - отклонить регистрацию"
        )
    else:
        await message.answer(
            "*Справка по командам (Игрок):*\n\n"
            "/start - главное меню\n"
            "/stats - информация о вашей стране\n"
            "/post - отправить пост с действием\n"
            "/world - информация о других странах\n"
            "/help - показать эту справку"
        )


def register_common_handlers(dp: Dispatcher) -> None:
    """Register common handlers"""
    dp.message.register(start_command, Command("start"))
    dp.message.register(help_command, Command("help"))
