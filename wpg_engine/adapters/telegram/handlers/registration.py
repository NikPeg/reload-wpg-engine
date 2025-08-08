"""
Registration handlers
"""

from aiogram import Dispatcher
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from wpg_engine.core.admin_utils import determine_player_role
from wpg_engine.core.engine import GameEngine
from wpg_engine.models import Country, Game, GameStatus, Player, get_db
from wpg_engine.models.message import Message as MessageModel


class RegistrationStates(StatesGroup):
    """Registration states"""

    waiting_for_country_name = State()
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
    waiting_for_capital = State()
    waiting_for_population = State()

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

        # Check if user is already registered
        result = await game_engine.db.execute(
            select(Player).options(selectinload(Player.country)).where(Player.telegram_id == user_id).limit(1)
        )
        existing_player = result.scalar_one_or_none()

        # Get available game (created or active) - take the first one
        result = await game_engine.db.execute(
            select(Game).where(Game.status.in_([GameStatus.CREATED, GameStatus.ACTIVE])).limit(1)
        )
        game = result.scalar_one_or_none()

        if not game:
            await message.answer("❌ В данный момент нет доступных игр. Обратитесь к администратору.")
            return
        break

    # If user is already registered, ask for confirmation to re-register
    if existing_player:
        # Store data for confirmation
        await state.update_data(
            user_id=user_id,
            game_id=game.id,
            max_points=game.max_points,
            existing_player_id=existing_player.id,
            existing_country_id=existing_player.country_id if existing_player.country else None,
        )

        country_info = ""
        if existing_player.country:
            country_info = f"Ваша текущая страна: *{existing_player.country.name}*\n"

        await message.answer(
            f"⚠️ *ВНИМАНИЕ! ОПАСНАЯ ОПЕРАЦИЯ!*\n\n"
            f"Вы уже зарегистрированы в игре.\n"
            f"{country_info}\n"
            f"Регистрация новой страны *ПОЛНОСТЬЮ УДАЛИТ* всю информацию о текущей регистрации:\n\n"
            f"• Все данные о стране будут потеряны\n"
            f"• История сообщений останется, но связь со страной пропадет\n"
            f"• Это действие *НЕОБРАТИМО*\n\n"
            f"Вы *ДЕЙСТВИТЕЛЬНО* хотите зарегистрировать новую страну?\n\n"
            f"Напишите *ПОДТВЕРЖДАЮ* (заглавными буквами), чтобы продолжить, или любое другое сообщение для отмены.",
            parse_mode="Markdown",
        )
        await state.set_state(RegistrationStates.waiting_for_reregistration_confirmation)
        return

    # New user registration
    await state.update_data(game_id=game.id, user_id=user_id, max_points=game.max_points, spent_points=0)

    await message.answer(
        f"🎮 *Регистрация в игре '{game.name}'*\n\n"
        f"Для участия в игре вам необходимо создать свою страну.\n"
        f"Вы будете управлять страной по 10 аспектам развития.\n\n"
        f"📊 *У вас есть {game.max_points} очков* для распределения между аспектами.\n"
        f"Каждый аспект можно развить от 0 до 10 уровня.\n\n"
        f"*Начнем с основной информации:*\n\n"
        f"Как будет называться ваша страна?",
        parse_mode="Markdown",
    )
    await state.set_state(RegistrationStates.waiting_for_country_name)


async def process_country_name(message: Message, state: FSMContext) -> None:
    """Process country name"""
    country_name = message.text.strip()

    if len(country_name) < 2 or len(country_name) > 100:
        await message.answer("❌ Название страны должно быть от 2 до 100 символов.")
        return

    await state.update_data(country_name=country_name)
    await message.answer(
        f"✅ Название страны: *{country_name}*\n\n"
        f"Теперь дайте краткое описание вашей страны "
        f"(история, особенности, культура):",
        parse_mode="Markdown",
    )
    await state.set_state(RegistrationStates.waiting_for_country_description)


async def process_country_description(message: Message, state: FSMContext) -> None:
    """Process country description"""
    description = message.text.strip()

    if len(description) < 10 or len(description) > 1000:
        await message.answer("❌ Описание должно быть от 10 до 1000 символов.")
        return

    data = await state.get_data()
    await state.update_data(country_description=description)
    await message.answer(
        f"✅ Описание сохранено.\n\n"
        f"*Теперь настроим аспекты развития вашей страны.*\n\n"
        f"📊 *Доступно очков: {data['max_points']} | Потрачено: {data['spent_points']} | Осталось: {data['max_points'] - data['spent_points']}*\n\n"
        f"Каждый аспект оценивается по шкале от 0 до 10:\n"
        f"• 0: отсутствует\n"
        f"• 1-3: слабый уровень\n"
        f"• 4-6: средний уровень\n"
        f"• 7-8: высокий уровень\n"
        f"• 9-10: выдающийся уровень\n\n"
        f"*{ASPECT_NAMES['economy']}* ({ASPECT_DESCRIPTIONS['economy']})\n"
        f"Введите значение от 0 до 10:",
        parse_mode="Markdown",
    )
    await state.set_state(RegistrationStates.waiting_for_economy)


