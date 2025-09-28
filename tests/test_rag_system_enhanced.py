"""
Тесты для улучшенной RAG системы с типизированными анализаторами
"""

from unittest.mock import AsyncMock, patch

import pytest

from wpg_engine.core.rag_system import RAGSystem


@pytest.fixture
def mock_db():
    """Мок базы данных"""
    return AsyncMock()


@pytest.fixture
def sample_countries_data():
    """Пример данных о странах для тестов"""
    return [
        {
            "name": "Тестовая Страна",
            "capital": "Тестград",
            "population": 1000000,
            "synonyms": ["ТС"],
            "aspects": {
                "economy": 5,
                "military": 7,
                "foreign_policy": 6,
                "territory": 4,
                "technology": 8,
                "religion_culture": 5,
                "governance_law": 6,
                "construction_infrastructure": 7,
                "social_relations": 5,
                "intelligence": 6,
            },
            "descriptions": {
                "economy": "Средняя экономика",
                "military": "Сильная армия",
                "foreign_policy": "Активная дипломатия",
                "territory": "Небольшая территория",
                "technology": "Высокие технологии",
                "religion_culture": "Традиционная культура",
                "governance_law": "Стабильное управление",
                "construction_infrastructure": "Развитая инфраструктура",
                "social_relations": "Стабильные отношения",
                "intelligence": "Хорошая разведка",
            },
        }
    ]


