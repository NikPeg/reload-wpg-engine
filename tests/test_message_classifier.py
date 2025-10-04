"""
Тесты для классификатора сообщений
"""

from unittest.mock import AsyncMock, patch

import pytest

from wpg_engine.core.message_classifier import MessageClassifier


class TestMessageClassifier:
    """Тесты для MessageClassifier"""

    @pytest.fixture
    def classifier(self):
        """Создать экземпляр классификатора"""
        return MessageClassifier()

    def test_normalize_classification(self, classifier):
        """Тест нормализации классификации"""
        # Тест точных совпадений
        assert classifier._normalize_classification("вопрос") == "вопрос"
        assert classifier._normalize_classification("приказ") == "приказ"
        assert classifier._normalize_classification("проект") == "проект"

        # Тест с дополнительным текстом
        assert classifier._normalize_classification("это вопрос игрока") == "вопрос"
        assert classifier._normalize_classification("определенно приказ") == "приказ"
        assert classifier._normalize_classification("долгосрочный проект") == "проект"

        # Тест неизвестных типов
        assert classifier._normalize_classification("неизвестно") == "иное"
        assert classifier._normalize_classification("") == "иное"
        assert classifier._normalize_classification("что-то странное") == "иное"

    async def test_classify_message_no_api_key(self, classifier):
        """Тест классификации без API ключа"""
        # Временно устанавливаем api_key в None
        original_api_key = classifier.api_key
        classifier.api_key = None

        result = await classifier.classify_message("Какой сейчас год?", "Россия")
        assert result == "иное"

        # Восстанавливаем оригинальное значение
        classifier.api_key = original_api_key

    async def test_classify_message_success(self, classifier):
        """Тест успешной классификации через мокинг метода _call_openrouter_api"""
        # Устанавливаем тестовые значения
        classifier.api_key = "test_key"
        classifier.model = "test_model"

        # Мокаем метод _call_openrouter_api напрямую
        async def mock_api_call(prompt):
            return "вопрос"

        classifier._call_openrouter_api = mock_api_call

        result = await classifier.classify_message("Какой сейчас год?", "Россия")
        assert result == "вопрос"

    @patch("wpg_engine.core.message_classifier.httpx.AsyncClient")
    async def test_classify_message_api_error(self, mock_client, classifier):
        """Тест обработки ошибки API"""
        # Устанавливаем тестовые значения
        classifier.api_key = "test_key"
        classifier.model = "test_model"

        # Мокаем ошибку API
        mock_client_instance = AsyncMock()
        mock_client_instance.post.side_effect = Exception("API Error")
        mock_client.return_value.__aenter__.return_value = mock_client_instance

        result = await classifier.classify_message("Какой сейчас год?", "Россия")
        assert result == "иное"

    def test_create_classification_prompt(self, classifier):
        """Тест создания промпта для классификации"""
        message = "Какой сейчас год?"
        country = "Россия"

        prompt = classifier._create_classification_prompt(message, country)

        assert message in prompt
        assert country in prompt
        assert "ВОПРОС" in prompt
        assert "ПРИКАЗ" in prompt
        assert "ПРОЕКТ" in prompt
        assert "ИНОЕ" in prompt
        assert "Тип:" in prompt


# Интеграционные тесты для проверки примеров из задания
class TestMessageClassificationExamples:
    """Тесты классификации на примерах из задания"""

    @pytest.fixture
    def classifier(self):
        return MessageClassifier()

    def test_question_examples(self, classifier):
        """Тест примеров вопросов"""
        questions = [
            "какой сейчас год?",
            "Какая страна на нас напала?",
            "С кем мы воюем?",
            "Сколько у нас населения?",
        ]

        for question in questions:
            # Проверяем, что промпт содержит правильные примеры
            prompt = classifier._create_classification_prompt(
                question, "Тестовая страна"
            )
            assert "какой год?" in prompt.lower()
            assert "кто напал?" in prompt.lower()

    def test_command_examples(self, classifier):
        """Тест примеров приказов"""
        commands = [
            "отправить разведчиков",
            "объявить войну Вирджинии",
            "переименовать государство",
        ]

        for command in commands:
            prompt = classifier._create_classification_prompt(
                command, "Тестовая страна"
            )
            assert "атаковать" in prompt.lower()
            assert "объявить войну" in prompt.lower()

    def test_project_examples(self, classifier):
        """Тест примеров проектов"""
        projects = ["захватить Вирджинию", "построить ракету", "перейти к демократии"]

        for project in projects:
            prompt = classifier._create_classification_prompt(
                project, "Тестовая страна"
            )
            assert "захватить континент" in prompt.lower()
            assert "построить космодром" in prompt.lower()

    def test_other_examples(self, classifier):
        """Тест примеров 'иное'"""
        others = ["ахахха", "понял", "ну ладно", "грустно"]

        for other in others:
            prompt = classifier._create_classification_prompt(other, "Тестовая страна")
            assert "хаха" in prompt.lower()
            assert "понял" in prompt.lower()
