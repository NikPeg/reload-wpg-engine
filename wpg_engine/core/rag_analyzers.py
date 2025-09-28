"""
Специализированные анализаторы RAG для разных типов сообщений
"""

from abc import ABC, abstractmethod
from typing import Any


class BaseRAGAnalyzer(ABC):
    """Базовый абстрактный класс для RAG анализаторов"""

    def __init__(self, countries_data: list[dict[str, Any]], sender_country: str):
        self.countries_data = countries_data
        self.sender_country = sender_country

    @abstractmethod
    def create_analysis_prompt(
        self, message: str, previous_admin_message: str | None = None
    ) -> str:
        """Создать промпт для анализа сообщения"""
        pass

    def _format_countries_info(self) -> str:
        """Форматировать информацию о странах для промпта"""
        countries_info = ""
        for country in self.countries_data:
            synonyms_str = (
                f" (синонимы: {', '.join(country['synonyms'])})"
                if country["synonyms"]
                else ""
            )

            countries_info += f"""
{country["name"]}{synonyms_str}
Столица: {country["capital"]}
Население: {country["population"]:,}
Аспекты (1-10):
- Экономика: {country["aspects"]["economy"]}{f" - {country['descriptions']['economy']}" if country["descriptions"]["economy"] else ""}
- Военное дело: {country["aspects"]["military"]}{f" - {country['descriptions']['military']}" if country["descriptions"]["military"] else ""}
- Внешняя политика: {country["aspects"]["foreign_policy"]}{f" - {country['descriptions']['foreign_policy']}" if country["descriptions"]["foreign_policy"] else ""}
- Территория: {country["aspects"]["territory"]}{f" - {country['descriptions']['territory']}" if country["descriptions"]["territory"] else ""}
- Технологии: {country["aspects"]["technology"]}{f" - {country['descriptions']['technology']}" if country["descriptions"]["technology"] else ""}
- Религия и культура: {country["aspects"]["religion_culture"]}{f" - {country['descriptions']['religion_culture']}" if country["descriptions"]["religion_culture"] else ""}
- Управление и право: {country["aspects"]["governance_law"]}{f" - {country['descriptions']['governance_law']}" if country["descriptions"]["governance_law"] else ""}
- Строительство и инфраструктура: {country["aspects"]["construction_infrastructure"]}{f" - {country['descriptions']['construction_infrastructure']}" if country["descriptions"]["construction_infrastructure"] else ""}
- Общественные отношения: {country["aspects"]["social_relations"]}{f" - {country['descriptions']['social_relations']}" if country["descriptions"]["social_relations"] else ""}
- Разведка: {country["aspects"]["intelligence"]}{f" - {country['descriptions']['intelligence']}" if country["descriptions"]["intelligence"] else ""}
"""
        return countries_info

    def _format_context_section(self, previous_admin_message: str | None) -> str:
        """Форматировать секцию контекста"""
        if previous_admin_message:
            return f"""
КОНТЕКСТ: Предыдущее сообщение от администратора к этому игроку:
"{previous_admin_message}"

Текущее сообщение игрока может быть ответом на это сообщение администратора.
"""
        return ""


class QuestionAnalyzer(BaseRAGAnalyzer):
    """Анализатор для вопросов игроков"""

    def create_analysis_prompt(
        self, message: str, previous_admin_message: str | None = None
    ) -> str:
        context_section = self._format_context_section(previous_admin_message)
        countries_info = self._format_countries_info()

        return f"""Ты помощник администратора многопользовательской стратегической игры.
{context_section}
Игрок из страны "{self.sender_country}" задал ВОПРОС:
"{message}"

Доступные страны в игре:
{countries_info}

Твоя задача:
1. Проанализировать вопрос игрока{" (учитывая контекст предыдущих сообщений)" if previous_admin_message else ""}
2. Определить, какие страны упоминаются или подразумеваются в вопросе (включая синонимы)
3. Предоставить администратору краткую справку по релевантным странам

Создай краткую справку для администратора, которая поможет ему дать точный ответ на вопрос игрока. Сосредоточься на:
- релевантных аспектах упомянутых стран в контексте вопроса
- фактических данных, которые помогут ответить на вопрос

Отвечай на русском языке. Будь кратким и информативным."""


