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
from wpg_engine.models import Example, Game, Player, get_db

# Removed PostStates - no longer needed


def truncate_text(text: str, max_length: int = 300) -> str:
    """Truncate text to max_length characters, adding ... if truncated"""
    if not text:
        return text
    if len(text) <= max_length:
        return text
    return text[:max_length].rstrip() + "..."


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
        aspects_text += f"   <i>{escape_html(truncate_text(description, 300))}</i>\n\n"

    # Build country info message
    country_info = "🏛️ <b>Информация о вашей стране</b>\n\n"
    country_info += f"<b>Название:</b> {escape_html(country.name)}\n"

    # Show synonyms if they exist
    if country.synonyms:
        synonyms_text = ", ".join([escape_html(syn) for syn in country.synonyms])
        country_info += f"<b>Синонимы:</b> {synonyms_text}\n"

    country_info += f"<b>Столица:</b> {escape_html(country.capital or 'Не указана')}\n"
    country_info += f"<b>Население:</b> {country.population:,} чел.\n\n"
    country_info += f"<b>Описание:</b>\n<i>{escape_html(truncate_text(country.description, 300))}</i>\n\n"
    country_info += f"<b>Аспекты развития:</b>\n\n{aspects_text}"
    country_info += f"<b>Игра:</b> {escape_html(player.game.name)}\n"
    country_info += f"<b>Сеттинг:</b> {escape_html(player.game.setting)}\n"
    country_info += f"<b>Темп:</b> {player.game.years_per_day} лет/день"

    await message.answer(country_info, parse_mode="HTML")


# Removed post_command and process_post_content functions
# Posts are now handled through direct messages


async def world_command(message: Message) -> None:
    """Handle /world command - show info about countries"""
    user_id = message.from_user.id

    # Parse command arguments
    command_text = message.text or ""
    parts = command_text.split(maxsplit=1)
    country_name = parts[1].strip() if len(parts) > 1 else None

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

        user_is_admin = await is_admin(user_id, game_engine.db, message.chat.id)

        # Get all countries in the game
        game = await game_engine.get_game(player.game_id)
        if not game:
            await message.answer("❌ Игра не найдена.")
            return
        break

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

    if country_name:
        # Show info about specific country
        country = await game_engine.find_country_by_name_or_synonym(
            player.game_id, country_name
        )

        if not country:
            await message.answer(
                f"❌ Страна '{escape_html(country_name)}' не найдена.\n\n"
                f"Используйте /world без параметров для просмотра всех стран.",
                parse_mode="HTML",
            )
            return

        # Check if country is NPC (example or without active player)
        async for db in get_db():
            # Check if country is an example
            result = await db.execute(
                select(Example).where(Example.country_id == country.id)
            )
            is_example = result.scalar_one_or_none() is not None
            
            # Check if country has an active player
            result = await db.execute(
                select(Player).where(Player.country_id == country.id)
            )
            has_player = result.scalar_one_or_none() is not None
            break
        
        is_npc = is_example or not has_player
        
        country_info = ""
        if is_npc:
            country_info += "🤖 <b>NPC</b>\n\n"
        
        country_info += f"🏛️ <b>{escape_html(country.name)}</b>\n"

        country_info += (
            f"<b>Столица:</b> {escape_html(country.capital or 'Неизвестна')}\n"
        )

        if country.population:
            country_info += f"<b>Население:</b> {country.population:,} чел.\n"

        # Show description for all players when requesting specific country
        if country.description:
            country_info += f"<b>Описание:</b> <i>{escape_html(truncate_text(country.description, 300))}</i>\n"

        country_info += "\n"

        # When requesting specific country, show detailed info (like admin but without intelligence for regular players)
        aspects = country.get_aspects()
        country_info += "<b>Аспекты развития:</b>\n\n"

        for aspect, data in aspects.items():
            # Hide intelligence from regular players
            if aspect == "intelligence" and not user_is_admin:
                continue

            emoji = aspect_emojis.get(aspect, "📊")
            name = aspect_names.get(aspect, aspect)
            value = data["value"]
            description = data["description"] or "Нет описания"

            # Add rating bar
            rating_bar = "█" * value + "░" * (10 - value)

            country_info += f"{emoji} <b>{name}</b>: {value}/10\n"
            country_info += f"   {rating_bar}\n"
            country_info += (
                f"   <i>{escape_html(truncate_text(description, 300))}</i>\n\n"
            )

        # Add hidden marker for admin editing (invisible to user) only for admins
        if user_is_admin:
            country_info += f"\n<code>[EDIT_COUNTRY:{country.id}]</code>"

        # Send country info
        await message.answer(country_info, parse_mode="HTML")
    else:
        # Show info about all countries (original behavior)
        await message.answer("🌍 <b>Информация о странах мира</b>", parse_mode="HTML")

        # Send info about each country in separate messages
        for country in game.countries:
            if not user_is_admin and country.id == player.country_id:
                continue  # Skip own country for regular players, but show for admins

            # Check if country is NPC (example or without active player)
            async for db in get_db():
                # Check if country is an example
                result = await db.execute(
                    select(Example).where(Example.country_id == country.id)
                )
                is_example = result.scalar_one_or_none() is not None
                
                # Check if country has an active player
                result = await db.execute(
                    select(Player).where(Player.country_id == country.id)
                )
                has_player = result.scalar_one_or_none() is not None
                break
            
            is_npc = is_example or not has_player
            
            country_info = ""
            if is_npc:
                country_info += "🤖 <b>NPC</b>\n\n"
            
            country_info += f"🏛️ <b>{escape_html(country.name)}</b>\n"

            # Show synonyms if they exist
            if country.synonyms:
                synonyms_text = ", ".join(
                    [escape_html(syn) for syn in country.synonyms]
                )
                country_info += f"<b>Синонимы:</b> {synonyms_text}\n"

            country_info += (
                f"<b>Столица:</b> {escape_html(country.capital or 'Неизвестна')}\n"
            )

            if country.population:
                country_info += f"<b>Население:</b> {country.population:,} чел.\n"

            if country.description and user_is_admin:
                country_info += f"<b>Описание:</b> <i>{escape_html(truncate_text(country.description, 300))}</i>\n"

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
                    country_info += (
                        f"   <i>{escape_html(truncate_text(description, 300))}</i>\n\n"
                    )

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

                        # Hide intelligence from regular players
                        if aspect == "intelligence" and not user_is_admin:
                            continue

                        country_info += f"  {emoji} {name}: {value}/10\n"
                else:
                    country_info += "<i>Публичная информация недоступна</i>\n"

            # Send country info as separate message
            await message.answer(country_info, parse_mode="HTML")


