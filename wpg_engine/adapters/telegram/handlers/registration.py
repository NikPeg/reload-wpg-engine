"""
Registration handlers
"""

from aiogram import Dispatcher, F
from aiogram.filters import Command, Filter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from wpg_engine.adapters.telegram.utils import escape_html
from wpg_engine.core.engine import GameEngine
from wpg_engine.models import (
    Country,
    Example,
    Game,
    GameStatus,
    Player,
    PlayerRole,
    get_db,
)


class IsExampleSelection(Filter):
    """Filter to check if message is selecting an example during registration"""

    async def __call__(self, message: Message, state: FSMContext) -> bool:
        # Must be a reply
        if not message.reply_to_message:
            return False

        # Must be in registration state
        current_state = await state.get_state()
        if not current_state or not current_state.startswith("RegistrationStates:"):
            return False

        # Skip confirmation state
        if (
            current_state
            == "RegistrationStates:waiting_for_reregistration_confirmation"
        ):
            return False

        # Must reply to example message
        reply_text = message.reply_to_message.text or ""
        if "[EXAMPLE:" not in reply_text:
            return False

        # Must say "выбрать" or "выбираю"
        user_text = message.text.strip().lower() if message.text else ""
        return user_text in ["выбрать", "выбираю"]


class RegistrationStates(StatesGroup):
    """Registration states"""

    waiting_for_country_name = State()
    waiting_for_capital = State()
    waiting_for_population = State()
    waiting_for_country_description = State()
    waiting_for_economy = State()
    waiting_for_military = State()
    waiting_for_foreign_policy = State()
    waiting_for_territory = State()
    waiting_for_technology = State()
    waiting_for_religion_culture = State()
    waiting_for_governance_law = State()
    waiting_for_construction_infrastructure = State()
    waiting_for_social_relations = State()
    waiting_for_intelligence = State()

    # Re-registration confirmation state
    waiting_for_reregistration_confirmation = State()


ASPECT_NAMES = {
    "economy": "Экономика",
    "military": "Военное дело",
    "foreign_policy": "Внешняя политика",
    "territory": "Территория",
    "technology": "Технологичность",
    "religion_culture": "Религия и культура",
    "governance_law": "Управление и право",
    "construction_infrastructure": "Строительство и инфраструктура",
    "social_relations": "Общественные отношения",
    "intelligence": "Разведка",
}

ASPECT_DESCRIPTIONS = {
    "economy": "торговля, ресурсы, финансы",
    "military": "армия, вооружение, военная мощь",
    "foreign_policy": "дипломатия, международные отношения",
    "territory": "размер, географическое положение, границы",
    "technology": "научно-технический прогресс, инновации",
    "religion_culture": "духовная жизнь, традиции, идеология",
    "governance_law": "государственное устройство, законы",
    "construction_infrastructure": "дороги, города, коммуникации",
    "social_relations": "социальная структура, мобильность",
    "intelligence": "шпионаж, контрразведка, информационные сети",
}