async def process_aspect(message: Message, state: FSMContext, aspect: str, next_state: State) -> None:
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
        # All aspects done, ask for capital
        await message.answer(
            f"✅ {ASPECT_NAMES[aspect]}: {value}\n\n"
            f"📊 *Итого потрачено: {new_spent} из {max_points} очков*\n"
            f"*Осталось неиспользованных: {remaining} очков*\n\n"
            f"*Дополнительная информация*\n\n"
            f"Как называется столица вашей страны?",
            parse_mode="Markdown",
        )
        await state.set_state(RegistrationStates.waiting_for_capital)


async def process_economy(message: Message, state: FSMContext) -> None:
    await process_aspect(message, state, "economy", RegistrationStates.waiting_for_military)


async def process_military(message: Message, state: FSMContext) -> None:
    await process_aspect(message, state, "military", RegistrationStates.waiting_for_foreign_policy)


async def process_foreign_policy(message: Message, state: FSMContext) -> None:
    await process_aspect(message, state, "foreign_policy", RegistrationStates.waiting_for_territory)


async def process_territory(message: Message, state: FSMContext) -> None:
    await process_aspect(message, state, "territory", RegistrationStates.waiting_for_technology)


async def process_technology(message: Message, state: FSMContext) -> None:
    await process_aspect(message, state, "technology", RegistrationStates.waiting_for_religion_culture)


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


async def process_construction_infrastructure(message: Message, state: FSMContext) -> None:
    await process_aspect(
        message,
        state,
        "construction_infrastructure",
        RegistrationStates.waiting_for_social_relations,
    )


async def process_social_relations(message: Message, state: FSMContext) -> None:
    await process_aspect(message, state, "social_relations", RegistrationStates.waiting_for_intelligence)


async def process_intelligence(message: Message, state: FSMContext) -> None:
    await process_aspect(message, state, "intelligence", RegistrationStates.waiting_for_capital)


async def process_capital(message: Message, state: FSMContext) -> None:
    """Process capital name"""
    capital = message.text.strip()

    if len(capital) < 2 or len(capital) > 50:
        await message.answer("❌ Название столицы должно быть от 2 до 50 символов.")
        return

    await state.update_data(capital=capital)
    await message.answer(
        f"✅ Столица: *{capital}*\n\n"
        f"Какова примерная численность населения вашей страны? "
        f"(введите число, например: 50000000)",
        parse_mode="Markdown",
    )
    await state.set_state(RegistrationStates.waiting_for_population)


async def process_population(message: Message, state: FSMContext) -> None:
    """Process population and complete registration"""
    try:
        population = int(message.text.strip())
        if population < 1000 or population > 2000000000:
            raise ValueError()
    except ValueError:
        await message.answer("❌ Введите корректное число населения (от 1000 до 2 млрд).")
        return

    # Get all registration data
    data = await state.get_data()
    data["population"] = population

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

        # Determine player role
        player_role = await determine_player_role(
            telegram_id=data["user_id"], game_id=data["game_id"], db=game_engine.db
        )

        # Create player with determined role
        await game_engine.create_player(
            game_id=data["game_id"],
            telegram_id=data["user_id"],
            username=message.from_user.username,
            display_name=message.from_user.full_name,
            country_id=country.id,
            role=player_role,
        )

        # If this is a regular player, send registration to admin
        if player_role.value == "player":
            # Find admin to send registration to
            from wpg_engine.models import PlayerRole

            result = await game_engine.db.execute(
                select(Player).where(Player.game_id == data["game_id"]).where(Player.role == PlayerRole.ADMIN).limit(1)
            )
            admin = result.scalar_one_or_none()

            if admin and admin.telegram_id:
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
                        f"<b>Игрок:</b> {message.from_user.full_name}\n"
                        f"<b>Username:</b> @{message.from_user.username or 'не указан'}\n"
                        f"<b>Telegram ID:</b> <code>{data['user_id']}</code>\n\n"
                        f"<b>Страна:</b> {data['country_name']}\n"
                        f"<b>Столица:</b> {data['capital']}\n"
                        f"<b>Население:</b> {population:,}\n\n"
                        f"<b>Описание:</b>\n{data['country_description']}\n\n"
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
                    await bot.send_message(admin.telegram_id, registration_message, parse_mode="HTML")

                except Exception as e:
                    print(f"Failed to send registration to admin: {e}")

        break

    # Show summary with role-specific message
    role_message = ""
    if player_role.value == "admin":
        role_message = (
            "👑 *Вы назначены администратором игры!*\n" "Используйте /admin для доступа к панели управления.\n\n"
        )
    else:
        role_message = (
            "⏳ *Ваша заявка отправлена администратору на рассмотрение.*\n"
            "Вы получите уведомление, когда заявка будет одобрена.\n\n"
        )

    await message.answer(
        f"🎉 *Регистрация завершена!*\n\n"
        f"*Ваша страна:* {data['country_name']}\n"
        f"*Столица:* {data['capital']}\n"
        f"*Население:* {population:,}\n\n"
        f"*Аспекты развития:*\n"
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
        f"{role_message}"
        f"Используйте /start для просмотра доступных команд.",
        parse_mode="Markdown",
    )

    await state.clear()