async def examples_command(message: Message) -> None:
    """Handle /examples command - show example countries for new players"""
    user_id = message.from_user.id

    async for db in get_db():
        game_engine = GameEngine(db)

        # Get player to check if registered and get game_id
        result = await game_engine.db.execute(
            select(Player)
            .options(selectinload(Player.game))
            .where(Player.telegram_id == user_id)
        )
        player = result.scalar_one_or_none()

        if not player:
            # For unregistered users, show examples from first available game
            result = await game_engine.db.execute(select(Game).limit(1))
            game = result.scalar_one_or_none()
            if not game:
                await message.answer("❌ В данный момент нет активных игр.")
                return
            game_id = game.id
        else:
            game_id = player.game_id

        # Get all examples for the game
        result = await game_engine.db.execute(
            select(Example)
            .options(selectinload(Example.country))
            .where(Example.game_id == game_id)
            .order_by(Example.created_at.desc())
        )
        examples = result.scalars().all()
        break

    if not examples:
        await message.answer(
            "📝 <b>Примеры стран</b>\n\n"
            "Пока нет примеров стран для вашей игры.\n"
            "Администратор может добавить примеры с помощью команды /add_example",
            parse_mode="HTML",
        )
        return

    # Send initial message
    await message.answer(
        "📝 <b>Примеры стран для выбора</b>\n\n"
        "Вы можете выбрать одну из этих стран для игры.\n"
        "Просто ответьте на сообщение о стране словом <b>выбрать</b> или <b>выбираю</b>.",
        parse_mode="HTML",
    )

    # Aspect emojis and names for displaying
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

    # Send each example country as a separate message
    for example in examples:
        country = example.country
        country_text = f"🏛️ <b>{escape_html(country.name)}</b>\n\n"

        if country.capital:
            country_text += f"<b>Столица:</b> {escape_html(country.capital)}\n"
        if country.population:
            country_text += f"<b>Население:</b> {country.population:,} чел.\n"

        if country.description:
            country_text += (
                f"\n<b>Описание:</b>\n<i>{escape_html(country.description)}</i>\n"
            )

        country_text += "\n<b>Аспекты развития:</b>\n\n"

        # Show all aspects with descriptions
        aspects = country.get_aspects()
        for aspect, data in aspects.items():
            emoji = aspect_emojis.get(aspect, "📊")
            name = aspect_names.get(aspect, aspect)
            value = data["value"]
            description = data["description"] or "Нет описания"

            # Add rating bar
            rating_bar = "█" * value + "░" * (10 - value)

            country_text += f"{emoji} <b>{name}</b>: {value}/10\n"
            country_text += f"   {rating_bar}\n"
            country_text += (
                f"   <i>{escape_html(truncate_text(description, 200))}</i>\n\n"
            )

        country_text += (
            "\n💡 <b>Чтобы играть за эту страну, ответьте на это сообщение</b> "
            "и напишите <b>выбрать</b> или <b>выбираю</b>.\n\n"
            f"<code>[EXAMPLE:{example.id}]</code>"
        )

        await message.answer(country_text, parse_mode="HTML")


def register_player_handlers(dp: Dispatcher) -> None:
    """Register player handlers"""
    dp.message.register(stats_command, Command("stats"))
    dp.message.register(world_command, Command("world"))
    dp.message.register(examples_command, Command("examples"))