async def register_command(message: Message, state: FSMContext) -> None:
    """Handle /register command"""
    user_id = message.from_user.id

    async for db in get_db():
        game_engine = GameEngine(db)

        # Check if user is admin (already registered in DB)
        from wpg_engine.core.admin_utils import is_admin

        is_admin_user = await is_admin(user_id, game_engine.db, message.chat.id)

        # Check if user is already registered
        result = await game_engine.db.execute(
            select(Player)
            .options(selectinload(Player.country))
            .where(Player.telegram_id == user_id)
            .limit(1)
        )
        existing_player = result.scalar_one_or_none()

        # Get available game (created or active) - take the first one
        result = await game_engine.db.execute(
            select(Game)
            .where(Game.status.in_([GameStatus.CREATED, GameStatus.ACTIVE]))
            .limit(1)
        )
        game = result.scalar_one_or_none()

        if not game:
            await message.answer(
                "❌ В данный момент нет доступных игр. Обратитесь к администратору."
            )
            return
        break

    # If user is admin from DB, inform them they don't need to register
    if is_admin_user and not existing_player:
        await message.answer(
            "ℹ️ <b>Вы - администратор игры!</b>\n\n"
            "Администратору не требуется регистрировать страну.\n"
            "Используйте /start для доступа к панели администратора.\n\n"
            "Если вы всё же хотите зарегистрировать страну для себя как игрок, "
            "напишите <b>ПРОДОЛЖИТЬ</b> (заглавными буквами).",
            parse_mode="HTML",
        )
        # Store intent for optional registration
        await state.update_data(
            user_id=user_id,
            game_id=game.id,
            max_points=game.max_points,
            max_population=game.max_population,
            admin_wants_country=True,
        )
        await state.set_state(
            RegistrationStates.waiting_for_reregistration_confirmation
        )
        return

    # If user is already registered, ask for confirmation to re-register
    if existing_player:
        # Store data for confirmation
        await state.update_data(
            user_id=user_id,
            game_id=game.id,
            max_points=game.max_points,
            existing_player_id=existing_player.id,
            existing_country_id=(
                existing_player.country_id if existing_player.country else None
            ),
        )

        country_info = ""
        if existing_player.country:
            country_info = f"Ваша текущая страна: <b>{escape_html(existing_player.country.name)}</b>\n"

        await message.answer(
            f"⚠️ <b>ВНИМАНИЕ!</b>\n\n"
            f"Вы уже зарегистрированы в игре.\n"
            f"{country_info}\n"
            f"При регистрации новой страны:\n\n"
            f"• Ваша старая страна <b>останется в базе данных</b>, но будет отвязана от вас\n"
            f"• Вы будете управлять новой страной\n"
            f"• Старую страну сможет удалить только администратор командой /delete_country\n\n"
            f"Вы хотите зарегистрировать новую страну?\n\n"
            f"Напишите <b>ПОДТВЕРЖДАЮ</b> (заглавными буквами), чтобы продолжить, или любое другое сообщение для отмены.",
            parse_mode="HTML",
        )
        await state.set_state(
            RegistrationStates.waiting_for_reregistration_confirmation
        )
        return

    # New user registration - check if there are examples
    result = await game_engine.db.execute(
        select(Example).where(Example.game_id == game.id).limit(1)
    )
    has_examples = result.scalar_one_or_none() is not None

    await state.update_data(
        game_id=game.id,
        user_id=user_id,
        max_points=game.max_points,
        max_population=game.max_population,
        spent_points=0,
    )

    examples_hint = ""
    if has_examples:
        examples_hint = (
            "\n\n💡 <i>Вы можете использовать /examples для просмотра готовых примеров стран. "
            "Чтобы выбрать страну из примера, ответьте на сообщение с примером словом "
            "<b>выбрать</b> или <b>выбираю</b></i>"
        )

    await message.answer(
        f"🎮 <b>Регистрация в игре '{escape_html(game.name)}'</b>\n\n"
        f"Для участия в игре вам необходимо создать свою страну.\n"
        f"Вы будете управлять страной по <b>10 аспектам</b> развития.{examples_hint}\n\n"
        f"📊 <b>У вас есть {game.max_points} очков</b> для распределения между аспектами.\n"
        f"Каждый аспект можно развить от 0 до 10 уровня.\n\n"
        f"<b>Начнем с основной информации:</b>\n\n"
        f"Как будет называться ваша страна?",
        parse_mode="HTML",
    )
    await state.set_state(RegistrationStates.waiting_for_country_name)


async def process_country_name(message: Message, state: FSMContext) -> None:
    """Process country name"""
    country_name = message.text.strip()

    if len(country_name) < 2 or len(country_name) > 100:
        await message.answer("❌ Название страны должно быть от 2 до 100 символов.")
        return

    # Check if country name conflicts with existing countries or their synonyms
    data = await state.get_data()
    game_id = data["game_id"]

    async for db in get_db():
        game_engine = GameEngine(db)

        # Get all countries in the game
        result = await game_engine.db.execute(
            select(Country).where(Country.game_id == game_id)
        )
        existing_countries = result.scalars().all()

        # Check for conflicts
        for country in existing_countries:
            # Check official name
            if country.name.lower() == country_name.lower():
                await message.answer(
                    f"❌ Страна с названием '{escape_html(country_name)}' уже существует.\n"
                    f"Выберите другое название."
                )
                return

            # Check synonyms
            if country.synonyms:
                for synonym in country.synonyms:
                    if synonym.lower() == country_name.lower():
                        await message.answer(
                            f"❌ Название '{escape_html(country_name)}' уже используется как синоним страны '{escape_html(country.name)}'.\n"
                            f"Выберите другое название."
                        )
                        return
        break

    await state.update_data(country_name=country_name)
    await message.answer(
        f"✅ Название страны: <b>{escape_html(country_name)}</b>\n\n"
        f"Как называется столица вашей страны?",
        parse_mode="HTML",
    )
    await state.set_state(RegistrationStates.waiting_for_capital)


