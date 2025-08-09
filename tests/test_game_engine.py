"""
Тесты основной функциональности игрового движка
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from wpg_engine.core.engine import GameEngine
from wpg_engine.models import Game, PlayerRole


@pytest.fixture
async def game_engine(db_session: AsyncSession):
    """Создать экземпляр игрового движка"""
    return GameEngine(db_session)


@pytest.fixture
async def test_game(game_engine: GameEngine):
    """Создать тестовую игру"""
    return await game_engine.create_game(
        name="Тестовая игра",
        description="Игра для тестирования функциональности",
        setting="Современность",
        max_players=10,
    )


class TestGameEngine:
    """Тесты основной функциональности игрового движка"""

    async def test_create_game(self, game_engine: GameEngine):
        """Тест создания игры"""
        game = await game_engine.create_game(
            name="Новая игра",
            description="Описание игры",
            setting="Фэнтези",
            max_players=8,
        )

        assert game.id is not None
        assert game.name == "Новая игра"
        assert game.description == "Описание игры"
        assert game.setting == "Фэнтези"
        assert game.max_players == 8

    async def test_create_country(self, game_engine: GameEngine, test_game: Game):
        """Тест создания страны"""
        country = await game_engine.create_country(
            game_id=test_game.id,
            name="Тестовое королевство",
            description="Описание страны",
            capital="Столица",
            population=1000000,
            aspects={"economy": 7, "military": 5, "technology": 8},
        )

        assert country.id is not None
        assert country.name == "Тестовое королевство"
        assert country.capital == "Столица"
        assert country.population == 1000000
        assert country.economy == 7
        assert country.military == 5
        assert country.technology == 8

    async def test_create_admin_player(self, game_engine: GameEngine, test_game: Game):
        """Тест создания администратора"""
        admin = await game_engine.create_player(
            game_id=test_game.id,
            telegram_id=123456789,
            username="admin_user",
            display_name="Администратор",
            role=PlayerRole.ADMIN,
        )

        assert admin.id is not None
        assert admin.telegram_id == 123456789
        assert admin.username == "admin_user"
        assert admin.display_name == "Администратор"
        assert admin.role == PlayerRole.ADMIN

    async def test_create_regular_player_with_country(
        self, game_engine: GameEngine, test_game: Game
    ):
        """Тест создания обычного игрока и назначения ему страны"""
        # Создаем страну
        country = await game_engine.create_country(
            game_id=test_game.id,
            name="Игровая страна",
            description="Страна для игрока",
            capital="Город",
            population=500000,
        )

        # Создаем игрока
        player = await game_engine.create_player(
            game_id=test_game.id,
            telegram_id=987654321,
            username="player1",
            display_name="Игрок 1",
            role=PlayerRole.PLAYER,
        )

        # Назначаем игроку страну
        success = await game_engine.assign_player_to_country(player.id, country.id)

        assert success is True
        assert player.id is not None
        assert player.telegram_id == 987654321
        assert player.role == PlayerRole.PLAYER

    async def test_create_post(self, game_engine: GameEngine, test_game: Game):
        """Тест создания поста"""
        # Создаем игрока
        player = await game_engine.create_player(
            game_id=test_game.id,
            telegram_id=111222333,
            username="author",
            display_name="Автор",
            role=PlayerRole.PLAYER,
        )

        # Создаем пост
        post = await game_engine.create_post(
            author_id=player.id, game_id=test_game.id, content="Тестовый пост от игрока"
        )

        assert post.id is not None
        assert post.author_id == player.id
        assert post.game_id == test_game.id
        assert post.content == "Тестовый пост от игрока"

    async def test_create_verdict(self, game_engine: GameEngine, test_game: Game):
        """Тест создания вердикта"""
        # Создаем администратора
        admin = await game_engine.create_player(
            game_id=test_game.id,
            telegram_id=444555666,
            username="admin",
            display_name="Админ",
            role=PlayerRole.ADMIN,
        )

        # Создаем игрока
        player = await game_engine.create_player(
            game_id=test_game.id,
            telegram_id=777888999,
            username="player",
            display_name="Игрок",
            role=PlayerRole.PLAYER,
        )

        # Создаем пост
        post = await game_engine.create_post(
            author_id=player.id, game_id=test_game.id, content="Пост для вердикта"
        )

        # Создаем вердикт
        verdict = await game_engine.create_verdict(
            post_id=post.id,
            admin_id=admin.id,
            result="Одобрено",
            reasoning="Пост соответствует правилам",
        )

        assert verdict.id is not None
        assert verdict.post_id == post.id
        assert verdict.admin_id == admin.id
        assert verdict.result == "Одобрено"
        assert verdict.reasoning == "Пост соответствует правилам"

    async def test_start_game(self, game_engine: GameEngine, test_game: Game):
        """Тест запуска игры"""
        success = await game_engine.start_game(test_game.id)
        assert success is True

        # Проверяем, что статус игры изменился
        updated_game = await game_engine.get_game(test_game.id)
        assert updated_game.status.value == "active"

    async def test_game_statistics(self, game_engine: GameEngine, test_game: Game):
        """Тест получения статистики игры"""
        # Создаем некоторые данные
        await game_engine.create_country(
            game_id=test_game.id, name="Страна 1", description="Первая страна"
        )

        await game_engine.create_player(
            game_id=test_game.id,
            telegram_id=123123123,
            username="test_player",
            display_name="Тестовый игрок",
            role=PlayerRole.PLAYER,
        )

        # Получаем статистику
        stats = await game_engine.get_game_statistics(test_game.id)

        assert stats["game_id"] == test_game.id
        assert stats["game_name"] == test_game.name
        assert stats["countries_count"] == 1
        assert stats["players_count"] == 1
        assert "created_at" in stats
        assert "updated_at" in stats

    async def test_update_country_aspects(
        self, game_engine: GameEngine, test_game: Game
    ):
        """Тест обновления аспектов страны"""
        # Создаем страну
        country = await game_engine.create_country(
            game_id=test_game.id,
            name="Развивающаяся страна",
            description="Страна для тестирования обновлений",
            aspects={"economy": 5, "military": 3},
        )

        # Обновляем аспекты
        updated_country = await game_engine.update_country_aspects(
            country_id=country.id, aspects={"economy": 7, "technology": 6}
        )

        assert updated_country.economy == 7
        assert updated_country.military == 3  # Не изменился
        assert updated_country.technology == 6
