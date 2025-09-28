"""
Тесты для RAG анализаторов
"""

import pytest

from wpg_engine.core.rag_analyzers import (
    BaseRAGAnalyzer,
    OrderAnalyzer,
    OtherAnalyzer,
    ProjectAnalyzer,
    QuestionAnalyzer,
    RAGAnalyzerFactory,
)


@pytest.fixture
def sample_countries_data():
    """Пример данных о странах для тестов"""
    return [
        {
            "name": "Тестовая Страна",
            "capital": "Тестград",
            "population": 1000000,
            "synonyms": ["ТС", "Тестовая"],
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
        },
        {
            "name": "Соседняя Страна",
            "capital": "Соседград",
            "population": 2000000,
            "synonyms": ["СС"],
            "aspects": {
                "economy": 6,
                "military": 4,
                "foreign_policy": 5,
                "territory": 8,
                "technology": 3,
                "religion_culture": 7,
                "governance_law": 5,
                "construction_infrastructure": 4,
                "social_relations": 6,
                "intelligence": 5,
            },
            "descriptions": {
                "economy": "Развитая экономика",
                "military": "Слабая армия",
                "foreign_policy": "Нейтральная позиция",
                "territory": "Большая территория",
                "technology": "Отстающие технологии",
                "religion_culture": "Богатая культура",
                "governance_law": "Нестабильное управление",
                "construction_infrastructure": "Слабая инфраструктура",
                "social_relations": "Хорошие отношения",
                "intelligence": "Средняя разведка",
            },
        },
    ]


class TestBaseRAGAnalyzer:
    """Тесты для базового RAG анализатора"""

    def test_format_countries_info(self, sample_countries_data):
        """Тест форматирования информации о странах"""

        class TestAnalyzer(BaseRAGAnalyzer):
            def create_analysis_prompt(self, message, previous_admin_message=None):
                return "test"

        analyzer = TestAnalyzer(sample_countries_data, "Тестовая Страна")
        countries_info = analyzer._format_countries_info()

        assert "Тестовая Страна" in countries_info
        assert "Соседняя Страна" in countries_info
        assert "Тестград" in countries_info
        assert "1,000,000" in countries_info
        assert "Экономика: 5 - Средняя экономика" in countries_info
        assert "Военное дело: 7 - Сильная армия" in countries_info

    def test_format_context_section_with_message(self, sample_countries_data):
        """Тест форматирования секции контекста с предыдущим сообщением"""

        class TestAnalyzer(BaseRAGAnalyzer):
            def create_analysis_prompt(self, message, previous_admin_message=None):
                return "test"

        analyzer = TestAnalyzer(sample_countries_data, "Тестовая Страна")
        previous_message = "Предыдущее сообщение админа"
        context = analyzer._format_context_section(previous_message)

        assert "КОНТЕКСТ:" in context
        assert previous_message in context
        assert "может быть ответом" in context

    def test_format_context_section_without_message(self, sample_countries_data):
        """Тест форматирования секции контекста без предыдущего сообщения"""

        class TestAnalyzer(BaseRAGAnalyzer):
            def create_analysis_prompt(self, message, previous_admin_message=None):
                return "test"

        analyzer = TestAnalyzer(sample_countries_data, "Тестовая Страна")
        context = analyzer._format_context_section(None)

        assert context == ""


class TestQuestionAnalyzer:
    """Тесты для анализатора вопросов"""

    def test_create_analysis_prompt(self, sample_countries_data):
        """Тест создания промпта для вопроса"""
        analyzer = QuestionAnalyzer(sample_countries_data, "Тестовая Страна")
        message = "Какая у нас экономика?"

        prompt = analyzer.create_analysis_prompt(message)

        assert "задал ВОПРОС" in prompt
        assert message in prompt
        assert "Тестовая Страна" in prompt
        assert "дать точный ответ на вопрос" in prompt
        assert "фактических данных" in prompt

    def test_create_analysis_prompt_with_context(self, sample_countries_data):
        """Тест создания промпта для вопроса с контекстом"""
        analyzer = QuestionAnalyzer(sample_countries_data, "Тестовая Страна")
        message = "А что с военными?"
        previous_message = "Ваша экономика на среднем уровне"

        prompt = analyzer.create_analysis_prompt(message, previous_message)

        assert "КОНТЕКСТ:" in prompt
        assert previous_message in prompt
        assert "(учитывая контекст предыдущих сообщений)" in prompt