async def process_country_description(message: Message, state: FSMContext) -> None:
    """Process country description"""
    description = message.text.strip()

    if len(description) < 10 or len(description) > 1000:
        await message.answer("❌ Описание должно быть от 10 до 1000 символов.")
        return

    data = await state.get_data()
    await state.update_data(country_description=description)

    # Create aspects list for display
    aspects_list = []
    for i, (aspect_key, aspect_name) in enumerate(ASPECT_NAMES.items(), 1):
        aspects_list.append(
            f"{i}. <b>{aspect_name}</b> - {ASPECT_DESCRIPTIONS[aspect_key]}"
        )

    aspects_text = "\n".join(aspects_list)

    await message.answer(
        f"✅ Описание сохранено.\n\n"
        f"📊 <b>Теперь нужно будет распределить {data['max_points']} очков между 10 аспектами развития:</b>\n\n"
        f"{aspects_text}\n\n"
        f"Каждый аспект оценивается по шкале от 0 до 10:\n"
        f"• 0: отсутствует\n"
        f"• 1-3: слабый уровень\n"
        f"• 4-6: средний уровень\n"
        f"• 7-8: высокий уровень\n"
        f"• 9-10: выдающийся уровень\n\n"
        f"<b>{ASPECT_NAMES['economy']}</b> ({ASPECT_DESCRIPTIONS['economy']})\n"
        f"Введите значение от 0 до 10:",
        parse_mode="HTML",
    )
    await state.set_state(RegistrationStates.waiting_for_economy)


async def process_aspect(
    message: Message, state: FSMContext, aspect: str, next_state: State
) -> None:
    """Process aspect value"""
    try:
        value = int(message.text.strip())
        if not 0 <= value <= 10:
            raise ValueError()
    except ValueError:
        await message.answer("❌ Введите число от 0 до 10.")
        return

    # Get current data and check points
    data = await state.get_data()
    current_spent = data.get("spent_points", 0)
    max_points = data.get("max_points", 30)

    # Calculate new total if we set this aspect
    new_spent = current_spent + value
    remaining = max_points - new_spent

    # Check if we have enough points
    if new_spent > max_points:
        await message.answer(
            f"❌ Недостаточно очков!\n\n"
            f"📊 Потрачено: {current_spent} | Доступно: {max_points} | Осталось: {max_points - current_spent}\n"
            f"Вы пытаетесь потратить {value} очков, но у вас осталось только {max_points - current_spent}.\n\n"
            f"Введите значение от 0 до {max_points - current_spent}:",
            parse_mode="Markdown",
        )
        return

    # Store aspect value and update spent points
    data[aspect] = value
    data["spent_points"] = new_spent
    await state.update_data(**data)

    # Get next aspect or finish
    aspects = list(ASPECT_NAMES.keys())
    current_index = aspects.index(aspect)

    if current_index < len(aspects) - 1:
        next_aspect = aspects[current_index + 1]
        max_for_next = min(10, remaining)
        await message.answer(
            f"✅ {ASPECT_NAMES[aspect]}: {value}\n\n"
            f"📊 *Потрачено: {new_spent} | Осталось: {remaining}*\n\n"
            f"*{ASPECT_NAMES[next_aspect]}* ({ASPECT_DESCRIPTIONS[next_aspect]})\n"
            f"Введите значение от 0 до {max_for_next}:",
            parse_mode="Markdown",
        )
        await state.set_state(next_state)
    else:
        # All aspects done, complete registration
        await message.answer(
            f"✅ {ASPECT_NAMES[aspect]}: {value}\n\n"
            f"📊 <b>Итого потрачено: {new_spent} из {max_points} очков</b>\n"
            f"<b>Осталось неиспользованных: {remaining} очков</b>\n\n"
            f"🎉 Все аспекты настроены! Завершаем регистрацию...",
            parse_mode="HTML",
        )
        await complete_registration(message, state)