class TestRAGSystemEnhanced:
    """Тесты для улучшенной RAG системы"""

    @pytest.fixture
    def rag_system(self, mock_db):
        """Создание экземпляра RAG системы для тестов"""
        with patch("wpg_engine.core.rag_system.settings") as mock_settings:
            mock_settings.ai.openrouter_api_key = "test_api_key"
            mock_settings.ai.default_model = "test_model"
            return RAGSystem(mock_db)

    @patch("wpg_engine.core.rag_system.MessageClassifier")
    async def test_generate_admin_context_question(
        self, mock_classifier_class, rag_system, sample_countries_data
    ):
        """Тест генерации контекста для вопроса"""
        # Настройка моков
        mock_classifier = AsyncMock()
        mock_classifier.classify_message.return_value = "вопрос"
        mock_classifier_class.return_value = mock_classifier

        rag_system.classifier = mock_classifier

        # Мок для получения данных о странах
        rag_system._get_all_countries_data = AsyncMock(
            return_value=sample_countries_data
        )
        rag_system._get_previous_admin_message = AsyncMock(return_value=None)
        rag_system._call_openrouter_api = AsyncMock(return_value="Тестовый ответ")

        # Вызов метода
        result = await rag_system.generate_admin_context(
            "Какая у нас экономика?", "Тестовая Страна", 1, 1
        )

        # Проверки
        assert result == "Тестовый ответ"
        mock_classifier.classify_message.assert_called_once_with(
            "Какая у нас экономика?", "Тестовая Страна"
        )
        rag_system._call_openrouter_api.assert_called_once()

        # Проверяем, что был вызван правильный промпт (содержит специфичные для вопроса элементы)
        call_args = rag_system._call_openrouter_api.call_args[0][0]
        assert "задал ВОПРОС" in call_args
        assert "дать точный ответ" in call_args

    @patch("wpg_engine.core.rag_system.MessageClassifier")
    async def test_generate_admin_context_order(
        self, mock_classifier_class, rag_system, sample_countries_data
    ):
        """Тест генерации контекста для приказа"""
        # Настройка моков
        mock_classifier = AsyncMock()
        mock_classifier.classify_message.return_value = "приказ"
        mock_classifier_class.return_value = mock_classifier

        rag_system.classifier = mock_classifier
        rag_system._get_all_countries_data = AsyncMock(
            return_value=sample_countries_data
        )
        rag_system._get_previous_admin_message = AsyncMock(return_value=None)
        rag_system._call_openrouter_api = AsyncMock(return_value="Анализ приказа")

        # Вызов метода
        result = await rag_system.generate_admin_context(
            "Объявить войну соседям", "Тестовая Страна", 1, 1
        )

        # Проверки
        assert result == "Анализ приказа"
        mock_classifier.classify_message.assert_called_once_with(
            "Объявить войну соседям", "Тестовая Страна"
        )

        # Проверяем, что был вызван правильный промпт (содержит специфичные для приказа элементы)
        call_args = rag_system._call_openrouter_api.call_args[0][0]
        assert "отдал ПРИКАЗ" in call_args
        assert "ВЕРОЯТНОСТЬ УСПЕХА" in call_args

    @patch("wpg_engine.core.rag_system.MessageClassifier")
    async def test_generate_admin_context_project(
        self, mock_classifier_class, rag_system, sample_countries_data
    ):
        """Тест генерации контекста для проекта"""
        # Настройка моков
        mock_classifier = AsyncMock()
        mock_classifier.classify_message.return_value = "проект"
        mock_classifier_class.return_value = mock_classifier

        rag_system.classifier = mock_classifier
        rag_system._get_all_countries_data = AsyncMock(
            return_value=sample_countries_data
        )
        rag_system._get_previous_admin_message = AsyncMock(return_value=None)
        rag_system._call_openrouter_api = AsyncMock(return_value="Анализ проекта")

        # Вызов метода
        result = await rag_system.generate_admin_context(
            "Построить космическую программу", "Тестовая Страна", 1, 1
        )

        # Проверки
        assert result == "Анализ проекта"

        # Проверяем, что был вызван правильный промпт (содержит специфичные для проекта элементы)
        call_args = rag_system._call_openrouter_api.call_args[0][0]
        assert "предложил ПРОЕКТ" in call_args
        assert "СРОК ИСПОЛНЕНИЯ" in call_args

    @patch("wpg_engine.core.rag_system.MessageClassifier")
    async def test_generate_admin_context_other_no_rag(
        self, mock_classifier_class, rag_system, sample_countries_data
    ):
        """Тест что для типа 'иное' RAG не запускается"""
        # Настройка моков
        mock_classifier = AsyncMock()
        mock_classifier.classify_message.return_value = "иное"
        mock_classifier_class.return_value = mock_classifier

        rag_system.classifier = mock_classifier
        rag_system._get_all_countries_data = AsyncMock(
            return_value=sample_countries_data
        )
        rag_system._get_previous_admin_message = AsyncMock(return_value=None)
        rag_system._call_openrouter_api = AsyncMock()

        # Вызов метода
        result = await rag_system.generate_admin_context(
            "Спасибо", "Тестовая Страна", 1, 1
        )

        # Проверки
        assert result == ""  # Пустая строка для типа "иное"

        # Проверяем, что RAG API НЕ вызывался
        rag_system._call_openrouter_api.assert_not_called()

    @patch("wpg_engine.core.rag_system.MessageClassifier")
    async def test_generate_admin_context_with_previous_message(
        self, mock_classifier_class, rag_system, sample_countries_data
    ):
        """Тест генерации контекста с предыдущим сообщением админа"""
        # Настройка моков
        mock_classifier = AsyncMock()
        mock_classifier.classify_message.return_value = "вопрос"
        mock_classifier_class.return_value = mock_classifier

        rag_system.classifier = mock_classifier
        rag_system._get_all_countries_data = AsyncMock(
            return_value=sample_countries_data
        )
        rag_system._get_previous_admin_message = AsyncMock(
            return_value="Предыдущее сообщение админа"
        )
        rag_system._call_openrouter_api = AsyncMock(return_value="Контекстный ответ")

        # Вызов метода
        result = await rag_system.generate_admin_context(
            "А что дальше?", "Тестовая Страна", 1, 1
        )

        # Проверки
        assert result == "Контекстный ответ"

        # Проверяем, что контекст включен в промпт
        call_args = rag_system._call_openrouter_api.call_args[0][0]
        assert "КОНТЕКСТ:" in call_args
        assert "Предыдущее сообщение админа" in call_args
        assert "(учитывая контекст предыдущих сообщений)" in call_args

    async def test_generate_admin_context_no_api_key(self, mock_db):
        """Тест поведения без API ключа"""
        with patch("wpg_engine.core.rag_system.settings") as mock_settings:
            mock_settings.ai.openrouter_api_key = None
            rag_system = RAGSystem(mock_db)

            result = await rag_system.generate_admin_context(
                "Тест", "Тестовая Страна", 1, 1
            )

            assert result == ""

    @patch("wpg_engine.core.rag_system.MessageClassifier")
    async def test_generate_admin_context_no_countries_data(
        self, mock_classifier_class, rag_system
    ):
        """Тест поведения без данных о странах"""
        # Настройка моков
        mock_classifier = AsyncMock()
        mock_classifier_class.return_value = mock_classifier

        rag_system.classifier = mock_classifier
        rag_system._get_all_countries_data = AsyncMock(return_value=[])

        result = await rag_system.generate_admin_context(
            "Тест", "Тестовая Страна", 1, 1
        )

        assert result == ""

    @patch("wpg_engine.core.rag_system.MessageClassifier")
    async def test_generate_admin_context_api_error(
        self, mock_classifier_class, rag_system, sample_countries_data
    ):
        """Тест обработки ошибки API"""
        # Настройка моков
        mock_classifier = AsyncMock()
        mock_classifier.classify_message.return_value = "вопрос"
        mock_classifier_class.return_value = mock_classifier

        rag_system.classifier = mock_classifier
        rag_system._get_all_countries_data = AsyncMock(
            return_value=sample_countries_data
        )
        rag_system._get_previous_admin_message = AsyncMock(return_value=None)
        rag_system._call_openrouter_api = AsyncMock(side_effect=Exception("API Error"))

        result = await rag_system.generate_admin_context(
            "Тест", "Тестовая Страна", 1, 1
        )

        assert result == ""

    async def test_debug_output(self, rag_system, sample_countries_data, capsys):
        """Тест отладочного вывода"""
        with patch(
            "wpg_engine.core.rag_system.MessageClassifier"
        ) as mock_classifier_class:
            # Настройка моков
            mock_classifier = AsyncMock()
            mock_classifier.classify_message.return_value = "приказ"
            mock_classifier_class.return_value = mock_classifier

            rag_system.classifier = mock_classifier
            rag_system._get_all_countries_data = AsyncMock(
                return_value=sample_countries_data
            )
            rag_system._get_previous_admin_message = AsyncMock(
                return_value="Предыдущее сообщение"
            )
            rag_system._call_openrouter_api = AsyncMock(return_value="Ответ")

            await rag_system.generate_admin_context("Тест", "Тестовая Страна", 1, 1)

            # Проверяем отладочный вывод
            captured = capsys.readouterr()
            assert "🔍 RAG DEBUG: Тип сообщения: приказ" in captured.out
            assert "🔍 RAG DEBUG: Полный промпт для LLM:" in captured.out
            assert "✅ Найдено предыдущее сообщение админа" in captured.out
