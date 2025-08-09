"""
Player handlers
"""

from aiogram import Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from wpg_engine.adapters.telegram.utils import escape_html
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

        aspects_text += f"{emoji} <b>{name}</b>: {value}/10\n"
        aspects_text += f"   {rating_bar}\n"
        aspects_text += f"   <i>{escape_html(description)}</i>\n\n"

    # Build country info message
    country_info = "🏛️ <b>Информация о вашей стране</b>\n\n"
    country_info += f"<b>Название:</b> {escape_html(country.name)}\n"

    # Show synonyms if they exist
    if country.synonyms:
        synonyms_text = ", ".join([escape_html(syn) for syn in country.synonyms])
        country_info += f"<b>Синонимы:</b> {synonyms_text}\n"

    country_info += f"<b>Столица:</b> {escape_html(country.capital or 'Не указана')}\n"
    country_info += f"<b>Население:</b> {country.population:,} чел.\n\n"
    country_info += f"<b>Описание:</b>\n<i>{escape_html(country.description)}</i>\n\n"
    country_info += f"<b>Аспекты развития:</b>\n\n{aspects_text}"
    country_info += f"<b>Игра:</b> {escape_html(player.game.name)}\n"
    country_info += f"<b>Сеттинг:</b> {escape_html(player.game.setting)}\n"
    country_info += f"<b>Темп:</b> {player.game.years_per_day} лет/день"

    await message.answer(country_info, parse_mode="HTML")


# Removed post_command and process_post_content functions
# Posts are now handled through direct messages


async def world_command(message: Message) -> None:
    """Handle /world command - show info about other countries, sent one by one"""
    user_id = message.from_user.id

    async for db in get_db():
        game_engine = GameEngine(db)

        # Get player
        result = await game_engine.db.execute(
            select(Player)
            .options(selectinload(Player.country))
            .where(Player.telegram_id == user_id)
        )
        player = result.scalar_one_or_none()

        if not player:
            await message.answer(
                "❌ Вы не зарегистрированы в игре. Используйте /register"
            )
            return

        # Check if user is admin
        from wpg_engine.core.admin_utils import is_admin

        user_is_admin = await is_admin(user_id, game_engine.db)

        # Get all countries in the game
        game = await game_engine.get_game(player.game_id)
        if not game:
            await message.answer("❌ Игра не найдена.")
            return
        break

    # Send header message
    await message.answer("🌍 <b>Информация о странах мира</b>", parse_mode="HTML")

    # Aspect emojis and names
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

    # Send info about each country in separate messages
    for country in game.countries:
        if not user_is_admin and country.id == player.country_id:
            continue  # Skip own country for regular players, but show for admins

        country_info = f"🏛️ <b>{escape_html(country.name)}</b>\n"

        # Show synonyms if they exist
        if country.synonyms:
            synonyms_text = ", ".join([escape_html(syn) for syn in country.synonyms])
            country_info += f"<b>Синонимы:</b> {synonyms_text}\n"

        country_info += (
            f"<b>Столица:</b> {escape_html(country.capital or 'Неизвестна')}\n"
        )

        if country.population:
            country_info += f"<b>Население:</b> {country.population:,} чел.\n"

        if country.description and user_is_admin:
            country_info += (
                f"<b>Описание:</b> <i>{escape_html(country.description)}</i>\n"
            )

        country_info += "\n"

        if user_is_admin:
            # Admin sees all aspects with descriptions
            aspects = country.get_aspects()
            country_info += "<b>Все аспекты развития:</b>\n\n"

            for aspect, data in aspects.items():
                emoji = aspect_emojis.get(aspect, "📊")
                name = aspect_names.get(aspect, aspect)
                value = data["value"]
                description = data["description"] or "Нет описания"

                # Add rating bar
                rating_bar = "█" * value + "░" * (10 - value)

                country_info += f"{emoji} <b>{name}</b>: {value}/10\n"
                country_info += f"   {rating_bar}\n"
                country_info += f"   <i>{escape_html(description)}</i>\n\n"

            # Add hidden marker for admin editing (invisible to user)
            country_info += f"\n<code>[EDIT_COUNTRY:{country.id}]</code>"
        else:
            # Regular players see only public aspects (values only)
            public_aspects = country.get_public_aspects()

            if public_aspects:
                country_info += "<b>Известная информация:</b>\n"

                for aspect, data in public_aspects.items():
                    emoji = aspect_emojis.get(aspect, "📊")
                    name = aspect_names.get(aspect, aspect)
                    value = data["value"]
                    country_info += f"  {emoji} {name}: {value}/10\n"
            else:
                country_info += "<i>Публичная информация недоступна</i>\n"

        # Send country info as separate message
        await message.answer(country_info, parse_mode="HTML")


def register_player_handlers(dp: Dispatcher) -> None:
    """Register player handlers"""
    dp.message.register(stats_command, Command("stats"))
    dp.message.register(world_command, Command("world"))