async def process_economy(message: Message, state: FSMContext) -> None:
    await process_aspect(
        message, state, "economy", RegistrationStates.waiting_for_military
    )


async def process_military(message: Message, state: FSMContext) -> None:
    await process_aspect(
        message, state, "military", RegistrationStates.waiting_for_foreign_policy
    )


async def process_foreign_policy(message: Message, state: FSMContext) -> None:
    await process_aspect(
        message, state, "foreign_policy", RegistrationStates.waiting_for_territory
    )


async def process_territory(message: Message, state: FSMContext) -> None:
    await process_aspect(
        message, state, "territory", RegistrationStates.waiting_for_technology
    )


async def process_technology(message: Message, state: FSMContext) -> None:
    await process_aspect(
        message, state, "technology", RegistrationStates.waiting_for_religion_culture
    )


async def process_religion_culture(message: Message, state: FSMContext) -> None:
    await process_aspect(
        message,
        state,
        "religion_culture",
        RegistrationStates.waiting_for_governance_law,
    )


async def process_governance_law(message: Message, state: FSMContext) -> None:
    await process_aspect(
        message,
        state,
        "governance_law",
        RegistrationStates.waiting_for_construction_infrastructure,
    )


async def process_construction_infrastructure(
    message: Message, state: FSMContext
) -> None:
    await process_aspect(
        message,
        state,
        "construction_infrastructure",
        RegistrationStates.waiting_for_social_relations,
    )


async def process_social_relations(message: Message, state: FSMContext) -> None:
    await process_aspect(
        message, state, "social_relations", RegistrationStates.waiting_for_intelligence
    )


async def process_intelligence(message: Message, state: FSMContext) -> None:
    await process_aspect(message, state, "intelligence", None)


async def process_capital(message: Message, state: FSMContext) -> None:
    """Process capital name"""
    capital = message.text.strip()

    if len(capital) < 2 or len(capital) > 50:
        await message.answer("❌ Название столицы должно быть от 2 до 50 символов.")
        return

    await state.update_data(capital=capital)
    await message.answer(
        f"✅ Столица: <b>{escape_html(capital)}</b>\n\n"
        f"Какова примерная численность населения вашей страны? "
        f"(введите число, например: 5000000)",
        parse_mode="HTML",
    )
    await state.set_state(RegistrationStates.waiting_for_population)


async def process_population(message: Message, state: FSMContext) -> None:
    """Process population and move to country description"""
    # Get max population from game settings
    data = await state.get_data()
    max_population = data.get("max_population", 10_000_000)

    try:
        population = int(message.text.strip())
        if population < 1000 or population > max_population:
            raise ValueError()
    except ValueError:
        await message.answer(
            f"❌ Введите корректное число населения (от 1,000 до {max_population:,})."
        )
        return

    await state.update_data(population=population)
    await message.answer(
        f"✅ Население: <b>{population:,}</b>\n\n"
        f"Теперь дайте краткое описание вашей страны "
        f"(история, особенности, культура):",
        parse_mode="HTML",
    )
    await state.set_state(RegistrationStates.waiting_for_country_description)