class OrderAnalyzer(BaseRAGAnalyzer):
    """Анализатор для приказов игроков"""

    def create_analysis_prompt(
        self, message: str, previous_admin_message: str | None = None
    ) -> str:
        context_section = self._format_context_section(previous_admin_message)
        countries_info = self._format_countries_info()

        return f"""Ты помощник администратора многопользовательской стратегической игры.
{context_section}
Игрок из страны "{self.sender_country}" отдал ПРИКАЗ:
"{message}"

Доступные страны в игре:
{countries_info}

Твоя задача:
1. Проанализировать приказ игрока{" (учитывая контекст предыдущих сообщений)" if previous_admin_message else ""}
2. Определить, какие страны упоминаются или подразумеваются в приказе (включая синонимы)
3. Оценить ВЕРОЯТНОСТЬ УСПЕХА приказа (от 0 до 100%)
4. Предоставить администратору краткую справку по релевантным странам

Создай краткую справку для администратора, которая поможет ему принять правильное решение по приказу. Обязательно включи:
- релевантные аспекты упомянутых стран в контексте приказа
- ВЕРОЯТНОСТЬ УСПЕХА (0-100%) с обоснованием
- ключевые факторы, влияющие на успех приказа

Если в приказе упоминаются военные действия, обязательно сравни военную мощь всех задействованных стран.

Отвечай на русском языке. Будь кратким и информативным."""


class ProjectAnalyzer(BaseRAGAnalyzer):
    """Анализатор для проектов игроков"""

    def create_analysis_prompt(
        self, message: str, previous_admin_message: str | None = None
    ) -> str:
        context_section = self._format_context_section(previous_admin_message)
        countries_info = self._format_countries_info()

        return f"""Ты помощник администратора многопользовательской стратегической игры.
{context_section}
Игрок из страны "{self.sender_country}" предложил ПРОЕКТ:
"{message}"

Доступные страны в игре:
{countries_info}

Твоя задача:
1. Проанализировать проект игрока{" (учитывая контекст предыдущих сообщений)" if previous_admin_message else ""}
2. Определить, какие страны упоминаются или подразумеваются в проекте (включая синонимы)
3. Оценить СРОК ИСПОЛНЕНИЯ проекта (в годах)
4. Предоставить администратору краткую справку по релевантным странам

Создай краткую справку для администратора, которая поможет ему принять правильное решение по проекту. Обязательно включи:
- релевантные аспекты упомянутых стран в контексте проекта
- СРОК ИСПОЛНЕНИЯ (в годах) с обоснованием
- ключевые факторы, влияющие на реализацию проекта
- необходимые ресурсы и условия

Если в проекте упоминаются военные действия, обязательно сравни военную мощь всех задействованных стран.

Отвечай на русском языке. Будь кратким и информативным."""


class RAGAnalyzerFactory:
    """Фабрика для создания анализаторов RAG"""

    @staticmethod
    def create_analyzer(
        message_type: str, countries_data: list[dict[str, Any]], sender_country: str
    ) -> BaseRAGAnalyzer:
        """
        Создать анализатор для указанного типа сообщения

        Args:
            message_type: Тип сообщения ("вопрос", "приказ", "проект")
            countries_data: Данные о странах
            sender_country: Страна отправителя

        Returns:
            Соответствующий анализатор

        Raises:
            ValueError: Если тип сообщения не поддерживается
        """
        analyzers = {
            "вопрос": QuestionAnalyzer,
            "приказ": OrderAnalyzer,
            "проект": ProjectAnalyzer,
        }

        if message_type not in analyzers:
            raise ValueError(f"Unsupported message type: {message_type}")

        analyzer_class = analyzers[message_type]
        return analyzer_class(countries_data, sender_country)
