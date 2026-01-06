"""
Admin game management commands
"""

from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import text

from wpg_engine.adapters.telegram.utils import escape_html, escape_markdown
from wpg_engine.core.admin_utils import is_admin
from wpg_engine.core.engine import GameEngine
from wpg_engine.models import PlayerRole, get_db

from .admin_utils import AdminStates


async def restart_game_command(message: Message, state: FSMContext) -> None:
    """Handle /restart_game command"""
    user_id = message.from_user.id
    args = message.text.split(" ", 1)

    async with get_db() as db:
        game_engine = GameEngine(db)

        # Check if user is admin
        if not await is_admin(user_id, game_engine.db, message.chat.id):
            await message.answer("❌ У вас нет прав администратора.")
            return

        if len(args) < 2:
            await message.answer(
                "❌ Неверный формат команды.\n\n"
                "Используйте: <code>/restart_game Название игры | Сеттинг | Лет за сутки | Макс очков | Макс население</code>\n\n"
                "Пример: <code>/restart_game Древний мир | Античность | 10 | 30 | 10000000</code>\n"
                "• Макс очков - максимальная сумма очков для аспектов страны (по умолчанию 30)\n"
                "• Макс население - максимальное население страны (по умолчанию 10,000,000)",
                parse_mode="HTML",
            )
            return

        try:
            # Parse arguments
            parts = [part.strip() for part in args[1].split("|")]
            if len(parts) < 3 or len(parts) > 5:
                raise ValueError("Неверное количество параметров")

            game_name, setting, years_per_day_str = parts[:3]
            max_points_str = parts[3] if len(parts) >= 4 else "30"
            max_population_str = parts[4] if len(parts) == 5 else "10000000"

            years_per_day = int(years_per_day_str)
            max_points = int(max_points_str)
            max_population = int(max_population_str)

            if not game_name or not setting:
                raise ValueError("Название игры и сеттинг не могут быть пустыми")

            if years_per_day < 1 or years_per_day > 365:
                raise ValueError("Количество лет за сутки должно быть от 1 до 365")

            if max_points < 10 or max_points > 100:
                raise ValueError(
                    "Максимальное количество очков должно быть от 10 до 100"
                )

            if max_population < 1000 or max_population > 1_000_000_000:
                raise ValueError(
                    "Максимальное население должно быть от 1,000 до 1 млрд"
                )

        except ValueError as e:
            await message.answer(
                f"❌ Ошибка в параметрах: {e}\n\n"
                "Используйте: <code>/restart_game Название игры | Сеттинг | Лет за сутки | Макс очков | Макс население</code>\n\n"
                "Пример: <code>/restart_game Древний мир | Античность | 10 | 30 | 10000000</code>",
                parse_mode="HTML",
            )
            return

        # Store data for confirmation
        await state.update_data(
            user_id=user_id,
            game_name=game_name,
            setting=setting,
            years_per_day=years_per_day,
            max_points=max_points,
            max_population=max_population,
        )

        await message.answer(
            f"⚠️ *ВНИМАНИЕ! ОПАСНАЯ ОПЕРАЦИЯ!*\n\n"
            f"Вы собираетесь *ПОЛНОСТЬЮ ОЧИСТИТЬ* всю базу данных и создать новую игру:\n\n"
            f"*Название:* {escape_markdown(game_name)}\n"
            f"*Сеттинг:* {escape_markdown(setting)}\n"
            f"*Лет за сутки:* {years_per_day}\n"
            f"*Макс очков:* {max_points}\n"
            f"*Макс население:* {max_population:,}\n\n"
            f"*ВСЕ ДАННЫЕ БУДУТ ПОТЕРЯНЫ НАВСЕГДА:*\n"
            f"• Все игры\n"
            f"• Все игроки\n"
            f"• Все страны\n"
            f"• Все сообщения\n"
            f"• Все посты\n\n"
            f"Это действие *НЕОБРАТИМО*!\n\n"
            f"Вы *ДЕЙСТВИТЕЛЬНО* хотите перезапустить игру?\n\n"
            f"Напишите *ПОДТВЕРЖДАЮ* (заглавными буквами), чтобы продолжить, или любое другое сообщение для отмены.",
            parse_mode="Markdown",
        )
        await state.set_state(AdminStates.waiting_for_restart_confirmation)


async def process_restart_confirmation(message: Message, state: FSMContext) -> None:
    """Process confirmation for game restart"""
    confirmation = message.text.strip()

    if confirmation != "ПОДТВЕРЖДАЮ":
        await message.answer("❌ Перезапуск игры отменен.")
        await state.clear()
        return

    # Get stored data
    data = await state.get_data()
    user_id = data["user_id"]
    game_name = data["game_name"]
    setting = data["setting"]
    years_per_day = data["years_per_day"]
    max_points = data["max_points"]
    max_population = data["max_population"]

    async with get_db() as db:
        game_engine = GameEngine(db)

        # ПОЛНАЯ ОЧИСТКА БАЗЫ ДАННЫХ
        await message.answer("🔄 Очищаю базу данных...")

        # Удаляем все данные из всех таблиц
        await game_engine.db.execute(text("DELETE FROM verdicts"))
        await game_engine.db.execute(text("DELETE FROM posts"))
        await game_engine.db.execute(text("DELETE FROM messages"))
        await game_engine.db.execute(text("DELETE FROM examples"))
        await game_engine.db.execute(text("DELETE FROM players"))
        await game_engine.db.execute(text("DELETE FROM countries"))
        await game_engine.db.execute(text("DELETE FROM games"))
        await game_engine.db.commit()

        await message.answer("✅ База данных очищена. Создаю новую игру...")

        # Create new game
        game = await game_engine.create_game(
            name=game_name,
            description=f"Игра в сеттинге '{setting}'",
            setting=setting,
            max_players=20,
            years_per_day=years_per_day,
            max_points=max_points,
            max_population=max_population,
        )

        # Create admin player WITHOUT a country
        username = message.from_user.username
        display_name = message.from_user.full_name or f"Admin_{user_id}"

        await game_engine.create_player(
            game_id=game.id,
            telegram_id=user_id,
            username=username,
            display_name=display_name,
            role=PlayerRole.ADMIN,
        )

        await message.answer(
            f"✅ <b>Игра успешно перезапущена!</b>\n\n"
            f"<b>Название:</b> {escape_html(game_name)}\n"
            f"<b>Сеттинг:</b> {escape_html(setting)}\n"
            f"<b>Лет за сутки:</b> {years_per_day}\n"
            f"<b>Макс очков для стран:</b> {max_points}\n"
            f"<b>Макс население стран:</b> {max_population:,}\n"
            f"<b>ID игры:</b> {game.id}\n\n"
            f"Вы назначены администратором игры.\n\n"
            f"<i>💡 Администратору не требуется страна. "
            f"Если вы хотите создать страну для себя, используйте /register</i>\n\n"
            f"Теперь игроки могут регистрироваться в игре командой /register",
            parse_mode="HTML",
        )

    await state.clear()