async def complete_registration(message: Message, state: FSMContext) -> None:
    """Complete registration and create country and player"""
    # Get all registration data
    data = await state.get_data()

    async for db in get_db():
        game_engine = GameEngine(db)

        # Create country
        country = await game_engine.create_country(
            game_id=data["game_id"],
            name=data["country_name"],
            description=data["country_description"],
            capital=data["capital"],
            population=data["population"],
            aspects={
                "economy": data["economy"],
                "military": data["military"],
                "foreign_policy": data["foreign_policy"],
                "territory": data["territory"],
                "technology": data["technology"],
                "religion_culture": data["religion_culture"],
                "governance_law": data["governance_law"],
                "construction_infrastructure": data["construction_infrastructure"],
                "social_relations": data["social_relations"],
                "intelligence": data["intelligence"],
            },
        )

        # Create player with PLAYER role (registration is for countries, not admins)
        await game_engine.create_player(
            game_id=data["game_id"],
            telegram_id=data["user_id"],
            username=message.from_user.username,
            display_name=message.from_user.full_name,
            country_id=country.id,
            role=PlayerRole.PLAYER,
        )

        # Send registration to admin
        # Import settings to check if admin_id is a chat
        import random

        from wpg_engine.config.settings import settings

        # Determine target based on admin_id configuration
        admin = None
        target_chat_id = None

        if settings.telegram.is_admin_chat():
            # If admin_id is a chat (negative), send to that chat
            target_chat_id = settings.telegram.admin_id
        else:
            # Find admin(s) to send registration to
            result = await game_engine.db.execute(
                select(Player)
                .where(Player.game_id == data["game_id"])
                .where(Player.role == PlayerRole.ADMIN)
            )
            admins = result.scalars().all()

            if admins:
                # If multiple admins, choose one randomly
                admin = random.choice(admins)
                target_chat_id = admin.telegram_id

        if target_chat_id:
            try:
                # Calculate total points spent
                total_points = (
                    data["economy"]
                    + data["military"]
                    + data["foreign_policy"]
                    + data["territory"]
                    + data["technology"]
                    + data["religion_culture"]
                    + data["governance_law"]
                    + data["construction_infrastructure"]
                    + data["social_relations"]
                    + data["intelligence"]
                )

                # Format registration message for admin
                registration_message = (
                    f"📋 <b>Новая заявка на регистрацию</b>\n\n"
                    f"<b>Игрок:</b> {escape_html(message.from_user.full_name or 'Не указано')}\n"
                    f"<b>Username:</b> @{escape_html(message.from_user.username or 'не указан')}\n"
                    f"<b>Telegram ID:</b> <code>{data['user_id']}</code>\n\n"
                    f"<b>Страна:</b> {escape_html(data['country_name'])}\n"
                    f"<b>Столица:</b> {escape_html(data['capital'])}\n"
                    f"<b>Население:</b> {data['population']:,}\n\n"
                    f"<b>Описание:</b>\n{escape_html(data['country_description'])}\n\n"
                    f"📊 <b>Очки: {total_points}/{data['max_points']} (осталось: {data['max_points'] - total_points})</b>\n\n"
                    f"<b>Аспекты развития:</b>\n"
                    f"💰 Экономика: {data['economy']}/10\n"
                    f"⚔️ Военное дело: {data['military']}/10\n"
                    f"🤝 Внешняя политика: {data['foreign_policy']}/10\n"
                    f"🗺️ Территория: {data['territory']}/10\n"
                    f"🔬 Технологичность: {data['technology']}/10\n"
                    f"🏛️ Религия и культура: {data['religion_culture']}/10\n"
                    f"⚖️ Управление и право: {data['governance_law']}/10\n"
                    f"🏗️ Строительство: {data['construction_infrastructure']}/10\n"
                    f"👥 Общественные отношения: {data['social_relations']}/10\n"
                    f"🕵️ Разведка: {data['intelligence']}/10\n\n"
                    f"<b>Ответьте на это сообщение:</b>\n"
                    f"• <code>одобрить</code> - для одобрения заявки\n"
                    f"• <code>отклонить</code> - для отклонения заявки\n"
                    f"• <code>отклонить [причина]</code> - для отклонения с указанием причины"
                )

                # Send to admin
                bot = message.bot

                await bot.send_message(
                    target_chat_id, registration_message, parse_mode="HTML"
                )

            except Exception as e:
                print(f"Failed to send registration to admin: {e}")

        break

    # Show summary - registration request sent to admin
    await message.answer(
        f"🎉 <b>Регистрация завершена!</b>\n\n"
        f"<b>Ваша страна:</b> {escape_html(data['country_name'])}\n"
        f"<b>Столица:</b> {escape_html(data['capital'])}\n"
        f"<b>Население:</b> {data['population']:,}\n\n"
        f"<b>Аспекты развития:</b>\n"
        f"💰 Экономика: {data['economy']}\n"
        f"⚔️ Военное дело: {data['military']}\n"
        f"🤝 Внешняя политика: {data['foreign_policy']}\n"
        f"🗺️ Территория: {data['territory']}\n"
        f"🔬 Технологичность: {data['technology']}\n"
        f"🏛️ Религия и культура: {data['religion_culture']}\n"
        f"⚖️ Управление и право: {data['governance_law']}\n"
        f"🏗️ Строительство: {data['construction_infrastructure']}\n"
        f"👥 Общественные отношения: {data['social_relations']}\n"
        f"🕵️ Разведка: {data['intelligence']}\n\n"
        f"⏳ <b>Ваша заявка отправлена администратору на рассмотрение.</b>\n"
        f"Вы получите уведомление, когда заявка будет одобрена.\n\n"
        f"Используйте /start для просмотра доступных команд.",
        parse_mode="HTML",
    )

    await state.clear()


