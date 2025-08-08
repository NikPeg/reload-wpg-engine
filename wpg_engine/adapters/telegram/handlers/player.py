"""
Player handlers
"""

from aiogram import Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from wpg_engine.core.engine import GameEngine
from wpg_engine.models import Player, get_db

# Removed PostStates - no longer needed


async def stats_command(message: Message) -> None:
    """Handle /stats command - show player's country info"""
    user_id = message.from_user.id

    async for db in get_db():
        game_engine = GameEngine(db)

        # Get player
        result = await game_engine.db.execute(
            select(Player)
            .options(selectinload(Player.country), selectinload(Player.game))
            .where(Player.telegram_id == user_id)
        )
        player = result.scalar_one_or_none()
        break

    if not player:
        await message.answer("❌ Вы не зарегистрированы в игре. Используйте /register")
        return

    if not player.country:
        await message.answer("❌ Вам не назначена страна. Обратитесь к администратору.")
        return

    country = player.country
    aspects = country.get_aspects()

    # Format aspects with emojis
    aspect_emojis = {
        "economy": "💰",
        "military": "⚔️",
        "foreign_policy": "🤝",
        "territory": "🗺️",
        "technology": "🔬",
        "religion_culture": "🏛️",
        "governance_law": "⚖️",
        "construction_infrastructure": "🏗️",
        "social_relations": "👥",
        "intelligence": "🕵️",
    }

    aspect_names = {
        "economy": "Экономика",
        "military": "Военное дело",
        "foreign_policy": "Внешняя политика",
        "territory": "Территория",
        "technology": "Технологичность",
        "religion_culture": "Религия и культура",
        "governance_law": "Управление и право",
        "construction_infrastructure": "Строительство",
        "social_relations": "Общественные отношения",
        "intelligence": "Разведка",
    }

    aspects_text = ""
    for aspect, data in aspects.items():
        emoji = aspect_emojis.get(aspect, "📊")
        name = aspect_names.get(aspect, aspect)
        value = data["value"]
        description = data["description"] or "Нет описания"

        # Add rating bar
        rating_bar = "█" * value + "░" * (10 - value)

        aspects_text += f"{emoji} *{name}*: {value}/10\n"
        aspects_text += f"   {rating_bar}\n"
        aspects_text += f"   _{description}_\n\n"

    await message.answer(
        f"🏛️ *Информация о вашей стране*\n\n"
        f"*Название:* {country.name}\n"
        f"*Столица:* {country.capital or 'Не указана'}\n"
        f"*Население:* {country.population:,} чел.\n\n"
        f"*Описание:*\n_{country.description}_\n\n"
        f"*Аспекты развития:*\n\n{aspects_text}"
        f"*Игра:* {player.game.name}\n"
        f"*Сеттинг:* {player.game.setting}\n"
        f"*Темп:* {player.game.years_per_day} лет/день",
        parse_mode="Markdown",
    )


# Removed post_command and process_post_content functions
# Posts are now handled through direct messages


async def world_command(message: Message) -> None:
    """Handle /world command - show public info about other countries"""
    user_id = message.from_user.id

    async for db in get_db():
        game_engine = GameEngine(db)

        # Get player
        result = await game_engine.db.execute(
            select(Player).options(selectinload(Player.country)).where(Player.telegram_id == user_id)
        )
        player = result.scalar_one_or_none()

        if not player:
            await message.answer("❌ Вы не зарегистрированы в игре. Используйте /register")
            return

        # Get all countries in the game
        game = await game_engine.get_game(player.game_id)
        if not game:
            await message.answer("❌ Игра не найдена.")
            return
        break

    countries_info = "🌍 *Информация о странах мира*\n\n"

    for country in game.countries:
        if country.id == player.country_id:
            continue  # Skip own country

        public_aspects = country.get_public_aspects()

        countries_info += f"🏛️ *{country.name}*\n"
        countries_info += f"*Столица:* {country.capital or 'Неизвестна'}\n"

        if public_aspects:
            countries_info += "*Известная информация:*\n"
            aspect_emojis = {
                "economy": "💰",
                "military": "⚔️",
                "foreign_policy": "🤝",
                "territory": "🗺️",
                "technology": "🔬",
                "religion_culture": "🏛️",
                "governance_law": "⚖️",
                "construction_infrastructure": "🏗️",
                "social_relations": "👥",
                "intelligence": "🕵️",
            }

            aspect_names = {
                "economy": "Экономика",
                "military": "Военное дело",
                "foreign_policy": "Внешняя политика",
                "territory": "Территория",
                "technology": "Технологичность",
                "religion_culture": "Религия и культура",
                "governance_law": "Управление и право",
                "construction_infrastructure": "Строительство",
                "social_relations": "Общественные отношения",
                "intelligence": "Разведка",
            }

            for aspect, data in public_aspects.items():
                emoji = aspect_emojis.get(aspect, "📊")
                name = aspect_names.get(aspect, aspect)
                value = data["value"]
                countries_info += f"  {emoji} {name}: {value}/10\n"

        else:
            countries_info += "_Публичная информация недоступна_\n"

        countries_info += "\n"

    if len(countries_info) > 4000:
        # Split message if too long
        parts = countries_info.split("\n\n")
        current_message = "🌍 *Информация о странах мира*\n\n"

        for part in parts[1:]:  # Skip header
            if len(current_message + part + "\n\n") > 4000:
                await message.answer(current_message, parse_mode="Markdown")
                current_message = part + "\n\n"
            else:
                current_message += part + "\n\n"

        if current_message.strip():
            await message.answer(current_message, parse_mode="Markdown")
    else:
        await message.answer(countries_info, parse_mode="Markdown")


def register_player_handlers(dp: Dispatcher) -> None:
    """Register player handlers"""
    dp.message.register(stats_command, Command("stats"))
    dp.message.register(world_command, Command("world"))
