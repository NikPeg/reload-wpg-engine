"""
Admin example commands
"""

from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import select

from wpg_engine.adapters.telegram.utils import escape_html
from wpg_engine.core.admin_utils import get_admin_player, is_admin
from wpg_engine.core.engine import GameEngine
from wpg_engine.models import Example, get_db


async def add_example_command(message: Message, state: FSMContext) -> None:
    """Handle /add_example command - mark a country as example for new players"""
    user_id = message.from_user.id
    args = message.text.split(maxsplit=1)

    async with get_db() as db:
        game_engine = GameEngine(db)

        # Check if user is admin
        if not await is_admin(user_id, game_engine.db, message.chat.id):
            await message.answer("❌ У вас нет прав администратора.")
            return

        # Get admin player (works for both admin chat and admin user)
        admin = await get_admin_player(user_id, game_engine.db)

        if not admin:
            await message.answer(
                "❌ В игре нет зарегистрированных администраторов. Создайте игру с помощью /restart_game"
            )
            return

        # Check if country name is provided
        if len(args) < 2:
            await message.answer(
                "❌ Укажите название страны.\n\n"
                "Формат: <code>/add_example Название страны</code>\n\n"
                "Пример: <code>/add_example Римская Империя</code>",
                parse_mode="HTML",
            )
            return

        country_name = args[1].strip()

        # Find country by name or synonym
        country = await game_engine.find_country_by_name_or_synonym(
            admin.game_id, country_name
        )

        if not country:
            await message.answer(
                f"❌ Страна '{escape_html(country_name)}' не найдена.\n\n"
                f"Используйте /world для просмотра всех стран.",
                parse_mode="HTML",
            )
            return

        # Check if country is already an example
        result = await game_engine.db.execute(
            select(Example).where(Example.country_id == country.id)
        )
        existing_example = result.scalar_one_or_none()

        if existing_example:
            await message.answer(
                f"ℹ️ Страна <b>{escape_html(country.name)}</b> уже является примером.",
                parse_mode="HTML",
            )
            return

        # Create new example
        example = Example(
            country_id=country.id,
            game_id=admin.game_id,
            created_by_id=admin.id,
        )

        game_engine.db.add(example)
        await game_engine.db.commit()
        await game_engine.db.refresh(example)

        await message.answer(
            f"✅ <b>Страна добавлена в примеры!</b>\n\n"
            f"<b>Страна:</b> {escape_html(country.name)}\n\n"
            f"Новые игроки смогут увидеть эту страну как пример при регистрации, используя команду /examples",
            parse_mode="HTML",
        )


async def process_example_message(message: Message, state: FSMContext) -> None:
    """Process example message from admin - NO LONGER USED"""
    # This function is no longer needed but kept for backward compatibility
    await state.clear()
    await message.answer(
        "⚠️ Эта функция больше не используется. Используйте /add_example с названием страны.",
        parse_mode="HTML",
    )