async def process_reregistration_confirmation(
    message: Message, state: FSMContext
) -> None:
    """Process confirmation for re-registration"""
    confirmation = message.text.strip()

    # Get stored data to check if this is admin wanting country
    data = await state.get_data()
    is_admin_wanting_country = data.get("admin_wants_country", False)

    if confirmation != "ПОДТВЕРЖДАЮ" and confirmation != "ПРОДОЛЖИТЬ":
        if is_admin_wanting_country:
            await message.answer(
                "❌ Регистрация отменена. Используйте /start для доступа к панели администратора."
            )
        else:
            await message.answer(
                "❌ Перерегистрация отменена. Ваша текущая регистрация сохранена."
            )
        await state.clear()
        return

    # Handle admin wanting to register a country
    if is_admin_wanting_country and confirmation == "ПРОДОЛЖИТЬ":
        user_id = data["user_id"]
        game_id = data["game_id"]
        max_points = data["max_points"]
        max_population = data["max_population"]

        async for db in get_db():
            game_engine = GameEngine(db)
            result = await game_engine.db.execute(
                select(Game).where(Game.id == game_id)
            )
            game = result.scalar_one_or_none()

            # Check if there are examples
            result = await game_engine.db.execute(
                select(Example).where(Example.game_id == game_id).limit(1)
            )
            has_examples = result.scalar_one_or_none() is not None
            break

        examples_hint = ""
        if has_examples:
            examples_hint = (
                "\n\n💡 <i>Вы можете использовать /examples для просмотра готовых примеров стран. "
                "Чтобы выбрать страну из примера, ответьте на сообщение с примером словом "
                "<b>выбрать</b> или <b>выбираю</b></i>"
            )

        # Clear old data and start fresh registration
        await state.clear()
        await state.update_data(
            game_id=game_id,
            user_id=user_id,
            max_points=max_points,
            max_population=max_population,
            spent_points=0,
            is_admin_registering=True,  # Mark this as admin registering
        )

        await message.answer(
            f"✅ <b>Начинаем регистрацию страны для администратора.</b>\n\n"
            f"🎮 <b>Регистрация в игре '{escape_html(game.name)}'</b>\n\n"
            f"Для участия в игре вам необходимо создать свою страну.\n"
            f"Вы будете управлять страной по <b>10 аспектам</b> развития.{examples_hint}\n\n"
            f"📊 <b>У вас есть {game.max_points} очков</b> для распределения между аспектами.\n"
            f"Каждый аспект можно развить от 0 до 10 уровня.\n\n"
            f"<b>Начнем с основной информации:</b>\n\n"
            f"Как будет называться ваша страна?",
            parse_mode="HTML",
        )
        await state.set_state(RegistrationStates.waiting_for_country_name)
        return

    # Get stored data for normal re-registration
    user_id = data["user_id"]
    game_id = data["game_id"]
    max_points = data["max_points"]
    existing_player_id = data["existing_player_id"]

    async for db in get_db():
        game_engine = GameEngine(db)

        # Get the existing player
        result = await game_engine.db.execute(
            select(Player).where(Player.id == existing_player_id)
        )
        player = result.scalar_one_or_none()

        if player:
            # Отвязываем страну от игрока, но НЕ удаляем саму страну
            # Страна останется в базе данных и может быть удалена только админом через /delete_country
            player.country_id = None
            await game_engine.db.commit()

        # Get game info for new registration
        result = await game_engine.db.execute(select(Game).where(Game.id == game_id))
        game = result.scalar_one_or_none()
        break

    # Check if there are examples
    result = await game_engine.db.execute(
        select(Example).where(Example.game_id == game_id).limit(1)
    )
    has_examples = result.scalar_one_or_none() is not None

    examples_hint = ""
    if has_examples:
        examples_hint = (
            "\n\n💡 <i>Вы можете использовать /examples для просмотра готовых примеров стран. "
            "Чтобы выбрать страну из примера, ответьте на сообщение с примером словом "
            "<b>выбрать</b> или <b>выбираю</b></i>"
        )

    # Clear old data and start fresh registration
    await state.clear()
    await state.update_data(
        game_id=game_id,
        user_id=user_id,
        max_points=max_points,
        max_population=game.max_population,
        spent_points=0,
    )

    await message.answer(
        f"✅ <b>Старая страна отвязана.</b>\n\n"
        f"🎮 <b>Регистрация в игре '{escape_html(game.name)}'</b>\n\n"
        f"Для участия в игре вам необходимо создать свою страну.\n"
        f"Вы будете управлять страной по <b>10 аспектам</b> развития.{examples_hint}\n\n"
        f"📊 <b>У вас есть {game.max_points} очков</b> для распределения между аспектами.\n"
        f"Каждый аспект можно развить от 0 до 10 уровня.\n\n"
        f"<b>Начнем с основной информации:</b>\n\n"
        f"Как будет называться ваша страна?",
        parse_mode="HTML",
    )
    await state.set_state(RegistrationStates.waiting_for_country_name)