async def process_reregistration_confirmation(message: Message, state: FSMContext) -> None:
    """Process confirmation for re-registration"""
    confirmation = message.text.strip()

    if confirmation != "ПОДТВЕРЖДАЮ":
        await message.answer("❌ Перерегистрация отменена. Ваша текущая регистрация сохранена.")
        await state.clear()
        return

    # Get stored data
    data = await state.get_data()
    user_id = data["user_id"]
    game_id = data["game_id"]
    max_points = data["max_points"]
    existing_player_id = data["existing_player_id"]
    existing_country_id = data.get("existing_country_id")

    async for db in get_db():
        game_engine = GameEngine(db)

        # Delete existing player's messages first to avoid foreign key constraint issues
        result = await game_engine.db.execute(select(MessageModel).where(MessageModel.player_id == existing_player_id))
        messages = result.scalars().all()
        for msg in messages:
            await game_engine.db.delete(msg)

        # Delete existing country
        if existing_country_id:
            result = await game_engine.db.execute(select(Country).where(Country.id == existing_country_id))
            country = result.scalar_one_or_none()
            if country:
                await game_engine.db.delete(country)

        # Delete player
        result = await game_engine.db.execute(select(Player).where(Player.id == existing_player_id))
        player = result.scalar_one_or_none()
        if player:
            await game_engine.db.delete(player)

        await game_engine.db.commit()

        # Get game info for new registration
        result = await game_engine.db.execute(select(Game).where(Game.id == game_id))
        game = result.scalar_one_or_none()
        break

    # Clear old data and start fresh registration
    await state.clear()
    await state.update_data(game_id=game_id, user_id=user_id, max_points=max_points, spent_points=0)

    await message.answer(
        f"✅ *Предыдущая регистрация удалена.*\n\n"
        f"🎮 *Регистрация в игре '{game.name}'*\n\n"
        f"Для участия в игре вам необходимо создать свою страну.\n"
        f"Вы будете управлять страной по 10 аспектам развития.\n\n"
        f"📊 *У вас есть {game.max_points} очков* для распределения между аспектами.\n"
        f"Каждый аспект можно развить от 0 до 10 уровня.\n\n"
        f"*Начнем с основной информации:*\n\n"
        f"Как будет называться ваша страна?",
        parse_mode="Markdown",
    )
    await state.set_state(RegistrationStates.waiting_for_country_name)


def register_registration_handlers(dp: Dispatcher) -> None:
    """Register registration handlers"""
    dp.message.register(register_command, Command("register"))
    dp.message.register(process_reregistration_confirmation, RegistrationStates.waiting_for_reregistration_confirmation)
    dp.message.register(process_country_name, RegistrationStates.waiting_for_country_name)
    dp.message.register(process_country_description, RegistrationStates.waiting_for_country_description)
    dp.message.register(process_economy, RegistrationStates.waiting_for_economy)
    dp.message.register(process_military, RegistrationStates.waiting_for_military)
    dp.message.register(process_foreign_policy, RegistrationStates.waiting_for_foreign_policy)
    dp.message.register(process_territory, RegistrationStates.waiting_for_territory)
    dp.message.register(process_technology, RegistrationStates.waiting_for_technology)
    dp.message.register(process_religion_culture, RegistrationStates.waiting_for_religion_culture)
    dp.message.register(process_governance_law, RegistrationStates.waiting_for_governance_law)
    dp.message.register(
        process_construction_infrastructure,
        RegistrationStates.waiting_for_construction_infrastructure,
    )
    dp.message.register(process_social_relations, RegistrationStates.waiting_for_social_relations)
    dp.message.register(process_intelligence, RegistrationStates.waiting_for_intelligence)
    dp.message.register(process_capital, RegistrationStates.waiting_for_capital)
    dp.message.register(process_population, RegistrationStates.waiting_for_population)