class TestOrderAnalyzer:
    """Тесты для анализатора приказов"""

    def test_create_analysis_prompt(self, sample_countries_data):
        """Тест создания промпта для приказа"""
        analyzer = OrderAnalyzer(sample_countries_data, "Тестовая Страна")
        message = "Объявить войну Соседней Стране"

        prompt = analyzer.create_analysis_prompt(message)

        assert "отдал ПРИКАЗ" in prompt
        assert message in prompt
        assert "ВЕРОЯТНОСТЬ УСПЕХА (0-100%)" in prompt
        assert "с обоснованием" in prompt
        assert "ключевые факторы" in prompt
        assert "военную мощь" in prompt

    def test_create_analysis_prompt_with_context(self, sample_countries_data):
        """Тест создания промпта для приказа с контекстом"""
        analyzer = OrderAnalyzer(sample_countries_data, "Тестовая Страна")
        message = "Начать наступление"
        previous_message = "Готовьтесь к войне"

        prompt = analyzer.create_analysis_prompt(message, previous_message)

        assert "КОНТЕКСТ:" in prompt
        assert previous_message in prompt
        assert "ВЕРОЯТНОСТЬ УСПЕХА" in prompt


class TestProjectAnalyzer:
    """Тесты для анализатора проектов"""

    def test_create_analysis_prompt(self, sample_countries_data):
        """Тест создания промпта для проекта"""
        analyzer = ProjectAnalyzer(sample_countries_data, "Тестовая Страна")
        message = "Построить космическую программу"

        prompt = analyzer.create_analysis_prompt(message)

        assert "предложил ПРОЕКТ" in prompt
        assert message in prompt
        assert "СРОК ИСПОЛНЕНИЯ проекта (в годах)" in prompt
        assert "с обоснованием" in prompt
        assert "необходимые ресурсы" in prompt

    def test_create_analysis_prompt_with_context(self, sample_countries_data):
        """Тест создания промпта для проекта с контекстом"""
        analyzer = ProjectAnalyzer(sample_countries_data, "Тестовая Страна")
        message = "Расширить программу"
        previous_message = "Ваши технологии позволяют начать космическую программу"

        prompt = analyzer.create_analysis_prompt(message, previous_message)

        assert "КОНТЕКСТ:" in prompt
        assert previous_message in prompt
        assert "СРОК ИСПОЛНЕНИЯ" in prompt


class TestOtherAnalyzer:
    """Тесты для анализатора прочих сообщений"""

    def test_create_analysis_prompt(self, sample_countries_data):
        """Тест создания промпта для прочего сообщения"""
        analyzer = OtherAnalyzer(sample_countries_data, "Тестовая Страна")
        message = "Понятно, спасибо"

        prompt = analyzer.create_analysis_prompt(message)

        assert "отправил сообщение" in prompt
        assert message in prompt
        assert "понять контекст сообщения" in prompt
        assert "возможном значении" in prompt

    def test_create_analysis_prompt_with_context(self, sample_countries_data):
        """Тест создания промпта для прочего сообщения с контекстом"""
        analyzer = OtherAnalyzer(sample_countries_data, "Тестовая Страна")
        message = "Хорошо"
        previous_message = "Ваш приказ выполнен"

        prompt = analyzer.create_analysis_prompt(message, previous_message)

        assert "КОНТЕКСТ:" in prompt
        assert previous_message in prompt


class TestRAGAnalyzerFactory:
    """Тесты для фабрики RAG анализаторов"""

    def test_create_question_analyzer(self, sample_countries_data):
        """Тест создания анализатора вопросов"""
        analyzer = RAGAnalyzerFactory.create_analyzer(
            "вопрос", sample_countries_data, "Тестовая Страна"
        )

        assert isinstance(analyzer, QuestionAnalyzer)
        assert analyzer.sender_country == "Тестовая Страна"
        assert analyzer.countries_data == sample_countries_data

    def test_create_order_analyzer(self, sample_countries_data):
        """Тест создания анализатора приказов"""
        analyzer = RAGAnalyzerFactory.create_analyzer(
            "приказ", sample_countries_data, "Тестовая Страна"
        )

        assert isinstance(analyzer, OrderAnalyzer)

    def test_create_project_analyzer(self, sample_countries_data):
        """Тест создания анализатора проектов"""
        analyzer = RAGAnalyzerFactory.create_analyzer(
            "проект", sample_countries_data, "Тестовая Страна"
        )

        assert isinstance(analyzer, ProjectAnalyzer)

    def test_create_other_analyzer(self, sample_countries_data):
        """Тест создания анализатора прочих сообщений"""
        analyzer = RAGAnalyzerFactory.create_analyzer(
            "иное", sample_countries_data, "Тестовая Страна"
        )

        assert isinstance(analyzer, OtherAnalyzer)

    def test_create_unknown_type_analyzer(self, sample_countries_data):
        """Тест создания анализатора для неизвестного типа"""
        analyzer = RAGAnalyzerFactory.create_analyzer(
            "неизвестный_тип", sample_countries_data, "Тестовая Страна"
        )

        # Должен вернуть OtherAnalyzer по умолчанию
        assert isinstance(analyzer, OtherAnalyzer)