async def process_example_selection(message: Message, state: FSMContext) -> None:
    """
    Process example selection - this handler checks if user replied to example message
    with "выбрать" or "выбираю" during registration
    """
    # Check if message is a reply
    if not message.reply_to_message:
        return

    # Check if user is in any registration state
    current_state = await state.get_state()
    if not current_state or not current_state.startswith("RegistrationStates:"):
        return

    # Skip confirmation state
    if current_state == "RegistrationStates:waiting_for_reregistration_confirmation":
        return

    # Check if reply message contains [EXAMPLE:X] marker
    reply_text = message.reply_to_message.text or ""
    if "[EXAMPLE:" not in reply_text:
        return  # Not replying to example message, let normal handlers process it

    # Check if user wants to select this example
    user_text = message.text.strip().lower()
    if user_text not in ["выбрать", "выбираю"]:
        # User is replying to example but not selecting it - treat as normal name input
        return

    # Extract example ID from marker
    try:
        example_id_str = reply_text.split("[EXAMPLE:")[1].split("]")[0]
        example_id = int(example_id_str)
    except (IndexError, ValueError):
        await message.answer("❌ Ошибка при извлечении ID примера. Попробуйте еще раз.")
        return

    # Get state data
    data = await state.get_data()
    user_id = data.get("user_id", message.from_user.id)
    game_id = data.get("game_id")

    if not game_id:
        await message.answer(
            "❌ Ошибка: игра не найдена. Начните регистрацию заново с /register"
        )
        await state.clear()
        return

    async for db in get_db():
        game_engine = GameEngine(db)

        # Get the example
        result = await game_engine.db.execute(
            select(Example)
            .options(selectinload(Example.country))
            .where(Example.id == example_id)
            .where(Example.game_id == game_id)
        )
        example = result.scalar_one_or_none()

        if not example:
            await message.answer(
                "❌ Пример страны не найден или уже был выбран другим игроком.\n"
                "Используйте /examples для просмотра доступных примеров."
            )
            return

        country = example.country

        # Check if player already exists
        result = await game_engine.db.execute(
            select(Player).where(Player.telegram_id == user_id)
        )
        player = result.scalar_one_or_none()

        if player:
            # Update existing player with new country
            player.country_id = country.id
        else:
            # Create new player
            player = await game_engine.create_player(
                game_id=game_id,
                telegram_id=user_id,
                username=message.from_user.username,
                display_name=message.from_user.full_name,
                country_id=country.id,
                role=PlayerRole.PLAYER,
            )

        # Delete the example (it's now taken)
        await game_engine.db.delete(example)
        await game_engine.db.commit()

        # Send confirmation to user
        await message.answer(
            f"🎉 <b>Поздравляем!</b>\n\n"
            f"Вы выбрали страну <b>{escape_html(country.name)}</b>!\n\n"
            f"<b>Столица:</b> {escape_html(country.capital or 'Не указана')}\n"
            f"<b>Население:</b> {country.population:,} чел.\n\n"
            f"⏳ <b>Ваша заявка отправлена администратору на рассмотрение.</b>\n"
            f"Вы получите уведомление, когда заявка будет одобрена.\n\n"
            f"Используйте /start для просмотра доступных команд.",
            parse_mode="HTML",
        )

        # Send notification to admin
        import random

        from wpg_engine.config.settings import settings

        target_chat_id = None
        if settings.telegram.is_admin_chat():
            target_chat_id = settings.telegram.admin_id
        else:
            result = await game_engine.db.execute(
                select(Player)
                .where(Player.game_id == game_id)
                .where(Player.role == PlayerRole.ADMIN)
            )
            admins = result.scalars().all()
            if admins:
                admin = random.choice(admins)
                target_chat_id = admin.telegram_id

        if target_chat_id:
            try:
                registration_message = (
                    f"📋 <b>Новая заявка на регистрацию (из примера)</b>\n\n"
                    f"<b>Игрок:</b> {escape_html(message.from_user.full_name or 'Не указано')}\n"
                    f"<b>Username:</b> @{escape_html(message.from_user.username or 'не указан')}\n"
                    f"<b>Telegram ID:</b> <code>{user_id}</code>\n\n"
                    f"<b>Выбрана страна:</b> {escape_html(country.name)}\n"
                    f"<b>Столица:</b> {escape_html(country.capital or 'Не указана')}\n"
                    f"<b>Население:</b> {country.population:,}\n\n"
                    f"<b>Ответьте на это сообщение:</b>\n"
                    f"• <code>одобрить</code> - для одобрения заявки\n"
                    f"• <code>отклонить</code> - для отклонения заявки\n"
                    f"• <code>отклонить [причина]</code> - для отклонения с указанием причины"
                )

                bot = message.bot
                await bot.send_message(
                    target_chat_id, registration_message, parse_mode="HTML"
                )
            except Exception as e:
                print(f"Failed to send registration to admin: {e}")

        break

    # Clear state
    await state.clear()


