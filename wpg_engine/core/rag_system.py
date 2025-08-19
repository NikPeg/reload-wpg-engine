"""
RAG (Retrieval-Augmented Generation) system for admin assistance
"""

from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wpg_engine.config.settings import settings
from wpg_engine.models import Country


class RAGSystem:
    """RAG system for analyzing player messages and providing context to admin"""

    def __init__(self, db: AsyncSession):
        self.db = db
        # Используем стандартные настройки
        self.api_key = settings.ai.openrouter_api_key
        self.model = settings.ai.default_model

    async def generate_admin_context(
        self, message_content: str, sender_country_name: str, game_id: int
    ) -> str:
        """
        Generate context for admin based on player message

        Args:
            message_content: The player's message
            sender_country_name: Name of sender's country
            game_id: Game ID to get countries data

        Returns:
            Context string for admin
        """
        if not self.api_key:
            return ""

        # Get all countries data from the game
        countries_data = await self._get_all_countries_data(game_id)

        if not countries_data:
            return ""

        # Create prompt for LLM analysis
        prompt = self._create_analysis_prompt(
            message_content, sender_country_name, countries_data
        )

        try:
            # Get analysis from LLM
            context = await self._call_openrouter_api(prompt)
            return context
        except Exception as e:
            print(f"Error calling AI API: {e}")
            return ""

    async def _get_all_countries_data(self, game_id: int) -> list[dict[str, Any]]:
        """Get data for all countries in the game"""
        result = await self.db.execute(
            select(Country).where(Country.game_id == game_id)
        )
        countries = result.scalars().all()

        countries_data = []
        for country in countries:
            aspects = country.get_aspects()

            country_info = {
                "name": country.name,
                "capital": country.capital or "Не указана",
                "population": country.population or 0,
                "synonyms": country.synonyms or [],
                "aspects": {
                    "economy": aspects["economy"]["value"],
                    "military": aspects["military"]["value"],
                    "foreign_policy": aspects["foreign_policy"]["value"],
                    "territory": aspects["territory"]["value"],
                    "technology": aspects["technology"]["value"],
                    "religion_culture": aspects["religion_culture"]["value"],
                    "governance_law": aspects["governance_law"]["value"],
                    "construction_infrastructure": aspects[
                        "construction_infrastructure"
                    ]["value"],
                    "social_relations": aspects["social_relations"]["value"],
                    "intelligence": aspects["intelligence"]["value"],
                },
                "descriptions": {
                    "economy": aspects["economy"]["description"],
                    "military": aspects["military"]["description"],
                    "foreign_policy": aspects["foreign_policy"]["description"],
                    "territory": aspects["territory"]["description"],
                    "technology": aspects["technology"]["description"],
                    "religion_culture": aspects["religion_culture"]["description"],
                    "governance_law": aspects["governance_law"]["description"],
                    "construction_infrastructure": aspects[
                        "construction_infrastructure"
                    ]["description"],
                    "social_relations": aspects["social_relations"]["description"],
                    "intelligence": aspects["intelligence"]["description"],
                },
            }
            countries_data.append(country_info)

        return countries_data

    def _create_analysis_prompt(
        self, message: str, sender_country: str, countries_data: list[dict[str, Any]]
    ) -> str:
        """Create prompt for LLM analysis"""

        # Format countries data for the prompt
        countries_info = ""
        for country in countries_data:
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
- Экономика: {country["aspects"]["economy"]}
- Военное дело: {country["aspects"]["military"]}
- Внешняя политика: {country["aspects"]["foreign_policy"]}
- Территория: {country["aspects"]["territory"]}
- Технологии: {country["aspects"]["technology"]}
- Религия и культура: {country["aspects"]["religion_culture"]}
- Управление и право: {country["aspects"]["governance_law"]}
- Строительство и инфраструктура: {country["aspects"]["construction_infrastructure"]}
- Общественные отношения: {country["aspects"]["social_relations"]}
- Разведка: {country["aspects"]["intelligence"]}
"""

        prompt = f"""Ты помощник администратора многопользовательской стратегической игры.

Игрок из страны "{sender_country}" отправил сообщение:
"{message}"

Доступные страны в игре:
{countries_info}

Твоя задача:
1. Проанализировать сообщение игрока
2. Определить, какие страны упоминаются или подразумеваются в сообщении (включая синонимы)
3. Предоставить администратору краткую справку по релевантным странам

Создай краткую справку для администратора, которая поможет ему принять правильное решение. Сосредоточься на:
- релевантных упомянутых стран аспектах в контексте сообщения

Если в сообщении упоминаются военные действия, обязательно сравни военную мощь всех задействованных стран.

Отвечай на русском языке. Начни ответ с "📊 RAG-справка:" и будь кратким и информативным."""

        return prompt

    async def _call_openrouter_api(self, prompt: str) -> str:
        """Call OpenRouter API"""
        url = "https://openrouter.ai/api/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        data = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1000,  # Увеличено для более полных ответов
            "temperature": 0.3,  # Низкая температура для более точных ответов
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=data, headers=headers)
            response.raise_for_status()

            result = response.json()
            return result["choices"][0]["message"]["content"].strip()