def register_registration_handlers(dp: Dispatcher) -> None:
    """Register registration handlers"""

    # Register example selection handler FIRST with highest priority
    # This will intercept replies to example messages with "выбрать"/"выбираю"
    dp.message.register(
        process_example_selection,
        IsExampleSelection(),
    )

    dp.message.register(register_command, Command("register"))
    dp.message.register(
        process_reregistration_confirmation,
        RegistrationStates.waiting_for_reregistration_confirmation,
    )
    # New sequence: country name -> capital -> population -> description -> aspects
    dp.message.register(
        process_country_name,
        RegistrationStates.waiting_for_country_name,
        ~F.text.startswith("/"),
    )
    dp.message.register(
        process_capital, RegistrationStates.waiting_for_capital, ~F.text.startswith("/")
    )
    dp.message.register(
        process_population,
        RegistrationStates.waiting_for_population,
        ~F.text.startswith("/"),
    )
    dp.message.register(
        process_country_description,
        RegistrationStates.waiting_for_country_description,
        ~F.text.startswith("/"),
    )
    dp.message.register(
        process_economy, RegistrationStates.waiting_for_economy, ~F.text.startswith("/")
    )
    dp.message.register(
        process_military,
        RegistrationStates.waiting_for_military,
        ~F.text.startswith("/"),
    )
    dp.message.register(
        process_foreign_policy,
        RegistrationStates.waiting_for_foreign_policy,
        ~F.text.startswith("/"),
    )
    dp.message.register(
        process_territory,
        RegistrationStates.waiting_for_territory,
        ~F.text.startswith("/"),
    )
    dp.message.register(
        process_technology,
        RegistrationStates.waiting_for_technology,
        ~F.text.startswith("/"),
    )
    dp.message.register(
        process_religion_culture,
        RegistrationStates.waiting_for_religion_culture,
        ~F.text.startswith("/"),
    )
    dp.message.register(
        process_governance_law,
        RegistrationStates.waiting_for_governance_law,
        ~F.text.startswith("/"),
    )
    dp.message.register(
        process_construction_infrastructure,
        RegistrationStates.waiting_for_construction_infrastructure,
        ~F.text.startswith("/"),
    )
    dp.message.register(
        process_social_relations,
        RegistrationStates.waiting_for_social_relations,
        ~F.text.startswith("/"),
    )
    dp.message.register(
        process_intelligence,
        RegistrationStates.waiting_for_intelligence,
        ~F.text.startswith("/"),
    )
